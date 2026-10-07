"""Unit tests for the MIKE 1D engine-log QA parser (pure, no license)."""
import time

from mikeplus_mcp.runtime.engine_log import parse_engine_log, read_run_log

# mirrors the real engine log format (timestamps, WARNING lines, a per-phase
# roll-up, and the terminal 'Simulation done')
OK_LOG = """\
2026-06-21 04:58:43: MIKE 1D Engine started (2026 - 64 bit)
2026-06-21 04:58:44: Loading setup file Model.sqlite...
2026-06-21 04:58:44: WARNING: 'Diurnal pattern normalized' (GE_WAR_Generic)
2026-06-21 04:58:44: Validating setup
2026-06-21 04:58:44: WARNING: Reach start top level above node for reach 'C1.1' (ND_WAR_X)
2026-06-21 04:58:44: WARNING: Reach start top level above node for reach 'C2.1' (ND_WAR_X)
2026-06-21 04:58:44: WARNING: 3 issue(s) found during validate (0 error(s)).
2026-06-21 04:58:46: Running simulation
2026-06-21 04:59:35: Simulation done
"""

ERR_DONE_LOG = """\
2026-06-21 05:00:00: Validating setup
2026-06-21 05:00:00: WARNING: 1 issue(s) found during validate (2 error(s)).
2026-06-21 05:00:30: Simulation done
"""

INCOMPLETE_LOG = """\
2026-06-21 05:00:00: Loading setup file Model.sqlite...
2026-06-21 05:00:01: ERROR: Boundary item not found (EN_ERR_X)
2026-06-21 05:00:01: Simulation stopped
"""


def test_ok_log_counts_warnings_and_completes():
    qa = parse_engine_log(OK_LOG)
    assert qa["completed"] is True
    assert qa["errors"] == 0
    assert qa["warnings"] == 3          # 3 real WARNING lines; the roll-up is excluded
    assert qa["issues"] == 3            # from "3 issue(s) found"
    assert qa["status"] == "completed_with_warnings"


def test_clean_log_is_ok():
    qa = parse_engine_log("2026-06-21 05:00:00: Running simulation\n2026-06-21 05:01:00: Simulation done\n")
    assert qa == {"completed": True, "errors": 0, "warnings": 0, "issues": 0, "status": "ok"}


def test_errors_from_summary_when_completed():
    qa = parse_engine_log(ERR_DONE_LOG)
    assert qa["errors"] == 2            # from "(2 error(s))"
    assert qa["completed"] is True
    assert qa["status"] == "completed_with_errors"


def test_incomplete_run_with_error_line():
    qa = parse_engine_log(INCOMPLETE_LOG)
    assert qa["completed"] is False
    assert qa["errors"] == 1            # counted from the ERROR: line
    assert qa["status"] == "incomplete"


def test_tail_only_still_detects_completion():
    # _log_tail holds just the end of stdout; the QA gate must still see completion
    qa = parse_engine_log(OK_LOG[-120:])
    assert qa["completed"] is True


def test_read_run_log_finds_and_parses(tmp_path):
    (tmp_path / "Model_Sim.log").write_text(OK_LOG, encoding="utf-8")
    qa = read_run_log(tmp_path)
    assert qa["log_file"].endswith("Model_Sim.log")
    assert qa["completed"] is True
    assert qa["status"] == "completed_with_warnings"


def test_read_run_log_picks_newest(tmp_path):
    old = tmp_path / "old.log"
    old.write_text("2026-01-01 00:00:00: Simulation done\n", encoding="utf-8")
    time.sleep(0.01)
    new = tmp_path / "new.log"
    new.write_text(OK_LOG, encoding="utf-8")
    assert read_run_log(tmp_path)["log_file"].endswith("new.log")


def test_read_run_log_empty_dir_is_unknown(tmp_path):
    qa = read_run_log(tmp_path)
    assert qa["log_file"] is None
    assert qa["status"] == "unknown"


def test_read_run_log_respects_since_mtime(tmp_path):
    (tmp_path / "x.log").write_text(OK_LOG, encoding="utf-8")
    # a far-future threshold excludes the file just written
    assert read_run_log(tmp_path, since_mtime=time.time() + 1_000)["log_file"] is None
