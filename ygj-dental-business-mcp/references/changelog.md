# 变更与遗留记录

本文件只收纳**追溯时才需要**的信息：已作废口径、一次性核验留下的样本数字、未随技能分发的历史脚本。
统计规则正文不依赖本文件；遇到「这个数字哪来的」「旧口径为什么废掉」时再读。

## 一、已作废口径（勿再引用）

### 企微好友标签口径

| 作废口径 | 问题 |
| --- | --- |
| 用 `patientId → patients_get_details.data.wecom[].label` 作为好友标签的唯一通道 | ① **覆盖极低**：深湾店 2026-10-16 61 条中仅 **14 条**有 `patientId` ⇒ 只统计出 **9 位**带标签好友，漏 **18 位**；② 读的是**患者档案**上的对象，**不是好友自身的标签**；2026-10-16 改用 `wecom_list_friends.records[].tags`（**键 61/61 恒在**） |
| 「未关联 HIS 患者的好友，标签不可得」 | 错。`patientId=None` 的好友**照样有** `tags`（实测 `["陈亚妮客户","未成交"]`）⇒ 标签与是否关联患者**无关**；分桶改为**有标签 / 无标签**，不存在「标签不可得」 |
| 「`corpId` 服务端无合法来源」 | 部分作废：`wecom_list_friends` **出参自带 `corpId`**（`records[].corpId`）；该结论仅对 `wecom_get_friends_details`（需外部同传 `corpId` + `wecomExternalUserId`）成立 |
| 用 `data.lables[]`（患者标签）参与企微好友标签统计 | 属**患者标签体系**，与企微好友标签**共用同一 `labelId` 编号体系**（「已成交」= `8888000000005085`）⇒ 按 id 匹配必然跨体系误用；**一律禁用**，匹配只按**标签名**精确比对 |

### 项目数量口径

| 旧值 | 错误原因 |
| --- | --- |
| 331 / 166 | 对 `fdiToothCodes`（牙位列表）做文章 ⇒ 得到的是牙位次数，非数量 |
| 329 | 旧 `itemTypeMasterName="补牙类"` 全行求和 |
| 443 | labelLevel 全行求和 ⇒ 一颗牙被重复计 4~5 次 |
| 121 | 精确项目名口径，含根管组合内的修复子项（应按 labelLevel 归入「根管」） |

### 组合交易按患者汇总口径

| 作废口径 | 问题 |
| --- | --- |
| 用交易表 `id` 当组键 | `id` 行级标识不唯一，不同收费单的行被错并（补牙数量 161 → 157） |
| 价目表挂牌价 `combs.price` 当成交标价 | 多步骤组合 + 调价场景失真（全店差 5,873.00） |
| 「同 `(billId, billDetailId)` 一律求和合并」的字面读法 | **2026-10-15.12 细分**：该键下有两种形态 —— 互补阶段行（金额/数量落在互斥位置）**应合并**；**反向冲销对**（收 `+x/+n` ＋ 退 `−x/−n`）**不应合并**，合并会把退费抵消成 0、掩盖退费事实（实测 10-15 邓海军「全口洁治」收 200 / 退 200、门店退费 −200.00 会被抹成 0）。两口径下 `SUM(payAmount)` / `SUM(refundCount)` **完全相同** |

### 收入取数口径

| 作废口径 | 问题 |
| --- | --- |
| 用账单接口 `clinics_list_bills` / `patients_list_bills` 算收入 | 按首次收费时间（`firstChargeTime`）归集，漏跨月退款 / 补收老单 ⇒ 高估营业额 |

### 分部 / 大区判定口径

| 作废口径 | 问题 |
| --- | --- |
| `structName` 含负责人姓名 **∪** 逐店扫 `employees_list`（「双通道取并集」） | 2026-10-13 的**字段缺失期间接推断法**；2026-10-15 服务端 schema 扩展后 `employees_list_work_clinic` 已直出 `divisionalId` / `divisionalName` / `divisionalGeneralManager` ⇒ 推断法作废，**直接读字段**（现行口径见 [clinic-and-staff-lookup.md](clinic-and-staff-lookup.md) §四） |
| 拿 `employees_list_work_clinic.employeeId` 当门店负责人 | 实测 **288 行全为同一值**（= 当前登录账号本人），不是负责人 |
| 用 `oaOrgId` 前缀推分部 | 282/288 行同前缀（同一集团根组织），**不区分分部** |
| 按省份硬编码推负责人 | 当年成立但**不可泛化**（同省可挂不同负责人） |

历史样本（2026-10-13，仅作回归对照，**非业务口径**）：邓海军 ①`structName` 命中 11 家 / ②扫员工表命中 12 家 / **并集 13 家**；海南 2 家门店 `structName` =「海南省」不带负责人后缀；汕头美年店（已撤店）员工表已无「区域总经理」；扫 288 家约 13 min，3/288 偶发 `Remote end closed connection`。

> 现行判定法 = **`divisional*` 三字段**（2026-10-15 用户确认定稿）。**基数已实测**（同日）：288 家 → **22 个 `divisionalId`**（1:N，单分部 1~44 家），`clinicId` : `divisionalId` = N:1（实测 0 冲突）；`divisionalGeneralManager` 有值 **286/288**（空值 2 家为法人主体 / 总部）。旧双通道法为**严格子集**：新法多捕 5 家旧扫描盲区店、旧法零独家命中 —— 详见证 [clinic-and-staff-lookup.md](clinic-and-staff-lookup.md) §四。

### 预约工具名口径

