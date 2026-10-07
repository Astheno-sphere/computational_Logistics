/**
 * Static introspection catalog for the Off-Nadir Delta stdio MCP proxy.
 *
 * AUTO-GENERATED from the Off-Nadir Delta contract registry
 * (src/lib/api/toolRegistry.ts + src/lib/api/mcpResources.ts) by
 * scripts/gen-contract-artifacts.mjs — DO NOT EDIT BY HAND.
 *
 * These tool / resource / prompt definitions mirror the live remote MCP server
 * (https://offnadir-delta.com/api/v1/mcp) so that `tools/list`, `resources/list`,
 * and `prompts/list` answer instantly and WITHOUT credentials — this is what
 * lets registries (e.g. Glama) introspect the server in a bare container.
 *
 * Actual `tools/call` / `resources/read` / `prompts/get` requests are forwarded
 * to the remote server with the caller's OFFNADIR_DELTA_API_KEY (see index.ts).
 */

// Generated for Off-Nadir Delta MCP 3.3.0.

export const TOOLS = [
  {
    "name": "query_signals",
    "description": "Geolocated world events from global news media, AI-enriched with severity/GEOINT scores and collection recommendations.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "bbox": {
          "type": "array",
          "items": {
            "type": "number"
          },
          "minItems": 4,
          "maxItems": 4,
          "description": "[minLon, minLat, maxLon, maxLat] WGS84. Omit for worldwide."
        },
        "startDate": {
          "type": "string",
          "description": "Date range start, YYYY-MM-DD (UTC). With endDate. Records start 2026-09-23 (earlier: unrecorded, not quiet). Plan-bounded: meta.window_clamp."
        },
        "endDate": {
          "type": "string",
          "description": "Date range end, YYYY-MM-DD (UTC), inclusive."
        },
        "recency": {
          "type": "string",
          "enum": [
            "15m",
            "1h",
            "24h"
          ],
          "description": "Last reported within. Default 24h when no date range."
        },
        "categories": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": [
              "kinetic",
              "armed_conflict",
              "maritime",
              "natural_disaster",
              "infrastructure",
              "aviation",
              "humanitarian",
              "protest",
              "diplomacy",
              "other"
            ]
          },
          "description": "Restrict to these categories."
        },
        "q": {
          "type": "string",
          "description": "Text search: all words; \"phrase\"; -exclude."
        },
        "stages": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": [
              "reported",
              "localized",
              "pinpointed"
            ]
          },
          "description": "reported=country/province, localized=town, pinpointed=block/facility."
        },
        "minSeverityBand": {
          "type": "integer",
          "enum": [
            4,
            6,
            9
          ],
          "description": "severity_band >= this."
        },
        "minPublishers": {
          "type": "integer",
          "enum": [
            2,
            3,
            5
          ],
          "description": "At least this many publishers."
        },
        "markets": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": [
              "oil",
              "natural_gas",
              "grain",
              "shipping",
              "defense",
              "metals",
              "semiconductors",
              "fx",
              "equities"
            ]
          },
          "description": "Exposed markets (physical/supply channel)."
        },
        "placement": {
          "type": "string",
          "enum": [
            "all",
            "map",
            "list"
          ],
          "description": "map=a point; list=country/province only."
        },
        "origin": {
          "type": "string",
          "enum": [
            "all",
            "reported",
            "measured",
            "thermal",
            "transit"
          ],
          "description": "thermal=heat sources measured by satellite; transit=ship transits at a strait far from their recent level; measured=both; reported=reporting only."
        },
        "linkedTo": {
          "type": "string",
          "description": "Shares a connector: facility:<entity_id>, place:<place_key>, actor:<name>. Plan-gated."
        },
        "watchId": {
          "type": "string",
          "description": "Events linked to this watch (list_watches id)."
        },
        "sort": {
          "type": "string",
          "enum": [
            "latest",
            "oldest",
            "geoint"
          ],
          "description": "Default latest. geoint (plan-gated): observable, then geoint_score."
        },
        "updatedSince": {
          "type": "string",
          "description": "Refolded at/after (ISO)."
        },
        "limit": {
          "type": "integer",
          "minimum": 1,
          "maximum": 50,
          "description": "Page size (default 20). Rows are digests; full rows: full_records."
        },
        "cursor": {
          "type": "string",
          "description": "From meta.next_cursor."
        }
      }
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "meta": {
          "type": "object",
          "description": "Query echo, token charge/balance (meta.tokens), and pagination where applicable."
        },
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "signals": {
          "type": "array",
          "items": {
            "type": "object"
          }
        },
        "full_records": {
          "type": "object",
          "description": "The same query on the REST API and the Python SDK, which return every field and larger pages.",
          "properties": {
            "note": {
              "type": "string"
            },
            "rest": {
              "type": "string"
            },
            "sdk": {
              "type": "string"
            },
            "docs": {
              "type": "string"
            }
          }
        }
      },
      "required": [
        "meta",
        "signals"
      ]
    },
    "annotations": {
      "readOnlyHint": false,
      "openWorldHint": false,
      "destructiveHint": true
    }
  },
  {
    "name": "get_world_brief",
    "description": "AI world brief: daily (prior UTC day, all plans) or weekly/monthly by plan. freshness.is_stale: no newer day, so relay as stale.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "period": {
          "type": "string",
          "enum": [
            "daily",
            "weekly",
            "monthly"
          ]
        },
        "date": {
          "type": "string",
          "description": "YYYY-MM-DD UTC (daily: within the plan window); weekly/monthly: last day. Default latest"
        }
      }
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "brief": {
          "type": "object"
        },
        "freshness": {
          "type": "object",
          "description": "Freshness of the returned brief: brief_date, generated_at, age_hours, freshness (operational|delayed|degraded), is_stale, note."
        }
      },
      "required": [
        "brief"
      ]
    },
    "annotations": {
      "readOnlyHint": true,
      "openWorldHint": false,
      "destructiveHint": false
    }
  },
  {
    "name": "get_usage",
    "description": "The calling key's remaining token balance and plan capabilities. Pre-flight a metered call with it.",
    "inputSchema": {
      "type": "object",
      "properties": {}
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "tokens": {
          "type": "object",
          "properties": {
            "allocation": {
              "type": "number",
              "description": "Monthly token allocation for the plan."
            },
            "used": {
              "type": "number",
              "description": "Tokens used in the current period."
            },
            "remaining": {
              "type": "number",
              "description": "Tokens remaining this period."
            }
          },
          "required": [
            "allocation",
            "used",
            "remaining"
          ]
        },
        "plan": {
          "type": "object",
          "properties": {
            "api_llm_access": {
              "type": "boolean",
              "description": "Whether AI tools over the API are enabled."
            }
          },
          "required": [
            "api_llm_access"
          ]
        }
      },
      "required": [
        "tokens",
        "plan"
      ]
    },
    "annotations": {
      "readOnlyHint": true,
      "openWorldHint": false,
      "destructiveHint": false
    }
  },
  {
    "name": "search_imagery",
    "description": "Search the imagery catalog over an area and window. Metadata only, no pixels. eventDate tags each scene pre/post — **a same-day scene is same_day_unknown, never post** — and eventPoint/eventAoi add target_relation, so a scene that only clips the bbox is not read as covering the event.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "bbox": {
          "type": "array",
          "items": {
            "type": "number"
          },
          "minItems": 4,
          "maxItems": 4,
          "description": "[minLon, minLat, maxLon, maxLat] WGS84. Required."
        },
        "collection": {
          "type": "string",
          "enum": [
            "sentinel-1-grd",
            "sentinel-1-rtc",
            "sentinel-2-l2a",
            "NISAR_L2_GCOV_PROVISIONAL_V1"
          ],
          "description": "Catalog collection. Default sentinel-2-l2a."
        },
        "startDate": {
          "type": "string",
          "description": "Date range start, YYYY-MM-DD (UTC). With endDate; omit both for the last 7 days (max 30)."
        },
        "endDate": {
          "type": "string",
          "description": "Date range end, YYYY-MM-DD (UTC), inclusive."
        },
        "eventDate": {
          "type": "string",
          "description": "Widens to the canonical pre/post span with bracketing; sentinel-1-grd adds sar_pair_status."
        },
        "eventPoint": {
          "type": "array",
          "items": {
            "type": "number"
          },
          "minItems": 2,
          "maxItems": 2,
          "description": "[lon, lat] WGS84. Drives covers_event_point / usable_for_event."
        },
        "eventAoi": {
          "type": "array",
          "items": {
            "type": "number"
          },
          "minItems": 4,
          "maxItems": 4,
          "description": "[minLon,minLat,maxLon,maxLat]. Drives intersects_event_aoi / coverage_ratio."
        },
        "eventTimestamp": {
          "type": "string",
          "description": "ISO 8601 event time — promotes same-day scenes to pre/post."
        },
        "cloudCoverMax": {
          "type": "number",
          "minimum": 0,
          "maximum": 100,
          "description": "Sentinel-2 only: max cloud cover %."
        },
        "limit": {
          "type": "integer",
          "minimum": 1,
          "maximum": 25,
          "description": "Max scenes. Default 10."
        }
      },
      "required": [
        "bbox"
      ]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "meta": {
          "type": "object",
          "description": "Query echo, token charge/balance (meta.tokens), and pagination where applicable."
        },
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "scenes": {
          "type": "array",
          "items": {
            "type": "object"
          }
        },
        "full_records": {
          "type": "object",
          "description": "The same query on the REST API and the Python SDK, which return every field and larger pages.",
          "properties": {
            "note": {
              "type": "string"
            },
            "rest": {
              "type": "string"
            },
            "sdk": {
              "type": "string"
            },
            "docs": {
              "type": "string"
            }
          }
        }
      },
      "required": [
        "meta",
        "scenes"
      ]
    },
    "annotations": {
      "readOnlyHint": false,
      "openWorldHint": false,
      "destructiveHint": true
    }
  },
  {
    "name": "plan_event_imagery",
    "description": "The deterministic imagery plan for ONE event: checks BOTH sensors exactly once — sentinel-1-grd (SAR, the only look that survives cloud and night) and sentinel-2-l2a — against the event footprint and a pre/post window. **A VHR recommendation never invalidates what the free catalog showed.**",
    "inputSchema": {
      "type": "object",
      "properties": {
        "event_id": {
          "type": "string",
          "description": "The `id` (UUID) from query_signals; the server resolves its point and AOI."
        },
        "analysis_goal": {
          "type": "string",
          "enum": [
            "damage_assessment",
            "flood_mapping",
            "wildfire_assessment"
          ],
          "description": "What the imagery must establish — decides the lead collection and cloud gating."
        },
        "event_date": {
          "type": "string",
          "description": "YYYY-MM-DD. The event row supplies it when known."
        }
      },
      "required": [
        "event_id",
        "analysis_goal"
      ]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "meta": {
          "type": "object",
          "description": "Query echo, token charge/balance (meta.tokens), and pagination where applicable."
        },
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "plan": {
          "type": "object"
        }
      },
      "required": [
        "meta",
        "plan"
      ]
    },
    "annotations": {
      "readOnlyHint": false,
      "openWorldHint": false,
      "destructiveHint": true
    }
  },
  {
    "name": "rank_imaging_priority",
    "description": "WHERE, and with what class of satellite, observation is most worthwhile now: composite IMPORTANCE crossed with the SPEC CLASS the required resolution demands — coarse, hr (free Sentinel-class) or vhr. Deterministic.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "bbox": {
          "type": "array",
          "items": {
            "type": "number"
          },
          "minItems": 4,
          "maxItems": 4,
          "description": "[west, south, east, north] WGS84. Omit for global."
        },
        "start_date": {
          "type": "string",
          "description": "YYYY-MM-DD, inclusive. Default today. Records start 2026-09-23 (earlier: unrecorded, not quiet). Plan-bounded: meta.window_clamp."
        },
        "end_date": {
          "type": "string",
          "description": "YYYY-MM-DD, inclusive. Default today; capped at 30 days."
        },
        "categories": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "description": "Restrict to these Delta categories."
        },
        "min_geoint_score": {
          "type": "number",
          "description": "Drop events below this GEOINT score before ranking."
        },
        "top_n": {
          "type": "number",
          "minimum": 1,
          "maximum": 50,
          "description": "How many top targets to return (default 12)."
        }
      },
      "required": []
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "meta": {
          "type": "object",
          "description": "Query echo, token charge/balance (meta.tokens), and pagination where applicable."
        },
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "priority": {
          "type": "object"
        }
      },
      "required": [
        "meta",
        "priority"
      ]
    },
    "annotations": {
      "readOnlyHint": false,
      "openWorldHint": false,
      "destructiveHint": true
    }
  },
  {
    "name": "predict_satellite_passes",
    "description": "WHEN a place can next be imaged and by WHAT: 13 free-systematic and commercial-taskable families. **Every pass is a GEOMETRIC access opportunity** — no operator plan is consulted. retrieval_ok:false means timing is UNAVAILABLE, never \"no passes\".",
    "inputSchema": {
      "type": "object",
      "properties": {
        "lat": {
          "type": "number",
          "minimum": -90,
          "maximum": 90,
          "description": "Target latitude. Required unless bbox is given."
        },
        "lon": {
          "type": "number",
          "minimum": -180,
          "maximum": 180,
          "description": "Target longitude. Required unless bbox is given."
        },
        "bbox": {
          "type": "array",
          "items": {
            "type": "number"
          },
          "minItems": 4,
          "maxItems": 4,
          "description": "[west, south, east, north] WGS84. Its CENTRE is the target if lat/lon are omitted."
        },
        "start_date": {
          "type": "string",
          "description": "YYYY-MM-DD (UTC), inclusive. Default today."
        },
        "end_date": {
          "type": "string",
          "description": "YYYY-MM-DD (UTC), inclusive. Default start+2 days; 7-day horizon."
        },
        "satellites": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": [
              "sentinel-1",
              "sentinel-2",
              "landsat",
              "worldview",
              "iceye",
              "capella",
              "skysat",
              "umbra",
              "synspective",
              "iqps",
              "radarsat-2",
              "cosmo-skymed",
              "nisar"
            ]
          },
          "description": "Families to consider. Omit for all thirteen."
        },
        "max_passes": {
          "type": "number",
          "minimum": 1,
          "maximum": 100,
          "description": "Maximum passes to return, soonest first (default 40)."
        }
      },
      "required": []
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "meta": {
          "type": "object",
          "description": "Query echo, token charge/balance (meta.tokens), and pagination where applicable."
        },
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "passes": {
          "type": "array",
          "items": {
            "type": "object"
          }
        },
        "freshness": {
          "type": "object"
        }
      },
      "required": [
        "meta",
        "passes"
      ]
    },
    "annotations": {
      "readOnlyHint": false,
      "openWorldHint": false,
      "destructiveHint": true
    }
  },
  {
    "name": "assess_signal",
    "description": "AI remote-sensing deep-dive for one signal: what to observe, sensors, a collection window. Also returns a deterministic `context` whose `imagery_handoff.parameters` are the exact search_imagery inputs. Cached per signal; not-observable signals are rejected before any charge.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "eventId": {
          "type": "string",
          "description": "Signal id (UUID) from query_signals."
        },
        "kind": {
          "type": "string",
          "enum": [
            "quick",
            "deep"
          ],
          "description": "Assessment depth. Defaults to quick."
        }
      },
      "required": [
        "eventId"
      ]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "kind": {
          "type": "string",
          "description": "Assessment depth actually run (\"quick\" | \"deep\")."
        },
        "cached": {
          "type": "boolean",
          "description": "True when a prior assessment for this signal was reused (no re-charge)."
        },
        "model": {
          "type": "string"
        },
        "content": {
          "type": "object"
        },
        "meta": {
          "type": "object",
          "description": "Query echo, token charge/balance (meta.tokens), and pagination where applicable."
        },
        "context": {
          "type": "object",
          "description": "Deterministic collection context for this signal — not model prose. Use `imagery_handoff` to go straight from the assessment to real scene candidates.",
          "properties": {
            "event_id": {
              "type": "string"
            },
            "event_date": {
              "type": [
                "string",
                "null"
              ]
            },
            "category": {
              "type": [
                "string",
                "null"
              ]
            },
            "target": {
              "type": [
                "string",
                "null"
              ],
              "description": "Normalized observation target."
            },
            "location": {
              "type": [
                "string",
                "null"
              ]
            },
            "aoi_bbox": {
              "type": [
                "array",
                "null"
              ],
              "items": {
                "type": "number"
              },
              "minItems": 4,
              "maxItems": 4,
              "description": "Event AOI [minLon, minLat, maxLon, maxLat] (WGS84), or null when unresolved."
            },
            "point": {
              "type": [
                "object",
                "null"
              ],
              "description": "{ lat, lng } of the event, or null."
            },
            "satellite_observability": {
              "type": "string",
              "enum": [
                "observable",
                "not-observable",
                "insufficient-detail"
              ]
            },
            "quality_status": {
              "type": "string",
              "description": "Cross-field consistency verdict for the signal row."
            },
            "rs_level": {
              "type": [
                "string",
                "null"
              ]
            },
            "rs_sensor": {
              "type": [
                "string",
                "null"
              ]
            },
            "signal_verification": {
              "type": "object"
            },
            "verification_reconciliation": {
              "type": [
                "object",
                "null"
              ]
            },
            "collection_plan": {
              "type": "object"
            },
            "claim_test": {
              "type": [
                "object",
                "null"
              ]
            },
            "imagery_handoff": {
              "type": "object",
              "description": "How to turn this assessment into a real scene search.",
              "properties": {
                "tool": {
                  "type": "string",
                  "description": "Always \"search_imagery\"."
                },
                "handoff_mode": {
                  "type": "string",
                  "enum": [
                    "targeted_collection",
                    "wide_area_screening",
                    "multi_aoi_collection",
                    "blocked"
                  ]
                },
                "target_specificity": {
                  "type": "string",
                  "enum": [
                    "point_or_aoi",
                    "multi_region",
                    "unresolved"
                  ]
                },
                "parameters": {
                  "type": "object",
                  "description": "Pass straight to search_imagery — these keys ARE its input-schema keys, no renaming.",
                  "properties": {
                    "bbox": {
                      "type": [
                        "array",
                        "null"
                      ],
                      "items": {
                        "type": "number"
                      },
                      "minItems": 4,
                      "maxItems": 4
                    },
                    "eventDate": {
                      "type": [
                        "string",
                        "null"
                      ]
                    },
                    "eventPoint": {
                      "type": [
                        "array",
                        "null"
                      ],
                      "items": {
                        "type": "number"
                      },
                      "minItems": 2,
                      "maxItems": 2,
                      "description": "[lon, lat]."
                    },
                    "eventAoi": {
                      "type": [
                        "array",
                        "null"
                      ],
                      "items": {
                        "type": "number"
                      },
                      "minItems": 4,
                      "maxItems": 4
                    },
                    "eventTimestamp": {
                      "type": [
                        "string",
                        "null"
                      ]
                    }
                  }
                },
                "missing_parameters": {
                  "type": "array",
                  "description": "Parameters that could not be filled, each with why — so the gap is legible.",
                  "items": {
                    "type": "object",
                    "properties": {
                      "field": {
                        "type": "string"
                      },
                      "reason": {
                        "type": "string"
                      }
                    }
                  }
                },
                "note": {
                  "type": "string"
                }
              },
              "required": [
                "tool",
                "handoff_mode",
                "parameters"
              ]
            }
          },
          "required": [
            "event_id",
            "satellite_observability",
            "imagery_handoff"
          ]
        },
        "status": {
          "type": "string",
          "enum": [
            "not_observable",
            "needs_repair"
          ],
          "description": "Present ONLY on a pre-charge rejection; `content` and `meta` are then absent."
        },
        "event_id": {
          "type": "string",
          "description": "Echoed on a rejection so the caller can tell which signal it was."
        },
        "charged": {
          "type": "integer",
          "description": "Tokens charged on a rejection — always 0."
        },
        "reason": {
          "type": "string",
          "description": "Why the signal was rejected before any charge."
        },
        "reason_codes": {
          "type": "array",
          "items": {
            "type": "string"
          }
        }
      },
      "required": []
    },
    "annotations": {
      "readOnlyHint": false,
      "openWorldHint": false,
      "destructiveHint": true,
      "idempotentHint": true
    }
  },
  {
    "name": "ask_analyst",
    "description": "Ask the Delta Analyst an OSINT/GEOINT question; returns a structured brief. **Durable async**: {status:\"processing\", job_id} comes back immediately and the run finishes in a background worker. Fetch with get_analyst_job, or re-send the SAME idempotencyKey (no second charge).",
    "inputSchema": {
      "type": "object",
      "properties": {
        "question": {
          "type": "string",
          "description": "The analytic question (≤ 500 chars)."
        },
        "bbox": {
          "type": "array",
          "items": {
            "type": "number"
          },
          "minItems": 4,
          "maxItems": 4,
          "description": "Focus bbox [minLon, minLat, maxLon, maxLat] WGS84."
        },
        "mode": {
          "type": "string",
          "enum": [
            "fast",
            "deep"
          ],
          "description": "fast (default) or deep. Deep widens reasoning and gathering: slower, ceiling 123→415, still charged by usage."
        },
        "idempotencyKey": {
          "type": "string",
          "description": "At-most-once key. Re-sending the SAME key returns the SAME run with no second charge, so a timeout is recoverable."
        }
      },
      "required": [
        "question"
      ]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "brief": {
          "type": "object"
        },
        "meta": {
          "type": "object",
          "description": "Query echo, token charge/balance (meta.tokens), and pagination where applicable."
        },
        "status": {
          "type": "string",
          "description": "\"processing\" when the run is still going (poll get_analyst_job or re-send the same idempotencyKey)."
        },
        "job_id": {
          "type": "string",
          "description": "Id of the analyst run — pass to get_analyst_job (also at GET /api/v1/analyst/{job_id})."
        },
        "progress": {
          "type": "object",
          "description": "Pipeline progress while the job is processing. completed_steps reaches total_steps ONLY when status is \"done\".",
          "properties": {
            "stage": {
              "type": "string",
              "enum": [
                "queued",
                "retrieval",
                "imagery_reconciliation",
                "synthesis",
                "final_validation",
                "persistence",
                "complete"
              ],
              "description": "Current pipeline stage."
            },
            "completed_steps": {
              "type": "integer",
              "description": "Completed pipeline steps (0-6)."
            },
            "total_steps": {
              "type": "integer",
              "description": "Always 6."
            },
            "agent_progress": {
              "type": "object",
              "description": "The model's internal step counter (an upper bound on the steps a run may take), or null.",
              "properties": {
                "completed_steps": {
                  "type": "integer"
                },
                "total_steps": {
                  "type": "integer"
                }
              }
            }
          },
          "required": [
            "stage",
            "completed_steps",
            "total_steps"
          ]
        },
        "estimated_charge": {
          "type": "object",
          "description": "The charge ceiling quoted for THIS run, fixed at enqueue (統合改善指示書 P1-1). The completed run reports the actual charge in meta.tokens.charged and echoes this ceiling as meta.tokens.maximum_promised; actual never exceeds it.",
          "properties": {
            "minimum": {
              "type": "integer",
              "description": "Floor charge for any completed run."
            },
            "maximum": {
              "type": "integer",
              "description": "Ceiling this run may be charged."
            }
          },
          "required": [
            "minimum",
            "maximum"
          ]
        },
        "message": {
          "type": "string"
        }
      }
    },
    "annotations": {
      "readOnlyHint": false,
      "openWorldHint": false,
      "destructiveHint": true
    }
  },
  {
    "name": "get_analyst_job",
    "description": "Status and result of an ask_analyst run. Status is \"processing\", \"done\" or \"error\"; result_quality.status is **SEPARATE** — a done job can carry a partial result.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "job_id": {
          "type": "string",
          "description": "The job_id returned by ask_analyst."
        }
      },
      "required": [
        "job_id"
      ]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "job_id": {
          "type": "string"
        },
        "status": {
          "type": "string",
          "description": "\"processing\" | \"done\" | \"error\"."
        },
        "progress": {
          "type": "object",
          "description": "Pipeline progress while the job is processing. completed_steps reaches total_steps ONLY when status is \"done\".",
          "properties": {
            "stage": {
              "type": "string",
              "enum": [
                "queued",
                "retrieval",
                "imagery_reconciliation",
                "synthesis",
                "final_validation",
                "persistence",
                "complete"
              ],
              "description": "Current pipeline stage."
            },
            "completed_steps": {
              "type": "integer",
              "description": "Completed pipeline steps (0-6)."
            },
            "total_steps": {
              "type": "integer",
              "description": "Always 6."
            },
            "agent_progress": {
              "type": "object",
              "description": "The model's internal step counter (an upper bound on the steps a run may take), or null.",
              "properties": {
                "completed_steps": {
                  "type": "integer"
                },
                "total_steps": {
                  "type": "integer"
                }
              }
            }
          },
          "required": [
            "stage",
            "completed_steps",
            "total_steps"
          ]
        },
        "brief": {
          "type": "object"
        },
        "meta": {
          "type": "object",
          "description": "Query echo, token charge/balance (meta.tokens), and pagination where applicable."
        },
        "error": {
          "type": "string",
          "description": "Failure reason when status is \"error\"."
        },
        "message": {
          "type": "string"
        },
        "created_at": {
          "type": "string"
        },
        "updated_at": {
          "type": "string"
        }
      }
    },
    "annotations": {
      "readOnlyHint": true,
      "openWorldHint": false,
      "destructiveHint": false
    }
  },
  {
    "name": "query_developments",
    "description": "What actually CHANGED about the events in an area, not which articles are new. Each change is labelled `world` (the event's own state moved) or `measurement` (what we can see moved). Plan-dependent values say so (`locked_by`).",
    "inputSchema": {
      "type": "object",
      "properties": {
        "bbox": {
          "type": "array",
          "items": {
            "type": "number"
          },
          "minItems": 4,
          "maxItems": 4,
          "description": "[minLon, minLat, maxLon, maxLat]. Omit for worldwide."
        },
        "start_date": {
          "type": "string",
          "description": "Date range start (YYYY-MM-DD). With end_date; omit both for today. Records start 2026-09-23 (earlier: unrecorded, not quiet). Plan-bounded: meta.window_clamp."
        },
        "end_date": {
          "type": "string",
          "description": "Date range end (YYYY-MM-DD), inclusive."
        },
        "categories": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "description": "Restrict to these signal categories."
        },
        "axes": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": [
              "attributed_actor",
              "casualties_disputed",
              "casualties_injured",
              "casualties_killed",
              "distinct_hosts",
              "escalation_trend",
              "geoint_score",
              "imagery_post_status",
              "imagery_sar_pair_status",
              "location_level",
              "means_reported",
              "member_count",
              "occurred_at",
              "point_plottable",
              "quality_status",
              "severity_score",
              "stage",
              "target_effect",
              "target_status",
              "targets_named"
            ]
          },
          "description": "Restrict to these axes. An unknown value errors rather than returning nothing."
        },
        "notable_only": {
          "type": "boolean",
          "description": "Default true. False returns every recorded change."
        },
        "include_member_count": {
          "type": "boolean",
          "description": "Default false. \"One more report arrived\" is not news about the event."
        },
        "limit": {
          "type": "number",
          "minimum": 1,
          "maximum": 50,
          "description": "Developments to return (default 20)."
        },
        "offset": {
          "type": "number",
          "minimum": 0,
          "description": "Skip this many; meta.total_count is the window."
        }
      },
      "required": []
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "meta": {
          "type": "object",
          "description": "Query echo, token charge/balance (meta.tokens), and pagination where applicable."
        },
        "developments": {
          "type": "array",
          "items": {
            "type": "object"
          }
        }
      },
      "required": [
        "developments"
      ]
    },
    "annotations": {
      "readOnlyHint": false,
      "openWorldHint": false,
      "destructiveHint": true
    }
  },
  {
    "name": "get_event_thread",
    "description": "One event end to end: state plus every change in order — the \"new event or update\" distinction a feed cannot make. `occurred_at_basis` distinguishes stated, absent and never measured. Plan-dependent: see `locked_by`, `plan_lock`.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "event_id": {
          "type": "string",
          "description": "Event id (UUID). A folded id resolves to its event; merged_from_request says so."
        }
      },
      "required": [
        "event_id"
      ]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "canonical_event": {
          "type": "object"
        },
        "timeline": {
          "type": "array",
          "items": {
            "type": "object"
          }
        },
        "sources": {
          "type": "array",
          "items": {
            "type": "object"
          }
        }
      },
      "required": [
        "canonical_event",
        "timeline"
      ]
    },
    "annotations": {
      "readOnlyHint": true,
      "openWorldHint": false,
      "destructiveHint": false
    }
  },
  {
    "name": "list_watches",
    "description": "The Watchlist as one list, each entry with a state bucket. `updated_since` returns only watches whose CONTENT changed after that instant — what a synchronised copy should poll.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "updated_since": {
          "type": "string",
          "description": "ISO 8601. Only watches whose CONTENT changed after it — the evidence, not renames."
        },
        "cursor": {
          "type": "string",
          "description": "Cursor from meta.next_cursor."
        },
        "limit": {
          "type": "integer",
          "description": "Watches per page when paging (1..500, default 100).",
          "minimum": 1,
          "maximum": 500
        }
      },
      "required": []
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "watches": {
          "type": "array",
          "items": {
            "type": "object"
          }
        },
        "buckets": {
          "type": "object"
        },
        "limits": {
          "type": "object"
        },
        "meta": {
          "type": "object"
        }
      },
      "required": [
        "watches"
      ]
    },
    "annotations": {
      "readOnlyHint": true,
      "openWorldHint": false,
      "destructiveHint": false
    }
  },
  {
    "name": "list_notifications",
    "description": "What changed across the Watchlist, newest first: one row per change a watch reported, with read state. Reading does not mark them read. A value the plan does not open is `locked`, never filled in.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "unread_only": {
          "type": "boolean",
          "description": "Only notifications not yet read."
        },
        "kind": {
          "type": "string",
          "enum": [
            "event_development",
            "related_event",
            "monitoring_anomaly",
            "site_event",
            "new_imagery",
            "standing_order"
          ]
        },
        "watch_id": {
          "type": "string",
          "description": "Id from list_watches."
        },
        "cursor": {
          "type": "string",
          "description": "Cursor from meta.next_cursor."
        },
        "limit": {
          "type": "integer",
          "description": "Rows per page (1..25, default 10).",
          "minimum": 1,
          "maximum": 25
        }
      },
      "required": []
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "notifications": {
          "type": "array",
          "items": {
            "type": "object"
          }
        },
        "meta": {
          "type": "object"
        },
        "full_records": {
          "type": "object",
          "description": "The same query on the REST API and the Python SDK, which return every field and larger pages.",
          "properties": {
            "note": {
              "type": "string"
            },
            "rest": {
              "type": "string"
            },
            "sdk": {
              "type": "string"
            },
            "docs": {
              "type": "string"
            }
          }
        }
      },
      "required": [
        "notifications"
      ]
    },
    "annotations": {
      "readOnlyHint": true,
      "openWorldHint": false,
      "destructiveHint": false
    }
  },
  {
    "name": "get_watch",
    "description": "One watch end to end: target, state, latest change, measurements with recent series, standing-order questions, and for an event watch its stage, developments and thread, plus this account's notes.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "watch_id": {
          "type": "string",
          "description": "Id from list_watches."
        },
        "include_passes": {
          "type": "boolean",
          "description": "Add the collection outlook. Costs the same as predict_satellite_passes; omit it and the call is free."
        }
      },
      "required": [
        "watch_id"
      ]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "watch": {
          "type": "object"
        },
        "thread": {
          "type": "object"
        }
      },
      "required": [
        "watch"
      ]
    },
    "annotations": {
      "readOnlyHint": true,
      "openWorldHint": false,
      "destructiveHint": false
    }
  },
  {
    "name": "create_watch",
    "description": "Add a target to the Watchlist. EVENT: the signal's event id binds the canonical event — **never watch an article URL**. AREA: a bbox. SITE: entity_id or lat+lon, and scale.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "target_type": {
          "type": "string",
          "enum": [
            "event",
            "area",
            "site"
          ]
        },
        "event_id": {
          "type": "string",
          "description": "EVENT: signal uuid."
        },
        "bbox": {
          "type": "array",
          "items": {
            "type": "number"
          },
          "minItems": 4,
          "maxItems": 4,
          "description": "AREA: [W,S,E,N] WGS84, at most 100,000 km² (larger → 400)."
        },
        "entity_id": {
          "type": "string",
          "description": "SITE: registry id"
        },
        "lat": {
          "type": "number"
        },
        "lon": {
          "type": "number"
        },
        "scale": {
          "type": "string",
          "enum": [
            "facility",
            "city",
            "country"
          ]
        },
        "radius_m": {
          "type": "number"
        },
        "metric": {
          "type": "string",
          "description": "SITE: metric or \"none\"."
        },
        "name": {
          "type": "string",
          "description": "Label."
        },
        "notify_email": {
          "type": "boolean",
          "description": "Email on changes."
        },
        "imagery_alerts": {
          "type": "boolean",
          "description": "AREA/SITE: new-scene alerts."
        }
      },
      "required": [
        "target_type"
      ]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "watch": {
          "type": "object"
        },
        "already_existed": {
          "type": "boolean"
        }
      },
      "required": [
        "watch"
      ]
    },
    "annotations": {
      "readOnlyHint": false,
      "openWorldHint": false,
      "destructiveHint": false
    }
  },
  {
    "name": "update_watch",
    "description": "Pause, resume or close a watch. **Pausing is not a display state**: monitored areas stop being measured and charged, standing orders stop checking. **Closing states how the question ended** (close_reason).",
    "inputSchema": {
      "type": "object",
      "properties": {
        "watch_id": {
          "type": "string",
          "description": "Id from list_watches."
        },
        "status": {
          "type": "string",
          "enum": [
            "active",
            "paused",
            "saved",
            "closed"
          ],
          "description": "\"paused\" stops the bound checks; \"active\" resumes them; \"closed\" ends the question and needs close_reason."
        },
        "close_reason": {
          "type": "string",
          "enum": [
            "resolved",
            "lapsed",
            "false_alarm"
          ],
          "description": "Required when status is \"closed\". resolved = an answer was reached; lapsed = interest moved on without an answer; false_alarm = never a watchable event. They point at different things to fix, so do not collapse them."
        },
        "notify_email": {
          "type": "boolean",
          "description": "Email on changes."
        },
        "notify_chat": {
          "type": "boolean",
          "description": "Also post changes to the Slack/Discord channel connected in settings."
        },
        "imagery_alerts": {
          "type": "boolean",
          "description": "AREA/SITE: new-scene alerts."
        }
      },
      "required": [
        "watch_id"
      ]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "watch": {
          "type": "object"
        }
      }
    },
    "annotations": {
      "readOnlyHint": false,
      "openWorldHint": false,
      "destructiveHint": false
    }
  },
  {
    "name": "delete_watch",
    "description": "Delete a watch and its underlying resources — bound monitored areas with their history, and standing orders. To stop without losing them, pause with update_watch.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "watch_id": {
          "type": "string",
          "description": "Id from list_watches."
        }
      },
      "required": [
        "watch_id"
      ]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "deleted": {
          "type": "string"
        },
        "removed": {
          "type": "object"
        }
      }
    },
    "annotations": {
      "readOnlyHint": false,
      "openWorldHint": false,
      "destructiveHint": true,
      "idempotentHint": true
    }
  },
  {
    "name": "add_note",
    "description": "Add a note to a watch, start a thread, or reply. **Confidence is what separates a note from a judgment**: with one it is a JUDGMENT that supersedes the previous judgment rather than overwriting it.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "watch_id": {
          "type": "string",
          "description": "Id from list_watches."
        },
        "note": {
          "type": "string",
          "description": "What you want kept with this watch."
        },
        "title": {
          "type": "string",
          "description": "A heading makes it a thread. A reply cannot have one."
        },
        "parent_id": {
          "type": "string",
          "description": "Reply to this note id. One level deep."
        },
        "confidence": {
          "type": "string",
          "enum": [
            "high",
            "moderate",
            "low"
          ],
          "description": "How sure the judgment is — about the evidence, not the event. Omit and it stays a note."
        },
        "likelihood": {
          "type": "string",
          "enum": [
            "very unlikely",
            "unlikely",
            "roughly even chance",
            "likely",
            "very likely",
            "almost certain"
          ],
          "description": "How probable the thing itself is (ICD 203). Omit rather than guess."
        },
        "gaps": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "description": "What would change this judgment. Only meaningful with a confidence."
        },
        "next_check": {
          "type": "string",
          "description": "When/what to look at next."
        }
      },
      "required": [
        "watch_id",
        "note"
      ]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "note": {
          "type": "object"
        }
      },
      "required": [
        "note"
      ]
    },
    "annotations": {
      "readOnlyHint": false,
      "openWorldHint": false,
      "destructiveHint": false
    }
  },
  {
    "name": "search_entities",
    "description": "Find a named place (airport, base, plant, port, dam, strait…) in any language or by IATA/ICAO code. Max 50.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "Name or partial name (at least 2 characters)."
        },
        "subtypes": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": [
              "port_facility",
              "military_base",
              "airport",
              "refinery_energy",
              "nuclear_facility",
              "launch_site",
              "dam",
              "bridge",
              "government_site",
              "chokepoint",
              "water_body"
            ]
          },
          "description": "Kinds to keep. Omit for all."
        },
        "limit": {
          "type": "number",
          "description": "Max rows (1-50, default 20)."
        }
      },
      "required": [
        "query"
      ]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "entities": {
          "type": "array",
          "items": {
            "type": "object"
          }
        },
        "limit": {
          "type": "number"
        }
      },
      "required": [
        "entities"
      ]
    },
    "annotations": {
      "readOnlyHint": true,
      "openWorldHint": false,
      "destructiveHint": false
    }
  },
  {
    "name": "get_entity",
    "description": "What has happened at one place: the registry record plus its most recent linked events, each with HOW it was linked. **`link_kind: proximity` is an association, not a statement that the event happened there.**",
    "inputSchema": {
      "type": "object",
      "properties": {
        "entity_id": {
          "type": "string",
          "description": "The id from search_entities."
        }
      },
      "required": [
        "entity_id"
      ]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "entity": {
          "type": "object"
        },
        "events": {
          "type": "array",
          "items": {
            "type": "object"
          }
        },
        "event_count": {
          "type": "number"
        },
        "events_24h": {
          "type": "number"
        }
      },
      "required": [
        "entity"
      ]
    },
    "annotations": {
      "readOnlyHint": true,
      "openWorldHint": false,
      "destructiveHint": false
    }
  },
  {
    "name": "get_related_events",
    "description": "The relations recorded for one event: others at the same registry facility, naming the same place, or stored as the same campaign, each saying what is shared; plus reports merged into it. Merely-nearby events are not relations and are not returned. Plan-dependent: see `plan_lock`.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "event_id": {
          "type": "string",
          "description": "The event id (a UUID) from query_signals."
        }
      },
      "required": [
        "event_id"
      ]
    },
    "outputSchema": {
      "type": "object",
      "properties": {
        "summary": {
          "type": "string",
          "description": "One-line natural-language summary of the result, ready to relay to a user."
        },
        "anchor": {
          "type": "object"
        },
        "facilities": {
          "type": "array",
          "items": {
            "type": "object"
          }
        },
        "places": {
          "type": "array",
          "items": {
            "type": "object"
          }
        },
        "related": {
          "type": "array",
          "items": {
            "type": "object"
          }
        },
        "merged_in": {
          "type": "array",
          "items": {
            "type": "object"
          }
        },
        "accounting": {
          "type": "object"
        }
      },
      "required": [
        "related"
      ]
    },
    "annotations": {
      "readOnlyHint": true,
      "openWorldHint": false,
      "destructiveHint": false
    }
  }
] as const;

