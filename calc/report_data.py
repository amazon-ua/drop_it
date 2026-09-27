"""Общие функции для отчёта: восстановление схемы по результатам, ведомости, раскрой."""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

import checks as C
import costs as K
import model as M
from optimize import rotated
from sections import load_price_list

SECS = load_price_list()


def sec_by_name(name):
    rot = name.endswith(" пл.")
    base = name[:-4] if rot else name
    for s in SECS:
        if s.name == base:
            return rotated(s) if rot else s
    raise KeyError(name)


def scheme_from_result(r):
    p = dict(r["params"])
    sc = M.Scheme(name=r["label"], **p)
    sc.groups = {g: sec_by_name(n) for g, n in r["groups"].items()}
    return sc


def piece_list(model, sc):
    """Детали каркаса: группа, сечение, длина, количество (одинаковые объединены)."""
    q = K.quantities(model, sc)
    rows = defaultdict(lambda: dict(n=0))
    for p in q["pieces"]:
        L = round(p["L"], 3)
        key = (p["group"], p["sec"].name, L)
        if p["group"] == "col":
            key = (p["group"], p["sec"].name, L, M.column_name(p["meta"]["x"], p["meta"]["y"]))
        rows[key]["n"] += 1
        rows[key]["sec"] = p["sec"]
        rows[key]["parts"] = p["parts"]
    out = []
    for key, d in sorted(rows.items(), key=lambda kv: (list(M.GROUP_INFO).index(kv[0][0]), -kv[0][2])):
        g, sn, L = key[:3]
        name = M.GROUP_INFO[g][0]
        if g == "col":
            nm = key[3]
            zb = [v for v in M.COLUMN_BASES.values() if v[0] == nm][0][1]
            name = f"Колонна {nm} (верх бетона {zb:+.2f})"
        out.append(dict(group=g, name=name, sec=sn, L=L, n=d["n"], parts=d["parts"],
                        mass=d["sec"].mass * L * d["n"], price=d["sec"].price))
    return out, q


def cutting_plan(pieces, stock=K.STOCK_LEN, kerf=K.CUT_ALLOW):
    """Раскрой на хлысты 6 м (FFD) — для варианта закупки целыми хлыстами.

    Детали длиннее хлыста делятся: полный хлыст + остаток (стык на раме)."""
    by_sec = defaultdict(list)
    for p in pieces:
        for _ in range(p["n"]):
            L = p["L"]
            while L > stock + 1e-9:
                by_sec[p["sec"]].append((stock, p["name"] + " (часть)"))
                L -= stock
            by_sec[p["sec"]].append((L, p["name"]))
    plan = {}
    for sec, items in by_sec.items():
        items.sort(key=lambda t: -t[0])
        bars = []
        for L, nm in items:
            for b in bars:
                if b["free"] >= L + kerf - 1e-9:
                    b["cuts"].append((L, nm))
                    b["free"] -= L + kerf
                    break
            else:
                bars.append(dict(cuts=[(L, nm)], free=stock - L - kerf))
        plan[sec] = bars
    return plan


def member_table(an):
    """Сводка по группам: сечение, число стержней, max коэффициент, определяющая проверка."""
    m = an.model
    gu = an.group_util()
    rows = []
    for g in M.GROUP_INFO:
        if g not in an.sc.groups:
            continue
        mids = [mid for mid, mm in m.members.items() if mm["group"] == g]
        if not mids:
            continue
        # максимальные усилия по группе
        Nc = Nt = My = 0.0
        for mid in mids:
            for f in an.member_results[mid]["forces"].values():
                Nc = max(Nc, -f["Nmin"])
                Nt = max(Nt, f["Nmax"])
                My = max(My, f["My"], f["Mz"])
        u, gov = gu.get(g, (0.0, ""))
        rows.append(dict(group=g, name=M.GROUP_INFO[g][0], sec=an.sc.groups[g].name, u=u, gov=gov,
                         Nc=Nc / 1e3, Nt=Nt / 1e3, M=My / 1e3))
    return rows


