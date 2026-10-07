# DailyMobility Benchmark

## Overview

The DailyMobility benchmark evaluates LLM agents' capabilities in daily mobility behavior generation based on Beijing users. This benchmark focuses on simulating real users' daily travel patterns, including key mobility features such as gyration radius, daily location numbers, intention sequences, and intention proportions.

## Evaluation Task

### Daily Mobility Behavior Generation
- **Task Description**: Generate daily mobility patterns that conform to real user behavior based on user characteristics and urban environment
- **Input**: User demographic features, city geographic information, time constraints
- **Output**: User daily mobility behavior data, including:
  - Gyration Radius
  - Daily Location Numbers
  - Intention Sequences
  - Intention Proportions

## Building Your Agent

### Agent Structure

Your agent should inherit from `DailyMobilityAgent` and implement the `forward` method. You can use `template_agent.py` as a starting point:

```python
from agentsociety_benchmark.benchmarks import DailyMobilityAgent

class YourDailyMobilityAgent(DailyMobilityAgent):
    """
    Your custom agent for the Daily Mobility Generation benchmark.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def forward(self):
        # Your implementation here
        pass
```

### Core APIs Provided by DailyMobilityAgent

The `DailyMobilityAgent` base class provides two essential APIs for mobility behavior generation:

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

#### 2. Intention Logging API: `log_intention(intention: str)`
"""
Logs the agent's current intention for the mobility behavior. (Description)
- **Description**:
    - Records the agent's current intention in the memory for tracking mobility patterns.

- **Args**:
    - `intention` (str): The intention type, must be one of the predefined intention types.

- **Returns**:
    - None: The intention is stored in the agent's memory.
"""

### Available Intention Types

Your agent must choose intentions from the following predefined list:
- `"sleep"`: Sleeping or resting activities
- `"home activity"`: Activities performed at home
- `"work"`: Work-related activities
- `"shopping"`: Shopping activities
- `"eating out"`: Dining activities outside home
- `"leisure and entertainment"`: Recreational activities
- `"other"`: Other activities not covered by the above categories

**Note**: Any intention type not in this list will be automatically categorized as `"other"`.

### Environment Information Access

Your agent can access comprehensive urban environment information through the following APIs:

#### Agent Status Information

```python
# Get agent's home and workplace
home = await self.status.get("home")
home_aoi_id = home["aoi_position"]["aoi_id"]
workplace = await self.status.get("work")
workplace_aoi_id = workplace["aoi_position"]["aoi_id"]

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

Here's a complete example showing how to implement a basic agent with proper API usage:

```python
from agentsociety_benchmark.benchmarks import DailyMobilityAgent
from pycityproto.city.person.v2.motion_pb2 import Status
import random

