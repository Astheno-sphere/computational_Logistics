# BehaviorModeling Benchmark

## Overview

The BehaviorModeling benchmark evaluates LLM agents' capabilities in user behavior modeling, including two core tasks: item recommendation and review generation. This benchmark supports both test and inference modes, providing a comprehensive evaluation framework for agent behavior modeling research.

## Evaluation Tasks

### 1. Item Recommendation Task
- **Task Description**: Recommend the most suitable items to users based on their historical behavior and preferences
- **Input**: User ID, candidate item category, candidate item list
- **Output**: Ranked item list by recommendation priority

### 2. Review Generation Task
- **Task Description**: Simulate user review generation for specific items, including ratings and review text
- **Input**: User ID, item ID, item information
- **Output**: Star rating (1-5 stars) and review text

## Building Your Agent

### Agent Structure

Your agent should inherit from `IndividualAgentBase` and implement the `forward` method. You can use `template_agent.py` as a starting point:

```python
from agentsociety.agent import IndividualAgentBase
from typing import Any
from .interactiontool import InteractionTool  # Optional: direct import of InteractionTool

class YourBehaviorModelingAgent(IndividualAgentBase):
    """
    Your custom agent for the Behavior Modeling benchmark.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def forward(self, task_context: dict[str, Any]):
        # Your implementation here
        pass
```

### Task Context Understanding

The `task_context` parameter contains all necessary information for task execution, with different fields for different task types:

```python
# Task Context Structure
task_context = {
    "target": str,           # Task type: "review_writing" or "recommendation"
    "user_id": str,          # User ID for the current task (included in all task types)
    
    # Fields only included in recommendation tasks (target == "recommendation"):
    "candidate_category": str, # Item category: "book", "business", "product"
    "candidate_list": list,  # List of candidate item IDs as strings
    
    # Fields only included in review writing tasks (target == "review_writing"):
    "item_id": str,          # Item ID for the target item to generate review
}
```

**Field Descriptions**:
- `target`: Task objective type
  - `"recommendation"`: Item recommendation task
  - `"review_writing"`: Review generation task
- `user_id`: User identifier for retrieving user behavior history and preferences
- `candidate_category`: Only appears in recommendation tasks, specifies the category of candidate items
- `candidate_list`: Only appears in recommendation tasks, contains list of all candidate item IDs
- `item_id`: Only appears in review writing tasks, specifies the target item for review generation

### Using Interaction Tools

The benchmark provides a user-item-review interaction tool (`InteractionTool`) to access historical data. This tool is based on LMDB caching and provides efficient data querying capabilities:

```python
# Get the interaction tool
user_item_review_tool = self.toolbox.get_tool_object("uir")
```

#### User Information Queries

```python
# Get detailed user information
user_info = user_item_review_tool.get_user(user_id)
# Returns: {"user_id": str, "user_name": str, ...} or None
```

#### Item Information Queries

```python
# Get detailed item information
item_info = user_item_review_tool.get_item(item_id)
# Returns: {"item_id": str, "item_name": str, "category": str, ...} or None
```

#### Review Information Queries

```python
# Query reviews by different criteria
reviews_related_to_item = user_item_review_tool.get_reviews(item_id=item_id)
reviews_related_to_user = user_item_review_tool.get_reviews(user_id=user_id)
reviews_related_to_review = user_item_review_tool.get_reviews(review_id=review_id)

# Returns: [{"review_id": str, "user_id": str, "item_id": str, "stars": int, "review": str, ...}, ...]
```

### LLM Integration

Your agent can use the integrated LLM for reasoning and generation:

```python
# 1. Organize your prompt
messages = [
    {"role": "system", "content": "You are a behavior modeling expert."},
    {"role": "user", "content": "Based on user history, recommend items..."}
]

# 2. Call the LLM
response = await self.llm.atext_request(messages)

# 3. Parse the response
# Process the response according to your needs
```

**LLM Usage Best Practices**:

**Prompt Design**:
- Clearly define role and task objectives in system prompts
- Include specific task requirements and data in user prompts
- Use structured output format requirements for easier parsing

**Response Parsing**:
- Design clear output formats, such as "Rating: X, Review: Y"
- Implement robust parsing logic to handle LLM output format variations
- Provide default values for parsing failure scenarios

**Performance Optimization**:
- Organize prompts reasonably to avoid performance degradation from excessive length
- Include key information in prompts to reduce LLM reasoning burden
- Consider using few-shot examples to improve generation quality

### Return Format Requirements

Your agent must return results in the correct format based on the task type:

