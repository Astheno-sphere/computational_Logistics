# {py:mod}`agentsociety.environment.mapdata`

```{py:module} agentsociety.environment.mapdata
```

```{autodoc2-docstring} agentsociety.environment.mapdata
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`MapConfig <agentsociety.environment.mapdata.MapConfig>`
  - ```{autodoc2-docstring} agentsociety.environment.mapdata.MapConfig
    :summary:
    ```
* - {py:obj}`MapData <agentsociety.environment.mapdata.MapData>`
  - ```{autodoc2-docstring} agentsociety.environment.mapdata.MapData
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`__all__ <agentsociety.environment.mapdata.__all__>`
  - ```{autodoc2-docstring} agentsociety.environment.mapdata.__all__
    :summary:
    ```
````

### API

````{py:data} __all__
:canonical: agentsociety.environment.mapdata.__all__
:value: >
   ['MapData', 'MapConfig']

```{autodoc2-docstring} agentsociety.environment.mapdata.__all__
```

````

`````{py:class} MapConfig(/, **data: typing.Any)
:canonical: agentsociety.environment.mapdata.MapConfig

Bases: {py:obj}`pydantic.BaseModel`

```{autodoc2-docstring} agentsociety.environment.mapdata.MapConfig
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.environment.mapdata.MapConfig.__init__
```

````{py:attribute} file_path
:canonical: agentsociety.environment.mapdata.MapConfig.file_path
:type: str
:value: >
   'Field(...)'

```{autodoc2-docstring} agentsociety.environment.mapdata.MapConfig.file_path
```

````

`````

`````{py:class} MapData(config: agentsociety.environment.mapdata.MapConfig, s3config: agentsociety.s3.S3Config)
:canonical: agentsociety.environment.mapdata.MapData

```{autodoc2-docstring} agentsociety.environment.mapdata.MapData
```

```{rubric} Initialization
```

```{autodoc2-docstring} agentsociety.environment.mapdata.MapData.__init__
```

````{py:attribute} header
:canonical: agentsociety.environment.mapdata.MapData.header
:type: dict
:value: >
   None

```{autodoc2-docstring} agentsociety.environment.mapdata.MapData.header
```

````

````{py:attribute} aois
:canonical: agentsociety.environment.mapdata.MapData.aois
:type: typing.Dict[int, dict]
:value: >
   None

```{autodoc2-docstring} agentsociety.environment.mapdata.MapData.aois
```

````

````{py:attribute} pois
:canonical: agentsociety.environment.mapdata.MapData.pois
:type: typing.Dict[int, dict]
:value: >
   None

```{autodoc2-docstring} agentsociety.environment.mapdata.MapData.pois
```

````

````{py:method} get_all_aois()
:canonical: agentsociety.environment.mapdata.MapData.get_all_aois

```{autodoc2-docstring} agentsociety.environment.mapdata.MapData.get_all_aois
```

````

````{py:method} get_aoi(aoi_id: int)
:canonical: agentsociety.environment.mapdata.MapData.get_aoi

```{autodoc2-docstring} agentsociety.environment.mapdata.MapData.get_aoi
```

````

````{py:method} get_all_pois()
:canonical: agentsociety.environment.mapdata.MapData.get_all_pois

```{autodoc2-docstring} agentsociety.environment.mapdata.MapData.get_all_pois
```

````

````{py:method} get_poi(poi_id: int)
:canonical: agentsociety.environment.mapdata.MapData.get_poi

```{autodoc2-docstring} agentsociety.environment.mapdata.MapData.get_poi
```

````

````{py:method} _parse_map(m: typing.List[typing.Any]) -> typing.Dict[str, typing.Any]
:canonical: agentsociety.environment.mapdata.MapData._parse_map

```{autodoc2-docstring} agentsociety.environment.mapdata.MapData._parse_map
```

````

````{py:method} _build_geo_index()
:canonical: agentsociety.environment.mapdata.MapData._build_geo_index

```{autodoc2-docstring} agentsociety.environment.mapdata.MapData._build_geo_index
```

````

````{py:method} query_pois(center: typing.Union[typing.Tuple[float, float], shapely.geometry.Point], radius: typing.Optional[float] = None, category_prefix: typing.Optional[str] = None, limit: typing.Optional[int] = None, return_distance: bool = True) -> typing.Union[typing.List[typing.Tuple[typing.Any, float]], typing.List[typing.Any]]
:canonical: agentsociety.environment.mapdata.MapData.query_pois

```{autodoc2-docstring} agentsociety.environment.mapdata.MapData.query_pois
```

````

````{py:method} get_poi_cate()
:canonical: agentsociety.environment.mapdata.MapData.get_poi_cate

```{autodoc2-docstring} agentsociety.environment.mapdata.MapData.get_poi_cate
```

````

````{py:method} get_map_header()
:canonical: agentsociety.environment.mapdata.MapData.get_map_header

```{autodoc2-docstring} agentsociety.environment.mapdata.MapData.get_map_header
```

````

````{py:method} get_projector()
:canonical: agentsociety.environment.mapdata.MapData.get_projector

```{autodoc2-docstring} agentsociety.environment.mapdata.MapData.get_projector
```

````

````{py:method} query_aois(center: typing.Union[typing.Tuple[float, float], shapely.geometry.Point], radius: float, urban_land_uses: typing.Optional[typing.List[str]] = None, limit: typing.Optional[int] = None) -> typing.List[typing.Tuple[typing.Any, float]]
:canonical: agentsociety.environment.mapdata.MapData.query_aois

```{autodoc2-docstring} agentsociety.environment.mapdata.MapData.query_aois
```

````

`````
