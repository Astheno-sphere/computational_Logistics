# {py:mod}`agentsociety.cityagent.blocks.social_block`

```{py:module} agentsociety.cityagent.blocks.social_block
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`MessagePromptManager <agentsociety.cityagent.blocks.social_block.MessagePromptManager>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.MessagePromptManager
    :summary:
    ```
* - {py:obj}`SocialNoneBlock <agentsociety.cityagent.blocks.social_block.SocialNoneBlock>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialNoneBlock
    :summary:
    ```
* - {py:obj}`FindPersonBlock <agentsociety.cityagent.blocks.social_block.FindPersonBlock>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.FindPersonBlock
    :summary:
    ```
* - {py:obj}`MessageBlock <agentsociety.cityagent.blocks.social_block.MessageBlock>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.MessageBlock
    :summary:
    ```
* - {py:obj}`SocialBlockParams <agentsociety.cityagent.blocks.social_block.SocialBlockParams>`
  -
* - {py:obj}`SocialBlockContext <agentsociety.cityagent.blocks.social_block.SocialBlockContext>`
  -
* - {py:obj}`SocialBlock <agentsociety.cityagent.blocks.social_block.SocialBlock>`
  - ```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialBlock
    :summary:
    ```
````

### API

`````{py:class} MessagePromptManager()
:canonical: agentsociety.cityagent.blocks.social_block.MessagePromptManager

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.MessagePromptManager
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.MessagePromptManager.__init__
```

````{py:method} get_prompt(memory, step: dict[str, typing.Any], environment_info: str, target: int, template: str)
:canonical: agentsociety.cityagent.blocks.social_block.MessagePromptManager.get_prompt
:async:

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.MessagePromptManager.get_prompt
```

````

`````

`````{py:class} SocialNoneBlock(toolbox: agentsociety.agent.AgentToolbox, agent_memory: agentsociety.memory.Memory)
:canonical: agentsociety.cityagent.blocks.social_block.SocialNoneBlock

Bases: {py:obj}`agentsociety.agent.Block`

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialNoneBlock
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialNoneBlock.__init__
```

````{py:attribute} name
:canonical: agentsociety.cityagent.blocks.social_block.SocialNoneBlock.name
:value: >
   'SocialNoneBlock'

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialNoneBlock.name
```

````

````{py:attribute} description
:canonical: agentsociety.cityagent.blocks.social_block.SocialNoneBlock.description
:value: >
   'Handle all other cases if you are not trying to determine the social target or send a message to som...'

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialNoneBlock.description
```

````

````{py:method} forward(context)
:canonical: agentsociety.cityagent.blocks.social_block.SocialNoneBlock.forward
:async:

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialNoneBlock.forward
```

````

`````

`````{py:class} FindPersonBlock(toolbox: agentsociety.agent.AgentToolbox, agent_memory: agentsociety.memory.Memory)
:canonical: agentsociety.cityagent.blocks.social_block.FindPersonBlock

Bases: {py:obj}`agentsociety.agent.Block`

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.FindPersonBlock
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.FindPersonBlock.__init__
```

````{py:attribute} name
:canonical: agentsociety.cityagent.blocks.social_block.FindPersonBlock.name
:value: >
   'FindPersonBlock'

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.FindPersonBlock.name
```

````

````{py:attribute} description
:canonical: agentsociety.cityagent.blocks.social_block.FindPersonBlock.description
:value: >
   'Find a suitable person to socialize with'

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.FindPersonBlock.description
```

````

````{py:method} forward(context: agentsociety.agent.DotDict)
:canonical: agentsociety.cityagent.blocks.social_block.FindPersonBlock.forward
:async:

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.FindPersonBlock.forward
```

````

`````

`````{py:class} MessageBlock(toolbox: agentsociety.agent.AgentToolbox, agent_memory: agentsociety.memory.Memory)
:canonical: agentsociety.cityagent.blocks.social_block.MessageBlock

Bases: {py:obj}`agentsociety.agent.Block`

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.MessageBlock
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.MessageBlock.__init__
```

````{py:attribute} name
:canonical: agentsociety.cityagent.blocks.social_block.MessageBlock.name
:value: >
   'MessageBlock'

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.MessageBlock.name
```

````

````{py:attribute} description
:canonical: agentsociety.cityagent.blocks.social_block.MessageBlock.description
:value: >
   'Send social message to someone (including online and offline, phone call, social post, etc.)'

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.MessageBlock.description
```

````

````{py:method} forward(context: agentsociety.agent.DotDict)
:canonical: agentsociety.cityagent.blocks.social_block.MessageBlock.forward
:async:

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.MessageBlock.forward
```

````

`````

```{py:class} SocialBlockParams(/, **data: typing.Any)
:canonical: agentsociety.cityagent.blocks.social_block.SocialBlockParams

Bases: {py:obj}`agentsociety.agent.BlockParams`

```

`````{py:class} SocialBlockContext(/, **data: typing.Any)
:canonical: agentsociety.cityagent.blocks.social_block.SocialBlockContext

Bases: {py:obj}`agentsociety.agent.BlockContext`

````{py:attribute} target
:canonical: agentsociety.cityagent.blocks.social_block.SocialBlockContext.target
:type: typing.Optional[int]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialBlockContext.target
```

````

`````

`````{py:class} SocialBlock(toolbox: agentsociety.agent.AgentToolbox, agent_memory: agentsociety.memory.Memory, block_params: typing.Optional[agentsociety.cityagent.blocks.social_block.SocialBlockParams] = None)
:canonical: agentsociety.cityagent.blocks.social_block.SocialBlock

Bases: {py:obj}`agentsociety.agent.Block`

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialBlock
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialBlock.__init__
```

````{py:attribute} ParamsType
:canonical: agentsociety.cityagent.blocks.social_block.SocialBlock.ParamsType
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialBlock.ParamsType
```

````

````{py:attribute} OutputType
:canonical: agentsociety.cityagent.blocks.social_block.SocialBlock.OutputType
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialBlock.OutputType
```

````

````{py:attribute} ContextType
:canonical: agentsociety.cityagent.blocks.social_block.SocialBlock.ContextType
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialBlock.ContextType
```

````

````{py:attribute} NeedAgent
:canonical: agentsociety.cityagent.blocks.social_block.SocialBlock.NeedAgent
:value: >
   True

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialBlock.NeedAgent
```

````

````{py:attribute} name
:canonical: agentsociety.cityagent.blocks.social_block.SocialBlock.name
:value: >
   'SocialBlock'

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialBlock.name
```

````

````{py:attribute} description
:canonical: agentsociety.cityagent.blocks.social_block.SocialBlock.description
:value: >
   'Do social interactions, for example, find a friend, send a message, and other social activities.'

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialBlock.description
```

````

````{py:attribute} actions
:canonical: agentsociety.cityagent.blocks.social_block.SocialBlock.actions
:value: >
   None

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialBlock.actions
```

````

````{py:method} forward(agent_context: agentsociety.agent.DotDict) -> agentsociety.cityagent.sharing_params.SocietyAgentBlockOutput
:canonical: agentsociety.cityagent.blocks.social_block.SocialBlock.forward
:async:

```{autodoc2-docstring} agentsociety.cityagent.blocks.social_block.SocialBlock.forward
```

````

`````
