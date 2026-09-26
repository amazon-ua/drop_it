"""Исходный вариант (черновик 2026-ПР-480, «оптимальный по бюджету»)."""
from sections import load_price_list, by_name
import model as M

SECS = load_price_list()


def baseline_scheme():
    g = {
        "col": "120×120×4", "raf": "100×100×4", "tie": "100×50×3", "kp": "40×40×2",
        "strut": "40×40×2", "knee": "40×40×2", "lath": "40×40×2", "sd": "40×40×2",
        "sb": "60×60×3", "st": "100×50×3", "stub": "100×100×4", "xb": "60×60×2",
    }
    sc = M.Scheme(name="Черновик", frames=3, web="KS", strut_dx=1.0, knee_t=True, knee_z=2.10,
                  knee_dx=0.90, side_zb=2.10, side_top=True, roof_x=True, base="spring", embed=1.152)
    # embed подобран так, чтобы суммарная длина колонн совпала с ведомостью черновика
    # (4.24 + 4.30 + 4.43 + 4.48 = 17.45 м) при фактических отметках верха бетона
    sc.groups = {k: by_name(SECS, v) for k, v in g.items()}
    return sc
