"""Open-access full-text PDF download for literature index entries.

Downloads PDFs into ``papers/full_texts/`` and records paths under
``extra_fields.full_text`` in ``papers/literature_index.json``.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import shutil
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from agentsociety2.logger import get_logger

logger = get_logger()

FullTextOutcome = Literal["downloaded", "no_candidate", "failed", "skipped"]

USER_AGENT = (
    "AgentSociety2 literature skill (+https://github.com/tsinghua-fib-lab/agentsociety)"
)


class FullTextDownloadError(Exception):
    """Raised when a candidate URL does not yield a valid PDF."""


def load_literature_index_dict(workspace: Path) -> tuple[Path, dict[str, Any]]:
    """Load ``papers/literature_index.json`` from a workspace.

    :param workspace: Workspace root directory.
    :returns: Tuple of index file path and parsed JSON object.
    :raises FileNotFoundError: If the index file is missing.
    :raises ValueError: If the file is not valid JSON.
    """
    index_path = workspace / "papers" / "literature_index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"Literature index not found: {index_path}")
    try:
        return index_path, json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {index_path}: {exc}") from exc


def save_literature_index_dict(index_path: Path, data: dict[str, Any]) -> None:
    """Write the literature index and set ``updated_at`` to the current UTC time.

    :param index_path: Path to ``literature_index.json``.
    :param data: Index document to serialize.
    """
    data["updated_at"] = datetime.now(UTC).isoformat()
    index_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def index_entries(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the ``entries`` array from an index document.

    :param data: Parsed literature index JSON.
    :returns: List of entry dicts.
    :raises ValueError: If ``entries`` is missing or not a list.
    """
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("literature_index.json has no valid entries array")
    return entries


def pick_index_entry(data: dict[str, Any], entry_number: int) -> dict[str, Any]:
    """Select one index entry by 1-based position.

    :param data: Parsed literature index JSON.
    :param entry_number: 1-based entry index (CLI convention).
    :returns: The entry dict at that position.
    :raises IndexError: If ``entry_number`` is out of range.
    :raises TypeError: If the entry is not an object.
    """
    entries = index_entries(data)
    if entry_number < 1 or entry_number > len(entries):
        raise IndexError(
            f"Entry {entry_number} is out of range; index has {len(entries)} entries"
        )
    entry = entries[entry_number - 1]
    if not isinstance(entry, dict):
        raise TypeError(f"Entry {entry_number} is not an object")
    return entry


def entry_extra_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """Return ``extra_fields`` on an entry, creating an empty dict if absent.

    :param entry: Literature index entry.
    :returns: Mutable ``extra_fields`` dict attached to ``entry``.
    """
    extra = entry.get("extra_fields")
    if not isinstance(extra, dict):
        extra = {}
        entry["extra_fields"] = extra
    return extra


