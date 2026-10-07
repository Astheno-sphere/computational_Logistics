# LLM配置

LLM配置定义了智能体使用的大语言模型相关设置。AgentSociety支持多个LLM配置，系统会采用轮询的方式自动在多个配置间进行负载均衡。

## 配置字段

- `provider` (LLMProviderType): LLM服务提供商类型，支持以下选项：
  - `openai`: OpenAI及兼容的API
  - `deepseek`: [DeepSeek模型服务](https://platform.deepseek.com/usage)
  - `qwen`: [阿里百炼大模型平台](https://bailian.console.aliyun.com/#/home)
  - `zhipuai`: [智谱AI](https://www.bigmodel.cn/)
  - `siliconflow`: [硅基流动](https://siliconflow.cn/)
  - `volcengine`: [字节跳动火山方舟大模型引擎](https://www.volcengine.com/product/ark)
  - `vllm`: [VLLM](https://docs.vllm.ai/en/stable/)部署的模型服务，也用于接入OpenAI API兼容的大模型
- `model` (str): 使用的模型名称，需根据服务提供商的要求设置
- `api_key` (str): API访问密钥
- `base_url` (Optional[str]): API基础URL，仅VLLM类型支持自定义，其他类型提供该供应商的默认URL
- `concurrency` (int): 并发数量，用于控制请求频率避免触发限流，默认200
- `timeout` (float): 请求超时时间（秒），默认30秒，最大60秒

## 配置示例

**OpenAI兼容API配置**：
```yaml
llm:
  - provider: openai
    model: gpt-4o-mini
    api_key: sk-your-api-key
    concurrency: 100
    timeout: 30
```

**多LLM配置（负载均衡）**：
```yaml
llm:
  - provider: deepseek
    model: deepseek-chat
    api_key: sk-deepseek-key
    concurrency: 200
  - provider: qwen
    model: qwen-turbo
    api_key: sk-qwen-key
    concurrency: 150
```

**VLLM本地部署配置**：
```yaml
llm:
  - provider: vllm
    model: qwen2.5-14b-instruct
    api_key: token-abc123
    base_url: http://localhost:8000/v1
    concurrency: 50
```