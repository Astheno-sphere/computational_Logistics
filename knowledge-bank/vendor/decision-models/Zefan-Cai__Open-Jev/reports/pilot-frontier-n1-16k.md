# 原 100-step pilots：N1 上的 16,384-token JF100 复测审计

三个模型的 **900/900 个 benchmark 请求均已完成且可计分**，全部 HTTP 200、零服务错误、零上下文容量错误。Suite manifest 的最终状态仍是 `failed`：全部评测完成、最后一个服务关闭后，launcher 的 GPU 空闲检查发现其他项目进程。该清理检查失败不应被写成模型评测失败，也不能把整个 suite 状态改报为成功。

本报告使用原先每模型 **100 optimizer steps、400 条混合训练记录**的 pilot checkpoint，不是 release-v2 full-pass 训练结果。原 [4K 评测](pilot-suite-n1-4k.md) 保留为独立配置；两组不能覆盖或合并。

## 4K 与 16K 的完整分母结果

每模型均为同样的 100 题 × 3 个选项位置轮换，共 300 个唯一 trials。请求重建及 hash 比较确认，两组逐 trial 的可见输入完全相同。原 4K 的容量错误按协议计零分，保留在分母中。

| 模型 | 4K 正确 / 300 | 16K 正确 / 300 | 16K 准确率（95% CI） | 容量错误：4K → 16K |
|---|---:|---:|---:|---:|
| Qwen3.5-2B pilot | 142（47.33%） | 148 | 49.33%（43.00–55.00%） | 12 → 0 |
| Qwen3.5-9B pilot | 177（59.00%） | 187 | 62.33%（56.00–68.33%） | 12 → 0 |
| Qwen3.8-27B pilot | 186（62.00%） | 196 | 65.33%（59.33–71.33%） | 12 → 0 |

原 12 个失败 trials 在 16K 全部返回有效响应，2B/9B/27B 分别答对 6/9/9 个。其余 288 个两组均有效的 trials 中，分别有 11/2/12 个答案变化，其中 8/1/9 个正确性变化。因此，总分提升不能全部归因于接受更长输入。

两组 checkpoint 权重、base-model revision 和校准温度一致；运行配置及代码版本不同：

| 配置 | max-length | 服务 batch-size | 代码 commit |
|---|---:|---:|---|
| 原 4K | 4096 | 16 | `99e881108c6cacadafd364088505e84975ca43fc` |
| 本次 16K | 16384 | 1 | `fb9d51731f1d2e720bfc44dd58ee4edf0adfc875` |

上述 flags 均从各模型保存的 `server_command` 核对；16K 的 900 个原始响应也均记录 `metadata.max_length=16384`。这不是只改变上下文上限的受控消融。

## 与已发布 Jev reference 的探索性比较

复用上游实验 v0.2-budget 中 **Jev 1.13.0 的 231/300（77.00%）**，本次未重新运行 Jev。

| 模型 | 16K 相对 Jev 的准确率差 | 配对差的 95% CI |
|---|---:|---:|
| 2B pilot | −27.67 pp | −35.00 至 −20.33 pp |
| 9B pilot | −14.67 pp | −22.67 至 −7.00 pp |
| 27B pilot | −11.67 pp | −17.67 至 −6.33 pp |

区间按 50 个 paired templates、domain 分层 bootstrap 计算，5,000 draws、seed 92026；三个位置轮换不是独立随机样本。这是有限题库上的探索性比较，硬件、精度、接口和运行配置不匹配，不能据此宣称通用能力或速度等价。训练数据与此题库的独立检查只覆盖精确可见输入及长原文嵌入匹配，不能证明预训练或语义层面完全无污染。

## 完成时间与 launcher 失败

所有时间为 2026-09-20 UTC，来自原始 manifest：

| 模型 | frontier 测量结束 | 测量退出码 | 服务停止 |
|---|---|---:|---|
| 2B | 01:09:01.196377 | 0 | 01:09:01.460866 |
| 9B | 01:10:36.040144 | 0 | 01:10:36.313186 |
| 27B | 01:13:59.797559 | 0 | 01:14:00.176016 |

三个服务停止时均记录 `server_exit_code=-15`，与 launcher 测量结束后的服务关闭一致。01:14:30.477000 的最终错误是物理 GPU 3 仍被 PID `812949` 占用（5,252 MiB），空闲保护检查据此使 suite 失败。审计时该 PID 已不存在，无法从 `/proc/812949/stat` 恢复启动时间，因此无法判断它是否也与 27B 测量部分重叠。本报告不使用本次墙钟耗时作性能结论。没有终止其他进程，也没有重跑评测。

## 可追溯性与审计范围

只读来源为 N1-1（`kwade5342000001`）、物理 GPU 3 的 `/data/zefan/open-jev/evals/pilot-frontier-16k-n1-v1`，原组为相邻的 `pilot-suite-n1-v1`。本次审计只运行 CPU 数据核对：逐行重建请求及 hash、核对身份与 checkpoint、重算计分、domain/difficulty 汇总、置信区间和配对差；三个模型的 `audit_outcomes` 均返回零错误。没有展示 benchmark 题干与 gold，没有启动模型或改动远端文件。

JF100 来源：[softpudding/jev-frontier-100](https://github.com/softpudding/jev-frontier-100)，MIT，固定 commit `9abacec47394f3b393f81fbe3cdd524f028bc088`；dataset v0.1.0 SHA-256：`dd107ba90de381eaa479408492e81d7222115782e5fe601ab43986f94cd1d0fa`。16K suite manifest SHA-256：`d0326cf090c7c6f2a9993a1206dd549dddba6852aeffda2b9406a1673a394c52`。

| 模型 | Checkpoint SHA-256（与原 4K 相同） | 16K outcomes SHA-256 |
|---|---|---|
| 2B | `1d3c0e4e37bf04731edee447363ddc02d084a9c1f10ab829ac4d424f7d7c413b` | `1ab5ee08be376d2d8a0a8fc6074a56b9a1b85b9fb051d60d9aaa27c1e5f01010` |
| 9B | `7aa5f62fa39b83aee07915e7e351da5c4c38b4ce5f751cf22c7d45edf7dfc0ef` | `1021efd4fa80c1ec59849cc981a6a1bf4c392a03d679fcd735367917d723317d` |
| 27B | `68ff078d7a83a92f3a4b6458d4c349b81bf533baf373d0361135f53e684357a2` | `b4ead98bb9efa8e3464ec73434a9856e849b0d622e3e1bf1668c0fa5dac70f1a` |
