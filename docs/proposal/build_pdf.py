#!/usr/bin/env python3
"""Print PDFs from the built HTML: the five-page proposal on A4 (proposal.pdf) and the portfolio on A3
(portfolio.pdf). Full bleed in the plate colours, name and page number in the footer. Run build.py first.

    python docs/proposal/build.py && python docs/proposal/build_pdf.py
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
FOOT = ('<div style="width:100%;font:7px Roboto,Arial,sans-serif;color:#A8958A;letter-spacing:.06em;'
        'padding:0 15mm;display:flex;justify-content:space-between">'
        '<span>ARSHAD AKHTAR ABBASIA · THE PATH TO 2050 · TRANSPLAN, MOLDE UNIVERSITY COLLEGE</span>'
        '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')


def render(b, html, pdf, fmt):
    pg = b.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto((HERE / html).as_uri(), wait_until="networkidle")
    pg.wait_for_timeout(800)
    assert not errors, errors
    pg.pdf(path=str(HERE / pdf), format=fmt, print_background=True, prefer_css_page_size=True,
           display_header_footer=True, header_template="<span></span>", footer_template=FOOT)
    pg.close()
    print("wrote", HERE / pdf)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
        render(b, "proposal-5p.html", "proposal.pdf", "A4")
        render(b, "portfolio.html", "portfolio.pdf", "A3")
        b.close()


if __name__ == "__main__":
    main()
