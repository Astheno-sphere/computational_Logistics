"""Onboarding demo environment: mutable weather state via @tool methods."""

from __future__ import annotations

from datetime import datetime

from agentsociety2.env import EnvBase, tool


class WeatherEnvironment(EnvBase):
    """Demo env with weather/temperature tools for intervene + ask examples."""

    def __init__(self) -> None:
        super().__init__()
        self._weather = "sunny"
        self._temperature = 25
        self._agent_locations: dict[int, str] = {}

    @classmethod
    def description(cls) -> str:
        return "Onboarding demo: weather and temperature tools."

    @classmethod
    def init_description(cls) -> str:
        return """WeatherEnvironment: onboarding demo environment.

No constructor kwargs. Default weather=sunny, temperature=25.

**Tools:**
- get_weather(agent_id): observe weather at agent location
- change_weather(weather, temperature): mutate global weather
- set_agent_location(agent_id, location): bind agent to a place
- get_average_temperature(): current temperature
"""

    @classmethod
    def is_concurrency_safe(cls) -> bool:
        return False

    @tool(readonly=True, kind="observe")
    def get_weather(self, agent_id: int) -> str:
        """Get the current weather for an agent's location."""
        location = self._agent_locations.get(agent_id, "unknown location")
        return (
            f"The weather in {location} is {self._weather} with {self._temperature}°C."
        )

    @tool(readonly=False)
    def change_weather(self, weather: str, temperature: int) -> str:
        """Change the weather conditions."""
        self._weather = weather
        self._temperature = temperature
        return f"Weather changed to {weather} at {temperature}°C."

    @tool(readonly=False)
    def set_agent_location(self, agent_id: int, location: str) -> str:
        """Set an agent's location."""
        self._agent_locations[agent_id] = location
        return f"Agent {agent_id} is now in {location}."

    @tool(readonly=True, kind="statistics")
    def get_average_temperature(self) -> str:
        """Get the current average temperature."""
        return f"The current temperature is {self._temperature}°C."

    async def step(self, tick: int, t: datetime) -> None:
        return None
