import sys, json, dataclasses, math
ROOT = __import__('pathlib').Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'calc'))
import model as M, checks as C
from report_data import scheme_from_result, sec_by_name
fd = json.load(open(ROOT / 'output' / 'final_design.json'))
t = sec_by_name('100×60×3')
bp, tp = float(sys.argv[1]) / 1000, float(sys.argv[2]) / 1000     # полоса: ширина, толщина
Ap = bp * tp
yp = -(t.h / 2 + tp / 2)
A = t.A + Ap
yc = Ap * yp / A
Iy = t.Iy + t.A * yc ** 2 + bp * tp ** 3 / 12 + Ap * (yp - yc) ** 2
Iz = t.Iz + tp * bp ** 3 / 12
cmax = max(t.h / 2 - yc, t.h / 2 + tp + yc)
r = dataclasses.replace(t, name=f"100×60×3+{sys.argv[1]}×{sys.argv[2]}", A=A, Iy=Iy, Iz=Iz, Wy=Iy / cmax,
                        Wz=Iz / (t.b / 2), iy=math.sqrt(Iy / A), iz=math.sqrt(Iz / A), mass=t.mass + Ap * 7850)
print('труба Iy', round(t.Iy * 1e8, 1), 'Wy', round(t.Wy * 1e6, 2), '| с полосой Iy', round(Iy * 1e8, 1), 'Wy(мин)', round(r.Wy * 1e6, 2),
      'yc мм', round(yc * 1000, 1), 'A', round(A * 1e4, 2))
orig = M.build
def build(sc_):
    m = orig(sc_)
    for e in m.elems:
        mm = m.members[e.member]
        if mm['group'] == 'raf' and mm.get('frame') in (0.0, M.BAY):
            xs = (mm['p1'][0], mm['p2'][0])
            if min(xs) > M.X_RIDGE + 0.5 and max(xs) <= M.SPAN + 1e-6:      # участок от подкоса фермы до узла над колонной
                e.sec = r
    return m
M.build = build
x = dict(fd); x['params'] = dict(x['params'], side_panel=True)
sc = scheme_from_result(x)
for L in (M.Loads(), M.Loads(Ch=0.7)):
    a = C.Analysis(sc, L).run_all()
    m = a.model
    gu = a.group_util()
    rr = sorted(((float(v['u']), v['gov'], m.members[k].get('frame'), round(min(m.members[k]['p1'][0], m.members[k]['p2'][0]), 2))
                 for k, v in a.member_results.items() if m.members[k]['group'] == 'raf'), reverse=True)[:3]
    print('Ch', L.Ch, 'max', round(max(float(v[0]) for v in gu.values()), 3), 'стропила:', [(round(u, 3), g[:30], f, x0) for u, g, f, x0 in rr])
    # поперечная сила в усиленном участке — для швов
    Vmax = 0
    for k, v in a.member_results.items():
        mm = m.members[k]
        if mm['group'] == 'raf' and mm.get('frame') in (0.0, M.BAY) and min(mm['p1'][0], mm['p2'][0]) > M.X_RIDGE + 0.5 and max(mm['p1'][0], mm['p2'][0]) <= M.SPAN + 1e-6:
            Vmax = max(Vmax, max(max(f['Vy'], f['Vz']) for f in v['forces'].values()))
    S = Ap * abs(yp - yc)
    print('   V max', round(Vmax / 1e3, 2), 'кН; сдвиг на шов', round(Vmax * S / Iy / 1e3, 1), 'Н/мм (на 2 шва)')
