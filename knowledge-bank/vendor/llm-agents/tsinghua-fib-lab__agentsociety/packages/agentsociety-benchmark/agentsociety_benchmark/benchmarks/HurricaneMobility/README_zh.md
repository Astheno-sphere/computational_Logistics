# HurricaneMobility Benchmark

## 概述

HurricaneMobility benchmark 以Hurricane Dorian为背景，评估LLM智能体在面对极端天气时的移动行为生成能力。该benchmark专注于模拟用户在飓风期间、飓风前和飓风后的出行模式变化，测试智能体对极端事件响应的建模能力。

## 评测任务

### 极端天气移动行为生成
- **任务描述**: 基于Hurricane Dorian的真实数据，生成用户在飓风前、飓风期间和飓风后的移动行为模式
- **输入**: 飓风信息、用户特征、时间阶段（前/中/后）
- **输出**: 用户的移动行为数据，包括：
  - 总出行时间 (Total Travel Times)
  - 小时出行分布 (Hourly Travel Times)
  - 相对变化率 (Relative Changes)

## 构建您的智能体

### 智能体结构

您的智能体应该继承自 `HurricaneMobilityAgent` 并实现 `forward` 方法。您可以使用 `template_agent.py` 作为起点：

```python
from agentsociety_benchmark.benchmarks import HurricaneMobilityAgent

class YourHurricaneMobilityAgent(HurricaneMobilityAgent):
    """
    您的自定义智能体，用于飓风移动行为生成benchmark。
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def forward(self):
        # 您的实现代码
        pass
```

### HurricaneMobilityAgent 提供的核心API

`HurricaneMobilityAgent` 基类提供了用于飓风移动行为生成的核心API：

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

#### 2. 天气信息API: `get_current_weather()`
"""
从环境获取当前天气信息。 (Description)
- **描述**:
    - 获取实时天气数据，包括飓风条件、风速、降水量和其他气象信息。

- **参数**:
    - None: 无需参数。

- **返回值**:
    - weather_statement (str): 当前天气信息，包括飓风状态、条件和警告。
"""

### 环境信息访问

您的智能体可以通过以下API访问全面的城市环境和天气信息：

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

#### 天气信息

```python
# 获取当前天气信息
weather_info = self.get_current_weather()
# 返回天气信息
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

以下是一个展示如何实现飓风感知智能体的完整示例：

```python
from agentsociety_benchmark.benchmarks import HurricaneMobilityAgent
from pycityproto.city.person.v2.motion_pb2 import Status
import random

