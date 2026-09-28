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
        xmin, xmax, ymin, ymax = -1.9, M.SPAN + 2.0, -0.62, 4.0
    elif view == "side":
        xmin, xmax, ymin, ymax = M.Y_MIN - 1.6, M.Y_MAX + 1.7, -0.62, 4.3
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
    if view == "side":
        # кровля и стропила (схематично, пунктир): проекция на плоскость левого ряда колонн
        import math as _m
        raf = sc.groups["raf"]
        lath = sc.groups["lath"]
        dz_top = raf.h / 2 / _m.cos(M.SLOPE)            # от оси стропила до его верха по вертикали
        dz_roof = dz_top + lath.h + 0.04                 # + обрешётка + профиль металлочерепицы ~40 мм
        xe, xr, xe2 = -M.OVH_L, M.X_RIDGE, M.SPAN + M.OVH_R

        def PP(x, y, z):
            p = model.phys((x, y, z))
            return T((p[1], p[2]))
        for fy in model.frames_y:
            a, b = PP(xe, fy, M.z_rafter(xe)), PP(xr, fy, M.z_rafter(xr))
            out.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" '
                       f'stroke="{COLORS["raf"]}" stroke-width="{max(1.5, raf.b * s):.1f}" stroke-opacity="0.45" '
                       f'stroke-dasharray="10 6"/>')
        # контур левого ската по верху кровли
        pts = [PP(xe, M.Y_MIN, M.z_rafter(xe) + dz_roof), PP(xe, M.Y_MAX, M.z_rafter(xe) + dz_roof),
               PP(xr, M.Y_MAX, M.z_rafter(xr) + dz_roof), PP(xr, M.Y_MIN, M.z_rafter(xr) + dz_roof)]
        out.append('<polygon points="' + " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts)
                   + '" fill="#94a3b8" fill-opacity="0.12" stroke="var(--fg)" stroke-width="1.4" stroke-dasharray="7 4"/>')
        # карниз правого ската (ниже — свес 0.90)
        a, b = PP(xe2, M.Y_MIN, M.z_rafter(xe2) + dz_roof), PP(xe2, M.Y_MAX, M.z_rafter(xe2) + dz_roof)
        out.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="var(--dim)" '
                   f'stroke-width="1.2" stroke-dasharray="3 4"/>')
        lab = PP(xr, M.Y_MAX, M.z_rafter(xr) + dz_roof)
        out.append(f'<text x="{lab[0]+8:.1f}" y="{lab[1]+4:.1f}" class="lev">конёк</text>')
        lab = PP(xe, M.Y_MAX, M.z_rafter(xe) + dz_roof)
        out.append(f'<text x="{lab[0]+8:.1f}" y="{lab[1]+4:.1f}" class="lev">карниз левого ската</text>')
        lab = PP(xe2, M.Y_MIN, M.z_rafter(xe2) + dz_roof)
        out.append(f'<text x="{lab[0]-8:.1f}" y="{lab[1]+14:.1f}" class="lev" text-anchor="end">карниз правого ската</text>')
        for fy, nm in zip(model.frames_y, ("рама 1", "рама 2", "рама 3")):
            lab = PP(xr, fy, M.z_rafter(xr) + dz_roof)
            out.append(f'<text x="{lab[0]:.1f}" y="{lab[1]-8:.1f}" class="lev" text-anchor="middle">{nm}</text>')
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
        dim((0, -0.52), (M.SPAN, -0.52), "5.45", 0)
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
    if view in ("front", "side"):
        # отметки верха бетона у колонн этого вида
        for (xc, yc), (nm, zb, dep, zg) in M.COLUMN_BASES.items():
            if view == "front" and abs(yc) > 1e-6:
                continue
            if view == "side" and abs(xc) > 1e-6:
                continue
            u = xc if view == "front" else yc
            p = T((u, zb))
            out.append(f'<text x="{p[0]+8:.1f}" y="{p[1]+14:.1f}" class="lev">{nm}: верх бетона {zb:+.2f}</text>')
    if view == "side":
        dim((0, -0.52), (M.BAY, -0.52), "4.60", 0)
        dim((M.Y_MIN, 4.2), (0, 4.2), "1.18", 0)
        dim((M.BAY, 4.2), (M.Y_MAX, 4.2), "1.20", 0)
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


