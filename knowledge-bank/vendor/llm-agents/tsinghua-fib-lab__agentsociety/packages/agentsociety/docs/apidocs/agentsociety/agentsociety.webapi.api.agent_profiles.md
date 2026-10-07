# {py:mod}`agentsociety.webapi.api.agent_profiles`

```{py:module} agentsociety.webapi.api.agent_profiles
```

```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`SaveProfileRequest <agentsociety.webapi.api.agent_profiles.SaveProfileRequest>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.SaveProfileRequest
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`list_agent_profiles <agentsociety.webapi.api.agent_profiles.list_agent_profiles>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.list_agent_profiles
    :summary:
    ```
* - {py:obj}`get_agent_profile <agentsociety.webapi.api.agent_profiles.get_agent_profile>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.get_agent_profile
    :summary:
    ```
* - {py:obj}`delete_agent_profile <agentsociety.webapi.api.agent_profiles.delete_agent_profile>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.delete_agent_profile
    :summary:
    ```
* - {py:obj}`validate_and_process_ids <agentsociety.webapi.api.agent_profiles.validate_and_process_ids>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.validate_and_process_ids
    :summary:
    ```
* - {py:obj}`upload_agent_profile <agentsociety.webapi.api.agent_profiles.upload_agent_profile>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.upload_agent_profile
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.webapi.api.agent_profiles.__all__>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.__all__
    :summary:
    ```
* - {py:obj}`router <agentsociety.webapi.api.agent_profiles.router>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.router
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.webapi.api.agent_profiles.__all__
:value: >
   ['router']

```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.__all__
```

````

````{py:data} router
:canonical: agentsociety.webapi.api.agent_profiles.router
:value: >
   'APIRouter(...)'

```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.router
```

````

`````{py:class} SaveProfileRequest(/, **data: typing.Any)
:canonical: agentsociety.webapi.api.agent_profiles.SaveProfileRequest

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.SaveProfileRequest
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.SaveProfileRequest.__init__
```

````{py:attribute} name
:canonical: agentsociety.webapi.api.agent_profiles.SaveProfileRequest.name
:type: str
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.SaveProfileRequest.name
```

````

````{py:attribute} description
:canonical: agentsociety.webapi.api.agent_profiles.SaveProfileRequest.description
:type: typing.Optional[str]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.SaveProfileRequest.description
```

````

````{py:attribute} agent_type
:canonical: agentsociety.webapi.api.agent_profiles.SaveProfileRequest.agent_type
:type: str
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.SaveProfileRequest.agent_type
```

````

````{py:attribute} file_path
:canonical: agentsociety.webapi.api.agent_profiles.SaveProfileRequest.file_path
:type: str
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.SaveProfileRequest.file_path
```

````

`````

````{py:function} list_agent_profiles(request: fastapi.Request) -> agentsociety.webapi.models.ApiResponseWrapper[typing.List[agentsociety.webapi.models.agent_profiles.ApiAgentProfile]]
:canonical: agentsociety.webapi.api.agent_profiles.list_agent_profiles
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.list_agent_profiles
```
````

````{py:function} get_agent_profile(request: fastapi.Request, profile_id: uuid.UUID) -> agentsociety.webapi.models.ApiResponseWrapper[typing.List[typing.Dict[str, typing.Any]]]
:canonical: agentsociety.webapi.api.agent_profiles.get_agent_profile
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.get_agent_profile
```
````

````{py:function} delete_agent_profile(request: fastapi.Request, profile_id: uuid.UUID) -> agentsociety.webapi.models.ApiResponseWrapper[typing.Dict[str, str]]
:canonical: agentsociety.webapi.api.agent_profiles.delete_agent_profile
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.delete_agent_profile
```
````

````{py:function} validate_and_process_ids(data: typing.List[typing.Dict[str, typing.Any]]) -> typing.List[typing.Dict[str, typing.Any]]
:canonical: agentsociety.webapi.api.agent_profiles.validate_and_process_ids

```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.validate_and_process_ids
```
````

````{py:function} upload_agent_profile(request: fastapi.Request, file: fastapi.UploadFile = File(...), name: typing.Optional[str] = Form(None), description: typing.Optional[str] = Form(None)) -> agentsociety.webapi.models.ApiResponseWrapper[agentsociety.webapi.models.agent_profiles.ApiAgentProfile]
:canonical: agentsociety.webapi.api.agent_profiles.upload_agent_profile
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent_profiles.upload_agent_profile
```
````
