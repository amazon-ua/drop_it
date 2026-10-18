"""Отдельный документ: полоса сотового поликарбоната по правому ряду колонн и раскосы ферм у опор
→ output/polosa.html (+ PDF: python3 make_pdf.py polosa).

Полоса — графит 8 мм, от верха колонн (+3.040) до низа нижнего пояса боковой фермы (+2.070), на всю длину кровли;
лист в плоскости наружных граней колонн. Обрешётка: верхние рейки 40×20×2 на +3.000 (между колоннами — два пролёта,
торцы к фасонкам узлов А и Б; за колоннами — консоли к фасонкам А), нижняя прокладка 20×20 на поясе фермы, нижние
рейки-консоли 40×20×2 к колоннам, торцевые стойки 20×20 к торцевой обвязке. Ветер на полосу перегружал правые
стропила — вместо усиления в каждой половине рам добавлен раскос 20×20×2 (DECISIONS, п. 7i). Швы 15–18.
"""
from __future__ import annotations

import html
import json
import math

import checks as C
import model as M
from nodes_drawing import COL, NODE_CSS, OUT, SEAM, Svg
from report_data import sec_by_name

# ---------------- геометрия полосы (мм) ----------------
# y — вдоль ряда от оси рамы 1; x — от оси правого ряда колонн наружу; z — отметка
Z_BOT, Z_TOP = 2070.0, 3040.0          # лист: низ (низ пояса фермы) … верх (верх колонн)
SH_X, SH_T = 50.0, 8.0                 # лист — по наружной грани колонн, толщина 8
TR = dict(z1=2990.0, z2=3010.0, x1=10.0, x2=50.0)      # верхняя рейка 40×20 (40 — поперёк листа)
BR = dict(z1=2110.0, z2=2130.0, x1=10.0, x2=50.0)      # нижние рейки-консоли 40×20 (верх — по верху пояса)
SP = dict(z1=2110.0, z2=2130.0, x1=30.0, x2=50.0)      # прокладка 20×20 по наружной грани пояса
COL_HB, COL_HH = 30.0, 50.0            # колонна 100×60: полуширина вдоль ряда / в плоскости рамы
STUB_H = 30.0                          # стойка-вставка 60×60
GT = 5.0                               # фасонки узлов А и Б
POST_D = 175.0                         # торцевые стойки — в 175 мм от кромок (по торцевой обвязке)
SCREW_STEP = 350.0                     # шаг термошайб
EDGE_MIN = 40.0                        # саморез — не ближе 40 мм к кромке листа
SHEET_W, SHEET_L = 2100.0, 6000.0      # лист сотового поликарбоната 2.1 × 6 м (канавки вдоль 6 м)
CUT_KERF = 0.003                       # пропил, м


def Y0():
    return M.Y_MIN * 1000


def Y1():
    return M.Y_MAX * 1000


def BAYmm():
    return M.BAY * 1000


def z_ge_bot(raf, ge):
    """Низ торцевой обвязки (на ребро, под обрешёткой) над осью правого ряда, мм."""
    return (M.z_rafter(M.SPAN) + raf.h / 2 / M.COS - ge.h / M.COS) * 1000


def parts(raf, ge):
    """Детали обрешётки полосы: (обозначение, сечение, длина, мм, кол-во, примечание)."""
    y0, y1, B = Y0(), Y1(), BAYmm()
    g = COL_HB + GT                                         # грань фасонки от оси колонны / стойки
    post = z_ge_bot(raf, ge) - SP["z1"]
    return [
        ("Р1", "40×20×2", B / 2 - 2 * g, 2, "верхняя рейка между колонной и стойкой рамы 2, торцы прямые"),
        ("Р2", "40×20×2", -g - y0, 1, "верхняя рейка-консоль за П1 (к передней кромке)"),
        ("Р3", "40×20×2", y1 - B - g, 1, "верхняя рейка-консоль за П3 (к задней кромке)"),
        ("Р4", "40×20×2", -COL_HB - y0, 1, "нижняя рейка-консоль за П1"),
        ("Р5", "40×20×2", y1 - B - COL_HB, 1, "нижняя рейка-консоль за П3"),
        ("Пр", "20×20×2", B - 2 * COL_HB, 1, "прокладка по наружной грани нижнего пояса правой фермы, между гранями колонн"),
        ("С1", "20×20×2", post, 2, f"торцевая стойка в {POST_D:.0f} мм от кромки; верх — рез {math.degrees(M.SLOPE):.0f}° "
                                   "по низу торцевой обвязки"),
    ]


def ew_geom(fd, raf, tie):
    """Раскос фермы у опоры: углы, длина по оси между гранями, положение пятен."""
    dxt, dxr = fd["panel"]["ext_web"][0][1], fd["panel"]["ext_web"][0][2]
    run = dxr - dxt
    dz = M.z_rafter(M.SPAN - dxr) - M.Z_TIE
    beta = math.atan2(dz, run)
    gam = beta - M.SLOPE
    Lc = math.hypot(run, dz) - (tie.h / 2) / math.sin(beta) - (raf.h / 2) / math.sin(gam)
    foot_t = dxt + (tie.h / 2) / math.tan(beta)          # центр пятна на верху затяжки от оси колонны
    foot_r = (raf.h / 2) / math.tan(gam)                 # центр пятна на низу стропила: от узла по стропилу к колонне
    return dict(dxt=dxt, dxr=dxr, beta=beta, gam=gam, Lc=Lc, foot_t=foot_t, foot_r=foot_r,
                len_t=0.02 / math.sin(beta), len_r=0.02 / math.sin(gam))


# ---------------- расчёт ----------------
def calc(fd):
    L = M.Loads(Ch=0.70)
    w = L.W0 * L.gfm_wind * L.Ch * L.cp_panel          # расчётное, Па
    we = L.W0 * L.gfe_wind * L.Ch * L.cp_panel         # эксплуатационное (для прогибов, как в проекте)
    r40 = sec_by_name("40×20×2")
    zm = (TR["z1"] + TR["z2"]) / 2
    zb = (BR["z1"] + BR["z2"]) / 2
    mid = (zm + zb) / 2
    ht, hb = (Z_TOP - mid) / 1000, (mid - Z_BOT) / 1000     # грузовые полосы верхней и нижней линии крепления
    pr = {p[0]: p[2] / 1000 for p in parts(sec_by_name(fd["groups"]["raf"]), sec_by_name(fd["groups"]["ge"]))}
    rows = []

    def beam(name, q, qe, Lb, cant):
        Mx = q * Lb ** 2 / (2 if cant else 8)
        sig = Mx / r40.Wy
        f = qe * Lb ** 4 / (8 if cant else 384 / 5) / (C.E * r40.Iy)
        lim, n = C.defl_limit(2 * Lb if cant else Lb)
        rows.append((name, Lb, q, Mx, sig, sig / C.RY, f * 1000, lim * 1000, n))
    beam("Верхняя рейка Р1 между колонной и стойкой (пролёт, концы — шарнир, в запас)", w * ht, we * ht, pr["Р1"], False)
    beam("Верхняя рейка-консоль Р3 (без учёта торцевой стойки, в запас)", w * ht, we * ht, max(pr["Р2"], pr["Р3"]), True)
    beam("Нижняя рейка-консоль Р5 (без учёта торцевой стойки, в запас)", w * hb, we * hb, max(pr["Р4"], pr["Р5"]), True)
    area = (Y1() - Y0()) / 1000 * (Z_TOP - Z_BOT) / 1000
    span_sheet = (zm - zb) / 1000
    screw = w * ht * SCREW_STEP / 1000
    return dict(w=w, we=we, ht=ht, hb=hb, rows=rows, F=w * area, area=area, span_sheet=span_sheet, screw=screw,
                kg=w / 9.81)


