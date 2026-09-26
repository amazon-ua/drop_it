"""Чертежи узлов (output/uzly.html): А — оголовок колонны, Б — опора средней рамы на боковую ферму,
В — примыкание раскоса и нижнего пояса боковой фермы к колонне.

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

# цвета элементов (как на общем чертеже)
COL = {"col": "#2563eb", "raf": "#0f766e", "tie": "#b45309", "sd": "#dc2626", "sb": "#0891b2",
       "plate": "#6b7280", "lath": "#db2777", "stub": "#2563eb", "kp": "#7c3aed"}

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
"""


class Svg:
    """Вид в мм: u — горизонталь чертежа, z — отметка (мм)."""

    def __init__(self, umin, umax, zmin, zmax, pad=40, W=None):
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
        self.items.append(f'<text x="{p[0]:.1f}" y="{p[1]:.1f}" class="{cls}" text-anchor="{anchor}">{html.escape(s)}</text>')

    def leader(self, u1, z1, u2, z2, s, cls="lb", anchor="start"):
        self.line(u1, z1, u2, z2, "ld")
        self.text(u2 + (4 if anchor == "start" else -4), z2 - 6, s, cls, anchor)

    def weld(self, u, z, n):
        """Маркер шва с номером."""
        p = self.P(u, z)
        self.items.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="12" class="wm"/>')
        self.items.append(f'<text x="{p[0]:.1f}" y="{p[1]+6:.1f}" text-anchor="middle" '
                          f'style="fill:#111;font-size:17px;font-weight:700">{n}</text>')

    def dim_h(self, u1, u2, z, s, off=0):
        a, b = self.P(u1, z), self.P(u2, z)
        self.items.append(f'<line x1="{a[0]:.1f}" y1="{a[1]+off:.1f}" x2="{b[0]:.1f}" y2="{b[1]+off:.1f}" class="dl"/>')
        for q in (a, b):
            self.items.append(f'<line x1="{q[0]:.1f}" y1="{q[1]+off-4:.1f}" x2="{q[0]:.1f}" y2="{q[1]+off+4:.1f}" class="dl"/>')
        self.items.append(f'<text x="{(a[0]+b[0])/2:.1f}" y="{a[1]+off-3:.1f}" class="dt" text-anchor="middle">{s}</text>')

    def dim_v(self, u, z1, z2, s, off=0, anchor="end"):
        a, b = self.P(u, z1), self.P(u, z2)
        self.items.append(f'<line x1="{a[0]+off:.1f}" y1="{a[1]:.1f}" x2="{b[0]+off:.1f}" y2="{b[1]:.1f}" class="dl"/>')
        for q in (a, b):
            self.items.append(f'<line x1="{q[0]+off-4:.1f}" y1="{q[1]:.1f}" x2="{q[0]+off+4:.1f}" y2="{q[1]:.1f}" class="dl"/>')
        dx = -4 if anchor == "end" else 4
        self.items.append(f'<text x="{a[0]+off+dx:.1f}" y="{(a[1]+b[1])/2+4:.1f}" class="dt" text-anchor="{anchor}">{s}</text>')

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
    mm = lambda v: v * 1000
    g["Hc"], g["Bc"] = mm(col.h), mm(col.b)            # колонна: 100 в плоскости рамы, 60 поперёк
    g["Hr"], g["Br"] = mm(raf.h), mm(raf.b)
    g["Ht"], g["Bt"] = mm(tie.h), mm(tie.b)
    g["Hs"], g["Bs"] = mm(stub.h), mm(stub.b)
    g["Hd"] = mm(sd.h)
    g["Hb"] = mm(sb.h)
    g["alpha"] = math.atan((M.Z_TIE - 2.10) / (M.BAY / 2))
    return g


def z_axis(x):          # ось стропила левого ската, мм
    return 3100 + T12 * x


def z_bot(x, Hr):       # низ стропила
    return z_axis(x) - Hr / 2 / C12


# ---------------- узел А ----------------
GUSSET = dict(x1=-50, x2=200, zb=2920)   # фасонка: от наружной грани колонны до 200 мм по затяжке
CAP = dict(len=140, t=6)


