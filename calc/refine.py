"""Доводка лучших схем: повторный жадный поиск с большим лимитом расчётов."""
import json
import sys
from multiprocessing import Pool

import model as M
import optimize as O
from report_data import scheme_from_result
from run_opt import LOADS, NORMAL_MODES, OUT, SECS_ALL, SECS_NORMAL, calibration


def work(args):
    r, mode = args
    secs = SECS_NORMAL if mode in NORMAL_MODES else SECS_ALL
    loads = LOADS[mode]
    sc = scheme_from_result(r)
    res = O.size_scheme(sc, loads, secs, calibration(), max_greedy=160)
    sc2, an, est, q = res
    gu = an.group_util()
    out = dict(r)
    out.update(total=est["total"], frame_part=est["frame_part"], pipes=est["pipes"], mass=q["mass"],
               groups={g: s.name for g, s in sc2.groups.items()},
               util={g: [round(u, 3), gov] for g, (u, gov) in gu.items()},
               n_cuts=q["n_cuts"], weld_len=q["weld_len"], area=q["area"], refined=True)
    return out


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    path = OUT / f"opt_results_{mode}.json"
    res = json.loads(path.read_text())
    top = [r for r in res if "total" in r][:n]
    with Pool(4) as p:
        new = p.map(work, [(r, mode) for r in top])
    for r_old, r_new in zip(top, new):
        print(f"{r_old['label']}: {r_old['total']:,.0f} → {r_new['total']:,.0f}")
    keep = {json.dumps(r["params"], sort_keys=True): r for r in res}
    for r in new:
        k = json.dumps(r["params"], sort_keys=True)
        keep[k] = r   # после пересчёта с уточнёнными проверками берём новый результат
    allr = sorted(keep.values(), key=lambda r: r.get("total", 1e12))
    path.write_text(json.dumps(allr, ensure_ascii=False, indent=1))
