"""PDF из HTML-документов (Chromium через Playwright)."""
import glob
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent / "output"


def to_pdf(name):
    src = ROOT / f"{name}.html"
    dst = ROOT / f"{name}.pdf"
    exe = glob.glob("/opt/pw-browsers/chromium*/chrome-linux*/chrome")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe[0]) if exe else p.chromium.launch()
        pg = b.new_page(viewport={"width": 1100, "height": 1400}, color_scheme="light")
        pg.goto(src.as_uri())
        pg.wait_for_timeout(500)
        pg.pdf(path=str(dst), format="A4", print_background=True, scale=0.72,
               margin={"top": "12mm", "bottom": "14mm", "left": "10mm", "right": "10mm"},
               display_header_footer=True,
               header_template="<span></span>",
               footer_template='<div style="font-size:8px;width:100%;text-align:center;color:#666">'
                               '<span class="pageNumber"></span> / <span class="totalPages"></span></div>')
        b.close()
    return dst


if __name__ == "__main__":
    for n in (sys.argv[1:] or ["navis_optimized"]):
        print(to_pdf(n))