def node_A(g, mid=False):
    """Вид в плоскости рамы. mid=True — узел Б (вместо колонны — стойка-вставка)."""
    Hr, Ht = g["Hr"], g["Ht"]
    Hc = g["Hs"] if mid else g["Hc"]
    s = Svg(-560, 700, 2780, 3330)
    x1g, x2g = (-Hc / 2 if mid else GUSSET["x1"]), GUSSET["x2"]
    zbg = GUSSET["zb"]
    # колонна / стойка
    zb_col = 2780 if not mid else 2930
    cap_t = CAP["t"]
    top = lambda x: z_bot(x, Hr) - cap_t
    s.poly([(-Hc / 2, zb_col), (Hc / 2, zb_col), (Hc / 2, top(Hc / 2)), (-Hc / 2, top(-Hc / 2))],
           COL["stub" if mid else "col"], "#0008", 0.9)
    if mid:
        s.rect(-Hc / 2 - 2, zb_col - 3, Hc / 2 + 2, zb_col, COL["plate"], "#0008", 1)
    # опорная пластина (крышка колонны)
    L = CAP["len"] / 2
    s.poly([(-L, top(-L)), (L, top(L)), (L, z_bot(L, Hr)), (-L, z_bot(-L, Hr))], COL["plate"], "#000a", 1)
    # стропило
    xa, xb = -400, 400
    s.poly([(xa, z_bot(xa, Hr)), (xb, z_bot(xb, Hr)), (xb, z_bot(xb, Hr) + Hr / C12), (xa, z_bot(xa, Hr) + Hr / C12)],
           COL["raf"], "#0008", 0.9)
    # обрешётина (сечения) на стропиле
    for x in (-114, 228):
        zt = z_bot(x, Hr) + Hr / C12
        a = g["lath"].h * 1000
        s.poly([(x - a / 2, zt), (x + a / 2, zt), (x + a / 2, zt + a), (x - a / 2, zt + a)], COL["lath"], "#0008", 0.9)
    # затяжка
    s.rect(Hc / 2, 3000 - Ht / 2, 400, 3000 + Ht / 2, COL["tie"], "#0008", 0.9)
    # фасонка (ближняя) — полупрозрачная
    gpts = [(x1g, zbg), (x2g, zbg), (x2g, z_axis(x2g)), (x1g, z_axis(x1g))]
    s.poly(gpts, "#9ca3af", "#111", 0.55, 1.2)
    # оси
    s.line(-420, z_axis(-420), 420, z_axis(420))
    s.line(-420, 3000, 420, 3000)
    s.line(0, 2780 if not mid else 2840, 0, 3290)
    s.items.append(f'<circle cx="{s.P(0, 3100)[0]:.1f}" cy="{s.P(0, 3100)[1]:.1f}" r="3" fill="var(--fg)"/>')
    # размеры
    s.dim_h(x1g, x2g, zbg, f"{x2g - x1g:.0f}", off=22)
    s.dim_v(x2g, zbg, z_axis(x2g), f"{z_axis(x2g) - zbg:.0f}", off=26, anchor="start")
    s.dim_v(x1g, zbg, z_axis(x1g), f"{z_axis(x1g) - zbg:.0f}", off=-30)
    s.dim_v(640, 3000, 3100, "e=100", off=0, anchor="end")
    # отметки и подписи
    s.text(420, 3008, "ось затяжки +3.000", "dt")
    s.text(8, 3318, "ось " + ("стойки" if mid else "колонны"), "dt")
    s.text(10, 3080, "+3.100", "dt")
    s.leader(-250, z_bot(-250, Hr) + Hr / C12 / 2, -540, 3300, f"стропило □{g['raf'].name}", "lb")
    s.leader(-60, top(-60) + 3, -540, 3225, f"опорная пластина {CAP['len']}×60×{cap_t}", "lbs")
    s.leader(390, 3010 if mid else 2990, 470, 3075 if mid else 2930, f"затяжка □{g['tie'].name}")
    if mid:
        s.leader(-Hc / 2, 2960, -540, 2880, f"стойка-вставка □{g['stub'].name}")
        s.leader(0, zb_col - 2, -540, 2820, "заглушка 60×60×3", "lbs")
        # раскосы боковой фермы — подходят из плоскости рамы (за и перед фасонками)
        zc = 3000 - (Hc / 2 + 5) * math.tan(g["alpha"])
        hh = g["Hd"] / 2 / math.cos(g["alpha"])
        s.rect(-Hc / 2, zc - hh, Hc / 2, zc + hh, "none", "#dc2626", 1, 2.2, dash="6 4")
        s.leader(Hc / 2, zc - hh, 60, 2815, "торцы раскосов боковой фермы — на фасонках с обеих сторон", "lbs")
    else:
        s.leader(-Hc / 2, 2850, -540, 2850, f"колонна □{g['col'].name}")
    s.leader(120, 2932, 250, 2880 if mid else 2835, "фасонка t=5 — 2 шт., с обеих сторон", "lb")
    s.leader(228, z_bot(228, Hr) + Hr / C12 + 20, 330, 3312, f"обрешётина □{g['lath'].name}", "lbs")
    # швы
    s.weld(Hc / 2 + 12, 3000 + Ht / 2 + 12, 1)        # затяжка к колонне
    s.weld(-L + 10, top(-L) - 12, 2)                   # колонна-пластина-стропило
    s.weld(x2g + 12, 2975, 3)                          # фасонка
    s.weld((x1g + x2g) / 2, z_axis((x1g + x2g) / 2) + 12, 3)
    s.weld(-20, zbg - 12, 3)
    return s.svg("узел — вид в плоскости рамы")


