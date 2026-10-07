from typing import Optional

import numpy as np
from pydantic import Field

from ..agent import AgentParams, AgentToolbox, BankAgentBase, Block
from ..logger import get_logger
from ..memory import Memory

__all__ = ["BankAgent"]


def calculate_inflation(prices):
    """
    Calculate annual inflation rates based on historical price data.

    Args:
        prices (list/np.array): A list of monthly price values

    Returns:
        list: Annual inflation rates in percentages. Returns empty list if
              insufficient data (less than 2 full years of data).

    Logic:
        1. Truncates input to full years of data (multiples of 12 months)
        2. Reshapes monthly data into yearly groups
        3. Computes average price per year
        4. Calculates year-over-year inflation rates
    """
    # Make sure the length of price data is a multiple of 12
    length = len(prices)
    months_in_year = 12
    full_years = length // months_in_year  # Calculate number of complete years

    # Remaining data not used in calculation
    prices = prices[: full_years * months_in_year]

    # Group by year, calculate average price for each year
    annual_avg_prices = np.mean(np.reshape(prices, (-1, months_in_year)), axis=1)

    # Calculate annual inflation rates
    inflation_rates = []
    for i in range(1, full_years):
        inflation_rate = (
            (annual_avg_prices[i] - annual_avg_prices[i - 1]) / annual_avg_prices[i - 1]
        ) * 100
        inflation_rates.append(inflation_rate)

    return inflation_rates


class BankAgentConfig(AgentParams):
    """Configuration for BankAgent."""

    time_diff: int = Field(
        default=30 * 24 * 60 * 60,
        description="Time difference between each forward, day * hour * minute * second",
    )


class BankAgent(BankAgentBase):
    """
    A central banking agent that manages monetary policy in the simulation.

    Key Responsibilities:
    1. Adjusts interest rates based on inflation trends (Taylor Rule implementation)
    2. Applies interest to citizens' savings periodically
    3. Interacts with economic simulation components via EconomyClient

    Configurable Parameters:
    - time_diff: Frequency of policy updates in simulation seconds (default: 30 days)
    """

    ParamsType = BankAgentConfig
    description: str = """
The central banking agent that manages monetary policy in the simulation.
    """

    def __init__(
        self,
        id: int,
        name: str,
        toolbox: AgentToolbox,
        memory: Memory,
        agent_params: Optional[BankAgentConfig] = None,
        blocks: Optional[list[Block]] = None,
    ) -> None:
        """
        Initialize the banking agent.

        - **Args**:
            - `name` (`str`): The name or identifier of the agent.
            - `toolbox` (`AgentToolbox`): The toolbox of the agent.
            - `memory` (`Memory`): The memory of the agent.

        - **Description**:
            - Initializes the banking agent with the provided parameters and sets up necessary internal states.
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
        """Reset the BankAgent."""
        pass

    async def month_trigger(self) -> bool:
        """
        Check if monthly policy update should be triggered.

        Returns:
            bool: True if required time interval has passed since last update

        Note:
            Uses simulation time rather than real-world time
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
        """
        Execute monthly policy update cycle.

        Performs two main actions:
        1. Applies interest to citizens' savings
        2. Adjusts interest rate based on inflation (Taylor Rule)
        """
        if await self.month_trigger():
            bank_id = self.id
            get_logger().debug(f"Agent {self.id}: Start main workflow - bank forward")
            interest_rate, citizens = await self.environment.economy_client.get(
                bank_id,
                ["interest_rate", "citizens"],
            )
            currencies = await self.environment.economy_client.get(citizens, "currency")
            # update currency with interest
            for citizen, wealth in zip(citizens, currencies):
                await self.environment.economy_client.delta_update_agents(
                    citizen, delta_currency=interest_rate * wealth
                )
            nbs_id = await self.environment.economy_client.get_nbs_ids()
            nbs_id = nbs_id[0]
            prices = await self.environment.economy_client.get(nbs_id, "prices")
            prices = list(prices.values())
            inflations = calculate_inflation(prices)
            natural_interest_rate = 0.01
            target_inflation = 0.02
            if len(inflations) > 0:
                # natural_unemployment_rate = 0.04
                inflation_coeff = 0.5
                tao = 1
                avg_inflation = np.mean(inflations[-tao:])
                interest_rate = (
                    natural_interest_rate
                    + target_inflation
                    + inflation_coeff * (avg_inflation - target_inflation)
                )
            else:
                interest_rate = natural_interest_rate + target_inflation
            await self.environment.economy_client.update(
                bank_id, "interest_rate", interest_rate
            )
            get_logger().debug(
                f"Agent {self.id}: Finished main workflow - bank forward"
            )
