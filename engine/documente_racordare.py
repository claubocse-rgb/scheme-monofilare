"""documente_racordare — dosarul de racordare al prosumatorului / producătorului, precompletat din datele proiectului (E2).

Documente (fiecare ca .docx și PDF): cererea de racordare (Ord. ANRE 19/2022 anexa 1 / notificarea anexa 2; pentru CEF
care nu e prosumator — cererea după Ord. ANRE 59/2013), fișa tehnică a instalației de producere, lista echipamentelor
cu certificatele cerute, declarația de conformitate a instalatorului (model) + schema monofilară (PDF-ul planșei).

Date suplimentare (opționale) în `dosar` (în corpul cererii sau în intrarea fizică):
    {"tip_cerere": "nou" | "existent" | "notificare",
     "solicitant": {"nume", "cnp_cui", "reg_com", "adresa", "telefon", "email", "reprezentant", "iban"},
     "loc": {"judet", "localitate", "strada", "nr", "cf", "nr_cadastral"},
     "cod_loc_consum", "nr_atr", "P_aprobata_kW", "data_pif", "OD",
     "instalator": {"firma", "atestat_tip", "atestat_nr", "electrician", "grad", "legitimatie"}}
Tot ce lipsește apare „de completat” (galben); ce vine din proiect apare pe fond albastru.
"""
import io
import zipfile

from .documente_doc import Document, Camp, camp
from .sabloane import racordare as S
from . import documente_tabele as dt


def _g(d, *chei):
    for k in chei:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def echipamente(m):
    """echipamentele planșei (fără noduri / cutii), agregate pe (tip, text) → [{ref[], tip, denumire, caracteristici,
    producator, model, buc, param}]"""
    out = {}

    def ad(a):
        if not isinstance(a, dict) or not a.get("tip") or a.get("tip") in ("nod", "cutie") or not a.get("lista"):
            return
        if a.get("existent"):
            return
        lst = [dt._n(x) for x in a.get("lista") or []]
        k = (a["tip"], tuple(lst))
        e = out.setdefault(k, {"ref": [], "tip": a["tip"], "denumire": lst[0] if lst else "", "caracteristici": " · ".join(lst[1:]),
                               "producator": (a.get("param") or {}).get("producator"), "model": (a.get("param") or {}).get("model"),
                               "buc": 0, "param": a.get("param") or {}})
        if a.get("ref"):
            e["ref"].append(a["ref"])
        e["buc"] += int(a.get("buc") or 1) if isinstance(a.get("buc"), (int, float)) else 1

    def walk(o):
        if isinstance(o, dict):
            if "tip" in o and "lista" in o:
                ad(o)
            for k, v in o.items():
                if k not in ("lista", "spec", "param", "note", "cartus", "calc", "calc_rezumat", "tabel_pi"):
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk({k: m.get(k) for k in ("intrari", "bara", "plecari")})
    return list(out.values())


