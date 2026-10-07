# {py:mod}`agentsociety.agent.agent_base`

```{py:module} agentsociety.agent.agent_base
```

```{autodoc2-docstring} agentsociety.agent.agent_base
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`AgentParams <agentsociety.agent.agent_base.AgentParams>`
  - ```{autodoc2-docstring} agentsociety.agent.agent_base.AgentParams
    :summary:
    ```
* - {py:obj}`GatherQuery <agentsociety.agent.agent_base.GatherQuery>`
  - ```{autodoc2-docstring} agentsociety.agent.agent_base.GatherQuery
    :summary:
    ```
* - {py:obj}`AgentType <agentsociety.agent.agent_base.AgentType>`
  - ```{autodoc2-docstring} agentsociety.agent.agent_base.AgentType
    :summary:
    ```
* - {py:obj}`Agent <agentsociety.agent.agent_base.Agent>`
  - ```{autodoc2-docstring} agentsociety.agent.agent_base.Agent
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`extract_json <agentsociety.agent.agent_base.extract_json>`
  - ```{autodoc2-docstring} agentsociety.agent.agent_base.extract_json
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.agent.agent_base.__all__>`
  - ```{autodoc2-docstring} agentsociety.agent.agent_base.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.agent.agent_base.__all__
:value: >
   ['Agent', 'AgentType', 'AgentParams', 'GatherQuery']

```{autodoc2-docstring} agentsociety.agent.agent_base.__all__
```

````

````{py:class} AgentParams(/, **data: typing.Any)
:canonical: agentsociety.agent.agent_base.AgentParams

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.agent.agent_base.AgentParams
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.agent.agent_base.AgentParams.__init__
```

````

`````{py:class} GatherQuery(/, **data: typing.Any)
:canonical: agentsociety.agent.agent_base.GatherQuery

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.agent.agent_base.GatherQuery
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.agent.agent_base.GatherQuery.__init__
```

````{py:attribute} key
:canonical: agentsociety.agent.agent_base.GatherQuery.key
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.agent.agent_base.GatherQuery.key
```

````

````{py:attribute} target_agent_ids
:canonical: agentsociety.agent.agent_base.GatherQuery.target_agent_ids
:type: list[int]
:value: >
   None

```{autodoc2-docstring} agentsociety.agent.agent_base.GatherQuery.target_agent_ids
```

````

````{py:attribute} flatten
:canonical: agentsociety.agent.agent_base.GatherQuery.flatten
:type: bool
:value: >
   True

```{autodoc2-docstring} agentsociety.agent.agent_base.GatherQuery.flatten
```

````

````{py:attribute} keep_id
:canonical: agentsociety.agent.agent_base.GatherQuery.keep_id
:type: bool
:value: >
   True

```{autodoc2-docstring} agentsociety.agent.agent_base.GatherQuery.keep_id
```

````

`````

`````{py:class} AgentType(*args, **kwds)
:canonical: agentsociety.agent.agent_base.AgentType

Bases: {py:obj}`enum.Enum`

```{autodoc2-docstring} agentsociety.agent.agent_base.AgentType
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.agent.agent_base.AgentType.__init__
```

````{py:attribute} Unspecified
:canonical: agentsociety.agent.agent_base.AgentType.Unspecified
:value: >
   'Unspecified'

```{autodoc2-docstring} agentsociety.agent.agent_base.AgentType.Unspecified
```

````

````{py:attribute} Citizen
:canonical: agentsociety.agent.agent_base.AgentType.Citizen
:value: >
   'Citizen'

```{autodoc2-docstring} agentsociety.agent.agent_base.AgentType.Citizen
```

````

````{py:attribute} Institution
:canonical: agentsociety.agent.agent_base.AgentType.Institution
:value: >
   'Institution'

```{autodoc2-docstring} agentsociety.agent.agent_base.AgentType.Institution
```

````

````{py:attribute} Supervisor
:canonical: agentsociety.agent.agent_base.AgentType.Supervisor
:value: >
   'Supervisor'

```{autodoc2-docstring} agentsociety.agent.agent_base.AgentType.Supervisor
```

````

````{py:attribute} Individual
:canonical: agentsociety.agent.agent_base.AgentType.Individual
:value: >
   'Individual'

```{autodoc2-docstring} agentsociety.agent.agent_base.AgentType.Individual
```

````

`````

````{py:function} extract_json(output_str)
:canonical: agentsociety.agent.agent_base.extract_json

```{autodoc2-docstring} agentsociety.agent.agent_base.extract_json
```
````

`````{py:class} Agent(id: int, name: str, type: agentsociety.agent.agent_base.AgentType, toolbox: agentsociety.agent.toolbox.AgentToolbox, memory: agentsociety.memory.Memory, agent_params: typing.Optional[typing.Any] = None, blocks: typing.Optional[list[agentsociety.agent.block.Block]] = None)
:canonical: agentsociety.agent.agent_base.Agent

Bases: {py:obj}`abc.ABC`

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.__init__
```

````{py:attribute} ParamsType
:canonical: agentsociety.agent.agent_base.Agent.ParamsType
:type: type[agentsociety.agent.agent_base.AgentParams]
:value: >
   None

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.ParamsType
```

````

````{py:attribute} Context
:canonical: agentsociety.agent.agent_base.Agent.Context
:type: type[agentsociety.agent.context.AgentContext]
:value: >
   None

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.Context
```

