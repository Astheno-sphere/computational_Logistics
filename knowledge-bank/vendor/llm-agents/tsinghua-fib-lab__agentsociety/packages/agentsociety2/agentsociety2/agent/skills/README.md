# Agent Skill 技术方案

> 适用范围：`agentsociety2`（v2.x）。本文描述 `PersonAgent` 的 Skill 子系统——
> 从目录结构、发现机制、可见性/激活模型，到**脚本执行模型（进程内 entrypoint）**
> 与生命周期 hook 的注入方式。文档面向 Skill 作者与二次开发者，后续会整理进
> ReadTheDocs。

## 1. 概述

PersonAgent 是一个轻量的 ReAct 编排器，其能力由**可插拔的 Skill 流水线**提供。
Skill 遵循 **metadata-first、selected-only** 模型：

- **选择阶段**：LLM 只看到 Skill 目录（`name` + `description`），据此决定激活哪些。
- **执行阶段**：只有被 LLM 选中的 Skill 才会被加载、读取、执行（惰性加载）。

这样做的好处是：提示词体积可控（未选中的 Skill 不进上下文），且 Skill 可独立
演进、热加载。

一个 Skill 是一个自包含目录，至少包含一个 `SKILL.md`（YAML frontmatter + 行为
文档），可选地包含 `scripts/`（可执行脚本）和 `references/`（参考资料）。

```
agent/skills/
└── daily-guidance/              # 一个 Skill = 一个目录
    ├── SKILL.md                 # frontmatter（name/description/script/hooks）+ 行为说明
    ├── scripts/
    │   └── daily_guidance.py    # 可执行脚本（提供 entrypoint）
    └── references/
        └── examples.md          # SKILL.md 引用、按需读取的参考资料
```

## 2. 目录结构与 SKILL.md 规范

### 2.1 目录约定

| 路径 | 是否必需 | 说明 |
| --- | --- | --- |
| `SKILL.md` | 必需 | YAML frontmatter + Markdown 行为文档。是 Skill 的入口。 |
| `scripts/*.py` | 可选 | 可执行脚本。`script:` 指向默认脚本；`hooks:` 指向生命周期脚本。 |
| `references/*` | 可选 | SKILL.md 中引用的补充材料，按需被 agent 读取（渐进式披露）。 |

### 2.2 SKILL.md frontmatter

frontmatter 目前识别以下字段（见 `registry.py` 的解析逻辑）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `name` | str | Skill 显示名，与命名空间组合成 `skill_id`（`namespace@name`）。 |
| `description` | str | **目录描述**——选择阶段 LLM 唯一可见的文本，决定是否激活。务必精炼、可操作。 |
| `script` | str | 可选，默认脚本相对路径（如 `scripts/daily_guidance.py`）。`execute_skill_script` 不传 `script_path` 时用它。 |
| `hooks` | dict | 可选，生命周期 hook 脚本映射，键为 hook 类型（如 `pre_step`、`post_step`），值为相对脚本路径。 |

示例（取自 `daily-guidance`）：

```markdown
---
name: daily-guidance
description: 强制使用：凡是时间尺度在小时及以下的日常行为模拟，必须使用本 Skill 生成、评估、执行和修正每日 Story。
script: scripts/daily_guidance.py
hooks:
  pre_step: scripts/daily_guidance.py
---

# Daily Guidance

（Markdown 行为文档：告诉 LLM 何时、如何使用本 Skill……）
```

> frontmatter 之后的 Markdown 正文，是 Skill 被**激活后**注入到 system prompt 的
> 行为说明（`<skill_content>` 块）。未激活时不进上下文。

## 3. 发现机制（内置 / 自定义）

`SkillRegistry` 按目录扫描，用 `namespace@name` 作为稳定 `skill_id`：

- **内置 Skill**：扫描 `agentsociety2/agent/skills/`，命名空间 `built-in`
  （如 `built-in@daily-guidance`）。
- **自定义 Skill**：扫描 agent 工作区下的 `custom/skills/`，命名空间 `custom`
  （如 `custom@my-skill`）。**热加载**——放进去即可在运行时被发现，无需改框架代码。

扫描规则（见 `registry._scan_skill_root`）：

- 每个子目录必须含 `SKILL.md`，否则跳过。
- 以 `.` 或 `_` 开头的目录被忽略（缓存、内部目录）。
- 同名（同 `skill_id`）先到先得，后扫描的不会覆盖。

agent 启动时通过 `default_activated_skill_ids` 配置默认激活哪些 Skill（例如
daily-mobility 默认激活 `built-in@daily-guidance`）。

## 4. 可见性与激活