# ---------------- чертежи ----------------
def mark(s, u, z, n):
    p = s.P(u, z)
    s.items.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{13 * s.k:.0f}" fill="#1e3a8a"/>'
                   f'<text x="{p[0]:.1f}" y="{p[1] + 6 * s.k:.1f}" text-anchor="middle" '
                   f'style="fill:#fff;font-size:{16 * s.k:.0f}px;font-weight:700">{n}</text>')


def washer(s, u, z, r=7.0):
    p = s.P(u, z)
    s.items.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{r * s.k:.1f}" fill="#e5e7eb" stroke="#111" '
                   f'stroke-width="{0.8 * s.k:.1f}"/>')


SHEET_FILL = "#475569"
RAIL = "#0f766e"
RAIL2 = "#14b8a6"


def kfit(W, frac=1.0):
    """Масштаб шрифтов: подпись ≈ 13 px при ширине карточки ≈ 1000·frac px."""
    return 0.72 * W / (1000 * frac)


def level(s, u, z, zt, t, left=False):
    """Отметка: короткая линия от уровня z к полке на высоте zt и текст."""
    k = s.k
    du = -60 * k if left else 60 * k
    a, b = s.P(u, z), s.P(u + du, zt)
    s.items.append(f'<polyline points="{a[0]:.1f},{a[1]:.1f} {b[0]:.1f},{b[1]:.1f}" class="ld"/>')
    s.text(u + du + (-6 * k if left else 6 * k), zt - 6 * k, t, "dt", "end" if left else "start")


def row_view(raf, ge):
    """Вид на правый ряд снаружи: лист (полупрозрачный), обрешётка, колонны, ферма."""
    y0, y1, B = Y0(), Y1(), BAYmm()
    W = (y1 - y0) + 1300
    s = Svg(y0 - 450, y1 + 850, 1640, 3560, k=kfit(W), pad=30)
    tg = M.shop_truss_geom(0.06, 0.06, 0.06)
    zpt = tg["plate_top"] * 1000
    zge = z_ge_bot(raf, ge)
    for yc in (0.0, B):
        s.rect(yc - COL_HB, 1700, yc + COL_HB, 3043, COL["col"], "#0008", 0.9)
    s.rect(COL_HB, 2070, B - COL_HB, 2130, COL["sb"], "#0008", 0.9)
    ym = B / 2
    for sg in (-1, 1):
        yc = ym + sg * ym
        s.poly([(yc - sg * COL_HB, 2130), (yc - sg * COL_HB - sg * 170, 2130), (ym, zpt - 8), (ym, zpt - 8)],
               COL["sd"], "#0008", 0.9)
    s.rect(ym - 185, zpt - 8, ym + 185, zpt, COL["plate"], "#000a", 1)
    s.rect(ym - STUB_H, zpt, ym + STUB_H, 3049, COL["stub"], "#0008", 0.9)
    for fy in (0.0, ym, B):
        hb = COL_HB if fy != ym else STUB_H
        s.rect(fy - 30, 3049, fy + 30, 3151, COL["raf"], "#0008", 0.9)
        s.rect(fy - hb - GT, 2920, fy - hb, 3100, "#9ca3af", "#111", 0.8, 0.8)
        s.rect(fy + hb, 2920, fy + hb + GT, 3100, "#9ca3af", "#111", 0.8, 0.8)
    s.rect(y0, 3151, y1, 3186, COL["lath"], "none", 0.25)
    s.rect(y0, 3186, y1, 3196, "#64748b", "none", 0.6)
    for ye in (y0 + POST_D, y1 - POST_D):
        s.rect(ye - 15, zge, ye + 15, 3151, COL["ge"], "#0008", 0.9)
        s.rect(ye - 10, SP["z1"], ye + 10, zge, RAIL2, "#0008", 0.9)
    g = COL_HB + GT
    for a, b in ((y0, -g), (g, ym - g), (ym + g, B - g), (B + g, y1)):
        s.rect(a, TR["z1"], b, TR["z2"], RAIL, "#0008", 0.9)
    for a, b in ((y0, -COL_HB), (B + COL_HB, y1)):
        s.rect(a, BR["z1"], b, BR["z2"], RAIL, "#0008", 0.9)
    s.rect(COL_HB, SP["z1"], B - COL_HB, SP["z2"], RAIL2, "#0008", 0.9)
    s.rect(y0, Z_BOT, y1, Z_TOP, SHEET_FILL, "#1f2937", 0.22, 2.5)
    for yj in joints():
        s.rect(yj - 10, Z_BOT, yj + 10, Z_TOP, "#cbd5e1", "#334155", 0.9, 1.2)
    # размеры: сверху — оси и стойки, снизу — общая длина
    s.dim_h(y0, y0 + POST_D, 3290, f"{POST_D:.0f}", off=0)
    s.dim_h(y1 - POST_D, y1, 3290, f"{POST_D:.0f}", off=0)
    for a, b in ((y0, 0.0), (0.0, ym), (ym, B), (B, y1)):
        s.dim_h(a, b, 3390, f"{abs(b - a):.0f}", off=0)
    s.dim_h(y0, y1, 1740, f"{(y1 - y0):.0f} — полоса на всю длину кровли", off=0)
    for yy, t in ((0.0, "рама 1"), (ym, "рама 2"), (B, "рама 3")):
        s.text(yy, 3480, t, "lb", "middle")
    s.text(y0, 1790, "передняя кромка", "lbs")
    s.text(y1, 1790, "задняя кромка", "lbs", "end")
    s.text(-80, 1790, "П1", "lb", "end")
    s.text(B + 80, 1790, "П3", "lb")
    level(s, y1, Z_TOP, 3200, "+3.040")
    level(s, y1, (TR["z1"] + TR["z2"]) / 2, 2900, "+3.000")
    level(s, y1, (SP["z1"] + SP["z2"]) / 2, 2290, "+2.120")
    level(s, y1, Z_BOT, 1960, "+2.070")
    marks = [(y0 + 1300, 2600, 1), (ym - 1000, 3000, 2), (-500, 3000, 3), (-500, 2120, 4), (ym + 1200, 2120, 5),
             (y0 + POST_D, 2600, 6), (y1 - POST_D, 3126, 7), (ym, 3100, 8), (ym + 650, 2500, 9),
             (joints()[0], 2350, 10)]
    for u, z, n in marks:
        mark(s, u, z, n)
    return s.svg("вид на правый ряд колонн снаружи")


