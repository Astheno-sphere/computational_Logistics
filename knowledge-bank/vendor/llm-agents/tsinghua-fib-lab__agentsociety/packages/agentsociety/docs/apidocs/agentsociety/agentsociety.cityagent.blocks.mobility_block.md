# {py:mod}`agentsociety.cityagent.blocks.mobility_block`

```{py:module} agentsociety.cityagent.blocks.mobility_block
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`PlaceSelectionBlock <agentsociety.cityagent.blocks.mobility_block.PlaceSelectionBlock>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.PlaceSelectionBlock
    :summary:
    ```
* - {py:obj}`MoveBlock <agentsociety.cityagent.blocks.mobility_block.MoveBlock>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MoveBlock
    :summary:
    ```
* - {py:obj}`MobilityNoneBlock <agentsociety.cityagent.blocks.mobility_block.MobilityNoneBlock>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityNoneBlock
    :summary:
    ```
* - {py:obj}`MobilityBlockParams <agentsociety.cityagent.blocks.mobility_block.MobilityBlockParams>`
  -
* - {py:obj}`MobilityBlockContext <agentsociety.cityagent.blocks.mobility_block.MobilityBlockContext>`
  -
* - {py:obj}`MobilityBlock <agentsociety.cityagent.blocks.mobility_block.MobilityBlock>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityBlock
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`gravity_model <agentsociety.cityagent.blocks.mobility_block.gravity_model>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.gravity_model
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`PLACE_TYPE_SELECTION_PROMPT <agentsociety.cityagent.blocks.mobility_block.PLACE_TYPE_SELECTION_PROMPT>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.PLACE_TYPE_SELECTION_PROMPT
    :summary:
    ```
* - {py:obj}`PLACE_SECOND_TYPE_SELECTION_PROMPT <agentsociety.cityagent.blocks.mobility_block.PLACE_SECOND_TYPE_SELECTION_PROMPT>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.PLACE_SECOND_TYPE_SELECTION_PROMPT
    :summary:
    ```
* - {py:obj}`PLACE_ANALYSIS_PROMPT <agentsociety.cityagent.blocks.mobility_block.PLACE_ANALYSIS_PROMPT>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.PLACE_ANALYSIS_PROMPT
    :summary:
    ```
* - {py:obj}`RADIUS_PROMPT <agentsociety.cityagent.blocks.mobility_block.RADIUS_PROMPT>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.RADIUS_PROMPT
    :summary:
    ```
````

### API

````{py:data} PLACE_TYPE_SELECTION_PROMPT
:canonical: agentsociety.cityagent.blocks.mobility_block.PLACE_TYPE_SELECTION_PROMPT
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.PLACE_TYPE_SELECTION_PROMPT
```

````

````{py:data} PLACE_SECOND_TYPE_SELECTION_PROMPT
:canonical: agentsociety.cityagent.blocks.mobility_block.PLACE_SECOND_TYPE_SELECTION_PROMPT
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.PLACE_SECOND_TYPE_SELECTION_PROMPT
```

````

````{py:data} PLACE_ANALYSIS_PROMPT
:canonical: agentsociety.cityagent.blocks.mobility_block.PLACE_ANALYSIS_PROMPT
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.PLACE_ANALYSIS_PROMPT
```

````

````{py:data} RADIUS_PROMPT
:canonical: agentsociety.cityagent.blocks.mobility_block.RADIUS_PROMPT
:value: <Multiline-String>

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.RADIUS_PROMPT
```

````

````{py:function} gravity_model(pois)
:canonical: agentsociety.cityagent.blocks.mobility_block.gravity_model

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.gravity_model
```
````

`````{py:class} PlaceSelectionBlock(toolbox: agentsociety.agent.AgentToolbox, agent_memory: agentsociety.memory.Memory, search_limit: int = 50)
:canonical: agentsociety.cityagent.blocks.mobility_block.PlaceSelectionBlock

Bases: {py:obj}`agentsociety.agent.Block`

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.PlaceSelectionBlock
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.PlaceSelectionBlock.__init__
```

````{py:attribute} name
:canonical: agentsociety.cityagent.blocks.mobility_block.PlaceSelectionBlock.name
:value: >
   'PlaceSelectionBlock'

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.PlaceSelectionBlock.name
```

````

````{py:attribute} description
:canonical: agentsociety.cityagent.blocks.mobility_block.PlaceSelectionBlock.description
:value: >
   'Selects destinations for unknown locations (excluding home/work)'

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.PlaceSelectionBlock.description
```

