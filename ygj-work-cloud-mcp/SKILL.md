---
name: ygj-work-cloud-mcp
description: 通过 ygj-work-cloud-mcp 接口查询工作云数据，覆盖应用、部门、法人主体、人员、模型（表单/流程）、权限视图、模型记录数据与关联表单组件候选记录，另含 2 支模型记录删除工具。当用户提到工作云、工作云应用、表单模型、流程模型、权限视图、模型记录、表单数据、部门、人员、法人主体、删除模型记录等操作时使用本技能。
version: 2026.11.19.3
---

# ygj-work-cloud-mcp 接口

通过 `ygj-work-cloud-mcp` 这个工作云 MCP，从「接通」用到「取到数据」。

**环境：生产** `https://api-chishu.lifesega.com/v1/mcp`｜**共 14 个工具**（2026-11-19 实测 `tools/list`）｜其中 **12 个只读查询**、**2 个删除**，**没有新增、编辑、流程审批类工具**。

> ⚠️ **接口标签说明**：服务端 `tools/list` **不返回标签字段**（工具定义只有 `name` / `title` / `description` / `inputSchema` / `outputSchema`）。当前凭据可见的 14 个工具全部以 `work_` 开头，即「工作云」这一组；若需要其他标签的接口，必须换用被授权到对应标签的 MCP 账号。
>
> ✅ **本次实测**（2026-11-19）：`work_apps_list`、`work_departments_search`、`work_legal_entities_search`、`work_models_list`、`work_models_views`、`work_models_form_info`、`work_models_flow_from_info`、`work_models_components`、`work_models_records_search`、`work_models_records_data` 已真实调用并核对返回结构。
>
> ⚠️ **未执行**：`work_users_search`（会返回人员原始手机号、证件号，避免无必要拉取）、`work_models_components_related_records`（测试租户无关联表单组件）、`work_models_records_delete` / `work_models_records_batch_delete`（破坏性操作，仅核对 schema）。这些工具的返回与错误文案以首次实际调用为准。
>
> 🔌 **首次加载**：先读同目录 `mcp.json` 建立连接，再进入 §A / §B。连接参数只认这个文件。

## 全局铁律

1. **能力边界优先。** 先判断问题是否在 14 个工具范围内，再选工具，不许试错式调用。没有「新建记录 / 修改记录 / 发起审批 / 处理审批」接口。
2. **删除是破坏性操作，默认不执行。** `work_models_records_delete` / `work_models_records_batch_delete` 是全库仅有的写操作。① 必须用户明确要求才调用；② 删除前列出「模型 + 记录 ID + 记录标识字段」让用户确认；③ 优先单条删除，批量删除只在用户明确给出多条 ID 时使用；④ **禁止遍历列表批量删**；⑤ 删除后必须重新查询确认记录已消失，不能只凭 `code:200` 宣称成功。
3. **不猜 ID。** `appId`、`formId`、`authGroupId`、`fieldId`、`formRecordId` 都必须从上游工具取，不得编造、不得跨模型复用。
4. **`authGroupId` 是权限视图闸门，不是可选装饰。** 必须来自 `work_models_views`；拿不到视图就不要查记录。
5. **字段表述用中文 `title`，调用入参用英文 code。** 面向用户输出「商品名称」「提交时间」这类中文名，请求里仍写 `formId`、`authGroupId`。
6. **`formItems[].id` 才是字段数据键，`name` 是组件类型。** 详见 §B3.4，这是最容易读错数据的一处。
7. **隐私最小必要。** `work_users_search` 返回 `phoneNumber`（原始手机号）与 `idNumber`（证件号）；`work_legal_entities_search` 返回统一社会信用代码。除非用户明确要人员/法人清单，不主动整段外发。
8. **否定结论必须举证。** 「schema 声明」≠「运行时返回」；未实测的工具只能写「本次未验证」，不能写成「没有该字段」。
9. **分页形态因工具而异。** 先判返回形态再解析，见 §B3.3；对非分页工具查 `data.records` 会误报「没有数据」。
10. **错误码看文案，不只看码。** `[MCP-PARAM-001]` 是通用参数/请求码，至少包含「缺少必填字段」「未知工具」等不同语义，判定前比对完整文案。

