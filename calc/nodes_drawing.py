"""Чертежи узлов (output/uzly.html): А — оголовок колонны, Б — опора средней рамы на столик цеховой боковой
фермы (с аксонометрией), В — конец боковой фермы у колонны; общий вид фермы и порядок сборки цех / объект.

Размеры в мм, отметки от верха щебня (±0.000). Узлы показаны для левого ряда колонн (x = 0);
у правого ряда — зеркально. Сечения берутся из output/final_design.json.
"""
from __future__ import annotations

import html
import json
import math
from pathlib import Path

import model as M
from drawing import CSS
from report_data import sec_by_name

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"

T12 = math.tan(M.SLOPE)
C12 = math.cos(M.SLOPE)
ALPHA_SD = None  # угол раскоса боковой фермы к горизонту, задаётся по геометрии

SEAM = "#3b0764"   # сварные швы — тёмно-фиолетовые

# цвета элементов (как на общем чертеже)
COL = {"col": "#2563eb", "raf": "#0f766e", "tie": "#b45309", "sd": "#dc2626", "sb": "#0891b2",
       "plate": "#6b7280", "lath": "#db2777", "stub": "#2563eb", "kp": "#7c3aed", "ge": "#ea580c", "gk": "#65a30d"}

NODE_CSS = CSS + """
svg.nd{width:100%;height:auto;display:block;background:var(--card)}
.ax{stroke:var(--dim);stroke-width:0.6;stroke-dasharray:10 3 2 3;fill:none}
.dl{stroke:var(--dim);stroke-width:0.6;fill:none}
.dt{fill:var(--dim);font-size:18px;font-family:system-ui,sans-serif}
.lb{fill:var(--fg);font-size:21px;font-family:system-ui,sans-serif}
.lbs{fill:var(--muted);font-size:18px;font-family:system-ui,sans-serif}
.ld{stroke:var(--muted);stroke-width:0.6;fill:none}
.wm{fill:#f59e0b;stroke:none}
.wn{fill:#f59e0b;font-size:11px;font-weight:700;font-family:system-ui,sans-serif}
.grid2{display:grid;grid-template-columns:1fr;gap:12px}
@media(min-width:900px){.grid2{grid-template-columns:1.35fr 1fr}}
.pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:2px 10px;margin:2px 4px 2px 0;font-size:13px}
h3{font-size:15px;margin:14px 0 6px}
ol li,ul li{margin:3px 0}
.wk{display:inline-block;min-width:22px;text-align:center;border-radius:4px;background:#f59e0b;color:#111;font-weight:700;margin-right:6px}
.mmrow{display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.mmimg{flex:0 1 420px;min-width:260px}.mmtxt{flex:1 1 260px;font-size:14px}.mmtxt p{margin:6px 0}
svg.mm{background:transparent}
@media print{
  body{background:#fff}
  .mmimg{flex:0 0 46%}
  main{max-width:none;padding:0}
  .grid2{grid-template-columns:1fr}
  .grid2 > .card:nth-child(2){width:62%;margin:0 auto}
  h2.pb{break-before:page;page-break-before:always}
  .grid2.c{grid-template-columns:1.8fr 1fr}
  .grid2.c > .card:nth-child(2){width:auto;margin:0}
  .card,.grid2,tr,li{break-inside:avoid;page-break-inside:avoid}
  h2,h3{break-after:avoid;page-break-after:avoid}
  h2{break-before:auto}
}
"""


class Svg:
    """Вид в мм: u — горизонталь чертежа, z — отметка (мм)."""

    FS = {"lb": 21, "lbs": 18, "dt": 18}

    def __init__(self, umin, umax, zmin, zmax, pad=40, W=None, k=1.0):
        self.k = k                               # масштаб шрифтов и маркеров (для крупных видов)
        pad = pad * k
        self.umin, self.umax, self.zmin, self.zmax, self.pad = umin, umax, zmin, zmax, pad
        self.w = umax - umin + 2 * pad
        self.h = zmax - zmin + 2 * pad
        self.items = []

    def P(self, u, z):
        return (u - self.umin + self.pad, self.zmax - z + self.pad)

    def poly(self, pts, fill, stroke="none", op=1.0, sw=0.8, dash=None, cls=None):
        s = " ".join(f"{self.P(u, z)[0]:.1f},{self.P(u, z)[1]:.1f}" for u, z in pts)
        d = f' stroke-dasharray="{dash}"' if dash else ""
        c = f' class="{cls}"' if cls else ""
        self.items.append(f'<polygon points="{s}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" '
                          f'stroke-width="{sw}"{d}{c}/>')

    def rect(self, u1, z1, u2, z2, fill, stroke="none", op=1.0, sw=0.8, dash=None):
        self.poly([(u1, z1), (u2, z1), (u2, z2), (u1, z2)], fill, stroke, op, sw, dash)

    def tube(self, pts_outer, t, fill):
        """Сечение/вид трубы: заливка + внутренний контур (стенка)."""
        self.poly(pts_outer, fill, "#0006", 0.9, 0.6)

    def line(self, u1, z1, u2, z2, cls="ax"):
        a, b = self.P(u1, z1), self.P(u2, z2)
        self.items.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" class="{cls}"/>')

    def text(self, u, z, s, cls="lb", anchor="start"):
        p = self.P(u, z)
        st = f' style="font-size:{self.FS.get(cls, 18) * self.k:.0f}px"' if self.k != 1 else ""
        self.items.append(f'<text x="{p[0]:.1f}" y="{p[1]:.1f}" class="{cls}" text-anchor="{anchor}"{st}>{html.escape(s)}</text>')

    def leader(self, u1, z1, u2, z2, s, cls="lb", anchor=None):
        """Выноска: точка на детали (u1, z1) → излом (u2, z2) → полка под текстом.
        Полка и текст продолжают выноску в её направлении (влево или вправо)."""
        k = self.k
        left = (anchor == "end") if anchor else (u2 < u1)
        w = len(s) * self.FS.get(cls, 18) * 0.56 * k + 4 * k
        u3 = u2 - w if left else u2 + w
        a, b, c = self.P(u1, z1), self.P(u2, z2), self.P(u3, z2)
        self.items.append(f'<polyline points="{a[0]:.1f},{a[1]:.1f} {b[0]:.1f},{b[1]:.1f} {c[0]:.1f},{c[1]:.1f}" class="ld"/>')
        self.items.append(f'<circle cx="{a[0]:.1f}" cy="{a[1]:.1f}" r="{2.2 * k:.1f}" fill="var(--muted)"/>')
        self.text(u2 - 3 * k if left else u2 + 3 * k, z2 + 4 * k, s, cls, "end" if left else "start")

    def seam(self, pts, w=4.5, closed=False):
        """Сварной шов — толстая тёмно-фиолетовая линия по кромке соединения."""
        pp = " ".join(f"{self.P(u, z)[0]:.1f},{self.P(u, z)[1]:.1f}" for u, z in pts)
        tag = "polygon" if closed else "polyline"
        self.items.append(f'<{tag} points="{pp}" fill="none" stroke="{SEAM}" stroke-width="{w * self.k:.1f}" '
                          f'stroke-linecap="round" stroke-linejoin="round" stroke-opacity="0.95"/>')

    def weld(self, u, z, n):
        """Маркер шва с номером."""
        p = self.P(u, z)
        k = self.k
        self.items.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{12 * k:.1f}" class="wm"/>')
        self.items.append(f'<text x="{p[0]:.1f}" y="{p[1]+6 * k:.1f}" text-anchor="middle" '
                          f'style="fill:#111;font-size:{17 * k:.0f}px;font-weight:700">{n}</text>')

    def dim_h(self, u1, u2, z, s, off=0):
        a, b = self.P(u1, z), self.P(u2, z)
        k = self.k
        self.items.append(f'<line x1="{a[0]:.1f}" y1="{a[1]+off:.1f}" x2="{b[0]:.1f}" y2="{b[1]+off:.1f}" class="dl"/>')
        for q in (a, b):
            self.items.append(f'<line x1="{q[0]:.1f}" y1="{q[1]+off-4*k:.1f}" x2="{q[0]:.1f}" y2="{q[1]+off+4*k:.1f}" class="dl"/>')
        st = f' style="font-size:{18 * k:.0f}px"' if k != 1 else ""
        self.items.append(f'<text x="{(a[0]+b[0])/2:.1f}" y="{a[1]+off-3*k:.1f}" class="dt" text-anchor="middle"{st}>{s}</text>')

    def dim_v(self, u, z1, z2, s, off=0, anchor="end"):
        a, b = self.P(u, z1), self.P(u, z2)
        k = self.k
        self.items.append(f'<line x1="{a[0]+off:.1f}" y1="{a[1]:.1f}" x2="{b[0]+off:.1f}" y2="{b[1]:.1f}" class="dl"/>')
        for q in (a, b):
            self.items.append(f'<line x1="{q[0]+off-4*k:.1f}" y1="{q[1]:.1f}" x2="{q[0]+off+4*k:.1f}" y2="{q[1]:.1f}" class="dl"/>')
        dx = (-4 if anchor == "end" else 4) * k
        st = f' style="font-size:{18 * k:.0f}px"' if k != 1 else ""
        self.items.append(f'<text x="{a[0]+off+dx:.1f}" y="{(a[1]+b[1])/2+4*k:.1f}" class="dt" text-anchor="{anchor}"{st}>{s}</text>')

    def svg(self, label):
        return (f'<svg viewBox="0 0 {self.w:.0f} {self.h:.0f}" class="nd" role="img" aria-label="{html.escape(label)}">'
                + "".join(self.items) + "</svg>")


def geometry(groups):
    col = sec_by_name(groups["col"])
    raf = sec_by_name(groups["raf"])
    tie = sec_by_name(groups["tie"])
    stub = sec_by_name(groups["stub"])
    sd = sec_by_name(groups["sd"])
    sb = sec_by_name(groups["sb"])
    lath = sec_by_name(groups["lath"])
    g = dict(col=col, raf=raf, tie=tie, stub=stub, sd=sd, sb=sb, lath=lath)
    for k in ("ge", "gk", "le", "lr"):
        if k in groups:
            g[k] = sec_by_name(groups[k])
    mm = lambda v: v * 1000
    g["Hc"], g["Bc"] = mm(col.h), mm(col.b)            # колонна: 100 в плоскости рамы, 60 поперёк
    g["Hr"], g["Br"] = mm(raf.h), mm(raf.b)
    g["Ht"], g["Bt"] = mm(tie.h), mm(tie.b)
    g["Hs"], g["Bs"] = mm(stub.h), mm(stub.b)
    g["Hd"] = mm(sd.h)
    g["Hb"] = mm(sb.h)
    tg = M.shop_truss_geom(col.b, sb.h, sd.h)
    g["tg"] = {k: (v * 1000 if k != "alpha" else v) for k, v in tg.items()}   # мм
    g["alpha"] = tg["alpha"]
    return g


def z_axis(x):          # ось стропила левого ската, мм
    return 3100 + T12 * x


def z_bot(x, Hr):       # низ стропила
    return z_axis(x) - Hr / 2 / C12


# ---------------- узел А ----------------
GUSSET = dict(x1=-50, x2=200, zb=2920)   # фасонка узла А: от наружной грани колонны до 200 мм по затяжке
CAP = dict(len=140, t=6)
PLATE_B = dict(w=80)                      # опорный столик фермы: ширина поперёк фермы (вдоль рамы), мм


def node_A(g):
    """Узел А — вид в плоскости рамы."""
    Hr, Ht, Hc = g["Hr"], g["Ht"], g["Hc"]
    s = Svg(-560, 700, 2780, 3330)
    x1g, x2g, zbg = GUSSET["x1"], GUSSET["x2"], GUSSET["zb"]
    zb_col = 2780
    cap_t = CAP["t"]
    top = lambda x: z_bot(x, Hr) - cap_t
    s.poly([(-Hc / 2, zb_col), (Hc / 2, zb_col), (Hc / 2, top(Hc / 2)), (-Hc / 2, top(-Hc / 2))], COL["col"], "#0008", 0.9)
    L = CAP["len"] / 2
    s.poly([(-L, top(-L)), (L, top(L)), (L, z_bot(L, Hr)), (-L, z_bot(-L, Hr))], COL["plate"], "#000a", 1)
    xa, xb = -400, 400
    s.poly([(xa, z_bot(xa, Hr)), (xb, z_bot(xb, Hr)), (xb, z_bot(xb, Hr) + Hr / C12), (xa, z_bot(xa, Hr) + Hr / C12)],
           COL["raf"], "#0008", 0.9)
    for x in (-114, 228):
        zt = z_bot(x, Hr) + Hr / C12
        a = g["lath"].h * 1000
        s.poly([(x - a / 2, zt), (x + a / 2, zt), (x + a / 2, zt + a), (x - a / 2, zt + a)], COL["lath"], "#0008", 0.9)
    s.rect(Hc / 2, 3000 - Ht / 2, 400, 3000 + Ht / 2, COL["tie"], "#0008", 0.9)
    gpts = [(x1g, zbg), (x2g, zbg), (x2g, z_axis(x2g)), (x1g, z_axis(x1g))]
    s.poly(gpts, "#9ca3af", "#111", 0.55, 1.2)
    s.line(-420, z_axis(-420), 420, z_axis(420))
    s.line(-420, 3000, 420, 3000)
    s.line(0, 2780, 0, 3290)
    s.items.append(f'<circle cx="{s.P(0, 3100)[0]:.1f}" cy="{s.P(0, 3100)[1]:.1f}" r="3" fill="var(--fg)"/>')
    s.dim_h(x1g, x2g, zbg, f"{x2g - x1g:.0f}", off=22)
    s.dim_v(x2g, zbg, z_axis(x2g), f"{z_axis(x2g) - zbg:.0f}", off=26, anchor="start")
    s.dim_v(x1g, zbg, z_axis(x1g), f"{z_axis(x1g) - zbg:.0f}", off=-30)
    s.dim_v(640, 3000, 3100, "e=100", off=0, anchor="end")
    s.text(420, 3008, "ось затяжки +3.000", "dt")
    s.text(8, 3318, "ось колонны", "dt")
    s.text(10, 3080, "+3.100", "dt")
    # швы
    seams_frame_node(s, g, Hc / 2, x1g, x2g, zbg, top, cap_zb=None)
    s.leader(-150, z_bot(-150, Hr) + Hr / C12 - 4, -200, 3300, f"стропило □{g['raf'].name}", "lb")
    s.leader(-L + 5, (top(-L + 5) + z_bot(-L + 5, Hr)) / 2, -300, 3130, f"опорная пластина {CAP['len']}×60×{cap_t}", "lbs")
    s.leader(-Hc / 2, 2830, -300, 2830, f"колонна □{g['col'].name}")
    s.leader(360, 3000 + Ht / 2, 470, 3070, f"затяжка □{g['tie'].name}")
    s.leader(160, 2935, 250, 2840, "фасонка t=5 — 2 шт., с обеих сторон", "lb")
    s.leader(228, z_bot(228, Hr) + Hr / C12 + 20, 330, 3312, f"обрешётина □{g['lath'].name}", "lbs")
    s.weld(Hc / 2 + 14, 3000 - Ht / 2 - 14, 1)
    s.weld(-L - 16, top(-L) - 4, 2)
    s.weld(x2g + 16, 2975, 3)
    s.weld(x1g - 16, 2960, 3)
    return s.svg("узел А — вид в плоскости рамы")


