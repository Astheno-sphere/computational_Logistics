import importlib.util
from pathlib import Path


def _load_daily_guidance_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "agentsociety2"
        / "agent"
        / "skills"
        / "daily-guidance"
        / "scripts"
        / "daily_guidance.py"
    )
    spec = importlib.util.spec_from_file_location("daily_guidance_test_module", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_normalize_argv_preserves_lifecycle_hook_args_json():
    daily_guidance = _load_daily_guidance_module()

    assert daily_guidance.normalize_argv(
        ["--args-json", '{"hook_type":"pre_step"}']
    ) == [
        "--args-json",
        '{"hook_type":"pre_step"}',
    ]


def test_normalize_argv_treats_extra_args_json_as_plan_json_alias():
    daily_guidance = _load_daily_guidance_module()

    assert daily_guidance.normalize_argv(
        ["--args-json", '{"story_id":"s","date":"2026-06-17","segments":[]}', "plan"]
    ) == [
        "plan",
        "--json",
        '{"story_id":"s","date":"2026-06-17","segments":[]}',
    ]


def test_parse_args_no_longer_reports_trailing_plan_as_unrecognized(capsys):
    daily_guidance = _load_daily_guidance_module()

    args = daily_guidance.parse_args(["--args-json", "plan", "plan"])
    captured = capsys.readouterr()
    assert "unrecognized arguments: plan" not in captured.err
    assert args.cmd == "plan"
    assert args.json == "plan plan"


def test_parse_args_accepts_legacy_args_json_plan_without_date():
    daily_guidance = _load_daily_guidance_module()
    payload = '{"story_id":"s","date":"2026-06-17","segments":[]}'

    args = daily_guidance.parse_args(["--args-json", payload, "plan"])

    assert args.cmd == "plan"
    assert args.date == ""
    assert args.json == payload


def test_normalize_argv_infers_record_command_from_options():
    daily_guidance = _load_daily_guidance_module()

    assert daily_guidance.normalize_argv(
        [
            "--date",
            "2026-06-17",
            "record",
            "--activity",
            "work",
            "--location",
            "office",
        ]
    ) == [
        "record",
        "--date",
        "2026-06-17",
        "--activity",
        "work",
        "--location",
        "office",
    ]


def test_normalize_argv_supports_date_first_plan_shorthand():
    daily_guidance = _load_daily_guidance_module()

    assert daily_guidance.normalize_argv(
        [
            "2026-06-17",
            "--json",
            '{"story_id":"s","date":"2026-06-17","segments":[]}',
        ]
    ) == [
        "plan",
        "--date",
        "2026-06-17",
        "--json",
        '{"story_id":"s","date":"2026-06-17","segments":[]}',
    ]
