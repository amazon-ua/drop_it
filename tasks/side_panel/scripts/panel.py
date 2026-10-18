import sys, json
ROOT = __import__('pathlib').Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'calc'))
import model as M, checks as C
from report_data import scheme_from_result
fd = json.load(open(ROOT / 'output' / 'final_design.json'))
for sp in (False, True):
    x = dict(fd); x['params'] = dict(x['params'], side_panel=sp)
    sc = scheme_from_result(x)
    for L in (M.Loads(), M.Loads(Ch=0.7)):
        a = C.Analysis(sc, L).run_all()
        if sp and L.Ch == 0.4:
            cs = a.cases['Wpanel']
            tot = sum(v[0] * a.model.elems[ei].L for ei, v in cs.items())
            print('панель: сумма на 1 Па', round(tot, 2), 'м2 (ожидается ~', round(0.97 * 6.98, 2), ')')
        gu = a.group_util()
        fr = {str(k): round(float(v['u']), 2) for k, v in a.found_results.items()}
        jr = round(max(j['u'] for j in a.joint_results.values()), 2)
        print('панель' if sp else 'без   ', 'Ch', L.Ch, 'max', round(max(float(v[0]) for v in gu.values()), 3),
              {k: (round(float(v[0]), 3), v[1][:28]) for k, v in gu.items() if k in ('col', 'sb', 'sd', 'raf', 'stub', 'tie')},
              'лунки', fr, 'узлы', jr, flush=True)
