# {py:mod}`agentsociety.webapi.models`

```{py:module} agentsociety.webapi.models
```

```{autodoc2-docstring} agentsociety.webapi.models
:allowtitles:
```

## Submodules

```{toctree}
:titlesonly:
:maxdepth: 1

agentsociety.webapi.models.metric
agentsociety.webapi.models.agent_profiles
agentsociety.webapi.models.agent
agentsociety.webapi.models.experiment
agentsociety.webapi.models._base
agentsociety.webapi.models.config
agentsociety.webapi.models.agent_template
agentsociety.webapi.models.survey
```

## Package Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`ApiResponseWrapper <agentsociety.webapi.models.ApiResponseWrapper>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.ApiResponseWrapper
    :summary:
    ```
* - {py:obj}`ApiPaginatedResponseWrapper <agentsociety.webapi.models.ApiPaginatedResponseWrapper>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.ApiPaginatedResponseWrapper
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.webapi.models.__all__>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.__all__
    :summary:
    ```
* - {py:obj}`T <agentsociety.webapi.models.T>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.T
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.webapi.models.__all__
:value: >
   ['ApiResponseWrapper']

```{autodoc2-docstring} agentsociety.webapi.models.__all__
```

````

````{py:data} T
:canonical: agentsociety.webapi.models.T
:value: >
   'TypeVar(...)'

```{autodoc2-docstring} agentsociety.webapi.models.T
```

````

`````{py:class} ApiResponseWrapper(/, **data: typing.Any)
:canonical: agentsociety.webapi.models.ApiResponseWrapper

Bases: {py:obj}`pydantic.BaseModel`, {py:obj}`typing.Generic`\[{py:obj}`agentsociety.webapi.models.T`\]

```{autodoc2-docstring} agentsociety.webapi.models.ApiResponseWrapper
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.ApiResponseWrapper.__init__
```

````{py:attribute} data
:canonical: agentsociety.webapi.models.ApiResponseWrapper.data
:type: agentsociety.webapi.models.T
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.webapi.models.ApiResponseWrapper.data
```

````

`````

`````{py:class} ApiPaginatedResponseWrapper(/, **data: typing.Any)
:canonical: agentsociety.webapi.models.ApiPaginatedResponseWrapper

Bases: {py:obj}`pydantic.BaseModel`, {py:obj}`typing.Generic`\[{py:obj}`agentsociety.webapi.models.T`\]

```{autodoc2-docstring} agentsociety.webapi.models.ApiPaginatedResponseWrapper
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.ApiPaginatedResponseWrapper.__init__
```

````{py:attribute} total
:canonical: agentsociety.webapi.models.ApiPaginatedResponseWrapper.total
:type: int
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.webapi.models.ApiPaginatedResponseWrapper.total
```

````

````{py:attribute} data
:canonical: agentsociety.webapi.models.ApiPaginatedResponseWrapper.data
:type: typing.List[agentsociety.webapi.models.T]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.webapi.models.ApiPaginatedResponseWrapper.data
```

````

`````