def seams_frame_node(s, g, xf, x1g, x2g, zbg, top, cap_zb=None):
    """Швы узла рамы на опорной пластине (узлы А и Б), вид в плоскости рамы.
    xf — полуширина колонны/стойки в плоскости рамы; x1g…x2g, zbg — фасонка."""
    Hr, Ht = g["Hr"], g["Ht"]
    L = CAP["len"] / 2
    s.seam([(xf, 3000 - Ht / 2), (xf, 3000 + Ht / 2)])                          # 1: торец затяжки
    s.seam([(-xf, top(-xf)), (xf, top(xf))], w=3.5)                             # 2: колонна — пластина
    for x in (-L, L):                                                           # 2: пластина — стропило
        s.seam([(x, top(x)), (x, z_bot(x, Hr))])
    # 3: фасонка — только по наружным кромкам (доступны снаружи и после установки второй фасонки):
    #    вертикальная кромка и низ — к колонне, верх — к стропилу, торцевая кромка — поперёк затяжки.
    #    Рёбра затяжки под фасонкой не обвариваются: между фасонками доступа нет.
    s.seam([(x1g, zbg), (x1g, z_axis(x1g))])
    s.seam([(x1g, zbg), (xf, zbg)])
    s.seam([(x1g, z_axis(x1g)), (x2g, z_axis(x2g))])
    s.seam([(x2g, 3000 - Ht / 2), (x2g, 3000 + Ht / 2)])


def node_A_section(g):
    """Узел А — разрез по оси колонны, вид со стороны пролёта."""
    Hr, Ht, Bc = g["Hr"], g["Ht"], g["Bc"]
    B = Bc
    s = Svg(-330, 520, 2780, 3330)
    zb_col = 2780
    tp = 5
    zb = z_bot(0, Hr)
    zcap = zb - CAP["t"]
    tc = g["col"].t * 1000
    for u1, u2 in ((-B / 2, -B / 2 + tc), (B / 2 - tc, B / 2)):
        s.rect(u1, zb_col, u2, zcap, COL["col"], "#000a", 1, 0.6)
    s.line(-B / 2 + tc, zb_col, -B / 2 + tc, zcap, "ld")
    s.line(B / 2 - tc, zb_col, B / 2 - tc, zcap, "ld")
    s.rect(-B / 2 - 0.1, zcap, B / 2 + 0.1, zb, COL["plate"], "#000a", 1)
    s.rect(-g["Br"] / 2, zb, g["Br"] / 2, zb + Hr / C12, COL["raf"], "#0008", 0.9)
    tw = g["raf"].t * 1000
    s.rect(-g["Br"] / 2 + tw, zb + tw, g["Br"] / 2 - tw, zb + Hr / C12 - tw, "var(--card)", "none")
    s.rect(-g["Bt"] / 2, 3000 - Ht / 2, g["Bt"] / 2, 3000 + Ht / 2, "none", COL["tie"], 1, 1.6, dash="6 4")
    ztop = z_axis(0)
    for sgn in (-1, 1):
        u1, u2 = sgn * B / 2, sgn * (B / 2 + tp)
        s.rect(min(u1, u2), GUSSET["zb"], max(u1, u2), ztop, "#6b7280", "#111", 1, 0.8)
    # швы: колонна — опорная пластина; фасонки — к колонне по низу; к стропилу по верху
    s.seam([(-B / 2, zcap), (B / 2, zcap)], w=3.5)
    for sgn in (-1, 1):
        s.seam([(sgn * B / 2, GUSSET["zb"]), (sgn * (B / 2 + tp), GUSSET["zb"])], w=5)
        s.seam([(sgn * (B / 2 + tp), zb), (sgn * (B / 2 + tp), zb + 12)], w=5)
    s.leader(g["Br"] / 2, zb + Hr / C12 - 20, 130, 3265, f"стропило □{g['raf'].name}")
    s.leader(B / 2 + 0.1, zb - 3, 130, 3190, "опорная пластина", "lbs")
    s.leader(g["Bt"] / 2, 3000 + 10, 130, 3110, "затяжка — вне разреза (пунктир)", "lbs")
    s.leader(B / 2 + tp, GUSSET["zb"] + 30, 130, 2960, "фасонки t=5", "lbs")
    s.leader(B / 2, 2850, 130, 2850, f"колонна □{g['col'].name} (рассечена вдоль)", "lbs")
    s.dim_h(-B / 2 - tp, B / 2 + tp, GUSSET["zb"], f"{B + 2 * tp:.0f}", off=18)
    s.dim_h(-B / 2, B / 2, zb_col, f"{B:.0f}", off=16)
    s.line(0, 2790, 0, 3290)
    s.text(-320, 3322, "разрез по оси колонны, вид со стороны пролёта", "lbs")
    s.weld(-B / 2 - tp - 18, GUSSET["zb"] + 6, 3)
    s.weld(-B / 2 - 18, zcap - 8, 2)
    return s.svg("узел А — разрез поперёк рамы")


# ---------------- узел Б ----------------
def gusset_B(g):
    """Фасонка узла Б: от наружной грани стойки до 200 мм по затяжке, низ — по низу стойки (верх столика)."""
    tg = g["tg"]
    return dict(x1=-g["Hs"] / 2, x2=GUSSET["x2"], zb=tg["plate_top"])


def node_B(g):
    """Узел Б — вид в плоскости средней рамы."""
    Hr, Ht, Hs = g["Hr"], g["Ht"], g["Hs"]
    tg = g["tg"]
    gb = gusset_B(g)
    s = Svg(-560, 700, 2740, 3330)
    zpt, zpb = tg["plate_top"], tg["z_pb"]
    cap_t = CAP["t"]
    top = lambda x: z_bot(x, Hr) - cap_t
    # раскосы фермы — уходят от зрителя и к зрителю (из плоскости чертежа), под столиком
    s.rect(-g["Hd"] / 2, 2740, g["Hd"] / 2, zpb, COL["sd"], "#0008", 0.35)
    s.line(-g["Hd"] / 2, 2740, -g["Hd"] / 2, zpb, "ld")
    # столик фермы
    w = PLATE_B["w"]
    s.rect(-w / 2, zpb, w / 2, zpt, COL["plate"], "#000a", 1)
    # стойка-вставка
    s.poly([(-Hs / 2, zpt), (Hs / 2, zpt), (Hs / 2, top(Hs / 2)), (-Hs / 2, top(-Hs / 2))], COL["stub"], "#0008", 0.9)
    L = CAP["len"] / 2
    s.poly([(-L, top(-L)), (L, top(L)), (L, z_bot(L, Hr)), (-L, z_bot(-L, Hr))], COL["plate"], "#000a", 1)
    xa, xb = -400, 400
    s.poly([(xa, z_bot(xa, Hr)), (xb, z_bot(xb, Hr)), (xb, z_bot(xb, Hr) + Hr / C12), (xa, z_bot(xa, Hr) + Hr / C12)],
           COL["raf"], "#0008", 0.9)
    s.rect(Hs / 2, 3000 - Ht / 2, 400, 3000 + Ht / 2, COL["tie"], "#0008", 0.9)
    gpts = [(gb["x1"], gb["zb"]), (gb["x2"], gb["zb"]), (gb["x2"], z_axis(gb["x2"])), (gb["x1"], z_axis(gb["x1"]))]
    s.poly(gpts, "#9ca3af", "#111", 0.55, 1.2)
    s.line(-420, z_axis(-420), 420, z_axis(420))
    s.line(-420, 3000, 420, 3000)
    s.line(0, 2750, 0, 3290)
    s.items.append(f'<circle cx="{s.P(0, 3100)[0]:.1f}" cy="{s.P(0, 3100)[1]:.1f}" r="3" fill="var(--fg)"/>')
    s.dim_h(gb["x1"], gb["x2"], gb["zb"], f"{gb['x2'] - gb['x1']:.0f}", off=40)
    s.dim_v(gb["x2"], gb["zb"], z_axis(gb["x2"]), f"{z_axis(gb['x2']) - gb['zb']:.0f}", off=26, anchor="start")
    s.dim_v(gb["x1"], gb["zb"], z_axis(gb["x1"]), f"{z_axis(gb['x1']) - gb['zb']:.0f}", off=-62)
    s.dim_h(-w / 2, w / 2, zpb, f"{w:.0f}", off=48)
    s.text(420, 3008, "ось затяжки +3.000", "dt")
    s.text(8, 3318, "ось стойки", "dt")
    s.text(10, 3080, "+3.100", "dt")
    s.text(240, zpt - 38, f"верх столика +{zpt/1000:.3f}", "dt")
    seams_frame_node(s, g, Hs / 2, gb["x1"], gb["x2"], gb["zb"], top)
    s.seam([(-w / 2 + 2, zpt), (w / 2 - 2, zpt)], w=5)                           # 4: к столику (объект)
    s.leader(-150, z_bot(-150, Hr) + Hr / C12 - 4, -200, 3300, f"стропило □{g['raf'].name}", "lb")
    s.leader(-L + 5, (top(-L + 5) + z_bot(-L + 5, Hr)) / 2, -300, 3130, f"опорная пластина {CAP['len']}×60×{cap_t}", "lbs")
    s.leader(-Hs / 2, 2960, -250, 2930, f"стойка-вставка □{g['stub'].name}")
    s.leader(-w / 2, (zpt + zpb) / 2, -230, 2870, f"опорный столик фермы {tg['plate_len']:.0f}×{w:.0f}×{tg['plate_t']:.0f}", "lbs")
    s.leader(-g["Hd"] / 2, 2790, -130, 2770, f"раскосы фермы □{g['sd'].name} (из плоскости)", "lbs")
    s.leader(360, 3000 + Ht / 2, 470, 3070, f"затяжка □{g['tie'].name}")
    s.leader(160, 2945, 250, 2825, "фасонка t=5 — 2 шт., с обеих сторон", "lb")
    s.weld(Hs / 2 + 14, 3000 - Ht / 2 - 14, 1)
    s.weld(-L - 16, top(-L) - 4, 2)
    s.weld(gb["x2"] + 16, 2975, 3)
    s.weld(gb["x1"] - 16, 2995, 3)
    s.weld(-w / 2 - 16, zpt - 8, 4)
    return s.svg("узел Б — вид в плоскости средней рамы")