- **可见（visible）**：Skill 出现在目录里，LLM 能看到、能选择激活。
- **激活（activated）**：Skill 的 `SKILL.md` 正文被注入 system prompt，其脚本/hook
  可被调用。

LLM 通过下列工具操作 Skill（见 `person_tools.py`）：

| 工具 | 作用 | 改变状态？ |
| --- | --- | --- |
| `activate_skill` | 加载某 Skill 的 SKILL.md 进上下文 | 是 |
| `deactivate_skill` | 从上下文移除某 Skill | 是 |
| `read_skill_file` | 读取 Skill 内的文件（渐进式披露） | 否 |
| `execute_skill_script` | 执行 Skill 脚本 | 否（脚本内部可能写工作区） |

> ReAct 主循环每个 `step()` 开始前会刷新可见 Skill 集合；ask 模式下（外部问答）
> 只暴露只读工具子集。

## 5. 脚本执行模型（进程内 entrypoint）⭐

这是改版后的**核心**。历史上 Skill 脚本以子进程方式执行（`python script.py
<argv>`），每个 agent 每步都要 fork 一个新解释器，冷启动开销巨大（实测单个
daily-guidance hook 约 9s，主要花在解释器启动与依赖 import 上）。

改版后，Skill 脚本默认**在 agent 进程内执行**，分三档优先级：

```
① entrypoint(argv, ctx)        ← 首选：缓存 import 后直接调用，毫秒级，完全并发安全
② 动态包装器（exec）             ← 兜底：无 entrypoint 时，以 __name__=="__main__" 就地执行
③ 子进程（python script.py）    ← 最后回退：模块无法 import 时
```

### 5.1 `entrypoint` 契约（推荐所有 Skill 脚本遵循）

Skill 脚本可在模块顶层定义一个 `entrypoint`，runtime 会优先调用它：

```python
def entrypoint(argv: list[str], ctx) -> str:
    """进程内入口。

    Args:
        argv: 命令行参数（去掉脚本名之后的部分），与子进程方式的 sys.argv[1:] 一致。
        ctx:  SkillScriptContext，携带本 agent 的运行上下文（见 5.2）。

    Returns:
        str: 脚本原本会打印到 stdout 的文本（通常是 YAML/JSON 结果块）。
    """
```

要点：

- **签名兼容**：runtime 检测形参数量，`entrypoint(argv)` 与 `entrypoint(argv, ctx)`
  都支持。**强烈建议接受 `ctx`**（见 5.2 的并发安全要求）。
- **返回 stdout**：不要依赖 `print` 被 capture；直接 `return` 结果字符串。
  runtime 把返回值当作 stdout 处理（也可返回 `(stdout, stderr)` 二元组）。
- **异常即失败**：`entrypoint` 抛异常 → 该次执行记为失败（`exit_code=1`，
  `stderr=traceback`）。不要用 `sys.exit()`；如需表达“逻辑失败”，在返回的文本里
  写 `ok: false`（和 CLI 语义一致）。
- **幂等加载**：runtime 按 `(路径, mtime)` 缓存模块，模块顶层代码只执行一次。
  把可变状态放进函数内或 contextvar，**不要放模块级全局**（见 5.3）。

CLI 与 entrypoint 共用同一套派发逻辑，是最佳实践（参见 5.5 的 daily-guidance 示例）。

### 5.2 `SkillScriptContext`

进程内执行时，runtime 不再依赖进程全局的环境变量，而是把上下文通过 `ctx` 显式
传入（定义在 `runtime.py`）：

| 字段 | 说明 | 子进程时代的对应物 |
| --- | --- | --- |
| `ctx.workspace_root` | 本 agent 的工作区根目录 | 环境变量 `AGENT_WORK_DIR` |
| `ctx.skill_dir` | 本 Skill 的包根目录 | 环境变量 `SKILL_DIR` |
| `ctx.skill_id` | 注册 id（`namespace@name`） | 环境变量 `SKILL_ID` |
| `ctx.skill_name` | 显示名 | 环境变量 `SKILL_NAME` |
| `ctx.env` | 子进程方式本会设置的 env 快照（dict） | 进程 `os.environ` |

> 用 `Path(str(getattr(ctx, "workspace_root")))` 取工作区根，**不要**读
> `os.environ["AGENT_WORK_DIR"]`。

### 5.3 并发安全要求（重要）

一次模拟里 50 个 agent 在**同一个进程**内并发跑各自的 Skill 脚本。下列进程级
状态是**共享**的，绝不能在 entrypoint 里直接读写，否则会产生数据竞争：

