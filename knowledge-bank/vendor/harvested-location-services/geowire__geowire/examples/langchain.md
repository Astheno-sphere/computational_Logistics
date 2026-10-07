# GeoWire from Python / LangChain

GeoWire exposes a plain REST API, so any Python agent can call it. Start the
server first:

```bash
npx @geowirehq/cli            # http://localhost:4980
```

## Plain REST (requests)

```python
import requests

def search_places(query, near=None, limit=10):
    r = requests.post("http://localhost:4980/v1/places/search",
                      json={"query": query, "near": near, "limit": limit}, timeout=10)
    r.raise_for_status()
    return r.json()["results"]

for p in search_places("pharmacy", near={"latitude": 10.7769, "longitude": 106.7009}):
    print(p["name"], p["location"], [s["provider"] for s in p["sources"]])
```

## As a LangChain tool

```python
from langchain_core.tools import tool
import requests

@tool
def search_places(query: str) -> list[dict]:
    """Search for real-world places (businesses, POIs) by natural-language query."""
    r = requests.post("http://localhost:4980/v1/places/search",
                      json={"query": query, "limit": 5}, timeout=10)
    r.raise_for_status()
    return r.json()["results"]

# agent = create_react_agent(llm, tools=[search_places])
```

## Or connect over MCP

GeoWire is also an MCP server (`npx @geowirehq/mcp` for stdio, or `POST /mcp` for
HTTP). Use any MCP client adapter (e.g. `langchain-mcp-adapters`) to load its 5
tools directly.