def node_B_section(g):
    """Узел Б — разрез по оси стойки поперёк рамы (в плоскости боковой фермы), вид со стороны пролёта."""
    Hr, Ht = g["Hr"], g["Ht"]
    tg = g["tg"]
    B = g["Bs"]
    s = Svg(-470, 470, 2690, 3330)
    tp = 5
    zb = z_bot(0, Hr)
    zcap = zb - CAP["t"]
    zpt, zpb = tg["plate_top"], tg["z_pb"]
    a = g["alpha"]
    ta = math.tan(a)
    Hd = g["Hd"]
    foot = tg["foot"]
    # раскосы — рассечены вдоль (в плоскости разреза): верхняя и нижняя стенки, внутри пусто
    td = g["sd"].t * 1000 / math.cos(a)
    yb = 440                                    # обрыв
    for sgn in (-1, 1):
        lower = [(0, zpb), (sgn * yb, zpb - yb * ta)]
        upper = [(sgn * foot, zpb), (sgn * yb, zpb - (yb - foot) * ta)]
        for (p1, p2), inward in ((lower, 1), (upper, -1)):
            (u1, z1), (u2, z2) = p1, p2
            s.poly([(u1, z1), (u2, z2), (u2, z2 + inward * td), (u1, z1 + inward * td)], COL["sd"], "#000a", 1, 0.6)
        s.line(sgn * yb, zpb - yb * ta, sgn * yb, zpb - (yb - foot) * ta, "ld")
    # столик — рассечён вдоль
    Lp = tg["plate_len"]
    s.rect(-Lp / 2, zpb, Lp / 2, zpt, COL["plate"], "#000a", 1)
    # стойка (рассечена вдоль) и фасонки (рассечены поперёк)
    tc = g["stub"].t * 1000
    for u1, u2 in ((-B / 2, -B / 2 + tc), (B / 2 - tc, B / 2)):
        s.rect(u1, zpt, u2, zcap, COL["stub"], "#000a", 1, 0.6)
    s.rect(-B / 2 - 0.1, zcap, B / 2 + 0.1, zb, COL["plate"], "#000a", 1)
    s.rect(-g["Br"] / 2, zb, g["Br"] / 2, zb + Hr / C12, COL["raf"], "#0008", 0.9)
    tw = g["raf"].t * 1000
    s.rect(-g["Br"] / 2 + tw, zb + tw, g["Br"] / 2 - tw, zb + Hr / C12 - tw, "var(--card)", "none")
    s.rect(-g["Bt"] / 2, 3000 - Ht / 2, g["Bt"] / 2, 3000 + Ht / 2, "none", COL["tie"], 1, 1.6, dash="6 4")
    ztop = z_axis(0)
    for sgn in (-1, 1):
        u1, u2 = sgn * B / 2, sgn * (B / 2 + tp)
        s.rect(min(u1, u2), zpt, max(u1, u2), ztop, "#6b7280", "#111", 1, 0.8)
    # оси раскосов и точка пересечения
    za = tg["apex_z"]
    s.line(-yb, za - yb * ta, 0, za)
    s.line(0, za, yb, za - yb * ta)
    s.line(0, 2700, 0, 3290)
    s.items.append(f'<circle cx="{s.P(0, za)[0]:.1f}" cy="{s.P(0, za)[1]:.1f}" r="3" fill="var(--fg)"/>')
    s.dim_h(0, foot, zpb - 120, f"{foot:.0f}", off=0)
    s.text(-460, 3322, "разрез по оси стойки поперёк рамы — в плоскости боковой фермы", "lbs")
    s.text(-460, za + 8, f"оси раскосов +{za/1000:.3f}", "dt")
    s.text(-460, 2705, f"раскосы под {math.degrees(a):.1f}° к горизонту", "dt")
    # швы: 4 — низ стойки и фасонок к столику (объект); 7 — раскосы под столиком (цех);
    # 2 — стойка к опорной пластине
    for sgn in (-1, 1):
        s.seam([(sgn * (B / 2 + tp), zpt + 1), (sgn * (B / 2 + tp + 8), zpt + 1)], w=6)
        s.seam([(0, zpb - 1.5), (sgn * foot, zpb - 1.5)], w=4)
    s.seam([(-B / 2, zcap), (B / 2, zcap)], w=3.5)
    s.leader(g["Br"] / 2, zb + Hr / C12 - 20, 130, 3265, f"стропило □{g['raf'].name}")
    s.leader(g["Bt"] / 2, 3000 + 10, 130, 3150, "затяжка — вне разреза (пунктир)", "lbs")
    s.leader(B / 2 + tp, 2975, 130, 3060, "фасонки t=5", "lbs")
    s.leader(-B / 2 + tc / 2, 2990, -150, 3080, f"стойка □{g['stub'].name}", "lbs")
    s.leader(Lp / 2 - 10, zpt, 250, 2990, f"столик {Lp:.0f}×{PLATE_B['w']}×{tg['plate_t']:.0f}", "lbs")
    s.leader(360, zpb - 360 * ta + 4, 400, 2735, f"раскос □{g['sd'].name} (рассечён вдоль)", "lbs", anchor="end")
    s.weld(B / 2 + tp + 26, zpt + 16, 4)
    s.weld(-B / 2 - tp - 26, zpt + 16, 4)
    s.weld(-foot * 0.6, zpb - 20, 7)
    s.weld(foot * 0.6, zpb - 20, 7)
    s.weld(-B / 2 - 18, zcap - 8, 2)
    return s.svg("узел Б — разрез в плоскости боковой фермы")


# ---------------- аксонометрия узла Б ----------------
class Axo:
    """Простая аксонометрия из призм (алгоритм художника по граням). Координаты в мм:
    x — вдоль рамы (к середине пролёта), y — вдоль ряда колонн, z — вверх."""

    def __init__(self, eye=(-0.62, -0.95, 0.55), S=0.55):
        import numpy as np
        e = np.array(eye, float)
        self.e = e / np.linalg.norm(e)
        self.rt = np.cross([0, 0, 1.0], self.e)
        self.rt /= np.linalg.norm(self.rt)
        self.up = np.cross(self.e, self.rt)
        self.S = S
        self.faces = []
        self.marks = []
        self.labels = []
        self.lines = []

    def pr(self, p):
        import numpy as np
        p = np.asarray(p, float)
        return float(p @ self.rt) * self.S, float(-(p @ self.up)) * self.S

    def prism(self, poly, plane, a, b, fill, op=1.0, dz=0.0, layer=0):
        """poly — многоугольник в плоскости plane ('xz' | 'yz' | 'xy'), вытянутый по третьей оси от a до b."""
        import numpy as np

        def P3(u, v, w):
            if plane == "xz":
                return np.array([u, w, v + dz])
            if plane == "yz":
                return np.array([w, u, v + dz])
            return np.array([u, v, w + dz])
        bot = [P3(u, v, a) for u, v in poly]
        top = [P3(u, v, b) for u, v in poly]
        n = len(poly)
        fs = [bot, top[::-1]] + [[bot[i], bot[(i + 1) % n], top[(i + 1) % n], top[i]] for i in range(n)]
        for f in fs:
            c = sum(f) / len(f)
            # нормаль грани — наружу от центра призмы
            nrm = np.cross(f[1] - f[0], f[2] - f[0])
            cen = (sum(bot) + sum(top)) / (2 * n)
            if np.dot(nrm, c - cen) < 0:
                nrm = -nrm
            if np.linalg.norm(nrm) < 1e-9 or np.dot(nrm, self.e) <= 1e-9:
                continue                       # грань смотрит от зрителя
            shade = 0.55 + 0.45 * abs(np.dot(nrm / np.linalg.norm(nrm), self.e))
            self.faces.append((layer, float(c @ self.e), f, fill, op, shade))

    def box(self, x1, x2, y1, y2, z1, z2, fill, op=1.0, dz=0.0, layer=0):
        self.prism([(x1, z1), (x2, z1), (x2, z2), (x1, z2)], "xz", y1, y2, fill, op, dz, layer)

    def mark(self, p, n):
        self.marks.append((p, n))

    def label(self, p, side, yf, text, cls="lbs"):
        """Выноска от точки p (3D) к подписи в колонке слева/справа (side = 'L'|'R'), yf — доля высоты."""
        self.labels.append((p, side, yf, text, cls))

    def line(self, p, q, style):
        self.lines.append((p, q, style, "line"))

    def seam(self, pts, closed=False):
        """Сварной шов — толстая тёмно-фиолетовая линия; рисуются только видимые участки
        (закрытые непрозрачными деталями — стропилом, стойкой и т. п. — не показываются)."""
        pts = list(pts) + ([pts[0]] if closed else [])
        for p, q in zip(pts[:-1], pts[1:]):
            self.lines.append((p, q, f'stroke="{SEAM}" stroke-width="4.5" stroke-linecap="round"', "seam"))

    def _hidden(self, p, faces):
        """Точка p закрыта от зрителя непрозрачной гранью (луч к зрителю пересекает грань)."""
        import numpy as np
        for f, nrm, d0 in faces:
            den = float(nrm @ self.e)
            if abs(den) < 1e-9:
                continue
            t = (d0 - float(nrm @ p)) / den
            if t <= 2.0:                       # грань за точкой или сама точка на грани (шов на кромке)
                continue
            x = p + t * self.e
            # точка внутри выпуклого многоугольника грани
            sgn = 0
            inside = True
            for i in range(len(f)):
                a, b = f[i], f[(i + 1) % len(f)]
                c = float(np.cross(b - a, x - a) @ nrm)
                if abs(c) < 1e-6:
                    continue
                if sgn == 0:
                    sgn = 1 if c > 0 else -1
                elif (c > 0) != (sgn > 0):
                    inside = False
                    break
            if inside:
                return True
        return False

    def _visible_runs(self, p, q, faces, n=60):
        import numpy as np
        p, q = np.asarray(p, float), np.asarray(q, float)
        ts = np.linspace(0, 1, n + 1)
        vis = [not self._hidden(p + t * (q - p), faces) for t in ts]
        runs, start = [], None
        for i, v in enumerate(vis):
            if v and start is None:
                start = i
            if (not v or i == n) and start is not None:
                end = i if v else i - 1
                if end > start:
                    runs.append((p + ts[start] * (q - p), p + ts[end] * (q - p)))
                start = None
        return runs

    def svg(self, aria):
        pts = [self.pr(v) for _, _, f, *_ in self.faces for v in f]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        mg = 250
        x0, x1 = min(xs) - mg, max(xs) + mg
        y0, y1 = min(ys) - 30, max(ys) + 30
        W, H = x1 - x0, y1 - y0
        P = lambda p: (self.pr(p)[0] - x0, self.pr(p)[1] - y0)
        o = [f'<svg viewBox="0 0 {W:.0f} {H:.0f}" class="nd" role="img" aria-label="{html.escape(aria)}">']
        # слои рисуются снизу вверх (раскосы → столик → рама), внутри слоя — по глубине граней
        for _, d, f, fill, op, shade in sorted(self.faces, key=lambda t: (t[0], t[1])):
            s_ = " ".join(f"{P(v)[0]:.1f},{P(v)[1]:.1f}" for v in f)
            o.append(f'<polygon points="{s_}" fill="{fill}" fill-opacity="{op:.2f}" stroke="#111" stroke-opacity="0.55" '
                     f'stroke-width="0.7" style="filter:brightness({shade:.2f})"/>')
        import numpy as np
        occl = []                                  # непрозрачные грани (прозрачная фасонка швы не закрывает)
        for _, _, f, _, op, _ in self.faces:
            if op < 0.8:
                continue
            nrm = np.cross(f[1] - f[0], f[2] - f[0])
            nrm = nrm / np.linalg.norm(nrm)
            occl.append((f, nrm, float(nrm @ f[0])))
        for p, q, style, kind in self.lines:
            segs = self._visible_runs(p, q, occl) if kind == "seam" else [(p, q)]
            for p_, q_ in segs:
                a, b = P(p_), P(q_)
                o.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" {style}/>')
        for p, n in self.marks:
            a = P(p)
            o.append(f'<circle cx="{a[0]:.1f}" cy="{a[1]:.1f}" r="11" class="wm" stroke="#111" stroke-width="0.8"/>'
                     f'<text x="{a[0]:.1f}" y="{a[1]+5.5:.1f}" text-anchor="middle" style="fill:#111;font-size:15px;font-weight:700">{n}</text>')
        for p, side, yf, text, cls in self.labels:
            a = P(p)
            bx = (mg - 12) if side == "L" else (W - mg + 12)
            by = 30 + yf * (H - 60)
            anchor = "end" if side == "L" else "start"
            o.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{bx:.1f}" y2="{by:.1f}" class="ld"/>')
            dx = -4 if side == "L" else 4
            fs = 15 if cls == "lb" else 13.5
            for k, ln in enumerate(text.split("\n")):
                o.append(f'<text x="{bx+dx:.1f}" y="{by-4+k*(fs+2):.1f}" class="{cls}" text-anchor="{anchor}" '
                         f'style="font-size:{fs}px">{html.escape(ln)}</text>')
        o.append("</svg>")
        return "".join(o)


