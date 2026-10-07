"""Bounded native Jev and verbalized GPT evaluation on public JevBench tasks.

Uses the pinned upstream adapters, Runner, scoring and durable budget ledger.
No retries or generated replacement tasks. Raw evidence stays private; a
reservation is a conservative execution guard, not a provider billing limit.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess

from scripts import jevbench_openjev as benchmark


ROOT = Path(__file__).resolve().parents[1]
KEY_ENV = "OPENJEV_JEVBENCH_API_KEY"
PROVIDERS = {
    "jev": {"model": "jev-1.13.0", "endpoint": "https://api.typesafe.ai", "kind": "typesafe",
            "input_price": .042, "output_price": 0., "options": {}, "probabilities": "native",
            "price_source": "https://docs.typesafe.ai/models"},
    "luna": {"model": "gpt-5.6-luna", "endpoint": "https://api.openai.com/v1", "kind": "openai_compat",
             "input_price": .2, "output_price": 1.2, "probabilities": "verbalized",
             "options": {"temperature": None, "max_tokens": None, "max_completion_tokens": 4096,
                         "reasoning_effort": "none"},
             "price_source": "https://developers.openai.com/api/docs/models/gpt-5.6-luna"},
    "astra": {"model": "gpt-6-astra", "endpoint": "https://api.openai.com/v1", "kind": "openai_compat",
              "input_price": 10., "output_price": 50., "probabilities": "verbalized",
              "options": {"temperature": None, "max_tokens": None, "max_completion_tokens": 4096,
                          "reasoning_effort": "low"},
              "price_source": "https://developers.openai.com/api/docs/models/gpt-6-astra"},
}


class DeadlineReached(BaseException):
    """Bypasses upstream network-error handling so no request follows a timeout."""


def git_ancestor(path):
    return next((parent for parent in (path, *path.parents) if (parent / ".git").exists()), None)


def read_key(path):
    path = Path(path).resolve(strict=True)
    if git_ancestor(path.parent) is not None:
        raise ValueError("API key files must be outside every Git checkout")
    key = path.read_text().strip()
    if not key or len(key) > 4096 or any(character.isspace() for character in key):
        raise ValueError("Expected one nonempty API key in the private file")
    return key


def private_output(path):
    path = Path(path).resolve()
    repository = git_ancestor(path.parent)
    if repository is not None:
        result = subprocess.run(["git", "-C", str(repository), "check-ignore", "--no-index", "-q", str(path)],
                                check=False, capture_output=True)
        if result.returncode != 0:
            raise ValueError("Raw run outputs must be outside Git or inside an ignored directory")
    return path


@contextmanager
def scoped_key(key):
    previous = os.environ.get(KEY_ENV)
    os.environ[KEY_ENV] = key
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(KEY_ENV, None)
        else:
            os.environ[KEY_ENV] = previous


def usage_cost(usage, config):
    if not isinstance(usage, dict):
        return None
    values = [usage.get("input_tokens", usage.get("prompt_tokens")),
              usage.get("output_tokens", usage.get("completion_tokens"))]
    if any(type(value) is not int or value < 0 for value in values):
        return None
    return (values[0] * config["input_price"] + values[1] * config["output_price"]) / 1e6


def reservation(body, config):
    wire_bytes = len(json.dumps(body).encode("utf-8"))  # Exact upstream JSON transport serialization.
    output_tokens = body.get("max_completion_tokens", 0)
    if config["kind"] == "openai_compat" and output_tokens != 4096:
        raise ValueError("GPT completion cap must remain 4096, including reasoning tokens")
    # Full wire bytes overcount ordinary byte-level text tokenization. Retain
    # an additional framing/schema allowance; observed usage is audited below.
    input_bound = wire_bytes + 4096
    reserve = (input_bound * config["input_price"] + output_tokens * config["output_price"]) / 1e6
    return {"wire_bytes": wire_bytes, "input_token_bound": input_bound,
            "output_token_bound": output_tokens, "reserve_usd": reserve}


def redact(value, key):
    if isinstance(value, str):
        return value.replace(key, "[REDACTED]")
    if isinstance(value, list):
        return [redact(item, key) for item in value]
    if isinstance(value, dict):
        return {redact(name, key): redact(item, key) for name, item in value.items()}
    return value


class BoundedAdapter:
    """Keep upstream inference unchanged; bound reservations and retain error usage."""
    def __init__(self, inner, config, key):
        self.inner, self.config, self.key = inner, config, key

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def reserve_estimate(self, task):
        return reservation(self.inner.build_request(task), self.config)["reserve_usd"]

    def run(self, task):
        result = self.inner.run(task)
        # Upstream preserves usage on malformed successful HTTP responses but
        # not on non-200 responses. Preserve any such returned usage for audit.
        if not result.usage and isinstance(result.raw, dict) and isinstance(result.raw.get("usage"), dict):
            result.usage = result.raw["usage"].copy()
        result.raw = redact(result.raw, self.key)
        result.error = redact(result.error, self.key)
        result.request_body = redact(result.request_body, self.key)
        return result


class StreamLedger:
    def __init__(self, ledger, name):
        self.ledger, self.name = ledger, name

    def reserve(self, amount, meta=None):
        return self.ledger.reserve(amount, {**(meta or {}), "provider_stream": self.name})

    def settle(self, identifier, amount, meta=None):
        return self.ledger.settle(identifier, amount, {**(meta or {}), "provider_stream": self.name})


def create_adapter(name, key, timeout):
    config = PROVIDERS[name]
    module = importlib.import_module("jevbench.adapters." + config["kind"])
    cls = module.TypeSafeAdapter if name == "jev" else module.OpenAICompatAdapter
    inner = cls(endpoint=config["endpoint"], model=config["model"], key_env=KEY_ENV, timeout_s=timeout,
                price_input_per_m=config["input_price"], price_output_per_m=config["output_price"])
    inner.request_options = config["options"].copy()
    return BoundedAdapter(inner, config, key)


def stream(upstream, name, key, output, ledger, *, timeout=120, max_seconds=3600):
    config = PROVIDERS[name]
    adapter = create_adapter(name, key, timeout)
    bounds = [reservation(adapter.build_request(task), config) for task in upstream.tasks]
    manifest = {"provider": name, **config, "status": "running", "scope": benchmark.SCOPE,
                "upstream_commit": benchmark.UPSTREAM_COMMIT, "planned_requests": len(upstream.tasks),
                "dataset_hash": upstream.task_module.dataset_hash(upstream.tasks),
                "request_bound": {field: max(row[field] for row in bounds) for field in bounds[0]},
                "max_seconds": max_seconds, "request_timeout": timeout, "concurrency": 1, "retries": 0,
                "latency_note": "Upstream Runner full-call wall times, heterogeneous requests, no warmup. Remote HTTP and local GPU timings do not measure matched hardware.",
                "budget_note": "Full JSON wire byte count plus 4096 input framing tokens, and at most 4096 output tokens; uncached tariffs. Unknown/failed cost retains its reservation. Not a provider-side billing limit."}
    output.mkdir(parents=True, exist_ok=False)
    (output / "manifest.json").write_bytes(benchmark.json_bytes(manifest))
    runner_module = importlib.import_module("jevbench.runner")
    runner = runner_module.Runner(adapter, StreamLedger(ledger, name), output / "raw", default_reserve_usd=0)
    results = output / "results.jsonl"
    caught = None

    def expire(_signum, _frame):
        raise DeadlineReached()

    previous = signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, max_seconds)
    try:
        with scoped_key(key):
            runner.run_all(upstream.tasks, results_path=results, progress_every=50)
        manifest["status"] = "finished"
    except DeadlineReached:
        manifest["status"] = "stopped_time_limit"
    except BaseException as error:
        caught = error
        manifest.update(status="interrupted_or_failed", error_type=type(error).__name__)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        records = [benchmark.strict_json(line) for line in results.read_bytes().splitlines()] if results.exists() else []
        events = [benchmark.strict_json(line) for line in Path(ledger.path).read_bytes().splitlines()] if Path(ledger.path).exists() else []
        starts = [row for row in events if row["event"] == "reserve" and row.get("meta", {}).get("provider_stream") == name]
        summary = upstream.summary.public_export({}, upstream.tasks, records)
        failure_costs = [usage_cost(row.get("usage"), config) for row in records if not row["ok"]]
        summary.update(scope=benchmark.SCOPE, upstream_commit=benchmark.UPSTREAM_COMMIT,
                       accuracy_denominator="attempted_scorable_requests",
                       planned_accuracy=summary["n_correct"] / len(upstream.tasks),
                       dataset_hash=manifest["dataset_hash"], provider=name, requested_model=config["model"],
                       request_options=config["options"], probability_source=config["probabilities"],
                       started_requests=len(starts), pending_requests=len(upstream.tasks) - len(starts),
                       in_flight_or_unrecorded_requests=len(starts) - len(records),
                       failure_usage_cost_usd=sum(value for value in failure_costs if value is not None),
                       failures_with_unknown_usage_cost=sum(value is None for value in failure_costs),
                       budget_cost_note="Failed requests remain in the denominator. Known failure usage cost is retained separately; the shared ledger conservatively retains full reservations for failed or unknown charges.",
                       per_public_file={tier: upstream.summary.public_export({}, tasks, [
                           row for row in records if row["task_id"] in {task.id for task in tasks}])
                           for tier, tasks in upstream.tiers.items()})
        manifest.update(attempted_requests=len(records), started_requests=len(starts),
                        failed_requests=sum(not row["ok"] for row in records),
                        pending_requests=summary["pending_requests"], shared_ledger_charged_usd=ledger.charged,
                        resolved_models=summary["model_identities"],
                        model_identity_matches_requested_alias=all(model == config["model"] for model in summary["model_identities"]))
        if manifest["status"] == "finished":
            manifest["status"] = ("complete" if len(records) == len(upstream.tasks) else "stopped_partial")
        if not manifest["model_identity_matches_requested_alias"]:
            manifest["status"] = "model_identity_requires_review"
        (output / "summary.json").write_bytes(benchmark.json_bytes(summary))
        (output / "manifest.json").write_bytes(benchmark.json_bytes(manifest))
    if caught is not None:
        raise caught
    return manifest


def run(args):
    if (not math.isfinite(args.cap_usd) or args.cap_usd <= 0
            or not 0 < args.request_timeout <= 300 or not 0 < args.provider_timeout <= 86400):
        raise ValueError("Invalid finite budget or bounded timeout")
    if len(set(args.providers)) != len(args.providers):
        raise ValueError("Provider streams cannot repeat")
    upstream = benchmark.load_upstream(args.upstream)
    keys = {name: read_key(args.jev_key_file if name == "jev" else args.openai_key_file) for name in args.providers}
    output = private_output(args.output_root)
    output.mkdir(parents=True, exist_ok=False)
    ledger_path = private_output(args.ledger) if args.ledger else output / "ledger.jsonl"
    budget = importlib.import_module("jevbench.budget")
    ledger = budget.Ledger(ledger_path, cap_usd=args.cap_usd)
    if ledger_path.exists():
        prior = [benchmark.strict_json(line) for line in ledger_path.read_bytes().splitlines()]
        if any(row.get("event") == "reserve" and row.get("meta", {}).get("provider_stream") in args.providers for row in prior):
            raise ValueError("The shared ledger already contains attempts for a selected provider; no retries")
    report = {"scope": benchmark.SCOPE, "upstream_commit": benchmark.UPSTREAM_COMMIT,
              "source_sha256": benchmark.sha256(Path(__file__).read_bytes()),
              "cap_usd": args.cap_usd, "provider_order": args.providers, "providers": {}, "status": "running"}
    try:
        for name in args.providers:
            report["providers"][name] = stream(upstream, name, keys[name], output / name, ledger,
                                               timeout=args.request_timeout, max_seconds=args.provider_timeout)
            (output / "manifest.json").write_bytes(benchmark.json_bytes(report))
        report["status"] = "complete" if all(row["status"] == "complete" for row in report["providers"].values()) else "partial"
    except BaseException as error:
        report.update(status="interrupted_or_failed", error_type=type(error).__name__)
        raise
    finally:
        report["shared_ledger_charged_usd"] = ledger.charged
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        (output / "manifest.json").write_bytes(benchmark.json_bytes(report))
        keys.clear()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--jev-key-file", type=Path)
    parser.add_argument("--openai-key-file", type=Path)
    parser.add_argument("--providers", nargs="+", choices=list(PROVIDERS), default=list(PROVIDERS))
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--cap-usd", type=float, default=25)
    parser.add_argument("--request-timeout", type=float, default=120)
    parser.add_argument("--provider-timeout", type=float, default=3600)
    args = parser.parse_args(argv)
    if ("jev" in args.providers and args.jev_key_file is None) or (set(args.providers) & {"luna", "astra"} and args.openai_key_file is None):
        parser.error("Selected providers require their private key-file arguments")

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt()

    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        report = run(args)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    print(json.dumps({"status": report["status"], "cap_usd": report["cap_usd"],
                      "shared_ledger_charged_usd": report["shared_ledger_charged_usd"]}))
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