def date_proiect(corp, m, r):
    """datele folosite de formulare, din: corpul cererii (dosar, profil), cartuș, intrarea fizică, calcul, planșă"""
    corp = corp if isinstance(corp, dict) else {}
    inp = m.get("calc") or corp.get("calc") or {}
    k = m.get("cartus") or {}
    rz = (r or {}).get("rezultat") or {}
    dos = corp.get("dosar") if isinstance(corp.get("dosar"), dict) else (inp.get("dosar") if isinstance(inp.get("dosar"), dict) else {})
    sume = rz.get("sume") or {}
    ech = echipamente(m)
    inv = [e for e in ech if e["tip"] == "invertor"]
    pv = [e for e in ech if e["tip"] == "string_pv"]
    bat = [e for e in ech if e["tip"] in ("baterie",)]
    pcs = [e for e in ech if e["tip"] == "convertor_bess"]
    kwp = inp.get("kWp") or sum(float(e["param"].get("kWp") or 0) for e in pv) or None
    bess = inp.get("bess") if isinstance(inp.get("bess"), dict) else {}
    tip = inp.get("tip_schema")
    prosumator = tip == "prosumator" or bool(dos.get("prosumator"))      # CEF pe locul de consum declarată prosumator
    tc = dos.get("tip_cerere") or ("notificare" if tip == "prosumator" and inp.get("P_aprobata_kW") and
                                   (sume.get("Pn_total_kW") or 0) <= float(inp.get("P_aprobata_kW") or 0) else "existent"
                                   if tip == "prosumator" else "producator")
    return {"inp": inp, "cartus": k, "rez": rz, "dosar": dos, "tip": tip, "prosumator": prosumator,
            "tip_cerere": tc, "echipamente": ech, "invertoare": inv, "pv": pv, "baterii": bat, "pcs": pcs,
            "kWp": kwp, "Pn_kW": sume.get("Pn_total_kW") or sume.get("Pn_invertoare_kW"),
            "Pn_inv_kW": sume.get("Pn_invertoare_kW") or sume.get("Pn_total_kW"),
            "P_injectabila_kW": sume.get("P_injectabila_kW") or (rz.get("limitare_injectie") or {}).get("P_kW")
            or inp.get("limitare_injectie_kW") or sume.get("Pn_total_kW"),
            "Iac_A": sume.get("Iac_total_A"), "S_kVA": sume.get("S_total_kVA"),
            "bess_kWh": bess.get("kWh") or inp.get("baterie_kWh") or (rz.get("bess_date") or {}).get("kWh"),
            "bess_kW": bess.get("P_kW") or (rz.get("bess_date") or {}).get("P_kW"),
            "retea": "trifazată 3 × 400/230 V" if (inp.get("retea") or "tri") == "tri" else "monofazată 230 V",
            "schema_pamant": rz.get("schema_pamant") or inp.get("schema_pamant"),
            "racord": rz.get("racord"), "PI": rz.get("PI"), "contor": rz.get("contor"),
            "QG": rz.get("QG"), "tabel_pi": m.get("tabel_pi"), "limitare_PCC": rz.get("limitare_PCC"),
            "P_aprobata_kW": dos.get("P_aprobata_kW") or inp.get("P_aprobata_kW")}


def _antet(d):
    k = d["cartus"]
    return " · ".join(x for x in (k.get("proiectant"), f"Proiect nr. {k['nr_pr']}" if k.get("nr_pr") else "",
                                  k.get("denumire2")) if x)


def _adresa_loc(d):
    loc = d["dosar"].get("loc") if isinstance(d["dosar"].get("loc"), dict) else {}
    if loc:
        return ", ".join(x for x in (f"jud. {loc['judet']}" if loc.get("judet") else "", loc.get("localitate"),
                                     f"str. {loc['strada']}" if loc.get("strada") else "", f"nr. {loc['nr']}" if loc.get("nr") else "") if x)
    return d["cartus"].get("adresa") or None


def _fmt_kw(x):
    return camp(round(float(x), 2) if isinstance(x, (int, float)) else None, "kW")


