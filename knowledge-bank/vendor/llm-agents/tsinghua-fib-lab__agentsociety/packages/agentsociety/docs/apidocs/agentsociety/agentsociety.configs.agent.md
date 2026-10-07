# {py:mod}`agentsociety.configs.agent`

```{py:module} agentsociety.configs.agent
```

```{autodoc2-docstring} agentsociety.configs.agent
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`InstitutionAgentClass <agentsociety.configs.agent.InstitutionAgentClass>`
  - ```{autodoc2-docstring} agentsociety.configs.agent.InstitutionAgentClass
    :summary:
    ```
* - {py:obj}`AgentConfig <agentsociety.configs.agent.AgentConfig>`
  - ```{autodoc2-docstring} agentsociety.configs.agent.AgentConfig
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.configs.agent.__all__>`
  - ```{autodoc2-docstring} agentsociety.configs.agent.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.configs.agent.__all__
:value: >
   ['AgentConfig']

```{autodoc2-docstring} agentsociety.configs.agent.__all__
```

````

`````{py:class} InstitutionAgentClass()
:canonical: agentsociety.configs.agent.InstitutionAgentClass

Bases: {py:obj}`str`, {py:obj}`enum.Enum`

```{autodoc2-docstring} agentsociety.configs.agent.InstitutionAgentClass
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.configs.agent.InstitutionAgentClass.__init__
```

````{py:attribute} FIRM
:canonical: agentsociety.configs.agent.InstitutionAgentClass.FIRM
:value: >
   'firm'

```{autodoc2-docstring} agentsociety.configs.agent.InstitutionAgentClass.FIRM
```

````

````{py:attribute} GOVERNMENT
:canonical: agentsociety.configs.agent.InstitutionAgentClass.GOVERNMENT
:value: >
   'government'

```{autodoc2-docstring} agentsociety.configs.agent.InstitutionAgentClass.GOVERNMENT
```

````

````{py:attribute} BANK
:canonical: agentsociety.configs.agent.InstitutionAgentClass.BANK
:value: >
   'bank'

```{autodoc2-docstring} agentsociety.configs.agent.InstitutionAgentClass.BANK
```

````

````{py:attribute} NBS
:canonical: agentsociety.configs.agent.InstitutionAgentClass.NBS
:value: >
   'nbs'

```{autodoc2-docstring} agentsociety.configs.agent.InstitutionAgentClass.NBS
```

````

`````

`````{py:class} AgentConfig(/, **data: typing.Any)
:canonical: agentsociety.configs.agent.AgentConfig

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.configs.agent.AgentConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.configs.agent.AgentConfig.__init__
```

````{py:attribute} model_config
:canonical: agentsociety.configs.agent.AgentConfig.model_config
:value: >
   'ConfigDict(...)'

```{autodoc2-docstring} agentsociety.configs.agent.AgentConfig.model_config
```

````

````{py:attribute} agent_class
:canonical: agentsociety.configs.agent.AgentConfig.agent_class
:type: typing.Union[type[agentsociety.agent.Agent], str]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.agent.AgentConfig.agent_class
```

````

````{py:attribute} number
:canonical: agentsociety.configs.agent.AgentConfig.number
:type: int
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.agent.AgentConfig.number
```

````

````{py:attribute} agent_params
:canonical: agentsociety.configs.agent.AgentConfig.agent_params
:type: typing.Optional[typing.Any]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.agent.AgentConfig.agent_params
```

````

````{py:attribute} blocks
:canonical: agentsociety.configs.agent.AgentConfig.blocks
:type: typing.Optional[dict[typing.Union[type[agentsociety.agent.Block], str], typing.Any]]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.agent.AgentConfig.blocks
```

````

````{py:attribute} tools
:canonical: agentsociety.configs.agent.AgentConfig.tools
:type: typing.Optional[list[agentsociety.agent.CustomTool]]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.agent.AgentConfig.tools
```

````

````{py:attribute} memory_config_func
:canonical: agentsociety.configs.agent.AgentConfig.memory_config_func
:type: typing.Optional[collections.abc.Callable]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.agent.AgentConfig.memory_config_func
```

````

````{py:attribute} memory_from_file
:canonical: agentsociety.configs.agent.AgentConfig.memory_from_file
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.agent.AgentConfig.memory_from_file
```

````

````{py:attribute} memory_distributions
:canonical: agentsociety.configs.agent.AgentConfig.memory_distributions
:type: typing.Optional[dict[str, typing.Union[agentsociety.agent.distribution.Distribution, agentsociety.agent.distribution.DistributionConfig]]]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.agent.AgentConfig.memory_distributions
```

````

````{py:method} validate_configuration()
:canonical: agentsociety.configs.agent.AgentConfig.validate_configuration

```{autodoc2-docstring} agentsociety.configs.agent.AgentConfig.validate_configuration
```

````

````{py:method} serialize_agent_class(agent_class, info)
:canonical: agentsociety.configs.agent.AgentConfig.serialize_agent_class

```{autodoc2-docstring} agentsociety.configs.agent.AgentConfig.serialize_agent_class
```

````

````{py:method} serialize_memory_config_func(memory_config_func, info)
:canonical: agentsociety.configs.agent.AgentConfig.serialize_memory_config_func

```{autodoc2-docstring} agentsociety.configs.agent.AgentConfig.serialize_memory_config_func
```

````

````{py:method} serialize_memory_distributions(memory_distributions, info)
:canonical: agentsociety.configs.agent.AgentConfig.serialize_memory_distributions

```{autodoc2-docstring} agentsociety.configs.agent.AgentConfig.serialize_memory_distributions
```

````

`````
