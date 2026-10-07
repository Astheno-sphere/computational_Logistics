# {py:mod}`agentsociety.storage.model`

```{py:module} agentsociety.storage.model
```

```{autodoc2-docstring} agentsociety.storage.model
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`Experiment <agentsociety.storage.model.Experiment>`
  - ```{autodoc2-docstring} agentsociety.storage.model.Experiment
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`agent_profile <agentsociety.storage.model.agent_profile>`
  - ```{autodoc2-docstring} agentsociety.storage.model.agent_profile
    :summary:
    ```
* - {py:obj}`agent_status <agentsociety.storage.model.agent_status>`
  - ```{autodoc2-docstring} agentsociety.storage.model.agent_status
    :summary:
    ```
* - {py:obj}`agent_survey <agentsociety.storage.model.agent_survey>`
  - ```{autodoc2-docstring} agentsociety.storage.model.agent_survey
    :summary:
    ```
* - {py:obj}`agent_dialog <agentsociety.storage.model.agent_dialog>`
  - ```{autodoc2-docstring} agentsociety.storage.model.agent_dialog
    :summary:
    ```
* - {py:obj}`global_prompt <agentsociety.storage.model.global_prompt>`
  - ```{autodoc2-docstring} agentsociety.storage.model.global_prompt
    :summary:
    ```
* - {py:obj}`pending_dialog <agentsociety.storage.model.pending_dialog>`
  - ```{autodoc2-docstring} agentsociety.storage.model.pending_dialog
    :summary:
    ```
* - {py:obj}`pending_survey <agentsociety.storage.model.pending_survey>`
  - ```{autodoc2-docstring} agentsociety.storage.model.pending_survey
    :summary:
    ```
* - {py:obj}`task_result <agentsociety.storage.model.task_result>`
  - ```{autodoc2-docstring} agentsociety.storage.model.task_result
    :summary:
    ```
* - {py:obj}`metric <agentsociety.storage.model.metric>`
  - ```{autodoc2-docstring} agentsociety.storage.model.metric
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.storage.model.__all__>`
  - ```{autodoc2-docstring} agentsociety.storage.model.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.storage.model.__all__
:value: >
   ['agent_profile', 'agent_status', 'agent_survey', 'agent_dialog', 'global_prompt', 'pending_dialog',...

```{autodoc2-docstring} agentsociety.storage.model.__all__
```

````

````{py:function} agent_profile(table_name: str)
:canonical: agentsociety.storage.model.agent_profile

```{autodoc2-docstring} agentsociety.storage.model.agent_profile
```
````

````{py:function} agent_status(table_name: str)
:canonical: agentsociety.storage.model.agent_status

```{autodoc2-docstring} agentsociety.storage.model.agent_status
```
````

````{py:function} agent_survey(table_name: str)
:canonical: agentsociety.storage.model.agent_survey

```{autodoc2-docstring} agentsociety.storage.model.agent_survey
```
````

````{py:function} agent_dialog(table_name: str)
:canonical: agentsociety.storage.model.agent_dialog

```{autodoc2-docstring} agentsociety.storage.model.agent_dialog
```
````

````{py:function} global_prompt(table_name: str)
:canonical: agentsociety.storage.model.global_prompt

```{autodoc2-docstring} agentsociety.storage.model.global_prompt
```
````

````{py:function} pending_dialog(table_name: str)
:canonical: agentsociety.storage.model.pending_dialog

```{autodoc2-docstring} agentsociety.storage.model.pending_dialog
```
````

````{py:function} pending_survey(table_name: str)
:canonical: agentsociety.storage.model.pending_survey

```{autodoc2-docstring} agentsociety.storage.model.pending_survey
```
````

````{py:function} task_result(table_name: str)
:canonical: agentsociety.storage.model.task_result

```{autodoc2-docstring} agentsociety.storage.model.task_result
```
````

````{py:function} metric(table_name: str)
:canonical: agentsociety.storage.model.metric

```{autodoc2-docstring} agentsociety.storage.model.metric
```
````

`````{py:class} Experiment
:canonical: agentsociety.storage.model.Experiment

Bases: {py:obj}`agentsociety.storage._base.Base`

```{autodoc2-docstring} agentsociety.storage.model.Experiment
```

````{py:attribute} __tablename__
:canonical: agentsociety.storage.model.Experiment.__tablename__
:value: >
   None

```{autodoc2-docstring} agentsociety.storage.model.Experiment.__tablename__
```

````

