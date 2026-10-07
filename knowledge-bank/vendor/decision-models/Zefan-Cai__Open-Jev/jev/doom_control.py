"""Versioned Doom runtime contract matching frozen vizdoom-basic-v1 inputs.

Movement and attack drive buttons. Alignment is a recorded model judgment;
it never repairs or overrides an action. No teacher is used in this module.
"""

import copy
import math

from .api import compile_request, format_response
from .case_doom import MOVEMENTS, SCORE_OPTIONS


DECISION_MODES = ("combined-v1", "typed-v1")
ATTACK_THRESHOLD = 0.5


def typed_request(state):
    # Keep these strings/options identical to the frozen training rows. Tests
    # compare candidate prompts with records_from_episode and the saved corpus.
    request = {"state": copy.deepcopy(state), "questions": {
        "movement": {"type": "choice", "instructions": "Which lateral movement does the momentum-aware tracking policy choose to align with the nearest visible target?",
                     "criteria": dict.fromkeys(MOVEMENTS)},
        "attack": {"type": "noul", "instructions": "Should the tracking policy press attack now: a visible target is within 3 degrees, ammunition remains, and the player is alive?"},
        "alignment": {"type": "score", "instructions": "Rate the current shot alignment using the supplied ordered suitability grades. These grades are an aiming heuristic, not expected game reward.",
                      "criteria": list(SCORE_OPTIONS)},
    }}
    compile_request(**request)
    return request


def is_typed_request(request):
    return set(request.get("questions", {})) == {"movement", "attack", "alignment"}


def decode_answers(request, answers):
    """Validate every model head, then project only movement/attack to buttons."""
    if request != typed_request(request["state"]):
        raise ValueError("Doom typed request differs from the frozen training contract")
    if not isinstance(answers, dict) or set(answers) != set(request["questions"]):
        raise ValueError("Doom response must answer movement, attack, and alignment exactly")
    records, probabilities = compile_request(**request), []
    for record in records:
        answer = answers[record["id"]]
        if not isinstance(answer, dict) or answer.get("type") != record["kind"]:
            raise ValueError("Doom answer type differs from its requested head")
        if record["kind"] == "noul":
            p = answer.get("noul")
            if type(p) not in (int, float) or not math.isfinite(p):
                raise ValueError("Doom attack must be a finite probability")
            probabilities.append([1 - p, p])
        else:
            values = answer.get("probabilities")
            if not isinstance(values, dict) or set(values) != set(record["answer_keys"]):
                raise ValueError("Doom probabilities must cover exactly the offered candidates")
            if any(type(p) not in (int, float) or not math.isfinite(p) for p in values.values()):
                raise ValueError("Doom probabilities must be finite numbers, not booleans or strings")
            probabilities.append([values[key] for key in record["answer_keys"]])
    normalized = format_response(records, probabilities)["answers"]
    for key in ("movement", "alignment"):
        confidence = answers[key].get("confidence")
        if (type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1
                or not math.isclose(confidence, normalized[key]["confidence"], abs_tol=1e-6)):
            raise ValueError("Doom confidence must match its probability distribution")
    if answers["alignment"].get("legend") != normalized["alignment"]["legend"]:
        raise ValueError("Doom alignment legend differs from the offered training levels")
    movement = answers["movement"].get("choice")
    distribution = normalized["movement"]["probabilities"]
    if movement not in distribution or distribution[movement] != max(distribution.values()):
        raise ValueError("Doom movement must select a maximum-probability offered candidate")
    alignment = answers["alignment"].get("score")
    if (type(alignment) not in (int, float) or not math.isfinite(alignment) or not 0 <= alignment <= len(SCORE_OPTIONS) - 1
            or not math.isclose(alignment, normalized["alignment"]["score"], abs_tol=1e-6)):
        raise ValueError("Doom alignment Score must match its probability distribution")
    attack_probability = normalized["attack"]["noul"]
    attack = attack_probability >= ATTACK_THRESHOLD
    lateral = ("left", "right", "hold")[MOVEMENTS.index(movement)]
    return {"movement": movement, "attack_probability": attack_probability,
            "attack_threshold": ATTACK_THRESHOLD, "attack": attack,
            "alignment_score": alignment,
            "action": lateral + ("_attack" if attack else "_wait"),
            "buttons": [lateral == "left", lateral == "right", attack]}
