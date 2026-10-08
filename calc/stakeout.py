"""Разбивочный план лунок (вид сверху) — отдельный документ output/razbivka.html (+ PDF через make_pdf.py).

Привязка — как в черновике 2026-ПР-480: от опор ворот (точки A и B), X — вдоль линии задних граней опор вправо,
Y — перпендикулярно вглубь участка. Лунки не переносились: те же 4 точки. Колонны 100×60×4 — на всю глубину лунки.
"""
from __future__ import annotations

import html
import json
import math

import model as M
from nodes_drawing import NODE_CSS, OUT, Svg

# центры лунок, м (X от A, Y от линии опор) — разбивка черновика
HOLES = {"Л1": (-0.350, 1.000), "П1": (5.100, 1.000), "Л3": (-0.121, 5.592), "П3": (5.329, 5.592)}
A, B = (0.0, 0.0), (4.20, 0.0)          # задние наружные углы опор ворот (опоры 100×100)
# размеры для разбивки — как в черновике (округлены до мм; расхождение с координатами ≤ 1 мм, допуск ±10 мм)
FROM_AB = {"Л1": (1.060, 4.659), "П1": (5.197, 1.345), "Л3": (5.593, 7.066), "П3": (7.725, 5.705)}
CTRL = dict(cross=5.450, along=4.597, d_l1p3=7.304, d_p1l3=6.952, front=1.000, rear=1.000, left=0.400, right=0.350)
PLOT_W, PLOT_D = 5.40, 6.592            # площадка: по фронту и глубина (по перпендикуляру)
TAN = math.tan(M.SKEW)
HOLE = 0.30                             # лунка 300×300, стороны параллельны передней кромке
COL_B, COL_H = 0.100, 0.060             # колонна: 100 вдоль рамы (параллельно передней кромке), 60 вдоль ряда
PAVER = 0.06                            # бетонная плитка на дне лунки
GAP = 0.10                              # низ колонны над дном лунки
Z_COL_TOP = M.Z_COL_TOP                 # верх колонны под опорной пластиной


def dist(p, q):
    return math.hypot(q[0] - p[0], q[1] - p[1])


SHOW_COL, SHOW_HOLE = 4.0, 1.8         # на плане колонны и лунки увеличены (иначе грань от центра не отличить)


def col_marks(show=1.0):
    """Точки на колоннах для контроля по граням: середины обращённых друг к другу граней и ближние рёбра.
    Колонна 100×60: сторона 100 — вдоль рамы (по X), 60 — вдоль ряда (по Y)."""
    hb, hh = COL_B / 2 * show, COL_H / 2 * show
    m = {}
    for n, (x, y) in HOLES.items():
        sx = 1 if n.startswith("Л") else -1          # внутрь, к другому ряду
        sy = 1 if n.endswith("1") else -1            # к другой раме
        m[n] = dict(side=(x + sx * hb, y),           # середина грани, обращённой к другому ряду (60 мм)
                    end=(x, y + sy * hh),            # середина грани, обращённой к другой раме (100 мм)
                    rib=(x + sx * hb, y + sy * hh))  # ближнее ребро (угол)
    return m


def clear_dims():
    """Расстояния между гранями колонн (по серединам граней) и диагонали между ближними рёбрами, м."""
    c = col_marks()
    return dict(cross1=dist(c["Л1"]["side"], c["П1"]["side"]), cross3=dist(c["Л3"]["side"], c["П3"]["side"]),
                alongL=dist(c["Л1"]["end"], c["Л3"]["end"]), alongR=dist(c["П1"]["end"], c["П3"]["end"]),
                d_l1p3=dist(c["Л1"]["rib"], c["П3"]["rib"]), d_p1l3=dist(c["П1"]["rib"], c["Л3"]["rib"]))


def plot_corners():
    s = PLOT_D * TAN
    return [(0.0, 0.0), (PLOT_W, 0.0), (PLOT_W + s, PLOT_D), (s, PLOT_D)]


