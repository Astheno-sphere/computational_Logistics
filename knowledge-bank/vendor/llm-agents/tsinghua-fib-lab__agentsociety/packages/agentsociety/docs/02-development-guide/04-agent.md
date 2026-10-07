# 智能体开发

本文档主要介绍如何在AgentSociety中设计和实现自定义智能体。

---

## 第一部分：智能体在AgentSociety中的定位

### 智能体的核心定位

在AgentSociety中，智能体是**城市环境中的自主执行单元**。每个智能体都代表着一个能够在城市环境中独立运行、自主决策的实体，它们构成了整个城市模拟系统的核心组成部分。

智能体不仅仅是简单的程序模块，而是具有以下特征的复杂系统：

- **自主性**：智能体能够根据自身状态和环境信息独立做出决策
- **持续性**：智能体在整个模拟过程中持续存在，维护自己的状态和历史
- **交互性**：智能体能够与其他智能体、环境系统进行交互
- **适应性**：智能体能够根据环境变化调整自己的行为策略

### 智能体的基本职责

作为城市环境中的自主执行单元，智能体承担着以下核心职责：

**1. 自主决策**: 智能体需要根据当前状态、历史经验和环境信息，自主决定下一步的行动。这种决策过程可能涉及：
- 需求分析：识别当前需要解决的问题
- 计划制定：制定实现目标的行动方案
- 行为执行：将计划转化为具体的行动

**2. 环境交互**: 智能体需要与城市环境进行持续的交互，包括：
- 环境感知：获取环境中的相关信息
- 状态更新：根据环境变化更新自身状态
- 行为反馈：通过行动影响环境状态

**3. 状态维护**: 智能体需要维护自己的内部状态，包括：
- 实时状态：当前的情绪、位置、活动等
- 历史记忆：过去的经历和决策
- 知识积累：从经验中学习到的知识

---

## 第二部分：智能体核心工作流

智能体的工作流是智能体运行的核心机制，定义了智能体如何响应和执行任务。理解工作流对于开发有效的智能体至关重要。

### 主动工作流：run()方法

智能体的主要工作流通过`run()`方法实现，这是一个统一的入口点，协调整个执行流程。

#### 基于run()方法控制的Agent工作流程

```python
async def run(self) -> Any:
    """
    Unified entry point for executing the agent's logic.
    
    - **Description**:
        - It calls the forward method to execute the agent's behavior logic.
        - Acts as the main control flow for the agent, coordinating when and how the agent performs its actions.
    """
    start_time = time.time()
    # run required methods before agent forward
    await self.before_forward()
    await self.before_blocks()
    # run agent forward
    await self.forward()
    # run required methods after agent forward
    await self.after_blocks()
    await self.after_forward()
    await self.status_summary()
    end_time = time.time()
    return end_time - start_time
```

**重要说明**：`run()`方法是智能体的统一入口点，**请勿修改**。它按照固定的顺序调用各个生命周期方法。

#### 必须实现的核心方法

**forward()方法**

```python
@abstractmethod
async def forward(self) -> Any:
    """
    Define the behavior logic of the agent.
    
    - **Description**:
        - This abstract method should contain the core logic for what the agent does at each step of its operation.
        - It is intended to be overridden by subclasses to define specific behaviors.
    """
    raise NotImplementedError
```

`forward()`方法是智能体的核心行为逻辑，**必须由子类实现**。它包含智能体的主要决策和行为逻辑。

**before_forward()和after_forward()方法**

```python
async def before_forward(self):
    """
    Before forward - prepare context and environment
    """
    pass

async def after_forward(self):
    """
    After forward - cleanup and save state
    """
    pass
```

这两个方法是**可选的**，用于执行前的准备工作和执行后的清理工作。

#### Block相关的生命周期执行方法

```python
async def before_blocks(self):
    """
    Before blocks - prepare all blocks
    """
    if self.blocks is None:
        return
    for block in self.blocks:
        await block.before_forward()

async def after_blocks(self):
    """
    After blocks - cleanup all blocks
    """
    if self.blocks is None:
        return
    for block in self.blocks:
        await block.after_forward()
```

这两个方法会自动调用所有注册Block的`before_forward()`和`after_forward()`方法，确保Block的生命周期管理，**请勿修改**。Block相关内容请参考后续内容。

### 被动响应工作流：react_to_intervention()

智能体需要响应外部干预，这是通过`react_to_intervention()`方法实现的。