| 作废口径 | 问题 |
| --- | --- |
| 用 `appoints_list` 查门店预约 | 该名**已废除，并已于 2026-11-13 从本技能移除**（不再收录、不再出现在任何清单里）。与 `clinics_list_appoints` 为过渡期双挂 —— 本机实测两名的参数集、`required`、`description` 文本逐字一致。⚠️ 服务端 `tools/list` **仍会返回**这个旧名，看到它**不要使用**、也不要据此认为存在第二个预约接口；门店预约一律用 `clinics_list_appoints` |

### 「MCP 全部只读」

| 作废口径 | 问题 |
| --- | --- |
| 「工具全部是明细 / 列表查询型，没有任何写操作」 | 2026-11-13 `tools/list` 实测 **48 个**（含旧名 `appoints_list`），本技能收录 **47 个**，其中 **2 个是写工具**：`patients_incremental_submit_labels`（患者标签增删）、`wecom_externalcontact_mark_tag`（企微好友标签增删，好友已关联患者时**同步改患者标签**）。其余 45 个仍只读；**仍无聚合 / 报表工具**，也**没有**建档、改预约、退费、发券等其他写能力。写路径**只核对 schema、未执行**（见 [label-write.md](label-write.md)） |

## 二、一次性核验样本数字（苏州样例）

以下数字只用于**回归对照**，不是业务口径，不写进交付结论。

| 项目 | 数值 | 用途 |
| --- | --- | --- |
| 原始交易行 → 互补副本合并后 | 367 → 362 | 验证「同 `(billId, billDetailId)` 按字段求和、不删行」 |
| 交易表行数 / 去重 `id` 数 | 232 行 / 54 个 | 证明交易表 `id` 不可作组键 |
| 组内无主项目行的组合组 | 4 组（如「根管治疗·单根管牙」只有材料/加收行） | 验证「只记金额、不计数量」并单列披露 |
| 退款行 / 涉及患者 / 退款组 | 7 行 / 2 位 / 3 组 | 验证退款行不与正向行共享 `billId` |
| 0 元行 | 原始 14 行（含 5 行互补副本）→ 合并后 9 行 | 验证互补副本不重复计 0 元行 |
| 白名单门店数 | 实测 288 家 | 验证 `employees_list_work_clinic` 返回形态 |

## 三、历史脚本未随技能分发

**🆕 2026-10-16.14 起本技能首次自带 `scripts/`**（此前全盘检索无任何可执行脚本）：

| 脚本 | 用途 | 说明 |
| --- | --- | --- |
| `$SKILL/scripts/export_clinic_charge_combs.py` | ✅ **现行** · 导出门店收费组合及明细（子能力 `export-clinic-charge-combs`） | 自包含；`ygj_client.py` 按 `YGJ_CLIENT_DIR` → 技能 `scripts/` → 同机工作区 → 工作区默认位 解析（凭证 `~/.workbuddy/ygj-mcp-prod-credentials.json` 需就位）；默认输出目录 = 客户端所在工作区 `outputs/`。算法 / 纪律见 [export-clinic-charge-combs.md](export-clinic-charge-combs.md) |

以下脚本**仍不在本技能目录中**，当年属**工作区（`$WS`）或共享位任务资产**。技能正文已自包含其算法与纪律，需要时按下表重写，或从第四节所述备份取回：

