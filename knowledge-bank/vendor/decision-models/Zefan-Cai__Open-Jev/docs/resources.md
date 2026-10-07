# Runtime and deployment records

**Current public deployment entry:** [released-model deployment guide](deployment.md).
The 2B, 9B and 27B v1.1 adapter/head packages are published. The
[27B full internal audit](internal-full-evaluation.md) and historical 231-public
result are complete; [fresh independent 27B sealed evaluation](evaluation-ledger.md)
remains pending. The machine allocations and unfinished training statements
below are historical operational snapshots, not current job or release status.

The [2026-10-02 deployment validation](../reports/deployment-validation-20261002/report.json)
records fresh base-wheel/API checks without loading model weights. It does
not claim fresh Linux CUDA, full-size MPS or trained GPU inference validation.

Separate [H200 released-2B measurements](../reports/efficiency-20261002/h200-2b-summary.md)
now record actual model inference, HTTP and parity, with the pinned checkpoint,
verified base files and runtime versions. They reused a read-only runtime with
an isolated package overlay. The [reproducibility receipt](reproducibility-receipt-20261002.md)
distinguishes these measurements from the clean base-package checks.

## Archived operational records

# 集群与模型运行环境

## 当前分配：仅 MS N1-1 前四张卡

用户最新要求覆盖下面的历史资源选择。所有 Open-Jev 训练、推理和评测只使用
**N1-1 / `kwade5342000001` 的物理 GPU 0–3**。2B、9B 已完成训练和四卡
分片全量评测；现在这四张卡共同运行新的 27B DDP 训练。GPU 4–7 有其他任务，
不操作。资源约束保存在 `state/auto_research/resource_policy.json`；阶段顺序和
独占规则见[四卡调度](four-gpu-handoff.md)，不得同时启动额外 GPU 评测。

- SSH：`ssh -o BatchMode=yes sigma@192.0.2.1`
- 活动调度和 27B 代码：`/mnt/localssd/open-jev/four-gpu-repo`，固定在
  `99c5361d83edd5f9dbd11cb3f4bd9f9c54b5973e`，运行期间不更新。
- 原训练代码：`/mnt/localssd/open-jev/repo`，固定在
  `99e881108c6cacadafd364088505e84975ca43fc`；原评测 checkout 也保持原版本。
- Python：`/mnt/localssd/open-jev/runtime/venv/bin/python`
- 模型缓存：`/mnt/localssd/open-jev/hf-cache`；三个固定 revision 已下载完整。
- 原 release-v2 数据：`/mnt/localssd/open-jev/repo/data/release-v2`
- 新 27B 数据：`/data/zefan/open-jev/data/browser-drone-expansion-v1`
- 持久运行产物：`/data/zefan/open-jev/runs`
- 环境探测：`/mnt/localssd/open-jev/logs/runtime-probe-result.json`

已完成的 2B、9B release-v2 训练各读取 80,816 条训练记录、完成 20,204 步，
产物保存在 `/data/zefan/open-jev/runs/release-v2-fullpass-n1-v1`。两模型每个
26,452 条全量评测已通过[独立审计](../reports/full-data-eval-n1-v1/README.md)。
同目录下的旧单卡 27B 已停止，保留 9,000 步断点和原日志。

新 27B 从固定上游权重重新训练，计划 110,324 条记录、全局 batch 4、27,581 步。
产物写入 `/data/zefan/open-jev/runs/browser-drone-expansion-v1-27b-ddp-n1-v1`，
每 500 步保存 DDP 恢复快照。[早期运行证据](../reports/27b-ddp-n1/README.md)
已核实实际 CUDA 优化与首个快照；全部训练和最终评测尚未完成。
启动记录在 `reports/launches/`。原始 pilot checkpoint 和本地副本继续保留。

N4-4 上本项目的三个服务和三个扩展训练进程已经停止；停止后检查全部八张卡均无
计算进程、显存 0 MiB、利用率 0%。原始 pilot checkpoint 和日志已保留。
被中断的扩展训练不算完成：2B 完成 400 步但评测未完成，9B 停于 287 步，
27B 停于 90 步；后两者没有可恢复快照。不得在 N4-4 重启这些任务。
后续复查确认这六个原进程均已退出，N4-4 已被其他工作使用；释放记录不代表它
此刻仍然空闲。

