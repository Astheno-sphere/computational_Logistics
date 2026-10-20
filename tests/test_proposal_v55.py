"""Guards for the v5.5 proposal text (docs/proposal/src/proposal-v55.html): house rules, citations, open items."""
import html
import re

from conftest import ROOT

SRC = (ROOT / "docs" / "proposal" / "src" / "proposal-v55.html").read_text(encoding="utf-8")


def prose(s):
    s = re.sub(r"<style.*?</style>|<script.*?</script>|<!--.*?-->", " ", s, flags=re.S)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)))


def test_prose_has_no_em_dashes():
    assert "—" not in prose(SRC)


def test_every_cited_source_is_listed_and_every_listed_source_is_cited():
    text = prose(SRC)
    body, refs = text.split("06 · REFERENCES")
    refs = refs.split("S · FURTHER PLATES")[0]
    cited = {k for m in re.findall(r"\[([a-z][a-z0-9, ]*)\]", body) for k in re.split(r"[, ]+", m) if k and k not in ("to",)}
    cited -= {"confirm"}
    listed = set(re.findall(r"\[([a-z0-9]+)\]", refs))
    assert cited <= listed, sorted(cited - listed)
    assert listed <= cited, sorted(listed - cited)


def test_open_items_are_left_open():
    text = prose(SRC)
    assert "[N1]" in text and "[to confirm" in text
