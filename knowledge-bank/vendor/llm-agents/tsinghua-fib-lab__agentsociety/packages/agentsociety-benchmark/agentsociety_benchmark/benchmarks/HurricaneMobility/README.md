# HurricaneMobility Benchmark

## Overview

The HurricaneMobility benchmark evaluates LLM agents' capabilities in generating mobility behavior during extreme weather events, using Hurricane Dorian as the context. This benchmark focuses on simulating user travel pattern changes before, during, and after hurricanes, testing agents' modeling capabilities for extreme event responses.

## Evaluation Task

### Extreme Weather Mobility Behavior Generation
- **Task Description**: Generate user mobility behavior patterns before, during, and after Hurricane Dorian based on real data
- **Input**: Hurricane information, user features, time phases (before/during/after)
- **Output**: User mobility behavior data, including:
  - Total Travel Times
  - Hourly Travel Times
  - Relative Changes

## Building Your Agent

### Agent Structure

Your agent should inherit from `HurricaneMobilityAgent` and implement the `forward` method. You can use `template_agent.py` as a starting point:

```python
from agentsociety_benchmark.benchmarks import HurricaneMobilityAgent

class YourHurricaneMobilityAgent(HurricaneMobilityAgent):
    """
    Your custom agent for the Hurricane Mobility Generation benchmark.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def forward(self):
        # Your implementation here
        pass
```

### Core APIs Provided by HurricaneMobilityAgent

The `HurricaneMobilityAgent` base class provides essential APIs for hurricane mobility behavior generation:

#### 1. Movement API: `go_to_aoi(aoi_id: int)`
"""
Moves the agent to a specific AOI (Area of Interest). (Description)
- **Description**:
    - Moves the agent to a specific AOI destination in the urban environment.

- **Args**:
    - `aoi_id` (int): The ID of the target AOI to move to.

- **Returns**:
    - None: The agent will start moving to the specified destination.
"""

#### 2. Weather Information API: `get_current_weather()`
"""
Retrieves current weather information from the environment. (Description)
- **Description**:
    - Gets real-time weather data including hurricane conditions, wind speed, precipitation, and other meteorological information.

- **Args**:
    - None: No parameters required.

- **Returns**:
    - weather_statement (dict): Current weather information including hurricane status, conditions, and warnings.
"""

### Environment Information Access

Your agent can access comprehensive urban environment and weather information through the following APIs:

#### Agent Status Information

```python
# Get agent's home and workplace
home = await self.status.get("home")
home_aoi_id = home["aoi_position"]["aoi_id"]
workplace = await self.status.get("work")
work_aoi_id = workplace["aoi_position"]["aoi_id"]

# Get current agent status
citizen_status = await self.status.get("status")

# Get agent's current position
agent_position = await self.status.get("position")
x = agent_position["xy_position"]["x"]
y = agent_position["xy_position"]["y"]

# Get current time
day, time = self.environment.get_datetime()
# time is seconds since midnight (e.g., 10:00:00 = 36000)
# Alternative: self.environment.get_datetime(format_time=True) returns "HH:MM:SS"
```

#### Weather Information

```python
# Get current weather information
weather_info = self.get_current_weather()
# Returns weather data including hurricane conditions, wind speed, precipitation, etc.
```

#### Map and POI Information

```python
# Get all AOIs (Areas of Interest)
all_aois = self.environment.map.get_all_aois()
"""
AOI collection contains the following attributes:
- id (int): AOI ID
- positions (list[XYPosition]): Polygon shape coordinates
- area (float): Area in square meters
- driving_positions (list[LanePosition]): Connection points to driving lanes
- walking_positions (list[LanePosition]): Connection points to pedestrian lanes
- driving_gates (list[XYPosition]): AOI boundary positions for driving connections
- walking_gates (list[XYPosition]): AOI boundary positions for walking connections
- urban_land_use (Optional[str]): Urban land use classification (GB 50137-2011)
- poi_ids (list[int]): List of contained POI IDs
- shapely_xy (shapely.geometry.Polygon): AOI shape in xy coordinates
- shapely_lnglat (shapely.geometry.Polygon): AOI shape in lat/lng coordinates
"""

# Get all POIs (Points of Interest)
all_pois = self.environment.map.get_all_pois()
"""
POI collection contains the following attributes:
- id (int): POI ID
- name (string): POI name
- category (string): POI category code
- position (XYPosition): POI position
- aoi_id (int): AOI ID to which the POI belongs
"""

# Get specific AOI information
aoi_info = self.environment.map.get_aoi(aoi_id)

# Get specific POI information
poi_info = self.environment.map.get_poi(poi_id)

# Get POI categories
poi_cates = self.environment.get_poi_cate()

# Get POIs around agent's position
filtered_pois = self.environment.get_around_poi(
    center=(x, y),
    radius=1000,
    poi_type=["category_1", "category_2"],
)
```