ROW_LEGEND = [
    "лист сотового поликарбоната 8 мм, графит, +2.070…+3.040, на всю длину кровли; канавки вертикально, УФ-слой наружу",
    "верхняя рейка Р1 40×20×2 на +3.000 (40 — поперёк листа): два пролёта между фасонками узлов А и Б, шов 16",
    "верхние рейки-консоли Р2, Р3 40×20×2 за колоннами, торцом к фасонке узла А, шов 16",
    "нижние рейки-консоли Р4, Р5 40×20×2 за колоннами (+2.110…+2.130), торцом к боковой грани колонны, шов 16",
    "прокладка Пр 20×20×2 по наружной грани нижнего пояса фермы (+2.110…+2.130), шов 17 — выводит лист в плоскость колонн",
    "торцевые стойки С1 20×20×2 в 175 мм от кромок — за рейками, к торцевой обвязке и к рейкам, шов 18",
    "торцевая обвязка 50×30×2 (в 175 мм от передней и задней кромки, низ ≈ +3.10)",
    "стропила рам 1–3 над рядом (сечение) и фасонки узлов А, Б; щель ≈ 15 см между верхом листа и кровлей открыта",
    "боковая ферма: пояс 60×60×2, раскосы, столик, стойка рамы 2 — на 20 мм глубже плоскости листа",
    "соединительные H-профили 8 мм (3 шт.) — стыки кусков листа",
]


def joints():
    """Стыки кусков листа (H-профили) от передней кромки: 3 × 2.1 м, узкий кусок — у задней кромки."""
    y0 = Y0()
    return [y0 + SHEET_W * k for k in (1, 2, 3)]


def plan_node(kind):
    """Разрез на отметке +3.000, вид сверху: у колонны П1 (kind='A') или у стойки рамы 2 (kind='B')."""
    W = 1400
    s = Svg(-700, 700, -270, 170, k=kfit(W))
    hb = COL_HB if kind == "A" else STUB_H
    hh = COL_HH if kind == "A" else STUB_H
    s.rect(-30, -260, 30, -hh, COL["tie"], "#0008", 0.9)
    gx1, gx2 = (-200, COL_HH) if kind == "A" else (-170, STUB_H)
    for sg in (-1, 1):
        s.rect(sg * hb, gx1, sg * (hb + GT), gx2, "#9ca3af", "#111", 0.9, 1)
    s.rect(-hb, -hh, hb, hh, COL["col"] if kind == "A" else COL["stub"], "#0008", 0.9)
    g = hb + GT
    for sg in (-1, 1):
        a, b = sorted((sg * g, sg * 330))
        s.rect(a, TR["x1"], b, TR["x2"], RAIL, "#0008", 0.9)
        s.seam([(sg * g, TR["x1"]), (sg * g, min(TR["x2"], gx2))], w=4)
    for sg in (-1, 1):                                  # обрыв реек
        s.line(sg * 330, TR["x1"] - 12, sg * 330, TR["x2"] + 4, "ld")
    s.rect(-340, SH_X, 340, SH_X + SH_T, SHEET_FILL, "#1f2937", 0.5, 1)
    for u in (-240, 240):
        s.rect(u - 9, SH_X + SH_T, u + 9, SH_X + SH_T + 5, "#e5e7eb", "#111", 1, 0.8)
        s.rect(u - 2.5, TR["x1"] + 4, u + 2.5, SH_X + SH_T, "#374151", "none")
    s.line(-340, 0, 340, 0, "ax")
    s.line(0, -265, 0, 160, "ax")
    nm = "колонна П1 □100×60×4" if kind == "A" else "стойка-вставка рамы 2 □60×60×3"
    s.leader(-hb + 8, -hh + 10, -360, -130, nm, "lbs")
    s.leader(hb + GT / 2, gx1 + 30, 360, -170, f"фасонки узла {'А' if kind == 'A' else 'Б'} t=5, с обеих сторон", "lbs")
    s.leader(12, -235, 360, -235, "затяжка □60×60×2", "lbs")
    s.leader(300, (TR["x1"] + TR["x2"]) / 2, 360, -60, "рейка Р1 40×20×2 → к " + ("стойке рамы 2" if kind == "A" else "колонне П3"), "lbs")
    s.leader(-300, (TR["x1"] + TR["x2"]) / 2, -360, -50,
             "консоль Р2 40×20×2 → к кромке" if kind == "A" else "рейка Р1 40×20×2 → к колонне П1", "lbs")
    s.leader(-200, SH_X + SH_T, -360, 120, "лист 8 мм" + (" по наружной грани колонны" if kind == "A" else ""), "lbs")
    s.leader(240, SH_X + SH_T + 5, 360, 120, "саморез с термошайбой", "lbs")
    s.weld(g + 24, TR["x1"] - 18, 16)
    s.weld(-g - 24, TR["x1"] - 18, 16)
    s.dim_v(345, TR["x1"], TR["x2"], "40", off=0, anchor="start")
    s.dim_v(345, 0, TR["x1"], f"{TR['x1']:.0f}", off=0, anchor="start")
    if kind == "B":
        s.dim_v(-345, STUB_H, SH_X, "20", off=0)
    s.text(-690, 160, "наружу ↑", "lbs")
    return s.svg(f"узел крепления верхней рейки у {'колонны' if kind == 'A' else 'стойки рамы 2'}")


def _u_profile(s, z_edge, up):
    sg = 1 if up else -1
    u = [(SH_X - 1.5, z_edge - sg * 18), (SH_X - 1.5, z_edge + sg * 1.5), (SH_X + SH_T + 1.5, z_edge + sg * 1.5),
         (SH_X + SH_T + 1.5, z_edge - sg * 18)]
    s.items.append('<polyline points="' + " ".join(f"{s.P(*q)[0]:.1f},{s.P(*q)[1]:.1f}" for q in u)
                   + f'" fill="none" stroke="#111" stroke-width="{1.6 * s.k:.1f}"/>')


def _screw(s, x_in, zs):
    s.rect(x_in, zs - 2.5, SH_X + SH_T + 5, zs + 2.5, "#374151", "none")
    s.rect(SH_X + SH_T, zs - 10, SH_X + SH_T + 5, zs + 10, "#e5e7eb", "#111", 1, 0.8)