````

````{py:method} forward(context: agentsociety.agent.DotDict)
:canonical: agentsociety.cityagent.blocks.mobility_block.PlaceSelectionBlock.forward
:async:

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.PlaceSelectionBlock.forward
```

````

`````

`````{py:class} MoveBlock(toolbox: agentsociety.agent.AgentToolbox, agent_memory: agentsociety.memory.Memory)
:canonical: agentsociety.cityagent.blocks.mobility_block.MoveBlock

Bases: {py:obj}`agentsociety.agent.Block`

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MoveBlock
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MoveBlock.__init__
```

````{py:attribute} name
:canonical: agentsociety.cityagent.blocks.mobility_block.MoveBlock.name
:value: >
   'MoveBlock'

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MoveBlock.name
```

````

````{py:attribute} description
:canonical: agentsociety.cityagent.blocks.mobility_block.MoveBlock.description
:value: >
   'Executes mobility operations between locations'

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MoveBlock.description
```

````

````{py:method} forward(context: agentsociety.agent.DotDict)
:canonical: agentsociety.cityagent.blocks.mobility_block.MoveBlock.forward
:async:

````

`````

`````{py:class} MobilityNoneBlock(toolbox: agentsociety.agent.AgentToolbox, agent_memory: agentsociety.memory.Memory)
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityNoneBlock

Bases: {py:obj}`agentsociety.agent.Block`

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityNoneBlock
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityNoneBlock.__init__
```

````{py:attribute} name
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityNoneBlock.name
:value: >
   'MobilityNoneBlock'

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityNoneBlock.name
```

````

````{py:attribute} description
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityNoneBlock.description
:value: >
   'Handles other mobility operations'

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityNoneBlock.description
```

````

````{py:method} forward(context: agentsociety.agent.DotDict)
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityNoneBlock.forward
:async:

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityNoneBlock.forward
```

````

`````

`````{py:class} MobilityBlockParams(/, **data: typing.Any)
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityBlockParams

Bases: {py:obj}`agentsociety.agent.BlockParams`

````{py:attribute} radius_prompt
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityBlockParams.radius_prompt
:type: str
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityBlockParams.radius_prompt
```

````

````{py:attribute} search_limit
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityBlockParams.search_limit
:type: int
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityBlockParams.search_limit
```

````

`````

`````{py:class} MobilityBlockContext(/, **data: typing.Any)
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityBlockContext

Bases: {py:obj}`agentsociety.agent.BlockContext`

````{py:attribute} next_place
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityBlockContext.next_place
:type: typing.Optional[tuple[str, int]]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityBlockContext.next_place
```

````

`````

`````{py:class} MobilityBlock(toolbox: agentsociety.agent.AgentToolbox, agent_memory: agentsociety.memory.Memory, block_params: typing.Optional[agentsociety.cityagent.blocks.mobility_block.MobilityBlockParams] = None)
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityBlock

Bases: {py:obj}`agentsociety.agent.Block`

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityBlock
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityBlock.__init__
```

````{py:attribute} ParamsType
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityBlock.ParamsType
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityBlock.ParamsType
```

````

````{py:attribute} OutputType
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityBlock.OutputType
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityBlock.OutputType
```

````

````{py:attribute} ContextType
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityBlock.ContextType
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityBlock.ContextType
```

````

````{py:attribute} name
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityBlock.name
:value: >
   'MobilityBlock'

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityBlock.name
```

````

````{py:attribute} description
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityBlock.description
:value: >
   'Used for moving like go to work, go to home, go to other places, etc.'

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityBlock.description
```

````

````{py:attribute} actions
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityBlock.actions
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityBlock.actions
```

````

````{py:method} forward(agent_context: agentsociety.agent.DotDict) -> agentsociety.cityagent.sharing_params.SocietyAgentBlockOutput
:canonical: agentsociety.cityagent.blocks.mobility_block.MobilityBlock.forward
:async:

```{autodoc2-docstring} agentsociety.cityagent.blocks.mobility_block.MobilityBlock.forward
```

````

`````
