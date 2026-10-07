# BehaviorModeling Benchmark

## 概述

BehaviorModeling benchmark 旨在评估LLM智能体在用户行为建模方面的能力，包括物品推荐和评价生成两类核心任务。该benchmark支持test和inference两种运行模式，为智能体行为建模研究提供全面的评估框架。

## 评测任务

### 1. 物品推荐任务 (Recommendation Task)
- **任务描述**: 基于用户历史行为和偏好，为用户推荐最合适的物品
- **输入**: 用户ID、候选物品类别、候选物品列表
- **输出**: 按推荐优先级排序的物品列表

### 2. 评价生成任务 (Review Writing Task)
- **任务描述**: 模拟用户对特定物品的评价生成，包括评分和评论文本
- **输入**: 用户ID、物品ID、物品信息
- **输出**: 星级评分(1-5星)和评论文本

## 构建您的智能体

### 智能体结构

您的智能体应该继承自 `IndividualAgentBase` 并实现 `forward` 方法。可以参考 `template_agent.py` 文件作为起点：

```python
from agentsociety.agent import IndividualAgentBase
from typing import Any
from .interactiontool import InteractionTool  # 可选：直接导入InteractionTool

class YourBehaviorModelingAgent(IndividualAgentBase):
    """
    您的自定义行为建模智能体。
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def forward(self, task_context: dict[str, Any]):
        # 您的实现代码
        pass
```

### 任务上下文理解

`task_context` 参数包含任务执行所需的所有信息，不同任务类型会包含不同的字段：

```python
# 任务上下文结构
task_context = {
    "target": str,           # 任务类型: "review_writing" 或 "recommendation"
    "user_id": str,          # 当前任务的用户ID (所有任务类型都包含)
    
    # 仅推荐任务 (target == "recommendation") 包含的字段:
    "candidate_category": str, # 物品类别: "book", "business", "product"
    "candidate_list": list,  # 候选物品列表，包含物品ID字符串
    
    # 仅评价生成任务 (target == "review_writing") 包含的字段:
    "item_id": str,          # 需要生成评价的物品ID
}
```

**字段说明**:
- `target`: 任务目标类型
  - `"recommendation"`: 物品推荐任务
  - `"review_writing"`: 评价生成任务
- `user_id`: 用户标识符，用于获取用户历史行为和偏好
- `candidate_category`: 仅在推荐任务中出现，指定候选物品的类别
- `candidate_list`: 仅在推荐任务中出现，包含所有候选物品的ID列表
- `item_id`: 仅在评价生成任务中出现，指定需要生成评价的目标物品

### 使用交互工具

benchmark提供了用户-物品-评价交互工具 (`InteractionTool`) 来访问历史数据。该工具基于LMDB缓存，提供高效的数据查询功能：

```python
# 获取交互工具
user_item_review_tool = self.toolbox.get_tool_object("uir")
```

#### 用户信息查询

```python
# 获取用户详细信息
user_info = user_item_review_tool.get_user(user_id)
# 返回格式: {"user_id": str, "user_name": str, ...} 或 None
```

#### 物品信息查询

```python
# 获取物品详细信息
item_info = user_item_review_tool.get_item(item_id)
# 返回格式: {"item_id": str, "item_name": str, "category": str, ...} 或 None
```

#### 评价信息查询

```python
# 按不同条件查询评价
reviews_related_to_item = user_item_review_tool.get_reviews(item_id=item_id)
reviews_related_to_user = user_item_review_tool.get_reviews(user_id=user_id)
reviews_related_to_review = user_item_review_tool.get_reviews(review_id=review_id)

# 返回格式: [{"review_id": str, "user_id": str, "item_id": str, "stars": int, "review": str, ...}, ...]
```

### LLM集成

您的智能体可以使用集成的LLM进行推理和生成：

```python
# 1. 组织您的提示
messages = [
    {"role": "system", "content": "您是一个行为建模专家。"},
    {"role": "user", "content": "基于用户历史，推荐物品..."}
]

# 2. 调用LLM
response = await self.llm.atext_request(messages)

# 3. 解析响应
# 根据您的需求处理响应
```

**LLM使用最佳实践**：

**提示词设计**：
- 在系统提示中明确角色和任务目标
- 在用户提示中包含具体的任务要求和数据
- 使用结构化的输出格式要求，便于解析

**响应解析**：
- 设计明确的输出格式，如"评分: X, 评价: Y"
- 实现健壮的解析逻辑，处理LLM输出格式变化
- 提供默认值处理解析失败的情况

**性能优化**：
- 合理组织提示词，避免过长导致性能下降
- 在提示中包含关键信息，减少LLM推理负担
- 考虑使用few-shot示例提高生成质量

### 返回格式要求

您的智能体必须根据任务类型返回正确格式的结果：