def node_B_axo(g, lift=240.0, eye=(-1.0, -0.7, 0.5)):
    """Аксонометрия узла Б: сверху — узел средней рамы (цех), снизу — вершина боковой фермы (цех);
    раздвинуты на lift мм, стрелка — установка рамы на столик на объекте."""
    tg = g["tg"]
    Hr, Ht, Hs, Bs = g["Hr"], g["Ht"], g["Hs"], g["Bs"]
    Hd = g["Hd"]
    ta = math.tan(g["alpha"])
    foot = tg["foot"]
    zpt, zpb = tg["plate_top"], tg["z_pb"]
    w = PLATE_B["w"]
    Lp = tg["plate_len"]
    A = Axo(eye=eye)
    # --- ферма (низ): раскосы и столик
    yb = 380
    for sgn in (-1, 1):
        poly = [(0, zpb), (sgn * foot, zpb), (sgn * yb, zpb - (yb - foot) * ta), (sgn * yb, zpb - yb * ta)]
        A.prism(poly, "yz", -Hd / 2, Hd / 2, COL["sd"])
    A.box(-w / 2, w / 2, -Lp / 2, Lp / 2, zpb, zpt, COL["plate"], layer=1)   # столик лежит поверх раскосов
    # --- узел средней рамы (верх), поднят на lift
    cap_t = CAP["t"]
    top = lambda x: z_bot(x, Hr) - cap_t
    dz = lift
    # слои рамы (от дальних к ближним): дальняя фасонка → стойка, пластина, затяжка → стропило (нависает над
    # пластиной и затяжкой и закрывает торец пластины) → ближняя фасонка (перед стропилом, прозрачная)
    A.prism([(-Hs / 2, zpt), (Hs / 2, zpt), (Hs / 2, top(Hs / 2)), (-Hs / 2, top(-Hs / 2))], "xz", -Bs / 2, Bs / 2,
            COL["stub"], dz=dz, layer=3)
    L = CAP["len"] / 2
    A.prism([(-L, top(-L)), (L, top(L)), (L, z_bot(L, Hr)), (-L, z_bot(-L, Hr))], "xz", -Bs / 2, Bs / 2, COL["plate"], dz=dz, layer=3)
    xa, xb = -220, 320
    A.prism([(xa, z_bot(xa, Hr)), (xb, z_bot(xb, Hr)), (xb, z_bot(xb, Hr) + Hr / C12), (xa, z_bot(xa, Hr) + Hr / C12)],
            "xz", -g["Br"] / 2, g["Br"] / 2, COL["raf"], dz=dz, layer=4)
    A.box(Hs / 2, 380, -g["Bt"] / 2, g["Bt"] / 2, 3000 - Ht / 2, 3000 + Ht / 2, COL["tie"], dz=dz, layer=3)
    gb = gusset_B(g)
    gp = [(gb["x1"], gb["zb"]), (gb["x2"], gb["zb"]), (gb["x2"], z_axis(gb["x2"])), (gb["x1"], z_axis(gb["x1"]))]
    A.prism(gp, "xz", Bs / 2, Bs / 2 + 5, "#9ca3af", 0.9, dz=dz, layer=2)
    A.prism(gp, "xz", -Bs / 2 - 5, -Bs / 2, "#9ca3af", 0.45, dz=dz, layer=5)
    # стрелка установки
    A.line((-120, 0, zpt + dz - 20), (-120, 0, zpt + 25),
           'stroke="#dc2626" stroke-width="2.5" stroke-dasharray="8 5" marker-end="url(#arr)"')
    # швы: 1 — торец затяжки к стойке; 2 — пластина к стропилу; 3 — ближняя фасонка по кромкам;
    # 4 — место шва на столике (объект); 7 — раскосы под столиком (видимая сторона)
    yn = -Bs / 2 - 5
    # 2: стойка к опорной пластине — по контуру верха стойки (видны грань −x и, сквозь ближнюю фасонку, грань −y);
    #    пластина к стропилу — по торцу (виден ближний к зрителю торец)
    A.seam([(-Hs / 2, Bs / 2, top(-Hs / 2) + dz), (-Hs / 2, -Bs / 2, top(-Hs / 2) + dz),
            (Hs / 2, -Bs / 2, top(Hs / 2) + dz)])
    A.seam([(-L, -Bs / 2, z_bot(-L, Hr) + dz), (-L, Bs / 2, z_bot(-L, Hr) + dz)])
    # 1: торец затяжки к стойке — по контуру (видны боковая грань сквозь ближнюю фасонку и верх)
    A.seam([(Hs / 2, -g["Bt"] / 2, 3000 - Ht / 2 + dz), (Hs / 2, -g["Bt"] / 2, 3000 + Ht / 2 + dz),
            (Hs / 2, g["Bt"] / 2, 3000 + Ht / 2 + dz)])
    # 3: дальняя фасонка — видна её вертикальная кромка у стойки
    yf_ = Bs / 2 + 5
    A.seam([(gb["x1"], yf_, gb["zb"] + dz), (gb["x1"], yf_, z_axis(gb["x1"]) + dz)])
    A.seam([(gb["x1"], yn, gb["zb"] + dz), (gb["x1"], yn, z_axis(gb["x1"]) + dz),
            (gb["x2"], yn, z_axis(gb["x2"]) + dz)])
    A.seam([(gb["x2"], yn, 3000 - Ht / 2 + dz), (gb["x2"], yn, 3000 + Ht / 2 + dz)])
    A.seam([(-Hs / 2, -Bs / 2 - 5, zpt), (Hs / 2, -Bs / 2 - 5, zpt), (Hs / 2, Bs / 2 + 5, zpt),
            (-Hs / 2, Bs / 2 + 5, zpt)], closed=True)
    A.seam([(-Hd / 2, -foot, zpb), (-Hd / 2, foot, zpb)])
    A.mark((Hs / 2 + 30, -Bs / 2 - 6, 3000 + Ht / 2 + dz), 1)
    A.mark((-Hs / 2 - 28, -Bs / 2 - 6, top(-Hs / 2) + dz - 30), 2)       # у видимого участка шва стойки к пластине
    A.mark((150, -Bs / 2 - 6, 2990 + dz), 3)
    A.mark((w / 2, -Lp / 2 + 30, zpt), 4)
    A.mark((0, -foot / 2, zpb - 10), 7)
    # подписи
    A.label((250, 0, z_axis(250) + Hr / C12 + dz), "R", 0.02, f"стропило □{g['raf'].name}")
    A.label((380, g["Bt"] / 2, 3000 + dz), "R", 0.16, f"затяжка □{g['tie'].name}")
    A.label((180, -Bs / 2 - 5, 2950 + dz), "R", 0.30, "фасонки t=5, 2 шт.\n(ближняя — прозрачная)")
    A.label((0, -Bs / 2, 2945 + dz), "R", 0.46, f"стойка-вставка □{g['stub'].name}\n(низ открыт)")
    A.label((w / 2, Lp / 2 - 20, zpt), "R", 0.66, f"опорный столик\n{Lp:.0f}×{w:.0f}×{tg['plate_t']:.0f}")
    A.label((0, -yb * 0.75, zpb - yb * 0.75 * ta + 20), "R", 0.90, f"раскос фермы □{g['sd'].name}")
    A.label((-200, 0, z_axis(-200) + dz), "L", 0.08, "СРЕДНЯЯ РАМА\n(изготовлена в цеху)")
    A.label((-120, 0, zpt + dz * 0.5), "L", 0.48, "на объекте: опустить\nраму стойкой на столик,\nобварить шов 4")
    A.label((0, yb * 0.7, zpb - yb * 0.7 * ta), "L", 0.86, "БОКОВАЯ ФЕРМА\n(изготовлена в цеху)")
    s = A.svg("узел Б — аксонометрия")
    arr = ('<defs><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" '
           'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#dc2626"/></marker></defs>')
    return s.replace('aria-label="узел Б — аксонометрия">', 'aria-label="узел Б — аксонометрия">' + arr, 1)


# ---------------- боковая ферма целиком ----------------
def truss_elev(g):
    """Цеховая боковая ферма — вид с внутренней стороны ряда колонн (Л1 слева, Л3 справа)."""
    tg = g["tg"]
    Hb = g["Hb"]
    a = g["alpha"]
    ta = math.tan(a)
    half = M.BAY * 1000 / 2
    yf = -tg["y_face"]                      # от оси фермы до грани колонны
    foot = tg["foot"]
    zpt, zpb = tg["plate_top"], tg["z_pb"]
    Lp = tg["plate_len"]
    zct = tg["z_ct"]
    s = Svg(-half - 150, half + 150, 1840, 3100, k=4.0, pad=30)
    for sgn in (-1, 1):
        u1, u2 = sgn * half - g["Bc"] / 2, sgn * half + g["Bc"] / 2
        s.rect(min(u1, u2), 1860, max(u1, u2), 3050, COL["col"], "#0008", 0.35)
    s.rect(-yf, 2100 - Hb / 2, yf, 2100 + Hb / 2, COL["sb"], "#0008", 0.95)
    for sgn in (-1, 1):
        poly = [(sgn * yf, zct), (sgn * (yf - foot), zct), (0, zpb), (sgn * foot, zpb)]
        s.poly(poly, COL["sd"], "#0008", 0.95)
    s.rect(-Lp / 2, zpb, Lp / 2, zpt, COL["plate"], "#000a", 1)
    s.line(-half - 120, 2100, half + 120, 2100)
    za = tg["apex_z"]
    for sgn in (-1, 1):
        s.line(sgn * half, tg["z_axis_col"], 0, za)
    s.line(0, 1860, 0, 3080)
    s.dim_h(-yf, yf, 1985, f"нижний пояс {2 * yf:.0f} — между гранями колонн", off=0)
    s.dim_h(-half, half, 1880, f"{2 * half:.0f} — оси колонн", off=0)
    s.dim_v(Lp / 2 + 30, 2100, zpt, f"{zpt - 2100:.0f}", off=0, anchor="start")
    s.text(220, zpt + 20, f"верх столика +{zpt/1000:.3f}, столик {Lp:.0f}×{PLATE_B['w']}×{tg['plate_t']:.0f}", "dt")
    s.text(200, 2100 + 50, "ось пояса +2.100", "dt")
    for sgn in (-1, 1):
        s.seam([(sgn * yf, zct + 1), (sgn * (yf - foot), zct + 1)], w=4)          # 6: раскос на поясе
        s.seam([(0, zpb - 1), (sgn * foot, zpb - 1)], w=4)                       # 7: раскос под столиком
        s.seam([(sgn * yf, 2100 - Hb / 2), (sgn * yf, zct + 3)], w=4)             # 5: торец фермы к колонне
    s.leader(-half * 0.55, 2100 + Hb / 2, -half * 0.48, 2290, f"нижний пояс □{g['sb'].name}", "lb")
    ya = yf - 380
    s.leader(-ya, zct + (yf - foot - ya) * ta + 30, -1700, 2860, f"раскос □{g['sd'].name}", "lb", anchor="start")
    s.text(-half + 60, 3060, "колонна Л1", "lbs")
    s.text(half - 60, 3060, "колонна Л3", "lbs", "end")
    s.text(150, 2330, f"раскос под {math.degrees(a):.1f}° к горизонту", "lbs")
    s.weld(-yf + foot / 2 + 40, zct + 90, 6)
    s.weld(yf - foot / 2 - 40, zct + 90, 6)
    s.weld(-foot / 2 - 60, zpb - 60, 7)
    s.weld(foot / 2 + 60, zpb - 60, 7)
    s.weld(-yf - 55, 2100, 5)
    s.weld(yf + 55, 2100, 5)
    return s.svg("боковая ферма — общий вид")


# ---------------- узел В ----------------
def node_C(g):
    """Узел В — торец цеховой фермы у колонны, вид с внутренней стороны ряда колонн."""
    Bc, Hb, Hd = g["Bc"], g["Hb"], g["Hd"]
    tg = g["tg"]
    a = g["alpha"]
    ta = math.tan(a)
    foot = tg["foot"]
    zct = tg["z_ct"]
    s = Svg(-420, 700, 1900, 2380)
    s.rect(-Bc / 2, 1990, Bc / 2, 2360, COL["col"], "#0008", 0.9)
    # пояс
    s.rect(Bc / 2, 2100 - Hb / 2, 690, 2100 + Hb / 2, COL["sb"], "#0008", 0.9)
    # раскос: нижний торец — горизонтальный рез по верху пояса, от грани колонны на длину foot
    u0 = Bc / 2
    u1 = u0 + foot
    ue = 690
    poly = [(u0, zct), (u1, zct), (ue, zct + (ue - u1) * ta), (ue, zct + (ue - u0) * ta + 0.0)]
    s.poly(poly, COL["sd"], "#0008", 0.9)
    # оси
    s.line(-140, 2100, 690, 2100)
    zax = lambda u: tg["z_axis_col"] + (u - 0) * ta
    s.line(-140, zax(-140), 690, zax(690))
    s.line(0, 1995, 0, 2355)
    s.dim_h(u0, u1, 2100 - Hb / 2, f"{foot:.0f}", off=34)
    s.text(-410, 2100 + 6, "ось пояса +2.100", "dt")
    s.seam([(u0, 2100 - Hb / 2), (u0, zct + 3)], w=5)                            # 5: торец фермы к колонне
    s.seam([(u0, zct + 1), (u1, zct + 1)], w=5)                                  # 6: раскос на поясе
    s.leader(600, zct + (600 - (u0 + u1) / 2) * ta, 560, 2355, f"раскос □{g['sd'].name}", "lb")
    s.leader(460, 2100 - Hb / 2, 420, 1990, f"нижний пояс □{g['sb'].name}", "lb")
    s.leader(-Bc / 2, 2300, -200, 2330, f"колонна □{g['col'].name}", "lb")
    s.text(-410, 1945, f"раскос под {math.degrees(a):.1f}° к горизонту; оси раскоса", "lbs")
    s.text(-410, 1922, "и пояса пересекаются у грани колонны", "lbs")
    s.weld(u0 + 18, 2100 - Hb / 2 - 16, 5)
    s.weld(u1 + 40, zct + 26, 6)
    return s.svg("узел В — торец фермы у колонны")


def node_C_face(g):
    """Вид на грань колонны со стороны фермы: след торца пояса и угла раскоса."""
    Hc, Hb, Hd = g["Hc"], g["Hb"], g["Hd"]
    zct = g["tg"]["z_ct"]
    s = Svg(-260, 320, 1960, 2380)
    s.rect(-Hc / 2, 1960, Hc / 2, 2360, COL["col"], "#0008", 0.9)
    s.rect(-Hb / 2, 2100 - Hb / 2, Hb / 2, 2100 + Hb / 2, COL["sb"], "#000", 0.85, 1.2)
    s.rect(-Hd / 2, zct, Hd / 2, zct + 4, COL["sd"], "#000", 0.85, 1.0)
    s.seam([(-Hb / 2, 2100 - Hb / 2), (Hb / 2, 2100 - Hb / 2), (Hb / 2, zct + 4), (-Hb / 2, zct + 4)], w=4, closed=True)
    s.dim_h(-Hc / 2, Hc / 2, 1960, f"{Hc:.0f}", off=16)
    s.dim_h(-Hb / 2, Hb / 2, 2100 + Hb / 2, f"{Hb:.0f}", off=-14)
    s.text(-250, 2365, "вид на грань колонны со стороны фермы", "lbs")
    s.leader(Hd / 2, zct + 2, 110, 2250, "угол раскоса", "lbs")
    s.leader(Hb / 2, 2100 - Hb / 2 + 5, 110, 2040, "след торца пояса", "lbs")
    s.weld(-Hb / 2 - 16, 2100, 5)
    return s.svg("узел В — вид на грань колонны")



# ---------------- узел Г: торцевая обвязка ----------------
GE_D = 175.0          # отступ оси обвязки от кромки кровли, мм
TILE_STEP = 15.0      # высота ступеньки металлочерепицы (по профилю производителя), мм
COL_LE, COL_LR = "#be185d", "#9d174d"


def _slope_pts(c, sn, pts, right=False):
    """(s, n) по скату → (u, z): s — вдоль ската от начала, n — по нормали вверх."""
    if right:
        return [(s * c + n * sn, -s * sn + n * c) for s, n in pts]
    return [(s * c - n * sn, s * sn + n * c) for s, n in pts]