N1 的独立 runtime 不修改共享环境；已验证完整 CPU 测试及真实 Qwen GPU 前向、
反向。重要产物须同步到本地或持久存储，NVMe 路径仍然只是临时空间。

### N1 runtime 版本记录

2026-09-20 09:04:57 UTC 的只读包元数据记录 (`../reports/runtime-checks/n1-runtime-metadata-20260920.json`, operational record retained in the development archive)
来自上述 N1 Python：CPython 3.11.15、Linux x86_64、内核
`5.15.0-1102-azure`。按 `importlib.metadata.distribution(name).version`
的首个匹配记录：

| 包 | distribution metadata 版本 |
| --- | --- |
| torch | 2.8.0 |
| transformers | 5.10.2 |
| peft | 0.19.1 |
| accelerate | 1.13.0 |
| datasets | 5.0.0 |
| safetensors | 0.7.0 |
| tokenizers | 0.22.2 |
| huggingface-hub | 1.19.0 |

项目 runtime 的基础前缀是 `/path/to/user/miniconda3/envs/llm_env`，可见包集合
包含重复的同名 distribution；枚举后用字典覆盖会错误选到其他版本。
上述记录不导入 Torch 或模型，未捕获当前 CUDA wheel 的构建后缀，不能把下方
历史 N4 的 `+cu128` 作为 N1 的本次观测。实际训练是否成功由运行日志单独证明。

`pyproject.toml` 和 `requirements.txt` 已固定 transformers、peft、accelerate、
datasets 的上述版本；Torch 仍允许 `>=2.8`，safetensors 没有固定版本。
这份环境记录用于定位已运行的配置；完整依赖锁、wheel 来源及全新 Linux GPU
环境安装验证尚未完成。调度器和完整测试套件使用 Unix `fcntl`，当前 GPU 流程以 Linux 为目标。
ViZDoom 通过 `.[doom]` 单独安装，固定的 1.2.4 要求 Python `<3.13`；
未装引擎时的跳过测试不构成 Doom 运行验证。

### 基础包独立安装验证

本地[独立安装记录](../reports/runtime-checks/base-wheel-install-local.json)针对
macOS arm64、Python 3.12.14 的全新 venv：构建普通 wheel、安装后离开源码目录，
检查包导入、两个 CLI 的帮助入口以及协议和客户端路径。未安装训练依赖、加载模型
或分配 GPU；这些结果不替代上面的 Linux GPU 环境验证。

该检查发现原先允许的 setuptools 68 无法解析 `project.license = "MIT"`。
`pyproject.toml` 的最低构建版本已提高到 **77.0.3**，并以该版本验证构建。
许可证仍为 MIT。浏览器静态示例、训练及 `scripts.*` 评测继续按 README 从仓库
checkout 运行；普通 wheel 没有包含这些静态示例或评测脚本。

### 训练代码版本记录

后续单卡和四卡训练从训练模块所在的 **Git checkout** 获取 commit；调用命令时
所在的目录不决定代码版本。普通 wheel 或没有 `.git` 的源码目录不能提供这个
来源记录，训练入口会在导入模型、读取数据或创建输出前报错，并提示从 Git
checkout 使用 `pip install -e '.[train]'`。帮助入口和推理不需要此训练检查。
[本地 CPU 回归记录](../reports/runtime-checks/training-source-provenance-local.json)
覆盖不同调用目录、调用者 Git 环境变量、脏工作区、worktree 和普通安装路径；
9 项新测试及 9 项已有检查通过，5 项需要 Torch 的数值测试未运行。

该修复只影响后续使用新代码的作业。当前 N1 训练一直从其固定 checkout 启动，
记录的 commit 已由进程工作目录、源码哈希和检查点独立核验；活动代码与已有
run metadata 保持原样。已有恢复机制仍按保存的代码哈希校验，恢复当前训练时
必须继续使用原固定版本。

## 历史核验（不再作为启动依据）

只读核验时间：2026-09-19 21:19–21:23 UTC。以下保留首次选机的历史快照，
其中 N4-4 的使用建议已经被上述用户新分配取代。