```python
# 对于评价生成任务 (target == "review_writing")
if target == "review_writing":
    return {
        "stars": int,        # 1-5星评分，必须是整数
        "review": str        # 评价文本，字符串格式
    }

# 对于推荐任务 (target == "recommendation")
elif target == "recommendation":
    return {
        "item_list": list    # 排序后的物品ID列表，必须来自candidate_list
    }
```

**返回格式说明**：

**评价生成任务返回格式**：
- `stars`: 整数类型，范围1-5，表示用户对物品的星级评分
- `review`: 字符串类型，用户对物品的评价文本内容

**推荐任务返回格式**：
- `item_list`: 列表类型，包含按推荐优先级排序的物品ID
  - 列表中的每个元素必须是 `candidate_list` 中的物品ID
  - 列表长度应该等于 `candidate_list` 的长度
  - 排序顺序表示推荐优先级（第一个物品优先级最高）

### 完整智能体示例

以下是一个展示如何实现基本智能体的完整示例，包含详细的InteractionTool使用和最佳实践：

```python
from agentsociety.agent import IndividualAgentBase
from typing import Any

class BehaviorModelingAgent(IndividualAgentBase):
    """
    行为建模benchmark的完整示例智能体。
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def forward(self, task_context: dict[str, Any]):
        # 提取任务信息
        target = task_context["target"]
        user_id = task_context["user_id"]
        
        # 获取交互工具
        user_item_review_tool = self.toolbox.get_tool_object("uir")
        
        if target == "review_writing":
            item_id = task_context["item_id"]
            
            # 获取用户信息
            user_info = user_item_review_tool.get_user(user_id)
            
            # 获取物品信息
            item_info = user_item_review_tool.get_item(item_id)
            
            # 获取用户历史评价（用于学习用户偏好和写作风格）
            user_reviews = user_item_review_tool.get_reviews(user_id=user_id)
            
            # 获取物品相关评价（用于了解物品特点）
            item_reviews = user_item_review_tool.get_reviews(item_id=item_id)
            
            # 构建提示词，包含用户历史和物品信息
            user_history_text = ""
            if user_reviews:
                user_history_text = f"用户历史评价风格：{[r['review'][:100] + '...' for r in user_reviews[:3]]}"
            
            item_info_text = ""
            if item_info:
                item_info_text = f"物品信息：{item_info.get('item_name', '')} - {item_info.get('category', '')}"
            
            # 使用LLM生成评价
            messages = [
                {"role": "system", "content": "您是一个用户，需要为物品写评价。请根据用户的历史偏好和物品特点生成合适的评价。"},
                {"role": "user", "content": f"""
                用户ID: {user_id}
                {user_history_text}
                
                目标物品: {item_id}
                {item_info_text}
                
                请为该物品生成一个评价，包括1-5星评分和评价文本。
                返回格式：评分: [1-5], 评价: [评价文本]
                """}
            ]
            response = await self.llm.atext_request(messages)
            
            # 解析响应（这里简化处理，实际应该更复杂的解析逻辑）
            try:
                # 简单的解析示例
                if "评分:" in response and "评价:" in response:
                    stars_text = response.split("评分:")[1].split(",")[0].strip()
                    review_text = response.split("评价:")[1].strip()
                    stars = int(stars_text)
                    return {"stars": stars, "review": review_text}
                else:
                    # 默认返回
                    return {"stars": 4, "review": response}
            except:
                return {"stars": 4, "review": response}
            
        elif target == "recommendation":
            candidate_list = task_context["candidate_list"]
            candidate_category = task_context["candidate_category"]
            
            # 获取用户信息
            user_info = user_item_review_tool.get_user(user_id)
            
            # 获取用户历史评价（分析用户偏好）
            user_reviews = user_item_review_tool.get_reviews(user_id=user_id)
            
            # 获取候选物品信息
            candidate_items_info = []
            for item_id in candidate_list:
                item_info = user_item_review_tool.get_item(item_id)
                if item_info:
                    candidate_items_info.append(item_info)
            
            # 分析用户偏好
            user_preferences = ""
            if user_reviews:
                avg_rating = sum(r['stars'] for r in user_reviews) / len(user_reviews)
                user_preferences = f"用户平均评分: {avg_rating:.1f}星，历史评价数量: {len(user_reviews)}"
            
            # 构建候选物品描述
            candidates_text = ""
            for item_info in candidate_items_info:
                candidates_text += f"- {item_info.get('item_name', '')} (ID: {item_info.get('item_id', '')})\n"
            
            # 使用LLM生成推荐
            messages = [
                {"role": "system", "content": "您是一个推荐专家，需要根据用户偏好为用户推荐最合适的物品。"},
                {"role": "user", "content": f"""
                用户ID: {user_id}
                {user_preferences}
                
                候选物品类别: {candidate_category}
                候选物品列表:
                {candidates_text}
                
                请根据用户偏好，将候选物品按推荐优先级排序。
                返回格式：item_id1, item_id2, item_id3, ...
                """}
            ]
            response = await self.llm.atext_request(messages)
            
            # 解析响应并确保返回的列表包含所有候选物品
            try:
                # 简单的解析示例
                recommended_items = [item.strip() for item in response.split(",")]
                # 确保所有候选物品都在结果中
                final_list = []
                for item in recommended_items:
                    if item in candidate_list and item not in final_list:
                        final_list.append(item)
                # 添加未推荐的候选物品
                for item in candidate_list:
                    if item not in final_list:
                        final_list.append(item)
                return {"item_list": final_list}
            except:
                return {"item_list": candidate_list}
```