# ---------------------------------------------------------------------------
# Заготовки для изготовления: фактические длины реза и торцевые резы
# ---------------------------------------------------------------------------
def fab_details(model, sc, lath_split=False):
    """Список заготовок: name, group, sec, L (длина реза, м), n, cuts (описание торцов).

    Длины — «в чистоте» по узлам из output/uzly.html (затяжка между гранями колонн, раскос — от грани
    колонны до фасонки и т. д.); обрешётина делится на две заготовки со стыком над стропилом рамы 3."""
    import math as _m
    q = K.quantities(model, sc)
    g = sc.groups
    col, raf, tie, stub = g["col"], g["raf"], g["tie"], g["stub"]
    TP = 0.005                                   # фасонка
    slope = _m.degrees(M.SLOPE)
    out = []

    def add(name, group, sec, L, n, cuts):
        for d in out:
            if d["name"] == name and d["sec"].name == sec.name and abs(d["L"] - L) < 5e-4:
                d["n"] += n
                return
        out.append(dict(name=name, group=group, sec=sec, L=round(L, 3), n=n, cuts=cuts))

    for p in q["pieces"]:
        grp, sec, L, meta = p["group"], p["sec"], p["L"], p["meta"]
        if grp == "col":
            nm = M.column_name(meta["x"], meta["y"])
            add(f"Колонна {nm}", grp, sec, L, 1,
                f"низ — прямой рез (+ заглушка), верх — под {slope:.0f}° по низу стропила; в бетоне {sc.embed:.2f} м")
        elif grp == "raf":
            add("Стропило " + ("короткое (свес 0.40)" if meta.get("side") == "L" else "длинное (свес 0.90)"),
                grp, sec, L, 1,
                f"у конька — вертикальный рез ({90 - slope:.0f}° к оси), у карниза — перпендикулярно оси")
        elif grp == "tie":
            mid = abs(meta.get("frame", 0.0) - M.BAY / 2) < 1e-6
            w = stub.h if mid else col.h
            add("Затяжка " + ("средней рамы" if mid else "крайней рамы"), grp, sec, L - w, 1,
                "оба торца — прямые, между гранями " + ("стоек" if mid else "колонн"))
        elif grp == "stub":
            zb = M.z_rafter(0.0) - raf.h / 2 / _m.cos(M.SLOPE) - 0.006
            add("Стойка-вставка", grp, sec, zb - 2.930, 1, f"низ — прямой (встаёт на столик фермы), верх — под {slope:.0f}°")
        elif grp == "kp":
            Lc = (M.z_rafter(M.X_RIDGE) - raf.h / 2 / _m.cos(M.SLOPE)) - (M.Z_TIE + tie.h / 2)
            add("Подвеска у конька", grp, sec, Lc, 1, f"низ — прямой, верх — «домиком» 2×{slope:.0f}° под стропила")
        elif grp == "strut":
            dx = sc.strut_dx
            dz = M.z_rafter(M.X_RIDGE - dx) - M.Z_TIE
            beta = _m.atan2(dz, dx)                                  # к горизонту
            gam = beta + M.SLOPE                                     # к стропилу
            Lc = _m.hypot(dx, dz) - (tie.h / 2) / _m.sin(beta) - (raf.h / 2) / _m.sin(gam)
            add("Подкос фермы", grp, sec, Lc, 1,
                f"низ — под {_m.degrees(beta):.0f}° к оси (на затяжку у подвески), верх — под {_m.degrees(gam):.0f}° (на стропило)")
        elif grp == "sd":
            tg = M.shop_truss_geom(col.b, g["sb"].h, sec.h)
            add("Раскос боковой фермы", grp, sec, tg["L_cut"], 1,
                f"оба торца — горизонтальные резы под {_m.degrees(tg['alpha']):.1f}° к оси (рез по грани "
                f"{tg['foot'] * 1000:.0f} мм): низ — на пояс, верх — под столик")
        elif grp == "sb":
            add("Нижний пояс боковой фермы", grp, sec, L - col.b, 1,
                "оба торца — прямые; по фактическому расстоянию между гранями колонн")
        elif grp == "lath" and lath_split:
            add("Обрешётина, часть 1 (край → рама 3)", grp, sec, M.BAY - M.Y_MIN, 1,
                "торцы прямые; стык с частью 2 — над стропилом рамы 3")
            add("Обрешётина, часть 2 (рама 3 → край)", grp, sec, M.Y_MAX - M.BAY, 1, "торцы прямые")
        elif grp == "lath":
            add("Обрешётина цельная", grp, sec, M.Y_MAX - M.Y_MIN, 1,
                "торцы прямые; из хлыста 12 м, без стыка")
        else:
            add(M.GROUP_INFO[grp][0], grp, sec, L, 1, "")
    order = list(M.GROUP_INFO)
    out.sort(key=lambda d: (order.index(d["group"]), d["name"], -d["L"]))
    for d in out:
        d["mass"] = d["sec"].mass * d["L"] * d["n"]
    return out, q


