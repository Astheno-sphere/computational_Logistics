# {py:mod}`agentsociety.executor.process`

```{py:module} agentsociety.executor.process
```

```{autodoc2-docstring} agentsociety.executor.process
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`ProcessExecutor <agentsociety.executor.process.ProcessExecutor>`
  - ```{autodoc2-docstring} agentsociety.executor.process.ProcessExecutor
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.executor.process.__all__>`
  - ```{autodoc2-docstring} agentsociety.executor.process.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.executor.process.__all__
:value: >
   ['ProcessExecutor']

```{autodoc2-docstring} agentsociety.executor.process.__all__
```

````

`````{py:class} ProcessExecutor(home_dir: str)
:canonical: agentsociety.executor.process.ProcessExecutor

```{autodoc2-docstring} agentsociety.executor.process.ProcessExecutor
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.executor.process.ProcessExecutor.__init__
```

````{py:method} _get_status_file(exp_id: str, tenant_id: str) -> pathlib.Path
:canonical: agentsociety.executor.process.ProcessExecutor._get_status_file

```{autodoc2-docstring} agentsociety.executor.process.ProcessExecutor._get_status_file
```

````

````{py:method} _get_log_file(exp_id: str, tenant_id: str) -> pathlib.Path
:canonical: agentsociety.executor.process.ProcessExecutor._get_log_file

```{autodoc2-docstring} agentsociety.executor.process.ProcessExecutor._get_log_file
```

````

````{py:method} _acquire_file_lock(file_path: pathlib.Path)
:canonical: agentsociety.executor.process.ProcessExecutor._acquire_file_lock

```{autodoc2-docstring} agentsociety.executor.process.ProcessExecutor._acquire_file_lock
```

````

````{py:method} _release_file_lock(lock_fd: int)
:canonical: agentsociety.executor.process.ProcessExecutor._release_file_lock

```{autodoc2-docstring} agentsociety.executor.process.ProcessExecutor._release_file_lock
```

````

````{py:method} create(config_base64: typing.Optional[str] = None, config_path: typing.Optional[str] = None, callback_url: str = '', callback_auth_token: str = '', tenant_id: str = '')
:canonical: agentsociety.executor.process.ProcessExecutor.create
:async:

```{autodoc2-docstring} agentsociety.executor.process.ProcessExecutor.create
```

````

````{py:method} delete(tenant_id: str, exp_id: str) -> None
:canonical: agentsociety.executor.process.ProcessExecutor.delete
:async:

```{autodoc2-docstring} agentsociety.executor.process.ProcessExecutor.delete
```

````

````{py:method} get_logs(tenant_id: str, exp_id: str, line_limit: int = 1000) -> str
:canonical: agentsociety.executor.process.ProcessExecutor.get_logs
:async:

```{autodoc2-docstring} agentsociety.executor.process.ProcessExecutor.get_logs
```

````

````{py:method} get_status(tenant_id: str, exp_id: str) -> str
:canonical: agentsociety.executor.process.ProcessExecutor.get_status
:async:

```{autodoc2-docstring} agentsociety.executor.process.ProcessExecutor.get_status
```

````

`````
