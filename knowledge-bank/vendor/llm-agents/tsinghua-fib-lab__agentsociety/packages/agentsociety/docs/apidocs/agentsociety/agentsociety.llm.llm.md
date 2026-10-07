# {py:mod}`agentsociety.llm.llm`

```{py:module} agentsociety.llm.llm
```

```{autodoc2-docstring} agentsociety.llm.llm
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`LLMProviderType <agentsociety.llm.llm.LLMProviderType>`
  - ```{autodoc2-docstring} agentsociety.llm.llm.LLMProviderType
    :summary:
    ```
* - {py:obj}`LLMConfig <agentsociety.llm.llm.LLMConfig>`
  - ```{autodoc2-docstring} agentsociety.llm.llm.LLMConfig
    :summary:
    ```
* - {py:obj}`LLMActor <agentsociety.llm.llm.LLMActor>`
  - ```{autodoc2-docstring} agentsociety.llm.llm.LLMActor
    :summary:
    ```
* - {py:obj}`LLM <agentsociety.llm.llm.LLM>`
  - ```{autodoc2-docstring} agentsociety.llm.llm.LLM
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.llm.llm.__all__>`
  - ```{autodoc2-docstring} agentsociety.llm.llm.__all__
    :summary:
    ```
* - {py:obj}`MAX_TIMEOUT <agentsociety.llm.llm.MAX_TIMEOUT>`
  - ```{autodoc2-docstring} agentsociety.llm.llm.MAX_TIMEOUT
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.llm.llm.__all__
:value: >
   ['LLM', 'LLMConfig', 'LLMProviderType']

```{autodoc2-docstring} agentsociety.llm.llm.__all__
```

````

````{py:data} MAX_TIMEOUT
:canonical: agentsociety.llm.llm.MAX_TIMEOUT
:value: >
   60

```{autodoc2-docstring} agentsociety.llm.llm.MAX_TIMEOUT
```

````

`````{py:class} LLMProviderType()
:canonical: agentsociety.llm.llm.LLMProviderType

Bases: {py:obj}`str`, {py:obj}`enum.Enum`

```{autodoc2-docstring} agentsociety.llm.llm.LLMProviderType
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.llm.llm.LLMProviderType.__init__
```

````{py:attribute} OpenAI
:canonical: agentsociety.llm.llm.LLMProviderType.OpenAI
:value: >
   'openai'

```{autodoc2-docstring} agentsociety.llm.llm.LLMProviderType.OpenAI
```

````

````{py:attribute} DeepSeek
:canonical: agentsociety.llm.llm.LLMProviderType.DeepSeek
:value: >
   'deepseek'

```{autodoc2-docstring} agentsociety.llm.llm.LLMProviderType.DeepSeek
```

````

````{py:attribute} Qwen
:canonical: agentsociety.llm.llm.LLMProviderType.Qwen
:value: >
   'qwen'

```{autodoc2-docstring} agentsociety.llm.llm.LLMProviderType.Qwen
```

````

````{py:attribute} ZhipuAI
:canonical: agentsociety.llm.llm.LLMProviderType.ZhipuAI
:value: >
   'zhipuai'

```{autodoc2-docstring} agentsociety.llm.llm.LLMProviderType.ZhipuAI
```

````

````{py:attribute} SiliconFlow
:canonical: agentsociety.llm.llm.LLMProviderType.SiliconFlow
:value: >
   'siliconflow'

```{autodoc2-docstring} agentsociety.llm.llm.LLMProviderType.SiliconFlow
```

````

````{py:attribute} VolcEngine
:canonical: agentsociety.llm.llm.LLMProviderType.VolcEngine
:value: >
   'volcengine'

```{autodoc2-docstring} agentsociety.llm.llm.LLMProviderType.VolcEngine
```

````

````{py:attribute} VLLM
:canonical: agentsociety.llm.llm.LLMProviderType.VLLM
:value: >
   'vllm'

```{autodoc2-docstring} agentsociety.llm.llm.LLMProviderType.VLLM
```

````

`````

`````{py:class} LLMConfig(/, **data: typing.Any)
:canonical: agentsociety.llm.llm.LLMConfig

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.llm.llm.LLMConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.llm.llm.LLMConfig.__init__
```

