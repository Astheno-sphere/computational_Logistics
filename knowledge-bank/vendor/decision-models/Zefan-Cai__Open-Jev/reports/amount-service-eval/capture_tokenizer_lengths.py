"""Pinned CPU tokenizer lengths for all held-out amount A and possible B inputs."""
import base64
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from jev.api import candidate_prompts, compile_request
from jev.case_amount_extraction import amount_attributes

MODELS = {
    "2b": ("Qwen/Qwen3.5-2B", "15852e8c16360a2fea060d615a32b45270f8a8fc"),
    "9b": ("Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a"),
    "27b": ("Qwen/Qwen3.8-27B", "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"),
}
VERSION = "amount-extraction-control-v1"
PIN = "6f89f81336ac36505c563193da27fca2155fa566175451854f0ac410979ea80b"
PREFIX = re.compile(rb'^\{"id":("(?:[^"\\]|\\.)*"),')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = ROOT / "reports/amount-service-eval/tokenizer-lengths.json"
    raw_output = ROOT / "reports/amount-service-eval/tokenizer-lengths-raw.json.gz"
    if any(p.exists() or p.is_symlink() for p in (output, raw_output)):
        raise ValueError("Preserve prior evidence; outputs must be new")
    directory = ROOT / "data" / VERSION
    assert sha(directory / "manifest.json") == PIN
    manifest = json.loads((directory / "manifest.json").read_bytes())
    for name, digest in manifest["files_sha256"].items():
        assert sha(directory / name) == digest
    sources = {"jev/" + name: digest for name, digest in manifest["configuration"]["source_files_sha256"].items()}
    for name, digest in sources.items():
        assert sha(ROOT / name) == digest
    index = {}
    for raw in (directory / "families.jsonl").read_bytes().splitlines():
        family = json.loads(raw)
        for identifier in family["case_ids"]:
            assert identifier not in index
            index[identifier] = family
    entries, counts, decoded, seen = [], Counter(), Counter(), set()
    with (directory / "cases.jsonl").open("rb") as stream:
        for raw in stream:
            prefix = PREFIX.match(raw)
            assert prefix is not None
            identifier = json.loads(prefix[1])
            assert identifier in index and identifier not in seen
            seen.add(identifier)
            family = index[identifier]
            if family["split"] not in ("test", "ood"):
                continue
            case = json.loads(raw)
            decoded[case["split"]] += 1
            assert case["family_id"] == family["id"]
            assert all(case[k] == family[k] for k in ("split", "group_id"))
            request = case["selection_request"]
            assert set(request) == {"state", "questions"}
            requests = [("selection", None, request)]
            requests += [("attributes", key, amount_attributes(request, key)) for key in request["state"]["candidates"]]
            for stage, candidate, value in requests:
                counts[VERSION + "/" + case["split"] + "/" + stage] += 1
                for record in compile_request(**value):
                    for index_, prompt in enumerate(candidate_prompts(record)):
                        entries.append({"corpus": VERSION, "split": case["split"], "case_id": case["id"],
                                        "stage": stage, "candidate_id": candidate, "head": record["id"],
                                        "option_index": index_, "prompt": prompt})
    assert seen == set(index)
    assert decoded == {"test": 224, "ood": 640}
    wire = json.dumps({"models": MODELS, "entries": entries}, ensure_ascii=False, separators=(",", ":")).encode()
    payload = base64.b64encode(gzip.compress(wire, mtime=0)).decode()
    remote = "PAYLOAD = " + repr(payload) + "\n" + r'''
import base64,datetime,gzip,hashlib,json,os,socket
import transformers,tokenizers
from transformers import AutoTokenizer
assert socket.gethostname() == 'kwade5342000001'
assert os.environ['CUDA_VISIBLE_DEVICES'] == ''
payload=json.loads(gzip.decompress(base64.b64decode(PAYLOAD)))
result={'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'models':{},'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES'],'transformers':transformers.__version__,'tokenizers':tokenizers.__version__}
assert transformers.__version__ == '5.10.2'
for tag,(model,revision) in payload['models'].items():
    tokenizer=AutoTokenizer.from_pretrained(model,revision=revision,local_files_only=True)
    lengths=[]
    for offset in range(0,len(payload['entries']),64):
        batch=payload['entries'][offset:offset+64]
        rendered=[tokenizer.apply_chat_template([{'role':'user','content':row['prompt']}],tokenize=False,add_generation_prompt=True,enable_thinking=False) for row in batch]
        tokens=tokenizer(rendered,padding=False,truncation=False,return_attention_mask=False)['input_ids']
        lengths.extend(len(ids) for ids in tokens)
    result['models'][tag]={'model':model,'revision':revision,'tokenizer_class':type(tokenizer).__name__,'chat_template_sha256':hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),'lengths':lengths}
print(json.dumps(result))
'''
    command = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "sigma@192.0.2.1",
               "env CUDA_VISIBLE_DEVICES='' HF_HUB_CACHE=/mnt/localssd/open-jev/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 RAYON_NUM_THREADS=1 /mnt/localssd/open-jev/runtime/venv/bin/python -B -"]
    completed = subprocess.run(command, input=remote, text=True, capture_output=True, check=True, timeout=300)
    result = json.loads(completed.stdout)
    identities = [{key: value for key, value in entry.items() if key != "prompt"} for entry in entries]
    with raw_output.open("xb") as stream:
        stream.write(gzip.compress(json.dumps({"entries": identities, "result": result}, separators=(",", ":")).encode(), mtime=0))
    for model in result["models"].values():
        lengths = model.pop("lengths")
        assert len(lengths) == len(entries)
        model.update(sequences=len(lengths), minimum=min(lengths), maximum=max(lengths),
                     over_4096=sum(n > 4096 for n in lengths), over_16384=sum(n > 16384 for n in lengths),
                     maximum_example=identities[lengths.index(max(lengths))])
    result.update(status="complete", request_counts=dict(counts), candidate_sequences=len(entries),
                  dataset_manifest_sha256={VERSION: PIN}, source_files_sha256=sources,
                  capture_script_sha256=sha(__file__), prompt_payload_sha256=hashlib.sha256(wire).hexdigest(),
                  raw_lengths=str(raw_output.relative_to(ROOT)), raw_lengths_sha256=sha(raw_output),
                  full_case_payloads_decoded_by_split=dict(decoded), nonheldout_case_payloads_decoded=0,
                  scope="Pinned cached tokenizers, one CPU thread, serving chat-template settings. All held-out A and every actual-candidate B path, including the declared is_credit head even where its target is undefined. Case IDs route before full decoding; only heldout state/questions enter prompts. All family metadata is read for routing. No model weights, GPU allocation, HTTP inference, training or active-checkout modifications. This measures input length, not model quality or A-selected B outcomes.")
    with output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"report": str(output.relative_to(ROOT)), "candidate_sequences": len(entries), "models": result["models"]}))


if __name__ == "__main__":
    main()