def roof_corners():
    """Контур кровли: свесы 0.40 / 0.90 вдоль рамы от осей рядов, 1.18 / 1.20 вдоль ряда от рам 1 и 3."""
    l1, p1, l3, p3 = (HOLES[k] for k in ("Л1", "П1", "Л3", "П3"))
    ux, uy = (l3[0] - l1[0]) / dist(l1, l3), (l3[1] - l1[1]) / dist(l1, l3)   # направление ряда
    f = (-M.Y_MIN, M.Y_MAX - M.BAY)                                         # 1.18 спереди, 1.20 сзади
    lf = (l1[0] - f[0] * ux - M.OVH_L, l1[1] - f[0] * uy)
    rf = (p1[0] - f[0] * ux + M.OVH_R, p1[1] - f[0] * uy)
    rr = (p3[0] + f[1] * ux + M.OVH_R, p3[1] + f[1] * uy)
    lr = (l3[0] + f[1] * ux - M.OVH_L, l3[1] + f[1] * uy)
    return [lf, rf, rr, lr]


class Plan(Svg):
    """План в мм: u = X, z = Y (вглубь участка — вверх по листу)."""

    def dim(self, p, q, text, off=0.0, color="var(--dim)", tpos=0.5):
        """Размер между p и q (м), смещённый по нормали на off (мм); подпись по линии размера."""
        (x1, y1), (x2, y2) = (p[0] * 1000, p[1] * 1000), (q[0] * 1000, q[1] * 1000)
        L = math.hypot(x2 - x1, y2 - y1)
        nx, ny = -(y2 - y1) / L, (x2 - x1) / L
        a = (x1 + nx * off, y1 + ny * off)
        b = (x2 + nx * off, y2 + ny * off)
        k = self.k
        for e, f in ((p, a), (q, b)):
            if abs(off) > 1:
                sg = 1 if off > 0 else -1
                E, F = self.P(e[0] * 1000, e[1] * 1000), self.P(f[0] + nx * 60 * sg, f[1] + ny * 60 * sg)
                self.items.append(f'<line x1="{E[0]:.1f}" y1="{E[1]:.1f}" x2="{F[0]:.1f}" y2="{F[1]:.1f}" '
                                  f'stroke="{color}" stroke-width="{0.7 * self.k:.1f}" stroke-opacity="0.85"/>')
        A_, B_ = self.P(*a), self.P(*b)
        self.items.append(f'<line x1="{A_[0]:.1f}" y1="{A_[1]:.1f}" x2="{B_[0]:.1f}" y2="{B_[1]:.1f}" '
                          f'stroke="{color}" stroke-width="{1.1 * k:.1f}" marker-start="url(#ar)" marker-end="url(#ar)" '
                          f'style="color:{color}"/>')
        ang = math.degrees(math.atan2(-(B_[1] - A_[1]), B_[0] - A_[0]))
        if ang > 90:
            ang -= 180
        if ang < -90:
            ang += 180
        cx = A_[0] + (B_[0] - A_[0]) * tpos
        cy = A_[1] + (B_[1] - A_[1]) * tpos
        fs = 15 * k
        w = len(text) * fs * 0.6 + 6 * k
        self.items.append(f'<g transform="translate({cx:.1f} {cy:.1f}) rotate({-ang:.2f})">'
                          f'<rect x="{-w / 2:.1f}" y="{-fs * 1.05:.1f}" width="{w:.1f}" height="{fs * 1.1:.1f}" '
                          f'fill="var(--card)" opacity="0.92"/>'
                          f'<text x="0" y="{-fs * 0.18:.1f}" text-anchor="middle" style="fill:{color};font-size:{fs:.0f}px;'
                          f'font-weight:700;font-family:system-ui,sans-serif">{html.escape(text)}</text></g>')

    def mpoly(self, pts, fill, stroke, op=1.0, sw=1.0, dash=None):
        self.poly([(x * 1000, y * 1000) for x, y in pts], fill, stroke, op, sw * self.k, dash)

    def mtext(self, x, y, s, cls="lbs", anchor="start", color=None, size=None, bold=False):
        p = self.P(x * 1000, y * 1000)
        fs = (size or self.FS.get(cls, 18)) * self.k
        st = f"font-size:{fs:.0f}px" + (f";fill:{color}" if color else "") + (";font-weight:800" if bold else "")
        self.items.append(f'<text x="{p[0]:.1f}" y="{p[1]:.1f}" class="{cls}" text-anchor="{anchor}" '
                          f'style="{st}">{html.escape(s)}</text>')


