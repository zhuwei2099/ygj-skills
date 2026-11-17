# 价目表域：收费组合 / 收费项目（基础字典）

> 适用：导出**某门店的收费组合（组合名称 / 总价格 / 明细）**、查收费项目（单价 / 单位 / 技耗分类）。
> 工具：`basedatas_list_charge_combs`（收费组合）· `basedatas_list_charge_items`（收费项目）。
> 均为**门店级**（必填 `clinicId`），同一套配置各店独立 —— 逐店拉，禁单店代表全公司。

## 一、入参

| 工具 | 必填 | 可选 | 分页 |
| --- | --- | --- | --- |
| `basedatas_list_charge_combs` | `clinicId` | `keyword`（名称 / 编码模糊）、`status`（`0`=启用**默认** / `1`=禁用）、`current`、`size` | 默认 **10**，上限 **100** |
| `basedatas_list_charge_items` | `clinicId` | `keyword`（编码 / 名称 / 拼音）、`status`（不传=全部）、`current`、`size` | 默认 **10**，上限 **100** |

- 只查「已启用」时**显式传 `status=0`**；不传即默认启用，但显式更稳。
- 禁用组合可另跑一次 `status=1` 作对照（宣武门店实测：启用 **301** / 禁用 **25**）。

## 二、出参：组合是**嵌套结构**（下拉返回，无需再查明细接口）

`data.records[]` = 组合；每个组合自带 `items[]` = 明细行。**导出组合明细只需这一支工具**。

组合级字段：`id` · `clinicId` · `name` · `code` · `parentId`/`parentName` · `sort` · `price` · `mainItemId` · `pinyin` · `remark` · `warrantyDesc` · `status`/`statusLabel` · `items[]`

明细级字段（16 个）：

| 字段 | 含义 | 备注 |
| --- | --- | --- |
| `combStepName` | 组合步骤名 | **可能全部为空**（宣武门店 1484/1484 为空 ⇒ 该店组合无步骤概念，不要预设一定有步骤） |
| `itemId` / `itemCode` / `itemName` / `itemPinyin` | 收费项目主键 / 编码 / 名称 / 拼音 | |
| `isMainItem` | **主项目**标记（`int`，`1`=是 / `0`=否） | 门店配置事实，**可能整单全 0**（未勾选主项目） |
| `unit` | 单位 | 可能为空串 |
| `chargeType` | **技耗分类** | schema `title` 就是「技耗分类」；实测取值：治疗费 / 专用耗材费 / 检查费 / 手术费 / 基础耗材费 |
| `marketPrice` | 市场价 | 常为空 |
| `price` | 单价（**字符串**） | |
| `count` | 数量（**int**） | |
| `amount` | 金额（**字符串**） | = `price × count` |
| `pricingInfo` | **计价说明** | 医保 / 物价长文本，常含换行；部分行自带 `&quot;` 等 HTML 实体残留 |
| `sort` | 行内排序 | 用 `sort` 排，别依赖返回顺序 |

> 类型不统一：`price`/`amount`/`marketPrice` 是**字符串**，`count`/`isMainItem` 是 **int**。
> 取值一律 `r.get()`（服务端按行省略 `null` 键），判「空」要区分**键缺席**与**空串** —— 本域实测键全在、值为空串。

## 三、字段映射：要出的 10 列怎么取

| 输出列 | 取数 |
| --- | --- |
| 组合名称 | `comb.name` |
| 总价格 | `comb.price`（组合挂牌总价，**不是成交价**） |
| 项目名称 | `items[].itemName` |
| 主项目 | `items[].isMainItem` → 是 / 否 |
| 单位 | `items[].unit` |
| 技耗分类 | `items[].chargeType` |
| 单价 | `items[].price` |
| 数量 | `items[].count` |
| 金额 | `items[].amount` |
| 计价说明 | `items[].pricingInfo` |

## 四、🚨 四个实测坑（导出前必查）

1. **`code` 可能全空** —— 宣武门店 301 / 301 个组合编码为空 ⇒ **不能用编码当唯一键**，只能用 `id`（实测 `id` 唯一）。
2. **组合名称会重名** —— 宣武门店 9 组重名（最多一组同名 9 个，价格从 5,751 到 26,088）。只按名称筛会把不同组合混在一起；输出必须附 `id` 或序号，并在报告里显式提示重名组。
3. **`isMainItem` 可能整单无 1** —— 宣武门店 169 / 301 个组合未勾选主项目（不是导出错误，是源系统配置缺失）。**不要把「每组合必有 1 个主项目」当作勾稽条件去判 fail**。
4. **`unit` / `chargeType` 可能为空串** —— 宣武门店 6 行缺单位、2 行缺技耗分类。属源数据缺口，报告如实列示、**不得编造填补**。

## 五、勾稽（导出组合明细时逐组合做）

| 编号 | 条件 | 说明 |
| --- | --- | --- |
| C1 | 组合数 = 组合清单行数 | |
| C2 | 明细行数 = Σ各组合明细行数 | |
| C3 | 无空组合（每组合 ≥1 明细） | 只有空组合才 warn |
| C4 | `comb.price` = Σ`items[].amount` | 实测宣武门店 301/301 全等 |
| C5 | 每组合 `isMainItem=1` 的行 **≤1** | 只判「多于 1」；等于 0 记 warn（见坑 3） |
| C6 | `items[].amount = price × count` | 逐行 |

## 六、现成脚本

✅ **技能内置（优先）**：`$SKILL/scripts/export_clinic_charge_combs.py`

```bash
python export_clinic_charge_combs.py --store 宣武门店          # 按门店名（白名单内模糊匹配，命中多家则列候选并退出）
python export_clinic_charge_combs.py --clinic-id 8888000000000067
python export_clinic_charge_combs.py --store 宣武门店 --include-disabled
```

完整流程 / 输出规格 / C1–C13 勾稽见 [export-clinic-charge-combs.md](export-clinic-charge-combs.md)。

产三件套：`<门店>_已启用收费组合及明细_YYYYMMDD.xlsx`（`组合明细` 指定 10 列 / `组合清单` 含组合ID+勾稽 / `说明` 含字段映射+C1–C13 校验）、同名 `.csv`（10 列平铺）、`_raw.json`（原始报文 + 展开行）。

⚪ 工作区另有一份等效副本 `$WS/scripts/ygj_charge_combs_export.py`（实测 `rows` 逐行一致），仅供历史复现，**不要用它替代技能内置版**。
