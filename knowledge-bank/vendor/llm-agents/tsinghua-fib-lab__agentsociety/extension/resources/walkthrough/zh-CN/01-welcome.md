## 欢迎使用 AI Social Scientist

**AgentSociety²** 不只是一个多智能体模拟器。它是一套面向“可执行社会科学”的集成研究环境（IRE）：把研究问题、理论假设、硅基参与者、仿真环境、干预、测量和研究结论放进同一个可检查、可修改、可复现的工作区。

![AgentSociety 2 双角色研究环境](../images/agentsociety2-dual-role.png)

*图：AgentSociety² 将 AI Social Scientists 与 Silicon Participants 放进同一个闭环。原图来自 [AgentSociety 2 论文](https://arxiv.org/abs/2607.11895)。*

### 三个协作角色

| 角色 | 负责什么 |
|------|----------|
| **人类研究者** | 提出问题，在假设、干预、有效性解释和结论发布等关键节点做判断 |
| **AI Social Scientist** | 协调文献、假设、实验设计、仿真执行、分析与论文草拟 |
| **Silicon Participants** | 在可配置环境中感知、推理、行动并产生可测量的行为反馈 |

### AI Social Scientist 的七阶段工作流

AI Social Scientist 是 IRE 中负责研究编排的角色。它把研究组织成七个可见、可检查的阶段：研究范围界定、假设生成、实验设计、仿真配置、运行执行、结果分析和论文草拟。

![AI Social Scientist 七阶段工作流](../images/ai-social-scientist-workflow.png)

*图：来自 [AgentSociety 2 论文](https://arxiv.org/abs/2607.11895) 的 AI Social Scientist 七阶段架构。*

这里的“可执行”很重要：研究想法不只停留在一段对话里，而会逐步变成 `TOPIC.md`、假设包、实验配置、运行记录、分析报告和论文材料。你可以检查中间产物、修改参数、回退阶段并重新运行。

### 你可以用它做什么

| 环节 | 工作区能力 |
|------|------------|
| 文献与问题 | 维护 `TOPIC.md`、文献库和数据资产 |
| 假设与设计 | 形成可检验假设、实验组、干预与测量方案 |
| 社会模拟 | 配置 Agent、Environment 与 Steps，运行多尺度实验 |
| 分析与写作 | 检查运行记录、回放、图表、报告与论文材料 |
| 能力扩展 | 安装研究技能、Agent 运行时技能，以及 Claude/Codex 技能 |

### 最短上手路径

1. **进入工作区**：信任文件夹，必要时切换中文界面。
2. **认识界面**：找到项目树、编辑器、AI Chat 与状态栏。
3. **初始化项目**：创建研究目录和 `TOPIC.md`。
4. **配置运行环境**：设置仿真 LLM，验证并启动本地后端。
5. **启动研究闭环**：从一个明确问题开始，让 AI Social Scientist 生成可审阅的下一阶段产物。

后面的步骤会按这个顺序展开。遇到陌生术语，可随时查看最后一章“术语附录”。
