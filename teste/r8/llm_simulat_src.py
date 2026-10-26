"""SIMULARE (nu apel real): ieșirile uneltei `intrare_fizica` scrise de Claude în rolul modelului care primește DOAR
promptul de sistem (interpretor.system_llm()), schema uneltei și fraza. Scrise ÎNAINTE de a citi „asteptat” din
fraze.json. Se rulează o dată pentru a produce llm_simulat.json."""
import json, pathlib

T, F = True, False


def U(intr, q=(), n=(), c=None):
    d = {"intrare_fizica": intr, "intrebari": list(q), "neinteles": list(n)}
    if c:
        d["cartus"] = c
    return d


def inv(n, pn, prod=None, model=None):
    d = {"n": n, "Pn_kW": pn}
    if prod: d["producator"] = prod
    if model: d["model"] = model
    return d


def pl(nume, **k):
    return dict({"nume": nume}, **k)


S = {}
# ------------------------------------------------------------------------------------------- fotovoltaic
S["fotovoltaic"] = {
 28: U({"tip_schema": "cef", "invertoare": [inv(2, 110, "Sungrow", "SG110CX"), inv(2, 50, "Sungrow", "SG50CX")]},
       ["Textul spune „300 kW cu 3 invertoare”, dar 2 × SG110CX + 2 × SG50CX = 4 invertoare / 320 kW. Care e configurația corectă?"]),
 33: U({"tip_schema": "prosumator", "retea": "tri", "schema_pamant": "TN-S", "Pn_inv_kW": 24.6,
        "invertoare": [inv(3, 8.2, "Fronius", "Primo 8.2-1")]}, [], ["conectate câte unul pe fiecare fază"]),
 51: U({"tip_schema": "cef", "kWp": 100, "racord": "tg_existent", "schema_pamant": "TN-S",
        "invertoare": [inv(2, 50, "Sungrow", "SG50CX")]}),
 58: U({"tip_schema": "cef", "racord": "tg_existent", "schema_pamant": "TN-S",
        "invertoare": [inv(2, 50, "XYZ Solar", "SPX-50")]}),
 61: U({"tip_schema": "cef", "kWp": 700, "schema_pamant": "TN-S", "pt_Sn_kVA": 630, "pt_existent": F, "racord": "pt",
        "invertoare": [inv(6, 100, "Huawei", "SUN2000-100KTL-M2")],
        "modul": {"producator": "Trina", "model": "TSM-NEG21C.20", "Pmax_W": 700}}),
 26: U({"tip_schema": "cef", "racord": "pt", "pt_Sn_kVA": 800, "pt_existent": T, "schema_pamant": "TN-S",
        "invertoare": [inv(3, 100, "Huawei", "SUN2000-100KTL-M2"), inv(2, 50, "Huawei", "SUN2000-50KTL-M3")],
        "bess": {"P_kW": 100, "kWh": 200, "producator": "Huawei", "model": "LUNA2000-200KWH-2H1"}}),
 34: U({"tip_schema": "cef", "kWp": 199, "racord": "tg_existent", "schema_pamant": "TN-S", "limitare_injectie_kW": 0,
        "Ik3_TG_kA": 20, "racord_In_Q_A": 400, "invertoare": [inv(2, 110, "Sungrow", "SG110CX")]}),
 45: U({"tip_schema": "cef", "kWp": 2000, "invertoare": [inv(20, 100)], "bess": {"P_kW": 2000, "kWh": 4000},
        "pt_Sn_kVA": 2000, "n_trafo": 2, "pt_existent": F, "masura": "MT", "limitare_injectie_kW": 3000}),
 53: U({"tip_schema": "cef", "racord": "pt", "pt_Sn_kVA": 400, "pt_existent": T, "Ik3_TG_kA": 30, "racord_In_Q_A": 63,
        "invertoare": [inv(1, 60, "Huawei", "SUN2000-60KTL-M0")]},
       ["Racordul e în PT-ul existent 400 kVA, dar e menționat și „întreruptor TG 63 A”: centrala se leagă în TG (pe "
        "întreruptorul de 63 A) sau direct pe bara JT a PT-ului?"]),
 1: U({"tip_schema": "cef", "retea": "tri", "kWp": 99.4, "racord": "bmpt", "In_Q_bransament_A": 250,
       "P_aprobata_kW": 120, "P_evacuata_kW": 80, "limitare_injectie_kW": 80, "masura_ceruta": "semidirecta",
       "invertoare": [inv(1, 100, "Huawei", "SUN2000-100KTL-M2")]}),
 7: U({"tip_schema": "cef", "kWp": 2000, "invertoare": [inv(8, 330, "Huawei", "SUN2000-330KTL-H1")], "pt_Sn_kVA": 2500,
       "pt_existent": F, "U_MT_kV": 20, "U_ca_V": 800, "masura": "MT"}),
 9: U({"tip_schema": "cef", "kWp": 3600, "invertoare": [inv(30, 100, "Sungrow", "SG100CX")], "pt_Sn_kVA": 1600,
       "n_trafo": 2, "pt_existent": F, "U_MT_kV": 20, "masura": "MT"}),
 13: U({"tip_schema": "cef", "bess": {"P_kW": 1000, "kWh": 2000}, "pt_Sn_kVA": 1250, "pt_existent": F, "U_MT_kV": 20,
        "masura": "MT"}),
 15: U({"tip_schema": "cef", "kWp": 250, "invertoare": [inv(2, 110, "Sungrow", "SG110CX")], "P_evacuata_kW": 100,
        "limitare_injectie_kW": 100, "racord": "tg_existent", "schema_pamant": "TN-C-S"}),
 16: U({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 20,
        "invertor": {"producator": "Huawei", "model": "SUN2000-20KTL-M2", "Pn_kW": 20}, "P_evacuata_kW": 20,
        "limitare_injectie_kW": 0},
       ["Injecție zero (limitare 0 kW) sau injecție până la 20 kW, cât e aprobat pentru evacuare în ATR?"]),
 24: U({"tip_schema": "prosumator", "retea": "tri", "schema_pamant": "TN-C-S", "Pn_inv_kW": 50, "racord": "bmpt",
        "In_Q_bransament_A": 40, "invertor": {"producator": "Huawei", "model": "SUN2000-50KTL-M3", "Pn_kW": 50}},
       ["Invertorul de 50 kW pe BMPT existent 3 × 40 A: branșamentul se mărește (ATR nou) sau se limitează puterea?"]),
 25: U({"tip_schema": "cef", "kWp": 1500, "pt_Sn_kVA": 1600, "pt_existent": F,
        "invertoare": [inv(4, 250, "Sungrow", "SG250HX"), inv(2, 110, "Sungrow", "SG110CX")]},
       ["SG250HX are ieșirea la 800 V c.a., iar SG110CX la 400 V: trafo cu două înfășurări JT / două trafo, sau alt "
        "model pentru una din grupe?"]),
 29: U({"tip_schema": "cef", "kWp": 200, "invertoare": [inv(2, 100, "Huawei", "SUN2000-100KTL-M2")], "pt_Sn_kVA": 250,
        "pt_existent": F},
       ["Racordul: în BMPT-ul existent sau prin PT-ul nou de 250 kVA? (textul le menționează pe amândouă)"]),
 35: U({"tip_schema": "cef", "kWp": 1000, "invertoare": [inv(10, 100, "Huawei", "SUN2000-100KTL-M2")], "racord": "pt",
        "pt_Sn_kVA": 1000, "pt_existent": T, "masura": "MT", "U_MT_kV": 20}),
 37: U({"tip_schema": "cef", "kWp": 150, "invertoare": [inv(1, 110, "Sungrow", "SG110CX")], "racord": "tg_existent",
        "schema_pamant": "TN-S"}),
}
# ------------------------------------------------------------------------------------------- industrial
S["industrial"] = {
 12: U({"tip_schema": "ge_ats", "Sn_GE_kVA": 125, "sursa_retea": "tgd", "schema_pamant": "TN-S", "siguranta_tablou": T,
        "titlu_tablou": "TDSI sprinklere",
        "consumatori": [{"nume": "Electropompă sprinklere", "P_kW": 55, "pornire": "stea_triunghi", "siguranta": T},
                        {"nume": "Pompă jockey", "P_kW": 2.2, "siguranta": T}]}),
 14: U({"tip_schema": "tablou", "origine": "tg_existent", "schema_pamant": "TN-S", "siguranta_tablou": T,
        "titlu_tablou": "TE desfumare",
        "plecari": [pl("Ventilator desfumare 1", P_kW=11, receptor="motor", siguranta=T),
                    pl("Ventilator desfumare 2", P_kW=11, receptor="motor", siguranta=T),
                    pl("Clapete desfumare", P_kW=0.1, n_circuite=4, siguranta=T)]}),
 64: U({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 630, "schema_pamant": "TN-S",
        "plecari": [pl("Pompă incendiu", P_kW=45, receptor="motor", siguranta=T),
                    pl("Pompă tehnologică", P_kW=45, receptor="motor"),
                    pl("Iluminat", P_kW=10, receptor="iluminat")]}),
 1: U({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 400, "schema_pamant": "TN-S",
       "plecari": [pl("Iluminat hală LED", P_kW=3, n_circuite=6, receptor="iluminat"),
                   pl("Iluminat exterior", P_kW=2, receptor="iluminat"),
                   pl("Rampe de încărcare", P_kW=1.1, n_circuite=4, receptor="motor"),
                   pl("Uși secționale", P_kW=0.75, n_circuite=4, receptor="motor"),
                   pl("Centrală detecție incendiu", P_kW=0.5, siguranta=T),
                   pl("Prize de serviciu", In_A=16, n_circuite=6, receptor="prize"),
                   pl("TD birouri", P_kW=40, receptor="tablou")]}, [], ["hala depozitare 2400 mp, P+0"]),
 2: U({"tip_schema": "tablou", "origine": "tg_existent", "schema_pamant": "TN-S",
       "plecari": [pl("Strung CNC 1", P_kW=18.5, receptor="motor"), pl("Strung CNC 2", P_kW=18.5, receptor="motor"),
                   pl("Freză", P_kW=11, receptor="motor"), pl("Compresor șurub", P_kW=30, receptor="motor"),
                   pl("Iluminat", P_kW=6, receptor="iluminat")]}),
 4: U({"tip_schema": "tablou", "origine": "tg_existent", "titlu_tablou": "TE-Chiller", "schema_pamant": "TN-S",
       "L_alimentare_m": 60, "cablu": {"material": "Cu", "S_fortat": 120, "N_fortat": 70},
       "plecari": [pl("Compresor 1", P_kW=42, pornire="soft", receptor="motor"),
                   pl("Compresor 2", P_kW=42, pornire="soft", receptor="motor"),
                   pl("Pompă de circulație", P_kW=5.5, pornire="convertizor", receptor="motor"),
                   pl("Ventilatoare condensator", P_kW=1.5, n_circuite=4, receptor="motor")]}),
 5: U({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 250,
       "plecari": [pl("Pompă 1", P_kW=7.5, receptor="motor"), pl("Pompă 2", P_kW=7.5, receptor="motor"),
                   pl("Pompă 3", P_kW=7.5, receptor="motor")]}),
 7: U({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 250, "schema_pamant": "TN-S",
       "plecari": [pl("Compresor", P_kW=160, receptor="motor"), pl("Cuptor", P_kW=120),
                   pl("Iluminat", P_kW=20, receptor="iluminat")]},
      ["Plecările însumează 300 kW, iar PT-ul are 250 kVA: ce coeficient de simultaneitate are tabloul, sau trafo-ul e mai mare?"]),
 15: U({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 1000, "schema_pamant": "TN-S",
        "plecari": [pl("TD-A", In_A=250, receptor="tablou", copii=[
                        pl("TE-1", In_A=63, copii=[pl("Motor", P_kW=4, n_circuite=5, receptor="motor")]),
                        pl("TE-2", In_A=40, copii=[pl("Iluminat", P_kW=8, receptor="iluminat")])]),
                    pl("TD-B", In_A=160, receptor="tablou", copii=[
                        pl("Compresor", P_kW=45, receptor="motor"), pl("Prize", n_circuite=6, receptor="prize")])]},
       ["Ce calibru (A) sau putere au cele 6 circuite de prize din TD-B?"]),
 16: U({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 400, "schema_pamant": "TN-S",
        "titlu_tablou": "TGD",
        "plecari": [pl("TD-Hala1", In_A=125, receptor="tablou", copii=[
                        pl("TE-Linie1", copii=[pl("Motor 1", P_kW=5.5, receptor="motor"),
                                               pl("Motor 2", P_kW=5.5, receptor="motor"),
                                               pl("Motor 3", P_kW=5.5, receptor="motor")])])]}),
 17: U({"tip_schema": "pt", "Sn_kVA": 1600, "n_trafo": 2, "trafo_izolatie": "uscat", "U_MT_kV": 20, "cupla": "deschisa",
        "compensare_kvar": 300,
        "plecari": [pl("TD1", In_A=800, sectie=1), pl("TD2", In_A=630, sectie=1),
                    pl("TD3", In_A=800, sectie=2), pl("TD4", In_A=400, sectie=2),
                    pl("Chiller", P_kW=250, receptor="motor", sectie=2)]}, [],
       ["baterie 300 kvar pe semibara A"]),
 18: U({"tip_schema": "pt", "Sn_kVA": 1000, "trafo_izolatie": "ulei", "U_MT_kV": 10,
        "celule_mt": ["linie_intrare", "linie_iesire", "masura", "trafo"], "masura": "MT", "celula_trafo": "intreruptor",
        "In_Q_JT_A": 1600,
        "plecari": [pl(f"TD-{i}", In_A=250) for i in range(1, 7)]}, [], ["releu 50/51"]),
 22: U({"tip_schema": "pt", "Sn_kVA": 2000, "U_MT_kV": 6, "trafo_izolatie": "uscat", "celula_trafo": "intreruptor",
        "In_Q_JT_A": 3200, "plecari": [pl(f"TD-{i}", In_A=630) for i in range(1, 5)]}, [], ["stație 6 kV existentă"]),
 25: U({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 800, "schema_pamant": "TN-C-S", "L_alimentare_m": 90,
        "cablu": {"material": "Al", "izolatie": "XLPE", "S_fortat": 240, "N_fortat": 240, "n_paralel": 2},
        "plecari": [pl("TD1", In_A=400), pl("TD2", In_A=250)]}),
 26: U({"tip_schema": "tablou", "origine": "bmpt", "In_Q_amonte_A": 100, "schema_pamant": "TN-C-S",
        "plecari": [pl("Pompă", P_kW=7.5, L_m=80, receptor="motor", cablu={"material": "Cu", "S_fortat": 4}),
                    pl("Iluminat", P_kW=3, L_m=30, receptor="iluminat", retea="mono",
                       cablu={"material": "Cu", "S_fortat": 2.5}),
                    pl("Prize", n_circuite=3, receptor="prize")]},
       ["Ce calibru au cele 3 circuite de prize (ex. 16 A)?"]),
 27: U({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 1000, "schema_pamant": "TN-S",
        "compensare_kvar": 250, "plecari": [pl("TD1", In_A=400), pl("TD2", In_A=315)]}, [],
       ["filtru 7%, 8 trepte"]),
 28: U({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 630, "P_kW": 400, "cosfi": 0.78},
       ["Puterea bateriei de compensare (cosφ 0,78 → 0,95) nu o aleg eu din text: indicați bateria (kvar) și plecările "
        "TG-ului, sau folosiți calculul de compensare al aplicației."]),
 29: U({"tip_schema": "tablou", "origine": "tg_existent", "schema_pamant": "TN-S",
        "plecari": [pl("Motor 1", P_kW=7.46, receptor="motor"), pl("Motor 2", P_kW=7.46, receptor="motor"),
                    pl("Motor 3", P_kW=18.64, pornire="stea_triunghi", receptor="motor"),
                    pl("Macara 1", P_kW=5.5, receptor="motor"), pl("Macara 2", P_kW=5.5, receptor="motor")]}),
 30: U({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 630, "schema_pamant": "TN-S",
        "plecari": [pl("Chiller", P_kW=180, receptor="motor"),
                    pl("CTA 1", P_kW=22, pornire="convertizor", receptor="motor"),
                    pl("CTA 2", P_kW=22, pornire="convertizor", receptor="motor")]
                   + [pl(f"Pompă {i}", P_kW=3, receptor="motor") for i in range(1, 5)]
                   + [pl("Iluminat", P_kW=15, receptor="iluminat")]}),
 32: U({"tip_schema": "tablou", "origine": "tg_existent", "schema_pamant": "TN-S",
        "plecari": [pl("Pompă", P_kW=5.5, receptor="motor"), pl("Ventilator", P_kW=3, receptor="motor"),
                    pl("Iluminat", P_kW=2, receptor="iluminat"), pl("Prize", In_A=16, n_circuite=4, receptor="prize")]}),
}
# ------------------------------------------------------------------------------------------- locuințe
S["locuinte"] = {
 7: U({"tip_schema": "locuinta", "alimentare": {"tip": "bransament_nou"},
       "circuite": [{"nume": "Încălzire pardoseală baie 1", "receptor": "incalzire_electrica", "P_kW": 1.5},
                    {"nume": "Încălzire pardoseală baie 2", "receptor": "incalzire_electrica", "P_kW": 1.5},
                    {"nume": "Pompă de căldură", "receptor": "pompa_caldura"},
                    {"nume": "Aer condiționat etaj", "receptor": "aer_conditionat"}]},
      ["Branșamentul va fi trifazat? Ce putere aprobată se cere în ATR (20 sau 25 kW)?"]),
 17: U({"tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TN-C-S", "alimentare": {"P_aprobata_kW": 20},
        "circuite": [{"nume": "Plită", "receptor": "plita", "P_kW": 7.4, "faza": "3F"},
                     {"nume": "Cuptor", "receptor": "cuptor", "P_kW": 3.6},
                     {"nume": "Boiler", "receptor": "boiler", "P_kW": 2},
                     {"nume": "Pompă de căldură", "receptor": "pompa_caldura", "P_kW": 10, "faza": "3F"},
                     {"nume": "AC living", "receptor": "aer_conditionat", "P_kW": 2.5}]}),
 19: U({"tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TN-C-S", "alimentare": {"P_aprobata_kW": 16},
        "circuite": [{"nume": "Iluminat", "receptor": "iluminat", "P_kW": 1},
                     {"nume": "Prize", "receptor": "prize", "P_kW": 2},
                     {"nume": "Plită", "receptor": "plita", "P_kW": 7},
                     {"nume": "Încărcare VE", "receptor": "vehicul_electric", "P_kW": 22, "faza": "3F"}]},
       ["Stația VE de 22 kW depășește puterea aprobată de 16 kW: limitare la 11 kW / gestiune de sarcină, sau mărirea ATR?"]),
 46: U({"tip_schema": "locuinta", "retea": "mono", "schema_pamant": "TN-C-S", "alimentare": {"P_aprobata_kW": 9},
        "tablouri_secundare": [{"nume": "TD anexă (bucătărie de vară)", "L_m": 30,
                                "circuite": [pl("Prize", n_circuite=3, receptor="prize"),
                                             pl("Iluminat", receptor="iluminat"),
                                             pl("Plită", P_kW=3.5)]}]}, [], ["cu 3x6"]),
 4: U({"tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TT", "RA_ohm": 6,
       "alimentare": {"tip": "bransament_existent", "P_aprobata_kW": 25, "In_Q_bransament_A": 40},
       "circuite": [{"nume": "Wallbox garaj", "receptor": "vehicul_electric", "P_kW": 11, "L_m": 35, "faza": "3F"},
                    {"nume": "Ușă garaj", "receptor": "poarta_automata"}]},
      ["Desenez doar circuitele noi (wallbox, ușă garaj) adăugate în tabloul existent, sau tot tabloul casei?"]),
 6: U({"tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TN-C-S", "Ik3_OD_kA": 4.2, "Zb_OD_ohm": 0.45,
       "alimentare": {"P_aprobata_kW": 11, "L_coloana_m": 28, "cablu": {"metoda": "D1"}},
       "circuite": [{"nume": "Pompă de căldură", "receptor": "pompa_caldura"}]}, [], [], {"judet": "Bihor"}),
 22: U({"tip_schema": "prosumator", "retea": "tri", "schema_pamant": "TN-C-S", "P_aprobata_kW": 14, "P_evacuata_kW": 10,
        "Pn_inv_kW": 10, "Ik3_OD_kA": 6}),
 37: U({"tip_schema": "bransament", "retea": "tri", "P_kW": 15},
       ["Desenez și tabloul de șantier: câte prize 400 V și 230 V, cu ce calibre?"]),
 41: U({"tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TN-C-S", "alimentare": {"P_aprobata_kW": 22},
        "circuite": [{"nume": "Stație încărcare VE 1", "receptor": "vehicul_electric", "P_kW": 11, "faza": "3F"},
                     {"nume": "Stație încărcare VE 2", "receptor": "vehicul_electric", "P_kW": 11, "faza": "3F"}]},
       [], ["cu load balancing"]),
 45: U({"tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TN-C-S", "alimentare": {"P_aprobata_kW": 20},
        "tablouri_secundare": [{"nume": "TE etaj", "L_m": 20,
                                "circuite": [pl("Iluminat", n_circuite=2, receptor="iluminat"),
                                             pl("Prize", n_circuite=4, receptor="prize"),
                                             pl("Aer condiționat", n_circuite=2)]}]}, [], ["cablu 5x6"]),
 5: U({"tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TN-C-S", "alimentare": {"P_aprobata_kW": 20},
       "circuite": [{"nume": "Pompă de căldură", "receptor": "pompa_caldura", "P_kW": 12, "faza": "3F"},
                    {"nume": "Plită inducție", "receptor": "plita"}, {"nume": "Cuptor", "receptor": "cuptor"},
                    {"nume": "Încărcare VE", "receptor": "vehicul_electric", "P_kW": 11},
                    {"nume": "Aer condiționat 1", "receptor": "aer_conditionat"},
                    {"nume": "Aer condiționat 2", "receptor": "aer_conditionat"}]}),
 30: U({"tip_schema": "locuinta", "retea": "mono", "schema_pamant": "TN-C-S", "alimentare": {"In_Q_bransament_A": 32},
        "circuite": [{"nume": "Iluminat", "receptor": "iluminat"}, {"nume": "Prize", "receptor": "prize"},
                     {"nume": "Boiler", "receptor": "boiler"}]}),
 9: U({"tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TT", "alimentare": {"P_aprobata_kW": 15}}),
 12: U({"tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TT", "RA_ohm": 10, "alimentare": {"P_aprobata_kW": 22}}),
 18: U({"tip_schema": "locuinta", "retea": "mono", "schema_pamant": "TN-C-S", "alimentare": {"P_aprobata_kW": 9},
        "circuite": [{"nume": "Iluminat parter", "receptor": "iluminat", "P_kW": 0.8, "L_m": 25},
                     {"nume": "Iluminat etaj", "receptor": "iluminat", "P_kW": 0.6, "L_m": 30},
                     {"nume": "Prize bucătărie", "receptor": "prize_bucatarie", "P_kW": 3.5, "L_m": 15},
                     {"nume": "Mașină de spălat", "receptor": "masina_spalat_rufe", "P_kW": 2.2, "L_m": 12},
                     {"nume": "Boiler", "receptor": "boiler", "P_kW": 2, "L_m": 18}]}),
 21: U({"tip_schema": "locuinta", "retea": "mono", "schema_pamant": "TN-C-S", "alimentare": {"P_aprobata_kW": 7},
        "circuite": [{"nume": f"AC split {i}", "receptor": "aer_conditionat", "P_kW": 1.2} for i in range(1, 5)]
                    + [{"nume": f"Prize cameră {i}", "receptor": "prize"} for i in range(1, 6)]
                    + [{"nume": f"Iluminat {i}", "receptor": "iluminat"} for i in range(1, 4)]}),
 24: U({"tip_schema": "prosumator", "retea": "tri", "schema_pamant": "TN-C-S", "P_aprobata_kW": 30, "P_evacuata_kW": 30,
        "In_Q_bransament_A": 50, "racord": "bmpt", "Pn_inv_kW": 30}, [], [], {"localitate": "Oradea"}),
 27: U({"tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TN-C-S", "alimentare": {"P_aprobata_kW": 16},
        "circuite": [{"nume": "Pompă de căldură", "receptor": "pompa_caldura", "P_kW": 8},
                     {"nume": "Încărcare VE", "receptor": "vehicul_electric", "P_kW": 7.4, "faza": "L1"},
                     {"nume": "Aer condiționat 1", "receptor": "aer_conditionat"},
                     {"nume": "Aer condiționat 2", "receptor": "aer_conditionat"}]}),
 34: U({"tip_schema": "locuinta", "retea": "mono", "schema_pamant": "TT", "alimentare": {"P_aprobata_kW": 7}},
       ["Legarea PE la nul în tablou la o schemă TT nu e permisă (conductorul de protecție devine activ la o întrerupere a "
        "nulului). Declanșările DDR se rezolvă căutând defectul de izolație / verificând RA. Generez schema TT corectă?"]),
 39: U({"tip_schema": "locuinta", "retea": "mono", "schema_pamant": "TN-C-S", "alimentare": {"P_aprobata_kW": 10},
        "circuite": [{"nume": "Pompă de căldură", "receptor": "pompa_caldura", "P_kW": 16, "faza": "L1"}]},
       ["Pompa de căldură monofazată de 16 kW depășește puterea aprobată de 10 kW și limita unui branșament monofazat: "
        "treceți pe trifazat (și pompă trifazată) sau o pompă mai mică?"]),
}