```python
# For review writing tasks (target == "review_writing")
if target == "review_writing":
    return {
        "stars": int,        # Rating from 1-5, must be integer
        "review": str        # Review text, string format
    }

# For recommendation tasks (target == "recommendation")
elif target == "recommendation":
    return {
        "item_list": list    # Ranked list of item IDs, must be from candidate_list
    }
```

**Return Format Descriptions**:

**Review Generation Task Return Format**:
- `stars`: Integer type, range 1-5, representing user's star rating for the item
- `review`: String type, user's review text content for the item

**Recommendation Task Return Format**:
- `item_list`: List type, containing item IDs ranked by recommendation priority
  - Each element in the list must be an item ID from `candidate_list`
  - List length should equal the length of `candidate_list`
  - Order indicates recommendation priority (first item has highest priority)

### Complete Agent Example

Here's a complete example showing how to implement a basic agent with detailed InteractionTool usage and best practices:

```python
from agentsociety.agent import IndividualAgentBase
from typing import Any

class BehaviorModelingAgent(IndividualAgentBase):
    """
    A complete example agent for the Behavior Modeling benchmark.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def forward(self, task_context: dict[str, Any]):
        # Extract task information
        target = task_context["target"]
        user_id = task_context["user_id"]
        
        # Get interaction tool
        user_item_review_tool = self.toolbox.get_tool_object("uir")
        
        if target == "review_writing":
            item_id = task_context["item_id"]
            
            # Get user information
            user_info = user_item_review_tool.get_user(user_id)
            
            # Get item information
            item_info = user_item_review_tool.get_item(item_id)
            
            # Get user's historical reviews (for learning user preferences and writing style)
            user_reviews = user_item_review_tool.get_reviews(user_id=user_id)
            
            # Get item-related reviews (for understanding item characteristics)
            item_reviews = user_item_review_tool.get_reviews(item_id=item_id)
            
            # Build prompt with user history and item information
            user_history_text = ""
            if user_reviews:
                user_history_text = f"User's review style: {[r['review'][:100] + '...' for r in user_reviews[:3]]}"
            
            item_info_text = ""
            if item_info:
                item_info_text = f"Item info: {item_info.get('item_name', '')} - {item_info.get('category', '')}"
            
            # Generate review using LLM
            messages = [
                {"role": "system", "content": "You are a user writing a review. Generate appropriate review based on user's historical preferences and item characteristics."},
                {"role": "user", "content": f"""
                User ID: {user_id}
                {user_history_text}
                
                Target Item: {item_id}
                {item_info_text}
                
                Please generate a review for this item, including 1-5 star rating and review text.
                Return format: Rating: [1-5], Review: [review text]
                """}
            ]
            response = await self.llm.atext_request(messages)
            
            # Parse response (simplified here, actual implementation should be more complex)
            try:
                # Simple parsing example
                if "Rating:" in response and "Review:" in response:
                    stars_text = response.split("Rating:")[1].split(",")[0].strip()
                    review_text = response.split("Review:")[1].strip()
                    stars = int(stars_text)
                    return {"stars": stars, "review": review_text}
                else:
                    # Default return
                    return {"stars": 4, "review": response}
            except:
                return {"stars": 4, "review": response}
            
        elif target == "recommendation":
            candidate_list = task_context["candidate_list"]
            candidate_category = task_context["candidate_category"]
            
            # Get user information
            user_info = user_item_review_tool.get_user(user_id)
            
            # Get user's historical reviews (for analyzing user preferences)
            user_reviews = user_item_review_tool.get_reviews(user_id=user_id)
            
            # Get candidate item information
            candidate_items_info = []
            for item_id in candidate_list:
                item_info = user_item_review_tool.get_item(item_id)
                if item_info:
                    candidate_items_info.append(item_info)
            
            # Analyze user preferences
            user_preferences = ""
            if user_reviews:
                avg_rating = sum(r['stars'] for r in user_reviews) / len(user_reviews)
                user_preferences = f"User average rating: {avg_rating:.1f} stars, historical reviews: {len(user_reviews)}"
            
            # Build candidate items description
            candidates_text = ""
            for item_info in candidate_items_info:
                candidates_text += f"- {item_info.get('item_name', '')} (ID: {item_info.get('item_id', '')})\n"
            
            # Generate recommendations using LLM
            messages = [
                {"role": "system", "content": "You are a recommendation expert. Recommend the most suitable items based on user preferences."},
                {"role": "user", "content": f"""
                User ID: {user_id}
                {user_preferences}
                
                Candidate Item Category: {candidate_category}
                Candidate Items:
                {candidates_text}
                
                Please rank the candidate items by recommendation priority based on user preferences.
                Return format: item_id1, item_id2, item_id3, ...
                """}
            ]
            response = await self.llm.atext_request(messages)
            
            # Parse response and ensure all candidate items are included
            try:
                # Simple parsing example
                recommended_items = [item.strip() for item in response.split(",")]
                # Ensure all candidate items are in the result
                final_list = []
                for item in recommended_items:
                    if item in candidate_list and item not in final_list:
                        final_list.append(item)
                # Add unrecommended candidate items
                for item in candidate_list:
                    if item not in final_list:
                        final_list.append(item)
                return {"item_list": final_list}
            except:
                return {"item_list": candidate_list}
```

