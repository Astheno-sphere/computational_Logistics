# Daily Mobility Example

本目录整理自 `agentsociety_data/daily_mobility_experiment`，只保留可协作的模拟配置生成代码、评估代码和小型 groundtruth 数据。运行输出、SQLite、日志、agent workspace 都写入 `tmp/`，默认不加入 git。

## 目录

| 路径 | 用途 | 是否适合提交 |
|---|---|---|
| `init/config_params.py` | 生成 `init_config.json` 和 `steps.yaml` | 是 |
| `run_all.py` | 一站式生成配置、world description 检查、仿真、指标计算 | 是 |
| `tools/eval_metrics.py` | 根据 `mobility_metrics_export.json` 和问卷 artifacts 计算指标 | 是 |
| `data/groundtruth/` | DailyMobility 指标真值小数据 | 是 |
| `tmp/init/` | 生成的配置文件 | 否 |
| `tmp/run/` | CLI 输出、日志、数据库、agent workspace | 否 |

## 生成配置

```bash
DAILY_MOBILITY_PRESET=smoke \
DAILY_MOBILITY_NUM_AGENTS=2 \
uv run python examples/v2/daily_mobility/init/config_params.py
```

生成文件：

- `examples/v2/daily_mobility/tmp/init/init_config.json`
- `examples/v2/daily_mobility/tmp/init/steps.yaml`

生成的 agent 类型为 `PersonAgent`，并使用 `max_react_turns`。
环境模块为 `MobilitySpace`。

## 一站式脚本

只生成配置并测试 world description：

```bash
uv run python examples/v2/daily_mobility/run_all.py \
  --stage world-description \
  --preset smoke \
  --num-agents 2
```

本地没有可用 LLM 时，可以只验证环境模块加载和 world description 输入摘要：

```bash
AGENTSOCIETY_LLM_API_KEY=dummy \
AGENTSOCIETY_LLM_API_BASE=http://localhost/v1 \
uv run python examples/v2/daily_mobility/run_all.py \
  --stage world-description \
  --preset smoke \
  --num-agents 2 \
  --world-description-dry-run
```

完整 smoke 流程：

```bash
uv run python examples/v2/daily_mobility/run_all.py \
  --stage all \
  --preset smoke \
  --num-agents 2
```

## 运行仿真

```bash
uv run python -m agentsociety2.society.cli \
  --config examples/v2/daily_mobility/tmp/init/init_config.json \
  --steps examples/v2/daily_mobility/tmp/init/steps.yaml \
  --run-dir examples/v2/daily_mobility/tmp/run \
  --experiment-id daily_mobility \
  --log-file examples/v2/daily_mobility/tmp/run/output.log
```

地图文件默认从 `DAILY_MOBILITY_MAP_PATH`、`AGENTSOCIETY_HOME_DIR` 或仓库根目录的 `agentsociety_data/` 查找。`.pb` 地图文件不纳入 git。

## 计算指标

```bash
uv run python examples/v2/daily_mobility/tools/eval_metrics.py
```

默认读取：

- run 目录：`examples/v2/daily_mobility/tmp/run`
- groundtruth：`examples/v2/daily_mobility/data/groundtruth`

输出：

- `examples/v2/daily_mobility/tmp/run/scores.json`
