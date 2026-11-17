# 子能力 `export-clinic-charge-combs`：导出门店收费组合及明细

> **一句话**：把**某一家门店**当前启用的**收费组合**连同**每个组合下的明细项目**，展平成 10 列清单（xlsx + csv + 原始报文），并出组合级勾稽。
>
> **命中触发**：导出/列出某门店的收费组合、套餐、组合项目、组合明细、价目表组合；问「XX 门店有哪些套餐 / 组合包含了哪些项目 / 组合总价怎么构成」。
>
> **不适用**：算成交金额 / 营业额（→ [revenue-and-deal-count.md](revenue-and-deal-count.md)）· 按二级分类统计项目数量（→ [label-level-rules.md](label-level-rules.md)）· 只查单项收费项目单价（→ [price-list-and-combos.md](price-list-and-combos.md) §二）。

---

## 一、六步固定流程（不可跳步、不可换序）

| # | 步骤 | 要点 |
| --- | --- | --- |
| 1 | **门店定位（闸门）** | `employees_list_work_clinic`（无参）取白名单 → 按门店名/`clinicId` 定位。**`clinicId` 必须来自本次调用**，禁外部来源、禁历史缓存 |
| 2 | **取组合** | `basedatas_list_charge_combs`，`status=0`，`size=100` 翻页全量 |
| 3 | **展平** | 组合 × `items[]` → 10 列平铺行；**组合内按 `items[].sort` 排序**，不依赖返回顺序 |
| 4 | **勾稽** | C1–C13 **三态**：`ok` 通过 / `warn` 源数据缺口 / `fail` 口径不一致 |
| 5 | **输出** | xlsx（`组合明细` / `组合清单` / `说明`）+ 同名 csv + `_raw.json` |
| 6 | **报缺口** | 空编码、重名、无主项目、空单位/分类等**如实列示，不编造填补** |

## 二、门店定位：同名门店必须列候选，不替用户选

白名单里**门店名会撞车**。实测「宣武」命中 2 家：

| 门店 | clinicId | 状态 | 启用组合 |
| --- | --- | --- | --- |
| **宣武门店** | `8888000000000067` | 营业中 | 301 |
| 北京宣武门体检店 | `34625225207565940` | 已撤店 | 0 |

同名时**不要按「看起来对」挑一个**。若两家都有数据，把候选（`clinicId` / 简称 / 状态 / 组合数）列给用户选；若只有一家有数据（`total>0`），取之并**显式说明另一家为 0 / 已撤店**。
匹配优先级：`abbreviation` → `clinicName` → `oaOrgName`；先精确相等，再子串模糊。细节见 [clinic-and-staff-lookup.md](clinic-and-staff-lookup.md)。

## 三、取数契约

| 项 | 值 |
| --- | --- |
| 工具 | `basedatas_list_charge_combs` |
| 必填入参 | `clinicId` |
| 可选入参 | `search`（名称/编码模糊）· `status`（`0`=启用 **默认** / `1`=禁用）· `current` · `size` |
| 分页 | 默认 10，**上限 100**；终止条件 = 本页为空 或 `current >= pages` |
| 返回形态 | `data.records[]` = 组合，**每个组合自带 `items[]` 明细** |

🚨 **组合是嵌套返回 —— 导出组合明细只需这一支工具，不要再去找「组合明细接口」**。字段全表见 [price-list-and-combos.md](price-list-and-combos.md) §二。

## 四、10 列字段映射（唯一输出口径，顺序固定）

| 输出列 | 服务端字段 | 说明 |
| --- | --- | --- |
| 组合名称 | `comb.name` | 逐行重复 |
| 总价格 | `comb.price` | **组合挂牌总价，不是成交价** |
| 项目名称 | `items[].itemName` | |
| 主项目 | `items[].isMainItem` | `1`→「是」/ `0`→「否」/ 缺失→空 |
| 单位 | `items[].unit` | 可能空串 |
| 技耗分类 | `items[].chargeType` | schema `title` 原文就叫「技耗分类」 |
| 单价 | `items[].price` | **字符串** |
| 数量 | `items[].count` | **int** |
| 金额 | `items[].amount` | = 单价 × 数量 |
| 计价说明 | `items[].pricingInfo` | 长文本，可含换行 / HTML 实体残留 |

类型不统一是**服务端事实**：`price` / `amount` / `marketPrice` 是字符串，`count` / `isMainItem` 是 int。取值一律 `.get()`（服务端按行省略 `null` 键）。

## 五、展平与关联规则

- 一行 = 一个组合 × 一条明细；**同一组合的多条明细连续排列**，`组合名称` 与 `总价格` 逐行重复。
- 行顺序 = `items[].sort`（**不要用返回顺序**；`sort` 非 int 时兜底 9999 保持稳定）。
- 组合与《组合清单》通过**「序号」**一一对应；xlsx 主表用交替底色分区、`freeze_panes=A2`、开启筛选。
- **不要硬编码「每组合必有步骤」**：`combStepName` 可能整店全空（宣武门店 1484/1484 为空）。

## 六、勾稽（三态，逐组合 + 逐行）

