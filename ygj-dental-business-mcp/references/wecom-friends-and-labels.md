# 企业微信好友 · 取数口径与**好友标签**口径

**适用**：用户问「某门店今天/某时段新增了多少企微好友」「按**好友标签**分组给个人数」「筛出带某标签的好友」，或要按员工统计加好友业绩。

**核心结论（2026-10-16 重定）**：
- 企微好友域的数据**已接入**（2026-10-15 起，旧「一律 `total:0`」的说法**已作废**）。
- 标签**就在好友记录里** —— 出参 `records[].tags`（数组）。**一步可得，无需二次取患者档案**。
- ⛔ **严格忽略患者标签**：`patients_get_details.data.lables[]`（患者标签）与旧通道 `data.wecom[].label` / `labelId` **一律不得进入任何判断 / 过滤 / 匹配 / 统计**。

---

## 一、一步链路：标签在好友身上

```
wecom_list_friends
  → data.records[].tags        # 好友自身标签数组（键恒在，无标签为 []）
```

### `wecom_list_friends`

| 入参 | 说明 |
| --- | --- |
| `clinicId` | **必填**，须来自 `employees_list_work_clinic` 白名单 |
| `current` / `size` | **必填**；`size` 上限 **100** |
| `startDate` / `endDate` | **必传**（`required` 里没写，但实传须 5 个）；**语义 = 添加好友日期**，跨度上限 1 年 |
| `name` | 选填，好友昵称 |
| `bindStatus` | 选填；`0`=未关联 / `1`=已关联 |
| **`tags`** | 选填（**2026-10-16 新增**）；**好友标签**。🚨 **子串匹配** —— `tags=补牙` 会同时召回「潜在补牙」；逗号 = **AND（交集）**；`\|` 无效 ⇒ **只作预筛，取回后必须客户端精确复核** |

出参关键字段：

| 字段 | 说明 |
| --- | --- |
| **`tags`** | **🆕 好友标签数组（标签唯一来源）**。实测 **键 61/61 行恒在**，空值为 `[]`（**不是省略键**） |
| **`addTime`** | 添加时间（时间口径就是它） |
| **`patientId`** | 关联患者；**键按行省略**，取值一律 `.get()`。**仅作参考维度，与标签无关** |
| `externalUserId` / `corpId` | 好友唯一键 = `(corpId, externalUserId)`；⚠️ 旧记「`corpId` 无合法来源」**已订正** —— 本工具出参**自带 `corpId`**（仅 `wecom_get_friends_details` 仍需外部传入）。📌 `externalUserId` **原值即** `wecom_get_friends_details` / `wecom_externalcontact_mark_tag` 的入参 `wecomExternalUserId`（2026-11-13 只读实测：同值反查返回同一位好友） |
| `name` / `gender` / `avatar` | 昵称 / 性别(0未知 1男 2女) / 头像 |
| `userId` / `userName` / `wecomUserId` | 添加的企微员工（`userName` 见 §2 陷阱） |
| `bindEmployeeId` / `bindEmployeeName` / `bindDatetime` / `remarkMobiles` / `unionid` / `wecomId` | 关联信息 / 备注手机号 / 微信 unionid / HIS 主键 |

### ⛔ 已作废通道（保留可知，禁止使用）

旧做法是 `records[].patientId` → `patients_get_details { patientId }` → `data.wecom[].label` / `labelId`。**作废理由**：
1. 覆盖极低 —— 深湾店 61 条里只有 **14 条**有 `patientId` ⇒ 旧口径只统计得出 9 位带标签好友，**漏掉 18 位**；
2. 它读的是患者档案上的对象，**不是好友自身的标签**；
3. `data.lables[]`（患者标签）与本通道**共用同一 `labelId` 编号体系**（实测「已成交」= `8888000000005085`）⇒ 按 id 匹配必然跨体系误用。

**唯一合法来源 = `records[].tags`；匹配一律按标签名精确比对，禁用 `labelId`。**

> 📌 **限定（2026-11-13）**：此禁令针对**读侧统计 / 匹配**。写侧新增的 `wecom_externalcontact_mark_tag` **必须**用 HIS 标签 **id** 才能提交 —— 「读用名、写用 id」，两者不冲突。见 [label-write.md](label-write.md)。

---

## 二、分组统计口径

