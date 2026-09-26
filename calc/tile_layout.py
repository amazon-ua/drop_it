"""Раскладка и подрезка металлочерепицы по скатам (развёртка).

Кровля — параллелограмм: карниз и конёк параллельны боковым сторонам площадки (ось y), передняя
и задняя кромки параллельны рамам и скошены на SKEW. Листы кладутся перпендикулярно карнизу
(по линии ската), полезная ширина листа 1.10 м (волна 350 мм), укладка — от переднего края (дорога) к заднему.
Координаты развёртки: u — вдоль карниза (как y на плане, м), v — вдоль ската от линии обреза
стропила у карниза (м).
"""
from __future__ import annotations

import html
import math

import model as M

W_USE = 1.10          # полезная ширина листа, м
W_FULL = 1.18         # полная (габаритная) ширина листа, м
EAVE_OVH = 0.045      # свес листа за торец стропила (под жёлоб), м
RIDGE_GAP = 0.030     # недобег листа до линии конька (закрывается коньком 200×200), м


def slope_geometry(side):
    """side: 'L' (свес 0.40) или 'R' (свес 0.90)."""
    t = math.tan(M.SKEW)
    Ls = M.slope_len_left() if side == "L" else M.slope_len_right()
    v0, v1 = -EAVE_OVH, Ls - RIDGE_GAP

    def x_at(v):   # горизонтальная координата (поперёк) точки ската
        return (-M.OVH_L + v * M.COS) if side == "L" else (M.SPAN + M.OVH_R - v * M.COS)

    def u_front(v):
        return M.Y_MIN + x_at(v) * t

    def u_back(v):
        return M.Y_MAX + x_at(v) * t

    def u_frame(fy, v):
        return fy + x_at(v) * t

    return dict(Ls=Ls, v0=v0, v1=v1, x_at=x_at, u_front=u_front, u_back=u_back, u_frame=u_frame,
                L_sheet=v1 - v0)


def layout(side):
    g = slope_geometry(side)
    v0, v1 = g["v0"], g["v1"]
    # укладка от переднего края (дорога): первый лист — целый, с косым подрезом; узкий последний лист
    # уходит к заднему краю, где он не виден с дороги
    uf = min(g["u_front"](v0), g["u_front"](v1))
    need = max(g["u_back"](v0), g["u_back"](v1)) - uf
    n = math.ceil(need / W_USE - 1e-9)
    sheets = []
    for k in range(n):
        lo = uf + k * W_USE
        hi = lo + W_USE
        # обрезки по краям кровли (ширина обрезаемой полосы у карниза и у конька)
        cut_back = (max(0.0, hi - g["u_back"](v0)), max(0.0, hi - g["u_back"](v1)))
        cut_front = (max(0.0, g["u_front"](v0) - lo), max(0.0, g["u_front"](v1) - lo))
        sheets.append(dict(k=k + 1, lo=lo, hi=hi, cut_back=cut_back, cut_front=cut_front,
                           width=(W_USE - cut_back[0] - cut_front[0], W_USE - cut_back[1] - cut_front[1])))
    return g, sheets


def rows_on_slope(side):
    """Положения обрешётин вдоль ската (v) для этого ската."""
    out = []
    for (x, z, trib, sd) in M.lath_rows():
        if sd == side or sd == "ridge":
            v = (x + M.OVH_L) / M.COS if side == "L" else (M.SPAN + M.OVH_R - x) / M.COS
            out.append(v)
    return sorted(out)