| 编号 | 条件 | 不满足时 |
| --- | --- | --- |
| C1 | 组合数 = 组合清单行数 | `fail` |
| C2 | 明细行数 = Σ各组合明细行数 | `fail` |
| C3 | 每个组合都有明细（无空组合） | `warn` |
| C4 | `comb.price` = Σ`items[].amount`（逐组合） | `fail` ← **核心口径校验** |
| C5 | 每组合 `isMainItem=1` 的行 **≤1** | `fail`（**判「多于 1」**，等于 0 走 C12 warn） |
| C6 | `items[].amount` = `price × count`（逐行） | `fail` |
| C7 | 项目名称无空值 | `warn` |
| C8 | 单位无空值 | `warn` |
| C9 | 技耗分类无空值 | `warn` |
| C10 | 组合名称可唯一定位（无重名） | `warn` |
| C11 | 组合编码非空 | `warn` |
| C12 | 无主项目标记的组合 | `warn` |
| C13 | 计价说明无 HTML 实体残留 | `warn` |

> **三态的意义**：C8–C13 全是**源系统配置缺口**，不是导出错误。一律 `warn` 并列明「哪几行缺什么」，**绝不能因为 warn 就编数据补齐，也不能报成 fail 说导出失败**。

## 七、🚨 四个实测坑（导出前必查）

1. **`code` 可能全空** —— 宣武门店 301/301 组合编码为空 ⇒ **唯一键只能用 `id`**。主表不含 ID，故《组合清单》必须带「组合ID」列。
2. **组合名称会重名** —— 宣武门店 9 组重名（最多一组同名 9 个，价格 5,751～26,088）⇒ **「组合名称」不能当唯一键**，输出必须提示重名组。
3. **`isMainItem` 可能整单无 1** —— 宣武门店 169/301 个组合未勾选主项目 ⇒ 不要把「每组合必有 1 个主项目」当 `fail` 判据。
4. **`unit` / `chargeType` 可能为空串** —— 属源数据缺口，如实列示并建议在 HIS 后台补配。

## 八、脚本

```bash
# 技能内置（推荐）：$SKILL/scripts/
python export_clinic_charge_combs.py --store 宣武门店
python export_clinic_charge_combs.py --clinic-id 8888000000000067
python export_clinic_charge_combs.py --store 宣武门店 --include-disabled --out-dir D:/tmp
```

| 参数 | 说明 |
| --- | --- |
| `--store` | 门店名（简称 / 诊所名 / 组织名，可模糊）；命中多家时列候选并退出（exit 2） |
| `--clinic-id` | 直接指定（须在本次白名单内，否则拒绝取数） |
| `--include-disabled` | 并入禁用组合，输出改为「全部收费组合」；不加则只取启用（禁用数作对照打印） |
| `--out-dir` | 输出目录，默认客户端所在工作区的 `outputs/` |
| `--tag` | 文件名日期标记，默认今天 `YYYYMMDD` |

**依赖解析**：脚本按 `YGJ_CLIENT_DIR` 环境变量 → 技能 `scripts/` → 同机工作区 → 工作区默认位 的顺序查找 `ygj_client.py`（凭证 `~/.workbuddy/ygj-mcp-prod-credentials.json` 需同时就位）。找不到会明确报错并提示设 `YGJ_CLIENT_DIR`。

**产物命名**：`<门店>_已启用收费组合及明细_<tag>.xlsx / .csv / _raw.json`（并入禁用时前缀变「全部收费组合」）。

| 文件 | 内容 |
| --- | --- |
| `.xlsx` `组合明细` | **严格 10 列**，按组合分区、冻结首行、可筛选 |
| `.xlsx` `组合清单` | 组合级：序号 / 组合名称 / **组合ID** / 明细行数 / 总价格 / Σ明细金额 / **差额** / 主项目 / 重名提示 / 状态 |
| `.xlsx` `说明` | 字段映射、关联方式、唯一键提示、字段分布、C1–C13 校验结果 |
| `.csv` | 10 列平铺同顺序，供程序化使用 |
| `_raw.json` | 原始报文 + 展开行 + 组合元信息 + 勾稽，可复核 |

## 九、实测锚点（复核用，引用前重测）

2026-10-16 · 宣武门店 `8888000000000067`（刘萍分部 / 营业中）
启用组合 **301**（禁用 25 对照）· 明细 **1484** 行 · C1–C7 全绿（**C4 301/301 全等**）
技耗分类：治疗费 649 / 专用耗材费 574 / 检查费 151 / 手术费 105 / 基础耗材费 3 / 空 2
缺口：空编码 301、重名 9 组 36 个、无主项目 169、空单位 6 行、空分类 2 行、实体残留 188 行

## 十、相关

- 字段契约 / 价目表域全貌 → [price-list-and-combos.md](price-list-and-combos.md)
- 门店名匹配、白名单、同组织多门店合并 → [clinic-and-staff-lookup.md](clinic-and-staff-lookup.md)
- 否定结论举证纪律（"取不到"≠"不存在"） → [verification-discipline.md](verification-discipline.md)
- 版本沿革 → [changelog.md](changelog.md)
