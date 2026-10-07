# Skill 编写指南

本文档介绍如何为 `PersonAgent` 编写自定义 Skill。Skill 的目标不是把所有逻辑写成复杂插件，而是把一种能力的触发条件、输入文件、执行步骤和输出文件说明清楚，让智能体在合适的时候调用它。

## 概述

Skill 是 `PersonAgent` 的行为模块。常见写法有两种：

- **Prompt-only（推荐）**：只写 `SKILL.md`，适合判断、反思、总结、计划等开放任务。
- **带脚本**：额外提供 Python 脚本，适合确定性计算、格式转换、批处理和可重复的数据维护。
  脚本默认**在 agent 进程内**经 `entrypoint(argv, ctx)` 执行（毫秒级、并发安全）；无 `entrypoint`
  时回退到动态包装器，最后才回退到子进程。

与环境交互时，不需要在 frontmatter 里声明特殊 executor；在正文中说明何时使用 `ask_env` 工具即可。
完整的设计说明见 `agentsociety2/agent/skills/README.md` 与 :doc:`/agent_skills`。

## 快速开始

### 创建一个简单的Skill

1. 在`custom/skills/`目录下创建新文件夹：

```
custom/skills/my-skill/
└── SKILL.md
```

2. 编写SKILL.md：

```markdown
---
name: my-skill
description: 一句话描述功能。什么时候使用。产生什么输出。
---

# My Skill

## 何时使用
描述触发条件。

## 输入文件
- 当前 step 的 observation 已在 ReAct 上下文中，不需要从固定文件读取
- `state/needs.json`：需求状态（如果存在）
- `AGENT_MEMORY.md`：长期摘要（如果需要）

## 执行步骤
1. 首先，用 `read` 读取需要的 workspace 文件
2. 然后，分析内容并做出决策
3. 最后，用 `write` 写入输出文件

## 输出格式
\`\`\`json
{
  "field1": "描述",
  "field2": 0.5
}
\`\`\`

## 示例

**输入**：
\`\`\`
ReAct step context: "在公园遇到了Alice"
\`\`\`

**输出**：
\`\`\`json
{
  "event": "met Alice at park",
  "emotion": "happy"
}
\`\`\`
```

无需编程，模型会根据你的描述读取文件、调用工具并写入输出。写得越具体，行为越稳定。

## SKILL.md结构详解

### Frontmatter（必需）

Frontmatter是YAML格式的元数据块，位于文件开头：

```yaml
---
name: skill-name           # 必需：唯一标识符
description: 描述           # 必需：catalog / 选择器用
---
```

可选：在同目录下放置 ``scripts/<name>.py``。推荐在脚本顶层定义
``def entrypoint(argv, ctx) -> str``，运行时会优先在进程内调用它（缓存 import、无 fork）；
无 ``entrypoint`` 时回退到动态包装器 / 子进程。依赖关系写在正文里，由模型按需 ``activate_skill``。

### Body（必需）

Body是Markdown格式的行为指南，告诉LLM：

1. **何时使用**：触发条件
2. **输入**：读取哪些文件
3. **做什么**：执行步骤
4. **输出**：产生什么文件

## 可用的内置工具

Skill 的 Markdown body 中可以指导 LLM 使用 ``PersonAgent`` 的 ReAct 工具（注意实际工具名）：

| 工具 | 用途 | 示例 |
|------|------|------|
| `read` | 读取工作区文件 | `read("state/needs.json")` |
| `write` | 写入工作区文件 | `write("state/result.json", content)` |
| `append` | 追加内容 | `append("state/notes.jsonl", line)` |
| `list` | 列出目录文件 | `list(".")` |
| `grep` | 在工作区文件中搜索 | `grep("pattern", ".")` |
| `ask_env` | 向环境路由器发请求 | `ask_env("<observe>")` |
| `activate_skill` / `read_skill_file` / `execute_skill_script` | 激活/读取/执行其它 skill | 见 :doc:`/agent_skills` |
| `finish` | 结束当前仿真步 | 带可选 summary |

