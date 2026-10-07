# Experiments

<p align="center">
  <a href="./README.md">English</a> · <a href="./README_zh.md">中文</a>
</p>

This directory contains experiment scripts and entry points for running simulations with AgentSociety 2.

## Directory Structure

```
experiments/
├── env_main.py                      # Basic environment demo
├── env_main_commons_tragedy_v2.py   # Commons Tragedy game
├── env_main_prisoners_dilemma_v2.py # Prisoner's Dilemma game
├── env_main_public_goods_v2.py      # Public Goods game
├── env_main_trust_game_v2.py        # Trust Game
├── env_main_volunteer_dilemma_v2.py # Volunteer's Dilemma game
├── env_main_self_reference_effect.py # Self Reference Effect experiment
├── env_main_self_enhancement.py     # Self Enhancement experiment
├── env_main_endowment_effect.py     # Endowment Effect experiment
├── main.py                          # Multi-module benchmark
├── main_lab.py                      # Lab experiments
├── disaster_mobility.py             # Disaster mobility simulation
└── env_benchmark.py                 # Environment benchmark
```

## Running Experiments

Each script can be run directly with Python:

```bash
# Run a game theory experiment
cd packages/agentsociety2
uv run python experiments/env_main_prisoners_dilemma_v2.py

# Run the multi-module benchmark
uv run python experiments/main.py
```

## Configuration

Most experiments require:
1. LLM API credentials set in environment variables or `.env` file
2. See `.env.example` in the project root for required configuration
