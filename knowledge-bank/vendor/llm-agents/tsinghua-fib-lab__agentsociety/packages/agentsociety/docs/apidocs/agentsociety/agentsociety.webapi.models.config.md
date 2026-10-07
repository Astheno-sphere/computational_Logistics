# {py:mod}`agentsociety.webapi.models.config`

```{py:module} agentsociety.webapi.models.config
```

```{autodoc2-docstring} agentsociety.webapi.models.config
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`LLMConfig <agentsociety.webapi.models.config.LLMConfig>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.config.LLMConfig
    :summary:
    ```
* - {py:obj}`ApiLLMConfig <agentsociety.webapi.models.config.ApiLLMConfig>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.config.ApiLLMConfig
    :summary:
    ```
* - {py:obj}`MapConfig <agentsociety.webapi.models.config.MapConfig>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.config.MapConfig
    :summary:
    ```
* - {py:obj}`MapTempDownloadLink <agentsociety.webapi.models.config.MapTempDownloadLink>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.config.MapTempDownloadLink
    :summary:
    ```
* - {py:obj}`ApiMapConfig <agentsociety.webapi.models.config.ApiMapConfig>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.config.ApiMapConfig
    :summary:
    ```
* - {py:obj}`AgentConfig <agentsociety.webapi.models.config.AgentConfig>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.config.AgentConfig
    :summary:
    ```
* - {py:obj}`ApiAgentConfig <agentsociety.webapi.models.config.ApiAgentConfig>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.config.ApiAgentConfig
    :summary:
    ```
* - {py:obj}`WorkflowConfig <agentsociety.webapi.models.config.WorkflowConfig>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.config.WorkflowConfig
    :summary:
    ```
* - {py:obj}`ApiWorkflowConfig <agentsociety.webapi.models.config.ApiWorkflowConfig>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.config.ApiWorkflowConfig
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.webapi.models.config.__all__>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.config.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.webapi.models.config.__all__
:value: >
   ['RealLLMConfig', 'RealMapConfig', 'RealAgentsConfig', 'RealWorkflowStepConfig', 'LLMConfig', 'ApiLL...

```{autodoc2-docstring} agentsociety.webapi.models.config.__all__
```

````

`````{py:class} LLMConfig
:canonical: agentsociety.webapi.models.config.LLMConfig

Bases: {py:obj}`agentsociety.webapi.models._base.Base`

```{autodoc2-docstring} agentsociety.webapi.models.config.LLMConfig
```

````{py:attribute} __tablename__
:canonical: agentsociety.webapi.models.config.LLMConfig.__tablename__
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.LLMConfig.__tablename__
```

````

````{py:attribute} tenant_id
:canonical: agentsociety.webapi.models.config.LLMConfig.tenant_id
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.LLMConfig.tenant_id
```

````

````{py:attribute} id
:canonical: agentsociety.webapi.models.config.LLMConfig.id
:type: sqlalchemy.orm.Mapped[uuid.UUID]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.LLMConfig.id
```

````

````{py:attribute} name
:canonical: agentsociety.webapi.models.config.LLMConfig.name
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.LLMConfig.name
```

````

````{py:attribute} description
:canonical: agentsociety.webapi.models.config.LLMConfig.description
:type: sqlalchemy.orm.Mapped[typing.Optional[str]]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.LLMConfig.description
```

````

````{py:attribute} config
:canonical: agentsociety.webapi.models.config.LLMConfig.config
:type: sqlalchemy.orm.Mapped[typing.Any]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.LLMConfig.config
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.config.LLMConfig.created_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.LLMConfig.created_at
```

````

````{py:attribute} updated_at
:canonical: agentsociety.webapi.models.config.LLMConfig.updated_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.LLMConfig.updated_at
```

````

`````

``````{py:class} ApiLLMConfig(/, **data: typing.Any)
:canonical: agentsociety.webapi.models.config.ApiLLMConfig

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiLLMConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiLLMConfig.__init__
```

````{py:attribute} tenant_id
:canonical: agentsociety.webapi.models.config.ApiLLMConfig.tenant_id
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiLLMConfig.tenant_id
```

````

````{py:attribute} id
:canonical: agentsociety.webapi.models.config.ApiLLMConfig.id
:type: typing.Optional[uuid.UUID]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiLLMConfig.id
```

````

````{py:attribute} name
:canonical: agentsociety.webapi.models.config.ApiLLMConfig.name
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiLLMConfig.name
```

````

````{py:attribute} description
:canonical: agentsociety.webapi.models.config.ApiLLMConfig.description
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiLLMConfig.description
```

````

````{py:attribute} config
:canonical: agentsociety.webapi.models.config.ApiLLMConfig.config
:type: list[dict[str, typing.Any]]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiLLMConfig.config
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.config.ApiLLMConfig.created_at
:type: typing.Optional[pydantic.AwareDatetime]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiLLMConfig.created_at
```

````

````{py:attribute} updated_at
:canonical: agentsociety.webapi.models.config.ApiLLMConfig.updated_at
:type: typing.Optional[pydantic.AwareDatetime]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiLLMConfig.updated_at
```

````

`````{py:class} Config
:canonical: agentsociety.webapi.models.config.ApiLLMConfig.Config

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiLLMConfig.Config
```

````{py:attribute} from_attributes
:canonical: agentsociety.webapi.models.config.ApiLLMConfig.Config.from_attributes
:value: >
   True

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiLLMConfig.Config.from_attributes
```

````

`````

````{py:method} validate_config()
:canonical: agentsociety.webapi.models.config.ApiLLMConfig.validate_config

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiLLMConfig.validate_config
```

````

``````

`````{py:class} MapConfig
:canonical: agentsociety.webapi.models.config.MapConfig

Bases: {py:obj}`agentsociety.webapi.models._base.Base`

```{autodoc2-docstring} agentsociety.webapi.models.config.MapConfig
```

````{py:attribute} __tablename__
:canonical: agentsociety.webapi.models.config.MapConfig.__tablename__
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.MapConfig.__tablename__
```

````

````{py:attribute} tenant_id
:canonical: agentsociety.webapi.models.config.MapConfig.tenant_id
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.MapConfig.tenant_id
```

````

````{py:attribute} id
:canonical: agentsociety.webapi.models.config.MapConfig.id
:type: sqlalchemy.orm.Mapped[uuid.UUID]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.MapConfig.id
```

````

````{py:attribute} name
:canonical: agentsociety.webapi.models.config.MapConfig.name
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.MapConfig.name
```

````

````{py:attribute} description
:canonical: agentsociety.webapi.models.config.MapConfig.description
:type: sqlalchemy.orm.Mapped[typing.Optional[str]]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.MapConfig.description
```

````

````{py:attribute} config
:canonical: agentsociety.webapi.models.config.MapConfig.config
:type: sqlalchemy.orm.Mapped[typing.Any]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.MapConfig.config
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.config.MapConfig.created_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.MapConfig.created_at
```

````

````{py:attribute} updated_at
:canonical: agentsociety.webapi.models.config.MapConfig.updated_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.MapConfig.updated_at
```

````

`````

`````{py:class} MapTempDownloadLink
:canonical: agentsociety.webapi.models.config.MapTempDownloadLink

Bases: {py:obj}`agentsociety.webapi.models._base.Base`

```{autodoc2-docstring} agentsociety.webapi.models.config.MapTempDownloadLink
```

````{py:attribute} __tablename__
:canonical: agentsociety.webapi.models.config.MapTempDownloadLink.__tablename__
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.MapTempDownloadLink.__tablename__
```

````

````{py:attribute} id
:canonical: agentsociety.webapi.models.config.MapTempDownloadLink.id
:type: sqlalchemy.orm.Mapped[int]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.MapTempDownloadLink.id
```

````

````{py:attribute} map_config_id
:canonical: agentsociety.webapi.models.config.MapTempDownloadLink.map_config_id
:type: sqlalchemy.orm.Mapped[uuid.UUID]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.MapTempDownloadLink.map_config_id
```

````

````{py:attribute} token
:canonical: agentsociety.webapi.models.config.MapTempDownloadLink.token
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.MapTempDownloadLink.token
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.config.MapTempDownloadLink.created_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.MapTempDownloadLink.created_at
```

````

````{py:attribute} expire_at
:canonical: agentsociety.webapi.models.config.MapTempDownloadLink.expire_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.MapTempDownloadLink.expire_at
```

````

`````

``````{py:class} ApiMapConfig(/, **data: typing.Any)
:canonical: agentsociety.webapi.models.config.ApiMapConfig

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiMapConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiMapConfig.__init__
```

````{py:attribute} tenant_id
:canonical: agentsociety.webapi.models.config.ApiMapConfig.tenant_id
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiMapConfig.tenant_id
```

````

````{py:attribute} id
:canonical: agentsociety.webapi.models.config.ApiMapConfig.id
:type: typing.Optional[uuid.UUID]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiMapConfig.id
```

````

````{py:attribute} name
:canonical: agentsociety.webapi.models.config.ApiMapConfig.name
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiMapConfig.name
```

````

````{py:attribute} description
:canonical: agentsociety.webapi.models.config.ApiMapConfig.description
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiMapConfig.description
```

````

````{py:attribute} config
:canonical: agentsociety.webapi.models.config.ApiMapConfig.config
:type: dict[str, typing.Any]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiMapConfig.config
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.config.ApiMapConfig.created_at
:type: typing.Optional[pydantic.AwareDatetime]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiMapConfig.created_at
```

````

````{py:attribute} updated_at
:canonical: agentsociety.webapi.models.config.ApiMapConfig.updated_at
:type: typing.Optional[pydantic.AwareDatetime]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiMapConfig.updated_at
```

````

`````{py:class} Config
:canonical: agentsociety.webapi.models.config.ApiMapConfig.Config

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiMapConfig.Config
```

````{py:attribute} from_attributes
:canonical: agentsociety.webapi.models.config.ApiMapConfig.Config.from_attributes
:value: >
   True

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiMapConfig.Config.from_attributes
```

````

`````

````{py:method} validate_config()
:canonical: agentsociety.webapi.models.config.ApiMapConfig.validate_config

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiMapConfig.validate_config
```

````

``````

`````{py:class} AgentConfig
:canonical: agentsociety.webapi.models.config.AgentConfig

Bases: {py:obj}`agentsociety.webapi.models._base.Base`

```{autodoc2-docstring} agentsociety.webapi.models.config.AgentConfig
```

````{py:attribute} __tablename__
:canonical: agentsociety.webapi.models.config.AgentConfig.__tablename__
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.AgentConfig.__tablename__
```

````

````{py:attribute} tenant_id
:canonical: agentsociety.webapi.models.config.AgentConfig.tenant_id
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.AgentConfig.tenant_id
```

````

````{py:attribute} id
:canonical: agentsociety.webapi.models.config.AgentConfig.id
:type: sqlalchemy.orm.Mapped[uuid.UUID]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.AgentConfig.id
```

````

````{py:attribute} name
:canonical: agentsociety.webapi.models.config.AgentConfig.name
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.AgentConfig.name
```

````

````{py:attribute} description
:canonical: agentsociety.webapi.models.config.AgentConfig.description
:type: sqlalchemy.orm.Mapped[typing.Optional[str]]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.AgentConfig.description
```

````

````{py:attribute} config
:canonical: agentsociety.webapi.models.config.AgentConfig.config
:type: sqlalchemy.orm.Mapped[typing.Any]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.AgentConfig.config
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.config.AgentConfig.created_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.AgentConfig.created_at
```

````

````{py:attribute} updated_at
:canonical: agentsociety.webapi.models.config.AgentConfig.updated_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.AgentConfig.updated_at
```

````

`````

``````{py:class} ApiAgentConfig(/, **data: typing.Any)
:canonical: agentsociety.webapi.models.config.ApiAgentConfig

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiAgentConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiAgentConfig.__init__
```

````{py:attribute} tenant_id
:canonical: agentsociety.webapi.models.config.ApiAgentConfig.tenant_id
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiAgentConfig.tenant_id
```

````

````{py:attribute} id
:canonical: agentsociety.webapi.models.config.ApiAgentConfig.id
:type: typing.Optional[uuid.UUID]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiAgentConfig.id
```

````

````{py:attribute} name
:canonical: agentsociety.webapi.models.config.ApiAgentConfig.name
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiAgentConfig.name
```

````

````{py:attribute} description
:canonical: agentsociety.webapi.models.config.ApiAgentConfig.description
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiAgentConfig.description
```

````

````{py:attribute} config
:canonical: agentsociety.webapi.models.config.ApiAgentConfig.config
:type: dict[str, typing.Any]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiAgentConfig.config
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.config.ApiAgentConfig.created_at
:type: typing.Optional[pydantic.AwareDatetime]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiAgentConfig.created_at
```

````

````{py:attribute} updated_at
:canonical: agentsociety.webapi.models.config.ApiAgentConfig.updated_at
:type: typing.Optional[pydantic.AwareDatetime]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiAgentConfig.updated_at
```

````

`````{py:class} Config
:canonical: agentsociety.webapi.models.config.ApiAgentConfig.Config

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiAgentConfig.Config
```

````{py:attribute} from_attributes
:canonical: agentsociety.webapi.models.config.ApiAgentConfig.Config.from_attributes
:value: >
   True

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiAgentConfig.Config.from_attributes
```

````

`````

````{py:method} validate_config()
:canonical: agentsociety.webapi.models.config.ApiAgentConfig.validate_config

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiAgentConfig.validate_config
```

````

``````

`````{py:class} WorkflowConfig
:canonical: agentsociety.webapi.models.config.WorkflowConfig

Bases: {py:obj}`agentsociety.webapi.models._base.Base`

```{autodoc2-docstring} agentsociety.webapi.models.config.WorkflowConfig
```

````{py:attribute} __tablename__
:canonical: agentsociety.webapi.models.config.WorkflowConfig.__tablename__
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.WorkflowConfig.__tablename__
```

````

````{py:attribute} tenant_id
:canonical: agentsociety.webapi.models.config.WorkflowConfig.tenant_id
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.WorkflowConfig.tenant_id
```

````

````{py:attribute} id
:canonical: agentsociety.webapi.models.config.WorkflowConfig.id
:type: sqlalchemy.orm.Mapped[uuid.UUID]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.WorkflowConfig.id
```

````

````{py:attribute} name
:canonical: agentsociety.webapi.models.config.WorkflowConfig.name
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.WorkflowConfig.name
```

````

````{py:attribute} description
:canonical: agentsociety.webapi.models.config.WorkflowConfig.description
:type: sqlalchemy.orm.Mapped[typing.Optional[str]]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.WorkflowConfig.description
```

````

````{py:attribute} config
:canonical: agentsociety.webapi.models.config.WorkflowConfig.config
:type: sqlalchemy.orm.Mapped[typing.Any]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.WorkflowConfig.config
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.config.WorkflowConfig.created_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.WorkflowConfig.created_at
```

````

````{py:attribute} updated_at
:canonical: agentsociety.webapi.models.config.WorkflowConfig.updated_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.config.WorkflowConfig.updated_at
```

````

`````

``````{py:class} ApiWorkflowConfig(/, **data: typing.Any)
:canonical: agentsociety.webapi.models.config.ApiWorkflowConfig

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiWorkflowConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiWorkflowConfig.__init__
```

````{py:attribute} tenant_id
:canonical: agentsociety.webapi.models.config.ApiWorkflowConfig.tenant_id
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiWorkflowConfig.tenant_id
```

````

````{py:attribute} id
:canonical: agentsociety.webapi.models.config.ApiWorkflowConfig.id
:type: typing.Optional[uuid.UUID]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiWorkflowConfig.id
```

````

````{py:attribute} name
:canonical: agentsociety.webapi.models.config.ApiWorkflowConfig.name
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiWorkflowConfig.name
```

````

````{py:attribute} description
:canonical: agentsociety.webapi.models.config.ApiWorkflowConfig.description
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiWorkflowConfig.description
```

````

````{py:attribute} config
:canonical: agentsociety.webapi.models.config.ApiWorkflowConfig.config
:type: list[dict[str, typing.Any]]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiWorkflowConfig.config
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.config.ApiWorkflowConfig.created_at
:type: typing.Optional[pydantic.AwareDatetime]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiWorkflowConfig.created_at
```

````

````{py:attribute} updated_at
:canonical: agentsociety.webapi.models.config.ApiWorkflowConfig.updated_at
:type: typing.Optional[pydantic.AwareDatetime]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiWorkflowConfig.updated_at
```

````

`````{py:class} Config
:canonical: agentsociety.webapi.models.config.ApiWorkflowConfig.Config

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiWorkflowConfig.Config
```

````{py:attribute} from_attributes
:canonical: agentsociety.webapi.models.config.ApiWorkflowConfig.Config.from_attributes
:value: >
   True

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiWorkflowConfig.Config.from_attributes
```

````

`````

````{py:method} validate_config()
:canonical: agentsociety.webapi.models.config.ApiWorkflowConfig.validate_config

```{autodoc2-docstring} agentsociety.webapi.models.config.ApiWorkflowConfig.validate_config
```

````

``````
