"""
Constants and static data used across the mapmover application.

NOTE: Many constants have been moved to reference files for maintainability:
- state_abbreviations -> reference/usa/usa_admin.json
- TOPIC_KEYWORDS -> derived from catalog.json (preprocessor aggregates category/topic_tags/keywords)
- DISASTER_OVERLAYS -> reference/disasters.json (loaded by preprocessor)
- LOCATION_STOP_WORDS -> reference/stopwords.json (loaded by preprocessor, currently disabled)
- unit conversions -> reference/unit_conversions.json (loaded by utils.py)
"""

# =============================================================================
# CHAT HISTORY CONFIGURATION
# =============================================================================
# How many messages the LLM sees for context continuity.
# Frontend sends this many, backend uses this many.
# Higher = better context but more tokens. 8 = 4 user/assistant exchanges.
CHAT_HISTORY_LLM_LIMIT = 8

# Unit multiplier mappings for filter value conversion
# Kept here as these are mathematical constants that won't change
UNIT_MULTIPLIERS = {
    "trillion": 1_000_000_000_000,
    "billion": 1_000_000_000,
    "million": 1_000_000,
    "thousand": 1_000,
    "k": 1_000,
    "m": 1_000_000,
    "b": 1_000_000_000,
    "t": 1_000_000_000_000
}
