# Planșele de control r9 (motor / desen): python3 teste/r9/fix_motor/randeaza.py
import sys, json, pathlib
D = pathlib.Path(__file__).parent
sys.path.insert(0, str(D.parents[2]))
from engine import constructor, validare, layout, render_svg
import cairosvg

CAZURI = {
    "m1_psi_ge_ats": {"tip_schema": "ge_ats", "titlu_tablou": "Stație pompare PSI", "Sn_GE_kVA": 100, "sursa_retea": "pt",
                      "pt_Sn_kVA": 250, "consumatori": [{"nume": "Electropompe", "P_kW": 30, "n": "1+1"},
                                                        {"nume": "Pompa pilot", "P_kW": 1.1}]},
    "m2_tg_mixt_sprinkler": {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 400, "schema_pamant": "TN-S",
                             "plecari": [{"nume": "Pompa sprinkler", "P_kW": 75, "pornire": "stea_triunghi"},
                                         {"nume": "Pompa jockey", "P_kW": 3}, {"nume": "Iluminat hală", "P_kW": 8},
                                         {"nume": "CTA 1", "P_kW": 4}, {"nume": "CTA 2", "P_kW": 4},
                                         {"nume": "Rampe", "P_kW": 4.4}]},
    "m3_cef_800v_2trafo": {"tip_schema": "cef", "n_trafo": 2, "pt_Sn_kVA": 2000, "masura": "MT", "U_inv_ca_V": 800,
                           "retea": "tri", "invertoare": [{"n": 12, "Pn_kW": 250, "producator": "Sungrow", "model": "SG250HX"}]},
    "m4_casa_ve_11kw": {"tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TN-C-S",
                        "alimentare": {"P_aprobata_kW": 20},
                        "circuite": [{"nume": "Iluminat interior", "receptor": "iluminat"},
                                     {"nume": "Iluminat exterior", "receptor": "iluminat"},
                                     {"nume": "Prize camere", "receptor": "prize"}, {"nume": "Prize living", "receptor": "prize"},
                                     {"nume": "Prize bucătărie", "receptor": "prize_bucatarie"},
                                     {"nume": "Prize baie", "receptor": "prize_baie"}, {"nume": "Plită", "receptor": "plita"},
                                     {"nume": "Boiler", "receptor": "boiler"},
                                     {"nume": "Centrală termică", "receptor": "centrala_termica"},
                                     {"nume": "Încărcare VE", "receptor": "vehicul_electric", "P_kW": 11, "L_m": 20}]},
}

if __name__ == "__main__":
    for nume, inp in CAZURI.items():
        m, r = constructor.genereaza(inp)
        v = validare.valideaza(m)
        svg = render_svg.render(layout.build(m), "t")
        (D / f"{nume}.svg").write_text(svg)
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(D / f"{nume}.png"), output_width=2400)
        print(nume, "BLOCANT" if v["blocheaza"] else "ok",
              [f"{x['cod']} {x['nivel']}" for x in v["verificari"] if x["nivel"] != "INFO" and x["cod"] != "V42"])
