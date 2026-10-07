from typing import Optional

import numpy as np
from pydantic import Field

from ..agent import AgentParams, AgentToolbox, NBSAgentBase
from ..logger import get_logger
from ..memory import Memory
from ..agent.block import Block

__all__ = ["NBSAgent"]


class NBSAgentConfig(AgentParams):
    """Configuration for NBSAgent."""

    time_diff: int = Field(
        default=30 * 24 * 60 * 60,
        description="Time difference between each forward, day * hour * minute * second",
    )
    num_labor_hours: int = Field(
        default=168, description="Number of labor hours per week"
    )
    productivity_per_labor: float = Field(
        default=1, description="Productivity per labor hour"
    )


class NBSAgent(NBSAgentBase):
    """National Bureau of Statistics Agent simulating economic data collection and analysis.

    Inherits from InstitutionAgent to manage economic indicators and interactions with other
    agents in a simulated environment. Handles monthly economic metrics calculations including
    GDP, labor statistics, prices, and citizen welfare indicators.
    """

    ParamsType = NBSAgentConfig
    description: str = """
The National Bureau of Statistics Agent simulating economic data collection and analysis.
    """

    def __init__(
        self,
        id: int,
        name: str,
        toolbox: AgentToolbox,
        memory: Memory,
        agent_params: Optional[NBSAgentConfig] = None,
        blocks: Optional[list[Block]] = None,
    ) -> None:
        """Initialize NBSAgent with dependencies and configuration.

        - **Args**:
            - `name` (`str`): The name or identifier of the agent.
            - `toolbox` (`AgentToolbox`): The toolbox of the agent.
            - `memory` (`Memory`): The memory of the agent.

        - **Description**:
            - Initializes the NBSAgent with the provided parameters and sets up necessary internal states.
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
        """Reset the NBSAgent."""
        pass

    async def month_trigger(self):
        """Check if a monthly cycle should be triggered based on simulation time.

        Returns:
            True if monthly interval has passed since last trigger, False otherwise
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
        """Execute monthly economic data collection and update cycle.

        Performs:
        1. Real GDP calculation
        2. Labor statistics aggregation
        3. Price level monitoring
        4. Citizen welfare metrics collection
        5. Economic indicator updates
        """
        if await self.month_trigger() or self.gather_flag:
            if not self.gather_flag:
                get_logger().debug(f"Agent {self.id}: Start main workflow - nbs forward - gather phase")
                citizen_ids = await self.memory.status.get("citizen_ids")
                self.register_gather_query("work_propensity", citizen_ids, keep_id=False)
                self.register_gather_query("depression", citizen_ids, keep_id=False)
                self.gather_flag = True
            else:
                get_logger().debug(f"Agent {self.id}: Start main workflow - nbs forward - process phase")
                try:
                    t_now = str(self.environment.get_tick())
                    nbs_id = self.id
                    # real gdp
                    await self.environment.economy_client.calculate_real_gdp(nbs_id)
                    real_gdp = await self.environment.economy_client.get(nbs_id, "real_gdp")
                    if len(real_gdp) > 0:
                        latest_time = max(real_gdp.keys())
                        real_gdp = real_gdp[latest_time]
                        await self.memory.status.update("real_gdp_metric", real_gdp)
                    citizens_ids = await self.memory.status.get("citizen_ids")
                    work_propensity = self.get_gather_results("work_propensity")
                    depression = self.get_gather_results("depression")
                    if work_propensity is None or depression is None:
                        return
                    
                    # working hours
                    if sum(work_propensity) == 0.0:
                        working_hours = 0.0
                    else:
                        working_hours = np.mean(work_propensity) * self.params.num_labor_hours # type: ignore
                    await self.environment.economy_client.update(
                        nbs_id, "working_hours", {t_now: working_hours}, mode="merge"
                    )
                    await self.memory.status.update("working_hours_metric", working_hours)
                    
                    # price
                    firms_id = await self.environment.economy_client.get_firm_ids()
                    prices = await self.environment.economy_client.get(firms_id, "price")
                    price = float(np.mean(prices))
                    await self.environment.economy_client.update(
                        nbs_id, "prices", {t_now: price}, mode="merge"
                    )
                    await self.memory.status.update("price_metric", price)
                    
                    # depression
                    if sum(depression) == 0.0:
                        depression = 0.0
                    else:
                        depression = np.mean(depression) # type: ignore
                    await self.environment.economy_client.update(
                        nbs_id, "depression", {t_now: depression}, mode="merge"
                    )
                    await self.memory.status.update("depression_metric", depression)
                    
                    # consumption currency
                    consumption_currency = await self.environment.economy_client.get(
                        citizens_ids, "consumption"
                    )
                    if sum(consumption_currency) == 0.0:
                        consumption_currency = 0.0
                    else:
                        consumption_currency = np.mean(consumption_currency)
                    await self.environment.economy_client.update(
                        nbs_id,
                        "consumption_currency",
                        {t_now: consumption_currency},
                        mode="merge",
                    )
                    await self.memory.status.update("consumption_currency_metric", consumption_currency)
                    
                    # income currency
                    income_currency = await self.environment.economy_client.get(
                        citizens_ids, "income"
                    )
                    if sum(income_currency) == 0.0:
                        income_currency = 0.0
                    else:
                        income_currency = np.mean(income_currency)
                    await self.environment.economy_client.update(
                        nbs_id, "income_currency", {t_now: income_currency}, mode="merge"
                    )
                    await self.memory.status.update("income_currency_metric", income_currency)
                    
                    get_logger().debug(f"Agent {self.id}: Finished main workflow - nbs forward")
                    self.forward_times += 1
                    await self.memory.status.update("forward_times", self.forward_times)
                except Exception as e:
                    get_logger().error(f"Agent {self.id}: Error in nbs forward: {e}")
                    return
                finally:
                    self.gather_flag = False