def node_G(g):
    """Разрез по обвязке у карниза (левый скат): обвязка под обрешётинами, карнизная обрешётина выше на 15 мм."""
    ge, le = g["ge"], g["le"]
    a_ge, a_le, a_l = ge.h * 1000, le.h * 1000, g["lath"].h * 1000
    b_le, b_l = le.b * 1000, g["lath"].b * 1000
    c, sn = math.cos(M.SLOPE), math.sin(M.SLOPE)
    SP = lambda pts: _slope_pts(c, sn, pts)
    s_end = 830.0
    s = Svg(-560, 1220, -300, 430, k=1.35)
    # обвязка (вид сбоку, на ребро), обрыв справа
    s.poly(SP([(0, 0), (s_end, 0), (s_end, -a_ge), (0, -a_ge)]), COL["ge"], "#0008", 0.85)
    zz = SP([(s_end, 12), (s_end - 12, -a_ge / 2 + 6), (s_end + 12, -a_ge / 2 - 6), (s_end, -a_ge - 12)])
    s.items.append('<polyline points="' + " ".join(f"{s.P(u, z)[0]:.1f},{s.P(u, z)[1]:.1f}" for u, z in zz)
                   + '" fill="none" stroke="var(--fg)" stroke-width="1"/>')
    # карнизная обрешётина 50×30 на ребро — наружная грань по торцу обвязки
    s.poly(SP([(0, 0), (b_le, 0), (b_le, a_le), (0, a_le)]), COL_LE, "#0008", 0.9)
    # рядовые обрешётины 35×35 (оси — 292.5 и 642.5 мм по скату от карниза)
    lath_s = [292.5, 642.5]
    for sc_ in lath_s:
        s.poly(SP([(sc_ - b_l / 2, 0), (sc_ + b_l / 2, 0), (sc_ + b_l / 2, a_l), (sc_ - b_l / 2, a_l)]),
               COL["lath"], "#0008", 0.9)
    # уровень верха рядовых обрешётин — пунктир до карниза
    s.poly(SP([(-20, a_l), (s_end, a_l)]), "none", "var(--dim)", 1, 1, dash="6 4")
    # металлочерепица: ступенька опирается на обрешётину; модуль идёт от ступеньки вниз по скату с подъёмом
    # на высоту ступеньки — у карниза его низ лежит на карнизной обрешётине (выше рядовых на 15 мм)
    st = TILE_STEP
    # от верха к карнизу: над ступенькой лист на высоте ступеньки, у ступеньки — вниз на обрешётину
    l2 = lath_s[1] + 350.0
    pts = [(s_end, a_l + st * (l2 - s_end) / 350.0)]
    for x in (lath_s[1], lath_s[0]):
        pts += [(x, a_l + st), (x, a_l)]
    pts += [(b_le / 2, a_le), (-45, a_le + 45 * st / (lath_s[0] - b_le / 2))]
    tp = SP(pts)
    s.items.append('<polyline points="' + " ".join(f"{s.P(u, z)[0]:.1f},{s.P(u, z)[1]:.1f}" for u, z in tp)
                   + '" fill="none" stroke="var(--fg)" stroke-width="2.4" stroke-linejoin="round"/>')
    # швы 12: обрешётины к обвязке (по боковым граням в месте опирания)
    for s0, b0 in [(b_le / 2, b_le)] + [(x, b_l) for x in lath_s]:
        s.seam(SP([(s0 - b0 / 2, 0), (s0 + b0 / 2, 0)]), w=4)
    u12, z12 = SP([(lath_s[0] + 60, -a_ge - 45)])[0]
    ut, zt = SP([(lath_s[0] + b_l / 2, 0)])[0]
    s.line(u12, z12, ut, zt, "ld")
    s.weld(u12, z12, 12)
    # размеры: подъём карнизной обрешётины над уровнем рядовых
    ua, za = SP([(0, a_le)])[0]
    ub, zb = SP([(0, a_l)])[0]
    ud = min(ua, ub) - 55
    s.line(ua, za, ud - 8, za, "dl")
    s.line(ub, zb, ud - 8, zb, "dl")
    s.dim_v(ud, zb, za, f"{a_le - a_l:.0f}", off=0, anchor="end")
    # подписи
    u0, z0 = SP([(0, -a_ge)])[0]
    s.leader(*SP([(120, -a_ge / 2)])[0], 30, -200, f"обвязка □{ge.name} на ребро (h = {a_ge:.0f})", "lbs", anchor="end")
    s.leader(*SP([(b_le / 2, a_le * 0.7)])[0], 40, 300, f"карнизная обрешётина □{le.name} на ребро", "lbs", anchor="start")
    s.leader(*SP([(lath_s[1], a_l / 2)])[0], 700, 70, f"обрешётина □{g['lath'].name}", "lbs", anchor="start")
    s.leader(*SP([(560, a_l + st * 0.6)])[0], 620, 260, "металлочерепица: ступенька на обрешётине", "lbs",
             anchor="start")
    s.text(-550, 405, "у карниза ступеньки нет — край листа лежит на карнизной обрешётине, она выше на 15 мм", "lbs")
    s.text(-550, -285, "разрез по обвязке, вид с торца навеса — левый скат у карниза (правый — так же)", "lbs")
    return s.svg("узел Г — обвязка и карнизная обрешётина")


def node_G_ridge(g):
    """Разрез по обвязке у конька: стык половин обвязки, коньковая обрешётина 60×60."""
    ge, lr = g["ge"], g["lr"]
    a_ge, a_lr, a_l, b_l = ge.h * 1000, lr.h * 1000, g["lath"].h * 1000, g["lath"].b * 1000
    c, sn = math.cos(M.SLOPE), math.sin(M.SLOPE)
    L = 470.0
    s = Svg(-660, 660, -290, 260, k=1.35)
    zb = -a_ge / c
    for right in (False, True):
        sg = 1 if right else -1
        # в координатах (s, n): вниз по скату от конька; для левой половины — зеркально
        P = lambda pts, r=right: [(-u, z) for u, z in _slope_pts(c, sn, pts, right=True)] if not r else \
            _slope_pts(c, sn, pts, right=True)
        q = P([(L, 0), (L, -a_ge)])
        s.poly([(0, 0)] + q + [(0, zb)], COL["ge"], "#0008", 0.85)
        # рядовая обрешётина у конька: слева 102 мм по скату, справа 264 мм
        xs_ = [r[0] for r in M.lath_rows()]
        x_n = min((x for x in xs_ if x > M.X_RIDGE + 1e-6)) if right else max((x for x in xs_ if x < M.X_RIDGE - 1e-6))
        sc_ = abs(x_n - M.X_RIDGE) / c * 1000
        s.poly(P([(sc_ - b_l / 2, 0), (sc_ + b_l / 2, 0), (sc_ + b_l / 2, a_l), (sc_ - b_l / 2, a_l)]),
               COL["lath"], "#0008", 0.9)
        s.seam(P([(sc_ - b_l / 2, 0), (sc_ + b_l / 2, 0)]), w=4)
        zz = P([(L, 12), (L - 12, -a_ge / 2 + 6), (L + 12, -a_ge / 2 - 6), (L, -a_ge - 12)])
        s.items.append('<polyline points="' + " ".join(f"{s.P(u, z)[0]:.1f},{s.P(u, z)[1]:.1f}" for u, z in zz)
                       + '" fill="none" stroke="var(--fg)" stroke-width="1"/>')
    # коньковая обрешётина 60×60 — на вершине стропил, по оси конька
    s.rect(-a_lr / 2, 0, a_lr / 2, a_lr, COL_LR, "#0008", 0.9)
    # швы: 13 — стык половин обвязки (вертикальные резы, по контуру), 14 — коньковая обрешётина через пруток
    s.seam([(0, 0), (0, zb)], w=5)
    # клиновой зазор под коньковой обрешётиной — прутки Ø6 (как на стропилах), шов 14
    xr = ridge_rod_x(a_lr)
    for sg_ in (-1, 1):
        p_ = s.P(sg_ * xr, -ROD_D / 2)
        s.items.append(f'<circle cx="{p_[0]:.1f}" cy="{p_[1]:.1f}" r="{ROD_D / 2 * 1.35:.1f}" fill="#374151" '
                       f'stroke="#111" stroke-width="0.6"/>')
        s.seam([(sg_ * a_lr / 2, 0.5), (sg_ * (a_lr / 2 + 6), 0.5)], w=4)
    s.weld(0, zb - 40, 13)
    s.weld(-a_lr / 2 - 40, 50, 14)
    s.line(0, zb - 70, 0, a_lr + 60)
    s.text(8, a_lr + 45, "ось конька", "dt")
    s.leader(-300, -300 * sn / c * 1 - a_ge / 2 / c, -120, -230, f"обвязка □{ge.name}, левая половина", "lbs", anchor="end")
    s.leader(330, -330 * sn / c - a_ge / 2 / c, 380, -200, "правая половина", "lbs", anchor="start")
    s.leader(a_lr / 2, a_lr * 0.75, 200, 170, f"коньковая обрешётина □{lr.name}", "lbs", anchor="start")
    s.text(-630, 235, "разрез по обвязке у конька: половины встык вертикальными резами", "lbs")
    return s.svg("узел Г — стык обвязки у конька")


# ---------------- коньковая обрешётина на стропилах ----------------
ROD_D = 6.0           # пруток-подкладка в клиновой зазор под коньковой обрешётиной, мм


def ridge_rod_x(a_lr):
    """Положение оси прутка Ø6 (от оси конька) в клине между низом обрешётины и верхом стропила."""
    t = math.tan(M.SLOPE)
    r = ROD_D / 2
    return r * (1 + math.sqrt(1 + t * t)) / t


def ridge_lath(g):
    """Коньковая обрешётина на вершине стропил: разрез в плоскости рамы, клиновой зазор и прутки Ø6."""
    lr, Hr = g["lr"], g["Hr"]
    a = lr.h * 1000
    t = math.tan(M.SLOPE)
    c = math.cos(M.SLOPE)
    hr = Hr / c                                     # высота стропила по вертикали
    X = 165.0
    s = Svg(-235, 235, -hr - 85, a + 95, k=0.8)
    # стропила левого и правого ската (верх — от вершины вниз), торцы — вертикальный рез по оси конька
    for sg in (-1, 1):
        s.poly([(0, 0), (sg * X, -X * t), (sg * X, -X * t - hr), (0, -hr)], COL["raf"], "#0008", 0.9)
        zz = [(sg * X, -X * t + 12), (sg * (X - 10), -X * t - hr / 2 + 6), (sg * (X + 10), -X * t - hr / 2 - 6),
              (sg * X, -X * t - hr - 12)]
        s.items.append('<polyline points="' + " ".join(f"{s.P(u, z)[0]:.1f},{s.P(u, z)[1]:.1f}" for u, z in zz)
                       + '" fill="none" stroke="var(--fg)" stroke-width="1"/>')
    # коньковая обрешётина — касается вершины только по оси
    s.rect(-a / 2, 0, a / 2, a, COL_LR, "#0008", 0.9)
    tl = lr.t * 1000
    s.rect(-a / 2 + tl, tl, a / 2 - tl, a - tl, "var(--card)", "none")
    # прутки Ø6 в клиновом зазоре у боковых граней обрешётины
    xr = ridge_rod_x(a)
    for sg in (-1, 1):
        p = s.P(sg * xr, -ROD_D / 2)
        s.items.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="{ROD_D / 2:.1f}" fill="#374151" stroke="#111" '
                       f'stroke-width="0.6"/>')
        # шов 14: пруток к обрешётине (сверху) и к стропилу (снизу, по скату)
        s.seam([(sg * (a / 2), 0.3), (sg * (a / 2 + 5), 0.3)], w=4)
        s.seam([(sg * (xr + 2), -(xr + 2) * t - 0.5), (sg * (xr + 9), -(xr + 9) * t - 0.5)], w=4)
    s.seam([(0, 0), (0, -hr)], w=4)                  # стык стропил на коньке (по контуру)
    # размер зазора у грани обрешётины
    s.dim_v(a / 2 + 40, -a / 2 * t, 0, f"{a / 2 * t:.1f}", off=0, anchor="start")
    s.line(a / 2, -a / 2 * t, a / 2 + 48, -a / 2 * t, "dl")
    s.line(a / 2, 0, a / 2 + 48, 0, "dl")
    s.line(0, -hr - 40, 0, a + 60)
    s.text(6, -hr - 30, "ось конька", "dt")
    s.weld(-a / 2 - 34, 22, 14)
    s.weld(a / 2 + 26, 30, 14)
    s.leader(a / 2 - 10, a * 0.7, 60, a + 50, f"коньковая □{lr.name}", "lbs", anchor="start")
    s.leader(-xr, -ROD_D / 2, -75, 55, f"пруток Ø{ROD_D:.0f}, L = 60", "lbs", anchor="end")
    s.leader(-120, -120 * t - hr / 2, -90, -hr - 65, f"стропило □{g['raf'].name}", "lbs", anchor="end")
    s.text(-230, a + 80, "разрез по оси рамы у конька", "lbs")
    return s.svg("коньковая обрешётина на стропилах")


# ---------------- стык обрешётины ----------------
def lath_splice(g):
    """Стык обрешётины встык — вид сбоку вдоль обрешётины (по скату), размеры в мм."""
    from report_data import LATH_SPLICE_Y
    a = g["lath"].h * 1000
    d = (M.BAY - LATH_SPLICE_Y) * 1000          # от стыка до оси стропила рамы 3
    Hr = g["Hr"]
    s = Svg(-420, 560, -140, 110)
    # стропило рамы 3 (сечение, под обрешётиной)
    s.rect(d - 30, -Hr, d + 30, 0, COL["raf"], "#0008", 0.9)
    tw = g["raf"].t * 1000
    s.rect(d - 30 + tw, -Hr + tw, d + 30 - tw, -tw, "var(--card)", "none")
    # две части обрешётины
    s.rect(-400, 0, -1, a, COL["lath"], "#0008", 0.85)
    s.rect(1, 0, 540, a, COL["lath"], "#0008", 0.85)
    # шов по контуру стыка и приварка к стропилу
    s.seam([(0, 0), (0, a)], w=5)
    s.seam([(d - 30, a * 0 - 0.5), (d + 30, -0.5)], w=3.5)
    s.line(-410, a / 2, 550, a / 2)
    s.line(d, -Hr - 10, d, a + 40)
    s.dim_h(0, d, a + 30, f"{d:.0f}", off=0)
    s.leader(-250, a, -250, 80, f"часть 1 (5.49 м) □{g['lath'].name}", "lbs")
    s.leader(500, a, 470, 80, "часть 2 (1.49 м)", "lbs")
    s.leader(d + 30, -Hr / 2, d + 80, -100, "стропило рамы 3", "lbs")
    s.text(d + 6, -Hr - 22, "ось стропила", "dt")
    s.weld(0, a + 16, 8)
    s.weld(d - 45, -14, 9)
    return s.svg("стык обрешётины встык")