def cerere_racordare(d):
    tc = d["tip_cerere"]
    sol = d["dosar"].get("solicitant") if isinstance(d["dosar"].get("solicitant"), dict) else {}
    loc = d["dosar"].get("loc") if isinstance(d["dosar"].get("loc"), dict) else {}
    pros = d["prosumator"]
    doc = Document(S.TITLU_CERERE.get(tc, "CERERE DE RACORDARE"),
                   S.ANEXA.get(tc if pros else "producator", S.ANEXA["producator"]), _antet(d))
    doc.legenda()
    doc.p("Către: ", camp(d["dosar"].get("OD")), " (operatorul de distribuție)")
    doc.p("Subsemnatul / Subscrisa ", camp(sol.get("nume") or d["cartus"].get("beneficiar")),
          ", CNP / CUI ", camp(sol.get("cnp_cui")), ", nr. de înregistrare la ONRC ", camp(sol.get("reg_com")),
          ", cu domiciliul / sediul în ", camp(sol.get("adresa")), ", telefon ", camp(sol.get("telefon")), ", e-mail ",
          camp(sol.get("email")), ", reprezentat(ă) prin ", camp(sol.get("reprezentant")),
          ", solicit ", Camp(S.OBIECT_CERERE.get(tc if pros else "producator")), " situat la adresa:")
    doc.campuri([("Județ", camp(loc.get("judet"))), ("Localitate", camp(loc.get("localitate"))),
                 ("Strada, nr.", camp(" ".join(str(x) for x in (loc.get("strada"), loc.get("nr")) if x) or None)),
                 ("Nr. carte funciară / nr. cadastral", camp(" / ".join(str(x) for x in (loc.get("cf"), loc.get("nr_cadastral")) if x) or None)),
                 ("Adresa din proiect (cartuș)", camp(d["cartus"].get("adresa"))),
                 ("Cod loc de consum / nr. ATR existent", camp(d["dosar"].get("cod_loc_consum") or d["dosar"].get("nr_atr")
                                                              or d["cartus"].get("atr"))),
                 ("Data estimată pentru punerea sub tensiune finală", camp(d["dosar"].get("data_pif")))])
    doc.h("1. Locul de consum", 2)
    doc.campuri([("Puterea aprobată existentă (consum)", _fmt_kw(d.get("P_aprobata_kW"))),
                 ("Tipul racordului", Camp(d["retea"])),
                 ("Puterea maximă absorbită solicitată", camp(None)),
                 ("Schema de legare la pământ", camp(d.get("schema_pamant")))])
    doc.h("2. Locul de producere", 2)
    doc.campuri([("Puterea instalată în module (c.c.)", camp(d.get("kWp"), "kWp")),
                 ("Puterea instalată a invertoarelor (c.a.)", _fmt_kw(d.get("Pn_inv_kW"))),
                 ("Puterea maximă evacuată (injectată) solicitată", _fmt_kw(d.get("P_injectabila_kW"))),
                 ("Limitarea puterii la punctul de racord", camp(f"{dt._f(d['limitare_PCC']['P_kW'])} kW (EMS + analizor la PCC)"
                                                                 if (d.get("limitare_PCC") or {}).get("P_kW") else
                                                                 f"injecție limitată la {dt._f(d['inp']['limitare_injectie_kW'])} kW (EMS)"
                                                                 if d["inp"].get("limitare_injectie_kW") is not None else
                                                                 "nu este prevăzută")),
                 ("Consum servicii proprii", camp(None)),
                 ("Compensare de putere reactivă", Camp("nu (invertoarele asigură Q reglabil)"))])
    if d["invertoare"]:
        doc.p("Invertoare:")
        doc.tabel(["Nr. buc.", "Producător", "Model", "Pn [kW]", "Iac,max [A]", "Certificare"],
                  [[camp(e["buc"]), camp(e["producator"]), camp(e["model"]), camp(e["param"].get("Pn_kW")),
                    camp(round(e["param"]["Iac_max_A"], 1) if e["param"].get("Iac_max_A") else None),
                    camp(e["param"].get("certificare"))] for e in d["invertoare"]])
    if d["pv"]:
        doc.p("Panouri fotovoltaice:")
        doc.tabel(["Producător", "Model", "Pmax [Wp]", "Nr. module", "P totală [kWp]"],
                  [[camp(e["producator"]), camp(e["model"]), camp(e["param"].get("Pmax_W")),
                    camp(round(float(e["param"]["kWp"]) * 1000 / float(e["param"]["Pmax_W"])) if e["param"].get("Pmax_W")
                         and e["param"].get("kWp") else None), camp(e["param"].get("kWp"))] for e in d["pv"]])
    doc.h("3. Stocare", 2)
    doc.campuri([("Sistem de stocare", Camp("da") if d.get("bess_kWh") or d["baterii"] else Camp("nu")),
                 ("Capacitate [kWh]", camp(d.get("bess_kWh"))), ("Putere [kW]", camp(d.get("bess_kW"))),
                 ("Capacitate [Ah]", camp(None)),
                 ("Schema de alimentare a bateriei", camp("conform schemei monofilare anexate" if d.get("bess_kWh") or d["baterii"] else None))])
    doc.h("4. Măsurare", 2)
    doc.campuri([("Grup de măsurare existent", camp(None)), ("Serie / tip contor", camp(None)),
                 ("Contor prevăzut în proiect", camp(d.get("contor") or "bidirecțional, furnizat de OD"))])
    doc.h("5. Documente anexate", 2)
    cand = "nou" if tc == "nou" else "existent"
    doc.lista([f"{lit}) {txt}" for lit, txt, c in S.DOCUMENTE_ANEXATE if c in ("ambele", cand)]
              + ["schema electrică monofilară (planșa " + (d["cartus"].get("plansa") or "E01") + ") — anexată în dosar"])
    doc.p("Declar pe propria răspundere că datele de mai sus sunt corecte și că documentele anexate în copie sunt "
          "conforme cu originalul.")
    doc.campuri([("Data", camp(None)), ("Semnătura solicitantului", camp(None))])
    doc.p(f"Temei: {S.TEMEI_PROSUMATOR if d['prosumator'] else S.TEMEI_PRODUCATOR}. Model verificat la "
          f"{S.VERIFICAT_LA}; se verifică macheta OD înainte de depunere.", stil="mic")
    return doc


