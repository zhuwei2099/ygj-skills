---
name: ygj-dental-business-mcp
description: 通过 ygj-dental-business-mcp 接口查询蓝莓象（HIS 系统）数据，覆盖患者、预约、咨询、影像、病历、收费、收费组合（套餐/组合明细/价目表/技耗分类/组合标价）、卡券、会员与积分、回访、复诊、门店、企业微信客户与群（新增好友/好友标签 `records[].tags`/按标签筛选好友）、小程序 SCRM、业务字典等模块，以及营业额、成交人数等经营指标的取数口径；另含 2 支标签写工具（患者标签增删 / 企微好友标签增删），除打标签外全部只读。当用户提到蓝莓象、HIS、查询患者、预约、咨询、影像、病历、收费、收费组合、套餐、组合明细、价目表、导出组合、卡券、优惠券、核销、会员、积分、回访、复诊、门店、企业微信客户与群、企微新增好友、好友标签、按标签筛选好友、小程序账号、企业微信聊天信息、给患者打标签、给企微好友打标签、新增标签、删除标签、标签维护等操作时使用本技能。
version: 2026.11.13.3
skill下载地址: http://git.ygjkq.com:18000/ai/blueberry-dental-skills.git
---

# ygj-dental-business-mcp 接口

通过 `ygj-dental-business-mcp` 这个口腔业务 MCP，从「接通」用到「取到数据」。

**环境：生产** `https://api-chishu.lifesega.com/v1/mcp`｜**共 47 个工具**｜其中 **45 个只读明细 / 列表查询**、**2 个写工具（打标签）**，**没有任何聚合、报表工具** —— 统计口径一律靠明细求和。

> 工具清单基线：**2026-11-13** 实测 `tools/list`。较 2026-10-31 版新增 **2 个写工具**：`patients_incremental_submit_labels`（患者标签增删）、`wecom_externalcontact_mark_tag`（企微好友标签增删，好友已关联患者时**同步改患者标签**）—— 见 §B2 七 与 [references/label-write.md](references/label-write.md)。卡券 / 会员 / 积分 / SCRM 四域见 [references/coupon-member-point.md](references/coupon-member-point.md)。
>
> ⚠️ **「全部只读」已作废**（2026-11-13 起）：新增两支写工具，调用前必读铁律 14。写路径本次**只核对了 `tools/list` schema，未实际执行**（避免污染生产数据）。
>
> 🚫 **已剔除旧名 `appoints_list`**：服务端 `tools/list` 仍会返回它（与 `clinics_list_appoints` schema 逐字一致），但它是**已废除的旧名**，本技能**不收录、不使用**；门店预约一律用 `clinics_list_appoints`。计数 47 = 服务端 48 − 该旧名。

## 全局铁律

1. **能力边界优先。** 先判断问题是否在当前能力范围内，再选工具。**不许试错式调用。**
2. **不填越权参数。** `Blade-TenantId` / `Blade-AccountId` 任何情况下都不填 —— 租户与账号只能由服务端按 token 推导，填了等于越权。新增的卡券 / 会员 / 积分工具同样适用；这些工具**响应里会回显 `tenantId`**（如 `patients_point_account`），该字段只用于展示与自查，**禁止回填请求头或下次调用参数**。
3. **不主动外发患者影像链接与线上标识。** `imageUrl` 是隐私裸链；文书类影像（知情同意书、病历申请单）不做主动汇总。`scrm_get_user` 返回的 `wxUnionId` / `wxOpenId` 与 `account` 按同级隐私处理；`patients_list_coupons` 的 `allowedClinicNames` / `allowedClinicIds` 是长列表，**按最小必要摘取，不整段外发**。
4. **验证不通过不要反复重试。** 先把证据落下来，立刻反馈用户确认。
5. **读 schema 说明用双口径：`description` 或 `title` 任一非空就算「有说明」。** 本服务端把中文字段名写在 `title` 里 —— **只读 `description` 会误判出一堆「黑盒参数」**。判定「某参数没说明」前，必须两个字段都看过。
6. **分清「工具不存在」与「工具未授权」（两种错误码，含义相反）。**
   - `[MCP-PARAM-001] Unknown or unpublished Tool` = **真不存在 / 未发布**（**任何编造的名字都报这个**）。
   - `[MCP-AUTH-002] Account is not authorized for Tool <name>` = **工具已注册，只是当前账号无权调用** → 正确处理是**找服务端 / 研发开授权**，**绝不能答复「功能没有 / 接口没做」**。
   - ⚠️ **判定「是否存在」必须比对「码 + 消息文本」，不能只比码**：`MCP-PARAM-001` 是**参数 / 请求层通用码**，至少有 4 种消息 —— `Unknown or unpublished Tool` / `缺少必填字段，路径 /X` / `未声明字段，路径 /X` / `类型应为<类型>，路径 /X`。**只有第一种**能推出「工具不存在」。
   - 判定方法：拿一个明知不存在的名字（如 `zzz_not_exist`）做基线对照，**比对完整消息文本**，而不是比对错误码。
7. **取数范围默认收敛到「我的工作门店」，越权一律拒绝。** 白名单、默认单店、跨店与 fail-closed 细则见 §B3。
8. **字段表述用中文 `title`。** 面向用户输出字段名一律用服务端 schema 的 `title`（中文字段名，如「实收金额」「交易时间」），**不用英文 code**（如 `payAmount`、`optDateTime`）；调用入参仍用英文字段名（API 只认 code）。
9. **收入取数只走交易接口。** 收入相关场景一律用 `*_bill_docs`，**禁用账单接口** `clinics_list_bills` / `patients_list_bills`。见 §B3。
10. **数量与金额的聚合范围不同，不能互相推导。** 数量只认主项目行、金额计全行；两者符号也不必然一致。按 labelLevel 分类统计时见 [label-level-rules.md](references/label-level-rules.md)。
11. **「取不到数 / 全 0」是时刻属性，不是接口属性。** 结论必须带核对时刻，**复用前必须重新实测**；跨店一致为空只证明「此刻该域无数据」，不能写成永久属性。
12. **否定结论必须举证。** 「schema 声明」≠「运行时返回」；服务端**按行省略取值为 `null` 的键** ⇒ **「键缺席」≠「字段不存在」**。判存在走三步法（看声明 → 看运行时 → 找对照样本）；拿不出「该有值的场景下也没有」的证据，只能写「本次样本未出现，未验证」。
13. **官方文档给的是「口径」不是「事实」。** 凡可实测的断言，落进技能前必须复测；文档与实测冲突时**保留两者并标注以实测为准**。
    → 11–13 的案例、三步法细节与判定三分见 [references/verification-discipline.md](references/verification-discipline.md)。
