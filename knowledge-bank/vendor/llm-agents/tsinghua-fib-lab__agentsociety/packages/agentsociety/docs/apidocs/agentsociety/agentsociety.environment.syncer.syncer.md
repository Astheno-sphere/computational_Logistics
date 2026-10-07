# {py:mod}`agentsociety.environment.syncer.syncer`

```{py:module} agentsociety.environment.syncer.syncer
```

```{autodoc2-docstring} agentsociety.environment.syncer.syncer
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`Syncer <agentsociety.environment.syncer.syncer.Syncer>`
  -
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.environment.syncer.syncer.__all__>`
  - ```{autodoc2-docstring} agentsociety.environment.syncer.syncer.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.environment.syncer.syncer.__all__
:value: >
   ['Syncer']

```{autodoc2-docstring} agentsociety.environment.syncer.syncer.__all__
```

````

`````{py:class} Syncer(addr: str)
:canonical: agentsociety.environment.syncer.syncer.Syncer

Bases: {py:obj}`pycityproto.city.sync.v2.sync_service_pb2_grpc.SyncServiceServicer`

````{py:method} init() -> None
:canonical: agentsociety.environment.syncer.syncer.Syncer.init
:async:

```{autodoc2-docstring} agentsociety.environment.syncer.syncer.Syncer.init
```

````

````{py:method} close() -> None
:canonical: agentsociety.environment.syncer.syncer.Syncer.close
:async:

```{autodoc2-docstring} agentsociety.environment.syncer.syncer.Syncer.close
```

````

````{py:method} __del__()
:canonical: agentsociety.environment.syncer.syncer.Syncer.__del__

```{autodoc2-docstring} agentsociety.environment.syncer.syncer.Syncer.__del__
```

````

````{py:method} SetURL(request: pycityproto.city.sync.v2.sync_service_pb2.SetURLRequest, context: grpc.aio.ServicerContext) -> pycityproto.city.sync.v2.sync_service_pb2.SetURLResponse
:canonical: agentsociety.environment.syncer.syncer.Syncer.SetURL
:async:

```{autodoc2-docstring} agentsociety.environment.syncer.syncer.Syncer.SetURL
```

````

````{py:method} GetURL(request: pycityproto.city.sync.v2.sync_service_pb2.GetURLRequest, context: grpc.aio.ServicerContext) -> pycityproto.city.sync.v2.sync_service_pb2.GetURLResponse
:canonical: agentsociety.environment.syncer.syncer.Syncer.GetURL
:async:

```{autodoc2-docstring} agentsociety.environment.syncer.syncer.Syncer.GetURL
```

````

````{py:method} EnterStepSync(request: pycityproto.city.sync.v2.sync_service_pb2.EnterStepSyncRequest, context: grpc.aio.ServicerContext) -> pycityproto.city.sync.v2.sync_service_pb2.EnterStepSyncResponse
:canonical: agentsociety.environment.syncer.syncer.Syncer.EnterStepSync
:async:

```{autodoc2-docstring} agentsociety.environment.syncer.syncer.Syncer.EnterStepSync
```

````

````{py:method} ExitStepSync(request: pycityproto.city.sync.v2.sync_service_pb2.ExitStepSyncRequest, context: grpc.aio.ServicerContext) -> pycityproto.city.sync.v2.sync_service_pb2.ExitStepSyncResponse
:canonical: agentsociety.environment.syncer.syncer.Syncer.ExitStepSync
:async:

```{autodoc2-docstring} agentsociety.environment.syncer.syncer.Syncer.ExitStepSync
```

````

````{py:method} step(close: bool = False) -> bool
:canonical: agentsociety.environment.syncer.syncer.Syncer.step
:async:

```{autodoc2-docstring} agentsociety.environment.syncer.syncer.Syncer.step
```

````

`````
