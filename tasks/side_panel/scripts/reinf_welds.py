"""Усиление правых стропил: эпюра M, N вдоль стропила, сечение у конца фасонок без усиления (до включения
обрезка в работу), сила в обрезке и швы. Запуск: python3 tasks/side_panel/scripts/reinf_welds.py [сечение] [Ch]"""
import sys, json, math
ROOT = __import__('pathlib').Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'calc'))
import numpy as np
import model as M, checks as C, fem
from report_data import scheme_from_result, sec_by_name
from sections import reinforced

fd = json.load(open(ROOT / 'output' / 'final_design.json'))
name = sys.argv[1] if len(sys.argv) > 1 else '80×40×2,5 пл.'
Ch = float(sys.argv[2]) if len(sys.argv) > 2 else 0.7
x = dict(fd); x['params'] = dict(x['params'], side_panel=True)
sc = scheme_from_result(x); sc.raf_reinf = sec_by_name(name)
a = C.Analysis(sc, M.Loads(Ch=Ch)).run_all(); m = a.model
t = sc.groups['raf']; add = sc.raf_reinf; rs = reinforced(t, add)
y2 = -(t.h / 2 + add.h / 2); yc = add.A * y2 / rs.A; d_add = y2 - yc        # от ц.т. составного до ц.т. обрезка
S = add.A * abs(d_add)
RWF, BF = 180e6, 0.7          # Э42, ручная сварка (ДБН В.2.6-198, табл. Г.2 / 16.3)
k = 0.0025
qw = BF * k * RWF             # Н/мм·1000 — несущая способность 1 м углового шва
worst = dict(q=0, Nr=0, u20=0, u20s=0)
for cn in a.uls:
    u, ends, ql, forces = a.env[cn]
    leff, _ = a.effective_lengths(ends, forces) if cn == 'D+S+0.9W+x' else (None, None)
    for mid, mm in m.members.items():
        if mm.get('reinf') is None:
            continue
        for ei in mm['elems']:
            e = m.elems[ei]
            p1 = np.array(m.nodes[e.n1]); p2 = np.array(m.nodes[e.n2])
            arr = fem.member_forces_along(e, ends[ei], ql[ei] if ql is not None else None, nst=21)
            for r in arr:
                xx = p1[0] + (p2[0] - p1[0]) * r[0] / e.L
                dist = M.SPAN - xx
                N = r[1]; V = max(abs(r[2]), abs(r[3])); My = r[5] if abs(r[5]) > abs(r[6]) else r[6]
                Mabs = max(abs(r[5]), abs(r[6]))
                if mm['reinf'] != 'gusset':
                    q = V * S / rs.Iy
                    if q > worst['q']:
                        worst.update(q=q, q_cn=cn, q_d=dist)
                    Nr = abs(add.A * (N / rs.A) + add.A * Mabs * abs(d_add) / rs.Iy)
                    if Nr > worst['Nr']:
                        worst.update(Nr=Nr, Nr_cn=cn, Nr_d=dist)
                if abs(dist - sc.rr_x0) < 0.012 and mm['reinf'] != 'gusset':
                    # у конца фасонок — голая труба (обрезок ещё не включился): прочность и устойчивость
                    us = (abs(N) / t.A + Mabs / t.Wy) / C.RY
                    if us > worst['u20']:
                        worst.update(u20=us, u20_cn=cn, u20_M=Mabs, u20_N=N)
print(f'{name}, Ch {Ch}: составное A {rs.A*1e4:.2f} см2, Iy {rs.Iy*1e8:.0f} см4, Wy {rs.Wy*1e6:.1f} см3, S обрезка {S*1e6:.1f} см3')
print(f"  сдвиг по контакту q = V·S/I: max {worst['q']/1e3:.1f} Н/мм ({worst['q_cn']}, {worst['q_d']:.2f} м от оси); "
      f"2 шва k=2.5 прерывистые 50/150: {2 * qw * 50 / 200 / 1e3:.0f} Н/мм → {worst['q'] / (2 * qw * 50 / 200):.2f}")
print(f"  сила в обрезке: max {worst['Nr']/1e3:.1f} кН ({worst['Nr_cn']}, {worst['Nr_d']:.2f} м); концевые швы 2×100 мм k=2.5: "
      f"{2 * 0.1 * qw / 1e3:.0f} кН → {worst['Nr'] / (2 * 0.1 * qw):.2f}")
print(f"  голая труба у конца фасонок ({sc.rr_x0} м): M {worst['u20_M']/1e3:.2f} кНм, N {worst['u20_N']/1e3:.1f} кН, "
      f"прочность {worst['u20']:.3f} ({worst['u20_cn']})")
