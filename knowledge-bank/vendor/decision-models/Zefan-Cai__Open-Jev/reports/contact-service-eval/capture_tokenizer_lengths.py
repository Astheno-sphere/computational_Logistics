"""CPU-only cached-tokenizer lengths for every held-out contact request path."""
import base64
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from jev.api import candidate_prompts, compile_request
from jev.case_phone_extraction import phone_attributes

MODELS = {
    "2b": ("Qwen/Qwen3.5-2B", "15852e8c16360a2fea060d615a32b45270f8a8fc"),
    "9b": ("Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a"),
    "27b": ("Qwen/Qwen3.8-27B", "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"),
}
PINS = {
    "email-selection-control-v1": "4c18cc791425003c5c8f052ce27ed034dfb54c79ddac24de13f7290ab3b3316c",
    "phone-extraction-control-v1": "1001f1e04795308bf4f68db51076e8e1e1e47802986de54fc33b3b8d33548cfb",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = ROOT / "reports/contact-service-eval/tokenizer-lengths.json"
    raw_output = ROOT / "runs/contact-service-eval/tokenizer-lengths.json.gz"
    if output.exists() or raw_output.exists():
        raise ValueError("Preserve existing evidence; outputs must be new")
    entries, counts, sources = [], Counter(), {}
    for corpus, pin in PINS.items():
        directory = ROOT / "data" / corpus
        assert sha(directory / "manifest.json") == pin
        manifest = json.loads((directory / "manifest.json").read_text())
        assert sha(directory / "cases.jsonl") == manifest["files_sha256"]["cases.jsonl"]
        for name, digest in manifest["configuration"]["source_files_sha256"].items():
            assert sha(ROOT / "jev" / name) == digest
            sources["jev/" + name] = digest
        with (directory / "cases.jsonl").open() as stream:
            for line in stream:
                case = json.loads(line)
                if case["split"] not in ("test", "ood"):
                    continue
                request = case["request"] if corpus.startswith("email") else case["selection_request"]
                requests = [("selection", None, request)]
                if corpus.startswith("phone"):
                    requests += [("attributes", key, phone_attributes(request, key)) for key in request["state"]["candidates"]]
                for stage, candidate, value in requests:
                    counts[corpus + "/" + case["split"] + "/" + stage] += 1
                    for record in compile_request(**value):
                        for index, prompt in enumerate(candidate_prompts(record)):
                            entries.append({"corpus": corpus, "split": case["split"], "case_id": case["id"],
                                            "stage": stage, "candidate_id": candidate, "head": record["id"],
                                            "option_index": index, "prompt": prompt})
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
    raw = {"entries": identities, "result": result}
    raw_output.parent.mkdir(parents=True, exist_ok=True)
    with raw_output.open("xb") as stream:
        stream.write(gzip.compress(json.dumps(raw, separators=(",", ":")).encode(), mtime=0))
    for model in result["models"].values():
        lengths = model.pop("lengths")
        assert len(lengths) == len(entries)
        maximum = max(lengths)
        model.update(sequences=len(lengths), minimum=min(lengths), maximum=maximum,
                     over_4096=sum(n > 4096 for n in lengths), over_16384=sum(n > 16384 for n in lengths),
                     maximum_example=identities[lengths.index(maximum)])
    result.update(status="complete", request_counts=dict(counts), candidate_sequences=len(entries),
                  dataset_manifest_sha256=PINS, source_files_sha256=sources,
                  capture_script_sha256=sha(Path(__file__)), prompt_payload_sha256=hashlib.sha256(wire).hexdigest(),
                  raw_lengths=str(raw_output.relative_to(ROOT)), raw_lengths_sha256=sha(raw_output),
                  scope="Tokenizer-only CPU check using pinned cached revisions and the serving chat-template settings. All held-out A requests and all possible actual phone B candidates; no labels in prompts, no model weights/tensors, GPU allocation, HTTP inference, active-checkout changes or quality measurement. Training split requests are excluded.")
    with output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"report": str(output.relative_to(ROOT)), "models": result["models"]}))


if __name__ == "__main__":
    main()
