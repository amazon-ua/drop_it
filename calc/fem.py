"""Пространственная стержневая МКЭ-модель (6 степеней свободы в узле).

Линейный статический расчёт, геометрическая матрица жёсткости и
линейный расчёт устойчивости (собственные числа K·φ = λ·(−K_G)·φ).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

E = 2.06e11   # Па
G = 0.79e11   # Па


@dataclass
class Elem:
    n1: int
    n2: int
    group: str          # группа сечения
    zdir: np.ndarray    # направление высоты сечения h (глобальное)
    member: int         # номер проверяемого элемента (стержень между узлами конструкции)
    piece: int          # номер отправочной/заготовочной детали
    sec: object = None  # Section
    T: np.ndarray = None
    L: float = 0.0


@dataclass
class Model:
    nodes: list = field(default_factory=list)       # [np.array(3)]
    elems: list = field(default_factory=list)
    springs: dict = field(default_factory=dict)     # node -> [kx,ky,kz,krx,kry,krz] (None = закреплено)
    members: dict = field(default_factory=dict)     # member id -> dict(meta)
    pieces: dict = field(default_factory=dict)      # piece id -> dict(meta)

    def add_node(self, xyz, tol=1e-6):
        p = np.asarray(xyz, dtype=float)
        if not hasattr(self, "_index"):
            self._index = {}
        key = tuple(np.round(p / 1e-5).astype(np.int64))
        # соседние ячейки округления (защита от граничных случаев)
        for dk in ((0, 0, 0),):
            i = self._index.get(key)
            if i is not None:
                return i
        for i in self._near(key):
            if np.linalg.norm(p - self.nodes[i]) < tol:
                return i
        self.nodes.append(p)
        self._index[key] = len(self.nodes) - 1
        return len(self.nodes) - 1

    def _near(self, key):
        out = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    i = self._index.get((key[0] + dx, key[1] + dy, key[2] + dz))
                    if i is not None:
                        out.append(i)
        return out

    @property
    def ndof(self):
        return 6 * len(self.nodes)


def _transform(p1, p2, zdir):
    x = p2 - p1
    L = float(np.linalg.norm(x))
    ex = x / L
    z = np.asarray(zdir, float)
    z = z - np.dot(z, ex) * ex
    if np.linalg.norm(z) < 1e-9:
        # запасной вариант
        z = np.array([0.0, 0.0, 1.0]) if abs(ex[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        z = z - np.dot(z, ex) * ex
    ez = z / np.linalg.norm(z)
    ey = np.cross(ez, ex)
    R = np.vstack([ex, ey, ez])       # строки — локальные оси
    T = np.zeros((12, 12))
    for k in range(4):
        T[3 * k:3 * k + 3, 3 * k:3 * k + 3] = R
    return T, L


def k_local(L, A, Iy, Iz, J):
    """Локальная матрица жёсткости. Iy — изгиб в плоскости x–z (ось h), Iz — в плоскости x–y."""
    k = np.zeros((12, 12))
    EA = E * A / L
    GJ = G * J / L
    k[0, 0] = k[6, 6] = EA
    k[0, 6] = k[6, 0] = -EA
    k[3, 3] = k[9, 9] = GJ
    k[3, 9] = k[9, 3] = -GJ
    # изгиб в плоскости x–y (перемещение v, поворот θz), инерция Iz
    a = E * Iz
    idx = [1, 5, 7, 11]
    kb = np.array([[12, 6 * L, -12, 6 * L],
                   [6 * L, 4 * L * L, -6 * L, 2 * L * L],
                   [-12, -6 * L, 12, -6 * L],
                   [6 * L, 2 * L * L, -6 * L, 4 * L * L]]) * a / L ** 3
    for i in range(4):
        for j in range(4):
            k[idx[i], idx[j]] += kb[i, j]
    # изгиб в плоскости x–z (перемещение w, поворот θy), инерция Iy
    a = E * Iy
    idx = [2, 4, 8, 10]
    kb = np.array([[12, -6 * L, -12, -6 * L],
                   [-6 * L, 4 * L * L, 6 * L, 2 * L * L],
                   [-12, 6 * L, 12, 6 * L],
                   [-6 * L, 2 * L * L, 6 * L, 4 * L * L]]) * a / L ** 3
    for i in range(4):
        for j in range(4):
            k[idx[i], idx[j]] += kb[i, j]
    return k


def kg_local(L, N):
    """Геометрическая матрица (N>0 — растяжение)."""
    k = np.zeros((12, 12))
    c = N / (30 * L)
    kb = np.array([[36, 3 * L, -36, 3 * L],
                   [3 * L, 4 * L * L, -3 * L, -L * L],
                   [-36, -3 * L, 36, -3 * L],
                   [3 * L, -L * L, -3 * L, 4 * L * L]]) * c
    idx = [1, 5, 7, 11]
    for i in range(4):
        for j in range(4):
            k[idx[i], idx[j]] += kb[i, j]
    kb2 = np.array([[36, -3 * L, -36, -3 * L],
                    [-3 * L, 4 * L * L, 3 * L, -L * L],
                    [-36, 3 * L, 36, 3 * L],
                    [-3 * L, -L * L, 3 * L, 4 * L * L]]) * c
    idx = [2, 4, 8, 10]
    for i in range(4):
        for j in range(4):
            k[idx[i], idx[j]] += kb2[i, j]
    return k


def fixed_end_local(L, q):
    """Узловые силы от равномерной нагрузки q (локальные компоненты [qx,qy,qz], Н/м)."""
    qx, qy, qz = q
    f = np.zeros(12)
    f[0] = f[6] = qx * L / 2
    f[1] = f[7] = qy * L / 2
    f[5] = qy * L * L / 12
    f[11] = -qy * L * L / 12
    f[2] = f[8] = qz * L / 2
    f[4] = -qz * L * L / 12
    f[10] = qz * L * L / 12
    return f


class Solver:
    def __init__(self, model: Model):
        self.m = model
        for e in model.elems:
            e.T, e.L = _transform(model.nodes[e.n1], model.nodes[e.n2], e.zdir)
        self._assemble_K()

    def _dofs(self, e):
        return np.r_[6 * e.n1:6 * e.n1 + 6, 6 * e.n2:6 * e.n2 + 6]

    def _assemble_K(self):
        m = self.m
        rows, cols, vals = [], [], []
        self.kloc = []
        for e in m.elems:
            s = e.sec
            kl = k_local(e.L, s.A, s.Iy, s.Iz, s.J)
            self.kloc.append(kl)
            kg = e.T.T @ kl @ e.T
            d = self._dofs(e)
            rows.append(np.repeat(d, 12))
            cols.append(np.tile(d, 12))
            vals.append(kg.ravel())
        n = m.ndof
        K = sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                          shape=(n, n)).tocsr()
        # опоры: пружины / жёсткие закрепления
        fixed = []
        diag = np.zeros(n)
        for node, ks in m.springs.items():
            for i, kv in enumerate(ks):
                if kv is None:
                    fixed.append(6 * node + i)
                elif kv > 0:
                    diag[6 * node + i] += kv
        K = K + sp.diags(diag)
        self.fixed = np.array(sorted(fixed), dtype=int)
        free = np.ones(n, bool)
        free[self.fixed] = False
        # узлы без элементов (не должно быть) — защита от вырожденности
        self.free = np.where(free)[0]
        self.K = K
        self.Kff = K[self.free][:, self.free].tocsc()
        self.lu = spla.splu(self.Kff)

    def solve(self, elem_loads: dict, nodal: dict | None = None):
        """elem_loads: {elem_index: global q (3,) Н/м}; nodal: {node: (6,) Н}.

        Возвращает (u, end_forces_local[list of 12], q_local[list])."""
        m = self.m
        F = np.zeros(m.ndof)
        q_loc_all = [None] * len(m.elems)
        for ei, qg in elem_loads.items():
            e = m.elems[ei]
            R = e.T[:3, :3]
            ql = R @ np.asarray(qg)
            q_loc_all[ei] = ql
            fl = fixed_end_local(e.L, ql)
            F[self._dofs(e)] += e.T.T @ fl
        if nodal:
            for nd, f in nodal.items():
                F[6 * nd:6 * nd + 6] += f
        u = np.zeros(m.ndof)
        u[self.free] = self.lu.solve(F[self.free])
        ends = []
        for ei, e in enumerate(m.elems):
            ul = e.T @ u[self._dofs(e)]
            fl = self.kloc[ei] @ ul
            if q_loc_all[ei] is not None:
                fl = fl - fixed_end_local(e.L, q_loc_all[ei])
            ends.append(fl)
        return u, ends, q_loc_all

    def reactions(self, u, elem_loads, nodal=None):
        m = self.m
        F = np.zeros(m.ndof)
        for ei, qg in elem_loads.items():
            e = m.elems[ei]
            ql = e.T[:3, :3] @ np.asarray(qg)
            F[self._dofs(e)] += e.T.T @ fixed_end_local(e.L, ql)
        if nodal:
            for nd, f in nodal.items():
                F[6 * nd:6 * nd + 6] += f
        Ku = self.K @ u
        R = Ku - F
        # для пружин реакция = k·u (уже учтена в K)
        return R

    def KG(self, ends):
        m = self.m
        rows, cols, vals = [], [], []
        for ei, e in enumerate(m.elems):
            N = -ends[ei][0]  # усилие на конце 1: сила на узел; N(растяжение) = −f0
            kgl = kg_local(e.L, N)
            kg = e.T.T @ kgl @ e.T
            d = self._dofs(e)
            rows.append(np.repeat(d, 12))
            cols.append(np.tile(d, 12))
            vals.append(kg.ravel())
        n = m.ndof
        return sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                             shape=(n, n)).tocsr()

    def buckling(self, ends, nmodes=8):
        """Наименьшие коэффициенты критической нагрузки α_cr и формы."""
        KG = self.KG(ends)
        B = (-KG)[self.free][:, self.free].tocsc()
        # K φ = λ B φ  ->  B φ = μ K φ, μ = 1/λ; ищем наибольшие μ
        Kinv = spla.LinearOperator(self.Kff.shape, matvec=self.lu.solve, dtype=float)
        try:
            vals, vecs = spla.eigsh(B, k=nmodes, M=self.Kff, Minv=Kinv, which="LA",
                                    tol=1e-6, maxiter=5000)
        except spla.ArpackNoConvergence as ex:
            vals, vecs = ex.eigenvalues, ex.eigenvectors
        order = np.argsort(-vals)
        out = []
        for i in order:
            mu = vals[i]
            if mu <= 1e-12:
                continue
            phi = np.zeros(self.m.ndof)
            phi[self.free] = vecs[:, i]
            out.append((1.0 / mu, phi))
        return out, KG


def member_forces_along(e: Elem, fl, ql, nst=5):
    """Внутренние усилия в nst точках по длине элемента (локальные оси).

    Возвращает массив [x, N, Vy, Vz, T, My, Mz] (N>0 растяжение)."""
    L = e.L
    qx, qy, qz = (ql if ql is not None else (0.0, 0.0, 0.0))
    res = []
    for s in np.linspace(0, L, nst):
        # равновесие отрезка [0,s]: внутренние силы = −(силы на конце 1 + нагрузка)
        N = -(fl[0] + qx * s)
        Vy = fl[1] + qy * s
        Vz = fl[2] + qz * s
        T = -fl[3]
        # моменты (знак не важен — используются по модулю)
        Mz = -fl[5] + fl[1] * s + qy * s * s / 2
        My = -fl[4] - fl[2] * s - qz * s * s / 2
        res.append((s, N, Vy, Vz, T, My, Mz))
    return np.array(res)
