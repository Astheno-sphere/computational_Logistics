# 实验配置

实验配置定义了仿真实验的流程、环境参数等核心设置。

## 主要字段

**ExpConfig字段**：
- `name` (str): 实验名称，默认`default_experiment`
- `id` (UUID): 实验唯一标识符，自动生成
- `workflow` (list[WorkflowStepConfig]): 工作流步骤列表，必需
- `environment` (EnvironmentConfig): 环境配置

**EnvironmentConfig字段**：
- `start_tick` (int): 一天的开始时间（秒），默认28800（8:00）
- `metric_interval` (int): 指标收集间隔（秒），默认3600
- `weather` (str): 天气描述，默认"The weather is sunny"
- `temperature` (str): 温度描述，默认"The temperature is 23C"
- `workday` (bool): 是否为工作日，默认true
- `other_information` (str): 其他环境信息，默认空

(workflowstep)=
## 工作流步骤类型

**主要执行类型**：
- `run`: 按天执行模拟
  - `days` (float): 模拟天数
  - `ticks_per_step` (int): 每步时间间隔（秒）

- `step`: 按步执行模拟
  - `steps` (int): 执行步数
  - `ticks_per_step` (int): 每步时间间隔（秒）

(intervene)=
### 智能体交互类型

- `interview`: 向指定智能体发送访谈消息
  - `target_agent`: {ref}`目标智能体筛选设置 <target_agent>`
  - `interview_message` (str): 访谈消息

- `survey`: 向指定智能体发送问卷调查
  - `target_agent`: {ref}`目标智能体筛选设置 <target_agent>`
  - `survey`: 调查问卷对象，详见下方{ref}`问卷调查配置 <exp-survey>`

- `message`: 向智能体发送干预消息
  - `target_agent`: {ref}`目标智能体筛选设置 <target_agent>`
  - `intervene_message` (str): 干预消息

- `update_state`: 直接更新智能体状态
  - `target_agent`: {ref}`目标智能体筛选设置 <target_agent>`
  - `key` (str): 智能体状态键
  - `value` (Any): 状态值

(save_context)=
### 保存智能体上下文

- `save_context`: 保存智能体上下文到全局Context变量（dict），该变量最后存储为文件
  - `target_agent`: {ref}`目标智能体筛选设置 <target_agent>`
  - `key` (str): 智能体状态键
  - `save_as` (str): 全局变量`context`中保存智能体状态的上下文键

- `delete_agent`: 删除指定智能体
  - `target_agent`: {ref}`目标智能体筛选设置 <target_agent>`

(environment)=
### 环境控制类型

- `environment`: 修改环境变量，即`EnvironmentConfig`中除`start_tick`外的其他字段
  - `key` (str): 环境变量键
  - `value` (Any): 环境变量值

**其他类型**：
- `next_round`: 进入下一轮仿真，将重置所有智能体（调用`agent.reset()`，具体实现由智能体类决定）
- `function`: 执行自定义函数

(target_agent)=
### 目标智能体筛选设置

`target_agent`参数用于指定操作的目标智能体，支持两种格式：

#### 智能体ID列表

直接指定需要操作的智能体ID列表：

```yaml
target_agent: [1, 2, 3, 4, 5]
```

#### 智能体筛选配置对象

使用配置对象指定筛选条件，包括智能体类名列表（可选）和筛选条件（可选）：

```yaml
target_agent:
  agent_class: ["SocietyAgent"]
  filter_str: "${profile.age} > 30"
```

**筛选配置字段说明**：
- `agent_class` (Optional[list[str]]): 智能体类名列表，用于按类型筛选智能体
- `filter_str` (Optional[str]): 筛选条件字符串，支持对智能体属性进行条件判断

**筛选条件语法**：
筛选条件使用Python表达式语法，通过`${profile.属性名}`访问智能体属性：
- 支持比较操作：`>`, `<`, `>=`, `<=`, `==`, `!=`
- 支持逻辑操作：`and`, `or`, `not`
- 数值比较：`${profile.age} > 30`
- 字符串比较：`${profile.gender} == 'male'`
- 组合条件：`${profile.age} > 25 and ${profile.income} < 10000`

**筛选配置示例**：

按智能体类型筛选：
```yaml
target_agent:
  agent_class: ["SocietyAgent"]
```

按属性条件筛选：
```yaml
target_agent:
  filter_str: "${profile.age} >= 18 and ${profile.age} <= 65"
```

组合筛选（特定类型且满足条件的智能体）：
```yaml
target_agent:
  agent_class: ["SocietyAgent"]
  filter_str: "${profile.gender} == 'female' and ${profile.education} == 'university'"

target_agent:
  filter_str: "(${profile.age} > 30 and ${profile.income} > 8000) or ${profile.occupation} == 'teacher'"
```

**注意事项**：
- `agent_class`和`filter_str`至少需要提供一个
- 如果智能体属性为空或不存在筛选条件中的属性，该智能体将被排除
- 筛选条件中的属性名必须与智能体配置文件中的属性名完全匹配

(exp-survey)=
### 问卷调查配置

问卷调查配置用于定义在`survey`工作流步骤中使用的调查问卷。

#### Survey主要字段

- `id` (UUID): 问卷唯一标识符
- `title` (str): 问卷标题，可选，默认为空
- `description` (str): 问卷描述，可选，默认为空
- `pages` (list[Page]): 问卷页面列表，必需