```python
async def react_to_intervention(self, intervention_message: str):
    """
    React to an intervention.
    
    - **Args**:
        - `intervention_message` (`str`): The message of the intervention.
    
    - **Description**:
        - React to an intervention from external sources.
    """
    # Parse intervention message
    intervention_data = json.loads(intervention_message)
    
    # Update agent behavior based on intervention
    if intervention_data.get("type") == "policy_change":
        await self.memory.status.update("policy_awareness", True)
        await self.memory.stream.add(
            topic="intervention",
            description=f"Received policy intervention: {intervention_data.get('content')}"
        )
    
    # Adjust behavior accordingly
    await self.adjust_behavior_for_intervention(intervention_data)
```

**重要说明**：`react_to_intervention()`方法是**必须实现的**，用于处理外部干预。

### CitizenAgentBase的被动响应工作流

CitizenAgentBase除了标准的run()工作流外，还提供了几个核心的被动响应方法，这些方法都有默认实现，是可选的实现项。

#### do_chat()方法

用于响应其他智能体的社交消息

```python
async def do_chat(self, message: Message) -> str:
    """
    Process a chat message received from another agent.
    
    - **Args**:
        - `message` (`Message`): The chat message data received from another agent.
    
    - **Returns**:
        - `str`: Response to the chat message
    """
    # Default implementation
    resp = f"Agent {self.id} received agent chat response: {message.payload}"
    get_logger().debug(resp)
    return resp
```

**特点**：
- 有默认实现，可以直接使用
- 可以被子类重写以提供自定义的聊天响应逻辑
- 自动处理消息存储和日志记录

#### do_survey()方法

用于响应问卷调查

```python
async def do_survey(self, survey: Survey) -> str:
    """
    Process a survey questionnaire.
    
    - **Args**:
        - `survey` (`Survey`): The survey questionnaire to respond to.
    
    - **Returns**:
        - `str`: Survey response based on agent's memory and background
    """
    # Get survey questions
    questions = survey.to_prompt()
    
    # Generate response based on agent's memory
    response = await self.llm.atext_request([
        {"role": "system", "content": "You are a citizen, please answer based on your background"},
        {"role": "user", "content": questions[0]}
    ])
    
    return response
```

**特点**：
- 基于智能体的记忆生成调查回答
- 自动处理调查数据的存储
- 可以重写以提供更复杂的回答逻辑

#### do_interview()方法

用于响应采访

```python
async def do_interview(self, question: str) -> str:
    """
    Process an interview question.
    
    - **Args**:
        - `question` (`str`): The interview question.
    
    - **Returns**:
        - `str`: Interview response based on agent's background
    """
    # Get agent background
    background = await self.memory.status.get("background_story")
    
    # Generate interview response
    response = await self.llm.atext_request([
        {"role": "system", "content": f"You are {background}, please answer the interview question"},
        {"role": "user", "content": question}
    ])
    
    return response
```

**特点**：
- 基于智能体的背景故事生成访谈回答
- 支持深度交流，比问卷调查更注重个人经历
- 可以重写以提供更个性化的回答

### 工作流的执行顺序

智能体的工作流执行遵循以下顺序：

1. **主动工作流**（通过run()触发）：
   - `before_forward()` - 准备工作
   - `before_blocks()` - Block准备工作
   - `forward()` - 核心行为逻辑
   - `after_blocks()` - Block清理工作
   - `after_forward()` - 清理工作

2. **被动响应工作流**（由外部事件触发）：
   - `react_to_intervention()` - 响应干预
   - `do_chat()` - 响应聊天消息
   - `do_survey()` - 响应问卷调查
   - `do_interview()` - 响应访谈问题

### 5. 工作流设计原则

#### 主动工作流设计原则

- **单一职责**：每个生命周期方法只负责特定的功能
- **可扩展性**：可以轻松添加新的准备工作或清理工作
- **错误处理**：在每个阶段都要妥善处理异常
- **状态管理**：确保状态在各个环节的一致性

#### 被动响应工作流设计原则

- **响应性**：快速响应外部事件
- **一致性**：保持与主动工作流的状态一致
- **可定制性**：允许子类重写以提供特定行为
- **数据完整性**：确保响应数据的完整记录

---

## 第三部分：智能体核心子系统

AgentSociety的智能体设计基于四个核心要素，每个要素都有其独特的设计原理和价值。理解这些核心要素的设计思想对于开发高质量的智能体至关重要。

### 记忆系统设计原理

智能体的记忆系统是智能体能够保持连续性和学习能力的关键。AgentSociety设计了两种不同类型的记忆，每种都有其特定的用途和优势。

#### Status Memory：实时状态存储

Status Memory采用键值对的形式存储智能体的实时状态，具有以下特点：

- **快速访问**：通过键名直接访问，响应速度快
- **结构化存储**：每个状态都有明确的类型和默认值
- **实时更新**：状态可以随时更新，反映智能体的当前状况
- **可嵌入性**：支持向量化存储，便于语义检索