# ---------------- мини-карта ----------------
def minimap(model, marks, primary, label):
    """Аксонометрия всего навеса с выделением узлов.

    marks — список логических координат (x, y, z) всех таких узлов, primary — показанный на чертеже."""
    import numpy as np
    eye = np.array([-5.5, -8.5, 7.5])
    center = np.array([M.SPAN / 2, M.BAY / 2, 1.8])
    fw = center - eye
    fw /= np.linalg.norm(fw)
    rt = np.cross(fw, [0, 0, 1.0])
    rt /= np.linalg.norm(rt)
    up = np.cross(rt, fw)

    def pr(p):
        p = np.asarray(p, float)
        return float(p @ rt), float(-(p @ up))
    pts = [pr(n) for n in model.nodes]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs) - 0.6, max(xs) + 0.6, min(ys) - 0.5, max(ys) + 0.4
    S = 60.0
    W, H = (x1 - x0) * S, (y1 - y0) * S

    def P(p):
        a, b = pr(p)
        return (a - x0) * S, (b - y0) * S
    o = [f'<svg viewBox="0 0 {W:.0f} {H:.0f}" class="nd mm" role="img" aria-label="{html.escape(label)}">']
    # земля — контур площадки под навесом
    gpts = [model.phys((x, y, 0.0)) for x, y in ((-0.6, -1.4), (M.SPAN + 1.1, -1.4), (M.SPAN + 1.1, M.BAY + 1.4), (-0.6, M.BAY + 1.4))]
    o.append('<polygon points="' + " ".join(f"{P(p)[0]:.1f},{P(p)[1]:.1f}" for p in gpts)
             + '" fill="#94a3b8" fill-opacity="0.12" stroke="#94a3b8" stroke-width="1"/>')
    # коридор проезда
    cp = [model.phys((x, y, 0.0)) for x, y in ((M.CORRIDOR_X[0], -1.4), (M.CORRIDOR_X[1], -1.4),
                                               (M.CORRIDOR_X[1], M.BAY + 1.4), (M.CORRIDOR_X[0], M.BAY + 1.4))]
    o.append('<polygon points="' + " ".join(f"{P(p)[0]:.1f},{P(p)[1]:.1f}" for p in cp)
             + '" fill="none" stroke="#16a34a" stroke-width="1" stroke-dasharray="5 4"/>')
    # стержни (обрешётка — тонко и бледно)
    order = {"lath": 0, "sb": 1, "sd": 1, "tie": 2, "kp": 2, "strut": 2, "raf": 3, "stub": 4, "col": 4}
    els = sorted(model.elems, key=lambda e: order.get(model.members[e.member]["group"], 2))
    for e in els:
        g = model.members[e.member]["group"]
        a, b = P(model.nodes[e.n1]), P(model.nodes[e.n2])
        w, op = (0.7, 0.22) if g == "lath" else ((3.2, 0.95) if g == "col" else (2.2, 0.9))
        o.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{COL.get(g, "#555")}" '
                 f'stroke-width="{w}" stroke-opacity="{op}" stroke-linecap="round"/>')
    # подписи рядов колонн и сторон
    for (xc, yc), (nm, zb, dep, zg) in M.COLUMN_BASES.items():
        a = P(model.phys((xc, yc, zb)))
        o.append(f'<text x="{a[0]:.1f}" y="{a[1]+20:.1f}" class="lb" text-anchor="middle" '
                 f'style="font-weight:700;paint-order:stroke;stroke:#fff;stroke-width:4px">{nm}</text>')
    a = P(model.phys((M.SPAN / 2, -1.4, 0.0)))
    o.append(f'<text x="{a[0]:.1f}" y="{a[1]+22:.1f}" class="lbs" text-anchor="middle">дорога / въезд</text>')
    # отметки узлов
    for m in marks:
        a = P(model.phys(m))
        o.append(f'<circle cx="{a[0]:.1f}" cy="{a[1]:.1f}" r="9" fill="#f59e0b" fill-opacity="0.35" stroke="#b45309" stroke-width="1.5"/>')
    a = P(model.phys(primary))
    o.append(f'<circle cx="{a[0]:.1f}" cy="{a[1]:.1f}" r="17" fill="none" stroke="#dc2626" stroke-width="3.5"/>')
    o.append(f'<line x1="{a[0]+14:.1f}" y1="{a[1]-14:.1f}" x2="{a[0]+60:.1f}" y2="{a[1]-60:.1f}" stroke="#dc2626" stroke-width="2"/>')
    o.append(f'<text x="{a[0]+64:.1f}" y="{a[1]-62:.1f}" style="fill:#dc2626;font-size:24px;font-weight:700;'
             f'font-family:system-ui,sans-serif;paint-order:stroke;stroke:#fff;stroke-width:5px">{html.escape(label)}</text>')
    o.append("</svg>")
    return "".join(o)


def minimap_block(model, marks, primary, label, text):
    return (f'<div class="card mmrow"><div class="mmimg">{minimap(model, marks, primary, label)}</div>'
            f'<div class="mmtxt"><b>Где находится</b><p>{text}</p>'
            f'<p class="note">Красное кольцо — узел, показанный на чертеже; жёлтые точки — такие же узлы на навесе. '
            f'Зелёный пунктир — коридор проезда.</p></div></div>')



def build(final, nf):
    g = geometry(final["groups"])
    from report_data import scheme_from_result
    mdl = M.build(scheme_from_result(final))
    zA = M.Z_NODE
    marksA = [(x, y, zA) for x in (0.0, M.SPAN) for y in (0.0, M.BAY)]
    mmA = minimap_block(mdl, marksA, (0.0, 0.0, zA), "узел А",
                        "Оголовки всех четырёх колонн — 4 одинаковых узла (у правого ряда — зеркально). "
                        "На чертеже — колонна <b>Л1</b>: левый ряд, рама 1 со стороны дороги. Здесь стропило "
                        "крайней рамы проходит над колонной, а затяжка этой рамы приходит на колонну.")
    marksB = [(x, M.BAY / 2, M.Z_TIE) for x in (0.0, M.SPAN)]
    mmB = minimap_block(mdl, marksB, (0.0, M.BAY / 2, M.Z_TIE), "узел Б",
                        "Опоры средней рамы (рама 2) — 2 одинаковых узла, по одному в каждом ряду колонн, "
                        "посередине между колоннами. Здесь у средней рамы нет колонны: её стропило и затяжка "
                        "опираются на вершину Λ-образной боковой фермы (два красных раскоса от колонн). "
                        "На чертеже — узел у левого ряда (между Л1 и Л3).")
    zC = 2.10
    marksC = [(x, y, zC) for x in (0.0, M.SPAN) for y in (0.0, M.BAY)]
    mmC = minimap_block(mdl, marksC, (0.0, 0.0, zC), "узел В",
                        "Концы боковых ферм у колонн, отметка оси пояса +2.100 — 4 одинаковых узла (на каждой колонне, "
                        "со стороны соседней колонны своего ряда). Здесь торец цеховой фермы — нижний пояс (голубой) "
                        "и лежащий на нём раскос (красный) — приваривается к грани колонны. "
                        "На чертеже — колонна <b>Л1</b>: левый ряд, со стороны дороги; у Л3 — зеркально, у правого ряда — так же.")
    svgA = node_A(g)
    svgA2 = node_A_section(g)
    svgB = node_B(g)
    svgB2 = node_B_section(g)
    svgB3 = node_B_axo(g)
    svgT = truss_elev(g)
    svgL = lath_splice(g)
    svgC = node_C(g)
    svgC2 = node_C_face(g)
    has_edge = "ge" in g
    if has_edge:
        svgG = node_G(g)
        svgGr = node_G_ridge(g)
        svgRL = ridge_lath(g)
        yge = (M.Y_MIN + GE_D / 1000, M.Y_MAX - GE_D / 1000)
        xs_ = [r[0] for r in mdl.rows]
        marksG = [(x, y, M.z_rafter(x)) for x in (min(xs_), M.X_RIDGE, max(xs_)) for y in yge]
        mmG = minimap_block(mdl, marksG, (min(xs_), yge[0], M.z_rafter(min(xs_))), "узел Г",
                            "Торцевая обвязка — под обрешёткой в 175 мм от передней и задней кромки кровли, по скату от "
                            "карниза до конька (4 половины). Подкосов нет: концы обвязки держат карнизные обрешётины "
                            "(у обоих карнизов) и коньковая обрешётина. На чертеже — у карниза левого ската, спереди.")
    inst = final.get("installer", {})

    def f(key, k):
        return nf.get(key, {}).get(k, 0.0)

    tg = g["tg"]
    gus_w = GUSSET["x2"] - GUSSET["x1"]
    gus_h1 = z_axis(GUSSET["x1"]) - GUSSET["zb"]
    gus_h2 = z_axis(GUSSET["x2"]) - GUSSET["zb"]
    gb = gusset_B(g)
    gbw = gb["x2"] - gb["x1"]
    gbh1 = z_axis(gb["x1"]) - gb["zb"]
    gbh2 = z_axis(gb["x2"]) - gb["zb"]
    Lp, wp, tpl = tg["plate_len"], PLATE_B["w"], tg["plate_t"]
    foot = tg["foot"]
    a = g["alpha"]
    sa, ca = math.sin(a), math.cos(a)

    # проверки сварных швов (ДБН В.2.6-198: Rwf = 180 МПа для Э42, βf = 0.7; Rwz = 0.45·Run = 162 МПа, βz = 1)
    def weld_cap(k, L):
        return min(0.7 * k * L * 180, 1.0 * k * L * 162) / 1e3
    tie_perim = 2 * (g["Ht"] + g["Bt"]) - 20
    w1 = weld_cap(2, tie_perim)
    u_w1 = f("A_затяжка", "Nt") / w1
    A_g = 2 * 5 * gus_w
    W_g = 2 * 5 * gus_w ** 2 / 6
    sig_g = f("A_колонна_оголовок", "M") * 1e6 / W_g
    tau_g = f("A_колонна_оголовок", "V") * 1e3 / A_g
    Nsd = max(f("Б_раскос_боковой_фермы", "Nc"), f("В_раскос_боковой_фермы", "Nc"))
    Nsb = f("В_нижний_пояс", "Nt")
    Nst = f("Б_стойка_на_столике", "Nc")
    # шов 4: стойка + фасонки к столику, по контуру 2·(60 + 70), k=3
    L4 = 2 * (g["Hs"] + g["Bs"] + 10)
    w4 = weld_cap(3, L4)
    # швы 6 и 7: раскос к поясу / под столик — по контуру опирания 2·foot + 60, k=2
    L67 = 2 * foot + g["Hd"]
    w67 = weld_cap(2, L67)
    # шов 5: торец фермы к колонне — пояс по контуру, k=2; усилие — равнодействующая (с запасом)
    L5 = 2 * (g["Hb"] + g["Hb"]) - 20
    w5 = weld_cap(2, L5)
    R5 = math.hypot(Nsd * sa, max(Nsb, Nsd * ca))
    # столик: сжатие от распора раскосов
    sig_p = Nsd * ca * 1e3 / (wp * tpl)
    # раскос на поясе (β = 1, EN 1993-1-8, боковая стенка пояса)
    sb_ = g["sb"]
    h0, t0 = sb_.h * 1000, sb_.t * 1000
    lam = 3.46 * (h0 / t0 - 2) * math.sqrt(1 / sa)
    lam_r = lam / (math.pi * math.sqrt(210000 / 235))
    phi = 0.5 * (1 + 0.21 * (lam_r - 0.2) + lam_r ** 2)
    chi = min(1.0, 1 / (phi + math.sqrt(phi ** 2 - lam_r ** 2)))
    N_sw = chi * 235 * t0 * (2 * g["Hd"] / sa + 10 * t0) / sa / 1e3
    u_sw = Nsd / N_sw

    # швы фасонок к колонне (2 фасонки): вертикальная кромка gus_h1 + низ по колонне Hc, k=4;
    # момент узла — на пару швов как на изгиб (с запасом — без учёта нижних кромок)
    Wwg = 2 * 0.7 * 4 * gus_h1 ** 2 / 6
    sig_wg = f("A_колонна_оголовок", "M") * 1e6 / Wwg
    tau_wg = f("A_колонна_оголовок", "V") * 1e3 / (2 * 0.7 * 4 * (gus_h1 + g["Hc"]))
    u_wg = math.hypot(sig_wg, tau_wg) / 180

    secG = ""
    if has_edge:
        ge_, le_, lr_ = g["ge"], g["le"], g["lr"]
        secG = f"""
<h2 class="pb">Узел Г — торцевая обвязка, карнизные и коньковая обрешётины</h2>
{mmG}
<div class="card">{svgG}</div>
<div class="grid2 c"><div class="card">{svgGr}</div><div class="card">{svgRL}</div></div>
<div class="card">
<h3>Зачем</h3>
<p>Обрешётина выступает за крайнюю раму консолью 1.18–1.20 м. Под монтажником (нагрузка по ДБН В.1.2-2, п. 6.10:
100 кгс × 1.2) одиночная обрешётина 35×35×2 не проходит: на самом конце консоли — коэффициент ≈ 3, прогиб ≈ 95 мм;
даже если к кромке ближе 40 см не подходить — ≈ 2.0, прогиб ≈ 30 мм. Обвязка в 175 мм от кромки связывает концы всех
обрешётин ската: груз под монтажником разносится на соседние консоли, а концы обвязки опираются на карнизную и коньковую
обрешётины — они сделаны жёстче рядовых. С обвязкой (монтажник не ближе 40 см к кромкам): обрешётка
{inst.get('lath', 0):.2f}, карнизные {inst.get('le', 0):.2f}, коньковая {inst.get('lr', 0):.2f}, обвязка
{inst.get('ge', 0):.2f}, прогиб под грузом {inst.get('прогиб, мм', 0):.0f} мм. Заодно обвязка — ровная кромка для крепления
торцевых планок.</p>
<h3>Как устроен</h3>
<ul>
<li><b>Обвязка □{ge_.name}</b>, на ребро (50 мм — по высоте), у передней и у задней кромки кровли, по скату от карниза
до конька, в 175 мм от кромки. Верх обвязки — вровень с верхом стропил: обрешётины лежат и на стропилах, и на обвязке.
Каждая обвязка — из двух половин (по скату), у конька половины стыкуются вертикальными резами и свариваются встык —
шов <span class="wk">13</span>. У карниза торец обвязки — под карнизной обрешётиной, заглушить.</li>
<li><b>Карнизные обрешётины □{le_.name}</b> (первая от карниза на каждом скате) — поставлены на ребро: высота 50 мм,
верх на 15 мм выше рядовых 35×35. Это одновременно требование монтажа металлочерепицы: на рядовых обрешётинах лист
опирается ступенькой, а у карниза ступеньки нет — край листа ложится на карнизную обрешётину, и она должна быть выше
на высоту ступеньки. <b>Высоту ступеньки проверить по выбранному профилю</b>: если она не 15 мм, подъём добрать
подкладкой или сменить высоту карнизной трубы (сообщить — пересчитаю).</li>
<li><b>Коньковая обрешётина □{lr_.name}</b> — на вершине стропил, по оси конька, под коньковой планкой (листы до неё
не доходят); её короткая часть (1.49 м) — из обрезка заказчика □60×60×3, наружные размеры те же. Её верх на 25 мм выше рядовых; если с выбранным коньком это мешает — сообщить.</li>
<li><b>Опирание коньковой обрешётины.</b> Её плоский низ лежит на «домике» из двух стропил под 12° и касается их
только по оси конька; у боковых граней обрешётины зазор {30 * math.tan(M.SLOPE):.1f} мм. Варить через такой зазор
нельзя (шов «по воздуху», прожог стенки 2 мм), поэтому в клин с каждой стороны закладывается <b>пруток Ø6</b>
(катанка, арматура) — он сам садится под грань обрешётины. Шов <span class="wk">14</span>: пруток к обрешётине
и к стропилу, с обеих сторон конька, по всей ширине стропила (60 мм). Так же — на вершине обвязки (пруток 30 мм).
Всего 6 прутков по 60 мм (3 рамы × 2) и 4 по 30 мм (2 обвязки × 2), ≈ 0.5 м. Усилия в этом узле малы — это обычное
опирание обрешётины; пруток нужен только чтобы шов лёг на металл.</li>
<li>Все обрешётины привариваются к обвязке, как к стропилам, — шов <span class="wk">12</span> (два прихваточных шва по
40 мм). Консоль обрешётины за обвязкой — 175 мм. Подкосов у обвязки нет.</li>
</ul>
<h3>Порядок монтажа (объект)</h3>
<ol>
<li>После установки рам 1–3 и боковых ферм — выставить половины обвязки на временных подпорках: верх вровень с верхом
стропил (по натянутому шнуру от стропил рамы), по линии в 175 мм от будущей кромки кровли. Сварить стык половин
у конька (шов <span class="wk">13</span>).</li>
<li>Уложить карнизные, коньковую и рядовые обрешётины (стыки сварены заранее), приварить к стропилам и к обвязке
(шов <span class="wk">12</span>); коньковую — через прутки Ø6 в клиновом зазоре (шов <span class="wk">14</span>).</li>
<li>Убрать подпорки — только после приварки всех обрешётин к обвязке.</li>
</ol>
<h3>Швы и проверка</h3>
<table><thead><tr><th>№</th><th>Что с чем</th><th>Шов</th><th>Где</th></tr></thead><tbody>
<tr><td><span class="wk">12</span></td><td>обрешётина (в т. ч. карнизная и коньковая) к обвязке</td><td>2 прихваточных шва по 40 мм</td><td>объект</td></tr>
<tr><td><span class="wk">13</span></td><td>стык половин обвязки у конька</td><td>встык по контуру, k=2</td><td>объект</td></tr>
<tr><td><span class="wk">14</span></td><td>коньковая обрешётина к стропилам и обвязке через пруток Ø6</td><td>пруток к обрешётине и к стропилу, по 60 мм (на обвязке — 30 мм) с каждой стороны, k=2</td><td>объект</td></tr>
</tbody></table>
<ul>
<li>Обвязка, карнизные и коньковая обрешётины проверены в общем расчёте на все сочетания снега и ветра и на нагрузку
монтажника. Сжатие в обвязке мало (до {f("Г_обвязка", "Nc"):.1f} кН); расчётная длина в вертикальной плоскости —
по её собственной устойчивости на упругих опорах-обрешётинах (≈ 1.1 м), из плоскости ската — шаг обрешётин.</li>
</ul></div>
"""

    col, raf, tie, stub, sd, sb = g["col"], g["raf"], g["tie"], g["stub"], g["sd"], g["sb"]
    page = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Узлы каркаса навеса</title>