export const RESOURCES = [
  {
    "uri": "brief://latest",
    "name": "Daily World Brief (latest)",
    "description": "The most recent AI-synthesized Daily World Brief (JSON). Free.",
    "mimeType": "application/json"
  },
  {
    "uri": "signals://schema",
    "name": "Signal object schema",
    "description": "JSON Schema of the public Signal shape returned by query_signals / /api/v1/signals.",
    "mimeType": "application/json"
  },
  {
    "uri": "usage://current",
    "name": "API usage & quota",
    "description": "Remaining token balance and plan capabilities for the calling key. Free.",
    "mimeType": "application/json"
  },
  {
    "uri": "status://current",
    "name": "Data freshness & pipeline status",
    "description": "How current the data is (ingestion/enrichment frontier), the Daily World Brief status, and an Operational/Delayed/Degraded roll-up. Free.",
    "mimeType": "application/json"
  }
] as const;

export const RESOURCE_TEMPLATES = [
  {
    "uriTemplate": "brief://{date}",
    "name": "Daily World Brief by date",
    "description": "The Daily World Brief for a specific UTC date (YYYY-MM-DD). Free.",
    "mimeType": "application/json"
  },
  {
    "uriTemplate": "watch://{watch_id}",
    "name": "One watch, end to end",
    "description": "A Watchlist entry with its current state, latest meaningful change, measurements, (for event watches) the full event thread, and the notes kept against it. The same body get_watch returns. Free.",
    "mimeType": "application/json"
  }
] as const;

export const PROMPTS = [] as const;