Status Memory主要用于存储：
- 智能体的基本属性（姓名、年龄、职业等）
- 当前状态（心情、位置、活动等）
- 实时数据（精力值、满意度等）

##### Status Memory的功能说明

**定义状态属性**

在智能体类中通过`StatusAttributes`类变量定义该智能体所包含的状态属性：

```python
class MyAgent(Agent):
    StatusAttributes = [
        MemoryAttribute(
            name="mood",
            type=str,
            default_or_value="happy",
            description="Agent's current mood",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="energy",
            type=float,
            default_or_value=0.8,
            description="Agent's energy level, 0-1",
        ),
        MemoryAttribute(
            name="current_activity",
            type=str,
            default_or_value="idle",
            description="Agent's current activity",
        ),
    ]
```

**获取状态值**

在智能体中通过`memory.status.get()`方法获取状态值：

```python
async def forward(self):
    # Get current mood and energy
    mood = await self.memory.status.get("mood")
    energy = await self.memory.status.get("energy")
```

**更新状态值**

在智能体中通过`memory.status.update()`方法更新状态值：

```python
async def update_status(self):
    # Update mood based on recent events
    await self.memory.status.update("mood", "excited")
```

#### Stream Memory：流式记忆

Stream Memory采用流式存储的方式记录智能体随时间线的经历，具有以下特点：

- **时序性**：按时间顺序记录事件和经历
- **丰富性**：可以存储复杂的文本描述和认知过程
- **可检索性**：支持语义检索，找到相关的历史经验
- **学习性**：通过历史经验指导未来的决策

Stream Memory主要用于存储：
- 智能体的经历和回忆
- 决策过程和思考过程
- 与其他智能体的交互历史
- 从环境中获得的事件信息

##### Stream Memory的功能说明

**添加记忆条目**

在智能体中通过`memory.stream.add()`方法添加新的记忆条目：

```python
async def record_experience(self, event: str, thought: str):
    # Record a new experience
    await self.memory.stream.add(
        topic=f"Event",
        description="I met my friend"
    )
```

**检索相关记忆**

通过语义检索找到相关的历史记忆：

```python
async def recall_related_memories(self, query: str, limit: int = 5):
    # Search for memories related to the query
    memories = await self.memory.stream.search(
        query=query,
        topic:Optional[str]='Event',
        top_k=limit
    )
    return memories
```

### Block系统设计原理

Block系统是AgentSociety中实现复杂智能体行为的关键设计。Block类似于神经网络中的层，每个Block负责特定的功能模块。

#### Block与Agent的关系

- **Agent是容器**：Agent负责协调和管理多个Block
- **Block是功能模块**：每个Block专注于特定的功能
- **组合式设计**：通过组合不同的Block构建复杂的智能体行为
- **可复用性**：Block可以在不同的智能体之间复用

#### Block存在的意义

Block系统的设计解决了以下问题：

- **模块化开发**：将复杂的行为分解为独立的功能模块
- **代码复用**：相同的功能可以在不同智能体中复用
- **易于测试**：每个Block可以独立测试
- **灵活组合**：可以根据需要组合不同的Block

#### Block设计原则

- **单一职责**：每个Block只负责一个特定的功能
- **可组合性**：Block之间可以灵活组合
- **可测试性**：每个Block都可以独立测试
- **可扩展性**：可以轻松添加新的Block

#### Block的功能说明

**创建自定义Block**

通过继承`Block`基类创建自定义Block：

```python
class MyBlockParams(BlockParams):
    threshold: float = 0.5
    max_iterations: int = 10

class MyBlockOutput(BlockOutput):
    success: bool = True
    result: str = ""
    confidence: float = 0.0

class MyCustomBlock(Block):
    ParamsType = MyBlockParams
    OutputType = MyBlockOutput
    name = "my_custom_block"
    description = "A custom block for specific functionality"
    
    async def forward(self, agent_context):
        # Get parameters
        threshold = self.params.threshold
        max_iterations = self.params.max_iterations
        
        # Access agent memory
        current_mood = await self.memory.status.get("mood")
        
        # Perform block-specific logic
        result = await self.process_logic(agent_context, threshold)
        
        # Return output
        return MyBlockOutput(
            success=True,
            result=result,
            confidence=0.8
        )
    
    async def process_logic(self, context, threshold):
        # Implement specific logic here
        return "Processed result"
```

**Block的生命周期**

每个Block都有完整的生命周期, 包括`before_forward`, `forward`以及`after_forward`三个部分，其中必须实现的为`forward`：

