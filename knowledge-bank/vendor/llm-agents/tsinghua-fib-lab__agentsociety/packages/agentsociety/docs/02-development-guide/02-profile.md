# 智能体画像

智能体画像是对虚拟世界中创建的每一个市民智能体的信息描述，包括姓名、性别、年龄、教育水平、职业、婚姻状况、人格角色、背景故事等内容，这些信息构成了智能体的自我认知，是智能体进行一切行为和决策的基础。

**文件示例**
```json
[
  {
    "name": "解琛",
    "gender": "男",
    "education": "小学及以下",
    "occupation": "物流文员",
    "marriage_status": "曾经结婚",
    "persona": "传统复兴者",
    "background_story": "解琛，36岁，在香港九龙的唐楼间租住一室，担任物流文员。虽学历不高，但他痴迷传统文化，常利用业余时间修复旧物，从破损的木雕到泛黄的书册皆精心处理。他婚姻失败后更坚定复兴传统的信念，抵制消费主义，将有限收入投入古玩市场。他信奉集体价值，常与邻里分享修复技艺，以传统连接人心。",
    "age": 36,
    "id": 1
  },
  {
    "name": "廖曉彤",
    "gender": "女",
    "education": "大学本科及以上",
    "occupation": "社工",
    "marriage_status": "曾经结婚",
    "persona": "文化混血儿",
    "background_story": "廖曉彤，60歲，香港土生土長，父親是廣東人，母親為英國移民。她自幼生活在中西文化交融的家庭，接受中式價值觀與西方自由思潮的雙重薰陶。曾任社工，致力於幫助弱勢群體融入多元社會。雖曾經結婚，現獨居，熱愛陶藝與閱讀，崇尚簡樸生活，在傳統與現代間尋求平衡，追求文化融合的生命意義。",
    "age": 60,
    "id": 2
  }
]
```

**字段说明：**
- `name` (str): 智能体姓名
- `gender` (str): 智能体性别
- `education` (str): 智能体教育水平
- `occupation` (str): 智能体职业
- `marriage_status` (str): 智能体婚姻状况
- `persona` (str): 智能体人格角色
- `background_story` (str): 智能体背景故事
- `age` (int): 智能体年龄
- `id` (int): 智能体ID，推荐设置为从1开始的连续整数，在实验设置中可用于{ref}`筛选智能体 <target_agent>`

上述信息将存储在智能体的Key-Value形式的`Status Memory`中，在运行过程中被按需提取以加入大模型请求中来影响大模型的决策行为。
其中`background_story`在默认的智能体实现中总是加入大模型提示词中，因此编写合适的背景故事是构建智能体画像的最关键的环节。

```{admonition} 提示
:class: note

我们提供了一些智能体画像的示例，可以登录[AgentSociety官网](https://agentsociety.fiblab.net/)内的[智能体画像](https://agentsociety.fiblab.net/profiles)下载。
```