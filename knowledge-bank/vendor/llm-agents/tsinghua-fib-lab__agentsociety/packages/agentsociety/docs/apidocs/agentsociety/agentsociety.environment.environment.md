# {py:mod}`agentsociety.environment.environment`

```{py:module} agentsociety.environment.environment
```

```{autodoc2-docstring} agentsociety.environment.environment
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`EnvironmentConfig <agentsociety.environment.environment.EnvironmentConfig>`
  - ```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentConfig
    :summary:
    ```
* - {py:obj}`Environment <agentsociety.environment.environment.Environment>`
  - ```{autodoc2-docstring} agentsociety.environment.environment.Environment
    :summary:
    ```
* - {py:obj}`EnvironmentStarter <agentsociety.environment.environment.EnvironmentStarter>`
  - ```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentStarter
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_generate_yaml_config <agentsociety.environment.environment._generate_yaml_config>`
  - ```{autodoc2-docstring} agentsociety.environment.environment._generate_yaml_config
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.environment.environment.__all__>`
  - ```{autodoc2-docstring} agentsociety.environment.environment.__all__
    :summary:
    ```
* - {py:obj}`POI_START_ID <agentsociety.environment.environment.POI_START_ID>`
  - ```{autodoc2-docstring} agentsociety.environment.environment.POI_START_ID
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.environment.environment.__all__
:value: >
   ['Environment', 'EnvironmentStarter', 'EnvironmentConfig']

```{autodoc2-docstring} agentsociety.environment.environment.__all__
```

````

````{py:data} POI_START_ID
:canonical: agentsociety.environment.environment.POI_START_ID
:value: >
   700000000

```{autodoc2-docstring} agentsociety.environment.environment.POI_START_ID
```

````

`````{py:class} EnvironmentConfig(/, **data: typing.Any)
:canonical: agentsociety.environment.environment.EnvironmentConfig

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentConfig.__init__
```

````{py:attribute} model_config
:canonical: agentsociety.environment.environment.EnvironmentConfig.model_config
:value: >
   'ConfigDict(...)'

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentConfig.model_config
```

````

````{py:attribute} start_tick
:canonical: agentsociety.environment.environment.EnvironmentConfig.start_tick
:type: int
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentConfig.start_tick
```

````

````{py:attribute} metric_interval
:canonical: agentsociety.environment.environment.EnvironmentConfig.metric_interval
:type: int
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentConfig.metric_interval
```

````

````{py:attribute} weather
:canonical: agentsociety.environment.environment.EnvironmentConfig.weather
:type: str
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentConfig.weather
```

````

````{py:attribute} temperature
:canonical: agentsociety.environment.environment.EnvironmentConfig.temperature
:type: str
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentConfig.temperature
```

````

````{py:attribute} workday
:canonical: agentsociety.environment.environment.EnvironmentConfig.workday
:type: bool
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentConfig.workday
```

````

````{py:attribute} other_information
:canonical: agentsociety.environment.environment.EnvironmentConfig.other_information
:type: str
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentConfig.other_information
```

````

````{py:method} to_prompts() -> dict[str, typing.Any]
:canonical: agentsociety.environment.environment.EnvironmentConfig.to_prompts

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentConfig.to_prompts
```

````

`````

`````{py:class} Environment(map_data: agentsociety.environment.mapdata.MapData, server_addr: typing.Optional[str], environment_config: agentsociety.environment.environment.EnvironmentConfig, citizen_ids: set[int] = set(), firm_ids: set[int] = set(), bank_ids: set[int] = set(), nbs_ids: set[int] = set(), government_ids: set[int] = set())
:canonical: agentsociety.environment.environment.Environment

```{autodoc2-docstring} agentsociety.environment.environment.Environment
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.environment.environment.Environment.__init__
```

````{py:attribute} poi_cate
:canonical: agentsociety.environment.environment.Environment.poi_cate
:value: >
   None

```{autodoc2-docstring} agentsociety.environment.environment.Environment.poi_cate
```

````

````{py:attribute} _log_list
:canonical: agentsociety.environment.environment.Environment._log_list
:value: >
   []

```{autodoc2-docstring} agentsociety.environment.environment.Environment._log_list
```

````

````{py:attribute} _lock
:canonical: agentsociety.environment.environment.Environment._lock
:value: >
   'Lock(...)'

```{autodoc2-docstring} agentsociety.environment.environment.Environment._lock
```

````

