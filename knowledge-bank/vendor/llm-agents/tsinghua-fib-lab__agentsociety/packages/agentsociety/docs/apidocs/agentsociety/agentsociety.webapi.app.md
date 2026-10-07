# {py:mod}`agentsociety.webapi.app`

```{py:module} agentsociety.webapi.app
```

```{autodoc2-docstring} agentsociety.webapi.app
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`empty_get_tenant_id <agentsociety.webapi.app.empty_get_tenant_id>`
  - ```{autodoc2-docstring} agentsociety.webapi.app.empty_get_tenant_id
    :summary:
    ```
* - {py:obj}`_try_load_commercial_features <agentsociety.webapi.app._try_load_commercial_features>`
  - ```{autodoc2-docstring} agentsociety.webapi.app._try_load_commercial_features
    :summary:
    ```
* - {py:obj}`create_app <agentsociety.webapi.app.create_app>`
  - ```{autodoc2-docstring} agentsociety.webapi.app.create_app
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.webapi.app.__all__>`
  - ```{autodoc2-docstring} agentsociety.webapi.app.__all__
    :summary:
    ```
* - {py:obj}`_script_dir <agentsociety.webapi.app._script_dir>`
  - ```{autodoc2-docstring} agentsociety.webapi.app._script_dir
    :summary:
    ```
* - {py:obj}`_parent_dir <agentsociety.webapi.app._parent_dir>`
  - ```{autodoc2-docstring} agentsociety.webapi.app._parent_dir
    :summary:
    ```
* - {py:obj}`logger <agentsociety.webapi.app.logger>`
  - ```{autodoc2-docstring} agentsociety.webapi.app.logger
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.webapi.app.__all__
:value: >
   ['create_app', 'empty_get_tenant_id']

```{autodoc2-docstring} agentsociety.webapi.app.__all__
```

````

````{py:data} _script_dir
:canonical: agentsociety.webapi.app._script_dir
:value: >
   'dirname(...)'

```{autodoc2-docstring} agentsociety.webapi.app._script_dir
```

````

````{py:data} _parent_dir
:canonical: agentsociety.webapi.app._parent_dir
:value: >
   'dirname(...)'

```{autodoc2-docstring} agentsociety.webapi.app._parent_dir
```

````

````{py:data} logger
:canonical: agentsociety.webapi.app.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} agentsociety.webapi.app.logger
```

````

````{py:function} empty_get_tenant_id(_: fastapi.Request) -> str
:canonical: agentsociety.webapi.app.empty_get_tenant_id
:async:

```{autodoc2-docstring} agentsociety.webapi.app.empty_get_tenant_id
```
````

````{py:function} _try_load_commercial_features(app: fastapi.FastAPI, commercial: typing.Dict[str, typing.Any]) -> None
:canonical: agentsociety.webapi.app._try_load_commercial_features

```{autodoc2-docstring} agentsociety.webapi.app._try_load_commercial_features
```
````

````{py:function} create_app(db_dsn: str, read_only: bool, env: agentsociety.configs.EnvConfig, more_state: typing.Dict[str, typing.Any] = {}, commercial: typing.Dict[str, typing.Any] = {})
:canonical: agentsociety.webapi.app.create_app

```{autodoc2-docstring} agentsociety.webapi.app.create_app
```
````
