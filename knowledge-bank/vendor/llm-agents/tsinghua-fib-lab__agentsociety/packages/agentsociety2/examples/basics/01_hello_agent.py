"""Basic Agent Example: Hello Agent.

Stable onboarding demo: questions are answered from society specs via
``list_agents`` / ``get_agent_profile`` (no per-agent ReAct loop).
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
    run_dir = fresh_run_dir(Path("run_hello_agent"))
    agent_specs = [
        {
            "id": 1,
            "profile": {
                "id": 1,
                "name": "Alice",
                "age": 28,
                "personality": "friendly, curious, and optimistic",
                "bio": "A software engineer who loves hiking, reading sci-fi novels, and cooking.",
                "location": "San Francisco",
            },
            "config": {},
        }
    ]
    names = [(spec["id"], spec["profile"]["name"]) for spec in agent_specs]

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

    print("=== Basic Agent Interaction ===\n")
    questions = [
        "Use list_agents. What are the id and name of every agent?",
        "Use get_agent_profile for name=Alice. Summarize personality, bio, and location.",
        "Use list_agents. How many agents exist in this simulation?",
    ]
    answers: list[str] = []
    t0 = time.perf_counter()
    for question in questions:
        print(f"Question: {question}")
        response = await society.ask(question)
        answers.append(str(response))
        print(f"Answer: {response}\n")
    wall = time.perf_counter() - t0
    stats = society.all_token_stats()
    await society.close()
    require_no_critical_failures(run_dir)

    joined = " ".join(answers).lower()
    ok = ("alice" in joined) and ("1" in joined or "one" in joined)
    print(f"Token stats: {stats}")
    print(f"WALL_SEC={wall:.2f}")
    print(f"SUCCESS={ok}")
    if not ok:
        print("ERROR: expected answers to mention Alice / agent count", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
