"""Custom Agent Example.

Uses the contrib SpecialistAgent (Ray-discoverable). Answers come from
get_agent_profile / ask_agents — stable onboarding, no multi-hop ReAct.
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
    run_dir = fresh_run_dir(Path("run_specialist_agent"))

    agent_specs = [
        {
            "id": 1,
            "profile": {
                "id": 1,
                "name": "Dr. Climate",
                "personality": "scientific and concerned",
                "specialty": "climate science and environmental policy",
            },
            "config": {"specialty": "climate science and environmental policy"},
        }
    ]
    names = [(1, "Dr. Climate")]
    env_router = await create_env_router_proxy(
        ["SimpleSocialSpace"],
        {"SimpleSocialSpace": {"agent_id_name_pairs": names}},
        run_dir=run_dir,
    )
    society = AgentSociety(
        agent_specs=agent_specs,
        agent_class_name="SpecialistAgent",
        env_router=env_router,
        start_t=datetime.now(),
        run_dir=run_dir,
    )
    await society.init()

    print("=== Custom Agent Example ===\n")
    q1 = "Use get_agent_profile for name='Dr. Climate'. What is the specialty?"
    print(f"Question: {q1}")
    t0 = time.perf_counter()
    a1 = str(await society.ask(q1))
    print(f"Answer: {a1}\n")

    q2 = "Use ask_agents with agent_ids=[1]: what is your specialty?"
    print(f"Question: {q2}")
    a2 = str(await society.ask(q2))
    print(f"Answer: {a2}\n")
    wall = time.perf_counter() - t0
    stats = society.all_token_stats()
    await society.close()
    require_no_critical_failures(run_dir)

    joined = f"{a1} {a2}".lower()
    ok = "climate" in joined
    print(f"Token stats: {stats}")
    print(f"WALL_SEC={wall:.2f}")
    print(f"SUCCESS={ok}")
    if not ok:
        print("ERROR: expected climate specialty in answers", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
