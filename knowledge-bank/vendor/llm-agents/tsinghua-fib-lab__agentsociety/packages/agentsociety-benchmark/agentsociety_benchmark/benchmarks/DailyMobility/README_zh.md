# DailyMobility Benchmark

## 概述

DailyMobility benchmark 以北京市用户为基础，评估LLM智能体在日常移动行为生成方面的能力。该benchmark专注于模拟真实用户的日常出行模式，包括活动半径、每日访问地点数量、意图序列和意图比例等关键移动特征。

## 评测任务

### 日常移动行为生成
- **任务描述**: 基于用户特征和城市环境，生成符合真实用户行为的日常移动模式
- **输入**: 用户人口统计学特征、城市地理信息、时间约束
- **输出**: 用户的日常移动行为数据，包括：
  - 回转半径 (Gyration Radius)
  - 每日访问地点数量 (Daily Location Numbers)
  - 意图序列 (Intention Sequences)
  - 意图比例分布 (Intention Proportions)

## 构建您的智能体

### 智能体结构

您的智能体应该继承自 `DailyMobilityAgent` 并实现 `forward` 方法。您可以使用 `template_agent.py` 作为起点：

```python
from agentsociety_benchmark.benchmarks import DailyMobilityAgent

class YourDailyMobilityAgent(DailyMobilityAgent):
    """
    您的自定义智能体，用于日常移动行为生成benchmark。
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def forward(self):
        # 您的实现代码
        pass
```

### DailyMobilityAgent 提供的核心API

`DailyMobilityAgent` 基类提供了两个用于移动行为生成的核心API：

#### 1. 移动API: `go_to_aoi(aoi_id: int)`
"""
将智能体移动到特定的AOI（兴趣区域）。 (Description)
- **描述**:
    - 将智能体移动到城市环境中的特定AOI目的地。

- **参数**:
    - `aoi_id` (int): 目标AOI的ID。

- **返回值**:
    - None: 智能体将开始移动到指定目的地。
"""

#### 2. 意图记录API: `log_intention(intention: str)`
"""
记录智能体当前的移动行为意图。 (Description)
- **描述**:
    - 在内存中记录智能体的当前意图，用于跟踪移动模式。

- **参数**:
    - `intention` (str): 意图类型，必须是预定义的意图类型之一。

- **返回值**:
    - None: 意图存储在智能体的内存中。
"""

### 可用的意图类型

您的智能体必须从以下预定义列表中选择意图：
- `"sleep"`: 睡眠或休息活动
- `"home activity"`: 在家中进行的活动
- `"work"`: 工作相关活动
- `"shopping"`: 购物活动
- `"eating out"`: 外出就餐活动
- `"leisure and entertainment"`: 休闲娱乐活动
- `"other"`: 上述类别未涵盖的其他活动

**注意**: 任何不在此列表中的意图类型将自动归类为 `"other"`。

### 环境信息访问

您的智能体可以通过以下API访问全面的城市环境信息：

#### 智能体状态信息

```python
# 获取智能体的家和 workplace
home = await self.status.get("home")
home_aoi_id = home["aoi_position"]["aoi_id"]
workplace = await self.status.get("work")
work_aoi_id = workplace["aoi_position"]["aoi_id"]

# 获取当前智能体状态
citizen_status = await self.status.get("status")

# 获取智能体的当前位置
agent_position = await self.status.get("position")
x = agent_position["xy_position"]["x"]
y = agent_position["xy_position"]["y"]

# 获取当前时间
day, time = self.environment.get_datetime()
# time是自午夜以来的秒数（例如，10:00:00 = 36000）
# 替代方案：self.environment.get_datetime(format_time=True) 返回 "HH:MM:SS"
```

#### 地图和POI信息