## 首轮选择：MS N4-4

三模型首轮统一在 **MS N4-4 / `datava-004`** 运行。远端 hostname 为 `datava270000004`，Tailscale 地址为 `192.0.2.1`，用户为 `sigma`。本机现有 SSH alias 已连续验证成功，保留严格主机密钥校验：

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 \
  -o StrictHostKeyChecking=yes -o LogLevel=ERROR datava-004
```

| 项目 | 实测结果 |
| --- | --- |
| GPU | 8 × NVIDIA H100 80GB HBM3 |
| GPU 索引 | 0–7 均无计算任务；利用率均为 0% |
| 显存 | 每卡总量 81,559 MiB，可用 81,076–81,080 MiB |
| `/data` | 3.9 TiB，总体使用率 99%，仅余 72 GiB；可写 |
| `/mnt/localssd` | 28 TiB，余 15 TiB；可写 |
| Python | `/path/to/user/miniconda3/envs/llm/bin/python`，3.11.15 |
| 项目、数据、checkpoint | 首轮使用 `/mnt/localssd/jev-qwen` 下独立子目录 |
| HF cache | `/mnt/localssd/jev-hf-cache` |

`/mnt/localssd` 是临时 NVMe 空间，重启或宿主迁移可能丢失。可复现代码保存在 Git，关键指标、小型 adapter、数据 manifest 及最终产物应同步到持久存储。三个 BF16 模型的权重合计约 79.4 GB，不能把仅余 72 GiB 的 `/data` 当作新下载默认位置。

启动前可重复运行：

```bash
ssh -o BatchMode=yes -o ConnectTimeout=10 \
  -o StrictHostKeyChecking=yes -o LogLevel=ERROR datava-004 \
  'nvidia-smi --query-gpu=index,name,memory.free,memory.used,utilization.gpu --format=csv,noheader; nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv,noheader'
```

## 已有 Python 环境与模型兼容性

`llm` 环境的已安装版本：

| 包 | 版本 |
| --- | --- |
| torch | 2.8.0+cu128 |
| transformers | 5.10.2 |
| peft | 0.19.1 |
| accelerate | 1.13.0 |
| datasets | 5.0.0 |
| flash-linear-attention | 0.5.0 |
| wandb | 0.27.1 |

已实际导入 `torch`、`transformers`、`peft`、`accelerate` 与 `Qwen3_5ForConditionalGeneration`。三模型的在线 `config.json` 都能用已安装的 `Qwen3_5Config.from_dict` 构造配置。完整权重加载、前向/反向以及 GPU kernel 正确性仍须由首轮 smoke 验证；包版本和配置导入不能代替训练验证。

Qwen3.8-27B 的公开配置仍使用 `model_type=qwen3_5`、`text_config.model_type=qwen3_5_text` 和 `architectures=[Qwen3_5ForConditionalGeneration]`。其配置记录的 `transformers_version` 为 `5.8.0.dev0`，本机已有 5.10.2 包含对应类，因此不需要仅因为名称含 3.8 就改写模型架构或升级共享环境。

建议显式选择环境和实验目录：

```bash
JEV_PYTHON=/path/to/user/miniconda3/envs/llm/bin/python
JEV_ROOT=/mnt/localssd/jev-qwen
export HF_HOME=/mnt/localssd/jev-hf-cache
export HF_HUB_CACHE="$HF_HOME"
export PYTHONDONTWRITEBYTECODE=1
export TOKENIZERS_PARALLELISM=false
```

## Hugging Face 访问与权重缓存

从 `datava-004` 直接 HTTPS 读取三个模型的 API metadata 和配置成功，对各模型第一份 safetensors 的 HTTP HEAD 请求均返回 200。该探测 shell 没有设置 `HF_ENDPOINT`、`HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 及小写同名变量，无需额外代理或凭据配置。

| 模型 | 本次解析的 revision | safetensors 分片 | 参数数 |
| --- | --- | --- | --- |
| Qwen/Qwen3.5-2B | `15852e8c16360a2fea060d615a32b45270f8a8fc` | 1 | 2,274,069,824 |
| Qwen/Qwen3.5-9B | `c202236235762e1c871ad0ccb60c8ee5ba337b9a` | 4 | 9,653,104,368 |
| Qwen/Qwen3.8-27B | `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` | 18 | 27,781,427,952 |