def _pack(items, k12, stocks, kerf):
    """Лучший подходящий (best fit) по убыванию: первые k12 новых хлыстов — 12 м, далее 6 м
    (деталь длиннее короткого хлыста всегда идёт в длинный)."""
    short, long_ = min(stocks), max(stocks)
    bars = []
    n12 = 0
    for L, nm in items:
        best = None
        for b in bars:
            if b["free"] >= L + kerf - 1e-9 and (best is None or b["free"] < best["free"]):
                best = b
        if best is None:
            use_long = (L + kerf > short + 1e-9) or n12 < k12
            st = long_ if use_long else short
            if L + kerf > st + 1e-9:
                return None
            n12 += use_long
            best = dict(cuts=[], free=st, stock=st)
            bars.append(best)
        best["cuts"].append((L, nm))
        best["free"] -= L + kerf
    # длинный хлыст, заполненный не больше короткого, — заменить на короткий
    for b in bars:
        used = b["stock"] - b["free"]
        if b["stock"] == long_ and used <= short + 1e-9:
            b["stock"], b["free"] = short, short - used
    return bars


def bar_plan(details, stocks=None, kerf=K.CUT_ALLOW):
    """Раскрой на хлысты 6 и 12 м: по каждому сечению — сочетание с наименьшей длиной закупки."""
    stocks = stocks or K.BAR_LENGTHS
    by_sec = defaultdict(list)
    secs = {}
    for d in details:
        secs[d["sec"].name] = d["sec"]
        for _ in range(d["n"]):
            by_sec[d["sec"].name].append((d["L"], d["name"]))
    plan = {}
    for sn, items in by_sec.items():
        items.sort(key=lambda t: -t[0])
        best = None
        for k12 in range(len(items) + 1):
            bars = _pack(items, k12, stocks, kerf)
            if bars is None:
                continue
            key = (sum(b["stock"] for b in bars), len(bars))
            if best is None or key < best[0]:
                best = (key, bars)
        plan[sn] = dict(sec=secs[sn], bars=best[1], need=sum(L for L, _ in items),
                        buy=best[0][0])
    return plan


PLATES = [
    # позиция, размер, t (мм), кол-во, масса 1 шт (кг), где, из чего резать
    ("Фасонка узла А", "трапеция 250 × 169 / 223", 5, 8, 0.250 * 0.196 * 0.005 * 7850,
     "узлы А (4 × 2), ставятся на объекте", "полоса 250 мм из листа t=5: 4 пары «валетом» по 392 мм → 250 × 1568"),
    ("Фасонка узла Б", "трапеция 230 × 164 / 213", 5, 4, 0.230 * 0.188 * 0.005 * 7850,
     "узлы Б (2 × 2), в цеху на средней раме", "полоса 230 мм из листа t=5: 2 пары «валетом» по 377 мм → 230 × 754"),
    ("Опорный столик боковой фермы", "370 × 80", 8, 2, 0.37 * 0.08 * 0.008 * 7850,
     "вершина боковой фермы", "полоса 80×8: 2 × 370 = 740 мм"),
    ("Опорная пластина под стропило", "140 × 60", 6, 6, 0.14 * 0.06 * 0.006 * 7850,
     "верх колонн и стоек-вставок", "полоса 60×6: 6 × 140 = 840 мм"),
    ("Заглушка низа колонны", "110 × 70", 4, 4, 0.11 * 0.07 * 0.004 * 7850,
     "низ колонн в лунке", "лист t=4: 4 шт → 220 × 140"),
    ("Заглушка торца стропила в свесе", "100 × 60", 2, 6, 0.1 * 0.06 * 0.002 * 7850,
     "концы стропил у карниза", "лист t=2 (или пластиковые заглушки 100×60)"),
    ("Заглушка торца обрешётины", "35 × 35", 0, 44, 0.0,
     "торцы обрешётин на кромках кровли", "пластиковые заглушки 35×35"),
]