def nested_dict(parent: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a nested dict value on ``parent``, or an empty dict if missing or wrong type."""
    value = parent.get(key)
    return value if isinstance(value, dict) else {}


def add_candidate_url(candidates: list[str], value: Any) -> None:
    if not isinstance(value, str):
        return
    value = value.strip()
    if not value or not re.match(r"^https?://", value, re.IGNORECASE):
        return
    if value not in candidates:
        candidates.append(value)


def arxiv_pdf_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    patterns = [
        r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5})(?:v\d+)?",
        r"10\.48550/arxiv\.([0-9]{4}\.[0-9]{4,5})(?:v\d+)?",
        r"\barxiv[:/ ]+([0-9]{4}\.[0-9]{4,5})(?:v\d+)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            return f"https://arxiv.org/pdf/{match.group(1)}.pdf"
    return None


def candidate_urls(entry: dict[str, Any]) -> list[str]:
    """Collect HTTP(S) PDF candidate URLs from entry metadata.

    :param entry: Literature index entry (top-level and ``extra_fields``).
    :returns: De-duplicated list of candidate URLs (arxiv abs URLs normalized to PDF).
    """
    candidates: list[str] = []
    extra_fields = nested_dict(entry, "extra_fields")
    sources: list[dict[str, Any]] = [entry]
    if extra_fields:
        sources.append(extra_fields)

    for source in sources:
        for field in (
            "pdf_url",
            "pdf",
            "full_text_url",
            "fulltext_url",
            "download_url",
            "url",
        ):
            value = source.get(field)
            resolved = arxiv_pdf_url(value)
            add_candidate_url(candidates, resolved or value)

        for nested_key in ("open_access", "best_oa_location", "primary_location"):
            nested = source.get(nested_key)
            if isinstance(nested, dict):
                for field in ("pdf_url", "landing_page_url", "url"):
                    value = nested.get(field)
                    resolved = arxiv_pdf_url(value)
                    add_candidate_url(candidates, resolved or value)

    doi = entry.get("doi") or extra_fields.get("doi")
    resolved = arxiv_pdf_url(doi)
    if resolved:
        add_candidate_url(candidates, resolved)
    elif isinstance(doi, str) and doi.strip():
        doi = doi.strip()
        add_candidate_url(
            candidates,
            (
                doi
                if doi.startswith(("http://", "https://"))
                else f"https://doi.org/{doi}"
            ),
        )

    return candidates


def safe_pdf_stem(entry: dict[str, Any]) -> str:
    """Build a filesystem-safe basename for a full-text PDF file.

    :param entry: Literature index entry.
    :returns: Stem derived from ``file_path`` or sanitized ``title``.
    """
    file_path = entry.get("file_path")
    if isinstance(file_path, str) and file_path:
        return Path(file_path).stem
    title = entry.get("title") or "full_text"
    stem = re.sub(r'[<>:"/\\|?*\s]+', "_", str(title)).strip("_")
    return stem[:100] or "full_text"


def looks_like_pdf(url: str, content_type: str, content: bytes) -> bool:
    return (
        "application/pdf" in content_type.lower()
        or urlparse(url).path.lower().endswith(".pdf")
        or content.startswith(b"%PDF-")
    )


def _is_restricted_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return not ip.is_global


def _validate_public_url(url: str) -> None:
    """Validate that a URL is safe to fetch (SSRF protection).

    Allows only http/https. Blocks literal private IPs, localhost aliases,
    and hostnames whose DNS answers include non-global addresses.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FullTextDownloadError(f"Unsupported URL scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise FullTextDownloadError(f"URL has no hostname: {url}")

    if hostname.lower() in ("localhost", "metadata.google.internal"):
        raise FullTextDownloadError(f"URL targets restricted host: {hostname}")

    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if _is_restricted_ip(literal_ip):
            raise FullTextDownloadError(f"URL targets restricted IP range: {hostname}")
        return

    try:
        addr_infos = socket.getaddrinfo(
            hostname, parsed.port or 0, type=socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise FullTextDownloadError(
            f"DNS resolution failed for {hostname}: {exc}"
        ) from exc

    if not addr_infos:
        raise FullTextDownloadError(
            f"DNS resolution returned no addresses for {hostname}"
        )

    for info in addr_infos:
        ip = ipaddress.ip_address(info[4][0])
        if _is_restricted_ip(ip):
            raise FullTextDownloadError(
                f"URL hostname resolves to restricted address: {hostname} -> {ip}"
            )


class _SafeRedirectHandler(HTTPRedirectHandler):
    """Re-validate every redirect hop before following it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_pdf_bytes(url: str, *, timeout: int = 60) -> tuple[bytes, str]:
    """Download bytes from a URL and verify the response looks like a PDF.

    :param url: HTTP(S) URL to fetch.
    :param timeout: Socket timeout in seconds.
    :returns: Tuple of PDF bytes and final URL after redirects.
    :raises FullTextDownloadError: On HTTP errors, network errors, or non-PDF content.
    """
    _validate_public_url(url)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    opener = build_opener(_SafeRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            content = response.read()
            final_url = response.geturl()
            _validate_public_url(final_url)
            content_type = response.headers.get("content-type", "")
            if not looks_like_pdf(final_url, content_type, content):
                raise FullTextDownloadError(
                    "The candidate URL did not return a PDF. "
                    f"content-type={content_type!r}, final_url={final_url}"
                )
            return content, final_url
    except HTTPError as exc:
        raise FullTextDownloadError(f"HTTP {exc.code} for {url}") from exc
    except URLError as exc:
        raise FullTextDownloadError(str(exc.reason)) from exc


def relative_workspace_path(workspace: Path, target: Path) -> str:
    return target.resolve().relative_to(workspace.resolve()).as_posix()


def record_full_text(
    entry: dict[str, Any],
    *,
    status: str,
    file_path: str | None = None,
    source_url: str | None = None,
    reason: str | None = None,
) -> None:
    """Update ``extra_fields.full_text`` on an index entry.

    :param entry: Literature index entry (mutated in place).
    :param status: Outcome status (e.g. ``downloaded``, ``failed``, ``no_candidate``).
    :param file_path: Workspace-relative path to the PDF, if any.
    :param source_url: URL used for a successful download.
    :param reason: Human-readable failure or skip reason.
    """
    info: dict[str, Any] = {
        "status": status,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if file_path:
        info["file_path"] = file_path
    if source_url:
        info["source_url"] = source_url
    if reason:
        info["reason"] = reason
    entry_extra_fields(entry)["full_text"] = info


def full_text_status(entry: dict[str, Any]) -> str:
    """Return the ``status`` field from ``extra_fields.full_text``, or empty string.

    :param entry: Literature index entry.
    :returns: Status string such as ``downloaded`` or ``failed``.
    """
    full_text = nested_dict(nested_dict(entry, "extra_fields"), "full_text")
    return str(full_text.get("status", ""))


def download_entry_pdf(
    workspace_path: Path,
    entry: dict[str, Any],
    *,
    explicit_url: str | None = None,
    output_name: str | None = None,
    skip_if_downloaded: bool = True,
) -> FullTextOutcome:
    """Try to download an open-access PDF for one index entry.

    :param workspace_path: Workspace root directory.
    :param entry: Literature index entry (mutated in place on success or failure).
    :param explicit_url: Optional URL to try before metadata-derived candidates.
    :param output_name: Optional filename under ``papers/full_texts/``.
    :param skip_if_downloaded: If true, skip when status is already ``downloaded``.
    :returns: One of ``downloaded``, ``skipped``, ``no_candidate``, or ``failed``.
    """
    if skip_if_downloaded and full_text_status(entry) == "downloaded":
        extra = entry_extra_fields(entry)
        ft = extra.get("full_text", {})
        if isinstance(ft, dict) and ft.get("file_path"):
            return "skipped"

    urls = [explicit_url] if explicit_url else candidate_urls(entry)
    if not urls:
        record_full_text(
            entry,
            status="no_candidate",
            reason="No open PDF candidate URL was found in the metadata.",
        )
        return "no_candidate"

    full_text_dir = workspace_path / "papers" / "full_texts"
    full_text_dir.mkdir(parents=True, exist_ok=True)
    target = full_text_dir / (output_name or f"{safe_pdf_stem(entry)}.pdf")

    errors: list[str] = []
    for url in urls:
        try:
            content, final_url = download_pdf_bytes(url)
            target.write_bytes(content)
            rel = relative_workspace_path(workspace_path, target)
            record_full_text(
                entry,
                status="downloaded",
                file_path=rel,
                source_url=final_url,
            )
            return "downloaded"
        except FullTextDownloadError as exc:
            errors.append(f"{url}: {exc}")

    record_full_text(
        entry,
        status="failed",
        reason="; ".join(errors),
    )
    return "failed"


def download_open_access_pdfs(
    workspace_path: Path,
    *,
    only_without_full_text: bool = True,
) -> dict[str, int]:
    """Download open-access PDFs for all entries in the workspace index.

    :param workspace_path: Workspace root directory.
    :param only_without_full_text: Skip entries already marked ``downloaded``.
    :returns: Counts keyed by outcome: ``downloaded``, ``failed``, ``no_candidate``, ``skipped``.
    """
    index_path, data = load_literature_index_dict(workspace_path)
    stats = {"downloaded": 0, "failed": 0, "no_candidate": 0, "skipped": 0}

    for entry in index_entries(data):
        if not isinstance(entry, dict):
            continue
        if only_without_full_text and full_text_status(entry) == "downloaded":
            stats["skipped"] += 1
            continue

        outcome = download_entry_pdf(
            workspace_path,
            entry,
            skip_if_downloaded=only_without_full_text,
        )
        stats[outcome] += 1

    save_literature_index_dict(index_path, data)
    logger.info(
        "Full-text download finished: downloaded=%s failed=%s no_candidate=%s skipped=%s",
        stats["downloaded"],
        stats["failed"],
        stats["no_candidate"],
        stats["skipped"],
    )
    return stats


def is_enrichable(entry: dict[str, Any]) -> bool:
    """Return whether an entry failed download and has not been marked enriched.

    :param entry: Literature index entry.
    :returns: ``True`` if status is ``failed`` or ``no_candidate`` and ``enriched`` is false.
    """
    full_text = nested_dict(nested_dict(entry, "extra_fields"), "full_text")
    status = full_text.get("status", "")
    enriched = full_text.get("enriched", False)
    return status in ("failed", "no_candidate") and not enriched


def command_candidates(args: argparse.Namespace) -> int:
    _, data = load_literature_index_dict(args.workspace)
    entries = index_entries(data)
    selected = [args.entry] if args.entry else list(range(1, len(entries) + 1))
    for number in selected:
        entry = pick_index_entry(data, number)
        print(f"\n[{number}] {entry.get('title', 'Untitled')}")
        urls = candidate_urls(entry)
        if not urls:
            print("  No candidate URLs found.")
            continue
        for url in urls:
            print(f"  - {url}")
    return 0


def command_download(args: argparse.Namespace) -> int:
    index_path, data = load_literature_index_dict(args.workspace)
    entry = pick_index_entry(data, args.entry)
    outcome = download_entry_pdf(
        args.workspace,
        entry,
        explicit_url=args.url,
        output_name=args.output_name,
        skip_if_downloaded=False,
    )
    save_literature_index_dict(index_path, data)
    if outcome == "downloaded":
        rel = entry_extra_fields(entry)["full_text"]["file_path"]
        print(f"Downloaded PDF: {rel}")
        print(f"Updated index: {index_path}")
        return 0
    if outcome == "no_candidate":
        print("No candidate URLs found; index marked as no_candidate.")
        return 2
    print("No PDF could be downloaded. Index marked as failed.")
    reason = entry_extra_fields(entry).get("full_text", {}).get("reason", "")
    if reason:
        print(reason)
    return 1


def command_register(args: argparse.Namespace) -> int:
    index_path, data = load_literature_index_dict(args.workspace)
    entry = pick_index_entry(data, args.entry)
    source = args.file.expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise SystemExit(f"PDF file not found: {source}")

    full_text_dir = args.workspace / "papers" / "full_texts"
    full_text_dir.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() != ".pdf":
        raise SystemExit("Only PDF files should be registered as full_text artifacts")

    try:
        rel = relative_workspace_path(args.workspace, source)
        is_in_full_text_dir = source.is_relative_to(full_text_dir.resolve())
    except ValueError:
        is_in_full_text_dir = False

    if not is_in_full_text_dir:
        target = full_text_dir / (args.output_name or f"{safe_pdf_stem(entry)}.pdf")
        shutil.copy2(source, target)
        rel = relative_workspace_path(args.workspace, target)

    record_full_text(
        entry,
        status="downloaded",
        file_path=rel,
        source_url=args.source_url,
    )
    save_literature_index_dict(index_path, data)
    print(f"Registered PDF: {rel}")
    print(f"Updated index: {index_path}")
    return 0


def command_mark(args: argparse.Namespace) -> int:
    index_path, data = load_literature_index_dict(args.workspace)
    entry = pick_index_entry(data, args.entry)
    record_full_text(
        entry,
        status=args.status,
        source_url=args.source_url,
        reason=args.reason,
    )
    save_literature_index_dict(index_path, data)
    print(f"Marked entry {args.entry} as {args.status}")
    print(f"Updated index: {index_path}")
    return 0


def command_enrich(args: argparse.Namespace) -> int:
    index_path, data = load_literature_index_dict(args.workspace)
    entries = index_entries(data)

    if args.dry_run:
        found = []
        for i, entry in enumerate(entries, 1):
            if is_enrichable(entry):
                title = entry.get("title", "Untitled")
                ft = nested_dict(nested_dict(entry, "extra_fields"), "full_text")
                status = ft.get("status", "")
                reason = ft.get("reason", "")
                found.append(i)
                print(f"[{i}] {title} (status: {status})")
                if reason:
                    print(f"     Reason: {reason[:120]}")
        if not found:
            print("No enrichable entries found.")
        else:
            print(f"\n{len(found)} enrichable entry/entries: {found}")
        return 0

    if args.entry:
        entry = pick_index_entry(data, args.entry)
        extra = entry_extra_fields(entry)
        full_text = nested_dict(extra, "full_text")
        full_text["enriched"] = True
        full_text["enriched_at"] = datetime.now(UTC).isoformat()
        extra["full_text"] = full_text
        save_literature_index_dict(index_path, data)
        print(f"Marked entry {args.entry} as enriched")
        print(f"Updated index: {index_path}")
        return 0

    print(
        "Provide --entry N to mark an entry as enriched, or --dry-run to list enrichable entries."
    )
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage literature full-text PDFs")
    parser.add_argument(
        "--workspace", type=Path, default=Path("."), help="Workspace path"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    candidates = subparsers.add_parser("candidates", help="List candidate PDF URLs")
    candidates.add_argument("--entry", type=int, help="1-based literature entry number")
    candidates.set_defaults(func=command_candidates)

    download = subparsers.add_parser(
        "download", help="Download an open PDF and update index"
    )
    download.add_argument(
        "--entry", type=int, required=True, help="1-based literature entry number"
    )
    download.add_argument("--url", help="Explicit PDF URL to try first")
    download.add_argument(
        "--output-name", help="Filename to use under papers/full_texts/"
    )
    download.set_defaults(func=command_download)

    register = subparsers.add_parser("register", help="Register an existing local PDF")
    register.add_argument(
        "--entry", type=int, required=True, help="1-based literature entry number"
    )
    register.add_argument("--file", type=Path, required=True, help="PDF path")
    register.add_argument("--source-url", help="Original URL, if known")
    register.add_argument(
        "--output-name",
        help="Filename if the PDF must be copied into papers/full_texts/",
    )
    register.set_defaults(func=command_register)

    mark = subparsers.add_parser("mark", help="Record full-text status without a PDF")
    mark.add_argument(
        "--entry", type=int, required=True, help="1-based literature entry number"
    )
    mark.add_argument("--status", choices=["no_candidate", "failed"], required=True)
    mark.add_argument("--reason", help="Human-readable reason")
    mark.add_argument("--source-url", help="Candidate URL, if relevant")
    mark.set_defaults(func=command_mark)

    enrich = subparsers.add_parser(
        "enrich",
        help="List or mark entries whose notes were manually supplemented (no PDF)",
    )
    enrich.add_argument(
        "--entry", type=int, help="1-based literature entry number to mark as enriched"
    )
    enrich.add_argument(
        "--dry-run",
        action="store_true",
        help="List entries that can be enriched (do not modify)",
    )
    enrich.set_defaults(func=command_enrich)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.workspace = args.workspace.expanduser().resolve()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