````{py:attribute} provider
:canonical: agentsociety.llm.llm.LLMConfig.provider
:type: agentsociety.llm.llm.LLMProviderType
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.llm.llm.LLMConfig.provider
```

````

````{py:attribute} base_url
:canonical: agentsociety.llm.llm.LLMConfig.base_url
:type: typing.Optional[str]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.llm.llm.LLMConfig.base_url
```

````

````{py:attribute} api_key
:canonical: agentsociety.llm.llm.LLMConfig.api_key
:type: str
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.llm.llm.LLMConfig.api_key
```

````

````{py:attribute} model
:canonical: agentsociety.llm.llm.LLMConfig.model
:type: str
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.llm.llm.LLMConfig.model
```

````

````{py:attribute} concurrency
:canonical: agentsociety.llm.llm.LLMConfig.concurrency
:type: int
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.llm.llm.LLMConfig.concurrency
```

````

````{py:attribute} timeout
:canonical: agentsociety.llm.llm.LLMConfig.timeout
:type: float
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.llm.llm.LLMConfig.timeout
```

````

````{py:method} serialize_provider(provider: agentsociety.llm.llm.LLMProviderType, info)
:canonical: agentsociety.llm.llm.LLMConfig.serialize_provider

```{autodoc2-docstring} agentsociety.llm.llm.LLMConfig.serialize_provider
```

````

````{py:method} validate_configuration()
:canonical: agentsociety.llm.llm.LLMConfig.validate_configuration

```{autodoc2-docstring} agentsociety.llm.llm.LLMConfig.validate_configuration
```

````

`````

`````{py:class} LLMActor()
:canonical: agentsociety.llm.llm.LLMActor

```{autodoc2-docstring} agentsociety.llm.llm.LLMActor
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.llm.llm.LLMActor.__init__
```

````{py:method} call(config: agentsociety.llm.llm.LLMConfig, dialog: list[openai.types.chat.ChatCompletionMessageParam], response_format: typing.Union[openai.types.chat.completion_create_params.ResponseFormat, openai.NotGiven] = NOT_GIVEN, temperature: float = 1, max_tokens: typing.Optional[int] = None, top_p: typing.Optional[float] = None, frequency_penalty: typing.Optional[float] = None, presence_penalty: typing.Optional[float] = None, timeout: int = 300, retries: int = 10, tools: typing.Union[typing.List[openai.types.chat.ChatCompletionToolParam], openai.NotGiven] = NOT_GIVEN, tool_choice: typing.Union[openai.types.chat.ChatCompletionToolChoiceOptionParam, openai.NotGiven] = NOT_GIVEN)
:canonical: agentsociety.llm.llm.LLMActor.call
:async:

```{autodoc2-docstring} agentsociety.llm.llm.LLMActor.call
```

````

`````

`````{py:class} LLM(configs: typing.List[agentsociety.llm.llm.LLMConfig], num_actors: int = min(cpu_count(), 8))
:canonical: agentsociety.llm.llm.LLM

```{autodoc2-docstring} agentsociety.llm.llm.LLM
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.llm.llm.LLM.__init__
```

````{py:method} get_log_list()
:canonical: agentsociety.llm.llm.LLM.get_log_list

```{autodoc2-docstring} agentsociety.llm.llm.LLM.get_log_list
```

````

````{py:method} clear_log_list()
:canonical: agentsociety.llm.llm.LLM.clear_log_list

```{autodoc2-docstring} agentsociety.llm.llm.LLM.clear_log_list
```

````

````{py:method} _get_index()
:canonical: agentsociety.llm.llm.LLM._get_index

```{autodoc2-docstring} agentsociety.llm.llm.LLM._get_index
```

````

````{py:method} atext_request(dialog: list[openai.types.chat.ChatCompletionMessageParam], response_format: typing.Union[openai.types.chat.completion_create_params.ResponseFormat, openai.NotGiven] = NOT_GIVEN, temperature: float = 1, max_tokens: typing.Optional[int] = None, top_p: typing.Optional[float] = None, frequency_penalty: typing.Optional[float] = None, presence_penalty: typing.Optional[float] = None, timeout: int = 300, retries: int = 10, tools: typing.Union[typing.List[openai.types.chat.ChatCompletionToolParam], openai.NotGiven] = NOT_GIVEN, tool_choice: typing.Union[openai.types.chat.ChatCompletionToolChoiceOptionParam, openai.NotGiven] = NOT_GIVEN)
:canonical: agentsociety.llm.llm.LLM.atext_request
:async:

```{autodoc2-docstring} agentsociety.llm.llm.LLM.atext_request
```

````

`````
