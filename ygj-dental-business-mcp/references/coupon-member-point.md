# 卡券 · 会员 · 积分 · 小程序取数口径

本文件覆盖 2026-10-31 新增的 10 个工具。**正文只在这些场景命中时加载**，不要预先读。

> 基线：2026-10-31 生产端点实调。结论带核对时刻；复用前按铁律 11 重新实测。

## 〇、入口前提（四域共用）

1. **门店入参先过白名单**：`clinicId` / `consumeClinicId` 只能取自 `employees_list_work_clinic`；不在名单内一律拒绝，白名单不可用时 fail-closed。
2. **患者入参先有 `patientId`**：来自 `patients_list`（按时段列患者，读 `data.total` 拿总数）或 `patients_quick_search`（按姓名 / 手机号 / 病历号快搜）。
3. **日期区间一律 ≤3 个月**：卡券三工具、`clinics_list_members` 全部受限。超限实测（2026-10-31，`clinics_list_members`，`2026-01-01 ~ 2026-10-31`）返回 `{"code":400,"success":false,"msg":"查询日期跨度不能超过3个月"}` —— **不是** `[UPSTREAM_BUSINESS_REJECTED]`。SKILL.md §B3 沿用旧描述把「日期跨度超限」归入该笼统码，**以本实测为准**；其余工具未逐个复测。
4. **禁止填 `Blade-TenantId` / `Blade-AccountId`**；响应里的 `tenantId` 只用于自查，不回填。

## 一、卡券

### 1.1 三个工具的分工

| 问题 | 工具 | 门店参数 | 日期参数 | 时间语义 |
| --- | --- | --- | --- | --- |
| 发了多少张券 / 谁发的 / 卖了多少钱 | `clinics_list_coupon_sale_records` | `clinicId` | `startDate` / `endDate` | **发券时间** |
| 核销了多少张 / 核销了什么项目 | `clinics_list_coupon_consume_records` | **`consumeClinicId`** | `consumeStartTime` / `consumeEndTime` | **核销时间** |
| 券的领用 / 下发 / 撤回流水 | `clinics_list_coupon_records` | `clinicId` | `receiveStartTime` / `receiveEndTime` | **操作记录时间** |

⚠️ 三个工具的门店参数和日期参数**命名各不相同**，照抄另一个工具的字段名会直接报 `[MCP-PARAM-001] 缺少必填字段`。

### 1.2 典型问法与取数

- **「某门店这周发了多少张券」** → `clinics_list_coupon_sale_records`，读 `data.total` 即为发放条数；金额看 `actualAmount`（`price` 是券面价，`buyPoint` 是购买积分）。
- **「某门店这周核销了多少张」** → `clinics_list_coupon_consume_records`，读 `data.total`；涉及项目看 `consumeItemName`，抵扣金额看 `deductionAmount`。
- **「这张券经历过什么」** → `clinics_list_coupon_records`，按 `cardNo`（模糊）或 `couponName`（模糊）收窄；`operationTypeText` 表示动作（如「领用(下发)」）。
- **「某患者有哪些券、用了没有」** → 不要用上面三个门店工具，用 `patients_list_coupons`（患者维度，见 1.3）。

### 1.3 患者持券：`patients_list_coupons`

- 必填 `patientId`；`clinicId` 可选（不传则查该患者在本租户全部诊所）。
- **`data` 直挂数组**，无 `records` / `total`。
- 主券字段：`cardNo`、`couponName`、`couponAlias`、`couponType`、`statusText`、`startTime`、`expireTime`、`consumedQuantity`、`consumedAmount`。
- 活动包 / 自选包会带 `childCoupons[]` 子券；`childCouponCount` 是子券数量。
- ⚠️ `allowedClinicNames` / `allowedClinicIds` 是**长列表**（实测单个主券可带 21 家门店中文名），单次响应可能达到数万字符。回答「哪些门店能用」时按最小必要摘取，不整段贴出。
- ⚠️ `currentClinicApplicable` 表示「当前门店是否适用」，做门店可用性判断时优先读它，不要自己拿 `allowedClinicIds` 做匹配。

