# {py:mod}`agentsociety.commercial.auth.api.login`

```{py:module} agentsociety.commercial.auth.api.login
```

```{autodoc2-docstring} agentsociety.commercial.auth.api.login
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`post_signin <agentsociety.commercial.auth.api.login.post_signin>`
  - ```{autodoc2-docstring} agentsociety.commercial.auth.api.login.post_signin
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.commercial.auth.api.login.__all__>`
  - ```{autodoc2-docstring} agentsociety.commercial.auth.api.login.__all__
    :summary:
    ```
* - {py:obj}`router <agentsociety.commercial.auth.api.login.router>`
  - ```{autodoc2-docstring} agentsociety.commercial.auth.api.login.router
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.commercial.auth.api.login.__all__
:value: >
   ['router']

```{autodoc2-docstring} agentsociety.commercial.auth.api.login.__all__
```

````

````{py:data} router
:canonical: agentsociety.commercial.auth.api.login.router
:value: >
   'APIRouter(...)'

```{autodoc2-docstring} agentsociety.commercial.auth.api.login.router
```

````

````{py:function} post_signin(request: starlette.requests.Request, code: str = Query(...), state: typing.Optional[str] = Query(None))
:canonical: agentsociety.commercial.auth.api.login.post_signin
:async:

```{autodoc2-docstring} agentsociety.commercial.auth.api.login.post_signin
```
````
