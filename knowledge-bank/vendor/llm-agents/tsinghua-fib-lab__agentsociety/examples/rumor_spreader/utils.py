import random

import networkx as nx
import numpy as np

from agentsociety.cityagent.societyagent import SocietyAgent
from agentsociety.logger import get_logger
from agentsociety.simulation import AgentSociety

__all__ = ["initialize_social_network_with_graphs"]


async def initialize_social_network_with_graphs(
    networks: tuple[nx.Graph, nx.Graph], simulation: AgentSociety
):
    """
    Initializes the social network between agents.

    - **Description**:
        - Creates friendship relationships between agents
        - Assigns relationship types (family, colleague, friend)
        - Sets relationship strengths based on type
        - Initializes chat histories and interaction records

    - **Returns**:
        - None
    """
    get_logger().info("Initializing social network...")

    public_network, private_network = networks

    # Define possible relationship types
    relation_types = ["family", "colleague", "friend"]

    # Get all agent IDs
    citizen_ids = await simulation.filter(types=(SocietyAgent,))

    assert (
        len(private_network.nodes) == len(public_network.nodes) == len(citizen_ids)
    ), "The number of nodes in the private and public networks must be equal to the number of citizen IDs"
    random.seed(len(citizen_ids))
    for idx, agent_id in enumerate(citizen_ids):
        private_friends = list(private_network.neighbors(idx))
        public_friends = list(public_network.neighbors(idx))

        # Initialize friend relationships
        await simulation.update([agent_id], "friends", private_friends)
        await simulation.update([agent_id], "public_friends", public_friends)

        # Initialize relationship types and strengths with each friend
        relationships = {}
        relation_type_map = {}

        for friend_id in private_friends + public_friends:
            # Randomly select relationship type
            relation_type = random.choice(relation_types)
            # Set initial relationship strength range based on type
            if relation_type == "family":
                strength = random.randint(60, 90)  # Higher strength for family
            elif relation_type == "colleague":
                strength = random.randint(40, 70)  # Medium strength for colleagues
            else:  # friend
                strength = random.randint(30, 80)  # Wide range for friends

            relationships[friend_id] = strength
            relation_type_map[friend_id] = relation_type

        # Update relationship strengths and types
        await simulation.update([agent_id], "relationships", relationships)
        await simulation.update([agent_id], "relation_types", relation_type_map)

        # Initialize empty chat histories and interaction records
        await simulation.update(
            [agent_id],
            "chat_histories",
            {friend_id: "" for friend_id in private_friends + public_friends},
        )
        await simulation.update(
            [agent_id],
            "interactions",
            {friend_id: [] for friend_id in private_friends + public_friends},
        )
