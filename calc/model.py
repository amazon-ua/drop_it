"""Геометрия навеса, схемы каркаса и нагрузки.

Оси: x — поперёк (ось левого ряда колонн x=0, правого x=5.45),
     y — вдоль конька (рама 1 со стороны дороги y=0, рама 3 y=4.60),
     z — вверх, 0 = верх щебня у левой опоры ворот.
Неизменяемое по условию: уклон 12°, положение и число опор (4 колонны),
кровля (металлочерепица, волна/шаг обрешётки 350 мм), размеры в плане,
коридор проезда 4.00 × 2.90 м (x = 0.40…4.40).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np

from fem import Elem, Model

# ---------------- неизменяемая геометрия ----------------
SPAN = 5.45
BAY = 4.60                  # расстояние между рядами рам с колоннами (рама 1 — рама 3)
# Площадка — параллелограмм: ряды колонн, конёк и карнизы параллельны боковым сторонам,
# рамы и передняя/задняя кромки кровли — передней кромке площадки (косина 2.87°).
# Модель строится в «логических» прямоугольных координатах и сдвигается: y_физ = y + x·tg(SKEW).
# Пролёт 5.45 принят по перпендикуляру между рядами (в плоскости рамы 5.457 — в запас).
SKEW = math.radians(2.87)
SLOPE = math.radians(12.0)
TAN, COS, SIN = math.tan(SLOPE), math.cos(SLOPE), math.sin(SLOPE)
OVH_L, OVH_R = 0.40, 0.90    # свесы поперёк (гориз. от осей колонн)
Y_MIN, Y_MAX = -1.18, BAY + 1.20   # кромки кровли вдоль конька (6.98 м)
X_RIDGE = SPAN / 2
Z_NODE = 3.10               # пересечение осей стропила и колонны
Z_TIE = 3.00                # ось затяжки / обвязки (низ ≥ 2.95 > 2.90)
Z_BASE = -0.08              # верх бетона (заделка колонны), среднее — для справки
# Фактические отметки по разбивке черновика (таблица «Привязка колонн к фактическому рельефу»):
# площадка не выравнивается, верх бетона у левых лунок на 2 см выше земли, у правых — в уровень щебня.
# Ключ — (x, y) оси колонны: x = 0 левый ряд (Л), x = SPAN правый (П); y = 0 рама 1, y = BAY рама 3.
COLUMN_BASES = {
    # (x, y): (имя, верх бетона, глубина бетона, земля)
    (0.0, 0.0): ("Л1", -0.06, 1.20, -0.08),
    (5.45, 0.0): ("П1", -0.09, 1.30, -0.21),
    (0.0, 4.60): ("Л3", -0.25, 1.20, -0.27),
    (5.45, 4.60): ("П3", -0.27, 1.35, -0.45),
}
Z_COL_TOP = 3.043           # верх колонны под опорной пластиной (низ стропила −6 мм) по оси колонны


def z_base(x, y):
    return COLUMN_BASES[(round(x, 2), round(y, 2))][1]


def column_name(x, y):
    return COLUMN_BASES[(round(x, 2), round(y, 2))][0]
CORRIDOR_X = (0.40, 4.40)
CORRIDOR_H = 2.90
LATH_PITCH = 0.35
EMBED_DRAFT = 1.25          # заделка колонны в бетон в черновике, м (1.20–1.35)


def z_rafter(x: float) -> float:
    return Z_NODE + TAN * (x if x <= X_RIDGE else SPAN - x)


def slope_len_left():
    return (OVH_L + X_RIDGE) / COS


def slope_len_right():
    return (OVH_R + X_RIDGE) / COS


def lath_rows():
    """Ряды обрешётки: список (x, z, trib_slope, side). side: 'L','R','ridge'."""
    rows = []
    for side, Ls in (("L", slope_len_left()), ("R", slope_len_right())):
        s_list = [0.0125]
        s = 0.2925
        while s <= Ls - 0.03:
            s_list.append(s)
            s += LATH_PITCH
        for s in s_list:
            x_h = s * COS  # гориз. от карниза
            x = -OVH_L + x_h if side == "L" else SPAN + OVH_R - x_h
            rows.append([x, z_rafter(x), s, side])
    # ряд у конька
    rows.append([X_RIDGE, z_rafter(X_RIDGE), None, "ridge"])
    # грузовые ширины по скату
    out = []
    for side, Ls in (("L", slope_len_left()), ("R", slope_len_right())):
        ss = sorted(r[2] for r in rows if r[3] == side) + [Ls]
        for i, s in enumerate(ss[:-1]):
            lo = 0.0 - 0.045 if i == 0 else (ss[i - 1] + s) / 2   # свес листа 45 мм
            hi = (s + ss[i + 1]) / 2 if i + 1 < len(ss) - 1 else (s + Ls) / 2
            x = [r for r in rows if r[3] == side and abs(r[2] - s) < 1e-9][0]
            out.append((x[0], x[1], hi - lo, side))
    # конёк: по половине последнего шага с каждой стороны
    trib_r = 0.0
    for side, Ls in (("L", slope_len_left()), ("R", slope_len_right())):
        last = max(r[2] for r in rows if r[3] == side)
        trib_r += (Ls - last) / 2
    out.append((X_RIDGE, z_rafter(X_RIDGE), trib_r, "ridge"))
    return sorted(out, key=lambda r: r[0])


# ---------------- цеховая боковая ферма ----------------
def shop_truss_geom(col_b, Hb, Hd, zb=2.10, plate_top=2.930, plate_t=0.008):
    """Геометрия цеховой Λ-фермы (размеры в м, y — от оси стойки средней рамы к колонне со знаком «−»).

    Нижний пояс (высота Hb, ось zb) — между гранями колонн. Раскос (высота Hd) нижним торцом лежит на
    верхней грани пояса (горизонтальный рез) и упирается в грань колонны; верхним торцом (тоже
    горизонтальный рез) приварен снизу к опорному столику; нижние грани двух раскосов сходятся
    под осью стойки. Возвращает угол раскоса, отметки пересечения осей и длины."""
    z_ct = zb + Hb / 2                    # верх пояса
    z_pb = plate_top - plate_t            # низ столика
    y_face = -(BAY / 2 - col_b / 2)       # грань колонны
    a = math.atan2(z_pb - z_ct, -y_face)
    for _ in range(50):
        foot = Hd / math.sin(a)           # длина опирания раскоса на пояс / под столиком
        y1 = y_face + foot                # точка, где нижняя грань раскоса выходит на верх пояса
        a = math.atan2(z_pb - z_ct, -y1)
    foot = Hd / math.sin(a)
    y1 = y_face + foot
    off = Hd / 2 / math.cos(a)            # от нижней грани до оси по вертикали
    t = math.tan(a)
    z_axis = lambda y: z_ct + (y - y1) * t + off
    # заготовка раскоса: оба торца — горизонтальные резы; длина по грани 0…y1, по оси —
    # от нижнего угла у колонны до верхнего угла у столика
    L_edge = (0.0 - y1) / math.cos(a)
    L_upper = (0.0 - y_face) * math.cos(a) + (z_pb - z_ct) * math.sin(a)
    return dict(alpha=a, foot=foot, y_face=y_face, y1=y1, z_ct=z_ct, z_pb=z_pb,
                apex_z=z_axis(0.0), z_axis_face=z_axis(y_face), z_axis_col=z_axis(-BAY / 2),
                L_cut=L_upper, L_edge=L_edge, plate_len=2 * foot + 0.03, plate_top=plate_top, plate_t=plate_t)


# ---------------- параметры схемы ----------------
@dataclass
class Scheme:
    name: str = "custom"
    frames: int = 3                  # 3 — как в черновике (средняя рама на боковых фермах), 2 — только по колоннам
    web: str = "KS"                  # 'K' — подвеска; 'KS' — подвеска + 2 подкоса к стропилам; 'N' — только затяжка
    strut_dx: float = 1.0            # подкосы фермы: точка на стропиле, м от конька по горизонтали
    knee_t: bool = True              # поперечные подкосы колонна→затяжка
    knee_z: float = 2.10             # отметка подкоса на колонне
    knee_dx: float = 0.90            # точка на затяжке от оси колонны
    side_zb: float = 2.10            # 3 рамы: нижний пояс боковой фермы
    side_top: bool = True            # 3 рамы: верхний пояс боковой фермы (обвязка) +3.00
    eave_beam: bool = False          # 2 рамы: продольная обвязка по оголовкам колонн
    knee_l: bool = False             # 2 рамы: продольные подкосы колонна→обвязка
    knee_l_dy: float = 1.0
    roof_x: bool = True              # связи-кресты по скатам
    base: str = "spring"             # 'spring' — упругая заделка в лунке, 'pin' — шарнир
    embed: float = 1.25              # заделка колонны в бетон, м
    skew: float = SKEW               # косина площадки (0 — прямоугольник)
    edge_d: float = 0.25             # 5 ферм: крайние фермы — на столько внутрь от кромок кровли, м
    edge_groups: bool = True         # 5 ферм: у крайних ферм свои (облегчённые) сечения
    spr_zb: float = 2.10             # 5 ферм: нижний узел шпренгеля под продольной балкой
    gable_edge: bool = False         # торцевая обвязка под обрешётинами у передней и задней кромки
    ge_d: float = 0.175              # отступ обвязки от кромки кровли, м
    ge_knee: bool = True             # подкосы обвязки от колонн (в плоскости рядов колонн)
    lath_strut: bool = False         # нижние подкосы консолей обрешётин (к низу стропила крайней рамы)
    ls_dz: float = 0.12              # глубина: от оси обрешётины до низа стропила, м
    gable_diag: bool = False        # диагонали по скатам: конёк крайней рамы → дальний угол обрешётки
    gd_knee: bool = False            # подкосы диагоналей от колонн (в плоскости рядов колонн)
    apex_z: float | None = None      # 3 рамы: цеховая боковая ферма — отметка пересечения осей раскосов
                                     # под опорным столиком (None — раскосы сходятся на оси затяжки)
    ridge_row_group: str = "lath"
    groups: dict = field(default_factory=dict)   # группа -> Section

    def copy(self, **kw):
        return replace(self, groups=dict(self.groups), **kw)


GROUP_INFO = {
    # группа: (описание, тип для проверки)
    "col": ("Колонны", "main"),
    "raf": ("Стропила", "main"),
    "tie": ("Затяжки", "main"),
    "kp": ("Подвеска (стойка у конька)", "web"),
    "strut": ("Подкосы фермы", "web"),
    "knee": ("Подкосы колонна→затяжка", "web"),
    "lath": ("Обрешётка", "beam"),
    "ge": ("Торцевая обвязка обрешётки", "beam"),
    "gk": ("Подкосы торцевой обвязки", "web"),
    "gd": ("Диагонали по скатам к углам обрешётки", "beam"),
    "ls": ("Нижние подкосы консолей обрешётки", "web"),
    "lk": ("Жёсткая вставка (обрешётина — низ стропила)", "main"),
    "sd": ("Раскосы боковой фермы", "web"),
    "sb": ("Нижний пояс боковой фермы", "main"),
    "st": ("Верхний пояс боковой фермы / обвязка", "main"),
    "stub": ("Стойка-вставка средней рамы", "main"),
    "eave": ("Продольная обвязка", "main"),
    "kl": ("Продольные подкосы", "web"),
    "xb": ("Связи по скатам", "brace"),
    "raf_e": ("Стропила крайних ферм", "main"),
    "tie_e": ("Затяжки крайних ферм", "main"),
    "kp_e": ("Подвеска крайних ферм", "web"),
    "strut_e": ("Подкосы крайних ферм", "web"),
    "lb": ("Продольная балка", "main"),
    "spd": ("Раскосы шпренгеля", "web"),
    "spp": ("Стойка шпренгеля", "web"),
}


class Builder:
    def __init__(self, sc: Scheme):
        self.sc = sc
        self.m = Model()
        self.m.skew_t = math.tan(sc.skew)
        self._member = 0
        self._piece = 0
        self.member_meta = {}
        self.piece_meta = {}

    def node(self, xyz):
        return self.m.add_node(xyz)

    def new_piece(self, group, **meta):
        self._piece += 1
        self.piece_meta[self._piece] = dict(group=group, **meta)
        return self._piece

    def add_member(self, pts, group, zdir, piece=None, nsub=1, **meta):
        """pts — узловые точки стержня (ломаная по прямой). Каждый участок между
        соседними точками делится на nsub конечных элементов."""
        self._member += 1
        mid = self._member
        if piece is None:
            piece = self.new_piece(group)
        L = 0.0
        eids = []
        for a, b in zip(pts[:-1], pts[1:]):
            a, b = np.asarray(a, float), np.asarray(b, float)
            for k in range(nsub):
                p1 = a + (b - a) * k / nsub
                p2 = a + (b - a) * (k + 1) / nsub
                n1, n2 = self.node(p1), self.node(p2)
                self.m.elems.append(Elem(n1, n2, group, np.asarray(zdir, float), mid, piece,
                                         sec=self.sc.groups[group]))
                eids.append(len(self.m.elems) - 1)
            L += float(np.linalg.norm(b - a))
        self.member_meta[mid] = dict(group=group, L=L, elems=eids,
                                     p1=np.asarray(pts[0], float), p2=np.asarray(pts[-1], float), **meta)
        return mid


def build(sc: Scheme):
    b = Builder(sc)
    rows = lath_rows()
    if sc.frames == 5:
        frames_y = [Y_MIN + sc.edge_d, 0.0, BAY / 2, BAY, Y_MAX - sc.edge_d]
    else:
        frames_y = [0.0, BAY / 2, BAY] if sc.frames == 3 else [0.0, BAY]
    col_y = [0.0, BAY]
    xcols = [0.0, SPAN]
    nlat = np.array([0, 1, 0])  # горизонтальная ось, перпендикулярная плоскости рамы

    frame_nodes = {}
    stub_piece = {}
    for fy in frames_y:
        mid_frame = fy not in col_y
        edge = sc.frames == 5 and fy not in (0.0, BAY / 2, BAY) and sc.edge_groups
        sfx = "_e" if edge else ""
        rafter_g = "raf" + sfx
        # --- стропила: разбивка по рядам обрешётки + узлы решётки
        xs = sorted(set([r[0] for r in rows] + [0.0, SPAN, X_RIDGE,
                                                 X_RIDGE - sc.strut_dx, X_RIDGE + sc.strut_dx]))
        xs = [x for x in xs if -OVH_L - 1e-9 <= x <= SPAN + OVH_R + 1e-9]
        if -OVH_L not in xs:
            xs = [-OVH_L] + xs
        if SPAN + OVH_R not in xs:
            xs.append(SPAN + OVH_R)
        left = [x for x in xs if x <= X_RIDGE + 1e-9]
        right = [x for x in xs if x >= X_RIDGE - 1e-9]
        # структурные точки стропила (границы проверяемых участков)
        key_l = [-OVH_L, 0.0, X_RIDGE - sc.strut_dx if sc.web == "KS" else None, X_RIDGE]
        key_r = [X_RIDGE, X_RIDGE + sc.strut_dx if sc.web == "KS" else None, SPAN, SPAN + OVH_R]
        for side, xl, keys in (("L", left, key_l), ("R", right, key_r)):
            keys = [k for k in keys if k is not None]
            piece = b.new_piece(rafter_g, frame=fy, side=side)
            for k1, k2 in zip(keys[:-1], keys[1:]):
                seg = [x for x in xl if k1 - 1e-9 <= x <= k2 + 1e-9]
                pts = [(x, fy, z_rafter(x)) for x in seg]
                zdir = np.array([-SIN, 0, COS]) if side == "L" else np.array([SIN, 0, COS])
                b.add_member(pts, rafter_g, zdir, piece=piece, kind="rafter", frame=fy,
                             overhang=(k1 < 0 or k2 > SPAN), nsub=1)
        # --- затяжка
        xt = [0.0, SPAN]
        if sc.web in ("K", "KS"):
            xt.append(X_RIDGE)
        if sc.knee_t:
            xt += [sc.knee_dx, SPAN - sc.knee_dx]
        xt = sorted(set(xt))
        tie_piece = b.new_piece("tie" + sfx, frame=fy)
        for x1, x2 in zip(xt[:-1], xt[1:]):
            b.add_member([(x1, fy, Z_TIE), (x2, fy, Z_TIE)], "tie" + sfx, (0, 0, 1), piece=tie_piece,
                         nsub=2, kind="tie", frame=fy)
        # связь затяжки с узлом стропила: короткая вставка колонны (у рам на колоннах —
        # сама колонна; у средней рамы — стойка-вставка)
        for xc in xcols:
            g = "stub" if mid_frame else "col"
            pc = b.new_piece(g, frame=fy) if mid_frame else None
            if mid_frame:
                stub_piece[xc] = pc
            b.add_member([(xc, fy, Z_TIE), (xc, fy, Z_NODE)], g, (1, 0, 0), piece=pc,
                         kind="col_head", frame=fy)
        # --- решётка фермы
        if sc.web in ("K", "KS"):
            b.add_member([(X_RIDGE, fy, Z_TIE), (X_RIDGE, fy, z_rafter(X_RIDGE))], "kp" + sfx, (1, 0, 0),
                         nsub=2, kind="kp", frame=fy)
        if sc.web == "KS":
            for xs_ in (X_RIDGE - sc.strut_dx, X_RIDGE + sc.strut_dx):
                b.add_member([(X_RIDGE, fy, Z_TIE), (xs_, fy, z_rafter(xs_))], "strut" + sfx, (0, 1, 0),
                             nsub=2, kind="strut", frame=fy)
        # --- поперечные подкосы колонна→затяжка (только у рам на колоннах)
        if sc.knee_t and not mid_frame:
            b.add_member([(0.0, fy, sc.knee_z), (sc.knee_dx, fy, Z_TIE)], "knee", (0, 1, 0),
                         nsub=2, kind="knee", frame=fy)
            b.add_member([(SPAN, fy, sc.knee_z), (SPAN - sc.knee_dx, fy, Z_TIE)], "knee", (0, 1, 0),
                         nsub=2, kind="knee", frame=fy)
        frame_nodes[fy] = True

    # --- колонны
    col_piece = {}
    for xc in xcols:
        for yc in col_y:
            zs = [z_base(xc, yc), Z_TIE]
            if sc.knee_t:
                zs.append(sc.knee_z)
            if sc.frames == 3:
                zs.append(sc.side_zb)
            if sc.frames == 2 and sc.knee_l:
                zs.append(sc.knee_z)
            zs = sorted(set(zs))
            pc = b.new_piece("col", x=xc, y=yc)
            col_piece[(xc, yc)] = pc
            for z1, z2 in zip(zs[:-1], zs[1:]):
                b.add_member([(xc, yc, z1), (xc, yc, z2)], "col", (1, 0, 0), piece=pc, nsub=2,
                             kind="col", x=xc, y=yc)
    # оголовки колонн (участок Z_TIE…Z_NODE) относим к той же детали
    for mid, mm in b.member_meta.items():
        if mm.get("kind") == "col_head" and mm["group"] == "col":
            pc = col_piece[(mm["p1"][0], mm["p1"][1])]
            for ei in mm["elems"]:
                b.m.elems[ei].piece = pc

    # --- боковые фермы (3 рамы)
    if sc.frames == 3:
        ym = BAY / 2
        for xc in xcols:
            apex = (xc, ym, Z_TIE)
            if sc.apex_z is not None:
                # цеховая ферма: раскосы сходятся под опорным столиком ниже затяжки;
                # стойка-вставка средней рамы стоит на столике (звено столик — затяжка)
                apex = (xc, ym, sc.apex_z)
                b.add_member([apex, (xc, ym, Z_TIE)], "stub", (1, 0, 0), piece=stub_piece[xc],
                             kind="stub_low")
            for yc in col_y:
                b.add_member([apex, (xc, yc, sc.side_zb)], "sd", (1, 0, 0), nsub=2, kind="sd")
            b.add_member([(xc, 0.0, sc.side_zb), (xc, BAY, sc.side_zb)], "sb", (0, 0, 1), nsub=4, kind="sb")
            if sc.side_top:
                pc = b.new_piece("st", x=xc)
                b.add_member([(xc, 0.0, Z_TIE), apex], "st", (0, 0, 1), piece=pc, nsub=2, kind="st")
                b.add_member([apex, (xc, BAY, Z_TIE)], "st", (0, 0, 1), piece=pc, nsub=2, kind="st")
    elif sc.frames == 5:
        # продольная балка по оголовкам колонн — от крайней фермы до крайней (консоли за колоннами)
        # + шпренгель под средним пролётом: раскосы от оголовков колонн вниз к узлу на spr_zb
        # и стойка от узла вверх к балке под средней фермой
        ym = BAY / 2
        for xc in xcols:
            pc = b.new_piece("lb", x=xc)
            for y1, y2 in zip(frames_y[:-1], frames_y[1:]):
                b.add_member([(xc, y1, Z_TIE), (xc, y2, Z_TIE)], "lb", (0, 0, 1), piece=pc, nsub=2, kind="lb")
            bot = (xc, ym, sc.spr_zb)
            for yc in col_y:
                b.add_member([(xc, yc, Z_TIE), bot], "spd", (1, 0, 0), nsub=2, kind="spd")
            b.add_member([bot, (xc, ym, Z_TIE)], "spp", (1, 0, 0), nsub=2, kind="spp")
    else:
        if sc.eave_beam:
            for xc in xcols:
                pts = [(xc, 0.0, Z_TIE)]
                if sc.knee_l:
                    pts += [(xc, sc.knee_l_dy, Z_TIE), (xc, BAY - sc.knee_l_dy, Z_TIE)]
                pts.append((xc, BAY, Z_TIE))
                pc = b.new_piece("eave", x=xc)
                for p1, p2 in zip(pts[:-1], pts[1:]):
                    b.add_member([p1, p2], "eave", (0, 0, 1), piece=pc, nsub=2, kind="eave")
                if sc.knee_l:
                    b.add_member([(xc, 0.0, sc.knee_z), (xc, sc.knee_l_dy, Z_TIE)], "kl", (1, 0, 0),
                                 nsub=2, kind="kl")
                    b.add_member([(xc, BAY, sc.knee_z), (xc, BAY - sc.knee_l_dy, Z_TIE)], "kl", (1, 0, 0),
                                 nsub=2, kind="kl")

    # --- связи по скатам: диагонали в плоскости ската от узла колонны одной рамы
    #     к коньку другой; привариваются к обрешётке в каждом пересечении
    braces = []
    if sc.roof_x:
        for x_e in (0.0, SPAN):
            braces.append(((x_e, 0.0), (X_RIDGE, BAY)))
            braces.append(((x_e, BAY), (X_RIDGE, 0.0)))

    # диагонали по скатам: от конька крайней рамы к дальнему углу обрешётки (передний и задний свес)
    diags = []
    if sc.gable_diag:
        x_eaves = (min(r[0] for r in rows), max(r[0] for r in rows))
        for yf, ye in ((0.0, Y_MIN), (BAY, Y_MAX)):
            for x_e in x_eaves:
                diags.append(((X_RIDGE, yf), (x_e, ye)))

    def brace_y_at(br, x):
        (x1, y1), (x2, y2) = br
        if min(x1, x2) - 1e-9 <= x <= max(x1, x2) + 1e-9 and abs(x2 - x1) > 1e-9:
            return y1 + (y2 - y1) * (x - x1) / (x2 - x1)
        return None

    # --- обрешётка (неразрезная по рамам, консоли на концах)
    ys = sorted(set([Y_MIN, Y_MAX] + frames_y))
    for (x, z, trib, side) in rows:
        g = "lath"
        zdir = np.array([-SIN, 0, COS]) if x < X_RIDGE - 1e-6 else (
            np.array([SIN, 0, COS]) if x > X_RIDGE + 1e-6 else np.array([0, 0, 1.0]))
        pc = b.new_piece(g, x=x)
        extra = [yb for br in braces + diags for yb in [brace_y_at(br, x)] if yb is not None]
        if sc.gable_edge:
            extra += [Y_MIN + sc.ge_d, Y_MAX - sc.ge_d]
        for y1, y2 in zip(ys[:-1], ys[1:]):
            cant = (y1 == Y_MIN or y2 == Y_MAX)
            pts_y = [y1] + sorted(y for y in extra if y1 + 1e-6 < y < y2 - 1e-6) + [y2]
            fine = [pts_y[0]]
            for a_, b_ in zip(pts_y[:-1], pts_y[1:]):
                n = max(1, int(math.ceil((b_ - a_) / 0.6)))
                fine += [a_ + (b_ - a_) * (k + 1) / n for k in range(n)]
            b.add_member([(x, y, z) for y in fine], g, zdir, piece=pc, nsub=1, kind="lath",
                         cant=cant, trib=trib, side=side, span=y2 - y1)
    if sc.lath_strut:
        # нижний подкос консоли каждой обрешётины: от конца консоли вниз к нижней плоскости стропила крайней рамы
        # (внахлёст к боковой грани стропила); в модели — до точки на глубине ls_dz под осью обрешётины и жёсткая
        # вставка к узлу стропила (пара сил «обрешётина сверху — подкос снизу» передаётся на стропило кручением)
        for (x, z, trib, side) in rows:
            zdir = np.array([-SIN, 0, COS]) if x < X_RIDGE - 1e-6 else (
                np.array([SIN, 0, COS]) if x > X_RIDGE + 1e-6 else np.array([0, 0, 1.0]))
            for yf, ye in ((0.0, Y_MIN), (BAY, Y_MAX)):
                bot = (x, yf, z - sc.ls_dz)
                b.add_member([(x, ye, z), bot], "ls", zdir, nsub=3, kind="ls")
                b.add_member([bot, (x, yf, z)], "lk", (1, 0, 0), nsub=1, kind="lk")
    if sc.gable_edge:
        # торцевая обвязка: поперечный стержень под обрешётинами, в ge_d от передней и задней кромки,
        # по скату от карниза до конька (прямая по скату); подкосы — от колонн в плоскости рядов колонн
        # к обвязке над рядом колонн
        for yy in (Y_MIN + sc.ge_d, Y_MAX - sc.ge_d):
            for left in (True, False):
                sl = sorted((x, z) for (x, z, trib, side) in rows
                            if (x <= X_RIDGE + 1e-6 if left else x >= X_RIDGE - 1e-6))
                if len(sl) < 2:
                    continue
                xc = 0.0 if left else SPAN
                zc = float(np.interp(xc, [p[0] for p in sl], [p[1] for p in sl]))
                pts = sorted(set([(x, yy, z) for x, z in sl] + ([(xc, yy, zc)] if sc.ge_knee else [])))
                zdir = np.array([-SIN, 0, COS]) if left else np.array([SIN, 0, COS])
                b.add_member(pts, "ge", zdir, piece=b.new_piece("ge", y=yy), nsub=1, kind="ge")
                if sc.ge_knee:
                    yc = 0.0 if yy < BAY / 2 else BAY
                    b.add_member([(xc, yc, sc.side_zb), (xc, yy, zc)], "gk", (1, 0, 0),
                                 piece=b.new_piece("gk", y=yc), nsub=2, kind="gk")
    for br in diags:
        (x1, y1), (x2, y2) = br
        xk = 0.0 if x2 < X_RIDGE else SPAN                    # над рядом колонн — точка подкоса
        xs_c = sorted(set([x1, x2] + [r[0] for r in rows if min(x1, x2) < r[0] < max(x1, x2)]
                          + ([xk] if sc.gd_knee else [])), reverse=x2 < x1)
        pts = [(x, brace_y_at(br, x), z_rafter(x)) for x in xs_c]
        zdir = np.array([-SIN, 0, COS]) if x2 < X_RIDGE else np.array([SIN, 0, COS])
        b.add_member(pts, "gd", zdir, piece=b.new_piece("gd"), nsub=1, kind="gd")
        if sc.gd_knee:
            yc = 0.0 if y1 < BAY / 2 else BAY
            b.add_member([(xk, yc, sc.side_zb), (xk, brace_y_at(br, xk), z_rafter(xk))], "gk", (1, 0, 0),
                         nsub=2, kind="gk")
    for br in braces:
        (x1, y1), (x2, y2) = br
        xs_c = sorted(set([x1, x2] + [r[0] for r in rows if min(x1, x2) < r[0] < max(x1, x2)]))
        if x1 > x2:
            xs_c = xs_c[::-1]
        pts = [(x, brace_y_at(br, x), z_rafter(x)) for x in xs_c]
        zdir = np.array([-SIN, 0, COS]) if min(x1, x2) < X_RIDGE - 1e-6 else np.array([SIN, 0, COS])
        pc = b.new_piece("xb")
        for p1, p2 in zip(pts[:-1], pts[1:]):
            b.add_member([p1, p2], "xb", zdir, piece=pc, nsub=1, kind="xb")

    # --- опоры
    m = b.m
    for xc in xcols:
        for yc in col_y:
            n = m.add_node((xc, yc, z_base(xc, yc)))
            if sc.base == "pin":
                m.springs[n] = [None, None, None, 0.0, 0.0, None]
            else:
                k_rot = base_rot_stiffness()
                m.springs[n] = [None, None, None, k_rot, k_rot, None]
    m.members = b.member_meta
    used = {e.piece for e in m.elems}
    m.pieces = {k: v for k, v in b.piece_meta.items() if k in used}
    m.scheme = sc
    m.rows = rows
    m.frames_y = frames_y
    return m


# ---------------- грунт / заделка ----------------
# hole_L — рабочая глубина бетона в грунте: у всех лунок ≈ 1.18 м (глубина бетона минус выступ над землёй / щебень)
SOIL = dict(phi=22.0, gamma=18e3, c=0.0, kh=10e6, hole_b=0.30, hole_L=1.18)


def base_rot_stiffness(b=None, L=None, kh=None):
    """Поворотная жёсткость бетонного столба в грунте (жёсткий короткий столб,
    коэффициент постели kh постоянный по глубине, поворот вокруг точки на 2/3 L)."""
    b = b or SOIL["hole_b"]
    L = L or SOIL["hole_L"]
    kh = kh or SOIL["kh"]
    # для жёсткого столба в однородном основании поворотная жёсткость у верха ≈ kh·b·L^3/12
    # (свободная точка вращения; берётся нижняя оценка)
    return kh * b * L ** 3 / 12


# ---------------- нагрузки ----------------
@dataclass
class Loads:
    """Нагрузки по ДБН В.1.2-2:2006 (зі змінами № 1, 2)."""
    S0: float = 1600.0          # Па, Харків, дод. Е
    gfm_snow: float = 1.00      # табл. 8.1, T = 50 років
    gfe_snow: float = 0.49      # табл. 8.3, η = 0.02 (масове будівництво)
    W0: float = 430.0           # Па, Харків, дод. Е
    gfm_wind: float = 1.00      # табл. 9.1, T = 50 років
    gfe_wind: float = 0.21      # табл. 9.3, η = 0.02
    Ch: float = 0.40            # табл. 9.01, z ≤ 5 м, тип місцевості III (приміська забудова)
    gn: float = 1.00            # ДБН В.1.2-14, клас наслідків СС1, перша група
    gn_sls: float = 0.95        # друга група
    gf_steel: float = 1.05      # табл. 5.1, металеві (зусилля від власної ваги < 50 %)
    gf_steel_fav: float = 0.95  # те саме, коли вага розвантажує
    g_roof: float = 50.0        # Па по скату: металочерепиця 0.45–0.5 мм + саморізи
    g_gutter: float = 30.0      # Н/м по карнизу: жолоб + кріплення
    weld_add: float = 1.03      # надбавка на зварні шви / фасонки до ваги сталі
    # схема 11 дод. И (навіси, тип I — двосхилий), α = 12° (інтерполяція 10°…20°)
    ce: tuple = (0.62, -1.04, -0.88, -0.08)
    cx_member: float = 2.0      # лобовий опір стрижнів прямокутного перерізу
    cf: float = 0.04            # тертя для хвилястого покриття (прим. 2 до схеми 11)
    psi2: float = 0.9           # ψt2, п. 4.18


def unit_cases(model, L: Loads):
    """Одиничні (характеристичні) завантаження: name -> {elem: q_global (Н/м)}."""
    m = model
    cases = {}
    cases["Dsteel"] = {ei: np.array([0.0, 0.0, -e.sec.mass * 9.81 * L.weld_add])
                       for ei, e in enumerate(m.elems)}
    D_roof, SL, SR = {}, {}, {}
    zones = {k: {} for k in ("L_out", "L_in", "R_in", "R_out")}
    nL = np.array([-SIN, 0, COS])
    nR = np.array([SIN, 0, COS])
    x_eave_L = -OVH_L + 0.0125 * COS
    x_eave_R = SPAN + OVH_R - 0.0125 * COS
    for mid, mm in m.members.items():
        if mm.get("kind") != "lath":
            continue
        trib, side = mm["trib"], mm["side"]
        x = mm["p1"][0]
        for ei in mm["elems"]:
            gr = L.g_roof * trib
            if abs(x - x_eave_L) < 1e-3 or abs(x - x_eave_R) < 1e-3:
                gr += L.g_gutter
            D_roof[ei] = np.array([0.0, 0.0, -gr])
            s_v = np.array([0.0, 0.0, -trib * COS])      # на 1 Па снігу (по плану)
            if side == "L":
                SL[ei] = s_v
            elif side == "R":
                SR[ei] = s_v
            else:
                SL[ei] = s_v / 2
                SR[ei] = s_v / 2
            # вітер: тиск 1 Па "вниз" (до поверхні) на зону
            if side == "ridge":
                zones["L_in"][ei] = -nL * trib / 2
                zones["R_in"][ei] = -nR * trib / 2
            else:
                Ls = slope_len_left() if side == "L" else slope_len_right()
                s = (x - (-OVH_L)) / COS if side == "L" else (SPAN + OVH_R - x) / COS
                zone = side + ("_out" if s < Ls / 2 else "_in")
                zones[zone][ei] = -(nL if side == "L" else nR) * trib
    cases["Droof"] = D_roof
    cases["SL"] = SL
    cases["SR"] = SR
    for k, v in zones.items():
        cases["W_" + k] = v
    # лобовий опір стрижнів (на 1 Па) поперек (+x) і вздовж (+y)
    Wx, Wy = {}, {}
    for ei, e in enumerate(m.elems):
        mm = m.members[e.member]
        if mm.get("kind") == "lath":
            continue
        p1, p2 = m.nodes[e.n1], m.nodes[e.n2]
        d = (p2 - p1) / np.linalg.norm(p2 - p1)
        for vec, store in ((np.array([1.0, 0, 0]), Wx), (np.array([0, 1.0, 0]), Wy)):
            perp = vec - np.dot(vec, d) * d
            if np.linalg.norm(perp) < 1e-6:
                continue
            # ширина проекції: грань, що перпендикулярна потоку
            width = e.sec.b if abs(np.dot(e.T[2, :3], vec)) > 0.7 else e.sec.h
            store[ei] = perp * L.cx_member * width
    # тертя по покрівлі (від площі горизонтальної проекції)
    area = (Y_MAX - Y_MIN) * (OVH_L + SPAN + OVH_R)
    tot_len = sum(mm["L"] for mm in m.members.values() if mm.get("kind") == "lath")
    for mid, mm in m.members.items():
        if mm.get("kind") != "lath":
            continue
        for ei in mm["elems"]:
            Wy[ei] = Wy.get(ei, np.zeros(3)) + np.array([0, L.cf * area / tot_len, 0])
            fx = np.array([L.cf * area / tot_len, 0, 0])
            Wx[ei] = Wx.get(ei, np.zeros(3)) + fx
    cases["Wx"] = Wx
    cases["Wy"] = Wy
    return cases


def combos(L: Loads):
    """Основні сполучення (п. 4.18): ψt1 = 1.0, ψt2 = 0.9. ULS — граничні, SLS — експлуатаційні."""
    Sm = L.S0 * L.gfm_snow
    wm = L.W0 * L.gfm_wind * L.Ch
    we = L.W0 * L.gfe_wind * L.Ch
    Se = L.S0 * L.gfe_snow
    c1, c2, c3, c4 = L.ce

    def D(fav=False):
        g = L.gf_steel_fav if fav else L.gf_steel
        return {"Dsteel": g, "Droof": g}

    def S(k=1.0, left=True, right=True):
        out = {}
        if left:
            out["SL"] = Sm * k
        if right:
            out["SR"] = Sm * k
        return out

    def W(direction, k=1.0, w=wm):
        # вітер зліва (+x): навітряний лівий схил: зовн. половина c1, внутр. c2;
        # підвітряний правий: внутр. c3, зовн. c4.  Справа — дзеркально.
        if direction == "+x":
            z = {"W_L_out": c1, "W_L_in": c2, "W_R_in": c3, "W_R_out": c4, "Wx": 1.0}
        elif direction == "-x":
            z = {"W_R_out": c1, "W_R_in": c2, "W_L_in": c3, "W_L_out": c4, "Wx": -1.0}
        elif direction == "+y":
            z = {"Wy": 1.0}
        else:
            z = {"Wy": -1.0}
        return {kk: v * w * k for kk, v in z.items()}

    def add(store, name, gn, *parts):
        c = {}
        for p in parts:
            for kk, v in p.items():
                c[kk] = c.get(kk, 0.0) + v
        store[name] = {kk: v * gn for kk, v in c.items()}

    uls = {}
    p = L.psi2
    add(uls, "D+S", L.gn, D(), S())
    add(uls, "D+S(лів.)", L.gn, D(), S(right=False))
    add(uls, "D+S(прав.)", L.gn, D(), S(left=False))
    for d in ("+x", "-x", "+y"):
        add(uls, f"D+S+0.9W{d}", L.gn, D(), S(), W(d, p))
        add(uls, f"D+0.9S+W{d}", L.gn, D(), S(p), W(d))
        add(uls, f"0.95D+W{d}", L.gn, D(fav=True), W(d))
    add(uls, "D+S(лів.)+0.9W-x", L.gn, D(), S(right=False), W("-x", p))
    add(uls, "D+S(прав.)+0.9W+x", L.gn, D(), S(left=False), W("+x", p))
    sls = {}
    D1 = {"Dsteel": 1.0, "Droof": 1.0}
    add(sls, "SLS D+Se", L.gn_sls, D1, {"SL": Se, "SR": Se})
    add(sls, "SLS D+Se(лів.)", L.gn_sls, D1, {"SL": Se})
    add(sls, "SLS D+Se+0.9We+x", L.gn_sls, D1, {"SL": Se, "SR": Se}, W("+x", p, we))
    add(sls, "SLS D+We+y", L.gn_sls, D1, W("+y", 1.0, we))
    add(sls, "SLS D+We+x", L.gn_sls, D1, W("+x", 1.0, we))
    return uls, sls
