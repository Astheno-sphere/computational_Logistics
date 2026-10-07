# Daily Guidance Examples

## Init

```bash
python scripts/daily_guidance.py init --date 2026-06-12
```

This creates `state/daily_guidance/2026-06-12/story.yaml` with TODO comments.

## Check

```bash
python scripts/daily_guidance.py check --date 2026-06-12
```

## Executable Story

```yaml
story_id: agent_0007:2026-06-12
date: "2026-06-12"
status: ready
segments:
  - id: morning_work
    start: "09:00"
    end: "12:00"
    activity: work
    location_policy: work_aoi
    maslow_reason:
      need: esteem.role_obligation
      reason: work satisfies the agent's weekday role obligation
      risk: worker profile would lack a realistic workday
      required: required
    tpb_reason:
      want:
        reason: agent wants to complete expected work duties
        status: supported
      norm:
        reason: weekday work is normal for this role
        status: supported
      can:
        reason: work location is reachable from home
        status: supported
      proof: profile occupation and work AOI support weekday morning work
      choice: commit
self_check:
  maslow_result: pass
  tpb_result: pass
  issues: []
execution:
  current_segment_id: morning_work
  completed_segments: []
  actual_timeline: []
  pending_deviation: null
change_log:
  - event_id: story_0001
    type: story_created
    time: "2026-06-12T06:05:00"
    reason: initial LLM daily story based on profile and environment
```