def plan_svg():
    k = 10.0
    s = Plan(-1700, 7400, -1500, 7300, pad=60, k=k)
    road = "#64748b"
    # дорога и забор
    s.rect(-1700, -1450, 7400, -110, "#94a3b8", "none", 0.18)
    s.mtext(2.1, -1.1, "ДОРОГА · ВЪЕЗД", "lb", "middle", road, 20, True)
    s.line(B[0] * 1000, -100, 7400, -100, "ld")
    s.items.append(s.items.pop().replace('class="ld"', f'stroke="{road}" stroke-width="{3 * k:.0f}" stroke-dasharray="{4 * k:.0f} {6 * k:.0f}"'))
    s.mtext(6.0, -0.32, "забор", "dt", "middle", road)
    # площадка
    pc = plot_corners()
    s.mpoly(pc, "#cbd5e1", "var(--fg)", 0.25, 1.6)
    # опоры ворот 100×100 и полотно
    s.mpoly([(0, -0.1), (0.1, -0.1), (0.1, 0), (0, 0)], "#475569", "var(--fg)", 1, 0.8)
    s.mpoly([(4.1, -0.1), (4.2, -0.1), (4.2, 0), (4.1, 0)], "#475569", "var(--fg)", 1, 0.8)
    s.mpoly([(0.1, -0.07), (4.1, -0.07), (4.1, -0.03), (0.1, -0.03)], "#64748b", "none", 0.6)
    s.mtext(2.1, -0.36, "проём ворот 4.00, полотно → вправо", "dt", "middle")
    # коридор заезда
    dy = PLOT_D
    s.mpoly([(0.1, 0), (4.1, 0), (4.1 + dy * TAN, dy), (0.1 + dy * TAN, dy)], "none", "#16a34a", 1, 1.2, "40 30")
    s.mtext(2.25, 3.3, "коридор заезда 4.00", "dt", "middle", "#16a34a")
    # контур кровли
    s.mpoly(roof_corners(), "none", "#dc2626", 0.9, 1.3, "70 40")
    rc = roof_corners()
    s.mtext(rc[3][0] + 0.05, rc[3][1] + 0.12, "контур кровли 6.75 × 6.98", "dt", "start", "#dc2626")
    # оси рядов и рам
    l1, p1, l3, p3 = (HOLES[n] for n in ("Л1", "П1", "Л3", "П3"))
    for a_, b_ in ((l1, l3), (p1, p3), (l1, p1), (l3, p3)):
        ex = 0.45 / dist(a_, b_)
        q1 = (a_[0] - (b_[0] - a_[0]) * ex, a_[1] - (b_[1] - a_[1]) * ex)
        q2 = (b_[0] + (b_[0] - a_[0]) * ex, b_[1] + (b_[1] - a_[1]) * ex)
        s.line(q1[0] * 1000, q1[1] * 1000, q2[0] * 1000, q2[1] * 1000, "ax")
        s.items[-1] = s.items[-1].replace('class="ax"', f'class="ax" style="stroke:#dc2626;stroke-width:{0.9 * k:.1f};'
                                                         f'stroke-dasharray:{14 * k:.0f} {4 * k:.0f} {3 * k:.0f} {4 * k:.0f}"')
    # размеры
    blue, gold, purple, teal = "#0369a1", "#a16207", "#7e22ce", "#0f766e"
    # между колоннами — по граням (середины обращённых друг к другу граней), диагонали — между ближними рёбрами
    c, cd = col_marks(SHOW_COL), clear_dims()          # точки — по увеличенным колоннам, цифры — фактические
    s.dim(c["Л1"]["side"], c["П1"]["side"], f"{cd['cross1']:.3f}", off=-520, color=blue)
    s.dim(c["Л3"]["side"], c["П3"]["side"], f"{cd['cross3']:.3f}", off=480, color=blue)
    s.dim(c["Л1"]["end"], c["Л3"]["end"], f"{cd['alongL']:.3f}", off=520, color=blue)
    s.dim(c["П1"]["end"], c["П3"]["end"], f"{cd['alongR']:.3f}", off=-480, color=blue)
    s.dim(c["Л1"]["rib"], c["П3"]["rib"], f"{cd['d_l1p3']:.3f}", color=gold, tpos=0.3)
    s.dim(c["П1"]["rib"], c["Л3"]["rib"], f"{cd['d_p1l3']:.3f}", color=gold, tpos=0.3)
    s.dim(A, l1, f"{FROM_AB['Л1'][0]:.3f}", color=purple)
    s.dim(B, p1, f"{FROM_AB['П1'][1]:.3f}", color=purple)
    # привязки к кромкам площадки
    s.dim((3.2, 0.0), (3.2, l1[1]), "1.000", color=teal)
    yr = l3[1]
    s.dim((3.2 + yr * TAN, yr), (3.2 + PLOT_D * TAN, PLOT_D), "1.000", color=teal)
    ym = 2.9
    xl = ym * TAN                              # левая кромка площадки на высоте ym
    xa = l1[0] + (ym - l1[1]) * TAN            # ось левого ряда
    s.dim((xa, ym), (xl, ym), f"{CTRL['left']:.3f}", color=teal)
    xr = PLOT_W + ym * TAN
    xb = p1[0] + (ym - p1[1]) * TAN
    s.dim((xb, ym), (xr, ym), f"{CTRL['right']:.3f}", color=teal)
    s.dim((0, -0.62), (PLOT_W, -0.62), "площадка 5.40", color="var(--dim)")
    # лунки и колонны
    for n, (x, y) in HOLES.items():
        h = HOLE / 2 * SHOW_HOLE
        s.mpoly([(x - h, y - h), (x + h, y - h), (x + h, y + h), (x - h, y + h)], "#e5e7eb", "#0369a1", 1, 1.6)
        cb, ch = COL_B / 2 * SHOW_COL, COL_H / 2 * SHOW_COL
        s.mpoly([(x - cb, y - ch), (x + cb, y - ch), (x + cb, y + ch), (x - cb, y + ch)], "#2563eb", "#111", 1, 0.8)
        for key in ("side", "end", "rib"):
            q = s.P(*(v * 1000 for v in col_marks(SHOW_COL)[n][key]))
            s.items.append(f'<circle cx="{q[0]:.1f}" cy="{q[1]:.1f}" r="{3.2 * k:.0f}" '
                           f'fill="{"#a16207" if key == "rib" else "#0369a1"}" stroke="#fff" stroke-width="{0.8 * k:.0f}"/>')
        left = n.startswith("Л")
        s.mtext(x + (-0.36 if left else 0.36), y + 0.25, n, "lb", "end" if left else "start", None, 26, True)
    for nm, p in (("A", A), ("B", B)):
        q = s.P(p[0] * 1000, p[1] * 1000)
        s.items.append(f'<circle cx="{q[0]:.1f}" cy="{q[1]:.1f}" r="{4 * k:.0f}" fill="#ca8a04"/>')
        s.mtext(p[0] + (-0.1 if nm == "A" else 0.1), p[1] - 0.3, nm, "lb", "end" if nm == "A" else "start",
                "#a16207", 24, True)
    svg = s.svg("разбивочный план лунок")
    marker = ('<defs><marker id="ar" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" '
              'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="currentColor"/></marker></defs>')
    return svg.replace('aria-label="разбивочный план лунок">', 'aria-label="разбивочный план лунок">' + marker, 1)