### 1.4 卡券坑

- `couponType` 是 **number**：`0` 现金、`1` 折扣、`2` 项目、`3` 自选包、`4` 活动包。传字符串会报类型错误。
- 发放工具的 `couponName` / `couponAlias` 是**精确匹配**，操作记录与核销工具的同名字段是**模糊匹配** —— 同名不同义，别混用。
- `fromType`：`0` 直接发放、`1` 活动充值、`2` 自选包、`3` 分享、`4` 活动包、`5` 自选包拆分后分享、`6` 活动包拆分后分享、`7` 活动充值后分享。
- `saleChannel` 在两个工具里语义不同：发放工具是 `1` 蓝莓象 / `2` 蓝莓熊；核销工具是 `1` HIS / `2` 蓝莓熊 / `3` 代理人团队 / `4` 拼团。

## 二、会员

### 2.1 门店会员清单：`clinics_list_members`

- 必填：`clinicId`、`dateType`、`startDate`、`endDate`、`current`、`size`（≤100）。
- `dateType` 决定日期语义：`1` 开卡、`2` 续费、`3` 到期。**问「本月新办会员」用 `1`；问「本月到期」用 `3`**。
- 可选：`status`（`0` 生效中 / `1` 已失效 / `2` 已过期）、`categoryId`（会员分组）、`handleEmpId`、`renewTimes`。
- 关键字段：`categoryName`、`cardNo`、`cardName`、`statusText`、`openDate`、`expireDate`、`renewTimes`、`handleTypeText`（如「新办」）、`handleEmpName`、`cardBalance`。
- `data.total` = 会员身份行数，**不等于去重患者数**：一个患者可能有多张卡 / 多次续费。

### 2.2 患者会员身份：`patients_list_memberships`

- 必填 `patientId`；`clinicId` 可选。
- **`data` 直挂数组**；数组里每个元素是一个会员身份，嵌套 `memberCards[]` 列具体卡。
- 关键字段：`categoryName`（如「480会员」）、`statusText`、`openDate`、`expireDate`、`renewTimes`、`wholeDiscountRate`（整单折扣率）、`pointsRatio`（积分倍率）、`cardAmount`、`activeCardBalance`。
- 与门店清单的区别：门店清单是「这家店有哪些会员」，本工具是「这个人是哪家店的什么会员」。

### 2.3 「480 会员卡」等具体卡种的识别（2026-11-07 实测）

**按会员分组 `categoryId` 识别，不要按卡名。** 实测（深湾 + 6 个分部抽样，全公司一致）：

| 分组 | `categoryId` | `categoryName` |
| --- | --- | --- |
| 480 会员 | `777616002` | `480会员` |
| 预防会员 | `777616001` | `预防会员` |

- 🚨 **卡模板名有多种变体**：「480会员卡-双倍积分-限购1份」「480会员卡-延保1年-限购1份」「480会员卡-双倍积分-延保1年-限购1份」（不同门店/时段配置不同）⇒ **按 `cardName` 精确匹配会漏统计，必须按 `categoryId` 分组**。
- **「某卡种今天办了多少张」的取数**：`clinics_list_members` + `dateType=1`（开卡）+ `startDate=endDate=当天`，客户端按 `categoryId` 过滤计数；**续费走 `dateType=2`，另计不重复**。
- ✅ **行数 = 去重患者数**（抽样 4 家 79 行、去重患者 79 位，无一人多卡）——仅当单日；跨度拉长后一人在同一天不可能多卡，但跨日会出现同卡续费，勿混。
- 性能实测：310 家门店 × 2 个 `dateType`，8 线程 **约 2 分钟**；单日绝大多数门店 `total=0`，无分页压力。
- **锚点**（2026-11-07，核对时刻 16:37）：480 会员开卡 **952 张**，覆盖 **129 家门店**（在册 310 家），续费 **0 张**；全部会员开卡 955 张（非 480 的预防会员 3 张）；单店最高杭州迪安店 24 张，户均 7.4 张；分部第一严东平 227 张（23.8%）。首轮 4 家网络瞬断（石家庄美兆/美年美宝/南宁江南/慈铭杨浦）重试后补齐，贡献 36 张 —— **网络失败必须重试，否则静默少计**。

