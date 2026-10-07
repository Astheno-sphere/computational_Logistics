# {py:mod}`agentsociety.webapi.api.agent`

```{py:module} agentsociety.webapi.api.agent
```

```{autodoc2-docstring} agentsociety.webapi.api.agent
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`AgentChatMessage <agentsociety.webapi.api.agent.AgentChatMessage>`
  -
* - {py:obj}`AgentSurveyMessage <agentsociety.webapi.api.agent.AgentSurveyMessage>`
  -
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`get_agent_dialog_by_exp_id_and_agent_id <agentsociety.webapi.api.agent.get_agent_dialog_by_exp_id_and_agent_id>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent.get_agent_dialog_by_exp_id_and_agent_id
    :summary:
    ```
* - {py:obj}`list_agent_profile_by_exp_id <agentsociety.webapi.api.agent.list_agent_profile_by_exp_id>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent.list_agent_profile_by_exp_id
    :summary:
    ```
* - {py:obj}`get_agent_profile_by_exp_id_and_agent_id <agentsociety.webapi.api.agent.get_agent_profile_by_exp_id_and_agent_id>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent.get_agent_profile_by_exp_id_and_agent_id
    :summary:
    ```
* - {py:obj}`list_agent_status_by_day_and_t <agentsociety.webapi.api.agent.list_agent_status_by_day_and_t>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent.list_agent_status_by_day_and_t
    :summary:
    ```
* - {py:obj}`get_agent_status_by_exp_id_and_agent_id <agentsociety.webapi.api.agent.get_agent_status_by_exp_id_and_agent_id>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent.get_agent_status_by_exp_id_and_agent_id
    :summary:
    ```
* - {py:obj}`get_agent_survey_by_exp_id_and_agent_id <agentsociety.webapi.api.agent.get_agent_survey_by_exp_id_and_agent_id>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent.get_agent_survey_by_exp_id_and_agent_id
    :summary:
    ```
* - {py:obj}`get_global_prompt_by_day_t <agentsociety.webapi.api.agent.get_global_prompt_by_day_t>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent.get_global_prompt_by_day_t
    :summary:
    ```
* - {py:obj}`post_agent_dialog <agentsociety.webapi.api.agent.post_agent_dialog>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent.post_agent_dialog
    :summary:
    ```
* - {py:obj}`post_agent_survey <agentsociety.webapi.api.agent.post_agent_survey>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent.post_agent_survey
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.webapi.api.agent.__all__>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent.__all__
    :summary:
    ```
* - {py:obj}`router <agentsociety.webapi.api.agent.router>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent.router
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.webapi.api.agent.__all__
:value: >
   ['router']

```{autodoc2-docstring} agentsociety.webapi.api.agent.__all__
```

````

````{py:data} router
:canonical: agentsociety.webapi.api.agent.router
:value: >
   'APIRouter(...)'

```{autodoc2-docstring} agentsociety.webapi.api.agent.router
```

````

````{py:function} get_agent_dialog_by_exp_id_and_agent_id(request: fastapi.Request, exp_id: uuid.UUID, agent_id: int) -> agentsociety.webapi.models.ApiResponseWrapper[typing.List[agentsociety.webapi.models.agent.ApiAgentDialog]]
:canonical: agentsociety.webapi.api.agent.get_agent_dialog_by_exp_id_and_agent_id
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent.get_agent_dialog_by_exp_id_and_agent_id
```
````

````{py:function} list_agent_profile_by_exp_id(request: fastapi.Request, exp_id: uuid.UUID) -> agentsociety.webapi.models.ApiResponseWrapper[typing.List[agentsociety.webapi.models.agent.ApiAgentProfile]]
:canonical: agentsociety.webapi.api.agent.list_agent_profile_by_exp_id
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent.list_agent_profile_by_exp_id
```
````

