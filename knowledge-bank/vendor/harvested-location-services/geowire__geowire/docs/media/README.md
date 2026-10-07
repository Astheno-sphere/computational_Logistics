# Media

Demo GIFs used in the top-level `README.md`.

| File | Shows |
|---|---|
| `geowire-search.gif` | `geowire search "Eiffel Tower"` in the terminal — results table with source attribution + response time |
| `geowire-mcp.gif` | The `@geowirehq/mcp` stdio server: `tools/list` (5 tools) and a real `geocode_address` call |
| `geowire-merge.gif` | The differentiator: your store DB + Google + OSM merged into one record with per-field provenance (real run) |

## Regenerating

Both GIFs are rendered deterministically with Python + Pillow (no screen
recording). The content mirrors real CLI / MCP output.

```bash
pip install Pillow
python make_search_gif.py   # -> geowire-search.gif
python make_mcp_gif.py      # -> geowire-mcp.gif
python make_merge_gif.py    # -> geowire-merge.gif
```

Note: the scripts hard-code the Consolas font path (`C:\Windows\Fonts\consola.ttf`).
On macOS/Linux, point the `ImageFont.truetype(...)` calls at any monospaced font
that includes `→ · ─ ▸ ◂ •` (e.g. JetBrains Mono, Menlo, DejaVu Sans Mono).
