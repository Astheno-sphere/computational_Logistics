from typing import Optional

import numpy as np
from pydantic import Field

from ..agent import AgentParams, AgentToolbox, GovernmentAgentBase, Block
from ..logger import get_logger
from ..memory import Memory

__all__ = ["GovernmentAgent"]


class GovernmentAgentConfig(AgentParams):
    """Configuration for GovernmentAgent."""

    time_diff: int = Field(
        default=30 * 24 * 60 * 60,
        description="Time difference between each forward, day * hour * minute * second",
    )


class GovernmentAgent(GovernmentAgentBase):
    """A government institution agent that handles periodic economic operations such as tax collection."""

    ParamsType = GovernmentAgentConfig
    description: str = """
A government institution agent that handles periodic economic operations such as tax collection.
    """

    def __init__(
        self,
        id: int,
        name: str,
        toolbox: AgentToolbox,
        memory: Memory,
        agent_params: Optional[GovernmentAgentConfig] = None,
        blocks: Optional[list[Block]] = None,
    ) -> None:
        """
        Initialize the GovernmentAgent.

        Args:
            - `name` (`str`): The name or identifier of the agent.
            - `toolbox` (`AgentToolbox`): The toolbox of the agent.
            - `memory` (`Memory`): The memory of the agent.

        - **Description**:
            - Initializes the GovernmentAgent with the provided parameters and sets up necessary internal states.
        """
        super().__init__(
            id=id,
            name=name,
            toolbox=toolbox,
            memory=memory,
            agent_params=agent_params,
            blocks=blocks,
        )
        self.initailzed = False
        self.last_time_trigger = None
        self.gather_flag = False
        self.forward_times = 0

    async def reset(self):
        """Reset the GovernmentAgent."""
        pass

    async def month_trigger(self):
        """
        Check if the monthly tax cycle should be triggered based on elapsed time.

        Returns:
            True if the time difference since last trigger exceeds `time_diff`, False otherwise.
        """
        now_tick = self.environment.get_tick()
        if self.last_time_trigger is None:
            self.last_time_trigger = now_tick
            return False
        if now_tick - self.last_time_trigger >= self.params.time_diff:
            self.last_time_trigger = now_tick
            return True
        return False

    async def forward(self):
        """Execute the government's periodic tax collection and notification cycle."""
        if (await self.month_trigger()) or self.gather_flag:
            if not self.gather_flag:
                get_logger().debug(
                    f"Agent {self.id}: Start main workflow - government forward - gather phase"
                )
                citizen_ids = await self.memory.status.get("citizen_ids")
                self.register_gather_query("forward", citizen_ids, keep_id=False)
                self.register_gather_query("income_currency", citizen_ids, keep_id=False)
                self.gather_flag = True
            else:
                get_logger().debug(
                    f"Agent {self.id}: Start main workflow - government forward - process phase"
                )
                try:
                    citizen_ids = await self.memory.status.get("citizen_ids")
                    agents_forward = self.get_gather_results("forward")
                    incomes = self.get_gather_results("income_currency")
                    if incomes is None or agents_forward is None:
                        return
                    
                    if not np.all(np.array(agents_forward) > self.forward_times):
                        return
                    _, post_tax_incomes = (
                        await self.environment.economy_client.calculate_taxes_due(
                            self.id, citizen_ids, incomes, enable_redistribution=False # type: ignore
                        )
                    )
                    for citizen_id, income, post_tax_income in zip(
                        citizen_ids, incomes, post_tax_incomes
                    ):
                        tax_paid = income - post_tax_income
                        await self.send_message_to_agent(
                            citizen_id, f"tax_paid@{tax_paid}", "economy"
                        )
                    self.forward_times += 1
                    for citizen_id in citizen_ids:
                        await self.send_message_to_agent(
                            citizen_id, f"government_forward@{self.forward_times}", "economy"
                        )
                    get_logger().debug(
                        f"Agent {self.id}: Finished main workflow - government forward"
                    )
                except Exception as e:
                    get_logger().error(
                        f"Agent {self.id}: Error in government forward: {e}"
                    )
                    return
                finally:
                    self.gather_flag = False
