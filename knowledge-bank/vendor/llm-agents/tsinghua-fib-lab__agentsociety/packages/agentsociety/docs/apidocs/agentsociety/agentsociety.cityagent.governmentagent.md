# {py:mod}`agentsociety.cityagent.governmentagent`

```{py:module} agentsociety.cityagent.governmentagent
```

```{autodoc2-docstring} agentsociety.cityagent.governmentagent
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`GovernmentAgentConfig <agentsociety.cityagent.governmentagent.GovernmentAgentConfig>`
  - ```{autodoc2-docstring} agentsociety.cityagent.governmentagent.GovernmentAgentConfig
    :summary:
    ```
* - {py:obj}`GovernmentAgent <agentsociety.cityagent.governmentagent.GovernmentAgent>`
  - ```{autodoc2-docstring} agentsociety.cityagent.governmentagent.GovernmentAgent
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.cityagent.governmentagent.__all__>`
  - ```{autodoc2-docstring} agentsociety.cityagent.governmentagent.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.cityagent.governmentagent.__all__
:value: >
   ['GovernmentAgent']

```{autodoc2-docstring} agentsociety.cityagent.governmentagent.__all__
```

````

`````{py:class} GovernmentAgentConfig(/, **data: typing.Any)
:canonical: agentsociety.cityagent.governmentagent.GovernmentAgentConfig

Bases: {py:obj}`agentsociety.agent.AgentParams`

```{autodoc2-docstring} agentsociety.cityagent.governmentagent.GovernmentAgentConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.governmentagent.GovernmentAgentConfig.__init__
```

````{py:attribute} time_diff
:canonical: agentsociety.cityagent.governmentagent.GovernmentAgentConfig.time_diff
:type: int
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.cityagent.governmentagent.GovernmentAgentConfig.time_diff
```

````

`````

`````{py:class} GovernmentAgent(id: int, name: str, toolbox: agentsociety.agent.AgentToolbox, memory: agentsociety.memory.Memory, agent_params: typing.Optional[agentsociety.cityagent.governmentagent.GovernmentAgentConfig] = None, blocks: typing.Optional[list[agentsociety.agent.Block]] = None)
:canonical: agentsociety.cityagent.governmentagent.GovernmentAgent

Bases: {py:obj}`agentsociety.agent.GovernmentAgentBase`

```{autodoc2-docstring} agentsociety.cityagent.governmentagent.GovernmentAgent
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.governmentagent.GovernmentAgent.__init__
```

````{py:attribute} ParamsType
:canonical: agentsociety.cityagent.governmentagent.GovernmentAgent.ParamsType
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.governmentagent.GovernmentAgent.ParamsType
```

````

````{py:attribute} description
:canonical: agentsociety.cityagent.governmentagent.GovernmentAgent.description
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.cityagent.governmentagent.GovernmentAgent.description
```

````

````{py:method} reset()
:canonical: agentsociety.cityagent.governmentagent.GovernmentAgent.reset
:async:

```{autodoc2-docstring} agentsociety.cityagent.governmentagent.GovernmentAgent.reset
```

````

````{py:method} month_trigger()
:canonical: agentsociety.cityagent.governmentagent.GovernmentAgent.month_trigger
:async:

```{autodoc2-docstring} agentsociety.cityagent.governmentagent.GovernmentAgent.month_trigger
```

````

````{py:method} forward()
:canonical: agentsociety.cityagent.governmentagent.GovernmentAgent.forward
:async:

```{autodoc2-docstring} agentsociety.cityagent.governmentagent.GovernmentAgent.forward
```

````

`````
