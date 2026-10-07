"""Tests for literature library sync and BibTeX helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from agentsociety2.skills.literature.doi_lookup import BibliographicRecord
from agentsociety2.skills.literature.library_ops import (
    enrich_metadata,
    entry_to_bibtex,
    export_bibtex,
    import_bibtex,
    sync_library,
)


def _seed_index(workspace: Path, entries: list[dict]) -> None:
    papers = workspace / "papers"
    papers.mkdir(parents=True, exist_ok=True)
    now = "2024-01-01T00:00:00+00:00"
    (papers / "literature_index.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "created_at": now,
                "updated_at": now,
                "entries": entries,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_enrich_metadata_fills_gaps(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    note = workspace / "papers" / "note.md"
    note.parent.mkdir(parents=True)
    note.write_text("# stub\n", encoding="utf-8")
    _seed_index(
        workspace,
        [
            {
                "title": "stub.pdf",
                "journal": None,
                "doi": "10.1000/example",
                "abstract": None,
                "file_path": "papers/note.md",
                "file_type": "markdown",
                "source": "user_upload",
                "saved_at": "2024-01-01T00:00:00+00:00",
                "extra_fields": {},
            }
        ],
    )
    record = BibliographicRecord(
        identifier="10.1000/example",
        id_type="doi",
        title="Real Title",
        authors=("Ada Lovelace",),
        year=2024,
        venue="Journal of Tests",
        doi="10.1000/example",
        url="https://doi.org/10.1000/example",
        abstract="Hello abstract",
        cite_key="lovelace2024real",
    )
    with patch(
        "agentsociety2.skills.literature.library_ops.lookup_identifier",
        return_value=record,
    ):
        stats = enrich_metadata(workspace)

    assert stats.metadata_updated == 1
    data = json.loads(
        (workspace / "papers" / "literature_index.json").read_text(encoding="utf-8")
    )
    entry = data["entries"][0]
    assert entry["title"] == "Real Title"
    assert entry["journal"] == "Journal of Tests"
    assert entry["abstract"] == "Hello abstract"
    assert entry["extra_fields"]["authors"] == ["Ada Lovelace"]
    assert entry["extra_fields"]["year"] == 2024


def test_enrich_metadata_scans_attached_pdf(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    note = workspace / "papers" / "note.md"
    pdf = workspace / "papers" / "full_texts" / "mystery.pdf"
    note.parent.mkdir(parents=True)
    pdf.parent.mkdir(parents=True)
    note.write_text("# stub\n", encoding="utf-8")
    pdf.write_bytes(b"%PDF-1.4\ndoi:10.1000/from-pdf\n")
    _seed_index(
        workspace,
        [
            {
                "title": "mystery.pdf",
                "journal": None,
                "doi": None,
                "abstract": None,
                "file_path": "papers/note.md",
                "file_type": "markdown",
                "source": "user_upload",
                "saved_at": "2024-01-01T00:00:00+00:00",
                "extra_fields": {
                    "original_name": "mystery.pdf",
                    "full_text": {
                        "file_path": "papers/full_texts/mystery.pdf",
                        "status": "downloaded",
                        "source": "user_upload",
                    },
                },
            }
        ],
    )
    record = BibliographicRecord(
        identifier="10.1000/from-pdf",
        id_type="doi",
        title="Scanned Title",
        authors=("Grace Hopper",),
        year=2023,
        venue="CACM",
        doi="10.1000/from-pdf",
        url="https://doi.org/10.1000/from-pdf",
        abstract="Scanned abstract",
        cite_key="hopper2023scanned",
    )
    with patch(
        "agentsociety2.skills.literature.library_ops.lookup_identifier",
        return_value=record,
    ) as mocked:
        stats = enrich_metadata(workspace)

    mocked.assert_called_once_with("10.1000/from-pdf", timeout=20.0)
    assert stats.metadata_updated == 1
    data = json.loads(
        (workspace / "papers" / "literature_index.json").read_text(encoding="utf-8")
    )
    entry = data["entries"][0]
    assert entry["title"] == "Scanned Title"
    assert entry["doi"] == "10.1000/from-pdf"
    assert entry["extra_fields"]["authors"] == ["Grace Hopper"]


def test_enrich_metadata_rejects_pdf_path_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    outside = tmp_path / "secret.pdf"
    outside.write_bytes(b"%PDF-1.4\ndoi:10.1000/leaked\n")
    note = workspace / "papers" / "note.md"
    note.parent.mkdir(parents=True)
    note.write_text("# stub\n", encoding="utf-8")
    _seed_index(
        workspace,
        [
            {
                "title": "escape.pdf",
                "journal": None,
                "doi": None,
                "abstract": None,
                "file_path": "papers/note.md",
                "file_type": "markdown",
                "source": "user_upload",
                "saved_at": "2024-01-01T00:00:00+00:00",
                "extra_fields": {
                    "full_text": {
                        "file_path": "../secret.pdf",
                        "status": "downloaded",
                        "source": "user_upload",
                    },
                },
            }
        ],
    )
    with (
        patch(
            "agentsociety2.skills.literature.library_ops.lookup_identifier"
        ) as mocked,
        patch(
            "agentsociety2.skills.literature.library_ops.extract_identifier_from_pdf"
        ) as scanned,
    ):
        stats = enrich_metadata(workspace)

    mocked.assert_not_called()
    scanned.assert_not_called()
    assert stats.metadata_skipped == 1


def test_sync_calls_pdf_download(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    note = workspace / "papers" / "note.md"
    note.parent.mkdir(parents=True)
    note.write_text("# t\n", encoding="utf-8")
    _seed_index(
        workspace,
        [
            {
                "title": "Complete Paper",
                "journal": "J",
                "doi": "10.1000/complete",
                "abstract": "A",
                "file_path": "papers/note.md",
                "file_type": "markdown",
                "source": "user_upload",
                "saved_at": "2024-01-01T00:00:00+00:00",
                "extra_fields": {"authors": ["A B"], "year": 2020},
            }
        ],
    )
    with patch(
        "agentsociety2.skills.literature.library_ops.download_entry_pdf",
        return_value="downloaded",
    ) as mocked:
        stats = sync_library(workspace)
    assert mocked.called
    assert stats.pdf_downloaded == 1
    assert stats.metadata_skipped == 1


def test_export_and_import_bibtex(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    note = workspace / "papers" / "note.md"
    note.parent.mkdir(parents=True)
    note.write_text("# n\n", encoding="utf-8")
    _seed_index(
        workspace,
        [
            {
                "title": "Deep Learning",
                "journal": "Nature",
                "doi": "10.1038/nature14539",
                "abstract": "Abs",
                "file_path": "papers/note.md",
                "file_type": "markdown",
                "source": "literature_search",
                "saved_at": "2024-01-01T00:00:00+00:00",
                "extra_fields": {"authors": ["Yann LeCun"], "year": 2015},
            }
        ],
    )
    exported = export_bibtex(workspace)
    assert exported["count"] == 1
    assert (workspace / "papers" / "library.bib").is_file()
    bib = entry_to_bibtex(
        json.loads(
            (workspace / "papers" / "literature_index.json").read_text(encoding="utf-8")
        )["entries"][0]
    )
    assert "@article{" in bib
    assert "Deep Learning" in bib

    other = tmp_path / "ws2"
    other.mkdir()
    bib_file = tmp_path / "sample.bib"
    bib_file.write_text(
        "@article{smith2020test,\n"
        "  title = {Imported Paper},\n"
        "  author = {Alice Smith and Bob Jones},\n"
        "  year = {2020},\n"
        "  journal = {Test Journal},\n"
        "  doi = {10.1000/import},\n"
        "}\n",
        encoding="utf-8",
    )
    result = import_bibtex(other, bib_file)
    assert result["added"] == 1
    data = json.loads(
        (other / "papers" / "literature_index.json").read_text(encoding="utf-8")
    )
    assert data["entries"][0]["title"] == "Imported Paper"
    assert data["entries"][0]["doi"] == "10.1000/import"
