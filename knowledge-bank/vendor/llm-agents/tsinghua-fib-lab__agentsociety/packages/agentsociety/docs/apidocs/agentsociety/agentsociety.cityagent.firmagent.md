# {py:mod}`agentsociety.cityagent.firmagent`

```{py:module} agentsociety.cityagent.firmagent
```

```{autodoc2-docstring} agentsociety.cityagent.firmagent
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`FirmAgentConfig <agentsociety.cityagent.firmagent.FirmAgentConfig>`
  - ```{autodoc2-docstring} agentsociety.cityagent.firmagent.FirmAgentConfig
    :summary:
    ```
* - {py:obj}`FirmAgent <agentsociety.cityagent.firmagent.FirmAgent>`
  - ```{autodoc2-docstring} agentsociety.cityagent.firmagent.FirmAgent
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.cityagent.firmagent.__all__>`
  - ```{autodoc2-docstring} agentsociety.cityagent.firmagent.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.cityagent.firmagent.__all__
:value: >
   ['FirmAgent']

```{autodoc2-docstring} agentsociety.cityagent.firmagent.__all__
```

````

`````{py:class} FirmAgentConfig(/, **data: typing.Any)
:canonical: agentsociety.cityagent.firmagent.FirmAgentConfig

Bases: {py:obj}`agentsociety.agent.AgentParams`

```{autodoc2-docstring} agentsociety.cityagent.firmagent.FirmAgentConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.firmagent.FirmAgentConfig.__init__
```

````{py:attribute} time_diff
:canonical: agentsociety.cityagent.firmagent.FirmAgentConfig.time_diff
:type: int
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.cityagent.firmagent.FirmAgentConfig.time_diff
```

````

````{py:attribute} max_price_inflation
:canonical: agentsociety.cityagent.firmagent.FirmAgentConfig.max_price_inflation
:type: float
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.cityagent.firmagent.FirmAgentConfig.max_price_inflation
```

````

````{py:attribute} max_wage_inflation
:canonical: agentsociety.cityagent.firmagent.FirmAgentConfig.max_wage_inflation
:type: float
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.cityagent.firmagent.FirmAgentConfig.max_wage_inflation
```

````

`````

`````{py:class} FirmAgent(id: int, name: str, toolbox: agentsociety.agent.AgentToolbox, memory: agentsociety.memory.Memory, agent_params: typing.Optional[agentsociety.cityagent.firmagent.FirmAgentConfig] = None, blocks: typing.Optional[list[agentsociety.agent.Block]] = None)
:canonical: agentsociety.cityagent.firmagent.FirmAgent

Bases: {py:obj}`agentsociety.agent.FirmAgentBase`

```{autodoc2-docstring} agentsociety.cityagent.firmagent.FirmAgent
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.firmagent.FirmAgent.__init__
```

````{py:attribute} ParamsType
:canonical: agentsociety.cityagent.firmagent.FirmAgent.ParamsType
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.firmagent.FirmAgent.ParamsType
```

````

````{py:attribute} description
:canonical: agentsociety.cityagent.firmagent.FirmAgent.description
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.cityagent.firmagent.FirmAgent.description
```

````

````{py:method} reset()
:canonical: agentsociety.cityagent.firmagent.FirmAgent.reset
:async:

```{autodoc2-docstring} agentsociety.cityagent.firmagent.FirmAgent.reset
```

````

````{py:method} month_trigger()
:canonical: agentsociety.cityagent.firmagent.FirmAgent.month_trigger
:async:

```{autodoc2-docstring} agentsociety.cityagent.firmagent.FirmAgent.month_trigger
```

````

````{py:method} forward()
:canonical: agentsociety.cityagent.firmagent.FirmAgent.forward
:async:

```{autodoc2-docstring} agentsociety.cityagent.firmagent.FirmAgent.forward
```

````

`````
