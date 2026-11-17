# 门店与员工速查（工作门店白名单）

确定「查哪家店」「门店叫什么」「多家店要不要合并」时读本文件。**所有 `clinicId` 入参的唯一来源**就在这里的 `employees_list_work_clinic`。

## 一、接口 `employees_list_work_clinic`

**无入参，可直接调用**，返回当前 token 可见的全部工作诊所（行数随账号门店授权变化，以当次调用为准；历史实测 288 行 → 308 / 311 行）。返回形态：数组直接挂在 `data` 下，**不是分页对象**（无 `records` / `total`）。

### 返回字段使用方式（2026-10-15 schema 扩展后，outputSchema 声明 26 字段、实测返回 24 字段）

| 字段 | 用途 |
| --- | --- |
| `oaOrgId` | 组织机构 id —— **门店级汇总分组键** |
| `oaOrgName` / `clinicName` / `abbreviation` | 组织机构名称 / 诊所名称 / 诊所简称 —— 名称匹配与展示 |
| `clinicId` | 诊所 id —— 后续所有 `clinicId` 入参的**唯一来源**（白名单） |
| `clinicNo` | 门店号 —— 门店编码展示 |
| `id` | 关系主键 —— 行主键 |
| `isDefault` | 是否默认诊所，`"1"` 为默认 —— 缺省单店统计时取默认店 |
| `clinicStatus` | 诊所状态 |
| `deptName` / `structName` / `postNames` / `roleNames` | 组织 / 岗位 / 角色信息 —— 范围与角色上下文 |
| `roleList` | 角色列表**数组**，每行均有：`roleName`（角色名）、`roleType`（1-平台 2-连锁 3-诊所 4-自定义）、`patientDataScope`（患者访问权限：1-连锁患者 2-门店患者 3-我的患者）、`viewCurrentClinic`（患者记录是否只允许查看当前门店：0-否 1-是）—— **与「有效范围 = min（请求范围，`patientDataScope` / `viewCurrentClinic` 声明）」直接对应** |
| `divisionalId` / `divisionalName` / `divisionalGeneralManager` | 分部（大区）id / 名称 / 负责人 —— **分部 / 大区维度的唯一分组依据**（门店级分组用 `oaOrgId`，见 §四） |
| `addressProvince` / `addressCity` / `addressRegion` | 所在地省 / 市 / 区县 —— 区域维度筛选与展示 |
| `isAssistant` / `preceptorEmployeeName` | 是否助理医生（0-否 1-是）/ 指导医生员工姓名 —— 员工角色上下文；`preceptorEmployeeId` 在 schema 中有声明但实测未返回 |

其余原有字段 `employeeId` / `manageAuths` 等保持不变。

> **`oaOrgId` 与 `clinicId` 是 1:N —— 一个组织机构（`oaOrgId`）可挂多个门店（`clinicId`）**（实测 288 行 = 281 个 `oaOrgId`，其中 7 个各挂 2 个 `clinicId`，如「深圳宝安店」组织 = 深圳牙管家口腔门诊部 + 美年大健康美宝门诊部）。
> 汇总用 `oaOrgId`，接口入参用 `clinicId`。⚠️ **按 `oaOrgId` 汇总 = 把同组织多店合并**，属**组织级口径**，会改变单店数值；出数时必须注明合并了哪些 `clinicId`。

## 二、按名称查找门店规则

- 匹配字段（**模糊匹配 / 包含**）：`abbreviation`（诊所简称）→ `clinicName`（诊所名称）→ `oaOrgName`（组织机构名称）。
- **匹配优先级**：
  1. 先按 `abbreviation` 简称匹配（最稳定）；
  2. 再按 `clinicName` 诊所名称匹配；
  3. 最后按 `oaOrgName` 组织机构名称匹配。
- **多字段同时命中**：取**优先级最高**的命中（简称 → 诊所名 → 组织名）；命中 **0 家** → 明确告知无此门店并给出相近候选。
- 命中后：用命中的 `clinicId` 继续取数，`oaOrgId` 用于汇总分组。

## 三、同组织（`oaOrgId`）多门店合并规则

