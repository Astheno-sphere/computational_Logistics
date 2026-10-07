#!/usr/bin/env python3
"""
Transcript Manager - Robust YouTube transcript fetching with tracking.

Designed for cron jobs. Processes videos in small batches, tracks status,
and distinguishes between "no transcript available" and "rate limited".

Status tracking:
- success: Transcript fetched and saved
- no_transcript: Confirmed no transcript available (after 3 attempts)
- rate_limited: Failed due to rate limiting (will retry)
- pending: Not yet attempted

Usage:
    python transcript_manager.py              # Process next batch (default: 15)
    python transcript_manager.py --batch 20   # Process 20 videos
    python transcript_manager.py --status     # Show current status
    python transcript_manager.py --reset      # Reset rate_limited to pending

Recommended cron (every 30 minutes):
    */30 * * * * cd /path/to/scripts && python transcript_manager.py --batch 15

"""

import json
import re
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import (
        TranscriptsDisabled,
        NoTranscriptFound,
        VideoUnavailable,
    )
except ImportError:
    print("ERROR: youtube-transcript-api not installed")
    print("Run: pip install youtube-transcript-api")
    exit(1)

REFERENCES_DIR = Path(__file__).parent.parent / "references"
SCRIPTS_DIR = Path(__file__).parent
STATUS_FILE = SCRIPTS_DIR / "transcript_status.json"
LOG_FILE = SCRIPTS_DIR / "transcript_manager.log"

# Files with <= this many lines need transcripts
MIN_LINES_FOR_TRANSCRIPT = 50

# After this many "no transcript" failures, mark as permanently unavailable
MAX_NO_TRANSCRIPT_ATTEMPTS = 3

# Default batch size
DEFAULT_BATCH_SIZE = 15


