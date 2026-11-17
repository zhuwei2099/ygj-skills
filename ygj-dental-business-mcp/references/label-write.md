# 标签写入（全库仅有的 2 支写工具）

**适用**：用户要求「给某患者打个标签 / 去掉某标签」「给某个企微好友打标签」，或需要核对标签写入的前置条件、副作用与回读方式。

**基线**：2026-11-13 实测 `tools/list`。本域两支工具是**整个 MCP 唯一的写操作**，其余 45 个（本技能收录）全部只读。

> ⚠️ **未实测声明（必读）**：本文的入参、必填项来自 `tools/list` **schema 声明**；**写路径本次没有实际执行**（避免污染生产数据）。因此 **返回结构、成功/失败文案、错误码、是否幂等** 均**未验证**。首次使用必须先做最小样本验证（见 §六），再常规使用。

---

## 一、两支工具对照

| 项 | `patients_incremental_submit_labels` | `wecom_externalcontact_mark_tag` |
| --- | --- | --- |
| 作用对象 | 患者（HIS 主档） | 企微外部联系人（好友） |
| 必填 | `patientId` | `wecomExternalUserId` |
| 增标签 | `addLabelIds`（**数组**） | `addLabelIds`（**数组**） |
| 删标签 | `deleteLabelIds`（**数组**） | `deleteLabelIds`（**数组**） |
| 语义 | 在**已有标签基础上增量**增删 | 同左 |
| 副作用 | 只改患者标签 | **好友已关联患者时，同步更新该患者标签** |
| schema `title` | 患者增量打标签参数 | 企微好友增量打标签参数 |

### 三条硬语义

1. **`addLabelIds` / `deleteLabelIds` 至少一侧非空**（schema 描述原文）。两侧都传 `[]` 属无效调用。
2. **空数组 = 该侧不操作**，**不是「清空全部标签」**。想清空某患者的标签必须显式列出要删的每个 id。
3. **这是「增量」接口**，不是「以入参为准整体覆盖」。因此**不要**为了「改成目标状态」而盲目把所有非目标标签塞进 `deleteLabelIds` —— 先读现状、算差集。

---

## 二、标签 ID 从哪来（不得臆造）

| 需要什么 | 用哪个工具 | 说明 |
| --- | --- | --- |
| 门店**可用**的标签定义（全量候选） | `basedatas_list_label_definitions` | 必填 `clinicId`；**门店级**标签字典 |
| 某患者**当前已打**的标签 | `patients_list_labels` | 必填 `patientId`；`data` **直挂数组** |
| 某好友当前已打的标签 | `wecom_list_friends` → `records[].tags` | 标签**中文名**数组，**不含 id** |

- 两支写工具都只收 **HIS 标签 id**（schema 属性描述原文「HIS 标签」）。**面向用户一律用中文标签名，提交前才换成 id，并在确认信息里同时给出「名 → id」对应。**
- ⚠️ **id 不可猜**：`basedatas_list_label_definitions` 返回的 id 才是合法来源；`basedatas_list_bizdict` 对**错误的 `code` 会静默返回 `{}`**，不要拿字典接口的结果当标签 id。
- ⚠️ **同名标签可能不止一个 id**（不同门店 / 不同层级各有一套定义）。命中多个时**列候选让用户确认**，不得替他挑一个。

---

## 三、执行流程（六步，缺一不可）

1. **确认意图**：用户是否**明确要求改数据**。「能不能打标签」「支持打标签吗」这类问句 → **只回答能力，不调用写工具**。
2. **定位对象**：患者 → `patients_quick_search` / `patients_list` 拿 `patientId`；企微好友 → `wecom_list_friends` 拿 `externalUserId`，**原值直接传给写工具的 `wecomExternalUserId`**。

   > ✅ **映射已实测（2026-11-13，只读核对）**：取 `wecom_list_friends.records[].externalUserId` = `wma0G5KQ…`，连同同行的 `corpId` 调 `wecom_get_friends_details`，返回**同一位好友**（`externalUserId` 原样回显）⇒ 出参 `externalUserId` 与入参 `wecomExternalUserId` **是同一个值，只是字段名不同**。`corpId` 也从同一行取，无需外部提供。
