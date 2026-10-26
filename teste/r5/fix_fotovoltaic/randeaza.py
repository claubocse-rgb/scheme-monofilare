"""Randează planșele de regresie R5 fotovoltaic (intrare fizică directă) în teste/r5/fix_fotovoltaic/."""
import json, os, subprocess, sys
RAD = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, RAD)
from engine import constructor, layout, render_svg
from engine.topologie import coliziuni
OUT = os.path.dirname(os.path.abspath(__file__))
HUAWEI100 = {"producator": "Huawei", "model": "SUN2000-100KTL-M2", "Pn_kW": 100}
SG50 = {"producator": "Sungrow", "model": "SG50CX", "Pn_kW": 50}
PLANSE = {
    "p1_cef_2inv_bess": {"tip_schema": "cef", "retea": "tri", "kWp": 180, "racord": "tg_existent", "L_racord_m": 50,
                         "invertoare": [dict(HUAWEI100, n=1), dict(SG50, n=1)],
                         "bess": {"producator": "Huawei", "model": "LUNA2000-215", "P_kW": 100, "kWh": 215}},
    "p2_prosumator_hibrid": {"tip_schema": "prosumator", "retea": "tri", "kWp": 12, "In_Q_bransament_A": 32,
                             "invertoare": [{"n": 1, "Pn_kW": 10, "producator": "Huawei", "model": "SUN2000-10KTL-M1", "hibrid": True}],
                             "bess": {"producator": "Huawei", "model": "LUNA2000-10", "kWh": 10, "U_nom_V": 450}},
    "p3_cef_tg_existent_pt": {"tip_schema": "cef", "retea": "tri", "kWp": 600, "invertoare": [{"n": 5, "Pn_kW": 110}],
                              "racord": "tg_existent", "pt_Sn_kVA": 1000, "L_racord_m": 40, "racord_In_Q_A": 1000,
                              "Ik3_TG_kA": 20},
    "p4_injectie_zero": {"tip_schema": "prosumator", "retea": "tri", "kWp": 300, "racord": "tg_existent",
                         "invertoare": [{"n": 2, "Pn_kW": 125}], "bess": {"P_kW": 100, "kWh": 200},
                         "limitare_injectie_kW": 0, "L_racord_m": 30},
    "p5_bess_singur": {"tip_schema": "bess", "retea": "tri", "racord": "tg_existent", "L_racord_m": 40, "pt_Sn_kVA": 1000,
                       "bess": {"producator": "Sungrow", "model": "PowerStack 255CS", "P_kW": 500, "kWh": 1000}},
}
if __name__ == "__main__":
    rez = {}
    for nume, inp in PLANSE.items():
        m, r = constructor.genereaza(inp)
        c = layout.build(m)
        open(f"{OUT}/{nume}.svg", "w").write(render_svg.render(c))
        rez[nume] = {"blocant": r["blocheaza_export"], "coliziuni": coliziuni(c),
                     "verificari": [f"{v['nivel'][:2]} {v['cod']} {v['obiect']}: {v['mesaj']}" for v in r["verificari"]]}
        print(nume, "BLOCANT" if r["blocheaza_export"] else "ok", rez[nume]["coliziuni"][:3])
        for v in rez[nume]["verificari"]:
            print("   ", v[:160])
    json.dump(rez, open(f"{OUT}/rezultat.json", "w"), ensure_ascii=False, indent=1)
    subprocess.run(["node", f"{OUT}/conv.js"] + list(PLANSE), cwd=OUT)