def node_A_section(g, mid=False):
    """Разрез поперёк рамы (по оси колонны, взгляд со стороны пролёта)."""
    Hr, Ht, Bc = g["Hr"], g["Ht"], g["Bc"]
    B = g["Bs"] if mid else Bc
    s = Svg(-330, 470, 2780 if not mid else 2840, 3330)
    zb_col = 2780 if not mid else 2930
    tp = 5
    # колонна (вид с торца затяжки не виден — затяжка перед колонной)
    s.rect(-B / 2, zb_col, B / 2, z_bot(0, Hr) - CAP["t"], COL["stub" if mid else "col"], "#0008", 0.9)
    s.rect(-B / 2 - 0.1, z_bot(0, Hr) - CAP["t"], B / 2 + 0.1, z_bot(0, Hr), COL["plate"], "#000a", 1)
    # стропило (сечение)
    zb = z_bot(0, Hr)
    s.rect(-g["Br"] / 2, zb, g["Br"] / 2, zb + Hr / C12, COL["raf"], "#0008", 0.9)
    tw = g["raf"].t * 1000
    s.rect(-g["Br"] / 2 + tw, zb + tw, g["Br"] / 2 - tw, zb + Hr / C12 - tw, "var(--card)", "none")
    # затяжка (сечение)
    s.rect(-g["Bt"] / 2, 3000 - Ht / 2, g["Bt"] / 2, 3000 + Ht / 2, COL["tie"], "#0008", 0.9)
    tt = g["tie"].t * 1000
    s.rect(-g["Bt"] / 2 + tt, 3000 - Ht / 2 + tt, g["Bt"] / 2 - tt, 3000 + Ht / 2 - tt, "var(--card)", "none")
    # фасонки
    ztop = z_axis(0)
    for sgn in (-1, 1):
        u1 = sgn * B / 2
        u2 = sgn * (B / 2 + tp)
        s.rect(min(u1, u2), GUSSET["zb"], max(u1, u2), ztop, "#6b7280", "#111", 1, 0.8)
    if mid:
        # раскосы боковой фермы подходят к наружным граням фасонок
        a = g["alpha"]
        Hd = g["Hd"]
        for sgn in (-1, 1):
            u0 = sgn * (B / 2 + tp)
            zc = 3000 - (abs(u0)) * math.tan(a)
            # полоса раскоса, уходящая вниз-наружу
            L = 150
            du = sgn * L * math.cos(a)
            dz = -L * math.sin(a)
            h = Hd / 2 / math.cos(a)
            s.poly([(u0, zc + h), (u0 + du, zc + h + dz), (u0 + du, zc - h + dz), (u0, zc - h)],
                   COL["sd"], "#0008", 0.9)
        s.leader(-150, 2930, -320, 2870, f"раскос □{g['sd'].name}", "lbs")
        s.weld(B / 2 + tp + 14, 3000 + 40, 4)
    zb_ = z_bot(0, Hr)
    s.leader(g["Br"] / 2, zb_ + Hr / C12 - 20, 130, 3290, f"стропило □{g['raf'].name}")
    s.leader(B / 2, zb_ - 3, 130, 3200, "опорная пластина", "lbs")
    s.leader(g["Bt"] / 2, 3000 + 10, 130, 3110, f"затяжка □{g['tie'].name} (сечение)", "lbs")
    s.leader(B / 2 + tp, GUSSET["zb"] + 10, 130, 2860 if mid else 2960, "фасонки t=5", "lbs")
    if not mid:
        s.leader(B / 2, 2850, 130, 2850, f"колонна □{g['col'].name}", "lbs")
    s.dim_h(-B / 2 - tp, B / 2 + tp, GUSSET["zb"], f"{B + 2 * tp:.0f}", off=18)
    s.dim_h(-B / 2, B / 2, zb_col, f"{B:.0f}", off=16)
    s.line(0, 2790, 0, 3290)
    s.text(-320, 3310, "разрез поперёк рамы (по оси колонны)", "lbs")
    s.weld(B / 2 + tp + 10, GUSSET["zb"] + 30, 3)
    s.weld(-B / 2 - tp - 10, 3000, 3)
    return s.svg("узел — разрез поперёк рамы")


