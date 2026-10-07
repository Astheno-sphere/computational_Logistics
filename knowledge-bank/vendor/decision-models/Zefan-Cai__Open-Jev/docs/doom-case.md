# Doom case：真实轨迹上的 typed decisions

这是 ViZDoom 内置 `basic` 靶场上的小规模行为模仿实验。数据由真实 Doom 引擎运行产生，输入是结构化文本状态，输出是 Choice、Noul 和 Score。它不是 TypeSafe Jev 私有模型、RLCD 训练方法或演示视频的复现，也不是视觉 Doom benchmark。

## 已验证的环境

MS N4-4 / `datava-004` 上已创建独立环境 `/mnt/localssd/jev-qwen/doom-venv`，通过 `--system-site-packages` 继承已有 `llm` 环境；`vizdoom==1.2.4` 及新增依赖只安装到这个新 venv。没有修改共享 `llm` 环境。

短 CPU/headless 探测已成功：`basic.wad/map01` 提供真实 Cacodemon、DoomPlayer labels；可以读取 health、AMMO2、位置、角度、速度和可见敌人的世界坐标。默认开局 health=100、ammo=50，敌人的横向位置随 engine seed 变化。渲染窗口和声音关闭，采集不分配 GPU、不操作已有训练进程。

官方来源：