## Evaluation Process

### Test Mode
1. **Data Preparation**: Load test dataset containing user behavior history and ground truth labels
2. **Task Execution**: Agent processes recommendation and review generation tasks
3. **Result Evaluation**: Calculate various evaluation metrics
4. **Score Calculation**: Combine recommendation accuracy and review quality for final score

### Inference Mode
1. **Inference Execution**: Agent performs reasoning based on given context
2. **Result Validation**: Compare with ground truth labels
3. **Metric Collection**: Collecting results for evaluation to a .pkl file
4. **Result Output**: After running in inference mode, the output result file (e.g., .pkl) is the final result for submission/scoring

## Evaluation Metrics

### Recommendation Metrics

#### Hit Rate@N
Calculate the proportion of samples where the ground truth item appears in the top-N recommendations:

**Formula**:
```
HR@N = (Number of samples with ground truth item in top-N recommendations) / (Total number of samples)
```

**Specific Metrics**:
- **Top-1 Hit Rate**: HR@1, hit rate for the first item in recommendation list
- **Top-3 Hit Rate**: HR@3, hit rate for top three items in recommendation list
- **Top-5 Hit Rate**: HR@5, hit rate for top five items in recommendation list
- **Average Hit Rate**: (HR@1 + HR@3 + HR@5) / 3

### Simulation Metrics

#### 1. Preference Estimation Accuracy
Based on star rating accuracy:

**Formula**:
```
Preference Estimation = 1 - (Average Star Rating Error / 5)
```

where Star Rating Error = |Predicted Rating - Ground Truth Rating| / 5

#### 2. Review Generation Quality
Comprehensive evaluation considering sentiment, emotion, and topic similarity:

**Formula**:
```
Review Generation = 1 - (Sentiment Error × 0.25 + Emotion Error × 0.25 + Topic Error × 0.5)
```

**Sub-metrics**:
- **Sentiment Error**: Calculate sentiment polarity difference between generated and ground truth reviews using VADER sentiment analyzer
- **Emotion Error**: Calculate emotion distribution difference using RoBERTa emotion classifier
- **Topic Error**: Calculate semantic similarity using SentenceTransformer

#### 3. Overall Quality
**Formula**:
```
Overall Quality = (Preference Estimation + Review Generation) / 2
```

### Final Score
**Formula**:
```
Final Score = ((Average Hit Rate + Overall Quality) / 2) × 100
```

## Dataset Information

- **Dataset Repository**: https://huggingface.co/datasets/tsinghua-fib-lab/behavior-modeling-benchmark
- **Branch**: main
- **Supported Modes**: test, inference

## Dependencies

```python
numpy >= 1.26.4
scipy >= 1.13.0
nltk
transformers
sentence-transformers
torch
```

## Usage Example

```shell
# Test mode: evaluate agent performance
asbench run --config <YOUR-CONFIG>.yml --agent <YOUR-AGENT.py> --mode test BehaviorModeling

# Inference mode: generate inference results
asbench run --config <YOUR-CONFIG>.yml --agent <YOUR-AGENT.py> --mode inference BehaviorModeling
# After running in inference mode, the output result file (e.g., .pkl) in the specified directory is the final result for submission/scoring
```

**Configuration File Example**:
```yaml
# config.yml
llm:
  provider: openai
  model: gpt-4
  api_key: your-api-key

# Other configuration items...
```

## Version Information

- **Version**: 1.0.0
- **Author**: AgentSociety Team
- **Tags**: behavior-modeling, recommendation, review-writing

## Related Files

- `template_agent.py`: Agent template file with basic structure and comment instructions
- `interactiontool.py`: InteractionTool implementation file providing data access functionality
- `README.md`: English documentation
- `README_zh.md`: Chinese documentation 