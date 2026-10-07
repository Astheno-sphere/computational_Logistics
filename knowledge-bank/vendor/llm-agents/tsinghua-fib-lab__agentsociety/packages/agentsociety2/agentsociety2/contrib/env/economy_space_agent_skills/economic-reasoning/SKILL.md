---
name: economic-reasoning
description: Economic decision-making for agents in EconomySpace. Activate when the agent observes currency, prices, income, tax, or trading opportunities to make informed financial decisions.
script: scripts/economic_reasoning.py
requires:
  - observation
---

# Economic Reasoning

Provides economic reasoning capabilities when the agent operates in an EconomySpace environment.

## What It Does

1. Analyzes the agent's financial state (currency, income, consumption)
2. Evaluates trading and employment opportunities based on cost-benefit analysis
3. Records economic decisions and reasoning as cognition memory

## When To Activate

- Observation contains financial information (currency, prices, income)
- Agent needs to make economic decisions (buy, sell, work, invest)
- Tax or policy changes affect the agent's financial situation

## Data Available via Environment

The EconomySpace environment provides these tools:
- `get_person(agent_id)` — current financial state
- `get_all_products()` — available products and prices
- `buy_product(agent_id, product_name, quantity)` — purchase
- `find_job(agent_id)` — find employment
