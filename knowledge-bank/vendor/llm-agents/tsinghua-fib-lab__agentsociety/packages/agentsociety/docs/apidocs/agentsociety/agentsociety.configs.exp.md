# {py:mod}`agentsociety.configs.exp`

```{py:module} agentsociety.configs.exp
```

```{autodoc2-docstring} agentsociety.configs.exp
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`WorkflowType <agentsociety.configs.exp.WorkflowType>`
  - ```{autodoc2-docstring} agentsociety.configs.exp.WorkflowType
    :summary:
    ```
* - {py:obj}`AgentFilterConfig <agentsociety.configs.exp.AgentFilterConfig>`
  - ```{autodoc2-docstring} agentsociety.configs.exp.AgentFilterConfig
    :summary:
    ```
* - {py:obj}`WorkflowStepConfig <agentsociety.configs.exp.WorkflowStepConfig>`
  - ```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig
    :summary:
    ```
* - {py:obj}`ExpConfig <agentsociety.configs.exp.ExpConfig>`
  - ```{autodoc2-docstring} agentsociety.configs.exp.ExpConfig
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.configs.exp.__all__>`
  - ```{autodoc2-docstring} agentsociety.configs.exp.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.configs.exp.__all__
:value: >
   ['WorkflowStepConfig', 'EnvironmentConfig', 'ExpConfig', 'WorkflowType', 'AgentFilterConfig']

```{autodoc2-docstring} agentsociety.configs.exp.__all__
```

````

`````{py:class} WorkflowType()
:canonical: agentsociety.configs.exp.WorkflowType

Bases: {py:obj}`str`, {py:obj}`enum.Enum`

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowType
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowType.__init__
```

````{py:attribute} STEP
:canonical: agentsociety.configs.exp.WorkflowType.STEP
:value: >
   'step'

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowType.STEP
```

````

````{py:attribute} RUN
:canonical: agentsociety.configs.exp.WorkflowType.RUN
:value: >
   'run'

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowType.RUN
```

````

````{py:attribute} INTERVIEW
:canonical: agentsociety.configs.exp.WorkflowType.INTERVIEW
:value: >
   'interview'

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowType.INTERVIEW
```

````

````{py:attribute} SURVEY
:canonical: agentsociety.configs.exp.WorkflowType.SURVEY
:value: >
   'survey'

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowType.SURVEY
```

````

````{py:attribute} UPDATE_STATE_INTERVENE
:canonical: agentsociety.configs.exp.WorkflowType.UPDATE_STATE_INTERVENE
:value: >
   'update_state'

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowType.UPDATE_STATE_INTERVENE
```

````

````{py:attribute} MESSAGE_INTERVENE
:canonical: agentsociety.configs.exp.WorkflowType.MESSAGE_INTERVENE
:value: >
   'message'

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowType.MESSAGE_INTERVENE
```

````

````{py:attribute} DELETE_AGENT
:canonical: agentsociety.configs.exp.WorkflowType.DELETE_AGENT
:value: >
   'delete_agent'

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowType.DELETE_AGENT
```

````

````{py:attribute} ENVIRONMENT_INTERVENE
:canonical: agentsociety.configs.exp.WorkflowType.ENVIRONMENT_INTERVENE
:value: >
   'environment'

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowType.ENVIRONMENT_INTERVENE
```

````

````{py:attribute} NEXT_ROUND
:canonical: agentsociety.configs.exp.WorkflowType.NEXT_ROUND
:value: >
   'next_round'

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowType.NEXT_ROUND
```

````

````{py:attribute} SAVE_CONTEXT
:canonical: agentsociety.configs.exp.WorkflowType.SAVE_CONTEXT
:value: >
   'save_context'

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowType.SAVE_CONTEXT
```

````

````{py:attribute} INTERVENE
:canonical: agentsociety.configs.exp.WorkflowType.INTERVENE
:value: >
   'other'

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowType.INTERVENE
```

````

````{py:attribute} FUNCTION
:canonical: agentsociety.configs.exp.WorkflowType.FUNCTION
:value: >
   'function'

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowType.FUNCTION
```

````

`````

`````{py:class} AgentFilterConfig(/, **data: typing.Any)
:canonical: agentsociety.configs.exp.AgentFilterConfig

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.configs.exp.AgentFilterConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.configs.exp.AgentFilterConfig.__init__
```

````{py:attribute} agent_class
:canonical: agentsociety.configs.exp.AgentFilterConfig.agent_class
:type: typing.Optional[typing.Union[tuple[type[agentsociety.agent.Agent]], list[str]]]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.exp.AgentFilterConfig.agent_class
```

````