```python
# 获取所有AOI（兴趣区域）
all_aois = self.environment.map.get_all_aois()
"""
AOI集合包含以下属性：
- id (int): AOI ID
- positions (list[XYPosition]): 多边形形状坐标
- area (float): 面积（平方米）
- driving_positions (list[LanePosition]): 与车道的连接点
- walking_positions (list[LanePosition]): 与人行道的连接点
- driving_gates (list[XYPosition]): 车道连接的AOI边界位置
- walking_gates (list[XYPosition]): 人行道连接的AOI边界位置
- urban_land_use (Optional[str]): 城市建设用地分类（GB 50137-2011）
- poi_ids (list[int]): 包含的POI ID列表
- shapely_xy (shapely.geometry.Polygon): xy坐标系中的AOI形状
- shapely_lnglat (shapely.geometry.Polygon): 经纬度坐标系中的AOI形状
"""

# 获取所有POI（兴趣点）
all_pois = self.environment.map.get_all_pois()
"""
POI集合包含以下属性：
- id (int): POI ID
- name (string): POI名称
- category (string): POI类别编码
- position (XYPosition): POI位置
- aoi_id (int): POI所属的AOI ID
"""

# 获取特定AOI信息
aoi_info = self.environment.map.get_aoi(aoi_id)

# 获取特定POI信息
poi_info = self.environment.map.get_poi(poi_id)

# 获取POI类别
poi_cates = self.environment.get_poi_cate()

# 获取智能体位置周围的POI
filtered_pois = self.environment.get_around_poi(
    center=(x, y),
    radius=1000,
    poi_type=["category_1", "category_2"],
)
```

### 移动状态处理

您的智能体应该在做出决策前检查当前的移动状态：

```python
# 检查智能体是否正在移动
if citizen_status in self.movement_status:
    # 智能体正在步行或驾驶，您可以通过设置新目的地来中断
    # 或者返回让当前移动继续
    return
```

### 完整智能体示例

以下是一个展示如何实现基本智能体的完整示例，包含正确的API使用：

```python
from agentsociety_benchmark.benchmarks import DailyMobilityAgent
from pycityproto.city.person.v2.motion_pb2 import Status
import random

class MyDailyMobilityAgent(DailyMobilityAgent):
    """
    日常移动行为生成benchmark的完整示例智能体。
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def forward(self):
        # 获取智能体的家和 workplace
        home = await self.status.get("home")
        home_aoi_id = home["aoi_position"]["aoi_id"]
        workplace = await self.status.get("work")
        work_aoi_id = workplace["aoi_position"]["aoi_id"]
        
        # 获取当前智能体状态
        citizen_status = await self.status.get("status")
        if citizen_status in self.movement_status:
            # 智能体正在移动，让它继续
            return
        
        # 获取当前位置和时间
        agent_position = await self.status.get("position")
        x = agent_position["xy_position"]["x"]
        y = agent_position["xy_position"]["y"]
        day, time = self.environment.get_datetime()
        
        # 获取环境信息
        all_aois = self.environment.map.get_all_aois()
        all_pois = self.environment.map.get_all_pois()
        
        # 基于时间的简单决策逻辑
        if 6 <= time // 3600 <= 8:  # 6:00-8:00 AM
            # 早晨：去工作
            if workplace_aoi_id:
                await self.go_to_aoi(workplace_aoi_id)
                await self.log_intention("work")
        elif 12 <= time // 3600 <= 13:  # 12:00-1:00 PM
            # 午餐时间：外出就餐
            await self.go_to_aoi(random.choice(list(all_aois.keys())))
            await self.log_intention("eating out")
        elif 18 <= time // 3600 <= 20:  # 6:00-8:00 PM
            # 晚上：休闲或购物
            await self.go_to_aoi(random.choice(list(all_aois.keys())))
            await self.log_intention(random.choice(["leisure and entertainment", "shopping"]))
        elif 22 <= time // 3600 or time // 3600 <= 6:  # 10:00 PM - 6:00 AM
            # 夜间：回家睡觉
            if home_aoi_id:
                await self.go_to_aoi(home_aoi_id)
                await self.log_intention("sleep")
        else:
            # 其他时间：随机活动
            await self.go_to_aoi(random.choice(list(all_aois.keys())))
            await self.log_intention(random.choice(self.intention_list))
```

### LLM集成

您的智能体可以使用集成的LLM进行更复杂的决策：

```python
# 使用LLM进行决策的示例
messages = [
    {"role": "system", "content": "您是一个城市移动专家。根据当前时间、位置和用户特征决定下一个目的地和意图。"},
    {"role": "user", "content": f"""
    当前时间: {time // 3600}:{(time % 3600) // 60:02d}
    当前位置: ({x}, {y})
    家AOI: {home_aoi_id}
    工作场所AOI: {workplace_aoi_id}
    
    可用意图: {self.intention_list}
    
    决定下一个目的地AOI ID和意图。
    返回格式: AOI_ID, intention
    """}
]

response = await self.llm.atext_request(messages)
# 解析响应并执行移动
# 实现细节取决于您的解析策略
```