def column_inset():
    """Лунка с колонной крупно: откуда мерить — середины граней и рёбра."""
    from nodes_drawing import Svg as _S
    s = _S(-200, 470, -215, 250, k=2.0)
    s.rect(-150, -150, 150, 150, "#e5e7eb", "#0369a1", 1, 2.5)
    s.rect(-50, -30, 50, 30, "#2563eb", "#111", 1, 1.2)
    for (u, z) in ((50, 0), (0, 30)):
        p = s.P(u, z)
        s.items.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="9" fill="#0369a1" stroke="#fff" stroke-width="2"/>')
    p = s.P(50, 30)
    s.items.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="9" fill="#a16207" stroke="#fff" stroke-width="2"/>')
    s.dim_h(-50, 50, -30, "100", off=40)
    s.dim_v(-50, -30, 30, "60", off=-34)
    s.leader(50, 0, 165, -70, "середина грани", "lbs", anchor="start")
    s.leader(0, 30, -20, 205, "середина грани", "lbs", anchor="start")
    s.leader(50, 30, 165, 120, "ребро (угол)", "lbs", anchor="start")
    s.text(-190, -200, "Л1 крупно; дорога внизу", "lbs")
    return s.svg("колонна в лунке — откуда мерить")


def build(final):
    rows = []
    for n, (x, y) in HOLES.items():
        rows.append(f"<tr><td><b>{n}</b></td><td class='n'>{x:+.3f}</td><td class='n'>{y:.3f}</td>"
                    f"<td class='n'>{FROM_AB[n][0]:.3f}</td><td class='n'>{FROM_AB[n][1]:.3f}</td></tr>")
    l1, p1, l3, p3 = (HOLES[n] for n in ("Л1", "П1", "Л3", "П3"))
    pc = plot_corners()
    ctrl = [
        ("Л1–П1 и Л3–П3 (поперёк, вдоль рам)", f"{CTRL['cross']:.3f}"),
        ("Л1–Л3 и П1–П3 (вдоль рядов)", f"{CTRL['along']:.3f}"),
        ("Диагональ Л1–П3", f"{CTRL['d_l1p3']:.3f}"),
        ("Диагональ П1–Л3", f"{CTRL['d_p1l3']:.3f}"),
        ("Ось Л1–П1 → передняя кромка площадки (по перпендикуляру)", f"{CTRL['front']:.3f}"),
        ("Ось Л3–П3 → задняя кромка площадки (по перпендикуляру)", f"{CTRL['rear']:.3f}"),
        ("Ось Л1–Л3 → левая кромка площадки, наружу (вдоль рамы)", f"{CTRL['left']:.3f}"),
        ("Ось П1–П3 → правая кромка площадки, внутрь (вдоль рамы)", f"{CTRL['right']:.3f}"),
        ("Диагонали площадки (от левого / правого переднего угла)",
         f"{dist(pc[0], pc[2]):.2f} / {dist(pc[1], pc[3]):.2f}"),
    ]
    crow = "".join(f"<tr><td>{a}</td><td class='n'>{b}</td></tr>" for a, b in ctrl)
    cd = clear_dims()
    cctrl = [
        ("Л1–П1 и Л3–П3: между внутренними гранями (по серединам граней)", f"{cd['cross1']:.3f}"),
        ("Л1–Л3 и П1–П3: между гранями вдоль ряда (по серединам граней)", f"{cd['alongL']:.3f}"),
        ("Диагональ Л1–П3: между ближними рёбрами", f"{cd['d_l1p3']:.3f}"),
        ("Диагональ П1–Л3: между ближними рёбрами", f"{cd['d_p1l3']:.3f}"),
    ]
    ccrow = "".join(f"<tr><td>{a}</td><td class='n'>{b}</td></tr>" for a, b in cctrl)
    # отметки: земля, щебень (из черновика), верх бетона, глубина
    ground = {"Л1": (-0.08, None), "П1": (-0.21, -0.09), "Л3": (-0.27, None), "П3": (-0.45, -0.27)}
    erows = []
    for (x, y), (nm, ztop, dep, zg) in M.COLUMN_BASES.items():
        g_, sh = ground[nm]
        zbot = ztop - dep
        zcb = zbot + GAP
        Lc = Z_COL_TOP - zcb
        erows.append(f"<tr><td><b>{nm}</b></td><td class='n'>{g_:+.2f}</td><td class='n'>{'—' if sh is None else f'{sh:+.2f}'}</td>"
                     f"<td class='n'>{ztop:+.2f}</td><td class='n'>{dep:.2f}</td><td class='n'>{zbot:+.2f}</td>"
                     f"<td class='n'>{zcb:+.2f}</td><td class='n'>{dep - GAP:.2f}</td><td class='n'><b>{Lc:.3f}</b></td></tr>")
    order = ["Л1", "П1", "Л3", "П3"]
    erows = [r for o in order for r in erows if f"<b>{o}</b>" in r]
    css = NODE_CSS + """
table td.n,table th.n{text-align:right;font-variant-numeric:tabular-nums}
.leg{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13px;color:var(--muted);margin:6px 0 0}
.leg span b{display:inline-block;width:22px;height:0;border-top:3px solid;vertical-align:middle;margin-right:6px}
@media print{.plan{break-inside:avoid}}
"""
    page = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Разбивка лунок</title>
