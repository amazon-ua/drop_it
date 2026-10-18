import sys, json
ROOT = __import__('pathlib').Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'calc'))
import model as M, checks as C
from report_data import scheme_from_result
fd = json.load(open(ROOT / 'output' / 'final_design.json'))
h, cant = float(sys.argv[1]), sys.argv[2] == 'cant'
x = dict(fd); x['params'] = dict(x['params'], side_panel=True, sp_top=2.07 + h, sp_bot=2.07, sp_cant=cant)
sc = scheme_from_result(x)
for L in (M.Loads(Ch=0.7),):
    a = C.Analysis(sc, L).run_all()
    gu = a.group_util()
    top = sorted(gu.items(), key=lambda kv: -kv[1][0])[:2]
    print(h, 'на всю длину' if cant else 'между колоннами', {k: (round(float(v[0]), 3), v[1][:28]) for k, v in top}, flush=True)