## 路径约定

技能本体位于 `ygj-skills/ygj-work-cloud-mcp/`，正文与参考文件均用相对路径。本技能目前没有内置脚本。

- `mcp.json`：MCP 接入参数（端点、传输、OAuth 配置），首次加载与重连时读取。
- `SKILL.md`：使用说明与工具契约正文。

## 第一步：模式路由

| 用户意图 | 模式 | 去处 |
| --- | --- | --- |
| 接入 / 安装 / 配 MCP / 换端点 / 更新凭据 | **A 接入** | §A |
| 查应用、部门、人员、法人主体、模型、记录数据 | **B 查询** | §B |
| 删除模型记录 | **B 写操作（需确认）** | §B3.7 |

## §A 模式：接入

### A1 连接参数

**接入参数统一放在同目录 [mcp.json](mcp.json)，这是唯一来源。** 首次加载本技能、需要建立连接时，先读取该文件，不要从本正文或对话里另抄一份；换端点、换账号只改 `mcp.json`。

| 项 | 值 |
| --- | --- |
| 端点 | `https://api-chishu.lifesega.com/v1/mcp` |
| 传输 | `streamable-http`，`protocolVersion: 2024-11-05` |
| 鉴权 | OAuth2 `client_credentials`（`client_secret_basic`） |
| Token 端点 | `https://api-chishu.lifesega.com/oauth2/token` |
| Scope / Resource | `mcp.invoke` / `https://api-chishu.lifesega.com/v1/mcp` |
| Token 有效期 | 900 秒，不返回 refresh_token |

首次加载时按以下顺序解析凭据，**填进 `mcp.json` 的 `clientId` / `clientSecret` 后立即校验 JSON 语法**：

1. 环境变量 `YGJ_WORK_CLOUD_APP_KEY` / `YGJ_WORK_CLOUD_APP_SECRET`；
2. 本机凭据文件 `~/.config/ygj-work-cloud-mcp-credentials.json`（`{"appKey":"…","appSecret":"…"}`）；
3. 都取不到就向用户索取，**不要编造**。

凭据只落本机凭据文件或环境变量，**不写进受版本控制的配置文件、不回显到对话**。Claude Code 这类不支持 client_credentials 直连的客户端，需走本地 stdio 桥接（换 token、过期前刷新、401 重试）。一次只接一个 Agent。

## §B 模式：业务查询

### B1 先判能力边界

| 用户问的是 | 能否回答 | 怎么做 |
| --- | --- | --- |
| 我能访问哪些应用 / 应用分组 | ✅ | `work_apps_list`（无参） |
| 部门结构 / 某部门下有哪些部门 | ✅ | `work_departments_search`（`deptId` 传 `0` 查顶级） |
| 人员列表 / 某人属于哪个部门 | ✅ | `work_users_search`（支持按部门、手机号/拼音关键词筛） |
| 可访问法人主体清单 | ✅ | `work_legal_entities_search` |
| 某应用下有哪些模型（表单/流程） | ✅ | `work_models_list`（必填 `appId`） |
| 某模型有哪些权限视图（可读范围） | ✅ | `work_models_views`（必填 `formId`） |
| 某模型的字段结构 / 组件配置 | ✅ | 普通表单 `work_models_form_info`；流程模型 `work_models_flow_from_info`；只要组件清单用 `work_models_components` |
| 某模型某视图下的记录列表 / 按字段筛选 / 排序 / 分页 | ✅ | `work_models_records_search`（必填 `formId` + `authGroupId`） |
| 某条记录的完整表单数据 | ✅ | `work_models_records_data`（必填 `formId` + `authGroupId` + `formRecordId`） |
| 关联表单组件的候选记录（选关联数据时下拉用什么） | ✅ | `work_models_components_related_records`（必填 `formId` + `fieldId`） |
| 流程审批状态 / 当前节点 / 处理人 | ✅（只读） | 记录在 `work_models_records_search` 返回的 `statusText` / `nodeName` / `approveUsers` / `bussinessStatus` / `endTime` 等字段里；**没有独立的审批查询工具** |
| 新建、修改记录 / 发起或审批流程 | ❌ | 无对应工具，只能如实说明不具备该能力 |
| 删除模型记录 | ⚠️ 可写 | 见 §B3.7，默认不执行 |