class MyHurricaneMobilityAgent(HurricaneMobilityAgent):
    """
    飓风移动行为生成benchmark的完整示例智能体。
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
        
        # 获取当前天气信息
        weather_info = self.get_current_weather()
        
        # 飓风感知决策逻辑
        if "飓风天":
            # 飓风逻辑
        else:
            # 正常天气条件 - 常规移动模式
            if 6 <= time // 3600 <= 8:  # 6:00-8:00 AM
                # 早晨：去工作
                if workplace_aoi_id:
                    await self.go_to_aoi(workplace_aoi_id)
            elif 12 <= time // 3600 <= 13:  # 12:00-1:00 PM
                # 午餐时间：外出就餐
                await self.go_to_aoi(random.choice(list(all_aois.keys())))
            elif 18 <= time // 3600 <= 20:  # 6:00-8:00 PM
                # 晚上：休闲或购物
                await self.go_to_aoi(random.choice(list(all_aois.keys())))
            elif 22 <= time // 3600 or time // 3600 <= 6:  # 10:00 PM - 6:00 AM
                # 夜间：回家睡觉
                if home_aoi_id:
                    await self.go_to_aoi(home_aoi_id)
            else:
                # 其他时间：随机活动
                await self.go_to_aoi(random.choice(list(all_aois.keys())))
```

### LLM集成

您的智能体可以使用集成的LLM进行复杂的飓风响应决策：

```python
# 使用LLM进行飓风感知决策的示例
messages = [
    {"role": "system", "content": "您是一个专门从事飓风响应的城市移动专家。根据当前天气条件、时间和位置决定下一个目的地。"},
    {"role": "user", "content": f"""
    当前时间: {time // 3600}:{(time % 3600) // 60:02d}
    当前位置: ({x}, {y})
    家AOI: {home_aoi_id}
    工作场所AOI: {workplace_aoi_id}
    
    天气信息: {weather_info}
    
    根据飓风条件决定下一个目的地AOI ID。
    返回格式: AOI_ID
    """}
]

response = await self.llm.atext_request(messages)
# 解析响应并执行移动
# 实现细节取决于您的解析策略
```

### 返回格式要求

您的智能体不需要返回任何特定的数据结构。benchmark会自动收集：
- 通过 `go_to_aoi` API调用收集移动轨迹
- 通过环境模拟收集位置数据
- 通过移动频率分析收集天气响应模式

benchmark将从收集的移动数据中计算所需的指标（总出行时间、小时出行时间、相对变化），这些数据跨越不同的飓风阶段。

## 评测流程

### 数据准备阶段
1. **真实数据加载**: 从数据集加载Hurricane Dorian期间的真实移动行为数据
2. **智能体初始化**: 配置智能体参数和飓风环境设置
3. **任务分发**: 为不同时间阶段生成相应的移动行为任务

### 行为生成阶段
1. **环境感知**: 智能体理解飓风影响和交通状况变化
2. **风险评估**: 分析不同时间阶段的出行风险
3. **行为生成**: 生成符合极端天气条件的移动模式
4. **数据输出**: 输出结构化的移动行为数据

### 评估阶段
1. **变化率对比**: 比较生成数据与真实数据的变化率
2. **分布相似性**: 评估小时出行分布的相似性
3. **加权评分**: 综合各项指标得出最终评分

## 评价指标

### 1. 变化率准确度 (Change Rate Score)

评估生成数据在飓风期间和飓风后相对于飓风前的变化率准确性。

**公式**:
```
MAPE = (|真实变化率 - 生成变化率| / |真实变化率|) × 100%
变化率分数 = max(0, 100 - 平均MAPE)
```

其中：
- **飓风期间变化率**: (飓风期间出行时间 - 飓风前出行时间) / 飓风前出行时间 × 100%
- **飓风后变化率**: (飓风后出行时间 - 飓风前出行时间) / 飓风前出行时间 × 100%
- **平均MAPE**: (飓风期间MAPE + 飓风后MAPE) / 2

### 2. 分布相似度 (Distribution Score)

评估生成的小时出行分布与真实分布的相似性。

**公式**:
```
余弦相似度 = (A · B) / (||A|| × ||B||)
分布分数 = max(0, 平均余弦相似度 × 100)
```

其中：
- A, B: 归一化后的小时出行分布向量
- 平均余弦相似度: (飓风前相似度 + 飓风期间相似度 + 飓风后相似度) / 3

### 3. 最终评分 (Final Score)

**公式**:
```
最终分数 = 变化率分数 × 0.6 + 分布分数 × 0.4
```

**权重说明**:
- 变化率分数权重60%：直接衡量飓风影响的准确性
- 分布分数权重40%：评估出行模式的时间分布相似性

## 数据集信息

- **数据集仓库**: https://huggingface.co/datasets/tsinghua-fib-lab/hurricane-mobility-generation-benchmark
- **分支**: main
- **支持模式**: inference (test模式暂不支持)
- **数据特征**: Hurricane Dorian期间的真实移动行为数据

## 依赖要求

```python
numpy >= 1.26.4
```

## 使用示例

```shell
asbench run --config <YOUR-CONFIG-FILE>.yml --agent <YOUR-AGENT-FILE>.py --mode inference HurricaneMobility
# inference模式执行后会在指定目录输出结果文件（如.pkl），该文件即为可提交/评分的最终结果
```

## 输出数据格式

```python
{
    "total_travel_times": [120, 85, 95],  # [飓风前, 飓风期间, 飓风后] 总出行时间(分钟)
    "hourly_travel_times": [
        [10, 15, 20, 25, 30, 35, 40, 35, 30, 25, 20, 15, 10, 5, 0, 0, 0, 0, 5, 10, 15, 20, 15, 10],  # 飓风前24小时分布
        [5, 8, 12, 15, 18, 20, 22, 20, 18, 15, 12, 8, 5, 2, 0, 0, 0, 0, 2, 5, 8, 12, 8, 5],  # 飓风期间24小时分布
        [8, 12, 16, 20, 24, 28, 32, 28, 24, 20, 16, 12, 8, 4, 0, 0, 0, 0, 4, 8, 12, 16, 12, 8]   # 飓风后24小时分布
    ]
}
```

## 详细评估指标

评估结果还包含以下详细指标：

```python
{
    "change_rate_score": 85.2,  # 变化率准确度分数
    "distribution_score": 78.9,  # 分布相似度分数
    "final_score": 82.7,  # 最终加权分数
    "detailed_metrics": {
        "real_change_rates": {
            "during_vs_before": -29.2,  # 真实飓风期间变化率(%)
            "after_vs_before": -20.8    # 真实飓风后变化率(%)
        },
        "generated_change_rates": {
            "during_vs_before": -31.5,  # 生成飓风期间变化率(%)
            "after_vs_before": -22.1    # 生成飓风后变化率(%)
        },
        "change_rate_error": {
            "during_vs_before": 2.3,    # 飓风期间变化率误差
            "after_vs_before": 1.3      # 飓风后变化率误差
        }
    }
}
```

## 版本信息

- **版本**: 1.0.0
- **作者**: AgentSociety Team
- **标签**: hurricane-mobility, extreme-weather 