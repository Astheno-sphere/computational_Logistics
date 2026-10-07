# {py:mod}`agentsociety.webapi.api.experiment`

```{py:module} agentsociety.webapi.api.experiment
```

```{autodoc2-docstring} agentsociety.webapi.api.experiment
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_find_started_experiment_by_id <agentsociety.webapi.api.experiment._find_started_experiment_by_id>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment._find_started_experiment_by_id
    :summary:
    ```
* - {py:obj}`list_experiments <agentsociety.webapi.api.experiment.list_experiments>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment.list_experiments
    :summary:
    ```
* - {py:obj}`get_experiment_by_id <agentsociety.webapi.api.experiment.get_experiment_by_id>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment.get_experiment_by_id
    :summary:
    ```
* - {py:obj}`get_experiment_status_timeline_by_id <agentsociety.webapi.api.experiment.get_experiment_status_timeline_by_id>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment.get_experiment_status_timeline_by_id
    :summary:
    ```
* - {py:obj}`delete_experiment_by_id <agentsociety.webapi.api.experiment.delete_experiment_by_id>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment.delete_experiment_by_id
    :summary:
    ```
* - {py:obj}`get_experiment_metrics_by_id <agentsociety.webapi.api.experiment.get_experiment_metrics_by_id>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment.get_experiment_metrics_by_id
    :summary:
    ```
* - {py:obj}`serialize_metrics <agentsociety.webapi.api.experiment.serialize_metrics>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment.serialize_metrics
    :summary:
    ```
* - {py:obj}`get_experiment_metrics <agentsociety.webapi.api.experiment.get_experiment_metrics>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment.get_experiment_metrics
    :summary:
    ```
* - {py:obj}`export_experiment_data <agentsociety.webapi.api.experiment.export_experiment_data>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment.export_experiment_data
    :summary:
    ```
* - {py:obj}`export_experiment_artifacts <agentsociety.webapi.api.experiment.export_experiment_artifacts>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment.export_experiment_artifacts
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.webapi.api.experiment.__all__>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment.__all__
    :summary:
    ```
* - {py:obj}`router <agentsociety.webapi.api.experiment.router>`
  - ```{autodoc2-docstring} agentsociety.webapi.api.experiment.router
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.webapi.api.experiment.__all__
:value: >
   ['router']

```{autodoc2-docstring} agentsociety.webapi.api.experiment.__all__
```

````

````{py:data} router
:canonical: agentsociety.webapi.api.experiment.router
:value: >
   'APIRouter(...)'

```{autodoc2-docstring} agentsociety.webapi.api.experiment.router
```

````

````{py:function} _find_started_experiment_by_id(request: fastapi.Request, db: sqlalchemy.ext.asyncio.AsyncSession, exp_id: uuid.UUID) -> agentsociety.webapi.models.experiment.Experiment
:canonical: agentsociety.webapi.api.experiment._find_started_experiment_by_id
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment._find_started_experiment_by_id
```
````

````{py:function} list_experiments(request: fastapi.Request) -> agentsociety.webapi.models.ApiResponseWrapper[typing.List[agentsociety.webapi.models.experiment.ApiExperiment]]
:canonical: agentsociety.webapi.api.experiment.list_experiments
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment.list_experiments
```
````

````{py:function} get_experiment_by_id(request: fastapi.Request, exp_id: uuid.UUID) -> agentsociety.webapi.models.ApiResponseWrapper[agentsociety.webapi.models.experiment.ApiExperiment]
:canonical: agentsociety.webapi.api.experiment.get_experiment_by_id
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment.get_experiment_by_id
```
````

````{py:function} get_experiment_status_timeline_by_id(request: fastapi.Request, exp_id: uuid.UUID) -> agentsociety.webapi.models.ApiResponseWrapper[typing.List[agentsociety.webapi.models.experiment.ApiTime]]
:canonical: agentsociety.webapi.api.experiment.get_experiment_status_timeline_by_id
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment.get_experiment_status_timeline_by_id
```
````

````{py:function} delete_experiment_by_id(request: fastapi.Request, exp_id: uuid.UUID)
:canonical: agentsociety.webapi.api.experiment.delete_experiment_by_id
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment.delete_experiment_by_id
```
````

````{py:function} get_experiment_metrics_by_id(request: fastapi.Request, db: sqlalchemy.ext.asyncio.AsyncSession, exp_id: uuid.UUID) -> typing.Tuple[bool, typing.Dict[str, typing.List[agentsociety.webapi.models.metric.ApiMetric]]]
:canonical: agentsociety.webapi.api.experiment.get_experiment_metrics_by_id
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment.get_experiment_metrics_by_id
```
````

````{py:function} serialize_metrics(metrics_by_key: typing.Dict[str, typing.List[agentsociety.webapi.models.metric.ApiMetric]]) -> typing.Dict[str, typing.List[dict]]
:canonical: agentsociety.webapi.api.experiment.serialize_metrics

```{autodoc2-docstring} agentsociety.webapi.api.experiment.serialize_metrics
```
````

````{py:function} get_experiment_metrics(request: fastapi.Request, exp_id: uuid.UUID) -> agentsociety.webapi.models.ApiResponseWrapper[typing.Dict[str, typing.List[agentsociety.webapi.models.metric.ApiMetric]]]
:canonical: agentsociety.webapi.api.experiment.get_experiment_metrics
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment.get_experiment_metrics
```
````

````{py:function} export_experiment_data(request: fastapi.Request, exp_id: uuid.UUID) -> fastapi.responses.StreamingResponse
:canonical: agentsociety.webapi.api.experiment.export_experiment_data
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment.export_experiment_data
```
````

````{py:function} export_experiment_artifacts(request: fastapi.Request, exp_id: uuid.UUID) -> fastapi.responses.StreamingResponse
:canonical: agentsociety.webapi.api.experiment.export_experiment_artifacts
:async:

```{autodoc2-docstring} agentsociety.webapi.api.experiment.export_experiment_artifacts
```
````
