"""Эскиз к задаче «полоса поликарбоната по правому ряду + усиление правых стропил рам 1 и 3».

Выход: tasks/side_panel/drawings/eskiz.html и eskiz.pdf. Размеры — из расчётной модели (calc/model.py).
Это эскиз-предложение для обсуждения, не рабочий чертёж.
"""
from __future__ import annotations

import glob
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "calc"))
import model as M                                  # noqa: E402
from nodes_drawing import COL, NODE_CSS, Svg        # noqa: E402

OUT = Path(__file__).resolve().parent / "drawings"
Z_BOT, Z_TOP = 2070.0, 3040.0                      # полоса: низ пояса фермы … верх колонн, мм
GE_D = 175.0


def mark(s, u, z, n):
    p = s.P(u, z)
    s.items.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{13 * s.k:.0f}" fill="#1e3a8a"/>'
                   f'<text x="{p[0]:.1f}" y="{p[1] + 6 * s.k:.1f}" text-anchor="middle" '
                   f'style="fill:#fff;font-size:{16 * s.k:.0f}px;font-weight:700">{n}</text>')


def row_view():
    """Вид на правый ряд колонн снаружи (с +x): горизонталь — вдоль ряда (y), мм."""
    y0, y1 = M.Y_MIN * 1000, M.Y_MAX * 1000
    s = Svg(y0 - 250, y1 + 250, 1850, 3450, k=4.0, pad=30)
    tg = M.shop_truss_geom(0.06, 0.06, 0.06)
    zpt = tg["plate_top"] * 1000
    # полоса поликарбоната
    s.rect(y0, Z_BOT, y1, Z_TOP, "#475569", "#1f2937", 0.28, 2.5)
    # колонны П1, П3 (грань 60 вдоль ряда)
    for yc in (0.0, M.BAY * 1000):
        s.rect(yc - 30, 1850, yc + 30, 3043, COL["col"], "#0008", 0.9)
    # боковая ферма: пояс, раскосы, столик, стойка средней рамы
    s.rect(30, 2070, M.BAY * 1000 - 30, 2130, COL["sb"], "#0008", 0.9)
    ym = M.BAY * 500
    for sg in (-1, 1):
        yc = ym + sg * ym
        s.poly([(yc - sg * 30, 2130), (yc - sg * 30 - sg * 170, 2130), (ym, zpt - 8), (ym + sg * 0, zpt - 8)],
               COL["sd"], "#0008", 0.9)
    s.rect(ym - 185, zpt - 8, ym + 185, zpt, COL["plate"], "#000a", 1)
    s.rect(ym - 30, zpt, ym + 30, 3043, COL["stub"], "#0008", 0.9)
    # стропила над рядом (в сечении) и кровля
    for fy in (0.0, ym, M.BAY * 1000):
        s.rect(fy - 30, 3049, fy + 30, 3151, COL["raf"], "#0008", 0.9)
    s.rect(y0, 3151, y1, 3186, "#db2777", "none", 0.25)
    s.line(y0, 3200, y1, 3200, "ld")
    for ye in (y0 + GE_D, y1 - GE_D):
        s.rect(ye - 15, 3101, ye + 15, 3151, "#ea580c", "#0008", 0.9)
    # обрешётка полосы (предложение): верхняя рейка 40×20 на +3.0, нижние консольные рейки 40×20,
    # прокладка 20×20 по поясу между колоннами, торцевые стойки 20×20 к обвязке
    rail = "#0f766e"
    s.rect(y0, 2990, y1, 3010, rail, "#0008", 0.9)
    for a, b in ((y0, -30), (M.BAY * 1000 + 30, y1)):
        s.rect(a, 2070, b, 2090, rail, "#0008", 0.9)
    s.rect(30, 2070, M.BAY * 1000 - 30, 2090, "#14b8a6", "#0008", 0.9)
    for ye in (y0 + GE_D, y1 - GE_D):
        s.rect(ye - 10, 2070, ye + 10, 3101, rail, "#0008", 0.9)
    # размеры
    s.dim_h(y0, y1, 1900, f"полоса на всю длину кровли {(y1 - y0) / 1000:.2f} м", off=0)
    s.dim_h(y0, 0, 3330, f"{-y0:.0f}", off=0)
    s.dim_h(0, M.BAY * 1000, 3330, f"{M.BAY * 1000:.0f} (оси П1–П3)", off=0)
    s.dim_h(M.BAY * 1000, y1, 3330, f"{y1 - M.BAY * 1000:.0f}", off=0)
    s.dim_v(y1 + 120, Z_BOT, Z_TOP, f"{Z_TOP - Z_BOT:.0f}", off=0, anchor="start")
    s.text(y0 - 230, Z_TOP + 15, "+3.040", "dt")
    s.text(y0 - 230, Z_BOT - 40, "+2.070", "dt")
    s.text(-60, 1880, "П1", "lb", "end")
    s.text(M.BAY * 1000 + 60, 1880, "П3", "lb")
    for n, (u, z) in enumerate([(y0 + 700, 2550), (ym - 900, 3000), (ym + 1100, 2080), (y0 + 600, 2080),
                                (y0 + GE_D, 2600), (ym, 3100), (y1 - GE_D, 3126), (ym + 600, 2500)], 1):
        mark(s, u, z, n)
    return s.svg("вид на правый ряд")


