"""r11 — planșele de control ale reparațiilor din motor (PT 2 trafo + AAR, TG cu UPS, TG bară normală + vitală,
6 stații VE, CEF cu 2 TGD-CF). Rulare: python3 teste/r11/fix_motor/randeaza.py [nume …]"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
from engine import constructor, layout, render_svg, validare  # noqa: E402

D = pathlib.Path(__file__).parent
CAZURI = {
    "pt_2trafo_aar": {"tip_schema": "pt", "Sn_kVA": 800, "n_trafo": 2, "cupla": "deschisa", "aar": True,
                      "trafo_izolatie": "uscat", "ucc_pct": 6, "grupa_conexiuni": "Dyn11", "U_MT_kV": 20,
                      "schema_pamant": "TN-S", "masura_pt": "MT", "celule_mt": {"linie": 2, "masura": True},
                      "plecari": [{"nume": "TD Hală 1", "P_kW": 220, "L_m": 60, "sectie": 1},
                                  {"nume": "TD Compresoare", "receptor": "tablou", "P_kW": 160, "L_m": 40, "sectie": 1},
                                  {"nume": "TD Hală 2", "P_kW": 200, "L_m": 80, "sectie": 2},
                                  {"nume": "TD Birouri", "P_kW": 60, "L_m": 50, "sectie": 2}]},
    "tg_ups_200": {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 1000, "schema_pamant": "TN-S",
                   "L_alimentare_m": 30, "titlu_tablou": "TG Data center",
                   "plecari": [{"nume": "UPS 200 kVA", "ups": True, "Sn_kVA": 200, "bypass": True, "L_m": 20,
                                "copii": [{"nume": "PDU A", "P_kW": 60, "L_m": 15}, {"nume": "PDU B", "P_kW": 60, "L_m": 15},
                                          {"nume": "Rack-uri rând C", "P_kW": 5, "n_circuite": 4, "L_m": 20}]},
                               {"nume": "Climatizare", "P_kW": 120, "L_m": 40},
                               {"nume": "Iluminat", "P_kW": 8, "L_m": 30}]},
    "tg_normal_vital": {"tip_schema": "ge_ats", "Sn_GE_kVA": 400, "bara_vitala": True, "sursa_retea": "pt",
                        "pt_Sn_kVA": 1000, "schema_pamant": "TN-S",
                        "consumatori": [{"nume": "Pompă incendiu", "P_kW": 75, "pornire": "stea_triunghi", "siguranta": True},
                                        {"nume": "Sprinklere jockey", "P_kW": 3, "siguranta": True},
                                        {"nume": "Desfumare", "P_kW": 11, "n": 2, "siguranta": True},
                                        {"nume": "Iluminat siguranță", "P_kW": 3, "vital": True},
                                        {"nume": "Servere", "P_kW": 20, "vital": True},
                                        {"nume": "HVAC", "P_kW": 150, "vital": False},
                                        {"nume": "Iluminat", "P_kW": 40, "vital": False},
                                        {"nume": "Prize", "P_kW": 30, "vital": False}]},
    "ve_6x22": {"tip_schema": "tablou", "origine": "tg_existent", "schema_pamant": "TN-S", "Ik3_sursa_kA": 15,
                "titlu_tablou": "TD Parcare VE", "L_alimentare_m": 40,
                "plecari": [{"nume": "Stație VE", "P_kW": 22, "n": 6, "retea": "tri", "ddr": {"tip": "B"}, "L_m": 25}]},
    "cef_2tgd": {"tip_schema": "cef", "racord": "pt", "pt_Sn_kVA": 630, "pt_existent": True, "retea": "tri",
                 "schema_pamant": "TN-S", "n_tgd_cf": 2, "L_racord_m": 60, "limitare_injectie_kW": 0,
                 "invertoare": [{"n": 3, "Pn_kW": 50, "producator": "Huawei", "model": "SUN2000-50KTL-M3", "tgd": 1},
                                {"n": 3, "Pn_kW": 50, "producator": "Huawei", "model": "SUN2000-50KTL-M3", "tgd": 2}]},
}


def main(nume=None):
    for k, inp in CAZURI.items():
        if nume and k not in nume:
            continue
        m, r = constructor.genereaza(inp)
        v = validare.valideaza(m)
        svg = render_svg.render(layout.build(m), k)
        svg = svg[0] if isinstance(svg, tuple) else svg
        (D / f"{k}.svg").write_text(svg)
        try:
            import cairosvg
            cairosvg.svg2png(bytestring=svg.encode(), write_to=str(D / f"{k}.png"), output_width=2400)
        except Exception as e:  # noqa: BLE001
            print("png:", e)
        ver = [f"{x['nivel'][:2]} {x['cod']} {x['obiect']}: {x['mesaj']}" for x in r["verificari"] + v["verificari"]
               if x["nivel"] != "INFO"]
        (D / f"{k}.json").write_text(json.dumps({"intrare": inp, "verificari": ver, "presupus": r.get("presupus")},
                                                ensure_ascii=False, indent=1))
        print(f"== {k}: blocheaza={v['blocheaza']}")
        for x in ver:
            print("  ", x[:200])


if __name__ == "__main__":
    main(sys.argv[1:] or None)