def _bars_txt(n12, n6):
    return " + ".join(t for t in (f"{n12}×12 м" if n12 else "", f"{n6}×6 м" if n6 else "") if t)


def _bar_svg(cuts, free, stock, colors, scale_len=12.0):
    """Полоса хлыста: заготовки + остаток (масштаб — по самому длинному хлысту в раскрое)."""
    W, H = 720, 34
    sx = W / scale_len
    out = [f'<svg viewBox="0 0 {W + 2} {H + 2}" class="bar" role="img" aria-label="раскроенный хлыст">',
           f'<rect x="1" y="1" width="{stock * sx:.1f}" height="{H}" fill="none" stroke="#0007"/>']
    x = 1
    for L, nm, g in cuts:
        w = L * sx
        out.append(f'<rect x="{x:.1f}" y="1" width="{w:.1f}" height="{H}" fill="{colors.get(g, "#888")}" '
                   f'fill-opacity="0.85" stroke="#0007" stroke-width="0.8"/>')
        if w > 30:
            out.append(f'<text x="{x + w / 2:.1f}" y="{H / 2 + 6:.1f}" class="bt" text-anchor="middle">{L:.2f}</text>')
        x += w + 0.003 * sx
    if free > 1e-3:
        w = free * sx
        out.append(f'<rect x="{x:.1f}" y="1" width="{max(w - 1, 0):.1f}" height="{H}" fill="url(#hatch)" '
                   f'stroke="#0005" stroke-width="0.8"/>')
        if w > 40:
            out.append(f'<text x="{x + w / 2:.1f}" y="{H / 2 + 6:.1f}" class="bt2" text-anchor="middle">ост. {free:.2f}</text>')
    out.append("</svg>")
    return "".join(out)


HATCH = ('<svg width="0" height="0" style="position:absolute"><defs><pattern id="hatch" width="6" height="6" '
         'patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="var(--card)"/>'
         '<line x1="0" y1="0" x2="0" y2="6" stroke="var(--dim)" stroke-width="1.2"/></pattern></defs></svg>')