### B2 工具速查（14 个）

参数名以代码标注，**调用时一律用英文字段名**；命名统一为 `work_<域>_<动作>`。

| 分组 | 工具数 | 入口参数 | 返回形态 |
| --- | --- | --- | --- |
| 组织与身份 | 4 | 无必填或 `appId` 外的简单条件 | `apps`/`departments` 非分页；人员/法人分页 |
| 模型元数据 | 5 | `appId` / `formId` | 分页对象 / 裸数组 / 单对象 |
| 记录读取 | 2 | `formId` + `authGroupId`（+ `formRecordId`） | 分页对象 / 单对象 |
| 关联组件 | 1 | `formId` + `fieldId` | 分页对象 |
| 记录删除 | 2 | `formId` + `id`/`ids` | 布尔 |
| **合计** | **14** | — | **12 只读 + 2 删除** |

#### 一、组织与身份（4）

| 工具 | 必要参数 | 说明 |
| --- | --- | --- |
| `work_apps_list` | 无 | 当前用户可访问应用，按分组返回。`data.groups[]` → `{groupId, groupName, items[]}`；`items[]` → `{appId, groupId, appName, logo, admin}`。`admin` 表示当前用户是否该应用管理员。**不分页** |
| `work_departments_search` | 无（`deptId` 传 `0` 查顶级） | 部门展开。可选：`deptId`（要展开的部门）、`permPid` + `level`（指定层级起点与深度）、`ssd`（`0` 当前部门 / `1` 上下级关联部门，默认 `0`）、`deptName`（模糊）。`data.items[]` → `{id, name, status, leader, parent_id}`，`status` 为 `0` 启用 / `1` 禁用。**不分页** |
| `work_legal_entities_search` | 无 | 可访问法人主体。可选：`name`（企业名模糊）、`uscc`（纳税号模糊）、`current`、`size`（上限 500）。分页对象 `data.records[]` → `{id, name, uscc}` + `total/size/current/pages` |
| `work_users_search` | 无 | 人员列表。可选：`deptId`（含兼任部门）、`keyword`（手机号 / 全拼 / 拼音首字母模糊）、`status`（`0` 正常 / `1` 离职，默认在职）、`current`、`size`（上限 500）。分页对象 `data.records[]` → `id/name/isLeader/avatar/sex/selected/mainDeptId/mainDeptName/phone/phoneNumber/idNumber/jobNumber/status`。⚠️ `phoneNumber` 是原始手机号、`idNumber` 是证件号，按铁律 7 最小化使用 |

#### 二、模型元数据（5）

