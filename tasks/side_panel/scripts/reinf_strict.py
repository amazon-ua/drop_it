"""Строгая проверка усиления правых стропил рам 1 и 3 по участкам (Scheme.raf_reinf):
узел А с фасонками (0…rr_x0), труба + усиление (rr_x0…rr_x1), голая труба до узла подкоса фермы.
Запуск: python3 tasks/side_panel/scripts/reinf_strict.py [сечение усиления|none] [rr_x0] [rr_x1] [Ch]"""
import sys, json
ROOT = __import__('pathlib').Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'calc'))
import model as M, checks as C
from report_data import scheme_from_result, sec_by_name
from sections import plate_section

fd = json.load(open(ROOT / 'output' / 'final_design.json'))
arg = sys.argv[1] if len(sys.argv) > 1 else '80×40×2,5 пл.'
x = dict(fd); x['params'] = dict(x['params'], side_panel=True)
sc = scheme_from_result(x)
if arg != 'none':
    if arg.startswith('полоса'):
        b_, t_ = (float(v) / 1000 for v in arg.split()[1].split('×'))
        sc.raf_reinf = plate_section(b_, t_)
    else:
        sc.raf_reinf = sec_by_name(arg)
    if len(sys.argv) > 2:
        sc.rr_x0, sc.rr_x1 = float(sys.argv[2]), float(sys.argv[3])
Ch = float(sys.argv[4]) if len(sys.argv) > 4 else 0.7
a = C.Analysis(sc, M.Loads(Ch=Ch)).run_all()
m = a.model
gu = a.group_util()
top = sorted(gu.items(), key=lambda kv: -kv[1][0])[:4]
print(f'усиление: {arg}; Ch = {Ch}; максимум {top[0][1][0]:.3f}')
for g, (u, gov) in top:
    print(f'   {g:6s} {u:.3f}  {gov}')
print('правые стропила рам на колоннах (от оси колонны, м):')
for mid, mm in sorted(m.members.items()):
    if mm['group'] == 'raf' and mm.get('frame') in (0.0, M.BAY) and M.X_RIDGE + 0.5 < min(mm['p1'][0], mm['p2'][0]) \
            and max(mm['p1'][0], mm['p2'][0]) <= M.SPAN + 1e-6:
        r = a.member_results[mid]
        sec = m.elems[mm['elems'][0]].sec
        d1, d2 = sorted((M.SPAN - mm['p1'][0], M.SPAN - mm['p2'][0]))
        cn = r['gov'].split('[')[-1].rstrip(']')
        f = r['forces'][cn]
        print(f"  рама {1 if mm['frame'] == 0 else 3}: {d1:.3f}…{d2:.3f}  {sec.name:24s} Wy {sec.Wy*1e6:5.1f} см3  "
              f"u {r['u']:.3f} ({r['gov']})  N {-f['Nmin']/1e3:.1f} кН  M {max(f['My'], f['Mz'])/1e3:.2f} кНм  "
              f"V {max(f['Vz'], f['Vy'])/1e3:.2f} кН  Ly {r['Ly']:.2f} Lz {r['Lz']:.2f}  "
              f"прочн {r.get('chk_прочность', 0):.3f} уст {r.get('chk_устойчивость', 0):.3f}")