```python
class LifecycleBlock(Block):
    async def before_forward(self):  # Optional
        """Called before forward execution"""
        # Prepare context, validate inputs
        pass
    
    async def forward(self, agent_context):  # You have to rewrite the forward function
        """Main execution logic"""
        # Core block functionality
        return result
    
    async def after_forward(self):  # Optional
        """Called after forward execution"""
        # Cleanup, update state
        pass
```

**Block与Agent的集成**

方案一：在Agent中直接使用Block：

```python
class MyAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Create and add blocks
        self.analysis_block = MyCustomBlock(
            toolbox=self.toolbox,
            agent_memory=self.memory,
            block_params=MyBlockParams(threshold=0.7)
        )
        
        # Set agent reference for blocks that need it
        self.analysis_block.set_agent(self)
    
    async def forward(self):
        # Use blocks in agent logic
        context = self.context
        
        # Execute analysis block
        analysis_result = await self.analysis_block.forward(context)
        
        # Use block output for decision making
        if analysis_result.success and analysis_result.confidence > 0.8:
            # High confidence result, proceed with action
            pass
```

方案二：将多个Block注册到dispatcher中：

```python
class DispatcherAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Create multiple blocks
        self.news_collector = NewsCollectorBlock(
            toolbox=self.toolbox,
            agent_memory=self.memory,
            block_params=NewsCollectorParams(sources=["rss", "api"])
        )
        
        self.news_analyzer = NewsAnalyzerBlock(
            toolbox=self.toolbox,
            agent_memory=self.memory,
            block_params=NewsAnalyzerParams(importance_threshold=0.7)
        )
        
        self.news_distributor = NewsDistributorBlock(
            toolbox=self.toolbox,
            agent_memory=self.memory,
            block_params=NewsDistributorParams(distribution_channels=["social"])
        )
        
        # Set agent reference for blocks that need it
        for block in [self.news_collector, self.news_analyzer, self.news_distributor]:
            if block.NeedAgent:
                block.set_agent(self)
        
        # Register blocks to dispatcher
        self.dispatcher.register_blocks([
            self.news_collector,
            self.news_analyzer,
            self.news_distributor
        ])
    
    async def forward(self):
        # Update context with current intention
        self.context.current_intention = "collect and analyze news"
        
        # Let dispatcher automatically select the most appropriate block
        selected_block = await self.dispatcher.dispatch(self.context)
        
        if selected_block:
            # Execute the selected block
            result = await selected_block.forward(self.context)
            
            # Process the result
            if result.success:
                # Update context with block results
                self.context.last_block_result = result
                
                # Record the activity
                await self.memory.stream.add(
                    topic="activity",
                    description=f"Executed {selected_block.name}: {result.evaluation}"
                )
            else:
                # Handle block failure
                await self.memory.stream.add(
                    topic="error",
                    description=f"Block {selected_block.name} failed: {result.error}"
                )
        else:
            # No suitable block found
            await self.memory.stream.add(
                topic="activity",
                description=f"No suitable block found for: {self.context.current_intention}"
            )
        
        return "Agent behavior completed"
```

**Dispatcher工作原理**

Dispatcher基于Block的`name`和`description`，通过LLM智能选择最合适的Block来执行任务。Dispatcher使用可自定义的prompt模板，自动从context中获取格式化变量：

1. **Block注册**：每个Block在注册时需要提供清晰的`name`和`description`
2. **Prompt模板**：使用可自定义的prompt模板，支持从context中获取变量
3. **智能选择**：LLM根据prompt和Block描述进行语义匹配，选择最合适的Block

**自定义Dispatcher Prompt**

```python
# the default prompt template
DEFAULT_DISPATCHER_PROMPT = """
Based on the task information (which describes the needs of the user), select the most appropriate block to handle the task.
Each block has its specific functionality as described in the function schema.
        
Task information:
${context.current_intention}
"""

# define your dispatcher prompt
CUSTOM_DISPATCHER_PROMPT = """
Based on the current situation and agent state, select the most appropriate block to handle the task.

Current situation:
- Agent mood: ${context.current_mood}
- Current activity: ${context.current_activity}
- Task priority: ${context.task_priority}
- Available time: ${context.available_time}

Task information:
${context.current_intention}

Select the block that best matches the current situation and task requirements.
"""

# register your prompt
class CustomDispatcherAgent(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # register prompt
        self.dispatcher.register_dispatcher_prompt(CUSTOM_DISPATCHER_PROMPT)
        # register blocks
        self.dispatcher.register_blocks([...])
```

**Block描述的重要性**

```python
class WellDescribedBlock(Block):
    name = "news_collector"  # A clear name
    description = "Collects news from RSS feeds and APIs, filters content based on keywords, and returns structured news data"  # A clear description helps the LLM to make decisions
    
    async def forward(self, agent_context):
        # Block implementation
        pass
```

**Dispatcher的优势**