14. **写工具只有「打标签」两支，默认不执行。** `patients_incremental_submit_labels` / `wecom_externalcontact_mark_tag` 是**全库仅有的写操作**（其余 45 个只读）。① **必须用户明确要求才调用** —— 问「能不能打标签」只答能力、不动数据；② 写前把**目标对象 + 标签中文名 + 增/删集合**列给用户确认；③ `addLabelIds` / `deleteLabelIds` **至少一侧非空**，空数组 = 该侧无操作、**不是「清空全部标签」**；④ **禁止批量遍历写**，一次一对象；⑤ `wecom_externalcontact_mark_tag` 在好友**已关联患者**时会**同步改患者标签**（跨对象副作用），写前必须告知；⑥ 写后**回读复核**（`patients_list_labels` / `wecom_list_friends`），不得只凭返回码宣称成功。详见 [references/label-write.md](references/label-write.md)。

## 路径约定（读任何命令前先看这段）

**`$SKILL` 在各 Agent 的落点不同**（技能本体在跨 Agent 共享位 `~/.agents/skills/ygj-dental-business-mcp`，各端按下表解析）：

| Agent | `$SKILL` |
| --- | --- |
| WorkBuddy | `%USERPROFILE%\.workbuddy\skills\ygj-dental-business-mcp`（**目录联接**到共享位） |
| Hermes | `%LOCALAPPDATA%\hermes\skills\ygj-dental-business-mcp` |
| OpenClaw | `~/.openclaw/skills/ygj-dental-business-mcp` |
| 共享位（源） | `~/.agents/skills/ygj-dental-business-mcp` |

`$SKILL/scripts/` 目前内置一支可执行脚本：`export_clinic_charge_combs.py`（子能力 `export-clinic-charge-combs`，见 [references/export-clinic-charge-combs.md](references/export-clinic-charge-combs.md)）。它依赖 `ygj_client.py`，按 `YGJ_CLIENT_DIR` → 技能 `scripts/` → 同机工作区 → 工作区默认位 的顺序解析，**不必手工拷客户端**。

## 第一步：模式路由

每次先判这里，再进正文。

| 用户意图 | 模式 | 去处 |
| --- | --- | --- |
| 接入 / 安装 / 配 MCP / 换端点 / 更新凭据 / 分享给同事 / 断了要重配 | **A 接入** | §A |
| 问业务数据怎么查，或直接问某个指标 | **B 查询** | §B |

## 什么时候去读 references/

正文只保留「选工具 + 填参数 + 避坑」。**统计口径是场景性知识**，命中下表才读对应文件，不要预先加载。

| 什么时候读 | 文件 |
| --- | --- |
| 要下「取不到 / 不存在 / 全 0 / 没这个字段」这类否定结论，或把实测结论写进交付 | [references/verification-discipline.md](references/verification-discipline.md) |
| 算营业额 / 交易实收 / 成交人数 / 体检人数，或需要区分支付分类；**或出「某分部 / 大区 / 负责人的门店业绩」** | [references/revenue-and-deal-count.md](references/revenue-and-deal-count.md)（§五 分部级业绩出数流程） |
| **导出某门店的收费组合及明细清单**（10 列 / xlsx+csv+原始报文三件套 / C1–C13 勾稽），或问「某店有哪些套餐、组合里包含哪些项目」 | [references/export-clinic-charge-combs.md](references/export-clinic-charge-combs.md)（子能力 `export-clinic-charge-combs`，含内置脚本） |
| 查**收费组合 / 收费项目**的字段契约（单价 / 单位 / 技耗分类 / 组合标价怎么来的、类型与空值坑） | [references/price-list-and-combos.md](references/price-list-and-combos.md) |
| 按 `labelLevel1` / `labelLevel2` 分类统计项目数量与金额 | [references/label-level-rules.md](references/label-level-rules.md) |
| 把交易明细还原成治疗组、按患者汇总金额、互补副本合并、勾稽校验 | [references/combo-transaction-by-patient.md](references/combo-transaction-by-patient.md) |
| 业绩 1 级 / 2 级标签分类，或按门店（`oaOrgId`）汇总指标 | [references/business-category-and-store-summary.md](references/business-category-and-store-summary.md) |
| 看白名单字段、按名称找门店、同组织多门店合并、**分部 / 大区（`divisionalId`）划分** | [references/clinic-and-staff-lookup.md](references/clinic-and-staff-lookup.md) |
| 查卡券发放 / 核销 / 操作流水、会员卡与会员身份、积分账户与流水、小程序账号；或需要区分「分页对象 / 裸数组 / 单对象」三种返回形态 | [references/coupon-member-point.md](references/coupon-member-point.md) |
| **统计某门店某时段新增企微好友数、按好友标签（`records[].tags`）分组或筛选、按添加员工统计**，或问「标签怎么取」「怎么按标签筛好友」 | [references/wecom-friends-and-labels.md](references/wecom-friends-and-labels.md) |
| **给患者 / 企微好友打标签、删标签**，或要核对标签写入的前置条件、标签 ID 来源、企微写→患者标签联动、写后回读 | [references/label-write.md](references/label-write.md) |
| 追溯作废口径、历史样本数字、版本沿革、与共享位副本的差异 | [references/changelog.md](references/changelog.md) |

## §A 模式：接入

把 MCP 接到用户当前使用的 Agent 上，**验证到「能取到真实业务数据」为止**。

### A1 确认参数

如果用户没有配置 MCP，参考以下客户端连接信息初始化配置。

