"""Проверки элементов по ДБН В.2.6-198:2014 (методика СНиП II-23 / СП 16),
узлов труб — по ДСТУ-Н Б EN 1993-1-8 (табл. 7.10–7.11), заделки — по Бромсу.
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

from fem import E, Solver, member_forces_along, kg_local
import model as M

RY = 230e6        # Па, расчётное сопротивление (С235 / S235JR, t ≤ 20 мм)
RS = 0.58 * RY
GAMMA_C = 1.0
CT_COMP = 42.0    # предельное c/t сжатой стенки (класс 3)
CT_WEB = 124.0

# предельные гибкости (ДБН В.2.6-198, табл. 16.1/16.2)
def lam_limit_comp(kind_type, alpha):
    a = max(alpha, 0.5)
    if kind_type == "main":
        return 180 - 60 * a
    if kind_type == "web":
        return 210 - 60 * a
    return 200.0


LAM_LIMIT_TENS = 400.0


def phi_buckling(lam, curve="b"):
    """Коэффициент устойчивости φ при центральном сжатии (ДБН В.2.6-198, ф. 8.3)."""
    lb = lam * math.sqrt(RY / E)
    if lb <= 0.4:
        return 1.0
    a, b = {"a": (0.03, 0.06), "b": (0.04, 0.09), "c": (0.04, 0.14)}[curve]
    lim = {"a": 3.8, "b": 4.4, "c": 5.8}[curve]
    if lb > lim:
        return min(1.0, 7.6 / lb ** 2)
    d = 9.87 * (1 - a + b * lb) + lb ** 2
    ph = 0.5 * (d - math.sqrt(d * d - 39.48 * lb * lb)) / lb ** 2
    return min(1.0, ph, 7.6 / lb ** 2)


def defl_limit(L):
    """Предельный прогиб элементов покрытия (эстетико-психологические требования):
    L ≤ 1 м — L/120; 3 м — L/150; 6 м — L/200; 24 м — L/250 (интерполяция)."""
    pts = [(1.0, 120), (3.0, 150), (6.0, 200), (24.0, 250)]
    if L <= 1.0:
        n = 120
    elif L >= 24:
        n = 250
    else:
        for (l1, n1), (l2, n2) in zip(pts[:-1], pts[1:]):
            if l1 <= L <= l2:
                n = n1 + (n2 - n1) * (L - l1) / (l2 - l1)
                break
    return L / n, n



def member_checks(sec, f, Ly, Lz, kt, L, use_sig=True):
    """Все проверки стержня для одного сочетания. f: Nmin, Nmax, My, Mz, Vy, Vz, sig."""
    checks = {}
    if use_sig and f.get("sig") is not None:
        checks["прочность"] = f["sig"] / (RY * GAMMA_C)
    else:
        N = max(abs(f["Nmin"]), abs(f["Nmax"]))
        checks["прочность"] = (N / sec.A + f["My"] / sec.Wy + f["Mz"] / sec.Wz) / (RY * GAMMA_C)
    Aw_z = 2 * sec.h * sec.t
    Aw_y = 2 * sec.b * sec.t
    checks["срез"] = max(f["Vz"] / Aw_z, f["Vy"] / Aw_y) / (RS * GAMMA_C)
    Nc = max(0.0, -f["Nmin"])
    Nt = max(0.0, f["Nmax"])
    lam_y = Ly / sec.iy
    lam_z = Lz / sec.iz
    if Nc > 1.0:
        ph = min(phi_buckling(lam_y), phi_buckling(lam_z))
        Ncr_y = math.pi ** 2 * E * sec.Iy / Ly ** 2
        Ncr_z = math.pi ** 2 * E * sec.Iz / Lz ** 2
        ay, az = Nc / Ncr_y, Nc / Ncr_z
        if ay >= 0.999 or az >= 0.999:
            stab = 9.99
        else:
            stab = (Nc / (ph * sec.A * RY * GAMMA_C)
                    + f["My"] / (sec.Wy * RY * GAMMA_C * (1 - ay))
                    + f["Mz"] / (sec.Wz * RY * GAMMA_C * (1 - az)))
        checks["устойчивость"] = stab
        alpha_n = Nc / (ph * sec.A * RY * GAMMA_C)
        if kt != "beam" or alpha_n > 0.1:
            lim = lam_limit_comp(kt if kt != "beam" else "brace", alpha_n)
            checks["гибкость"] = max(lam_y, lam_z) / lim
        if alpha_n > 0.2:
            checks["стенка c/t"] = sec.c_t_max / CT_COMP
    if Nt > 1.0 and kt != "beam":
        checks["гибкость раст."] = max(L / sec.iy, L / sec.iz) / LAM_LIMIT_TENS
    if f["My"] > 0 or f["Mz"] > 0:
        if f["My"] >= f["Mz"]:
            ct = max(sec.c_t_b / CT_COMP, sec.c_t_h / CT_WEB)
        else:
            ct = max(sec.c_t_h / CT_COMP, sec.c_t_b / CT_WEB)
        checks["стенка c/t изг."] = ct
    return checks



def lam_check(sec, f, Ly, Lz, kt):
    Nc = max(0.0, -f["Nmin"])
    if Nc <= 1.0:
        return None
    lam_y, lam_z = Ly / sec.iy, Lz / sec.iz
    ph = min(phi_buckling(lam_y), phi_buckling(lam_z))
    alpha_n = Nc / (ph * sec.A * RY * GAMMA_C)
    if kt == "beam" and alpha_n <= 0.1:
        return None
    lim = lam_limit_comp(kt if kt != "beam" else "brace", alpha_n)
    return max(lam_y, lam_z) / lim

class Analysis:
    """Расчёт схемы: усилия от единичных загружений, сочетания, устойчивость, проверки."""

    def __init__(self, sc: M.Scheme, loads: M.Loads, nmodes=12, do_buckling=True):
        self.sc = sc
        self.loads = loads
        self.model = M.build(sc)
        self.solver = Solver(self.model)
        self.cases = M.unit_cases(self.model, loads)
        self.uls, self.sls = M.combos(loads)
        self.nmodes = nmodes
        self.do_buckling = do_buckling
        self._solve_cases()

    def _solve_cases(self):
        self.case_res = {}
        for name, el in self.cases.items():
            u, ends, ql = self.solver.solve(el)
            self.case_res[name] = (u, ends, ql)

    def combine(self, coeffs):
        n_el = len(self.model.elems)
        u = np.zeros(self.model.ndof)
        ends = [np.zeros(12) for _ in range(n_el)]
        ql = [np.zeros(3) for _ in range(n_el)]
        for name, c in coeffs.items():
            if c == 0 or name not in self.case_res:
                continue
            uc, ec, qc = self.case_res[name]
            u += c * uc
            for i in range(n_el):
                ends[i] = ends[i] + c * ec[i]
                if qc[i] is not None:
                    ql[i] = ql[i] + c * qc[i]
        return u, ends, ql

    # ---------------------------------------------------------------
    def member_forces(self, ends, ql):
        """Для каждого проверяемого стержня: N (min/max), |My|max, |Mz|max, |V|max."""
        m = self.model
        out = {}
        for mid, mm in m.members.items():
            Nmin, Nmax, My, Mz, Vy, Vz = 1e30, -1e30, 0.0, 0.0, 0.0, 0.0
            smax = 0.0
            for ei in mm["elems"]:
                e = m.elems[ei]
                f = member_forces_along(e, ends[ei], ql[ei], nst=5)
                Nmin = min(Nmin, f[:, 1].min())
                Nmax = max(Nmax, f[:, 1].max())
                My = max(My, np.abs(f[:, 5]).max())
                Mz = max(Mz, np.abs(f[:, 6]).max())
                Vy = max(Vy, np.abs(f[:, 2]).max())
                Vz = max(Vz, np.abs(f[:, 3]).max())
                s = e.sec
                sig = np.abs(f[:, 1]) / s.A + np.abs(f[:, 5]) / s.Wy + np.abs(f[:, 6]) / s.Wz
                smax = max(smax, sig.max())
            out[mid] = dict(Nmin=Nmin, Nmax=Nmax, My=My, Mz=Mz, Vy=Vy, Vz=Vz, sig=smax)
        return out

    def effective_lengths(self, ends, forces):
        """Расчётные длины сжатых стержней из расчёта на устойчивость (энергетическое участие)."""
        m = self.model
        res = {}
        alpha1 = None
        if not self.do_buckling:
            return {mid: (mm["L"], mm["L"], None) for mid, mm in m.members.items()}, None
        modes, KG = self.solver.buckling(ends, nmodes=self.nmodes)
        if modes:
            alpha1 = modes[0][0]
        # вклад каждого стержня в работу геометрической матрицы по формам (векторно)
        ne = len(m.elems)
        if not hasattr(self, "_vec"):
            dofs = np.array([np.r_[6 * e.n1:6 * e.n1 + 6, 6 * e.n2:6 * e.n2 + 6] for e in m.elems])
            Ts = np.array([e.T for e in m.elems])
            Ls = np.array([e.L for e in m.elems])
            mem_ids = sorted(m.members)
            pos = {mid: i for i, mid in enumerate(mem_ids)}
            emem = np.array([pos[e.member] for e in m.elems])
            self._vec = (dofs, Ts, Ls, mem_ids, emem)
        dofs, Ts, Ls, mem_ids, emem = self._vec
        Nel = np.array([-ends[i][0] for i in range(ne)])
        c = Nel / (30 * Ls)
        part = []
        for lam, phi in modes:
            ul = np.einsum("nij,nj->ni", Ts, phi[dofs])
            a0, a1, a2, a3 = ul[:, 1], ul[:, 5], ul[:, 7], ul[:, 11]
            L_ = Ls
            qv = (36 * a0 ** 2 + 4 * L_ ** 2 * a1 ** 2 + 36 * a2 ** 2 + 4 * L_ ** 2 * a3 ** 2
                  + 2 * (3 * L_ * a0 * a1 - 36 * a0 * a2 + 3 * L_ * a0 * a3 - 3 * L_ * a1 * a2
                         - L_ ** 2 * a1 * a3 - 3 * L_ * a2 * a3))
            b0, b1, b2, b3 = ul[:, 2], ul[:, 4], ul[:, 8], ul[:, 10]
            qw = (36 * b0 ** 2 + 4 * L_ ** 2 * b1 ** 2 + 36 * b2 ** 2 + 4 * L_ ** 2 * b3 ** 2
                  + 2 * (-3 * L_ * b0 * b1 - 36 * b0 * b2 - 3 * L_ * b0 * b3 + 3 * L_ * b1 * b2
                         - L_ ** 2 * b1 * b3 + 3 * L_ * b2 * b3))
            gv = np.bincount(emem, weights=c * qv, minlength=len(mem_ids))
            gw = np.bincount(emem, weights=c * qw, minlength=len(mem_ids))
            tot = np.minimum(gv, 0).sum() + np.minimum(gw, 0).sum()
            g = {mid: (gv[i], gw[i]) for i, mid in enumerate(mem_ids)}
            part.append((lam, g, tot))
        # доля групп в работе геометрической матрицы по каждой форме
        grp_of = {mid: m.members[mid]["group"] for mid in mem_ids}
        mode_info = []
        for lam, g, tot in part:
            if tot >= 0:
                mode_info.append(None)
                continue
            gsh = {}
            for mid, (gv, gw) in g.items():
                gsh[grp_of[mid]] = gsh.get(grp_of[mid], 0.0) + (min(gv, 0) + min(gw, 0)) / tot
            mode_info.append(gsh)
        # расчётная длина определяется для целой детали (неразрезного стержня)
        # по наибольшему сжатию в ней; участвуют только формы, где группа даёт ≥ 25 %
        piece_of = {mid: m.elems[m.members[mid]["elems"][0]].piece for mid in mem_ids}
        piece_N = {}
        for mid in mem_ids:
            pc = piece_of[mid]
            piece_N[pc] = max(piece_N.get(pc, 0.0), -forces[mid]["Nmin"])
        piece_L = {}
        for mode_i, ((lam, g, tot), gsh) in enumerate(zip(part, mode_info)):
            if gsh is None:
                continue
            pg = {}
            for mid, (gv, gw) in g.items():
                pc = piece_of[mid]
                v, w = pg.get(pc, (0.0, 0.0))
                pg[pc] = (v + min(gv, 0), w + min(gw, 0))
            gmax = {}
            for pc, (v, w) in pg.items():
                grp = m.pieces[pc]["group"]
                gmax[grp] = min(gmax.get(grp, 0.0), v + w)
            for pc, (v, w) in pg.items():
                grp = m.pieces[pc]["group"]
                if gsh.get(grp, 0.0) < 0.25 or (v + w) > 0.1 * gmax[grp] or piece_N[pc] <= 1.0:
                    continue
                cur = piece_L.setdefault(pc, {})
                plane = "z" if v <= w else "y"
                if plane not in cur:
                    cur[plane] = (lam, piece_N[pc])
        for mid, mm in m.members.items():
            L = mm["L"]
            Lz, Ly = L, L   # Lz — изгиб в плоскости b (ось Iz), Ly — в плоскости h (ось Iy)
            sec = m.elems[mm["elems"][0]].sec
            pc = piece_of[mid]
            if -forces[mid]["Nmin"] > 1.0 and pc in piece_L:
                for plane, (lam, Nref) in piece_L[pc].items():
                    if plane == "z":
                        Lz = max(math.pi * math.sqrt(E * sec.Iz / (lam * Nref)), L)
                    else:
                        Ly = max(math.pi * math.sqrt(E * sec.Iy / (lam * Nref)), L)
            res[mid] = (Ly, Lz, alpha1)
        return res, alpha1

    # ---------------------------------------------------------------
    def check_members(self):
        m = self.model
        results = defaultdict(lambda: dict(u=0.0, gov=""))
        self.alpha = {}
        self.env = {}
        for cname, coeffs in self.uls.items():
            u, ends, ql = self.combine(coeffs)
            forces = self.member_forces(ends, ql)
            leff, a1 = self.effective_lengths(ends, forces)
            self.alpha[cname] = a1
            for mid, mm in m.members.items():
                sec = m.elems[mm["elems"][0]].sec
                f = forces[mid]
                kt = M.GROUP_INFO[mm["group"]][1]
                Ly, Lz, _ = leff[mid]
                checks = member_checks(sec, f, Ly, Lz, kt, mm["L"])
                # предельная гибкость — по сочетанию с наибольшим сжатием стержня (ниже)
                checks.pop("гибкость", None)
                Ncur = -f["Nmin"]
                rr = results[mid]
                if Ncur > rr.get("Ncmax", 0.0):
                    rr["Ncmax"] = Ncur
                    rr["lam_case"] = (cname, Ly, Lz, f)
                r = results[mid]
                for k, v in checks.items():
                    if v > r["u"]:
                        r["u"] = v
                        r["gov"] = f"{k} [{cname}]"
                    key = "chk_" + k
                    r[key] = max(r.get(key, 0.0), v)
                r.setdefault("forces", {})[cname] = f
                r["Ly"] = max(r.get("Ly", 0), Ly)
                r["Lz"] = max(r.get("Lz", 0), Lz)
            self.env[cname] = (u, ends, ql, forces)
        for mid, r in results.items():
            if "lam_case" not in r:
                continue
            cname, Ly, Lz, f = r["lam_case"]
            mm = m.members[mid]
            sec = m.elems[mm["elems"][0]].sec
            kt = M.GROUP_INFO[mm["group"]][1]
            v = lam_check(sec, f, Ly, Lz, kt)
            if v is not None:
                r["chk_гибкость"] = v
                if v > r["u"]:
                    r["u"] = v
                    r["gov"] = f"гибкость [{cname}]"
        self.member_results = dict(results)
        return self.member_results

    # ---------------------------------------------------------------
    def check_deflections(self):
        m = self.model
        res = {}
        for cname, coeffs in self.sls.items():
            u, ends, ql = self.combine(coeffs)
            U = u.reshape(-1, 6)[:, :3]
            for mid, mm in m.members.items():
                kind = mm.get("kind")
                if kind not in ("lath", "rafter", "tie", "eave", "sb", "st"):
                    continue
                nodes = []
                for ei in mm["elems"]:
                    e = m.elems[ei]
                    nodes += [e.n1, e.n2]
                nodes = list(dict.fromkeys(nodes))
                P = np.array([m.nodes[n] for n in nodes])
                p1, p2 = mm["p1"], mm["p2"]
                i1 = int(np.argmin(np.linalg.norm(P - p1, axis=1)))
                i2 = int(np.argmin(np.linalg.norm(P - p2, axis=1)))
                d = p2 - p1
                Lm = np.linalg.norm(d)
                d = d / Lm
                cant = mm.get("cant") or mm.get("overhang")
                maxrel = 0.0
                for k, n in enumerate(nodes):
                    t = np.dot(m.nodes[n] - p1, d) / Lm
                    if cant:
                        # консоль: прогиб конца относительно касательной у опоры не
                        # вычисляем — берём полное перемещение свободного конца
                        # относительно опорного узла
                        # опорный узел — тот, что ближе к раме/колонне
                        base = self._cant_base(mm, nodes, P)
                        rel = U[n] - U[base]
                    else:
                        rel = U[n] - ((1 - t) * U[nodes[i1]] + t * U[nodes[i2]])
                    rel = rel - np.dot(rel, d) * d
                    maxrel = max(maxrel, np.linalg.norm(rel))
                Lef = 2 * Lm if cant else Lm
                lim, n_ = defl_limit(Lef)
                r = res.setdefault(mid, dict(u=0.0, gov=""))
                val = maxrel / lim
                if val > r["u"]:
                    r.update(u=val, gov=f"прогиб {maxrel*1000:.1f} мм ≤ {lim*1000:.1f} (L/{n_:.0f}) [{cname}]",
                             f=maxrel, lim=lim)
            # общий прогиб конька и снос оголовков
            for fy in m.frames_y:
                nr = m.add_node((M.X_RIDGE, fy, M.z_rafter(M.X_RIDGE)))
                nl = m.add_node((0.0, fy, M.Z_NODE))
                nrr = m.add_node((M.SPAN, fy, M.Z_NODE))
                dz = abs(U[nr][2] - 0.5 * (U[nl][2] + U[nrr][2]))
                lim, n_ = defl_limit(M.SPAN)
                key = f"frame_{fy}"
                r = res.setdefault(key, dict(u=0.0, gov=""))
                if dz / lim > r["u"]:
                    r.update(u=dz / lim, gov=f"прогиб конька {dz*1000:.1f} мм ≤ {lim*1000:.1f} [{cname}]")
            for xc in (0.0, M.SPAN):
                for yc in (0.0, M.BAY):
                    n = m.add_node((xc, yc, M.Z_NODE))
                    dh = np.linalg.norm(U[n][:2])
                    H = M.Z_NODE - M.Z_BASE
                    lim = H / 150
                    key = f"sway_{xc}_{yc}"
                    r = res.setdefault(key, dict(u=0.0, gov=""))
                    if dh / lim > r["u"]:
                        r.update(u=dh / lim, gov=f"снос оголовка {dh*1000:.1f} мм ≤ {lim*1000:.1f} (h/150) [{cname}]")
        self.defl_results = res
        return res

    def _cant_base(self, mm, nodes, P):
        m = self.model
        if mm.get("kind") == "lath":
            # опора — узел на раме (y в frames_y)
            for k, n in enumerate(nodes):
                if any(abs(P[k][1] - fy) < 1e-6 for fy in m.frames_y):
                    return n
        else:
            for k, n in enumerate(nodes):
                if abs(P[k][0]) < 1e-6 or abs(P[k][0] - M.SPAN) < 1e-6:
                    return n
        return nodes[0]

    # ---------------------------------------------------------------
    def check_joints(self):
        """Узлы примыкания решётки к поясу (труба к грани трубы, без фасонок)."""
        m = self.model
        # узел -> список стержней
        node_members = defaultdict(set)
        for mid, mm in m.members.items():
            for ei in mm["elems"]:
                e = m.elems[ei]
                node_members[e.n1].add(mid)
                node_members[e.n2].add(mid)
        chord_kinds = {"rafter", "tie", "col", "eave", "sb", "st"}
        brace_kinds = {"strut", "kp", "knee", "sd", "kl", "sb"}
        gusset_nodes = self.gusset_nodes()
        res = {}
        for mid, mm in m.members.items():
            kind = mm.get("kind")
            if kind not in brace_kinds:
                continue
            for end_pt in (mm["p1"], mm["p2"]):
                n = m.add_node(end_pt)
                if n in gusset_nodes:
                    continue
                chords = [c for c in node_members[n] if c != mid and m.members[c].get("kind") in chord_kinds
                          and m.members[c]["group"] != mm["group"]]
                if not chords:
                    continue
                # пояс — самый крупный
                ch = max(chords, key=lambda c: m.elems[m.members[c]["elems"][0]].sec.A)
                cm = m.members[ch]
                s0 = m.elems[cm["elems"][0]].sec
                s1 = m.elems[mm["elems"][0]].sec
                d1 = mm["p2"] - mm["p1"]
                d0 = cm["p2"] - cm["p1"]
                cos = abs(np.dot(d1, d0)) / (np.linalg.norm(d1) * np.linalg.norm(d0))
                sin = math.sqrt(max(1e-6, 1 - cos * cos))
                # ориентация: нормаль к плоскости «раскос–пояс»
                e1 = m.elems[mm["elems"][0]]
                e0 = m.elems[cm["elems"][0]]
                nrm = np.cross(d1, d0)
                if np.linalg.norm(nrm) < 1e-9:
                    continue
                nrm = nrm / np.linalg.norm(nrm)
                br_across = "b" if abs(np.dot(e1.T[1, :3], nrm)) > 0.7 else "h"
                ch_face = "b" if abs(np.dot(e0.T[1, :3], nrm)) > 0.7 else "h"
                b1 = s1.b if br_across == "b" else s1.h
                h1 = s1.h if br_across == "b" else s1.b
                b0 = s0.b if ch_face == "b" else s0.h
                h0 = s0.h if ch_face == "b" else s0.b
                t0 = s0.t
                beta = min(1.0, b1 / b0)
                eta = h1 / b0
                # усилие в раскосе, max по сочетаниям
                Nmax = 0.0
                n0max = 0.0
                for cname, (u, ends, ql, forces) in self.env.items():
                    Nb = max(abs(forces[mid]["Nmin"]), abs(forces[mid]["Nmax"]))
                    Nmax = max(Nmax, Nb)
                    fc = forces[ch]
                    n0max = max(n0max, fc["sig"] / RY if fc["Nmin"] < 0 else 0.0)
                from optimize import joint_capacity_util
                jr = dict(N=Nmax, sin=sin, n0=n0max, br_across=br_across, ch_face=ch_face)
                u = joint_capacity_util(s1, s0, jr)
                NRd = Nmax / u if u > 0 else float("inf")
                beta = b1 / b0
                mode = "продавливание грани пояса" if beta <= 0.85 else "стенки пояса / раскоса"
                if b1 > b0 + 1e-9:
                    u, mode = 9.0, "раскос шире пояса"
                key = (mid, n)
                res[key] = dict(u=u, N=Nmax, NRd=NRd, brace=mm["group"], chord=cm["group"],
                                beta=beta, mode=mode, sin=sin, br_across=br_across, ch_face=ch_face,
                                n0=n0max)
        self.joint_results = res
        return res

    def gusset_nodes(self):
        """Узлы, выполняемые на фасонках (оголовки колонн, опора средней рамы)."""
        m = self.model
        out = set()
        for fy in m.frames_y:
            for xc in (0.0, M.SPAN):
                out.add(m.add_node((xc, fy, M.Z_TIE)))
                out.add(m.add_node((xc, fy, M.Z_NODE)))
        return out

    # ---------------------------------------------------------------
    def check_foundations(self):
        """Лунка 300×300, бетон, глубина 1.2 м в суглинке φ=22°, c=0 (как в черновике)."""
        m = self.model
        phi_d = math.atan(math.tan(math.radians(M.SOIL["phi"])) / 1.1)
        Kp = math.tan(math.pi / 4 + phi_d / 2) ** 2
        B, L, g = M.SOIL["hole_b"], M.SOIL["hole_L"], M.SOIL["gamma"]
        Mu = 0.5 * g * B * L ** 3 * Kp    # Бромс, короткий свайный столб, несвязный грунт
        res = {}
        for xc in (0.0, M.SPAN):
            for yc in (0.0, M.BAY):
                n = m.add_node((xc, yc, M.Z_BASE))
                worst = dict(u=0.0)
                for cname, coeffs in self.uls.items():
                    u, ends, ql = self.combine(coeffs)
                    # реакция: сумма концевых сил элементов в узле
                    F = np.zeros(6)
                    for ei, e in enumerate(m.elems):
                        if e.n1 == n:
                            F += (e.T.T @ ends[ei])[:6]
                        elif e.n2 == n:
                            F += (e.T.T @ ends[ei])[6:]
                    H = math.hypot(F[0], F[1])
                    Mb = math.hypot(F[3], F[4])
                    V = F[2]  # сила от колонны на узел (вниз > 0 — сжатие)
                    demand = H * L + Mb
                    uu = demand / Mu
                    if uu > worst["u"]:
                        worst = dict(u=uu, H=H, M=Mb, V=V, combo=cname)
                    worst.setdefault("Vcomp", 0.0)
                    worst["Vcomp"] = max(worst["Vcomp"], V)      # сжатие колонны на основание
                    worst.setdefault("Vuplift", 0.0)
                    worst["Vuplift"] = max(worst["Vuplift"], -V)  # выдёргивание
                worst["Mu"] = Mu
                res[(xc, yc)] = worst
        self.found_results = res
        return res

    # ---------------------------------------------------------------
    def run_all(self):
        self.check_members()
        self.check_deflections()
        self.check_joints()
        self.check_foundations()
        return self

    def group_util(self):
        """Максимальный коэффициент использования по группам сечений."""
        m = self.model
        gu = defaultdict(lambda: (0.0, ""))
        for mid, r in self.member_results.items():
            g = m.members[mid]["group"]
            if r["u"] > gu[g][0]:
                gu[g] = (r["u"], r["gov"])
        for mid, r in getattr(self, "defl_results", {}).items():
            if isinstance(mid, int):
                g = m.members[mid]["group"]
            elif str(mid).startswith("frame"):
                g = "raf"
            else:
                g = "col"
            if r["u"] > gu[g][0]:
                gu[g] = (r["u"], r["gov"])
        for key, r in getattr(self, "joint_results", {}).items():
            for g in (r["brace"], r["chord"]):
                if r["u"] > gu[g][0]:
                    gu[g] = (r["u"], f"узел {r['brace']}→{r['chord']}: {r['mode']} N={r['N']/1e3:.1f} кН, NRd={r['NRd']/1e3:.1f} кН")
        return dict(gu)