| 脚本 | 用途 | 算法 / 纪律现落在 |
| --- | --- | --- |
| `$SKILL/scripts/gen_sz_comb_patient_summary.py` | 生成苏州样例的组合交易按患者汇总表 | [combo-transaction-by-patient.md](combo-transaction-by-patient.md)：互补副本合并 → 治疗组构造 → 逐组聚合 → 按患者汇总 → 7 条勾稽，纯函数、无外部依赖 |
| `$SKILL/scripts/ygj_field_probe.py` | 字段存在性三步法探针（主样本 vs 对照样本字段差集 + 三分类判定 + `null` 省略检测 + 键缺失分布） | [verification-discipline.md](verification-discipline.md) §3 |
| `$WS/scripts/ygj_find_struct_stores.py` | ⚠️ **基于已作废的双通道口径** —— 扫员工表落 hits JSON（旧「通道 ②」） | 口径作废见 §一；实现在 `E:\zhuwei\AI\workspace-ai\scripts\` |
| `$WS/scripts/gz_struct_revenue.py` | ⚠️ **2026-10-15.12 起已废弃**（由 `gz_divisional_revenue.py` 取代：按 `optClinicId` 归店 + 跨店剔除 + `oaOrgId` 归并 + 每分部独立 JSON）；本脚本按「查询用的 `clinicId`」归店、无跨店剔除 / 无副本合并，**仅供历史复现** | 同上；同目录另有 `gen_struct_revenue_report.py` |
| `$WS/scripts/gz_divisional_revenue.py` | ✅ **现行分部业绩取数** —— 名册 1 次调用（`divisionalGeneralManager`，**不取员工表**）→ 4 线程逐店 `clinics_list_bill_docs` → 整行精确去重 → 互补阶段行合并 → `optClinicId` 归店剔除 → `optDateTime` 日期校验 → 门店 / `oaOrgId` / 分部三层汇总；含 audit + R1–R8 勾稽 | [revenue-and-deal-count.md](revenue-and-deal-count.md) §五 |
| `$WS/scripts/gen_divisional_report.py` | ✅ **现行分部业绩报告** —— **每个分部负责人一个独立 HTML**（不合并），KPI / `oaOrgId` 归并 / 逐门店 / 零业绩 / 归集审计+勾稽+口径 五区块，样式走 `mac_style.py` | 同上 |
| `$WS/scripts/mac_style.py` | 🎨 **全工作区 HTML 统一模板（MAC 浅色）** —— CSS 变量 + `page/cards/sec/table/notes/tip/badge/esc/money/num`；同时固化「表头 sticky + 禁固定高度 + `border-collapse:separate`」三条硬约定 | 新脚本一律 `import mac_style as M`，禁止再各自内联 CSS |

| `$WS/scripts/ygj_charge_combs_export.py` | ⚪ **工作区副本（等效，可保留）** —— 与技能内置脚本同算法；实测两者 `rows` 逐行一致。**优先用技能内置版**（可随技能分发到各 Agent），本副本仅供历史复现 | [export-clinic-charge-combs.md](export-clinic-charge-combs.md) |

- 上述 `$WS` 脚本**本体仍在** `E:\zhuwei\AI\workspace-ai\scripts\`，属**工作区资产，非本技能仓库**。其中 `gz_divisional_revenue.py` / `gen_divisional_report.py` / `mac_style.py` 为**现行**；`gz_struct_revenue.py` / `gen_struct_daily_report.py` **已标注废弃**（仅供历史复现）；`ygj_find_struct_stores.py` **已标注废弃**（仅保留作交叉校验 / 取证），**不得再用它取名册**。
- `$SKILL/scripts/` **现仅含 `export_clinic_charge_combs.py` 一支**；引用其他脚本名（如 `gen_sz_comb_patient_summary.py`）前先确认文件是否存在，不要假设存在。

## 四、跨 Agent 共享位副本（2026-10-15 已同步）

技能本体同时存在于两个位置，**以本仓库为唯一事实来源**：

- 本仓库（源）：`ygjhis-ai/ygj-skills/ygj-dental-business-mcp/`（历史文档中曾写作 `blueberry-dental-skills/skills/...`，指同一技能）
- 跨 Agent 共享位（派生）：`~/.agents/skills/ygj-dental-business-mcp/` —— WorkBuddy / Hermes / OpenClaw 均指向此目录

**2026-10-15 已用本仓库版整体覆盖共享位**，两份现逐文件字节一致（`diff -r` 无差异）。覆盖前整体备份在 `~/.agents/backups/ygj-dental-business-mcp-20261015/`。

> ✅ **2026-10-31 已完成双向回灌**：此前落在共享位的 2026.10.15.11 ~ 2026.10.16.17 增量（`revenue-and-deal-count.md` §五、`combo-transaction-by-patient.md` 互补副本适用范围限定、`clinic-and-staff-lookup.md` 分部实测、`export-clinic-charge-combs.md` / `price-list-and-combos.md` / `wecom-friends-and-labels.md` 三份新 reference、`scripts/export_clinic_charge_combs.py`、`SKILL.md` 索引与限流口径、本 changelog）已按「共享位增量 → 仓库」回灌；随后按「仓库 → 共享位」整体覆盖并 `diff -r` 校验一致。备份在 `~/.agents/backups/ygj-dental-business-mcp-20261031/`。

> ⚠️ **2026-11-17 复核订正**：上述「逐文件字节一致」的措辞不再准确 —— 共享位 `SKILL.md` 的 frontmatter 额外保留一行 `skill下载地址: http://git.ygjkq.com:18000/ai/blueberry-dental-skills.git`，仓库版没有；除该行外两份内容一致。后续同步以「内容一致 + 该下载地址行仅保留在共享位」为准。
>
> ✅ **2026-11-13 再次双向合并**（本次**不是**单向覆盖）：比对发现共享位在 `coupon-member-point.md`（§2.3 480 会员卡识别，2026-11-07 实测，+12 行）与 `revenue-and-deal-count.md`（§六 全门店营业额排名 + R6 订正，2026-11-01 定，+20 行 / 改 1 行）**比仓库新**，仓库无独有内容 ⇒ ① 先把上述两份增量**回灌到仓库**；② 再把本次 2026.11.13.1–.3 的改动（`SKILL.md`、`references/wecom-friends-and-labels.md`、`references/verification-discipline.md`、新增 `references/label-write.md`、本 changelog）同步到共享位；③ `diff -r` 校验两份**逐文件一致**。覆盖前备份在 `~/.agents/backups/ygj-dental-business-mcp-20261113/`（13 个文件）。⚠️ 教训沿用：**同步前必须先 `diff -r`**，单向覆盖会在共享位存在未回灌增量时静默丢数据。

### 本次覆盖被移除的内容（仅存于备份）

共享位此前那份比本仓库版多出以下能力，覆盖后**不再随技能分发**，需要时从备份取回：

| 被移除 | 内容 |
| --- | --- |
| `reference.md` | 单文件参考（原 §3 / §4 / §5 / §7 / §8），已被 `references/` 目录取代 |
| `probe.py` | 环境探测 |
| `scripts/ygj_mcp_proxy.py` | 本机代理（连生产端点用） |
| `scripts/ygj_proxy_supervisor.py` | 代理看门狗 |
| `scripts/ygj_scope.py` | 取数范围闸门（退出码 0=ALLOW / 1=DENY / 2=白名单不可用） |
| `scripts/ygj_field_probe.py` | 字段存在性三步法探针 |
| `state.json` | 运行态 |

一并移除的还有共享位版 SKILL.md 中的**额外 11 条铁律与整节故障诊断（模式 C）**，其中数条是本仓库版尚无对应内容的验证纪律：