def log(message: str):
    """Log message to file and stdout."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_line + '\n')


def load_status() -> dict:
    """Load status from JSON file."""
    if STATUS_FILE.exists():
        with open(STATUS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"videos": {}, "last_run": None, "stats": {}}


def save_status(status: dict):
    """Save status to JSON file."""
    status["last_updated"] = datetime.now().isoformat()
    with open(STATUS_FILE, 'w', encoding='utf-8') as f:
        json.dump(status, f, indent=2)


def extract_youtube_id(content: str) -> Optional[str]:
    """Extract YouTube ID from file content."""
    match = re.search(r'\*\*YouTube ID:\*\*\s*(\S+)', content)
    return match.group(1) if match else None


def scan_all_videos() -> dict[str, dict]:
    """Scan references directory for all videos needing transcripts."""
    videos = {}

    for filepath in sorted(REFERENCES_DIR.glob("*.md")):
        if filepath.name in {"index.yaml", "summaries.md", "quick-index.md", "learning-paths.md"}:
            continue

        try:
            content = filepath.read_text(encoding='utf-8')
        except Exception:
            continue

        youtube_id = extract_youtube_id(content)
        if not youtube_id:
            continue

        lines = len(content.split('\n'))

        videos[filepath.name] = {
            "youtube_id": youtube_id,
            "lines": lines,
            "needs_transcript": lines <= MIN_LINES_FOR_TRANSCRIPT
        }

    return videos


def initialize_status() -> dict:
    """Initialize or update status with current video list."""
    status = load_status()
    videos = scan_all_videos()

    for filename, info in videos.items():
        if filename not in status["videos"]:
            if info["needs_transcript"]:
                status["videos"][filename] = {
                    "youtube_id": info["youtube_id"],
                    "status": "pending",
                    "attempts": 0,
                    "last_attempt": None
                }
            else:
                # Already has content
                status["videos"][filename] = {
                    "youtube_id": info["youtube_id"],
                    "status": "success",
                    "attempts": 0,
                    "last_attempt": None,
                    "note": "Already had content"
                }

    save_status(status)
    return status


def get_videos_to_process(status: dict, batch_size: int) -> list[tuple[str, str]]:
    """Get next batch of videos to process."""
    to_process = []

    for filename, info in status["videos"].items():
        if info["status"] == "pending":
            to_process.append((filename, info["youtube_id"]))
        elif info["status"] == "rate_limited":
            # Check if enough time has passed (30 minutes)
            if info.get("last_attempt"):
                last = datetime.fromisoformat(info["last_attempt"])
                if datetime.now() - last > timedelta(minutes=30):
                    to_process.append((filename, info["youtube_id"]))

    return to_process[:batch_size]


def fetch_transcript(youtube_id: str) -> tuple[Optional[str], str]:
    """
    Fetch transcript from YouTube.

    Returns:
        (transcript_text, status) where status is:
        - "success" if transcript fetched
        - "no_transcript" if no transcript available
        - "rate_limited" if rate limited or other error
    """
    try:
        api = YouTubeTranscriptApi()

        # Try English first
        try:
            fetched = api.fetch(youtube_id, languages=['en', 'en-US', 'en-GB'])
            return format_transcript(fetched), "success"
        except NoTranscriptFound:
            pass

        # Try any available language
        try:
            transcript_list = api.list(youtube_id)
            for transcript in transcript_list:
                fetched = transcript.fetch()
                return format_transcript(fetched), "success"
        except NoTranscriptFound:
            pass

        return None, "no_transcript"

    except TranscriptsDisabled:
        return None, "no_transcript"
    except VideoUnavailable:
        return None, "no_transcript"
    except Exception as e:
        error_msg = str(e).lower()
        # These patterns indicate rate limiting
        if any(x in error_msg for x in ["too many", "429", "quota", "blocked", "captcha"]):
            return None, "rate_limited"
        # Unknown error - treat as rate limited to be safe
        log(f"    Unknown error for {youtube_id}: {e}")
        return None, "rate_limited"


def format_transcript(fetched) -> str:
    """Format transcript entries into readable paragraphs."""
    if not fetched:
        return ""

    paragraphs = []
    current_para = []
    current_time = 0

    for entry in fetched:
        text = entry.text.strip() if entry.text else ""
        if not text:
            continue

        start = entry.start

        if start - current_time > 30 and current_para:
            paragraphs.append(' '.join(current_para))
            current_para = []
            current_time = start

        current_para.append(text)

    if current_para:
        paragraphs.append(' '.join(current_para))

    return '\n\n'.join(paragraphs)


def update_file_with_transcript(filepath: Path, transcript: str) -> bool:
    """Append transcript to file."""
    try:
        content = filepath.read_text(encoding='utf-8')
        new_content = content.rstrip() + '\n\n## Transcript\n\n' + transcript + '\n'
        filepath.write_text(new_content, encoding='utf-8')
        return True
    except Exception as e:
        log(f"    Error writing file: {e}")
        return False


def process_batch(batch_size: int = DEFAULT_BATCH_SIZE) -> dict:
    """Process a batch of videos."""
    status = initialize_status()
    to_process = get_videos_to_process(status, batch_size)

    if not to_process:
        log("No videos to process")
        return {"processed": 0, "success": 0, "no_transcript": 0, "rate_limited": 0}

    log(f"Processing {len(to_process)} videos...")

    results = {"processed": 0, "success": 0, "no_transcript": 0, "rate_limited": 0}
    rate_limited = False

    for i, (filename, youtube_id) in enumerate(to_process):
        if rate_limited:
            break

        log(f"[{i+1}/{len(to_process)}] {filename}")

        transcript, result_status = fetch_transcript(youtube_id)
        results["processed"] += 1

        video_status = status["videos"][filename]
        video_status["last_attempt"] = datetime.now().isoformat()
        video_status["attempts"] = video_status.get("attempts", 0) + 1

        if result_status == "success" and transcript:
            filepath = REFERENCES_DIR / filename
            if update_file_with_transcript(filepath, transcript):
                video_status["status"] = "success"
                results["success"] += 1
                log(f"    SUCCESS - {len(transcript.split())} words")
            else:
                video_status["status"] = "rate_limited"  # Retry later
                results["rate_limited"] += 1

        elif result_status == "no_transcript":
            video_status["attempts"] = video_status.get("attempts", 0)
            if video_status["attempts"] >= MAX_NO_TRANSCRIPT_ATTEMPTS:
                video_status["status"] = "no_transcript"
                log(f"    NO TRANSCRIPT (confirmed after {video_status['attempts']} attempts)")
            else:
                video_status["status"] = "rate_limited"  # Try again later
                log(f"    No transcript (attempt {video_status['attempts']}/{MAX_NO_TRANSCRIPT_ATTEMPTS})")
            results["no_transcript"] += 1

        elif result_status == "rate_limited":
            video_status["status"] = "rate_limited"
            results["rate_limited"] += 1
            log("    RATE LIMITED - stopping batch")
            rate_limited = True

        # Small delay between requests
        if not rate_limited and i < len(to_process) - 1:
            time.sleep(1.0)

    save_status(status)

    # Calculate totals
    totals = {"success": 0, "pending": 0, "no_transcript": 0, "rate_limited": 0}
    for v in status["videos"].values():
        s = v.get("status", "pending")
        totals[s] = totals.get(s, 0) + 1

    log(f"\nBatch complete: {results['success']} success, {results['no_transcript']} no transcript, {results['rate_limited']} rate limited")
    log(f"Overall: {totals['success']} done, {totals['pending']} pending, {totals['rate_limited']} rate limited, {totals['no_transcript']} unavailable")

    return results


def show_status():
    """Show current status summary."""
    status = load_status()

    totals = {"success": 0, "pending": 0, "no_transcript": 0, "rate_limited": 0}
    for v in status["videos"].values():
        s = v.get("status", "pending")
        totals[s] = totals.get(s, 0) + 1

    total = sum(totals.values())

    print(f"\n{'='*50}")
    print("Transcript Status Summary")
    print(f"{'='*50}")
    print(f"  Total videos:      {total}")
    print(f"  Success:           {totals['success']} ({100*totals['success']/total:.1f}%)")
    print(f"  Pending:           {totals['pending']}")
    print(f"  Rate limited:      {totals['rate_limited']} (will retry)")
    print(f"  No transcript:     {totals['no_transcript']} (confirmed unavailable)")
    print(f"\n  Last updated: {status.get('last_updated', 'Never')}")

    if totals['rate_limited'] > 0:
        print(f"\n  Run again in 30 minutes to retry rate-limited videos")


def reset_rate_limited():
    """Reset rate-limited videos to pending for retry."""
    status = load_status()
    count = 0

    for v in status["videos"].values():
        if v.get("status") == "rate_limited":
            v["status"] = "pending"
            v["attempts"] = 0
            count += 1

    save_status(status)
    log(f"Reset {count} rate-limited videos to pending")


def main():
    parser = argparse.ArgumentParser(description="Manage YouTube transcript fetching")
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Batch size (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--status", action="store_true",
                        help="Show current status")
    parser.add_argument("--reset", action="store_true",
                        help="Reset rate-limited videos to pending")
    args = parser.parse_args()

    if args.status:
        initialize_status()
        show_status()
    elif args.reset:
        reset_rate_limited()
    else:
        results = process_batch(args.batch)

        # Exit code indicates if there's more work to do
        # 0 = all done, 1 = more pending, 2 = rate limited
        if results["rate_limited"] > 0:
            exit(2)
        elif results["processed"] > 0:
            exit(1)
        else:
            exit(0)


if __name__ == "__main__":
    main()