ROW_LEGEND = [
    "полоса сотового поликарбоната 8 мм, графит, +2.070…+3.040 (0.97 м), на всю длину кровли; канавки вертикально",
    "верхняя рейка 40×20×2 на +3.0: между колоннами и стойкой средней рамы — два пролёта по 2.3 м; за колоннами — консоли",
    "прокладка 20×20 по наружной грани нижнего пояса фермы (выводит лист в плоскость наружных граней колонн)",
    "нижние консольные рейки 40×20×2 за колоннами (≈ 1.15 м)",
    "торцевые стойки 20×20 в 175 мм от кромок кровли, подвешены к торцевой обвязке 50×30",
    "стропила рам 1–3 над рядом (сечение); щель ≈ 15 см до кровли оставляется открытой",
    "торцевая обвязка 50×30 (в 175 мм от передней и задней кромки)",
    "боковая ферма: пояс 60×60×2, раскосы, столик +2.930, стойка средней рамы — лист проходит снаружи",
]


def rafter_view():
    """Правая часть рамы 1 (или 3) в плоскости рамы: узел А над П1, стропило, затяжка, подкос фермы, усиление."""
    t, c = M.TAN, M.COS
    s = Svg(3350, 6450, 2700, 3700, k=2.6, pad=30)
    X = M.SPAN * 1000

    def zr(x):                      # ось стропила, мм
        return M.z_rafter(x / 1000) * 1000
    h = 100 / c
    xs = [3350, X_R := M.X_RIDGE * 1000]
    pts_top = [(x, zr(x) + h / 2) for x in (3350, X, 6350)]
    pts_bot = [(x, zr(x) - h / 2) for x in (6350, X, 3350)]
    s.poly(pts_top + pts_bot, COL["raf"], "#0008", 0.9)
    # колонна, опорная пластина
    s.rect(X - 50, 2700, X + 50, 3043, COL["col"], "#0008", 0.9)
    s.poly([(X - 70, 3043 - 70 * t * 0), (X + 70, 3043), (X + 70, zr(X + 70) - h / 2), (X - 70, zr(X - 70) - h / 2)],
           COL["plate"], "#000a", 1)
    # затяжка
    s.rect(3350, 2970, X - 50, 3030, COL["tie"], "#0008", 0.9)
    # фасонка узла А (от наружной грани колонны до 200 мм внутрь, низ 2920, верх — ось стропила)
    g1, g2 = X + 50, X - 200
    s.poly([(g1, 2920), (g2, 2920), (g2, zr(g2)), (g1, zr(g1))], "#9ca3af", "#111", 0.55, 1.2)
    # подкос фермы к стропилу в x = 3720 и подвеска у конька — схематично
    xk, xb = M.X_RIDGE * 1000 + 1000, M.X_RIDGE * 1000          # подкос: от подвески у конька (на затяжке) к стропилу
    zk = zr(xk) - h / 2
    zl = 3030 + (zk - 3030) * (3350 - xb) / (xk - xb)
    s.poly([(xk - 20, zk), (xk + 20, zk), (3350 + 20, zl), (3350 - 20, zl)], COL["kp"], "#0008", 0.9)
    # усиление: обрезок 80×40×2.5 плашмя (40 по высоте) под низом стропила, от конца фасонок к подкосу
    a, b = X - 210, 3720 + 60
    s.poly([(a, zr(a) - h / 2), (b, zr(b) - h / 2), (b, zr(b) - h / 2 - 40 / c), (a, zr(a) - h / 2 - 40 / c)],
           "#f59e0b", "#7c2d12", 0.95, 1.5)
    s.seam([(a, zr(a) - h / 2), (b, zr(b) - h / 2)], w=2.5)
    s.line(X, 2700, X, 3420)
    s.text(X + 10, 3405, "ось колонны П1", "dt")
    s.dim_h(b, a, 2870, f"≈ {(a - b) / c / 1000:.2f} м по скату", off=0)
    s.dim_h(a, X, 2780, f"{X - a:.0f}", off=0)
    for n, (u, z) in enumerate([((a + b) / 2, zr((a + b) / 2) - h / 2 - 20), (X - 75, 2950), (X - 600, 3000),
                                (X + 45, 3110), (xk - 120, zr(xk - 120) - h / 2 - 60), (X, 2850)], 1):
        mark(s, u, z, n)
    return s.svg("усиление правого стропила")


