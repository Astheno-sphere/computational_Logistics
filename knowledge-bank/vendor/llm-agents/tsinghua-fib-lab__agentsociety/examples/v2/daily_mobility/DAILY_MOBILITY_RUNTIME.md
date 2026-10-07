# Daily Mobility 运行时架构

本文档说明 **仿真真值**（agent 步进）与 **看板展示**（`live_data`）的分工，便于排查「问卷 / 曲线 / 位置」不一致。

## 一步仿真内的顺序（PersonAgent.step）

| 阶段 | 组件                                  | 作用                                                                |
| ---- | ------------------------------------- | ------------------------------------------------------------------- |
| 1    | `pre_step` hooks（按 skill 名字母序） | 见下表                                                              |
| 2    | 工具循环                              | LLM：observation → cognition → mobility ask_env …                   |
| 3    | `run_mobility_harness`                | 步后：observe → 对账 plan → 强制早餐/晚餐 pending、17:00 回家、记餐 |
| 4    | 持久化                                | session / replay                                                    |

### pre_step hooks（当前）

| 顺序 | Skill       | 脚本                       | 输出                                                                                                                                                      |
| ---- | ----------- | -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | `cognition` | `scripts/decay_needs.py`   | 更新 `state/needs.json`、追加 `needs_history.jsonl`；**仅当 `meal_state.restored_windows` 已有该餐且意图为 eating out 时** 在 decay 中二次 restore hunger |
| 2    | `rhythm`    | `scripts/update_rhythm.py` | `state/rhythm_state.json`、`state/rhythm_hints.txt`（软建议，不执行移动）                                                                                 |

问卷 slot 边界（society 层，非 agent step）：

- `normalize_questionnaire_intention` / `build_questionnaire_runtime_hints`
- 问卷提交后：`pending_meal_enforce`、`questionnaire_intention_overrides`
- `capture_mobility_snapshots` → artifact

## 三层约束（不要混为一谈）

| 层            | 代码入口                                                            | 改什么                                                       |
| ------------- | ------------------------------------------------------------------- | ------------------------------------------------------------ |
| **生理真值**  | `decay_needs.py`、`person._record_meal_state`                       | `needs.json`；hunger 下降必须记餐                            |
| **行为强制**  | `mobility_harness.py`、`person._enforce_pending_questionnaire_meal` | 移动、到店、禁止工位晚餐                                     |
| **标签/展示** | `daily_mobility_intentions.py`、`live_data.py`                      | 问卷 normalize、看板通勤/每餐一格 eating out、曲线 meal 台阶 |

## 关键文件

| 文件                                           | 用途                                       |
| ---------------------------------------------- | ------------------------------------------ |
| `state/meal_state.json`                        | `restored_windows`、`pending_meal_enforce` |
| `state/questionnaire_intention_overrides.json` | 记餐后覆盖问卷展示                         |
| `run_dir/env_tool_calls.jsonl`                 | 环境调用追踪                               |
| `artifacts/questionnaire_step_*.json`          | 每 slot 问卷 + mobility_snapshots          |

## 已知不足（待完善）

1. **文档与常量**：部分 SKILL 仍写 18:00 回家；代码为 `WORK_COMMUTE_END_HOUR=17`（已在对照表中修正 mobility SKILL）。
2. **问卷 raw vs 展示**：artifact 原文可能仍为 work；分析以 `meal_state` + 看板修正为准。
3. **午餐 dedupe**：Agent2 仍可能出现午餐窗 2–3 格 eating out；`dedupe_eating_out_intentions` 可再收紧。
4. **路由依赖**：routing/embedding 失败时 pending 无法到店，hunger 顶满（eo19 类）。
5. **出图中文**：matplotlib 未配置 CJK 字体。
6. **pre_step 顺序**：目前依赖 skill 名字母序（cognition → rhythm）；若新增 hook 需显式约定顺序。

## 相关 SKILL 文档

- `agent/skills/cognition/SKILL.md` — needs 衰减与 restore 原则
- `agent/skills/rhythm/SKILL.md` — 软节律分数
- `contrib/env/mobility_space/agent_skills/mobility/SKILL.md` — 每 tick 移动计划
- `agent/skills/cognition/references/daily_mobility_intentions.md` — 问卷标签
- `agent/skills/cognition/references/daily_mobility_runtime.md` — 本架构的 skill 侧摘要