| ❌ 禁止 | ✅ 替代方案 |
| --- | --- |
| `os.environ["AGENT_WORK_DIR"] = ...` | 用 `ctx.workspace_root` |
| `os.chdir(workspace)` | 用绝对路径（`ctx.workspace_root / ...`） |
| `print(...)` 并依赖 stdout 捕获 | 在 entrypoint 里 `return` 字符串 |
| 模块级可变全局当作“本次调用状态” | 用 `contextvars.ContextVar`（任务级隔离） |

`daily_guidance.py` 的做法：用两个 `ContextVar` 分别承载“本次调用的工作区根”
和“本次调用的 emit 缓冲”，`entrypoint` 设置后、`dispatch` 内全程可见，调用结束
`reset`——天然并发安全：

```python
import contextvars

_WORKSPACE_ROOT: contextvars.ContextVar[Path | None] = contextvars.ContextVar(
    "dg_workspace_root", default=None
)
_EMIT_BUFFER: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "dg_emit_buffer", default=None
)


def agent_work_dir() -> Path:
    override = _WORKSPACE_ROOT.get()
    if override is not None:
        return override
    raw = os.environ.get("AGENT_WORK_DIR")  # 子进程回退路径才用
    return Path(raw).resolve() if raw else Path.cwd().resolve()
```

### 5.4 动态包装器（无 `entrypoint` 的脚本）

如果脚本没有定义 `entrypoint`，runtime 会用**动态包装器**就地执行：

- 以 `__name__ == "__main__"`、`sys.argv = [script, *argv]` 在全新命名空间里
  `exec` 脚本源码——语义等价于子进程，但复用热解释器，**无 fork、无冷启动**。
- 临时设置 `os.environ` / `os.chdir` / 捕获 stdout，执行后**逐一恢复**。
- 因为这些是进程级状态，**动态包装器由一把全局锁串行**执行（`_DYNAMIC_EXEC_LOCK`）。

权衡：

- 动态包装器依旧比子进程快得多（无解释器启动），但**多 agent 并发时会串行**。
- 因此**推荐所有 Skill 脚本提供 `entrypoint`**，享受完全并发。
- 动态包装器**无法硬性超时杀线程**（不像子进程能 `kill`）。若脚本可能长时间
  阻塞，请提供 `entrypoint` 并自行保证及时返回；runtime 仍会在加载失败时回退
  到子进程。

### 5.5 完整示例：daily-guidance 的 entrypoint

`daily_guidance.py` 把 CLI 派发抽成 `dispatch(args)`，`main()` 和 `entrypoint()`
共用它：

```python
def dispatch(args: argparse.Namespace) -> int:
    if args.cmd == "plan":
        return command_plan(args)
    if args.cmd == "current":
        return command_current(args)
    # …其余命令…
    return command_hook_init(args)


def entrypoint(argv: list[str], ctx: Any) -> str:
    workspace_root = Path(str(getattr(ctx, "workspace_root"))).resolve()
    ws_token = _WORKSPACE_ROOT.set(workspace_root)
    buf_token = _EMIT_BUFFER.set([])
    try:
        args = parse_args(list(argv))  # parse_args 接受显式 argv
        dispatch(args)
        return "".join(_EMIT_BUFFER.get() or [])  # 把 emit 累积的 YAML 文本返回
    finally:
        _EMIT_BUFFER.reset(buf_token)
        _WORKSPACE_ROOT.reset(ws_token)


def main() -> int:
    return dispatch(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())  # 子进程回退路径仍可用
```

`emit()` 改为写入 ContextVar 缓冲（entrypoint 模式）或 `print`（子进程模式）：

```python
def emit(payload: dict[str, Any]) -> None:
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    buffer = _EMIT_BUFFER.get()
    if buffer is not None:
        buffer.append(text)
    else:
        print(text)
```

## 6. 生命周期 Hook（pre_step / post_step）

在 `SKILL.md` 的 `hooks:` 里声明，每个仿真步自动触发：

- **`pre_step`**：`agent.step()` 开头、ReAct 循环之前运行。典型用途：根据仿真时钟
  推导当前状态（如 daily-guidance 的 `active_segment`），**注入到首轮上下文**。
- **`post_step`**：ReAct 循环之后运行。典型用途：记录实际行为、收尾。

### 6.1 Hook 输入与注入（改版后）

- **输入**：hook 以 `--args-json <json>` 形式接收 payload，含 `hook_type` / `tick` /
  `time` / `agent_id` / `step_count`。脚本用 `ctx.workspace_root` 定位工作区、用
  payload 里的 `time` 作为仿真时钟。
