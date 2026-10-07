# {py:mod}`agentsociety.storage.database`

```{py:module} agentsociety.storage.database
```

```{autodoc2-docstring} agentsociety.storage.database
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`DatabaseConfig <agentsociety.storage.database.DatabaseConfig>`
  - ```{autodoc2-docstring} agentsociety.storage.database.DatabaseConfig
    :summary:
    ```
* - {py:obj}`DatabaseWriter <agentsociety.storage.database.DatabaseWriter>`
  - ```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_create_async_engine_from_config <agentsociety.storage.database._create_async_engine_from_config>`
  - ```{autodoc2-docstring} agentsociety.storage.database._create_async_engine_from_config
    :summary:
    ```
* - {py:obj}`_create_tables <agentsociety.storage.database._create_tables>`
  - ```{autodoc2-docstring} agentsociety.storage.database._create_tables
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.storage.database.__all__>`
  - ```{autodoc2-docstring} agentsociety.storage.database.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.storage.database.__all__
:value: >
   ['DatabaseWriter', 'DatabaseConfig']

```{autodoc2-docstring} agentsociety.storage.database.__all__
```

````

`````{py:class} DatabaseConfig(/, **data: typing.Any)
:canonical: agentsociety.storage.database.DatabaseConfig

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.storage.database.DatabaseConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.storage.database.DatabaseConfig.__init__
```

````{py:attribute} enabled
:canonical: agentsociety.storage.database.DatabaseConfig.enabled
:type: bool
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.storage.database.DatabaseConfig.enabled
```

````

````{py:attribute} db_type
:canonical: agentsociety.storage.database.DatabaseConfig.db_type
:type: typing.Literal[postgresql, sqlite]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.storage.database.DatabaseConfig.db_type
```

````

````{py:attribute} pg_dsn
:canonical: agentsociety.storage.database.DatabaseConfig.pg_dsn
:type: typing.Optional[str]
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.storage.database.DatabaseConfig.pg_dsn
```

````

````{py:method} validate_config()
:canonical: agentsociety.storage.database.DatabaseConfig.validate_config

```{autodoc2-docstring} agentsociety.storage.database.DatabaseConfig.validate_config
```

````

````{py:method} get_dsn(sqlite_path: pathlib.Path)
:canonical: agentsociety.storage.database.DatabaseConfig.get_dsn

```{autodoc2-docstring} agentsociety.storage.database.DatabaseConfig.get_dsn
```

````

`````

````{py:function} _create_async_engine_from_config(config: agentsociety.storage.database.DatabaseConfig, sqlite_path: pathlib.Path)
:canonical: agentsociety.storage.database._create_async_engine_from_config

```{autodoc2-docstring} agentsociety.storage.database._create_async_engine_from_config
```
````

````{py:function} _create_tables(exp_id: str, config: agentsociety.storage.database.DatabaseConfig, sqlite_path: pathlib.Path)
:canonical: agentsociety.storage.database._create_tables
:async:

```{autodoc2-docstring} agentsociety.storage.database._create_tables
```
````

`````{py:class} DatabaseWriter(tenant_id: str, exp_id: str, config: agentsociety.storage.database.DatabaseConfig, home_dir: str)
:canonical: agentsociety.storage.database.DatabaseWriter

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.__init__
```

````{py:method} init()
:canonical: agentsociety.storage.database.DatabaseWriter.init
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.init
```

````

````{py:method} _init_tables()
:canonical: agentsociety.storage.database.DatabaseWriter._init_tables

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter._init_tables
```

````

````{py:method} _create_tables()
:canonical: agentsociety.storage.database.DatabaseWriter._create_tables
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter._create_tables
```

````

````{py:method} _get_insert_func()
:canonical: agentsociety.storage.database.DatabaseWriter._get_insert_func

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter._get_insert_func
```

````

````{py:property} exp_info_file
:canonical: agentsociety.storage.database.DatabaseWriter.exp_info_file

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.exp_info_file
```

````

````{py:property} storage_path
:canonical: agentsociety.storage.database.DatabaseWriter.storage_path

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.storage_path
```

````

````{py:method} read_dialogs(day: typing.Optional[int] = None, speaker: typing.Optional[str] = None, dialog_type: typing.Optional[int] = None, start_t: typing.Optional[float] = None, end_t: typing.Optional[float] = None, limit: typing.Optional[int] = None, offset: typing.Optional[int] = None, order_by: str = 'created_at', order_direction: str = 'asc') -> typing.List[typing.Dict[str, typing.Any]]
:canonical: agentsociety.storage.database.DatabaseWriter.read_dialogs
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.read_dialogs
```

````

````{py:method} read_statuses(day: typing.Optional[int] = None, agent_id: typing.Optional[int] = None, start_t: typing.Optional[float] = None, end_t: typing.Optional[float] = None, action: typing.Optional[str] = None, limit: typing.Optional[int] = None, offset: typing.Optional[int] = None, order_by: str = 'created_at', order_direction: str = 'asc') -> typing.List[typing.Dict[str, typing.Any]]
:canonical: agentsociety.storage.database.DatabaseWriter.read_statuses
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.read_statuses
```

