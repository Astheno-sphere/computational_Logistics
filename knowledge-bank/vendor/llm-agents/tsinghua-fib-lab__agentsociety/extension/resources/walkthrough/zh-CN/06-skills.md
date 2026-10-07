## 用技能扩展研究能力

AgentSociety² 将可复用的方法、工具与行为过程封装为技能。AI Social Scientist 会按任务逐步加载研究技能，Silicon Participants 则在仿真中激活行为技能；这样不必把全部规则塞进一个超长 Prompt，也更容易审计每一步使用了什么能力。

侧边栏点 **技能**，或从命令面板打开技能管理。页内分四个 Tab（运行时 / Claude / 市场 / MCP）；详细说明在标题旁 **?** 或页头帮助中。市场源与 Token 在页头 **设置** 统一配置。

### 作为硅基参与者的 PersonAgent

`PersonAgent` 是内置的、由人物画像驱动的 Silicon Participant。它采用论文中的 workspace-backed Social Generative Agent 架构：Profile、State、Memory、Logs 与 Checkpoints 都以可检查的形式保存；ReAct 循环连接观察、意图、行动与反思；工具和技能则根据当前环境与实验需要按需加载。

![PersonAgent 使用的 workspace-backed Social Generative Agent 架构](../images/person-agent-architecture.png)

*图：来自 [AgentSociety 2 论文](https://arxiv.org/abs/2607.11895) 的 Social Generative Agent 架构；`PersonAgent` 是运行在这套架构上的内置 profile-based 实现。*

### Agent 运行时

**Agent 运行时** Tab 管理仿真 Agent 使用的工作区技能（位于 `custom/skills/`，通常需后端注册）：

![Agent 运行时技能](../images/agent-skills.png)

PersonAgent 内置行为技能目前主要为 `daily-guidance`；工作区还可安装自定义技能，环境模块也可提供 `env` 技能。它们改变的是**仿真参与者如何行动**。

### Claude 目录

**Claude 目录** Tab 管理 Claude Code / Codex 使用的技能模板（同步到 `.claude/skills/`）：

![Claude 目录技能](../images/claude-skills.png)

扩展附带模板可开关、重新同步；也可导入外部 Claude 技能。文献检索、假设管理、实验配置、运行和分析等研究流程主要由这一层驱动。

### 对照

| 类型 | 位置 | 用途 |
|------|------|------|
| **Agent 运行时** | `custom/skills/` | Silicon Participants 的行为能力 |
| **Claude / Codex 目录** | `.claude/skills/` | AI Social Scientist 的研究与工程能力 |

### 技能市场

**市场** Tab 从远程仓库浏览技能，可选择安装到运行时（`custom/skills/`）或 Claude 目录（`.claude/skills/`）。

### MCP

文献 MCP 在 **配置页 → 文献 MCP** 填写；在 **技能管理 → MCP 集成** 同步到 Claude / Codex。MCP 提供外部工具与数据入口，Skill 则规定何时调用、如何核对以及产出什么，两者作用不同。

[打开技能管理](command:aiSocialScientist.openSkillMarketplace)