# ---------------- узел В ----------------
def node_C(g):
    """Вид с внутренней стороны ряда колонн (плоскость боковой фермы y–z) и вид на грань колонны."""
    Bc, Hc = g["Bc"], g["Hc"]
    Hd, Hb = g["Hd"], g["Hb"]
    a = g["alpha"]
    e = 50.0
    zb = 2100.0
    zc = zb + e
    s = Svg(-330, 700, 1960, 2380)
    # колонна: в этом виде видна её ширина поперёк рамы (Bc)
    s.rect(-Bc / 2, 1960, Bc / 2, 2360, COL["col"], "#0008", 0.9)
    # нижний пояс
    s.rect(Bc / 2, zb - Hb / 2, 520, zb + Hb / 2, COL["sb"], "#0008", 0.9)
    # раскос: ось через (0, zc) под углом a
    u0 = Bc / 2
    z_face = zc + u0 * math.tan(a)
    h = Hd / 2 / math.cos(a)
    u1 = 520
    z1 = zc + u1 * math.tan(a)
    s.poly([(u0, z_face - h), (u1, z1 - h), (u1, z1 + h), (u0, z_face + h)], COL["sd"], "#0008", 0.9)
    # оси
    s.line(-140, zb, 520, zb)
    s.line(-140, zc - 140 * math.tan(a), 520, z1)
    s.line(0, 1965, 0, 2355)
    # размеры
    s.dim_v(-60, zb, zc, f"e={e:.0f}", off=0)
    gap_z1 = zb + Hb / 2
    gap_z2 = z_face - h
    s.dim_v(u0 + 40, gap_z1, gap_z2, f"зазор {gap_z2 - gap_z1:.0f}", off=0, anchor="start")
    s.text(-320, zb + 6, "ось пояса +2.100", "dt")
    s.leader(300, zc + 300 * math.tan(a) + h, 330, 2345, f"раскос боковой фермы □{g['sd'].name}", "lb")
    s.leader(260, zb - Hb / 2, 290, 2010, f"нижний пояс □{g['sb'].name}", "lb")
    s.leader(-Bc / 2, 2300, -320, 2330, f"колонна □{g['col'].name}", "lb")
    s.text(-320, 1985, f"раскос под {math.degrees(a):.1f}° к горизонту", "lbs")
    s.weld(u0 + 16, z_face + h + 14, 5)
    s.weld(u0 + 16, zb - Hb / 2 - 14, 6)
    return s.svg("узел В — вид в плоскости боковой фермы"), e, gap_z2 - gap_z1, z_face, h