def cerere_consum(d):
    """cererea de racordare a unui loc de CONSUM (branșament / locuință / tablou) — Ord. ANRE 59/2013, anexa cererii
    de racordare: date solicitant, loc, puteri, tip racord, receptoare principale, documente anexate"""
    sol = d["dosar"].get("solicitant") if isinstance(d["dosar"].get("solicitant"), dict) else {}
    loc = d["dosar"].get("loc") if isinstance(d["dosar"].get("loc"), dict) else {}
    rz, inp = d["rez"], d["inp"]
    bil = rz.get("bilant") if isinstance(rz.get("bilant"), dict) else {}
    alim = rz.get("alimentare") if isinstance(rz.get("alimentare"), dict) else {}
    al_in = inp.get("alimentare") if isinstance(inp.get("alimentare"), dict) else {}
    p_cer = bil.get("Pc_kW") or rz.get("Pa_kW") or inp.get("P_kW") or al_in.get("P_aprobata_kW")
    doc = Document("CERERE DE RACORDARE — LOC DE CONSUM", "conform " + S.TEMEI_PRODUCATOR.split(" — ")[0]
                   + " (Regulamentul de racordare)", _antet(d))
    doc.legenda()
    doc.p("Către: ", camp(d["dosar"].get("OD")), " (operatorul de distribuție)")
    doc.p("Subsemnatul / Subscrisa ", camp(sol.get("nume") or d["cartus"].get("beneficiar")), ", CNP / CUI ",
          camp(sol.get("cnp_cui")), ", cu domiciliul / sediul în ", camp(sol.get("adresa")), ", telefon ",
          camp(sol.get("telefon")), ", e-mail ", camp(sol.get("email")),
          ", solicit racordarea la rețeaua electrică de interes public a locului de consum situat la adresa:")
    doc.campuri([("Județ / localitate", camp(" / ".join(x for x in (loc.get("judet"), loc.get("localitate")) if x) or None)),
                 ("Strada, nr.", camp(" ".join(str(x) for x in (loc.get("strada"), loc.get("nr")) if x) or None)),
                 ("Adresa din proiect (cartuș)", camp(d["cartus"].get("adresa"))),
                 ("Tipul cererii", camp(d["dosar"].get("tip_cerere_consum") or None)),
                 ("Cod loc de consum / ATR existent", camp(d["dosar"].get("cod_loc_consum") or d["cartus"].get("atr")))])
    doc.h("Date tehnice", 2)
    doc.campuri([("Puterea maximă simultan absorbită solicitată", _fmt_kw(p_cer)),
                 ("Puterea instalată", _fmt_kw(bil.get("Pi_kW"))),
                 ("Tipul racordului", Camp(d["retea"])),
                 ("Blocul de măsură și protecție / Q branșament", camp(" · ".join(str(x) for x in (
                     rz.get("bloc"), f"Q {(rz.get('Q') or {}).get('In_A')} A" if (rz.get("Q") or {}).get("In_A") else None,
                     f"Q {alim.get('Q', {}).get('In_A')} A" if isinstance(alim.get("Q"), dict) and alim["Q"].get("In_A") else None) if x) or None)),
                 ("Schema de legare la pământ", camp(d.get("schema_pamant"))),
                 ("Receptoare cu regim special (motoare, sudură, VE, pompe de căldură)", camp(None)),
                 ("Data estimată pentru punerea sub tensiune", camp(d["dosar"].get("data_pif")))])
    doc.h("Documente anexate", 2)
    doc.lista(["copia actului de identitate / certificatului de înregistrare", "certificatul de urbanism (loc nou)",
               "planul de situație / de încadrare în zonă", "documentul de proprietate sau de folosință",
               "schema electrică monofilară (planșa " + (d["cartus"].get("plansa") or "E01") + ")"])
    doc.p("Declar pe propria răspundere că datele de mai sus sunt corecte.")
    doc.campuri([("Data", camp(None)), ("Semnătura solicitantului", camp(None))])
    return doc