- **注入**：改版前，pre_step 的 stdout 被塞进通用的 `<recent_observations>` JSON
  dump 里，容易被 LLM 忽略（这是个 bug）。**改版后**，pre_step 的输出渲染为**专用
  的 `<skill_hooks>` XML 分块**，出现在 ReAct 首条 user 消息中，agent 据此把
  `active_segment` 当作权威指引：

  ```xml
  <skill_hooks>
  <skill_hook skill="built-in@daily-guidance" hook="pre_step" ok="true">
  ok: true
  active_segment:
    activity: sleep
    location_policy: home_aoi
  guidance: Your intended activity now is 'sleep' …
  </skill_hook>
  </skill_hooks>
  ```

这样 agent 不必再花一轮 `observe` + `execute_skill_script` 去“重新发现”状态——
实测 ReAct 平均轮数从 4.02 降到 2.44。

## 7. 环境类 Skill（`env:` 前缀）

以 `env:` 开头的 skill_id 会被 `execute_skill_script` **重定向到 `ask_env`**
（走环境路由 RouterBase），而非执行脚本。用于把“查询/操作仿真环境”包装成 Skill
暴露给 LLM。这类 Skill 不需要 `entrypoint`。

## 8. 性能（改版前后对比）

50-agent daily-mobility 实测（trace 聚合）：

| 指标 | 子进程方式（旧） | 进程内 entrypoint（新） | 提速 |
| --- | --- | --- | --- |
| `pre_step` hook 单次 | ~8933 ms | ~95 ms | ~93× |
| `execute_skill_script` 单次 | ~4023 ms | ~50 ms | ~80× |
| ReAct 轮数 / 步 | 4.02（36% 撞 6 轮上限） | 2.44（14% 撞顶） | 轮数 ↓39% |
| `agent.step` 整体 | ~75 s | ~31 s（median） | ~2.4× |

要点：

- **entrypoint 走内联调用**（不经过 `asyncio.to_thread`）。曾尝试用线程池，但默认
  executor + GIL 争用让 50 个并发 hook 反而膨胀到 ~5.5s/次；entrypoint 本身是
  毫秒级、I/O 密集，内联调用最合适。
- 动态包装器（无 entrypoint 脚本）仍比子进程快，但并发时会串行——所以**务必给
  热路径脚本补 `entrypoint`**。

## 9. 编写 Skill 的检查清单

新建一个 Skill 时，对照以下清单：

- [ ] 目录放在 `agent/skills/<name>/`（内置）或工作区 `custom/skills/<name>/`（自定义）。
- [ ] 有 `SKILL.md`：frontmatter 含 `name`、`description`（精炼可操作）、可选 `script`/`hooks`；
      正文是激活后注入的行为说明。
- [ ] 若有脚本：
  - [ ] 提供 `def entrypoint(argv, ctx) -> str`，**接受 `ctx`**。
  - [ ] 工作区根取自 `ctx.workspace_root`，不读 `os.environ`/不 `os.chdir`。
  - [ ] 结果用 `return` 返回，不依赖 `print` 捕获。
  - [ ] 用 `contextvars` 承载“本次调用状态”，不用模块级可变全局。
  - [ ] CLI 派发与 `entrypoint` 共用同一函数（`main()` 调 `dispatch(parse_args())`）。
- [ ] 若声明 `pre_step` hook，输出要自包含、可直接作为 agent 指引（会被包进
      `<skill_hooks>`）。
- [ ] 参考资料放 `references/`，SKILL.md 里点名引用，按需被读取（控制上下文体积）。

## 10. 相关代码索引

| 关注点 | 位置 |
| --- | --- |
| Skill 元数据与发现 | `agent/skills/registry.py`（`SkillRegistry`、`SkillDescriptor`、`_parse_hooks`） |
| 可见性/激活/脚本执行/hook | `agent/skills/runtime.py`（`AgentSkillRuntime`、`SkillScriptContext`、`_run_in_process`、`_call_entrypoint`、`_exec_script_dynamic`） |
| 工作区文件系统门面 | `agent/skills/workspace_fs.py`（`WorkspaceFS`、`CommandResult`，子进程回退路径） |
| ReAct 工具与 schema | `agent/person_tools.py`（`activate_skill`/`execute_skill_script`/…） |
| ReAct 提示词与 `<skill_hooks>` 渲染 | `agent/person_prompt.py`（`build_react_messages`、`_render_skill_hooks_xml`） |
| hook 注入与 step 编排 | `agent/person.py`（`_run_lifecycle_hooks`、`step`） |
| 进程内 entrypoint 参考实现 | `agent/skills/daily-guidance/scripts/daily_guidance.py`（`entrypoint`、`dispatch`、`agent_work_dir`、`emit`） |