def build_html(an, sc, title, notes, details, plan, plates, q, details_split=None, tiles_html=""):
    from report_data import member_table
    import model as _M
    m = an.model
    mt = member_table(an)
    legend = "".join(
        f'<tr><td><span class="sw" style="background:{COLORS.get(r["group"], "#555")}"></span>{html.escape(r["name"])}</td>'
        f'<td>□{html.escape(r["sec"])}</td><td class="n">{r["Nc"]:.1f}</td><td class="n">{r["Nt"]:.1f}</td>'
        f'<td class="n">{r["M"]:.2f}</td><td class="n">{r["u"]:.2f}</td><td class="note">{html.escape(r["gov"])}</td></tr>'
        for r in mt)
    drow = "".join(
        f'<tr><td><span class="sw" style="background:{COLORS.get(d["group"], "#555")}"></span>{html.escape(d["name"])}</td>'
        f'<td>□{html.escape(d["sec"].name)}</td><td class="n">{d["L"]:.3f}</td><td class="n">{d["n"]}</td>'
        f'<td class="n">{d["mass"]:.1f}</td><td class="note">{html.escape(d["cuts"])}</td></tr>' for d in details)
    grp_of = {d["name"]: d["group"] for d in list(details) + list(details_split or [])}
    need_by_sec = {}
    for d in details:
        need_by_sec[d["sec"].name] = need_by_sec.get(d["sec"].name, 0.0) + d["L"] * d["n"]
    blocks = []
    srow = []
    tot_need = tot_buy = 0.0
    n6 = n12 = 0
    scale_len = max(b["stock"] for p in plan.values() for b in p["bars"])
    for sn, p in sorted(plan.items(), key=lambda kv: -kv[1]["need"] * kv[1]["sec"].price):
        bars = p["bars"]
        need_m = need_by_sec.get(sn, p["need"])
        short = p["need"] < 1.0
        pat = {}
        for b in bars:
            key = (b["stock"],) + tuple((round(L, 3), nm) for L, nm in b["cuts"])
            pat.setdefault(key, [0, b["free"]])
            pat[key][0] += 1
        rows_html = []
        c6 = sum(1 for b in bars if b["stock"] < 7)
        c12 = len(bars) - c6
        for key, (cnt, free) in sorted(pat.items(), key=lambda kv: -kv[0][0]):
            stock = key[0]
            cuts = [(L, nm, grp_of.get(nm, "")) for L, nm in key[1:]]
            names = {}
            for L, nm, g in cuts:
                names[(nm, L)] = names.get((nm, L), 0) + 1
            desc = "; ".join(f"{nm} {L:.3f}" + (f" × {k}" if k > 1 else "") for (nm, L), k in names.items())
            if short:
                rows_html.append(f'<div class="bl"><div class="bh">покупать отрезком ≈ {p["need"] + 0.02:.2f} м '
                                 f'(хлыст не нужен)</div><div class="bd">{html.escape(desc)}</div></div>')
            else:
                word = "хлыст" if cnt == 1 else "хлыста" if cnt < 5 else "хлыстов"
                rows_html.append(f'<div class="bl"><div class="bh"><b>× {cnt}</b> {word} {stock:.0f} м</div>'
                                 f'{_bar_svg(cuts, free, stock, COLORS, scale_len)}<div class="bd">{html.escape(desc)}</div></div>')
        buy = p["need"] + 0.02 if short else p["buy"]
        if not short:
            n6 += c6
            n12 += c12
        tot_need += need_m
        tot_buy += buy
        bars_txt = "отрезок" if short else " + ".join(t for t in (f"{c12}×12 м" if c12 else "", f"{c6}×6 м" if c6 else "") if t)
        srow.append(f'<tr><td>□{html.escape(sn)}</td><td class="n">{need_m:.2f}</td>'
                    f'<td class="n">{need_m * p["sec"].price:,.0f}</td>'.replace(",", "\u202f")
                    + f'<td>{bars_txt}</td><td class="n">{buy:.2f}</td>'
                    f'<td class="n">{buy * p["sec"].price:,.0f}</td></tr>'.replace(",", "\u202f"))
        blocks.append(f'<h3>□{html.escape(sn)} — {bars_txt}</h3>' + "".join(rows_html))
    cost_m = sum(d["L"] * d["n"] * d["sec"].price for d in details)
    cost_b = sum((p["need"] + 0.02 if p["need"] < 1 else p["buy"]) * p["sec"].price for p in plan.values())
    srow.append(f'<tr><td><b>Итого</b></td><td class="n"><b>{tot_need:.2f}</b></td><td class="n"><b>{_n(cost_m)}</b></td>'
                f'<td><b>{_bars_txt(n12, n6)}</b></td><td class="n"><b>{tot_buy:.2f}</b></td>'
                f'<td class="n"><b>{_n(cost_b)}</b></td></tr>')
    prow = "".join(
        f'<tr><td>{html.escape(nm)}</td><td>{html.escape(size)}</td><td class="n">{t if t else "—"}</td>'
        f'<td class="n">{n}</td><td class="n">{mass * n:.1f}</td><td class="note">{html.escape(where)}</td>'
        f'<td class="note">{html.escape(src)}</td></tr>'
        for nm, size, t, n, mass, where, src in plates)
    plate_kg = sum(mass * n for _, _, _, n, mass, _, _ in plates)
    tube_kg = sum(d["mass"] for d in details)
    kpi = (f'<div class="kpi"><div>Металл труб<b>{tube_kg:.0f} кг</b></div>'
           f'<div>Пластины<b>{plate_kg:.0f} кг</b></div>'
           f'<div>Трубы по метражу<b>{tot_need:.0f} м</b></div>'
           f'<div>Или целыми хлыстами<b>{_bars_txt(n12, n6)}</b></div></div>')
    notes_html = "".join(f"<li>{html.escape(n)}</li>" for n in notes)
    extra_css = """
svg.bar{width:100%;max-width:760px;height:auto;display:block;margin:4px 0}
.bt{fill:#fff;font-size:13px;font-weight:600;font-family:system-ui,sans-serif}
.bt2{fill:var(--dim);font-size:12px;font-family:system-ui,sans-serif}
.bl{margin:8px 0 12px}.bh{font-size:14px}.bd{color:var(--muted);font-size:13px}
h3{font-size:15px;margin:18px 0 4px}
.tn{fill:#1e293b;font-size:26px;font-weight:700;font-family:system-ui,sans-serif}
@media print{
  body{background:#fff}
  main{max-width:none;padding:0}
  .card{break-inside:avoid;page-break-inside:avoid}
  .card.long{break-inside:auto;page-break-inside:auto}
  .bl,tr,svg{break-inside:avoid;page-break-inside:avoid}
  h2,h3{break-after:avoid;page-break-after:avoid}
}
"""
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Навес: каркас и раскрой</title>
<style>{CSS}{extra_css}</style></head><body>{HATCH}<main>
<h1>Навес 5.45 × 4.60 м (кровля 6.75 × 6.98 м): каркас, заготовки, раскрой</h1>
<p class="sub">{html.escape(title)}</p>
{kpi}
<h2>Вид А — рама (фасад со стороны дороги)</h2><div class="card">{_svg_view(m, sc, "front")}</div>
<h2>Вид Б — продольная сторона (левый ряд колонн); кровля и стропила — пунктиром</h2><div class="card">{_svg_view(m, sc, "side")}</div>
<h2>Вид В — план покрытия (площадка — параллелограмм, рамы параллельны передней кромке)</h2><div class="card">{_svg_view(m, sc, "plan", H=620)}</div>
<h2>Сечения и проверки</h2><div class="card"><table><thead><tr><th>Элемент</th><th>Сечение</th>
<th class="n">N сж, кН</th><th class="n">N раст, кН</th><th class="n">M, кН·м</th><th class="n">Исп.</th><th>Определяющая проверка</th></tr></thead>
<tbody>{legend}</tbody></table></div>
<h2>Заготовки (длины реза)</h2>
<p class="note">Длины — в чистоте, по узлам (см. чертежи узлов): затяжки между гранями колонн/стоек, раскосы боковой фермы —
от верха пояса у грани колонны до столика, подвески и подкосы — между затяжкой и стропилом. Длины колонн — с заделкой в бетон; стропил — по оси.
Подкосы и подвески лучше окончательно подогнать по месту на стенде.</p>
<div class="card long"><table><thead><tr><th>Заготовка</th><th>Сечение</th><th class="n">Длина, м</th><th class="n">Кол-во</th>
<th class="n">Масса, кг</th><th>Торцы</th></tr></thead><tbody>{drow}</tbody></table></div>
<h2>Закупка и раскрой труб (длины хлыстов — по прайсу)</h2>
<p class="note"><b>Рекомендуется покупать по метражу с резкой в магазине</b>: платите только за длину деталей.
Длины хлыстов — по прайсу СтройРяда (колонка L): 100×60 — только 12 м, 60×60×3 — 6 и 12 м, остальные
наши трубы — 6 м. Труба 35×35 идёт хлыстами 6 м, поэтому обрешётина 6.98 м — из двух частей 5.49 + 1.49 м со стыком на
вкладыше в пролёте, в 0.29 м от стропила рамы 3 (стыки всех обрешётин — на одной линии, см. чертежи узлов).
Если магазин продаёт только целыми хлыстами — ниже раскрой с наименьшей закупкой. Пропил 3 мм. Суммы — по прайсу,
для сравнения способов.</p>
<div class="card"><table><thead><tr><th>Профиль</th><th class="n">По метражу, м</th><th class="n">По метражу, грн</th>
<th>Целыми хлыстами</th><th class="n">Хлыстов, м</th><th class="n">Хлыстами, грн</th></tr></thead>
<tbody>{"".join(srow)}</tbody></table></div>
<h3>Раскрой при покупке целыми хлыстами</h3>
<div class="card long">{"".join(blocks)}</div>
<h2>Пластины, заглушки</h2><div class="card"><table><thead><tr><th>Позиция</th><th>Размер, мм</th><th class="n">t, мм</th>
<th class="n">Кол-во</th><th class="n">Масса, кг</th><th>Где</th><th>Из чего резать</th></tr></thead><tbody>{prow}</tbody></table>
<p class="note">Размеры и сварка фасонок и пластин — на чертежах узлов (uzly.html). Хомуты Ø8 в лунках (по 3 шт.) — по черновику.</p></div>
<h2>Раскладка и подрезка металлочерепицы</h2>{tiles_html}
<h2>Примечания</h2><ul>{notes_html}</ul>
</main></body></html>"""
