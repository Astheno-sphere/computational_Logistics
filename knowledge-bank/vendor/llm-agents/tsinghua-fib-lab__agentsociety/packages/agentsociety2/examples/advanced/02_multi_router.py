"""Multi-Router note + CodeGen production path demo.

Production env routing uses CodeGen inside a Ray ``EnvRouterProxy``.
This example only exercises that path with a stable ``list_agents`` ask.
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
from _checks import fresh_run_dir, require_no_critical_failures


async def main() -> None:
    run_dir = fresh_run_dir(Path("run_router_codegen"))
    agent_specs = [
        {
            "id": 1,
            "profile": {
                "id": 1,
                "name": "Tester",
                "personality": "analytical and helpful",
            },
            "config": {},
        }
    ]
    names = [(1, "Tester")]
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
    )
    await society.init()

    print("=== CodeGen Router (production EnvRouterProxy path) ===\n")
    question = "Use list_agents. What is the name of the only agent?"
    print(f"Question: {question}")
    t0 = time.perf_counter()
    response = await society.ask(question)
    wall = time.perf_counter() - t0
    print(f"Response: {response}")
    stats = society.all_token_stats()
    await society.close()
    require_no_critical_failures(run_dir)
    ok = "tester" in str(response).lower()
    print(f"Token stats: {stats}")
    print(f"WALL_SEC={wall:.2f}")
    print(f"SUCCESS={ok}")
    if not ok:
        print("ERROR: expected answer to mention Tester", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
