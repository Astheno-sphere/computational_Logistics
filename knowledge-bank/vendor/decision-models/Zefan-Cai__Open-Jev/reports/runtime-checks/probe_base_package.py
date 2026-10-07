"""Probe an installed Open-Jev base wheel without model or training imports."""
import importlib.metadata as metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import jev
from jev.api import candidate_prompts, compile_request, format_response
from jev.client import Client
from jev.server import make_server


checks = []


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)


prefix = Path(sys.prefix).resolve()
check("venv_is_separate_from_base", sys.prefix != sys.base_prefix)
check("installed_import_origin", Path(jev.__file__).resolve().is_relative_to(prefix))
check("cwd_is_outside_installed_package", not Path.cwd().resolve().is_relative_to(Path(jev.__file__).resolve().parent))
venv_config = (prefix / "pyvenv.cfg").read_text()
check("system_site_packages_disabled", "include-system-site-packages = false" in venv_config)

distribution = metadata.distribution("open-jev")
expected_entries = {"open-jev-serve": "jev.server:main", "open-jev-train": "jev.train:main"}
actual_entries = {entry.name: entry.value for entry in distribution.entry_points if entry.group == "console_scripts"}
check("both_console_entry_points_installed", actual_entries == expected_entries)
env = dict(os.environ)
env.pop("PYTHONPATH", None)
env.pop("PYTHONHOME", None)
env["PYTHONNOUSERSITE"] = "1"
env["PYTHONDONTWRITEBYTECODE"] = "1"
cli = []
for name in expected_entries:
    command = [str(prefix / "bin" / name), "--help"]
    result = subprocess.run(command, cwd=Path.cwd(), env=env, capture_output=True, text=True, timeout=30)
    check(name + "_help", result.returncode == 0 and "usage:" in result.stdout)
    cli.append({"argv": command, "cwd": str(Path.cwd()), "returncode": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr})

state = {"message": "订单损坏，请退款。", "order_id": "fixture-order"}
questions = {
    "action": {"type": "choice", "instructions": "Select a fixture action.",
               "criteria": {"refund": "Refund the order", "replace": "Replace the order"}},
    "urgency": {"type": "score", "instructions": "Select a fixture urgency level.",
                "criteria": ["low", "medium", "high"]},
    "requested": {"type": "noul", "instructions": "Is a refund requested?"},
}
records = compile_request(state, questions)
check("three_protocol_forms_compile", [record["kind"] for record in records] == ["choice", "score", "noul"])
check("protocol_records_have_no_targets", all("target" not in record for record in records))
check("candidate_prompt_counts", [len(candidate_prompts(record)) for record in records] == [2, 3, 1])
probabilities = [[0.8, 0.2], [0.1, 0.2, 0.7], [0.1, 0.9]]
expected = format_response(records, probabilities)
check("choice_answer_mapping", expected["answers"]["action"]["choice"] == "refund")
check("score_expected_value", math.isclose(expected["answers"]["urgency"]["score"], 1.6))
check("noul_probability", expected["answers"]["requested"]["noul"] == 0.9)
try:
    format_response(records, [[0.9, 0.9], probabilities[1], probabilities[2]])
except ValueError:
    checks.append("invalid_probability_mass_rejected")
else:
    raise AssertionError("invalid probability mass accepted")


class ProtocolFixture:
    """Deterministic transport fixture; does not perform model inference."""

    model_name = "cpu-protocol-fixture"
    method = "fixture-only"

    def __init__(self):
        self.received = []

    def predict(self, request):
        self.received.append(request)
        if request["state"] == "wrong-ids-fixture":
            return {"answers": {"unrequested": {"type": "noul", "noul": 0.5}}}
        return format_response(compile_request(request["state"], request["questions"]), probabilities)


fixture = ProtocolFixture()
server = make_server(fixture, host="127.0.0.1", port=0)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
endpoint = f"http://127.0.0.1:{server.server_port}"
static_root_status = None
try:
    client = Client(endpoint + "/v1/systemone", timeout=5)
    response = client.ask(state, questions, model="fixture-request-model")
    check("loopback_client_server_protocol_roundtrip", response == expected)
    check("client_preserves_unicode_state_and_questions", fixture.received[-1] == {
        "model": "fixture-request-model", "state": state, "questions": questions})
    try:
        client.ask("wrong-ids-fixture", questions)
    except ValueError as error:
        check("client_rejects_mismatched_question_ids", "question IDs" in str(error))
    else:
        raise AssertionError("client accepted mismatched question IDs")
    with urlopen(endpoint + "/health", timeout=5) as response:
        check("health_route_without_train_dependencies", json.load(response)["model"] == fixture.model_name)
    with urlopen(endpoint + "/examples.json", timeout=5) as response:
        installed_examples = json.load(response)["files"]
    try:
        with urlopen(endpoint + "/", timeout=5) as response:
            static_root_status = response.status
    except HTTPError as error:
        static_root_status = error.code
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)

forbidden = [name for name in sys.modules if any(
    name == root or name.startswith(root + ".")
    for root in ("torch", "transformers", "peft", "jev.model"))]
check("no_model_or_train_module_imported_by_probe", not forbidden)
missing_train = {name: importlib.util.find_spec(name) is None
                 for name in ["torch", "transformers", "peft", "accelerate", "datasets"]}
check("train_packages_are_absent", all(missing_train.values()))

print(json.dumps({
    "status": "passed",
    "scope": "Local CPU base-wheel packaging and standard-library protocol/client transport only; deterministic fixture, no model predictions.",
    "python": sys.version,
    "platform": platform.platform(),
    "machine": platform.machine(),
    "executable": sys.executable,
    "prefix": sys.prefix,
    "base_prefix": sys.base_prefix,
    "cwd": str(Path.cwd()),
    "jev_import_origin": jev.__file__,
    "system_site_packages": False,
    "installed_distributions": {dist.metadata["Name"]: dist.version for dist in metadata.distributions()},
    "requires_python": distribution.metadata.get("Requires-Python"),
    "requires_dist": distribution.requires or [],
    "entry_points": actual_entries,
    "cli_help": cli,
    "checks_passed": checks,
    "train_packages_absent": missing_train,
    "forbidden_modules_imported": forbidden,
    "static_assets_observation": {"root_http_status": static_root_status, "examples_json_files": installed_examples},
    "real_model_inference_validated": False,
    "linux_gpu_install_validated": False,
}, indent=2))
