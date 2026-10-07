import re


RECENT_EVENT_PATTERNS = (
    "recent earthquakes",
    "recent earthquake",
    "recent storms",
    "recent storm",
    "recent tropical cyclones",
    "recent wildfire",
    "recent wildfires",
    "recent floods",
    "recent tornadoes",
    "recent volcanoes",
    "recent tsunamis",
    "latest earthquakes",
    "latest storms",
    "latest wildfire",
    "latest wildfires",
)

EVENT_DISPLAY_PATTERNS = (
    "show me",
    "display",
    "map",
    "list",
    "find",
    "events",
    "event",
    "tracks",
    "track",
    "points",
    "recent",
    "latest",
    "strongest",
    "largest",
    "major",
    "significant",
    "severe",
    "deadliest",
    "struck",
    "hit",
    "occurred",
    "happened",
)

AGGREGATE_PATTERNS = (
    "how many",
    "count",
    "counts",
    "number of",
    "total",
    "average",
    "avg",
    "mean",
    "sum",
    "frequency",
    "trend",
    "compare",
    "ranking",
    "rank",
    "highest",
    "lowest",
    "per year",
    "rolling",
    "share",
    "rate",
    "exposure",
)

AGGREGATE_ONLY_PATTERNS = (
    "how many",
    "count",
    "counts",
    "number of",
    "frequency",
    "per year",
    "rolling",
    "exposure",
    "share",
    "rate",
)

EXPLICIT_EVENT_VIEW_PATTERNS = (
    "individual",
    "individual events",
    "events",
    "event",
    "tracks",
    "track",
    "points",
    "recent",
    "latest",
    "show me",
    "display",
    "map",
    "list",
)

EXPLICIT_AGGREGATE_VIEW_PATTERNS = (
    "aggregate",
    "aggregated",
    "annual",
    "annually",
    "yearly",
    "per year",
    "rolling",
    "count",
    "counts",
    "frequency",
    "exposure",
    "share",
    "rate",
    "ranking",
    "rank",
)

EVENT_STYLE_ADJECTIVES = (
    "strongest",
    "largest",
    "major",
    "significant",
    "severe",
    "deadliest",
    "most recent",
    "latest",
    "newest",
)

HISTORICAL_EVENT_IMPACT_TERMS = (
    "impact",
    "impacts",
    "damage",
    "damages",
    "deaths",
    "fatalities",
    "struck",
    "hit",
    "happened",
    "occurred",
    "caused",
    "deadliest",
    "destructive",
    "most affected",
)

SHORT_CURRENT_WINDOW_REGEX = re.compile(
    r"\b(?:today|current|currently|right now|last\s+\d+\s+(?:hour|hours|day|days|week|weeks|month|months)|"
    r"past\s+\d+\s+(?:hour|hours|day|days|week|weeks|month|months)|"
    r"last\s+(?:week|month)|past\s+(?:week|month))\b"
)

TIME_WINDOW_TERMS = (
    "today",
    "current",
    "currently",
    "right now",
    "last 24 hours",
    "past 24 hours",
    "last 7 days",
    "past 7 days",
    "last 30 days",
    "past 30 days",
    "last 60 days",
    "past 60 days",
    "last 90 days",
    "past 90 days",
    "last week",
    "past week",
    "last month",
    "past month",
    "last 10 years",
    "last 20 years",
    "last 30 years",
    "past 10 years",
    "past 20 years",
    "past 30 years",
    "this year",
    "last year",
)


def semantic_query_text(query: str) -> str:
    text = str(query or "").strip()
    if not text:
        return ""
    marker = " qa mode:"
    lower = text.lower()
    idx = lower.find(marker)
    if idx >= 0:
        text = text[:idx]
    return text.strip().lower()


def query_requests_recent_events(query: str) -> bool:
    query_lower = semantic_query_text(query)
    if not query_lower:
        return False
    return any(pattern in query_lower for pattern in RECENT_EVENT_PATTERNS)


