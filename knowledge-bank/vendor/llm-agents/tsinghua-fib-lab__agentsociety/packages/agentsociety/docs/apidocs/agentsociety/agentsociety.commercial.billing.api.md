# {py:mod}`agentsociety.commercial.billing.api`

```{py:module} agentsociety.commercial.billing.api
```

```{autodoc2-docstring} agentsociety.commercial.billing.api
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`get_account <agentsociety.commercial.billing.api.get_account>`
  - ```{autodoc2-docstring} agentsociety.commercial.billing.api.get_account
    :summary:
    ```
* - {py:obj}`list_bills <agentsociety.commercial.billing.api.list_bills>`
  - ```{autodoc2-docstring} agentsociety.commercial.billing.api.list_bills
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.commercial.billing.api.__all__>`
  - ```{autodoc2-docstring} agentsociety.commercial.billing.api.__all__
    :summary:
    ```
* - {py:obj}`router <agentsociety.commercial.billing.api.router>`
  - ```{autodoc2-docstring} agentsociety.commercial.billing.api.router
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.commercial.billing.api.__all__
:value: >
   ['router']

```{autodoc2-docstring} agentsociety.commercial.billing.api.__all__
```

````

````{py:data} router
:canonical: agentsociety.commercial.billing.api.router
:value: >
   'APIRouter(...)'

```{autodoc2-docstring} agentsociety.commercial.billing.api.router
```

````

````{py:function} get_account(request: fastapi.Request) -> agentsociety.webapi.models.ApiResponseWrapper[agentsociety.commercial.billing.models.ApiAccount]
:canonical: agentsociety.commercial.billing.api.get_account
:async:

```{autodoc2-docstring} agentsociety.commercial.billing.api.get_account
```
````

````{py:function} list_bills(request: fastapi.Request, item: typing.Optional[str] = None, skip: int = 0, limit: int = 100) -> agentsociety.webapi.models.ApiPaginatedResponseWrapper[agentsociety.commercial.billing.models.ApiBill]
:canonical: agentsociety.commercial.billing.api.list_bills
:async:

```{autodoc2-docstring} agentsociety.commercial.billing.api.list_bills
```
````