def section_top():
    """Разрез по листу между колоннами — верх: рейка, лист, U-профиль, щель до кровли (позиции — номерами)."""
    s = Svg(-110, 250, 2960, 3215, k=kfit(360, 0.5))
    s.rect(TR["x1"], TR["z1"], TR["x2"], TR["z2"], RAIL, "#0008", 0.9)
    s.rect(SH_X, 2960, SH_X + SH_T, Z_TOP, SHEET_FILL, "#1f2937", 0.5, 1)
    _u_profile(s, Z_TOP, True)
    zs = (TR["z1"] + TR["z2"]) / 2
    _screw(s, TR["x1"] + 5, zs)
    for zz in (3151, 3186):
        s.line(-110, zz, 250, zz, "ld")
    s.dim_v(150, Z_TOP, 3186, f"≈ {3186 - Z_TOP:.0f}", off=0, anchor="start")
    s.dim_v(-10, zs, Z_TOP, f"{Z_TOP - zs:.0f}", off=0)
    s.dim_h(TR["x1"], TR["x2"], 3025, "40", off=0)
    for u, z, n in ((25, 2985, 1), (54, 2975, 2), (54, 3062, 3), (90, zs + 18, 4), (-60, 3165, 5), (-60, 3198, 6)):
        mark(s, u, z, n)
    s.text(245, 2966, "наружу →", "lbs", "end")
    return s.svg("разрез: верх полосы")


SEC_TOP_LEGEND = ["верхняя рейка 40×20×2 (+2.990…+3.010)", "лист 8 мм, УФ-слой наружу",
                  "U-профиль 8 мм, под ним — сплошная лента", "саморез 5.5 по металлу с термошайбой",
                  "низ обрешётки кровли ≈ +3.15", "низ металлочерепицы ≈ +3.19"]


def section_bot():
    """Разрез по листу между колоннами — низ: пояс фермы, прокладка, лист, U-профиль (позиции — номерами)."""
    s = Svg(-110, 250, 2030, 2200, k=kfit(360, 0.5))
    s.rect(-30, 2070, 30, 2130, COL["sb"], "#0008", 0.9)
    s.rect(-28, 2072, 28, 2128, "var(--card)", "none")
    s.rect(SP["x1"], SP["z1"], SP["x2"], SP["z2"], RAIL2, "#0008", 0.9)
    s.rect(SH_X, Z_BOT, SH_X + SH_T, 2200, SHEET_FILL, "#1f2937", 0.5, 1)
    _u_profile(s, Z_BOT, False)
    zs = (SP["z1"] + SP["z2"]) / 2
    _screw(s, SP["x1"] + 3, zs)
    s.seam([(SP["x1"] - 1, SP["z2"]), (SP["x1"] + 3, SP["z2"] + 3)], w=4)
    s.seam([(SP["x1"] - 1, SP["z1"]), (SP["x1"] + 3, SP["z1"] - 3)], w=4)
    s.weld(SP["x1"] - 14, SP["z2"] + 22, 17)
    s.dim_v(150, Z_BOT, zs, f"{zs - Z_BOT:.0f}", off=0, anchor="start")
    for u, z, n in ((-55, 2100, 1), (36, 2121, 2), (54, 2180, 3), (70, 2048, 4), (95, zs + 20, 5)):
        mark(s, u, z, n)
    return s.svg("разрез: низ полосы")


SEC_BOT_LEGEND = ["нижний пояс боковой фермы □60×60×2", "прокладка 20×20×2 (+2.110…+2.130), шов 17",
                  "лист 8 мм", "U-профиль 8 мм с отверстиями для стока, под ним — перфорированная лента",
                  "саморез 5.5 по металлу с термошайбой"]


def post_view(raf, ge):
    """Торцевая стойка у передней кромки — вид изнутри навеса (стойка перед рейками, лист за ними), с разрывом."""
    y0 = Y0()
    yp = y0 + POST_D
    zge = z_ge_bot(raf, ge)
    ZC, CUT = 2250.0, 650.0                           # разрыв: участок ZC…ZC+CUT не показан
    q = lambda z: z if z <= ZC else z - CUT
    s = Svg(y0 - 160, y0 + 1050, 1990, 3240 - CUT, k=kfit(1210), pad=30)

    def R(u1, z1, u2, z2, *a, **kw):
        if z1 < ZC < z2 and z2 > ZC + CUT:
            s.rect(u1, q(z1), u2, ZC - 8, *a, **kw)
            s.rect(u1, ZC + 8, u2, q(z2), *a, **kw)
        else:
            s.rect(u1, q(z1), u2, q(z2), *a, **kw)
    x2 = y0 + 520
    R(y0, Z_BOT, x2, Z_TOP, SHEET_FILL, "#1f2937", 0.18, 1.5)
    R(y0, Z_BOT, y0 + 4, Z_TOP, "#111", "none", 0.8)
    for zz in (TR, BR):
        R(y0, zz["z1"], x2, zz["z2"], RAIL, "#0008", 0.9)
    R(yp - 15, zge, yp + 15, 3151, COL["ge"], "#0008", 0.9)
    R(y0 - 160, 3151, x2, 3186, COL["lath"], "#0006", 0.6)
    R(y0 - 160, 3186, x2, 3196, "#64748b", "none", 0.6)
    R(yp - 10, BR["z1"], yp + 10, zge, RAIL2, "#0008", 0.95)
    for zz in (ZC - 8, ZC + 8):
        s.line(y0 - 20, zz, x2 + 20, zz, "ld")
    s.text(x2 + 30, ZC - 6, "разрыв", "lbs")
    s.seam([(yp - 10, q(zge)), (yp + 10, q(zge))], w=4)
    for zz in (TR, BR):
        for sg in (-1, 1):
            s.seam([(yp + sg * 10, q(zz["z1"])), (yp + sg * 10, q(zz["z2"]))], w=4)
    s.weld(yp + 45, q(zge) - 25, 18)
    s.weld(yp + 45, q(TR["z1"]) - 28, 18)
    s.weld(yp + 45, q(BR["z2"]) + 30, 18)
    s.dim_h(y0, yp, 2010, f"{POST_D:.0f}", off=0)
    s.leader(yp + 15, q(zge) + 30, x2 + 30, q(3120), "торцевая обвязка □50×30×2 (сечение)", "lbs")
    s.leader(yp, q(2180), x2 + 30, q(2180), f"стойка С1 20×20×2, L = {zge - BR['z1']:.0f}", "lbs")
    s.leader(y0 + 400, q(TR["z2"]), x2 + 30, q(3040), "консоль верхней рейки, +2.990…+3.010", "lbs")
    s.leader(y0 + 400, q(BR["z2"]), x2 + 30, q(2140), "консоль нижней рейки, +2.110…+2.130", "lbs")
    s.leader(y0 + 2, q(2090), x2 + 30, q(2075), "кромка листа, U-профиль", "lbs")
    s.text(y0 - 150, q(3215), "обрешётина кровли, лист", "lbs")
    s.text(y0 + POST_D + 30, 2000, "от передней кромки", "lbs")
    return s.svg("торцевая стойка полосы")


def band(p1, p2, w):
    """Полоса шириной w вдоль оси p1→p2 (элемент на виде)."""
    dx, dz = p2[0] - p1[0], p2[1] - p1[1]
    L = math.hypot(dx, dz)
    nx, nz = -dz / L * w / 2, dx / L * w / 2
    return [(p1[0] + nx, p1[1] + nz), (p2[0] + nx, p2[1] + nz), (p2[0] - nx, p2[1] - nz), (p1[0] - nx, p1[1] - nz)]