````{py:function} get_agent_profile_by_exp_id_and_agent_id(request: fastapi.Request, exp_id: uuid.UUID, agent_id: int) -> agentsociety.webapi.models.ApiResponseWrapper[agentsociety.webapi.models.agent.ApiAgentProfile]
:canonical: agentsociety.webapi.api.agent.get_agent_profile_by_exp_id_and_agent_id
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent.get_agent_profile_by_exp_id_and_agent_id
```
````

````{py:function} list_agent_status_by_day_and_t(request: fastapi.Request, exp_id: uuid.UUID, day: typing.Optional[int] = Query(None, description='the day for getting agent status'), t: typing.Optional[float] = Query(None, description='the time for getting agent status')) -> agentsociety.webapi.models.ApiResponseWrapper[typing.List[agentsociety.webapi.models.agent.ApiAgentStatus]]
:canonical: agentsociety.webapi.api.agent.list_agent_status_by_day_and_t
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent.list_agent_status_by_day_and_t
```
````

````{py:function} get_agent_status_by_exp_id_and_agent_id(request: fastapi.Request, exp_id: uuid.UUID, agent_id: int) -> agentsociety.webapi.models.ApiResponseWrapper[typing.List[agentsociety.webapi.models.agent.ApiAgentStatus]]
:canonical: agentsociety.webapi.api.agent.get_agent_status_by_exp_id_and_agent_id
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent.get_agent_status_by_exp_id_and_agent_id
```
````

````{py:function} get_agent_survey_by_exp_id_and_agent_id(request: fastapi.Request, exp_id: uuid.UUID, agent_id: int) -> agentsociety.webapi.models.ApiResponseWrapper[typing.List[agentsociety.webapi.models.agent.ApiAgentSurvey]]
:canonical: agentsociety.webapi.api.agent.get_agent_survey_by_exp_id_and_agent_id
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent.get_agent_survey_by_exp_id_and_agent_id
```
````

````{py:function} get_global_prompt_by_day_t(request: fastapi.Request, exp_id: uuid.UUID, day: typing.Optional[int] = Query(None, description='the day for getting agent status'), t: typing.Optional[float] = Query(None, description='the time for getting agent status')) -> agentsociety.webapi.models.ApiResponseWrapper[typing.Optional[agentsociety.webapi.models.agent.ApiGlobalPrompt]]
:canonical: agentsociety.webapi.api.agent.get_global_prompt_by_day_t
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent.get_global_prompt_by_day_t
```
````

`````{py:class} AgentChatMessage(/, **data: typing.Any)
:canonical: agentsociety.webapi.api.agent.AgentChatMessage

Bases: {py:obj}`pydantic.BaseModel`

````{py:attribute} content
:canonical: agentsociety.webapi.api.agent.AgentChatMessage.content
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent.AgentChatMessage.content
```

````

````{py:attribute} day
:canonical: agentsociety.webapi.api.agent.AgentChatMessage.day
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent.AgentChatMessage.day
```

````

````{py:attribute} t
:canonical: agentsociety.webapi.api.agent.AgentChatMessage.t
:type: float
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent.AgentChatMessage.t
```

````

`````

````{py:function} post_agent_dialog(request: fastapi.Request, exp_id: uuid.UUID, agent_id: int, message: agentsociety.webapi.api.agent.AgentChatMessage = Body(...)) -> agentsociety.webapi.models.ApiResponseWrapper[None]
:canonical: agentsociety.webapi.api.agent.post_agent_dialog
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent.post_agent_dialog
```
````

`````{py:class} AgentSurveyMessage(/, **data: typing.Any)
:canonical: agentsociety.webapi.api.agent.AgentSurveyMessage

Bases: {py:obj}`pydantic.BaseModel`

````{py:attribute} survey_id
:canonical: agentsociety.webapi.api.agent.AgentSurveyMessage.survey_id
:type: uuid.UUID
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent.AgentSurveyMessage.survey_id
```

````

````{py:attribute} day
:canonical: agentsociety.webapi.api.agent.AgentSurveyMessage.day
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent.AgentSurveyMessage.day
```

````

````{py:attribute} t
:canonical: agentsociety.webapi.api.agent.AgentSurveyMessage.t
:type: float
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent.AgentSurveyMessage.t
```

````

`````

````{py:function} post_agent_survey(request: fastapi.Request, exp_id: uuid.UUID, agent_id: int, message: agentsociety.webapi.api.agent.AgentSurveyMessage = Body(...)) -> agentsociety.webapi.models.ApiResponseWrapper[None]
:canonical: agentsociety.webapi.api.agent.post_agent_survey
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent.post_agent_survey
```
````
