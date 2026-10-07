# {py:mod}`agentsociety.cityagent.blocks.other_block`

```{py:module} agentsociety.cityagent.blocks.other_block
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`SleepBlock <agentsociety.cityagent.blocks.other_block.SleepBlock>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.SleepBlock
    :summary:
    ```
* - {py:obj}`OtherNoneBlock <agentsociety.cityagent.blocks.other_block.OtherNoneBlock>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.OtherNoneBlock
    :summary:
    ```
* - {py:obj}`OtherBlockParams <agentsociety.cityagent.blocks.other_block.OtherBlockParams>`
  -
* - {py:obj}`OtherBlockContext <agentsociety.cityagent.blocks.other_block.OtherBlockContext>`
  -
* - {py:obj}`OtherBlock <agentsociety.cityagent.blocks.other_block.OtherBlock>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.OtherBlock
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`SLEEP_TIME_ESTIMATION_PROMPT <agentsociety.cityagent.blocks.other_block.SLEEP_TIME_ESTIMATION_PROMPT>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.SLEEP_TIME_ESTIMATION_PROMPT
    :summary:
    ```
````

### API

````{py:data} SLEEP_TIME_ESTIMATION_PROMPT
:canonical: agentsociety.cityagent.blocks.other_block.SLEEP_TIME_ESTIMATION_PROMPT
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.SLEEP_TIME_ESTIMATION_PROMPT
```

````

`````{py:class} SleepBlock(toolbox: agentsociety.agent.AgentToolbox, agent_memory: typing.Optional[agentsociety.memory.Memory] = None, sleep_time_estimation_prompt: str = SLEEP_TIME_ESTIMATION_PROMPT)
:canonical: agentsociety.cityagent.blocks.other_block.SleepBlock

Bases: {py:obj}`agentsociety.agent.Block`

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.SleepBlock
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.SleepBlock.__init__
```

````{py:attribute} name
:canonical: agentsociety.cityagent.blocks.other_block.SleepBlock.name
:value: >
   'SleepBlock'

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.SleepBlock.name
```

````

````{py:attribute} description
:canonical: agentsociety.cityagent.blocks.other_block.SleepBlock.description
:value: >
   'Handles sleep-related actions'

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.SleepBlock.description
```

````

````{py:method} forward(context: agentsociety.agent.DotDict)
:canonical: agentsociety.cityagent.blocks.other_block.SleepBlock.forward
:async:

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.SleepBlock.forward
```

````

`````

`````{py:class} OtherNoneBlock(toolbox: agentsociety.agent.AgentToolbox, agent_memory: typing.Optional[agentsociety.memory.Memory] = None)
:canonical: agentsociety.cityagent.blocks.other_block.OtherNoneBlock

Bases: {py:obj}`agentsociety.agent.Block`

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.OtherNoneBlock
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.OtherNoneBlock.__init__
```

````{py:attribute} name
:canonical: agentsociety.cityagent.blocks.other_block.OtherNoneBlock.name
:value: >
   'OtherNoneBlock'

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.OtherNoneBlock.name
```

````

````{py:attribute} description
:canonical: agentsociety.cityagent.blocks.other_block.OtherNoneBlock.description
:value: >
   'Handles all kinds of intentions/actions except sleep'

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.OtherNoneBlock.description
```

````

````{py:method} forward(context: agentsociety.agent.DotDict)
:canonical: agentsociety.cityagent.blocks.other_block.OtherNoneBlock.forward
:async:

````

`````

`````{py:class} OtherBlockParams(/, **data: typing.Any)
:canonical: agentsociety.cityagent.blocks.other_block.OtherBlockParams

Bases: {py:obj}`agentsociety.agent.BlockParams`

````{py:attribute} sleep_time_estimation_prompt
:canonical: agentsociety.cityagent.blocks.other_block.OtherBlockParams.sleep_time_estimation_prompt
:type: str
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.OtherBlockParams.sleep_time_estimation_prompt
```

````

`````

```{py:class} OtherBlockContext(/, **data: typing.Any)
:canonical: agentsociety.cityagent.blocks.other_block.OtherBlockContext

Bases: {py:obj}`agentsociety.agent.BlockContext`

```

`````{py:class} OtherBlock(toolbox: agentsociety.agent.AgentToolbox, agent_memory: agentsociety.memory.Memory, block_params: typing.Optional[agentsociety.cityagent.blocks.other_block.OtherBlockParams] = None)
:canonical: agentsociety.cityagent.blocks.other_block.OtherBlock

Bases: {py:obj}`agentsociety.agent.Block`

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.OtherBlock
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.OtherBlock.__init__
```

````{py:attribute} ParamsType
:canonical: agentsociety.cityagent.blocks.other_block.OtherBlock.ParamsType
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.OtherBlock.ParamsType
```

````

````{py:attribute} OutputType
:canonical: agentsociety.cityagent.blocks.other_block.OtherBlock.OutputType
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.OtherBlock.OutputType
```

````

````{py:attribute} ContextType
:canonical: agentsociety.cityagent.blocks.other_block.OtherBlock.ContextType
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.OtherBlock.ContextType
```

````

````{py:attribute} name
:canonical: agentsociety.cityagent.blocks.other_block.OtherBlock.name
:value: >
   'OtherBlock'

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.OtherBlock.name
```

````

````{py:attribute} description
:canonical: agentsociety.cityagent.blocks.other_block.OtherBlock.description
:value: >
   'Responsible for all kinds of intentions/actions except mobility, economy, and social, for example, s...'

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.OtherBlock.description
```

````

````{py:attribute} actions
:canonical: agentsociety.cityagent.blocks.other_block.OtherBlock.actions
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.OtherBlock.actions
```

````

````{py:method} forward(agent_context: agentsociety.agent.DotDict) -> agentsociety.cityagent.sharing_params.SocietyAgentBlockOutput
:canonical: agentsociety.cityagent.blocks.other_block.OtherBlock.forward
:async:

```{autodoc2-docstring} agentsociety.cityagent.blocks.other_block.OtherBlock.forward
```

````

`````
