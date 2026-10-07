"""Module D: local web dashboard for claw-tsaver token savings."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

LOG_PATH = Path.home() / ".claw-tsaver" / "log.jsonl"

_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>claw-tsaver</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,sans-serif;background:#f4f4f4;color:#222}
.wrap{max-width:1000px;margin:0 auto;padding:28px 16px}
h1{font-size:1.3rem;font-weight:700;margin-bottom:24px;color:#111}
.cards{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:24px}
.card{flex:1;min-width:160px;background:#fff;border:1px solid #ddd;
      border-radius:8px;padding:18px 20px}
.card .lbl{font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;
           color:#666;margin-bottom:6px}
.card .val{font-size:1.9rem;font-weight:700;color:#111}
.box{background:#fff;border:1px solid #ddd;border-radius:8px;
     padding:18px 20px;margin-bottom:20px}
.box h2{font-size:.75rem;text-transform:uppercase;letter-spacing:.06em;
        color:#555;margin-bottom:14px;font-weight:600}
.chart-wrap{position:relative;height:200px}
table{width:100%;border-collapse:collapse;font-size:.82rem}
th{text-align:left;padding:6px 10px;border-bottom:2px solid #e8e8e8;
   color:#555;font-weight:600;white-space:nowrap}
td{padding:6px 10px;border-bottom:1px solid #f0f0f0;color:#333}
tr:last-child td{border-bottom:none}
.y{background:#e8f5e9;color:#2e7d32;padding:1px 6px;
   border-radius:3px;font-size:.72rem}
.n{background:#f0f0f0;color:#888;padding:1px 6px;
   border-radius:3px;font-size:.72rem}
.foot{font-size:.68rem;color:#aaa;text-align:right;margin-top:6px}
</style>
</head>
<body>
<div class="wrap">
  <h1>claw-tsaver &middot; token savings</h1>
  <div class="cards">
    <div class="card"><div class="lbl">Today saved</div>
      <div class="val" id="c_today">—</div></div>
    <div class="card"><div class="lbl">All-time saved</div>
      <div class="val" id="c_alltime">—</div></div>
    <div class="card"><div class="lbl">Compression rate</div>
      <div class="val" id="c_rate">—</div></div>
    <div class="card"><div class="lbl">Total calls</div>
      <div class="val" id="c_calls">—</div></div>
  </div>

  <div class="box">
    <h2>Tokens saved by tool</h2>
    <div class="chart-wrap"><canvas id="toolChart"></canvas></div>
  </div>

  <div class="box">
    <h2>Recent calls</h2>
    <table>
      <thead><tr>
        <th>Time</th><th>Tool</th><th>Original</th>
        <th>Returned</th><th>Saved</th><th>Compressed</th>
      </tr></thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>

  <div class="foot" id="foot">loading…</div>
</div>
<script>
let chart=null;
const $=id=>document.getElementById(id);
const fmt=n=>Number(n).toLocaleString();
const pct=f=>((f||0)*100).toFixed(1)+'%';
const ts2s=ts=>{
  const d=new Date(ts*1000);
  return d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});
};
async function refresh(){
  try{
    const d=await(await fetch('/api/stats')).json();
    $('c_today').textContent=fmt(d.today_saved);
    $('c_alltime').textContent=fmt(d.alltime_saved);
    $('c_rate').textContent=pct(d.compression_rate);
    $('c_calls').textContent=fmt(d.total_calls);
    const tb=$('tbody');
    tb.innerHTML='';
    for(const r of d.recent){
      const tr=document.createElement('tr');
      tr.innerHTML=`<td>${ts2s(r.ts)}</td><td>${r.tool}</td>`+
        `<td>${fmt(r.original_tokens)}</td><td>${fmt(r.returned_tokens)}</td>`+
        `<td>${fmt(r.saved)}</td>`+
        `<td><span class="${r.compressed?'y':'n'}">${r.compressed?'yes':'no'}</span></td>`;
      tb.appendChild(tr);
    }
    const labels=d.by_tool.map(x=>x.tool);
    const vals=d.by_tool.map(x=>x.saved);
    if(!chart){
      chart=new Chart($('toolChart').getContext('2d'),{
        type:'bar',
        data:{labels,datasets:[{label:'Tokens saved',data:vals,
          backgroundColor:'#555',borderRadius:3}]},
        options:{responsive:true,maintainAspectRatio:false,
          plugins:{legend:{display:false}},
          scales:{y:{beginAtZero:true}}}
      });
    }else{
      chart.data.labels=labels;
      chart.data.datasets[0].data=vals;
      chart.update();
    }
    $('foot').textContent='Last updated: '+new Date().toLocaleTimeString();
  }catch(e){
    $('foot').textContent='Error: '+e.message;
  }
}
refresh();
setInterval(refresh,3000);
</script>
</body>
</html>
"""

app = FastAPI(title="claw-tsaver dashboard", docs_url=None, redoc_url=None)


def _read_log() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    rows: list[dict] = []
    try:
        with LOG_PATH.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return rows


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _HTML


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/stats")
def stats() -> JSONResponse:
    rows = _read_log()

    today_start = (
        datetime.now()
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .timestamp()
    )

    today_saved = 0
    alltime_saved = 0
    alltime_original = 0
    compressed_calls = 0
    by_tool: dict[str, dict] = {}

    for row in rows:
        saved = int(row.get("saved", 0))
        original = int(row.get("original_tokens", 0))
        tool = str(row.get("tool", "unknown"))
        ts = float(row.get("ts", 0))
        compressed = bool(row.get("compressed", False))

        alltime_saved += saved
        alltime_original += original
        if compressed:
            compressed_calls += 1
        if ts >= today_start:
            today_saved += saved

        entry = by_tool.setdefault(tool, {"tool": tool, "saved": 0, "calls": 0})
        entry["saved"] += saved
        entry["calls"] += 1

    compression_rate = (
        alltime_saved / alltime_original if alltime_original > 0 else 0.0
    )

    recent_rows = sorted(rows, key=lambda r: r.get("ts", 0), reverse=True)[:50]
    recent_out = [
        {
            "ts": int(r.get("ts", 0)),
            "tool": str(r.get("tool", "unknown")),
            "original_tokens": int(r.get("original_tokens", 0)),
            "returned_tokens": int(r.get("returned_tokens", 0)),
            "saved": int(r.get("saved", 0)),
            "compressed": bool(r.get("compressed", False)),
        }
        for r in recent_rows
    ]

    return JSONResponse(
        {
            "today_saved": today_saved,
            "alltime_saved": alltime_saved,
            "compression_rate": round(compression_rate, 4),
            "total_calls": len(rows),
            "compressed_calls": compressed_calls,
            "by_tool": sorted(
                by_tool.values(), key=lambda x: x["saved"], reverse=True
            ),
            "recent": recent_out,
        }
    )


def run() -> None:
    """Start the dashboard server on localhost:7878 (blocking)."""
    uvicorn.run(app, host="127.0.0.1", port=7878)
