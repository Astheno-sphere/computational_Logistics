# Case 数据准备状态

> 2026-09-19 更新：四个官方 workflow 页面后来已成功读取；下文的 403 是早期抓取记录。最新来源、任务范围和数据见 [能力清单](../docs/public-capabilities.md) 与 [workflow 实现](../docs/workflows.md)。公开页面可读不等于已获得完整官方数据集。

2026-09-19。这里的“已准备”指可读、可训练、已通过划分与标签检查的自建研究数据，不代表拿到了 TypeSafe 官方原始数据或完整复现其演示。

| 原帖演示 | 已生成数据 | 对齐范围 | 验证 |
| --- | --- | --- | --- |
| 客服并行判断 | 1,000 会话，6,000 单问 | 官方公开 fan-out 五问 + 本地 churn 扩展；自然语言 synthetic control | 同会话/实体/模板划分、隐藏情形反事实测试、完整 workflow 输入 |
| Doom | 480 episode，3,031 真实状态，9,093 单问 | 真实 ViZDoom basic 靶场，横移/攻击/射击对准程度；脚本弱监督 | 10 episode / 67 步真实引擎回放全一致；完整动作和 reward 轨迹 |
| Wikiracing | 300 目标，2,253 Choice | 真实 Wikispeedia 4,604 文章 / 119,882 链接；候选子集导航 | 固定 archive SHA、完整图 BFS、无 oracle 候选插入、目标分组隔离 |

合计 **17,346 条、1,780 个 group**：train 12,260；calibration 1,091；validation 711；test 1,640；OOD 1,644。跨 split 相同真实模型 prompt 和 state 的审计均为 0。manifest 见 [data-manifests](data-manifests/mixed.json)。

另备通用 synthetic/BoolQ 15,103 条，作为辅助研究数据，不把它们代称为原帖 case。

原帖完整客服共享 query 目前需登录；四个 workflow（Security Incidents、Agent Trace Observability、Invoice Processing、Customer Service）的官方 eval 页面未成功读取原始数据。因此 **这四套官方评测数据尚未准备齐**；[official-cases.md](../docs/official-cases.md) 记录了已确认来源与可获得范围。

模型侧三种指定 Qwen 都已完成真实训练、保存和重载的工程 smoke，以及同设置的 100 步正式 case pilot；重载 logits 误差均为 0。tiny smoke 的准确率没有研究意义；case pilot 使用同一数据、训练步数与评估 ID。[完整结果](pilot-results.md) 明确记录了客服/Doom收益及 Wiki OOD 命中下降。三个保存的 checkpoint 也均通过混合 Choice/Noul/Score 的实际 API 请求。