### Movement Status Handling

Your agent should check the current movement status before making decisions:

```python
# Check if agent is currently moving
if citizen_status in self.movement_status:
    # Agent is walking or driving, you can interrupt by setting new destination
    # or return to let the current movement continue
    return
```

### Complete Agent Example

Here's a complete example showing how to implement a hurricane-aware agent:

```python
from agentsociety_benchmark.benchmarks import HurricaneMobilityAgent
from pycityproto.city.person.v2.motion_pb2 import Status
import random

class MyHurricaneMobilityAgent(HurricaneMobilityAgent):
    """
    A complete example agent for the Hurricane Mobility Generation benchmark.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def forward(self):
        # Get agent's home and workplace
        home = await self.status.get("home")
        home_aoi_id = home["aoi_position"]["aoi_id"]
        workplace = await self.status.get("work")
        work_aoi_id = workplace["aoi_position"]["aoi_id"]
        
        # Get current agent status
        citizen_status = await self.status.get("status")
        if citizen_status in self.movement_status:
            # Agent is moving, let it continue
            return
        
        # Get current position and time
        agent_position = await self.status.get("position")
        x = agent_position["xy_position"]["x"]
        y = agent_position["xy_position"]["y"]
        day, time = self.environment.get_datetime()
        
        # Get environment information
        all_aois = self.environment.map.get_all_aois()
        all_pois = self.environment.map.get_all_pois()
        
        # Get current weather information
        weather_info = self.get_current_weather()
        
        # Hurricane-aware decision logic
        if "is the weather is not good":
            # Hurricane is active - implement evacuation behavior
        else:
            # Normal weather conditions - regular mobility patterns
            if 6 <= time // 3600 <= 8:  # 6:00-8:00 AM
                # Morning: go to work
                if workplace_aoi_id:
                    await self.go_to_aoi(workplace_aoi_id)
            elif 12 <= time // 3600 <= 13:  # 12:00-1:00 PM
                # Lunch time: eating out
                await self.go_to_aoi(random.choice(list(all_aois.keys())))
            elif 18 <= time // 3600 <= 20:  # 6:00-8:00 PM
                # Evening: leisure or shopping
                await self.go_to_aoi(random.choice(list(all_aois.keys())))
            elif 22 <= time // 3600 or time // 3600 <= 6:  # 10:00 PM - 6:00 AM
                # Night: go home to sleep
                if home_aoi_id:
                    await self.go_to_aoi(home_aoi_id)
            else:
                # Other times: random activity
                await self.go_to_aoi(random.choice(list(all_aois.keys())))
```

### LLM Integration

Your agent can use the integrated LLM for sophisticated hurricane response decision-making:

```python
# Example of using LLM for hurricane-aware decision making
messages = [
    {"role": "system", "content": "You are an urban mobility expert specializing in hurricane response. Decide the next destination based on current weather conditions, time, and location."},
    {"role": "user", "content": f"""
    Current time: {time // 3600}:{(time % 3600) // 60:02d}
    Current position: ({x}, {y})
    Home AOI: {home_aoi_id}
    Workplace AOI: {workplace_aoi_id}
    
    Weather Information: {weather_info}
    
    Decide the next destination AOI ID based on hurricane conditions.
    Return format: AOI_ID
    """}
]

response = await self.llm.atext_request(messages)
# Parse response and execute movement
# Implementation details depend on your parsing strategy
```

### Return Format Requirements

Your agent does not need to return any specific data structure. The benchmark automatically collects:
- Movement trajectories through the `go_to_aoi` API calls
- Position data through the environment simulation
- Weather response patterns through movement frequency analysis

The benchmark will calculate the required metrics (total travel times, hourly travel times, relative changes) from the collected movement data across different hurricane phases.

## Evaluation Process

### Data Preparation Phase
1. **Real Data Loading**: Load real mobility behavior data during Hurricane Dorian from dataset
2. **Agent Initialization**: Configure agent parameters and hurricane environment settings
3. **Task Distribution**: Generate corresponding mobility behavior tasks for different time phases

