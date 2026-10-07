# {py:mod}`agentsociety.cityagent.blocks.cognition_block`

```{py:module} agentsociety.cityagent.blocks.cognition_block
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`CognitionBlockParams <agentsociety.cityagent.blocks.cognition_block.CognitionBlockParams>`
  -
* - {py:obj}`CognitionBlock <agentsociety.cityagent.blocks.cognition_block.CognitionBlock>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.CognitionBlock
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`extract_json <agentsociety.cityagent.blocks.cognition_block.extract_json>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.extract_json
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.cityagent.blocks.cognition_block.__all__>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.cityagent.blocks.cognition_block.__all__
:value: >
   ['CognitionBlock']

```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.__all__
```

````

````{py:function} extract_json(output_str)
:canonical: agentsociety.cityagent.blocks.cognition_block.extract_json

```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.extract_json
```
````

`````{py:class} CognitionBlockParams(/, **data: typing.Any)
:canonical: agentsociety.cityagent.blocks.cognition_block.CognitionBlockParams

Bases: {py:obj}`agentsociety.agent.BlockParams`

````{py:attribute} top_k
:canonical: agentsociety.cityagent.blocks.cognition_block.CognitionBlockParams.top_k
:type: int
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.CognitionBlockParams.top_k
```

````

`````

`````{py:class} CognitionBlock(toolbox: agentsociety.agent.AgentToolbox, agent_memory: agentsociety.memory.Memory, block_params: typing.Optional[agentsociety.cityagent.blocks.cognition_block.CognitionBlockParams] = None)
:canonical: agentsociety.cityagent.blocks.cognition_block.CognitionBlock

Bases: {py:obj}`agentsociety.agent.Block`

```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.CognitionBlock
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.CognitionBlock.__init__
```

````{py:attribute} ParamsType
:canonical: agentsociety.cityagent.blocks.cognition_block.CognitionBlock.ParamsType
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.CognitionBlock.ParamsType
```

````

````{py:attribute} name
:canonical: agentsociety.cityagent.blocks.cognition_block.CognitionBlock.name
:value: >
   'CognitionBlock'

```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.CognitionBlock.name
```

````

````{py:attribute} description
:canonical: agentsociety.cityagent.blocks.cognition_block.CognitionBlock.description
:value: >
   'Handles daily updates of attitudes, thoughts, and emotions'

```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.CognitionBlock.description
```

````

````{py:attribute} actions
:canonical: agentsociety.cityagent.blocks.cognition_block.CognitionBlock.actions
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.CognitionBlock.actions
```

````

````{py:method} set_status(status)
:canonical: agentsociety.cityagent.blocks.cognition_block.CognitionBlock.set_status
:async:

```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.CognitionBlock.set_status
```

````

````{py:method} attitude_update()
:canonical: agentsociety.cityagent.blocks.cognition_block.CognitionBlock.attitude_update
:async:

```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.CognitionBlock.attitude_update
```

````

````{py:method} thought_update()
:canonical: agentsociety.cityagent.blocks.cognition_block.CognitionBlock.thought_update
:async:

```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.CognitionBlock.thought_update
```

````

````{py:method} cross_day()
:canonical: agentsociety.cityagent.blocks.cognition_block.CognitionBlock.cross_day
:async:

```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.CognitionBlock.cross_day
```

````

````{py:method} forward()
:canonical: agentsociety.cityagent.blocks.cognition_block.CognitionBlock.forward
:async:

```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.CognitionBlock.forward
```

````

````{py:method} emotion_update(incident)
:canonical: agentsociety.cityagent.blocks.cognition_block.CognitionBlock.emotion_update
:async:

```{autodoc2-docstring} agentsociety.cityagent.blocks.cognition_block.CognitionBlock.emotion_update
```

````

`````
