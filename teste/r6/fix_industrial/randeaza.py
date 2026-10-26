"""r6 — planșele de verificare pentru reparațiile din zona TABLOU / PT / GE / LOCUINȚĂ / BRANȘAMENT.
Rulare: python3 teste/r6/fix_industrial/randeaza.py  → svg/ + png/ în acest director."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
from engine import constructor, layout, render_svg, validare  # noqa: E402

D = pathlib.Path(__file__).parent
CAZURI = {
    "f1_tg_motoare_ge_incendiu": {
        "tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 400, "schema_pamant": "TN-S",
        "plecari": [{"nume": "Compresor", "P_kW": 30, "L_m": 40}, {"nume": "Pompă", "P_kW": 18.5, "L_m": 30,
                                                                    "receptor": "motor"},
                    {"nume": "TD-1", "In_A": 160, "L_m": 70, "copii": [
                        {"nume": "Ventilator", "P_kW": 22, "receptor": "motor"},
                        {"nume": "Moară", "P_kW": 18.5, "receptor": "motor"}, {"nume": "Iluminat", "P_kW": 3}]},
                    {"nume": "Iluminat hală", "P_kW": 1.5}]},
    "f1b_ge_pompe_incendiu": {
        "tip_schema": "ge_ats", "Sn_GE_kVA": 200, "sursa_retea": "pt", "pt_Sn_kVA": 400,
        "consumatori": [{"nume": "Pompă incendiu", "P_kW": 45, "n": 2, "pornire": "stea_triunghi"},
                        {"nume": "Hidrofor", "P_kW": 7.5}, {"nume": "Iluminat siguranță + TD vital", "P_kW": 15}]},
    "f2_pt_2x630": {"tip_schema": "pt", "Sn_kVA": 630, "n_trafo": 2,
                    "plecari": [{"nume": "TG1", "In_A": 800, "L_m": 30}, {"nume": "TG2", "In_A": 800, "L_m": 40}]},
    "f3_casa_atelier": {
        "tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TN-C-S",
        "alimentare": {"P_aprobata_kW": 15, "L_coloana_m": 20},
        "circuite": [{"nume": "Iluminat", "receptor": "iluminat"}, {"nume": "Prize camere", "receptor": "prize"},
                     {"nume": "Prize bucătărie", "receptor": "prize_bucatarie"}, {"nume": "Prize baie", "receptor": "prize_baie"},
                     {"nume": "Boiler", "receptor": "boiler"}, {"nume": "Încărcător VE", "receptor": "vehicul_electric", "P_kW": 7.4}],
        "tablouri_secundare": [{"nume": "TD atelier", "L_m": 40, "circuite": [
            {"nume": "Strung", "P_kW": 4, "pornire": "directa"}, {"nume": "Compresor", "P_kW": 3, "receptor": "motor"},
            {"nume": "Iluminat atelier", "P_kW": 0.5}, {"nume": "Prize atelier", "In_A": 16, "n_circuite": 2}]}]},
    "f4_bransament_bmpm32_7kw": {"tip_schema": "bransament", "retea": "mono", "P_kW": 7, "Q_In_A": 32, "L_coloana_m": 20},
    "f5_tg_compensare": {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 630, "compensare_kvar": 120,
                         "plecari": [{"nume": "TD-1", "In_A": 250, "L_m": 50}, {"nume": "TD-2", "In_A": 160, "L_m": 40},
                                     {"nume": "Compresor", "P_kW": 37, "pornire": "stea_triunghi", "L_m": 25}]},
    "f6_tg_sursa_nedeclarata": {"tip_schema": "tablou", "retea": "mono",
                                "plecari": [{"nume": "Iluminat", "P_kW": 1.5}, {"nume": "Prize", "P_kW": 2},
                                            {"nume": "Centrală", "P_kW": 0.2}, {"nume": "Pompă căldură", "P_kW": 9}]},
}

if __name__ == "__main__":
    import cairosvg
    (D / "svg").mkdir(exist_ok=True)
    (D / "png").mkdir(exist_ok=True)
    rez = {}
    for k, inp in CAZURI.items():
        m, r = constructor.genereaza(json.loads(json.dumps(inp)), cartus={"beneficiar": "TEST r6"})
        val = validare.valideaza(m) if hasattr(validare, "valideaza") else None
        svg = render_svg.render(layout.build(m), k)
        (D / "svg" / f"{k}.svg").write_text(svg, encoding="utf-8")
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(D / "png" / f"{k}.png"), output_width=2400)
        rez[k] = {"blocheaza_export": r.get("blocheaza_export"),
                  "blocante": [f"{v['cod']} {v['obiect']}: {v['mesaj']}" for v in r["verificari"] if v["nivel"] == "BLOCANT"],
                  "avertismente": [f"{v['cod']} {v['obiect']}: {v['mesaj']}" for v in r["verificari"] if v["nivel"] == "AVERTISMENT"]}
        print(k, "BLOCANT" if r.get("blocheaza_export") else "ok", len(rez[k]["avertismente"]), "AV")
    (D / "rezultat.json").write_text(json.dumps(rez, ensure_ascii=False, indent=1), encoding="utf-8")
