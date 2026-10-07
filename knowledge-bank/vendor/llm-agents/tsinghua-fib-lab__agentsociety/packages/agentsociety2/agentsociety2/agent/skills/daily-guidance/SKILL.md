---
name: daily-guidance
description: 强制使用：凡是时间尺度在小时及以下的日常行为模拟，必须使用本 Skill 生成、评估、执行和修正每日 Story。
script: scripts/daily_guidance.py
hooks:
  pre_step: scripts/daily_guidance.py
---

# Daily Guidance

Daily Guidance 让 agent 先形成一天的完整 Story，再按 Story 指导每个仿真步的行为。
**所有结构化操作都通过 `scripts/daily_guidance.py` 的 CLI 命令完成——你提交 JSON 内容，
脚本负责校验、序列化 YAML、以及从仿真时钟推导执行状态。**

每天一个文件：`state/daily_guidance/YYYY-MM-DD/story.yaml`（由脚本生成和维护）。

## 核心原则

1. **用 `plan --json` 提交一天的安排。** 提交 JSON 对象，脚本校验后写入 story.yaml。
2. **执行状态由时钟推导。** `completed_segments` / `current_segment_id` 是
   `(segments, 当前仿真时间)` 的函数，由脚本在读取时计算。时间到了自然完成。
3. **pre_step hook 每步输出当前 segment。** 每个 step 开始，hook 会注入 `active_segment`
   （含 `activity` 和 `location_policy`）。按此移动和回答问卷。

## 每步流程

每个 step 开始，pre_step hook 自动输出当前状态。两种情况：

**情况 A：还没有有效 Story（`ok: false`）**

hook 输出会包含 `next` 指引。立即提交一天的 Story：

```bash
python scripts/daily_guidance.py plan --date YYYY-MM-DD --json '<JSON对象>'
```

**情况 B：已有有效 Story（`ok: true`）**

hook 输出包含 `active_segment` 和 `guidance`，例如：

```yaml
active_segment:
  id: sleep_night
  activity: sleep
  location_policy: home_aoi
  start: "00:00"
  end: "07:00"
guidance: Your intended activity now is 'sleep' at location policy 'home_aoi'. ...
```

直接按 `active_segment.activity` 和 `location_policy` 行动并回答问卷。回答意图问卷时，以 `active_segment.activity` 为当前意图。

## CLI 命令

所有命令通过 `execute_skill_script` 调用，统一返回 `{ok, ...}` YAML 结果块。

| 命令 | 用途 |
| --- | --- |
| `plan --date D --json '<obj>'` | 提交一天的完整 Story（JSON）。校验通过才写文件，否则返回逐字段修复提示。 |
| `current --date D` | 返回当前时刻所处的 segment 摘要。 |
| `show --date D [--format summary\|full]` | 执行状态快照（completed/current 由时钟推导）。 |
| `record --date D --activity A --location L [--note N]` | 记录本步实际发生的活动到 `actual_timeline`。 |
| `deviate --date D --type T --reason R` | 记录偏差到 `change_log`。 |
| `revise --date D --from SEG_ID --json '<list>'` | 用新的尾段替换 `SEG_ID` 及其之后的所有 segment。 |
| `check --date D` | 校验现有 story.yaml。 |

## plan 的 JSON 格式

`--json` 接收一个对象，包含 `story_id`、`date`、`segments` 三个字段。`self_check` 可选。

```json
{
  "story_id": "agent_0007:2018-06-13",
  "date": "2018-06-13",
  "segments": [
    {
      "id": "sleep_night",
      "start": "00:00",
      "end": "07:00",
      "activity": "sleep",
      "location_policy": "home_aoi",
      "maslow_reason": {
        "need": "physiological.rest",
        "reason": "night sleep keeps the day physically plausible",
        "risk": "starting the day without rest",
        "required": "required"
      },
      "tpb_reason": {
        "want": {"reason": "sleep supports recovery", "status": "supported"},
        "norm": {"reason": "sleeping at night is normal", "status": "supported"},
        "can": {"reason": "the agent is at home", "status": "supported"},
        "proof": "night time at home supports sleeping",
        "choice": "commit"
      }
    }
  ]
}
```

## 生成规则

- 先读 `AGENT.json`，确认当前时间、职业、家庭/工作地点、角色义务。
- 如果 profile 表示有工作/学习义务，必须安排合理的 work/study segment，除非 `tpb_reason.can.status` 给出执行条件不足。
- 必须覆盖：睡眠/休息、进食、主要角色义务、安全返回或夜间栖身。
- 工作日应包含通勤、用餐、傍晚回家、休闲等真实节律，各 segment 均匀分布在全天。
- 每个 segment 必须有 `id/start/end/activity/location_policy/maslow_reason/tpb_reason`。
- `start`/`end` 用 `HH:MM`，按顺序**连续衔接**（前一段的 end 等于后一段的 start）；末尾可用 `24:00`。时间必须覆盖一整天 `00:00`–`24:00`。

## location_policy 取值

| 值 | 含义 |
| --- | --- |
| `home_aoi` | 在家 |
| `work_aoi` | 在工作地 |
| `near_home_aoi` | 家附近（搜索 POI） |
| `near_work_aoi` | 工作地附近（搜索 POI） |
| `transit` | 通勤途中 |
| `city` | 城市范围内自由活动 |

## Maslow Reason

用马斯洛需求层次解释一天安排是否合理。`maslow_reason.need` 是字符串，可用常见值或按场景扩展。

| 值 | 含义 |
| --- | --- |
| `physiological.food` | 进食、补充能量、维持餐食节律 |
| `physiological.rest` | 睡眠、休息、恢复体力 |
| `safety.home_shelter` | 稳定居所、夜间栖身、返回地点 |
| `safety.income_stability` | 通过工作、学习或职责维持稳定生活 |
| `belonging.social_connection` | 家庭、朋友、同事、社区连接 |
| `esteem.role_obligation` | 职业、学习、家庭或社会职责 |
| `esteem.competence` | 完成任务、能力感、认可 |
| `self_actualization.growth` | 学习、创造、探索 |
| `recovery.leisure` | 娱乐、散步、轻休闲 |

`maslow_reason.required` 使用 `required`、`soft_required` 或 `optional`。

## TPB Reason

计划行为理论（TPB）认为行为意图由三类因素形成：

- `want`：为什么想做或接受该行为。
- `norm`：为什么符合角色、社会规范或他人期待。
- `can`：为什么现在有时间、地点、交通、资源等执行条件。

每个字段含 `reason`（短句）和 `status`（`supported`/`weak`/`missing`/`contradicted`）。
`proof` 写一个短句说明依据。`choice` 用 `commit`/`revise`/`delay`/`skip`/`observe`。
当 `can.status: contradicted` 时，`choice` 不能用 `commit`。

## 偏差处理

现实与计划不符时，用 CLI 命令记录：

- `record --activity ... --location ...`：记录本步实际活动到 `actual_timeline`。
- `deviate --type record_only --reason ...`：轻微偏离，只追加 change_log。
- `deviate --type local_patch --reason ...`：需要调整当前或相邻 segment（随后用 `revise`）。
- `revise --from SEG_ID --json '<新尾段>'`：重写当天剩余 segments。
- `deviate --type carryover --reason ...`：当天无法补偿，留给第二天参考。
