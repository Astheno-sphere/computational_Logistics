#!/usr/bin/env python3
"""
Fetch YouTube transcripts for video files missing full content.

Uses youtube-transcript-api to get auto-generated or manual captions.
Appends transcripts to files that only have metadata/timestamps.

Requirements:
    pip install youtube-transcript-api

Usage:
    python fetch_transcripts.py           # Fetch all missing transcripts
    python fetch_transcripts.py --dry-run # Report which files need transcripts
    python fetch_transcripts.py --limit 5 # Process only first 5 files
"""

import re
import time
import argparse
from pathlib import Path
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
FAILED_LOG = SCRIPTS_DIR / "failed_transcripts.txt"

# Files with <= this many lines need transcripts
MIN_LINES_FOR_TRANSCRIPT = 50


def extract_youtube_id(content: str) -> Optional[str]:
    """Extract YouTube ID from file content."""
    match = re.search(r'\*\*YouTube ID:\*\*\s*(\S+)', content)
    return match.group(1) if match else None


def get_files_needing_transcripts() -> list[tuple[Path, str]]:
    """Find video files that need transcripts fetched."""
    files_to_process = []

    for filepath in sorted(REFERENCES_DIR.glob("*.md")):
        # Skip index files
        if filepath.name in {"index.yaml", "summaries.md", "quick-index.md", "learning-paths.md"}:
            continue

        try:
            content = filepath.read_text(encoding='utf-8')
        except Exception:
            continue

        lines = content.split('\n')

        # Check if it's a video with YouTube ID and short content
        youtube_id = extract_youtube_id(content)
        if youtube_id and len(lines) <= MIN_LINES_FOR_TRANSCRIPT:
            files_to_process.append((filepath, youtube_id))

    return files_to_process


def fetch_transcript(youtube_id: str) -> Optional[str]:
    """
    Fetch transcript from YouTube.

    Tries English first, then any available language.
    Returns formatted transcript text or None if unavailable.
    """
    try:
        api = YouTubeTranscriptApi()

        # Try to fetch English transcript directly
        try:
            fetched = api.fetch(youtube_id, languages=['en', 'en-US', 'en-GB'])
            return format_transcript(fetched)
        except NoTranscriptFound:
            pass

        # Try any available language as fallback
        try:
            transcript_list = api.list(youtube_id)
            for transcript in transcript_list:
                fetched = transcript.fetch()
                return format_transcript(fetched)
        except NoTranscriptFound:
            pass

        return None

    except TranscriptsDisabled:
        return None
    except VideoUnavailable:
        return None
    except NoTranscriptFound:
        return None
    except Exception as e:
        print(f"    Unexpected error: {e}")
        return None


def format_transcript(fetched) -> str:
    """
    Format transcript entries into readable paragraphs.

    Groups approximately 30 seconds of text together to create
    natural paragraph breaks.

    Args:
        fetched: FetchedTranscript object that iterates FetchedTranscriptSnippet objects
                 Each snippet has .text, .start, and .duration attributes
    """
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

        # Start new paragraph every ~30 seconds
        if start - current_time > 30 and current_para:
            paragraphs.append(' '.join(current_para))
            current_para = []
            current_time = start

        current_para.append(text)

    # Don't forget the last paragraph
    if current_para:
        paragraphs.append(' '.join(current_para))

    return '\n\n'.join(paragraphs)


def update_file_with_transcript(filepath: Path, transcript: str) -> bool:
    """
    Append transcript to file after the existing content.

    Returns True if successful, False otherwise.
    """
    try:
        content = filepath.read_text(encoding='utf-8')

        # Add transcript section
        new_content = content.rstrip() + '\n\n## Transcript\n\n' + transcript + '\n'

        filepath.write_text(new_content, encoding='utf-8')
        return True

    except Exception as e:
        print(f"    Error writing file: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Fetch YouTube transcripts for video files")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report which files need transcripts without fetching")
    parser.add_argument("--limit", type=int, default=0,
                        help="Process only first N files (0 = all)")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Delay between requests in seconds (default: 0.5)")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("YouTube Transcript Fetcher")
    print(f"{'='*60}")

    files_to_process = get_files_needing_transcripts()
    total = len(files_to_process)

    print(f"\nFound {total} files needing transcripts")

    if args.limit > 0:
        files_to_process = files_to_process[:args.limit]
        print(f"Processing first {args.limit} files only")

    if args.dry_run:
        print("\n[DRY RUN - No changes will be made]")
        print("\nFiles needing transcripts:")
        for filepath, youtube_id in files_to_process:
            print(f"  {filepath.name} ({youtube_id})")
        return

    success = 0
    failed = []
    skipped = 0

    print(f"\nProcessing {len(files_to_process)} files...")
    print(f"Rate limit: {args.delay}s between requests")
    print()

    for i, (filepath, youtube_id) in enumerate(files_to_process):
        progress = f"[{i+1}/{len(files_to_process)}]"
        print(f"{progress} {filepath.name} ({youtube_id})")

        transcript = fetch_transcript(youtube_id)

        if transcript:
            if update_file_with_transcript(filepath, transcript):
                lines_added = len(transcript.split('\n'))
                print(f"    ✓ Added {lines_added} lines of transcript")
                success += 1
            else:
                print(f"    ✗ Failed to write file")
                failed.append((filepath.name, youtube_id, "Write error"))
        else:
            print(f"    ✗ No transcript available")
            failed.append((filepath.name, youtube_id, "No transcript"))

        # Rate limiting
        if i < len(files_to_process) - 1:
            time.sleep(args.delay)

    # Summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    print(f"  Success: {success}")
    print(f"  Failed: {len(failed)}")
    print(f"  Total processed: {len(files_to_process)}")

    # Save failed list for manual review
    if failed:
        print(f"\nFailed files saved to: {FAILED_LOG}")
        with open(FAILED_LOG, 'w', encoding='utf-8') as f:
            f.write("# Files that failed to get transcripts\n")
            f.write("# Format: filename,youtube_id,reason\n\n")
            for name, yt_id, reason in failed:
                f.write(f"{name},{yt_id},{reason}\n")

        print("\nFailed files:")
        for name, yt_id, reason in failed[:10]:
            print(f"  - {name}: {reason}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more")


if __name__ == "__main__":
    main()
