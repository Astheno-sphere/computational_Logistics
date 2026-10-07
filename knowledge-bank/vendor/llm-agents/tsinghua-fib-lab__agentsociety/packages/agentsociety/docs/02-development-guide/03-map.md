# 自定义地图

地图生成依赖[MOSS: MObility Simulation System](https://python-moss.readthedocs.io/en/latest/)中的工具集`mosstool`。
`mosstool`将从[OpenStreetMap](https://www.openstreetmap.org/)中下载数据路网与AOI数据，进行预处理并重建车道级高精度地图文件，最终生成所需的Protobuf格式地图文件。

`mosstool`同样是Python软件包，可以通过`pip`快速安装：
```bash
pip install mosstool
```

安装完成后，采用以下代码即可生成一个指定经纬度范围内的地图文件：
```python
from mosstool.map.osm import RoadNet, Building
from mosstool.map.builder import Builder
from mosstool.util.format_converter import dict2pb
from mosstool.type import Map

min_latitude = 39.78
max_latitude = 39.92
min_longitude = 116.32
max_longitude = 116.40

projstr = f"+proj=tmerc +lat_0={(min_latitude + max_latitude) / 2} +lon_0={(min_longitude + max_longitude) / 2}"
rn = RoadNet(
    proj_str=projstr,
    max_latitude=max_latitude,
    min_latitude=min_latitude,
    max_longitude=max_longitude,
    min_longitude=min_longitude,
    proxies=None,
)
roadnet = rn.create_road_net()
building = Building(
    proj_str=projstr,
    max_latitude=max_latitude,
    min_latitude=min_latitude,
    max_longitude=max_longitude,
    min_longitude=min_longitude,
    proxies=None,
)
aois = building.create_building()
builder = Builder(
    net=roadnet,
    aois=aois,
    proj_str=projstr,
)
m = builder.build("map_name")
pb = dict2pb(m, Map())
with open("./map.pb", "wb") as f:
    f.write(pb.SerializeToString())
```

可以修改代码中的`min_latitude`、`max_latitude`、`min_longitude`、`max_longitude`来生成不同区域的地图。

```{admonition} 网络代理
:class: tip

如果需要使用代理下载数据，可以设置`proxies`参数，形如`proxies={"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}`。
```

```{admonition} 提示
:class: note

我们提供了部分大型城市的地图文件，可以登录[AgentSociety官网](https://agentsociety.fiblab.net/)内的[地图页面](https://agentsociety.fiblab.net/maps)下载。
```