| 工具 | 必要参数 | 说明 |
| --- | --- | --- |
| `work_models_list` | 应用 ID（`appId`） | 某应用下当前用户可访问的模型。可选：`keyword`（模型名模糊）、`types`（字符串数组，`form` 普通表单 / `flow` 流程模型）。`data.records[]` → `{formId, appId, groupId, formName, type, processDefId}`；**只有 records、没有 total/分页**，一次全量返回（实测 42 条一次返回） |
| `work_models_views` | 模型 ID（`formId`） | 该模型的**权限视图**。`data` 就是**裸数组** → `{id, name, dataAuthType, dataPerm}`。`dataAuthType`：`0` 全部 / `1` 本人 / `9` 自定义；`dataPerm` 是动作权限 JSON 字符串。**默认视图的 `id` 可能是 `"0"`**（实测） |
| `work_models_form_info` | 模型 ID（`formId`） | **普通表单**的完整配置。`data` 单对象：`appId/groupId/formId/formName/type/version/formItems[]/formConfig/settings/businessKey/logo/curt`。`settings` 是 JSON 字符串，`formConfig` 是对象 |
| `work_models_flow_from_info` | 模型 ID（`formId`） | **流程模型**的表单与流程信息。`data` 单对象：`appId/formId/processDefId/isStop/formName/logo/formItems[]/formConfig/process/curt`。`process` 是流程树对象（`id/type/name/props/children`） |
| `work_models_components` | 模型 ID（`formId`） | 模型实际使用的组件清单。`data` 单对象：`formId/formName/type/modelVersion/formItems[]`；`formItems[]` → `{id, icon, name, props, title, value, key, valueType, perm}`。`perm`：`E` 编辑 / `R` 只读 / `H` 隐藏 |

> `work_models_form_info` 与 `work_models_flow_from_info` 返回结构接近，但入口不同：**普通表单用前者、流程模型用后者**。不确定类型时先用 `work_models_list` 看 `type`。

#### 三、记录读取（2）

| 工具 | 必要参数 | 说明 |
| --- | --- | --- |
| `work_models_records_search` | `formId`、`authGroupId`（权限视图 ID） | 查询指定视图下的记录列表。可选：`keyword` + `keywordFields[]`（关键词与检索字段范围）、`propsLogic`（`1` AND / `2` OR）、`fieldProps[]`（字段筛选，见 §B3.5）、`orders[]`（`{fieldId, order}`，`0` 升序 / `1` 降序）、`current`、`size`、`sort[]`（游标续页）。分页对象 `data.records[]`，见 §B3.3 |
| `work_models_records_data` | `formId`、`authGroupId`、`formRecordId` | 单条记录完整数据。可选 `schemaVersionMode`：`CURRENT`（按模型最新版本，默认）/ `RECORD`（按记录保存时的版本）。`data` 单对象：模型元信息 + `formDataId` + `formData` + `staterUser`。⚠️ 字段名是服务端的 `staterUser`（拼写如此），表示提交人 `{id, name, empty}` |

#### 四、关联表单组件（1）

| 工具 | 必要参数 | 说明 |
| --- | --- | --- |
| `work_models_components_related_records` | `formId`、`fieldId`（关联表单组件的字段 ID） | 关联表单组件在选择数据时的候选记录。可选参数与 `records_search` 基本一致（`keyword` / `keywordFields` / `propsLogic` / `fieldProps` / `current` / `size` / `sort`）。返回分页对象，记录结构与 `records_search` 相同。`fieldId` 必须是 `props.relatedForm.isRelatedForm = true` 的组件 |

#### 五、记录删除（2，写操作）

| 工具 | 必要参数 | 说明 |
| --- | --- | --- |
| `work_models_records_delete` | `formId`、`id`（普通表单主记录 ID） | 删除单条记录，`data` 返回布尔 |
| `work_models_records_batch_delete` | `formId`、`ids[]`（普通表单主记录 ID 数组） | 批量删除，`data` 返回布尔。**禁止遍历列表自动批量删** |

> 两个工具 schema 均写明作用于「普通表单主记录」；**流程模型记录的删除行为未实测**，不得假定可用。删除不可逆，执行纪律见铁律 2 与 §B3.7。

### B3 取数范围与调用硬约束

#### 1. 标准取数链路

```text
work_apps_list
  → 取 appId
work_models_list(appId)
  → 取 formId 与 type
work_models_views(formId)
  → 取 authGroupId（视图 id）
work_models_records_search(formId, authGroupId)
  → 取记录 id 与 formDatas
work_models_records_data(formId, authGroupId, formRecordId)
  → 取 formData 完整值
```

查字段结构在中间插入：普通表单 `work_models_form_info`，流程模型 `work_models_flow_from_info`，组件清单 `work_models_components`。