```json
{
  "name": "ygj-dental-business-mcp",
  "transport": {
    "type": "streamable-http",
    "url": "https://api-chishu.lifesega.com/v1/mcp",
    "protocolVersion": "2024-11-05"
  },
  "authentication": {
    "type": "oauth2",
    "extension": "io.modelcontextprotocol/oauth-client-credentials",
    "grantType": "client_credentials",
    "tokenEndpoint": "https://api-chishu.lifesega.com/oauth2/token",
    "tokenEndpointAuthMethod": "client_secret_basic",
    "clientId": "<填写 MCP 账号的 appKey>",
    "clientSecret": "<填写创建或轮换时领取的 appSecret>",
    "scope": "mcp.invoke",
    "resource": "https://api-chishu.lifesega.com/v1/mcp"
  },
  "tokenUsage": {
    "type": "Bearer",
    "refresh": "在过期前或收到 HTTP 401 后重新获取一次"
  }
}
```

#### A1-1 用户凭证（示例）

```
APP_KEY=mcp_ak_********************-8hwO_FFN
APP_SECRET=mcp_sk_l2Y4PK-********************-********************-w
```

本机无凭据文件时索取。落在 `~/.config/ygj-dental-business-mcp-credentials.json`；**不进配置文件、不回显**

### A2 写配置

| Agent | 写法 |
| --- | --- |
| WorkBuddy | 改 `~/.workbuddy/mcp.json` 的 `mcpServers` |
| Hermes | **优先用 CLI**：`hermes mcp add <name> --url "<endpoint>" --auth header`。手改 YAML 极易缩进出错 |
| OpenClaw | 改 `~/.openclaw/openclaw.json` 的 `nodeHost.mcp.servers`（JSON5，注意尾逗号合法性） |
| 其他 | 读取 Agent 的配置指南，根据指南配置 MCP |

**一次只接一个 Agent。** 用户要接哪个就接哪个，不要批量写入。
**写完立即校验文件语法**（JSON / YAML / JSON5 解析），别等 Agent 报错。

## §B 模式：业务查询

把业务问题翻译成「调哪个工具、参数怎么填、结果怎么读、哪些坑必须避开」。

### B1 先判能力边界

**MCP 工具以明细查询为主**（46 只读 + 2 支标签写工具），查询分两条主路径：**患者维度**（`patientId` 入口）与**门店维度**（`clinicId` 入口）；患者检索入口有两条：**`patients_list`**（按时段 / 条件列患者）与 **`patients_quick_search`**（按姓名 / 手机号 / 病历号快速搜）。

| 用户问的是 | 能否回答 | 怎么做 |
| --- | --- | --- |
| 某个患者的预约 / 咨询 / 影像 / 病历 / 收费 / 回访 / 复诊明细 | ✅ | `patients_list_*` 8 个，**必须**先拿到 `patientId` |
| 按姓名 / 手机号 / 病历号快速找患者 | ✅ | `patients_quick_search`（必填 `clinicId` + `search`，同词字段并集、多词交集） |
| 某患者的完整档案 | ✅ | `patients_get_details`（必填 `patientId`） |
| 当前账号可见哪些门店 / **本次能查哪些门店（授权边界 + 默认范围）** | ✅ | `employees_list_work_clinic`（无参，可直接调）。**后续所有 `clinicId` 入参只能从这里取**；默认只查归属诊所 |
| 某门店某时段的预约 / 咨询 / 影像 / 病历 / 回访 / 复诊 / 体检登记 | ✅ | `clinics_list_appoints`（预约）+ `clinics_list_*` 8 个，**必填 `clinicId`** |
| 患者标签体系（门店可用的标签定义） | ✅ | `basedatas_list_label_definitions`（必填 `clinicId`） |
| 某患者已打上的标签 | ✅ | `patients_list_labels`（必填 `patientId`）；与标签定义不是一回事 |
| 给患者 / 企微好友**新增或删除标签** | ⚠️ **可写** | 全库仅 2 支写工具：`patients_incremental_submit_labels`（`patientId`）、`wecom_externalcontact_mark_tag`（`wecomExternalUserId`）。**须用户显式要求**，走铁律 14 与 §B2 七 |
| 业务字典 / 编码 | ✅ | 字典域 6 个（见 §B2 五） |
| 某门店某时段的**卡券发放 / 核销 / 操作流水** | ✅ | 发放 `clinics_list_coupon_sale_records`、核销 `clinics_list_coupon_consume_records`、操作记录 `clinics_list_coupon_records`；均必填门店 + 日期区间（≤3 个月） |
| 某门店的**会员开卡 / 续费 / 到期**清单 | ✅ | `clinics_list_members`（必填 `clinicId` + `dateType` + 日期区间） |
| 某患者的**会员卡、持券、积分余额与流水** | ✅ | `patients_list_memberships` / `patients_list_coupons` / `patients_point_account` + `patients_list_point_logs`，均必填 `patientId` |
| 某患者的**小程序（SCRM）账号** | ✅ | `scrm_get_user`（必填 `scrmUserId`，取自患者档案；空串表示未注册） |
| 某门店某日 / 某时段的营业额（实收） | ✅ | **收入相关场景一律用交易接口**：门店维度 `clinics_list_bill_docs`（按**交易时间** `optDateTime`）→ `sum(payAmount)` 即**净实收**（退费已以**负数行**计入，不必再扣）；患者维度 `patients_list_bill_docs` 同理 |
| 直接给出「上月营业额 / 新患者数 / 复诊率」等聚合报表 | ❌ | **没有聚合、报表工具**；只能在明细上自行求和。写能力**仅限打标签**。口径见 §B3 与 references |

### B2 工具速查（按模块 · 47 个）

参数名以代码标注，**调用时一律用英文字段名**；命名统一为 `<域>_<动作>` 风格。

