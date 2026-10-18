import sys, json
ROOT = __import__('pathlib').Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'calc'))
import model as M, checks as C
from report_data import scheme_from_result
fd = json.load(open(ROOT / 'output' / 'final_design.json'))
for sp in (False, True):
    x = dict(fd); x['params'] = dict(x['params'], side_panel=sp)
    sc = scheme_from_result(x)
    a = C.Analysis(sc, M.Loads(Ch=0.7)).run_all()
    m = a.model
    cn = 'D+S+0.9W+x'
    u, ends, ql, forces = a.env[cn]
    for mid, mm in m.members.items():
        k = mm.get('kind')
        if mm.get('frame') != 0.0: continue
        if (k == 'rafter' and min(mm['p1'][0], mm['p2'][0]) > 3.0) or (k in ('col',) and mm['p1'][0] > 5 and mm['p1'][1] == 0.0) or (k == 'tie' and max(mm['p1'][0], mm['p2'][0]) > 5.4):
            f = forces[mid]
            print('панель' if sp else 'без   ', k, [round(v, 2) for v in mm['p1']], '→', [round(v, 2) for v in mm['p2']],
                  'M', round(max(f['My'], f['Mz']) / 1e3, 2), 'Nсж', round(-f['Nmin'] / 1e3, 1), 'Nраст', round(f['Nmax'] / 1e3, 1))
    # горизонтальные реакции колонн
    print('  реакции H по лункам:', {k: round(v['H'] / 1e3, 2) for k, v in a.found_results.items()})