#### 2. 权限视图与范围

- `authGroupId` **只能**来自 `work_models_views`，不要手工填 `0` 以外的猜测值。
- **默认视图实测 `id = "0"`、`dataAuthType = 0`（全部）**；是否真的返回全部数据仍以服务端权限为准。
- `dataAuthType`：`0` 全部 / `1` 本人 / `9` 自定义。用户问「为什么只看到自己的数据」时，先看视图的 `dataAuthType`。
- 视图返回的 `dataPerm` 是动作权限 JSON 字符串，**只用于解释可读/可写范围，不替代服务端鉴权**。

#### 3. 分页与返回形态

**先判返回形态，再解析。**

| 形态 | 判定方法 | 工具 |
| --- | --- | --- |
| 分页对象 | `data.records` + `data.total` | `work_legal_entities_search`、`work_users_search`、`work_models_records_search`、`work_models_components_related_records` |
| 裸数组 | `data` 本身就是数组 | `work_models_views` |
| 单对象 | `data` 是对象 | `work_models_form_info`、`work_models_flow_from_info`、`work_models_components`、`work_models_records_data` |
| 分组对象 | `data.groups[]` | `work_apps_list` |
| 列表对象 | `data.items[]` | `work_departments_search` |
| 仅 records | `data.records`，**无 total / 无分页** | `work_models_list` |
| 布尔 | `data: true/false` | 两个删除工具 |

分页工具的 `size` 上限：`work_legal_entities_search` / `work_users_search` 为 **500**；两个记录查询工具的 schema 未声明上限，按服务端返回为准。`current` 从 **1** 开始。

#### 4. 字段数据键映射（最容易读错的一处）

- `formItems[].id`（如 `field7902010762500`）**才是** `formData` 对象里的键。
- `formItems[].name` 是**组件类型**（如 `TextInput`、`DateTime`、`AmountInput`），**不是**数据键，也不是字段中文名。
- 字段中文名看 `formItems[].title`；可读性/编辑性看 `perm`（`E`/`R`/`H`）。
- 记录列表 `records[].formDatas[]` 每项：`{id（字段ID）, name（组件类型）, title（中文字段名）, valueType, fieldValue, format, max, relatedFormName}`。**展示用 `title`，与字段定义对齐用 `id`。**
- `work_models_records_data.data.formData` 是**对象**：`{ "<字段id>": <值> }`，值类型随 `valueType` 变化（String / Number / Date / User / Dept / Array / Object）。
- `valueType` 可能缺失（实测 `LegalPicker` 组件就没有 `valueType`），不要假定每个组件都有。

#### 5. 字段筛选 `fieldProps`

每个筛选项：`{ fieldId, rule, textValue?, numberValue?, textValues?, numberValues? }`。

| 部分 | 含义 |
| --- | --- |
| `fieldId` | 参与筛选的组件或固定字段 ID（来自 `formItems[].id`） |
| `rule` | `1` 等于 / `2` 包含 / `3` 等于任意一个 / `4` 大于等于 / `5` 大于 / `6` 小于等于 / `7` 小于 / `8` 选择范围 / `9` 动态日期范围 / `10` 不包含 / `11` 不等于 / `12` 为空 / `13` 不为空 |
| `textValue` | 单个文本、选项、标识或日期时间 |
| `numberValue` | 比较数值或动态条件编码 |
| `textValues` | 多选内容或日期时间区间 |
| `numberValues` | 数值区间上下界 |

`propsLogic`：`1` = 所有条件都满足（AND），`2` = 任一满足（OR）。

#### 6. 游标续页 `sort`

- 首屏不传 `sort`。
- 取上一页**最后一条记录的 `sort` 数组**原样传入下一页（每项 `{value, kind}`，`kind` 如 `Long` / `String`）。
- `current` / `size` 页码分页与 `sort` 游标是两套机制；**不要混用**，深度翻页优先用游标。
- 子项 `kind` 当前不支持 `Any`。

#### 7. 删除执行纪律

