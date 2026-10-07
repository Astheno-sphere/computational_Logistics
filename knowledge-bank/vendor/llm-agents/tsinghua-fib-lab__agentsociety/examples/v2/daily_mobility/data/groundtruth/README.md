# Daily Mobility Ground Truth（北京用户）

## 描述

本数据集来自 **AgentSociety DailyMobility** 基准配套的真值（ground truth），用于评估智能体生成的日常出行行为是否接近真实分布。数据基于北京用户样本，包含 **100 名用户** 的下列指标：

- **回转半径（gyration radius）**：个体活动空间的典型尺度（与基准评估中一致，单位为米量级浮点值）。
- **每日访问地点数（daily location numbers）**：每人一天内访问的唯一 AOI 数量（每用户一个标量）。
- **意图序列（intention sequences）**：按 30 分钟时间片编码的出行意图类别索引（二维表：用户 × 时间片，形状 100 × 48）。
- **意图比例（intention proportions）**：各意图类别在一天内占比（每用户一行，7 维概率向量）。

## 数据格式

目录 `data/` 中包含以下文件：

| 文件 | 格式 | 说明 |
|------|------|------|
| `gyration_radius.csv` / `gyration_radius.npy` | CSV：单列浮点；NPY：一维数组 | 100 个标量，对应 100 名用户 |
| `daily_location_numbers.csv` / `daily_location_numbers.npy` | 同上 | 100 个标量 |
| `daily_intentions_2d.csv` / `daily_intentions_2d.npy` | CSV：无表头逗号分隔整数；NPY：二维整型数组 | 形状 **(100, 48)**，取值 **1–7**（见下表） |
| `intention_proportions_2d.csv` / `intention_proportions_2d.npy` | CSV：无表头 7 列浮点；NPY：二维浮点数组 | 形状 **(100, 7)** |
| `daily_intentions.json` | JSON 对象 | **另一个独立样本**（不同日期/不同用户）。键为用户 id 字符串（`"1"` … `"100"`），值为 48 个时间片的意图 **英文标签** 序列 |
| `intention_proportions.json` | JSON 对象 | 同上，键为用户 id，值为长度 7 的浮点列表 |

**重要**：`daily_intentions.json` 与 `daily_intentions_2d.npy` 是**两个独立的数据样本**，不是同一种数据的不同格式。评估时请以 `.npy` 文件为准（与官方基准对齐）。

### 意图类别索引（与 `daily_intentions_2d.csv` / `.npy` 中 1–7 对应）

| 索引 | 标签 |
|:----:|------|
| 1 | sleep |
| 2 | home activity |
| 3 | other |
| 4 | work |
| 5 | shopping |
| 6 | eating out |
| 7 | leisure and entertainment |

### 数据特征概要

以下为 `.npy` 文件中 100 名用户的统计概要：

| 指标 | 均值 | 中位数 | 说明 |
|------|------|--------|------|
| 回转半径 | 3,477m | 2,859m | 右偏分布，范围 0 ~ 12,435m |
| 每日地点数 | 2.55 | 2.4 | 范围 1 ~ 6 |
| sleep 占比 | 40.4% | — | 集中在 00:00-08:00 |
| work 占比 | 32.3% | — | 92/100 用户有工作，工作者平均 ~8.4h |
| home activity 占比 | 19.5% | — | 过渡时段填充 |
| other 占比 | 5.3% | — | — |
| leisure 占比 | 1.6% | — | 仅少数用户有 |
| eating out 占比 | 0.6% | — | 11/100 用户有 |
| shopping 占比 | 0.2% | — | 6/100 用户有 |

**数据性质**：这是一个**工作日**的数据（92% 的用户有工作行为）。

## 与基准评估对齐

官方评估代码（`agentsociety_benchmark.benchmarks.DailyMobility.evaluation`）直接加载 `.npy` 文件。本目录中的 `.npy` 文件可直接用于评估。

若需从 CSV 重新生成 `.npy`：

```python
import numpy as np

base = "."  # 或指向本数据集 data/ 的绝对路径
np.save(f"{base}/gyration_radius.npy", np.loadtxt(f"{base}/gyration_radius.csv"))
np.save(f"{base}/daily_location_numbers.npy", np.loadtxt(f"{base}/daily_location_numbers.csv"))
np.save(f"{base}/daily_intentions_2d.npy", np.loadtxt(f"{base}/daily_intentions_2d.csv", delimiter=",", dtype=np.int64))
np.save(f"{base}/intention_proportions_2d.npy", np.loadtxt(f"{base}/intention_proportions_2d.csv", delimiter=","))
```

## 来源

原始文件来自 HuggingFace 数据集：`tsinghua-fib-lab/daily-mobility-generation-benchmark`，路径为 `datasets/DailyMobility/groundtruth/`。

## Usage

在 AgentSociety2 中安装本数据集后，可在实验或分析中读取 `data/` 下文件；结合 **DailyMobility** 基准文档使用，用于对比模型输出与真值分布（Jensen–Shannon 散度指标）。