| 口径项 | 规则 |
| --- | --- |
| 去重 | 按**好友**去重，键 `(corpId, externalUserId)`；同一好友被多名员工添加只计 **1 位**；同键多行的 `tags` 取**并集** |
| 分母 | 「按标签分组」的分母是**有标签好友数**（`tags` 非空），**不是**全部新增好友数 |
| 多标签 | **同时计入各标签桶** ⇒ `标签计数合计 ≥ 有标签好友数`，**必然不等**，不要试图配平 |
| 分桶 | ① **有标签**（`tags` 非空）② **无标签**（`tags` = `[]`）；二者之和 = 好友总数。⚠️ 分桶**只按有无标签**，**与「是否关联患者」无关** |
| 标签可得性 | 标签来自**好友自身**，**与是否关联 HIS 患者无关**（实测 `patientId=None` 的好友照样有 `["陈亚妮客户","未成交"]`）。**不存在「标签不可得」**；无标签就是 `tags` 为空数组 |
| 接口 `total` | = **添加记录条数**（员工×好友关系数），≠ 好友人数 |

### 筛选 / 匹配（唯一正确做法）

1. 服务端入参 `tags` 只作**预筛**（子串、逗号 AND）；
2. 取回后一律用客户端**精确**匹配（集合运算）：`任一命中 / 全部命中 / 排除`；
3. 落盘与交付须写「服务端预筛 N → 客户端精确 M（子串陷阱拦截 N−M）」。

典型陷阱：`成交` 会同时命中「**已**成交」「**未**成交」；`补牙` 会命中「**潜在**补牙」。

### 🚨 `userName` 不是纯姓名

实测形如 **`晓丹 | 医生助理（深湾店）⭐`**（服务端把「姓名 | 岗位（门店）⭐」拼接；2026-10-16 深湾店 61 条中 42 条如此，其余为纯姓名如 `陈芝芝`）。

**员工维度聚合必须取「`|`」前段**，否则同一个人的记录会被拆成多个键、且长度不齐无法阅读。

⚠️ 员工维度还要**按「添加关系」展开**统计（同一好友被多人添加时分别计入各自记录数），**不能取折叠后代表行**的员工，否则会把他人记录张冠李戴。

---

## 三、勾稽清单（6 条基准 + 3 条可选）

| 编号 | 校验 | 关系 |
| --- | --- | --- |
| ① | 接口 `total` == 取回行数 | 分页取全 |
| ② | 去重后好友 + 重复条数 == 取回行数 | 无凭空增减 |
| ③ | 标签计数合计 ≥ 有标签好友数 | 多标签重复计入 |
| ④ | **`tags` 键覆盖率 == 100%** | 键恒在（空为 `[]`） |
| ⑤ | 有标签 + 无标签 == 好友总数 | 分桶闭合 |
| ⑥ | `addTime` 全部落在查询当日 | 时间口径校验 |
| ⑦ | 标签种类锚点（传 `--expect-kinds` 时） | 防口径漂移 |
| ⑧ | 标签计数锚点（传 `--expect-sum` 时） | 防口径漂移 |
| ⑨ | 服务端预筛 N ≥ 客户端精确 M（用了 `--tag` 时） | 子串陷阱拦截留痕 |

---

## 四、工具边界

| 工具 | 状态 |
| --- | --- |
| `wecom_list_friends` | ✅ 可用（**唯一好友入口**，也是**标签唯一来源**） |
| `wecom_get_friends_details` | ⚠️ 需 `corpId` + `wecomExternalUserId` 同传；出参**无任何标签字段**，对标签无增益 |
| `wecom_get_group_details` | ⚠️ 需 `corpId` + `chatId`（来自 `wecom_list_group_friends`）；出参**无标签字段** |
| `wecom_list_group_friends` | 群清单（`size` 上限 100） |
| `wecom_get_friends_private_message_text` / `_group_message_text` | 私聊 / 群聊文本 |
| `wecom_externalcontact_mark_tag` | ⚠️ **写工具**（2026-11-13 新增）：按 `wecomExternalUserId` + `addLabelIds` / `deleteLabelIds`（HIS 标签 id，数组）增量增删；**好友已关联患者时同步改该患者标签**。写前须用户确认，写后回读 `records[].tags`。见 [label-write.md](label-write.md) |

**HIS 侧替代口径（语义不同，勿混，且属患者标签体系）**：`patients_list` 支持 `bindingWecom`（1=已绑定企微）＋ `includeLabelIds` / `excludedLabelIds` —— 这是**患者档案视角**，表达不了「企微侧今天新添加」，其标签也**不是**企微好友标签。`basedatas_list_label_definitions` 同理（患者标签字典）。

---

## 五、实测锚点（复核请重测）

**核对时刻 2026-10-16 21:16（深湾店 `1749712633594671105`，新口径 = `records[].tags`）：**