HEAD 检查验证下载端点可达，没有实际下载权重。应将 revision 固定到训练 manifest，避免后续 `main` 更新改变实验。

下载启动前，已检查 `/path/to/user/.cache/huggingface/hub`、`/data/models`、`/mnt/localssd/models`、`/data/zefan/models` 以及常见 HF cache 子路径，**没有发现这三个目标模型的完整缓存**。默认 HF cache 存在 `models--Qwen--Qwen3.5-9B` 候选目录，但没有 `config.json` 或可验证 snapshot，不能视为已下载。已有 Qwen3、Qwen3.5-4B 是其他模型，不能替代本次指定权重。这个结论只涵盖列出的已检查目录，不声称扫描过整机所有文件。

2026-09-19 21:23:06 UTC，已在独立实验目录后台启动三个固定 revision 的下载，按 2B → 9B → 27B 顺序运行，`snapshot_download(max_workers=4)`，总下载文件并发不超过 4。脚本只允许配置、tokenizer、vocab、merges、safetensors 和权重索引文件，不下载其他仓库内容。

- 脚本：`/mnt/localssd/jev-qwen/scripts/download_models.py`；本仓库副本为 `scripts/download_models.py`。
- PID：`2266314`；PID 文件：`/mnt/localssd/jev-qwen/logs/model-download.pid`。
- 日志：`/mnt/localssd/jev-qwen/logs/model-download.log`。
- 每模型状态和 snapshot 路径：`/mnt/localssd/jev-qwen/state/model-download-status.json`。
- 下载使用原 `llm` 环境、不分配 GPU、不修改其他任务；原子状态文件中的 `complete` 才表示对应 snapshot 已通过脚本的配置和权重存在性检查。

## 其他集群的当时状态

| 集群 | 接入和资源证据 | 首轮决策 |
| --- | --- | --- |
| MS 全部 15 节点 | 6/15 可达，48 张 GPU 中 40 张有计算任务，8 张空闲；唯一实测整机空闲是 N4-4 | 使用 N4-4；其余机器保留原任务 |
| CoreWeave RTX PRO 集群 | 63 节点 × 8 = 504 GPU，Slurm 分配 13 张；10 节点显示 IDLE | 暂不使用，见下面的物理利用率差异 |
| CoreWeave B200 | 1 节点 × 8 GPU，8 张均分配给 `7946 / dsv4-trace-fulltest` | 不抢占；`/mnt/data` 也仅余 80 GiB |

MS 不可达节点为 N8-1 至 N8-8 以及 N1-2；不可达不代表空闲。可达且占用的节点是 N4-1、N4-2、N4-3、N1-1、N1-3。

用户习惯称为 “A6000” 的 CoreWeave 集群目前实际硬件是 **NVIDIA RTX PRO 6000 Blackwell Server Edition，96 GB 级显存**，不是旧款 RTX A6000 48 GB。证据：Slurm GRES 为 `gpu:nvidia_rtx_pro_6000_blackwell_server_edition:8`；节点 `slurm-rtxp6000-137-055` 的 `nvidia-smi` 返回该完整名称和每卡 97,887 MiB 总显存。该节点虽然 Slurm 显示 IDLE、显存使用 0 MiB，但 GPU 利用率均为 100%；因此只能报告“Slurm 未分配”，不能据此保证物理空闲。没有停止或分析这项后台负载。

CoreWeave 已验证的标准入口是先 SSH 到 `jump@192.0.2.1`，再用跳板现有 SSH 身份嵌套连接 `jjian@sunk.6af0ac-darkproteome-{rtxpro,b200}.coreweave.app`。本机 `cwb200` 的 ProxyJump 方式返回 publickey 错误，因为目的端接受的是跳板现有身份。这不是 MS 首轮的依赖，不需要修改本机或远端凭据。

CoreWeave 的 `hpc-prod` PriorityTier=65500，高于 `hpc-high` 的 32768 和 `hpc-mid` 的 16384，可能在作业分配时抢占其他任务。首轮不用这些分区，也不为验证资源另行提交探测作业。
