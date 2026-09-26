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
def fab_details(model, sc):
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
            add("Стойка-вставка", grp, sec, zb - 2.930, 1, f"низ — прямой (+ заглушка), верх — под {slope:.0f}°")
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
            e = 0.05
            run = M.BAY / 2 - col.b / 2 - (stub.b / 2 + TP)
            z1 = 2.10 + e + (col.b / 2) * (0.9 - e) / (M.BAY / 2)
            z2 = M.Z_TIE - (stub.b / 2 + TP) * (0.9 - e) / (M.BAY / 2)
            a = _m.atan2(z2 - z1, run)
            add("Раскос боковой фермы", grp, sec, _m.hypot(run, z2 - z1), 1,
                f"оба торца — вертикальные резы ({90 - _m.degrees(a):.1f}° к оси)")
        elif grp == "sb":
            add("Нижний пояс боковой фермы", grp, sec, L - col.b, 1, "оба торца — прямые, между гранями колонн")
        elif grp == "lath":
            add("Обрешётина, часть 1 (край → рама 3)", grp, sec, M.BAY - M.Y_MIN, 1,
                "торцы прямые; стык с частью 2 — над стропилом рамы 3")
            add("Обрешётина, часть 2 (рама 3 → край)", grp, sec, M.Y_MAX - M.BAY, 1, "торцы прямые")
        else:
            add(M.GROUP_INFO[grp][0], grp, sec, L, 1, "")
    order = list(M.GROUP_INFO)
    out.sort(key=lambda d: (order.index(d["group"]), d["name"], -d["L"]))
    for d in out:
        d["mass"] = d["sec"].mass * d["L"] * d["n"]
    return out, q


def bar_plan(details, stock=K.STOCK_LEN, kerf=K.CUT_ALLOW):
    """Раскрой на хлысты (первый подходящий по убыванию длины) по каждому сечению."""
    by_sec = defaultdict(list)
    secs = {}
    for d in details:
        secs[d["sec"].name] = d["sec"]
        for _ in range(d["n"]):
            by_sec[d["sec"].name].append((d["L"], d["name"]))
    plan = {}
    for sn, items in by_sec.items():
        items.sort(key=lambda t: -t[0])
        bars = []
        for L, nm in items:
            best = None
            for b in bars:
                if b["free"] >= L + kerf - 1e-9 and (best is None or b["free"] < best["free"]):
                    best = b
            if best is None:
                best = dict(cuts=[], free=stock)
                bars.append(best)
            best["cuts"].append((L, nm))
            best["free"] -= L + kerf
        plan[sn] = dict(sec=secs[sn], bars=bars, need=sum(L for L, _ in items))
    return plan


PLATES = [
    # позиция, размер, t (мм), кол-во, масса 1 шт (кг), где, из чего резать
    ("Фасонка", "трапеция 250 × 169 / 223", 5, 12, 0.250 * 0.196 * 0.005 * 7850,
     "узлы А (4 × 2) и Б (2 × 2)", "полоса 250 мм из листа t=5: 6 пар «валетом» по 392 мм → 250 × 2352"),
    ("Опорная пластина под стропило", "140 × 60", 6, 6, 0.14 * 0.06 * 0.006 * 7850,
     "верх колонн и стоек-вставок", "полоса 60×6: 6 × 140 = 840 мм"),
    ("Заглушка низа колонны", "110 × 70", 4, 4, 0.11 * 0.07 * 0.004 * 7850,
     "низ колонн в лунке", "лист t=4: 4 шт → 220 × 140"),
    ("Заглушка низа стойки-вставки", "60 × 60", 3, 2, 0.06 * 0.06 * 0.003 * 7850,
     "узел Б", "полоса 60×3: 2 × 60 = 120 мм"),
    ("Заглушка торца стропила в свесе", "100 × 60", 2, 6, 0.1 * 0.06 * 0.002 * 7850,
     "концы стропил у карниза", "лист t=2 (или пластиковые заглушки 100×60)"),
    ("Заглушка торца обрешётины", "35 × 35", 0, 44, 0.0,
     "торцы обрешётин на кромках кровли", "пластиковые заглушки 35×35"),
]