| 模块 | 工具数 | 入口参数 | 备注 |
| --- | --- | --- | --- |
| 患者维度 | 17 | `patientId` / `clinicId` | 2 个检索入口（`patients_list` / `patients_quick_search`）+ 15 个患者主档 / 子表，**含 1 支写工具** `patients_incremental_submit_labels`。2026-10-31 新增 5 个（持券 / 会员身份 / 积分账户 / 积分流水 / 已打标签）；2026-11-13 新增 1 个（患者标签增删） |
| 门店维度 | 13 | `clinicId` | **均强制**门店参数（核销工具为 `consumeClinicId`）；`bills` / `bill_docs` / `appoints` / `medically_register` / 3 个卡券工具 / `members` **额外强制**日期区间。其中 4 个为 2026-10-31 新增（卡券操作记录 / 发放 / 核销、会员）。旧名 `appoints_list` **已从本技能移除** |
| 员工与组织 | 3 | `clinicId`（部分无参） | 白名单与本人档案 |
| 企业微信 | 7 | `clinicId`（部分无参） | 好友 / 群 / 消息文本，**含 1 支写工具** `wecom_externalcontact_mark_tag`（2026-11-13 新增） |
| 基础字典 | 6 | 无（后四者需 `clinicId`） | 字典类别、字典项值、患者标签、收费组合、收费项目、预约项目 |
| 小程序 SCRM | 1 | `scrmUserId` | 2026-10-31 新增，按小程序用户 ID 查档案 |
| **合计** | **47** | — | **45 只读 + 2 写**；生产环境**不含** `get_clinic_info`；旧名 `appoints_list` 不收录 |

#### 一、患者维度（17）

| 工具 | 必要参数 | 说明 |
| --- | --- | --- |
| `patients_list` | 门店 id（`clinicId`）＋ 三段日期**至少传一段**：`createStartDate`/`createEndDate`、`firstVisitStartDate`/`firstVisitEndDate`、`lastVisitStartDate`/`lastVisitEndDate` | **唯一**能「按时段列患者 / 算新患者数」的入口（查 ES 患者索引）。⚠️ 只传 `clinicId` 会报 `[UPSTREAM_BUSINESS_REJECTED]`，**实为缺日期参数**、不是权限问题；日期跨度 ≤3 个月；总数直接读 `data.total`，无需翻页。可选筛选：`patientId`（按患者 id）、`wd`（查询关键词）、`consultantId`/`nurseId`、`firstSourceName`/`secondSourceName`/`threeSourceName`（建档来源）、`firstVisitDoctor`、`includeLabelIds`/`excludedLabelIds`（标签）、`bindingWecom`（已绑定企微）、`assignments`（患者归属） |
| `patients_quick_search` | 门店 id（`clinicId`）、搜索条件（`search`） | **快速检索**：仅支持姓名、手机号、病历号；同词字段取并集、多词取交集；`search` 最多 50 字符，支持空格 / Tab / 换行分词 |
| `patients_get_details` | 患者 id（`patientId`） | 按患者 id 聚合返回基本信息与各扩展子表；患者不存在时 `data` 为 null。⚠️ 必填字段名是 **`patientId`**（值为患者 id） |
| `patients_list_appointments` | 患者 id（`patientId`） | 预约列表（62 字段），含连锁门店的记录 |
| `patients_list_consults` | 患者 id（`patientId`） | 咨询列表（40 字段）；不传 `clinicId` 时跨门店返回该患者全部咨询 |
| `patients_list_emrs` | 患者 id（`patientId`） | 电子病历；牙位按 `tooth_scope` 拆成 5 个数组返回；不传 `clinicId` 跨门店 |
| `patients_list_images` | 患者 id（`patientId`） | 影像资料（全景片 / 小牙片 / CBCT / STL / 各类知情同意书 / 检查报告文档）。⚠️ `imageUrl` 是隐私裸链，见铁律 3 |
| `patients_list_bills` | 患者 id（`patientId`） | **⚠️ 已弃用（收入相关场景一律禁用，2026-10-13）**；收费单；收入取数一律走 `patients_list_bill_docs` |
| `patients_list_bill_docs` | 患者 id（`patientId`） | **营业额 / 交易实收唯一取数接口（患者维度，2026-10-13 起）**；收费单据明细粒度；不传 `status` 默认查正常交易。可选：`startDate`/`endDate`（**须成对**）、`billType`、`feeType`（1 收费 / 2 退费 / 3 减免 …）、`clinicId`（不传则跨门店） |
| `patients_list_followups` | 患者 id（`patientId`） | 随访；不传 `clinicId` 时跨门店 |
| `patients_list_returnvisits` | 患者 id（`patientId`） | 回访 / 复诊；不传 `clinicId` 时跨门店 |
| `patients_list_coupons` 🆕 | 患者 id（`patientId`） | 患者持券：主券 + 子券（`childCoupons[]`）；可选 `clinicId` 收窄。**`data` 直挂数组**，无分页。⚠️ `allowedClinicNames` 是长列表，按需摘取 |
| `patients_list_memberships` 🆕 | 患者 id（`patientId`） | 患者会员身份：会员分组、状态、开卡 / 到期、折扣率、积分倍率，嵌套 `memberCards[]`。**`data` 直挂数组** |
| `patients_point_account` 🆕 | 患者 id（`patientId`） | 积分账户：`point`（可用）/ `totalGainPoint`（累计获得）/ `totalUsePoint`（累计使用）。**`data` 是单个对象**；回显的 `tenantId` 不得回填 |
| `patients_list_point_logs` 🆕 | 患者 id（`patientId`） | 积分流水，分页（`current` / `size` ≤100）；`getWayText` 表示获得方式（如「消费奖励」） |
| `patients_list_labels` 🆕 | 患者 id（`patientId`） | 患者**已打上的标签**；**`data` 直挂数组**。与门店标签定义 `basedatas_list_label_definitions` 语义不同 |
| `patients_incremental_submit_labels` 🆕⚠️写 | 患者 id（`patientId`）；新增标签 `addLabelIds` / 删除标签 `deleteLabelIds`，**数组**，**至少一侧非空** | **患者标签增量增删**（全库仅 2 支写工具之一）。标签 ID 为 **HIS 标签 id**（来源 `basedatas_list_label_definitions`，复核用 `patients_list_labels`）。空数组 = 该侧无操作，**不等于「清空全部标签」**。⚠️ 写操作，须用户显式要求并写后回读，见铁律 14 |