## 评测流程

### Test模式
1. **数据准备**: 加载测试数据集，包含用户行为历史和真实标签
2. **任务执行**: 智能体处理推荐和评价生成任务
3. **结果评估**: 计算各项评价指标
4. **分数计算**: 综合推荐准确率和评价质量得出最终分数

### Inference模式
1. **推理执行**: 智能体基于给定上下文进行推理
2. **结果验证**: 与真实标签进行对比
3. **指标收集**: 收集用于智能体执行效果评价的指标
4. **结果输出**: inference模式执行后会输出结果文件（如.pkl），该文件即为可提交/评分的最终结果

## 评价指标

### 推荐任务指标 (Recommendation Metrics)

#### Hit Rate@N
计算推荐列表中前N个物品包含真实目标物品的比例：

**公式**:
```
HR@N = (推荐列表前N个物品中包含真实物品的样本数) / (总样本数)
```

**具体指标**:
- **Top-1 Hit Rate**: HR@1，推荐列表第一个物品的命中率
- **Top-3 Hit Rate**: HR@3，推荐列表前三个物品的命中率  
- **Top-5 Hit Rate**: HR@5，推荐列表前五个物品的命中率
- **Average Hit Rate**: (HR@1 + HR@3 + HR@5) / 3

### 评价生成任务指标 (Simulation Metrics)

#### 1. 偏好估计准确率 (Preference Estimation)
基于星级评分的准确性：

**公式**:
```
Preference Estimation = 1 - (平均星级误差 / 5)
```

其中星级误差 = |预测星级 - 真实星级| / 5

#### 2. 评价生成质量 (Review Generation)
综合考虑情感、情绪和主题相似性：

**公式**:
```
Review Generation = 1 - (情感误差 × 0.25 + 情绪误差 × 0.25 + 主题误差 × 0.5)
```

**子指标**:
- **情感误差**: 使用VADER情感分析器计算生成评价与真实评价的情感极性差异
- **情绪误差**: 使用RoBERTa情绪分类器计算情绪分布差异
- **主题误差**: 使用SentenceTransformer计算语义相似度

#### 3. 整体质量 (Overall Quality)
**公式**:
```
Overall Quality = (Preference Estimation + Review Generation) / 2
```

### 最终评分 (Final Score)
**公式**:
```
Final Score = ((Average Hit Rate + Overall Quality) / 2) × 100
```

## 数据集信息

- **数据集仓库**: https://huggingface.co/datasets/tsinghua-fib-lab/behavior-modeling-benchmark
- **分支**: main
- **支持模式**: test, inference

## 依赖要求

```python
numpy >= 1.26.4
scipy >= 1.13.0
nltk
transformers
sentence-transformers
torch
lmdb  # 用于InteractionTool的数据缓存
tqdm  # 用于进度显示
```

**安装建议**：
```bash
pip install numpy>=1.26.4 scipy>=1.13.0 nltk transformers sentence-transformers torch lmdb tqdm
```

## 使用示例

```shell
# 测试模式：评估智能体性能
asbench run --config <YOUR-CONFIG>.yml --agent <YOUR-AGENT>.py --mode test BehaviorModeling

# 推理模式：生成推理结果
asbench run --config <YOUR-CONFIG>.yml --agent <YOUR-AGENT>.py --mode inference BehaviorModeling
# inference模式执行后会在指定目录输出结果文件（如.pkl），该文件即为可提交/评分的最终结果
```

**配置文件示例**：
```yaml
# config.yml
llm:
  provider: openai
  model: gpt-4
  api_key: your-api-key

# 其他配置项...
```

## 版本信息

- **版本**: 1.0.0
- **作者**: AgentSociety Team
- **标签**: behavior-modeling, recommendation, review-writing

## 相关文件

- `template_agent.py`: 智能体模板文件，包含基本结构和注释说明
- `interactiontool.py`: InteractionTool实现文件，提供数据访问功能
- `README.md`: 英文版说明文档
- `README_zh.md`: 中文版说明文档 