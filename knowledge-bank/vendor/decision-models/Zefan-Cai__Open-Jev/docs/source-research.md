# Jev / System One：公开来源与自建边界

> 2026-09-19 更新：四个官方 workflow 页面后来已成功读取；下文的 403 是早期抓取记录。最新来源、任务范围和数据见 [能力清单](public-capabilities.md) 与 [workflow 实现](workflows.md)。公开页面可读不等于已获得完整官方数据集。

检索时间：2026-09-19 21:20 UTC。原帖发布：2026-09-15。本文记录一手公开来源；性能、校准等厂商宣称尚未经本项目独立验证。

## 确认用户所指的 Jev

- 原帖：[Diogo Almeida / CompleteSkeptic](https://x.com/CompleteSkeptic/status/2099925682726002904)，可读镜像 [FxTwitter API](https://api.fxtwitter.com/status/2099925682726002904)。作者介绍 TypeSafe AI 的 Jev，训练方法名为 RLCD。
- 一手发布文章：[Introducing System One Models & Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev)。Jev 是产品名，取自 William Stanley Jevons / Jevons paradox，不是论文缩写，也不是 JEPA。模型类别名 System One 来自 Kahneman 的快思考概念。
- RLCD 全称 **Reinforcement Learning for Calibrated Decisions**。发布文章的接口概括是："unstructured state in, typed probabilistic decisions out."
- 原帖后续 [2099925684256899543](https://x.com/CompleteSkeptic/status/2099925684256899543) 明确说："Jev can't generate text"。因此用 JSON SFT 包装一个生成模型可以作为基线，不能直接称为复现其非生成架构。

## 可以忠实实现的公开接口

请求是 `state`、`model`、`questions`，其中 `questions` 是调用者提供的 ID 到问题定义的映射。模型读取问题内容，不读取问题 ID。所有问题针对同一 state 独立求值，API 支持将三种 primitive 混合在一次请求中。

| Primitive | 输入定义 | 输出定义 | 一手来源 |
| --- | --- | --- | --- |
| Choice | `instructions`；`criteria` 为候选名称到描述的映射，最多 255 个候选 | `choice = argmax(p)`；全部候选 `probabilities`，和为 1；分布集中度 `confidence` | [Choice](https://docs.typesafe.ai/primitives/choice.md) |
| Score | `instructions`；`criteria` 为 2–10 个自然语言描述的有序等级 | 各等级 `probabilities`；`score = sum(i * p_i)`，等级从 0 开始；`confidence`；等级 `legend` | [Score](https://docs.typesafe.ai/primitives/score.md) |
| Noul | 二元问题 `instructions`；可选 `true` / `false` 语义边界 | `noul = P(yes)`，范围 [0,1]；无单独 `confidence` | [Noul](https://docs.typesafe.ai/primitives/noul.md) |

其他可复现的接口约束：

1. Choice 候选名称和描述都进入模型；不完备的答案空间需要显式 `other` / `not_stated` 等选项。
2. Score 的等级在软件中有序，但官方说明每个等级单独评价，模型不看等级序号和相邻等级。等级描述应自包含，不能写“比上一档更强”。
3. 概率和 confidence 不同。confidence 是分布的统计量，不能直接解释成该次答案正确的概率。
4. Score 的小数表示等级期望，不能解释为真实数值的精确插值。例如 `1.3` 不意味着问题影响了 30% 用户。
5. 一次请求中每个问题独立。需要多步推理时，由代码编排下一轮问题；不能让前一个问题的隐藏答案泄漏进后一个独立问题。

来源：[Introduction](https://docs.typesafe.ai/introduction.md)、[Confidence](https://docs.typesafe.ai/confidence.md)、[API](https://docs.typesafe.ai/api.md)、[Patterns](https://docs.typesafe.ai/patterns.md)。

## Confidence：有公开参考公式，但不要伪称托管模型内部公式已证实

TypeSafe 的官方开源 [system-one-adapter-python](https://github.com/typesafe-ai/system-one-adapter-python) 是把其他 LLM 包装为同一 API 的基线工具，不是 Jev 权重或训练实现。

固定版本：`adffc2eab300a4fa3c0e92252d4ffd6ceaa53700`，提交时间 2026-09-18 10:47:43 UTC。可审查 [confidence_metrics.py](https://github.com/typesafe-ai/system-one-adapter-python/blob/adffc2eab300a4fa3c0e92252d4ffd6ceaa53700/src/system_one_adapter/_utils/confidence_metrics.py)。以下是该开源 adapter 的确切公式：

令 `p` 已归一化，候选数量为 `K`：

```text
Choice confidence = (max(p) - 1/K) / (1 - 1/K)

m = argmax_i p_i                 # 并列时取首次出现的下标
D = sum_i p_i * abs(i - m)
U = sum_i abs(i - (K - 1)/2) / K
Score confidence = max(0, 1 - D/U)
```

`K=1` 返回 1；未归一化概率先除以总和；总和为 0 时使用均匀分布。我们的 API 可明确采用这些参考公式，不需要额外训练一个 confidence 回归头。

托管服务文档只定义 confidence 来自概率分布，没有公开其实现版本。文档中的展示数字也有舍入或示例差异，因此不应承诺我们的数值逐点等于 Jev 服务。**采用参考公式不会自动让模型变得 calibrated**；校准必须对带真值的独立数据测量。

## RLCD、架构和数据：公开到哪里

| 项目 | 公开事实 | 尚未公开或本文没有找到 |
| --- | --- | --- |
| 训练目标 | 输出决策和反映不确定性的概率；概率要与结果频率相符 | RLCD loss、reward、策略梯度估计、KL 约束、采样器、优化器、训练日程 |
| 架构 | 厂商宣称新架构、并行 sampler、单次查询给出全部概率、不生成文本 | backbone 型号/规模、attention 拓扑、head 设计、权重、kernel 实现 |
| 数据 | FAQ："We make all the data ourselves." | 数据集、生成/筛选/标注配方、teacher、分歧处理、混合权重 |
| 校准 | 概率 0.8 的一组事件应约有 80% 发生；这是群体统计 | 官方温度缩放参数、分域校准法、校准集与校准实测曲线 |

依据：[发布文章](https://typesafe.ai/blog/introducing-system-one-models-and-jev)（含网页内 FAQ 的序列化内容）、[AI primer](https://docs.typesafe.ai/introduction/machine-learning-primer.md)、[System One](https://docs.typesafe.ai/concepts/system-one.md)、[公开 GitHub 组织](https://github.com/typesafe-ai)。这些一手来源没有给出可复现 RLCD 的原始论文或训练代码；不能把我们选择的 CE/Brier/soft-target 方法称为官方 RLCD 实现。

## 官方评测的实际含义

发布文章描述 4 个由固定代码编排的 workflow。所有模型使用同一流程，参考答案是 GPT-6 Astra 和 Claude Fable 5.1 的平均概率。它不是独立人工真值测试。作者承认内部 capabilities team 构建 workflow 可能引入偏好；参考大模型也可能偏向各自厂商。

193.6x 更快、444.6x 更便宜来自这些 workflow；文章称其可能处于真实收益的较高端。演示使用短输入以强调并行输出优势；短输入对 Jev 有利。LLM 对照被要求输出完整概率，通常比只给离散答案更慢、更贵。原网站 [evals.typesafe.ai](https://evals.typesafe.ai/) 本次读取返回 HTTP 403，所以没有独立核验其下载数据或逐项算分。

“无幻觉”的可保证部分是输出满足给定 schema，不会虚构候选或字段；这不能证明选择语义正确。官方 [Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md)，2026-09-17 复核，明确记录数字推理、长上下文、复杂间接指代、对抗内容、同义/否定问题一致性的失败。甚至同一问题的 Noul 与二元 Choice 概率也可能显著不同。

## 我们的最小自建方案及归属

建议对外称 **Jev-inspired Qwen decision model**，或“兼容 System One 任务接口的 Qwen 决策模型”。下列训练和内部实现是本项目提出的方案，不能当作 TypeSafe 的秘密配方。

| 设计 | 与公开 Jev 的关系 |
| --- | --- |
| Qwen 文本 backbone，去掉生成路径，接非生成 decision heads | 我们的具体架构；忠实于决策输出目标，非官方架构复现 |
| Choice：对自然语言候选产生 logits，padding 候选 mask + softmax | 我们的实现；符合公开输出契约。候选需真正参与编码，不能让固定下标替代候选语义 |
| Noul：二元 logit + sigmoid | 我们的实现；符合公开输出契约 |
| Score：自然语言等级概率 + 软件计算期望 | 符合公开输出契约；具体训练/打分头由我们定义。若让等级互相看见，需注明没有复现官方的独立等级评估 |
| 每个 state/question 作为隔离样本；同请求的问题组成 GPU batch | 符合独立问题语义；只是朴素并行基线，不是官方 state 仅编码一次的高效实现 |
| temperature scaling / 独立校准集 | 我们的后处理；必须报告校准前后分数 |
| CE / BCE / soft-target CE / Brier 类适当评分规则 | 我们的训练基线；在没有真实 RL 目标与 rollout 时不可命名为 RLCD 复现 |

首阶段必须记录实际重复 state 的计算量和 p50/p95 延迟；不能从 batch 推理直接推论成本下降 100 倍。后续可评估共享 state 编码/缓存与隔离问题分支，但这也属于我们的架构研究。

## 数据构造与验证建议（本项目设计）

1. 先固定统一格式：`state + question(type, instructions, criteria) + target + provenance + source_group`。target 应区分硬真值、已知生成概率、人工分布、teacher 分布，不能混为真值。
2. 建立 Choice / Noul / Score 三族：意图路由、蕴含/证据判断、检索候选选择、抽取候选选择、有描述 rubric 的等级评分。程序计算的数值留在代码；语义判断交给模型。
3. 从已有带标签数据改写问题和候选，保留标签来源。QA 抽取先产候选 span，加 `not_stated`；多标签任务拆成多个 Noul；有序标注转成有描述等级的 Score。
4. 自造数据重点覆盖缺失证据、可合理多解、长尾选项、冲突信息、干扰文本。只有知道生成分布或有重复独立标注时才声称软标签反映真实不确定性；不能任意给正确类 0.8 就叫校准训练。
5. 在原始文档/源样本族层级切分 train / calibration / test，然后才改写、扩写和造负例。候选置换、同义改写与相同 state 的所有问题留在同一 split；另留域外模板和来源测试。
6. 评测 accuracy / macro-F1、NLL、Brier、ECE 和 risk–coverage；Score 加等级 MAE。按 domain、candidate count、输入长度、歧义/缺失证据分桶。ECE 单独低并不能证明模型有用。
7. 另外报告类型合法率、候选置换一致性、问题增删隔离性、同义改写稳健性、否定一致性。相同 benchmark 同时跑生成 JSON 基线、未训练 backbone + head、训练后 head、校准后 head，避免把接口约束收益混同于能力收益。
8. 使用相同输入、同一输出信息量、同一硬件/精度/批量记录端到端 latency、throughput、峰值显存和实际成本；再接固定 workflow 测最终任务效用。任何对 Jev 的直接比较都需要实际调用和固定版本，不能以厂商图表代替本项目实验。
