# {py:mod}`agentsociety.webapi.models.agent_profiles`

```{py:module} agentsociety.webapi.models.agent_profiles
```

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`AgentProfile <agentsociety.webapi.models.agent_profiles.AgentProfile>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.AgentProfile
    :summary:
    ```
* - {py:obj}`ApiAgentProfile <agentsociety.webapi.models.agent_profiles.ApiAgentProfile>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.ApiAgentProfile
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.webapi.models.agent_profiles.__all__>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.webapi.models.agent_profiles.__all__
:value: >
   ['AgentProfile', 'ApiAgentProfile']

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.__all__
```

````

`````{py:class} AgentProfile
:canonical: agentsociety.webapi.models.agent_profiles.AgentProfile

Bases: {py:obj}`agentsociety.webapi.models._base.Base`

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.AgentProfile
```

````{py:attribute} __tablename__
:canonical: agentsociety.webapi.models.agent_profiles.AgentProfile.__tablename__
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.AgentProfile.__tablename__
```

````

````{py:attribute} tenant_id
:canonical: agentsociety.webapi.models.agent_profiles.AgentProfile.tenant_id
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.AgentProfile.tenant_id
```

````

````{py:attribute} id
:canonical: agentsociety.webapi.models.agent_profiles.AgentProfile.id
:type: sqlalchemy.orm.Mapped[uuid.UUID]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.AgentProfile.id
```

````

````{py:attribute} name
:canonical: agentsociety.webapi.models.agent_profiles.AgentProfile.name
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.AgentProfile.name
```

````

````{py:attribute} description
:canonical: agentsociety.webapi.models.agent_profiles.AgentProfile.description
:type: sqlalchemy.orm.Mapped[typing.Optional[str]]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.AgentProfile.description
```

````

````{py:attribute} agent_type
:canonical: agentsociety.webapi.models.agent_profiles.AgentProfile.agent_type
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.AgentProfile.agent_type
```

````

````{py:attribute} file_path
:canonical: agentsociety.webapi.models.agent_profiles.AgentProfile.file_path
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.AgentProfile.file_path
```

````

````{py:attribute} record_count
:canonical: agentsociety.webapi.models.agent_profiles.AgentProfile.record_count
:type: sqlalchemy.orm.Mapped[int]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.AgentProfile.record_count
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.agent_profiles.AgentProfile.created_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.AgentProfile.created_at
```

````

````{py:attribute} updated_at
:canonical: agentsociety.webapi.models.agent_profiles.AgentProfile.updated_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.AgentProfile.updated_at
```

````

`````

``````{py:class} ApiAgentProfile(/, **data: typing.Any)
:canonical: agentsociety.webapi.models.agent_profiles.ApiAgentProfile

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.ApiAgentProfile
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.ApiAgentProfile.__init__
```

````{py:attribute} tenant_id
:canonical: agentsociety.webapi.models.agent_profiles.ApiAgentProfile.tenant_id
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.ApiAgentProfile.tenant_id
```

````

````{py:attribute} id
:canonical: agentsociety.webapi.models.agent_profiles.ApiAgentProfile.id
:type: typing.Optional[uuid.UUID]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.ApiAgentProfile.id
```

````

````{py:attribute} name
:canonical: agentsociety.webapi.models.agent_profiles.ApiAgentProfile.name
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.ApiAgentProfile.name
```

````

````{py:attribute} description
:canonical: agentsociety.webapi.models.agent_profiles.ApiAgentProfile.description
:type: typing.Optional[str]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.ApiAgentProfile.description
```

````

````{py:attribute} agent_type
:canonical: agentsociety.webapi.models.agent_profiles.ApiAgentProfile.agent_type
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.ApiAgentProfile.agent_type
```

````

````{py:attribute} file_path
:canonical: agentsociety.webapi.models.agent_profiles.ApiAgentProfile.file_path
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.ApiAgentProfile.file_path
```

````

````{py:attribute} record_count
:canonical: agentsociety.webapi.models.agent_profiles.ApiAgentProfile.record_count
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.ApiAgentProfile.record_count
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.agent_profiles.ApiAgentProfile.created_at
:type: typing.Optional[pydantic.AwareDatetime]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.ApiAgentProfile.created_at
```

````

````{py:attribute} updated_at
:canonical: agentsociety.webapi.models.agent_profiles.ApiAgentProfile.updated_at
:type: typing.Optional[pydantic.AwareDatetime]
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.ApiAgentProfile.updated_at
```

````

`````{py:class} Config
:canonical: agentsociety.webapi.models.agent_profiles.ApiAgentProfile.Config

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.ApiAgentProfile.Config
```

````{py:attribute} from_attributes
:canonical: agentsociety.webapi.models.agent_profiles.ApiAgentProfile.Config.from_attributes
:value: >
   True

```{autodoc2-docstring} agentsociety.webapi.models.agent_profiles.ApiAgentProfile.Config.from_attributes
```

````

`````

``````
