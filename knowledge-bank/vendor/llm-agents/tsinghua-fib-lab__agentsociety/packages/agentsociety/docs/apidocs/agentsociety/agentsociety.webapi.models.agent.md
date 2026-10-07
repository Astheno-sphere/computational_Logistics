# {py:mod}`agentsociety.webapi.models.agent`

```{py:module} agentsociety.webapi.models.agent
```

```{autodoc2-docstring} agentsociety.webapi.models.agent
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`AgentDialogType <agentsociety.webapi.models.agent.AgentDialogType>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.agent.AgentDialogType
    :summary:
    ```
* - {py:obj}`ApiAgentProfile <agentsociety.webapi.models.agent.ApiAgentProfile>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentProfile
    :summary:
    ```
* - {py:obj}`ApiAgentStatus <agentsociety.webapi.models.agent.ApiAgentStatus>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentStatus
    :summary:
    ```
* - {py:obj}`ApiAgentSurvey <agentsociety.webapi.models.agent.ApiAgentSurvey>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentSurvey
    :summary:
    ```
* - {py:obj}`ApiAgentDialog <agentsociety.webapi.models.agent.ApiAgentDialog>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentDialog
    :summary:
    ```
* - {py:obj}`ApiGlobalPrompt <agentsociety.webapi.models.agent.ApiGlobalPrompt>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiGlobalPrompt
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.webapi.models.agent.__all__>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.agent.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.webapi.models.agent.__all__
:value: >
   ['agent_dialog', 'agent_profile', 'agent_status', 'agent_survey', 'global_prompt', 'pending_dialog',...

```{autodoc2-docstring} agentsociety.webapi.models.agent.__all__
```

````

`````{py:class} AgentDialogType()
:canonical: agentsociety.webapi.models.agent.AgentDialogType

Bases: {py:obj}`enum.IntEnum`

```{autodoc2-docstring} agentsociety.webapi.models.agent.AgentDialogType
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.agent.AgentDialogType.__init__
```

````{py:attribute} Thought
:canonical: agentsociety.webapi.models.agent.AgentDialogType.Thought
:value: >
   0

```{autodoc2-docstring} agentsociety.webapi.models.agent.AgentDialogType.Thought
```

````

````{py:attribute} Talk
:canonical: agentsociety.webapi.models.agent.AgentDialogType.Talk
:value: >
   1

```{autodoc2-docstring} agentsociety.webapi.models.agent.AgentDialogType.Talk
```

````

````{py:attribute} User
:canonical: agentsociety.webapi.models.agent.AgentDialogType.User
:value: >
   2

```{autodoc2-docstring} agentsociety.webapi.models.agent.AgentDialogType.User
```

````

`````

``````{py:class} ApiAgentProfile(/, **data: typing.Any)
:canonical: agentsociety.webapi.models.agent.ApiAgentProfile

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentProfile
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentProfile.__init__
```

````{py:attribute} id
:canonical: agentsociety.webapi.models.agent.ApiAgentProfile.id
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentProfile.id
```

````

````{py:attribute} name
:canonical: agentsociety.webapi.models.agent.ApiAgentProfile.name
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentProfile.name
```

````

````{py:attribute} profile
:canonical: agentsociety.webapi.models.agent.ApiAgentProfile.profile
:type: typing.Any
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentProfile.profile
```

````

`````{py:class} Config
:canonical: agentsociety.webapi.models.agent.ApiAgentProfile.Config

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentProfile.Config
```

````{py:attribute} from_attributes
:canonical: agentsociety.webapi.models.agent.ApiAgentProfile.Config.from_attributes
:value: >
   True

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentProfile.Config.from_attributes
```

````

`````

``````

``````{py:class} ApiAgentStatus(/, **data: typing.Any)
:canonical: agentsociety.webapi.models.agent.ApiAgentStatus

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentStatus
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentStatus.__init__
```

````{py:attribute} id
:canonical: agentsociety.webapi.models.agent.ApiAgentStatus.id
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentStatus.id
```

````

````{py:attribute} day
:canonical: agentsociety.webapi.models.agent.ApiAgentStatus.day
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentStatus.day
```

````

````{py:attribute} t
:canonical: agentsociety.webapi.models.agent.ApiAgentStatus.t
:type: float
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentStatus.t
```

````

````{py:attribute} lng
:canonical: agentsociety.webapi.models.agent.ApiAgentStatus.lng
:type: typing.Optional[float]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentStatus.lng
```

````

````{py:attribute} lat
:canonical: agentsociety.webapi.models.agent.ApiAgentStatus.lat
:type: typing.Optional[float]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentStatus.lat
```

````

````{py:attribute} parent_id
:canonical: agentsociety.webapi.models.agent.ApiAgentStatus.parent_id
:type: typing.Optional[int]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentStatus.parent_id
```

````

````{py:attribute} action
:canonical: agentsociety.webapi.models.agent.ApiAgentStatus.action
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentStatus.action
```

````

````{py:attribute} status
:canonical: agentsociety.webapi.models.agent.ApiAgentStatus.status
:type: typing.Any
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentStatus.status
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.agent.ApiAgentStatus.created_at
:type: pydantic.AwareDatetime
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentStatus.created_at
```

````

`````{py:class} Config
:canonical: agentsociety.webapi.models.agent.ApiAgentStatus.Config

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentStatus.Config
```

````{py:attribute} from_attributes
:canonical: agentsociety.webapi.models.agent.ApiAgentStatus.Config.from_attributes
:value: >
   True

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentStatus.Config.from_attributes
```

````

`````

``````

``````{py:class} ApiAgentSurvey(/, **data: typing.Any)
:canonical: agentsociety.webapi.models.agent.ApiAgentSurvey

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentSurvey
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentSurvey.__init__
```

````{py:attribute} id
:canonical: agentsociety.webapi.models.agent.ApiAgentSurvey.id
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentSurvey.id
```

````

````{py:attribute} day
:canonical: agentsociety.webapi.models.agent.ApiAgentSurvey.day
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentSurvey.day
```

````

````{py:attribute} t
:canonical: agentsociety.webapi.models.agent.ApiAgentSurvey.t
:type: float
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentSurvey.t
```

````

````{py:attribute} survey_id
:canonical: agentsociety.webapi.models.agent.ApiAgentSurvey.survey_id
:type: uuid.UUID
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentSurvey.survey_id
```

````

````{py:attribute} result
:canonical: agentsociety.webapi.models.agent.ApiAgentSurvey.result
:type: typing.Any
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentSurvey.result
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.agent.ApiAgentSurvey.created_at
:type: pydantic.AwareDatetime
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentSurvey.created_at
```

````

`````{py:class} Config
:canonical: agentsociety.webapi.models.agent.ApiAgentSurvey.Config

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentSurvey.Config
```

````{py:attribute} from_attributes
:canonical: agentsociety.webapi.models.agent.ApiAgentSurvey.Config.from_attributes
:value: >
   True

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentSurvey.Config.from_attributes
```

````

`````

``````

``````{py:class} ApiAgentDialog(/, **data: typing.Any)
:canonical: agentsociety.webapi.models.agent.ApiAgentDialog

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentDialog
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentDialog.__init__
```

````{py:attribute} id
:canonical: agentsociety.webapi.models.agent.ApiAgentDialog.id
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentDialog.id
```

````

````{py:attribute} day
:canonical: agentsociety.webapi.models.agent.ApiAgentDialog.day
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentDialog.day
```

````

````{py:attribute} t
:canonical: agentsociety.webapi.models.agent.ApiAgentDialog.t
:type: float
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentDialog.t
```

````

````{py:attribute} type
:canonical: agentsociety.webapi.models.agent.ApiAgentDialog.type
:type: agentsociety.webapi.models.agent.AgentDialogType
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentDialog.type
```

````

````{py:attribute} speaker
:canonical: agentsociety.webapi.models.agent.ApiAgentDialog.speaker
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentDialog.speaker
```

````

````{py:attribute} content
:canonical: agentsociety.webapi.models.agent.ApiAgentDialog.content
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentDialog.content
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.agent.ApiAgentDialog.created_at
:type: pydantic.AwareDatetime
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentDialog.created_at
```

````

`````{py:class} Config
:canonical: agentsociety.webapi.models.agent.ApiAgentDialog.Config

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentDialog.Config
```

````{py:attribute} from_attributes
:canonical: agentsociety.webapi.models.agent.ApiAgentDialog.Config.from_attributes
:value: >
   True

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiAgentDialog.Config.from_attributes
```

````

`````

``````

``````{py:class} ApiGlobalPrompt(/, **data: typing.Any)
:canonical: agentsociety.webapi.models.agent.ApiGlobalPrompt

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiGlobalPrompt
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiGlobalPrompt.__init__
```

````{py:attribute} day
:canonical: agentsociety.webapi.models.agent.ApiGlobalPrompt.day
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiGlobalPrompt.day
```

````

````{py:attribute} t
:canonical: agentsociety.webapi.models.agent.ApiGlobalPrompt.t
:type: float
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiGlobalPrompt.t
```

````

````{py:attribute} prompt
:canonical: agentsociety.webapi.models.agent.ApiGlobalPrompt.prompt
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiGlobalPrompt.prompt
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.agent.ApiGlobalPrompt.created_at
:type: pydantic.AwareDatetime
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiGlobalPrompt.created_at
```

````

`````{py:class} Config
:canonical: agentsociety.webapi.models.agent.ApiGlobalPrompt.Config

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiGlobalPrompt.Config
```

````{py:attribute} from_attributes
:canonical: agentsociety.webapi.models.agent.ApiGlobalPrompt.Config.from_attributes
:value: >
   True

```{autodoc2-docstring} agentsociety.webapi.models.agent.ApiGlobalPrompt.Config.from_attributes
```

````

`````

``````
