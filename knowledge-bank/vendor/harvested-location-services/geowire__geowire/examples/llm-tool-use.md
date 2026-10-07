# GeoWire as an LLM tool (OpenAI / Anthropic function calling)

Give any function-calling LLM real-world place data. Two paths: **MCP** (the LLM
client loads GeoWire's 5 tools automatically) or a **hand-written tool** over the
REST API (shown here, framework-free).

Start a server first: `npx @geowirehq/cli` → `http://localhost:4980`.

## OpenAI (function calling over REST)

```python
import json, requests
from openai import OpenAI

client = OpenAI()

tools = [{
    "type": "function",
    "function": {
        "name": "search_places",
        "description": "Search real-world places by natural-language query, optionally near a coordinate.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "near": {"type": "object", "properties": {
                    "latitude": {"type": "number"}, "longitude": {"type": "number"}}},
                "radiusMeters": {"type": "number"},
            },
            "required": ["query"],
        },
    },
}]

def search_places(**args):
    r = requests.post("http://localhost:4980/v1/places/search", json=args, timeout=10)
    r.raise_for_status()
    return r.json()

messages = [{"role": "user", "content": "Find a Starbucks within 3km of 37.7749, -122.4194"}]
resp = client.chat.completions.create(model="gpt-4o", messages=messages, tools=tools)

call = resp.choices[0].message.tool_calls[0]
result = search_places(**json.loads(call.function.arguments))
print(result["results"][0]["name"], result["meta"]["providersUsed"])
```

## Anthropic (tool use over REST)

```python
import requests
from anthropic import Anthropic

client = Anthropic()

tools = [{
    "name": "search_places",
    "description": "Search real-world places by natural-language query, optionally near a coordinate.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "near": {"type": "object", "properties": {
                "latitude": {"type": "number"}, "longitude": {"type": "number"}}},
        },
        "required": ["query"],
    },
}]

msg = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "Where is the Eiffel Tower?"}],
)

for block in msg.content:
    if block.type == "tool_use":
        r = requests.post("http://localhost:4980/v1/places/search", json=block.input, timeout=10)
        print(r.json()["results"][0])
```

## Skip the glue: use MCP

Both OpenAI and Anthropic ecosystems have MCP adapters that load GeoWire's 5
tools (`search_places`, `geocode_address`, `reverse_geocode`, `get_place`,
`list_geo_providers`) directly — no hand-written schemas:

```bash
npx -y @geowirehq/mcp        # stdio
# or POST http://localhost:4980/mcp  (HTTP)
```

See [mcp-clients.md](./mcp-clients.md) for ready-made client configs.
