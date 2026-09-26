"""HTML-чертёж оптимизированного каркаса (фасад, вид сбоку, план) + таблицы."""
from __future__ import annotations

import html
import math

import numpy as np

import model as M

COLORS = {
    "col": "#2563eb", "raf": "#0f766e", "tie": "#b45309", "kp": "#7c3aed", "strut": "#7c3aed",
    "knee": "#16a34a", "lath": "#db2777", "sd": "#dc2626", "sb": "#0891b2", "st": "#0891b2",
    "stub": "#2563eb", "eave": "#0891b2", "kl": "#16a34a", "xb": "#ca8a04",
}


def _svg_view(model, sc, view, W=900, H=420, pad=50):
    """view: 'front' (x–z при y=0), 'side' (y–z при x=0), 'plan' (x–y)."""
    nodes = model.nodes
    segs = []
    for e in model.elems:
        p1, p2 = nodes[e.n1], nodes[e.n2]
        g = model.members[e.member]["group"]
        if view == "front":
            # рама 1 (логическая y = 0); в плоскости рамы откладываем расстояние от левой колонны
            if abs(model.logical_y(p1)) > 1e-6 or abs(model.logical_y(p2)) > 1e-6:
                continue
            if g == "lath":
                continue
            a, b = (p1[0], p1[2]), (p2[0], p2[2])
        elif view == "side":
            if abs(p1[0]) > 1e-6 or abs(p2[0]) > 1e-6:
                continue
            if g == "lath":
                continue
            a, b = (p1[1], p1[2]), (p2[1], p2[2])
        else:
            if g in ("col", "knee", "sd", "sb", "kl", "stub", "kp", "strut", "tie"):
                continue
            a, b = (p1[0], p1[1]), (p2[0], p2[1])
        segs.append((a, b, g, e.sec))
    if view == "front":
        xmin, xmax, ymin, ymax = -1.9, M.SPAN + 2.0, -0.4, 4.0
    elif view == "side":
        xmin, xmax, ymin, ymax = M.Y_MIN - 0.3, M.Y_MAX + 0.3, -0.4, 4.0
    else:
        xmin, xmax, ymin, ymax = -0.9, M.SPAN + 1.2, M.Y_MIN - 0.3, M.Y_MAX + 0.6
    sx = (W - 2 * pad) / (xmax - xmin)
    sy = (H - 2 * pad) / (ymax - ymin)
    s = min(sx, sy)
    W2 = int((xmax - xmin) * s + 2 * pad)
    H2 = int((ymax - ymin) * s + 2 * pad)

    def T(p):
        return pad + (p[0] - xmin) * s, H2 - pad - (p[1] - ymin) * s

    out = [f'<svg viewBox="0 0 {W2} {H2}" class="drw" role="img" aria-label="{view}">']
    if view in ("front", "side"):
        gx1, gy = T((xmin, 0.0))
        gx2, _ = T((xmax, 0.0))
        out.append(f'<line x1="{gx1:.1f}" y1="{gy:.1f}" x2="{gx2:.1f}" y2="{gy:.1f}" class="ground"/>')
    if view == "front":
        x1, y1 = T((M.CORRIDOR_X[0], M.CORRIDOR_H))
        x2, y2 = T((M.CORRIDOR_X[1], 0.0))
        out.append(f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{x2-x1:.1f}" height="{y2-y1:.1f}" class="corr"/>')
        out.append(f'<text x="{(x1+x2)/2:.1f}" y="{(y1+y2)/2:.1f}" class="corrt">проезд 4.00 × 2.90</text>')
        # сечения обрешётки на стропилах
        for (x, z, trib, side) in model.rows:
            px, py = T((x, z + 0.05))
            w = sc.groups["lath"].b * s
            h = sc.groups["lath"].h * s
            out.append(f'<rect x="{px-w/2:.1f}" y="{py-h/2:.1f}" width="{max(w,2):.1f}" height="{max(h,2):.1f}" '
                       f'fill="{COLORS["lath"]}"/>')
    if view == "plan":
        # контур кровли — параллелограмм (косина площадки)
        corners = [(-M.OVH_L, M.Y_MIN), (M.SPAN + M.OVH_R, M.Y_MIN), (M.SPAN + M.OVH_R, M.Y_MAX), (-M.OVH_L, M.Y_MAX)]
        pts = " ".join(f"{T(model.phys((x, y, 0))[:2])[0]:.1f},{T(model.phys((x, y, 0))[:2])[1]:.1f}" for x, y in corners)
        out.append(f'<polygon points="{pts}" class="roof"/>')
        for xc in (0.0, M.SPAN):
            for yc in (0.0, M.BAY):
                c = T(model.phys((xc, yc, 0))[:2])
                w = sc.groups["col"].b * s
                out.append(f'<rect x="{c[0]-w/2:.1f}" y="{c[1]-w/2:.1f}" width="{w:.1f}" height="{w:.1f}" '
                           f'fill="{COLORS["col"]}"/>')
        x1, _ = T((M.CORRIDOR_X[0], 0))
        x2, _ = T((M.CORRIDOR_X[1], 0))
        out.append(f'<line x1="{x1:.1f}" y1="{pad/2}" x2="{x1:.1f}" y2="{H2-pad/2}" class="corrl"/>')
        out.append(f'<line x1="{x2:.1f}" y1="{pad/2}" x2="{x2:.1f}" y2="{H2-pad/2}" class="corrl"/>')
    order = ["lath", "xb", "sb", "st", "eave", "tie", "kp", "strut", "knee", "sd", "kl", "raf", "stub", "col"]
    segs.sort(key=lambda t: order.index(t[2]) if t[2] in order else 0)
    for a, b, g, sec in segs:
        pa, pb = T(a), T(b)
        if view == "plan":
            w = max(1.2, (sec.b if g != "lath" else sec.b) * s)
        else:
            w = max(1.5, sec.h * s)
        out.append(f'<line x1="{pa[0]:.1f}" y1="{pa[1]:.1f}" x2="{pb[0]:.1f}" y2="{pb[1]:.1f}" '
                   f'stroke="{COLORS.get(g, "#555")}" stroke-width="{w:.1f}" stroke-linecap="butt" opacity="0.92"/>')
    # размеры
    def dim(p1, p2, text, off):
        a_, b_ = T(p1), T(p2)
        out.append(f'<line x1="{a_[0]:.1f}" y1="{a_[1]+off:.1f}" x2="{b_[0]:.1f}" y2="{b_[1]+off:.1f}" class="dim"/>')
        out.append(f'<text x="{(a_[0]+b_[0])/2:.1f}" y="{(a_[1]+b_[1])/2+off-4:.1f}" class="dimt">{text}</text>')
    if view == "front":
        dim((0, -0.25), (M.SPAN, -0.25), "5.45", 0)
        dim((-M.OVH_L, 3.9), (0, 3.9), "0.40", 0)
        dim((M.SPAN, 3.9), (M.SPAN + M.OVH_R, 3.9), "0.90", 0)
        for z, t, x_, anc in ((M.Z_NODE, "+3.10 (узел)", M.SPAN + M.OVH_R + 0.05, "start"),
                              (M.z_rafter(M.X_RIDGE), "+3.68 (конёк)", M.SPAN + M.OVH_R + 0.05, "start"),
                              (M.Z_TIE, "+3.00 (ось затяжки)", -M.OVH_L - 0.05, "end")):
            p = T((x_, z))
            out.append(f'<text x="{p[0]:.1f}" y="{p[1]+4:.1f}" class="lev" text-anchor="{anc}">{t}</text>')
        if sc.knee_t:
            p = T((-0.05, sc.knee_z))
            out.append(f'<text x="{p[0]:.1f}" y="{p[1]+4:.1f}" class="lev" text-anchor="end">+{sc.knee_z:.2f}</text>')
    if view == "side":
        dim((0, -0.25), (M.BAY, -0.25), "4.60", 0)
        dim((M.Y_MIN, 3.9), (0, 3.9), "1.18", 0)
        dim((M.BAY, 3.9), (M.Y_MAX, 3.9), "1.20", 0)
    if view == "plan":
        dim((0, M.Y_MIN - 0.15), (M.SPAN, M.Y_MIN - 0.15), "5.45", 0)
        p = T((M.SPAN + 0.1, M.Y_MIN - 0.05))
        out.append(f'<text x="{p[0]:.1f}" y="{p[1]:.1f}" class="dimt" text-anchor="start">косина 2.87°</text>')
    out.append("</svg>")
    return "\n".join(out)


CSS = """
:root{--bg:#f7f7f5;--fg:#1f2328;--muted:#5b6470;--card:#ffffff;--line:#d9dde3;--accent:#0f766e;--dim:#64748b;--corr:#16a34a}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#15181c;--fg:#e6e8eb;--muted:#9aa4b0;--card:#1d2127;--line:#343a42;--accent:#2dd4bf;--dim:#94a3b8;--corr:#4ade80}}
:root[data-theme="dark"]{--bg:#15181c;--fg:#e6e8eb;--muted:#9aa4b0;--card:#1d2127;--line:#343a42;--accent:#2dd4bf;--dim:#94a3b8;--corr:#4ade80}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 8px}p.sub{color:var(--muted);margin:0 0 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin:12px 0;overflow-x:auto}
svg.drw{width:100%;height:auto;display:block}
.ground{stroke:var(--muted);stroke-width:1.5}.corr{fill:none;stroke:var(--corr);stroke-dasharray:6 4;stroke-width:1.2}
.corrl{stroke:var(--corr);stroke-dasharray:6 4;stroke-width:1}.corrt{fill:var(--corr);font-size:12px;text-anchor:middle}
.roof{fill:none;stroke:var(--dim);stroke-dasharray:3 3}.dim{stroke:var(--dim);stroke-width:1}
.dimt{fill:var(--dim);font-size:12px;text-anchor:middle}.lev{fill:var(--dim);font-size:12px}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.sw{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.ok{color:var(--accent);font-weight:600}.kpi{display:flex;gap:12px;flex-wrap:wrap}.kpi div{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;min-width:160px}
.kpi b{display:block;font-size:20px}.note{color:var(--muted);font-size:13px}
"""


def _n(v, sign=False):
    t = f"{v:+,.0f}" if sign else f"{v:,.0f}"
    return t.replace(",", "\u202f")


def build_html(an, sc, est, est_base, pieces, title, notes):
    m = an.model
    rows = []
    from report_data import member_table
    mt = member_table(an)
    legend = "".join(
        f'<tr><td><span class="sw" style="background:{COLORS.get(r["group"], "#555")}"></span>{html.escape(r["name"])}</td>'
        f'<td>□{html.escape(r["sec"])}</td><td class="n">{r["Nc"]:.1f}</td><td class="n">{r["Nt"]:.1f}</td>'
        f'<td class="n">{r["M"]:.2f}</td><td class="n">{r["u"]:.2f}</td><td class="note">{html.escape(r["gov"])}</td></tr>'
        for r in mt)
    prow = "".join(
        f'<tr><td>{html.escape(p["name"])}</td><td>□{html.escape(p["sec"])}</td><td class="n">{p["L"]:.3f}</td>'
        f'<td class="n">{p["n"]}</td><td class="n">{p["mass"]:.1f}</td></tr>' for p in pieces)
    comp = []
    base_lines = {n: v for n, v, k in est_base["lines"]}
    for n, v, k in est["lines"]:
        b = base_lines.get(n, 0.0)
        comp.append(f'<tr><td>{html.escape(n)}</td><td class="n">{_n(b)}</td><td class="n">{_n(v)}</td>'
                    f'<td class="n">{_n(v-b, sign=True)}</td></tr>')
    comp_html = "".join(comp)
    save = est_base["total"] - est["total"]
    kpi = (f'<div class="kpi"><div>Итог было<b>{_n(est_base["total"])} грн</b></div>'
           f'<div>Итог стало<b>{_n(est["total"])} грн</b></div>'
           f'<div>Экономия<b class="ok">{_n(save)} грн</b></div>'
           f'<div>Трубы, грн: было → стало<b>{_n(est_base["pipes"])} → {_n(est["pipes"])}</b></div></div>')
    notes_html = "".join(f"<li>{html.escape(n)}</li>" for n in notes)
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Навес: оптимизированный каркас</title>
<style>{CSS}</style></head><body><main>
<h1>Навес 5.45 × 4.60 м (кровля 6.75 × 6.98 м): оптимизированный каркас</h1>
<p class="sub">{html.escape(title)}</p>
{kpi}
<h2>Вид А — рама (фасад со стороны дороги)</h2><div class="card">{_svg_view(m, sc, "front")}</div>
<h2>Вид Б — продольная сторона (левый ряд колонн)</h2><div class="card">{_svg_view(m, sc, "side")}</div>
<h2>Вид В — план покрытия (площадка — параллелограмм, рамы параллельны передней кромке)</h2><div class="card">{_svg_view(m, sc, "plan", H=620)}</div>
<h2>Сечения и проверки</h2><div class="card"><table><thead><tr><th>Элемент</th><th>Сечение</th>
<th class="n">N сж, кН</th><th class="n">N раст, кН</th><th class="n">M, кН·м</th><th class="n">Исп.</th><th>Определяющая проверка</th></tr></thead>
<tbody>{legend}</tbody></table></div>
<h2>Ведомость деталей</h2><div class="card"><table><thead><tr><th>Деталь</th><th>Сечение</th><th class="n">Длина, м</th>
<th class="n">Кол-во</th><th class="n">Масса, кг</th></tr></thead><tbody>{prow}</tbody></table></div>
<h2>Смета: было → стало</h2><div class="card"><table><thead><tr><th>Статья</th><th class="n">Было, грн</th>
<th class="n">Стало, грн</th><th class="n">Δ, грн</th></tr></thead><tbody>{comp_html}</tbody></table></div>
<h2>Примечания</h2><ul>{notes_html}</ul>
</main></body></html>"""