def query_requests_single_latest_event(query: str) -> bool:
    query_lower = semantic_query_text(query)
    if not query_lower:
        return False
    if not any(pattern in query_lower for pattern in ("most recent", "latest", "newest")):
        return False
    return not any(pattern in query_lower for pattern in ("top ", "show me 10", "show 10", "ten most recent"))


def query_has_time_window(query: str) -> bool:
    query_lower = semantic_query_text(query)
    if not query_lower:
        return False
    if re.search(r"\b(?:since|from|between|during|in)\s+\d{4}\b", query_lower):
        return True
    if re.search(r"\b(?:last|past)\s+\d+\s+(?:day|days|week|weeks|month|months|year|years|hour|hours)\b", query_lower):
        return True
    return any(token in query_lower for token in TIME_WINDOW_TERMS)


def query_requests_event_window(query: str) -> bool:
    query_lower = semantic_query_text(query)
    if not query_lower:
        return False
    has_event_subject = any(pattern in query_lower for pattern in EVENT_DISPLAY_PATTERNS)
    has_time_window = query_has_time_window(query_lower)
    has_aggregate_only = any(pattern in query_lower for pattern in AGGREGATE_ONLY_PATTERNS)
    if not (has_event_subject and has_time_window):
        return False
    if SHORT_CURRENT_WINDOW_REGEX.search(query_lower):
        return True
    return not has_aggregate_only


def query_requests_short_current_window(query: str) -> bool:
    query_lower = semantic_query_text(query)
    if not query_lower:
        return False
    if not SHORT_CURRENT_WINDOW_REGEX.search(query_lower):
        return False
    return query_has_time_window(query_lower)


def query_explicit_view_mode(query: str) -> tuple[bool, bool]:
    query_lower = semantic_query_text(query)
    if not query_lower:
        return False, False
    explicit_events = any(pattern in query_lower for pattern in EXPLICIT_EVENT_VIEW_PATTERNS)
    explicit_aggregate = any(pattern in query_lower for pattern in EXPLICIT_AGGREGATE_VIEW_PATTERNS)
    return explicit_events, explicit_aggregate


def query_prefers_event_source(query: str) -> bool:
    query_lower = semantic_query_text(query)
    if not query_lower:
        return False
    explicit_events, explicit_aggregate = query_explicit_view_mode(query_lower)
    if explicit_events and not explicit_aggregate:
        return True
    if query_requests_event_window(query_lower):
        return True
    has_event_adjective = any(re.search(rf"\b{re.escape(token)}\b", query_lower) for token in EVENT_STYLE_ADJECTIVES)
    has_aggregate_only = any(pattern in query_lower for pattern in AGGREGATE_ONLY_PATTERNS)
    has_historical_year = bool(re.search(r"\b(?:19|20)\d{2}\b", query_lower))
    has_historical_impact = any(term in query_lower for term in HISTORICAL_EVENT_IMPACT_TERMS)
    if has_historical_year and has_historical_impact and not has_aggregate_only:
        return True
    return has_event_adjective and not has_aggregate_only


def query_signals_event_vs_aggregate(query: str) -> tuple[bool, bool]:
    query_lower = semantic_query_text(query)
    if not query_lower:
        return False, False
    wants_events = any(pattern in query_lower for pattern in EVENT_DISPLAY_PATTERNS)
    wants_aggregate = any(pattern in query_lower for pattern in AGGREGATE_PATTERNS)
    if query_requests_event_window(query_lower):
        wants_events = True
        wants_aggregate = False
    return wants_events, wants_aggregate


def query_prefers_event_retry(query: str) -> bool:
    text = semantic_query_text(query)
    if not text:
        return False
    has_event_terms = any(term in text for term in EVENT_DISPLAY_PATTERNS)
    has_aggregate_terms = any(term in text for term in AGGREGATE_PATTERNS)
    has_time_window = bool(re.search(r"\b(?:since|from|between|during|in)\s+\d{4}\b", text)) or any(
        term in text for term in (
            "last 10 years",
            "last 20 years",
            "last 30 years",
            "past 10 years",
            "past 20 years",
            "past 30 years",
        )
    )
    return has_event_terms and (not has_aggregate_terms or has_time_window)