# v2 — DUPĂ ajustarea promptului (regula 5: Pn din catalog când nu e scris, „N x PCS”; schema: bess.n_pcs,
# tablouri_secundare[].cablu). NU mai e „orb”: rescrise după ce s-au văzut rezultatele așteptate — doar frazele atinse.
V2 = {"fotovoltaic": {
 33: U({"tip_schema": "prosumator", "retea": "tri", "schema_pamant": "TN-S", "Pn_inv_kW": 24.6,
        "invertoare": [dict(inv(1, 8.2, "Fronius", "Primo 8.2-1"), faza=f) for f in ("L1", "L2", "L3")]}),
 7: U({"tip_schema": "cef", "kWp": 2000, "invertoare": [{"n": 8, "producator": "Huawei", "model": "SUN2000-330KTL-H1"}],
       "pt_Sn_kVA": 2500, "pt_existent": F, "U_MT_kV": 20, "U_ca_V": 800, "masura": "MT"}),
 13: U({"tip_schema": "cef", "bess": {"P_kW": 1000, "kWh": 2000, "n_pcs": 4}, "pt_Sn_kVA": 1250, "pt_existent": F,
        "U_MT_kV": 20, "masura": "MT"}),
 45: U({"tip_schema": "cef", "kWp": 2000, "invertoare": [inv(20, 100)], "bess": {"P_kW": 2000, "kWh": 4000, "n_pcs": 8},
        "pt_Sn_kVA": 2000, "n_trafo": 2, "pt_existent": F, "masura": "MT", "limitare_injectie_kW": 3000}),
}, "locuinte": {
 46: U({"tip_schema": "locuinta", "retea": "mono", "schema_pamant": "TN-C-S", "alimentare": {"P_aprobata_kW": 9},
        "tablouri_secundare": [{"nume": "TD anexă (bucătărie de vară)", "L_m": 30, "cablu": {"S_fortat": 6, "material": "Cu"},
                                "circuite": [pl("Prize", n_circuite=3, receptor="prize"),
                                             pl("Iluminat", receptor="iluminat"),
                                             pl("Plită", P_kW=3.5)]}]}),
}}

if __name__ == "__main__":
    out = {"_nota": "SIMULARE — nu e un apel real la API. Ieșirile uneltei intrare_fizica au fost scrise de Claude "
                    "(Opus 5.5, sesiunea de dezvoltare) în rolul modelului care primește DOAR promptul de sistem + schema "
                    "+ fraza, înainte de a citi rezultatele așteptate. Scorul obținut cu ele este o estimare.",
           "raspunsuri": {d: {str(k): v for k, v in x.items()} for d, x in S.items()},
           "_nota_v2": "raspunsuri_v2: aceleași, cu frazele atinse de ajustarea promptului rescrise DUPĂ ce s-au văzut "
                       "rezultatele așteptate (nu e o măsurătoare oarbă).",
           "raspunsuri_v2": {d: {str(k): v for k, v in x.items()} for d, x in V2.items()}}
    p = pathlib.Path(__file__).with_name("llm_simulat.json")
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("scris", p, sum(len(x) for x in S.values()))
