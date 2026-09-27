"""Подбор сечений по минимуму стоимости для заданной схемы и перебор схем.

Алгоритм для схемы:
 1. полный расчёт (МКЭ + устойчивость + все проверки) при текущих сечениях;
 2. для каждой группы по усилиям и расчётным длинам текущего расчёта выбирается
    самое дешёвое сечение (цена трубы + окраска погонного метра), проходящее все
    проверки с запасом не менее target;
 3. повтор до сходимости; затем полный расчёт-проверка, при превышении — шаг вверх.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import replace

import numpy as np

import checks as C
import costs as K
import model as M
from sections import Section, load_price_list


def rotated(s: Section) -> Section:
    """То же сечение, повёрнутое на 90° (прямоугольная труба «плашмя»)."""
    return replace(s, name=s.name + " пл.", h=s.b, b=s.h, Iy=s.Iz, Iz=s.Iy, Wy=s.Wz, Wz=s.Wy,
                   iy=s.iz, iz=s.iy)


ROTATABLE = {"lath", "tie", "eave", "sb", "st", "tie_e", "lb"}


def candidates(secs, group, paint_rate, min_b=0.0, max_b=1.0):
    out = []
    for s in secs:
        for v in ([s, rotated(s)] if (group in ROTATABLE and s.h != s.b) else [s]):
            if v.b + 1e-9 < min_b or v.b > max_b + 1e-9:
                continue
            out.append(v)
    eff = lambda s: s.price + paint_rate * s.perim
    out.sort(key=eff)
    # Парето-фильтр: убрать сечения, у которых есть более дешёвое не хуже по всем свойствам
    keep = []
    for s in out:
        dom = False
        for k in keep:
            if (k.A >= s.A and k.Iy >= s.Iy and k.Iz >= s.Iz and k.Wy >= s.Wy and k.Wz >= s.Wz
                    and k.c_t_b <= s.c_t_b and k.c_t_h <= s.c_t_h and k.t >= s.t
                    and abs(k.b - s.b) < 1e-9):
                dom = True
                break
        if not dom:
            keep.append(s)
    return keep, eff


class GroupEvaluator:
    """Оценка коэффициента использования группы для другого сечения при тех же усилиях."""

    def __init__(self, an: C.Analysis):
        self.an = an
        m = an.model
        self.by_group = {}
        for mid, mm in m.members.items():
            self.by_group.setdefault(mm["group"], []).append(mid)

    def util(self, group, sec, sections_now):
        an = self.an
        m = an.model
        kt = M.GROUP_INFO[group][1]
        u = 0.0
        old = sections_now[group]
        for mid in self.by_group.get(group, []):
            r = an.member_results[mid]
            Ly, Lz = r["Ly"], r["Lz"]
            # расчётные длины из анализа устойчивости пересчитываем при смене жёсткости
            L = m.members[mid]["L"]
            for cname, f in r["forces"].items():
                ch = C.member_checks(sec, f, Ly, Lz, kt, L, use_sig=False)
                ch.pop("гибкость", None)
                u = max(u, max(ch.values()))
            if "lam_case" in r:
                _, Ly2, Lz2, f2 = r["lam_case"]
                v = C.lam_check(sec, f2, Ly2, Lz2, kt)
                if v is not None:
                    u = max(u, v)
        # прогибы
        for mid in self.by_group.get(group, []):
            d = an.defl_results.get(mid)
            if d:
                u = max(u, d["u"] * old.Iy / sec.Iy)
        if group == "raf":
            for k, d in an.defl_results.items():
                if str(k).startswith("frame"):
                    u = max(u, d["u"] * old.Iy / sec.Iy * 0.6 + d["u"] * 0.4)
        if group == "col":
            for k, d in an.defl_results.items():
                if str(k).startswith("sway"):
                    u = max(u, d["u"] * old.Iy / sec.Iy)
        # узлы
        for key, jr in an.joint_results.items():
            if jr["brace"] == group or jr["chord"] == group:
                u = max(u, self.joint_util(jr, key, group, sec, sections_now))
        return u

    def joint_util(self, jr, key, group, sec, sections_now):
        s1 = sec if jr["brace"] == group else sections_now[jr["brace"]]
        s0 = sec if jr["chord"] == group else sections_now[jr["chord"]]
        return joint_capacity_util(s1, s0, jr)


def joint_capacity_util(s1, s0, jr):
    """Узел трубы к грани трубы (EN 1993-1-8, табл. 7.10–7.11), Ry вместо fy, γM5 = 1."""
    b1 = s1.b if jr["br_across"] == "b" else s1.h
    h1 = s1.h if jr["br_across"] == "b" else s1.b
    b0 = s0.b if jr["ch_face"] == "b" else s0.h
    h0 = s0.h if jr["ch_face"] == "b" else s0.b
    if b1 > b0 + 1e-9:
        return 9.0
    t0, t1 = s0.t, s1.t
    sin = jr.get("sin", 0.7)
    fy = C.RY
    beta = b1 / b0
    if beta < 0.25:
        return 9.0   # вне области применения EN 1993-1-8 (b1/b0 ≥ 0.25)
    eta = h1 / b0
    n0 = jr.get("n0", 0.0)
    if beta <= 0.85:
        kn = 1.0 if n0 <= 0 else min(1.0, 1.3 - 0.4 * n0 / beta)
        NRd = kn * fy * t0 ** 2 / ((1 - beta) * sin) * (2 * eta / sin + 4 * math.sqrt(1 - beta))
    else:
        beff = min(b1, 10 / (b0 / t0) * t0 / t1 * b1)
        N_brace = fy * t1 * (2 * h1 - 4 * t1 + 2 * beff)
        lam = 3.46 * (h0 / t0 - 2) * math.sqrt(1 / sin) / (math.pi * math.sqrt(C.E / fy))
        Phi = 0.5 * (1 + 0.21 * (lam - 0.2) + lam * lam)
        chi = min(1.0, 1 / (Phi + math.sqrt(max(Phi * Phi - lam * lam, 1e-9))))
        N_side = chi * fy * t0 / sin * (2 * h1 / sin + 10 * t0)
        N085 = fy * t0 ** 2 / (0.15 * sin) * (2 * eta / sin + 4 * math.sqrt(0.15))
        NRd = min(N_brace, N085 + (N_side - N085) * (beta - 0.85) / 0.15)
    return jr["N"] / NRd


def _full(sc, loads):
    an = C.Analysis(sc, loads).run_all()
    gu = an.group_util()
    return an, gu, max(v[0] for v in gu.values())


def _with(sc, **groups):
    s2 = sc.copy()
    s2.groups.update(groups)
    return s2


def _eff_cost(sc, an, eff):
    """Стоимость групп по длинам (для выбора порядка улучшений)."""
    lens = {}
    for mm in an.model.members.values():
        lens[mm["group"]] = lens.get(mm["group"], 0.0) + mm["L"]
    return {g: lens.get(g, 0.0) * eff(sc.groups[g]) for g in sc.groups}


def size_scheme(sc: M.Scheme, loads: M.Loads, secs, cal: K.Calibration, target=1.0,
                verbose=False, fixed=None, min_b=None, max_greedy=60):
    """Подбор сечений: (0) выход в допустимую область, (1) прогноз по усилиям с
    демпфированием, (2) жадное удешевление по группам с полной перепроверкой."""
    fixed = fixed or {}
    min_b = dict(min_b or {})
    paint = cal.paint_rate()
    groups = [g for g in sc.groups if g not in fixed]
    cand, eff = {}, None
    for g in sc.groups:
        cand[g], eff = candidates(secs, g, paint, min_b=min_b.get(g, 0.0))
    for g, s in fixed.items():
        sc.groups[g] = s

    def log(msg):
        if verbose:
            print(msg, flush=True)

    def bump(sc_, bad):
        new = dict(sc_.groups)
        for g in bad:
            if g in fixed:
                continue
            cur = new[g]
            ups = [s for s in cand[g] if s.A >= cur.A * 1.05 and s.Iy >= cur.Iy and s.Iz >= cur.Iz
                   and s.b >= cur.b - 1e-9]
            if ups:
                new[g] = min(ups, key=eff)
        s2 = sc_.copy()
        s2.groups = new
        return s2

    # --- (0) допустимая начальная точка
    an, gu, umax = _full(sc, loads)
    for _ in range(15):
        if umax <= target:
            break
        bad = [g for g, (u, _) in gu.items() if u > target]
        log(f"  [0] u={umax:.2f}, усиливаю: {bad}")
        sc = bump(sc, bad)
        an, gu, umax = _full(sc, loads)
    if umax > target:
        return None
    n_full = 1
    # --- (1) прогноз по усилиям с запасом 0.85, откат при неудаче
    for it in range(4):
        ev = GroupEvaluator(an)
        new = dict(sc.groups)
        for g in groups:
            for s_ in cand[g]:
                if eff(s_) >= eff(sc.groups[g]) - 1e-9:
                    break
                if ev.util(g, s_, new) <= 0.85 * target:
                    new[g] = s_
                    break
        if all(new[g].name == sc.groups[g].name for g in groups):
            break
        trial = sc.copy()
        trial.groups = new
        an2, gu2, u2 = _full(trial, loads)
        n_full += 1
        if u2 <= target:
            sc, an, gu, umax = trial, an2, gu2, u2
            log(f"  [1] принято, u={u2:.2f}")
        else:
            bad = {g for g, (u, _) in gu2.items() if u > target}
            # откатываем провалившиеся группы и связанные с ними
            for g in bad:
                if g in new:
                    new[g] = sc.groups[g]
            trial = sc.copy()
            trial.groups = new
            an2, gu2, u2 = _full(trial, loads)
            n_full += 1
            if u2 <= target:
                sc, an, gu, umax = trial, an2, gu2, u2
                log(f"  [1] принято частично, u={u2:.2f}")
            else:
                log(f"  [1] отклонено (u={u2:.2f})")
    # --- (2) жадное удешевление
    tried = set()
    improved = True
    while improved and n_full < max_greedy:
        improved = False
        ev = GroupEvaluator(an)
        costs_now = _eff_cost(sc, an, eff)
        for g in sorted(groups, key=lambda g: -costs_now[g]):
            cheaper = [s_ for s_ in cand[g] if eff(s_) < eff(sc.groups[g]) - 1e-9
                       and (g, s_.name) not in tried]
            cheaper = [s_ for s_ in cheaper if ev.util(g, s_, sc.groups) <= 1.05 * target]
            for s_ in cheaper[:3]:
                tried.add((g, s_.name))
                trial = _with(sc, **{g: s_})
                an2, gu2, u2 = _full(trial, loads)
                n_full += 1
                if u2 <= target:
                    log(f"  [2] {g}: {sc.groups[g].name} → {s_.name}, u={u2:.2f}")
                    sc, an, gu, umax = trial, an2, gu2, u2
                    improved = True
                    break
            if improved or n_full >= max_greedy:
                break
    q = K.quantities(an.model, sc)
    est = K.estimate(q, cal)
    log(f"  расчётов: {n_full}, итог {est['total']:.0f} грн")
    return sc, an, est, q


def default_groups(sc: M.Scheme, secs):
    from sections import by_name
    start = {
        "col": "100×100×3", "raf": "80×80×3", "tie": "60×40×2", "kp": "40×40×2",
        "strut": "40×40×2", "knee": "40×40×2", "lath": "40×40×2", "sd": "50×50×2",
        "sb": "40×40×2", "st": "60×40×2", "stub": "80×80×3", "eave": "60×40×2",
        "kl": "40×40×2", "xb": "40×40×2",
        "raf_e": "60×40×2", "tie_e": "40×40×2", "kp_e": "20×20×2", "strut_e": "20×20×2",
        "lb": "80×40×3", "spd": "40×40×2", "spp": "50×50×2",
    }
    need = {"col", "raf", "tie", "lath"}
    if sc.web in ("K", "KS"):
        need.add("kp")
    if sc.web == "KS":
        need.add("strut")
    if sc.knee_t:
        need.add("knee")
    if sc.frames == 5:
        need |= {"stub", "lb", "spd", "spp"}
        if sc.edge_groups:
            need |= {"raf_e", "tie_e"}
            if sc.web in ("K", "KS"):
                need.add("kp_e")
            if sc.web == "KS":
                need.add("strut_e")
    if sc.frames == 3:
        need |= {"sd", "sb", "stub"}
        if sc.side_top:
            need.add("st")
    else:
        if sc.eave_beam:
            need.add("eave")
        if sc.knee_l:
            need.add("kl")
    if sc.roof_x:
        need.add("xb")
    out = {}
    for g in need:
        try:
            out[g] = by_name(secs, start[g])
        except KeyError:
            ref = by_name(load_price_list(), start[g])
            out[g] = min(secs, key=lambda s: abs(s.A - ref.A) + abs(s.h - ref.h))
    return out
