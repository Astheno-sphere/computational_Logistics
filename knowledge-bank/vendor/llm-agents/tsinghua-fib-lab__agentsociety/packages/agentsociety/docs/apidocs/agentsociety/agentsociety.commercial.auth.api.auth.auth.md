# {py:mod}`agentsociety.commercial.auth.api.auth.auth`

```{py:module} agentsociety.commercial.auth.api.auth.auth
```

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`CasdoorConfig <agentsociety.commercial.auth.api.auth.auth.CasdoorConfig>`
  -
* - {py:obj}`Casdoor <agentsociety.commercial.auth.api.auth.auth.Casdoor>`
  - ```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.Casdoor
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`auth_bearer_token <agentsociety.commercial.auth.api.auth.auth.auth_bearer_token>`
  - ```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.auth_bearer_token
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.commercial.auth.api.auth.auth.__all__>`
  - ```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.__all__
    :summary:
    ```
* - {py:obj}`ROLE <agentsociety.commercial.auth.api.auth.auth.ROLE>`
  - ```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.ROLE
    :summary:
    ```
* - {py:obj}`DEMO_USER_TOKEN <agentsociety.commercial.auth.api.auth.auth.DEMO_USER_TOKEN>`
  - ```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.DEMO_USER_TOKEN
    :summary:
    ```
* - {py:obj}`DEMO_USER_ID <agentsociety.commercial.auth.api.auth.auth.DEMO_USER_ID>`
  - ```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.DEMO_USER_ID
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.commercial.auth.api.auth.auth.__all__
:value: >
   ['auth_bearer_token', 'CasdoorConfig']

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.__all__
```

````

````{py:data} ROLE
:canonical: agentsociety.commercial.auth.api.auth.auth.ROLE
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.ROLE
```

````

````{py:data} DEMO_USER_TOKEN
:canonical: agentsociety.commercial.auth.api.auth.auth.DEMO_USER_TOKEN
:value: >
   'DEMO_USER_TOKEN'

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.DEMO_USER_TOKEN
```

````

````{py:data} DEMO_USER_ID
:canonical: agentsociety.commercial.auth.api.auth.auth.DEMO_USER_ID
:value: >
   'DEMO'

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.DEMO_USER_ID
```

````

`````{py:class} CasdoorConfig(/, **data: typing.Any)
:canonical: agentsociety.commercial.auth.api.auth.auth.CasdoorConfig

Bases: {py:obj}`pydantic.BaseModel`

````{py:attribute} enabled
:canonical: agentsociety.commercial.auth.api.auth.auth.CasdoorConfig.enabled
:type: bool
:value: >
   False

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.CasdoorConfig.enabled
```

````

````{py:attribute} client_id
:canonical: agentsociety.commercial.auth.api.auth.auth.CasdoorConfig.client_id
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.CasdoorConfig.client_id
```

````

````{py:attribute} client_secret
:canonical: agentsociety.commercial.auth.api.auth.auth.CasdoorConfig.client_secret
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.CasdoorConfig.client_secret
```

````

````{py:attribute} application_name
:canonical: agentsociety.commercial.auth.api.auth.auth.CasdoorConfig.application_name
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.CasdoorConfig.application_name
```

````

````{py:attribute} endpoint
:canonical: agentsociety.commercial.auth.api.auth.auth.CasdoorConfig.endpoint
:type: str
:value: >
   'https://login.fiblab.net'

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.CasdoorConfig.endpoint
```

````

````{py:attribute} org_name
:canonical: agentsociety.commercial.auth.api.auth.auth.CasdoorConfig.org_name
:type: str
:value: >
   'fiblab'

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.CasdoorConfig.org_name
```

````

````{py:attribute} certificate
:canonical: agentsociety.commercial.auth.api.auth.auth.CasdoorConfig.certificate
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.CasdoorConfig.certificate
```

````

`````

`````{py:class} Casdoor(config: agentsociety.commercial.auth.api.auth.auth.CasdoorConfig)
:canonical: agentsociety.commercial.auth.api.auth.auth.Casdoor

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.Casdoor
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.Casdoor.__init__
```

````{py:property} sdk
:canonical: agentsociety.commercial.auth.api.auth.auth.Casdoor.sdk
:type: casdoor.CasdoorSDK

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.Casdoor.sdk
```

````

````{py:method} get_user_by_id(user_id: str)
:canonical: agentsociety.commercial.auth.api.auth.auth.Casdoor.get_user_by_id
:async:

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.Casdoor.get_user_by_id
```

````

`````

````{py:function} auth_bearer_token(request: starlette.requests.Request)
:canonical: agentsociety.commercial.auth.api.auth.auth.auth_bearer_token
:async:

```{autodoc2-docstring} agentsociety.commercial.auth.api.auth.auth.auth_bearer_token
```
````
