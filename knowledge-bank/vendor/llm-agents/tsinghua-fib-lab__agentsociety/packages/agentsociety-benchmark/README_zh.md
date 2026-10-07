# AgentSociety Benchmark Toolkit

## 工具目标

AgentSociety Benchmark Toolkit 是一个专为多智能体系统设计的综合评估工具。该工具旨在帮助研究人员和开发者：

- **标准化评估流程**：提供统一的评估框架，确保不同智能体系统之间的公平比较
- **多场景测试**：支持多种现实世界场景的智能体行为评估
- **自动化评估**：简化从数据准备到结果分析的整个评估流程
- **可重现性**：确保实验结果的可重现性和可验证性

## 支持的Benchmark

### 1. BehaviorModeling（行为建模）
行为建模benchmark专注于评估智能体在复杂社会场景中的行为建模能力。该benchmark测试智能体如何：
- 理解和模拟人类行为模式
- 在群体环境中做出合理的决策
- 适应不同的社会规范和约束

### 2. DailyMobility（日常移动）
日常移动benchmark评估智能体在日常生活中的移动行为建模能力。该benchmark测试智能体如何：
- 规划合理的日常活动路线
- 考虑时间、地点和活动之间的关联性
- 模拟真实世界中的移动模式

### 3. HarricaneMobility（飓风移动）
飓风移动benchmark专注于评估智能体在紧急情况下的行为建模能力。该benchmark测试智能体如何：
- 在自然灾害中做出应急决策
- 模拟人群疏散和避难行为
- 处理不确定性和紧急情况下的资源分配

## 基础使用方法

### 安装工具

```bash
# 从源码安装
git clone <repository-url>
cd packages/agentsociety-benchmark
pip install -e .

# 或者使用pip安装（如果已发布）
pip install agentsociety-benchmark
```

### 查看可用任务

```bash
# 列出所有可用的benchmark任务
asbench list-tasks
```

### 下载数据集
- 需要提前安装git lfc
```bash
# 克隆特定benchmark的数据集，该操作会同时下载数据集并安装执行benchmark所需的依赖
asbench clone BehaviorModeling
asbench clone DailyMobility
asbench clone HarricaneMobility

# 查看已安装的benchmark
asbench list-installed

# 强制重新安装对应Benchmark的数据集与依赖
asbench clone BehaviorModeling --force

# 仅安装对应Benchmark所需的依赖
asbench clone BehaviorModeling --only-install-deps
```

### 运行评估

```bash
# 运行特定benchmark的评估
asbench run BehaviorModeling --config your_config.yaml

# 运行所有已安装的benchmark
asbench run all --config your_config.yaml
```

### 独立评估结果

```bash
# 对已生成的结果文件进行独立评估
asbench evaluate BehaviorModeling results.json

# 查看可评估的任务
asbench list-evaluatable-tasks
```

### 更新Benchmark

```bash
# 更新所有benchmark到最新版本
asbench update-benchmarks
```

### 存储和配置

- **数据存储**：所有benchmark数据存储在 `.agentsociety-benchmark/` 目录中
- **配置文件**：使用YAML格式的配置文件定义智能体参数和评估设置
- **结果存储**：评估结果以JSON格式保存，便于后续分析和比较

## 配置示例

```yaml
# config.yaml
llm:
- api_key: YOUR-API-KEY # LLM API密钥
  model: YOUR-MODEL # LLM模型
  provider: PROVIDER # LLM提供商
  semaphore: 200 # LLM请求的信号量，控制最大并发请求数
env:
  db:
    enabled: true # 是否启用数据库
  home_dir: .agentsociety-benchmark/agentsociety_data
```

## 依赖要求

- Python >= 3.11
- agentsociety >= 1.5.0a11
- 其他依赖见 `pyproject.toml`

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。 