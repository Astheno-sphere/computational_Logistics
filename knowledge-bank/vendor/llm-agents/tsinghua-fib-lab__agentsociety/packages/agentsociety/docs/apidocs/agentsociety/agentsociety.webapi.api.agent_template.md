# {py:mod}`agentsociety.webapi.api.agent_template`

```{py:module} agentsociety.webapi.api.agent_template
```

```{autodoc2-docstring} agentsociety.webapi.api.agent_template
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`ParamOption <agentsociety.webapi.api.agent_template.ParamOption>`
  -
* - {py:obj}`Param <agentsociety.webapi.api.agent_template.Param>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.Param
    :summary:
    ```
* - {py:obj}`NameTypeDescription <agentsociety.webapi.api.agent_template.NameTypeDescription>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.NameTypeDescription
    :summary:
    ```
* - {py:obj}`AgentParam <agentsociety.webapi.api.agent_template.AgentParam>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.AgentParam
    :summary:
    ```
* - {py:obj}`BlockParam <agentsociety.webapi.api.agent_template.BlockParam>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.BlockParam
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`list_agent_templates <agentsociety.webapi.api.agent_template.list_agent_templates>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.list_agent_templates
    :summary:
    ```
* - {py:obj}`get_agent_template <agentsociety.webapi.api.agent_template.get_agent_template>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.get_agent_template
    :summary:
    ```
* - {py:obj}`convert_agent_template_from_db_to_api <agentsociety.webapi.api.agent_template.convert_agent_template_from_db_to_api>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.convert_agent_template_from_db_to_api
    :summary:
    ```
* - {py:obj}`create_agent_template <agentsociety.webapi.api.agent_template.create_agent_template>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.create_agent_template
    :summary:
    ```
* - {py:obj}`update_agent_template <agentsociety.webapi.api.agent_template.update_agent_template>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.update_agent_template
    :summary:
    ```
* - {py:obj}`delete_agent_template <agentsociety.webapi.api.agent_template.delete_agent_template>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.delete_agent_template
    :summary:
    ```
* - {py:obj}`get_agent_blocks <agentsociety.webapi.api.agent_template.get_agent_blocks>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.get_agent_blocks
    :summary:
    ```
* - {py:obj}`simplify_type <agentsociety.webapi.api.agent_template.simplify_type>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.simplify_type
    :summary:
    ```
* - {py:obj}`parse_pydantic_to_table <agentsociety.webapi.api.agent_template.parse_pydantic_to_table>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.parse_pydantic_to_table
    :summary:
    ```
* - {py:obj}`parse_pydantic_to_antd_form <agentsociety.webapi.api.agent_template.parse_pydantic_to_antd_form>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.parse_pydantic_to_antd_form
    :summary:
    ```
* - {py:obj}`get_agent_param <agentsociety.webapi.api.agent_template.get_agent_param>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.get_agent_param
    :summary:
    ```
* - {py:obj}`get_block_param <agentsociety.webapi.api.agent_template.get_block_param>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.get_block_param
    :summary:
    ```
* - {py:obj}`get_agent_classes <agentsociety.webapi.api.agent_template.get_agent_classes>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.get_agent_classes
    :summary:
    ```
* - {py:obj}`get_workflow_functions <agentsociety.webapi.api.agent_template.get_workflow_functions>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.get_workflow_functions
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.webapi.api.agent_template.__all__>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.__all__
    :summary:
    ```
* - {py:obj}`router <agentsociety.webapi.api.agent_template.router>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.agent_template.router
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.webapi.api.agent_template.__all__
:value: >
   ['router']

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.__all__
```

````

````{py:data} router
:canonical: agentsociety.webapi.api.agent_template.router
:value: >
   'APIRouter(...)'

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.router
```

````

````{py:function} list_agent_templates(request: fastapi.Request) -> agentsociety.webapi.models.ApiResponseWrapper[typing.List[agentsociety.webapi.models.agent_template.ApiAgentTemplate]]
:canonical: agentsociety.webapi.api.agent_template.list_agent_templates
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.list_agent_templates
```
````