- **灵活配置**：支持自定义prompt模板
- **丰富上下文**：可以从context中获取任意变量
- **语义理解**：LLM能够理解复杂的上下文信息
- **智能匹配**：基于完整上下文选择最合适的Block
- **自动扩展**：添加新Block时无需修改选择逻辑
- **智能回退**：当没有合适Block时返回None而不是错误

**两种方案的区别**

| 特性 | 方案一：直接使用 | 方案二：Dispatcher |
|------|----------------|-------------------|
| **控制方式** | 手动控制Block执行顺序 | 自动选择最合适的Block |
| **灵活性** | 高，可以精确控制执行逻辑 | 中等，依赖LLM选择 |
| **复杂度** | 需要手动管理Block调用 | 自动管理，代码更简洁 |
| **适用场景** | 明确的执行流程 | 动态的任务分配 |
| **调试难度** | 容易调试，流程清晰 | 需要理解dispatcher逻辑 |

**Block参数配置**

Block支持灵活的参数配置：

```python
# Configure block with specific parameters
analysis_block = MyCustomBlock(
    toolbox=toolbox,
    agent_memory=memory,
    block_params=MyBlockParams(
        threshold=0.8,
        max_iterations=15
    )
)

# Access parameters in block
threshold = self.params.threshold
max_iterations = self.params.max_iterations
```

### 工具集合设计原理

AgentToolbox为智能体提供了统一的核心工具集合，每个工具都有其特定的作用和价值。

#### LLM工具：智能体的大脑

LLM工具是智能体进行推理和决策的核心：

- **自然语言理解**：理解输入的自然语言
- **推理能力**：基于上下文进行逻辑推理
- **生成能力**：生成自然语言的回复
- **知识应用**：应用已有的知识解决问题

#### Environment工具：环境感知和交互

Environment工具让智能体能够感知和影响环境：

- **环境感知**：获取环境中的信息（天气、位置、其他智能体等）
- **状态查询**：查询环境中的各种状态
- **行为执行**：在环境中执行具体的行动
- **反馈获取**：获取行动的结果和反馈

#### 访问核心工具

智能体可以直接访问工具箱中的核心工具：

```python
class MyAgent(Agent):
    async def forward(self):
        # Access LLM for reasoning
        response = await self.llm.atext_request([
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "What should I do next?"}
        ])
        
        # Access environment for information
        current_time = self.environment.get_datetime()
        weather = self.environment.sense("weather")
```

### 上下文系统设计原理

上下文系统不仅为智能体的长时间执行提供了统一的上下文入口，同时也为智能体和Block之间提供了灵活的信息传递机制。

#### AgentContext：智能体级别的上下文

AgentContext用于维护智能体级别的上下文信息：

- **全局状态**：智能体的全局状态信息
- **环境信息**：从环境获取的信息
- **配置参数**：智能体的配置参数
- **执行结果**：智能体执行的结果

#### BlockContext：模块级别的上下文

BlockContext用于在Block之间传递信息：

- **输入数据**：Block的输入数据
- **处理结果**：Block的处理结果
- **中间状态**：Block处理过程中的中间状态
- **错误信息**：Block执行过程中的错误信息

#### 上下文的作用

上下文系统解决了以下问题：

- **信息传递**：在不同组件之间传递信息
- **状态管理**：管理智能体和Block的状态
- **参数配置**：配置智能体和Block的参数
- **结果返回**：返回执行结果和错误信息

#### DotDict的设计

上下文系统基于DotDict实现，提供了点号访问的便利性：

- **属性式访问**：使用点号访问字典元素
- **嵌套支持**：支持嵌套的字典结构
- **合并操作**：支持字典的合并操作
- **深拷贝**：自动进行深拷贝，避免副作用

#### 上下文系统的功能说明

**定义AgentContext**

创建自定义的AgentContext类：

```python
class MyAgentContext(AgentContext):
    current_time: str = ""
    current_location: str = ""
    current_mood: str = ""
    recent_events: list[str] = []
    decision_history: list[dict] = []
    
    class Config:
        arbitrary_types_allowed = True
```

**定义BlockContext**

创建自定义的BlockContext类：

```python
class MyBlockContext(BlockContext):
    input_data: str = ""
    processing_stage: str = "initial"
    intermediate_results: list = []
    error_message: str = ""
    confidence_score: float = 0.0
```

**在Agent中使用上下文**

```python
class MyAgent(Agent):
    Context = MyAgentContext
    
    async def before_forward(self):
        # Update context with current information
        self.context.current_time = self.environment.get_datetime()
        self.context.current_location = self.environment.get_location()
        self.context.current_mood = await self.memory.status.get("mood")
        
        # Add recent events to context
        recent_memories = await self.memory.stream.search("", limit=5)
        self.context.recent_events = [mem.content for mem in recent_memories]
    
    async def forward(self):
        # Use context information for decision making
        if self.context.current_mood == "happy":
            # Agent is happy, can work efficiently
            pass
        elif len(self.context.recent_events) > 0:
            # Process recent events
            await self.process_recent_events(self.context.recent_events)
```

