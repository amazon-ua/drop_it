"""Вместо усиления — продление решётки ферм к опорам (Scheme.ext_web, группа "ew").
Запуск: python3 tasks/side_panel/scripts/extweb.py '<ext_web как python-кортеж>' [сечение ew] [frames col|all] [sides R|LR] [cp]"""
import sys, json, ast
ROOT = __import__('pathlib').Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'calc'))
import model as M, checks as C
from report_data import scheme_from_result, sec_by_name

fd = json.load(open(ROOT / 'output' / 'final_design.json'))
ew = ast.literal_eval(sys.argv[1])
secn = sys.argv[2] if len(sys.argv) > 2 else '20×20×2'
x = dict(fd); x['params'] = dict(x['params'], side_panel=True, ext_web=ew,
                                  ext_web_frames=sys.argv[3] if len(sys.argv) > 3 else 'col',
                                  ext_web_sides=sys.argv[4] if len(sys.argv) > 4 else 'R')
x['groups'] = dict(x['groups'], ew=secn)
cp = float(sys.argv[5]) if len(sys.argv) > 5 else 1.8
sc = scheme_from_result(x)
a = C.Analysis(sc, M.Loads(Ch=0.7, cp_panel=cp)).run_all(); m = a.model
gu = a.group_util()
top = sorted(gu.items(), key=lambda kv: -kv[1][0])[:5]
print(f'{ew} {secn} {sc.ext_web_frames} {sc.ext_web_sides} cp {cp}: максимум {top[0][1][0]:.3f}')
for g, (u, gov) in top:
    print(f'   {g:6s} {u:.3f}  {gov}')
for mid, mm in sorted(m.members.items()):
    if mm.get('frame') == 0.0 and mm['group'] in ('raf', 'ew', 'tie') and max(mm['p1'][0], mm['p2'][0]) > M.X_RIDGE + 0.5 \
            and min(mm['p1'][0], mm['p2'][0]) <= M.SPAN + 1e-6:
        r = a.member_results[mid]; cn = r['gov'].split('[')[-1].rstrip(']'); f = r['forces'][cn]
        d = sorted((round(M.SPAN - mm['p1'][0], 3), round(M.SPAN - mm['p2'][0], 3)))
        print(f"  рама 1 {mm['group']:4s} {d}  u {r['u']:.3f} ({r['gov']})  N {-f['Nmin']/1e3:.1f}/{f['Nmax']/1e3:.1f} кН  "
              f"M {max(f['My'], f['Mz'])/1e3:.2f} кНм")