def clip_member(a, d, w, f1, f2):
    """Стержень шириной w с осью a + t·d, обрезанный линиями f1(x, z) = 0 и f2(x, z) = 0 (обе линейны)."""
    L = math.hypot(*d)
    d = (d[0] / L, d[1] / L)
    n = (-d[1], d[0])
    pts = []
    for f in (f1, f2):
        for sg in ((1, -1) if f is f1 else (-1, 1)):
            o = (a[0] + sg * n[0] * w / 2, a[1] + sg * n[1] * w / 2)
            f0 = f(*o)
            f_1 = f(o[0] + d[0], o[1] + d[1])
            t = -f0 / (f_1 - f0)
            pts.append((o[0] + t * d[0], o[1] + t * d[1]))
    return pts


def diag_view(fd, raf, tie, eg):
    """Раскос фермы у опоры (правая половина рамы; левая и рама 2 — так же), вид в плоскости рамы."""
    X = M.SPAN * 1000
    Hr = raf.h * 1000 / M.COS
    zr = lambda x: M.z_rafter(x / 1000) * 1000
    xmin, xmax = X - 2000, X + 200
    s = Svg(xmin, xmax, 2840, 3640, k=kfit(xmax - xmin), pad=30)
    top = lambda x: zr(x) + Hr / 2
    bot = lambda x: zr(x) - Hr / 2
    s.poly([(xmin, bot(xmin)), (xmax, bot(xmax)), (xmax, top(xmax)), (xmin, top(xmin))], COL["raf"], "#0008", 0.9)
    s.rect(X - 50, 2860, X + 50, 3043, COL["col"], "#0008", 0.9)
    s.rect(xmin, 2970, X - 50, 3030, COL["tie"], "#0008", 0.9)
    g1, g2 = X + 50, X - 200
    s.poly([(g1, 2920), (g2, 2920), (g2, zr(g2)), (g1, zr(g1))], "#9ca3af", "#111", 0.55, 1.2)
    f_tie = lambda x, z: z - 3030.0
    sl = (zr(X) - zr(X - 1000)) / 1000
    f_raf = lambda x, z: z - (bot(X) + sl * (x - X))
    xn = X - eg["dxr"] * 1000
    zn = zr(xn)
    xs_, zs_ = M.X_RIDGE * 1000, 3000.0
    sp = clip_member((xs_, zs_), (xn - xs_, zn - zs_), 20, lambda x, z: x - xmin, f_raf)
    s.poly(sp, COL["kp"], "#0008", 0.9)
    xt = X - eg["dxt"] * 1000
    pts = clip_member((xt, 3000.0), (xn - xt, zn - 3000.0), 20, f_tie, f_raf)
    s.poly(pts, "#a855f7", "#3b0764", 0.95, 1.2)
    s.seam([pts[0], pts[1]], w=4.5)
    s.seam([pts[2], pts[3]], w=4.5)
    s.line(xt, 3000, xn, zn, "ax")
    s.line(xmin, 3000, xmax, 3000, "ax")
    s.line(xmin, zr(xmin), xmax, zr(xmax), "ax")
    s.line(X, 2870, X, 3560, "ax")
    s.line(xn, 2880, xn, 3560, "ax")
    s.line(xt, 2880, xt, 3000, "ax")
    p = s.P(xn, zn)
    s.items.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{3 * s.k:.1f}" fill="var(--fg)"/>')
    s.dim_h(xt, X, 2880, f"{eg['dxt'] * 1000:.0f}", off=0)
    s.dim_h(xn, X, 3540, f"{eg['dxr'] * 1000:.0f}", off=0)
    s.weld((pts[0][0] + pts[1][0]) / 2 + 70, 3080, 15)
    xm = (pts[2][0] + pts[3][0]) / 2
    s.weld(xm - 110, bot(xm - 110) - 40, 15)
    s.leader(xt - 0.3 * (xt - xn), 3000 + 0.3 * (zn - 3000), xt - 500, 2900,
             f"новый раскос □20×20×2, L ≈ {eg['Lc'] * 1000:.0f} по оси", "lbs", "end")
    sx = xmin + 100
    s.leader(sx, zs_ + (zn - zs_) * (sx - xs_) / (xn - xs_), xmin + 110, 3250, "подкос фермы (есть)", "lbs", "start")
    s.leader(xmin + 200, 3030, xmin + 260, 3100, f"затяжка □{tie.name}", "lbs", "start")
    s.leader(X - 300, top(X - 300), X - 250, 3420, f"стропило □{raf.name}", "lbs", "start")
    s.leader(X - 150, 2945, X - 400, 3075, "фасонка узла А", "lbs", "end")
    s.text(xn - 10, 3610, "узел подкоса", "lbs", "end")
    s.text(X + 10, 3610, "ось колонны", "lbs")
    s.text(xt - 230, 3040, f"{math.degrees(eg['beta']):.0f}°", "lb", "middle")
    s.text(xm + 260, bot(xm + 260) - 55, f"{math.degrees(eg['gam']):.0f}°", "lb", "middle")
    return s.svg("раскос фермы у опоры")


def sheet_layout():
    """Раскладка кусков листа по полосе (вид снаружи)."""
    y0, y1 = Y0(), Y1()
    s = Svg(y0 - 80, y1 + 80, 1820, 3170, k=kfit(y1 - y0 + 160), pad=20)
    js = [y0] + joints() + [y1]
    for i, (a, b) in enumerate(zip(js[:-1], js[1:]), 1):
        s.rect(a, Z_BOT, b, Z_TOP, SHEET_FILL, "#1f2937", 0.3 if i < 4 else 0.45, 1.5)
        s.text((a + b) / 2, (Z_BOT + Z_TOP) / 2 - 60, f"{i}", "lb", "middle")
        s.dim_h(a, b, 1900, f"{b - a:.0f}", off=0)
    for yj in js[1:-1]:
        s.rect(yj - 10, Z_BOT, yj + 10, Z_TOP, "#cbd5e1", "#334155", 0.9, 1.2)
    zs1, zs2 = (TR["z1"] + TR["z2"]) / 2, (SP["z1"] + SP["z2"]) / 2
    n = 0
    for a, b in zip(js[:-1], js[1:]):
        for yy in screw_pos(a, b):
            for zz in (zs1, zs2):
                p = s.P(yy, zz)
                s.items.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{4 * s.k:.0f}" fill="#e5e7eb" stroke="#111"/>')
                n += 1
    for y, t in ((0.0, "П1"), (BAYmm() / 2, "рама 2"), (BAYmm(), "П3")):
        s.line(y, Z_TOP + 10, y, 3110, "ax")
        s.text(y, 3125, t, "lbs", "middle")
    return s.svg("раскладка листа"), n


def screw_pos(a, b):
    """Термошайбы на куске листа a…b: от краёв не ближе EDGE_MIN (+20 мм на H/U-профиль), шаг ≤ SCREW_STEP."""
    e = EDGE_MIN + 20
    k = max(1, math.ceil((b - a - 2 * e) / SCREW_STEP))
    return [a + e + (b - a - 2 * e) * i / k for i in range(k + 1)]


