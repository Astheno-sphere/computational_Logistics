import logging

import networkx as nx


def generate_networks(
    agent_count: int,
    public_m: int,
    private_m: int,
    public_seed: int = 42,
    private_seed: int = 123,
) -> tuple[nx.Graph, nx.Graph]:
    """
    Generate public and private social networks (Barabási-Albert model).
    If files already exist, they won't be regenerated.
    Args:
        agent_count(int): Number of agents in the network.
        public_m(int): Average degree of the public network.
        private_m(int): Average degree of the private network.
        public_seed(int): Seed for the public network.
        private_seed(int): Seed for the private network.
    """

    logging.info(f"Starting to generate networks (nodes: {agent_count})...")
    # Use different random seeds to ensure the two networks have different structures
    try:
        public_network = nx.barabasi_albert_graph(
            agent_count, public_m, seed=public_seed
        )
        logging.info(
            f"Public network generation completed (BA, n={agent_count}, m={public_m})."
        )

        private_network = nx.barabasi_albert_graph(
            agent_count, private_m, seed=private_seed
        )
        logging.info(
            f"Private network generation completed (BA, n={agent_count}, m={private_m})."
        )
        return public_network, private_network

    except Exception as e:
        logging.error(f"Error generating or saving networks: {e}", exc_info=True)
        raise e from None
