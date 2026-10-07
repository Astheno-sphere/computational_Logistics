"""Mobility harness verification and Daily Mobility gate checks."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import yaml

from mobility_snapshot import verify_move_effect


def _load_check_module():
    path = (
        Path(__file__).resolve().parent
        / "daily_mobility/tools/check_daily_mobility_run.py"
    )
    spec = importlib.util.spec_from_file_location("check_daily_mobility_run", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verify_move_effect_accepts_live_target_trip():
    result = verify_move_effect(
        before={"status": "idle", "aoi_id": 1},
        after={"status": "moving", "aoi_id": None, "target_aoi_id": 2},
        target_id=2,
    )
    assert result["ok"] is True


def test_verify_move_effect_rejects_unchanged_state():
    result = verify_move_effect(
        before={"status": "idle", "aoi_id": 1},
        after={"status": "idle", "aoi_id": 1, "target_aoi_id": None},
        target_id=2,
    )
    assert result["ok"] is False


def test_daily_mobility_gate_fails_for_location_intention_mismatch():
    module = _load_check_module()
    report = {"totals": {"work_while_home": 3}, "agents": {}}
    gate = module.evaluate_gates(report)
    assert gate["status"] == "FAIL"
    assert gate["failures"][0]["issue"] == "work_while_home"


def test_benchmark_config_activates_daily_guidance_without_template_cache(tmp_path):
    script = Path(__file__).resolve().parent / "init" / "config_params.py"
    env = os.environ.copy()
    env.update(
        {
            "DAILY_MOBILITY_PRESET": "benchmark",
            "DAILY_MOBILITY_NUM_AGENTS": "2",
            "DAILY_MOBILITY_RUN_DIR": str(tmp_path / "run"),
        }
    )

    subprocess.run([sys.executable, str(script)], check=True, env=env)

    cfg_path = Path(__file__).resolve().parent / "tmp" / "init" / "init_config.json"
    config = json.loads(cfg_path.read_text(encoding="utf-8"))
    agents = config["agents"]
    assert len(agents) == 2
    assert all(
        agent["kwargs"]["default_activated_skill_ids"] == ["built-in@daily-guidance"]
        for agent in agents
    )
    assert all("disabled_skill_ids" not in agent["kwargs"] for agent in agents)

    steps_path = Path(__file__).resolve().parent / "tmp" / "init" / "steps.yaml"
    steps = yaml.safe_load(steps_path.read_text(encoding="utf-8"))["steps"]
    questionnaires = [step for step in steps if step["type"] == "questionnaire"]
    run_steps = sum(step.get("num_steps", 0) for step in steps if step["type"] == "run")
    assert len(questionnaires) == 48
    assert run_steps == 96
    first_prompt = questionnaires[0]["questions"][0]["prompt"]
    assert "time slot 1 of 48" in first_prompt
    assert "30-minute period" in first_prompt
    assert "dominant" in first_prompt.casefold()
    assert "current" in first_prompt.casefold()
    # The agent now reasons via its ReAct loop; the prompt no longer hard-codes
    # benchmark clock rules (those moved to postprocess normalization).
    assert "22:00-06:30" not in first_prompt
    assert "State first" not in first_prompt


def test_benchmark_config_can_generate_48_hour_run(tmp_path):
    script = Path(__file__).resolve().parent / "init" / "config_params.py"
    env = os.environ.copy()
    env.update(
        {
            "DAILY_MOBILITY_PRESET": "benchmark",
            "DAILY_MOBILITY_NUM_AGENTS": "2",
            "DAILY_MOBILITY_DURATION_HOURS": "48",
            "DAILY_MOBILITY_RUN_DIR": str(tmp_path / "run"),
        }
    )

    subprocess.run([sys.executable, str(script)], check=True, env=env)

    steps_path = Path(__file__).resolve().parent / "tmp" / "init" / "steps.yaml"
    steps = yaml.safe_load(steps_path.read_text(encoding="utf-8"))["steps"]
    questionnaires = [step for step in steps if step["type"] == "questionnaire"]
    run_steps = sum(step.get("num_steps", 0) for step in steps if step["type"] == "run")

    assert len(questionnaires) == 96
    assert run_steps == 192
    last_prompt = questionnaires[-1]["questions"][0]["prompt"]
    assert "time slot 96 of 96" in last_prompt
    assert "dominant" in last_prompt.casefold()
