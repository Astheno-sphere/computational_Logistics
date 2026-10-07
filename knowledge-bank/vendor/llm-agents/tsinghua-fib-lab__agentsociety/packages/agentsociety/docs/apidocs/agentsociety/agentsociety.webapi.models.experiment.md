# {py:mod}`agentsociety.webapi.models.experiment`

```{py:module} agentsociety.webapi.models.experiment
```

```{autodoc2-docstring} agentsociety.webapi.models.experiment
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`RunningExperiment <agentsociety.webapi.models.experiment.RunningExperiment>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.experiment.RunningExperiment
    :summary:
    ```
* - {py:obj}`ExperimentStatus <agentsociety.webapi.models.experiment.ExperimentStatus>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.experiment.ExperimentStatus
    :summary:
    ```
* - {py:obj}`ApiExperiment <agentsociety.webapi.models.experiment.ApiExperiment>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment
    :summary:
    ```
* - {py:obj}`ApiTime <agentsociety.webapi.models.experiment.ApiTime>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiTime
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.webapi.models.experiment.__all__>`
  - ```{autodoc2-docstring} agentsociety.webapi.models.experiment.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.webapi.models.experiment.__all__
:value: >
   ['Experiment', 'ExperimentStatus', 'ApiExperiment', 'ApiTime', 'RunningExperiment']

```{autodoc2-docstring} agentsociety.webapi.models.experiment.__all__
```

````

`````{py:class} RunningExperiment
:canonical: agentsociety.webapi.models.experiment.RunningExperiment

Bases: {py:obj}`agentsociety.webapi.models._base.Base`

```{autodoc2-docstring} agentsociety.webapi.models.experiment.RunningExperiment
```

````{py:attribute} __tablename__
:canonical: agentsociety.webapi.models.experiment.RunningExperiment.__tablename__
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.experiment.RunningExperiment.__tablename__
```

````

````{py:attribute} id
:canonical: agentsociety.webapi.models.experiment.RunningExperiment.id
:type: sqlalchemy.orm.Mapped[uuid.UUID]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.experiment.RunningExperiment.id
```

````

````{py:attribute} tenant_id
:canonical: agentsociety.webapi.models.experiment.RunningExperiment.tenant_id
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.experiment.RunningExperiment.tenant_id
```

````

````{py:attribute} callback_auth_token
:canonical: agentsociety.webapi.models.experiment.RunningExperiment.callback_auth_token
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.experiment.RunningExperiment.callback_auth_token
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.experiment.RunningExperiment.created_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.webapi.models.experiment.RunningExperiment.created_at
```

````

`````

`````{py:class} ExperimentStatus()
:canonical: agentsociety.webapi.models.experiment.ExperimentStatus

Bases: {py:obj}`enum.IntEnum`

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ExperimentStatus
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ExperimentStatus.__init__
```

````{py:attribute} NOT_STARTED
:canonical: agentsociety.webapi.models.experiment.ExperimentStatus.NOT_STARTED
:value: >
   0

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ExperimentStatus.NOT_STARTED
```

````

````{py:attribute} RUNNING
:canonical: agentsociety.webapi.models.experiment.ExperimentStatus.RUNNING
:value: >
   1

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ExperimentStatus.RUNNING
```

````

````{py:attribute} FINISHED
:canonical: agentsociety.webapi.models.experiment.ExperimentStatus.FINISHED
:value: >
   2

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ExperimentStatus.FINISHED
```

````

````{py:attribute} ERROR
:canonical: agentsociety.webapi.models.experiment.ExperimentStatus.ERROR
:value: >
   3

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ExperimentStatus.ERROR
```

````

````{py:attribute} STOPPED
:canonical: agentsociety.webapi.models.experiment.ExperimentStatus.STOPPED
:value: >
   4

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ExperimentStatus.STOPPED
```

````

`````

``````{py:class} ApiExperiment(/, **data: typing.Any)
:canonical: agentsociety.webapi.models.experiment.ApiExperiment

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment.__init__
```

````{py:attribute} tenant_id
:canonical: agentsociety.webapi.models.experiment.ApiExperiment.tenant_id
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment.tenant_id
```

````

````{py:attribute} id
:canonical: agentsociety.webapi.models.experiment.ApiExperiment.id
:type: uuid.UUID
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment.id
```

````

````{py:attribute} name
:canonical: agentsociety.webapi.models.experiment.ApiExperiment.name
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment.name
```

````

````{py:attribute} num_day
:canonical: agentsociety.webapi.models.experiment.ApiExperiment.num_day
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment.num_day
```

````

````{py:attribute} status
:canonical: agentsociety.webapi.models.experiment.ApiExperiment.status
:type: agentsociety.webapi.models.experiment.ExperimentStatus
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment.status
```

````

````{py:attribute} cur_day
:canonical: agentsociety.webapi.models.experiment.ApiExperiment.cur_day
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment.cur_day
```

````

````{py:attribute} cur_t
:canonical: agentsociety.webapi.models.experiment.ApiExperiment.cur_t
:type: float
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment.cur_t
```

````

````{py:attribute} config
:canonical: agentsociety.webapi.models.experiment.ApiExperiment.config
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment.config
```

````

````{py:attribute} error
:canonical: agentsociety.webapi.models.experiment.ApiExperiment.error
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment.error
```

````

````{py:attribute} input_tokens
:canonical: agentsociety.webapi.models.experiment.ApiExperiment.input_tokens
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment.input_tokens
```

````

````{py:attribute} output_tokens
:canonical: agentsociety.webapi.models.experiment.ApiExperiment.output_tokens
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment.output_tokens
```

````

````{py:attribute} created_at
:canonical: agentsociety.webapi.models.experiment.ApiExperiment.created_at
:type: pydantic.AwareDatetime
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment.created_at
```

````

````{py:attribute} updated_at
:canonical: agentsociety.webapi.models.experiment.ApiExperiment.updated_at
:type: pydantic.AwareDatetime
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment.updated_at
```

````

`````{py:class} Config
:canonical: agentsociety.webapi.models.experiment.ApiExperiment.Config

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment.Config
```

````{py:attribute} from_attributes
:canonical: agentsociety.webapi.models.experiment.ApiExperiment.Config.from_attributes
:value: >
   True

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiExperiment.Config.from_attributes
```

````

`````

``````

`````{py:class} ApiTime(/, **data: typing.Any)
:canonical: agentsociety.webapi.models.experiment.ApiTime

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiTime
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiTime.__init__
```

````{py:attribute} day
:canonical: agentsociety.webapi.models.experiment.ApiTime.day
:type: int
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiTime.day
```

````

````{py:attribute} t
:canonical: agentsociety.webapi.models.experiment.ApiTime.t
:type: float
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.models.experiment.ApiTime.t
```

````

`````
