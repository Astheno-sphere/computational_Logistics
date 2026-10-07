"""Unit tests for literature ingest (local file + identifier → index)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agentsociety2.skills.literature.doi_lookup import BibliographicRecord
from agentsociety2.skills.literature.ingest import (
    add_from_identifier,
    add_from_local_file,
    load_or_create_index,
)


def test_add_from_local_pdf_uses_note_and_full_texts(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    src = tmp_path / "Outside Paper.pdf"
    src.write_bytes(b"%PDF-1.4 mock")

    result = add_from_local_file(workspace, src)
    assert result.added is True
    assert result.file_path.endswith(".md")
    assert (workspace / result.file_path).is_file()

    _, index = load_or_create_index(workspace)
    entry = index.entries[0]
    assert entry.file_type == "markdown"
    assert entry.source == "user_upload"
    assert entry.extra_fields is not None
    pdf_rel = entry.extra_fields["full_text"]["file_path"]
    assert pdf_rel.startswith("papers/full_texts/")
    assert (workspace / pdf_rel).is_file()


def test_dnd_pdf_under_papers_is_relocated(tmp_path: Path) -> None:
    """Side-bar drop copies into papers/ first; ingest should move PDF to full_texts/."""
    workspace = tmp_path / "ws"
    papers = workspace / "papers"
    papers.mkdir(parents=True)
    dropped = papers / "Dropped.pdf"
    dropped.write_bytes(b"%PDF-1.4")

    result = add_from_local_file(workspace, dropped, title="Dropped")
    assert result.added is True
    assert not dropped.exists()
    _, index = load_or_create_index(workspace)
    pdf_rel = index.entries[0].extra_fields["full_text"]["file_path"]
    assert pdf_rel.startswith("papers/full_texts/")
    assert (workspace / pdf_rel).is_file()


def test_add_from_local_pdf_scans_doi_and_looks_up(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    src = tmp_path / "mystery.pdf"
    src.write_bytes(b"%PDF-1.4\ndoi:10.1000/example\n")
    record = BibliographicRecord(
        identifier="10.1000/example",
        id_type="doi",
        title="Resolved From PDF",
        authors=("Ada Lovelace",),
        year=2024,
        venue="Journal of Tests",
        doi="10.1000/example",
        url="https://doi.org/10.1000/example",
        abstract="From lookup",
        cite_key="lovelace2024resolved",
    )

    with patch(
        "agentsociety2.skills.literature.ingest.lookup_identifier",
        return_value=record,
    ):
        result = add_from_local_file(workspace, src)

    assert result.added is True
    assert result.doi == "10.1000/example"
    _, index = load_or_create_index(workspace)
    entry = index.entries[0]
    assert entry.title == "Resolved From PDF"
    assert entry.journal == "Journal of Tests"
    assert entry.abstract == "From lookup"
    assert entry.extra_fields["ingest"] == "local_file+doi_lookup"
    assert entry.extra_fields["full_text"]["status"] == "downloaded"


def test_add_from_local_markdown(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    note = tmp_path / "My Note.md"
    note.write_text("# Hello\n", encoding="utf-8")

    result = add_from_local_file(workspace, note, title="My Note")
    assert result.added is True
    assert result.file_path.startswith("papers/")
    assert result.file_path.endswith(".md")
    _, index = load_or_create_index(workspace)
    assert index.entries[0].title == "My Note"


def test_add_from_local_file_duplicate(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    papers = workspace / "papers"
    papers.mkdir(parents=True)
    note = papers / "note.md"
    note.write_text("# Same Title\n", encoding="utf-8")

    first = add_from_local_file(workspace, note, title="Same Title")
    second = add_from_local_file(workspace, note, title="Same Title")
    assert first.added is True
    assert second.added is False
    assert second.duplicate is True
    _, index = load_or_create_index(workspace)
    assert len(index.entries) == 1


def test_add_from_identifier_writes_note(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    record = BibliographicRecord(
        identifier="10.1000/example",
        id_type="doi",
        title="Example Paper",
        authors=("Ada Lovelace",),
        year=2024,
        venue="Journal of Tests",
        doi="10.1000/example",
        url="https://doi.org/10.1000/example",
        abstract="An abstract.",
        cite_key="lovelace2024example",
    )

    with patch(
        "agentsociety2.skills.literature.ingest.lookup_identifier",
        return_value=record,
    ):
        result = add_from_identifier(workspace, "10.1000/example")

    assert result.added is True
    assert result.doi == "10.1000/example"
    note = workspace / result.file_path
    assert note.is_file()
    text = note.read_text(encoding="utf-8")
    assert "# Example Paper" in text
    assert "10.1000/example" in text

    _, index = load_or_create_index(workspace)
    entry = index.entries[0]
    assert entry.journal == "Journal of Tests"
    assert entry.extra_fields is not None
    assert entry.extra_fields["authors"] == ["Ada Lovelace"]
    assert entry.extra_fields["year"] == 2024


def test_add_from_identifier_duplicate_by_doi(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    record = BibliographicRecord(
        identifier="10.1000/example",
        id_type="doi",
        title="Example Paper",
        authors=("Ada Lovelace",),
        year=2024,
        venue=None,
        doi="10.1000/example",
        url="https://doi.org/10.1000/example",
        abstract=None,
        cite_key="lovelace2024example",
    )
    with patch(
        "agentsociety2.skills.literature.ingest.lookup_identifier",
        return_value=record,
    ):
        assert add_from_identifier(workspace, "10.1000/example").added is True
        again = add_from_identifier(workspace, "https://doi.org/10.1000/example")
    assert again.duplicate is True
    _, index = load_or_create_index(workspace)
    assert len(index.entries) == 1


def test_add_from_identifier_lookup_failure(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    with (
        patch(
            "agentsociety2.skills.literature.ingest.lookup_identifier",
            side_effect=ValueError("Not a DOI: 'nope'"),
        ),
        pytest.raises(ValueError, match="Not a DOI"),
    ):
        add_from_identifier(workspace, "nope")
    _, index = load_or_create_index(workspace)
    assert index.entries == []