- 「取不到数 / 全 0」是**时刻属性**，结论必须带核对时刻，复用前必须重测
- 「schema 声明」≠「运行时返回」；服务端**按行省略取值为 `null` 的键** ⇒「键缺席」≠「字段不存在」
- 字段存在性**三步法**（看声明 → 看运行时 → 找对照样本）+ 举证责任倒置
- 官方文档给的是**口径**不是**事实**，可实测的断言落进技能前必须复测
- 分部 / 大区负责人管辖范围需**双通道取并集**（`structName` ∪ 员工表扫描）—— ⚠️ 该条虽已并回，但**随即作废**：2026-10-15 起改用 `divisional*` 三字段（见 §一）

> ✅ **2026-10-15 已并回本仓库版**：上述 5 条中**前 4 条**已落进 SKILL.md 铁律 11–13 与 [verification-discipline.md](verification-discipline.md)（时刻属性 / schema≠运行时 / 存在性三步法 / 文档口径≠事实），**保持有效**；**第 5 条（分部双通道）已随 `divisional*` 字段下发而作废**（见 §一）。备份仅作历史留档 —— 「共享位版更完整」只对前 4 条成立，对第 5 条**不成立**（它是字段缺失期的绕路）。

### 覆盖前已知的事实冲突与裁决

覆盖时**以本仓库为准**写入；备份中保留了相反结论。后续裁决如下：

| 冲突点 | 本仓库版（旧） | 共享位版（备份可见） | 裁决 |
| --- | --- | --- | --- |
| `oaOrgId` 与 `clinicId` 是否 1:1 | 实测 1:1 | 实测 288 行 = 281 个 `oaOrgId`，7 个各挂 2 个 `clinicId` | ✅ **1:N**（2026-10-15 确认）—— 共享位版正确，正文已改写 |
| `clinicId` 校验方式 | 只强调服务端已校验 | 客户端闸门必需 + 后端也校验 | ✅ **两层校验，缺一不可**（2026-10-15 确认）—— 已写入 §B3 |
| `clinicId` 越权漏网值 | 不再静默返回 `total:0` | 仍有漏网值（`1` / `12` / 带前导零形态）静默返回 `total:0` | ✅ **2026-10-31 复核：`1` / `12` 不是漏网值** —— `1` = 牙管家金沙慈卫店（营业中）、`12` = 牙管家南岸店（已撤店），**两者都在 `employees_list_work_clinic` 白名单内**；`clinicId=1` 实测 `clinics_list_members` 返回 `total=706`。真正「不在白名单」的 ID 拒绝表现**仍未复测**（本次未做越权探测） |
| 体检收费口径 1 | 账单 × 交易**双侧取交** | 收入场景只走交易接口 ⇒ 明细侧**单侧判定** | ✅ **单侧判定**（2026-10-15 裁决）—— 铁律 9 使双侧在收入场景**不可满足**（账单接口禁用，账单侧 `isPhysical` 根本取不到）⇒ 单侧是唯一可执行解。已改写 [revenue-and-deal-count.md](revenue-and-deal-count.md) 口径 1，并要求出数时标注「**明细侧单侧判定，未与账单侧交叉验证**」；原双侧口径降级为「非收入场景可选」 |
| 「工具不存在」判定法 | 比对报错码即可 | `MCP-PARAM-001` 是通用码（≥4 种消息），必须比对**完整消息文本** | ✅ **按共享位版从严**（2026-10-15 裁决）—— 只比码会把「缺必填参数 / 未声明字段 / 类型不符」误判成「工具不存在」。已写入 SKILL.md 铁律 6 |

| 分部 / 大区判定法 | —（`.8` 才引入该节） | `structName` 双通道（字段缺失期做法） | ✅ **`divisional*` 三字段**（2026-10-15 用户确认）—— 双通道作废，见 §一 |

✅ 五项均已裁决（`clinicId` 越权漏网值于 2026-10-31 复核，结论见上表）；引用前先确认。

## 五、版本沿革

