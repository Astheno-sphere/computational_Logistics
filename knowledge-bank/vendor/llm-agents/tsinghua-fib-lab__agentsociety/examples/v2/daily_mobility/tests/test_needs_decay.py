"""Test hunger/energy/stress decay and restoration logic."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import config_params
from agentsociety2.agent.skills.cognition.scripts import decay_needs as dn


def test_production_decay_uses_hunger_energy_stress_schema():
    needs = {"hunger": 0.30, "energy": 0.70, "stress": 0.10}
    changes = dn._apply_time_delta(
        needs,
        1.0,
        "work",
        datetime(2000, 1, 3, 10, 0, 0),
    )
    assert set(needs) == {"hunger", "energy", "stress"}
    assert needs["hunger"] > 0.30
    assert needs["energy"] < 0.70
    assert needs["stress"] > 0.10
    assert any("hunger:" in item for item in changes)
    assert any("energy:" in item for item in changes)
    assert any("stress:" in item for item in changes)


@dataclass
class NeedsState:
    hunger: float = 0.35
    energy: float = 0.65
    stress: float = 0.10

    def apply_time_delta(
        self, hours: float, previous_intention: str = "", *, when: datetime
    ) -> None:
        needs = {
            "hunger": self.hunger,
            "energy": self.energy,
            "stress": self.stress,
        }
        dn._apply_time_delta(needs, hours, previous_intention, when)
        self.hunger = needs["hunger"]
        self.energy = needs["energy"]
        self.stress = needs["stress"]

    def restore(self, intention: str, when: datetime) -> list[str]:
        goal = intention.lower()
        if "eating out" not in goal or self.hunger < dn.HUNGER_MEAL_THRESHOLD:
            return []
        hour = dn._hour_fraction(when)
        meal_window = dn.current_meal_window(hour)
        prev = self.hunger
        self.hunger = dn._meal_hunger_after(meal_window, prev)
        return [f"hunger: {prev:.3f} -> {self.hunger:.3f} (meal)"]

    def snapshot(self) -> dict[str, float]:
        return {
            "hunger": round(self.hunger, 4),
            "energy": round(self.energy, 4),
            "stress": round(self.stress, 4),
        }


def simulate_day(intentions: list[str], slot_hours: float = 0.5) -> list[dict]:
    needs = NeedsState()
    base = datetime(2000, 1, 3, 0, 0, 0)
    history = [{"slot": 0, "time_h": 0.0, "intention": "start", **needs.snapshot()}]

    for i, intent in enumerate(intentions):
        prev_intent = intentions[i - 1] if i > 0 else "start"
        when = base + timedelta(hours=(i + 1) * slot_hours)
        needs.apply_time_delta(slot_hours, prev_intent, when=when)
        needs.restore(intent, when)
        history.append(
            {
                "slot": i + 1,
                "time_h": round((i + 1) * slot_hours, 2),
                "intention": intent,
                **needs.snapshot(),
            }
        )

    return history


def test_hunger_increases_during_work_and_meal_reduces_it():
    n = NeedsState(hunger=0.60)
    n.apply_time_delta(1.0, "work", when=datetime(2000, 1, 3, 12, 0, 0))
    assert n.hunger > dn.HUNGER_MEAL_THRESHOLD
    restored = n.restore("eating out", datetime(2000, 1, 3, 12, 30, 0))
    assert any("meal" in r for r in restored)
    assert abs(n.hunger - dn.HUNGER_AFTER_LUNCH) < 0.001


def test_hunger_grows_slower_during_sleep():
    awake = NeedsState(hunger=0.3)
    asleep = NeedsState(hunger=0.3)
    awake.apply_time_delta(1.0, "work", when=datetime(2000, 1, 3, 10, 0, 0))
    asleep.apply_time_delta(1.0, "sleep", when=datetime(2000, 1, 3, 3, 0, 0))
    assert awake.hunger > asleep.hunger


def test_meal_does_not_restore_when_not_hungry():
    n = NeedsState(hunger=0.40)
    restored = n.restore("eating out", datetime(2000, 1, 3, 8, 0, 0))
    assert restored == []
    assert abs(n.hunger - 0.40) < 0.001


def test_breakfast_and_dinner_restore_differently():
    lunch = NeedsState(hunger=0.70)
    lunch.restore("eating out", datetime(2000, 1, 3, 12, 0, 0))
    breakfast = NeedsState(hunger=0.70)
    breakfast.restore("eating out", datetime(2000, 1, 3, 8, 0, 0))
    assert breakfast.hunger > lunch.hunger


def test_energy_drops_during_work_and_recovers_during_sleep():
    work = NeedsState(energy=0.8)
    work.apply_time_delta(3.0, "work", when=datetime(2000, 1, 3, 15, 0, 0))
    assert work.energy < 0.65

    sleep = NeedsState(energy=0.3)
    sleep.apply_time_delta(8.0, "sleep", when=datetime(2000, 1, 3, 6, 0, 0))
    assert sleep.energy > 0.60


def test_home_activity_at_night_drains_energy():
    home = NeedsState(energy=0.48)
    home.apply_time_delta(1.0, "home activity", when=datetime(2000, 1, 3, 2, 0, 0))
    assert home.energy < 0.48


def test_home_and_leisure_recover_energy_mildly():
    home = NeedsState(energy=0.45)
    home.apply_time_delta(2.0, "home activity", when=datetime(2000, 1, 3, 20, 0, 0))
    leisure = NeedsState(energy=0.45)
    leisure.apply_time_delta(
        2.0, "leisure and entertainment", when=datetime(2000, 1, 3, 19, 0, 0)
    )
    assert home.energy > 0.45
    assert leisure.energy > 0.45


def test_work_uses_faster_need_dynamics_than_home_activity():
    work = {"hunger": 0.35, "energy": 0.75, "stress": 0.10}
    home = {"hunger": 0.35, "energy": 0.75, "stress": 0.10}
    work_diag: dict = {}
    home_diag: dict = {}
    dn._apply_time_delta(
        work,
        1.0,
        "work",
        datetime(2000, 1, 3, 10, 0, 0),
        diagnostics=work_diag,
    )
    dn._apply_time_delta(
        home,
        1.0,
        "home activity",
        datetime(2000, 1, 3, 10, 0, 0),
        diagnostics=home_diag,
    )
    assert work["hunger"] > home["hunger"]
    assert work["energy"] < home["energy"]
    assert work["stress"] > home["stress"]
    assert (
        work_diag["hunger"]["rate_range_per_hour"][0]
        < work_diag["hunger"]["rate_range_per_hour"][1]
    )


def test_strong_rhythm_work_overrides_stale_home_restore(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    (tmp_path / "_restore_intention.json").write_text(
        json.dumps({"goal": "home activity"}), encoding="utf-8"
    )
    (state / "rhythm_state.json").write_text(
        json.dumps(
            {
                "time": "2000-01-03T10:00:00",
                "recommendation": "work",
                "norm_strength": 0.8,
                "scheduled_activity": {"activity": "work"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert dn._effective_previous_goal() == "work"


def test_stress_builds_at_work_and_recovers_at_home():
    work = NeedsState(stress=0.10)
    work.apply_time_delta(4.0, "work", when=datetime(2000, 1, 3, 14, 0, 0))
    assert 0.25 < work.stress <= dn.STRESS_WORK_CAP + 0.01

    commute = NeedsState(stress=0.10)
    commute.apply_time_delta(2.0, "commute_to_work", when=datetime(2000, 1, 3, 9, 0, 0))
    assert commute.stress > 0.15

    home = NeedsState(stress=0.50)
    home.apply_time_delta(3.0, "home activity", when=datetime(2000, 1, 3, 21, 0, 0))
    assert home.stress < 0.50


def test_low_energy_and_missed_meal_raise_stress():
    n = NeedsState(hunger=0.85, energy=0.25, stress=0.10)
    n.apply_time_delta(2.0, "work", when=datetime(2000, 1, 3, 14, 0, 0))
    assert n.stress > 0.22


def test_eo2_meal_restores_only_when_hungry():
    intentions = []
    for p in Path("/tmp/single_bench_eo2/artifacts").glob("questionnaire_step_*.json"):
        d = json.loads(p.read_text())
        intentions.append(d["responses"][0]["answers"][0]["parsed_value"])
    if len(intentions) != 48:
        return
    history = simulate_day(intentions)
    for i in range(1, len(history)):
        drop = history[i - 1]["hunger"] - history[i]["hunger"]
        if drop > 0.10:
            assert history[i - 1]["hunger"] >= dn.HUNGER_MEAL_THRESHOLD - 0.02


def test_realistic_day_has_meals_work_energy_dip_and_night_recovery():
    intentions = (
        ["sleep"] * 13
        + ["eating out"] * 1
        + ["home activity"] * 1
        + ["work"] * 11
        + ["eating out"] * 1
        + ["work"] * 9
        + ["eating out"] * 1
        + ["leisure and entertainment"] * 3
        + ["home activity"] * 2
        + ["sleep"] * 6
    )
    assert len(intentions) == 48

    history = simulate_day(intentions)
    hunger_vals = [h["hunger"] for h in history]
    energy_vals = [h["energy"] for h in history]
    stress_vals = [h["stress"] for h in history]

    meal_restores = sum(
        1
        for i in range(1, len(history))
        if history[i - 1]["hunger"] - history[i]["hunger"] > 0.10
    )
    assert meal_restores >= 2
    assert max(hunger_vals) > dn.HUNGER_MEAL_THRESHOLD
    assert min(energy_vals[18:38]) < energy_vals[0]
    assert energy_vals[-1] > energy_vals[38]
    assert max(stress_vals[18:38]) > stress_vals[0]


def test_benchmark_steps_query_at_slot_start_and_cover_24h():
    steps = config_params.build_steps_benchmark([1], tick=900)
    questionnaires = [s for s in steps if s["type"] == "questionnaire"]
    runs = [s for s in steps if s["type"] == "run"]

    assert steps[0]["type"] == "questionnaire"
    assert len(questionnaires) == 48
    assert questionnaires[0]["questionnaire_id"] == "daily_mobility_intention_slot_0"
    assert questionnaires[-1]["questionnaire_id"] == "daily_mobility_intention_slot_47"
    assert all(s["num_steps"] == 2 for s in runs)
    assert sum(s["num_steps"] * s["tick"] for s in runs) == 24 * 60 * 60