| 指标 | 数值 |
| --- | --- |
| 接口 `total` / 取回行 | 61 条 |
| 去重好友 | **49 位**（重复 12） |
| **有标签 / 无标签** | **27 位 / 22 位** |
| **标签种类 / 计数合计** | **29 个 / 91 次** |
| `tags` 键覆盖率 | 61 / 61 = **100%** |

标签分布（全部 29 个）：`未成交` 17、`陈亚妮客户` 10、`已成交` 9、`男` 6、`P(3000以下)` 5、`补牙` 5、`潜在补牙` 5、`洁牙` 4、`980预防会员` 3、`女` 2、`2月生日` 2、`根管` 2、`480会员` 2、`潜在种植` 2、`潜在洁牙` 2、`刘如连客户` 2、`10月生日` 1、`义齿` 1、`嵌体` 1、`拔牙` 1、`牙周` 1、`种植` 1、`V2(1-2万)` 1、`治疗未做完退费` 1、`谢瑶客户` 1、`7月生日` 1、`阳婵客户` 1、`潜在拔牙` 1、`潜在牙周` 1。

**子串陷阱实测**：服务端 `tags=补牙` → **8 条**（其中 **3 条**实际只含「潜在补牙」）；客户端精确 `any_=['补牙']` → **5 位**（3 位被正确拦截）。

⚠️ **旧锚点（49 次 / 20 个 · 9 位已关联）来自作废通道 `wecom[].label`，已作废，勿再引用。**

2026-10-15 深湾店：41 条 / 去重 34 位。**该日底稿无 `tags` 字段（字段当时尚未上线），如需重出须先实时重取。**

---

## 六、工作区脚本

`$WS/scripts/`（工作区资产，非本技能仓库）：

```bash
python fetch_wecom_friends_today.py --date 2026-10-16              # 取数，内联白名单闸门；raw 已含 tags
python fetch_wecom_friends_today.py --tag 补牙 --none 潜在补牙       # 预筛 + 客户端精确复核
python gen_wecom_friend_label_report.py                            # 出表：html + json + xlsx（MAC 风格）
python gen_wecom_friend_label_report.py --any 补牙 --none 潜在补牙   # 出「按标签筛选」版（文件名带 _筛选）
python enrich_wecom_friend_labels.py --with-patient-profile         # 可选：只补患者姓名/病历号，不含标签
```

| 脚本 | 职责 |
| --- | --- |
| `wecom_tags.py` | **标签逻辑唯一入口**（纯函数）：`tags_of` / `parse_tags` / `match_tags` / `filter_friends` / `tag_stats` / `assert_no_patient_labels` / `dedup_friends` |
| `fetch_wecom_friends_today.py` | 取数 + 预筛 + 精确复核；raw 落 `_wecom_friends_raw_*.json`（含 `tag_field` / `label_source_policy` / `tag_stats` / `prescreen`） |
| `gen_wecom_friend_label_report.py` | 出表；默认直读 raw，标签由 `tags_of()` 派生；自动匹配**同日期**的患者档案文件补姓名/病历号 |
| `enrich_wecom_friend_labels.py` | **可选**，默认不执行；只补患者档案字段，**不产出任何标签** |

- 🚨 **明细「患者姓名 / 病历号」必须补齐**（2026-10-16 实操踩坑）：这两列取自 `_wecom_friends_profile_<date>_*.json`，而**该文件不会自动产生**。若没先跑 `enrich_wecom_friend_labels.py --with-patient-profile`（只读 `baseInfo` 的 `patientName`/`medicalNo`/`sex`/`age`/`clinicId`/`clinicName` 白名单），`关联状态 = 已关联患者` 的行会**姓名全空**。出表勾稽 **⑦「已关联患者的患者姓名覆盖率」`n_named >= n_linked`** 专守此条，缺则 `[FAIL]` 并打印补跑命令；报告明细区也会给醒目提示。`--profile <路径>` 为显式指定档案文件（已修复「只赋值路径不加载」的老 bug）；未关联患者的两列记「—」，属正常。
- `fetch_wecom_friends_today.py` 的闸门为**内联白名单校验**（`employees_list_work_clinic` 一次调用 + fail-closed）—— 旧版依赖的外置 `$SKILL/scripts/ygj_scope.py` **已不在技能目录**，不要再引用。
- 报告页把「标签分组」放在第一节，并附「占有标签好友比」与合计行；HTML 走 `mac_style.py`（表头 sticky + 高度自适应）。
- 防呆：`wecom_tags.assert_records_clean()` 在取数/出表入口逐条断言 —— 记录一旦出现 `lables` / `label` / `labelId` / `lables_count` / `wecom_rows` 即 `AssertionError` 中止。