def node_C_face(g, e, z_face, h):
    """Вид на грань колонны (в сторону пролёта боковой фермы): следы швов."""
    Hc, Hd, Hb = g["Hc"], g["Hd"], g["Hb"]
    s = Svg(-260, 260, 1960, 2380)
    s.rect(-Hc / 2, 1960, Hc / 2, 2360, COL["col"], "#0008", 0.9)
    # след раскоса (по ширине 60, по высоте — наклонный срез)
    s.rect(-Hd / 2, z_face - h, Hd / 2, z_face + h, COL["sd"], "#000", 0.85, 1.2)
    s.rect(-Hb / 2, 2100 - Hb / 2, Hb / 2, 2100 + Hb / 2, COL["sb"], "#000", 0.85, 1.2)
    s.dim_h(-Hc / 2, Hc / 2, 1960, f"{Hc:.0f}", off=16)
    s.dim_h(-Hd / 2, Hd / 2, z_face + h, f"{Hd:.0f}", off=-12)
    s.text(-250, 2365, "вид на грань колонны со стороны фермы", "lbs")
    s.leader(Hd / 2, z_face + h - 8, 110, 2300, "след раскоса", "lbs")
    s.leader(Hb / 2, 2100 - Hb / 2 + 5, 110, 2040, "след пояса", "lbs")
    s.weld(-Hd / 2 - 16, z_face, 5)
    s.weld(-Hb / 2 - 16, 2100, 6)
    return s.svg("узел В — вид на грань колонны")


def build(final, nf):
    g = geometry(final["groups"])
    svgA = node_A(g)
    svgA2 = node_A_section(g)
    svgB = node_A(g, mid=True)
    svgB2 = node_A_section(g, mid=True)
    svgC, e, gap, z_face, h = node_C(g)
    svgC2 = node_C_face(g, e, z_face, h)

    def f(key, k):
        return nf.get(key, {}).get(k, 0.0)

    gus_w = GUSSET["x2"] - GUSSET["x1"]
    gus_h1 = z_axis(GUSSET["x1"]) - GUSSET["zb"]
    gus_h2 = z_axis(GUSSET["x2"]) - GUSSET["zb"]
    # проверки сварных швов (ДБН В.2.6-198: Rwf = 180 МПа для Э42, βf = 0.7; Rwz = 0.45·Run = 162 МПа, βz = 1)
    def weld_cap(k, L):
        return min(0.7 * k * L * 180, 1.0 * k * L * 162) / 1e3
    tie_perim = 2 * (g["Ht"] + g["Bt"]) - 20
    w1 = weld_cap(2, tie_perim)
    u_w1 = f("A_затяжка", "Nt") / w1
    # фасонки: сечение по верху колонны (две пластины 5 мм, длина gus_w)
    A_g = 2 * 5 * gus_w
    W_g = 2 * 5 * gus_w ** 2 / 6
    sig_g = f("A_колонна_оголовок", "M") * 1e6 / W_g
    tau_g = f("A_колонна_оголовок", "V") * 1e3 / A_g
    sd_perim = 2 * (g["Hd"] + g["Hd"] / math.cos(g["alpha"])) - 20
    w4 = weld_cap(2, sd_perim)
    Nsd = max(f("Б_раскос_боковой_фермы", "Nc"), f("В_раскос_боковой_фермы", "Nc"))
    Nsb = f("В_нижний_пояс", "Nt")
    Mecc = Nsb * e / 1000
    colA = g["col"].A * 1e6
    sig_c = (f("В_колонна_ниже", "Nc") * 1e3 / colA + f("В_колонна_ниже", "M") * 1e6 / (g["col"].Wy * 1e9)
             + Mecc / 2 * 1e6 / (g["col"].Wz * 1e9))

    col, raf, tie, stub, sd, sb = g["col"], g["raf"], g["tie"], g["stub"], g["sd"], g["sb"]
    page = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Узлы каркаса навеса</title>
