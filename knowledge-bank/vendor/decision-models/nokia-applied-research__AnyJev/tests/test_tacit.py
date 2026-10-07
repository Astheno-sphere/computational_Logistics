"""Tacit on CPU: the training prompt, the escalation cap, concurrency and the HTTP gateway, with a fake
engine (no model, numpy only)."""
import json
import math
import sys
import threading
import urllib.error
import urllib.request

import numpy as np
import pytest

from anyjev import Decider, Question
from anyjev.backends.fake import FakeBackend, FakeTokenizer
from anyjev.readout import DEFAULT_SYSTEM
from anyjev.serve import make_server
from anyjev.tacit import Tacit, restricted_logprobs


class FakeEngine:
    """'unsure' in the state gives a margin of 0.1, anything else 3.0; reasoning answers option 0."""

    def __init__(self):
        self.read_texts, self.reason_prompts = [], []

    def read(self, texts, label_ids):
        self.read_texts += texts
        out = []
        for t, ids in zip(texts, label_ids):
            z = np.zeros(len(ids))
            z[0] = 0.1 if "unsure" in t else 3.0
            out.append(restricted_logprobs(z))
        return out

    def reason_read(self, prompts, label_ids, max_tokens, sampling):
        self.reason_prompts += prompts
        return [(restricted_logprobs([5.0] + [0.0] * (len(ids) - 1)), 7) for ids in label_ids]


def make(**kw):
    eng = FakeEngine()
    return Tacit(eng, FakeTokenizer(), **kw), eng


# ---------------------------------------------------------------- the prompt the models were trained on
def test_one_forward_prompt_is_the_training_prompt():
    t, eng = make()
    t.decide(state="S", question="Q?", options=["track_order", "refund"])
    t.decide(state="S", question="Q?", kind="yes_no")
    t.decide(state="S", question="Q?", options=["low", "mid", "high"], kind="score")
    head = DEFAULT_SYSTEM + "\n\nState:\nS\n\nQuestion: Q?\n"
    assert eng.read_texts == [
        head + "Options:\nA. track_order\nB. refund\nAnswer with the letter only.\nAnswer:",
        head + "Answer Yes or No.\nAnswer:",
        head + "Pick the level that applies (the levels are ordered):\n1. low\n2. mid\n3. high\n"
               "Answer with the number only.\nAnswer:",
    ]


def test_decider_raw_reads_the_same_prompt():
    # a Tacit checkpoint is also an ordinary causal LM: Decider(level="raw") asks it exactly what Tacit asks
    seen = []

    class Spy(FakeBackend):
        def next_token_logprobs(self, prompts, token_ids):
            seen.extend(prompts)
            return super().next_token_logprobs(prompts, token_ids)

    d = Decider(Spy(lambda s, o: 0.0), level="raw")
    d.decide("S", [Question.choice("Q?", ["track_order", "refund"])])
    d.decide("S", [Question.noul("Q?")])
    d.decide("S", [Question.score("Q?", levels=["low", "mid", "high"])])
    t, eng = make()
    t.decide(state="S", question="Q?", options=["track_order", "refund"])
    t.decide(state="S", question="Q?", kind="yes_no")
    t.decide(state="S", question="Q?", options=["low", "mid", "high"], kind="score")
    assert seen == eng.read_texts


def test_score_levels_can_be_numbered_from_zero():
    t, eng = make()
    t.decide(state="S", question="Q?", options=["none", "some", "all"], kind="score", first_level=0)
    assert eng.read_texts[-1].endswith("Pick the level that applies (the levels are ordered):\n0. none\n1. some\n"
                                       "2. all\nAnswer with the number only.\nAnswer:")
    with pytest.raises(ValueError):
        t.decide(state="S", question="Q?", options=["a", "b"], kind="score", first_level=2)


def test_result_shape():
    t, _ = make()
    d = t.decide(state="S", question="Q?", options=["a", "b", "c"])
    assert d["answer"] == "a" and d["index"] == 0 and d["route"] == "one_forward"
    assert set(d["probs"]) == {"a", "b", "c"} and math.isclose(sum(d["probs"].values()), 1.0)
    assert d["margin"] == pytest.approx(3.0)
    y = t.decide(state="S", question="Q?", kind="yes_no")
    assert y["answer"] == "Yes" and set(y["probs"]) == {"Yes", "No"}


@pytest.mark.parametrize("item", [dict(question="Q", options=["a"]), dict(question="Q", options=["a", "a"]),
                                  dict(question="Q", options=["a", "b"], kind="rank"), dict(options=["a", "b"])])
def test_bad_requests_raise_value_error(item):
    t, _ = make()
    with pytest.raises(ValueError):
        t.decide_batch([item])


def test_restricted_logprobs():
    lp = restricted_logprobs([0.0, -math.inf, 0.0])
    assert np.exp(lp).tolist() == pytest.approx([0.5, 0.0, 0.5])
    assert np.exp(restricted_logprobs([-math.inf, -math.inf])).tolist() == pytest.approx([0.5, 0.5])


