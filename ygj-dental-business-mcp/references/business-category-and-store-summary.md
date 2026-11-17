# 门店业绩分类与门店级汇总口径

涉及**业绩 1 级 / 2 级标签分类**，或需要**按门店（`oaOrgId`）汇总指标**时读本文件。

> **分部 / 大区维度汇总改用 `divisionalId`**，见 [clinic-and-staff-lookup.md](clinic-and-staff-lookup.md) §四。本文件讲的是**门店 / 组织级**口径（`oaOrgId`），两者不要混用。

## 一、门店业绩分类统计口径（业绩 1 级 / 2 级标签）

### 分类维度与基础数据来源

| 业绩分类 | 基础数据接口 | 分类依据 |
| --- | --- | --- |
| **组合业绩** | `basedatas_list_charge_combs`（组合基础数据） | 业绩 1 级标签 `labelLevel1`、业绩 2 级标签 `labelLevel2` |
| **项目业绩** | `basedatas_list_charge_items`（收费项目基础数据） | 业绩 1 级标签 `labelLevel1`、业绩 2 级标签 `labelLevel2` |

### 两级标签使用方式

- `labelLevel1`（业绩 1 级标签）：一级分类维度（业绩大类），先按此聚合；
- `labelLevel2`（业绩 2 级标签）：二级分类维度（业绩细分，如补牙档位类），在一级结果下细分；
- 两级**独立取值、层级嵌套**：先按 `labelLevel1` 聚合，再在其内按 `labelLevel2` 细分；两级不得混用、不得互相替代。

### 与交易明细及既有口径的关联

- 交易明细中的组合场景（`combId` 非空）→ 以 `combId` 关联 `basedatas_list_charge_combs`，取其 `labelLevel1` / `labelLevel2` 归类为**组合业绩**；
- 交易明细中的主项目 / 单项目场景（`mainItemId` / `chargeItemId`）→ 以 `mainItemId` / `chargeItemId` 关联 `basedatas_list_charge_items`，取其 `labelLevel1` / `labelLevel2` 归类为**项目业绩**；
- 数量 / 金额口径**一律按「交易表 labelLevel 层级统计规则」执行**：数量仅主项目行（组合 / 主项目分支）或整行（单项目 / 缺失）、金额取全行 `payAmount` SUM。
  → 见 [label-level-rules.md](label-level-rules.md)

### 结构与口径一致性保证

- 组合业绩与项目业绩共用**同一套两级标签结构与聚合方式**，仅基础数据来源接口不同（`charge_combs` / `charge_items`）；
- 两级标签的聚合、细分、核验逻辑完全一致（二级业绩聚合值应等于对应一级业绩聚合值的细分），保证两类业绩统计可交叉核验。

## 二、门店数据分析汇总规则（`oaOrgId` 维度）

- **汇总维度**：按组织机构 id（`oaOrgId`）分组汇总，作为门店级唯一标识；展示名用 `oaOrgName`（组织机构名称）与 `clinicName`（诊所名称）。
- **统计指标**：门店营业天数（`medicallyDate` 去重计数）、医生出勤天数（员工 `employeeId+employeeName` 聚合后按日期去重）、门店当天上班医生数据（`workDoctorNum` 求和）等体检登记指标；营业额、成交人数等金额 / 人数指标沿用 [revenue-and-deal-count.md](revenue-and-deal-count.md)。
- **汇总范围**：以 `employees_list_work_clinic` 返回的白名单为范围；某门店无数据时按 `0` 计入汇总（如无体检登记的门店营业天数 = 0），**不静默跳过、不换店替代**。
- **`oaOrgId` 与 `clinicId` 的关系**：两者均为门店标识，**汇总用 `oaOrgId`，接口入参用 `clinicId`**；二者是 **1:N**（一个组织可挂多个门店，2026-10-15 样本 288 行 = 281 个 `oaOrgId`，7 个各挂 2 个 `clinicId`；白名单行数随授权变化）⇒ **按 `oaOrgId` 汇总会把同组织多店合并**，属**组织级口径**，不得当单店口径使用。
- **分部 / 大区维度不走 `oaOrgId`**：分部级汇总分组键是 `divisionalId`（`divisionalName` 展示、`divisionalGeneralManager` 负责人），属**独立维度**，见 [clinic-and-staff-lookup.md](clinic-and-staff-lookup.md) §四。
  → 白名单字段、按名称找店、同组织并店规则见 [clinic-and-staff-lookup.md](clinic-and-staff-lookup.md)