<style>{css}</style></head><body><main>
<h1>Разбивочный план лунок</h1>
<p class="sub">Навес 5.45 × 4.60 м · вид сверху, дорога внизу · размеры в метрах · косина площадки 2.87°.
На плане между колоннами — расстояния в свету: между гранями колонн (по серединам граней), диагонали — между ближними
рёбрами. Привязка центров лунок для разбивки до бурения — в таблицах ниже.</p>
<div class="card plan">{plan_svg()}
<div class="leg"><span><b style="border-color:#0369a1"></b>между гранями колонн (по серединам граней)</span>
<span><b style="border-color:#a16207"></b>диагонали между ближними рёбрами колонн</span>
<span><b style="border-color:#7e22ce"></b>засечки от опор ворот A и B до центров лунок</span>
<span><b style="border-color:#0f766e"></b>привязка осей рядов и рам к кромкам площадки</span>
<span><b style="border-color:#dc2626;border-top-style:dashed"></b>оси рядов и рам, контур кровли</span>
<span><b style="border-color:#16a34a;border-top-style:dashed"></b>коридор заезда</span></div>
<p class="note" style="margin:6px 0 0">Лунки и колонны на плане увеличены (не в масштабе), чтобы были видны грани и рёбра,
от которых идут размеры: синие точки — середины граней, жёлтые — ближние рёбра.</p></div>