- [ViZDoom 1.2.4 basic.cfg](https://github.com/Farama-Foundation/ViZDoom/blob/1.2.4/scenarios/basic.cfg)
- [内置场景说明](https://vizdoom.farama.org/environments/default/)
- [ViZDoom 许可说明](https://github.com/Farama-Foundation/ViZDoom/tree/1.2.4#license)

使用 wheel 自带 Freedoom 和 basic 场景，不下载商业 Doom WAD。manifest 保存 ViZDoom 版本、basic.cfg、basic.wad 和 freedoom2.wad 的 SHA-256。输出仅含生成的数值/文本轨迹，以 CC0-1.0 标记；不再分发 WAD、纹理、图像或引擎。ViZDoom 原创代码为 MIT，底层 ZDoom 代码有混合许可，不能把整套引擎都描述为 MIT。

## State 和三种任务

每个状态都来自 `game.get_state()`，包含：

- health、ammo。
- player 世界坐标和朝向。
- 实测前向/横向速度，单位为 Doom units/tic。
- 可见 Cacodemon 数量、最近可见目标的相对方位和距离。
- 当前 engine tic、这次控制动作会保持多少 tics。

`labels_buffer_enabled` 和 `objects_info_enabled` 启用；模型输入只使用可见 labels 中的 Cacodemon，不使用 `state.objects` 提供的不可见对象，不保存或提供像素。相对方位正角表示左侧。engine seed、episode ID、split、teacher 标签、reward 和下一状态全部留在模型输入之外。

| 任务 | 定义 | 标签依据 |
| --- | --- | --- |
| Choice | 横移左、横移右、停止横移 | 用目标横向偏差和实测横向速度预测偏差，追踪最近可见目标 |
| Noul | 当前是否按 ATTACK | 有可见目标、health>0、ammo>0，且目标绝对方位不超过 3° |
| Score | 五档当前射击对准程度 | 下述显式、有序启发式，不是预计奖励或击杀概率 |

Choice 与 Noul 可同时执行，组成 basic 场景实际的 `[MOVE_LEFT, MOVE_RIGHT, ATTACK]` 三个 bool 按钮。没有互斥地把“移动”和“射击”合成一个动作类别。

追踪脚本的横向偏差为 `distance × sin(bearing)`，减去 `lateral_velocity × 8 tics` 得到前视偏差。大于 10 units 横移左，小于 -10 units 横移右，其余停止横移。无法射击或没有目标时停止横移并不攻击。这是一个可解释的弱 expert，未搜索最优策略。

Score 的五个等级在每条输入中均提供完整、自包含描述：

| 等级 | 条件 |
| --- | --- |
| 0 | 无目标、无弹药、玩家死亡，或绝对方位大于 22° |
| 1 | 可射击目标存在，绝对方位 `(12°, 22°]` |
| 2 | 可射击目标存在，绝对方位 `(6°, 12°]` |
| 3 | 可射击目标存在，绝对方位 `(3°, 6°]` |
| 4 | 可射击目标存在，绝对方位 `[0°, 3°]` |

basic 是被动靶场，health/威胁信号变化有限，所以没有把这个 Score 称为“真实威胁”或动作 Q 值。Choice/Noul 标签来自脚本，Score 来自规则，均显式标记 `weak_script_expert_v1` 和 `expert_optimality_claim=false`。训练得到的是对脚本的模仿；需另外测量真实游戏 reward，才能讨论策略效果。

## 轨迹、拆分和复验

默认 400 个 ID episodes 加 80 个 OOD episodes，每 episode 最多 300 engine tics。ID 动作保持 4 tics、doom_skill=5；OOD 使用不重叠的 engine seed 区间、保持 8 tics、doom_skill=1。两组都使用 basic/map01，因此 **OOD 只是 seed 和控制/难度设置的变化，不是新地图泛化**；basic 中难度变化可能影响有限，主要可见变化来自控制时长。

ID 按完整 episode 的 hash 分为 train、calibration、validation、test；同一轨迹的三个任务始终在同一组。OOD seeds 从基础 seed 加 1,000,000 开始；不从 ID 轨迹抽取 OOD 状态。相同物理 observation 若重复出现，训练数据全局去重，不把 seed 或虚构 ID 塞进 state 来掩盖跨 split 重复。

`trajectories/episodes.jsonl` 保存每一步的完整结构化 state、state hash、expert 输出、实际按钮、真实 reward、下一状态 hash、终止标志和 episode 总 reward。轨迹保留所有状态，去重只作用于派生训练行。`manifest.json` 保存轨迹 checksum、每种动作/等级的计数、各 split episode 数和观测数；某等级若没出现，会如实计为 0，不补造状态。

`replay` 重新启动相同版本和资产的引擎、设置同一 episode seed，回放完整按钮序列，逐步比较当前/下一状态 hash、expert、reward、终止标志和总 reward。不是只对保存的 JSON 重算规则。默认复验 10 个 episodes，优先覆盖 train/calibration/validation/test/OOD，然后补足数量。`replay-report.json` 记录通过的 episode；若版本、资产、数据或轨迹不匹配则报错。

## 运行

### Linux checkout 安装与采集

使用 Linux 和 Python 3.11 或 3.12；固定的 `vizdoom==1.2.4` 要求 Python `<3.13`。
下面使用 Python 3.12，也可将 `python3.12` 替换为 `python3.11`。在独立 venv 中安装
`doom` 可选依赖即可进行 CPU/headless 采集和回放。

```bash
git clone https://github.com/Zefan-Cai/Open-Jev-Dev.git
cd Open-Jev-Dev
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[doom]'

python -m jev.case_doom build \
  --output-dir data/doom-basic-v1 --episodes 400 --ood-episodes 80 --seed 190919
python -m jev.case_doom replay data/doom-basic-v1 --limit 10
python -m jev.data validate data/doom-basic-v1
```

以上命令的参数已与 CLI 核对；引擎实测仍对应本文记录的 MS 环境，尚未完成新的
Linux 干净环境安装验证，详见[运行环境记录](resources.md)。

### 历史 MS 运行命令

以下保留 2026-09-19 在 MS N4-4 上使用已 commit/push 后部署代码的命令；路径对应当时的环境。

```bash
cd /mnt/localssd/jev-qwen/repo
JEV_DOOM_PY=/mnt/localssd/jev-qwen/doom-venv/bin/python
JEV_DOOM_DATA=/mnt/localssd/jev-qwen/repo/data/doom-basic-v1
PYTHONDONTWRITEBYTECODE=1 "$JEV_DOOM_PY" -m jev.case_doom build \
  --output-dir "$JEV_DOOM_DATA" --episodes 400 --ood-episodes 80 --seed 190919
PYTHONDONTWRITEBYTECODE=1 "$JEV_DOOM_PY" -m jev.case_doom replay \
  "$JEV_DOOM_DATA" --limit 10
"$JEV_DOOM_PY" -m jev.data validate "$JEV_DOOM_DATA"
```

测试：`python -m unittest discover -s tests -p test_case_doom.py -v`。普通环境运行方向、动量、等级边界、episode 划分和三任务 schema 测试；安装 ViZDoom 的独立环境还运行真实 engine rollout/replay、数据篡改检测，以及 ID/OOD 小数据集完整验证。

## 首轮实测结果

2026-09-19 已从 push 后并在 MS 核验的 commit `3c2f6135ef3f32ef871d8e1bd126bc7c2701a915` 执行正式生成，输出位于 `/mnt/localssd/jev-qwen/repo/data/doom-basic-v1`。

- 400 个 ID 加 80 个 OOD episodes，总计 **3,031 个真实状态、9,093 条 typed records**；没有重复状态需要删除。
- Choice、Noul、Score 各 3,031 条；全部记录通过 `jev.data validate`。
- 独立环境完整 **7/7 测试通过**，包括真实 engine 测试。
- 正式数据中抽取覆盖全部五个 splits 的 **10 个 episodes、67 个动作步**回放，state/next-state hashes、expert 按钮、逐步 reward、终止标志、总 reward 全部匹配。报告为 `replay-report.json`。

| Split | Episodes | Typed records |
| --- | ---: | ---: |
| train | 309 | 6,354 |
| calibration | 31 | 654 |
| validation | 18 | 402 |
| test | 42 | 858 |
| ood | 80 | 825 |

| 标签统计 | 实际状态数 |
| --- | ---: |
| 横移左 / 横移右 / 停止横移 | 935 / 1,012 / 1,084 |
| attack=yes / no | 880 / 2,151 |
| Score 0 / 1 / 2 / 3 / 4 | 175 / 847 / 627 / 502 / 880 |

脚本 expert 的真实平均 episode reward 为 **75.45**，最小 55，最大 95。这是当前 basic 场景和脚本的采集基线，**不是训练模型的成绩**，也没有证明策略最优。原始轨迹 SHA-256 为 `272e9defc93bb8ac0bb7f778a129bf221aa8fa3790352f50a308eba7bfd32ab4`；各 split 文件和引擎资产的 checksum 见 `manifest.json`。

`doom-venv` 的 `include-system-site-packages=true` 已核验，`torch 2.8.0+cu128` 与继承自 `llm` 的 `fla 0.5.0` 均实际 import 成功。Doom 采集自身不使用这些 GPU 库；后续训练安装额外包时仍应只写独立 venv。
