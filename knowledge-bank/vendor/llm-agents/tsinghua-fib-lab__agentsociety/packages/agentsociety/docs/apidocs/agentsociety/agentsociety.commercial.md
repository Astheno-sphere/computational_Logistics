# {py:mod}`agentsociety.commercial`

```{py:module} agentsociety.commercial
```

```{autodoc2-docstring} agentsociety.commercial
:allowtitles:
```

## Subpackages

```{toctree}
:titlesonly:
:maxdepth: 3

agentsociety.commercial.executor
agentsociety.commercial.auth
agentsociety.commercial.billing
```

## Package Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`is_available <agentsociety.commercial.is_available>`
  - ```{autodoc2-docstring} agentsociety.commercial.is_available
    :summary:
    ```
* - {py:obj}`get_auth_provider <agentsociety.commercial.get_auth_provider>`
  - ```{autodoc2-docstring} agentsociety.commercial.get_auth_provider
    :summary:
    ```
* - {py:obj}`get_kubernetes_executor <agentsociety.commercial.get_kubernetes_executor>`
  - ```{autodoc2-docstring} agentsociety.commercial.get_kubernetes_executor
    :summary:
    ```
* - {py:obj}`get_billing_system <agentsociety.commercial.get_billing_system>`
  - ```{autodoc2-docstring} agentsociety.commercial.get_billing_system
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <agentsociety.commercial.logger>`
  - ```{autodoc2-docstring} agentsociety.commercial.logger
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: agentsociety.commercial.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} agentsociety.commercial.logger
```

````

````{py:function} is_available() -> bool
:canonical: agentsociety.commercial.is_available

```{autodoc2-docstring} agentsociety.commercial.is_available
```
````

````{py:function} get_auth_provider(config: typing.Dict[str, typing.Any])
:canonical: agentsociety.commercial.get_auth_provider

```{autodoc2-docstring} agentsociety.commercial.get_auth_provider
```
````

````{py:function} get_kubernetes_executor(config: typing.Dict[str, typing.Any])
:canonical: agentsociety.commercial.get_kubernetes_executor

```{autodoc2-docstring} agentsociety.commercial.get_kubernetes_executor
```
````

````{py:function} get_billing_system(config: typing.Dict[str, typing.Any])
:canonical: agentsociety.commercial.get_billing_system

```{autodoc2-docstring} agentsociety.commercial.get_billing_system
```
````