> 没有 `bash` / `glob` / `codegen` / `batch` 工具；环境交互统一走 `ask_env`。

## Skill类型

### 类型1：纯Prompt驱动（推荐）

大多数Skill不需要编程，只需要清晰的描述：

```markdown
---
name: mood-check
description: Check and record current mood based on recent events.
---

# Mood Check

Analyze recent events and determine current mood.

## Input
- Current step context: current observation and available environment context
- `state/emotion.json`: Current emotional state
- `AGENT_MEMORY.md`: Persistent runtime summary, if needed

## Output
Write `state/mood.json`:
\`\`\`json
{
  "mood": "happy|sad|neutral|anxious|excited",
  "intensity": 0.0-1.0,
  "reason": "Brief explanation"
}
\`\`\`
```

### 类型2：带Python脚本

当需要确定性计算时，添加Python脚本：

```
custom/skills/calculator/
├── SKILL.md
└── scripts/
    └── calc.py
```

SKILL.md:
```yaml
---
name: calculator
description: Perform precise numerical calculations.
script: scripts/calc.py
---
```

calc.py（提供 ``entrypoint``，进程内执行；CLI 与 entrypoint 共用同一派发）：
```python
"""Calculator skill script."""

import argparse
import contextvars
import json
from pathlib import Path
from typing import Any

# 用 ContextVar 承载“本次调用的工作区根”，保证多 agent 并发安全
_WS_ROOT: contextvars.ContextVar[Path | None] = contextvars.ContextVar(
    "calc_ws_root", default=None
)


def dispatch(args: argparse.Namespace) -> int:
    ws = _WS_ROOT.get() or Path.cwd()
    state_dir = ws / "state"
    state_dir.mkdir(exist_ok=True)

    # 计算逻辑。真实项目中不要直接 eval 用户输入。
    expression = args.expression
    try:
        result = eval(expression)
        output = {"ok": True, "result": result}
    except Exception as e:
        output = {"ok": False, "error": str(e)}

    (state_dir / "result.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2)
    )
    print(json.dumps(output))
    return 0


def entrypoint(argv: list[str], ctx: Any) -> str:
    parser = argparse.ArgumentParser()
    parser.add_argument("--args-json", default="{}")
    ns = parser.parse_args(list(argv))
    import json as _json

    ns.expression = _json.loads(ns.args_json or "{}").get("expression", "0")
    _WS_ROOT.set(Path(str(getattr(ctx, "workspace_root"))).resolve())
    dispatch(ns)
    return ""  # 进程内：返回字符串而非依赖 print 捕获


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--args-json", default="{}")
    ns = parser.parse_args()
    import json as _json

    ns.expression = _json.loads(ns.args_json or "{}").get("expression", "0")
    return dispatch(ns)


if __name__ == "__main__":
    raise SystemExit(main())  # 子进程回退路径仍可用
```

### 与环境交互

在 SKILL 正文里说明何时调用内置 **`ask_env`** 工具即可；不要在 frontmatter 里写 ``executor``（框架不解析）。

## 最佳实践

### 1. 保持单一职责

每个 Skill 只做一件事：

- ✅ `mood-check`: 只更新当前情绪状态
- ✅ `social-reflection`: 只更新社交关系
- ❌ `mood_and_plan`: 做太多事情

### 2. 在正文写清产出文件

在 Markdown 里列出会写入的路径（如 ``state/result.json``）；frontmatter 不解析 ``outputs``、``inputs``、``requires`` 等扩展字段。

### 3. 处理缺失文件

Skill应该优雅处理输入文件不存在的情况：

```markdown
## Input Files
- Current step context contains the observation; do not assume `state/observation.txt` exists
- `state/needs.json`: Need state (use defaults if missing)
```

### 4. 提供示例

示例帮助LLM理解预期行为：

