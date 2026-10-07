"""Replay System Example.

Shows that ``enable_replay=True`` writes ``run/replay/_schema.json`` at init
(step-0 timeline). No agent LLM step is required for this smoke demo.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import asyncio
from datetime import datetime

from agentsociety2.env import create_env_router_proxy
from agentsociety2.society import AgentSociety

_EXAMPLES_ROOT = Path(__file__).resolve().parents[1]
if str(_EXAMPLES_ROOT) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_ROOT))
from _checks import fresh_run_dir


async def main() -> None:
    run_dir = fresh_run_dir(Path("run_replay_example"))

    agent_specs = [
        {
            "id": i,
            "profile": {
                "id": i,
                "name": f"Agent{i}",
                "personality": "friendly" if i % 2 == 0 else "curious",
            },
            "config": {},
        }
        for i in range(1, 3)
    ]
    names = [(spec["id"], spec["profile"]["name"]) for spec in agent_specs]

    t0 = time.perf_counter()
    env_router = await create_env_router_proxy(
        ["SimpleSocialSpace"],
        {"SimpleSocialSpace": {"agent_id_name_pairs": names}},
        run_dir=run_dir,
    )
    society = AgentSociety(
        agent_specs=agent_specs,
        agent_class_name="PersonAgent",
        env_router=env_router,
        start_t=datetime.now(),
        run_dir=run_dir,
        enable_replay=True,
    )
    await society.init()
    schema = run_dir / "replay" / "_schema.json"
    print("=== Replay System Demo ===\n")
    print(f"Replay schema: {schema}")
    print(f"Exists: {schema.is_file()}")
    stats = society.all_token_stats()
    await society.close()
    wall = time.perf_counter() - t0
    print(f"Token stats: {stats}")
    print(f"WALL_SEC={wall:.2f}")
    print(f"SUCCESS={schema.is_file()}")
    if not schema.is_file():
        print("ERROR: replay/_schema.json missing after init", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