````{py:function} get_agent_template(request: fastapi.Request, template_id: str) -> agentsociety.webapi.models.ApiResponseWrapper[agentsociety.webapi.models.agent_template.ApiAgentTemplate]
:canonical: agentsociety.webapi.api.agent_template.get_agent_template
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.get_agent_template
```
````

````{py:function} convert_agent_template_from_db_to_api(template: agentsociety.webapi.models.agent_template.AgentTemplateDB) -> agentsociety.webapi.models.agent_template.ApiAgentTemplate
:canonical: agentsociety.webapi.api.agent_template.convert_agent_template_from_db_to_api

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.convert_agent_template_from_db_to_api
```
````

````{py:function} create_agent_template(request: fastapi.Request, template: agentsociety.webapi.models.agent_template.ApiAgentTemplate = Body(...)) -> agentsociety.webapi.models.ApiResponseWrapper[agentsociety.webapi.models.agent_template.ApiAgentTemplate]
:canonical: agentsociety.webapi.api.agent_template.create_agent_template
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.create_agent_template
```
````

````{py:function} update_agent_template(request: fastapi.Request, template_id: str, template: agentsociety.webapi.models.agent_template.ApiAgentTemplate = Body(...)) -> agentsociety.webapi.models.ApiResponseWrapper[agentsociety.webapi.models.agent_template.ApiAgentTemplate]
:canonical: agentsociety.webapi.api.agent_template.update_agent_template
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.update_agent_template
```
````

````{py:function} delete_agent_template(request: fastapi.Request, template_id: str) -> agentsociety.webapi.models.ApiResponseWrapper[typing.Dict[str, str]]
:canonical: agentsociety.webapi.api.agent_template.delete_agent_template
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.delete_agent_template
```
````

````{py:function} get_agent_blocks(request: fastapi.Request) -> agentsociety.webapi.models.ApiResponseWrapper[typing.List[str]]
:canonical: agentsociety.webapi.api.agent_template.get_agent_blocks
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.get_agent_blocks
```
````

`````{py:class} ParamOption(/, **data: typing.Any)
:canonical: agentsociety.webapi.api.agent_template.ParamOption

Bases: {py:obj}`pydantic.BaseModel`

````{py:attribute} label
:canonical: agentsociety.webapi.api.agent_template.ParamOption.label
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.ParamOption.label
```

````

````{py:attribute} value
:canonical: agentsociety.webapi.api.agent_template.ParamOption.value
:type: typing.Any
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.ParamOption.value
```

````

`````

`````{py:class} Param(/, **data: typing.Any)
:canonical: agentsociety.webapi.api.agent_template.Param

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.Param
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.Param.__init__
```

````{py:attribute} name
:canonical: agentsociety.webapi.api.agent_template.Param.name
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.Param.name
```

````

````{py:attribute} required
:canonical: agentsociety.webapi.api.agent_template.Param.required
:type: bool
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.Param.required
```

````

````{py:attribute} default
:canonical: agentsociety.webapi.api.agent_template.Param.default
:type: typing.Optional[typing.Any]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.Param.default
```

````

````{py:attribute} description
:canonical: agentsociety.webapi.api.agent_template.Param.description
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.Param.description
```

````

````{py:attribute} type
:canonical: agentsociety.webapi.api.agent_template.Param.type
:type: typing.Literal[str, int, float, bool, sqlalchemy.select, select_multiple]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.Param.type
```

````

````{py:attribute} options
:canonical: agentsociety.webapi.api.agent_template.Param.options
:type: typing.List[agentsociety.webapi.api.agent_template.ParamOption]
:value: >
   []

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.Param.options
```

````

`````

`````{py:class} NameTypeDescription(/, **data: typing.Any)
:canonical: agentsociety.webapi.api.agent_template.NameTypeDescription

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.NameTypeDescription
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.NameTypeDescription.__init__
```

````{py:attribute} name
:canonical: agentsociety.webapi.api.agent_template.NameTypeDescription.name
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.NameTypeDescription.name
```

