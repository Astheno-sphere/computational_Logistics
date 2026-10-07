"""Small synthetic artifact tests; no real dataset rows, network, tensors or GPU."""
import ast
from contextlib import ExitStack
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "reports/full-data-eval-expansion-n1-v1"


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, AUDIT/filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


c = module("expansion_contract", "expansion_contract.py")
with patch.dict(sys.modules, {"expansion_contract":c}):
    verify = module("expansion_verify", "verify.py")
    capture = module("expansion_capture", "capture.py")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+"\n")


def lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value)+"\n" for value in values))


def read(path):
    return json.loads(path.read_text())


class SyntheticEvidence(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.evidence, self.data, self.package = (self.root/name for name in ("evidence", "data", "package"))
        self.directory, self.training = self.evidence/"evaluation", self.evidence/"training"
        counts = {"train":8, "calibration":2, "validation":1, "test":3, "ood":2}
        self.rows = {split:[{"id":f"{split}-{i}", "split":split, "group_id":f"{split}-g{i}",
                            "source":"synthetic-unit-fixture", "kind":"noul", "target":[1.,0.],
                            "options":["yes","no"], "metadata":{"question_id":"fixture"}} for i in range(n)]
                     for split,n in counts.items()}
        for split,rows in self.rows.items():
            lines(self.data/(split+".jsonl"), rows)
        hashes = {s:c.info(self.data/(s+".jsonl"))["sha256"] for s in counts}
        write(self.data/"manifest.json", {"counts":counts, "sha256":hashes})
        ids = [r["id"] for r in self.rows["calibration"]]
        for key,value in {"COUNTS":counts, "HASHES":hashes, "STEPS":2, "CALIBRATION_N":2,
                          "MANIFEST_SHA":c.info(self.data/"manifest.json")["sha256"],
                          "CALIBRATION_IDS_SHA":hashlib.sha256(json.dumps(ids).encode()).hexdigest()}.items():
            self.stack.enter_context(patch.object(c, key, value))
        self.ddp = {"world_size":4, "global_batch_size":4, "local_rows_per_step":1, "backend":"nccl",
                    "device_type":"cuda", "implementation_sha256":"d"*64, "bitwise_single_process_equivalence":False}
        self.run = {"model":c.MODEL, "revision":c.REVISION, "steps":2, "accumulation":4, "train_rows":0,
                    "training_rows_consumed":8, "training_sampling":"shuffled", "seed":c.SEED,
                    "data_sha256":hashes, "initialization":"fresh_pinned_upstream", "commit":c.TRAINING_COMMIT,
                    "identity_sha256":c.RUN_IDENTITY, "distribution":self.ddp, "max_length":4096, "lora_rank":8,
                    "calibration_ids":ids, "calibration_rows":2, "eval_rows":2,
                    "evaluation_ids":[r["id"] for r in self.rows["test"][:2]]}
        trained_summary = {"status":"complete", "model":c.MODEL, "steps":2, "trained_rows_consumed":8,
                           "distribution":self.ddp, "temperature":1., "checkpoint_reload_max_error":0.}
        self.temperature = {"temperature":1., "split":"calibration", "n":2, "ids_sha256":c.CALIBRATION_IDS_SHA}
        write(self.training/"run.json", self.run)
        write(self.training/"summary.json", trained_summary)
        lines(self.training/"training.jsonl", [{"step":i+1, "world_size":4, "global_batch_size":4,
                                              "loss":.5, "gradient_norm":1., "elapsed_seconds":i+1} for i in range(2)])
        for split,name,limit in (("calibration","calibration.jsonl",2), ("test","trained_test.jsonl",2), ("test","reload_check.jsonl",1)):
            lines(self.training/name, [{"id":r["id"], "target":r["target"], "logits":[0.,0.]} for r in self.rows[split][:limit]])
        write(self.training/"checkpoint/model.json", {"model_id":c.MODEL, "revision":c.REVISION,
              "max_length":4096, "lora_rank":8, "method":"independent_candidate_lora_nll_brier"})
        write(self.training/"checkpoint/temperature.json", self.temperature)
        write(self.training/"checkpoint/adapter/adapter_config.json", {"peft_type":"LORA", "r":8,
              "base_model_name_or_path":c.MODEL, "revision":c.REVISION})
        for name in ("head.pt", "adapter/adapter_model.safetensors", "adapter/README.md"):
            (self.training/"checkpoint"/name).write_bytes(b"SYNTHETIC UNIT FIXTURE, NOT TENSOR WEIGHTS\n")
        completion = {"steps":2, "trained_rows_consumed":8, "checkpoint_reload_max_error":0., "distribution":self.ddp,
                      "run_identity_sha256":c.RUN_IDENTITY, **{key:c.info(self.training/name)["sha256"] for key,name in (
                          ("run_sha256","run.json"), ("summary_sha256","summary.json"),
                          ("calibration_predictions_sha256","calibration.jsonl"), ("training_log_sha256","training.jsonl"))}}
        self.checkpoint = {"dataset_profile":c.PROFILE, "model":c.MODEL, "revision":c.REVISION,
                           "checkpoint_sha256":c.checkpoint_digest(self.training/"checkpoint"), "temperature":1.,
                           "calibration":self.temperature, "max_length":4096, "training_completion":completion}
        self.identity = {"dataset_profile":c.PROFILE, "partition":c.PARTITION, "manifest_sha256":c.MANIFEST_SHA,
                         "split_sha256":hashes, "counts":{"test":3,"ood":2}, "total_rows":5,
                         "ordered_ids_sha256":{s:c.objsha([r["id"] for r in self.rows[s]]) for s in c.SPLITS}}
        implementation, policy_sha = verify.pinned_source()
        checkout = "/synthetic/checkout"
        policy = {"hostname":c.HOSTNAME, "policy_sha256":policy_sha, "gpu_indices":[0,1,2,3]}
        self.plan = {"tag":"27b", "dataset_profile":c.PROFILE, "partition":c.PARTITION,
                     "data":c.REMOTE_DATA, "data_identity":self.identity, "checkpoint_path":c.REMOTE_RUN+"/checkpoint",
                     "checkpoint":self.checkpoint, "gpu_uuids":["fixture-gpu-"+str(r) for r in range(4)],
                     "implementation_sha256":implementation, "policy_path":checkout+"/state/auto_research/resource_policy.json",
                     "policy":policy, "assignments":{str(r):c.assignment_identity(c.assignments(self.rows,r),r) for r in range(4)}}
        write(self.directory/"plan.json", self.plan)
        predictions = {s:[] for s in c.SPLITS}
        for rank in range(4):
            assigned = c.assignments(self.rows,rank)
            results = []
            for split,index,row in assigned:
                value = {"id":row["id"], "split":split, "index":index, "shard_rank":rank,
                         "source":row["source"], "group_id":row["group_id"], "kind":row["kind"], "target":row["target"],
                         "row_sha256":c.objsha(row), "checkpoint":self.checkpoint, "question_id":"fixture",
                         "status":"ok", "logits":[0.,0.], "probabilities":[.5,.5], "input_tokens":7}
                results.append(value)
                predictions[split].append(value)
            lines(self.directory/f"shard-{rank}.jsonl",results)
            write(self.directory/f"shard-{rank}.json", {"status":"complete", "rank":rank,
                  "checkpoint":self.checkpoint, "dataset_profile":c.PROFILE, "data_identity":self.identity,
                  "gpu_uuid":self.plan["gpu_uuids"][rank],
                  "plan_sha256":c.info(self.directory/"plan.json")["sha256"], "assignment":self.plan["assignments"][str(rank)],
                  "output_sha256":c.info(self.directory/f"shard-{rank}.jsonl")["sha256"],
                  "counts":{"rows":len(results), "ok":len(results), "error":0}})
            (self.directory/f"shard-{rank}.log").write_text("synthetic unit fixture\n")
        split_summaries = {}
        for split,results in predictions.items():
            results.sort(key=lambda r:r["index"])
            lines(self.directory/f"merged-{split}.jsonl",results)
            split_summaries[split] = c.summarize(results)
            for field in ("source","kind","group_id"):
                split_summaries[split]["by_"+field] = {name:c.summarize([r for r in results if r[field] == name])
                                                      for name in sorted({r[field] for r in results})}
        write(self.directory/"summary.json", {"status":"complete", "dataset_profile":c.PROFILE, "partition":c.PARTITION,
              "data_identity":self.identity, "total_rows":5, "checkpoint":self.checkpoint, "splits":split_summaries,
              "workers":[read(self.directory/f"shard-{rank}.json") for rank in range(4)]})
        self.controller = {**{key:self.plan[key] for key in ("dataset_profile","partition","data_identity","gpu_uuids","implementation_sha256","policy")},
                           "status":"complete", "gpus_free_after_cleanup":True, "phase":"parallel_data_eval", "model_order":["27b"],
                           "models":{"27b":{"status":"complete", "exit_codes":[0]*4,
                           "children":[{"rank":r,"gpu_uuid":self.plan["gpu_uuids"][r]} for r in range(4)]}}}
        for name in c.WEIGHT_FILES:
            target = self.package/"checkpoint"/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(self.training/"checkpoint"/name,target)
        write(self.package/"provenance.json", {"model":c.MODEL,"revision":c.REVISION,"calibration":self.temperature,
              "data":{"name":c.PROFILE,"manifest_sha256":c.MANIFEST_SHA,"sha256":hashes,"rows_by_split":counts},
              "training":{"steps":2,"records_consumed":8,"selected_train_rows":8,"one_full_pass":True,"seed":c.SEED,
                          "sampling":"shuffled","run_identity_sha256":c.RUN_IDENTITY,"code_commit":c.TRAINING_COMMIT,"distribution":self.ddp},
              "source_evidence":{name:c.info(self.training/name) for name in c.RUN_FILES}})
        self.package_manifest()
        self.source = {"status":"ready", "hostname":c.HOSTNAME,"tag":"27b","source_commit":c.COMMIT,
                       "source_root":c.REMOTE,"source_run":c.REMOTE_RUN,"source_data":c.REMOTE_DATA,"source_checkout":checkout,
                       "implementation_sha256":implementation,"policy_sha256":policy_sha,
                       "checkpoint_sha256":self.checkpoint["checkpoint_sha256"],
                       "data_files":{name:c.info(self.data/name) for name in c.file_set(self.data)}}
        self.seal()
        self.args = SimpleNamespace(evidence=self.evidence,data=self.data,package=self.package)

    def package_manifest(self):
        write(self.package/"manifest.json", {"kind":"local_inference_weight_package","model":c.MODEL,"revision":c.REVISION,
              "weights_license":"Apache-2.0", "files":{name:c.info(self.package/name) for name in c.file_set(self.package)-{"manifest.json"}}})

    def seal(self):
        for label in ("before","after"):
            write(self.evidence/f"controller-manifest-{label}.json",self.controller)
        self.source["files"] = {label+"/"+name:c.info(self.evidence/label/name)
                               for label in ("evaluation","training") for name in c.file_set(self.evidence/label)}
        write(self.evidence/"capture.json", {"status":"copied_completed_expansion","read_only_remote":True,"model_inference_performed":False,
              "source_before":self.source,"source_after":self.source,
              "controller_manifests":{label:c.info(self.evidence/f"controller-manifest-{label}.json") for label in ("before","after")}})

    def test_complete_synthetic_capture(self):
        result = verify.audit(self.args)
        self.assertEqual(result["coverage"],{"expected_rows":5,"unique_ids":5,"shard_rows":[2,1,1,1],"missing":0,"duplicate":0,"failed":0})
        self.assertFalse(result["model_inference_performed"])
        self.assertFalse(result["calibration_refitted"])
        self.assertAlmostEqual(result["metrics"]["test"]["probability_metrics_all_rows"]["nll"],math.log(2))

    def test_global_partition_continues_across_split_boundary(self):
        self.assertEqual([[(s,i) for s,i,_ in c.assignments(self.rows,r)] for r in range(4)],
                         [[("test",0),("ood",1)],[("test",1)],[("test",2)],[("ood",0)]])

    def test_wrong_profile_or_controller_cleanup_rejected(self):
        for field,value in (("gpus_free_after_cleanup",False),("model_order",["2b","9b"]),("partition","per_split")):
            with self.subTest(field=field):
                old = self.controller[field]
                self.controller[field] = value
                self.seal()
                with self.assertRaises(ValueError):
                    verify.audit(self.args)
                self.controller[field] = old
        self.seal()

    def test_partial_training_or_wrong_revision_rejected_after_rehash(self):
        for name,key,value in (("run.json","revision","old-release"),("summary.json","steps",1),
                               ("summary.json","checkpoint_reload_max_error",.1),
                               ("run.json","identity_sha256","0"*64),("run.json","commit","0"*40)):
            with self.subTest(key=key):
                path = self.training/name
                old = path.read_bytes()
                content = read(path)
                content[key] = value
                write(path,content)
                self.seal()
                with self.assertRaises(ValueError):
                    verify.audit(self.args)
                path.write_bytes(old)
        self.seal()

    def test_changed_calibration_rejected_after_rehash(self):
        value = read(self.training/"checkpoint/temperature.json")
        value["ids_sha256"] = "0"*64
        write(self.training/"checkpoint/temperature.json",value)
        self.seal()
        with self.assertRaisesRegex(ValueError,"calibration identity"):
            verify.audit(self.args)

    def test_failed_duplicate_wrong_probability_or_missing_prediction_rejected(self):
        path = self.directory/"shard-0.jsonl"
        original = path.read_bytes()
        for mutation in ("failed","duplicate","probability","missing"):
            with self.subTest(mutation=mutation):
                rows = [json.loads(line) for line in original.splitlines()]
                if mutation == "failed":
                    rows[0]["status"] = "error"
                elif mutation == "duplicate":
                    rows[1] = rows[0]
                elif mutation == "probability":
                    rows[0]["probabilities"] = [.6,.4]
                else:
                    rows.pop()
                lines(path,rows)
                report = read(self.directory/"shard-0.json")
                report["output_sha256"] = c.info(path)["sha256"]
                write(self.directory/"shard-0.json",report)
                self.seal()
                with self.assertRaises(ValueError):
                    verify.audit(self.args)
        path.write_bytes(original)

    def test_summary_metric_mutation_rejected_after_rehash(self):
        value = read(self.directory/"summary.json")
        value["splits"]["test"]["probability_metrics_all_rows"]["nll"] += .1
        write(self.directory/"summary.json",value)
        self.seal()
        with self.assertRaisesRegex(ValueError,"metric difference"):
            verify.audit(self.args)

    def test_package_payload_mismatch_even_with_updated_manifest(self):
        (self.package/"checkpoint/head.pt").write_bytes(b"different synthetic fixture")
        self.package_manifest()
        with self.assertRaisesRegex(ValueError,"Packaged weights differ"):
            verify.audit(self.args)

    def test_source_bytes_or_before_after_change_rejected(self):
        (self.directory/"shard-0.log").write_text("changed after capture")
        with self.assertRaisesRegex(ValueError,"Evidence bytes differ"):
            verify.audit(self.args)
        self.seal()
        value = read(self.evidence/"capture.json")
        value["source_after"]["checkpoint_sha256"] = "0"*64
        write(self.evidence/"capture.json",value)
        with self.assertRaisesRegex(ValueError,"Unstable"):
            verify.audit(self.args)

    def test_symlinked_package_payload_rejected(self):
        path = self.package/"checkpoint/head.pt"
        path.unlink()
        path.symlink_to(self.training/"checkpoint/head.pt")
        with self.assertRaisesRegex(ValueError,"Symlinked"):
            verify.audit(self.args)


class Entrypoints(unittest.TestCase):
    def test_modified_pinned_producer_archive_is_rejected(self):
        name = "scripts/evaluate_checkpoints_parallel.py"
        original = verify.pinned_source_bytes(name)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / name
            path.parent.mkdir(parents=True)
            path.write_bytes(original + b"\n# modified archive\n")
            with patch.object(verify, "PINNED_SOURCE_ROOT", root):
                with self.assertRaisesRegex(ValueError, "Pinned producer bytes differ"):
                    verify.pinned_source_bytes(name)

    def test_pinned_producer_schemas_and_source_bytes(self):
        raw = verify.pinned_source_bytes("scripts/evaluate_checkpoints_parallel.py")
        tree = ast.parse(raw)
        functions = {node.name:node for node in tree.body if isinstance(node,ast.FunctionDef)}
        def keys(value):
            return {node.value for node in value.keys if isinstance(node,ast.Constant)}
        def returned(name):
            return [keys(node.value) for node in ast.walk(functions[name])
                    if isinstance(node,ast.Return) and isinstance(node.value,ast.Dict)][-1]
        self.assertEqual(returned("shard_identity"),set(c.assignment_identity([],0)))
        self.assertEqual(returned("checkpoint_identity"),{"dataset_profile","model","revision","checkpoint_sha256",
                         "temperature","calibration","max_length","training_completion"})
        self.assertEqual(returned("row_identity"),{"id","split","index","shard_rank","source","group_id","kind",
                         "target","row_sha256","checkpoint","question_id"})
        reports = [node.args[1] for node in ast.walk(functions["worker"]) if isinstance(node,ast.Call)
                   and isinstance(node.func,ast.Name) and node.func.id == "write_json"]
        self.assertEqual(keys(reports[0]),{"status","rank","checkpoint","dataset_profile","data_identity","gpu_uuid",
                         "plan_sha256","assignment","output_sha256","counts","model_load_seconds","shard_inference_seconds","peak_memory_gib"})
        preflight = read(ROOT/"reports/runtime-checks/27b-expansion-eval-preflight.json")
        self.assertEqual(verify.pinned_source()[0],preflight["runtime_implementation_sha256"])
        package_tree = ast.parse((ROOT/"scripts/package_checkpoint.py").read_text())
        source_evidence = [value for node in ast.walk(package_tree) if isinstance(node,ast.Dict)
                           for key,value in zip(node.keys,node.values)
                           if isinstance(key,ast.Constant) and key.value == "source_evidence"][0]
        names = {item.value for item in source_evidence.generators[0].iter.elts if isinstance(item,ast.Constant)}
        self.assertTrue(c.RUN_FILES <= names)

    def test_fixed_contract_matches_preflight_metadata(self):
        preflight = read(ROOT/"reports/runtime-checks/27b-expansion-eval-preflight.json")
        self.assertEqual(c.COUNTS,{s:info["rows"] for s,info in preflight["profile"]["files"].items()})
        self.assertEqual(c.HASHES,{s:info["sha256"] for s,info in preflight["profile"]["files"].items()})
        self.assertEqual(c.MANIFEST_SHA,preflight["profile"]["manifest_sha256"])
        self.assertEqual(sum(c.COUNTS[s] for s in c.SPLITS),40281)
        self.assertEqual(c.CALIBRATION_IDS_SHA,preflight["calibration_selection"]["ids_sha256_json_default"])
        self.assertEqual(c.info(c.HELPER)["sha256"],c.HELPER_SHA)

    def test_full_size_assignment_counts_without_reading_dataset_rows(self):
        preflight = read(ROOT/"reports/runtime-checks/27b-expansion-eval-preflight.json")
        counts = []
        for rank in range(4):
            offset, split_counts = 0, {}
            for split in c.SPLITS:
                n = c.COUNTS[split]
                first = (rank-offset) % 4
                split_counts[split] = (n-1-first)//4+1 if first < n else 0
                offset += n
            self.assertEqual(split_counts,preflight["rank_assignments"][rank]["counts"])
            counts.append(sum(split_counts.values()))
        self.assertEqual(counts,[10071,10070,10070,10070])

    def test_not_ready_capture_does_not_copy_or_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/"absent"
            with patch.object(capture,"probe",return_value={"status":"not_ready"}), patch.object(capture.subprocess,"run") as command:
                self.assertEqual(capture.capture(target),{"status":"not_ready"})
                command.assert_not_called()
                self.assertFalse(target.exists())

    def test_probe_missing_final_artifacts_returns_not_ready_without_subprocess(self):
        namespace = {}
        exec(capture.PROBE,namespace)
        with tempfile.TemporaryDirectory() as directory, patch("socket.gethostname",return_value=c.HOSTNAME), patch("subprocess.check_output") as command:
            config = capture.config()
            config.update(root=directory+"/eval",run=directory+"/run",data=directory+"/data")
            self.assertEqual(namespace["snapshot"](config)["status"],"not_ready")
            command.assert_not_called()

    def test_absent_evidence_writes_failed_report_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = ["verify.py","--evidence",str(root/"absent"),"--data",str(root/"data"),
                    "--package",str(root/"package"),"--output",str(root/"audit.json")]
            with patch.object(sys,"argv",args), self.assertRaises(ValueError):
                verify.main()
            result = read(root/"audit.json")
            self.assertEqual(result["status"],"failed")
            self.assertIsNone(result["metrics"])
            original = (root/"audit.json").read_bytes()
            with patch.object(sys,"argv",args), self.assertRaisesRegex(ValueError,"Preserve"):
                verify.main()
            self.assertEqual((root/"audit.json").read_bytes(),original)

    def test_archive_traversal_and_duplicate_members_rejected(self):
        for names in (("../escape",),("plan.json","plan.json")):
            with self.subTest(names=names), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with tarfile.open(root/"bad.tar","w") as archive:
                    for name in names:
                        member = tarfile.TarInfo(name)
                        member.size = 2
                        archive.addfile(member,io.BytesIO(b"{}"))
                with self.assertRaises(ValueError):
                    capture.unpack(root/"bad.tar",root/"out",{"plan.json"})
                self.assertFalse((root/"out").exists())


if __name__ == "__main__":
    unittest.main()
