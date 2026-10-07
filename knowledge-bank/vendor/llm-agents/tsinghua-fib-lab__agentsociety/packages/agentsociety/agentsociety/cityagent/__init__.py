import copy
from typing import Union, cast

from ..agent.distribution import Distribution, DistributionConfig
from ..cityagent.blocks.economy_block import EconomyBlock, EconomyBlockParams
from ..cityagent.blocks.mobility_block import MobilityBlock, MobilityBlockParams
from ..cityagent.blocks.other_block import OtherBlock, OtherBlockParams
from ..cityagent.blocks.social_block import SocialBlock, SocialBlockParams
from ..configs import InstitutionAgentClass, AgentConfig, Config
from .bankagent import BankAgent
from .firmagent import FirmAgent
from .governmentagent import GovernmentAgent
from .initial import bind_agent_info
from .memory_config import (
    DEFAULT_DISTRIBUTIONS,
    memory_config_bank,
    memory_config_firm,
    memory_config_government,
    memory_config_nbs,
    memory_config_societyagent,
)
from .nbsagent import NBSAgent
from .societyagent import SocietyAgent
from .sharing_params import (
    SocietyAgentConfig,
    SocietyAgentBlockOutput,
    SocietyAgentContext,
)

__all__ = [
    "default",
    "SocietyAgent",
    "FirmAgent",
    "BankAgent",
    "NBSAgent",
    "GovernmentAgent",
    "memory_config_societyagent",
    "memory_config_government",
    "memory_config_firm",
    "memory_config_bank",
    "memory_config_nbs",
    "SocietyAgentConfig",
    "SocietyAgentBlockOutput",
    "SocietyAgentContext",
]


BLOCK_MAPPING = {
    "MobilityBlock": MobilityBlock,
    "EconomyBlock": EconomyBlock,
    "SocialBlock": SocialBlock,
    "OtherBlock": OtherBlock,
}


def _fill_in_agent_class_and_memory_config(self: AgentConfig):
    if isinstance(self.agent_class, str):
        if self.agent_class == "citizen":
            self.agent_class = SocietyAgent
            if self.agent_params is not None:
                self.agent_params = SocietyAgent.ParamsType.model_validate(self.agent_params)
            if self.memory_config_func is None:
                self.memory_config_func = copy.deepcopy(memory_config_societyagent)
            distributions = cast(
                dict[str, Union[Distribution, DistributionConfig]],
                DEFAULT_DISTRIBUTIONS,
            )
            if self.memory_distributions is not None:
                distributions.update(self.memory_distributions)
            self.memory_distributions = copy.deepcopy(distributions)
            if self.blocks is None:
                self.blocks = {
                    MobilityBlock: MobilityBlockParams(),
                    EconomyBlock: EconomyBlockParams(),
                    SocialBlock: SocialBlockParams(),
                    OtherBlock: OtherBlockParams(),
                }
            else:
                blocks = {}
                for key, value in self.blocks.items():
                    if isinstance(key, str) and key in BLOCK_MAPPING:
                        blocks[BLOCK_MAPPING[key]] = BLOCK_MAPPING[key].ParamsType(
                            **value
                        )
                    else:
                        blocks[key] = value
                self.blocks = blocks
        elif self.agent_class == InstitutionAgentClass.FIRM.value:
            self.agent_class = FirmAgent
            if self.agent_params is not None:
                self.agent_params = FirmAgent.ParamsType(**self.agent_params)
            if self.memory_config_func is None:
                self.memory_config_func = memory_config_firm
        elif self.agent_class == InstitutionAgentClass.GOVERNMENT.value:
            self.agent_class = GovernmentAgent
            if self.agent_params is not None:
                self.agent_params = GovernmentAgent.ParamsType(**self.agent_params)
            if self.memory_config_func is None:
                self.memory_config_func = memory_config_government
        elif self.agent_class == InstitutionAgentClass.BANK.value:
            self.agent_class = BankAgent
            if self.agent_params is not None:
                self.agent_params = BankAgent.ParamsType(**self.agent_params)
            if self.memory_config_func is None:
                self.memory_config_func = memory_config_bank
        elif self.agent_class == InstitutionAgentClass.NBS.value:
            self.agent_class = NBSAgent
            if self.agent_params is not None:
                self.agent_params = NBSAgent.ParamsType(**self.agent_params)
            if self.memory_config_func is None:
                self.memory_config_func = memory_config_nbs
        else:
            pass
            # raise ValueError(f"Invalid agent class: {self.agent_class}")
    return self


def default(config: Config) -> Config:
    """
    Use the default values in cityagent to fill in the config.
    """
    # =====================
    # fill orgnizations
    # =====================
    if any(citizen_config.agent_class == "citizen" for citizen_config in config.agents.citizens):
        if len(config.agents.firms) == 0:
            config.agents.firms = [
                AgentConfig(
                    agent_class="firm",
                    number=1,
                )
            ]
        if len(config.agents.governments) == 0:
            config.agents.governments = [
                AgentConfig(
                    agent_class="government",
                    number=1,
                )
            ]
        if len(config.agents.banks) == 0:
            config.agents.banks = [
                AgentConfig(
                    agent_class="bank",
                    number=1,
                )
            ]
        if len(config.agents.nbs) == 0:
            config.agents.nbs = [
                AgentConfig(
                    agent_class="nbs",
                    number=1,
                )
            ]
    # =====================
    # agent config
    # =====================
    config.agents.citizens = [
        _fill_in_agent_class_and_memory_config(agent_config)
        for agent_config in config.agents.citizens
    ]
    config.agents.firms = [
        _fill_in_agent_class_and_memory_config(agent_config)
        for agent_config in config.agents.firms
    ]
    config.agents.governments = [
        _fill_in_agent_class_and_memory_config(agent_config)
        for agent_config in config.agents.governments
    ]
    config.agents.banks = [
        _fill_in_agent_class_and_memory_config(agent_config)
        for agent_config in config.agents.banks
    ]
    config.agents.nbs = [
        _fill_in_agent_class_and_memory_config(agent_config)
        for agent_config in config.agents.nbs
    ]
    if config.agents.supervisor is not None:
        config.agents.supervisor = _fill_in_agent_class_and_memory_config(
            config.agents.supervisor
        )
    # =====================
    # init functions
    # =====================
    if len(config.agents.init_funcs) == 0:
        config.agents.init_funcs = [
            bind_agent_info,
        ]
    return config