**在Block中使用上下文**

```python
class MyBlock(Block):
    Context = MyBlockContext
    
    async def forward(self, agent_context):
        # Initialize block context
        self.context.input_data = agent_context.get("input", "")
        self.context.processing_stage = "started"
        
        try:
            # Process input data
            result = await self.process_data(self.context.input_data)
            self.context.intermediate_results.append(result)
            
            # Update processing stage
            self.context.processing_stage = "completed"
            self.context.confidence_score = 0.9
            
            return result
            
        except Exception as e:
            # Handle errors
            self.context.error_message = str(e)
            self.context.processing_stage = "error"
            self.context.confidence_score = 0.0
            raise
```

**DotDict的使用**

DotDict提供了便利的点号访问：

```python
# Create DotDict
context = DotDict({
    "user": {
        "name": "Alice",
        "preferences": {
            "color": "blue",
            "food": "pizza"
        }
    },
    "session": {
        "start_time": "2024-01-01 10:00:00"
    }
})

# Access using dot notation
user_name = context.user.name  # "Alice"
user_color = context.user.preferences.color  # "blue"
session_time = context.session.start_time  # "2024-01-01 10:00:00"

# Update values
context.user.preferences.food = "sushi"

# Merge with another DotDict
additional_context = DotDict({
    "user": {
        "age": 25
    },
    "system": {
        "version": "1.0"
    }
})

# Merge contexts
merged_context = context | additional_context
# Now merged_context.user.age = 25, merged_context.system.version = "1.0"
```

**上下文传递示例**

```python
class ContextAwareAgent(Agent):
    Context = MyAgentContext
    
    async def forward(self):
        # Prepare agent context
        await self.prepare_context()
        
        # Pass context to blocks
        for block in self.blocks:
            try:
                result = await block.forward(self.context)
                # Update context with block results
                self.context.decision_history.append({
                    "block": block.name,
                    "result": result,
                    "timestamp": self.context.current_time
                })
            except Exception as e:
                # Handle block errors
                self.context.decision_history.append({
                    "block": block.name,
                    "error": str(e),
                    "timestamp": self.context.current_time
                })
    
    async def prepare_context(self):
        # Gather all necessary information
        self.context.current_time = self.environment.get_datetime()
        self.context.current_location = self.environment.get_location()
        self.context.current_mood = await self.memory.status.get("mood")
        
        # Get recent memories for context
        recent_memories = await self.memory.stream.search("", limit=3)
        self.context.recent_events = [mem.content for mem in recent_memories]
```

---

## 第四部分：开发示例

本小节通过具体的开发示例，展示如何在AgentSociety中构建不同类型的智能体。每个示例都包含完整的需求分析、设计思路和实现代码。

### 智能体类型与基类选择

在开始开发之前，需要根据智能体的功能和职责选择合适的基类：

| 实体类型 | 对应基类 | 主要功能 | 适用场景 |
|---------|---------|---------|---------|
| 城市居民 | CitizenAgentBase | 交通模拟、经济系统绑定、日常行为 | 模拟普通市民的生活行为 |
| 企业机构 | FirmAgentBase | 生产经营、市场交互、决策制定 | 模拟企业的经营决策 |
| 银行机构 | BankAgentBase | 金融服务、资金管理、风险评估 | 模拟银行的金融业务 |
| 政府机构 | GovernmentAgentBase | 政策制定、公共服务、监管职能 | 模拟政府的政策制定 |
| 央行机构 | NBSAgentBase | 货币政策、金融监管、宏观调控 | 模拟央行的货币政策 |
| 其他机构 | InstitutionAgentBase | 通用机构功能、组织管理 | 模拟其他类型的机构 |

### 开发流程概述

智能体开发遵循以下基本流程：

1. **需求分析**：明确智能体的功能需求和行为特征
2. **基类选择**：根据功能选择合适的智能体基类
3. **记忆设计**：定义Status Memory中的内容，明确Stream Memory在智能体中的作用
4. **Block设计**：将复杂功能分解为独立的Block模块
5. **逻辑实现**：实现智能体的核心行为逻辑
6. **测试验证**：验证智能体的功能和性能

### 完整开发案例：新闻传播智能体

#### 需求分析

构建一个能够收集、分析和传播新闻的智能体，具备以下功能：
- 从多个来源收集新闻信息
- 分析新闻内容的重要性和相关性
- 决定是否传播新闻以及传播方式
- 跟踪新闻传播的效果

