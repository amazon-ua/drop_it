"""output/otvet_ispolnitelyu.md → output/объяснение.pdf (ответ исполнителю, A4)."""
import glob
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "output"

CSS = """
@page{size:A4;margin:13mm 15mm 15mm 15mm}
body{font-family:"DejaVu Sans",system-ui,sans-serif;font-size:10pt;line-height:1.36;color:#111}
h2{font-size:14pt;margin:18px 0 8px;padding-bottom:3px;border-bottom:1.5px solid #3b0764;color:#1e1b4b}
h2:first-child{margin-top:0}
p{margin:6px 0}
ul,ol{margin:4px 0 8px;padding-left:22px}
li{margin:2px 0}
table{border-collapse:collapse;margin:6px 0 10px;width:100%}
th,td{border:1px solid #bbb;padding:4px 7px;vertical-align:top}
th{background:#f1f0f7;text-align:left}
td:not(:first-child){white-space:nowrap}
code{font-family:inherit;font-weight:600}
tr,li{break-inside:avoid}
h2{break-after:avoid}
"""


def main():
    md = (OUT / "otvet_ispolnitelyu.md").read_text(encoding="utf-8")
    body = markdown.markdown(md, extensions=["tables"])
    html = f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{body}</body></html>'
    src = OUT / "_obyasnenie.html"
    src.write_text(html, encoding="utf-8")
    dst = OUT / "объяснение.pdf"
    exe = glob.glob("/opt/pw-browsers/chromium*/chrome-linux*/chrome")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe[0]) if exe else p.chromium.launch()
        pg = b.new_page()
        pg.goto(src.as_uri())
        pg.pdf(path=str(dst), format="A4", print_background=True, prefer_css_page_size=True,
               display_header_footer=True, header_template="<span></span>",
               footer_template='<div style="font-size:8px;width:100%;text-align:center;color:#666">'
                               '<span class="pageNumber"></span> / <span class="totalPages"></span></div>')
        b.close()
    src.unlink()
    print(dst)


if __name__ == "__main__":
    main()