<style>{NODE_CSS}</style></head><body><main>
<h1>Узлы каркаса навеса</h1>
<p class="sub">Сварные узлы: оголовок колонны (А), опора средней рамы на боковую ферму (Б), конец боковой фермы
у колонны (В); боковая ферма целиком и порядок сборки — цех / объект. Размеры — мм, отметки — м от верха щебня.
Узлы показаны у левого ряда колонн; у правого ряда — зеркально. <b>Сварные швы — толстые тёмно-фиолетовые линии</b>
<span style="display:inline-block;width:28px;height:5px;border-radius:3px;background:{SEAM};vertical-align:middle"></span>,
номера <span class="wk">1</span> — швы из таблиц. На разрезах рассечённые трубы показаны стенками (внутри пусто), пластины — сплошными, элементы вне
плоскости разреза — пунктиром.</p>
<div class="card"><span class="pill">колонна □{col.name}</span><span class="pill">стропило □{raf.name}</span>
<span class="pill">затяжка □{tie.name}</span><span class="pill">стойка-вставка □{stub.name}</span>
<span class="pill">раскос боковой фермы □{sd.name}</span><span class="pill">нижний пояс □{sb.name}</span></div>

<h2>Общие правила</h2>
<ul>
<li><b>Все элементы, сходящиеся в узлах А и Б, — одной ширины 60 мм</b> (колонна □{col.name} стоит широкой стороной
100 в плоскости рамы, стропило □{raf.name}, затяжка □{tie.name}, стойка □{stub.name}). Поэтому фасонки прилегают
вплотную сразу ко всем элементам — без подкладок и зазоров. Не заменяйте сечения на другие по ширине.
Боковая ферма тоже вся из труб 60 мм: раскос □{sd.name} ложится на пояс □{sb.name} на всю ширину.</li>
<li>Электроды Э42 (АНО-21, МР-3) Ø2.0–2.5 или полуавтомат проволокой 0.8 мм. Катет шва — не больше толщины
более тонкой стенки: на трубах 2 мм — k = 2 мм, 3 мм — k = 3, на колонне 4 мм и пластинах — k = 3…4.</li>
<li>Швы на трубах 2 мм вести короткими участками вразбежку, без прожога. Сначала прихватить все элементы,
проверить размеры и диагонали, затем обваривать.</li>
<li><b>Фасонки — по одной с каждой стороны узла (2 шт. на узел).</b> Всё, что оказывается между ними (торец затяжки,
торцы опорной пластины), обваривается <b>до установки фасонок</b>. Сами фасонки привариваются только по наружным
кромкам — эти швы доступны снаружи и после установки второй фасонки. Внутри, между фасонками, швов нет.</li>
<li><b>На кровле ближе 40 см к кромкам (передней, задней, карнизам) не наступать</b> — так принято в расчёте на
нагрузку монтажника. Листы у кромок укладывать с лестницы или подмостей.</li>
<li>Все торцы труб, выходящие наружу (торцы стропил в свесе, обрешётины, низ колонн), заглушить
пластинами или заглушками — внутрь не должна попадать вода.</li>
<li>Косынки на коньке не нужны: стропила стыкуются встык и обвариваются по контуру (сечение то же, что в пролёте),
подвеска и подкосы фермы привариваются по контуру.</li>
</ul>

<h2 class="pb">Порядок изготовления и монтажа</h2>
<div class="card">
<h3>В цеху</h3>
<ol>
<li><b>Колонны (4 шт.).</b> Отрезать по длинам из ведомости, низ — заглушка, верх — срез под 12° и опорная пластина
{CAP['len']}×60×{CAP['t']} (шов <span class="wk">2</span> колонна — пластина).</li>
<li><b>Крайние рамы 1 и 3.</b> На стенде по шаблону: стропила, затяжка, подвеска, подкосы фермы. <b>Фасонки узла А
в цеху не приваривать</b> — их ставят на объекте, когда рама уже стоит на колоннах (иначе рама с фасонками должна
входить на колонну впритык, 60 в 60 мм).</li>
<li><b>Средняя рама 2.</b> На том же шаблоне, но вместо колонн — две стойки-вставки □{stub.name} с опорными
пластинами; затяжка к стойкам, фасонки узла Б — всё в цеху (швы <span class="wk">1</span>–<span class="wk">3</span>).
Низ стоек открытый — его закроет столик фермы.</li>
<li><b>Боковые фермы (2 шт.).</b> На ровном столе: пояс, два раскоса, опорный столик (швы <span class="wk">6</span>,
<span class="wk">7</span>). Проверить: верх столика на {tg['plate_top'] - 2100:.0f} мм выше оси пояса, столик
горизонтален, ферма плоская. Длину пояса лучше взять по фактическому расстоянию между гранями колонн после
бетонирования (по проекту {2 * (-tg['y_face']):.0f} мм, зазор до 2 мм с каждой стороны допускается).</li>
</ol>
<h3>На объекте</h3>
<ol start="5">
<li>Забетонировать колонны; после набора прочности проверить отметки верха опорных пластин (+3.043 по оси) и
расстояние между гранями колонн на отметке +2.100 в каждом ряду.</li>
<li><b>Рамы 1 и 3</b> поставить стропилами на опорные пластины колонн, выверить, прихватить. Швы
<span class="wk">1</span> (затяжка к колонне) и <span class="wk">2</span> (пластина к стропилу), затем фасонки узла А
с двух сторон — шов <span class="wk">3</span>.</li>
<li><b>Боковые фермы</b> завести между колоннами каждого ряда. <b>Выставлять по верху столика +{tg['plate_top']/1000:.3f}</b>
(он задаёт высоту средней рамы), ось пояса при этом +2.100 ± 5 мм. Прихватить, проверить вертикальность,
обварить торцы — шов <span class="wk">5</span>.</li>
<li><b>Раму 2</b> опустить стойками на столики. Столик длиннее стойки: свободный ход ±{(Lp - 70) / 2:.0f} мм вдоль ряда и
±{(wp - 60) / 2:.0f} мм поперёк — рама ставится по разметке без подгонки. Выверить, обварить шов <span class="wk">4</span>.</li>
<li>Торцевая обвязка у переднего и заднего свеса на подпорках, затем обрешётка (узел Г); подпорки убрать.</li>
<li>Кровля.</li>
</ol></div>

<h2 class="pb">Узел А — оголовок колонны (стропило + затяжка + колонна)</h2>
{mmA}
<div class="grid2"><div class="card">{svgA}</div><div class="card">{svgA2}</div></div>
<div class="card">
<h3>Как устроен</h3>
<ul>
<li><b>Стропило проходит над колонной неразрезным</b> и уходит в свес 0.40 м (у правого ряда — 0.90 м).
Верх колонны срезан под уклон 12°, на него приварена <b>опорная пластина {CAP['len']}×60×{CAP['t']}</b>, на пластину
ложится стропило. Оси стропила и колонны пересекаются на отметке +3.100.</li>
<li><b>Затяжка</b> □{tie.name} приходит на внутреннюю грань колонны (ширина грани 60 = ширине затяжки) и
приваривается торцом по контуру, ось затяжки +3.000 (низ +2.970 — выше габарита проезда 2.90).</li>
<li><b>Фасонки обязательны: 2 шт. t=5, трапеция {gus_w:.0f} × {gus_h1:.0f}/{gus_h2:.0f} мм</b> по обе стороны узла,
ставятся на объекте после установки рамы. Подкосов в раме нет, поэтому поперечную устойчивость навеса дают жёсткие
узлы «стропило — колонна» и заделка колонн в лунки. Через узел передаётся изгибающий момент до
{f('A_колонна_оголовок', 'M'):.1f} кН·м и усилие затяжки до {f('A_затяжка', 'Nt'):.0f} кН; одних швов по контуру
труб 2–3 мм для этого мало, фасонки делают узел жёстким и разгружают тонкие стенки.</li>
<li>Верх фасонки — по оси стропила (ниже обрешётки), низ — на 50 мм ниже затяжки, наружный край — по наружной
грани колонны, внутренний — в 200 мм от оси колонны (за край проезда не выходит: проезд начинается в 400 мм).</li>
<li>Эксцентриситет 100 мм между осями затяжки и стропила учтён в расчёте (оголовок колонны работает на изгиб).</li>
</ul>
<h3>Швы</h3>
<table><thead><tr><th>№</th><th>Что с чем</th><th>Шов</th><th>Где</th></tr></thead><tbody>
<tr><td><span class="wk">1</span></td><td>торец затяжки к грани колонны</td><td>по контуру, k=2</td><td>объект</td></tr>
<tr><td><span class="wk">2</span></td><td>колонна к опорной пластине; пластина к низу стропила</td><td>по контуру колонны k=4; по торцам пластины к стропилу k=3</td><td>цех / объект</td></tr>
<tr><td><span class="wk">3</span></td><td>фасонки к колонне, стропилу и затяжке</td><td>только по наружным кромкам каждой фасонки: вертикальная кромка и низ — к колонне k=4, верхняя кромка — к стропилу k=3, торцевая кромка поперёк затяжки — k=2. Нижняя кромка между колонной и торцом — свободная</td><td>объект</td></tr>
</tbody></table>
<h3>Порядок сварки узла</h3>
<ol>
<li>Раму поставить стропилом на опорную пластину, выверить, прихватить.</li>
<li>Шов <span class="wk">1</span> — торец затяжки к грани колонны <b>по всему контуру</b>, и шов <span class="wk">2</span> —
торцы опорной пластины к стропилу. Эти места потом закроют фасонки, поэтому варить их сейчас, пока доступ открыт;
зачистить.</li>
<li>Поставить обе фасонки (прижать струбциной), прихватить; проверить, что прилегают к колонне, стропилу и затяжке.</li>
<li>Шов <span class="wk">3</span> — по наружным кромкам, попеременно: участок на одной фасонке, затем симметричный на
другой, чтобы узел не повело.</li>
</ol>
<h3>Проверка (огибающие усилия из расчёта, сочетание с ветром местности II)</h3>
<ul>
<li>Стропило: N сж = {f('A_стропило', 'Nc'):.1f} кН, M = {f('A_стропило', 'M'):.2f} кН·м; затяжка: N раст = {f('A_затяжка', 'Nt'):.1f} кН;
колонна у узла: M = {f('A_колонна_оголовок', 'M'):.2f} кН·м, поперечная сила {f('A_колонна_оголовок', 'V'):.1f} кН.</li>
<li>Шов 1 (k=2, L≈{tie_perim:.0f} мм): несущая способность ≈ {w1:.0f} кН при N = {f('A_затяжка', 'Nt'):.1f} кН — использование {u_w1:.2f}.</li>
<li>Фасонки 2×5×{gus_w:.0f} по верху колонны: σ = {sig_g:.0f} МПа, τ = {tau_g:.0f} МПа при Ry = 230 МПа — с большим запасом;
толщина 5 мм принята конструктивно (под сварку и жёсткость узла).</li>
<li>Шов 3 фасонок к колонне (2 × вертикальная кромка {gus_h1:.0f} мм, k=4) на момент узла: σ ≈ {sig_wg:.0f} МПа,
τ ≈ {tau_wg:.0f} МПа при Rwf = 180 МПа — использование {u_wg:.2f}. Усилие затяжки передаётся швом 1 (выше), поэтому
продольные швы по рёбрам затяжки не нужны.</li>
</ul></div>

