import sys, json, dataclasses, math
ROOT = __import__('pathlib').Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'calc'))
import model as M, checks as C
from report_data import scheme_from_result, sec_by_name
fd = json.load(open(ROOT / 'output' / 'final_design.json'))
t = sec_by_name('100×60×3')
name, hh, bb, tt = sys.argv[1], float(sys.argv[2]) / 1000, float(sys.argv[3]) / 1000, float(sys.argv[4]) / 1000
# прямоугольная труба hh (по вертикали) × bb, стенка tt — под низом стропила
A2 = 2 * tt * (hh + bb) - 4 * tt * tt
I2 = (bb * hh ** 3 - (bb - 2 * tt) * (hh - 2 * tt) ** 3) / 12
y2 = -(t.h / 2 + hh / 2)
A = t.A + A2; yc = A2 * y2 / A
Iy = t.Iy + t.A * yc ** 2 + I2 + A2 * (y2 - yc) ** 2
Iz = t.Iz + (hh * bb ** 3 - (hh - 2 * tt) * (bb - 2 * tt) ** 3) / 12
cmax = max(t.h / 2 - yc, t.h / 2 + hh + yc)
r = dataclasses.replace(t, name="усил", A=A, Iy=Iy, Iz=Iz, Wy=Iy / cmax, Wz=Iz / (max(t.b, bb) / 2),
                        iy=math.sqrt(Iy / A), iz=math.sqrt(Iz / A), mass=t.mass + A2 * 7850)
orig = M.build
def build(sc_):
    m = orig(sc_)
    for e in m.elems:
        mm = m.members[e.member]
        if mm['group'] == 'raf' and mm.get('frame') in (0.0, M.BAY):
            xs = (mm['p1'][0], mm['p2'][0])
            if min(xs) > M.X_RIDGE + 0.5 and max(xs) <= M.SPAN + 1e-6:
                e.sec = r
    return m
M.build = build
x = dict(fd); x['params'] = dict(x['params'], side_panel=True)
sc = scheme_from_result(x)
a = C.Analysis(sc, M.Loads(Ch=0.7)).run_all()
m = a.model
rr = max(float(v['u']) for k, v in a.member_results.items() if m.members[k]['group'] == 'raf')
gu = a.group_util()
print(name, 'Wy', round(t.Wy * 1e6, 1), '→', round(r.Wy * 1e6, 1), 'см3; стропила', round(rr, 3), 'макс', round(max(float(v[0]) for v in gu.values()), 3), flush=True)