def svg_slope(side, title):
    g, sheets = layout(side)
    v0, v1 = g["v0"], g["v1"]
    umin = min(s["lo"] for s in sheets) - 0.35
    umax = max(s["hi"] for s in sheets) + 0.35
    S = 120.0                         # px на метр
    pad_l, pad_t, pad_b = 20, 40, 70
    W = (umax - umin) * S + 2 * pad_l
    Ls_draw = v1 - v0
    H = Ls_draw * S + pad_t + pad_b

    def P(u, v):
        return pad_l + (umax - u) * S, pad_t + (v1 - v) * S   # u растёт влево: задний край (рама 3) слева

    o = [f'<svg viewBox="0 0 {W:.0f} {H:.0f}" class="drw" role="img" aria-label="{html.escape(title)}">']
    # листы
    for s in sheets:
        a, b = P(s["hi"], v1), P(s["lo"], v0)
        fill = "#94a3b8" if s["k"] % 2 else "#cbd5e1"
        o.append(f'<rect x="{a[0]:.1f}" y="{a[1]:.1f}" width="{b[0]-a[0]:.1f}" height="{b[1]-a[1]:.1f}" '
                 f'fill="{fill}" fill-opacity="0.55" stroke="#475569" stroke-width="1"/>')
        c = P((s["lo"] + s["hi"]) / 2, (v0 + v1) / 2)
        o.append(f'<text x="{c[0]:.1f}" y="{c[1]+8:.1f}" class="tn" text-anchor="middle">{s["k"]}</text>')
    # обрезки (заштрихованы)
    for s in sheets:
        if max(s["cut_back"]) > 1e-4:
            pts = [(s["hi"], v0), (s["hi"], v1), (s["hi"] - s["cut_back"][1], v1), (s["hi"] - s["cut_back"][0], v0)]
            o.append('<polygon points="' + " ".join(f"{P(u, v)[0]:.1f},{P(u, v)[1]:.1f}" for u, v in pts)
                     + '" fill="url(#hatchR)" stroke="#dc2626" stroke-width="1.2"/>')
        if max(s["cut_front"]) > 1e-4:
            pts = [(s["lo"], v0), (s["lo"], v1), (s["lo"] + s["cut_front"][1], v1), (s["lo"] + s["cut_front"][0], v0)]
            o.append('<polygon points="' + " ".join(f"{P(u, v)[0]:.1f},{P(u, v)[1]:.1f}" for u, v in pts)
                     + '" fill="url(#hatchR)" stroke="#dc2626" stroke-width="1.2"/>')
    # обрешётка
    for v in rows_on_slope(side):
        if v0 <= v <= v1 + 0.05:
            a, b = P(g["u_back"](v), min(v, v1)), P(g["u_front"](v), min(v, v1))
            o.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="#db2777" '
                     f'stroke-width="1" stroke-opacity="0.6"/>')
    # стропила (рамы) — косые линии
    for fy, nm in ((0.0, "рама 1"), (M.BAY / 2, "рама 2"), (M.BAY, "рама 3")):
        a, b = P(g["u_frame"](fy, v0), v0), P(g["u_frame"](fy, v1), v1)
        o.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="#0f766e" '
                 f'stroke-width="2" stroke-dasharray="8 4"/>')
        o.append(f'<text x="{b[0]:.1f}" y="{b[1]-6:.1f}" class="lev" text-anchor="middle">{nm}</text>')
    # контур кровли
    pts = [(g["u_back"](v0), v0), (g["u_back"](v1), v1), (g["u_front"](v1), v1), (g["u_front"](v0), v0)]
    o.append('<polygon points="' + " ".join(f"{P(u, v)[0]:.1f},{P(u, v)[1]:.1f}" for u, v in pts)
             + '" fill="none" stroke="var(--fg)" stroke-width="2.2"/>')
    # подписи краёв
    a = P(g["u_back"](v1), v1)
    o.append(f'<text x="{a[0]:.1f}" y="{pad_t-22:.1f}" class="lev">задний край (вглубь)</text>')
    b = P(g["u_front"](v1), v1)
    o.append(f'<text x="{b[0]:.1f}" y="{pad_t-22:.1f}" class="lev" text-anchor="end">передний край (дорога)</text>')
    c = P(umax - 0.05, v1)
    o.append(f'<text x="{pad_l + 4:.1f}" y="{pad_t - 6:.1f}" class="lev">КОНЁК</text>')
    o.append(f'<text x="{pad_l + 4:.1f}" y="{H - pad_b + 18:.1f}" class="lev">КАРНИЗ (жёлоб)</text>')
    # стрелка направления укладки
    y_ar = H - 22
    x1, x2 = P(min(s["lo"] for s in sheets), v0)[0], P(max(s["hi"] for s in sheets), v0)[0]
    o.append(f'<line x1="{x1:.1f}" y1="{y_ar:.1f}" x2="{x2:.1f}" y2="{y_ar:.1f}" stroke="var(--dim)" '
             f'stroke-width="1.2" marker-end="url(#arr)"/>')
    o.append(f'<text x="{(x1+x2)/2:.1f}" y="{y_ar-6:.1f}" class="lev" text-anchor="middle">порядок укладки листов '
             f'1 → {len(sheets)}, полезная ширина {W_USE:.2f} м, нахлёст — одна волна</text>')
    # длина листа
    a, b = P(umin + 0.2, v1), P(umin + 0.2, v0)
    o.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" class="dim"/>')
    o.append(f'<text x="{a[0]-6:.1f}" y="{(a[1]+b[1])/2:.1f}" class="dimt" text-anchor="end" '
             f'transform="rotate(-90 {a[0]-6:.1f} {(a[1]+b[1])/2:.1f})">лист {g["L_sheet"]:.2f} м</text>')
    o.append("</svg>")
    return "".join(o), g, sheets