def fisa_tehnica(d):
    doc = Document("FIȘA TEHNICĂ A INSTALAȚIEI DE PRODUCERE", d["cartus"].get("denumire2") or "", _antet(d))
    doc.legenda()
    doc.h("1. Date generale", 2)
    doc.campuri([("Beneficiar", camp(d["cartus"].get("beneficiar"))), ("Amplasament", camp(_adresa_loc(d))),
                 ("Tipul instalației", Camp("prosumator — instalație de producere pe locul de consum" if d["prosumator"]
                                            else "centrală electrică fotovoltaică (CEF)" + (" cu stocare" if d.get("bess_kWh") else ""))),
                 ("Proiect", camp(" · ".join(x for x in (d["cartus"].get("nr_pr"), d["cartus"].get("denumire2")) if x) or None)),
                 ("Proiectant / atestat ANRE", camp(" · ".join(x for x in (d["cartus"].get("proiectant"), d["cartus"].get("atestat_tip"),
                                                                          d["cartus"].get("atestat_anre")) if x) or None)),
                 ("Rețeaua / schema de legare la pământ", Camp(f"{d['retea']} · {d.get('schema_pamant') or '—'}"))])
    doc.h("2. Puteri", 2)
    doc.campuri([("Puterea instalată c.c. (module)", camp(d.get("kWp"), "kWp")),
                 ("Puterea nominală c.a. (Σ invertoare / PCS)", _fmt_kw(d.get("Pn_kW"))),
                 ("Curentul maxim debitat (Σ Iac,max)", camp(round(d["Iac_A"], 1) if d.get("Iac_A") else None, "A")),
                 ("Puterea aparentă maximă", camp(round(d["S_kVA"], 1) if d.get("S_kVA") else None, "kVA")),
                 ("Puterea maximă injectată în rețea", _fmt_kw(d.get("P_injectabila_kW"))),
                 ("Puterea aprobată la locul de consum", _fmt_kw(d.get("P_aprobata_kW"))),
                 ("Raport c.c./c.a.", camp(round(float(d["kWp"]) / float(d["Pn_inv_kW"]), 2) if d.get("kWp") and d.get("Pn_inv_kW") else None))])
    doc.h("3. Unități generatoare și stocare", 2)
    rows = [[Camp("invertor"), camp(e["buc"]), camp(" ".join(x for x in (e["producator"], e["model"]) if x) or None),
             camp(e["param"].get("Pn_kW"), "kW"), camp(e["caracteristici"])] for e in d["invertoare"]]
    rows += [[Camp("BESS / PCS"), camp(e["buc"]), camp(" ".join(x for x in (e["producator"], e["model"]) if x) or None),
              camp(e["param"].get("Pn_kW"), "kW"), camp(e["caracteristici"])] for e in d["pcs"]]
    rows += [[Camp("baterie"), camp(e["buc"]), camp(" ".join(x for x in (e["producator"], e["model"]) if x) or None),
              camp(e["param"].get("kWh"), "kWh"), camp(e["caracteristici"])] for e in d["baterii"]]
    rows += [[Camp("module PV"), camp(e["buc"]), camp(" ".join(x for x in (e["producator"], e["model"]) if x) or None),
              camp(e["param"].get("kWp"), "kWp"), camp(e["caracteristici"])] for e in d["pv"]]
    doc.tabel(["Echipament", "Buc.", "Producător / model", "Putere", "Caracteristici"], rows or [[camp(None)] * 5])
    doc.h("4. Racordare, protecții și măsurare", 2)
    rac = d.get("racord") if isinstance(d.get("racord"), dict) else {"tip": d.get("racord")} if d.get("racord") else {}
    qg = d.get("QG") or {}
    doc.campuri([("Modul de racordare", camp(rac.get("tip"))),
                 ("Punctul de delimitare / racordare", camp(d["dosar"].get("punct_delimitare"))),
                 ("Întreruptorul general al instalației de producere (QG)",
                  camp(" ".join(str(x) for x in (qg.get("tip"), qg.get("poli"), f"In {qg['In_A']} A" if qg.get("In_A") else "",
                                                 f"Ir {dt._f(qg['Ir_A'])} A" if qg.get("Ir_A") else "",
                                                 f"Icu {qg['Icu_kA']} kA" if qg.get("Icu_kA") else "") if x) or None)),
                 ("Protecția de interfață", camp(d.get("PI"))),
                 ("Contor", camp(d.get("contor") or "bidirecțional, furnizat de OD")),
                 ("Limitarea puterii la PCC", camp(f"{dt._f(d['limitare_PCC']['P_kW'])} kW — EMS / controller de putere, TC + "
                                                   f"analizor la PCC" if (d.get("limitare_PCC") or {}).get("P_kW") else None))])
    pi = d.get("tabel_pi")
    if isinstance(pi, dict) and pi.get("randuri"):
        doc.p("Reglajele protecției de interfață (" + (pi.get("sursa") or "") + "):")
        doc.tabel(["Funcția", "Prag", "Temporizare"], [[Camp(x) for x in r[:3]] for r in pi["randuri"]])
    doc.semnaturi("Proiectant", "Beneficiar")
    return doc


