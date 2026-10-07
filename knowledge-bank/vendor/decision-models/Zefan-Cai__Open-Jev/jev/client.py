"""Standard-library client. The supplied endpoint is the only request target."""
import json
from urllib.request import Request, urlopen


class Client:
    def __init__(self, endpoint="http://127.0.0.1:8791/v1/systemone", timeout=300):
        self.endpoint, self.timeout = endpoint, timeout

    def ask(self, state, questions, model="open-jev"):
        request = Request(self.endpoint, json.dumps({"model": model, "state": state,
                          "questions": questions}, allow_nan=False).encode(),
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=self.timeout) as response:
            result = json.load(response)
        if set(result.get("answers", {})) != set(questions):
            raise ValueError("response question IDs do not match the request")
        return result