1. 用户明确要求删除，且能说出要删哪些记录。
2. 用 `work_models_records_search` 定位记录，列出「模型名 + 记录 ID + 一两个可辨识字段（如 `title`/提交人/提交时间）」给用户确认。
3. 确认删除范围是**普通表单主记录**；流程模型记录先说明未验证。
4. 单条用 `work_models_records_delete`；只有用户明确给多条 ID 时才用 `work_models_records_batch_delete`。
5. 删除后重新 `work_models_records_search` 回读，确认记录数减少且目标 ID 不再出现；**回读不到才算成功**。

#### 8. 错误与限流

- 成功包络：`{ code: 200, success: true, msg: "操作成功", data: ... }`，`structuredContent` 与 text 内容一致。
- 失败以 MCP `isError: true` + 纯文本错误返回，不是 JSON 包络。实测：
  - `[MCP-PARAM-001] 缺少必填字段，路径 /formId` → 少传必填参数。
  - `[MCP-PARAM-001] Unknown or unpublished Tool` → 工具名不存在 / 未发布。**必须比对完整文案**，不能只凭 `MCP-PARAM-001` 判定「工具不存在」。
- 本次未观测到 `MCP-AUTH-002`（已注册但账号未授权）；如遇到，按「需要开授权」处理，不要答复「功能没有」。
- 如遇 `MCP-LIMIT-001`，退避重试（3s / 6s / 9s）；批量取数优先串行，稳定后再考虑小幅并发。

### B4 端到端示例

#### 示例 1：查某应用下有哪些表单和流程

1. `work_apps_list` → 按 `appName` 找到目标应用，取 `appId`。
2. `work_models_list`：

   ```json
   { "appId": "…" }
   ```

3. `data.records[]` 里 `type` 为 `form` 的是普通表单、`flow` 的是流程模型；输出用 `formName`，并说明总数按数组长度统计（该工具没有 `total`）。

#### 示例 2：查某表单最近记录

1. `work_models_views`：

   ```json
   { "formId": "…" }
   ```

   → 取视图 `id` 作为 `authGroupId`（默认视图可能是 `"0"`）。

2. `work_models_records_search`：

   ```json
   { "formId": "…", "authGroupId": "…", "current": 1, "size": 20, "orders": [{ "fieldId": "字段ID", "order": 1 }] }
   ```

3. 每条记录读 `formDatas[]`：`title` 是字段中文名，`fieldValue` 是值；流程记录另有 `statusText` / `nodeName` / `approveUsers`。

#### 示例 3：查某条记录详情

1. 从示例 2 取 `records[].id`。
2. `work_models_records_data`：

   ```json
   { "formId": "…", "authGroupId": "…", "formRecordId": "…", "schemaVersionMode": "CURRENT" }
   ```

3. `data.formData` 按**字段 ID** 取值；用 `work_models_components`（或 `form_info`）的 `formItems[].id → title` 映射翻译成中文，再输出。

#### 示例 4：删除一条记录（写操作，须先确认）

1. `work_models_records_search` 找到目标记录 → 取 `id`。
2. **向用户确认**「模型 + 记录 ID + 记录标识字段」。
3. `work_models_records_delete`：

   ```json
   { "formId": "…", "id": "…" }
   ```

4. 重新 `work_models_records_search` 回读，确认记录已消失。

## 输出要求

- **不发明数据。** 取不到就说明卡在哪一步（缺 ID、无权限视图、接口未授权、无对应工具）。
- 字段名用中文 `title`；记录 ID、模型 ID 等标识可以原样给出，便于用户复核。
- 列表型结论写清返回形态与数量口径：分页工具用 `total`，`work_models_list` / `work_departments_search` / `work_apps_list` 用数组长度。
- 涉及人员手机号、证件号、法人纳税号时按最小必要输出，不整段搬运。
- 删除操作必须单独交代：删了哪个模型、哪些记录 ID、回读结果是否与预期一致；未回读不得写成「已删除成功」。
