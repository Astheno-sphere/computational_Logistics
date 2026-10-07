# 前置准备

本文档将介绍使用AgentSociety前需要准备的软硬件环境与依赖。

## 硬件环境

AgentSociety对硬件环境没有特殊要求，但建议使用具有一定CPU性能与足够内存的计算机以避免运行过慢或出现内存不足的问题。

建议配置不低于：
- CPU：4核
- 内存：16GB

## 软件环境

AgentSociety使用Python语言开发，需安装Python 3.11或更高版本。

同时，由于AgentSociety依赖的并行计算框架[ray](https://docs.ray.io/en/latest/ray-overview/installation.html)的支持情况，AgentSociety支持的系统与体系结构包括：
- Linux X86_64
- MacOS ARM

```{admonition} 注意
:class: warning

ray对Windows的支持是实验性的，因此AgentSociety不支持Windows系统，如有需要可以使用Windows Subsystem for Linux (WSL) 2运行AgentSociety。
```

## 大模型API

AgentSociety使用大模型完成智能体的推理，因此需要配置至少一个大模型API。

AgentSociety支持以下大模型API平台以及任何[OpenAI接口兼容](https://platform.openai.com/docs/api-reference/introduction)的大模型API：
- [DeepSeek](https://deepseek.com/)
- [OpenAI](https://openai.com/)
- [Qwen](https://tongyi.aliyun.com/)
- [SiliconFlow](https://siliconflow.cn/)
- [ZhipuAI](https://chatglm.cn/)：提供完全免费的大模型[`GLM-4.5-Flash`](https://www.bigmodel.cn/pricing)
- [VolcEngine](https://www.volcengine.com/)
- [vLLM](https://docs.vllm.ai/en/stable/): vLLM框架可私有化部署OpenAI API兼容大模型服务，注意必须启动[工具调用能力](https://docs.vllm.ai/en/stable/features/tool_calling.html)。
- 任何OpenAI接口兼容的大模型API：通过大模型相关配置中的`base_url`、`api_key`等字段配置

## 额外说明

```{admonition} 提示
:class: note

根据用户使用体验，AgentSociety 1.5版本大幅减少了所依赖的软件，移除了对[MLflow](https://mlflow.org/)、[Redis](https://redis.io/)等软件的依赖，因此用户可以更方便地使用AgentSociety。

数据库默认采用[SQLite](https://www.sqlite.org/index.html)进行文件形式的存储以避免软件依赖，用户仍可以通过配置文件中的`db`字段配置[PostgreSQL](https://www.postgresql.org/)数据库以便与团队成员共享数据。
```