````

````{py:attribute} BlockOutputType
:canonical: agentsociety.agent.agent_base.Agent.BlockOutputType
:type: type[agentsociety.agent.block.BlockOutput]
:value: >
   None

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.BlockOutputType
```

````

````{py:attribute} StatusAttributes
:canonical: agentsociety.agent.agent_base.Agent.StatusAttributes
:type: list[agentsociety.agent.memory_config_generator.MemoryAttribute]
:value: >
   []

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.StatusAttributes
```

````

````{py:attribute} description
:canonical: agentsociety.agent.agent_base.Agent.description
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.description
```

````

````{py:method} default_params()
:canonical: agentsociety.agent.agent_base.Agent.default_params
:classmethod:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.default_params
```

````

````{py:method} default_context()
:canonical: agentsociety.agent.agent_base.Agent.default_context
:classmethod:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.default_context
```

````

````{py:method} __init_subclass__(**kwargs)
:canonical: agentsociety.agent.agent_base.Agent.__init_subclass__
:classmethod:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.__init_subclass__
```

````

````{py:method} init()
:canonical: agentsociety.agent.agent_base.Agent.init
:async:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.init
```

````

````{py:method} __getstate__()
:canonical: agentsociety.agent.agent_base.Agent.__getstate__

````

````{py:property} id
:canonical: agentsociety.agent.agent_base.Agent.id

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.id
```

````

````{py:property} toolbox
:canonical: agentsociety.agent.agent_base.Agent.toolbox

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.toolbox
```

````

````{py:property} llm
:canonical: agentsociety.agent.agent_base.Agent.llm

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.llm
```

````

````{py:property} environment
:canonical: agentsociety.agent.agent_base.Agent.environment

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.environment
```

````

````{py:property} messager
:canonical: agentsociety.agent.agent_base.Agent.messager

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.messager
```

````

````{py:property} database_writer
:canonical: agentsociety.agent.agent_base.Agent.database_writer

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.database_writer
```

````

````{py:property} memory
:canonical: agentsociety.agent.agent_base.Agent.memory

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.memory
```

````

````{py:property} status
:canonical: agentsociety.agent.agent_base.Agent.status

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.status
```

````

````{py:property} stream
:canonical: agentsociety.agent.agent_base.Agent.stream

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.stream
```

````

````{py:method} reset()
:canonical: agentsociety.agent.agent_base.Agent.reset
:abstractmethod:
:async:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.reset
```

````

````{py:method} react_to_intervention(intervention_message: str)
:canonical: agentsociety.agent.agent_base.Agent.react_to_intervention
:abstractmethod:
:async:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.react_to_intervention
```

````

````{py:method} send_message_to_agent(to_agent_id: int, content: str, type: str = 'social')
:canonical: agentsociety.agent.agent_base.Agent.send_message_to_agent
:async:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.send_message_to_agent
```

````

````{py:method} _get_gather_query_and_clear()
:canonical: agentsociety.agent.agent_base.Agent._get_gather_query_and_clear

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent._get_gather_query_and_clear
```

````

````{py:method} register_gather_query(key: str, target_agent_ids: list[int], flatten: bool = True, keep_id: bool = True)
:canonical: agentsociety.agent.agent_base.Agent.register_gather_query

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.register_gather_query
```

````

````{py:method} get_gather_results(key: str) -> typing.Optional[list[typing.Any] | dict[int, typing.Any]]
:canonical: agentsociety.agent.agent_base.Agent.get_gather_results

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.get_gather_results
```

````

````{py:method} register_aoi_message(target_aoi: typing.Union[int, list[int]], content: str)
:canonical: agentsociety.agent.agent_base.Agent.register_aoi_message
:async:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.register_aoi_message
```

````

````{py:method} cancel_aoi_message(target_aoi: typing.Union[int, list[int]])
:canonical: agentsociety.agent.agent_base.Agent.cancel_aoi_message
:async:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.cancel_aoi_message
```

````

````{py:method} forward() -> typing.Any
:canonical: agentsociety.agent.agent_base.Agent.forward
:abstractmethod:
:async:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.forward
```

````

````{py:method} status_summary()
:canonical: agentsociety.agent.agent_base.Agent.status_summary
:async:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.status_summary
```

````

````{py:method} close()
:canonical: agentsociety.agent.agent_base.Agent.close
:async:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.close
```

````

````{py:method} before_forward()
:canonical: agentsociety.agent.agent_base.Agent.before_forward
:async:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.before_forward
```

````

````{py:method} after_forward()
:canonical: agentsociety.agent.agent_base.Agent.after_forward
:async:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.after_forward
```

````

````{py:method} before_blocks()
:canonical: agentsociety.agent.agent_base.Agent.before_blocks
:async:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.before_blocks
```

````

````{py:method} after_blocks()
:canonical: agentsociety.agent.agent_base.Agent.after_blocks
:async:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.after_blocks
```

````

````{py:method} run() -> typing.Any
:canonical: agentsociety.agent.agent_base.Agent.run
:async:

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent.run
```

````

````{py:method} _is_output_type_compatible(block_output_type) -> bool
:canonical: agentsociety.agent.agent_base.Agent._is_output_type_compatible

```{autodoc2-docstring} agentsociety.agent.agent_base.Agent._is_output_type_compatible
```

````

`````
