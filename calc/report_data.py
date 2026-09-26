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