#### 功能分解与Block设计

通过需求分析，将功能分解为以下Block：

1. **NewsCollectorBlock**：新闻收集模块
   - 从不同来源获取新闻
   - 过滤和预处理新闻内容
   - 提取新闻的关键信息

2. **NewsAnalyzerBlock**：新闻分析模块
   - 分析新闻的重要性
   - 评估新闻的相关性
   - 生成新闻摘要

3. **NewsDistributorBlock**：新闻传播模块
   - 决定传播策略
   - 选择传播渠道
   - 跟踪传播效果

#### 完整实现

**Step 1: 定义智能体参数和上下文**

```python
class NewsAgentParams(AgentParams):
    collection_interval: int = 300  # collection interval (s)
    analysis_threshold: float = 0.7  # analysis threshold
    distribution_radius: int = 1000  # broadcast radius

class NewsAgentContext(AgentContext):
    current_news_count: int = 0
    last_collection_time: str = ""
    distribution_stats: dict = {}

class NewsBlockOutput(BlockOutput):
    success: bool = True
    news_items: list = []
    analysis_results: dict = {}
    distribution_results: dict = {}
```

**Step 2: 实现新闻收集Block**

```python
class NewsCollectorParams(BlockParams):
    sources: list[str] = ["rss", "api", "social"]
    max_items_per_source: int = 10
    filter_keywords: list[str] = []

class NewsCollectorOutput(BlockOutput):
    collected_news: list[dict] = []
    source_stats: dict = {}

class NewsCollectorBlock(Block):
    ParamsType = NewsCollectorParams
    OutputType = NewsCollectorOutput
    name = "news_collector"
    description = "Collects news from various sources"
    
    async def forward(self, agent_context):
        collected_news = []
        source_stats = {}
        
        # Collect from RSS sources
        if "rss" in self.params.sources:
            rss_news = await self.collect_from_rss()
            collected_news.extend(rss_news)
            source_stats["rss"] = len(rss_news)
        
        # Collect from API sources
        if "api" in self.params.sources:
            api_news = await self.collect_from_api()
            collected_news.extend(api_news)
            source_stats["api"] = len(api_news)
        
        # Filter news based on keywords
        filtered_news = await self.filter_news(collected_news)
        
        return NewsCollectorOutput(
            collected_news=filtered_news,
            source_stats=source_stats
        )
    
    async def collect_from_rss(self):
        # Simulate RSS collection
        return [
            {"title": "Breaking News", "content": "Important event", "source": "rss"},
            {"title": "Local Update", "content": "Community news", "source": "rss"}
        ]
    
    async def collect_from_api(self):
        # Simulate API collection
        return [
            {"title": "Tech News", "content": "Technology update", "source": "api"}
        ]
    
    async def filter_news(self, news_list):
        # Filter based on keywords
        filtered = []
        for news in news_list:
            if any(keyword in news["title"].lower() for keyword in self.params.filter_keywords):
                filtered.append(news)
        return filtered
```

**Step 3: 实现新闻分析Block**

```python
class NewsAnalyzerParams(BlockParams):
    importance_threshold: float = 0.6
    relevance_keywords: list[str] = []

class NewsAnalyzerOutput(BlockOutput):
    analyzed_news: list[dict] = []
    importance_scores: dict = {}

class NewsAnalyzerBlock(Block):
    ParamsType = NewsAnalyzerParams
    OutputType = NewsAnalyzerOutput
    name = "news_analyzer"
    description = "Analyzes news content for importance and relevance"
    
    async def forward(self, agent_context):
        # Get news from previous block
        news_items = agent_context.get("collected_news", [])
        
        analyzed_news = []
        importance_scores = {}
        
        for news in news_items:
            # Analyze importance using LLM
            importance_prompt = f"""
            Analyze the importance of this news:
            Title: {news['title']}
            Content: {news['content']}
            
            Rate importance from 0-1 and explain why.
            """
            
            importance_response = await self.llm.atext_request([
                {"role": "system", "content": "You are a news analyst"},
                {"role": "user", "content": importance_prompt}
            ])
            
            # Extract importance score (simplified)
            importance_score = 0.7  # In real implementation, parse from response
            
            # Check if news meets importance threshold
            if importance_score >= self.params.importance_threshold:
                analyzed_news.append({
                    **news,
                    "importance_score": importance_score,
                    "should_distribute": True
                })
                importance_scores[news["title"]] = importance_score
        
        return NewsAnalyzerOutput(
            analyzed_news=analyzed_news,
            importance_scores=importance_scores
        )
```

**Step 4: 实现新闻传播Block**

