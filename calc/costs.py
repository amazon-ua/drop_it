"""Стоимость: металл по метражу из прайса, пластины, окраска, расходники, работа.

Статьи сметы (input/koshtorys_navis_onovlenyi.xlsx), которые зависят от каркаса,
пересчитываются пропорционально измерителям, откалиброванным на исходном
варианте (черновик 2026-ПР-480):
  * окраска (материал и работа) — площадь окрашиваемой поверхности;
  * сварочные расходники — длина сварных швов;
  * изготовление + монтаж + доп. работы — трудоёмкость (детали, резы, швы,
    стыковки обрешётки на рамах, масса).
Кровля, водосток, доставка и работы по ним — без изменений (вне оптимизации).
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

import model as M

STOCK_LEN = 6.0        # длина хлыста, м (продажа по метражу, но заготовки не длиннее хлыста)
CUT_ALLOW = 0.003      # пропил на рез, м
PLATE_PRICE = 55.0     # грн/кг (лист t=4…8; по черновику 9 кг ≈ 500 грн)

ESTIMATE = {
    # статья: (сумма по смете, грн, измеритель)
    "Арматура для лунок": (3000, "const"),
    "Бетон В20 для лунок": (8900, "const"),
    "Металлочерепица": (24750, "roof"),
    "Конёк": (2400, "roof"),
    "Торцевые планки": (3600, "roof"),
    "Саморезы и уплотнитель": (1200, "roof"),
    "Водосточная система": (18700, "roof"),
    "Грунт-эмаль (окраска)": (5500, "area"),
    "Сварочные расходники, круги, свёрла": (6600, "weld"),
    "Мелкий металл, непредвиденное": (1620, "const"),
    "Доставка": (6000, "roof"),
    "Работа: копка лунок": (7000, "const"),
    "Работа: армирование и бетонирование": (6000, "const"),
    "Работа: изготовление ферм и каркаса": (24000, "labor"),
    "Работа: окраска": (7000, "area"),
    "Работа: монтаж каркаса": (15000, "labor"),
    "Работа: монтаж кровли": (7000, "roof"),
    "Работа: водосток": (4000, "roof"),
    "Работа: доп. изготовление и монтаж": (7000, "labor"),
}
ESTIMATE_TOTAL = 239730   # итог сметы xlsx (материалы 162 730 + работа 77 000)
ESTIMATE_PIPES = 80460    # трубы по смете xlsx (24 м 100×100×5 + 90 м 60×40×3 + 228 м 40×40×2)


def quantities(model, sc):
    """Детали, длины, массы, площади, швы — по модели."""
    m = model
    piece_len = defaultdict(float)
    piece_sec = {}
    for e in m.elems:
        piece_len[e.piece] += e.L
        piece_sec[e.piece] = e.sec
    pieces = []
    for pid, L in piece_len.items():
        meta = m.pieces[pid]
        g = meta["group"]
        sec = piece_sec[pid]
        if g == "col":
            L += sc.embed
        pieces.append(dict(id=pid, group=g, sec=sec, L=L, meta=meta))
    # сварные соединения: концы деталей, примыкающие к другим деталям
    node_pieces = defaultdict(set)
    for e in m.elems:
        node_pieces[e.n1].add(e.piece)
        node_pieces[e.n2].add(e.piece)
    base_nodes = set(m.springs)
    weld_len = 0.0
    n_joints = 0
    n_cross = 0
    end_nodes = defaultdict(list)
    for e in m.elems:
        end_nodes[e.piece] += [e.n1, e.n2]
    for p in pieces:
        pid = p["id"]
        # концевые узлы детали = узлы, встречающиеся один раз в её элементах
        cnt = defaultdict(int)
        for n in end_nodes[pid]:
            cnt[n] += 1
        ends = [n for n, c in cnt.items() if c == 1]
        for n in ends:
            others = node_pieces[n] - {pid}
            if others:
                n_joints += 1
                weld_len += p["sec"].perim
            elif n in base_nodes:
                pass
        # пересечения (обрешётка по стропилам, связи по обрешётке): узлы внутри детали
        inner = [n for n, c in cnt.items() if c > 1]
        if p["group"] in ("lath", "xb"):
            for n in inner:
                if node_pieces[n] - {pid}:
                    n_cross += 1
                    weld_len += 0.08   # два прихваточных шва по 40 мм
    # стыки обрешётки и других длинных деталей (заготовка ≤ 6 м)
    n_splice = 0
    for p in pieces:
        k = max(1, math.ceil(p["L"] / STOCK_LEN - 1e-9))
        p["parts"] = k
        if k > 1:
            n_splice += k - 1
            weld_len += (k - 1) * p["sec"].perim
    n_cuts = sum(p["parts"] for p in pieces)
    # пластины: фасонки узлов на колоннах и опорах средней рамы, крышки колонн
    plate_kg = 0.0
    n_gusset_nodes = len(m.frames_y) * 2
    plate_kg += n_gusset_nodes * 2 * (0.20 * 0.22 * 0.005 * 7850)
    col = sc.groups["col"]
    plate_kg += 4 * ((col.b + 0.04) ** 2 * 0.006 * 7850 + (col.b + 0.01) ** 2 * 0.004 * 7850)
    weld_len += n_gusset_nodes * 1.2
    # площадь окраски (заделка — грунт, считаем 50 %)
    area = 0.0
    for p in pieces:
        Lp = p["L"]
        if p["group"] == "col":
            Lp = p["L"] - 0.5 * sc.embed
        area += p["sec"].perim * Lp
    area += plate_kg / 7850 / 0.005 * 2 * 0.5
    mass = sum(p["sec"].mass * p["L"] for p in pieces) + plate_kg
    return dict(pieces=pieces, weld_len=weld_len, n_joints=n_joints, n_cross=n_cross,
                n_splice=n_splice, n_cuts=n_cuts, plate_kg=plate_kg, area=area, mass=mass)


def labor_units(q):
    """Условная трудоёмкость изготовления и монтажа каркаса."""
    return (1.0 * q["n_cuts"]          # отрез, разметка, подача детали
            + 1.2 * q["n_joints"]      # сборка и прихватка стыка
            + 0.4 * q["n_cross"]       # приварка обрешётины к стропилу / связи к обрешётке
            + 1.0 * q["n_splice"]      # стык обрешётины на раме
            + 4.0 * q["weld_len"]      # обварка по контуру, м
            + 0.02 * q["mass"])        # подъём, кантовка, монтаж, кг


def metal_cost(q):
    by_sec = defaultdict(lambda: dict(L=0.0, n=0, kg=0.0, cost=0.0, groups=set()))
    for p in q["pieces"]:
        s = p["sec"]
        L = p["L"] + CUT_ALLOW * p["parts"]
        d = by_sec[s.name]
        d["L"] += L
        d["n"] += p["parts"]
        d["kg"] += L * s.mass
        d["cost"] += L * s.price
        d["groups"].add(p["group"])
        d["sec"] = s
    pipes = sum(d["cost"] for d in by_sec.values())
    return pipes, dict(by_sec)


class Calibration:
    """Коэффициенты пересчёта статей сметы, откалиброванные на исходном варианте."""

    def __init__(self, q_base):
        self.area0 = q_base["area"]
        self.weld0 = q_base["weld_len"]
        self.lab0 = labor_units(q_base)

    def paint_rate(self):
        """Окраска, грн за м² (материал + работа)."""
        return (ESTIMATE["Грунт-эмаль (окраска)"][0] + ESTIMATE["Работа: окраска"][0]) / self.area0


def estimate(q, cal: Calibration):
    pipes, by_sec = metal_cost(q)
    lines = []
    lines.append(("Профильные трубы (по метражу, прайс)", pipes, "metal"))
    lines.append(("Пластины (фасонки, крышки колонн)", q["plate_kg"] * PLATE_PRICE, "metal"))
    lu = labor_units(q)
    for name, (val, kind) in ESTIMATE.items():
        if kind == "const" or kind == "roof":
            v = val
        elif kind == "area":
            v = val * q["area"] / cal.area0
        elif kind == "weld":
            v = val * q["weld_len"] / cal.weld0
        elif kind == "labor":
            v = val * lu / cal.lab0
        lines.append((name, v, kind))
    total = sum(v for _, v, _ in lines)
    frame_part = sum(v for _, v, k in lines if k in ("metal", "area", "weld", "labor"))
    return dict(lines=lines, total=total, frame_part=frame_part, pipes=pipes, by_sec=by_sec,
                labor_units=lu)