````

````{py:method} read_surveys(day: typing.Optional[int] = None, survey_id: typing.Optional[str] = None, start_t: typing.Optional[float] = None, end_t: typing.Optional[float] = None, limit: typing.Optional[int] = None, offset: typing.Optional[int] = None, order_by: str = 'created_at', order_direction: str = 'asc') -> typing.List[typing.Dict[str, typing.Any]]
:canonical: agentsociety.storage.database.DatabaseWriter.read_surveys
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.read_surveys
```

````

````{py:method} read_profiles() -> typing.List[typing.Dict[str, typing.Any]]
:canonical: agentsociety.storage.database.DatabaseWriter.read_profiles
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.read_profiles
```

````

````{py:method} read_global_prompts(day: typing.Optional[int] = None, start_t: typing.Optional[float] = None, end_t: typing.Optional[float] = None, limit: typing.Optional[int] = None, offset: typing.Optional[int] = None, order_by: str = 'created_at', order_direction: str = 'asc') -> typing.List[typing.Dict[str, typing.Any]]
:canonical: agentsociety.storage.database.DatabaseWriter.read_global_prompts
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.read_global_prompts
```

````

````{py:method} read_task_results(agent_id: typing.Optional[int] = None, limit: typing.Optional[int] = None, offset: typing.Optional[int] = None, order_by: str = 'created_at', order_direction: str = 'asc') -> typing.List[typing.Dict[str, typing.Any]]
:canonical: agentsociety.storage.database.DatabaseWriter.read_task_results
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.read_task_results
```

````

````{py:method} read_metrics(key: typing.Optional[str] = None, step: typing.Optional[int] = None, start_step: typing.Optional[int] = None, end_step: typing.Optional[int] = None, limit: typing.Optional[int] = None, offset: typing.Optional[int] = None, order_by: str = 'step', order_direction: str = 'asc') -> typing.List[typing.Dict[str, typing.Any]]
:canonical: agentsociety.storage.database.DatabaseWriter.read_metrics
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.read_metrics
```

````

````{py:method} get_statistics() -> typing.Dict[str, typing.Any]
:canonical: agentsociety.storage.database.DatabaseWriter.get_statistics
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.get_statistics
```

````

````{py:method} write_dialogs(rows: list[agentsociety.storage.type.StorageDialog])
:canonical: agentsociety.storage.database.DatabaseWriter.write_dialogs
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.write_dialogs
```

````

````{py:method} write_statuses(rows: list[agentsociety.storage.type.StorageStatus])
:canonical: agentsociety.storage.database.DatabaseWriter.write_statuses
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.write_statuses
```

````

````{py:method} write_profiles(rows: list[agentsociety.storage.type.StorageProfile])
:canonical: agentsociety.storage.database.DatabaseWriter.write_profiles
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.write_profiles
```

````

````{py:method} write_surveys(rows: list[agentsociety.storage.type.StorageSurvey])
:canonical: agentsociety.storage.database.DatabaseWriter.write_surveys
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.write_surveys
```

````

````{py:method} write_global_prompt(prompt_info: agentsociety.storage.type.StorageGlobalPrompt)
:canonical: agentsociety.storage.database.DatabaseWriter.write_global_prompt
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.write_global_prompt
```

````

````{py:method} write_task_result(rows: list[agentsociety.storage.type.StorageTaskResult])
:canonical: agentsociety.storage.database.DatabaseWriter.write_task_result
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.write_task_result
```

````

````{py:method} log_metric(metrics: list[tuple[str, float, int]])
:canonical: agentsociety.storage.database.DatabaseWriter.log_metric
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.log_metric
```

````

````{py:method} update_exp_info(exp_info: agentsociety.storage.type.StorageExpInfo)
:canonical: agentsociety.storage.database.DatabaseWriter.update_exp_info
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.update_exp_info
```

````

````{py:method} fetch_pending_dialogs()
:canonical: agentsociety.storage.database.DatabaseWriter.fetch_pending_dialogs
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.fetch_pending_dialogs
```

````

````{py:method} mark_dialogs_as_processed(pending_ids: list[int])
:canonical: agentsociety.storage.database.DatabaseWriter.mark_dialogs_as_processed
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.mark_dialogs_as_processed
```

````

````{py:method} fetch_pending_surveys()
:canonical: agentsociety.storage.database.DatabaseWriter.fetch_pending_surveys
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.fetch_pending_surveys
```

````

````{py:method} mark_surveys_as_processed(pending_ids: list[int])
:canonical: agentsociety.storage.database.DatabaseWriter.mark_surveys_as_processed
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.mark_surveys_as_processed
```

````

````{py:method} close()
:canonical: agentsociety.storage.database.DatabaseWriter.close
:async:

```{autodoc2-docstring} agentsociety.storage.database.DatabaseWriter.close
```

````

`````