```markdown
## Example

**Input**:
\`\`\`
ReAct step context: "You see a cafe across the street."
\`\`\`

**Output** (intention.json):
\`\`\`json
{
  "intention": "Visit the café for lunch",
  "priority": 2,
  "reasoning": "I'm feeling hungry and there's a café nearby."
}
\`\`\`
```

### 5. 避免冗余描述

不需要告诉LLM"仔细思考"或"认真分析"，它会自然地做这些。

## 文件结构约定

推荐使用以下目录结构：

```
custom/skills/my-skill/
├── SKILL.md          # 必需：skill定义
├── scripts/          # 可选：Python脚本
│   └── main.py
├── templates/        # 可选：模板文件
│   └── prompt.jinja2
└── tests/            # 可选：测试
    └── test_skill.py
```

## 调试技巧

1. **查看workspace文件**：检查输出文件是否正确生成
2. **检查tool_calls.jsonl**：查看LLM调用了哪些工具
3. **简化描述**：如果Skill行为异常，尝试简化描述
4. **添加示例**：示例通常能显著改善LLM理解

## 示例：完整的Skill

```markdown
---
name: social-reflection
description: Reflect on recent social interactions and update relationship state.
---

# Social Reflection

Reflect on recent social interactions and how they affect relationships.

## When to Use
- After a significant social interaction
- When feeling uncertain about a relationship
- Before making social decisions

## Input Files
- Current step context: current perception and recent event text
- `state/relationships.json`: Current relationship state
- `AGENT_MEMORY.md`: Persistent runtime summary, if needed
- `state/emotion.json`: Current emotional state

## Execution Steps

1. Read `state/relationships.json` to understand current state
2. Read `AGENT_MEMORY.md` if additional background is needed
3. Consider current emotional state
4. Reflect on how recent events affect relationships
5. Write reflection to `state/social_reflection.json`

## Output Format

\`\`\`json
{
  "reflection": "What I learned about my relationships",
  "relationship_changes": [
    {
      "agent_id": "2",
      "change": "increased trust",
      "reason": "Alice helped me when I was in trouble"
    }
  ],
  "social_goals": [
    "Spend more time with Alice",
    "Resolve conflict with Bob"
  ]
}
\`\`\`

## Example

**Input**:
- ReAct step context: "Alice smiled and offered to help with my project."
- state/relationships.json: Agent 2 (Alice) is an acquaintance with trust 0.3

**Output**:
\`\`\`json
{
  "reflection": "Alice showed genuine kindness by offering help.",
  "relationship_changes": [
    {
      "agent_id": "2",
      "change": "increased trust and affection",
      "reason": "Alice's offer to help demonstrates reliability"
    }
  ],
  "social_goals": [
    "Accept Alice's help and build friendship"
  ]
}
\`\`\`
```

## 常见问题

**Q: Skill之间如何通信？**

A: 通过workspace文件。一个Skill写入文件，另一个Skill读取。

**Q: 如何控制Skill执行顺序？**

A: 由主模型在工具循环里决定先 ``activate_skill`` 哪一个；若有硬依赖，在 SKILL.md 正文写清并引导先激活依赖 skill。

**Q: Skill可以调用其他Skill吗？**

A: 不直接调用。通过workspace文件松耦合，LLM决定何时激活哪个Skill。

**Q: 如何测试Skill？**

A: 创建测试workspace，放置输入文件，运行agent，检查输出文件。

## 进阶主题

### 状态管理

如果Skill需要维护状态，写入JSON文件：

```json
{
  "state": "active",
  "progress": 0.5,
  "history": ["event1", "event2"]
}
```

### 与环境交互

使用`ask_env`工具与环境交互：

```markdown
## Environment Actions

1. Observe: `ask_env("<observe>")`
2. Move: `ask_env("Move to {location}")`
3. Speak: `ask_env("Say '{message}' to {target}")`
```

### 时间感知

Skill可以接收时间信息：

```markdown
The `tick` and `time` fields are auto-injected by the framework.
Use them for time-dependent logic.
```
