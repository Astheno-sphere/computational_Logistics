from typing import Optional

import numpy as np
from pydantic import Field

from ..agent import AgentParams, AgentToolbox, FirmAgentBase, Block
from ..logger import get_logger
from ..memory import Memory

__all__ = ["FirmAgent"]


class FirmAgentConfig(AgentParams):
    """Configuration for FirmAgent."""

    time_diff: int = Field(
        default=30 * 24 * 60 * 60,
        description="Time difference between each forward, day * hour * minute * second",
    )
    max_price_inflation: float = Field(
        default=0.05, description="Maximum price inflation rate"
    )
    max_wage_inflation: float = Field(
        default=0.05, description="Maximum wage inflation rate"
    )


class FirmAgent(FirmAgentBase):
    """Agent representing a firm in an economic simulation.

    Manages economic activities including price adjustments, wage policies,
    inventory control, and employee skill development.
    Inherits from InstitutionAgent and extends its economic behaviors.
    """

    ParamsType = FirmAgentConfig
    description: str = """
The firm agent that manages economic activities including price adjustments, wage policies, inventory control, and employee skill development.
    """

    def __init__(
        self,
        id: int,
        name: str,
        toolbox: AgentToolbox,
        memory: Memory,
        agent_params: Optional[FirmAgentConfig] = None,
        blocks: Optional[list[Block]] = None,
    ) -> None:
        """Initialize a FirmAgent with essential components for economic simulation.

        - **Args**:
            - `name` (`str`): The name or identifier of the agent.
            - `toolbox` (`AgentToolbox`): The toolbox of the agent.
            - `memory` (`Memory`): The memory of the agent.

        - **Description**:
            - Initializes the firm agent with the provided parameters and sets up necessary internal states.
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
        self.forward_times = 0

    async def reset(self):
        """Reset the FirmAgent."""
        pass

    async def month_trigger(self):
        """Check if monthly adjustment should be triggered.

        Compares current simulation time with last trigger time.
        Returns:
            True if time_diff has passed since last trigger, False otherwise
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
        """Execute monthly economic adjustments.

        Performs:
        - Employee skill adjustments based on market conditions
        - Price adjustments based on inventory/demand balance
        - Economic metrics reset (demand/sales tracking)
        """
        if await self.month_trigger():
            firm_id = self.id
            get_logger().debug(f"Agent {self.id}: Start main workflow - firm forward")
            employees, total_demand, goods_consumption, inventory, skills, price = (
                await self.environment.economy_client.get(
                    firm_id,
                    ["employees", "demand", "sales", "inventory", "skill", "price"],
                )
            )
            last_inventory = goods_consumption + inventory
            max_change_rate = (total_demand - last_inventory) / (
                max(total_demand, last_inventory) + 1e-8
            )
            skills = np.array(skills)
            skill_change_ratio = np.random.uniform(
                0, max_change_rate * self.params.max_wage_inflation
            )
            await self.environment.economy_client.update(
                employees,
                "skill",
                list(np.maximum(skills * (1 + skill_change_ratio), 1)),
            )
            await self.environment.economy_client.update(
                firm_id,
                "price",
                max(
                    price
                    * (
                        1
                        + np.random.uniform(
                            0, max_change_rate * self.params.max_price_inflation
                        )
                    ),
                    1,
                ),
            )
            await self.environment.economy_client.update(firm_id, "demand", 0)
            await self.environment.economy_client.update(firm_id, "sales", 0)
            get_logger().debug(
                f"Agent {self.id}: Finished main workflow - firm forward"
            )
