# {py:mod}`agentsociety.cityagent.bankagent`

```{py:module} agentsociety.cityagent.bankagent
```

```{autodoc2-docstring} agentsociety.cityagent.bankagent
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`BankAgentConfig <agentsociety.cityagent.bankagent.BankAgentConfig>`
  - ```{autodoc2-docstring} agentsociety.cityagent.bankagent.BankAgentConfig
    :summary:
    ```
* - {py:obj}`BankAgent <agentsociety.cityagent.bankagent.BankAgent>`
  - ```{autodoc2-docstring} agentsociety.cityagent.bankagent.BankAgent
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`calculate_inflation <agentsociety.cityagent.bankagent.calculate_inflation>`
  - ```{autodoc2-docstring} agentsociety.cityagent.bankagent.calculate_inflation
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.cityagent.bankagent.__all__>`
  - ```{autodoc2-docstring} agentsociety.cityagent.bankagent.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.cityagent.bankagent.__all__
:value: >
   ['BankAgent']

```{autodoc2-docstring} agentsociety.cityagent.bankagent.__all__
```

````

````{py:function} calculate_inflation(prices)
:canonical: agentsociety.cityagent.bankagent.calculate_inflation

```{autodoc2-docstring} agentsociety.cityagent.bankagent.calculate_inflation
```
````

`````{py:class} BankAgentConfig(/, **data: typing.Any)
:canonical: agentsociety.cityagent.bankagent.BankAgentConfig

Bases: {py:obj}`agentsociety.agent.AgentParams`

```{autodoc2-docstring} agentsociety.cityagent.bankagent.BankAgentConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.bankagent.BankAgentConfig.__init__
```

````{py:attribute} time_diff
:canonical: agentsociety.cityagent.bankagent.BankAgentConfig.time_diff
:type: int
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.cityagent.bankagent.BankAgentConfig.time_diff
```

````

`````

`````{py:class} BankAgent(id: int, name: str, toolbox: agentsociety.agent.AgentToolbox, memory: agentsociety.memory.Memory, agent_params: typing.Optional[agentsociety.cityagent.bankagent.BankAgentConfig] = None, blocks: typing.Optional[list[agentsociety.agent.Block]] = None)
:canonical: agentsociety.cityagent.bankagent.BankAgent

Bases: {py:obj}`agentsociety.agent.BankAgentBase`

```{autodoc2-docstring} agentsociety.cityagent.bankagent.BankAgent
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.bankagent.BankAgent.__init__
```

````{py:attribute} ParamsType
:canonical: agentsociety.cityagent.bankagent.BankAgent.ParamsType
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.bankagent.BankAgent.ParamsType
```

````

````{py:attribute} description
:canonical: agentsociety.cityagent.bankagent.BankAgent.description
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.cityagent.bankagent.BankAgent.description
```

````

````{py:method} reset()
:canonical: agentsociety.cityagent.bankagent.BankAgent.reset
:async:

```{autodoc2-docstring} agentsociety.cityagent.bankagent.BankAgent.reset
```

````

````{py:method} month_trigger() -> bool
:canonical: agentsociety.cityagent.bankagent.BankAgent.month_trigger
:async:

```{autodoc2-docstring} agentsociety.cityagent.bankagent.BankAgent.month_trigger
```

````

````{py:method} forward()
:canonical: agentsociety.cityagent.bankagent.BankAgent.forward
:async:

```{autodoc2-docstring} agentsociety.cityagent.bankagent.BankAgent.forward
```

````

`````