> 15 个患者主档 / 子表工具（`patients_get_details` + 8 个既有 `patients_list_*` + 5 个 2026-10-31 新增 + 1 个 2026-11-13 标签写工具）**全部强制 `patientId`**，拿不到患者 id 就不能用它们 —— 检索入口有两个：**`patients_list`**（按时段 / 条件列患者）与 **`patients_quick_search`**（按姓名 / 手机号 / 病历号快搜）。

#### 二、门店维度（13）

| 工具 | 必要参数 | 说明 |
| --- | --- | --- |
| `clinics_list_bill_docs` | 门店 id（`clinicId`）、开始日期（`startDate`）、结束日期（`endDate`） | **营业额 / 交易实收唯一取数接口（门店维度，2026-10-13 起）**。按**交易时间**（`optDateTime`）归集，`sum(payAmount)` 即**净实收**；退费已以负数行计入，无需再扣；构成字段最全（65 个，含 `chargePeriod`/`feeType`/医生 / 收费项目） |
| `clinics_list_bills` | 门店 id（`clinicId`）、开始日期（`startDate`）、结束日期（`endDate`） | **⚠️ 已弃用（收入相关场景一律禁用，2026-10-13）**。账单视角，按**首次收费时间**（`firstChargeTime`）归集，`sum(actualAmount)`；会漏掉跨月退款 → 高估营业额；收入取数一律走 `clinics_list_bill_docs` |
| `clinics_list_consults` | 门店 id（`clinicId`） | 咨询，返回含患者姓名与病历号。`status`：`0`=待执行 / `1`=已执行 / `2`=已取消。⚠️ `filterDateType` 默认 `1`=**计划执行时间**（可选 `2`=实际执行 / `3`=创建 / `4`=就诊时间）；取「按时段到店 / 就诊」必须传 `4`=就诊时间，否则命中「已排期未到店」 |
| `clinics_list_emrs` | 门店 id（`clinicId`） | 病历，返回含患者姓名、病历号与牙位数组。`filterDateType`：`1`=就诊时间（默认）/ `2`=创建时间 |
| `clinics_list_images` | 门店 id（`clinicId`） | 影像，返回含患者姓名与病历号。`filterDateType`：`1`=就诊时间（默认）/ `2`=创建时间；另有 `imageType` |
| `clinics_list_followups` | 门店 id（`clinicId`） | 随访，含患者姓名与病历号。`filterDateType`：`1`=随访时间（默认）/ `2`=就诊时间 / `3`=计划随访日期 / `4`=创建时间 |
| `clinics_list_returnvisits` | 门店 id（`clinicId`） | 回访，含患者姓名与病历号。`filterDateType`：`1`=计划时间（默认）/ `2`=执行时间 / `3`=创建时间 / `4`=就诊时间 |
| `clinics_list_appoints` | 门店 id（`clinicId`）、过滤日期类型（`filterDateType`）、开始日期（`startDate`）、结束日期（`endDate`） | **门店维度预约查询**（按患者查预约走 `patients_list_appointments`）。`filterDateType`：`1`=预约时间 / `2`=创建日期；日期跨度 ≤3 个月（含当天）；可选筛选：`status`（就诊状态，逗号分隔多值）、`searchType`（1-待定预约 2-已取消 3-已失约 4-已改约 5-改约创建）、`patientName`（模糊）、`patientId`、`appointPersonId`、`doctorId`/`consultantId`/`onlineConsultantId`/`roomId`/`visitType`、`isReach`/`isRegister`/`isCharge`/`isCustomerAppoint`、`appointCategoryId`/`appointItemIds`/来源三级（`firstSource`/`secondSource`/`threeSource`，**传 id 不是名称**）/ `cancelReason` 等。门店预约**只此一个入口**（旧名已从本技能移除） |
| `clinics_list_medically_register` | 门店 id（`clinicId`）、开始日期（`startDate`）、结束日期（`endDate`） | 门店**每日体检登记**信息；日期 `yyyy-MM-dd`，跨度 ≤3 个月 |
| `clinics_list_coupon_sale_records` 🆕 | 门店 id（`clinicId`）、开始日期（`startDate`）、结束日期（`endDate`）、当前页（`current`）、每页条数（`size`） | **卡券发放 / 销售记录**，按发券时间归集（≤3 个月）。可选：`patientId`、`couponName` / `couponAlias`（**精确**）、`couponCode`（模糊）、`couponType`、`isRefund`、`saleChannel`（1 蓝莓象 / 2 蓝莓熊）、`distributeEmployeeId`。分页对象 |
| `clinics_list_coupon_consume_records` 🆕 | **核销门店 id（`consumeClinicId`）**、核销开始日期（`consumeStartTime`）、核销结束日期（`consumeEndTime`）、当前页（`current`）、每页条数（`size`） | **卡券核销记录**。⚠️ 门店参数名是 `consumeClinicId`，**不是 `clinicId`**。可选：`patientId`、`couponName`（模糊）、`couponType`（0 现金 / 1 折扣 / 2 项目 / 3 自选包 / 4 活动包）、`itemId` / `itemName`（同时传取交集）、`chargeEmployeeId`、`distributeEmployeeId`、`fromType`（券来源 0–7）、`saleChannel`（1 HIS / 2 蓝莓熊 / 3 代理人团队 / 4 拼团）。分页对象 |
| `clinics_list_coupon_records` 🆕 | 门店 id（`clinicId`）、操作记录开始日期（`receiveStartTime`）、操作记录结束日期（`receiveEndTime`）、当前页（`current`）、每页条数（`size`） | **卡券操作流水**（领用 / 下发 / 撤回）。⚠️ 日期参数是 `receiveStartTime` / `receiveEndTime`。可选：`patientId`、`couponName`（模糊）、`cardNo`（模糊）、`couponType`、`allowedItemName`（适用项目名，模糊）、`distributeEmployeeId`、`fromType`、`sharable`（0 否 / 1 是 / 2 仅赠送）。分页对象 |
| `clinics_list_members` 🆕 | 门店 id（`clinicId`）、日期类型（`dateType`：1 开卡 / 2 续费 / 3 到期）、开始日期（`startDate`）、结束日期（`endDate`）、当前页（`current`）、每页条数（`size`） | **门店会员清单**，按 `dateType` 决定日期语义（≤3 个月）。可选：`patientId`、`categoryId`、`memberCardId`（卡模板 id）、`status`（0 生效中 / 1 已失效 / 2 已过期）、`handleEmpId`、`renewTimes`。分页对象 |

