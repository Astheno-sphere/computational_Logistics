from typing import Any
import text_helper.models as hm
from text_helper.type import EnvOb, EnvObCode

REGISTERED_MODELS: dict[EnvObCode, Any] = {
    "transfer": hm.EnvObTransfer,
    "transit": hm.EnvObTransit,
    "arrival": hm.EnvObArrival,
    "travel_plan": hm.TravelPlanWrapper,
    "travel_plan_query": hm.TravelPlanLiteWrapper,
    "wait_in_stop": hm.EnvObWaitInStop,
}

def env_ob_to_text(code: EnvObCode, ob: dict, purpose: str = None) -> str:
    if code not in REGISTERED_MODELS:
        raise ValueError(f"Unknown EnvOb type: {code}")

    text = REGISTERED_MODELS[code](**ob).describe().strip()
    # if purpose and code != "arrival":
    #     text = f" Heading to {purpose}; {text[0].lower() + text[1:]}"
    return text

def parse_ob(code: EnvObCode, ob: dict) -> EnvOb:
    if code not in REGISTERED_MODELS:
        raise ValueError(f"Unknown EnvOb type: {code}")
    return REGISTERED_MODELS[code](**ob)