````{py:attribute} filter_str
:canonical: agentsociety.configs.exp.AgentFilterConfig.filter_str
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.exp.AgentFilterConfig.filter_str
```

````

````{py:method} validate_func()
:canonical: agentsociety.configs.exp.AgentFilterConfig.validate_func

```{autodoc2-docstring} agentsociety.configs.exp.AgentFilterConfig.validate_func
```

````

`````

`````{py:class} WorkflowStepConfig(/, **data: typing.Any)
:canonical: agentsociety.configs.exp.WorkflowStepConfig

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.__init__
```

````{py:attribute} model_config
:canonical: agentsociety.configs.exp.WorkflowStepConfig.model_config
:value: >
   'ConfigDict(...)'

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.model_config
```

````

````{py:attribute} type
:canonical: agentsociety.configs.exp.WorkflowStepConfig.type
:type: agentsociety.configs.exp.WorkflowType
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.type
```

````

````{py:attribute} func
:canonical: agentsociety.configs.exp.WorkflowStepConfig.func
:type: typing.Optional[typing.Union[collections.abc.Callable, str]]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.func
```

````

````{py:attribute} days
:canonical: agentsociety.configs.exp.WorkflowStepConfig.days
:type: float
:value: >
   1

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.days
```

````

````{py:attribute} steps
:canonical: agentsociety.configs.exp.WorkflowStepConfig.steps
:type: int
:value: >
   1

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.steps
```

````

````{py:attribute} ticks_per_step
:canonical: agentsociety.configs.exp.WorkflowStepConfig.ticks_per_step
:type: int
:value: >
   300

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.ticks_per_step
```

````

````{py:attribute} target_agent
:canonical: agentsociety.configs.exp.WorkflowStepConfig.target_agent
:type: typing.Optional[typing.Union[list[int], agentsociety.configs.exp.AgentFilterConfig]]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.target_agent
```

````

````{py:attribute} interview_message
:canonical: agentsociety.configs.exp.WorkflowStepConfig.interview_message
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.interview_message
```

````

````{py:attribute} survey
:canonical: agentsociety.configs.exp.WorkflowStepConfig.survey
:type: typing.Optional[agentsociety.survey.Survey]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.survey
```

````

````{py:attribute} key
:canonical: agentsociety.configs.exp.WorkflowStepConfig.key
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.key
```

````

````{py:attribute} save_as
:canonical: agentsociety.configs.exp.WorkflowStepConfig.save_as
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.save_as
```

````

````{py:attribute} value
:canonical: agentsociety.configs.exp.WorkflowStepConfig.value
:type: typing.Optional[typing.Any]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.value
```

````

````{py:attribute} intervene_message
:canonical: agentsociety.configs.exp.WorkflowStepConfig.intervene_message
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.intervene_message
```

````

````{py:attribute} description
:canonical: agentsociety.configs.exp.WorkflowStepConfig.description
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.description
```

````

````{py:method} serialize_func(func, info)
:canonical: agentsociety.configs.exp.WorkflowStepConfig.serialize_func

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.serialize_func
```

````

````{py:method} validate_func()
:canonical: agentsociety.configs.exp.WorkflowStepConfig.validate_func

```{autodoc2-docstring} agentsociety.configs.exp.WorkflowStepConfig.validate_func
```

````

`````

`````{py:class} ExpConfig(/, **data: typing.Any)
:canonical: agentsociety.configs.exp.ExpConfig

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.configs.exp.ExpConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.configs.exp.ExpConfig.__init__
```

````{py:attribute} model_config
:canonical: agentsociety.configs.exp.ExpConfig.model_config
:value: >
   'ConfigDict(...)'

```{autodoc2-docstring} agentsociety.configs.exp.ExpConfig.model_config
```

````

````{py:attribute} name
:canonical: agentsociety.configs.exp.ExpConfig.name
:type: str
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.exp.ExpConfig.name
```

````

````{py:attribute} id
:canonical: agentsociety.configs.exp.ExpConfig.id
:type: uuid.UUID
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.exp.ExpConfig.id
```

````

````{py:attribute} workflow
:canonical: agentsociety.configs.exp.ExpConfig.workflow
:type: typing.List[agentsociety.configs.exp.WorkflowStepConfig]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.configs.exp.ExpConfig.workflow
```

````

````{py:attribute} environment
:canonical: agentsociety.configs.exp.ExpConfig.environment
:type: agentsociety.environment.EnvironmentConfig
:value: >
   None

```{autodoc2-docstring} agentsociety.configs.exp.ExpConfig.environment
```

````

````{py:method} serialize_id(id, info)
:canonical: agentsociety.configs.exp.ExpConfig.serialize_id

```{autodoc2-docstring} agentsociety.configs.exp.ExpConfig.serialize_id
```

````

`````