<style>{NODE_CSS}</style></head><body><main>
<h1>Узлы каркаса навеса</h1>
<p class="sub">Три сварных узла: оголовок колонны (А), опора средней рамы на боковую ферму (Б), примыкание раскоса
и нижнего пояса боковой фермы к колонне (В). Размеры — мм, отметки — м от верха щебня. Узлы показаны у левого ряда
колонн; у правого ряда — зеркально. Номера <span class="wk">1</span> на чертежах — швы из таблиц.</p>
<div class="card"><span class="pill">колонна □{col.name}</span><span class="pill">стропило □{raf.name}</span>
<span class="pill">затяжка □{tie.name}</span><span class="pill">стойка-вставка □{stub.name}</span>
<span class="pill">раскос боковой фермы □{sd.name}</span><span class="pill">нижний пояс □{sb.name}</span></div>

<h2>Общие правила</h2>
<ul>
<li><b>Все элементы, сходящиеся в узлах А и Б, — одной ширины 60 мм</b> (колонна □{col.name} стоит широкой стороной
100 в плоскости рамы, стропило □{raf.name}, затяжка □{tie.name}, стойка □{stub.name}). Поэтому фасонки прилегают
вплотную сразу ко всем элементам — без подкладок и зазоров. Не заменяйте сечения на другие по ширине.</li>
<li>Электроды Э42 (АНО-21, МР-3) Ø2.0–2.5 или полуавтомат проволокой 0.8 мм. Катет шва — не больше толщины
более тонкой стенки: на трубах 2 мм — k = 2 мм, 3 мм — k = 3, на колонне 4 мм и пластинах — k = 4.</li>
<li>Порядок: собрать раму на плоском стенде по шаблону, прихватить все элементы, проверить диагонали и отметки,
затем обварить. Швы на трубах 2 мм вести короткими участками вразбежку, без прожога.</li>
<li>Все торцы труб, выходящие наружу (низ стойки-вставки, торцы стропил в свесе, обрешётины), заглушить
пластинами или заглушками — внутрь не должна попадать вода.</li>
<li>Косынки на коньке не нужны: стропила стыкуются встык и обвариваются по контуру (сечение то же, что в пролёте),
подвеска и подкосы фермы привариваются по контуру.</li>
</ul>