> 13 个工具**全部强制门店参数**（核销工具为 `consumeClinicId`，其余为 `clinicId`）；`bills` / `bill_docs` / `clinics_list_appoints` / `medically_register` / 3 个卡券工具 / `members` 额外强制日期区间，跨度 ≤3 个月；收费组合 / 收费项目查询已迁移至基础字典域（`basedatas_list_charge_combs` / `basedatas_list_charge_items`）；预约工具**只用** `clinics_list_appoints`。
>
> 卡券 / 会员 / 积分的取数口径、典型问法与结果解读见 [references/coupon-member-point.md](references/coupon-member-point.md)。
> `filterDateType` **必须传 number**（传字符串报 `[MCP-PARAM-001] 类型应为number`），且**各工具取值语义不同**（`clinics_list_emrs` 与 `clinics_list_images` 相同：`1`=就诊时间 / `2`=创建时间）。

#### 三、员工与组织（3）

| 工具 | 必要参数 | 说明 |
| --- | --- | --- |
| `employees_list_work_clinic` | 无 | 当前账号的**工作门店授权清单**（实测 288 行）。**所有 `clinicId` 入参的唯一白名单来源**；`isDefault="1"` 仅 1 行 = 归属诊所；返回形态：数组直接挂在 `data`（**不是分页对象**，无 `records`/`total`）。字段用法见 [references/clinic-and-staff-lookup.md](references/clinic-and-staff-lookup.md)（2026-10-15 schema 扩展后实测 24 字段） |
| `employees_get_details` | 无 | **当前调用者本人**的员工档案（28 字段，全字符串）。不能查别人、**不含手机号**；`postNames` 是**连锁级**岗位（与 `employees_list_work_clinic` 的门店级岗位语义不同） |
| `employees_list` | 门店 id（`clinicId`）、当前页（`current`）、每页条数（`size`） | 按门店查员工列表（12 参数），支持 `search`（姓名 / 工号 / 手机 搜索）。⚠️ `size`/`current` 传**数字**，筛选参数（`postId`/`isLeave`/`isPartJob`/`isTrainee`/`isAssistant`/`oaJobStatus`/`wecomStatus`/`professionalTitle`/`search`）传**字符串** |

#### 四、企业微信（7）

| 工具 | 必要参数 | 说明 |
| --- | --- | --- |
| `wecom_list_friends` | 门店 id（`clinicId`）、当前页（`current`）、每页条数（`size`） | 指定门店的企微好友清单（可按 `name`/`bindStatus`/**`tags`**/日期筛选）。🚨 **出参 `records[].tags`（数组）= 好友标签唯一来源**（键恒在，无标签为 `[]`；**不是**省略键）；入参 `tags` 为**子串匹配**（`补牙` 会召回「潜在补牙」），逗号 = AND（**最多 10 个**），只作预筛、须客户端精确复核。⛔ 禁用患者标签（`data.lables[]` / `wecom[].label` / `labelId`） |
| `wecom_get_friends_details` | 企业 id（`corpId`）、企微外部联系人 userid（`wecomExternalUserId`） | 指定企微好友的详细信息。⚠️ **入参来源**：`wecomExternalUserId` 需先通过 `wecom_list_friends` 获取（最新 schema：两参均必填） |
| `wecom_get_friends_private_message_text` | 无 | 企微好友**私聊**文本信息（`clinicId`/`startDate`/`endDate`/`current`/`size` 选填） |
| `wecom_get_friends_group_message_text` | 无 | 企微好友**群聊**文本信息（`clinicId`/`startDate`/`endDate`/`current`/`size` 选填） |
| `wecom_list_group_friends` | 无 | 指定门店的企微好友**群清单**（`clinicId`/`name`/日期 选填） |
| `wecom_get_group_details` | 企微客户群 ID（`chatId`）、企业 id（`corpId`） | 指定企微好友群的详细信息。⚠️ **入参来源**：`chatId` 需先通过 `wecom_list_group_friends` 获取（最新 schema：两参均必填） |
| `wecom_externalcontact_mark_tag` 🆕⚠️写 | 企微外部联系人 userid（`wecomExternalUserId`）；新增标签 `addLabelIds` / 删除标签 `deleteLabelIds`，**数组**，**至少一侧非空** | **企微好友标签增量增删**（全库仅 2 支写工具之一，标签 ID 为 **HIS 标签**）。🚨 **好友已关联患者时会同步更新该患者标签** —— 跨对象副作用，写前必须告知用户。入参来源：`wecomExternalUserId` **直接取** `wecom_list_friends.records[].externalUserId`（同一值、仅字段名不同；✅ 2026-11-13 只读实测确认）。⚠️ 见铁律 14 |

> 该域 7 个工具中 4 个有强制参数：`wecom_list_friends`（`clinicId`+`current`+`size`）、`wecom_get_friends_details`（`corpId`+`wecomExternalUserId`）、`wecom_get_group_details`（`chatId`+`corpId`）、`wecom_externalcontact_mark_tag`（`wecomExternalUserId`）；其余 `required` 为空 —— 传参靠上下文与会话态，**稳定性弱于前三个域**。

#### 五、基础字典（6）

| 工具 | 必要参数 | 说明 |
| --- | --- | --- |
| `basedatas_list_biz_codes` | 无 | 取未封存、未删除的**顶层字典类别**（实测 **76** 本），返回 `code` 与字典名称；`code` 用于再调字典值接口 |
| `basedatas_list_bizdict` | 无 | **一个工具两种行为**：传 `codes`（可逗号分隔）→ 取字典**项值**；传 `dictValue` → 按**字典名称**模糊搜、只回**定义**。⚠️ `code` 传错**不报错、静默返回 `{}`**，猜 code 必须有已知存在的做对照 |
| `basedatas_list_label_definitions` | 门店 id（`clinicId`） | 按门店取可用的**患者标签基础数据**（标签定义），不是患者与标签的关联关系 |
| `basedatas_list_charge_combs` | 门店 id（`clinicId`） | 收费组合，关键词匹配名称 / 编码。`status`：`0`=启用（默认）/ `1`=禁用 |
| `basedatas_list_charge_items` | 门店 id（`clinicId`） | 收费项目（已配置价格），关键词匹配编码 / 名称 / 拼音。`status`：`0`=启用 / `1`=禁用，不传为全部。原 `clinics_list_charge_items` 已更名迁移至此域 |
| `basedatas_list_appoint_items` | 门店 id（`clinicId`） | **预约项目**基础数据，关键词匹配编码 / 名称 / 拼音。`status`：`0`=启用 / `1`=禁用，不传为全部；`size` 默认 **100**、上限 **500**（全局默认） |

