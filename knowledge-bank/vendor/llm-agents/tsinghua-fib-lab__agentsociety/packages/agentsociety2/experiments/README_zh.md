# 实验脚本

本目录包含 AgentSociety 2 仿真实验的入口脚本。

## 目录结构

```
experiments/
├── env_main.py                      # 基础环境演示
├── env_main_commons_tragedy_v2.py   # 公地悲剧博弈
├── env_main_prisoners_dilemma_v2.py # 囚徒困境博弈
├── env_main_public_goods_v2.py      # 公共物品博弈
├── env_main_trust_game_v2.py        # 信任博弈
├── env_main_volunteer_dilemma_v2.py # 志愿者困境博弈
├── env_main_self_reference_effect.py # 自我参照效应实验
├── env_main_self_enhancement.py     # 自我增强实验
├── env_main_endowment_effect.py     # 禀赋效应实验
├── main.py                          # 多模块基准测试
├── main_lab.py                      # 实验室实验
├── disaster_mobility.py             # 灾害应急出行模拟
└── env_benchmark.py                 # 环境基准测试
```

## 运行实验

每个脚本可直接用 Python 运行：

```bash
# 运行博弈论实验
cd packages/agentsociety2
uv run python experiments/env_main_prisoners_dilemma_v2.py

# 运行多模块基准测试
uv run python experiments/main.py
```

## 配置要求

大多数实验需要：
1. 在环境变量或 `.env` 文件中配置 LLM API 凭据
2. 详见项目根目录的 `.env.example`

---

> 英文版：参见 [README.md](./README.md)