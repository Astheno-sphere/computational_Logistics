# {py:mod}`agentsociety.cityagent.nbsagent`

```{py:module} agentsociety.cityagent.nbsagent
```

```{autodoc2-docstring} agentsociety.cityagent.nbsagent
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`NBSAgentConfig <agentsociety.cityagent.nbsagent.NBSAgentConfig>`
  - ```{autodoc2-docstring} agentsociety.cityagent.nbsagent.NBSAgentConfig
    :summary:
    ```
* - {py:obj}`NBSAgent <agentsociety.cityagent.nbsagent.NBSAgent>`
  - ```{autodoc2-docstring} agentsociety.cityagent.nbsagent.NBSAgent
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.cityagent.nbsagent.__all__>`
  - ```{autodoc2-docstring} agentsociety.cityagent.nbsagent.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.cityagent.nbsagent.__all__
:value: >
   ['NBSAgent']

```{autodoc2-docstring} agentsociety.cityagent.nbsagent.__all__
```

````

`````{py:class} NBSAgentConfig(/, **data: typing.Any)
:canonical: agentsociety.cityagent.nbsagent.NBSAgentConfig

Bases: {py:obj}`agentsociety.agent.AgentParams`

```{autodoc2-docstring} agentsociety.cityagent.nbsagent.NBSAgentConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.nbsagent.NBSAgentConfig.__init__
```

````{py:attribute} time_diff
:canonical: agentsociety.cityagent.nbsagent.NBSAgentConfig.time_diff
:type: int
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.cityagent.nbsagent.NBSAgentConfig.time_diff
```

````

````{py:attribute} num_labor_hours
:canonical: agentsociety.cityagent.nbsagent.NBSAgentConfig.num_labor_hours
:type: int
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.cityagent.nbsagent.NBSAgentConfig.num_labor_hours
```

````

````{py:attribute} productivity_per_labor
:canonical: agentsociety.cityagent.nbsagent.NBSAgentConfig.productivity_per_labor
:type: float
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.cityagent.nbsagent.NBSAgentConfig.productivity_per_labor
```

````

`````

`````{py:class} NBSAgent(id: int, name: str, toolbox: agentsociety.agent.AgentToolbox, memory: agentsociety.memory.Memory, agent_params: typing.Optional[agentsociety.cityagent.nbsagent.NBSAgentConfig] = None, blocks: typing.Optional[list[agentsociety.agent.block.Block]] = None)
:canonical: agentsociety.cityagent.nbsagent.NBSAgent

Bases: {py:obj}`agentsociety.agent.NBSAgentBase`

```{autodoc2-docstring} agentsociety.cityagent.nbsagent.NBSAgent
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.nbsagent.NBSAgent.__init__
```

````{py:attribute} ParamsType
:canonical: agentsociety.cityagent.nbsagent.NBSAgent.ParamsType
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.nbsagent.NBSAgent.ParamsType
```

````

````{py:attribute} description
:canonical: agentsociety.cityagent.nbsagent.NBSAgent.description
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.cityagent.nbsagent.NBSAgent.description
```

````

````{py:method} reset()
:canonical: agentsociety.cityagent.nbsagent.NBSAgent.reset
:async:

```{autodoc2-docstring} agentsociety.cityagent.nbsagent.NBSAgent.reset
```

````

````{py:method} month_trigger()
:canonical: agentsociety.cityagent.nbsagent.NBSAgent.month_trigger
:async:

```{autodoc2-docstring} agentsociety.cityagent.nbsagent.NBSAgent.month_trigger
```

````

````{py:method} forward()
:canonical: agentsociety.cityagent.nbsagent.NBSAgent.forward
:async:

```{autodoc2-docstring} agentsociety.cityagent.nbsagent.NBSAgent.forward
```

````

`````
