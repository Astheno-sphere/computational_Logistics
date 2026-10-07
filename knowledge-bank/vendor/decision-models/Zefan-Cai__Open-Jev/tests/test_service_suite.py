"""CPU-only launcher regression checks; no GPU, model, or network calls."""

import argparse
from contextlib import ExitStack, redirect_stdout, redirect_stderr
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

from scripts import run_service_suite as suite


class ServiceSuiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.policy_path = self.root / "state/auto_research/resource_policy.json"
        self.policy_path.parent.mkdir(parents=True, exist_ok=True)
        self.policy_path.write_text(json.dumps({
            "expected_hostname": "allowed-node", "allowed_gpu_indices": [0, 1, 2, 3],
            "training_gpu_indices": [0, 1, 2], "serial_evaluation_gpu_index": 3,
            "prohibited_nodes": ["forbidden-node"],
        }))
        root_patch = patch.object(suite, "ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def checkpoint(self, tag):
        path = self.root / 'runs' / f'{tag}-pilot-v1' / 'checkpoint'
        path.mkdir(parents=True)
        (path / 'model.json').write_text(json.dumps({'model_id': suite.MODELS[tag], 'revision': 'abc123'}))
        (path / 'temperature.json').write_text(json.dumps({'temperature': 1.25}))
        (path / 'weights.bin').write_bytes(b'local-test-not-model-weights')
        return path

    def test_hash_and_wrong_model(self):
        path = self.checkpoint('2b')
        actual = suite.checkpoint_identity(path, '2b', 'commit')
        digest = hashlib.sha256()
        for item in sorted(path.iterdir()):
            digest.update(item.name.encode() + b'\0' + item.read_bytes())
        self.assertEqual(actual['checkpoint_sha256'], digest.hexdigest())
        (path / 'weights.bin').write_bytes(b'modified')
        self.assertNotEqual(suite.checkpoint_identity(path, '2b', 'commit'), actual)
        with self.assertRaisesRegex(ValueError, 'wrong base model'):
            suite.checkpoint_identity(path, '9b', 'commit')

    def test_bad_temperature(self):
        path = self.checkpoint('2b')
        for value in (0, -1, float('nan'), float('inf'), True):
            (path / 'temperature.json').write_text(json.dumps({'temperature': value}))
            with self.assertRaises(ValueError):
                suite.checkpoint_identity(path, '2b', 'commit')

    def test_gpu_selection_and_busy_rejection(self):
        outputs = ['GPU-target, Test Device, 0, 0\n', 'GPU-other, 99, other-job, 3000\n']
        with patch.object(suite.subprocess, 'check_output', side_effect=outputs):
            result = suite.gpu_snapshot(3)
        self.assertEqual(result['uuid'], 'GPU-target')
        self.assertEqual(result['compute_processes'], [])
        with patch.object(suite, 'gpu_snapshot', return_value=result):
            self.assertEqual(suite.require_free_gpu(3), result)
        result['compute_processes'] = [{'pid': 12}]
        with patch.object(suite, 'gpu_snapshot', return_value=result), self.assertRaisesRegex(RuntimeError, 'occupied'):
            suite.require_free_gpu(3)

    def test_probe_rejects_changed_identity_and_invalid_probability(self):
        expected = suite.checkpoint_identity(self.checkpoint('2b'), '2b', 'commit')
        response = {'model': expected['model'], 'metadata': {key: value for key, value in expected.items() if key != 'model'},
                    'answers': {'identity_probe': {'type': 'noul', 'noul': 0.75}}}
        process = Mock()
        process.poll.return_value = None
        def probe():
            with patch.object(suite, 'urlopen', return_value=io.BytesIO(json.dumps(response).encode())):
                return suite.probe_identity(process, expected)
        self.assertEqual(probe(), response)
        response['metadata']['checkpoint_sha256'] = 'wrong'
        with self.assertRaisesRegex(RuntimeError, 'does not match'):
            probe()
        response['metadata']['checkpoint_sha256'] = expected['checkpoint_sha256']
        for value in (float('nan'), float('inf'), -0.2, 1.2, True, '0.5'):
            response['answers']['identity_probe']['noul'] = value
            with self.assertRaisesRegex(RuntimeError, 'finite Noul'):
                probe()

    def test_readiness_requires_own_log(self):
        path = self.root / 'server.log'
        path.write_text('unrelated startup\n')
        self.assertFalse(suite.ready_line(path, suite.MODELS['2b']))
        path.write_text(json.dumps({'url': suite.BASE, 'model': suite.MODELS['2b'], 'method': suite.METHOD}) + '\n')
        self.assertTrue(suite.ready_line(path, suite.MODELS['2b']))
        self.assertFalse(suite.ready_line(path, suite.MODELS['9b']))
        process = Mock()
        process.poll.return_value = 9
        process.returncode = 9
        with patch.object(suite, 'urlopen') as request, self.assertRaisesRegex(RuntimeError, 'server exited 9'):
            suite.wait_ready(process, path, {'model': suite.MODELS['2b']}, 1)
        request.assert_not_called()

    def test_command_workloads(self):
        args = argparse.Namespace(include_doom=True, workflow_cases=Path('cases'), frontier_source=Path('frontier'),
                                  measurements=list(suite.MEASUREMENTS))
        commands = dict(suite.measurement_commands(args, Path('output'), suite.MODELS['2b'], Path('checkpoint')))
        self.assertEqual(list(commands), ['demo_requests', 'workflows', 'frontier_100', 'games'])
        self.assertIn('--include-doom', commands['games'])
        self.assertEqual(commands['games'][commands['games'].index('--doom-decision-mode') + 1], 'combined-v1')
        self.assertIn('10001,10002,10003', commands['games'])
        self.assertIn('40', commands['games'])
        self.assertIn('12', commands['workflows'])
        self.assertIn('ood', commands['workflows'])
        for name in ('workflows', 'frontier_100', 'games'):
            self.assertIn(suite.MODELS['2b'], commands[name])
            self.assertIn(suite.METHOD, commands[name])

    def test_typed_doom_mode_reaches_game_evaluator(self):
        args = argparse.Namespace(include_doom=True, doom_decision_mode='typed-v1',
                                  workflow_cases=Path('cases'), frontier_source=Path('frontier'),
                                  measurements=['games'])
        command = dict(suite.measurement_commands(args, Path('output'), suite.MODELS['2b'], Path('checkpoint')))['games']
        self.assertEqual(command[command.index('--doom-decision-mode') + 1], 'typed-v1')

    def test_control_commands_pin_full_identity_and_complete_splits(self):
        args = argparse.Namespace(include_doom=False, workflow_cases=Path('unused'), frontier_source=Path('unused'),
                                  control_data_root=Path('frozen-controls'), measurements=['amount', 'contact'])
        identity = {'base_revision': 'base-revision', 'checkpoint_sha256': 'checkpoint-digest', 'temperature': 1.25}
        commands = dict(suite.measurement_commands(args, Path('output'), suite.MODELS['2b'], Path('checkpoint'), identity=identity))
        self.assertEqual(list(commands), ['contact', 'amount'])
        for name, command in commands.items():
            self.assertEqual(command[:3], [sys.executable, '-m', f'scripts.evaluate_{name}_service'])
            for flag, value in (('--endpoint', suite.ENDPOINT), ('--expected-model', suite.MODELS['2b']),
                                ('--expected-method', suite.METHOD), ('--expected-revision', 'base-revision'),
                                ('--expected-checkpoint-sha256', 'checkpoint-digest'), ('--expected-temperature', '1.25'),
                                ('--data-root', 'frozen-controls'), ('--output-dir', str(Path('output') / name))):
                self.assertEqual(command[command.index(flag) + 1], value)
            self.assertEqual(command[command.index('--splits') + 1:command.index('--splits') + 3], ['test', 'ood'])
            self.assertNotIn('--limit', command)
        contact = commands['contact']
        self.assertEqual(contact[contact.index('--corpora') + 1:contact.index('--corpora') + 3], ['email', 'phone'])
        self.assertNotIn('--corpora', commands['amount'])

    def test_control_preflight_is_opt_in_and_uses_existing_frozen_loaders(self):
        with patch('scripts.evaluate_contact_service.phone_library') as phone, \
                patch('scripts.evaluate_contact_service.load_cases', return_value=([{}, {}], {'email': 'evidence'})) as contact, \
                patch('scripts.evaluate_amount_service.load_cases', return_value=([{}], {'amount': 'evidence'})) as amount:
            self.assertEqual(suite.preflight_control_inputs(argparse.Namespace(measurements=suite.MEASUREMENTS)), {})
            phone.assert_not_called()
            contact.assert_not_called()
            amount.assert_not_called()
            args = argparse.Namespace(measurements=['amount'], control_data_root=self.root)
            self.assertEqual(suite.preflight_control_inputs(args), {'amount': {'selected_cases': 1, 'inputs': {'amount': 'evidence'}}})
            phone.assert_not_called()
            contact.assert_not_called()
            amount.assert_called_once_with(self.root, ('test', 'ood'))
            args.measurements = ['contact']
            self.assertEqual(suite.preflight_control_inputs(args), {'contact': {'selected_cases': 2, 'inputs': {'email': 'evidence'}}})
            phone.assert_called_once_with()
            contact.assert_called_once_with(self.root, ('email', 'phone'), ('test', 'ood'))

    def test_control_preflight_failure_precedes_output_gpu_and_subprocesses(self):
        for measurement, phone_error in (('contact', RuntimeError('pinned phone library missing')), ('contact', None), ('amount', None)):
            with patch.object(suite.socket, 'gethostname', return_value='allowed-node'), \
                    patch.object(suite, 'gpu_snapshot') as gpu, \
                    patch.object(suite, 'require_free_gpu') as free, \
                    patch.object(suite.subprocess, 'Popen') as spawn, \
                    patch.object(suite.subprocess, 'check_output') as command, \
                    patch('scripts.evaluate_contact_service.phone_library', side_effect=phone_error), \
                    patch('scripts.evaluate_contact_service.load_cases', side_effect=ValueError('changed frozen contact input')), \
                    patch('scripts.evaluate_amount_service.load_cases', side_effect=ValueError('changed frozen amount input')), \
                    redirect_stderr(io.StringIO()) as errors:
                with self.assertRaises(SystemExit) as raised:
                    suite.main(['--expected-hostname', 'allowed-node', '--output-root', str(self.root / 'output'),
                                '--measurements', measurement, '--control-data-root', str(self.root / 'controls')])
                self.assertEqual(raised.exception.code, 2)
                self.assertIn('control preflight failed', errors.getvalue())
            self.assertFalse((self.root / 'output').exists())
            gpu.assert_not_called()
            free.assert_not_called()
            spawn.assert_not_called()
            command.assert_not_called()

    def provider_fixture(self, *, duplicate=False, wrong_keys=False, question=None):
        from jev.api import compile_request
        from scripts.benchmark_inference_latency import digest
        directory = self.root / "providers" / "fixture"
        directory.mkdir(parents=True, exist_ok=True)
        request = {"state": "The lamp is on.", "questions": {
            "decision": question or {"type": "noul", "instructions": "Is the lamp on?"}}}
        compiled = compile_request(request["state"], request["questions"])[0]
        workload = {"id": "case", "request": request, "request_sha256": digest(request)}
        gold = {"request_id": "case", "question_id": "decision", "request_sha256": digest(request),
                "kind": compiled["kind"], "answer_keys": ["wrong"] if wrong_keys else compiled["answer_keys"],
                "target": 1, "source": "fixture", "split": "test", "group_id": "fixture"}
        workloads, golds = [workload] * (2 if duplicate else 1), [gold]
        files = {}
        for filename, document in (("requests.json", {"schema_version": 1, "workloads": workloads}),
                                   ("gold.json", {"rows": golds})):
            raw = json.dumps(document).encode()
            (directory / filename).write_bytes(raw)
            files[filename] = hashlib.sha256(raw).hexdigest()
        raw = json.dumps({"files": files}).encode()
        (directory / "manifest.json").write_bytes(raw)
        spec = (("coverage", "fixture", len(workloads), 1, hashlib.sha256(raw).hexdigest()),)
        args = argparse.Namespace(measurements=["provider_quality"], provider_data_root=directory.parent)
        return args, spec, workload

    def test_provider_preflight_pins_manifests_files_and_gold_alignment(self):
        self.assertEqual(suite.preflight_provider_inputs(argparse.Namespace(measurements=suite.MEASUREMENTS)), {})
        args, spec, _ = self.provider_fixture()
        with patch.object(suite, "PROVIDER_SUITES", spec):
            evidence = suite.preflight_provider_inputs(args)
            self.assertEqual(evidence["coverage"]["requests"], 1)
            self.assertEqual(evidence["coverage"]["labelled_decisions"], 1)
            path = args.provider_data_root / "fixture" / "gold.json"
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "frozen gold.json differs"):
                suite.preflight_provider_inputs(args)
        for kwargs, message in (({"duplicate": True}, "duplicate request"), ({"wrong_keys": True}, "candidate order")):
            args, spec, _ = self.provider_fixture(**kwargs)
            with patch.object(suite, "PROVIDER_SUITES", spec), self.assertRaisesRegex(ValueError, message):
                suite.preflight_provider_inputs(args)

    def test_provider_preflight_rejection_precedes_output_gpu_and_children(self):
        args, spec, _ = self.provider_fixture()
        (args.provider_data_root / "fixture" / "manifest.json").write_text("{}")
        with patch.object(suite, "PROVIDER_SUITES", spec), \
                patch.object(suite.socket, "gethostname", return_value="allowed-node"), \
                patch.object(suite, "gpu_snapshot") as gpu, patch.object(suite, "require_free_gpu") as free, \
                patch.object(suite.subprocess, "Popen") as spawn, patch.object(suite.subprocess, "check_output") as command, \
                redirect_stderr(io.StringIO()) as errors, self.assertRaises(SystemExit):
            suite.main(["--expected-hostname", "allowed-node", "--output-root", str(self.root / "output"),
                        "--measurements", "provider_quality", "--provider-data-root", str(args.provider_data_root)])
        self.assertIn("provider preflight failed", errors.getvalue())
        self.assertFalse((self.root / "output").exists())
        for call in (gpu, free, spawn, command):
            call.assert_not_called()

    def test_provider_commands_keep_gold_out_of_inference_and_pin_identity(self):
        args, spec, _ = self.provider_fixture()
        args.include_doom, args.workflow_cases, args.frontier_source = False, Path("unused"), Path("unused")
        identity = suite.checkpoint_identity(self.checkpoint("2b"), "2b", "commit", max_length=16384)
        with patch.object(suite, "PROVIDER_SUITES", spec):
            inputs = suite.preflight_provider_inputs(args)
            commands = suite.measurement_commands(args, Path("output"), suite.MODELS["2b"], Path("checkpoint"),
                                                  identity=identity, provider_inputs=inputs)
        self.assertEqual(len(commands), 1)
        phase, command = commands[0]
        self.assertEqual(phase, "provider_quality_coverage")
        self.assertEqual(command[:3], [sys.executable, "-m", "scripts.evaluate_openjev_provider"])
        for key in ("model", "method", "base_revision", "checkpoint_sha256", "temperature", "code_commit", "max_length"):
            flag = "--expected-" + key.replace("_", "-")
            self.assertEqual(command[command.index(flag) + 1], str(identity[key]))
        self.assertEqual(command[command.index("--input-sha256") + 1], inputs["coverage"]["files"]["requests.json"]["sha256"])
        self.assertFalse(any("gold" in value for value in command))
        self.assertNotIn("--warmup", command)

    def test_provider_summary_rechecks_raw_identity_and_retains_partial_denominator(self):
        from scripts import evaluate_openjev_provider as client
        args, spec, workload = self.provider_fixture()
        with patch.object(suite, "PROVIDER_SUITES", spec):
            frozen = suite.preflight_provider_inputs(args)["coverage"]
        expected = suite.checkpoint_identity(self.checkpoint("2b"), "2b", "commit", max_length=16384)
        response = {"model": expected["model"], "metadata": {**{k: v for k, v in expected.items() if k != "model"},
                    "prefix_cache": {"enabled": False}}, "usage": {"input_tokens": 10},
                    "answers": {"decision": {"type": "noul", "noul": .9}}}
        sample = {"request_id": "case", "request_sha256": workload["request_sha256"], "phase": "measured",
                  "repetition": 0, "mode": expected["model"], "success": True, "http_status": 200,
                  "raw_response": json.dumps(response), "response": response}
        report = {"status": "complete", "expected_identity": expected,
                  "input_sha256": frozen["files"]["requests.json"]["sha256"], "planned_requests": 1,
                  "attempted_requests": 1, "successful_requests": 1, "failed_requests": 0, "pending_requests": 0,
                  "started_requests": 1, "in_flight_requests": 0,
                  "source_sha256": hashlib.sha256(Path(client.__file__).read_bytes()).hexdigest(),
                  "concurrency": 1, "warmups": 0, "retries": 0, "prefix_cache": False}
        output = self.root / "collected"
        output.mkdir()
        (output / "requests.json").write_bytes((Path(frozen["directory"]) / "requests.json").read_bytes())
        (output / "report.json").write_text(json.dumps(report))
        (output / "samples.jsonl").write_text(json.dumps(sample) + "\n")
        attempt = {"event": "attempt_started", "request_id": "case", "request_sha256": workload["request_sha256"],
                   "started_at": "2026-09-21T00:00:00+00:00"}
        (output / "attempts.jsonl").write_text(json.dumps(attempt) + "\n")
        actual = suite.summarize_provider_output(output, frozen, expected)
        self.assertEqual(actual["overall"]["hard_correct"], 1)
        self.assertEqual(actual["pending_count"], 0)
        self.assertEqual(json.loads((output / "quality.json").read_bytes())["journal_sha256"],
                         hashlib.sha256((output / "attempts.jsonl").read_bytes()).hexdigest())
        with self.assertRaises(FileExistsError):
            suite.summarize_provider_output(output, frozen, expected)
        (output / "quality.json").unlink()
        sample["response"]["metadata"]["temperature"] = 2
        (output / "samples.jsonl").write_text(json.dumps(sample) + "\n")
        with self.assertRaisesRegex(ValueError, "raw response differs"):
            suite.summarize_provider_output(output, frozen, expected)
        report.update(status="stopped_budget", attempted_requests=0, successful_requests=0, pending_requests=1,
                      started_requests=0)
        (output / "report.json").write_text(json.dumps(report))
        (output / "samples.jsonl").write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "dispatch journal"):
            suite.summarize_provider_output(output, frozen, expected)
        self.assertFalse((output / "quality.json").exists())
        (output / "attempts.jsonl").write_bytes(b"")
        partial = suite.summarize_provider_output(output, frozen, expected)
        self.assertEqual(partial["quality_status"], "partial")
        self.assertEqual(partial["pending_count"], 1)
        self.assertEqual(partial["overall"]["evaluated"], 0)

    def test_provider_raw_binding_preserves_types_order_and_strict_decoding(self):
        from scripts import evaluate_openjev_provider as client
        args, spec, workload = self.provider_fixture(question={
            "type": "choice", "instructions": "Select the lamp state.",
            "criteria": {"off": "The lamp is off.", "on": "The lamp is on."}})
        with patch.object(suite, "PROVIDER_SUITES", spec):
            frozen = suite.preflight_provider_inputs(args)["coverage"]
        expected = suite.checkpoint_identity(self.checkpoint("2b"), "2b", "commit", max_length=16384)
        response = {"model": expected["model"], "metadata": {
            **{k: v for k, v in expected.items() if k != "model"}, "prefix_cache": {"enabled": False}},
            "usage": {"input_tokens": 10}, "answers": {"decision": {
                "type": "choice", "choice": "on", "probabilities": {"off": 0.0, "on": 1.0}}}}
        sample = {"request_id": "case", "request_sha256": workload["request_sha256"], "phase": "measured",
                  "repetition": 0, "mode": expected["model"], "success": True, "http_status": 200,
                  "raw_response": json.dumps(response), "response": response}
        report = {"status": "complete", "expected_identity": expected,
                  "input_sha256": frozen["files"]["requests.json"]["sha256"], "planned_requests": 1,
                  "attempted_requests": 1, "successful_requests": 1, "failed_requests": 0, "pending_requests": 0,
                  "started_requests": 1, "in_flight_requests": 0,
                  "source_sha256": hashlib.sha256(Path(client.__file__).read_bytes()).hexdigest(),
                  "concurrency": 1, "warmups": 0, "retries": 0, "prefix_cache": False}
        output = self.root / "collected"
        output.mkdir()
        (output / "requests.json").write_bytes((Path(frozen["directory"]) / "requests.json").read_bytes())
        (output / "report.json").write_text(json.dumps(report))
        (output / "attempts.jsonl").write_text(json.dumps({"event": "attempt_started", "request_id": "case",
            "request_sha256": workload["request_sha256"]}) + "\n")
        (output / "samples.jsonl").write_text(json.dumps(sample) + "\n")
        self.assertEqual(suite.summarize_provider_output(output, frozen, expected)["overall"]["hard_correct"], 1)
        (output / "quality.json").unlink()
        for probabilities in ({"off": False, "on": 1.0}, {"off": 0, "on": 1.0}, {"on": 1.0, "off": 0.0}):
            with self.subTest(raw_probabilities=probabilities):
                raw_response = json.loads(json.dumps(response))
                raw_response["answers"]["decision"]["probabilities"] = probabilities
                # All three mutations compare equal as Python dictionaries.
                self.assertEqual(raw_response, response)
                sample["raw_response"] = json.dumps(raw_response)
                (output / "samples.jsonl").write_text(json.dumps(sample) + "\n")
                with self.assertRaisesRegex(ValueError, "raw response differs"):
                    suite.summarize_provider_output(output, frozen, expected)
                self.assertFalse((output / "quality.json").exists())
        sample["raw_response"] = json.dumps(response).replace('"model":', '"model":"duplicate","model":', 1)
        (output / "samples.jsonl").write_text(json.dumps(sample) + "\n")
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            suite.summarize_provider_output(output, frozen, expected)
        self.assertFalse((output / "quality.json").exists())

    def trec_fixture(self):
        from scripts.evaluate_trec_provider import PROTOCOL
        root = self.root / "external-trec"
        root.mkdir(exist_ok=True)
        queries, manifests = [], {}
        for benchmark, count in (("dl19", 43), ("dl20", 54)):
            directory = root / benchmark
            directory.mkdir(exist_ok=True)
            candidates, qrels = [], []
            for index in range(count):
                identifier = str(index)
                documents = [{"id": str(rank), "text": "A passage."} for rank in range(100)]
                queries.append({"benchmark": benchmark, "id": identifier, "query": "A query.", "documents": documents})
                candidates.append({"id": identifier, "query": "A query.", "documents": [
                    {**document, "bm25_rank": rank, "bm25_score": 100 - rank}
                    for rank, document in enumerate(documents, 1)]})
                qrels.extend((f"{identifier} 0 0 3", f"{identifier} 0 outside-top100 2"))
            (directory / "candidates.jsonl").write_text("\n".join(json.dumps(row) for row in candidates) + "\n")
            (directory / "qrels.txt").write_text("\n".join(qrels) + "\n")
            manifest = {"usage": "evaluation_only", "benchmark": "TREC-" + benchmark.upper(),
                        "retriever": {"name": "BM25", "top_k": 100, "k1": .9, "b": .4},
                        "files_sha256": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                                         for name in ("candidates.jsonl", "qrels.txt")}}
            raw = json.dumps(manifest).encode()
            (directory / "manifest.json").write_bytes(raw)
            manifests[benchmark] = hashlib.sha256(raw).hexdigest()
        input_path = root / "input.json"
        input_path.write_text(json.dumps({"schema_version": 1, "usage": "evaluation_only", "protocol": PROTOCOL,
                                         "queries": queries}))
        args = argparse.Namespace(measurements=["trec"], trec_input=input_path, trec_holdout_root=root,
                                  output_root=self.root / "output")
        return args, hashlib.sha256(input_path.read_bytes()).hexdigest(), manifests

    def test_trec_preflight_is_opt_in_and_binds_full_input_and_qrels(self):
        self.assertEqual(suite.preflight_trec_inputs(argparse.Namespace(measurements=suite.MEASUREMENTS)), {})
        args, digest, manifests = self.trec_fixture()
        with patch("scripts.summarize_trec_provider.INPUT_SHA256", digest), \
                patch("scripts.summarize_trec_provider.MANIFEST_SHA256", manifests):
            evidence = suite.preflight_trec_inputs(args)
            self.assertEqual(evidence["queries"], 97)
            self.assertEqual(evidence["planned_max_requests"], 873)
            self.assertEqual(evidence["input_sha256"], digest)
            self.assertEqual([row["queries"] for row in evidence["holdouts"].values()], [43, 54])
            path = args.trec_holdout_root / "dl20/qrels.txt"
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "checksum differs"):
                suite.preflight_trec_inputs(args)

    def test_trec_preflight_bad_hashes_precede_output_gpu_and_children(self):
        args, digest, manifests = self.trec_fixture()
        for path in (args.trec_input, args.trec_holdout_root / "dl19/manifest.json"):
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            with patch("scripts.summarize_trec_provider.INPUT_SHA256", digest), \
                    patch("scripts.summarize_trec_provider.MANIFEST_SHA256", manifests), \
                    patch.object(suite.socket, "gethostname", return_value="allowed-node"), \
                    patch.object(suite, "gpu_snapshot") as gpu, patch.object(suite, "require_free_gpu") as free, \
                    patch.object(suite.subprocess, "Popen") as spawn, patch.object(suite.subprocess, "check_output") as command, \
                    redirect_stderr(io.StringIO()) as errors, self.assertRaises(SystemExit):
                suite.main(["--expected-hostname", "allowed-node", "--output-root", str(args.output_root),
                            "--measurements", "trec", "--max-length", "16384", "--trec-input", str(args.trec_input),
                            "--trec-holdout-root", str(args.trec_holdout_root)])
            self.assertIn("TREC preflight failed", errors.getvalue())
            self.assertFalse(args.output_root.exists())
            for call in (gpu, free, spawn, command):
                call.assert_not_called()
            path.write_bytes(original)

    def test_trec_inputs_and_outputs_cannot_enter_training_tree(self):
        args, _, _ = self.trec_fixture()
        for attribute in ("trec_input", "trec_holdout_root", "output_root"):
            original = getattr(args, attribute)
            for tree in ("data", "train"):
                setattr(args, attribute, self.root / tree / "external")
                with self.assertRaisesRegex(ValueError, "outside data/train"):
                    suite.preflight_trec_inputs(args)
            setattr(args, attribute, original)
        args.trec_input = None
        with self.assertRaisesRegex(ValueError, "trec-input is required"):
            suite.preflight_trec_inputs(args)

    def test_trec_commands_pin_identity_and_never_pass_qrels(self):
        args = argparse.Namespace(include_doom=False, workflow_cases=Path("unused"), frontier_source=Path("unused"),
                                  measurements=["trec"])
        identity = suite.checkpoint_identity(self.checkpoint("2b"), "2b", "commit", max_length=16384)
        inputs = {"input": "/external/input.json", "input_sha256": "a" * 64,
                  "holdouts": {"dl19": {"manifest": "/private-qrels/manifest.json"}}}
        commands = suite.measurement_commands(args, Path("output"), suite.MODELS["2b"], Path("checkpoint"),
                                             identity=identity, trec_inputs=inputs)
        self.assertEqual(len(commands), 1)
        phase, command = commands[0]
        self.assertEqual(phase, "trec")
        self.assertEqual(command[:3], [sys.executable, "-m", "scripts.evaluate_openjev_trec"])
        for key, value in identity.items():
            self.assertEqual(command[command.index("--expected-" + key.replace("_", "-")) + 1], str(value))
        self.assertEqual(command[command.index("--input") + 1], inputs["input"])
        self.assertEqual(command[command.index("--input-sha256") + 1], inputs["input_sha256"])
        self.assertEqual(command[command.index("--output") + 1], "output/trec")
        self.assertFalse(any("qrel" in value or "gold" in value or "holdout" in value for value in command))
        self.assertNotIn("--max-requests", command)

    def test_trec_summary_requires_settled_identity_and_offline_audit(self):
        expected = suite.checkpoint_identity(self.checkpoint("2b"), "2b", "commit", max_length=16384)
        output = self.root / "trec-output"
        output.mkdir()
        frozen = {"input_sha256": "a" * 64, "holdouts": {name: {"manifest": f"/{name}/manifest.json"}
                                                           for name in ("dl19", "dl20")}}
        report = {"expected_identity": expected, "input_sha256": frozen["input_sha256"],
                  "status": "complete", "in_flight_requests": 0}
        for update in ({"status": "running"}, {"status": "unknown"}, {"in_flight_requests": 1},
                       {"expected_identity": {}}, {"input_sha256": "b" * 64}):
            (output / "report.json").write_text(json.dumps({**report, **update}))
            with patch("scripts.summarize_openjev_trec.summarize") as audit, self.assertRaisesRegex(ValueError, "in-flight"):
                suite.summarize_trec_output(output, frozen, expected)
            audit.assert_not_called()
            self.assertFalse((output / "summary.json").exists())
        for status in ("complete", "completed_with_query_failures", "stopped_budget", "stopped_fatal", "interrupted_or_failed"):
            raw = json.dumps({**report, "status": status}).encode()
            (output / "report.json").write_bytes(raw)
            quality = {"status": "complete" if status.startswith("complete") else "partial", "runner_status": status,
                       "expected_identity": expected, "input_and_raw_sha256": {"report.json": hashlib.sha256(raw).hexdigest()},
                       "qrel_query_denominator": 97, "benchmarks": {}}
            with patch("scripts.summarize_openjev_trec.summarize", side_effect=ValueError("unsettled journal")), \
                    self.assertRaisesRegex(ValueError, "unsettled journal"):
                suite.summarize_trec_output(output, frozen, expected)
            self.assertFalse((output / "summary.json").exists())
            with patch("scripts.summarize_openjev_trec.summarize", return_value=quality) as audit:
                result = suite.summarize_trec_output(output, frozen, expected)
                self.assertEqual(result["collection_status"], status)
                self.assertEqual(result["qrel_query_denominator"], 97)
                audit.assert_called_once_with(output, {name: Path(f"/{name}/manifest.json") for name in ("dl19", "dl20")})
                with self.assertRaises(FileExistsError):
                    suite.summarize_trec_output(output, frozen, expected)
            (output / "summary.json").unlink()

    def test_cli_guard_before_gpu_and_children(self):
        for extra in (["--expected-hostname", "different-node"],
                      ["--expected-hostname", "unallocated-node", "--gpu", "0"],
                      ["--expected-hostname", "unallocated-node"]):
            with patch.object(suite.socket, "gethostname", return_value="unallocated-node"), \
                    patch.object(suite, "gpu_snapshot") as gpu, \
                    patch.object(suite.subprocess, "Popen") as spawn, redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    suite.main([*extra, "--output-root", str(self.root / "output")])
                self.assertEqual(raised.exception.code, 2)
            gpu.assert_not_called()
            spawn.assert_not_called()

    def test_binding_policy_cannot_override_hostname_or_training_card(self):
        policy_path = self.root / 'state/auto_research/resource_policy.json'
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy = {'expected_hostname': 'allowed-node', 'allowed_gpu_indices': [0, 1, 2, 3],
                  'training_gpu_indices': [0, 1, 2], 'serial_evaluation_gpu_index': 3,
                  'prohibited_nodes': ['forbidden-node']}
        policy_path.write_text(json.dumps(policy))
        with patch.object(suite, 'ROOT', self.root):
            with patch.object(suite.socket, 'gethostname', return_value='allowed-node'):
                result = suite.enforce_resource_policy(3, 'allowed-node')
                self.assertEqual(result['sha256'], hashlib.sha256(policy_path.read_bytes()).hexdigest())
                with self.assertRaises(ValueError):
                    suite.enforce_resource_policy(3, 'arbitrary-node')
                with self.assertRaises(ValueError):
                    suite.enforce_resource_policy(0, 'allowed-node')
            with patch.object(suite.socket, 'gethostname', return_value='arbitrary-node'), self.assertRaises(ValueError):
                suite.enforce_resource_policy(3, 'arbitrary-node')

    def test_nan_timeout_rejected_on_authorized_host(self):
        for flag in ('--startup-timeout', '--measurement-timeout'):
            with patch.object(suite.socket, 'gethostname', return_value='allowed-node'), \
                 patch.object(suite, 'gpu_snapshot') as gpu, patch.object(suite.subprocess, 'Popen') as spawn, \
                 redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    suite.main(['--expected-hostname', 'allowed-node', '--output-root', str(self.root / 'output'), flag, 'nan'])
                self.assertEqual(raised.exception.code, 2)
            gpu.assert_not_called()
            spawn.assert_not_called()

    def test_nonpositive_server_capacity_rejected_before_gpu_or_spawn(self):
        for flag in ("--max-length", "--batch-size"):
            for value in ("0", "-1"):
                with patch.object(suite.socket, "gethostname", return_value="allowed-node"), \
                        patch.object(suite, "gpu_snapshot") as gpu, \
                        patch.object(suite.subprocess, "Popen") as spawn, redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        suite.main(["--expected-hostname", "allowed-node", "--output-root",
                                    str(self.root / "output"), flag, value])
                    self.assertEqual(raised.exception.code, 2)
                gpu.assert_not_called()
                spawn.assert_not_called()

    def test_measurement_exit_and_live_pid_record(self):
        updates, record = [], {}
        result = suite.run_measurement([sys.executable, '-c', 'raise SystemExit(7)'], self.root / 'fail.log', os.environ, 5,
                                       record=record, update=lambda: updates.append(dict(record)))
        self.assertIs(result, record)
        self.assertEqual(record['exit_code'], 7)
        self.assertEqual(record['child_exit_code'], 7)
        self.assertIn('pid', updates[0])
        self.assertNotIn('exit_code', updates[0])
        self.assertIn('ended_at_utc', updates[-1])

    def test_measurement_timeout_reaps_own_child(self):
        record = suite.run_measurement([sys.executable, '-c', 'import time; time.sleep(5)'], self.root / 'timeout.log', os.environ, 0.05)
        self.assertEqual(record['exit_code'], 124)
        self.assertTrue(record['timeout'])
        self.assertEqual(record['child_exit_code'], -signal.SIGTERM)
        with self.assertRaises(ProcessLookupError):
            os.kill(record['pid'], 0)

    def test_measurement_interrupt_recorded_and_reaped(self):
        process = Mock()
        process.pid = 123
        process.poll.return_value = None
        process.wait.side_effect = [KeyboardInterrupt('test interruption'), -15, -15]
        updates, record = [], {}
        with patch.object(suite.subprocess, 'Popen', return_value=process), self.assertRaises(KeyboardInterrupt):
            suite.run_measurement(['test-child'], self.root / 'interrupt.log', {}, 5,
                                  record=record, update=lambda: updates.append(dict(record)))
        self.assertEqual(record['exit_code'], 130)
        self.assertEqual(record['child_exit_code'], -15)
        self.assertEqual(record['error_type'], 'KeyboardInterrupt')
        process.terminate.assert_called_once()
        self.assertEqual(len(updates), 2)

    def test_existing_measurement_logs_not_overwritten(self):
        path = self.root / 'old.log'
        path.write_text('keep')
        with patch.object(suite.subprocess, 'Popen') as spawn, self.assertRaises(FileExistsError):
            suite.run_measurement(['test-child'], path, {}, 5)
        spawn.assert_not_called()
        self.assertEqual(path.read_text(), 'keep')

    def run_main_mocked(self, *, mismatch=False, capacity=None, measurements=None, include_latency=True, models=None,
                        control_data_root=None, provider_data_root=None, trec_input=None,
                        failure_phases=('workflows',), expected_error=None):
        for tag in suite.MODELS if models is None else models:
            self.checkpoint(tag)
        frontier = self.root / 'frontier'
        if measurements is None or 'frontier_100' in measurements:
            frontier.mkdir()
        cases = self.root / 'cases.jsonl'
        if measurements is None or "workflows" in measurements:
            cases.write_text('{}\n')
        browser_cases = self.root / 'browser_cases.jsonl'
        if measurements is not None and "browser" in measurements:
            browser_cases.write_text('{}\n')
        drone_cases = self.root / 'drone_cases.jsonl'
        if measurements is not None and "drone" in measurements:
            drone_cases.write_text('{}\n')
        request = self.root / 'request.json'
        request.write_text('{}\n')
        output = self.root / 'output'
        active, servers, phases, envs = [], [], [], []
        snapshot = {'physical_gpu': 3, 'uuid': 'GPU-physical-three', 'name': 'Test GPU', 'memory_used_mib': 0,
                    'utilization_percent': 0, 'compute_processes': []}
        class Server:
            def __init__(inner, command, **kwargs):
                self.assertFalse(active)
                inner.command = command
                inner.pid = 1000 + len(servers)
                inner.returncode = None
                active.append(inner)
                servers.append(inner)
                envs.append(kwargs['env'].copy())
            def poll(inner):
                return inner.returncode
            def terminate(inner):
                inner.returncode = -15
                active.remove(inner)
            def wait(inner, timeout=None):
                return inner.returncode
            def kill(inner):
                raise AssertionError('normal cleanup should not need kill')
        def free(gpu, **kwargs):
            self.assertEqual(gpu, 3)
            self.assertFalse(active)
            return snapshot.copy()
        def loaded(gpu):
            self.assertEqual(gpu, 3)
            return {**snapshot, 'compute_processes': [{'pid': active[0].pid}]}
        probe_count = [0]
        expected = {}
        def probe(server, identity):
            self.assertIn(server, active)
            probe_count[0] += 1
            if expected_error and phases:
                raise AssertionError('stopped provider collection must not probe the server again')
            if mismatch and probe_count[0] == 2:
                raise RuntimeError('test identity mismatch')
            expected.clear()
            expected.update(identity)
            return {'model': identity['model'], 'metadata': {k: v for k, v in identity.items() if k != 'model'}}
        def measure(command, log, env, timeout, *, record, update):
            phase = log.stem
            if phase == 'latency':
                self.assertFalse(active)
            else:
                self.assertEqual(len(active), 1)
            self.assertEqual(env['CUDA_VISIBLE_DEVICES'], 'GPU-physical-three')
            phases.append(phase)
            record.update(command=command, pid=2000 + len(phases), exit_code=7 if phase in failure_phases else 0)
            update()
            if phase == 'demo_requests':
                response = {'model': expected['model'], 'metadata': {k: v for k, v in expected.items() if k != 'model'}}
                log.with_suffix('.jsonl').write_text(json.dumps({'response': response}) + '\n')
            return record
        args = ['--expected-hostname', 'allowed-node', '--checkpoint-root', str(self.root / 'runs'),
                '--frontier-source', str(frontier), '--workflow-cases', str(cases),
                '--browser-cases', str(browser_cases), '--drone-cases', str(drone_cases), '--output-root', str(output)]
        if include_latency:
            args.extend(["--include-latency", "--latency-request", str(request)])
        if capacity:
            args.extend(["--max-length", str(capacity[0]), "--batch-size", str(capacity[1])])
        if measurements is not None:
            args.extend(["--measurements", *measurements])
        if models is not None:
            args.extend(["--models", *models])
        if control_data_root is not None:
            args.extend(["--control-data-root", str(control_data_root)])
        if provider_data_root is not None:
            args.extend(["--provider-data-root", str(provider_data_root)])
        if trec_input is not None:
            args.extend(["--trec-input", str(trec_input)])
        with ExitStack() as stack:
            for name, value in [('require_free_gpu', free), ('gpu_snapshot', loaded), ('require_free_port', Mock()),
                                ('wait_ready', Mock(return_value={'status': 'ready'})), ('probe_identity', probe), ('run_measurement', measure)]:
                stack.enter_context(patch.object(suite, name, value))
            stack.enter_context(patch.object(suite.subprocess, 'Popen', Server))
            stack.enter_context(patch.object(suite.subprocess, 'check_output', return_value='test-commit\n'))
            stack.enter_context(patch.object(suite.socket, 'gethostname', return_value='allowed-node'))
            # Never acquire or overwrite the live launcher's advisory lock.
            stack.enter_context(patch.object(suite, "open", create=True,
                                            side_effect=lambda *args, **kwargs: (self.root / "suite.lock").open("a+")))
            stack.enter_context(patch.object(suite.signal, 'signal'))
            stack.enter_context(redirect_stdout(io.StringIO()))
            if mismatch or expected_error:
                with self.assertRaisesRegex(RuntimeError, expected_error or 'test identity mismatch'):
                    suite.main(args)
            else:
                result = suite.main(args)
                self.assertEqual(result, int(bool(set(phases) & set(failure_phases))))
            manifest = json.loads((output / 'manifest.json').read_text())
            count = len(servers)
            with self.assertRaises(FileExistsError):
                suite.main(args)
            self.assertEqual(len(servers), count)
        self.assertFalse(active)
        self.assertTrue(all(server.returncode == -15 for server in servers))
        self.assertTrue(all(env['HF_HUB_OFFLINE'] == env['TRANSFORMERS_OFFLINE'] == '1' for env in envs))
        self.assertTrue(all(env['CUDA_VISIBLE_DEVICES'] == snapshot['uuid'] for env in envs))
        return manifest, servers, phases

    def test_three_models_serial_semantic_failure_continues_latency_last(self):
        manifest, servers, measurements = self.run_main_mocked()
        self.assertEqual(len(servers), 3)
        self.assertEqual(measurements, ['demo_requests', 'workflows', 'frontier_100', 'games'] * 3 + ['latency'])
        self.assertEqual(manifest['status'], 'complete_with_measurement_failures')
        self.assertEqual(manifest['current_phase'], 'finished')
        self.assertEqual(manifest['child_cuda_visible_devices'], 'GPU-physical-three')
        self.assertEqual(set(manifest['models']), {'2b', '9b', '27b'})
        self.assertNotIn('control_inputs', manifest)
        self.assertNotIn('provider_inputs', manifest)
        self.assertNotIn('trec_inputs', manifest)

    def test_trec_models_are_serial_and_failed_queries_keep_cleanup(self):
        inputs = {"input": "/external/input.json", "input_sha256": "a" * 64}
        with patch.object(suite, "preflight_trec_inputs", return_value=inputs), \
                patch.object(suite, "summarize_trec_output", return_value={"collection_status": "completed_with_query_failures"}) as audit:
            manifest, servers, measurements = self.run_main_mocked(
                measurements=["trec"], models=["2b", "9b"], include_latency=False, capacity=(16384, 1),
                trec_input=Path(inputs["input"]), failure_phases=("trec",))
        self.assertEqual(measurements, ["trec", "trec"])
        self.assertEqual(len(servers), 2)
        self.assertEqual(audit.call_count, 2)
        self.assertEqual(manifest["trec_inputs"], inputs)
        self.assertEqual(manifest["status"], "complete_with_measurement_failures")
        for report in manifest["models"].values():
            self.assertEqual(report["server_exit_code"], -15)
            self.assertFalse(report["gpu_after_shutdown"]["compute_processes"])
        self.assertTrue(all("--prefix-cache" not in server.command for server in servers))

    def test_stopped_trec_retains_summary_and_cleans_before_any_next_probe(self):
        inputs = {"input": "/external/input.json", "input_sha256": "a" * 64}
        partial = {"collection_status": "stopped_fatal", "quality_status": "partial"}
        with patch.object(suite, "preflight_trec_inputs", return_value=inputs), \
                patch.object(suite, "summarize_trec_output", return_value=partial) as audit:
            manifest, servers, measurements = self.run_main_mocked(
                measurements=["trec"], models=["2b", "9b"], include_latency=True, capacity=(16384, 1),
                trec_input=Path(inputs["input"]), expected_error="TREC collection stopped")
        self.assertEqual(measurements, ["trec"])
        self.assertEqual(audit.call_count, 1)
        self.assertEqual(len(servers), 1)
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["models"]["2b"]["measurements"]["trec"]["quality"], partial)
        self.assertEqual(manifest["models"]["2b"]["server_exit_code"], -15)

    def test_trec_rejected_audit_cleans_before_any_next_probe(self):
        inputs = {"input": "/external/input.json", "input_sha256": "a" * 64}
        with patch.object(suite, "preflight_trec_inputs", return_value=inputs), \
                patch.object(suite, "summarize_trec_output", side_effect=RuntimeError("unsettled dispatch")):
            manifest, servers, measurements = self.run_main_mocked(
                measurements=["trec"], models=["2b", "9b"], include_latency=False, capacity=(16384, 1),
                trec_input=Path(inputs["input"]), expected_error="unsettled dispatch")
        self.assertEqual(measurements, ["trec"])
        self.assertEqual(len(servers), 1)
        self.assertEqual(manifest["models"]["2b"]["server_exit_code"], -15)

    def test_provider_quality_runs_all_five_suites_before_releasing_each_model(self):
        inputs = {name: {"directory": str(self.root / directory), "files": {"requests.json": {"sha256": "a" * 64}}}
                  for name, directory, _, _, _ in suite.PROVIDER_SUITES}
        with patch.object(suite, 'preflight_provider_inputs', return_value=inputs), \
                patch.object(suite, 'summarize_provider_output', return_value={"collection_status": "complete_with_request_failures"}) as summaries:
            manifest, servers, measurements = self.run_main_mocked(
                measurements=['provider_quality'], models=['2b', '9b'], include_latency=False, capacity=(16384, 1),
                provider_data_root=self.root / 'providers', failure_phases=('provider_quality_jf100',))
        expected = ['provider_quality_' + name for name, _, _, _, _ in suite.PROVIDER_SUITES]
        self.assertEqual(measurements, expected * 2)
        self.assertEqual(len(servers), 2)
        self.assertEqual(summaries.call_count, 10)
        self.assertEqual(manifest['status'], 'complete_with_measurement_failures')
        self.assertEqual(manifest['provider_inputs'], inputs)
        for report in manifest['models'].values():
            self.assertEqual(list(report['measurements']), expected)
            self.assertFalse(report['gpu_after_shutdown']['compute_processes'])
        for server in servers:
            self.assertNotIn('--prefix-cache', server.command)

    def test_fatal_provider_collection_retains_summary_then_cleans_without_probe(self):
        inputs = {name: {"directory": str(self.root / directory), "files": {"requests.json": {"sha256": "a" * 64}}}
                  for name, directory, _, _, _ in suite.PROVIDER_SUITES}
        partial = {"collection_status": "stopped_fatal", "quality_status": "partial", "pending_count": 145}
        with patch.object(suite, 'preflight_provider_inputs', return_value=inputs), \
                patch.object(suite, 'summarize_provider_output', return_value=partial) as summaries:
            manifest, servers, measurements = self.run_main_mocked(
                measurements=['provider_quality'], models=['2b', '9b'], include_latency=False,
                expected_error='Provider collection stopped')
        self.assertEqual(measurements, ['provider_quality_coverage'])
        self.assertEqual(summaries.call_count, 1)
        self.assertEqual(len(servers), 1)
        self.assertEqual(manifest['status'], 'failed')
        self.assertEqual(manifest['models']['2b']['measurements']['provider_quality_coverage']['quality'], partial)
        self.assertEqual(manifest['models']['2b']['server_exit_code'], -15)

    def test_identity_mismatch_stops_and_cleans_server(self):
        manifest, servers, measurements = self.run_main_mocked(mismatch=True)
        self.assertEqual(len(servers), 1)
        self.assertEqual(measurements, ['demo_requests'])
        self.assertEqual(manifest['status'], 'failed')
        self.assertIn('test identity mismatch', manifest['error'])
        self.assertEqual(manifest['models']['2b']['server_exit_code'], -15)

    def test_larger_capacity_reaches_every_server_and_identity(self):
        manifest, servers, _ = self.run_main_mocked(capacity=(16384, 4))
        self.assertEqual(manifest["configuration"]["max_length"], 16384)
        self.assertEqual(manifest["configuration"]["batch_size"], 4)
        for server in servers:
            self.assertEqual(server.command[server.command.index("--max-length") + 1], "16384")
            self.assertEqual(server.command[server.command.index("--batch-size") + 1], "4")
        for report in manifest["models"].values():
            self.assertEqual(report["expected_identity"]["max_length"], 16384)

    def test_frontier_only_runs_all_three_checkpoints_without_workflow_input(self):
        manifest, servers, measurements = self.run_main_mocked(
            capacity=(16384, 1), measurements=["frontier_100"], include_latency=False)
        self.assertEqual(len(servers), 3)
        self.assertEqual(measurements, ["frontier_100"] * 3)
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(manifest["configuration"]["measurements"], ["frontier_100"])
        self.assertNotIn("latency", manifest)
        self.assertFalse((self.root / "cases.jsonl").exists())
        for report in manifest["models"].values():
            self.assertEqual(set(report["measurements"]), {"frontier_100"})
            self.assertEqual(report["expected_identity"]["max_length"], 16384)
            command = report["measurements"]["frontier_100"]["command"]
            self.assertEqual(command[command.index("-m") + 1], "jev.eval_frontier")
            self.assertNotIn("--limit", command)
        for server in servers:
            self.assertEqual(server.command[server.command.index("--batch-size") + 1], "1")

    def test_selected_checkpoint_does_not_require_other_model_files(self):
        manifest, servers, measurements = self.run_main_mocked(
            measurements=["frontier_100"], include_latency=False, models=["9b"])
        self.assertEqual(len(servers), 1)
        self.assertEqual(measurements, ["frontier_100"])
        self.assertEqual(manifest["configuration"]["models"], ["9b"])
        self.assertEqual(list(manifest["models"]), ["9b"])
        self.assertEqual(manifest["status"], "complete")
        self.assertFalse((self.root / "runs/2b-pilot-v1").exists())
        self.assertFalse((self.root / "runs/27b-pilot-v1").exists())

    def test_repeated_or_unknown_model_rejected_before_gpu_or_spawn(self):
        for models in (["2b", "2b"], ["unknown"]):
            with patch.object(suite.socket, "gethostname", return_value="allowed-node"), \
                    patch.object(suite, "gpu_snapshot") as gpu, \
                    patch.object(suite.subprocess, "Popen") as spawn, redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    suite.main(["--expected-hostname", "allowed-node", "--output-root",
                                str(self.root / "output"), "--models", *models])
                self.assertEqual(raised.exception.code, 2)
            gpu.assert_not_called()
            spawn.assert_not_called()

    def test_browser_only_passes_checkpoint_identity_without_workflow_input(self):
        manifest, servers, measurements = self.run_main_mocked(
            measurements=["browser"], include_latency=False, models=["2b"])
        self.assertEqual(len(servers), 1)
        self.assertEqual(measurements, ["browser"])
        self.assertEqual(manifest["status"], "complete")
        report = manifest["models"]["2b"]
        command = report["measurements"]["browser"]["command"]
        self.assertEqual(command[command.index("-m") + 1], "scripts.evaluate_browser_service")
        for flag, key in (("--expected-revision", "base_revision"),
                          ("--expected-checkpoint-sha256", "checkpoint_sha256")):
            self.assertEqual(command[command.index(flag) + 1], report["expected_identity"][key])
        self.assertFalse((self.root / "cases.jsonl").exists())

    def test_missing_browser_cases_rejected_before_gpu_or_spawn(self):
        with patch.object(suite.socket, "gethostname", return_value="allowed-node"), \
                patch.object(suite, "gpu_snapshot") as gpu, \
                patch.object(suite.subprocess, "Popen") as spawn, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                suite.main(["--expected-hostname", "allowed-node", "--output-root", str(self.root / "output"),
                            "--measurements", "browser", "--browser-cases", str(self.root / "missing.jsonl")])
            self.assertEqual(raised.exception.code, 2)
        gpu.assert_not_called()
        spawn.assert_not_called()

    def test_drone_only_pins_identity_and_keeps_gpu_cleanup(self):
        manifest, servers, measurements = self.run_main_mocked(
            measurements=["drone"], include_latency=False, models=["27b"])
        self.assertEqual(len(servers), 1)
        self.assertEqual(measurements, ["drone"])
        self.assertEqual(manifest["status"], "complete")
        report = manifest["models"]["27b"]
        command = report["measurements"]["drone"]["command"]
        self.assertEqual(command[command.index("-m") + 1], "scripts.evaluate_drone_service")
        self.assertEqual(command[command.index("--cases") + 1], str((self.root / "drone_cases.jsonl").resolve()))
        for flag, key in (("--expected-revision", "base_revision"),
                          ("--expected-checkpoint-sha256", "checkpoint_sha256")):
            self.assertEqual(command[command.index(flag) + 1], report["expected_identity"][key])
        self.assertEqual(report["server_exit_code"], -15)
        self.assertFalse((self.root / "cases.jsonl").exists())
        self.assertFalse((self.root / "browser_cases.jsonl").exists())

    def test_missing_drone_cases_rejected_before_gpu_or_spawn(self):
        with patch.object(suite.socket, "gethostname", return_value="allowed-node"), \
                patch.object(suite, "gpu_snapshot") as gpu, \
                patch.object(suite.subprocess, "Popen") as spawn, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                suite.main(["--expected-hostname", "allowed-node", "--output-root", str(self.root / "output"),
                            "--measurements", "drone", "--drone-cases", str(self.root / "missing.jsonl")])
            self.assertEqual(raised.exception.code, 2)
        gpu.assert_not_called()
        spawn.assert_not_called()

    def test_controls_run_serially_retain_failures_and_clean_each_server(self):
        data_root = self.root / 'controls'
        with patch('scripts.evaluate_contact_service.phone_library'), \
                patch('scripts.evaluate_contact_service.load_cases', return_value=([{}, {}], {'email': 'evidence'})) as contact, \
                patch('scripts.evaluate_amount_service.load_cases', return_value=([{}], {'amount': 'evidence'})) as amount:
            manifest, servers, measurements = self.run_main_mocked(
                measurements=['amount', 'contact'], include_latency=False, capacity=(16384, 1),
                control_data_root=data_root, failure_phases=('contact',))
        # The helper also retries the same output to verify overwrite refusal.
        self.assertEqual(contact.call_count, 2)
        self.assertEqual(amount.call_count, 2)
        contact.assert_called_with(data_root.resolve(), ('email', 'phone'), ('test', 'ood'))
        amount.assert_called_with(data_root.resolve(), ('test', 'ood'))
        self.assertEqual(len(servers), 3)
        self.assertEqual(measurements, ['contact', 'amount'] * 3)
        self.assertEqual(manifest['status'], 'complete_with_measurement_failures')
        self.assertEqual(manifest['control_inputs']['contact']['selected_cases'], 2)
        self.assertEqual(manifest['control_inputs']['amount']['selected_cases'], 1)
        self.assertEqual(manifest['configuration']['control_data_root'], str(data_root.resolve()))
        self.assertNotIn('latency', manifest)
        for path in ('cases.jsonl', 'frontier', 'browser_cases.jsonl', 'drone_cases.jsonl'):
            self.assertFalse((self.root / path).exists())
        for report in manifest['models'].values():
            self.assertEqual(list(report['measurements']), ['contact', 'amount'])
            self.assertEqual(report['measurements']['contact']['exit_code'], 7)
            self.assertEqual(report['measurements']['amount']['exit_code'], 0)
            self.assertEqual(report['server_exit_code'], -15)
            self.assertFalse(report['gpu_after_shutdown']['compute_processes'])
            self.assertEqual(report['expected_identity']['max_length'], 16384)
            for result in report['measurements'].values():
                command = result['command']
                for flag, key in (('--expected-model', 'model'), ('--expected-method', 'method'),
                                  ('--expected-revision', 'base_revision'), ('--expected-checkpoint-sha256', 'checkpoint_sha256'),
                                  ('--expected-temperature', 'temperature')):
                    self.assertEqual(command[command.index(flag) + 1], str(report['expected_identity'][key]))
        for server in servers:
            self.assertEqual(server.command[server.command.index('--batch-size') + 1], '1')


if __name__ == '__main__':
    unittest.main(verbosity=2)