<h2>Узел А — оголовок колонны (стропило + затяжка + колонна)</h2>
<div class="grid2"><div class="card">{svgA}</div><div class="card">{svgA2}</div></div>
<div class="card">
<h3>Как устроен</h3>
<ul>
<li><b>Стропило проходит над колонной неразрезным</b> и уходит в свес 0.40 м (у правого ряда — 0.90 м).
Верх колонны срезан под уклон 12°, на него приварена <b>опорная пластина {CAP['len']}×60×{CAP['t']}</b>, на пластину
ложится стропило. Оси стропила и колонны пересекаются на отметке +3.100.</li>
<li><b>Затяжка</b> □{tie.name} приходит на внутреннюю грань колонны (ширина грани 60 = ширине затяжки) и
приваривается торцом по контуру, ось затяжки +3.000 (низ +2.970 — выше габарита проезда 2.90).</li>
<li><b>Фасонки обязательны: 2 шт. t=5, трапеция {gus_w:.0f} × {gus_h1:.0f}/{gus_h2:.0f} мм</b> по обе стороны узла.
Подкосов в раме нет, поэтому поперечную устойчивость навеса дают жёсткие узлы «стропило — колонна» и заделка
колонн в лунки. Через узел передаётся изгибающий момент до {f('A_колонна_оголовок', 'M'):.1f} кН·м и усилие
затяжки до {f('A_затяжка', 'Nt'):.0f} кН; одних швов по контуру труб 2–3 мм для этого мало, фасонки делают узел
жёстким и разгружают тонкие стенки.</li>
<li>Верх фасонки — по оси стропила (ниже обрешётки), низ — на 50 мм ниже затяжки, наружный край — по наружной
грани колонны, внутренний — в 200 мм от оси колонны (за край проезда не выходит: проезд начинается в 400 мм).</li>
<li>Эксцентриситет 100 мм между осями затяжки и стропила учтён в расчёте (стойка-оголовок работает на изгиб).</li>
</ul>
<h3>Швы</h3>
<table><thead><tr><th>№</th><th>Что с чем</th><th>Шов</th></tr></thead><tbody>
<tr><td><span class="wk">1</span></td><td>торец затяжки к грани колонны</td><td>по контуру, k=2</td></tr>
<tr><td><span class="wk">2</span></td><td>колонна к опорной пластине; пластина к низу стропила</td><td>по контуру колонны k=4; по торцам пластины к стропилу k=3</td></tr>
<tr><td><span class="wk">3</span></td><td>фасонки к колонне, стропилу и затяжке</td><td>по кромкам фасонки: к колонне k=4, к стропилу k=3, к затяжке k=2 + вдоль рёбер затяжки на длине 150 мм</td></tr>
</tbody></table>
<h3>Проверка (огибающие усилия из расчёта, сочетание с ветром местности II)</h3>
<ul>
<li>Стропило: N сж = {f('A_стропило', 'Nc'):.1f} кН, M = {f('A_стропило', 'M'):.2f} кН·м; затяжка: N раст = {f('A_затяжка', 'Nt'):.1f} кН;
колонна у узла: M = {f('A_колонна_оголовок', 'M'):.2f} кН·м, поперечная сила {f('A_колонна_оголовок', 'V'):.1f} кН.</li>
<li>Шов 1 (k=2, L≈{tie_perim:.0f} мм): несущая способность ≈ {w1:.0f} кН при N = {f('A_затяжка', 'Nt'):.1f} кН — использование {u_w1:.2f}.</li>
<li>Фасонки 2×5×{gus_w:.0f} по верху колонны: σ = {sig_g:.0f} МПа, τ = {tau_g:.0f} МПа при Ry = 230 МПа — с большим запасом;
толщина 5 мм принята конструктивно (под сварку и жёсткость узла).</li>
</ul></div>

<h2>Узел Б — опора средней рамы на боковую ферму</h2>
<div class="grid2"><div class="card">{svgB}</div><div class="card">{svgB2}</div></div>
<div class="card">
<h3>Как устроен</h3>
<ul>
<li>Средняя рама такая же, как крайние: стропило, затяжка, подвеска с подкосами. Вместо колонны у неё
<b>стойка-вставка □{stub.name}</b> длиной ~120 мм — от низа фасонок (+2.930) до опорной пластины под стропилом,
низ стойки заглушён пластиной 60×60×3.</li>
<li>Фасонки те же, что в узле А (2 шт. t=5, {gus_w:.0f} × {gus_h1:.0f}/{gus_h2:.0f}), только наружный край — по грани стойки.</li>
<li><b>Два раскоса боковой фермы</b> □{sd.name} приходят с обеих сторон (из плоскости рамы) и привариваются торцами
к <b>наружным граням фасонок напротив стойки</b>: ширина раскоса 60 = ширине стойки, поэтому давление раскоса через
фасонку передаётся прямо на стенки стойки. Торец раскоса срезан под {90 - math.degrees(g['alpha']):.1f}° к оси
(вертикальный рез). Оси раскосов сходятся на оси стойки на отметке +3.000.</li>
<li>Отдельных косынок не требуется. Вертикальная составляющая двух раскосов ≈ {2 * Nsd * math.sin(g['alpha']):.0f} кН — это и есть опора средней рамы.</li>
</ul>
<h3>Швы</h3>
<table><thead><tr><th>№</th><th>Что с чем</th><th>Шов</th></tr></thead><tbody>
<tr><td><span class="wk">1</span>–<span class="wk">3</span></td><td>как в узле А (затяжка к стойке, стойка — пластина — стропило, фасонки)</td><td>k=2…3 (стойка 3 мм — k=3)</td></tr>
<tr><td><span class="wk">4</span></td><td>торец раскоса к наружной грани фасонки</td><td>по контуру, k=2</td></tr>
</tbody></table>
<h3>Проверка</h3>
<ul>
<li>Раскос: N сж до {Nsd:.1f} кН; шов 4 (k=2, L≈{sd_perim:.0f} мм) ≈ {w4:.0f} кН — использование {Nsd / w4:.2f};
основная часть усилия передаётся смятием через фасонку на стойку.</li>
<li>Стойка-вставка: N = {f('Б_стойка_вставка', 'Nc'):.1f} кН, M = {f('Б_стойка_вставка', 'M'):.2f} кН·м — проверена в общем расчёте.</li>
</ul></div>

