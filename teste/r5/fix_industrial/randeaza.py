import sys, json, pathlib
sys.path.insert(0, '/home/claude/sm')
from engine import constructor, layout, render_svg
OUT = pathlib.Path('/home/claude/sm/teste/r5/fix_industrial')
CAZURI = {
 "tg_tt": {"tip_schema": "tablou", "schema_pamant": "TT", "RA_ohm": 30, "origine": "bmpt",
           "plecari": [{"nume": "TD-1", "In_A": 32}, {"nume": "TD-2", "In_A": 32}, {"nume": "TD-3", "In_A": 32}]},
 "tg_mono": {"tip_schema": "tablou", "retea": "mono", "origine": "tg_existent", "Ik3_sursa_kA": 6, "L_alimentare_m": 20,
             "plecari": [{"nume": "Iluminat", "P_kW": 2, "L_m": 30}, {"nume": "Prize", "P_kW": 3, "L_m": 25}]},
 "tg_motoare": {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 400, "schema_pamant": "TN-S",
                "plecari": [{"nume": "Pompa", "P_kW": 30, "pornire": "stea_triunghi", "L_m": 50},
                            {"nume": "Ventilator", "P_kW": 45, "pornire": "convertizor", "L_m": 35},
                            {"nume": "Banda transportoare", "P_kW": 7.5, "L_m": 40},
                            {"nume": "Iluminat", "In_A": 16, "n_circuite": 3, "L_m": 30, "prot_tip": "MCB"}]},
 "pt_uscat": {"tip_schema": "pt", "Sn_kVA": 400, "trafo_izolatie": "uscat", "celule_mt": ["linie", "linie", "masura", "trafo"],
              "masura": "MT", "plecari": [{"nume": "TD-1", "In_A": 200}, {"nume": "TD-2", "In_A": 160}]},
 "ge_din_pt": {"tip_schema": "ge_ats", "Sn_GE_kVA": 500, "P_sarcina_kW": 380, "sursa_retea": "pt", "pt_Sn_kVA": 630,
               "L_GE_ATS_m": 15},
}
for k in (sys.argv[1:] or CAZURI):
    m, rez = constructor.genereaza(CAZURI[k])
    c = layout.build(m)
    (OUT / f"{k}.svg").write_text(render_svg.render(c, k), encoding="utf-8")
    v = rez if isinstance(rez, dict) else {}
    print(k, "blocheaza:", v.get("blocheaza_export"), [x.get("cod") + "/" + x.get("nivel") for x in (v.get("verificari") or []) if x.get("nivel") != "INFO"][:12])