class MyDailyMobilityAgent(DailyMobilityAgent):
    """
    A complete example agent for the Daily Mobility Generation benchmark.
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
        
        # Simple decision logic based on time
        if 6 <= time // 3600 <= 8:  # 6:00-8:00 AM
            # Morning: go to work
            if workplace_aoi_id:
                await self.go_to_aoi(workplace_aoi_id)
                await self.log_intention("work")
        elif 12 <= time // 3600 <= 13:  # 12:00-1:00 PM
            # Lunch time: eating out
            await self.go_to_aoi(random.choice(list(all_aois.keys())))
            await self.log_intention("eating out")
        elif 18 <= time // 3600 <= 20:  # 6:00-8:00 PM
            # Evening: leisure or shopping
            await self.go_to_aoi(random.choice(list(all_aois.keys())))
            await self.log_intention(random.choice(["leisure and entertainment", "shopping"]))
        elif 22 <= time // 3600 or time // 3600 <= 6:  # 10:00 PM - 6:00 AM
            # Night: go home to sleep
            if home_aoi_id:
                await self.go_to_aoi(home_aoi_id)
                await self.log_intention("sleep")
        else:
            # Other times: random activity
            await self.go_to_aoi(random.choice(list(all_aois.keys())))
            await self.log_intention(random.choice(self.intention_list))
```

### LLM Integration

Your agent can use the integrated LLM for more sophisticated decision-making:

```python
# Example of using LLM for decision making
messages = [
    {"role": "system", "content": "You are an urban mobility expert. Decide the next destination and intention based on current time, location, and user characteristics."},
    {"role": "user", "content": f"""
    Current time: {time // 3600}:{(time % 3600) // 60:02d}
    Current position: ({x}, {y})
    Home AOI: {home_aoi_id}
    Workplace AOI: {workplace_aoi_id}
    
    Available intentions: {self.intention_list}
    
    Decide the next destination AOI ID and intention.
    Return format: AOI_ID, intention
    """}
]

response = await self.llm.atext_request(messages)
# Parse response and execute movement
# Implementation details depend on your parsing strategy
```

### Return Format Requirements

Your agent does not need to return any specific data structure. The benchmark automatically collects:
- Movement trajectories through the `go_to_aoi` API calls
- Intention sequences through the `log_intention` API calls
- Position data through the environment simulation

The benchmark will calculate the required metrics (gyration radius, daily location numbers, intention sequences, intention proportions) from the collected movement and intention data.

## Evaluation Process

### Data Preparation Phase
1. **Real Data Loading**: Load real mobility behavior data of Beijing users from dataset
2. **Agent Initialization**: Configure agent parameters and environment settings
3. **Task Distribution**: Generate corresponding mobility behavior tasks for each user

### Behavior Generation Phase
1. **User Feature Analysis**: Agent analyzes user demographic characteristics
2. **Environment Perception**: Understand city geographic layout and transportation network
3. **Behavior Generation**: Generate daily mobility patterns conforming to user characteristics
4. **Data Output**: Output structured mobility behavior data

### Evaluation Phase
1. **Distribution Comparison**: Compare generated data distribution with real data distribution
2. **JSD Calculation**: Calculate Jensen-Shannon divergence to evaluate distribution similarity
3. **Score Calculation**: Combine various metrics to obtain final score

## Evaluation Metrics

### Jensen-Shannon Divergence (JSD)

Jensen-Shannon divergence is used to measure the similarity between generated data distribution and real data distribution. Lower JSD values indicate more similar distributions.

**Formula**:
```
JSD(P||Q) = 0.5 × KL(P||M) + 0.5 × KL(Q||M)
```

where:
- P: Real data distribution
- Q: Generated data distribution
- M: (P + Q) / 2
- KL: Kullback-Leibler divergence

### Specific Evaluation Metrics

#### 1. Gyration Radius JSD
**Description**: Evaluate similarity between generated and real gyration radius distributions
**Formula**: `JSD(Real Gyration Radius Distribution || Generated Gyration Radius Distribution)`

#### 2. Daily Location Numbers JSD
**Description**: Evaluate similarity between generated and real daily location numbers distributions
**Formula**: `JSD(Real Location Numbers Distribution || Generated Location Numbers Distribution)`

#### 3. Intention Sequences JSD
**Description**: Evaluate similarity between generated and real intention sequences distributions
**Formula**: `JSD(Real Intention Sequences Distribution || Generated Intention Sequences Distribution)`

#### 4. Intention Proportions JSD
**Description**: Evaluate similarity between generated and real intention proportions distributions
**Formula**: `JSD(Real Intention Proportions Distribution || Generated Intention Proportions Distribution)`

### Final Score

**Formula**:
```
Final Score = ((1 - JSD_gyration + 1 - JSD_locations + 1 - JSD_sequences + 1 - JSD_proportions) / 4) × 100
```

**Explanation**:
- Each JSD metric is converted to similarity score: `1 - JSD`
- Four metrics are averaged with equal weights
- Final score ranges from 0-100, higher scores indicate better generation quality

## Dataset Information

- **Dataset Repository**: https://huggingface.co/datasets/tsinghua-fib-lab/daily-mobility-generation-benchmark
- **Branch**: main
- **Supported Modes**: inference (test mode not supported)
- **Data Features**: Beijing users' daily mobility behavior data

## Dependencies

```python
numpy >= 1.26.4
scipy >= 1.13.0
```

## Usage Example

```shell
asbench run --config <YOUR-CONFIG-FILE>.yml --agent <YOUR-AGENT-FILE>.py --mode inference DailyMobility
# After running, the output result file (e.g., .pkl) in the specified directory is the final result for submission/scoring
```

## Output Data Format

```python
{
    "gyration_radius": [2.5, 3.1, 1.8, ...],  # User gyration radius list
    "daily_location_numbers": [5, 7, 4, ...],  # Daily location numbers list
    "intention_sequences": [[1,2,3,1], [2,1,4,2], ...],  # Intention sequences list
    "intention_proportions": [[0.3,0.2,0.5], [0.4,0.3,0.3], ...]  # Intention proportions list
}
```

## Version Information

- **Version**: 1.0.0
- **Author**: AgentSociety Team
- **Tags**: mobility-generation 