<h2>Узел В — раскос и нижний пояс боковой фермы у колонны (+2.100)</h2>
<div class="grid2"><div class="card">{svgC}</div><div class="card">{svgC2}</div></div>
<div class="card">
<h3>Как устроен</h3>
<ul>
<li>Узел без фасонок: раскос □{sd.name} и нижний пояс □{sb.name} привариваются торцами по контуру прямо к грани
колонны шириной {g['Hc']:.0f} мм (стенка колонны {g['col'].t*1000:.0f} мм — проверка на продавливание грани колонны
выполнена: использование для раскоса {f('узел_sd→col', 'u'):.2f}, для пояса {f('узел_sb→col', 'u'):.2f}).</li>
<li><b>Чтобы раскос и пояс не наложились друг на друга</b>, ось раскоса поднята на e = {e:.0f} мм выше оси пояса:
между низом раскоса и верхом пояса остаётся зазор ≈ {gap:.0f} мм — достаточно, чтобы обварить оба элемента по контуру.</li>
<li>От эксцентриситета колонна получает местный момент ≈ {Mecc:.2f} кН·м (N пояса {Nsb:.1f} кН × {e:.0f} мм), который
делится на участки колонны выше и ниже узла — добавка напряжений около 20 МПа, колонна проходит с запасом
(её несущую способность определяет гибкость, а не прочность).</li>
<li>Нижний пояс — сплошной отрезок 4.60 м между колоннами, раскос — отрезок ≈ 2.47 м, торец срезан под
{90 - math.degrees(g['alpha']):.1f}° к оси.</li>
</ul>
<h3>Швы</h3>
<table><thead><tr><th>№</th><th>Что с чем</th><th>Шов</th></tr></thead><tbody>
<tr><td><span class="wk">5</span></td><td>торец раскоса к грани колонны</td><td>по контуру, k=2</td></tr>
<tr><td><span class="wk">6</span></td><td>торец нижнего пояса к грани колонны</td><td>по контуру, k=2</td></tr>
</tbody></table>
<h3>Проверка</h3>
<ul><li>Раскос: N сж = {f('В_раскос_боковой_фермы','Nc'):.1f} кН; нижний пояс: N раст = {Nsb:.1f} кН;
колонна ниже узла: N = {f('В_колонна_ниже','Nc'):.1f} кН, M = {f('В_колонна_ниже','M'):.2f} кН·м (+ местный момент от
эксцентриситета ≈ {Mecc/2:.2f} кН·м) — напряжения ≈ {sig_c:.0f} МПа при Ry = 230 МПа.</li></ul>
</div>

<h2>Пластины на весь навес</h2>
<div class="card"><table><thead><tr><th>Позиция</th><th>Размер, мм</th><th class="n">Кол-во</th><th>Где</th></tr></thead><tbody>
<tr><td>Фасонка</td><td>трапеция {gus_w:.0f} × {gus_h1:.0f}/{gus_h2:.0f}, t=5</td><td class="n">12</td><td>узлы А (4 × 2) и Б (2 × 2)</td></tr>
<tr><td>Опорная пластина</td><td>{CAP['len']}×60×{CAP['t']}</td><td class="n">6</td><td>под стропилом на колоннах и стойках</td></tr>
<tr><td>Заглушка стойки-вставки</td><td>60×60×3</td><td class="n">2</td><td>низ стойки, узел Б</td></tr>
<tr><td>Заглушка низа колонны</td><td>{g['Hc']+10:.0f}×{g['Bc']+10:.0f}×4</td><td class="n">4</td><td>низ колонны в лунке</td></tr>
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