RAF_LEGEND = [
    "УСИЛЕНИЕ (предложение): обрезок трубы 80×40×2.5 плашмя под низом стропила, L ≈ 1.5 м по скату, от конца фасонок "
    "(≈ 0.21 м от оси колонны) почти до подкоса фермы; швы k=2.5 прерывистые 50/150, концы сплошные 100 мм; торцы заглушить",
    "фасонки узла А t=5 (по обе стороны), до 200 мм от наружной грани колонны внутрь пролёта",
    "затяжка 60×60×2 на +3.000 (между низом стропила и затяжкой у колонны ≈ 20 мм — трубе не пройти)",
    "опорная пластина 140×60×6 на колонне; стропило 100×60×3 (уже смонтировано)",
    "подкос фермы 20×20 (от подвески у конька к стропилу в x ≈ 3.72 м) — конец участка 3.72–5.45, где перегруз 1.08",
    "колонна П1 100×60×4 (уже забетонирована)",
]


def build():
    leg1 = "".join(f"<li>{x}</li>" for x in ROW_LEGEND)
    leg2 = "".join(f"<li>{x}</li>" for x in RAF_LEGEND)
    css = NODE_CSS + "ol.l{font-size:14px;columns:2;column-gap:28px;padding-left:22px}ol.l li{break-inside:avoid;margin:3px 0}"
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Полоса и усиление — эскиз</title>
<style>{css}</style></head><body><main>
<h1>Эскиз задачи: полоса поликарбоната по правому ряду и усиление стропил</h1>
<p class="sub">Предложение для обсуждения (не рабочий чертёж). Размеры — по расчётной модели.</p>
<h2>1. Вид на правый ряд колонн снаружи</h2>
<div class="card">{row_view()}<ol class="l">{leg1}</ol></div>
<h2 class="pb">2. Правое стропило рамы 1 (рама 3 — так же), вид в плоскости рамы</h2>
<div class="card">{rafter_view()}<ol class="l">{leg2}</ol></div>
</main></body></html>"""


def main():
    OUT.mkdir(exist_ok=True)
    html = OUT / "eskiz.html"
    html.write_text(build(), encoding="utf-8")
    from playwright.sync_api import sync_playwright
    exe = glob.glob("/opt/pw-browsers/chromium*/chrome-linux*/chrome")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe[0]) if exe else p.chromium.launch()
        pg = b.new_page(viewport={"width": 1100, "height": 1400}, color_scheme="light")
        pg.goto(html.as_uri())
        pg.pdf(path=str(OUT / "eskiz.pdf"), format="A4", print_background=True, scale=0.72,
               margin={"top": "12mm", "bottom": "14mm", "left": "10mm", "right": "10mm"})
        b.close()
    print(OUT / "eskiz.pdf")


if __name__ == "__main__":
    main()