<div class="grid2 c"><div class="card">
<h3>Контроль колонн по граням (при установке и после бетонирования)</h3>
<table><thead><tr><th>Размер в свету</th><th class="n">м</th></tr></thead><tbody>{ccrow}</tbody></table>
<p>Рулетку прикладывать к <b>середине грани</b> (синие точки) или к <b>ребру</b> — углу колонны, ближнему к
другой колонне (жёлтая точка). Колонна 100×60: сторона 100 — вдоль рамы (параллельно передней кромке), 60 — вдоль
ряда. Допуск ±10 мм; обе диагонали должны сойтись.</p>
</div><div class="card">{column_inset()}</div></div>

<div class="grid2"><div class="card">
<h3>Привязка центров лунок</h3>
<table><thead><tr><th>Лунка</th><th class="n">X от A, м</th><th class="n">Y от линии опор, м</th>
<th class="n">от точки A, м</th><th class="n">от точки B, м</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p><b>A</b> — задний левый угол левой опоры ворот (левый передний угол площадки), <b>B</b> — задний правый угол правой
опоры (4.20 м от A по линии задних граней опор). X — вдоль этой линии вправо, Y — перпендикулярно вглубь участка.
Ряды лунок параллельны боковым сторонам площадки: левый — 0.40 м наружу, правый — 0.35 м внутрь; передний и задний —
1.00 м внутрь от передней и задней кромок.</p>
</div><div class="card">
<h3>Контроль разбивки центров лунок (до бурения)</h3>
<table><thead><tr><th>Контрольный размер</th><th class="n">м</th></tr></thead><tbody>{crow}</tbody></table>
</div></div>