````{py:attribute} _tick
:canonical: agentsociety.environment.environment.Environment._tick
:value: >
   0

```{autodoc2-docstring} agentsociety.environment.environment.Environment._tick
```

````

````{py:attribute} _aoi_message
:canonical: agentsociety.environment.environment.Environment._aoi_message
:type: dict[int, dict[int, list[str]]]
:value: >
   None

```{autodoc2-docstring} agentsociety.environment.environment.Environment._aoi_message
```

````

````{py:method} init() -> typing.Any
:canonical: agentsociety.environment.environment.Environment.init

```{autodoc2-docstring} agentsociety.environment.environment.Environment.init
```

````

````{py:method} close() -> typing.Any
:canonical: agentsociety.environment.environment.Environment.close

```{autodoc2-docstring} agentsociety.environment.environment.Environment.close
```

````

````{py:method} _create_poi_id_2_aoi_id()
:canonical: agentsociety.environment.environment.Environment._create_poi_id_2_aoi_id

```{autodoc2-docstring} agentsociety.environment.environment.Environment._create_poi_id_2_aoi_id
```

````

````{py:property} map
:canonical: agentsociety.environment.environment.Environment.map

```{autodoc2-docstring} agentsociety.environment.environment.Environment.map
```

````

````{py:property} city_client
:canonical: agentsociety.environment.environment.Environment.city_client

```{autodoc2-docstring} agentsociety.environment.environment.Environment.city_client
```

````

````{py:property} economy_client
:canonical: agentsociety.environment.environment.Environment.economy_client

```{autodoc2-docstring} agentsociety.environment.environment.Environment.economy_client
```

````

````{py:property} projector
:canonical: agentsociety.environment.environment.Environment.projector

```{autodoc2-docstring} agentsociety.environment.environment.Environment.projector
```

````

````{py:method} get_log_list()
:canonical: agentsociety.environment.environment.Environment.get_log_list

```{autodoc2-docstring} agentsociety.environment.environment.Environment.get_log_list
```

````

````{py:method} clear_log_list()
:canonical: agentsociety.environment.environment.Environment.clear_log_list

```{autodoc2-docstring} agentsociety.environment.environment.Environment.clear_log_list
```

````

````{py:method} get_poi_cate()
:canonical: agentsociety.environment.environment.Environment.get_poi_cate

```{autodoc2-docstring} agentsociety.environment.environment.Environment.get_poi_cate
```

````

````{py:method} get_aoi_ids()
:canonical: agentsociety.environment.environment.Environment.get_aoi_ids

```{autodoc2-docstring} agentsociety.environment.environment.Environment.get_aoi_ids
```

````

````{py:method} register_aoi_message(agent_id: int, target_aoi: typing.Union[int, list[int]], content: str)
:canonical: agentsociety.environment.environment.Environment.register_aoi_message

```{autodoc2-docstring} agentsociety.environment.environment.Environment.register_aoi_message
```

````

````{py:method} cancel_aoi_message(agent_id: int, target_aoi: typing.Union[int, list[int]])
:canonical: agentsociety.environment.environment.Environment.cancel_aoi_message

```{autodoc2-docstring} agentsociety.environment.environment.Environment.cancel_aoi_message
```

````

````{py:property} environment
:canonical: agentsociety.environment.environment.Environment.environment
:type: dict[str, str]

```{autodoc2-docstring} agentsociety.environment.environment.Environment.environment
```

````

````{py:method} set_environment(environment: dict[str, str])
:canonical: agentsociety.environment.environment.Environment.set_environment

```{autodoc2-docstring} agentsociety.environment.environment.Environment.set_environment
```

````

````{py:method} sense(key: str) -> typing.Any
:canonical: agentsociety.environment.environment.Environment.sense

```{autodoc2-docstring} agentsociety.environment.environment.Environment.sense
```

````

````{py:method} sense_aoi(aoi_id: int) -> str
:canonical: agentsociety.environment.environment.Environment.sense_aoi

```{autodoc2-docstring} agentsociety.environment.environment.Environment.sense_aoi
```

````

````{py:method} update_environment(key: str, value: typing.Any)
:canonical: agentsociety.environment.environment.Environment.update_environment

```{autodoc2-docstring} agentsociety.environment.environment.Environment.update_environment
```

````

````{py:method} get_environment() -> str
:canonical: agentsociety.environment.environment.Environment.get_environment

```{autodoc2-docstring} agentsociety.environment.environment.Environment.get_environment
```

````