def lista_certificate(d):
    doc = Document("LISTA ECHIPAMENTELOR ȘI A CERTIFICATELOR", d["cartus"].get("denumire2") or "", _antet(d))
    doc.legenda()
    doc.p("Echipamentele instalației de producere și ale instalației de utilizare asociate, cu documentele de "
          "conformitate care se anexează dosarului (Ord. ANRE nr. 19/2022, art. 19 lit. c).")
    rows = []
    prior = ("invertor", "convertor_bess", "baterie", "string_pv", "releu_pi", "spd_cc", "gpv", "separator_cc", "spd",
             "mccb", "acb", "mcb", "rcbo", "rccb", "contor")
    for i, e in enumerate(sorted([e for e in d["echipamente"] if e["tip"] in S.CERTIFICATE],
                                 key=lambda e: prior.index(e["tip"]) if e["tip"] in prior else 99), 1):
        rows.append([Camp(str(i)), Camp(", ".join(e["ref"]) or "—"), Camp(e["denumire"]), camp(e["buc"]),
                     camp(" ".join(x for x in (e["producator"], e["model"]) if x) or None),
                     Camp(S.CERTIFICATE[e["tip"]]), camp(None)])
    doc.tabel(["Nr.", "Ref.", "Echipament", "Buc.", "Producător / model", "Documente de conformitate cerute",
               "Nr. / data certificatului"], rows)
    doc.h("Dosarul instalației de utilizare", 2)
    doc.lista(S.DOSAR_INSTALATIE)
    return doc