def sheet_cut():
    s = Svg(-60, SHEET_L + 420, -60, SHEET_W + 260, k=kfit(SHEET_L + 480, 0.6), pad=20)
    n = int(SHEET_L // 970)
    for i in range(n):
        a, b = i * 970, (i + 1) * 970
        need = i < 4
        s.rect(a, 0, b, SHEET_W, SHEET_FILL if need else "#94a3b8", "#1f2937", 0.45 if need else 0.2, 1.2)
        s.text((a + b) / 2, SHEET_W / 2 + 120, f"{i + 1}", "lb", "middle")
        s.text((a + b) / 2, SHEET_W / 2 - 200, "в дело" if need else "запас", "lbs", "middle")
    s.rect(n * 970, 0, SHEET_L, SHEET_W, "none", "#1f2937", 1, 1, dash="8 6")
    s.line(3 * 970, 680, 4 * 970, 680, "ld")
    s.text(3 * 970 + 485, 420, "4: 0.68", "lbs", "middle")
    s.dim_h(0, SHEET_L, SHEET_W + 160, f"{SHEET_L:.0f}, канавки — вдоль", off=0)
    s.dim_v(SHEET_L + 30, 0, SHEET_W, f"{SHEET_W:.0f}", off=0, anchor="start")
    s.dim_h(0, 970, -30, "970", off=0)
    return s.svg("раскрой листа 2.1 × 6 м")


# ---------------- документ ----------------
def build():
    fd = json.loads((OUT / "final_design.json").read_text())
    nf = json.loads((OUT / "node_forces.json").read_text())
    g = fd["groups"]
    raf, tie, ge, col = (sec_by_name(g[k]) for k in ("raf", "tie", "ge", "col"))
    ew = sec_by_name(g["ew"])
    eg = ew_geom(fd, raf, tie)
    cc = calc(fd)
    u = {k: v[0] for k, v in fd["util"].items()}
    u4 = {k: v[0] for k, v in fd["util_ch04"].items()}
    lay_svg, n_screw = sheet_layout()
    pr = parts(raf, ge)
    css = NODE_CSS + """
table td.n,table th.n{text-align:right;font-variant-numeric:tabular-nums}
ol.l{font-size:14px;columns:2;column-gap:28px;padding-left:22px}ol.l li{break-inside:avoid;margin:3px 0}
.grid2e{display:grid;grid-template-columns:1fr;gap:12px}@media(min-width:800px){.grid2e{grid-template-columns:1fr 1fr}}
@media print{.grid2e{grid-template-columns:1fr 1fr}}
p.note{font-size:14px}
ol.s{font-size:13px;padding-left:22px;margin:6px 0}
"""
    # металл
    by = {}
    for p in pr:
        by.setdefault(p[1], []).append(p)
    prow = "".join(f"<tr><td>{a}</td><td>□{b}</td><td class='n'>{L / 1000:.3f}</td><td class='n'>{n}</td>"
                   f"<td>{html.escape(c)}</td></tr>" for a, b, L, n, c in pr)
    tot = {sn: sum(p[2] * p[3] for p in ps) / 1000 for sn, ps in by.items()}
    price = {sn: sec_by_name(sn).price for sn in by}
    kg = {sn: tot[sn] * sec_by_name(sn).mass for sn in by}
    p40 = {p[0]: p[2] / 1000 for p in pr}
    bars40 = [[p40["Р1"], p40["Р1"], p40["Р3"]], [p40["Р2"], p40["Р4"], p40["Р5"]]]
    b40 = "; ".join("[" + " + ".join(f"{x:.3f}" for x in b) + f"] остаток {6 - sum(b) - CUT_KERF * len(b):.2f}" for b in bars40)
    psp, pst = p40["Пр"], p40["С1"]
    # расчёт обрешётки
    crow = "".join(f"<tr><td>{html.escape(r[0])}</td><td class='n'>{r[1]:.2f}</td><td class='n'>{r[2]:.0f}</td>"
                   f"<td class='n'>{r[3]:.0f}</td><td class='n'>{r[4] / 1e6:.0f}</td><td class='n'>{r[5]:.2f}</td>"
                   f"<td class='n'>{r[6]:.1f} ≤ {r[7]:.1f}</td></tr>" for r in cc["rows"])
    n_u = len(joints()) + 1
    u_len = 2 * (Y1() - Y0()) / 1000 + 2 * (Z_TOP - Z_BOT) / 1000
    page = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Полоса поликарбоната</title>
<style>{css}</style></head><body><main>
<h1>Полоса поликарбоната по правому ряду колонн и раскосы ферм у опор</h1>
<p class="sub">Навес 5.45 × 4.60 м · сотовый поликарбонат 8 мм, графит · +2.070…+3.040 (0.97 м) на всю длину кровли
{(Y1() - Y0()) / 1000:.2f} м · каркас уже смонтирован: всё ниже делается на стоящем каркасе</p>

<div class="card">
<h3>Что делается и почему</h3>
<ul>
<li><b>Полоса</b> закрывает правую сторону навеса от верха колонн до низа нижнего пояса боковой фермы; щель ≈ 15 см
между верхом полосы и кровлей остаётся открытой. Лист — в плоскости наружных граней колонн (боковая ферма и стойка
рамы 2 — на 20 мм глубже). Канавки листа — вертикально (конденсат стекает вниз), УФ-слой — наружу.</li>
<li><b>Ветер на полосу</b> — как на отдельно стоящий приподнятый щит, суммарный коэффициент {M.Loads().cp_panel:g}
(в запас): расчётное давление {cc['w']:.0f} Па ({cc['kg']:.0f} кг/м²), на всю полосу ≈ {cc['F'] / 1000:.1f} кН.
Он передаётся на правый ряд колонн, и рама работает целиком: без доработки правые стропила рам 1 и 3 перегружены
({fd['panel']['raf_no_ew']:.2f}).</li>
<li><b>Вместо усиления стропил</b> продлена решётка ферм к опорам: в каждой половине каждой рамы — <b>раскос
□{ew.name}</b> от узла подкоса на стропиле вниз к затяжке (6 шт., одинаковый вид во всех рамах). Под стропилами
ничего не добавляется. Каркас с полосой и раскосами: стропила {u['raf']:.2f}, раскосы {u['ew']:.2f},
затяжки {u['tie']:.2f}, колонны {u['col']:.2f}; максимум по каркасу {max(u.values()):.2f} (обрешётка кровли, от полосы
не зависит). Для местности III — максимум {max(u4.values()):.2f}.</li>
</ul></div>

<h2>1. Вид на правый ряд колонн снаружи</h2>
<div class="card">{row_view(raf, ge)}<ol class="l">{''.join(f"<li>{html.escape(x)}</li>" for x in ROW_LEGEND)}</ol>
<p class="note">Лист показан полупрозрачным. Отметки — от того же нуля, что в основном комплекте (оси стропил над
колоннами +3.100, верх колонн +3.043).</p></div>

<h2 class="pb">2. Узлы обрешётки</h2>
<div class="card"><h3>У колонны П1 (П3 — так же), разрез на +3.000, вид сверху</h3>{plan_node("A")}
<p class="note">Верхние рейки подходят к колонне с двух сторон и привариваются торцом к фасонкам узла А
(шов <span class="wk">16</span>). Наружная грань рейки — в плоскости наружной грани колонны.</p></div>
<div class="card"><h3>У стойки рамы 2, разрез на +3.000, вид сверху</h3>{plan_node("B")}
<p class="note">Стойка-вставка на 20 мм глубже плоскости листа, поэтому рейка здесь не проходит насквозь: два
отдельных пролёта, торцы — к фасонкам узла Б по внутренним 20 мм (шов <span class="wk">16</span>). Перед стойкой
между торцами реек — зазор, лист проходит снаружи.</p></div>
<div class="card"><h3>Разрез по листу между колоннами</h3>
<div class="grid2e"><div><h3>Верх</h3>{section_top()}<ol class="s">{''.join(f"<li>{html.escape(x)}</li>" for x in SEC_TOP_LEGEND)}</ol></div>
<div><h3>Низ</h3>{section_bot()}<ol class="s">{''.join(f"<li>{html.escape(x)}</li>" for x in SEC_BOT_LEGEND)}</ol></div></div>
<p class="note">За колоннами (консоли) вместо пояса и прокладки — нижняя рейка
40×20×2 на тех же отметках +2.110…+2.130; лист крепится к ней так же. В нижнем U-профиле — отверстия Ø3–5 через
300 мм для стока конденсата.</p></div>
<div class="card"><h3>Торцевая стойка у передней кромки (у задней — зеркально), вид изнутри навеса</h3>{post_view(raf, ge)}
<p class="note">Стойка С1 стоит за рейками (лист к ней не крепится) и связывает концы консолей реек с торцевой
обвязкой: консоли не болтаются и меньше прогибаются. Рейки рассчитаны как консоли и без неё.</p></div>

<h2 class="pb">3. Раскосы ферм у опор — 6 шт.</h2>
<div class="card">{diag_view(fd, raf, tie, eg)}
<ul>
<li>В каждой половине каждой рамы (рамы 1, 2, 3; правый и левый скаты — зеркально; у рамы 2 размеры — от оси
стойки-вставки). Оси раскоса, подкоса фермы и стропила сходятся в одной точке — узле подкоса.</li>
<li><b>Заготовка □{ew.name}, длина по оси ≈ {eg['Lc'] * 1000:.0f} мм</b>; низ — рез под
{math.degrees(eg['beta']):.0f}° к оси (пятно на верху затяжки ≈ {eg['len_t'] * 1000:.0f} мм, центр — в
{eg['foot_t'] * 1000:.0f} мм от оси колонны), верх — рез под {math.degrees(eg['gam']):.0f}° (пятно на низу стропила
≈ {eg['len_r'] * 1000:.0f} мм, центр — в {eg['foot_r'] * 1000:.0f} мм по стропилу от узла подкоса в сторону
колонны). Затяжка и стропило уже стоят — первую заготовку подогнать по месту и по ней резать остальные.</li>
<li>Шов <span class="wk">15</span> — по контуру k = 2 на обоих концах (на стропиле — потолочный). Перед сваркой зачистить
краску; после — окрасить.</li>
<li>Расчёт: раскос сжат до {fd['panel']['ew_Nc']:.1f} кН, использование
{u['ew']:.2f} (гибкость); примыкание к затяжке — {nf.get('узел_ew→tie', {}).get('u', 0):.2f}, к стропилу —
{nf.get('узел_ew→raf', {}).get('u', 0):.2f}. Короче или длиннее не делать: при узле на затяжке ближе 0.7 м к колонне
раскос 20×20 теряет устойчивость, дальше 1.0 м — снова перегружается стропило.</li>
</ul></div>

<h2>4. Поликарбонат: раскладка и раскрой</h2>
<div class="card">{lay_svg}
<p class="note">Вид снаружи. Куски 1–3 по 2.10 м от передней кромки, кусок 4 (0.68 м) — у задней; стыки на H-профилях не попадают на
колонны и стойку. Кружки — термошайбы ({n_screw} шт.): по верхней рейке (+3.000) и по прокладке / нижним рейкам
(+2.120), шаг ≤ {SCREW_STEP:.0f} мм, от краёв и стыков не ближе 60 мм.</p></div>
<div class="card"><div class="grid2e"><div>{sheet_cut()}</div>
<p class="note">Лист 2.1 × 6 м режется <b>поперёк канавок</b> на полосы по 0.97 м (6 шт.): в дело — 4 (три по 2.10 м и
одна, распущенная вдоль канавки на 0.68 м), 2 — в запас. Резать мелкозубой пилой или ножом по линейке, стружку из
канавок выдуть. Кусок 4 — у задней кромки.</p></div></div>

<h2 class="pb">5. Спецификация</h2>
<div class="card">
<h3>Металл обрешётки полосы</h3>
<table><thead><tr><th>Поз.</th><th>Сечение</th><th class="n">L, м</th><th class="n">Кол.</th><th>Примечание</th></tr></thead>
<tbody>{prow}</tbody></table>
<table style="margin-top:10px"><thead><tr><th>Сечение</th><th class="n">Всего, м</th><th class="n">Масса, кг</th><th class="n">Цена по прайсу, грн/м</th><th>Закупка и раскрой</th></tr></thead><tbody>
<tr><td>□40×20×2</td><td class="n">{tot['40×20×2']:.2f}</td><td class="n">{kg['40×20×2']:.1f}</td><td class="n">{price['40×20×2']:.0f}</td><td>2 хлыста 6 м: {b40}</td></tr>
<tr><td>□20×20×2</td><td class="n">{tot['20×20×2']:.2f}</td><td class="n">{kg['20×20×2']:.1f}</td><td class="n">{price['20×20×2']:.0f}</td><td>1 хлыст 6 м: прокладка {psp:.3f} + стойка {pst:.3f}; вторая стойка — из остатка
20×20 по раскрою каркаса (≈ 2.6 м). Раскосы ферм — в ведомости каркаса (navis_optimized).</td></tr>
</tbody></table>
<h3>Поликарбонат и комплектующие</h3>
<table><thead><tr><th>Позиция</th><th class="n">Кол-во</th><th>Примечание</th></tr></thead><tbody>
<tr><td>Сотовый поликарбонат 8 мм, графит, с УФ-защитой, лист 2.1 × 6 м</td><td class="n">1 шт.</td><td>6 полос по 0.97 м, в дело 4</td></tr>
<tr><td>Профиль соединительный H 8 мм (неразъёмный), графит / прозрачный</td><td class="n">{len(joints())} × 0.97 м</td><td>из одного профиля 6 м (или 2 по 2.1 м)</td></tr>
<tr><td>Профиль торцевой U 8 мм</td><td class="n">{u_len:.1f} м</td><td>верх и низ по {(Y1() - Y0()) / 1000:.2f} м, торцы 2 × 0.97 м; 3 профиля по 6 м; в нижнем — отверстия Ø3–5 через 300 мм</td></tr>
<tr><td>Лента сплошная (алюминиевая) для торцов, 25 мм</td><td class="n">{(Y1() - Y0()) / 1000 + 0.1:.1f} м</td><td>верхняя кромка</td></tr>
<tr><td>Лента перфорированная (паропроницаемая), 25 мм</td><td class="n">{(Y1() - Y0()) / 1000 + 0.1:.1f} м</td><td>нижняя кромка</td></tr>
<tr><td>Термошайба для поликарбоната 8 мм с крышкой</td><td class="n">{math.ceil(n_screw * 1.1)} шт.</td><td>{n_screw} + 10 % запас</td></tr>
<tr><td>Саморез по металлу со сверлом 5.5 × 32…38 (под термошайбу 8 мм), оцинк.</td><td class="n">{math.ceil(n_screw * 1.1)} шт.</td><td>в стенку 2 мм рейки / прокладки</td></tr>
</tbody></table>
<h3>Швы</h3>
<table><thead><tr><th>№</th><th>Что с чем</th><th>Шов</th></tr></thead><tbody>
<tr><td><span class="wk">15</span></td><td>раскос фермы к верху затяжки и к низу стропила</td><td>по контуру, k = 2; на стропиле — потолочный</td></tr>
<tr><td><span class="wk">16</span></td><td>торцы реек 40×20 к фасонкам узлов А и Б; нижние консоли — к боковой грани колонны</td><td>по контуру торца в пределах фасонки / грани, k = 2 (у стойки рамы 2 — только внутренние 20 мм рейки)</td></tr>
<tr><td><span class="wk">17</span></td><td>прокладка 20×20 к наружной грани нижнего пояса фермы</td><td>по верхней и нижней кромке, k = 2, прерывистый 40 / 300, у концов — сплошной 50 мм</td></tr>
<tr><td><span class="wk">18</span></td><td>торцевая стойка к низу торцевой обвязки и к внутренним граням реек</td><td>по контуру к обвязке, по боковым кромкам к рейкам, k = 2</td></tr>
</tbody></table></div>

<h2>6. Расчёт обрешётки и листа</h2>
<div class="card">
<p class="note">Ветер на полосу: W0 = {M.Loads().W0:.0f} Па × Ch 0.70 (местность II) × {M.Loads().cp_panel:g} — расчётное
{cc['w']:.0f} Па, эксплуатационное {cc['we']:.0f} Па (для прогибов, как во всём проекте). Грузовые полосы: верхняя
линия крепления — {cc['ht']:.2f} м, нижняя — {cc['hb']:.2f} м. Рейка 40×20×2 работает на изгиб поперёк листа (40 —
поперёк): W = {sec_by_name('40×20×2').Wy * 1e6:.2f} см³, I = {sec_by_name('40×20×2').Iy * 1e8:.2f} см⁴; Ry = 230 МПа.</p>
<table><thead><tr><th>Элемент</th><th class="n">L, м</th><th class="n">q, Н/м</th><th class="n">M, Н·м</th><th class="n">σ, МПа</th><th class="n">Исп.</th><th class="n">Прогиб, мм</th></tr></thead>
<tbody>{crow}</tbody></table>
<ul>
<li>20×20×2 на пролёт 2.23 м не годится (≈ 3 раза слабее по моменту сопротивления: σ ≈ 240 МПа) — поэтому рейки 40×20.</li>
<li>Лист 8 мм перекрывает {cc['span_sheet']:.2f} м между линиями крепления канавками поперёк опор, нагрузка
{cc['kg']:.0f} кг/м² расчётная — в пределах обычных таблиц производителей для 8 мм (сверить с таблицей выбранного
производителя). Отрыв на одну термошайбу верхней линии ≈ {cc['screw']:.0f} Н.</li>
<li>Прокладка 20×20 приварена к поясу по всей длине и сама не изгибается: нижнюю линию держит пояс фермы (в расчёте
каркаса нагрузка нижней половины полосы приложена к поясу).</li>
<li>Тепловое удлинение графитового листа на солнце: ≈ 0.065 мм/(м·°C) → на куске 2.1 м ≈ ±6 мм. Поэтому в H-профилях
и U-профилях на торцах оставить по 3 мм, отверстия в листе — на 2–3 мм больше ножки термошайбы, саморезы не
перетягивать.</li>
</ul></div>

<h2>7. Порядок работ (на стоящем каркасе)</h2>
<div class="card"><ol>
<li><b>Раскосы ферм</b> (6 шт., п. 3) — первыми: они нужны каркасу под ветер на полосу. Зачистить краску в местах
швов, подогнать первую заготовку по месту, по ней нарезать остальные; прихватить, проверить, обварить (шов
<span class="wk">15</span>), окрасить.</li>
<li><b>Прокладка Пр</b> на наружную грань нижнего пояса правой фермы, верх — по верху пояса (+2.130), шов
<span class="wk">17</span>. Проверить шнуром: наружная грань прокладки — в плоскости наружных граней колонн (± 2 мм).</li>
<li><b>Нижние консоли Р4, Р5</b> — к наружным боковым граням колонн П1 и П3 на +2.110…+2.130, шов
<span class="wk">16</span>; горизонтально, наружная грань — в плоскости колонн.</li>
<li><b>Верхние рейки Р1</b> (2 пролёта) между фасонками узлов А и Б и <b>консоли Р2, Р3</b> к фасонкам узла А,
низ рейки +2.990, шов <span class="wk">16</span>. Проверить шнуром плоскость по всем рейкам.</li>
<li><b>Торцевые стойки С1</b> — за рейками, в 175 мм от кромок, к низу торцевой обвязки и к рейкам, шов
<span class="wk">18</span>. Торцы реек заглушить.</li>
<li>Зачистить и окрасить все швы и места зачистки (цвет — как каркас).</li>
<li><b>Лист:</b> нарезать (п. 4), выдуть стружку; на верхнюю кромку — сплошную ленту, на нижнюю — перфорированную;
надеть U-профили (в нижнем — отверстия для стока). Защитную плёнку снять у кромок, полностью — после монтажа.
УФ-сторона (маркировка на плёнке) — наружу.</li>
<li>Ставить куски от передней кромки, соединяя H-профилями; низ — по прокладке / нижним рейкам. Сверлить лист
по месту, термошайбы через ≤ {SCREW_STEP:.0f} мм в верхние рейки (+3.000) и в прокладку / нижние рейки (+2.120),
не ближе 60 мм к краям. Перед колоннами лист проходит снаружи; если мешает наплыв шва фасонки на наружной грани
колонны — сошлифовать.</li>
</ol></div>
</main></body></html>"""
    return page


def main():
    (OUT / "polosa.html").write_text(build(), encoding="utf-8")
    print("output/polosa.html")


if __name__ == "__main__":
    main()
