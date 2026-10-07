"""
Demo script for mobility environment.

This script demonstrates how to use the agentsociety2 framework
with the MobilitySpace environment module.
"""

import asyncio
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

from agentsociety2.contrib.env.global_information import GlobalInformationEnv
from agentsociety2.contrib.env.mobility_space import MobilitySpace
from agentsociety2.env import CodeGenRouter, EnvBase

# Disable telemetry before any imports
os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

load_dotenv()


async def main():
    # 1) Config: 1s tick, run for 60s
    start_t = datetime.now()

    # 2) Environment: only GlobalInformationEnv, also used as fallback
    global_info = GlobalInformationEnv()
    mobility = MobilitySpace(
        os.getenv("MOBILITY_MAP_PATH"),
        os.getenv("MOBILITY_HOME_DIR", os.path.expanduser("~/.agentsociety")),
        [
            {
                "id": 1,
                "position": {
                    "kind": "aoi",
                    "aoi_id": 5_0000_0000,
                },
            },
            {
                "id": 2,
                "position": {
                    "kind": "aoi",
                    "aoi_id": 5_0000_0001,
                },
            },
        ],
    )

    env_modules: list[EnvBase] = [mobility, global_info]

    env_router = CodeGenRouter(env_modules=env_modules)
    print("--------------------------------")
    print(env_router._writable_tools_xml)
    print("--------------------------------")
    await env_router.init(start_t)
    _, answer = await env_router.ask(
        {"id": 1},
        "Go to restaurant",
        readonly=False,
    )
    print(answer)

    await env_router.step(100, start_t + timedelta(seconds=100))
    _ctx, answer = await env_router.ask(
        {"id": 1},
        "go to restaurant",
        readonly=False,
    )
    print(answer)


if __name__ == "__main__":
    asyncio.run(main())
