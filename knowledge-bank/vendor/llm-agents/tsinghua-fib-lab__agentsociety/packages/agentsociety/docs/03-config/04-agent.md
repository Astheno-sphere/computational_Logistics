# 智能体配置

智能体配置定义了仿真中不同类型智能体的设置，支持市民、企业、银行、国家统计局、政府等多种类型，其主要用途如下：
- 市民：模拟城市中的居民，可以进行工作、消费、出行等行为
- 企业：模拟城市中的企业，为居民提供工作岗位并发放薪水
- 银行：调控利率水平，根据居民存款定期发放利息
- 统计局：收集居民收入、消费等数据，用于宏观经济分析
- 政府：调整税率，影响宏观经济
- 监管者：对市民间通过线上社交媒体进行的对话进行监管，过滤特定信息

## 配置字段

**AgentsConfig主要字段**：
- `citizens` (list[AgentConfig]): 市民智能体配置，必需且至少包含一个配置
- `firms` (list[AgentConfig]): 企业智能体配置，可选
- `banks` (list[AgentConfig]): 银行智能体配置，可选
- `nbs` (list[AgentConfig]): 国家统计局智能体配置，可选
- `governments` (list[AgentConfig]): 政府智能体配置，可选
- `supervisor` (Optional[AgentConfig]): 监管者智能体配置，可选

**单个AgentConfig主要字段**：

- `agent_class` (Union[type[Agent], str]): 智能体类名或类型

- `number` (int): 智能体数量，默认1，必须大于等于0

- `agent_params` (Optional[Any]): 智能体参数配置，用于自定义智能体行为
  - 支持任意类型，具体参数由智能体类定义
  - **必须根据使用的智能体类来填写对应的参数**
  - 例如：`SocietyAgent`支持`enable_cognition`、`max_plan_steps`等参数
  - 参数会影响智能体的决策逻辑和行为模式

- `blocks` (Optional[dict]): 智能体行为模块配置，定义智能体的功能模块
  - 键为模块类名或字符串标识符
  - 值为模块的具体配置参数
  - **必须根据使用的模块类型来填写对应的参数**
  - 常用模块：`MobilityBlock`、`EconomyBlock`、`SocialBlock`等
  - 模块配置会影响智能体的能力范围和行为方式

- `memory_from_file` (Optional[str]): 从文件加载初始记忆配置
  - 文件路径，支持本地文件和S3文件
  - 文件格式应为JSON，包含智能体的初始属性
  - 与`memory_distributions`互斥

- `tools` (Optional[list[CustomTool]]): 智能体工具配置，扩展智能体能力
  - 每个工具包含：`name`、`description`、`tool`、`category`等字段
  - `category`支持：`NORMAL`（普通工具）、`MCP`（模型上下文协议工具）
  - 工具可以扩展智能体的功能，如天气查询、路径规划等
  - **不支持文件配置方案**

```{admonition} 注意
:class: warning

所有从文件载入的与class相关的配置（如agent_class, Block等）均需要从community中进行转换
```

## 配置示例

**基础市民配置**：
```yaml
agents:
  citizens:
    - agent_class: citizen
      number: 100
```

**多类型智能体配置**：
```yaml
agents:
  citizens:
    - agent_class: citizen
      number: 1000
  firms:
    - agent_class: firm
      number: 5
  governments:
    - agent_class: government
      number: 1
  nbs:
    - agent_class: nbs
      number: 1
  banks:
    - agent_class: bank
      number: 1
```

**从文件加载智能体配置**：
```yaml
agents:
  citizens:
    - agent_class: citizen
      memory_from_file: ./agent_profiles.json
```

**自定义智能体参数配置**：
```yaml
agents:
  citizens:
    - agent_class: citizen
      number: 100
      agent_params:
        enable_cognition: true
        max_plan_steps: 5
        need_initialization_prompt: "你是一个市民，需要满足基本需求"
        plan_generation_prompt: "根据当前需求制定详细计划"
        block_dispatch_prompt: "根据意图选择合适的模块"
```

```{admonition} 注意
:class: warning

`agent_params`的具体参数需要根据使用的智能体类来确定。
```

**配置智能体行为模块**：
```yaml
agents:
  citizens:
    - agent_class: citizen
      number: 100
      blocks:
        MyBlock:
          max_speed: 5.0
          preferred_transport: "walking"
```

```{admonition} 注意
:class: warning

`blocks`配置需要根据使用的模块类型来确定参数。
```