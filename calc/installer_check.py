"""Проверка на сосредоточенную нагрузку от монтажника (ДБН В.1.2-2, п. 6.10).

1.0 кН (100 кгс) на площадке 10×10 см в самом невыгодном месте покрытия, γfm = 1.2, без других временных
нагрузок (с собственным весом, γf = 1.05). Нагрузка ставится по очереди в каждый узел обрешётки (концы
консолей, пролёты, свес у карниза) и в узлы торцевой обвязки; для каждой группы стержней — наибольший
коэффициент использования по прочности (σ = |N|/A + |My|/Wy + |Mz|/Wz ≤ Ry) и наибольший прогиб под грузом.
"""
from __future__ import annotations

import numpy as np

import fem as F
import model as M

P_CHAR = 1.0e3        # Н
GF = 1.2
RY = 230e6


def installer_check(model, P=P_CHAR * GF, groups=("lath", "ge"), margin=0.0):
    """margin — монтажник не подходит к кромкам кровли ближе margin, м (передняя/задняя кромки и карнизы)."""
    m = model
    S = F.Solver(m)
    uc = M.unit_cases(m, M.Loads())
    D = {}
    for name in ("Dsteel", "Droof"):
        for ei, q in uc.get(name, {}).items():
            D[ei] = D.get(ei, 0) + 1.05 * np.asarray(q)
    nodes = set()
    for mm in m.members.values():
        if m.members and mm["group"] in groups:
            for ei in mm["elems"]:
                e = m.elems[ei]
                nodes.update((e.n1, e.n2))
    if margin > 0:
        x_lo, x_hi = -M.OVH_L + margin, M.SPAN + M.OVH_R - margin
        y_lo, y_hi = M.Y_MIN + margin, M.Y_MAX - margin
        nodes = {n for n in nodes
                 if x_lo - 1e-6 <= m.nodes[n][0] <= x_hi + 1e-6
                 and y_lo - 1e-6 <= m.logical_y(m.nodes[n]) <= y_hi + 1e-6}
    A = np.array([e.sec.A for e in m.elems])
    Wy = np.array([e.sec.Wy for e in m.elems])
    Wz = np.array([e.sec.Wz for e in m.elems])
    L = np.array([e.L for e in m.elems])
    grp = np.array([m.members[e.member]["group"] for e in m.elems])
    st = np.linspace(0, 1, 3)[None, :] * L[:, None]
    res = {}
    for n in sorted(nodes):
        u, ends, ql = S.solve(D, {n: np.array([0, 0, -P, 0, 0, 0])})
        f = np.array(ends)
        q = np.array([x if x is not None else np.zeros(3) for x in ql])
        N = -(f[:, 0:1] + q[:, 0:1] * st)
        Mz = -f[:, 5:6] + f[:, 1:2] * st + q[:, 1:2] * st * st / 2
        My = -f[:, 4:5] - f[:, 2:3] * st - q[:, 2:3] * st * st / 2
        r = (np.abs(N) / A[:, None] + np.abs(My) / Wy[:, None] + np.abs(Mz) / Wz[:, None]).max(1) / RY
        for g in set(grp):
            v = r[grp == g].max()
            if v > res.get(g, (0.0,))[0]:
                res[g] = (float(v), tuple(np.round(m.nodes[n], 2)))
        dz = -u[6 * n + 2]
        if dz > res.get("прогиб, мм", (0.0,))[0] / 1000 or "прогиб, мм" not in res:
            res["прогиб, мм"] = (float(dz * 1000), tuple(np.round(m.nodes[n], 2)))
    return res