```python
class NewsDistributorParams(BlockParams):
    distribution_channels: list[str] = ["social", "email", "broadcast"]
    target_audience: list[int] = []

class NewsDistributorOutput(BlockOutput):
    distribution_results: dict = {}
    audience_reached: int = 0

class NewsDistributorBlock(Block):
    ParamsType = NewsDistributorParams
    OutputType = NewsDistributorOutput
    name = "news_distributor"
    description = "Distributes news to target audience"
    
    async def forward(self, agent_context):
        # Get analyzed news
        analyzed_news = agent_context.get("analyzed_news", [])
        
        distribution_results = {}
        audience_reached = 0
        
        for news in analyzed_news:
            if news.get("should_distribute", False):
                # Distribute through different channels
                for channel in self.params.distribution_channels:
                    result = await self.distribute_through_channel(news, channel)
                    distribution_results[f"{news['title']}_{channel}"] = result
                    audience_reached += result.get("audience_reached", 0)
        
        return NewsDistributorOutput(
            distribution_results=distribution_results,
            audience_reached=audience_reached
        )
    
    async def distribute_through_channel(self, news, channel):
        # Simulate distribution
        if channel == "social":
            # Send to nearby agents
            nearby_agents = self.environment.get_nearby_agents(radius=100)
            await self.messager.send_message_to_multiple(
                agent_ids=nearby_agents,
                content=f"News: {news['title']} - {news['content']}",
                message_type="news"
            )
            return {"audience_reached": len(nearby_agents), "channel": channel}
        
        return {"audience_reached": 0, "channel": channel}
```

**Step 5: 集成为完整的新闻传播智能体**

```python
class NewsAgent(CitizenAgentBase):
    ParamsType = NewsAgentParams
    Context = NewsAgentContext
    BlockOutputType = NewsBlockOutput
    
    # Define status attributes
    StatusAttributes = [
        MemoryAttribute(
            name="news_collection_count",
            type=int,
            default_or_value=0,
            description="Total number of news items collected",
        ),
        MemoryAttribute(
            name="distribution_success_rate",
            type=float,
            default_or_value=0.0,
            description="Success rate of news distribution",
        ),
        MemoryAttribute(
            name="last_news_collection",
            type=str,
            default_or_value="",
            description="Timestamp of last news collection",
        ),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initialize blocks
        self.collector_block = NewsCollectorBlock(
            toolbox=self.toolbox,
            agent_memory=self.memory,
            block_params=NewsCollectorParams(
                sources=["rss", "api"],
                filter_keywords=["breaking", "important", "urgent"]
            )
        )
        
        self.analyzer_block = NewsAnalyzerBlock(
            toolbox=self.toolbox,
            agent_memory=self.memory,
            block_params=NewsAnalyzerParams(
                importance_threshold=0.7
            )
        )
        
        self.distributor_block = NewsDistributorBlock(
            toolbox=self.toolbox,
            agent_memory=self.memory,
            block_params=NewsDistributorParams(
                distribution_channels=["social", "broadcast"]
            )
        )
        
        # Set agent reference for blocks
        self.collector_block.set_agent(self)
        self.analyzer_block.set_agent(self)
        self.distributor_block.set_agent(self)
    
    async def forward(self):
        # Update context
        self.context.current_news_count = await self.memory.status.get("news_collection_count")
        self.context.last_collection_time = self.environment.get_datetime()
        
        # Execute news collection
        collection_result = await self.collector_block.forward(self.context)
        
        # Update context with collection results
        self.context.collected_news = collection_result.collected_news
        
        # Execute news analysis
        analysis_result = await self.analyzer_block.forward(self.context)
        
        # Update context with analysis results
        self.context.analyzed_news = analysis_result.analyzed_news
        
        # Execute news distribution
        distribution_result = await self.distributor_block.forward(self.context)
        
        # Update memory with results
        await self.memory.status.update("news_collection_count", 
                                      self.context.current_news_count + len(collection_result.collected_news))
        
        # Calculate success rate
        total_distributed = len(distribution_result.distribution_results)
        if total_distributed > 0:
            success_rate = distribution_result.audience_reached / total_distributed
            await self.memory.status.update("distribution_success_rate", success_rate)
        
        await self.memory.status.update("last_news_collection", self.context.last_collection_time)
        
        # Record experience in stream memory
        await self.memory.stream.add(
            content=f"Collected {len(collection_result.collected_news)} news items, "
                   f"distributed to {distribution_result.audience_reached} audience",
            metadata={"type": "news_cycle", "timestamp": self.context.last_collection_time}
        )
        
        return NewsBlockOutput(
            news_items=collection_result.collected_news,
            analysis_results=analysis_result.importance_scores,
            distribution_results=distribution_result.distribution_results
        )
```