### Behavior Generation Phase
1. **Environment Perception**: Agent understands hurricane impact and transportation condition changes
2. **Risk Assessment**: Analyze travel risks in different time phases
3. **Behavior Generation**: Generate mobility patterns conforming to extreme weather conditions
4. **Data Output**: Output structured mobility behavior data

### Evaluation Phase
1. **Change Rate Comparison**: Compare change rates between generated and real data
2. **Distribution Similarity**: Evaluate similarity of hourly travel distributions
3. **Weighted Scoring**: Combine various metrics to obtain final score

## Evaluation Metrics

### 1. Change Rate Accuracy (Change Rate Score)

Evaluate the accuracy of change rates in generated data during and after hurricane relative to before hurricane.

**Formula**:
```
MAPE = (|Real Change Rate - Generated Change Rate| / |Real Change Rate|) × 100%
Change Rate Score = max(0, 100 - Average MAPE)
```

where:
- **During Hurricane Change Rate**: (During Travel Time - Before Travel Time) / Before Travel Time × 100%
- **After Hurricane Change Rate**: (After Travel Time - Before Travel Time) / Before Travel Time × 100%
- **Average MAPE**: (During MAPE + After MAPE) / 2

### 2. Distribution Similarity (Distribution Score)

Evaluate similarity between generated and real hourly travel distributions.

**Formula**:
```
Cosine Similarity = (A · B) / (||A|| × ||B||)
Distribution Score = max(0, Average Cosine Similarity × 100)
```

where:
- A, B: Normalized hourly travel distribution vectors
- Average Cosine Similarity: (Before Similarity + During Similarity + After Similarity) / 3

### 3. Final Score

**Formula**:
```
Final Score = Change Rate Score × 0.6 + Distribution Score × 0.4
```

**Weight Explanation**:
- Change Rate Score weight 60%: Directly measures hurricane impact accuracy
- Distribution Score weight 40%: Evaluates temporal distribution similarity of travel patterns

## Dataset Information

- **Dataset Repository**: https://huggingface.co/datasets/tsinghua-fib-lab/hurricane-mobility-generation-benchmark
- **Branch**: main
- **Supported Modes**: inference (test mode not supported)
- **Data Features**: Real mobility behavior data during Hurricane Dorian

## Dependencies

```python
numpy >= 1.26.4
```

## Usage Example

```shell
asbench run --config <YOUR-CONFIG-FILE>.yml --agent <YOUR-AGENT-FILE>.py --mode inference HurricaneMobility
# After running in inference mode, the output result file (e.g., .pkl) in the specified directory is the final result for submission/scoring
```

## Output Data Format

```python
{
    "total_travel_times": [120, 85, 95],  # [Before, During, After] Total travel time (minutes)
    "hourly_travel_times": [
        [10, 15, 20, 25, 30, 35, 40, 35, 30, 25, 20, 15, 10, 5, 0, 0, 0, 0, 5, 10, 15, 20, 15, 10],  # Before 24-hour distribution
        [5, 8, 12, 15, 18, 20, 22, 20, 18, 15, 12, 8, 5, 2, 0, 0, 0, 0, 2, 5, 8, 12, 8, 5],  # During 24-hour distribution
        [8, 12, 16, 20, 24, 28, 32, 28, 24, 20, 16, 12, 8, 4, 0, 0, 0, 0, 4, 8, 12, 16, 12, 8]   # After 24-hour distribution
    ]
}
```

## Detailed Evaluation Metrics

Evaluation results also include the following detailed metrics:

```python
{
    "change_rate_score": 85.2,  # Change rate accuracy score
    "distribution_score": 78.9,  # Distribution similarity score
    "final_score": 82.7,  # Final weighted score
    "detailed_metrics": {
        "real_change_rates": {
            "during_vs_before": -29.2,  # Real during hurricane change rate (%)
            "after_vs_before": -20.8    # Real after hurricane change rate (%)
        },
        "generated_change_rates": {
            "during_vs_before": -31.5,  # Generated during hurricane change rate (%)
            "after_vs_before": -22.1    # Generated after hurricane change rate (%)
        },
        "change_rate_error": {
            "during_vs_before": 2.3,    # During hurricane change rate error
            "after_vs_before": 1.3      # After hurricane change rate error
        }
    }
}
```

## Version Information

- **Version**: 1.0.0
- **Author**: AgentSociety Team
- **Tags**: hurricane-mobility, extreme-weather 