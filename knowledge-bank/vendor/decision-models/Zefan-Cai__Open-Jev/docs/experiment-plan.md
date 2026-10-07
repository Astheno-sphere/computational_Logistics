# 第一轮实验设计

## 假设与可证伪结论

问题不是能否输出合法 JSON，而是文本 backbone 经决策训练后能否在独立问题上给出更好的概率。

固定三模型、同数据、同 seed、同训练步数和同测试 ID，比较：

1. 原始 Qwen 的 Yes-minus-No readout（不进行文本生成）。
2. 同 backbone 的 LoRA + 共享标量 decision head，CE + Brier 训练。
3. 第 2 项加仅由 calibration split 拟合的全局温度。
4. 原始 readout 同样拟合独立温度，区分训练收益与仅靠校准就能得到的收益。

预期训练能降低 ID NLL/Brier；校准应降低概率误差而不改变 argmax 准确率。若校准损害 OOD，则报告该权衡，不改测试集或重选温度。所有结论允许低于预期。

初始固定 100 optimizer steps、LoRA rank 8、accumulation 4，每模型一张 H100。测试与校准各抽 128 行，OOD 另抽 128 行；仅属工程 pilot。若输入过长或内存失败，先修复并把旧运行标为 invalid；不得静默丢行或关闭方法。

2026-09-19 用户指出需覆盖原帖实际 case，因此正式 pilot 加入客服 fan-out、ViZDoom 真实状态、Wikispeedia 导航，而非仅使用通用 synthetic/BoolQ。评估按 source/kind 轮询抽样，避免大数据源掩盖较小 case；报告逐 source/kind/question 指标。100×4 只消费 400 条训练记录，不能描述成完整训练过整个数据集。

## 数据形式

每行包含 `id/group_id/split/source/state/question/kind/options/target/metadata`。推理只读取 state/question/kind/options。

- 多类分类 → Choice，target 为按同序候选排列的 one-hot/真实标注分布。
- 二元分类/真假 QA → Noul，target=[P(no),P(yes)]。
- 有序评分 → Score，每等级有自包含描述，target 是等级分布；期望由代码计算。
- 多标签 → 同一 group 的多个 Noul。
- 抽取/检索 → 候选列表 + 明确的“不在候选中”选项；候选生成本身单独计费和评测。

不能随意把硬标签平滑成 0.8 就声称知道真实不确定性。下一阶段的软标签来源应是已知随机机制、多位独立标注者或明确标注为 teacher 的分布。

## 首轮以后

先根据原始预测定位错误：读规则失败、候选语义不清、真假概率偏置、长输入或 OOD 校准失效。确认收益后才扩大数据和训练：

- 数据规模 10k/100k；新增有自然语言歧义、缺失证据、冲突证据、同义与否定的独立任务族。
- CE-only 对 CE+Brier；全局温度对按 primitive 校准；LoRA 对 head-only。
- 随机种子复跑与全测试集；保留未参与任何训练/调参的新任务家族。
- 加生成 JSON 基线，按同硬件、同输入、同输出信息量测 p50/p95 和 throughput。没有该对照就不报告加速倍数。
- 真正的效率研究：共享 state prefill、独立问题分支/缓存、固定类型 head；严格验证隔离和候选置换。
- 在监督基线成立后，才设计并命名本项目自己的 calibrated-decision RL 目标；不借用未公开 RLCD 名称。

MS H100 足够首轮，当前繁忙 B200 不参与。RTX PRO 6000 可用于后续数据生成/并行消融；使用前需重新查实时占用。
