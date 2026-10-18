import sys, json
ROOT = __import__('pathlib').Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'calc'))
import numpy as np
import model as M, checks as C, fem
from report_data import scheme_from_result
fd = json.load(open(ROOT / 'output' / 'final_design.json'))
x = dict(fd); x['params'] = dict(x['params'], side_panel=True)
sc = scheme_from_result(x)
a = C.Analysis(sc, M.Loads(Ch=0.7)).run_all()
m = a.model
u, ends, ql, forces = a.env['D+S+0.9W+x']
pts = []
for mid, mm in m.members.items():
    if mm['group'] == 'raf' and mm.get('frame') == 0.0 and min(mm['p1'][0], mm['p2'][0]) > 3.0 and max(mm['p1'][0], mm['p2'][0]) <= M.SPAN + 1e-6:
        for ei in mm['elems']:
            e = m.elems[ei]
            p1 = np.array(m.nodes[e.n1]); p2 = np.array(m.nodes[e.n2])
            arr = fem.member_forces_along(e, ends[ei], ql[ei] if ql is not None else None, nst=11)
            for r in arr:
                xx = p1[0] + (p2[0] - p1[0]) * r[0] / e.L
                pts.append((round(M.SPAN - xx, 3), round(r[1] / 1e3, 1), round(max(abs(r[5]), abs(r[6])) / 1e3, 2)))
pts = sorted(set(pts))
for d in (0.0, 0.07, 0.15, 0.25, 0.30, 0.40, 0.6, 0.8, 1.0, 1.3, 1.6, 1.73):
    q = min(pts, key=lambda t: abs(t[0] - d))
    print(f'от оси колонны {q[0]:.2f} м: N {q[1]} кН, M {q[2]} кНм')