3. **解析标签名 → id**：`basedatas_list_label_definitions`（候选）+ `patients_list_labels` / `records[].tags`（现状）。
4. **算差集**：只把「目标有、现状无」放进 `addLabelIds`，「现状有、目标无」放进 `deleteLabelIds`。已在目标态的不提交。
5. **向用户确认**：对象（姓名 / 病历号 / 门店）+ 标签中文名 + 增删方向 + **企微侧联动副作用**（若好友已关联患者）。确认后再调用。
6. **写后回读**：`patients_list_labels`（企微侧另回读 `wecom_list_friends.records[].tags`）核对。**回读不一致或读不到，一律报告失败/未确认，不得写成「已成功」。**

---

## 四、范围与越权

- 两支写工具**都不收 `clinicId`**，§B3.1 的门店白名单闸门**无法直接套用**。
- 代偿做法：先取到对象，确认其所属门店在 `employees_list_work_clinic` 白名单内，**再**执行写。
- 对象归属是否由服务端按租户校验：**schema 未声明、未实测** ⇒ **不得假定「跨店 / 跨租户也能写」，也不得假定「一定会被拦」**。遇到 `UPSTREAM_BUSINESS_REJECTED` 时按多因笼统码处理（可能缺参、可能无权）。
- **白名单取不到 → 不执行任何写**（fail-closed，同 §B3.1）。

---

## 五、禁止清单

| ⛔ 禁止 | 原因 |
| --- | --- |
| 未经用户明确要求就写 | 写工具默认不执行（铁律 14） |
| 按患者 / 好友列表**批量遍历写** | 影响面不可控；一次一对象 |
| 把写工具放进重试循环 | 重试语义未验证，可能重复写入或掩盖失败 |
| 只凭返回码宣称成功 | 必须回读（§三 第 6 步） |
| 用 `deleteLabelIds=[]` 表达「清空标签」 | 空数组 = 不操作 |
| 用猜测的 id 提交 | id 只能来自 `basedatas_list_label_definitions` / 现状读取 |
| 把读侧的「禁用 labelId 匹配」误用到写侧 | 读侧统计仍按**标签名**精确比对；写侧**必须**用 labelId —— 两者不冲突，见 [wecom-friends-and-labels.md](wecom-friends-and-labels.md) |

---

## 六、首次使用的最小样本验证（必做）

1. 选 **1 个**测试患者（或 1 个测试企微好友），记录写前状态（`patients_list_labels` 原文）。
2. 只提交 **1 个** `addLabelIds`，观察：返回结构、`code`、是否有 `isError`、写入是否生效、是否连带给对象加了别的标签。
3. 再提交 **1 个** `deleteLabelIds`，同样复核。
4. 验证通过后，把实际返回形态补进本文 §一，并删掉顶部的「未实测声明」相应条目。
5. 若第 2 步返回 `[MCP-AUTH-002]` ⇒ **工具已注册但当前账号未开通写权限**，按铁律 6 找服务端开授权，**不要答复「功能没有」**。

---

## 七、与「患者标签 / 企微好友标签」读侧口径的关系

- 读侧（统计 / 筛选）**唯一合法来源**仍是 `wecom_list_friends.records[].tags`（企微好友标签）与 `patients_list_labels`（患者标签），**按标签名精确比对、禁用 labelId**（见 [wecom-friends-and-labels.md](wecom-friends-and-labels.md)）。
- 写侧两套体系共用 **HIS 标签 id**；`wecom_externalcontact_mark_tag` 的联动语义（好友关联患者 → 同步患者标签）恰恰说明二者在**写路径上是同一套标签**。
- 结论：**读用名、写用 id**。不要把写接口能接受 id 解读为「读侧可以按 id 匹配」。
