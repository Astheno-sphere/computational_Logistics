"""Evaluate a Tacit model on the JevBench public set or the bev-decision test split, one forward or adaptive.

The model is served by a stock `vllm serve` (one or more replicas); the decisions go through the library's
`Tacit` exactly as a user's would.

    git clone https://github.com/fstandhartinger/jevbench           # the public set, MIT
    vllm serve morriszjm/Tacit-9B --host 127.0.0.1 --port 8000 --max-model-len 32768
    python scripts/eval_tacit.py --model morriszjm/Tacit-9B --servers http://127.0.0.1:8000 \\
        --task jevbench --jevbench ./jevbench --adaptive --out runs/tacit-9b-jevbench
    python scripts/eval_tacit.py --model morriszjm/Tacit-9B --servers http://127.0.0.1:8000 \\
        --task bev --adaptive --out runs/tacit-9b-bev --result bench/results_tacit/<date>/Tacit-9B.bev.json

Every item of the set is decided, in the order the set stores them. The stream is cut into blocks of
`--block` decisions (1,000, the default `cot_window`), each decided by one `decide_batch` call on its own
`Tacit`: a block is exactly one window of the escalation cap, so which decisions escalate depends on that
block alone, and blocks can run in parallel on several servers. Per-decision rows go to `--out` (a rerun
skips finished blocks); `--result` writes the summary that the README tables are read from.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import platform
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from anyjev.question import Question


# ---------------------------------------------------------------- the two test sets, as Tacit requests
def _request(i: int, qid: str, y: int, state: str, q: Question, first_level: Optional[int] = None) -> Dict[str, Any]:
    r = dict(i=i, qid=qid, y=y, state=state, question=q.text, options=list(q.options),
             kind={"noul": "yes_no"}.get(q.kind, q.kind))
    if first_level is not None:
        r["first_level"] = first_level
    return r


def jevbench_items(root: str, expected: Optional[int] = 231) -> List[Dict[str, Any]]:
    """The 231 public JevBench items (`datasets/public/*.jsonl` of a checkout), mapped the way the JevBench
    adapter maps them: the rubric goes into the question text; choice options are the criteria keys; score
    levels are numbered from 0, as JevBench numbers them."""
    out: List[Dict[str, Any]] = []
    for path in sorted(glob.glob(os.path.join(root, "datasets/public/*.jsonl"))):
        for line in open(path):
            rec = json.loads(line)
            q, crit = rec["question"], rec["question"].get("criteria")
            if q["type"] == "noul":
                crit = crit or {}
                labels = ["yes", "no"]                      # Question.noul lists Yes first
                rubric = {"no": crit.get("false", "No"), "yes": crit.get("true", "Yes")}
            elif q["type"] == "score":
                labels = [str(i) for i in range(len(crit))]
                rubric = dict(zip(labels, crit))
            else:
                labels = list(crit)
                rubric = {k: (v or k) for k, v in crit.items()}
            text = q["instructions"] + "\nAllowed answers and rubric: " + json.dumps(rubric, ensure_ascii=False)
            if q["type"] == "noul":
                question, first = Question.noul(text), None
            elif q["type"] == "score":
                question, first = Question.score(text, levels=[rubric[x] for x in labels]), 0
            else:
                question, first = Question.choice(text, labels), None
            state = rec["state"] if isinstance(rec["state"], str) else json.dumps(rec["state"], ensure_ascii=False)
            out.append(_request(len(out), str(rec["id"]), labels.index(str(rec["expected"])), state, question, first))
    if expected is not None and len(out) != expected:
        raise SystemExit("expected the %d public JevBench items under %s, found %d" % (expected, root, len(out)))
    return out


def bev_items(split: str = "test") -> List[Dict[str, Any]]:
    """Every (state, question) pair of avbiswas/bev-decision `split` that is a well-formed choice (2-26
    options), yes/no or score (2-10 levels) question, in the order the split stores them."""
    from datasets import load_dataset

    out: List[Dict[str, Any]] = []
    for row in load_dataset("avbiswas/bev-decision")[split]:
        try:
            qs = json.loads(row["questions_json"])
        except Exception:  # noqa: BLE001 - a malformed row is skipped, as the published evaluation did
            continue
        for qid, spec in qs.items():
            kind, crit, lab = spec.get("type"), spec.get("criteria"), spec.get("label")
            try:
                if kind == "choice":
                    if not isinstance(crit, dict) or not 2 <= len(crit) <= 26 or lab not in crit:
                        continue
                    keys = list(crit.keys())
                    q, y = Question.choice(spec["instructions"], [str(crit[k]) for k in keys]), keys.index(lab)
                elif kind == "noul":
                    if not isinstance(lab, bool):
                        continue
                    q, y = Question.noul(spec["instructions"]), 0 if lab else 1
                elif kind == "score":
                    if not isinstance(crit, list) or not 2 <= len(crit) <= 10:
                        continue
                    if not isinstance(lab, int) or not 0 <= lab < len(crit):
                        continue
                    q, y = Question.score(spec["instructions"], levels=[str(x) for x in crit]), lab
                else:
                    continue
            except Exception:  # noqa: BLE001 - e.g. duplicate options
                continue
            out.append(_request(len(out), qid, y, row["state"], q))
    return out


# ---------------------------------------------------------------- running and summarising
def run(items, model: str, servers: List[str], out: str, *, adaptive: bool, block: int, tau: float,
        max_cot_share: float, cot_max_tokens: int, per_server: int = 2) -> float:
    from transformers import AutoTokenizer

    from anyjev.tacit import ServerEngine, Tacit

    tok = AutoTokenizer.from_pretrained(model)
    blocks = [items[i:i + block] for i in range(0, len(items), block)]
    os.makedirs(out, exist_ok=True)

    def one(k):
        path = os.path.join(out, "block_%04d.jsonl" % k)
        if os.path.exists(path):
            return k, "skipped"
        t = Tacit(ServerEngine(servers[k % len(servers)], model, tok), tok, adaptive=adaptive, tau=tau,
                  max_cot_share=max_cot_share, cot_window=block, cot_max_tokens=cot_max_tokens, batch_size=1 << 30)
        keys = ("state", "question", "options", "kind", "first_level")
        t0 = time.time()
        got = t.decide_batch([{key: it[key] for key in keys if key in it} for it in blocks[k]])
        rows = []
        for it, d in zip(blocks[k], got):
            fp = d.get("first_pass", d)
            rows.append(dict(i=it["i"], qid=it["qid"], y=it["y"], index=d["index"], margin=d["margin"],
                             route=d["route"], first_index=fp["index"], first_margin=fp["margin"],
                             reasoning_tokens=d.get("reasoning_tokens", 0),
                             probs=[round(float(p), 6) for p in d["probs"].values()]))
        with open(path + ".part", "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            f.write(json.dumps(dict(block=k, seconds=time.time() - t0, stats=t.stats)) + "\n")
        os.replace(path + ".part", path)
        return k, "escalated %d of %d" % (t.escalated, t.decisions)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=len(servers) * per_server) as ex:
        for k, msg in ex.map(one, range(len(blocks))):
            print("block %d/%d: %s (%.0fs)" % (k + 1, len(blocks), msg, time.time() - t0), flush=True)
    return time.time() - t0


def summarise(items, out: str, tau: float) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for f in sorted(glob.glob(os.path.join(out, "block_*.jsonl"))):
        rows += [json.loads(x) for x in open(f)][:-1]
    if len(rows) != len(items):
        raise SystemExit("%s holds %d of %d decisions" % (out, len(rows), len(items)))
    n = len(rows)
    cot = [r for r in rows if r["route"] == "cot"]
    tokens = sum(r["reasoning_tokens"] for r in rows)
    return dict(n=n, one_forward=dict(correct=sum(r["first_index"] == r["y"] for r in rows)),
                adaptive=dict(correct=sum(r["index"] == r["y"] for r in rows), escalated=len(cot),
                              below_tau=sum(r["first_margin"] < tau for r in rows), reasoning_tokens=tokens),
                escalated_decisions=dict(correct_before=sum(r["first_index"] == r["y"] for r in cot),
                                         correct_after=sum(r["index"] == r["y"] for r in cot)))


def _server_version(url: str) -> Optional[str]:
    try:
        with urllib.request.urlopen(url.rstrip("/").removesuffix("/v1") + "/version", timeout=10) as r:
            return json.loads(r.read()).get("version")
    except Exception:  # noqa: BLE001 - the version is recorded when the server reports it
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", required=True, help="the repo the servers serve, e.g. morriszjm/Tacit-9B")
    ap.add_argument("--servers", required=True, help="comma-separated `vllm serve` URLs")
    ap.add_argument("--task", required=True, choices=["jevbench", "bev"])
    ap.add_argument("--jevbench", help="a checkout of github.com/fstandhartinger/jevbench (for --task jevbench)")
    ap.add_argument("--adaptive", action="store_true", help="escalate low-margin decisions to reasoning")
    ap.add_argument("--tau", type=float, default=0.5)
    ap.add_argument("--max-cot-share", type=float, default=0.2)
    ap.add_argument("--cot-max-tokens", type=int, default=8192)
    ap.add_argument("--block", type=int, default=1000, help="decisions per block = the cap's window")
    ap.add_argument("--per-server", type=int, default=2, help="blocks in flight per server")
    ap.add_argument("--out", required=True, help="directory for the per-decision rows")
    ap.add_argument("--result", help="write the summary JSON here")
    ap.add_argument("--hardware", default="", help="recorded in the summary, e.g. '4x H100 NVL'")
    a = ap.parse_args(argv)
    import anyjev

    if a.task == "jevbench" and not a.jevbench:
        ap.error("--task jevbench needs --jevbench <checkout>")
    items = jevbench_items(a.jevbench) if a.task == "jevbench" else bev_items("test")
    servers = a.servers.split(",")
    seconds = run(items, a.model, servers, a.out, adaptive=a.adaptive, block=a.block, tau=a.tau,
                  max_cot_share=a.max_cot_share, cot_max_tokens=a.cot_max_tokens, per_server=a.per_server)
    s = summarise(items, a.out, a.tau)
    s.update(model=a.model, task={"jevbench": "JevBench public set", "bev": "bev-decision test split"}[a.task],
             settings=dict(adaptive=a.adaptive, tau=a.tau, max_cot_share=a.max_cot_share, cot_window=a.block,
                           cot_max_tokens=a.cot_max_tokens, block=a.block, order="as stored"),
             env=dict(anyjev=anyjev.__version__, engine="vllm serve", vllm=_server_version(servers[0]),
                      replicas=len(servers), hardware=a.hardware, python=platform.python_version()),
             seconds=round(seconds, 1), date=dt.date.today().isoformat(),
             command="python scripts/eval_tacit.py " + " ".join(sys.argv[1:] if argv is None else argv))
    n = s["n"]
    print("%s %s n=%d one forward %.4f%s" % (a.model, a.task, n, s["one_forward"]["correct"] / n,
          " adaptive %.4f, escalated %.1f%%" % (s["adaptive"]["correct"] / n, 100 * s["adaptive"]["escalated"] / n)
          if a.adaptive else ""))
    if a.result:
        os.makedirs(os.path.dirname(a.result) or ".", exist_ok=True)
        with open(a.result, "w") as f:
            json.dump(s, f, indent=2)
            f.write("\n")


if __name__ == "__main__":
    main()
