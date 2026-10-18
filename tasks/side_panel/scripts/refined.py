import sys, json, math
ROOT = __import__('pathlib').Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'calc'))
import model as M, checks as C
from report_data import scheme_from_result, sec_by_name
fd = json.load(open(ROOT / 'output' / 'final_design.json'))
x = dict(fd); x['params'] = dict(x['params'], side_panel=True)
sc = scheme_from_result(x)
a = C.Analysis(sc, M.Loads(Ch=0.7)).run_all()
m = a.model
t = sec_by_name('100×60×3')
cn = 'D+S+0.9W+x'
u, ends, ql, forces = a.env[cn]
leff, _ = a.effective_lengths(ends, forces)
for mid, mm in m.members.items():
    if mm['group'] == 'raf' and mm.get('frame') == 0.0 and min(mm['p1'][0], mm['p2'][0]) > 3.0 and max(mm['p1'][0], mm['p2'][0]) <= M.SPAN + 1e-6:
        f = dict(forces[mid]); Ly, Lz, _ = leff[mid]
        print('L', round(mm['L'], 2), 'Ly', round(Ly, 2), 'Lz', round(Lz, 2), 'N', round(-f['Nmin'] / 1e3, 1), 'My', round(f['My'] / 1e3, 2), 'Mz', round(f['Mz'] / 1e3, 2))
        base = C.member_checks(t, f, Ly, Lz, 'main', mm['L'], use_sig=False)
        print('как в модели (M max на узле):', {k: round(v, 3) for k, v in base.items()})
        for Md in (0.5 * max(f['My'], f['Mz']),):
            g = dict(f); k_ = Md / max(f['My'], f['Mz']); g['My'] *= k_; g['Mz'] *= k_
            r = C.member_checks(t, g, Ly, Lz, 'main', mm['L'], use_sig=False)
            print('устойчивость с M = 0.5·Mmax (средняя треть ≤ 1.32):', round(r['устойчивость'], 3))
        # прочность у конца фасонок (0.20 м от оси) и у конца опорной пластины (0.07 м): голая труба
        N = -f['Nmin']
        for d, Mloc in ((0.20, 3.35e3), (0.07, 4.17e3)):
            print(f'прочность голой трубы в {d} м от оси: ', round((N / t.A + Mloc / t.Wy) / C.RY, 3))
        # прочность в узле (0 м): труба + 2 фасонки t=5 (низ фасонки ниже низа стропила; учитываем только высоту стенки стропила ниже оси)
        hg = 0.050 / math.cos(M.SLOPE)          # фасонка закрывает нижнюю половину стенки стропила (до оси)
        Ag = 2 * 0.005 * hg
        yg = -hg / 2
        A = t.A + Ag; yc = Ag * yg / A
        Iy = t.Iy + t.A * yc ** 2 + 2 * 0.005 * hg ** 3 / 12 + Ag * (yg - yc) ** 2
        W = Iy / (t.h / 2 - yc)
        print('прочность в узле (труба + фасонки только на нижней половине стенки):', round((N / A + 4.7e3 / W) / C.RY, 3))
