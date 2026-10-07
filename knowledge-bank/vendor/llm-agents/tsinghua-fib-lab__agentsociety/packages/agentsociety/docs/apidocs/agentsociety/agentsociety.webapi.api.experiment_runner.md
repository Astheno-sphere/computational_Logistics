# {py:mod}`agentsociety.webapi.api.experiment_runner`

```{py:module} agentsociety.webapi.api.experiment_runner
```

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`ConfigPrimaryKey <agentsociety.webapi.api.experiment_runner.ConfigPrimaryKey>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ConfigPrimaryKey
    :summary:
    ```
* - {py:obj}`ExperimentRequest <agentsociety.webapi.api.experiment_runner.ExperimentRequest>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ExperimentRequest
    :summary:
    ```
* - {py:obj}`ExperimentResponse <agentsociety.webapi.api.experiment_runner.ExperimentResponse>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ExperimentResponse
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`run_experiment <agentsociety.webapi.api.experiment_runner.run_experiment>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.run_experiment
    :summary:
    ```
* - {py:obj}`delete_experiment <agentsociety.webapi.api.experiment_runner.delete_experiment>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.delete_experiment
    :summary:
    ```
* - {py:obj}`get_experiment_logs <agentsociety.webapi.api.experiment_runner.get_experiment_logs>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.get_experiment_logs
    :summary:
    ```
* - {py:obj}`get_experiment_status <agentsociety.webapi.api.experiment_runner.get_experiment_status>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.get_experiment_status
    :summary:
    ```
* - {py:obj}`finish_experiment <agentsociety.webapi.api.experiment_runner.finish_experiment>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.finish_experiment
    :summary:
    ```
* - {py:obj}`_compute_commercial_bill <agentsociety.webapi.api.experiment_runner._compute_commercial_bill>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner._compute_commercial_bill
    :summary:
    ```
* - {py:obj}`_check_commercial_balance <agentsociety.webapi.api.experiment_runner._check_commercial_balance>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner._check_commercial_balance
    :summary:
    ```
* - {py:obj}`_record_experiment_bill <agentsociety.webapi.api.experiment_runner._record_experiment_bill>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner._record_experiment_bill
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.webapi.api.experiment_runner.__all__>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.__all__
    :summary:
    ```
* - {py:obj}`router <agentsociety.webapi.api.experiment_runner.router>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.router
    :summary:
    ```
* - {py:obj}`logger <agentsociety.webapi.api.experiment_runner.logger>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.logger
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.webapi.api.experiment_runner.__all__
:value: >
   ['router']

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.__all__
```

````

````{py:data} router
:canonical: agentsociety.webapi.api.experiment_runner.router
:value: >
   'APIRouter(...)'

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.router
```

````

````{py:data} logger
:canonical: agentsociety.webapi.api.experiment_runner.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.logger
```

````

`````{py:class} ConfigPrimaryKey(/, **data: typing.Any)
:canonical: agentsociety.webapi.api.experiment_runner.ConfigPrimaryKey

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ConfigPrimaryKey
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ConfigPrimaryKey.__init__
```

````{py:attribute} tenant_id
:canonical: agentsociety.webapi.api.experiment_runner.ConfigPrimaryKey.tenant_id
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ConfigPrimaryKey.tenant_id
```

````

````{py:attribute} id
:canonical: agentsociety.webapi.api.experiment_runner.ConfigPrimaryKey.id
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ConfigPrimaryKey.id
```

````

`````

`````{py:class} ExperimentRequest(/, **data: typing.Any)
:canonical: agentsociety.webapi.api.experiment_runner.ExperimentRequest

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ExperimentRequest
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ExperimentRequest.__init__
```

````{py:attribute} llm
:canonical: agentsociety.webapi.api.experiment_runner.ExperimentRequest.llm
:type: agentsociety.webapi.api.experiment_runner.ConfigPrimaryKey
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ExperimentRequest.llm
```

````

````{py:attribute} agents
:canonical: agentsociety.webapi.api.experiment_runner.ExperimentRequest.agents
:type: agentsociety.webapi.api.experiment_runner.ConfigPrimaryKey
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ExperimentRequest.agents
```

````

````{py:attribute} map
:canonical: agentsociety.webapi.api.experiment_runner.ExperimentRequest.map
:type: agentsociety.webapi.api.experiment_runner.ConfigPrimaryKey
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ExperimentRequest.map
```

````

````{py:attribute} workflow
:canonical: agentsociety.webapi.api.experiment_runner.ExperimentRequest.workflow
:type: agentsociety.webapi.api.experiment_runner.ConfigPrimaryKey
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ExperimentRequest.workflow
```

````

````{py:attribute} exp_name
:canonical: agentsociety.webapi.api.experiment_runner.ExperimentRequest.exp_name
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ExperimentRequest.exp_name
```

````

`````

`````{py:class} ExperimentResponse(/, **data: typing.Any)
:canonical: agentsociety.webapi.api.experiment_runner.ExperimentResponse

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ExperimentResponse
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ExperimentResponse.__init__
```

````{py:attribute} id
:canonical: agentsociety.webapi.api.experiment_runner.ExperimentResponse.id
:type: str
:value: >
   None

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.ExperimentResponse.id
```

````

`````

````{py:function} run_experiment(request: fastapi.Request, config: agentsociety.webapi.api.experiment_runner.ExperimentRequest = Body(...)) -> agentsociety.webapi.models.ApiResponseWrapper[agentsociety.webapi.api.experiment_runner.ExperimentResponse]
:canonical: agentsociety.webapi.api.experiment_runner.run_experiment
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.run_experiment
```
````

````{py:function} delete_experiment(request: fastapi.Request, exp_id: str)
:canonical: agentsociety.webapi.api.experiment_runner.delete_experiment
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.delete_experiment
```
````

````{py:function} get_experiment_logs(request: fastapi.Request, exp_id: str) -> str
:canonical: agentsociety.webapi.api.experiment_runner.get_experiment_logs
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.get_experiment_logs
```
````

````{py:function} get_experiment_status(request: fastapi.Request, exp_id: str) -> agentsociety.webapi.models.ApiResponseWrapper[str]
:canonical: agentsociety.webapi.api.experiment_runner.get_experiment_status
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.get_experiment_status
```
````

````{py:function} finish_experiment(request: fastapi.Request, exp_id: str, callback_auth_token: str = Query(...))
:canonical: agentsociety.webapi.api.experiment_runner.finish_experiment
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner.finish_experiment
```
````

````{py:function} _compute_commercial_bill(app_state, db: sqlalchemy.ext.asyncio.AsyncSession, experiment: agentsociety.webapi.models.experiment.Experiment)
:canonical: agentsociety.webapi.api.experiment_runner._compute_commercial_bill
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner._compute_commercial_bill
```
````

````{py:function} _check_commercial_balance(app_state, tenant_id: str, db: sqlalchemy.ext.asyncio.AsyncSession)
:canonical: agentsociety.webapi.api.experiment_runner._check_commercial_balance
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner._check_commercial_balance
```
````

````{py:function} _record_experiment_bill(app_state, db: sqlalchemy.ext.asyncio.AsyncSession, tenant_id: str, exp_id: uuid.UUID, llm_config_id: typing.Optional[uuid.UUID] = None)
:canonical: agentsociety.webapi.api.experiment_runner._record_experiment_bill
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment_runner._record_experiment_bill
```
````
