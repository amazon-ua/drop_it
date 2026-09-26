"""Перебор схем каркаса с подбором сечений; результаты — output/opt_results.json."""
from __future__ import annotations

import itertools
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import checks as C
import costs as K
import model as M
import optimize as O
from baseline import baseline_scheme
from sections import load_price_list

OUT = Path(__file__).resolve().parent.parent / "output"
OUT.mkdir(exist_ok=True)

SECS_ALL = load_price_list()
# «спеццены»: позиции существенно дешевле рынка (< 50 грн/кг) — проверяем отдельно
SECS_NORMAL = [s for s in SECS_ALL if s.price / s.mass >= 50.0]


def calibration():
    base = baseline_scheme()
    an = C.Analysis(base, M.Loads()).run_all()
    return K.Calibration(K.quantities(an.model, base))


def scheme_space():
    out = []
    common = dict(knee_z=2.30, knee_dx=0.70, embed=0.70, base="spring")
    for web, knee, top, rx, zb in itertools.product(("K", "KS"), (True, False), (True, False),
                                                    (True, False), (2.10,)):
        out.append(dict(frames=3, web=web, knee_t=knee, side_top=top, roof_x=rx, side_zb=zb, **common))
    for web, knee, (eb, kl), rx in itertools.product(("K", "KS"), (True, False),
                                                     ((False, False), (True, False), (True, True)),
                                                     (True, False)):
        out.append(dict(frames=2, web=web, knee_t=knee, eave_beam=eb, knee_l=kl, roof_x=rx, **common))
    return out


def label(p):
    if p["frames"] == 3:
        s = "3 рамы (средняя на боковых фермах)"
        s += ", верхн. пояс" if p.get("side_top") else ", без верхн. пояса"
        s += f", низ. пояс +{p.get('side_zb', 2.1):.2f}"
    else:
        s = "2 рамы (только по колоннам)"
        if p.get("eave_beam"):
            s += ", обвязка" + (" + прод. подкосы" if p.get("knee_l") else "")
    s += ", подвеска" if p["web"] == "K" else ", подвеска + подкосы фермы"
    s += ", попер. подкосы" if p["knee_t"] else ", без попер. подкосов"
    s += ", связи по скатам" if p["roof_x"] else ", без связей"
    return s


LOADS = {"all": M.Loads(), "normal": M.Loads(), "ch07": M.Loads(Ch=0.70),
         "normal07": M.Loads(Ch=0.70)}
NORMAL_MODES = ("normal", "normal07")


def run_one(args):
    p, price_mode = args
    secs = SECS_NORMAL if price_mode in NORMAL_MODES else SECS_ALL
    cal = calibration()
    sc = M.Scheme(name=label(p), **p)
    sc.groups = O.default_groups(sc, secs)
    t = time.time()
    try:
        res = O.size_scheme(sc, LOADS[price_mode], secs, cal)
    except Exception as ex:  # noqa: BLE001
        return dict(params=p, label=label(p), price_mode=price_mode, error=repr(ex))
    if res is None:
        return dict(params=p, label=label(p), price_mode=price_mode, error="не найдено допустимое решение")
    sc2, an, est, q = res
    gu = an.group_util()
    return dict(params=p, label=label(p), price_mode=price_mode, total=est["total"],
                frame_part=est["frame_part"], pipes=est["pipes"], mass=q["mass"],
                groups={g: s.name for g, s in sc2.groups.items()},
                util={g: [round(u, 3), gov] for g, (u, gov) in gu.items()},
                n_cuts=q["n_cuts"], weld_len=q["weld_len"], area=q["area"],
                alpha_min=min(v for v in an.alpha.values() if v), secs=round(time.time() - t, 1))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    space = scheme_space()
    if mode in ("normal", "ch07"):
        # без «спеццен» / для местности II считаем 4 лучшие схемы основного перебора
        prev = json.loads((OUT / "opt_results_all.json").read_text())
        space = [r["params"] for r in prev if "total" in r][:4]
    jobs = [(p, mode) for p in space]
    t0 = time.time()
    results = []
    with Pool(4) as pool:
        for i, r in enumerate(pool.imap_unordered(run_one, jobs)):
            results.append(r)
            tot = r.get("total")
            print(f"[{i+1}/{len(jobs)}] {r['label']}: "
                  + (f"{tot:,.0f} грн, металл {r['pipes']:,.0f}, {r['mass']:.0f} кг" if tot else r.get("error")),
                  flush=True)
    results.sort(key=lambda r: r.get("total", 1e12))
    (OUT / f"opt_results_{mode}.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"готово за {time.time()-t0:.0f} с")
