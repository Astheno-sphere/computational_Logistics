# 编程使用

本文档主要介绍如何使用命令行或代码运行AgentSociety。

---

这里假设已经完成[安装](./02-installation.md)，并准备好了{ref}`地图文件 <prep>`。
地图文件的存储路径为`./agentsociety_data/beijing.pb`。

(cli)=
## 命令行运行

一个最简单的配置文件如下，该配置包含了LLM设置、数据库配置、地图文件、智能体参数和实验配置等核心要素：

```yaml
llm:
  - model: qwen2.5-14b-instruct
    api_key: sk-123456
    base_url: https://cloud.infini-ai.com/maas/v1
    provider: vllm
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
      number: 10
exp:
  name: simplest_exp
  workflow:
    - type: run
      days: 1
      ticks_per_step: 300
  environment:
    start_tick: 28800
```

**LLM配置部分**：设置大语言模型相关参数，支持配置多个LLM实例
- `model`: 使用的模型名称，需根据模型提供商的说明设置
- `api_key`: 模型提供商的API密钥
- `base_url`: 模型提供商的API地址（此处为无问芯穹）
- `provider`: 模型提供商类型，此处使用vllm来接入OpenAI API兼容的大模型

**环境配置部分**：设置数据存储和数据库相关配置
- `db.enabled`: 是否启用数据库存储实验结果
- `db.db_type`: 数据库类型，此处使用SQLite
- `home_dir`: AgentSociety数据存储路径，包括sqlite数据库文件、HuggingFace模型文件、通过可视化界面管理的各类数据等，默认存储在当前目录下的`agentsociety_data`文件夹

**地图配置部分**：指定仿真环境使用的地图文件
- `file_path`: 地图文件的存储路径

**智能体配置部分**：定义仿真中的智能体类型和数量
- `citizens`: 市民智能体配置列表
- `agent_class`: 智能体类名，此处使用AgentSociety内置的`SocietyAgent`类
- `number`: 智能体实例数量

**实验配置部分**：定义实验的执行流程和环境参数
- `name`: 实验名称标识
- `workflow`: 实验流程配置列表，AgentSociety将顺序执行列表中的每个步骤
- `type`: 实验步骤类型，此处使用`run`类型执行仿真
- `days`: 仿真持续时间（单位：天）
- `ticks_per_step`: 仿真中两步之间的时间间隔（单位：秒），此处为300秒即5分钟，表示智能体每5分钟执行一次行动
- `environment.start_tick`: 仿真开始时间（单位：秒），此处为28800秒即早上8点

```{admonition} 提示
:class: note

配置数据格式采用[pydantic](https://docs.pydantic.dev/latest/)进行解析与校验，对所有字段的详细说明请参考[配置](../03-config/index.md)。
```

假设配置文件存储为`./config.yaml`，则可以通过以下命令运行AgentSociety命令行工具提供的配置预检查（预检查是可选步骤）：
```bash
agentsociety check -c ./config.yaml
```

如果配置文件正确，则输出内容如下：
```bash
Config format check. Passed.
Database connection check. Passed.
Map file. Passed.
```

否则将输出错误提示，可以根据提示说明修改配置文件。

配置预检查通过后，可以通过以下命令运行AgentSociety：
```bash
agentsociety run -c ./config.yaml
```

此后，AgentSociety开始模拟，并不断输出模拟过程中的日志。
模拟过程从虚拟世界的`start_tick`时间开始，模拟到当天的24点结束。
模拟过程中智能体的位置、状态、对话等数据将被存储到数据库中，可以通过可视化界面查看或编写代码[访问数据库](../02-development-guide/05-data-analysis.md)以进行进一步处理。

## 代码运行

除了使用命令行运行AgentSociety，也可以直接在Python代码中使用AgentSociety。下面是一个最小的代码示例：

```python
import asyncio
from agentsociety.cityagent import default
from agentsociety.configs import (
    AgentsConfig,
    Config,
    EnvConfig,
    ExpConfig,
    LLMConfig,
    MapConfig,
)
from agentsociety.configs.agent import AgentConfig
from agentsociety.configs.exp import WorkflowStepConfig, WorkflowType
from agentsociety.environment import EnvironmentConfig
from agentsociety.llm import LLMProviderType
from agentsociety.simulation import AgentSociety
from agentsociety.storage import DatabaseConfig

llm_config = LLMConfig(
    provider=LLMProviderType.VLLM,
    base_url="https://cloud.infini-ai.com/maas/v1",
    api_key="sk-123456",
    model="qwen2.5-14b-instruct",
    concurrency=200,
    timeout=60,
)

env_config = EnvConfig(
    db=DatabaseConfig(
        enabled=True,
        db_type="sqlite",
    ),
    home_dir="./agentsociety_data",
)

map_config = MapConfig(
    file_path="./agentsociety_data/beijing.pb",
)

agents_config = AgentsConfig(
    citizens=[
        AgentConfig(
            agent_class="citizen",
            number=10,
        )
    ],
)

exp_config = ExpConfig(
    name="simplest_code_exp",
    workflow=[
        WorkflowStepConfig(
            type=WorkflowType.RUN,
            days=1,
            ticks_per_step=300,
        ),
    ],
    environment=EnvironmentConfig(
        start_tick=8 * 60 * 60,
    ),
)

config = Config(
    llm=[llm_config],
    env=env_config,
    map=map_config,
    agents=agents_config,
    exp=exp_config,
)

config = default(config)

async def main():
    society = AgentSociety.create(config)

    try:
        await society.init()
        await society.run()
    finally:
        await society.close()


if __name__ == "__main__":
    asyncio.run(main())
```

这个示例与命令行运行的效果完全相同，主要包含以下步骤：

1. **导入必要的模块**：从agentsociety包中导入配置类、智能体类和模拟类
2. **创建配置对象**：设置LLM、数据库、地图、智能体和实验配置
3. **应用默认配置**：使用`default()`函数应用AgentSociety.cityagent默认设置，这将修饰智能体配置以添加默认值和默认的`agent_class`字符串到类型的映射使得配置符合初始化要求
4. **创建和运行模拟**：
   - 使用`AgentSociety.create()`创建模拟实例
   - 调用`init()`初始化环境
   - 调用`run()`开始模拟
   - 在`finally`块中调用`close()`清理资源

```{admonition} 提示
:class: note

- 确保在运行代码前已完成AgentSociety的安装和地图文件准备
- 记得将配置中的API密钥、模型名等参数替换为实际值
- 模拟运行时会在控制台输出日志，数据会保存到指定的数据库中
```

```{admonition} 高级用法
:class: tip

对于更复杂的实验场景，可以参考GitHub仓库中[examples/](https://github.com/tsinghua-fib-lab/AgentSociety/tree/main/examples)目录中的示例代码，了解如何配置问卷调查、消息干预、自定义智能体类等高级功能。
```

