# Design Guide

The documentation is for the developers who want to understand the code and contribute to the project.

## Directory Structure

The first part is the clients used for the simulation, including:
- `llm`: A LLM adapter for different LLM providers using openai api. It supports round-robin for multiple LLM providers, token consumption tracking, and error handling. Embedding is also supported.
- `message`: The agent message system implemented by ray. The supervisor is implemented by `MessageInterceptor`. The `MessageInterceptor` is a ray actor that intercepts the message and checks if it violates the rules (by LLM). Users can implement their own `MessageBlock` to block certain messages and also implement their own `MessageBlockListener` to listen to the blocked message and take actions.
- `metrics`: A metric recorder implemented by database.
- `storage`: Logging and saving implemented by `sqlite` or `postgresql`.
- `environment`: The key of the agentsociety, including the mobility simulator client and the economic simulator client. The map is also implemented in this part.

For all clients, we initialize them with pydantic config models, their `__init__` method and their async `init` method (if needed). And we provide a `close` method for them to release resources.

The second part is the agent simulation related code, including:
- `agent`: The base class of the agent and block (the basic unit of an agent, like the `Layer` concept in Pytorch) and some utilities for initializing the agent.
- `memory`: The implementation of the agent's memory, you can go deep into the directory to understand the design.
- `simulation`: The core runtime codes, including a `AgentSociety` class to manage the simulation and `AgentGroup` class to do parallel execution.
- `tools`: A tool base class and some tools for agents. TODO: should it be deprecated?
- `configs`: The whole config to start a simulation. You can see it as the only one entrypoint of AgentSociety

The third part is a default agent implementation, including:
- `cityagent`: The default agent implementation, including the `Block` implementation and the `Agent` implementation.

Then, we provide a web service implementation, including:
- `webapi`: A web backend implemented by FastAPI to start and manage simulations, and also provide a web UI to visualize the simulation results.

Some utilities are also included:
- `utils`: Some utility functions.
- `logger`: A logger for logging messages.