def declaratie_instalator(d):
    ins = d["dosar"].get("instalator") if isinstance(d["dosar"].get("instalator"), dict) else {}
    doc = Document("DECLARAȚIE DE CONFORMITATE A INSTALAȚIEI ELECTRICE", "(model — se completează de executantul atestat ANRE)",
                   _antet(d))
    doc.legenda()
    val = iter([ins.get("electrician"), ins.get("grad"), ins.get("legitimatie"), ins.get("firma"), ins.get("atestat_tip"),
                ins.get("atestat_nr"), _adresa_loc(d), d["cartus"].get("beneficiar"), d["cartus"].get("nr_pr"),
                d["cartus"].get("proiectant")])
    doc.p(*[x if x is not None else camp(next(val)) for x in S.DECLARATIE_INSTALATOR])
    doc.p("Instalația cuprinde: ", camp(d["cartus"].get("denumire2")), ", putere instalată ", _fmt_kw(d.get("Pn_kW")),
          (", " if d.get("kWp") else ""), camp(d.get("kWp"), "kWp") if d.get("kWp") else "", ".")
    doc.p("Au fost efectuate următoarele verificări și încercări, cu rezultate corespunzătoare (buletinele sunt anexate):")
    doc.tabel(["Verificarea", "Rezultat / buletin nr."], [[Camp(v), camp(None)] for v in S.VERIFICARI_INSTALATOR])
    doc.campuri([("Data", camp(None)), ("Executant (firma, atestat)", camp(" ".join(x for x in (ins.get("firma"), ins.get("atestat_tip"),
                                                                                              ins.get("atestat_nr")) if x) or None))])
    doc.semnaturi("Electrician autorizat ANRE", "Reprezentantul executantului")
    return doc


def dosar(corp, m, r):
    """[(nume_fișier_fără_extensie, Document)] + datele folosite"""
    d = date_proiect(corp, m, r)
    docs = [("01_Cerere_de_racordare", cerere_racordare(d)), ("02_Fisa_tehnica_instalatie_producere", fisa_tehnica(d)),
            ("03_Lista_echipamente_si_certificate", lista_certificate(d)),
            ("04_Declaratie_conformitate_instalator", declaratie_instalator(d))]
    return docs, d


def rezumat(corp, m, r):
    """pentru interfață: lista documentelor + câte câmpuri sunt completate / de completat"""
    docs, d = dosar(corp, m, r)
    return {"tip_cerere": d["tip_cerere"], "prosumator": d["prosumator"],
            "documente": [{"fisier": n, "titlu": doc.titlu, **doc.numar_campuri()} for n, doc in docs],
            "temei": S.TEMEI_PROSUMATOR if d["prosumator"] else S.TEMEI_PRODUCATOR, "verificat_la": S.VERIFICAT_LA}


def dosar_zip(corp, m, r, nume="Dosar_racordare", pdf=None, plansa_pdf=None):
    """arhiva dosarului: fiecare document .docx (sau .html dacă python-docx lipsește) + .pdf (dacă există convertor)"""
    docs, d = dosar(corp, m, r)
    bio = io.BytesIO()
    lista = []
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        for n, doc in docs:
            try:
                z.writestr(f"{n}.docx", doc.docx())
                lista.append(f"{n}.docx")
            except ImportError:
                z.writestr(f"{n}.html", doc.html())
                lista.append(f"{n}.html")
            if pdf:
                try:
                    z.writestr(f"{n}.pdf", pdf(doc.html()))
                    lista.append(f"{n}.pdf")
                except Exception:
                    pass
        if plansa_pdf:
            z.writestr("05_Schema_monofilara.pdf", plansa_pdf)
            lista.append("05_Schema_monofilara.pdf")
        z.writestr("CITESTE.txt", "\n".join(
            [f"Dosar de racordare — {d['cartus'].get('denumire2', '')}", "",
             "Câmpurile pe fond albastru au fost completate automat din datele proiectului — verificați-le.",
             "Câmpurile pe fond galben „(de completat)” se completează manual înainte de depunere / semnare.", "",
             f"Temei: {S.TEMEI_PROSUMATOR if d['prosumator'] else S.TEMEI_PRODUCATOR}",
             f"Model verificat la {S.VERIFICAT_LA}; formularul OD poate avea o machetă proprie — verificați-o.", ""]
            + [f"- {x}" for x in lista]))
    return bio.getvalue()
