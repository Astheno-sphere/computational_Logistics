# 局限

AnyJev 和 Tacit 模型做不到什么，以及这些数字在哪里不再适用。
英文版见 [limitations.md](limitations.md)。

- **准确率的上限是模型本身。** 读法去掉的是顺序和标签先验的影响，自蒸馏把推理挪进一次前向。两者都不会给模型增加它没有的知识。
- **Tacit 的一次前向按给定顺序读选项。** 它没有在轮换上做平均。
  在 Tacit 模型上用 `Decider(level="L0")` 可以做到，代价是 K 次 prefill；这一点我们还没测过。
- **一个转去推理的决策要花几秒，而不是几毫秒。** 它要生成最长 `cot_max_tokens` 的推理过程。
  上限管的是有多少决策转去推理，管不了单个决策要多久。
- **在 vLLM 上，Tacit 从前 20 个 log-probability 里读标签**，不在其中的标签按 0 计。
- **Tacit-9B 和 Tacit-2B（Qwen3.5）需要 transformers ≥ 5。** 在 Hopper GPU 上，`vllm serve` 要用 `nvcc` 给它们编译一个 kernel，
  所以机器上得装 CUDA toolkit；`engine="vllm"` 会自己换成 Triton kernel。
- **当一个批次里某个标签占绝大多数时，L0 的批次先验会损失准确率。** 这时用 `prior="content_free"` 或 `prior="none"`。

## 另外

- 字母读法最多支持 26 个选项。
- n = 300 时，5% 风险下的覆盖率是方差很大的估计。
- 已发布结果里的每个决策都是单独评分的，没有放在 agent 循环里。
