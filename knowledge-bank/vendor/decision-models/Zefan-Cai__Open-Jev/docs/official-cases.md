# 原帖案例、官方 workflow 与可用数据来源

> 2026-09-19 更新：四个官方 workflow 页面后来已成功读取；下文的 403 是早期抓取记录。最新来源、任务范围和数据见 [能力清单](public-capabilities.md) 与 [workflow 实现](workflows.md)。公开页面可读不等于已获得完整官方数据集。

检索日期：2026-09-19。本文是来源审计和任务定义，**不代表下列案例的数据已经生成或训练完成**。公开来源能证明什么与我们可以自造什么分开记录。

## 先明确“几个 case”分别是什么

原帖及[发布文章](https://typesafe.ai/blog/introducing-system-one-models-and-jev)给出了三种可见演示：客服多问题并行判定的 **Side-by-side demonstration**、**Doom**、**Wikiracing**。文章另外说发布了 **4 个 workflow evals**。图中的 **Triage → Disposition → Containment → Playbook 是一个安全响应 workflow 的四阶段，不是四个不同案例**。

| Case | 目前证据 | 原始 query / 数据可得性 |
| --- | --- | --- |
| Side-by-side demonstration | 一手发布文章与原帖后续 | 原始共享 query 链接存在，但本次匿名访问跳转登录；未取得完整 query/state |
| Doom | 一手文章确认结构化文本状态和实时操作 | 未找到官方公开源码、完整 query、轨迹或标签；有明确独立的社区实现 |
| Wikiracing | 一手文章确认页面链接导航及高基数处理 | 未找到官方轨迹/完整 prompt；公开 Wikispeedia 提供相同任务类型的数据 |
| Security Incidents | 一手文章中的完整流程图；第三方目录给出官方 eval 链接 | 图可读；eval 页本次 403，无原始题库/JSON |
| Agent Trace Observability | 第三方公开目录给出官方 eval 链接及流程概述 | 官方页本次 403；未独立核验题目逐字内容及原始数据 |
| Invoice Processing | 同上 | 同上 |
| Customer Service | 同上；它与原帖 side-by-side 不应默认等同 | 同上 |

四个 eval 名称和官方路径的公开线索来自 [Anil-matcha/awesome-jev-by-typesafe](https://github.com/Anil-matcha/awesome-jev-by-typesafe/blob/afd223fcd4395cca3d5b3c9d1acac30b19203e25/README.md)，固定 commit `afd223fcd4395cca3d5b3c9d1acac30b19203e25`。这是第三方二手目录，不是官方 eval 数据镜像；它的示例实现不能冒充官方原始 harness。该目录另提 Expense Claims，本文不把它计入四个主 workflow。

## 1. 原帖 Side-by-side：客服多问题并行判定

来源：[原帖后续](https://x.com/CompleteSkeptic/status/2099925684256899543)、[发布文章](https://typesafe.ai/blog/introducing-system-one-models-and-jev)。

- 文章说明输入是短、信息密集的自然语言段落，问题 key 为便于展示而写得直观。
- 可直接确认的一问名为 **Churn likelihood level**。文章说录制时它是与 GPT-5.6 Terra 唯一不同的判断，且作者认为答案有歧义。
- [原始共享 query](https://console.typesafe.ai/playground?share=shr_13a74b495fb786c4bd7964f11597301e7c9) 本次显示登录页。因此**其余原始问题名、候选、完整 state、标签均不可声称已拿到**。
- 这段演示比较并行概率输出与逐 token 生成，不是公布训练集。截图/演示中的输出也不是人工真值。

### 可完整取得的官方客服扩展例子

官方 [Speculative fan-out — support ticket triage](https://docs.typesafe.ai/patterns/fan-out.md) 给出完整 state、五问、候选和分支代码。**这是可复现的官方文档案例，不是已验证与原帖相同的 query。**

State 是一封自然语言工单：用户描述订单重复扣款、网站更新后无法登录、希望添加 Apple Pay，并表达不满。下面按原始 key 保留结构，问题/候选含义采用中文概述：

| 原始 key | Primitive | 问题与答案空间 |
| --- | --- | --- |
| `category` | Choice | 工单大类；`bug_report`（功能坏了/报错）、`billing`（扣费、发票、退款、订阅）、`feature_request`（新功能）、`account`（登录、权限、资料、安全） |
| `bug_severity` | Score | 0：仅外观且不影响功能；1：功能退化但有替代办法；2：阻断且没有替代办法 |
| `has_reproducible_steps` | Noul | 是否给出了具体复现步骤 |
| `refund_requested` | Noul | 是否明确要求退款或 credit |
| `frustration` | Score | 0：平静客观；1：不满但礼貌；2：非常愤怒 |

单次 fan-out 后由代码执行：

1. `category=bug_report`：severity > 1.5 且 repro > 0.6 时升级工程，否则进入 bug backlog。
2. `category=billing`：refund > 0.7 时向 billing 加退款标记，否则普通转 billing。
3. `category=feature_request`：记录功能请求。
4. 任意 category：frustration > 1.5 时加优先回复标记。
5. 文档代码没有实现 account 分支。若自建数据补齐该路径，必须标为本项目规则。

数据构造可用独立编写的自然语言工单和会话，变化类别、严重程度、是否提供步骤、是否要求退款、不满程度；同一 state 的五问共用 group。生成真值来自我们明确的潜变量/控制规则，不来自 Jev。保留混合意图和边界例子；不能擅自把文档中本来多义的工单当作唯一类别金标。`churn` 若新增，应注明是参考原帖主题的本项目扩展，原始分级定义未知。

## 2. Doom：状态到实时控制

来源：[原帖 Doom](https://x.com/CompleteSkeptic/status/2099925687465570372)、发布文章 Doom 小节。

一手可确认：模型收到的是**结构化状态的文本表示，不是游戏图像**；代码和模型组成实时控制回路，并可响应自然语言玩法要求。文章没有给出完整 state 字段、primitive 列表或逐帧动作标签。当前[官方 demos 索引](https://docs.typesafe.ai/demos.md)只列 Smart Home，没有 Doom 源码条目。

### 可检查的社区实现，不能标成原帖源码

[lukaske/jev-doom-agent](https://github.com/lukaske/jev-doom-agent/tree/318c32a24851444c1170bf083671c38723f3a35a) 使用 Chocolate Doom 3.1.1 WASM 和 Freedoom 0.13.0。固定 commit `318c32a24851444c1170bf083671c38723f3a35a`。

[Observation schema](https://github.com/lukaske/jev-doom-agent/blob/318c32a24851444c1170bf083671c38723f3a35a/src/types.ts)的 state 字段：

- `player`：health、armor、weapon、ammo、recent_damage、under_fire。
- `visible_enemies` / `visible_pickups`：类别、距离、方向、威胁/可达性。
- `navigation`：掩体、未探索方向、出口信息。
- `combat`：可见敌人数、最近敌人的血量/距离/相对角度/瞄准与射程状态。
- `exploration`、`history`、`policy`：探索记忆、前动作、卡住程度和玩法指令。
- `world`：实体和地图线段；`source`：engine 与是否发送 raw pixels 等来源标记。

实际 [server/typesafe.ts](https://github.com/lukaske/jev-doom-agent/blob/318c32a24851444c1170bf083671c38723f3a35a/server/typesafe.ts) 同时发四个 Choice（README 的“单个宏动作”概括不如代码精确）：

| 问题 | choices |
| --- | --- |
| `movement` | HOLD_POSITION, EXPLORE_WORLD, MOVE_TO_ENEMY, RETREAT_FROM_ENEMY, COLLECT_NEAREST_PICKUP, MOVE_TO_USE |
| `view` | KEEP_HEADING, SCAN, FACE_ENEMY |
| `trigger` | HOLD_FIRE, FIRE |
| `interaction` | NO_USE, USE |

四轴同时由本地控制器执行，再读取下个游戏状态。是否开火需考虑敌人可见、瞄准、距离、弹药；接近和转向本身不隐含开火。该社区实现有离线规则 policy，必须与 Jev 输出分开标注。

可自造同任务形式数据：用可再分发的 Freedoom 内容运行真实引擎，记录状态、合法控制、地图/episode、玩法指令、执行结果；规则 teacher、人工动作和模型动作各自记 provenance。训练/测试按地图和 episode 拆分，不能逐帧随机切分。仅手写 health/enemy 等模板算模拟控制数据，不能声称来自 Doom rollout。Chocolate Doom 为 GPL，Freedoom 内容许可证与署名见该仓库 `licenses/`；无需分发商业 Doom WAD。

## 3. Wikiracing：网页图上的多步链接选择

来源：[原帖 Wikiracing](https://x.com/CompleteSkeptic/status/2099925688925184171)、发布文章 Wikiracing 小节。

- 目标：从起始 Wikipedia 页面，只通过当前页面提供的链接，到达指定目标页面。
- 每步答案空间是当前页面真实可点击的链接，不能生成一个并不存在的页面名。
- 一手文章说 Jev Choice 上限 255。超过该数时，作者先对候选独立评分，再做明确选择；**原始 shortlist 大小、评分 rubric 和 prompt 没有在已读公开来源中给出**。
- 多步流程：读取当前页/目标/导航历史 → 取得合法出边 → 打分或 Choice → 点击合法出边 → 更新 state → 到达目标或触发步数/循环停止条件。

可下载的同任务公开数据：[Stanford SNAP Wikispeedia](https://snap.stanford.edu/data/wikispeedia.html)。它不是 Jev 原始演示数据：

| 内容 | 官方统计 / 下载 |
| --- | --- |
| 完成的人类路径 | 51,318 |
| 未完成路径 | 24,875 |
| 文章 / 链接 | 4,604 / 119,882 |
| 路径和图，9.5 MB | [wikispeedia_paths-and-graph.tar.gz](https://snap.stanford.edu/data/wikispeedia/wikispeedia_paths-and-graph.tar.gz) |
| 文章纯文本，35 MB | [wikispeedia_articles_plaintext.tar.gz](https://snap.stanford.edu/data/wikispeedia/wikispeedia_articles_plaintext.tar.gz) |

已实际读取两个压缩包，校验值：

```text
paths-and-graph: 9,901,821 bytes
SHA256 97697096f5d2dcb77aa69e3992305c6c561de89edb9fb10b5ad9feaf8ba534d5
articles_plaintext: 35,844,149 bytes
SHA256 8e43d12822d05746a59f7de8987ffd6eafa57d248303d1c02cfe85b519359dc1
```

路径/图包没有独立 LICENSE 文件；TSV 注释要求引用上述 WWW 2012 和 IJCAI 2009 两篇论文，不应伪造为 CC-BY-SA-4.0 数据包。纯文本来自 2007 Schools Wikipedia Selection，已检查 Earth 等文章尾部的 **GNU Free Documentation License** 声明，并附有 `plaintext_articles/Wikipedia_Text_of_the_GNU_Free_Documentation_License.txt`（GFDL 1.2 文本）。文章与人类路径的来源/许可记录应分开。

包内文件 schema（忽略 `#` 注释和空行；文章名 URL 编码，路径先按 `;` 拆分再 decode）：

| 文件 | 每行字段 |
| --- | --- |
| `articles.tsv` | article |
| `links.tsv` | source、target，两列 tab 分隔、有向边 |
| `categories.tsv` | article、hierarchical_category；同文章可多行 |
| `paths_finished.tsv` | hashedIpAddress、timestamp、durationInSec、path、rating |
| `paths_unfinished.tsv` | hashedIpAddress、timestamp、durationInSec、path、target、type |
| `shortest-path-distance-matrix.txt` | source/target 顺序均同 `articles.tsv`；每个距离是单字符 0–9，无分隔符；`_` 表示不可达 |

人类 path 中 `<` 是返回上一页，必须用导航栈解释，不能作为页面名或简单删除后把两旁页面直接连边；完成路径的 rating 为 1–5 或 `NULL`，未完成 type 为 `timeout` 或 `restart`。`hashedIpAddress` 不进入模型输入。纯文本路径为 `plaintext_articles/<URL-encoded article>.txt`，应清理 Schools/header/footer 后再提取摘要。

可转换为 `(current_article, target_article, history, outgoing_links) → next_link`。人类下一跳是行为示范，不是唯一最优金标；在固定图上算最短距离可生成集合式最优下一跳标签。最短路径/未来节点用于 teacher 和评测，不能泄漏到 state。固定源数据、保留 Wikipedia 原文的来源/许可证和引用；按起终点组合或子图/episode 拆分。要验证的是到达率、步数、回环率、每步合法性和总 wall time，不只有单步 accuracy。

若在最优动作之间放均匀 soft target，它表示自定义 teacher policy，**不是人类不确定性的 calibration 标签**。两个同样最优动作各给 0.5 时，现有 `expected_accuracy` 只测与随机 teacher action 的期望一致率；任意挑对一个最优动作应在 `optimal_action_hit` 记为 1。另需报告最优集合的预测概率质量与 excess distance。按目标文章 group 留出，测的是已知图上的新目标任务；测试目标仍可能以其他训练任务的候选或当前页出现，不能称为从未见过该页面。

## 4. 四个 workflow evals

官方页面首页与下面四个公开路径本次全部返回 HTTP 403。没有尝试认证绕过。以下 Security 的流程图是一手证据；其他三项详细语义仅由二手公开目录/示例 corroborate，不能视为原始 prompt 或数据。

### Security Incidents

官方路径：[security_incidents](https://evals.typesafe.ai/security_incidents)。一手[流程图](https://framerusercontent.com/images/ih1bFwZGYJxlnijbTuXx3f9NeM.png)可读。

State：一条 alert，加告警资产、工单、注册记录、计划任务/维护计划、授权记录；代码另外读取环境、资产重要性与 detector domain。

1. **Triage**：两个 Bool/Noul 等价判断（未经授权活动、已有记录是否事先解释该活动）及一个证据强度 Score。图没有公开完整字段 key 或每级 rubric。
2. **Disposition**：确定性代码判 close / queue / act。图中 act 使用未经授权概率 > 0.75；低风险且已有解释并且不是 domain controller 可关闭。排队的 identity 灰区 0.15–0.60 触发用户通知，否则转 Tier 2。图没有完整列出所有 close 阈值。
3. **Containment**：需 act 才问更深的 11 项：凭证泄漏、攻击者正在使用会话、恶意邮件在 inbox、重启后的 persistence、运行中的恶意进程、向攻击者的出站流量、持久配置变更、是否正在/即将发生、是否已扩散；另有扩散范围 Score 和攻击类别 Choice（host/account/mail/exfiltration）。
4. **Playbook**：按优先组匹配，再选本组条件满足的最强防御动作：正在外传→阻断目的地或资产外联；账户访问→禁用账户/撤销 key/session/要求重新认证；恶意邮件→阻断发件人/清理邮箱/隔离邮件；host compromise→隔离主机/终止进程/隔离文件；配置变更→移除 forwarding rules；无组匹配则紧急升级。

同形式数据可用本项目生成的告警与业务解释配对，例如“新设备登录+注册记录匹配”对“新设备登录+记录冲突”。多轮每个阶段共享同一 incident group。标签应区分语义原子判断与代码算出的动作；所有处置只生成离线 action intent，不能对真实系统执行。尚没有官方题库或 reference probabilities。

### Agent Trace Observability

官方路径：[agent_trace_observability](https://evals.typesafe.ai/agent_trace_observability)。可读二手[任务说明](https://github.com/Anil-matcha/awesome-jev-by-typesafe/blob/afd223fcd4395cca3d5b3c9d1acac30b19203e25/docs/jev-use-case-playbook.md)。

State：完整 agent instructions、对话、工具参数/返回、最终答复和用户反馈。二手示例定义 Noul `permission_breach` / `task_completed` / `user_satisfied`，以及 Choice `failure_kind` = expectation_gap / overt_failure / silent_failure / none；这些 key 是该社区示例的，不应写成官方原始 key。流程语义是先看权限越界，正常完成可关闭，否则进入人工 review、bug filing 或 on-call escalation。

可生成可审计的离线 agent traces：改变授权时间线、工具成功/失败、最终陈述与工具事实的对应关系。可精确验证的工具事实作硬标签；满意程度和预期差距需独立标注或明确为受控合成。按任务场景/trace family 切分，禁止把同 trace 的相邻 turn 分到不同 split。

### Invoice Processing

官方路径：[invoice_processing](https://evals.typesafe.ai/invoice_processing)。二手来源同上。

State：invoice、purchase order、contract、vendor record、prior invoices、往来信息、交付凭证、审批。社区示例的六个 Noul 是是否发票、wrong vendor、duplicate、fraud signal、是否匹配订单、是否待审批；另给 payment_path Choice = pay / schedule / hold / dispute / corrected_invoice / review。**尚未确认官方原始题目数量、types、rubric 或阈值。**

流程语义：先筛非发票/错误主体/重复/欺诈，再比订单和交付语义，代码计算总额、日期、账户等精确条件，最后输出支付/延期/挂起/争议/更正/审批的 action intent。可以独立生成虚构供应商、PO、发票和邮件配套文档，系统性控制重复账单、交付差异与缺少审批。按完整 vendor/order case 切分，不做真实付款。

### Customer Service（多动作 workflow）

官方路径：[customer_service](https://evals.typesafe.ai/customer_service)。二手来源同上。

State：客户会话，随后按分支加入账户 ledger、卡状态、退款记录、订阅和待确认提议。第一轮读取意图、不满、紧迫性、同意/授权、欺诈、法律风险、是否要人工；敏感分支再核对记录；最后检查助手先前陈述是否被账户事实支持。

输出是动作集合，二手概述列出 say / refund / freeze card / set intent / hand off / flag for review / close，不只是单一 intent label。完整候选、Noul/Score 分配、阈值和原始 state/query 未取得。公开社区示例中的 0.8/0.7 阈值不是已验证的官方参数。

同形式数据可生成多轮客服会话和对应账本，控制显式退款请求、对 pending proposal 的真实同意、卡盗用证据、已经退款但助手声称未退款等情形。每个 case 输出原子答案及经代码组合的动作集，并保留不相关问题的 mask。它比前面的五问 support-ticket 文档案例更复杂；二者不能混报覆盖。

## 数据交付时如何命名与验收

- `official_original`：只有真正拿到官方 query、固定来源与许可/数据说明后才能用；目前本文没有取得这类 eval 数据包。
- `official_docs_example`：可用于完整五问 fan-out 文档示例，但官方演示输出不是监督真值。
- `synthetic_control`：根据已核实任务形式独立生成，明确自己的模板、规则、标签和覆盖范围。
- `public_task_data`：如 Wikispeedia，固定数据版本和转换规则，声明不同于 Jev 原始数据。
- `community_implementation`：如上述 Doom 契约，保留实际仓库 commit，不改称官方实现。

每个案例至少分别报告：原始 case/group 数、questions 数、每 primitive 数、标签来源、split 粒度、是否实现完整多步状态转移、是否已有真实模型预测。拥有通用 Choice/Noul/Score schema 不能算“这些 case 的数据都已准备好”。
