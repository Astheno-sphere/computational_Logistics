#!/usr/bin/env python3
"""The five-page proposal -> docs/proposal/proposal.pdf (and proposal-5p.html), figures drawn from study.json.

    python docs/proposal/build_pdf.py
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent


def main():
    html = (HERE / "src" / "five-page.html").read_text(encoding="utf-8")
    html = html.replace("/*STUDY*/null", (HERE / "study.json").read_text(encoding="utf-8"))
    out = HERE / "proposal-5p.html"
    out.write_text(html, encoding="utf-8")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
        pg = b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(out.as_uri())
        pg.wait_for_timeout(1500)
        if errors:
            raise SystemExit(f"page errors: {errors}")
        pg.pdf(path=str(HERE / "proposal.pdf"), format="A4", print_background=True, prefer_css_page_size=True)
        b.close()
    from pypdf import PdfReader
    print("pages", len(PdfReader(str(HERE / "proposal.pdf")).pages))


if __name__ == "__main__":
    main()
