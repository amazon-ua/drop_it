"""Окончательное решение: лучший вариант перебора + конструктивные корректировки узлов.

Корректировки (для узлов на фасонках все элементы в плоскости рамы — одной ширины 60 мм):
  * колонна 100×50×4 → 100×60×4: фасонки ложатся на колонну, стропило и затяжку в одной плоскости;
  * стойка-вставка средней рамы 70×70×2 → 60×60×3: ширина как у стропила и затяжки.
Результат — output/final_design.json, усилия в узлах — output/node_forces.json.
"""
from __future__ import annotations

import json
import math

import numpy as np

import checks as C
import costs as K
import model as M
from baseline import baseline_scheme
from report_data import scheme_from_result, sec_by_name
from run_opt import OUT

OVERRIDES = {"col": "100×60×4", "stub": "60×60×3"}


def node_forces(an, sc):
    """Огибающие усилий в стержнях, примыкающих к узлам А, Б, В."""
    m = an.model
    env = {}

    def upd(key, f):
        e = env.setdefault(key, dict(Nc=0.0, Nt=0.0, M=0.0, V=0.0))
        e["Nc"] = max(e["Nc"], -f["Nmin"])
        e["Nt"] = max(e["Nt"], f["Nmax"])
        e["M"] = max(e["M"], f["My"], f["Mz"])
        e["V"] = max(e["V"], f["Vy"], f["Vz"])

    def near(p, q):
        return np.linalg.norm(np.asarray(p) - np.asarray(q)) < 1e-6

    yb = M.BAY / 2
    for cname, (u, ends, ql, forces) in an.env.items():
        for mid, mm in m.members.items():
            k = mm.get("kind")
            f = forces[mid]
            p1, p2 = mm["p1"], mm["p2"]
            fy = mm.get("frame")
            for xc in (0.0, M.SPAN):          # оба ряда колонн
                # узел А: оголовки колонн крайних рам
                for yc in (0.0, M.BAY):
                    if k == "rafter" and fy == yc and (near(p1, (xc, yc, M.Z_NODE)) or near(p2, (xc, yc, M.Z_NODE))):
                        upd("A_стропило", f)
                    if k == "tie" and fy == yc and (near(p1, (xc, yc, M.Z_TIE)) or near(p2, (xc, yc, M.Z_TIE))):
                        upd("A_затяжка", f)
                    if k == "col_head" and fy == yc and near(p1, (xc, yc, M.Z_TIE)):
                        upd("A_колонна_оголовок", f)
                    if k == "col" and near(p2, (xc, yc, M.Z_TIE)):
                        upd("A_колонна_под_затяжкой", f)
                    # узел В: колонна на отметке нижнего пояса боковой фермы
                    if k == "sd" and near(p2, (xc, yc, sc.side_zb)):
                        upd("В_раскос_боковой_фермы", f)
                    if k == "sb" and (near(p1, (xc, yc, sc.side_zb)) or near(p2, (xc, yc, sc.side_zb))):
                        upd("В_нижний_пояс", f)
                    if k == "col" and near(p2, (xc, yc, sc.side_zb)):
                        upd("В_колонна_ниже", f)
                    if k == "col" and near(p1, (xc, yc, sc.side_zb)):
                        upd("В_колонна_выше", f)
                # узел Б: опора средней рамы
                if k == "rafter" and fy == yb and (near(p1, (xc, yb, M.Z_NODE)) or near(p2, (xc, yb, M.Z_NODE))):
                    upd("Б_стропило", f)
                if k == "tie" and fy == yb and (near(p1, (xc, yb, M.Z_TIE)) or near(p2, (xc, yb, M.Z_TIE))):
                    upd("Б_затяжка", f)
                if k == "col_head" and fy == yb and near(p1, (xc, yb, M.Z_TIE)):
                    upd("Б_стойка_вставка", f)
                if k == "sd" and near(p1, (xc, yb, M.Z_TIE)):
                    upd("Б_раскос_боковой_фермы", f)
    # узлы труба-к-грани из общего расчёта
    for key, jr in an.joint_results.items():
        name = f"узел_{jr['brace']}→{jr['chord']}"
        e = env.setdefault(name, dict(u=0.0))
        e["u"] = max(e.get("u", 0.0), jr["u"] * 1e3)   # ×1e3: общий делитель ниже
    return {k: {kk: round(vv / 1e3, 2) for kk, vv in v.items()} for k, v in env.items()}


def main():
    res = json.loads((OUT / "opt_results_normal07.json").read_text())
    r = dict(res[0])
    groups = dict(r["groups"])
    groups.update(OVERRIDES)
    r["groups"] = groups
    sc = scheme_from_result(r)
    base = baseline_scheme()
    an_b = C.Analysis(base, M.Loads()).run_all()
    cal = K.Calibration(K.quantities(an_b.model, base, stock_len=6.0))
    out = {}
    for tag, L in (("Ch0.40", M.Loads()), ("Ch0.70", M.Loads(Ch=0.70))):
        an = C.Analysis(sc, L).run_all()
        gu = an.group_util()
        out[tag] = {g: [round(u, 3), gov] for g, (u, gov) in gu.items()}
        print(tag, "max u =", round(max(v[0] for v in gu.values()), 3),
              {g: round(v[0], 3) for g, v in gu.items()})
        if tag == "Ch0.70":
            an_main = an
    q = K.quantities(an_main.model, sc)
    est = K.estimate(q, cal)
    r.update(total=est["total"], pipes=est["pipes"], mass=q["mass"], frame_part=est["frame_part"],
             util=out["Ch0.70"], util_ch04=out["Ch0.40"], overrides=OVERRIDES, refined=True,
             label=r["label"])
    (OUT / "final_design.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    nf = node_forces(an_main, sc)
    (OUT / "node_forces.json").write_text(json.dumps(nf, ensure_ascii=False, indent=1))
    print("итог", round(est["total"]), "трубы", round(est["pipes"]), "масса", round(q["mass"], 1))
    for k, v in nf.items():
        print(f"  {k:28} {v}")


if __name__ == "__main__":
    main()
