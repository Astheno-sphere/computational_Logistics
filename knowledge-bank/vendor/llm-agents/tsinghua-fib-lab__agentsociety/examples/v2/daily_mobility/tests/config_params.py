#!/usr/bin/env python3
"""生成 DailyMobility 的 init_config.json 与 steps.yaml。

运行：
  cd <workspace>
  PYTHONPATH=agentsociety/packages/agentsociety2:$PYTHONPATH \\
    python hypothesis_daily_mobility/experiment_1/init/config_params.py

环境变量：
  DAILY_MOBILITY_PRESET   benchmark | benchmark_fast | smoke（默认 benchmark）
  DAILY_MOBILITY_NUM_AGENTS
  DAILY_MOBILITY_START_T  默认 2000-01-03T00:00:00（周一，与 groundtruth 一致）
  DAILY_MOBILITY_TICK_SEC 每步仿真秒数；fast 默认 1800（30min/步 = 1 run/时段）
  DAILY_MOBILITY_MAX_TOOL_ROUNDS  agent 每步最大工具轮数；fast/benchmark 默认 6
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import yaml

try:
    from agentsociety2.agent.v1_deprecated.init_utils import init_needs_state
except ModuleNotFoundError:

    def init_needs_state(
        *, hunger: float = 0.35, energy: float = 0.65, stress: float = 0.1
    ) -> dict:
        return {
            "hunger": float(hunger),
            "energy": float(energy),
            "stress": float(stress),
            "current_need": "",
            "thresholds": {"hunger": 0.45, "energy": 0.34, "stress": 0.72},
            "can_interrupt": True,
        }


SCRIPT_DIR = Path(__file__).resolve().parent
EXP_DIR = SCRIPT_DIR.parent
HYP_DIR = EXP_DIR.parent
WORKSPACE = HYP_DIR.parent

INTENTION_CHOICE_LABELS = (
    "sleep",
    "home activity",
    "work",
    "shopping",
    "eating out",
    "leisure and entertainment",
    "other",
)


def _rng_float(agent_id: int, salt: str, lo: float, hi: float) -> float:
    h = hashlib.sha256(f"{agent_id}:{salt}".encode()).digest()
    u = int.from_bytes(h[:4], "big") / 0xFFFFFFFF
    return lo + (hi - lo) * u


def workspace_needs_seed(agent_id: int) -> dict:
    # Low-midnight hunger prevents 00:00 meals but can naturally reach breakfast.
    hunger = _rng_float(agent_id, "hunger", 0.32, 0.42)
    energy = _rng_float(agent_id, "energy", 0.30, 0.42)
    stress = _rng_float(agent_id, "stress", 0.05, 0.15)
    core = init_needs_state(hunger=hunger, energy=energy, stress=stress)
    core["needs"] = {
        "hunger": float(core["hunger"]),
        "energy": float(core["energy"]),
        "stress": float(core["stress"]),
    }
    urgency = max(hunger, 1.0 - energy, stress)
    core["urgency"] = float(max(0.0, min(1.0, urgency * 0.65)))
    if hunger >= 0.62:
        core["current_need"] = "hunger"
    elif energy <= 0.34:
        core["current_need"] = "energy"
    elif stress >= 0.72:
        core["current_need"] = "stress"
    else:
        core["current_need"] = ""
    return core


def _profile_block(p: dict, slot_minutes: int) -> str:
    aid = p["id"]
    return (
        f"Agent-{aid}, age {p.get('age', '?')}, gender {p.get('gender', '?')}, "
        f"education {p.get('education', '?')}, occupation {p.get('occupation', '?')}, "
        f"home AOI {p.get('home')}, work AOI {p.get('work')}. "
        "You are simulating an ordinary day in an urban mobility environment. "
        f"Each simulation step advances about {slot_minutes} minutes on the same calendar day. "
        "Use mobility tools as a real person would for commuting, errands, meals, and leisure, "
        "consistent with your profile."
    )


def questionnaire_step(slot_index: int) -> dict:
    from agentsociety2.society.daily_mobility_intentions import (
        build_primary_intention_prompt,
    )

    prompt = build_primary_intention_prompt(slot_index)
    return {
        "type": "questionnaire",
        "questionnaire_id": f"daily_mobility_intention_slot_{slot_index}",
        "title": "Daily mobility intention (30 min)",
        "description": "",
        "questions": [
            {
                "id": "primary_intention",
                "prompt": prompt,
                "response_type": "choice",
                "choices": list(INTENTION_CHOICE_LABELS),
            }
        ],
    }


def _slot_run_steps(tick: int) -> int:
    slot_seconds = 30 * 60
    if tick <= 0 or slot_seconds % tick != 0:
        raise ValueError(
            "DAILY_MOBILITY_TICK_SEC must divide one 30-minute questionnaire slot; "
            "use 1800, 900, 600, or 300."
        )
    return slot_seconds // tick


def build_steps_benchmark(target_ids: list[int], tick: int) -> list[dict]:
    """48 questionnaire slots at slot starts, with finer internal run ticks after each answer."""
    steps: list[dict] = []
    runs_per_slot = _slot_run_steps(tick)
    for slot in range(48):
        q = questionnaire_step(slot)
        q["target_agent_ids"] = target_ids
        steps.append(q)
        steps.append({"type": "run", "num_steps": runs_per_slot, "tick": tick})
    return steps


def build_steps_benchmark_fast(target_ids: list[int], tick: int) -> list[dict]:
    """Alias for benchmark; speed is controlled by TICK_SEC and NUM_AGENTS."""
    return build_steps_benchmark(target_ids, tick)


def build_steps_smoke(tick: int) -> list[dict]:
    return [{"type": "run", "num_steps": 2, "tick": tick}]


def main() -> None:
    preset = os.environ.get("DAILY_MOBILITY_PRESET", "benchmark").strip().lower()
    start_t = os.environ.get("DAILY_MOBILITY_START_T", "2000-01-03T00:00:00").strip()
    tick_default = "1800" if preset == "benchmark_fast" else "900"
    tick = int(os.environ.get("DAILY_MOBILITY_TICK_SEC", tick_default))
    slot_minutes = max(1, tick // 60)
    rounds_default = "6"
    max_tool_rounds = int(
        os.environ.get("DAILY_MOBILITY_MAX_TOOL_ROUNDS", rounds_default)
    )

    # Resolve profiles via agentsociety2 package location
    import agentsociety2

    _pkg_dir = (
        Path(agentsociety2.__file__).resolve().parent.parent
    )  # packages/agentsociety2/
    profiles_path = _pkg_dir / "profiles.json"

    # Map file: use env override, or fall back to AGENTSOCIETY_HOME_DIR
    _home = Path(
        os.environ.get("AGENTSOCIETY_HOME_DIR", "./agentsociety_data")
    ).resolve()
    map_path_raw = os.environ.get("DAILY_MOBILITY_MAP_PATH", "").strip()
    map_path = Path(map_path_raw).expanduser().resolve() if map_path_raw else None
    if map_path is None or not map_path.is_file():
        for candidate in [
            _home / "beijing.pb",
            _home / "agentsociety_beijing.pb",
            WORKSPACE.parent / "beijing.pb",
            WORKSPACE.parent / "agentsociety_beijing.pb",
            WORKSPACE / "agentsociety_data" / "beijing.pb",
            WORKSPACE / "agentsociety_data" / "agentsociety_beijing.pb",
        ]:
            if candidate.is_file():
                map_path = candidate.resolve()
                break

    if not profiles_path.is_file():
        raise FileNotFoundError(f"找不到 profiles: {profiles_path}")
    if map_path is None or not map_path.is_file():
        raise FileNotFoundError(f"找不到地图: {map_path or map_path_raw or _home}")

    with open(profiles_path, encoding="utf-8") as f:
        profiles: list[dict] = json.load(f)

    if preset == "smoke":
        num = int(os.environ.get("DAILY_MOBILITY_NUM_AGENTS", "2"))
        num = min(num, len(profiles))
        use = profiles[:num]
        steps_list = build_steps_smoke(tick)
    elif preset == "benchmark_fast":
        num = int(os.environ.get("DAILY_MOBILITY_NUM_AGENTS", "10"))
        num = min(num, len(profiles))
        use = profiles[:num]
        actual_ids = [p["id"] for p in use]
        steps_list = build_steps_benchmark_fast(actual_ids, tick)
    else:
        num = int(os.environ.get("DAILY_MOBILITY_NUM_AGENTS", "100"))
        num = min(num, len(profiles))
        use = profiles[:num]
        actual_ids = [p["id"] for p in use]
        steps_list = build_steps_benchmark(actual_ids, tick)

    actual_ids = [p["id"] for p in use]
    run_dir = EXP_DIR / "run"
    mobility_home = (run_dir / "mobility_workspace").resolve()
    mobility_home.mkdir(parents=True, exist_ok=True)

    persons = [
        {
            "id": p["id"],
            "position": {"aoi_id": p["home"]},
            "home_aoi": p["home"],
            "work_aoi": p["work"],
        }
        for p in use
    ]

    agents = []
    for p in use:
        aid = p["id"]
        nd = workspace_needs_seed(aid)
        hunger = float(nd.get("hunger", nd.get("needs", {}).get("hunger", 0.35)))
        energy = float(nd.get("energy", nd.get("needs", {}).get("energy", 0.65)))
        stress = float(nd.get("stress", nd.get("needs", {}).get("stress", 0.1)))
        need_txt = (
            f"hunger={hunger:.3f}\n"
            f"energy={energy:.3f}\n"
            f"stress={stress:.3f}\n"
            "feeling=stable\n"
            "drive=none\n"
            "HUNGER IS NOT EATING: eating out means an outside restaurant/cafe/bar visit, not all meals.\n"
        )
        agents.append(
            {
                "agent_id": aid,
                "agent_type": "PersonAgent",
                "kwargs": {
                    "id": aid,
                    "profile": _profile_block(p, slot_minutes),
                    "max_tool_rounds": max_tool_rounds,
                    "init_state": {
                        "workspace_seed": {
                            "state/needs.json": nd,
                            "state/current_need.txt": need_txt,
                        }
                    },
                },
            }
        )

    init_cfg = {
        "env_modules": [
            {
                "module_type": "MobilitySpace",
                "kwargs": {
                    "file_path": str(map_path.resolve()),
                    "home_dir": str(mobility_home),
                    "persons": persons,
                },
            }
        ],
        "agents": agents,
    }

    steps_yaml = {"start_t": start_t, "steps": steps_list}

    out_cfg = SCRIPT_DIR / "init_config.json"
    out_steps = SCRIPT_DIR / "steps.yaml"
    out_cfg.write_text(
        json.dumps(init_cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    out_steps.write_text(
        yaml.safe_dump(steps_yaml, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"Wrote {out_cfg}")
    print(f"Wrote {out_steps}")
    agent_steps = sum(
        s.get("num_steps", 0) for s in steps_list if s.get("type") == "run"
    )
    q_count = sum(1 for s in steps_list if s.get("type") == "questionnaire")
    print(
        f"preset={preset} agents={len(use)} tick={tick}s "
        f"max_tool_rounds={max_tool_rounds} "
        f"questionnaires={q_count} agent_run_steps={agent_steps} "
        f"ids[:8]={actual_ids[:8]}"
    )


if __name__ == "__main__":
    main()
