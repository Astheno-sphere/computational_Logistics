"""
Agent implementations for AgentSociety v2.

Available agents:
"""

from agentsociety2.contrib.agent.commons_tragedy_agent import CommonsTragedyAgent
from agentsociety2.contrib.agent.prisoners_dilemma_agent import PrisonersDilemmaAgent
from agentsociety2.contrib.agent.public_goods_agent import PublicGoodsAgent
from agentsociety2.contrib.agent.specialist_agent import SpecialistAgent
from agentsociety2.contrib.agent.trust_game_agent import TrustGameAgent
from agentsociety2.contrib.agent.volunteer_dilemma_agent import VolunteerDilemmaAgent

__all__ = [
    "CommonsTragedyAgent",
    "PrisonersDilemmaAgent",
    "PublicGoodsAgent",
    "SpecialistAgent",
    "TrustGameAgent",
    "VolunteerDilemmaAgent",
]