⚠️ 本表**不含**到期数、失效数、卡内余额、储值实收金额；「今日 480 卡收款多少」需另走交易接口，不能由会员清单推导。

## 三、积分

### 3.1 账户：`patients_point_account`

- 必填 `patientId`。**`data` 是单个对象**。
- `point` = 可用积分、`totalGainPoint` = 累计获得、`totalUsePoint` = 累计使用。
- 未开积分账户的患者返回形态需实测后再下结论（本次样本均为已开户）。

### 3.2 流水：`patients_list_point_logs`

- 必填 `patientId`；`current` / `size` 选填，`size` ≤100。
- 分页对象形态。
- `getWayText` 表示获得方式（实测样本为「消费奖励」）；`changePoint` 是本次变动（正为增、负为减）；`point` 是变动后余额；`relBuzNo` 关联单据号。

## 四、小程序账号：`scrm_get_user`

- 必填 `scrmUserId`，来源是患者档案（`patients_list` / `patients_get_details`）的 `scrmUserId` 字段。
- **`scrmUserId` 为空串 = 该患者未注册小程序**，此时不要调本工具、也不要猜 ID。
- `data` 单对象；含 `account`、`realName`、`phone`（脱敏）、`createSource`、`isAgent`、`agentStatus`、`externalUserId`。
- ⚠️ `wxUnionId` / `wxOpenId` 是敏感标识：**不做主动汇总、不写入交付物、不整段外发**（铁律 3）。

## 五、返回形态速查

| 工具 | 形态 | 取值方式 |
| --- | --- | --- |
| `clinics_list_coupon_sale_records` | 分页对象 | `data.records` / `data.total` |
| `clinics_list_coupon_consume_records` | 分页对象 | 同上 |
| `clinics_list_coupon_records` | 分页对象 | 同上 |
| `clinics_list_members` | 分页对象 | 同上 |
| `patients_list_point_logs` | 分页对象 | 同上 |
| `patients_list_labels` | 裸数组 | `data` 即数组，长度即总数 |
| `patients_list_coupons` | 裸数组 | 同上 |
| `patients_list_memberships` | 裸数组 | 同上 |
| `patients_point_account` | 单对象 | 直接读 `data.point` 等 |
| `scrm_get_user` | 单对象 | 直接读 `data.wxOpenId` 等 |

## 六、核对样本（2026-10-31，仅作回归对照）

| 工具 | 门店 / 患者 | 参数 | 结果 |
| --- | --- | --- | --- |
| `clinics_list_coupon_sale_records` | 阳江江城门诊部 `2029490099437191169` | 2026-08-01 ~ 2026-10-31 | `total=145` |
| `clinics_list_coupon_consume_records` | 阳江 | 同上 | `total=69` |
| `clinics_list_coupon_records` | 阳江 | 同上 | `total=173` |
| `clinics_list_coupon_records` | 牙管家集团 `1476530438895636482` | 同上 | `total=0` |
| `clinics_list_members` | 阳江 | `dateType=1`，同上 | `total=137` |
| `clinics_list_members` | 牙管家集团 | 同上 | `total=0` |
| `patients_list_coupons` | 患者 `2092813379673554946` | — | 1 主券 + 2 子券 |
| `patients_list_memberships` | 同上 | — | 1 身份 + 1 卡 |
| `patients_point_account` | 同上 | — | `point=3080` |
| `patients_list_point_logs` | 同上 | — | `total=1` |
| `patients_list_labels` | 同上 | — | 3 个标签 |
| `scrm_get_user` | `scrmUserId=2092815602931187713` | — | 单对象 |

> 总部店（牙管家集团）两个门店维度工具为 `total=0`、阳江店有数据：这只能说明**此刻该门店该域无数据**，不能写成「该接口不支持 / 全集团无数据」。复用前重测。
