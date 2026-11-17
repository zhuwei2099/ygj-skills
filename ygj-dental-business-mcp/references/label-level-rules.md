# 交易表 labelLevel 层级统计规则 v1.0（项目数量与交易金额）

**定稿：2026-10-15**｜需要按一级 / 二级分类统计项目数量与交易金额时读本文件。

## 适用对象与数据源

- 交易表：`clinics_list_bill_docs`（门店）、`patients_list_bill_docs`（患者）；**一行 = 一条收费明细**（一次治疗常拆多行：主项目 + 材料 + 加收）
- 分类维度来源：`basedatas_list_charge_combs`（组合表，主键 **`id`**）、`basedatas_list_charge_items`（价目表，主键 **`chargeItemId`**）；标签与价格均为**门店级**，必须逐店拉表
- 🚨 **JOIN 键陷阱（必记）**：`bill_docs.combId → charge_combs.id`（组合表**没有** `combId` 字段）；`bill_docs.mainItemId / chargeItemId → charge_items.chargeItemId`（价目表**没有** `mainItemId` 字段）；按同名字段 JOIN 会**全盘落空**

## 行分类：三层优先级（自上而下命中即止，不回退）

1. `combId` 有值 → 用 `charge_combs[combId]` 的 `labelLevel1` / `labelLevel2`；查不到或一级为空 → 「组合缺失」桶
2. `combId` 空 且 `mainItemId` 有值 → 用 `charge_items[mainItemId]` 的 `labelLevel1` / `labelLevel2`；查不到或一级为空 → 「主项目缺失」桶
3. `combId`、`mainItemId` 均空 → 用 `charge_items[chargeItemId]` 的 `labelLevel1` / `labelLevel2`；查不到或一级为空 → 「项目缺失」桶

- **不回退**：① 命中但查不到 → 归「组合缺失」桶，**不**下沉到 ②/③；缺失桶**单列展示**，不静默丢弃

## 行类型定义

| 行类型 | 判据 |
| --- | --- |
| 主项目行 | `mainItemId` 有值 **且** `chargeItemId == mainItemId`（治疗主项目） |
| 单项目行 | `combId` 空 **且** `mainItemId` 空（无组合、直接单收） |
| 组合子项行 | 其余（组合内的材料 / 加收 / 步骤行） |

## 数量与金额聚合范围（核心：两者不同）

| | 组合（分支①） | 主项目（分支②） | 单项目（分支③） | 缺失桶 |
| --- | --- | --- | --- | --- |
| 层级字段来源 | `charge_combs[combId].labelLevel1/2` | `charge_items[mainItemId].labelLevel1/2` | `charge_items[chargeItemId].labelLevel1/2` | 无（单列） |
| **数量 `refundCount`** | **仅主项目行**（`chargeItemId==mainItemId`），非主项目行计 **0** | 同左 | **整行**计入 | 整行计入 |
| **金额 `payAmount`** | **所有行**无差别计入 | 同左 | 该行 | 该行 |

- **数量只计主项目行**：同次治疗多行共享同一 `mainItemId`，且每行 `refundCount` 是同一个数量（补 1 颗牙 = 修复费+树脂+脱敏+盖髓 4 行，`refundCount` 都是 1）；全行求和 ⇒ 一颗牙重复计 4~5 次
- **金额计全行**：材料费与加收费属于该次治疗的真实收入
- **组合组内无主项目行**（无任一行满足 `chargeItemId==mainItemId`）→ **只记金额、不计数量**（数量计 0），该组须**单列披露**（组合 id / 名称 / 行数 / 金额）

## labelLevel2（数组）展开规则

- `labelLevel2` 是**数组**，一行可能带多个二级标签 → **逐元素展开，该行数量与金额同时计入每一个二级桶** ⇒ 二级合计 ≥ 一级合计（差值即多标签行重复计入部分）
- 空数组 / 无标签 → 归 `(未分级)` 桶；`labelLevel1` 是字符串，直接归对应一级桶

## 汇总维度与勾稽

- 固定维度：`门店(clinicId) × 分支 × 一级 × 二级`，另附「缺失」单列；度量：`行数`、`Σ数量`、`Σ金额`（全部用 `Decimal`，避免浮点误差）
- 多店场景：**按门店分表统计后再合并**，禁用单店代表全公司
- **必做勾稽（5 项）**：
  1. `Σ一级行数 + 缺失行数 = 总行数`
  2. `Σ一级数量 + 缺失数量 = Σ数量贡献`
  3. `Σ一级金额 + 缺失金额 = ΣpayAmount`
  4. `Σ二级数量 ≥ Σ一级数量`
  5. `Σ二级金额 ≥ Σ一级金额`

## 口径红线（❌ 禁止）

- ❌ 用 `fdiToothCodes` 求和当颗数（它是**牙位列表**「哪些牙」，不是数量）
- ❌ 用 `itemTypeMasterName` / `itemTypeSubName` 做分类（分类维度**只认 `labelLevel1` / `labelLevel2`**）
- ❌ 数量对全行求和（一颗牙重复计 4~5 次）
- ❌ 用账单接口 `clinics_list_bills` / `patients_list_bills` 算收入（按 `firstChargeTime` 归集，漏跨月退款 / 补收老单）
- ❌ 用 `refundAmount` / `chargeRefundAmount` 当金额（恒为 0，不可用）
- ❌ 按同名字段 JOIN 基础表（组合表主键是 `id`，价目表主键是 `chargeItemId`）

## 与其他口径的关系

- 业绩 1 级 / 2 级标签分类口径与本规则**标签来源与关联规则一致**，数量 / 金额口径**一律按本规则执行** → [business-category-and-store-summary.md](business-category-and-store-summary.md)
- 组合交易按患者汇总**共用**本规则的三层优先级、数量/金额范围与红线口径；其按患者汇总的实收合计应与本规则一级金额合计（扣除缺失桶）**一致，可交叉验证** → [combo-transaction-by-patient.md](combo-transaction-by-patient.md)
- 已作废的旧数量口径（331 / 166 / 329 / 443 / 121）及其错误原因 → [changelog.md](changelog.md)
