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
    print('С ПОЛОСОЙ' if sp else 'БЕЗ ПОЛОСЫ')
    for mid, r in sorted(a.member_results.items(), key=lambda kv: (m.members[kv[0]]['p1'][0], m.members[kv[0]]['p1'][1], m.members[kv[0]]['p1'][2])):
        mm = m.members[mid]
        if mm['group'] != 'col': continue
        f = max(r['forces'].values(), key=lambda f: f['My'] + f['Mz'])
        print('  ', M.column_name(mm['p1'][0], mm['p1'][1]), f"z {mm['p1'][2]:+.2f}…{mm['p2'][2]:+.2f}", round(float(r['u']), 2), r['gov'][:34],
              {k[4:]: round(float(v), 2) for k, v in r.items() if k.startswith('chk_') and v > 0.05},
              'Mmax кНм', round(max(max(f['My'], f['Mz']) for f in r['forces'].values()) / 1e3, 2),
              'N кН', round(max(-f['Nmin'] for f in r['forces'].values()) / 1e3, 1))