<div class="card">
<h3>Порядок разбивки</h3>
<ol>
<li>От точек <b>A</b> и <b>B</b> двумя рулетками засечь центры <b>Л1</b> ({FROM_AB['Л1'][0]:.3f} от A, {FROM_AB['Л1'][1]:.3f} от B)
и <b>П1</b> ({FROM_AB['П1'][0]:.3f} от A, {FROM_AB['П1'][1]:.3f} от B). Проверить Л1–П1 = {CTRL['cross']:.3f}.</li>
<li>От Л1 и П1 засечь <b>Л3</b> и <b>П3</b>: {CTRL['along']:.3f} вдоль ряда и по диагоналям Л1–П3 = {CTRL['d_l1p3']:.3f},
П1–Л3 = {CTRL['d_p1l3']:.3f}. Проверить Л3–П3 = {CTRL['cross']:.3f}; для контроля — Л3 и П3 от A и B по таблице.</li>
<li>Если обе диагонали сошлись в пределах ±10 мм — разбивка верна.</li>
<li>Центр лунки отметить колышком и <b>отноской</b>: две вешки за пределами лунки по оси ряда и две — по оси рамы
(колышек уйдёт вместе с грунтом при бурении). По относкам потом выставляется колонна.</li>
<li>Лунка 300×300, стороны — параллельно передней кромке площадки. Колонна 100×60 стоит по центру лунки: сторона
100 — вдоль рамы (параллельно передней кромке), сторона 60 — вдоль ряда.</li>
</ol></div>

<div class="card">
<h3>Отметки и глубина лунок</h3>
<table><thead><tr><th>Лунка</th><th class="n">Земля</th><th class="n">Щебень</th><th class="n">Верх бетона</th>
<th class="n">Глубина бетона</th><th class="n">Дно лунки</th><th class="n">Низ колонны</th><th class="n">Колонна в бетоне</th>
<th class="n">Длина колонны</th></tr></thead><tbody>{''.join(erows)}</tbody></table>
<ul>
<li>Ноль проекта — верх щебня у левой опоры ворот (левый передний угол площадки); там же земля на −0.05. Площадка не
выравнивается: перепад по земле 37 см, щебень — только вдоль правого ряда.</li>
<li>Верх бетона у левых лунок — на 2 см выше земли, у правых — в уровень щебня. Глубина бетона у правых лунок больше
(1.30 и 1.35): их верх привязан к щебню, лежащему поверх земли. Если при бурении — супесь или насыпь, бурить глубже
(колонну тогда удлинить на столько же).</li>
<li>Колонна — на всю глубину лунки: на дно — бетонная плитка ≈ {PAVER * 100:.0f} см, на неё — колонна; низ колонны
в {GAP * 100:.0f} см над дном, высоту добрать стальными подкладками так, чтобы верх опорной пластины был на +{Z_COL_TOP:.3f}.
Арматура в лунках не нужна.</li>
<li>Вертикаль и положение по относкам — временными подкосами из досок до набора прочности бетона (3–7 суток).
Отметку верха контролировать нивелиром: после заливки регулировки нет.</li>
</ul></div>
</main></body></html>"""
    return page


def main():
    final = json.loads((OUT / "final_design.json").read_text())
    (OUT / "razbivka.html").write_text(build(final), encoding="utf-8")
    print("output/razbivka.html")


if __name__ == "__main__":
    main()