#### 六、小程序 SCRM（1）

| 工具 | 必要参数 | 说明 |
| --- | --- | --- |
| `scrm_get_user` 🆕 | 小程序用户 ID（`scrmUserId`） | 按患者档案里的 `scrmUserId` 查小程序用户信息。来源：`patients_list` / `patients_get_details` 返回的 `scrmUserId` 字段；**空串表示该患者未注册小程序**。**`data` 是单个对象**。⚠️ 返回含 `wxUnionId` / `wxOpenId`，按铁律 3 处理 |

#### 七、标签写入（2 个写工具，2026-11-13 新增）

**这是全库仅有的写操作**，其余 45 个工具只读。二者 schema 同构：都是「在原标签基础上**增量**增删」，`addLabelIds` / `deleteLabelIds` 为**标签 ID 数组**，**至少一侧非空**，空数组表示该侧不操作。

| 工具 | 作用对象 | 必填 | 副作用 |
| --- | --- | --- | --- |
| `patients_incremental_submit_labels` | 患者 | `patientId` | 只改患者标签 |
| `wecom_externalcontact_mark_tag` | 企微好友 | `wecomExternalUserId` | 好友**已关联患者时同步改该患者标签** |

**标签 ID 从哪来**（不得臆造）：① 门店可用标签定义 → `basedatas_list_label_definitions`（必填 `clinicId`）；② 已打标签 → `patients_list_labels`（可与 ① 比对取 id）。**面向用户一律用标签中文名，提交时才换成 id。**

**写前必做**：用户**明确要求** + 列出「对象 / 标签名 / 增删方向」待确认 + 计算差集（只提交真正需要变更的部分，已在目标态的不重复提交）。

**写后必做**：回读 `patients_list_labels`（企微侧回读 `wecom_list_friends.records[].tags`）核对实际结果，**不得只凭返回码宣称成功**。

> ⚠️ **未实测声明**：两工具本次仅核对 `tools/list` schema，**未实际调用**（避免污染生产数据），返回结构与错误文案均**未验证**。首次使用请先拿 1 个测试患者 / 好友做最小样本，确认返回形态后再常规使用。完整纪律见 [references/label-write.md](references/label-write.md)。

### B3 取数范围与调用硬约束

#### 1. 门店范围（`clinicId`）

- **白名单唯一来源 = `employees_list_work_clinic`**（按当前 token 下发），不接受本地名单。
- **两层校验，缺一不可（defense-in-depth）**：
  - **客户端闸门（必需）**：任何 `clinicId` 入参**先过工作诊所白名单**，不在名单内一律拒绝并报告 —— **不得因为「服务端也会拦」而省略这一步**。
  - **服务端校验（兜底）**：编造 / 非授权 `clinicId` 返回 **`[UPSTREAM_BUSINESS_REJECTED]`**（`isError:true`）；白名单内真实门店正常返回（`code:200`）。
  - **不得仅凭返回体判越权**：`UPSTREAM_BUSINESS_REJECTED` 是**多因笼统码**（缺必填参数 / 门店不存在或无权 / 日期跨度超限 **同码**），见到它**不能直接判越权**，须结合参数自查后再定性。
- **默认只查归属诊所**（`isDefault="1"`）；多条且无默认标记 → **不许替用户选**，让其指定。
- **跨店需用户显式要求**，且目标 `clinicId` 逐个过白名单；越权即停止并报告，**不得静默跳过或换店替代**。
- **fail-closed**：白名单取不到（网络 / 超时 / 授权失败 / 结构异常）→ **拒绝一切取数**，绝不退回「不校验」。
- **有效范围 = min（请求范围，服务端 `patientDataScope` / `viewCurrentClinic` 声明）** —— 取交集。
- **门店参数的别名同样要过白名单**：卡券核销工具的门店入参叫 `consumeClinicId`，与 `clinicId` 共用同一份工作诊所白名单，不得因为它换了名字就跳过客户端闸门。
- **汇总维度三选一，不要混用**：门店 / 组织级 → `oaOrgId`；**分部 / 大区级 → `divisionalId`（`divisionalGeneralManager` 为负责人）**；接口入参 → `clinicId`。见 [references/clinic-and-staff-lookup.md](references/clinic-and-staff-lookup.md) §三 / §四。

#### 2. 收入取数

| 场景 | 门店维度 | 患者维度 | 归集字段 |
| --- | --- | --- | --- |
| ✅ 收入相关**唯一**取数接口 | `clinics_list_bill_docs` | `patients_list_bill_docs` | 交易时间 `optDateTime` |
| ❌ 收入场景**禁用** | `clinics_list_bills` | `patients_list_bills` | 首次收费时间 `firstChargeTime`（漏跨月退款 / 补收老单） |

金额 = `sum(payAmount)`（退费以负数行计入，即净实收）；口径过滤见 [references/revenue-and-deal-count.md](references/revenue-and-deal-count.md)。

#### 3. 分页与返回形态

**先判返回形态，再解析。** 本端点有三种形态，混用会读出空结果：

| 形态 | 判定方法 | 工具 |
| --- | --- | --- |
| **分页对象** | `data.records` + `data.total` | 绝大多数列表工具；新增的 3 个卡券工具、`clinics_list_members`、`patients_list_point_logs` |
| **裸数组** | `data` 本身就是数组 | `patients_list_labels`、`patients_list_coupons`、`patients_list_memberships`、`employees_list_work_clinic` |
| **单对象** | `data` 是对象 | `patients_point_account`、`scrm_get_user`、`patients_get_details` |