| 版本 | 变更 |
| --- | --- |
| 2026.11.17.1 | **一致性审计修正（静态核对，未调用任何写工具）**：① §B1「46 只读」笔误改为 **45**（47 = 45 + 2）；② 价目表 / 导出两处关键词参数名 `search` → **`keyword`**（实际 schema；`search` 仅属 `patients_quick_search`）；③ §B3.1 拆分「日期跨度超限」返回 —— 卡券 / 会员实测为 `code:400`，**不是** `UPSTREAM_BUSINESS_REJECTED`；④ 拆分**营业额 / 交易实收 / 净实收**三口径，与 revenue 文档对齐；⑤ 白名单行数改为「随授权变化（288 → 308 / 311）」；⑥ 补凭据路径（MCP 侧 `~/.config/...`，内置脚本 `~/.workbuddy/...`）、`ygj_client.py` 未随技能分发与解析顺序、`employees_list` / `wecom_list_group_friends` 的 size 上限、`patients_list_bill_docs` 无分页参数；⑦ `description` 触发词补随访 / 体检登记 / 员工 / 分部 / 收费项目 / 标签定义；⑧ 修正仓库路径与共享位「字节一致」表述。 |
| 2026.11.13.3 | **企微好友 ID 映射由「未实测」改为「已实测」**（只读核对，未写任何数据）：① 取 `employees_list_work_clinic` 的 `isDefault="1"` 门店（牙管家集团 `1476530438895636482`，实测 **311** 行白名单）→ `wecom_list_friends`（`current=1`/`size=5`/`2026-01-01~2026-11-13`）→ **`total=241`、`tags` 键逐行存在（无标签为 `[]`）**；② 以 `records[0].externalUserId`（`wma0G5KQ…`）连同同行 `corpId`（`ww4a9cecd…`）调 `wecom_get_friends_details`，**返回同一位好友、`externalUserId` 原样回显** ⇒ 出参 `externalUserId` 与入参 `wecomExternalUserId` **同值、仅字段名不同**，`corpId` 也可从同一行直接取；③ 同步更新 SKILL.md §B2 四 与 [label-write.md](label-write.md) §三、[wecom-friends-and-labels.md](wecom-friends-and-labels.md) §一，删掉「首次使用先核对映射」的待验证措辞；④ **仍未实测**：两支写工具的实际调用（返回结构 / 错误文案 / 幂等性）、写侧跨店归属校验 —— 首次写仍须做最小样本 |
| 2026.11.13.2 | **从技能中移除旧名 `appoints_list`**：① SKILL.md 全量清理（页首计数、§B2 模块表、§B2 二 段首与脚注、`clinics_list_appoints` 行内提示），门店预约**只保留** `clinics_list_appoints` 一个入口；② 计数由 48 调整为 **47（45 只读 + 2 写）**，门店维度 14 → **13**；③ 页首补一条明确说明 —— 服务端 `tools/list` **仍返回**该旧名（schema 与新名逐字一致），属**服务端残留**，**不得使用、不得据此认为有两个预约接口**，避免后续重新收录；④ §一 作废口径表同步改为「已移除」；⑤ [verification-discipline.md](verification-discipline.md) 的历史案例**保留原始记录不改写**，仅更新顶部提示 |
| 2026.11.13.1 | **新增 2 个写工具（46 → 48），「全部只读」作废**：① 🚨 `patients_incremental_submit_labels`（患者标签增删）与 `wecom_externalcontact_mark_tag`（企微好友标签增删）为全库**仅有的写操作**；二者的 `addLabelIds` / `deleteLabelIds` 为**数组**、**至少一侧非空**、空数组 = 该侧不操作（≠ 清空全部标签）；② 🚨 `wecom_externalcontact_mark_tag` 在好友**已关联患者**时会**同步更新该患者标签**（跨对象副作用）；③ SKILL.md 新增**铁律 14**（写工具默认不执行：须用户明确要求 → 列对象/标签名/增删方向确认 → 禁批量 → 写后回读，不得只凭返回码宣称成功），§B1 补「可写」行，§B2 补**七、标签写入**，§B3 新增「6. 写操作范围」（两支写工具**都不收 `clinicId`**，白名单闸门无法直接套用，代偿做法 + fail-closed）；④ 新增 [label-write.md](label-write.md)（标签 ID 来源、六步流程、禁止清单、最小样本验证）；⑤ [wecom-friends-and-labels.md](wecom-friends-and-labels.md) 补工具边界行，并把「禁用 labelId」**限定为读侧**（读用名、写用 id）；⑥ 工具总数 46 → **48**（患者维度 16→17、企业微信 6→7，门店维度仍 14，含旧名 `appoints_list`）；⑦ 顺手按 2026-11-13 `tools/list` 校准若干参数：`clinics_list_appoints` 来源三级为 `firstSource`/`secondSource`/`threeSource`（传 id）、`clinics_list_consults` 的 `status` 与 `filterDateType` 1–4、`clinics_list_coupon_records` 补 `couponType`/`allowedItemName`/`distributeEmployeeId`/`sharable`、`clinics_list_coupon_consume_records` 补 `couponType`/`distributeEmployeeId`/`fromType`、`clinics_list_members` 补 `memberCardId`、`patients_list_bill_docs` 补可选 `startDate`/`endDate`（须成对）/`billType`/`feeType`、`wecom_list_friends` 的 `tags` 上限 10 个；⑧ ⚠️ **写路径未实测**：只核对 `tools/list` schema，**未实际调用**（避免污染生产数据），返回结构 / 错误文案 / 幂等性均未验证，首次使用须先做最小样本验证 |
| 2026.10.31.1 | **新增 10 个工具（36 → 46）**：卡券（`clinics_list_coupon_records` / `clinics_list_coupon_sale_records` / `clinics_list_coupon_consume_records`）、会员（`clinics_list_members` / `patients_list_memberships`）、积分（`patients_point_account` / `patients_list_point_logs`）、患者标签（`patients_list_labels`）、小程序 SCRM（`scrm_get_user`）。新增 [coupon-member-point.md](coupon-member-point.md) 承载四域口径；SKILL.md 补「返回形态三分」（分页对象 / 裸数组 / 单对象）、四套日期参数命名差异、铁律 2/3 的租户与隐私边界。**实测基线 2026-10-31**；四项工具在总部店实测 `total=0`、阳江店有数据，属门店差异。同时回灌共享位 2026.10.15.11 ~ 2026.10.16.17 的全部增量（见 §四） |
| 2026.10.16.17 | **企微好友报告「患者姓名/病历号」补齐链路修复**（用户指出「已关联患者的患者姓名为空值」）：① 根因 —— 这两列取自 `_wecom_friends_profile_<date>_*.json`，而该文件**不会自动产生**；上一版把 `enrich_wecom_friend_labels.py` 降级为「默认不跑」后，未先执行 `--with-patient-profile` 便出表 ⇒ 9 位已关联患者**姓名全空**（属流程断点，非数据缺失）；② 修复 `gen_wecom_friend_label_report.py`：`--profile <路径>` **真正加载文件**（旧实现只赋值路径、不读内容，传了也无效），读失败给出明确告警；③ **勾稽新增「已关联患者的患者姓名覆盖率」`n_named >= n_linked`**（姓名与病历号同源），缺则 `[FAIL]` + 双警示（档案读不到 / 需补跑 `--with-patient-profile`）；勾稽编号改为**末尾统一编**，避免条件项跳号；④ 明细区新增情境说明（已补齐 = 解释两列来源且注明「仅展示、不参与标签判断」；未补齐 = 醒目提示补跑命令）；口径块新增「患者档案列」「未关联患者」两条，payload 增 `linked_patients` / `named_patients`；⑤ 实测（2026-10-16 深湾店）：9 位已关联患者档案**全部补齐**，headless 读表格实况**空值为 0**；负向测试（`--profile` 指向不存在文件）→ 告警 + `[FAIL] 0 / 9`，证明断言有效 |
| 2026.10.16.16 | **企微好友标签口径纠偏：标签回归「好友自身」`records[].tags`，全面弃用患者侧通道**：① 🚨 **接口改版实测** —— 2026-10-16 21:15 实时 `tools/list` 显示 `wecom_list_friends` **新增入参 `tags`(string)** 与 **新增出参 `data.records[].tags`(array，标题「好友标签数组」)**（2026-10-13 快照无此二项）；运行时复测 **`tags` 键 61/61 行恒在**、空值为 `[]`（**不是省略键**），32 行非空；② 🚨 **作废旧链路**：`records[].patientId → patients_get_details → data.wecom[].label` **降为 ⛔ 作废通道** —— 覆盖极低（深湾店 61 条中仅 **14 条**有 `patientId` ⇒ 旧口径只统计出 9 位带标签好友，**漏 18 位**）、读的是患者档案对象而非好友标签、且与患者标签 `data.lables[]` **共用同一 `labelId` 编号体系**（实测「已成交」= `8888000000005085`）⇒ **只能按标签名精确匹配，禁用 labelId**；③ 🚨 **作废「未关联者标签不可得」** —— `patientId=None` 的好友照样有 `tags`（实测 `["陈亚妮客户","未成交"]`）⇒ 标签与是否关联 HIS 患者**无关**；分桶改为**只按有无标签**（有标签 / 无标签），**删除**「未关联（标签不可得）」桶；④ 🚨 **入参 `tags` 是子串匹配**（`tags=补牙` → 8 条，其中 **3 条**实际只含「潜在补牙」；`补牙` 的精确命中应为 **5**）⇒ **只作服务端预筛，取回后必须客户端精确复核**，并落痕「预筛 N → 精确 M」；逗号 = **AND（交集）**（`已成交,补牙` → 5），`\|` 无效（→ 0）；⑤ 新增**可复用标签能力** `$WS/scripts/wecom_tags.py`（`tags_of` / `parse_tags` / `match_tags` / `filter_friends` / `tag_stats` / `assert_no_patient_labels` / `dedup_friends`）—— 标签逻辑**唯一入口**，纯函数；⑥ 防呆：`assert_records_clean()` 在取数/出表入口逐条断言，记录一旦出现 `lables` / `label` / `labelId` / `labelIds` / `lables_count` / `wecom_rows` 即 `AssertionError` 中止；⑦ 脚本改造：`fetch_wecom_friends_today.py` 新增 `--tag/--has-tag/--no-tag` + raw 落 `tag_field`/`label_source_policy`/`tag_stats`/`prescreen`；`enrich_wecom_friend_labels.py` **删标签逻辑、降级为可选患者档案补齐器**（默认不跑，需 `--with-patient-profile`，只取 `baseInfo` 六字段白名单）；`gen_wecom_friend_label_report.py` **默认直读 raw**、标签由 `tags_of()` 派生、新增 `--any/--all/--none/--tagged/--untagged` 与「按标签筛选」区块、输出前缀改「**按好友标签**」；⑧ **勾稽 6 → 9 条**（新增 ④`tags` 键覆盖率=100% / ⑦标签种类锚点 / ⑧标签计数锚点 / ⑨预筛 N ≥ 精确 M）；⑨ **新锚点**（2026-10-16 21:16 深湾店）：61 条 → 去重 **49 位**（重复 12）／**有标签 27 / 无标签 22**／**29 种 / 91 次**（`未成交` 17、`陈亚妮客户` 10、`已成交` 9、`男` 6、`P(3000以下)` 5、`补牙` 5、`潜在补牙` 5、`洁牙` 4、`980预防会员` 3…）；**旧锚点「49 次 / 20 个 / 9 位已关联」作废**；⑩ ⚠️ **`corpId` 旧结论订正**：`wecom_list_friends` 出参**自带 `corpId`**，「服务端无合法来源」只对 `wecom_get_friends_details` 成立；四支企微工具 outputSchema **均无任何标签字段** |
| 2026.10.16.15 | **企微好友域（新增好友 / 客户标签 / 标签分组）口径落地**：新增 [references/wecom-friends-and-labels.md](wecom-friends-and-labels.md)（SKILL.md 索引与 `description` 触发词同步）——① 固化**两步链路**：`wecom_list_friends`（`startDate`/`endDate` **语义 = 添加好友日期**，非 `required` 但须实传）→ `records[].patientId` → `patients_get_details` → **`data.wecom[].label`（企微客户标签，已是中文名、逗号分隔）**；🚨 **`data.lables[]` 是「患者标签」，另一套**（标签名会重合但来源独立，勿混）；🚨 **同一患者 `wecom[]` 常有多条且 label 重复**（钟莉 4 条 / 余建涛 2 条）⇒ 必须按标签名保序去重；🚨 **只有「已关联 HIS 患者」的好友才有标签**，未关联者标签**不可得 ≠ 没有标签**；② 🚨 **新坑：`userName` 不是纯姓名** —— 实测形如 **`晓丹 | 医生助理（深湾店）⭐`**（服务端拼接「姓名\|岗位（门店）⭐」；2026-10-16 深湾店 61 条中 42 条如此）⇒ 员工维度聚合**必须取「\|」前段**，否则同一人被拆成多个键；③ 分组口径：去重键 `(corpId, externalUserId)`；**「按标签分组」的分母是带标签好友数而非全部新增好友数**；**多标签同时计入各桶**（`标签计数合计 ≥ 带标签好友数`，必然不等，勿配平）；④ 勾稽 6 条（`total`==取回行数 / 去重+重复==取回 / 标签计数≥带标签 / 关联状态闭合 / 分桶闭合 / `addTime` 全落当日）；⑤ 实测锚点：2026-10-16 深湾店 `total=61` → 去重 **49 位**（重复 12）／已关联 **9**（全部有标签）／未关联 **40**／**标签计数 49 次 · 20 个标签**（`已成交` 9 覆盖全部带标签好友、`P(3000以下)` 5、`补牙` 5、`洁牙` 4）；2026-10-15 同店 41 条 → 34 位 / 5 位有标签；⑥ 工具边界：`wecom_get_friends_details` / `wecom_get_group_details` 需 `corpId`，服务端**无合法来源** ⇒ 实际只得空壳 |
| 2026.10.16.14 | **子能力 `export-clinic-charge-combs` 沉淀为技能内置能力（**首次内置脚本**）**：① 新增 [references/export-clinic-charge-combs.md](export-clinic-charge-combs.md) —— 把「导出门店收费组合及明细」固化为**六步固定流程**（门店定位闸门 → 取组合 → 展平 → 勾稽 → 输出 → 报缺口）、**10 列字段映射**（唯一输出口径）、**关联规则**（组合内按 `items[].sort`、组合名与总价逐行重复、xlsx 交替底色分区 + 冻结首行 + 筛选）、**C1–C13 三态勾稽**（`ok` / `warn`=源数据缺口 / `fail`=口径不一致）、**输出三件套规格**；② 🆕 **技能首次带 `scripts/`**：`$SKILL/scripts/export_clinic_charge_combs.py`（自包含，`ygj_client.py` 按 `YGJ_CLIENT_DIR` → 技能 `scripts/` → 同机工作区 → 工作区默认位 解析；默认输出目录 = 客户端所在工作区 `outputs/`）；③ `--include-disabled` **由桩实现为真合并**（并入 `status=1` 禁用组合，输出前缀变「全部收费组合」，不加则仅取启用并把禁用数作对照打印）；④ 🚨 **同名门店不得替用户挑**：白名单「宣武」命中 2 家（宣武门店 `8888000000000067` 营业中 301 个组合 vs 北京宣武门体检店 `34625225207565940` 已撤店 0 个）⇒ 脚本命中多家时**列候选并 exit 2**；⑤ **零回归验证**：内置脚本 vs 工作区 `$WS/scripts/ygj_charge_combs_export.py` 在同店同日跑，`rows` **逐行完全一致**、`comb_meta` 与 `recon` 完全一致；⑥ 实测锚点不变（301 组合 / 1484 明细 / C1–C7 全绿 / C4 301-301 全等） |
| 2026.10.16.13 | **价目表域（收费组合 / 收费项目）契约落地**：新增 [references/price-list-and-combos.md](price-list-and-combos.md)（SKILL.md 索引同步）——① 🚨 **`basedatas_list_charge_combs` 是嵌套返回**：`data.records[]` 组合自带 `items[]` 明细（16 字段），**导出组合明细只需这一支工具**，无需再查明细接口；② 字段映射定稿：「技耗分类」＝`chargeType`（schema `title` 原文如此，实测取值 治疗费 / 专用耗材费 / 检查费 / 手术费 / 基础耗材费）、「主项目」＝`isMainItem`、「计价说明」＝`pricingInfo`、「单位」＝`unit`；③ ⚠️ **类型不统一**：`price`/`amount`/`marketPrice` 是**字符串**，`count`/`isMainItem` 是 **int**；`combStepName` **可能整单全空**（宣武门店 1484/1484 空 ⇒ 该店组合无步骤概念，勿预设必有步骤）；④ 🚨 **四个实测坑**：**`code` 可能全空**（宣武门店 301/301 空 ⇒ 唯一键只能用 `id`）、**组合名称会重名**（9 组 / 36 个，一组最多同名 9 个、价格 5,751~26,088）、**`isMainItem` 可能整单无 1**（169/301 未勾选，**不得当作勾稽 fail**）、**`unit`/`chargeType` 可能为空串**（6 行 / 2 行，如实列示不得编造）；⑤ 勾稽 C1–C6 定稿（`comb.price` = Σ`items[].amount` 实测 301/301 全等；每组合主项目 **≤1** 才判 fail）；⑥ 实测锚点：宣武门店（`8888000000000067`，刘萍分部，营业中）启用组合 **301** / 禁用 25 / 明细 **1484** 行；⑦ 工作区新增 `$WS/scripts/ygj_charge_combs_export.py`（产 xlsx 三 Sheet + csv 10 列 + raw json） |
| 2026.10.15.12 | **分部级业绩出数流程定型 + `(billId, billDetailId)` 多行两形态拆分**：① `revenue-and-deal-count.md` 新增 **§五 分部 / 大区级业绩出数流程**（六步：`divisionalGeneralManager` 定名册 → 逐店 `clinics_list_bill_docs` → **按返回体 `optClinicId` 归店 + 跨店行剔除** → **`oaOrgId` 组织机构归并** → 行级两道工序 → **每分部一个独立 HTML**），SKILL.md 索引同步；② 🚨 **重要细化**：同 `(billId, billDetailId)` 实测有**两种**多行形态，旧铁律「一律求和合并」需拆分 —— **互补阶段行**（金额与数量落在互斥位置，如开单行 `refundCount=n/payAmount=0` ＋ 收款行 `payAmount=x/refundCount=0`，实测时间相差数秒）**必须合并**；**反向冲销对**（收 `+x/+n` ＋ 退 `−x/−n`，两个位置都非零）**禁止合并**（合并会把退费抵消成 0、掩盖退费事实）。两种口径下 `SUM(payAmount)` / `SUM(refundCount)` 完全相同，差异只在「行数 / 收费额 / 退费额 / 退费行数」；③ 实测锚点（2026-10-15 当日）：邓海军 13 店净实收 **113,529.00**（6 组织 / 159 行 / 退费 −200.00 / 数量 255 / 成交 62）、刘倩 23 店 **194,865.60**（15 组织 / 385 行 / 退费 −1,700.00 / 数量 539 / 成交 149），合计与旧口径**逐项完全一致**；④ 工作区新增 `gz_divisional_revenue.py`（取数）＋ `gen_divisional_report.py`（每分部一个 HTML）＋ `mac_style.py`（MAC 浅色公共样式模块），旧 `gz_struct_revenue.py` / `gen_struct_daily_report.py` 标注废弃 |
| 2026.10.15.11 | **分部判定基数实测 + 取数限流实测放宽**：① `divisional*` 三字段基数实测（288 家 → **22 个 `divisionalId`**，1:N；`clinicId` : `divisionalId` = N:1，0 冲突；`divisionalGeneralManager` 有值 286/288）—— 补上 `.9` 标注的「尚未实测」空白；② 发现**同名负责人可挂多个 `divisionalId`**（王未 = `王未分部` 26 家 + `北京（直属分部）` 1 家）⇒ 按负责人姓名过滤**必须先判集合大小**；③ 实测 `divisionalGeneralManager` 口径为旧双通道扫描的**超集**（多捕 5 家盲区店、旧法零独家），成本 **1 次调用 vs 289 次**；④ **限流实测放宽**：服务端单次约 0.4s，串行 50 次（0.49s/次）与 4 线程并发 48 次（0.20s/次）均未触发 `MCP-LIMIT-001` ⇒ 客户端 `gap` 由 2.2s 调整为 **0.6s + 限流按线程隔离**（工作区 `ygj_client.py`），旧 2.2s 源自 2026-09-23 的账号级限流；⑤ 工作区脚本 `gz_struct_revenue.py` 对齐（邓海军 + 刘倩两分部 **11 秒**跑完，旧法含扫描 ~12 分钟），`ygj_find_struct_stores.py` 标注废弃 |
| 2026.10.15.10 | **预约工具更名**：`appoints_list` → `clinics_list_appoints`（旧名**即将废除**，过渡期双挂），SKILL.md §B1 / §B2 工具清单同步改新名，工具总数 35 → **36**（2026-10-15 本机 `tools/list` 实测，两名 schema 逐字一致）；旧名进 §一 作废表。新名实测取数正常且**与旧名同源**：浙江绍兴店 `total=1142` / 天津南开鼓楼店 `total=340`，运行时 **71** 字段（对上验证纪律记载的「schema 声明 81 / 运行时 71」） |
| 2026.10.15.9 | **分部 / 大区改用 `divisional*` 三字段**：`clinic-and-staff-lookup.md` §四 由「双通道取并集（`structName` ∪ 扫员工表）」整节重写为按 `divisionalId` / `divisionalName` / `divisionalGeneralManager` 直接判定（旧法降级进 §一 作废表）；`business-category-and-store-summary.md` 补分部维度交叉引用；SKILL.md §B3 补「汇总维度三选一」 |
| 2026.10.15.8 | **验证纪律并回**：新增 [references/verification-discipline.md](references/verification-discipline.md)（时刻属性 / schema≠运行时 / 存在性三步法 / 文档口径≠事实），SKILL.md 铁律 10 条扩为 **13 条**（新增 11–13）并从严改写铁律 6（`MCP-PARAM-001` 必须比对完整消息文本）；`revenue-and-deal-count.md` 口径 1 落地为**单侧判定**；`clinic-and-staff-lookup.md` 新增分部负责人双通道判定（**该节已于 `.9` 作废**）；[verification-discipline.md](references/verification-discipline.md) 与 [clinic-and-staff-lookup.md](clinic-and-staff-lookup.md) 补「未随技能分发的历史脚本」指引 |
| 2026.10.15.7 | 按裁决修正口径：`oaOrgId` 与 `clinicId` 明确为 **1:N**（原「1:1」作废，按 `oaOrgId` 汇总即组织级口径）；`clinicId` 校验改为**客户端闸门 + 服务端校验两层**，并补「`UPSTREAM_BUSINESS_REJECTED` 是多因笼统码，不得仅凭返回体判越权」 |
| 2026.10.15.6 | 渐进式披露重构：正文拆分出 `references/`；全局铁律去重为 10 条；工具清单前移至 §B2；`clinicId` 白名单与 `size` 例外收敛到 §B3；新增端到端示例；**用本仓库版整体同步跨 Agent 共享位**（覆盖前备份于 `~/.agents/backups/ygj-dental-business-mcp-20261015/`） |
| 2026.10.15.5 | 补充 `employees_list_work_clinic` 2026-10-15 schema 扩展（outputSchema 声明 26 字段 / 实测 24 字段） |
| 2026.10.15 | 交易表 labelLevel 层级统计规则 v1.0、组合交易按患者汇总规则 v1.0 定稿 |
| 2026.10.13 | 收入取数切换至交易接口（`*_bill_docs`），账单接口在收入场景禁用；服务端开始校验 `clinicId` 归属 |