<h2 class="pb">Узел Б — опора средней рамы на боковую ферму</h2>
{mmB}
<div class="card">{svgB3}
<p class="note">Аксонометрия: сверху — узел средней рамы (изготавливается в цеху вместе с рамой), снизу — вершина
боковой фермы с опорным столиком (цех). На объекте раму опускают стойкой на столик и обваривают шов 4.
Ближняя фасонка показана полупрозрачной.</p></div>
<div class="grid2"><div class="card">{svgB}</div><div class="card">{svgB2}</div></div>
<div class="card">
<h3>Как устроен</h3>
<ul>
<li><b>Верх — узел средней рамы (цех).</b> Средняя рама такая же, как крайние: стропило, затяжка, подвеска с
подкосами. Вместо колонны у неё <b>стойка-вставка □{stub.name}</b> длиной ~120 мм — от верха столика
(+{tg['plate_top']/1000:.3f}) до опорной пластины под стропилом. Затяжка приварена к грани стойки, стропило — к
опорной пластине, с двух сторон — <b>фасонки t=5, {gbw:.0f} × {gbh1:.0f}/{gbh2:.0f}</b> (низ фасонок — заподлицо с
низом стойки). Всё это варится в цеху на шаблоне рамы.</li>
<li><b>Низ — вершина боковой фермы (цех).</b> Два раскоса □{sd.name} подходят с обеих сторон вдоль ряда колонн;
верхние торцы срезаны горизонтально и приварены снизу к <b>опорному столику {Lp:.0f}×{wp:.0f}×{tpl:.0f}</b>
(опирание каждого раскоса — {foot:.0f} мм). Нижние грани раскосов сходятся под осью стойки, оси раскосов
пересекаются на отметке +{tg['apex_z']/1000:.3f} — прямо под стойкой, поэтому опорное давление рамы идёт в раскосы
без изгиба столика.</li>
<li><b>На объекте</b> раму опускают стойками на столики и обваривают по периметру низ стойки и фасонок — шов 4.
Столик шире стойки на {(wp - 60) / 2:.0f} мм с каждой стороны — под угловой шов.</li>
<li>Косынки не нужны. Вертикальная составляющая двух раскосов ≈ {2 * Nsd * sa:.0f} кН — это и есть опора средней
рамы; горизонтальные составляющие ({Nsd * ca:.0f} кН) взаимно гасятся через столик.</li>
</ul>
<h3>Швы</h3>
<table><thead><tr><th>№</th><th>Что с чем</th><th>Шов</th><th>Где</th></tr></thead><tbody>
<tr><td><span class="wk">1</span>–<span class="wk">3</span></td><td>затяжка к стойке, стойка — пластина — стропило, фасонки по наружным кромкам (как в узле А; сначала швы 1 и 2, затем фасонки)</td><td>k=2…3 (стойка 3 мм — k=3)</td><td>цех</td></tr>
<tr><td><span class="wk">4</span></td><td>низ стойки и фасонок к столику фермы</td><td>по периметру, k=3</td><td>объект</td></tr>
<tr><td><span class="wk">7</span></td><td>верхние торцы раскосов к низу столика; нижние грани раскосов между собой</td><td>по контуру опирания, k=2</td><td>цех</td></tr>
</tbody></table>
<h3>Проверка</h3>
<ul>
<li>Стойка на столике: N сж = {Nst:.1f} кН; шов 4 (k=3, L≈{L4:.0f} мм) ≈ {w4:.0f} кН — использование {Nst / w4:.2f}.</li>
<li>Раскос: N сж до {Nsd:.1f} кН; шов 7 (k=2, L≈{L67:.0f} мм) ≈ {w67:.0f} кН — использование {Nsd / w67:.2f}.</li>
<li>Столик: сжатие от распора раскосов {Nsd * ca:.1f} кН, σ = {sig_p:.0f} МПа при Ry = 230 МПа.</li>
<li>Стойка-вставка в узле рамы: N = {f('Б_стойка_вставка', 'Nc'):.1f} кН, M = {f('Б_стойка_вставка', 'M'):.2f} кН·м — проверена в общем расчёте.</li>
</ul></div>

<h2 class="pb">Боковая ферма (цеховая, 2 шт.)</h2>
<div class="card">{svgT}</div>
<div class="card">
<ul>
<li>Состав: нижний пояс □{sb.name} {2 * (-tg['y_face']):.0f} мм, два раскоса □{sd.name}, опорный столик
{Lp:.0f}×{wp:.0f}×{tpl:.0f}. Масса фермы ≈ {(sb.mass * 2 * (-tg['y_face']) / 1000 + 2 * sd.mass * tg['L_cut'] / 1000 + Lp * wp * tpl * 7.85e-6):.0f} кг —
переносится двумя людьми.</li>
<li>Раскос: заготовка {tg['L_cut']:.0f} мм, <b>оба торца — горизонтальные резы под {math.degrees(a):.1f}° к оси</b>
(длина реза по грани {foot:.0f} мм): нижний торец ложится на верх пояса вплотную к грани колонны, верхний — под
столик. Нижние грани двух раскосов сходятся под осью столика.</li>
<li><b>Обрезки заказчика:</b> оба раскоса одной из ферм режутся из обрезков □60×60×3 (2.80 и 2.70 м) — размеры и резы
те же, стенка толще (проверено расчётом). Катет шва по-прежнему k = 2 (по тонкой стенке пояса). Из обрезка 1.74 м —
короткая часть коньковой обрешётины (1.49 м) и обе стойки-вставки.</li>
<li>Оси раскоса и пояса пересекаются у грани колонны, оси раскосов — под стойкой средней рамы: ферма работает
без эксцентриситетов. Раскосы сжаты (до {Nsd:.1f} кН), пояс растянут (до {Nsb:.1f} кН).</li>
</ul></div>

<h2 class="pb">Узел В — конец боковой фермы у колонны (+2.100)</h2>
{mmC}
<div class="grid2 c"><div class="card">{svgC}</div><div class="card">{svgC2}</div></div>
<div class="card">
<h3>Как устроен</h3>
<ul>
<li><b>Цех:</b> раскос □{sd.name} лежит нижним торцом (горизонтальный рез, {foot:.0f} мм) на верхней грани пояса
□{sb.name} и приварен к нему — шов 6. Ширины одинаковые (60 = 60), стенки раскоса опираются прямо на стенки пояса.</li>
<li><b>Объект:</b> торец фермы — торец пояса и примыкающий угол раскоса — приваривается по контуру к грани колонны
шириной {g['Hc']:.0f} мм — шов 5. Пластин и косынок не нужно.</li>
<li>Оси раскоса и пояса пересекаются у грани колонны, поэтому колонна получает от фермы почти только вертикальную
опорную реакцию (≈ {Nsd * sa:.1f} кН) — без местного изгиба.</li>
</ul>
<h3>Швы</h3>
<table><thead><tr><th>№</th><th>Что с чем</th><th>Шов</th><th>Где</th></tr></thead><tbody>
<tr><td><span class="wk">5</span></td><td>торец фермы (пояс и угол раскоса) к грани колонны</td><td>по контуру, k=2</td><td>объект</td></tr>
<tr><td><span class="wk">6</span></td><td>нижний торец раскоса к верхней грани пояса</td><td>по контуру опирания, k=2</td><td>цех</td></tr>
</tbody></table>
<h3>Проверка</h3>
<ul>
<li>Шов 5 (k=2, L≈{L5:.0f} мм) ≈ {w5:.0f} кН при равнодействующей не более {R5:.1f} кН — использование {R5 / w5:.2f}.
Грань колонны под торцом фермы (продавливание стенки 4 мм): использование {f('узел_sb→col', 'u'):.2f}.</li>
<li>Шов 6 (k=2, L≈{L67:.0f} мм) ≈ {w67:.0f} кН при N раскоса {Nsd:.1f} кН — использование {Nsd / w67:.2f};
боковые стенки пояса под раскосом (EN 1993-1-8, β = 1): ≈ {N_sw:.0f} кН — использование {u_sw:.2f}.</li>
<li>Колонна ниже узла: N = {f('В_колонна_ниже','Nc'):.1f} кН, M = {f('В_колонна_ниже','M'):.2f} кН·м — проверена в общем расчёте.</li>
</ul></div>

<h2 class="pb">Стык обрешётины (22 шт.)</h2>
<div class="card" style="max-width:760px">{svgL}</div>
<div class="card"><ul>
<li>Труба 35×35 продаётся хлыстами 6 м, обрешётина — 6.98 м, поэтому она из двух частей: <b>5.49 м</b> (от переднего
края) и <b>1.49 м</b> (к заднему краю). Стык — <b>в пролёте, в 290 мм от оси стропила рамы 3</b>, у всех обрешётин
на одной линии. Там изгиб обрешётины мал, стык на стропиле не нужен.</li>
<li>Торцы частей — прямые. Обе части выставить на ровной полке (уголок, швеллер или ровная труба), зазор 1 мм,
прихватить с четырёх сторон, проверить прямолинейность, затем обварить.</li>
<li>Шов <span class="wk">8</span> — встык по всему контуру с полным проваром, k=2, короткими участками без прожога, зачистить.
Шов <span class="wk">9</span> — обрешётина к стропилу, как во всех пересечениях (два прихваточных шва по 40 мм).</li>
<li>Порядок: стык сварить заранее, на земле или на стенде — обрешётина ложится на стропила уже цельной 6.98 м.</li>
<li>Карнизные □{g['le'].name} и коньковая □{g['lr'].name} обрешётины — тоже из двух частей, стык на той же линии,
варится так же.</li>
<li>Проверка: в месте стыка коэффициент использования обрешётины ≤ 0.28 (карнизных — 0.21, коньковой — 0.18); стыковой
шов без физического контроля (Rwy = 0.85·Ry) — 0.33.</li>
</ul></div>
{secG}
<h2 class="pb">Пластины на весь навес</h2>
<div class="card"><table><thead><tr><th>Позиция</th><th>Размер, мм</th><th class="n">Кол-во</th><th>Где</th></tr></thead><tbody>
<tr><td>Фасонка узла А</td><td>трапеция {gus_w:.0f} × {gus_h1:.0f}/{gus_h2:.0f}, t=5</td><td class="n">8</td><td>узлы А (4 × 2), на объекте</td></tr>
<tr><td>Фасонка узла Б</td><td>трапеция {gbw:.0f} × {gbh1:.0f}/{gbh2:.0f}, t=5</td><td class="n">4</td><td>узлы Б (2 × 2), в цеху на средней раме</td></tr>
<tr><td>Опорная пластина</td><td>{CAP['len']}×60×{CAP['t']}</td><td class="n">6</td><td>под стропилом на колоннах и стойках</td></tr>
<tr><td>Опорный столик фермы</td><td>{Lp:.0f}×{wp:.0f}×{tpl:.0f}</td><td class="n">2</td><td>вершина боковой фермы</td></tr>
<tr><td>Заглушка низа колонны</td><td>{g['Hc']+10:.0f}×{g['Bc']+10:.0f}×4</td><td class="n">4</td><td>низ колонны в лунке</td></tr>
<tr><td>Пруток Ø6 (катанка)</td><td>60 мм — 6 шт., 30 мм — 4 шт. (≈ 0.5 м)</td><td class="n">10</td><td>клиновой зазор под коньковой обрешётиной</td></tr>
</tbody></table></div>
</main></body></html>"""
    return page


def main():
    final = json.loads((OUT / "final_design.json").read_text())
    nf = json.loads((OUT / "node_forces.json").read_text())
    (OUT / "uzly.html").write_text(build(final, nf), encoding="utf-8")
    print("output/uzly.html")


if __name__ == "__main__":
    main()
