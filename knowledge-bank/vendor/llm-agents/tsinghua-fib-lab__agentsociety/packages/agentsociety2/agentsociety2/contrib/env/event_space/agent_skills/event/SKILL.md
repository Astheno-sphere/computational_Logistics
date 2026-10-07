---
name: event
description: 事件管理：为 agent 启动、查询和停止行为事件。必须通过 ask_env 调用 EventSpace 工具。
---

# Event

EventSpace 管理每个 agent 的行为事件。每个 agent 同一时间最多有一个进行中的事件。**所有操作必须通过 `ask_env` 自然语言指令执行**。

## 环境概念

### 事件模型

每个事件包含：
- `event_type`：事件类型
- `event_name`：事件名称/描述（自由文本）
- `expected_duration_seconds`：预计耗时（秒）
- `start_time`：开始时间
- `expected_end_time`：预计结束时间

事件会随时间自动推进。`get_current_event` 返回 `elapsed_seconds`（已用时间）、`remaining_seconds`（剩余时间）、`progress_percentage`（进度百分比）。

### 内置事件类型

| 类型 | 含义 |
|------|------|
| `sleep` | 睡眠/休息 |
| `work` | 工作 |
| `eating out` | 外出用餐 |
| `home activity` | 居家活动 |
| `shopping` | 购物 |
| `leisure and entertainment` | 休闲娱乐 |
| `other` | 其他（不属于以上类别的活动） |

`event_name` 是自由文本，用于描述具体活动内容，agent 可根据实际需要自行命名。

## 可用工具

所有操作通过 `ask_env` 调用：

```
ask_env(instruction="<自然语言指令>", ctx={"id": <your_id>})
```

### get_current_event（只读，observe）

查询当前进行中的事件。返回事件类型、名称、状态、已用时间、剩余时间、进度百分比。无事件时返回 `None`。

### start_event（非只读）

启动一个新事件。同一 agent 同时只能有一个事件，启动前需先查询当前事件。
如果当前事件的 `event_type` 已经等于你当前要执行的类型，且事件仍在进行中，
不要调用 `stop_event`，也不要再次调用 `start_event`；这代表当前活动已在持续，只需保持当前状态或记录本步实际活动。

参数：
- `person_id`：person ID
- `event_type`：事件类型
- `event_name`：事件名称（自由文本，如 "lunch at Italian restaurant"、"afternoon nap"）
- `expected_duration_seconds`：预计耗时（秒）

只使用秒数，不使用 `duration_min`、`duration_minutes`、`duration`、`location_id`、`location_policy`、`home_aoi` 这类参数名。
参考值：30min=1800，45min=2700，1h=3600，4h=14400，7h=25200，8h=28800。

### stop_event（非只读）

停止当前事件。参数：`person_id`、`status`（`"completed"` 正常完成 或 `"cancelled"` 中断/取消）。

## 示例

### 查询事件

```
ask_env(instruction="Check current event for person 0", ctx={"id": 0})
→ 无事件（None）
```

### 启动事件

```
ask_env(instruction="Start a 'work' event for person 0, event name 'morning coding session', expected duration 14400 seconds", ctx={"id": 0})
→ 事件已启动
```

### 保持当前同类事件

```
ask_env(instruction="Check current event for person 0", ctx={"id": 0})
→ 当前已经是 sleep 事件时，不要再次启动 sleep，只保持睡眠状态。
```

### 停止事件

```
ask_env(instruction="Stop current event for person 0 with status completed", ctx={"id": 0})
→ 事件已结束
```

### 切换事件

```
ask_env(instruction="Stop current event for person 0, then start a 'leisure and entertainment' event, event name 'watching movie', expected duration 7200 seconds", ctx={"id": 0})
```

## 约束

1. **所有操作通过 `ask_env`**。不能直接调用 `start_event`、`get_current_event` 等函数。
2. **同时最多一个事件**。启动不同类型的新事件前需先停止当前事件。
3. **同类 active event 是持续状态**。例如当前已经有 `sleep` 事件且每日 Story 仍是 sleep segment，
   本 step 应保持睡眠，不要取消并重开 sleep；只有真实切换到不同活动时才停止当前事件。
4. **持续事件不要按 step 切片重开**。例如 00:00-07:00 的睡眠是一个长事件，不是每 15/30 分钟新建一个事件。
