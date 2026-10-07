# {py:mod}`agentsociety.webapi.models.survey`

```{py:module} agentsociety.webapi.models.survey
```

```{autodoc2-docstring} agentsociety.webapi.models.survey
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`Survey <agentsociety.webapi.models.survey.Survey>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.survey.Survey
    :summary:
    ```
* - {py:obj}`ApiSurvey <agentsociety.webapi.models.survey.ApiSurvey>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.survey.ApiSurvey
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.webapi.models.survey.__all__>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.survey.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.webapi.models.survey.__all__
:value: >
   ['Survey']

```{autodoc2-docstring} agentsociety.webapi.models.survey.__all__
```

````

`````{py:class} Survey
:canonical: agentsociety.webapi.models.survey.Survey

Bases: {py:obj}`agentsociety.webapi.models._base.Base`

```{autodoc2-docstring} agentsociety.webapi.models.survey.Survey
```

````{py:attribute} __tablename__
:canonical: agentsociety.webapi.models.survey.Survey.__tablename__
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.survey.Survey.__tablename__
```

````

````{py:attribute} tenant_id
:canonical: agentsociety.webapi.models.survey.Survey.tenant_id
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.survey.Survey.tenant_id
```

````

````{py:attribute} id
:canonical: agentsociety.webapi.models.survey.Survey.id
:type: sqlalchemy.orm.Mapped[uuid.UUID]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.survey.Survey.id
```

````

````{py:attribute} name
:canonical: agentsociety.webapi.models.survey.Survey.name
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.survey.Survey.name
```

````

````{py:attribute} data
:canonical: agentsociety.webapi.models.survey.Survey.data
:type: sqlalchemy.orm.Mapped[typing.Any]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.survey.Survey.data
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.survey.Survey.created_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.survey.Survey.created_at
```

````

````{py:attribute} updated_at
:canonical: agentsociety.webapi.models.survey.Survey.updated_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.survey.Survey.updated_at
```

````

`````

``````{py:class} ApiSurvey(/, **data: typing.Any)
:canonical: agentsociety.webapi.models.survey.ApiSurvey

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.models.survey.ApiSurvey
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.survey.ApiSurvey.__init__
```

````{py:attribute} id
:canonical: agentsociety.webapi.models.survey.ApiSurvey.id
:type: uuid.UUID
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.survey.ApiSurvey.id
```

````

````{py:attribute} name
:canonical: agentsociety.webapi.models.survey.ApiSurvey.name
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.survey.ApiSurvey.name
```

````

````{py:attribute} data
:canonical: agentsociety.webapi.models.survey.ApiSurvey.data
:type: typing.Any
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.survey.ApiSurvey.data
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.survey.ApiSurvey.created_at
:type: pydantic.AwareDatetime
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.survey.ApiSurvey.created_at
```

````

````{py:attribute} updated_at
:canonical: agentsociety.webapi.models.survey.ApiSurvey.updated_at
:type: pydantic.AwareDatetime
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.survey.ApiSurvey.updated_at
```

````

`````{py:class} Config
:canonical: agentsociety.webapi.models.survey.ApiSurvey.Config

```{autodoc2-docstring} agentsociety.webapi.models.survey.ApiSurvey.Config
```

````{py:attribute} from_attributes
:canonical: agentsociety.webapi.models.survey.ApiSurvey.Config.from_attributes
:value: >
   True

```{autodoc2-docstring} agentsociety.webapi.models.survey.ApiSurvey.Config.from_attributes
```

````

`````

``````
