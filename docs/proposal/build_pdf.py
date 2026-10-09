#!/usr/bin/env python3
"""The five-page proposal as a print PDF: docs/proposal/proposal-5p.html -> docs/proposal/proposal.pdf.

A4, full bleed in the plate colours, name and page number in the footer. Run build.py first.

    python docs/proposal/build.py && python docs/proposal/build_pdf.py
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
FOOT = ('<div style="width:100%;font:7px Roboto,Arial,sans-serif;color:#A8958A;letter-spacing:.06em;'
        'padding:0 15mm;display:flex;justify-content:space-between">'
        '<span>ARSHAD AKHTAR ABBASIA · THE PATH TO 2050 · TRANSPLAN, MOLDE UNIVERSITY COLLEGE</span>'
        '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
        pg = b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto((HERE / "proposal-5p.html").as_uri(), wait_until="networkidle")
        pg.wait_for_timeout(800)
        assert not errors, errors
        pg.pdf(path=str(HERE / "proposal.pdf"), format="A4", print_background=True, prefer_css_page_size=True,
               display_header_footer=True, header_template="<span></span>", footer_template=FOOT)
        b.close()
    print("wrote", HERE / "proposal.pdf")


if __name__ == "__main__":
    main()
