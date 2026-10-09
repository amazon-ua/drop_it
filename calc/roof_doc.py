"""Отдельный документ по кровле: раскладка металлочерепицы и коньковая планка → output/krovlya.html (+ PDF).

Конёк — плоский 200×200, гиб под уклон 2 × 12° (156°); под ним — коньковая обрешётина 60×60 на вершине стропил
(на прутках Ø6, шов 14 — см. uzly.pdf), листы не доходят до оси конька RIDGE_GAP (50 мм).
"""
from __future__ import annotations

import html
import math

import model as M
import tile_layout as T
from nodes_drawing import COL, NODE_CSS, OUT, Svg

WING = 200.0          # крыло конька, мм (по скату)
HEM = 12.0            # подгиб кромки крыла, мм
PROFILE_H = 30.0      # высота профиля металлочерепицы (для чертежа; по каталогу 25–40 мм)
CAP_PIECE = 2.0       # длина элемента конька, м
CAP_LAP = 0.10        # нахлёст элементов, м
WAVE = 0.185          # шаг продольной волны листа, м (≈ 1.10 / 6)


def rows_near_ridge():
    xs = [r[0] for r in M.lath_rows()]
    left = max(x for x in xs if x < M.X_RIDGE - 1e-6)
    right = min(x for x in xs if x > M.X_RIDGE + 1e-6)
    return (M.X_RIDGE - left) * 1000, (right - M.X_RIDGE) * 1000


