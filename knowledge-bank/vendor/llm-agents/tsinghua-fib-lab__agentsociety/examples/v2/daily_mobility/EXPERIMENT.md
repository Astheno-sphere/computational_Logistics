# DailyMobility Benchmark Example

本实验使用 `PersonAgent` 和 `MobilitySpace` 在北京路网上运行一日移动模拟，并用 DailyMobility groundtruth 计算 Jensen-Shannon 相关指标。

## 1. 生成配置

在仓库根目录运行：

```bash
DAILY_MOBILITY_PRESET=smoke \
DAILY_MOBILITY_NUM_AGENTS=2 \
uv run python examples/v2/daily_mobility/init/config_params.py
```

正式 benchmark 可使用：

```bash
DAILY_MOBILITY_PRESET=benchmark \
DAILY_MOBILITY_NUM_AGENTS=100 \
uv run python examples/v2/daily_mobility/init/config_params.py
```

生成文件位于：

- `examples/v2/daily_mobility/tmp/init/init_config.json`
- `examples/v2/daily_mobility/tmp/init/steps.yaml`

## 2. 运行仿真

```bash
uv run python -m agentsociety2.society.cli \
  --config examples/v2/daily_mobility/tmp/init/init_config.json \
  --steps examples/v2/daily_mobility/tmp/init/steps.yaml \
  --run-dir examples/v2/daily_mobility/tmp/run \
  --experiment-id daily_mobility \
  --log-file examples/v2/daily_mobility/tmp/run/output.log
```

运行产物位于 `examples/v2/daily_mobility/tmp/run/`。该目录包含 SQLite、日志、agent workspace、问卷 artifacts 和 mobility export，默认不加入 git。

## 3. 后处理评测

```bash
uv run python examples/v2/daily_mobility/tools/eval_metrics.py
```

脚本默认读取：

- `examples/v2/daily_mobility/tmp/run/mobility_metrics_export.json`
- `examples/v2/daily_mobility/tmp/run/artifacts/questionnaire*.json`
- `examples/v2/daily_mobility/data/groundtruth/*.npy`

结果写入：

- `examples/v2/daily_mobility/tmp/run/scores.json`

## 4. 本地依赖文件

地图和 profiles 属于本地大文件，不进入 git：

| 文件 | 查找方式 |
|---|---|
| 地图 `.pb` | `DAILY_MOBILITY_MAP_PATH`、`AGENTSOCIETY_HOME_DIR`、`agentsociety_data/` |
| `profiles.json` | `DAILY_MOBILITY_PROFILES_PATH`、仓库根目录、`packages/agentsociety2/` |

## 5. 变化

- agent 类型从 `PersonAgent` 改为 `PersonAgent`。
- agent 参数从 `max_tool_rounds` 改为 `max_react_turns`。
- 生成配置和运行产物统一放入 `tmp/`。
- 可协作的代码和 groundtruth 数据保留在 `examples/v2/daily_mobility/`。
