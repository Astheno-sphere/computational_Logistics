from agentsociety.agent import IndividualAgentBase
from typing import Any

class BehaviorModelingAgent(IndividualAgentBase):
    """
    A template agent for the Behavior Modeling benchmark.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def forward(self, task_context: dict[str, Any]):
        # ============================== Task Context ==============================
        # target: the target of the task, can be "review_writing" or "recommendation"
        # user_id: the user id for this specifictask
        # candidate_category: the item category if the target is "recommendation", including "book", "business", "product"
        # candidate_list: a list of items if the target is "recommendation"
        # item_id: the item id for this specific task if the target is "review_writing"
        # ============================== Task Context ==============================

        # ============================== Get Interaction Tool ==============================
        # user_item_review_tool: InteractionTool = self.toolbox.get_tool("uir") # type: ignore
        # ============================== Get Interaction Tool ==============================

        # ============================== Basic Usage of Interaction Tool ==============================
        # get user related information
        # user_info = user_item_review_tool.get_user(task_context["user_id"])

        # get item related information
        # item_info = user_item_review_tool.get_item(task_context["item_id"])

        # get the reviews related to the item
        # reviews_related_to_item = user_item_review_tool.get_reviews(item_id=item_id)
        # get the reviews related to the user
        # reviews_related_to_user = user_item_review_tool.get_reviews(user_id=user_id)
        # get the reviews related to the review
        # reviews_related_to_review = user_item_review_tool.get_reviews(review_id=review_id)
        # ============================== Basic Usage of Interaction Tool ==============================

        # ============================== LLM Usage ==============================
        # 1. Organize your prompt
        # messages  = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": "What is the capital of France?"}]
        # 2. Call the LLM
        # response = await self.llm.atext_request(messages)
        # 3. Parse the LLM response as you want
        # ============================== LLM Usage ==============================

        # ============================== Return Format ==============================
        # get the task target
        target = task_context["target"]
        if target == "review_writing":
            return {"stars": 3, "review": "This is a review"}
        elif target == "recommendation":
            return {"item_list": task_context["candidate_list"]}
        # ============================== Return Format ==============================