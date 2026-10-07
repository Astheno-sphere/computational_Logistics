"""
Greeks / Aetherfy Analytics — MCP server.

Exposes the commercial (derived-data) endpoints of the Greeks Analytics API as
Model Context Protocol tools so any MCP client (Claude Desktop, Cursor, etc.) can
pull real-time options analytics — Greeks, GEX/DEX, Max Pain, Flow, IV surface,
Expected Move, Sentiment — straight into a conversation.

Only the commercial /api/analytics/* surface is wrapped. Raw-data /internal/*
routes are intentionally NOT exposed: they are internal-only and not part of the
commercial offering.

Auth: set GREEKS_API_KEY (the grk_<48hex> key from POST /api/auth/keys). The base
URL defaults to the public API and can be overridden with GREEKS_BASE_URL for
local dev (http://localhost:8080).

Run:
    GREEKS_API_KEY=grk_... greeks-mcp        # or: python -m greeks_mcp

Transport is stdio by default (what MCP clients spawn). Set MCP_TRANSPORT=http to
serve over streamable HTTP instead.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_BASE_URL = "https://api.greeks.pro"

BASE_URL = os.environ.get("GREEKS_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
API_KEY = os.environ.get("GREEKS_API_KEY", "").strip()
# Seconds. Analytics with expiration=all can be slow (full chain), so keep this
# generous but bounded.
TIMEOUT = float(os.environ.get("GREEKS_TIMEOUT", "30"))

mcp = FastMCP("greeks-analytics")


# ─────────────────────────────────────────────────────────────────────────────
# HTTP helper
# ─────────────────────────────────────────────────────────────────────────────

class GreeksAPIError(RuntimeError):
    """Raised with a human-readable message when the API returns a non-2xx."""


def _headers(require_key: bool = True) -> dict[str, str]:
    """Build request headers.

    When require_key is True (commercial /api/analytics/* routes) a missing key is
    a hard error. Public routes pass require_key=False: the key is attached if
    present (harmless) but its absence is fine.
    """
    headers = {"Accept": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    elif require_key:
        raise GreeksAPIError(
            "GREEKS_API_KEY is not set. Create a key at POST /api/auth/keys and "
            "export it as GREEKS_API_KEY (format grk_<48 hex>)."
        )
    return headers


def _explain_status(status: int, body: str) -> str:
    """Map the API's status codes to actionable guidance."""
    hints = {
        400: "Bad request — check the symbol / expiration parameters.",
        401: "Unauthorized — GREEKS_API_KEY is missing or invalid.",
        402: "Payment required — this endpoint needs a higher plan.",
        403: "Forbidden — your plan does not include this route, or the symbol "
             "count / rate limit for your plan was exceeded.",
        404: "Not found — no options chain available for that symbol/expiration.",
        429: "Rate limited — you exceeded your plan's requests-per-minute.",
        500: "Server error — try again shortly.",
    }
    hint = hints.get(status, "")
    body = (body or "").strip()
    if len(body) > 500:
        body = body[:500] + "…"
    parts = [f"HTTP {status}"]
    if hint:
        parts.append(hint)
    if body:
        parts.append(f"Response: {body}")
    return " ".join(parts)


def _get(path: str, params: dict[str, Any], auth: bool = True) -> Any:
    """GET {BASE_URL}{path}, returning parsed JSON.

    Drops params whose value is None/empty so we never send blank query args.
    Set auth=False for public routes (no API key required).
    """
    clean = {k: v for k, v in params.items() if v not in (None, "")}
    url = f"{BASE_URL}{path}"
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(url, params=clean, headers=_headers(require_key=auth))
    except httpx.TimeoutException as exc:
        raise GreeksAPIError(
            f"Request to {path} timed out after {TIMEOUT}s. For heavy symbols try "
            f"a specific expiration instead of 'all'."
        ) from exc
    except httpx.HTTPError as exc:
        raise GreeksAPIError(f"Network error calling {path}: {exc}") from exc

    if resp.status_code // 100 != 2:
        raise GreeksAPIError(_explain_status(resp.status_code, resp.text))

    try:
        return resp.json()
    except ValueError as exc:
        raise GreeksAPIError(
            f"API returned non-JSON body from {path}: {resp.text[:200]}"
        ) from exc


def _analytics(path: str, symbol: str, expiration: Optional[str] = None,
               **extra: Any) -> Any:
    sym = (symbol or "").strip().upper()
    if not sym:
        raise GreeksAPIError("A non-empty 'symbol' is required (e.g. AAPL, SPY).")
    params: dict[str, Any] = {"symbol": sym, "expiration": expiration}
    params.update(extra)
    return _get(path, params)


# ─────────────────────────────────────────────────────────────────────────────
# Tools — commercial analytics (derived data only)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_max_pain(symbol: str, expiration: Optional[str] = None) -> Any:
    """Max Pain per expiration — the strike that minimizes total option value
    (where most options expire worthless), a magnet the price tends to converge
    toward at expiration.

    Plan: Free (1 symbol, 15-min delay) and up.

    Args:
        symbol: Underlying ticker, e.g. "AAPL", "SPY", "NDAQ".
        expiration: Unix expiration timestamp for a single expiry, or "all" for
            every expiration (slower, complete). Omit for the nearest expiry.

    Returns the raw MaxPainResponse JSON: symbol, spotPrice, timestamp, and
    results[] with maxPainStrike, totalPainAtMax, spotDistance, spotDistancePct.
    """
    return _analytics("/api/analytics/maxpain", symbol, expiration)


@mcp.tool()
def get_greeks(
    symbol: str,
    expiration: Optional[str] = None,
    range: Optional[str] = None,
    moneyness: Optional[str] = None,
    limit: Optional[int] = None,
) -> Any:
    """Black-Scholes Greeks (Delta, Gamma, Theta, Vega, Rho) plus theoretical
    price and mispricing for every contract in the chain.

    Plan: Trader and up.

    Args:
        symbol: Underlying ticker.
        expiration: Unix timestamp of a specific expiry, or "all". Omit for the
            nearest expiry.
        range: Pass "atm" to restrict the chain to at-the-money contracts.
        moneyness: A "low,high" pair (e.g. "0.9,1.1") to filter contracts by
            strike/spot ratio.
        limit: Cap the number of contracts returned (per side).

    Returns GreeksResponse JSON: symbol, spotPrice, timestamp, and contracts[]
    each with delta/gamma/theta/vega/rho, iv, theoreticalPrice, mispricing,
    inTheMoney.
    """
    return _analytics(
        "/api/analytics/greeks", symbol, expiration,
        range=range, moneyness=moneyness, limit=limit,
    )


@mcp.tool()
def get_gex(symbol: str, expiration: Optional[str] = None,
            symbols: Optional[str] = None) -> Any:
    """Gamma & Delta Exposure (GEX/DEX) per strike, plus total Net GEX and the
    Gamma Flip level (strike where Net GEX crosses zero — a regime transition).
    Positive Net GEX = dealers long gamma (price pins); negative = moves amplified.

    Plan: Trader and up.

    Args:
        symbol: Underlying ticker.
        expiration: Unix timestamp of a specific expiry, or "all". Omit for the
            nearest expiry.
        symbols: Optional comma-separated list for a multi-symbol GEX request
            (e.g. "SPY,QQQ,IWM"); when set it takes precedence over `symbol`.

    Returns GEXResponse JSON: symbol, spotPrice, timestamp, totalNetGEX,
    gammaFlip, and strikes[] with callGEX/putGEX/netGEX and callDEX/putDEX/netDEX.
    """
    extra = {"symbols": symbols} if symbols else {}
    return _analytics("/api/analytics/gex", symbol, expiration, **extra)


@mcp.tool()
def get_flow(symbol: str, expiration: Optional[str] = None) -> Any:
    """Unusual options activity detection — contracts with abnormally high
    volume relative to open interest, typically signalling institutional/"smart
    money" positioning.

    Signals: unusual_volume (high: Vol/OI ≥ 3.0, medium: ≥ 1.5) and
    opening_position (Vol ≥ 50 with OI = 0). Contracts with volume < 10 are noise.

    Plan: Trader and up.

    Args:
        symbol: Underlying ticker.
        expiration: Unix timestamp of a specific expiry, or "all". Omit for the
            nearest expiry.

    Returns FlowResponse JSON: symbol, spotPrice, timestamp, and signals[] each
    with contractSymbol, type, strike, expiration, dte, volumeOIRatio, iv,
    signal, severity.
    """
    return _analytics("/api/analytics/flow", symbol, expiration)


@mcp.tool()
def get_overview(symbol: str, expiration: Optional[str] = None) -> Any:
    """Full analytics dashboard for a symbol in one call: sentiment, GEX summary,
    max pain, expected moves, IV surface, term structure and top unusual flow.
    The cheapest way to get everything for a symbol at once.

    Plan: Pro and up.

    Args:
        symbol: Underlying ticker.
        expiration: Unix timestamp of a specific expiry, or "all" (recommended
            for the full dashboard). Omit for the nearest expiry.

    Returns OverviewResponse JSON: symbol, spotPrice, timestamp, riskFreeRate,
    dividendYield, sentiment, gexSummary, maxPain[], expectedMoves[],
    termStructure[], ivSurface[], topFlow[].
    """
    return _analytics("/api/analytics/overview", symbol, expiration)


@mcp.tool()
def get_snapshot(symbol: str, expiration: Optional[str] = None) -> Any:
    """Compact analytics snapshot for a symbol — a lighter-weight summary than
    the full overview, suitable for quick checks and cards.

    Args:
        symbol: Underlying ticker.
        expiration: Unix timestamp of a specific expiry, or "all". Omit for the
            nearest expiry.

    Returns the SnapshotResponse JSON as computed by the analytics engine.
    """
    return _analytics("/api/analytics/snapshot", symbol, expiration)


@mcp.tool()
def get_levels(symbol: str, expiration: Optional[str] = None) -> Any:
    """Key options-derived price levels for a symbol (support/resistance style
    levels from gamma and open-interest structure).

    Args:
        symbol: Underlying ticker.
        expiration: Unix timestamp of a specific expiry, or "all". Omit for the
            nearest expiry.

    Returns the LevelsResponse JSON as computed by the analytics engine.
    """
    return _analytics("/api/analytics/levels", symbol, expiration)


@mcp.tool()
def get_vex(symbol: str, expiration: Optional[str] = None) -> Any:
    """Vanna & Charm Exposure (VEX) — the second-order dealer Greeks. Vanna is
    how dealer delta shifts as implied volatility moves (∂Delta/∂IV); Charm is
    how it shifts as time passes (∂Delta/∂Time, i.e. delta decay). These are the
    flows behind OPEX drift and end-of-day drift, sitting one layer beneath GEX.

    Plan: Pro and up.

    Args:
        symbol: Underlying ticker.
        expiration: Unix timestamp of a specific expiry, or "all". Omit for the
            nearest expiry.

    Returns VEXResponse JSON: symbol, spotPrice, timestamp, totalNetVEX ($ delta
    shift per +1% IV move), totalNetCharm ($ delta shift per day), and strikes[]
    with callVEX/putVEX/netVEX and callCharm/putCharm/netCharm.
    """
    return _analytics("/api/analytics/vex", symbol, expiration)


@mcp.tool()
def get_vol_structure(symbol: str, expiration: Optional[str] = None) -> Any:
    """Volatility structure — the skew across strikes and the term structure
    across expirations, with plain-English reads. Skew (25-delta put IV minus
    call IV) shows where demand/fear sits; term slope (back ATM IV minus front)
    shows contango (calm) vs backwardation (near-term event stress).

    Plan: Trader and up.

    Args:
        symbol: Underlying ticker.
        expiration: Unix timestamp of a specific expiry, or "all". Omit for the
            nearest expiry.

    Returns VolStructureResponse JSON: symbol, spotPrice, timestamp, skew[] (per
    expiration: atmIV, skew25Delta, read), termStructure[] (ATM IV vs DTE),
    skewRead, termRead, and termSlope (back − front ATM IV; <0 = backwardation).
    """
    return _analytics("/api/analytics/vol-structure", symbol, expiration)


@mcp.tool()
def get_zero_dte(symbol: str) -> Any:
    """0DTE focus panel — isolates only today's expiring contracts and computes
    their GEX, gamma flip, max pain, expected move and a pin-risk read. On an
    expiration day, that day's dealer gamma dominates the intraday tape: positive
    gamma pins price toward max pain, negative gamma amplifies moves.

    Plan: Pro and up.

    Args:
        symbol: Underlying ticker (index/ETF names like SPY/QQQ have daily
            expiries; most single names do not).

    Returns ZeroDTEResponse JSON: symbol, spotPrice, timestamp, expiration, dte,
    totalNetGEX, gammaFlip, maxPainStrike, maxPainDistPct, expectedMovePct,
    upperBound, lowerBound, pinRisk, read, and isTrue0DTE. When isTrue0DTE is
    false nothing expires today (weekend / no daily expiry) and the panel falls
    back to the nearest expiration with pinRisk "n/a" — it never fakes a pin.
    """
    return _analytics("/api/analytics/zero-dte", symbol, None)


@mcp.tool()
def get_gex_intraday(symbol: str, date: Optional[str] = None) -> Any:
    """Intraday gamma-regime tracker — a time-series of Net GEX, spot, the gamma
    flip and the regime label ("positive"/"negative") through the session, plus
    the timestamp of the last regime flip. Positive gamma = dealers dampen moves
    (range-bound); negative = dealers amplify (trending/volatile).

    Plan: Pro and up.

    Args:
        symbol: Underlying ticker.
        date: Optional session date as "YYYY-MM-DD" (US/Eastern). Omit for today.

    Returns the intraday GEX JSON: symbol, date, regime (current), flippedAt
    (unix ts of the last regime change today, 0 = none), flippedFrom (prior
    regime), points[] (each with ts, spot, netGEX, gammaFlip, regime) and
    updatedAt. Note: this endpoint takes `date`, not `expiration`.
    """
    sym = (symbol or "").strip().upper()
    if not sym:
        raise GreeksAPIError("A non-empty 'symbol' is required (e.g. SPY, QQQ).")
    return _get("/api/analytics/gex-intraday", {"symbol": sym, "date": date})


@mcp.tool()
def get_track_record_detail(symbol: Optional[str] = None) -> Any:
    """Authenticated track-record detail — the day-by-day report card behind the
    public accuracy headline. For each scored day it lists the level published
    that morning (call_wall / put_wall / max_pain / expected_move) and whether
    the session respected it: the receipts behind the percentage.

    Plan: Pro and up. (The public, aggregate version is the keyless
    `track_record` tool.)

    Args:
        symbol: Optional ticker to filter the report to one name; omit for all
            scored symbols.

    Returns the detail JSON: days, outcomes[] (newest first — each with date,
    symbol, spotOpen, dayHigh, dayLow, dayClose, level, value, held, detail) and
    updatedAt.
    """
    sym = (symbol or "").strip().upper()
    return _get("/api/analytics/track-record", {"symbol": sym or None})


# ─────────────────────────────────────────────────────────────────────────────
# Tools — account / metadata (help the model use the API correctly)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_plans() -> Any:
    """List the available commercial plans with prices, limits and included
    routes (Free / Trader / Pro / Institutional). Public — no key needed.

    Use this to explain to the user which analytics their plan unlocks, or why a
    call returned 402/403.
    """
    return _get("/api/billing/plans", {}, auth=False)


@mcp.tool()
def health() -> Any:
    """Service health check: returns {status, supabase, stripe}. Public — no key
    needed. Use to verify GREEKS_BASE_URL is reachable before other calls.
    """
    return _get("/health", {}, auth=False)


def main() -> None:
    """Entry point for the `greeks-mcp` console script and `python -m greeks_mcp`."""
    transport = os.environ.get("MCP_TRANSPORT", "stdio").strip().lower()
    if transport in ("http", "streamable-http"):
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


@mcp.tool()
def screener() -> Any:
    """Public options screener across the curated watchlist (~26 liquid names:
    SPY, QQQ, AAPL, NVDA, TSLA, …). Returns a per-symbol row with spot price,
    sentiment and headline analytics — the fastest way to DISCOVER which symbols
    are interesting before drilling in with the authenticated analytics tools.

    Public — no key needed (IP rate-limited). Takes no arguments; the watchlist
    is fixed server-side.

    Returns the screener JSON (rows[] of symbol/spotPrice/sentiment/…).
    """
    return _get("/api/public/screener", {}, auth=False)


@mcp.tool()
def gex_heatmap(symbol: str = "SPY", expiry: Optional[str] = None) -> Any:
    """Public GEX-by-strike heatmap for a watchlist symbol (no key needed,
    IP rate-limited, cached ~5 min). A lightweight, unauthenticated way to see
    gamma exposure per strike without a plan.

    Args:
        symbol: A watchlist ticker (SPY, QQQ, AAPL, NVDA, TSLA, …). Defaults to
            SPY. Symbols outside the public watchlist return an error — use the
            authenticated `get_gex` for arbitrary symbols.
        expiry: Optional Unix expiration timestamp; omit for the nearest expiry.

    Returns the heatmap JSON: symbol plus GEX by strike.
    """
    sym = (symbol or "SPY").strip().upper()
    return _get("/api/public/gex-heatmap", {"symbol": sym, "expiry": expiry}, auth=False)


@mcp.tool()
def track_record() -> Any:
    """Public track record — aggregated accuracy of the published analytics over
    roughly the last 35 days (per-symbol daily snapshots vs realized high/low/
    close). Use it to gauge how the signals have performed historically.

    Public — no key needed. Takes no arguments.

    Returns the track-record JSON as computed server-side (updatedAt + records).
    """
    return _get("/api/public/track-record", {}, auth=False)


if __name__ == "__main__":
    main()
