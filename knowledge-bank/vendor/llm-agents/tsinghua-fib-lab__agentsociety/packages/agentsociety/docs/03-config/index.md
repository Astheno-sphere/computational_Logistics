# 配置

本文档详细介绍AgentSociety提供的所有配置项，从而帮助了解AgentSociety框架提供的所有功能，包括：
- [LLM配置](01-llm)
- [环境配置](02-env)
- [地图配置](03-map)
- [智能体配置](04-agent)
- [实验配置](05-exp)

## 完整配置示例

以下是一个包含所有主要配置项的完整示例，该配置展示了如何设置一个包含500个市民和20个企业的复杂仿真实验，包括问卷调查和环境干预等功能：

**大语言模型配置部分**：
- `provider`: 模型提供商类型
- `model`: 使用的模型名称
- `api_key`: API访问密钥
- `concurrency`: 并发请求数量
- `timeout`: 请求超时时间

**环境配置部分**：
- `db.enabled`: 是否启用数据库
- `db.db_type`: 数据库类型
- `home_dir`: 数据存储目录

**地图配置部分**：
- `file_path`: 地图文件路径

**智能体配置部分**：
- `citizens`: 市民智能体配置列表
- `firms`: 企业智能体配置列表
- `agent_class`: 智能体类名
- `number`: 智能体数量

**实验配置部分**：
- `name`: 实验名称
- `workflow`: 实验流程步骤列表，包括仿真运行、环境干预、问卷调查等
- `environment`: 仿真环境参数，包括开始时间、天气、温度等
- `logging_level`: 日志输出级别

```yaml
llm:
  - provider: qwen
    model: qwen-turbo
    api_key: sk-your-qwen-key
    concurrency: 200
    timeout: 30

env:
  db:
    enabled: true
    db_type: sqlite
  home_dir: ./agentsociety_data

map:
  file_path: ./agentsociety_data/beijing.pb

agents:
  citizens:
    - agent_class: SocietyAgent
      number: 500
  firms:
    - agent_class: firm
      number: 20

exp:
  name: comprehensive_simulation
  workflow:
    - type: run
      days: 1
      ticks_per_step: 300
    - type: environment
      key: weather
      value: "下雨"
    - type: survey
      target_agent: [1, 2, 3, 4, 5]
      survey:
        id: "550e8400-e29b-41d4-a716-446655440002"
        title: "天气影响调查"
        description: "了解天气变化对日常生活的影响"
        pages:
          - name: "出行影响"
            elements:
              - name: "travel_impact"
                title: "天气变化如何影响您的出行计划？"
                type: "text"
    - type: run
      days: 1
      ticks_per_step: 300
  environment:
    start_tick: 28800
    weather: "晴天"
    temperature: "温度22°C"
    workday: true
    metric_interval: 3600

logging_level: INFO
```

该配置文件的详细说明请参考各个子配置页面的文档。


```{toctree}
:maxdepth: 2
:hidden:

01-llm
02-env
03-map
04-agent
05-exp
```