> 对裸数组形态的 `data` 查 `data.records` 会得到 `undefined`，容易被误报成「没有数据」—— 这是最常见的解析错误。
> 数组长度即全部结果，没有 `total`；需要计数时按数组长度统计。

分页型工具结果包在 `data.records`，`total` 才是总数。**单页 `size` 默认 100、上限 500**，以下为例外：

| 工具 | 默认 `size` | 上限 |
| --- | --- | --- |
| `patients_quick_search` | **20** | **100** |
| `basedatas_list_charge_combs` | **10** | **100** |
| `basedatas_list_charge_items` | **10** | **100** |
| `clinics_list_medically_register` | **10** | **100** |
| `clinics_list_coupon_records` | —（必填） | **100** |
| `clinics_list_coupon_sale_records` | —（必填） | **100** |
| `clinics_list_coupon_consume_records` | —（必填） | **100** |
| `clinics_list_members` | —（必填） | **100** |
| `patients_list_point_logs` | 100 | **100** |
| `wecom_list_group_friends` | 100 | **100** |
| `employees_list_work_clinic` | —（不分页，数组直挂 `data`） | — |

#### 4. 限流与重试

账号级 QPS 限流触发时报 `MCP-LIMIT-001`，退避重试 **3s / 6s / 9s**。

调用间隔（客户端 `gap`）**默认 0.6s / 线程** —— 2026-10-15 实测：服务端单次响应约 0.4s，**串行 50 次（0.49s/次）与 4 线程并发 48 次（0.20s/次）均 0 失败**。限流器**按线程隔离**（工作区 `ygj_client.py._throttle`），因此「批量取数必须串行」已不再成立，可用 4 线程并发。

> 旧约定「间隔 ≥2s + 必须串行」源自 2026-09-23 的账号级限流，**已放宽**（见 [changelog.md](references/changelog.md) §五 2026.10.15.11）。若并发下出现 `MCP-LIMIT-001`，回落到串行并放大 `gap`。

#### 5. 无聚合工具

47 个里没有一个 `reports_*`，除 2 支标签写工具外所有返回都是明细 / 列表 —— 统计口径（营业额、新患者数、就诊人次、复诊率、发券数、核销数、会员数）**一律靠明细求和**。卡券 / 会员 / 积分三域同样没有汇总工具；`total` 是**行数**，不等于金额、也不等于去重患者数，需要按业务口径自行聚合。

#### 6. 写操作范围

- **只有打标签**：`patients_incremental_submit_labels` / `wecom_externalcontact_mark_tag`。除此以外**没有任何**增删改接口（无建档、无改预约、无退费、无发券）。
- 两支写工具**都不收 `clinicId`**（只收 `patientId` / `wecomExternalUserId`），因此 §B3.1 的门店白名单闸门**无法套用**；对象归属只能由服务端按租户校验 —— 该行为**未实测**，不得假定「跨店也能写」。先取到对象、确认其所属门店在 `employees_list_work_clinic` 白名单内，再执行写。
- **fail-closed 同样适用**：白名单取不到时，不执行任何写操作。

### B4 端到端示例

**示例 1：某门店某日营业额**

1. 调 `employees_list_work_clinic`（无参）→ 取 `isDefault="1"` 那一行的 `clinicId`。
2. 调 `clinics_list_bill_docs`：

   ```json
   { "clinicId": "…", "startDate": "2026-10-14", "endDate": "2026-10-14" }
   ```

3. 按 `optDateTime` 取该日明细 → 过滤**支付分类 ∈ {0, 3}**（营业额口径）→ 对 `payAmount` 求和（用 `Decimal`）。
4. 输出时字段用中文 `title`，并注明口径（营业额 / 交易实收）与门店。

**示例 2：按姓名找患者并取其收费明细**

1. 调 `employees_list_work_clinic`（无参）→ 按简称 / 诊所名 / 组织名命中门店，取 `clinicId`。
2. 调 `patients_quick_search`：

   ```json
   { "clinicId": "…", "search": "张三" }
   ```

   → 从 `data.records` 取 `patientId`（多人同名时列出候选让用户确认，不替用户选）。
3. 调 `patients_list_bill_docs`：

   ```json
   { "patientId": "…" }
   ```

   （可加日期区间收窄）→ 逐行取交易时间、收费项目、`payAmount`（退费为负数行）。
4. 需要按一级 / 二级分类或按患者汇总金额时，转 [references/label-level-rules.md](references/label-level-rules.md) 或 [references/combo-transaction-by-patient.md](references/combo-transaction-by-patient.md)。

**示例 3：给某患者加一个标签（写操作，须先确认）**

1. `patients_quick_search` 定位患者 → 取 `patientId`，并确认门店在白名单内。
2. `basedatas_list_label_definitions`（`clinicId`）→ 由标签中文名找到 **HIS 标签 id**；命中同名多条时列候选让用户选。
3. `patients_list_labels`（`patientId`）→ 读现状，**只把目标与现状的差集**放进 `addLabelIds`。
4. **向用户确认**「患者 + 标签名 + 新增」后再调用：

   ```json
   { "patientId": "…", "addLabelIds": ["8888000000005085"], "deleteLabelIds": [] }
   ```

5. `patients_list_labels` 回读，确认标签已出现；**回读不到就不算成功**。

> 写路径**未实测**，以上为 schema 形状示意；首次使用按 [references/label-write.md](references/label-write.md) §六 做最小样本验证。

## 输出要求

- **不发明数据。** 取不到就明说取不到，并说明卡在哪一步（缺参数、越权、白名单不可用、无对应工具）。
- 字段名用中文 `title`；金额 / 数量类结论**必须写清口径**（营业额还是交易实收、数量是主项目行还是全行）。
- 涉及多店时**按门店分别给出**，不做单店代表全公司的推断。
- 遇到 `[MCP-AUTH-002]` 按铁律 6 处理，不要答复「功能没有」。
- **写操作（打标签）必须单独交代**：改了哪个对象、加了 / 删了哪些标签（写中文名）、**回读结果是否与预期一致**；未回读不得写成「已成功」。
