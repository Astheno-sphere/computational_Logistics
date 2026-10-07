# 原 100-step pilots：N1 上的 4,096-token 评测审计

此报告评测的是原先每模型 **100 optimizer steps、400 条混合训练记录**的 pilot checkpoint；不是正在进行的 release-v2 full-pass 训练结果。服务运行在 MS N1-1，原始容量上限为 4,096 tokens。后续 16,384-token JF100 容量复测是独立实验，不能覆盖或合并本组结果。

## Workflow：完整动作集合

每模型 96 cases、96 个独立 parent groups：四个 workflow 各 24 cases（test 12 + OOD 12）。模型间选题完全相同，selection SHA-256 为 `9ea71672cd5beb53d9c97d2392a7beb5d04a1708e515f6ff8dc0e0e847d23c6a`。这些是本项目独立合成的简化策略，不是官方 workflow 题库。

| 模型 | 原始动作集合完全正确 | 软件 gate 后完全正确 | 被 gate 阻止的动作数 |
|---|---:|---:|---:|
| Qwen3.5-2B pilot | 9/96（9.4%） | 15/96（15.6%） | 43 |
| Qwen3.5-9B pilot | 33/96（34.4%） | 45/96（46.9%） | 32 |
| Qwen3.8-27B pilot | 41/96（42.7%） | 43/96（44.8%） | 15 |

| 原始动作集合完全正确，分母均为 24 | 2B | 9B | 27B |
|---|---:|---:|---:|
| 客服 | 3 | 12 | 8 |
| 安全事件 | 5 | 16 | 19 |
| Agent Trace | 1 | 5 | 7 |
| 发票处理 | 0 | 0 | 7 |

软件 gate 能过滤部分不合授权条件的动作，这部分增益不是模型能力提升。例如 9B 发票从原始 0/24 到 gate 后 10/24。当前较大的模型也没有在所有 workflow 上单调变好。

## 游戏闭环

每模型计划 45 个 episodes：5 个游戏 × 3 个固定 seeds（10001、10002、10003）× learned/random/teacher 三种策略，单局上限 40 steps。Random/teacher 是独立基线，不是模型失败后的补救。

| 原生指标，每项 3 局 | 2B learned | 9B learned | 27B learned | Random | Teacher |
|---|---:|---:|---:|---:|---:|
| Snake：平均食物数 | 0 | 0 | 0 | 0 | 7.67 |
| T-Rex：完成局数 | 2/3 | 2/3 | 3/3 | 0/3 | 3/3 |
| Tile platformer：完成局数 | 0/3 | 0/3 | 0/3 | 0/3 | 3/3 |
| Wiki 小图：到达目标局数 | 3/3 | 3/3 | 3/3 | 0/3 | 3/3 |
| ViZDoom basic：平均 engine reward | -29.0 | 62.33 | 82.33 | 46.0 | 80.33 |

三个模型各 45/45 episodes 有效、零运行错误，合计 135 episodes；其中每个模型只有 15 局使用 learned policy。2B/9B/27B 原始 trace 分别记录 501/574/480 步（合计 1,555，含全部基线）。Snake learned 都未吃到食物；9B platformer 三局均在 40-step 上限时仍没有前进。Wiki 是很小的固定图，3/3 不能证明真实 Wikipedia 导航能力。Doom 没有统一 success 字段，因此只报告原生奖励，不从 terminal 状态推断通关。

游戏种子/布局未证明完全脱离训练生成器；这是小规模集成闭环检查，不是独立官方游戏 benchmark。

## JF100：保留原 4K 容量结果

| 模型 | 正确 / 全部 300 请求 | 系统准确率 | 有效响应 | 4,096-token 容量错误 |
|---|---:|---:|---:|---:|
| Qwen3.5-2B pilot | 142/300 | 47.33% | 288/300 | 12 |
| Qwen3.5-9B pilot | 177/300 | 59.00% | 288/300 | 12 |
| Qwen3.8-27B pilot | 186/300 | 62.00% | 288/300 | 12 |
| 上游复用的 Jev 1.13.0 reference | 231/300 | 77.00% | 300/300 | — |

100 题 × 3 个位置轮换全部保留；容量错误按协议计零分，不能从分母中删去。2B/9B/27B 相对上游 Jev 的配对差分别为 −29.67 pp（95% CI −37.33 至 −22.00）、−18.00 pp（−27.00 至 −9.33）和 −15.00 pp（−21.67 至 −8.67）。这些是 50 个模板对、按 domain 分层的探索性 bootstrap，不是 300 个独立样本；上下文容量、精度、硬件和接口不同，不能据此推断通用模型能力或速度等价。

## 审计来源与边界

远端只读来源：`/data/zefan/open-jev/evals/pilot-suite-n1-v1/{2b,9b,27b}`。游戏核对了 report episode 计数、对应 trace 身份、逐局 metrics、step 数、initial-state hash 和分策略汇总均值；workflow 核对了 96 个 case/parent/prediction/原始响应计数、输入 hashes，并从 typed responses 重算动作集合和 gate 后计数。没有调用推理或改动训练。

三个服务记录的代码 commit 均为 `99e881108c6cacadafd364088505e84975ca43fc`。Checkpoint SHA-256：

- 2B：`1d3c0e4e37bf04731edee447363ddc02d084a9c1f10ab829ac4d424f7d7c413b`
- 9B：`7aa5f62fa39b83aee07915e7e351da5c4c38b4ce5f751cf22c7d45edf7dfc0ef`
- 27B：`68ff078d7a83a92f3a4b6458d4c349b81bf533baf373d0361135f53e684357a2`

最终只读审计时间：2026-09-20T01:09:08.141201+00:00。三个模型的 workflow、games、JF100 结果均已完整。所有已核对的计数/均值/trace 指标与汇总一致；三个 workflow 的逐行原始响应也与预测文件完全配对。本次没有重新审计额外 latency benchmark 文件。