````{py:attribute} tenant_id
:canonical: agentsociety.storage.model.Experiment.tenant_id
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.storage.model.Experiment.tenant_id
```

````

````{py:attribute} id
:canonical: agentsociety.storage.model.Experiment.id
:type: sqlalchemy.orm.Mapped[uuid.UUID]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.storage.model.Experiment.id
```

````

````{py:attribute} name
:canonical: agentsociety.storage.model.Experiment.name
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.storage.model.Experiment.name
```

````

````{py:attribute} num_day
:canonical: agentsociety.storage.model.Experiment.num_day
:type: sqlalchemy.orm.Mapped[int]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.storage.model.Experiment.num_day
```

````

````{py:attribute} status
:canonical: agentsociety.storage.model.Experiment.status
:type: sqlalchemy.orm.Mapped[int]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.storage.model.Experiment.status
```

````

````{py:attribute} cur_day
:canonical: agentsociety.storage.model.Experiment.cur_day
:type: sqlalchemy.orm.Mapped[int]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.storage.model.Experiment.cur_day
```

````

````{py:attribute} cur_t
:canonical: agentsociety.storage.model.Experiment.cur_t
:type: sqlalchemy.orm.Mapped[float]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.storage.model.Experiment.cur_t
```

````

````{py:attribute} config
:canonical: agentsociety.storage.model.Experiment.config
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.storage.model.Experiment.config
```

````

````{py:attribute} error
:canonical: agentsociety.storage.model.Experiment.error
:type: sqlalchemy.orm.Mapped[str]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.storage.model.Experiment.error
```

````

````{py:attribute} input_tokens
:canonical: agentsociety.storage.model.Experiment.input_tokens
:type: sqlalchemy.orm.Mapped[int]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.storage.model.Experiment.input_tokens
```

````

````{py:attribute} output_tokens
:canonical: agentsociety.storage.model.Experiment.output_tokens
:type: sqlalchemy.orm.Mapped[int]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.storage.model.Experiment.output_tokens
```

````

````{py:attribute} created_at
:canonical: agentsociety.storage.model.Experiment.created_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.storage.model.Experiment.created_at
```

````

````{py:attribute} updated_at
:canonical: agentsociety.storage.model.Experiment.updated_at
:type: sqlalchemy.orm.Mapped[datetime.datetime]
:value: >
   'mapped_column(...)'

```{autodoc2-docstring} agentsociety.storage.model.Experiment.updated_at
```

````

````{py:property} agent_profile_tablename
:canonical: agentsociety.storage.model.Experiment.agent_profile_tablename

```{autodoc2-docstring} agentsociety.storage.model.Experiment.agent_profile_tablename
```

````

````{py:property} agent_status_tablename
:canonical: agentsociety.storage.model.Experiment.agent_status_tablename

```{autodoc2-docstring} agentsociety.storage.model.Experiment.agent_status_tablename
```

````

````{py:property} agent_dialog_tablename
:canonical: agentsociety.storage.model.Experiment.agent_dialog_tablename

```{autodoc2-docstring} agentsociety.storage.model.Experiment.agent_dialog_tablename
```

````

````{py:property} agent_survey_tablename
:canonical: agentsociety.storage.model.Experiment.agent_survey_tablename

```{autodoc2-docstring} agentsociety.storage.model.Experiment.agent_survey_tablename
```

````

````{py:property} global_prompt_tablename
:canonical: agentsociety.storage.model.Experiment.global_prompt_tablename

```{autodoc2-docstring} agentsociety.storage.model.Experiment.global_prompt_tablename
```

````

````{py:property} pending_dialog_tablename
:canonical: agentsociety.storage.model.Experiment.pending_dialog_tablename

```{autodoc2-docstring} agentsociety.storage.model.Experiment.pending_dialog_tablename
```

````

````{py:property} pending_survey_tablename
:canonical: agentsociety.storage.model.Experiment.pending_survey_tablename

```{autodoc2-docstring} agentsociety.storage.model.Experiment.pending_survey_tablename
```

````

````{py:property} task_result_tablename
:canonical: agentsociety.storage.model.Experiment.task_result_tablename

```{autodoc2-docstring} agentsociety.storage.model.Experiment.task_result_tablename
```

````

````{py:property} metric_tablename
:canonical: agentsociety.storage.model.Experiment.metric_tablename

```{autodoc2-docstring} agentsociety.storage.model.Experiment.metric_tablename
```

````

````{py:method} to_dict()
:canonical: agentsociety.storage.model.Experiment.to_dict

```{autodoc2-docstring} agentsociety.storage.model.Experiment.to_dict
```

````

`````