### 返回格式要求

您的智能体不需要返回任何特定的数据结构。benchmark会自动收集：
- 通过 `go_to_aoi` API调用收集移动轨迹
- 通过 `log_intention` API调用收集意图序列
- 通过环境模拟收集位置数据

benchmark将从收集的移动和意图数据中计算所需的指标（回转半径、每日地点数量、意图序列、意图比例）。

## 评测流程

### 数据准备阶段
1. **真实数据加载**: 从数据集加载北京市用户的真实移动行为数据
2. **智能体初始化**: 配置智能体参数和环境设置
3. **任务分发**: 为每个用户生成相应的移动行为任务

### 行为生成阶段
1. **用户特征分析**: 智能体分析用户的人口统计学特征
2. **环境感知**: 理解城市地理布局和交通网络
3. **行为生成**: 生成符合用户特征的日常移动模式
4. **数据输出**: 输出结构化的移动行为数据

### 评估阶段
1. **分布对比**: 将生成数据与真实数据的分布进行对比
2. **JSD计算**: 计算Jensen-Shannon散度评估分布相似性
3. **分数计算**: 综合各项指标得出最终评分

## 评价指标

### Jensen-Shannon散度 (JSD)

Jensen-Shannon散度用于衡量生成数据分布与真实数据分布的相似性。JSD值越小，表示分布越相似。

**公式**:
```
JSD(P||Q) = 0.5 × KL(P||M) + 0.5 × KL(Q||M)
```

其中：
- P: 真实数据分布
- Q: 生成数据分布  
- M: (P + Q) / 2
- KL: Kullback-Leibler散度

### 具体评价指标

#### 1. 回转半径JSD (JSD Gyration Radius)
**描述**: 评估生成的回转半径分布与真实分布的相似性
**公式**: `JSD(真实回转半径分布 || 生成回转半径分布)`

#### 2. 每日地点数量JSD (JSD Daily Location Numbers)
**描述**: 评估生成的每日访问地点数量分布与真实分布的相似性
**公式**: `JSD(真实地点数量分布 || 生成地点数量分布)`

#### 3. 意图序列JSD (JSD Intention Sequences)
**描述**: 评估生成的意图序列分布与真实分布的相似性
**公式**: `JSD(真实意图序列分布 || 生成意图序列分布)`

#### 4. 意图比例JSD (JSD Intention Proportions)
**描述**: 评估生成的意图比例分布与真实分布的相似性
**公式**: `JSD(真实意图比例分布 || 生成意图比例分布)`

### 最终评分 (Final Score)

**公式**:
```
Final Score = ((1 - JSD_gyration + 1 - JSD_locations + 1 - JSD_sequences + 1 - JSD_proportions) / 4) × 100
```

**说明**:
- 每个JSD指标转换为相似性分数: `1 - JSD`
- 四个指标等权重平均
- 最终分数范围为0-100，分数越高表示生成质量越好

## 数据集信息

- **数据集仓库**: https://huggingface.co/datasets/tsinghua-fib-lab/daily-mobility-generation-benchmark
- **分支**: main
- **支持模式**: inference (test模式暂不支持)
- **数据特征**: 北京市用户日常移动行为数据

## 依赖要求

```python
numpy >= 1.26.4
scipy >= 1.13.0
```

## 使用示例

```shell
asbench run --config <YOUR-CONFIG-FILE>.yml --agent <YOUR-AGENT-FILE>.py --mode inference DailyMobility
# inference模式执行后会在指定目录输出结果文件（如.pkl），该文件即为可提交/评分的最终结果
```

## 输出数据格式

```python
{
    "gyration_radius": [2.5, 3.1, 1.8, ...],  # 用户回转半径列表
    "daily_location_numbers": [5, 7, 4, ...],  # 每日访问地点数量列表
    "intention_sequences": [[1,2,3,1], [2,1,4,2], ...],  # 意图序列列表
    "intention_proportions": [[0.3,0.2,0.5], [0.4,0.3,0.3], ...]  # 意图比例列表
}
```

## 版本信息

- **版本**: 1.0.0
- **作者**: AgentSociety Team
- **标签**: mobility-generation 