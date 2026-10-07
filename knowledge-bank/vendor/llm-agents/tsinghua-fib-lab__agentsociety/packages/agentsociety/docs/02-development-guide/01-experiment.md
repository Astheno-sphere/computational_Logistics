# 实验设计

本文档主要介绍如何使用AgentSociety设计一个社会模拟实验。

---

当设计一个AgentSociety虚拟世界中的社会实验时，我们首先需要设定虚拟世界的**初始状态**，然后通过模拟社会的运转并施加**干预**来影响智能体的行为，最终通过一系列**数据收集**手段来获取智能体的信息以便评估实验结果。

举例来说，如果我们希望研究恶劣天气（以飓风为例）对市民的影响，我们需要挑选一个沿海城市并设置市民的初始属性（如年龄、职业等）作为**初始状态**，市民应该正常出行。

当模拟虚拟世界的1天后，飓风来袭，此时通过{ref}`修改环境 <environment>`中的天气变量，将天气设置为飓风作为**干预**，市民智能体将处理这一新的信息并通过大模型做出适当的反应。

模拟结束后，我们通过{ref}`问卷调查 <exp-survey>`来收集市民智能体对飓风的感受，并根据市民智能体的回答来评估飓风对市民的影响。

我们也可以[访问数据库](./05-data-analysis.md)获取模拟过程中市民智能体的位置、心情、认知、对话等数据，并进行进一步分析。

## 初始状态设定

虚拟世界的初始状态设定主要包括[智能体画像](./02-profile.md)与[地图](./03-map.md)两部分。

智能体画像是对虚拟世界中创建的每一个市民智能体的信息描述，包括姓名、性别、年龄、教育水平、职业、婚姻状况、人格角色、背景故事等内容，这些信息构成了智能体的自我认知，是智能体进行一切行为和决策的基础。
因此，合理设置智能体画像对于任何社会模拟实验都有关键影响。

```{admonition} 提示
:class: note

智能体画像通过[智能体配置](../03-config/04-agent.md)中的`memory_from_file`字段来设置，该字段接受一个JSON文件路径，文件格式参见[智能体画像](./02-profile.md)文档。
```

```{admonition} 注意
:class: warning

只有`citizens`类型智能体接受智能体画像输入。
```

地图将影响智能体所活动的物理空间，包括道路、建筑、兴趣点的不同，主要影响智能体对于“我在哪”、“我周围有什么”的认知过程，对于智能体空间行为的研究和实验有很重要的影响。

```{admonition} 提示
:class: note

地图通过[地图配置](../03-config/03-map.md)中的`file_path`字段来设置，该字段接受一个protobuf格式的地图文件路径，新地图的构建参见[自定义地图](./03-map.md)文档。
```

(exp-intervene)=
## 干预

AgentSociety提供多种方式来{ref}`干预 <intervene>`智能体的行为，包括：
- 发送消息（`message`）：向指定的智能体发送一段文字，该文字会由智能体的`react_to_intervention(message: str)`函数处理从而产生影响，处理方式由智能体类实现。
- 修改环境（`environment`）：修改环境变量，如天气、时间、温度等，智能体可以主动获取这些变量加入决策过程，从而间接影响智能体的行为。
- 修改智能体状态（`update_state`）：直接修改智能体的Key-Value形式的`Status Memory`内的值，这种方式相当于直接“篡改”智能体的记忆，需要充分了解智能体`Status Memory`中包含的字段，**一般不建议使用**。

干预过程需要通过在[实验配置](../03-config/05-exp.md)中添加“干预”相关的工作流步骤来实现，干预步骤的类型与参数参见{ref}`实验配置 <intervene>`文档。

**示例：**
```yaml
exp:
  name: ...
  workflow:
    - ...
    - type: message
      target_agent: [1, 2, 3, 4, 5]
      message: "马上有恶劣天气，立刻回家！"
    - type: environment
      key: weather
      value: "下雨"
    - type: update_state
      target_agent: [1, 2, 3, 4, 5]
      key: goods_consumption
      value: 1000
    - ...
```

(message-interception)=
## 数据收集

AgentSociety提供多种方式来收集智能体的行为数据，包括：
- 问卷调查（`survey`）：向指定的智能体发送{ref}`问卷 <exp-survey>`，智能体回答后将答案存储到数据库中。**推荐**采用问卷的方式来批量收集智能体对于多个问题的回答。
- 访谈（`interview`）：向指定的智能体发送访谈，智能体回答后将答案存储到数据库中。
- 状态存储（`save_context`）：将智能体的Key-Value形式的`Status Memory`存储到全局Context变量中，该变量最后存储为文件，可以用于后续分析。这种方式需要充分了解智能体`Status Memory`中包含的字段，**一般不建议使用**。

与干预类似，数据收集过程需要通过在[实验配置](../03-config/05-exp.md)中添加“数据收集”相关的工作流步骤来实现，数据收集步骤的类型与参数参见{ref}`实验配置 <intervene>`文档。

**示例：**
```yaml
exp:
  name: ...
  workflow:
    - ...
    - type: interview
      target_agent: [1, 2, 3, 4, 5]
      interview_message: "您好，我是社区工作人员，请问您对社区生活有什么看法？"
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
    - type: save_context
      target_agent: [1, 2, 3, 4, 5]
      key: goods_consumption
      save_as: agent_goods_consumption
    - ...
```