def ridge_svg():
    """Разрез по оси рамы через конёк (мм; начало — вершина верха стропил). Подписи — номерами (легенда в тексте)."""
    t, c, sn = M.TAN, M.COS, M.SIN
    k = 0.9
    X = 320.0
    s = Svg(-345, 345, -150, 140, k=k)
    Hr = 100 / c
    for sg in (-1, 1):
        s.poly([(0, 0), (sg * X, -X * t), (sg * X, -X * t - Hr), (0, -Hr)], COL["raf"], "#0008", 0.85)
        zz = [(sg * X, -X * t + 10), (sg * (X - 8), -X * t - Hr / 2 + 5), (sg * (X + 8), -X * t - Hr / 2 - 5),
              (sg * X, -X * t - Hr - 10)]
        s.items.append('<polyline points="' + " ".join(f"{s.P(*q)[0]:.1f},{s.P(*q)[1]:.1f}" for q in zz)
                       + '" fill="none" stroke="var(--fg)" stroke-width="1"/>')
    s.line(0, 0, 0, -Hr, "ld")

    def on_slope(x0, b, h, sg):
        d = (sg * c, -sn)
        n = (sn * sg, c)
        z0 = -abs(x0) * t
        return [(x0 + a * d[0] + e * n[0], z0 + a * d[1] + e * n[1]) for a, e in ((-b / 2, 0), (b / 2, 0), (b / 2, h), (-b / 2, h))]
    xl, xr = rows_near_ridge()
    a = 35.0
    for x0, sg in ((-xl, -1), (xr, 1)):
        s.poly(on_slope(x0, a, a, sg), COL["lath"], "#0008", 0.9)
    # коньковая обрешётина 60×60 и прутки Ø6
    s.rect(-30, 0, 30, 60, "#9d174d", "#0008", 0.9)
    s.rect(-28, 2, 28, 58, "var(--card)", "none")
    xr_rod = 3 * (1 + math.sqrt(1 + t * t)) / t
    for sg in (-1, 1):
        p = s.P(sg * xr_rod, -3)
        s.items.append(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="3" fill="#374151"/>')
    # листы: основание по верху обрешётин, гребни волн — пунктир; торец в RIDGE_GAP от оси
    hl = a / c
    gap = T.RIDGE_GAP * 1000 * c
    for sg in (-1, 1):
        xe, xo = sg * gap, sg * X
        base = [(xe, hl - gap * t), (xo, hl - X * t)]
        crest = [(xe, hl + PROFILE_H - gap * t), (xo, hl + PROFILE_H - X * t)]
        s.poly([base[0], base[1], crest[1], crest[0]], "#94a3b8", "#334155", 0.35, 0.8)
        s.items.append(f'<line x1="{s.P(*crest[0])[0]:.1f}" y1="{s.P(*crest[0])[1]:.1f}" '
                       f'x2="{s.P(*crest[1])[0]:.1f}" y2="{s.P(*crest[1])[1]:.1f}" stroke="#334155" '
                       f'stroke-width="2" stroke-dasharray="10 5"/>')
    # конёк 200×200 с подгибом
    z_ap = hl + PROFILE_H
    wx = WING * c
    cap = [(-wx - HEM * sn, z_ap - wx * t - HEM * c), (-wx, z_ap - wx * t), (0, z_ap + 2.5),
           (wx, z_ap - wx * t), (wx + HEM * sn, z_ap - wx * t - HEM * c)]
    s.items.append('<polyline points="' + " ".join(f"{s.P(*q)[0]:.1f},{s.P(*q)[1]:.1f}" for q in cap)
                   + '" fill="none" stroke="#1e3a8a" stroke-width="4" stroke-linejoin="round"/>')
    # уплотнитель
    for sg in (-1, 1):
        x1, x2 = sg * (gap + 8), sg * (gap + 40)
        z1, z2 = z_ap - abs(x1) * t, z_ap - abs(x2) * t
        s.poly([(x1, z1), (x2, z2), (x2, z2 - 14), (x1, z1 - 14)], "#111827", "none", 0.8)
    # саморезы
    xs_l, xs_r = -xl, 140.0
    for x0, L in ((xs_l, PROFILE_H + 6 + a * 0.8), (xs_r, PROFILE_H + 8)):
        zt = z_ap - abs(x0) * t + 4
        p1, p2 = s.P(x0, zt + 6), s.P(x0, zt - L)
        s.items.append(f'<line x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" '
                       f'stroke="#b91c1c" stroke-width="3"/>')
        s.items.append(f'<rect x="{p1[0] - 7:.1f}" y="{p1[1] - 4:.1f}" width="14" height="5" fill="#b91c1c"/>')
    # размеры
    s.line(0, -Hr - 15, 0, z_ap + 45)
    s.dim_h(0, gap, -40, f"{T.RIDGE_GAP * 1000:.0f}", off=0)
    s.text(8, z_ap + 34, "156°", "dt")
    # номера-выноски
    marks = [((-wx * 0.6, z_ap - wx * 0.6 * t + 2), (-200, 115), 1),
             ((gap + 24, z_ap - (gap + 24) * t - 7), (130, 118), 2),
             ((xs_l, z_ap - xl * t + 10), (-235, 95), 3),
             ((xs_r, z_ap - xs_r * t + 10), (225, 100), 4),
             ((250, hl - 250 * t + PROFILE_H / 2), (295, 60), 5),
             ((22, 30), (95, -55), 6),
             ((xr, hl / 2 - xr * t), (275, -20), 7),
             ((-xl, hl / 2 - xl * t), (-165, -60), 7),
             ((-200, -200 * t - Hr / 2), (-245, -125), 8)]
    for (px, pz), (lx, lz), n in marks:
        a_, b_ = s.P(px, pz), s.P(lx, lz)
        s.items.append(f'<line x1="{a_[0]:.1f}" y1="{a_[1]:.1f}" x2="{b_[0]:.1f}" y2="{b_[1]:.1f}" class="ld"/>')
        s.items.append(f'<circle cx="{a_[0]:.1f}" cy="{a_[1]:.1f}" r="2.5" fill="var(--muted)"/>')
        s.items.append(f'<circle cx="{b_[0]:.1f}" cy="{b_[1]:.1f}" r="11" fill="#1e3a8a"/>'
                       f'<text x="{b_[0]:.1f}" y="{b_[1] + 5:.1f}" text-anchor="middle" '
                       f'style="fill:#fff;font-size:14px;font-weight:700">{n}</text>')
    return s.svg("конёк — разрез")


RIDGE_LEGEND = [
    "конёк плоский {w}×{w}, гиб 156° (2 × 12°), кромки подогнуты",
    "уплотнитель профильный под волну черепицы — у торцов листов",
    "саморез 4.8×35 с EPDM через гребень волны в обрешётину (левый скат, обрешётина в {xl} мм от оси)",
    "саморез 4.8×19 с EPDM «металл-металл» в гребень листа (правый скат)",
    "лист металлочерепицы: основание — по верху обрешётин, пунктир — гребни волн; торец в {gap} мм от оси",
    "коньковая обрешётина 60×60 на вершине стропил, на прутках Ø6 (шов 14, см. uzly.pdf)",
    "рядовая обрешётина 35×35: слева в {xl} мм от оси, справа в {xr} мм",
    "стропило 100×60×3",
]


def build():
    tiles_html, tiles = T.build_section()
    xl, xr = rows_near_ridge()
    roof_len = M.Y_MAX - M.Y_MIN
    n_cap = math.ceil((roof_len + 0.06 - CAP_LAP) / (CAP_PIECE - CAP_LAP) - 1e-9)
    n_screw = math.ceil(roof_len / (2 * WAVE)) + 1 + 2 * (n_cap - 1)
    css = NODE_CSS + """
table td.n,table th.n{text-align:right;font-variant-numeric:tabular-nums}
.drw{width:100%;height:auto;display:block}
.dim{stroke:var(--dim);stroke-width:1}.dimt{fill:var(--dim);font-size:12px;text-anchor:middle}.lev{fill:var(--dim);font-size:12px}
.ax{stroke:var(--dim);stroke-width:0.6;stroke-dasharray:10 3 2 3;fill:none}
p.note{font-size:14px}
ol.leg2{columns:2;column-gap:28px;font-size:14px;margin:8px 0 4px;padding-left:22px}
ol.leg2 li{break-inside:avoid}
"""
    spec = [
        (f"Конёк плоский {WING:.0f}×{WING:.0f}, гиб 156° (под уклон 2 × 12°), с подгибом кромок, элемент {CAP_PIECE:.0f} м",
         f"{n_cap} шт.", f"длина конька {roof_len:.2f} м + выпуски по 30 мм за торцевые планки; нахлёст элементов "
                         f"{CAP_LAP * 1000:.0f} мм; цвет — как черепица"),
        ("Уплотнитель профильный (верхний, под волну выбранной черепицы)", f"{2 * roof_len:.1f} м",
         "по обе стороны конька, у торцов листов"),
        ("Саморез кровельный 4.8×35 с шайбой EPDM, сверло по металлу", f"≈ {n_screw} шт.",
         f"левый скат: через гребень каждой второй волны (≈ {2 * WAVE * 1000:.0f} мм) в обрешётину, "
         f"она в {xl:.0f} мм от оси"),
        ("Саморез кровельный 4.8×19 с шайбой EPDM («металл-металл»)", f"≈ {n_screw} шт.",
         f"правый скат: в гребень каждой второй волны, только в лист (ближайшая обрешётина — в {xr:.0f} мм "
         f"от оси, крыло до неё не достаёт); + по 2 на каждый нахлёст"),
    ]
    srow = "".join(f"<tr><td>{html.escape(a)}</td><td class='n'>{html.escape(b)}</td><td>{html.escape(c)}</td></tr>"
                   for a, b, c in spec)
    page = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Кровля навеса</title>
<style>{css}</style></head><body><main>
<h1>Кровля: раскладка металлочерепицы и конёк</h1>
<p class="sub">Навес 5.45 × 4.60 м, кровля {roof_len:.2f} м вдоль конька, уклон 12°, косина площадки 2.87° ·
{tiles['n']} листов · конёк плоский {WING:.0f}×{WING:.0f}</p>

<h2>Раскладка листов</h2>
{tiles_html}

<h2 class="pb">Конёк</h2>
<div class="card">{ridge_svg()}
<ol class="leg2">{''.join(f"<li>{html.escape(x.format(w=int(WING), xl=int(round(xl)), xr=int(round(xr)), gap=int(T.RIDGE_GAP * 1000)))}</li>" for x in RIDGE_LEGEND)}</ol>
<p class="note">Разрез по оси рамы через конёк, левый скат — слева; листы и конёк — схематично (высота профиля принята
{PROFILE_H:.0f} мм).</p></div>
<div class="card">
<h3>Почему плоский конёк 200×200</h3>
<ul>
<li>Уклон пологий (12°): плоский конёк ложится крыльями на гребни волн и почти не выступает над кровлей; полукруглому
нужны торцевые заглушки, он дороже и больше парусит.</li>
<li>Крыло {WING:.0f} мм перекрывает по горизонтали ≈ {WING * M.COS:.0f} мм от оси: торец листа — в
{T.RIDGE_GAP * 1000:.0f} мм от оси, нахлёст конька на лист ≈ {WING * M.COS - T.RIDGE_GAP * 1000 * M.COS:.0f} мм
(нужно не меньше 100).</li>
<li><b>Угол гиба 156°</b> (180° − 2 × 12°). Стандартные коньки гнут на 90–120° — угол указать при заказе.</li>
<li>Под коньком по оси — коньковая обрешётина 60×60, её верх на 60 мм выше вершины стропил. Конёк лежит на гребнях
волн; его гиб — на 60–75 мм выше вершины стропил (зависит от высоты профиля черепицы, 25–40 мм). При профиле
от ≈ 35 мм конёк проходит над обрешётиной с зазором и крепится только по гребням; при низком профиле гиб ложится
на обрешётину — тогда можно дополнительно прикрутить его по оси к обрешётине саморезами 4.8×19 через 300–350 мм.</li>
</ul>
<h3>Спецификация</h3>
<table><thead><tr><th>Позиция</th><th class="n">Кол-во</th><th>Примечание</th></tr></thead><tbody>{srow}</tbody></table>
<h3>Монтаж</h3>
<ol>
<li>Листы укладывать по раскладке; длина листа — от свеса 45 мм за торец стропила до {T.RIDGE_GAP * 1000:.0f} мм не
доходя оси конька: торец листа не упирается в коньковую обрешётину, остаётся зазор ≈ 20 мм. Карнизная
обрешётина (50×30 на ребро) выше рядовых на 15 мм — под край листа без ступеньки; высоту ступеньки выбранного
профиля проверить (см. uzly.pdf, узел Г).</li>
<li>На правом скате лист у конька свешивается за последнюю обрешётину (она в {xr:.0f} мм от оси) на ≈
{xr - T.RIDGE_GAP * 1000 * M.COS:.0f} мм — на этот участок не наступать.</li>
<li>Наклеить уплотнитель у торцов листов с обеих сторон конька.</li>
<li>Уложить элементы конька с нахлёстом {CAP_LAP * 1000:.0f} мм; верхний в нахлёсте — со стороны преобладающего ветра.
Выпуск за торцевые планки — 30 мм, торцы подрезать и загнуть вниз.</li>
<li>Крепить через гребень каждой второй волны: слева — 4.8×35 в обрешётину, справа — 4.8×19 в лист; на нахлёстах —
по 2 самореза. Не перетягивать: шайба EPDM должна лишь слегка выдавиться.</li>
</ol>
</div>
</main></body></html>"""
    return page


def main():
    (OUT / "krovlya.html").write_text(build(), encoding="utf-8")
    print("output/krovlya.html")


if __name__ == "__main__":
    main()