````

````{py:attribute} type
:canonical: agentsociety.webapi.api.agent_template.NameTypeDescription.type
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.NameTypeDescription.type
```

````

````{py:attribute} description
:canonical: agentsociety.webapi.api.agent_template.NameTypeDescription.description
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.NameTypeDescription.description
```

````

`````

````{py:function} simplify_type(type_annotation)
:canonical: agentsociety.webapi.api.agent_template.simplify_type

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.simplify_type
```
````

````{py:function} parse_pydantic_to_table(model_class: type[pydantic.BaseModel], exclude_fields: list[str] = []) -> list[agentsociety.webapi.api.agent_template.NameTypeDescription]
:canonical: agentsociety.webapi.api.agent_template.parse_pydantic_to_table

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.parse_pydantic_to_table
```
````

````{py:function} parse_pydantic_to_antd_form(model_class: type[pydantic.BaseModel], exclude_fields: list[str] = []) -> list[agentsociety.webapi.api.agent_template.Param]
:canonical: agentsociety.webapi.api.agent_template.parse_pydantic_to_antd_form

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.parse_pydantic_to_antd_form
```
````

`````{py:class} AgentParam(/, **data: typing.Any)
:canonical: agentsociety.webapi.api.agent_template.AgentParam

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.AgentParam
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.AgentParam.__init__
```

````{py:attribute} params_type
:canonical: agentsociety.webapi.api.agent_template.AgentParam.params_type
:type: typing.List[agentsociety.webapi.api.agent_template.Param]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.AgentParam.params_type
```

````

````{py:attribute} context
:canonical: agentsociety.webapi.api.agent_template.AgentParam.context
:type: typing.List[agentsociety.webapi.api.agent_template.NameTypeDescription]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.AgentParam.context
```

````

````{py:attribute} status_attributes
:canonical: agentsociety.webapi.api.agent_template.AgentParam.status_attributes
:type: typing.List[agentsociety.webapi.api.agent_template.NameTypeDescription]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.AgentParam.status_attributes
```

````

`````

````{py:function} get_agent_param(request: fastapi.Request, agent_type: str, agent_class: str) -> agentsociety.webapi.models.ApiResponseWrapper[agentsociety.webapi.api.agent_template.AgentParam]
:canonical: agentsociety.webapi.api.agent_template.get_agent_param
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.get_agent_param
```
````

`````{py:class} BlockParam(/, **data: typing.Any)
:canonical: agentsociety.webapi.api.agent_template.BlockParam

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.BlockParam
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.BlockParam.__init__
```

````{py:attribute} params_type
:canonical: agentsociety.webapi.api.agent_template.BlockParam.params_type
:type: typing.List[agentsociety.webapi.api.agent_template.Param]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.BlockParam.params_type
```

````

````{py:attribute} context
:canonical: agentsociety.webapi.api.agent_template.BlockParam.context
:type: typing.List[agentsociety.webapi.api.agent_template.NameTypeDescription]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.BlockParam.context
```

````

`````

````{py:function} get_block_param(request: fastapi.Request, block_type: str) -> agentsociety.webapi.models.ApiResponseWrapper[agentsociety.webapi.api.agent_template.BlockParam]
:canonical: agentsociety.webapi.api.agent_template.get_block_param
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.get_block_param
```
````

````{py:function} get_agent_classes(request: fastapi.Request, agent_type: str) -> agentsociety.webapi.models.ApiResponseWrapper[typing.List[typing.Dict[str, str]]]
:canonical: agentsociety.webapi.api.agent_template.get_agent_classes
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.get_agent_classes
```
````

````{py:function} get_workflow_functions(request: fastapi.Request) -> agentsociety.webapi.models.ApiResponseWrapper[typing.List[str]]
:canonical: agentsociety.webapi.api.agent_template.get_workflow_functions
:async:

```{autodoc2-docstring} agentsociety.webapi.api.agent_template.get_workflow_functions
```
````
