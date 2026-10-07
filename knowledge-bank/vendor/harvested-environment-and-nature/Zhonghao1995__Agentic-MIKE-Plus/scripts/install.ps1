# One-command setup for Agentic MIKE+ on Windows + Claude Code.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\install.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "[1/4] Creating Python 3.11 venv (.venv) ..."
py -3.11 -m venv .venv
$py = Join-Path $root ".venv\Scripts\python.exe"

Write-Host "[2/4] Installing pinned dependencies + the package (incl. the [run] extra) ..."
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.lock
& $py -m pip install -e ".[run]"   # read/plot only needs `-e .` (no mikeplus / license)

Write-Host "[3/4] Registering the MCP server with Claude Code ..."
$addCmd = "claude mcp add mike-plus -- `"$py`" -m mikeplus_mcp.server"
if (Get-Command claude -ErrorAction SilentlyContinue) {
    claude mcp add mike-plus -- "$py" -m mikeplus_mcp.server
    Write-Host "  registered 'mike-plus' with Claude Code."
} else {
    Write-Host "  Claude CLI not found on PATH. Register manually with:"
    Write-Host "    $addCmd"
}

Write-Host "[4/4] Smoke test (license-free tool discovery) ..."
& $py scripts\smoke_test.py

Write-Host ""
Write-Host "Done. Restart Claude Code if it was open; the 'mike-plus' tools are now available."
Write-Host "Reading results / plotting need no MIKE+ license; running or editing a model does."