#### Page字段

- `name` (str): 页面名称，必需
- `elements` (list[Question]): 页面中的问题列表，必需

#### Question字段

- `name` (str): 问题名称，必需，用作唯一标识
- `title` (str): 问题标题，必需，显示给用户的问题文本
- `type` (QuestionType): 问题类型，必需，详见下方问题类型
- `choices` (list[str]): 选择项列表，用于选择题，默认为空
- `required` (bool): 是否必填，默认为true
- `min_rating` (int): 评分最小值，用于评分题，默认为1
- `max_rating` (int): 评分最大值，用于评分题，默认为5

#### 问题类型

**1. 文本题 (text)**
- 自由文本输入
- 不需要额外配置

**2. 单选题 (radiogroup)**
- 从多个选项中选择一个
- 需要配置`choices`字段

**3. 多选题 (checkbox)**
- 从多个选项中选择多个
- 需要配置`choices`字段

**4. 评分题 (rating)**
- 数值评分
- 可配置`min_rating`和`max_rating`

#### Survey配置示例

**基础问卷配置**：
```yaml
survey:
  id: "550e8400-e29b-41d4-a716-446655440000"
  title: "社区生活满意度调查"
  description: "了解您对社区生活的看法和建议"
  pages:
    - name: "基本信息"
      elements:
        - name: "age_group"
          title: "您的年龄段是？"
          type: "radiogroup"
          choices: ["18-25岁", "26-35岁", "36-45岁", "46-60岁", "60岁以上"]
        - name: "satisfaction"
          title: "请为社区整体满意度评分"
          type: "rating"
          min_rating: 1
          max_rating: 10
```

**复杂问卷配置**：
```yaml
survey:
  id: "550e8400-e29b-41d4-a716-446655440001"
  title: "工作与生活平衡调查"
  description: "了解您的工作生活状态"
  pages:
    - name: "工作状况"
      elements:
        - name: "work_from_home"
          title: "您是否支持远程办公？"
          type: "radiogroup"
          choices: ["是", "否"]
        - name: "work_benefits"
          title: "您希望公司提供哪些福利？"
          type: "checkbox"
          choices: ["健康保险", "弹性工作时间", "年假", "培训机会", "健身房"]
        - name: "feedback"
          title: "请分享您对工作的看法"
          type: "text"
```

**在工作流中使用问卷**：
```yaml
exp:
  name: "满意度调查实验"
  workflow:
    - type: run
      days: 1
      ticks_per_step: 3600
    - type: survey
      target_agent:
        agent_class: ["SocietyAgent"]
        filter_str: "${profile.age} >= 18"
      survey:
        id: "550e8400-e29b-41d4-a716-446655440000"
        title: "社区生活满意度调查"
        description: "了解您对社区生活的看法和建议"
        pages:
          - name: "满意度评价"
            elements:
              - name: "overall_satisfaction"
                title: "您对社区生活的整体满意度如何？"
                type: "rating"
                min_rating: 1
                max_rating: 5
              - name: "improvement_areas"
                title: "您认为社区最需要改进的方面有哪些？"
                type: "checkbox"
                choices: ["交通便利性", "环境卫生", "安全状况", "商业配套", "社区活动"]
```

## 配置示例

**基础实验配置**：

该配置展示了一个简单的仿真实验，包含以下要素：
- 实验名称：`basic_simulation`
- 工作流：仅包含一个运行步骤，持续3天，每5分钟执行一次行动
- 环境设置：从早上8点（28800秒）开始，设置天气为晴天，温度为25°C，并指定为工作日

```yaml
exp:
  name: basic_simulation
  workflow:
    - type: run
      days: 3
      ticks_per_step: 300
  environment:
    start_tick: 28800
    weather: "晴天"
    temperature: "温度25°C"
    workday: true
```

**包含干预的复杂实验**：

该配置展示了一个包含多种干预操作的复杂实验：
- 实验名称：`intervention_study`
- 工作流包含4个步骤：
  1. 运行1天的仿真（初始阶段）
  2. 环境干预：将天气改为“下雨”
  3. 对指定智能体（ID 1-5）进行问卷调查
  4. 继续运行1天的仿真（观察阶段）
- 环境设置：从早上7点（25200秒）开始，每30分钟（1800秒）收集一次指标

```yaml
exp:
  name: intervention_study
  workflow:
    - type: run
      days: 1
      ticks_per_step: 300
    - type: environment
      key: weather
      value: "下雨"
    - type: survey
      target_agent: [1, 2, 3, 4, 5]
      survey:
        id: "550e8400-e29b-41d4-a716-446655440002"
        title: "天气影响调查"
        description: "了解天气变化对日常生活的影响"
        pages:
          - name: "出行影响"
            elements:
              - name: "travel_impact"
                title: "天气变化如何影响您的出行计划？"
                type: "text"
    - type: run
      days: 1
      ticks_per_step: 300
  environment:
    start_tick: 25200
    metric_interval: 1800
```

**智能体过滤配置**：
```yaml
exp:
  name: targeted_intervention
  workflow:
    - type: run
      days: 1
      ticks_per_step: 600
    - type: interview
      target_agent:
        agent_class: ["SocietyAgent"]
        filter_str: "${profile.age} > 30"
      interview_message: "请描述您对当前经济状况的看法"
  environment:
    start_tick: 28800
```