# ---------------------------------------------------------------- escalation and its cap
def test_nothing_escalates_unless_adaptive():
    t, eng = make()
    assert t.decide(state="unsure", question="Q", options=["a", "b"])["route"] == "one_forward"
    assert eng.reason_prompts == []


def test_escalated_decision_reports_its_route_and_first_pass():
    t, eng = make(adaptive=True, max_cot_share=None)
    d = t.decide(state="unsure", question="Q?", options=["a", "b", "c"])
    assert d["route"] == "cot" and d["reasoning_tokens"] == 7 and d["answer"] == "a"
    assert d["first_pass"]["route"] == "one_forward" and d["first_pass"]["margin"] == pytest.approx(0.1)
    assert eng.reason_prompts[0].endswith("exactly this form:\nAnswer: <option letter>\n")


def run(window, stream, batch=1):
    t, _ = make(adaptive=True, tau=0.5, max_cot_share=0.2, cot_window=window)
    routes = []
    for i in range(0, len(stream), batch):
        out = t.decide_batch([dict(state=s, question="Q", options=["a", "b"]) for s in stream[i:i + batch]])
        routes += [d["route"] == "cot" for d in out]
    return routes, t


@pytest.mark.parametrize("batch", [1, 64])
def test_window_cap_holds_after_a_long_quiet_run(batch):
    # 10,000 confident decisions, then a burst of 2,000 unsure ones: the cap holds over the last 1,000
    routes, t = run(1000, ["sure"] * 10000 + ["unsure"] * 2000, batch)
    ends = [e for e in range(batch, len(routes) + 1, batch) if e >= 1000]
    ends += [len(routes)] if len(routes) % batch else []
    assert max(sum(routes[e - 1000:e]) for e in ends) <= 200
    assert sum(routes[10000:]) <= 0.2 * 2000 + batch


def test_cumulative_cap_banks_unused_budget():
    # the reason the default is a window: counted since loading, the same burst escalates entirely
    routes, _ = run(None, ["sure"] * 10000 + ["unsure"] * 2000)
    assert sum(routes[10000:]) == 2000


def test_cold_start():
    routes, t = run(1000, ["unsure"] * 50)
    assert sum(routes) == 10
    routes, t = run(1000, ["unsure"] * 10, batch=10)
    assert sum(routes) == 2 and t.stats["window_cot_share"] == pytest.approx(0.2)


def test_concurrent_callers_share_one_cap():
    t, _ = make(adaptive=True, tau=0.5, max_cot_share=0.2, cot_window=1000)

    def worker():
        for _ in range(100):
            t.decide(state="unsure", question="Q", options=["a", "b"])

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert t.decisions == 800 and t.escalated == sum(t._recent)
    assert t.escalated <= math.ceil(0.2 * 800) + 1


@pytest.mark.parametrize("url", ["http://127.0.0.1:8000", "http://127.0.0.1:8000/", "http://127.0.0.1:8000/v1",
                                 "http://127.0.0.1:8000/v1/"])
def test_server_engine_takes_the_root_or_the_v1_url(url):
    from anyjev.tacit import ServerEngine
    assert ServerEngine(url, "m", FakeTokenizer()).url == "http://127.0.0.1:8000/v1/completions"


def test_no_engine_imports_at_import_time():
    import anyjev.tacit  # noqa: F401
    assert "vllm" not in sys.modules


# ---------------------------------------------------------------- the HTTP gateway
@pytest.fixture
def gateway():
    t, _ = make(adaptive=True, tau=0.5, max_cot_share=None)
    server = make_server(t, "127.0.0.1", 0)
    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()
    yield "http://127.0.0.1:%d" % server.server_address[1]
    server.shutdown()


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def test_gateway_round_trip(gateway):
    d = post(gateway + "/v1/decide", {"state": "S", "question": "Q?", "options": ["a", "b"]})
    assert d["answer"] == "a" and d["route"] == "one_forward"
    b = post(gateway + "/v1/decide", {"items": [{"state": "unsure", "question": "Q?", "options": ["a", "b"]},
                                                {"state": "S", "question": "Ok?", "kind": "yes_no"}]})
    assert [x["route"] for x in b["decisions"]] == ["cot", "one_forward"]
    stats = json.loads(urllib.request.urlopen(gateway + "/v1/stats").read())
    assert stats["decisions"] == 3 and stats["escalated"] == 1
    assert json.loads(urllib.request.urlopen(gateway + "/health").read()) == {"ok": True}


def test_gateway_rejects_a_malformed_request(gateway):
    with pytest.raises(urllib.error.HTTPError) as e:
        post(gateway + "/v1/decide", {"question": "Q", "options": ["only one"]})
    assert e.value.code == 400
    with pytest.raises(urllib.error.HTTPError) as e:
        post(gateway + "/v1/other", {})
    assert e.value.code == 404