- 名称匹配命中的多家门店若**同属一个 `oaOrgId`**（如「深圳宝安店」组织 = 深圳牙管家口腔门诊部 + 美年大健康美宝门诊部，两家 `clinicId` 同一 `oaOrgId`）→ **按 `oaOrgId` 合并汇总为组织级门店**，不要求用户单选。
- 合并方式：组织下**所有 `clinicId` 的数据合并后统一聚合**（账单 / 业绩 / 体检登记等明细直接合并，数量与金额相加，去重口径按各指标定义执行）。
- 展示名用 `oaOrgName`（如「深圳宝安店」），并注明包含的 `clinicId` 列表；跨 `oaOrgId` 的多家命中仍**不许自选**，列候选让用户指定。

## 四、分部 / 大区（`divisional*` 三字段）

**分部 / 大区一律用这三个字段区分 —— 不要用 `structName` 推断，也不要逐店扫 `employees_list`**（字段缺失期的旧法已作废，见 [changelog.md](changelog.md) §一）。

| 字段 | 职责 |
| --- | --- |
| `divisionalId` | **分部 / 大区唯一分组键** —— 分部维度汇总按它分组 |
| `divisionalName` | 分部 / 大区展示名 |
| `divisionalGeneralManager` | 分部负责人 —— 按人找分部时过滤此字段 |

- **基数（2026-10-15 实测样本 288 家白名单；白名单行数随授权变化）**：`divisionalId` 与 `clinicId` 是 **1:N** —— 该样本 288 家门店归 **22 个 `divisionalId`**，单分部下辖 1~44 家不等；**一个 `clinicId` 只属一个 `divisionalId`**（实测 0 冲突）。`divisionalGeneralManager` 有值 **286/288**，为空 2 家是法人主体 / 总部（`112数字科技`、`总部`），不属任何业务分部。
- 🚨 **同名负责人可能挂多个 `divisionalId`**（实测「王未」既是 `王未分部(1777616006)` 26 家、又是 `北京（直属分部）(1937425549395931137)` 1 家）⇒ **按 `divisionalGeneralManager` 字符串过滤会误并两个分部**；筛出 `divisionalId` 集合后**先判元素个数**，`>1` 必须先向用户确认是合并还是拆分。
- **三维度分组键对照（不要混用）**：

  | 维度 | 分组键 | 说明 |
  | --- | --- | --- |
  | 门店 / 组织级 | `oaOrgId` | 同组织多店会被合并，见 §三 |
  | 分部 / 大区级 | `divisionalId` | 一个分部含多家门店 |
  | 接口入参 | `clinicId` | 唯一来源 = 工作诊所白名单 |

- **按负责人找分部**：用 `divisionalGeneralManager` 过滤出 `divisionalId` 集合 → 再展开该分部下的全部 `clinicId`；**不要**改用 `structName` 或扫员工表。
- **实测等价性（2026-10-15，与旧双通道法对照）**：`divisionalGeneralManager` 口径 = 旧「`structName` ∪ 逐店扫 `employees_list`」并集的**严格超集** —— 邓海军 13 家 / 刘倩 23 家名单一致；新法多捕到旧扫描的**盲区店**（已撤店、员工表已无该「区域总经理」，如汕头美年店）；**旧扫描侧零独家命中**。成本对比：**1 次调用 2.2s** vs **289 次调用 634s**。
- **出数口径标注**：分部级汇总必须写明「按 `divisionalId` 汇总（`divisionalName` / 负责人），含 N 家门店」并列出 `clinicId` 清单 —— 否则读数的人会当成单店数值。

> 分部名 / 负责人出现同名或跨省情形时，**以 `divisionalId` 为准**，名称仅作展示。

## 五、与员工相关工具的边界

| 工具 | 作用范围 |
| --- | --- |
| `employees_list_work_clinic` | 当前账号**可见的工作门店清单**（本节一 ~ 三）—— 白名单唯一来源 |
| `employees_get_details` | **当前调用者本人**的员工档案（28 字段，全字符串）。不能查别人、**不含手机号**；`postNames` 是**连锁级**岗位（与本文件门店级岗位语义不同） |
| `employees_list` | 按门店查员工列表（12 参数），支持 `search`（姓名 / 工号 / 手机） |