````{py:method} get_poi_categories(center: typing.Optional[typing.Union[tuple[float, float], shapely.geometry.Point]] = None, radius: typing.Optional[float] = None) -> list[str]
:canonical: agentsociety.environment.environment.Environment.get_poi_categories

```{autodoc2-docstring} agentsociety.environment.environment.Environment.get_poi_categories
```

````

````{py:method} set_tick(tick: int)
:canonical: agentsociety.environment.environment.Environment.set_tick

```{autodoc2-docstring} agentsociety.environment.environment.Environment.set_tick
```

````

````{py:method} get_tick() -> int
:canonical: agentsociety.environment.environment.Environment.get_tick

```{autodoc2-docstring} agentsociety.environment.environment.Environment.get_tick
```

````

````{py:method} get_datetime(format_time: bool = False, format: str = '%H:%M:%S') -> typing.Union[tuple[int, int], tuple[int, str]]
:canonical: agentsociety.environment.environment.Environment.get_datetime

```{autodoc2-docstring} agentsociety.environment.environment.Environment.get_datetime
```

````

````{py:method} get_person(person_id: int) -> dict
:canonical: agentsociety.environment.environment.Environment.get_person
:async:

```{autodoc2-docstring} agentsociety.environment.environment.Environment.get_person
```

````

````{py:method} add_person(dict_person: dict) -> dict
:canonical: agentsociety.environment.environment.Environment.add_person
:async:

```{autodoc2-docstring} agentsociety.environment.environment.Environment.add_person
```

````

````{py:method} set_aoi_schedules(person_id: int, target_positions: typing.Union[list[typing.Union[int, tuple[int, int]]], typing.Union[int, tuple[int, int]]], departure_times: typing.Optional[list[float]] = None, modes: typing.Optional[list[pycityproto.city.trip.v2.trip_pb2.TripMode]] = None)
:canonical: agentsociety.environment.environment.Environment.set_aoi_schedules
:async:

```{autodoc2-docstring} agentsociety.environment.environment.Environment.set_aoi_schedules
```

````

````{py:method} reset_person_position(person_id: int, aoi_id: typing.Optional[int] = None, poi_id: typing.Optional[int] = None, lane_id: typing.Optional[int] = None, s: typing.Optional[float] = None)
:canonical: agentsociety.environment.environment.Environment.reset_person_position
:async:

```{autodoc2-docstring} agentsociety.environment.environment.Environment.reset_person_position
```

````

````{py:method} get_around_poi(center: typing.Union[tuple[float, float], shapely.geometry.Point], radius: float, poi_type: typing.Union[str, list[str]]) -> list[dict]
:canonical: agentsociety.environment.environment.Environment.get_around_poi

```{autodoc2-docstring} agentsociety.environment.environment.Environment.get_around_poi
```

````

`````

`````{py:class} EnvironmentStarter(map_config: agentsociety.environment.mapdata.MapConfig, environment_config: agentsociety.environment.environment.EnvironmentConfig, s3config: agentsociety.s3.S3Config, log_dir: str, home_dir: str)
:canonical: agentsociety.environment.environment.EnvironmentStarter

Bases: {py:obj}`agentsociety.environment.environment.Environment`

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentStarter
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentStarter.__init__
```

````{py:method} to_init_args()
:canonical: agentsociety.environment.environment.EnvironmentStarter.to_init_args

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentStarter.to_init_args
```

````

````{py:property} syncer
:canonical: agentsociety.environment.environment.EnvironmentStarter.syncer

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentStarter.syncer
```

````

````{py:method} init()
:canonical: agentsociety.environment.environment.EnvironmentStarter.init
:async:

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentStarter.init
```

````

````{py:method} close()
:canonical: agentsociety.environment.environment.EnvironmentStarter.close
:async:

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentStarter.close
```

````

````{py:method} step(n: int)
:canonical: agentsociety.environment.environment.EnvironmentStarter.step
:async:

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentStarter.step
```

````

````{py:method} get_metrics() -> list[typing.Tuple[str, float, int]]
:canonical: agentsociety.environment.environment.EnvironmentStarter.get_metrics
:async:

```{autodoc2-docstring} agentsociety.environment.environment.EnvironmentStarter.get_metrics
```

````

`````

````{py:function} _generate_yaml_config(map_file) -> str
:canonical: agentsociety.environment.environment._generate_yaml_config

```{autodoc2-docstring} agentsociety.environment.environment._generate_yaml_config
```
````