def sheet_table(side, g, sheets):
    rows = []
    for s in sheets:
        cb, cf = s["cut_back"], s["cut_front"]
        if max(cb) > 1e-4 and max(cf) > 1e-4:
            cut = f"с двух сторон: задняя кромка {cb[0]*1000:.0f}→{cb[1]*1000:.0f}, передняя {cf[0]*1000:.0f}→{cf[1]*1000:.0f} мм"
        elif max(cb) > 1e-4:
            cut = f"по задней кромке: у карниза {cb[0]*1000:.0f} мм → у конька {cb[1]*1000:.0f} мм"
        elif max(cf) > 1e-4:
            cut = f"по передней кромке: у карниза {cf[0]*1000:.0f} мм → у конька {cf[1]*1000:.0f} мм"
        else:
            cut = "целый"
        rows.append(f"<tr><td class='n'>{s['k']}</td><td class='n'>{s['width'][0]*1000:.0f}</td>"
                    f"<td class='n'>{s['width'][1]*1000:.0f}</td><td>{html.escape(cut)}</td></tr>")
    return ("<table><thead><tr><th class='n'>Лист</th><th class='n'>Полезн. ширина у карниза, мм</th>"
            "<th class='n'>у конька, мм</th><th>Подрезка (ширина срезаемой полосы)</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>")


def build_section():
    """HTML-раздел для общего чертежа + сводка для отчёта."""
    parts = []
    summary = []
    for side, title in (("L", "Левый скат (свес 0.40 м)"), ("R", "Правый скат (свес 0.90 м)")):
        svg, g, sheets = svg_slope(side, title)
        n_cut = sum(1 for s in sheets if max(s["cut_back"]) > 1e-4 or max(s["cut_front"]) > 1e-4)
        delta = abs(g["u_front"](g["v1"]) - g["u_front"](g["v0"]))
        parts.append(f"<h3>{html.escape(title)}: {len(sheets)} листов по {g['L_sheet']:.2f} м, "
                     f"косой сдвиг кромки по длине ската {delta*1000:.0f} мм</h3>"
                     f"<div class='card'>{svg}{sheet_table(side, g, sheets)}</div>")
        summary.append(dict(side=side, title=title, n=len(sheets), L=g["L_sheet"], delta=delta, n_cut=n_cut,
                            sheets=sheets))
    n_tot = sum(s["n"] for s in summary)
    area_full = sum(s["n"] * W_FULL * s["L"] for s in summary)
    area_use = sum(s["n"] * W_USE * s["L"] for s in summary)
    roof = (M.Y_MAX - M.Y_MIN) * (M.slope_len_left() + M.slope_len_right())
    defs = ('<svg width="0" height="0" style="position:absolute"><defs>'
            '<pattern id="hatchR" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            '<rect width="7" height="7" fill="#fecaca" fill-opacity="0.7"/><line x1="0" y1="0" x2="0" y2="7" '
            'stroke="#dc2626" stroke-width="1.4"/></pattern>'
            '<marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            '<path d="M0,0 L10,5 L0,10 z" fill="#64748b"/></marker></defs></svg>')
    head = (f"<p class='note'>Развёртка скатов, вид сверху на скат (конёк вверху, карниз внизу). Листы кладутся "
            f"перпендикулярно карнизу, от переднего края (дорога) к заднему; полезная ширина {W_USE:.2f} м "
            f"(габаритная {W_FULL:.2f} м), нахлёст — одна волна. Из-за косины площадки 2.87° передний и задний края "
            f"кровли идут наискось к листам — крайние листы подрезаются по косой линии (красная штриховка), срез "
            f"закрывается торцевой планкой. Семь листов шире ската (7 × 1.10 = 7.70 м против ~7.15 м с учётом "
            f"косины), поэтому последний лист узкий — он поставлен у заднего края, где его не видно с дороги. Длина листа — от свеса {EAVE_OVH*1000:.0f} мм за торец стропила (над жёлобом) "
            f"до {RIDGE_GAP*1000:.0f} мм не доходя линии конька (закрывается коньком 200×200). Пунктир — стропила "
            f"(идут наискось, параллельно переднему краю), розовые линии — обрешётка. Резать ножницами по металлу "
            f"или высечными ножницами, не болгаркой (горит покрытие).</p>")
    summ = (f"<div class='card'><b>Итого: {n_tot} листов</b> — "
            + "; ".join(f"{s['title'].split(' (')[0].lower()}: {s['n']} × {s['L']:.2f} м" for s in summary)
            + f". Площадь листов по габаритной ширине {area_full:.1f} м² (по полезной {area_use:.1f} м²), "
              f"площадь кровли {roof:.1f} м². Длину листа уточнить у производителя под шаг поперечной волны "
              f"350 мм (заказ «кратно шагу + хвост»).</div>")
    return defs + head + "".join(parts) + summ, dict(n=n_tot, area_full=area_full, area_use=area_use, roof=roof,
                                                     slopes=summary)


if __name__ == "__main__":
    _, s = build_section()
    for sl in s["slopes"]:
        print(sl["title"], sl["n"], round(sl["L"], 3), "сдвиг", round(sl["delta"] * 1000), "мм")
        for sh in sl["sheets"]:
            print("   ", sh["k"], [round(c * 1000) for c in sh["cut_back"]], [round(c * 1000) for c in sh["cut_front"]])
    print({k: (round(v, 1) if isinstance(v, float) else v) for k, v in s.items() if k != "slopes"})
