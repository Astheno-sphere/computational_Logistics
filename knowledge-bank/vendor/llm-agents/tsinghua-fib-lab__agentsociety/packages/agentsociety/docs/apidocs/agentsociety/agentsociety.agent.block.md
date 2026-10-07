# {py:mod}`agentsociety.agent.block`

```{py:module} agentsociety.agent.block
```

```{autodoc2-docstring} agentsociety.agent.block
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`BlockParams <agentsociety.agent.block.BlockParams>`
  -
* - {py:obj}`BlockOutput <agentsociety.agent.block.BlockOutput>`
  -
* - {py:obj}`Block <agentsociety.agent.block.Block>`
  - ```{autodoc2-docstring} agentsociety.agent.block.Block
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`TRIGGER_INTERVAL <agentsociety.agent.block.TRIGGER_INTERVAL>`
  - ```{autodoc2-docstring} agentsociety.agent.block.TRIGGER_INTERVAL
    :summary:
    ```
* - {py:obj}`__all__ <agentsociety.agent.block.__all__>`
  - ```{autodoc2-docstring} agentsociety.agent.block.__all__
    :summary:
    ```
````

### API

````{py:data} TRIGGER_INTERVAL
:canonical: agentsociety.agent.block.TRIGGER_INTERVAL
:value: >
   1

```{autodoc2-docstring} agentsociety.agent.block.TRIGGER_INTERVAL
```

````

````{py:data} __all__
:canonical: agentsociety.agent.block.__all__
:value: >
   ['Block', 'BlockParams', 'BlockOutput']

```{autodoc2-docstring} agentsociety.agent.block.__all__
```

````

`````{py:class} BlockParams(/, **data: typing.Any)
:canonical: agentsociety.agent.block.BlockParams

Bases: {py:obj}`pydantic.BaseModel`

````{py:attribute} block_memory
:canonical: agentsociety.agent.block.BlockParams.block_memory
:type: typing.Optional[dict[str, typing.Any]]
:value: >
   None

```{autodoc2-docstring} agentsociety.agent.block.BlockParams.block_memory
```

````

`````

```{py:class} BlockOutput(/, **data: typing.Any)
:canonical: agentsociety.agent.block.BlockOutput

Bases: {py:obj}`pydantic.BaseModel`

```

`````{py:class} Block(toolbox: agentsociety.agent.toolbox.AgentToolbox, agent_memory: typing.Optional[agentsociety.memory.Memory] = None, block_params: typing.Optional[typing.Any] = None)
:canonical: agentsociety.agent.block.Block

```{autodoc2-docstring} agentsociety.agent.block.Block
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.agent.block.Block.__init__
```

````{py:attribute} ParamsType
:canonical: agentsociety.agent.block.Block.ParamsType
:value: >
   None

```{autodoc2-docstring} agentsociety.agent.block.Block.ParamsType
```

````

````{py:attribute} Context
:canonical: agentsociety.agent.block.Block.Context
:value: >
   None

```{autodoc2-docstring} agentsociety.agent.block.Block.Context
```

````

````{py:attribute} OutputType
:canonical: agentsociety.agent.block.Block.OutputType
:value: >
   None

```{autodoc2-docstring} agentsociety.agent.block.Block.OutputType
```

````

````{py:attribute} NeedAgent
:canonical: agentsociety.agent.block.Block.NeedAgent
:type: bool
:value: >
   False

```{autodoc2-docstring} agentsociety.agent.block.Block.NeedAgent
```

````

````{py:attribute} name
:canonical: agentsociety.agent.block.Block.name
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.agent.block.Block.name
```

````

````{py:attribute} description
:canonical: agentsociety.agent.block.Block.description
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.agent.block.Block.description
```

````

````{py:attribute} actions
:canonical: agentsociety.agent.block.Block.actions
:type: dict[str, str]
:value: >
   None

```{autodoc2-docstring} agentsociety.agent.block.Block.actions
```

````

````{py:method} default_params() -> ParamsType
:canonical: agentsociety.agent.block.Block.default_params
:classmethod:

```{autodoc2-docstring} agentsociety.agent.block.Block.default_params
```

````

````{py:method} default_context() -> Context
:canonical: agentsociety.agent.block.Block.default_context
:classmethod:

```{autodoc2-docstring} agentsociety.agent.block.Block.default_context
```

````

````{py:method} __init_subclass__(**kwargs)
:canonical: agentsociety.agent.block.Block.__init_subclass__
:classmethod:

```{autodoc2-docstring} agentsociety.agent.block.Block.__init_subclass__
```

````

````{py:method} set_agent(agent: typing.Any)
:canonical: agentsociety.agent.block.Block.set_agent

```{autodoc2-docstring} agentsociety.agent.block.Block.set_agent
```

````

````{py:property} agent
:canonical: agentsociety.agent.block.Block.agent
:type: typing.Any

```{autodoc2-docstring} agentsociety.agent.block.Block.agent
```

````

````{py:property} toolbox
:canonical: agentsociety.agent.block.Block.toolbox
:type: agentsociety.agent.toolbox.AgentToolbox

```{autodoc2-docstring} agentsociety.agent.block.Block.toolbox
```

````

````{py:property} llm
:canonical: agentsociety.agent.block.Block.llm
:type: agentsociety.llm.LLM

```{autodoc2-docstring} agentsociety.agent.block.Block.llm
```

````

````{py:property} memory
:canonical: agentsociety.agent.block.Block.memory
:type: agentsociety.memory.Memory

```{autodoc2-docstring} agentsociety.agent.block.Block.memory
```

````

````{py:property} agent_memory
:canonical: agentsociety.agent.block.Block.agent_memory
:type: agentsociety.memory.Memory

```{autodoc2-docstring} agentsociety.agent.block.Block.agent_memory
```

````

````{py:property} block_memory
:canonical: agentsociety.agent.block.Block.block_memory
:type: agentsociety.memory.KVMemory

```{autodoc2-docstring} agentsociety.agent.block.Block.block_memory
```

````

````{py:property} environment
:canonical: agentsociety.agent.block.Block.environment
:type: agentsociety.environment.Environment

```{autodoc2-docstring} agentsociety.agent.block.Block.environment
```

````

````{py:method} before_forward()
:canonical: agentsociety.agent.block.Block.before_forward
:async:

```{autodoc2-docstring} agentsociety.agent.block.Block.before_forward
```

````

````{py:method} after_forward()
:canonical: agentsociety.agent.block.Block.after_forward
:async:

```{autodoc2-docstring} agentsociety.agent.block.Block.after_forward
```

````

````{py:method} forward(agent_context: agentsociety.agent.context.DotDict)
:canonical: agentsociety.agent.block.Block.forward
:abstractmethod:
:async:

```{autodoc2-docstring} agentsociety.agent.block.Block.forward
```

````

`````
