"""documente_caiet — caietul de sarcini generat din lista de echipamente a planșei și din calcul (E2, #10).

Structura: 1 Generalități · 2 Standarde și normative · 3 Materiale și echipamente — caracteristici minime (neutre de
marcă: producătorul / modelul din fișe devin „sau echivalent”) · 4 Execuția lucrărilor · 5 Verificări și probe ·
6 Recepția · 7 Punerea în funcțiune · 8 Documentația as-built. Anexe: tabelul de cabluri și fișa de reglaje.
"""
import re

from .documente_doc import Document, Camp, camp
from .sabloane import caiet_sarcini as S
from . import documente_tabele as dt
from .documente_racordare import echipamente, _antet

TIPURI_CAIET = {"mcb", "mccb", "acb", "rccb", "rcbo", "sep_fuzibil", "fuzibil", "spd", "spd_cc", "gpv", "separator_cc",
                "invertor", "string_pv", "baterie", "convertor_bess", "tc", "generator", "separator", "contactor", "releu"}


def _neutru(text, prod, model):
    """scoate producătorul / modelul din textul listei (caracteristici neutre de marcă)"""
    t = text
    for x in (model, prod):
        if x and len(str(x)) >= 2:
            t = re.sub(r"\s*[—–-]?\s*" + re.escape(str(x)), "", t)
    return re.sub(r"\s{2,}", " ", t).strip(" —–-,")


def _normative(tip, inp):
    n = list(S.NORMATIVE_COMUNE)
    if tip in ("cef", "prosumator"):
        n += S.NORMATIVE_PV
        if inp.get("bess") or inp.get("baterie") or inp.get("baterie_kWh"):
            n += S.NORMATIVE_BESS
    if tip == "pt" or inp.get("pt_Sn_kVA") or (tip == "cef" and inp.get("celule_mt")):
        n += S.NORMATIVE_PT
    if tip == "ge_ats":
        n += S.NORMATIVE_GE
    if tip in ("bransament", "locuinta"):
        n += S.NORMATIVE_BRANSAMENT
    return n


def caiet_sarcini(corp, m, r):
    inp = m.get("calc") or (corp or {}).get("calc") or {}
    k = m.get("cartus") or {}
    tip = inp.get("tip_schema")
    doc = Document("CAIET DE SARCINI", f"Instalații electrice — {k.get('denumire2') or 'schema monofilară'}", _antet({"cartus": k}))
    doc.legenda()
    doc.h("1. Generalități", 1)
    doc.campuri([("Obiectivul", camp(k.get("titlu") or k.get("denumire2"))), ("Amplasament", camp(k.get("adresa"))),
                 ("Beneficiar", camp(k.get("beneficiar"))), ("Proiectant", camp(k.get("proiectant"))),
                 ("Proiect nr. / faza", camp(" / ".join(x for x in (k.get("nr_pr"), k.get("faza")) if x) or None)),
                 ("Atestat ANRE necesar executantului", camp((k.get("atestat_necesar") or "").replace("necesar: ", "") or None)),
                 ("Planșa schemei monofilare", camp(" ".join(x for x in (k.get("plansa"), k.get("denumire2")) if x) or None))])
    for t in S.GENERALITATI:
        doc.p(t)
    rz = (r or {}).get("rezultat") or {}
    date_teh = []
    if rz.get("sume"):
        su = rz["sume"]
        date_teh.append(("Puterea nominală c.a.", camp(su.get("Pn_total_kW"), "kW")))
    if inp.get("kWp"):
        date_teh.append(("Puterea instalată c.c.", camp(inp.get("kWp"), "kWp")))
    if rz.get("bilant"):
        b = rz["bilant"]
        date_teh.append(("Puterea instalată / cerută", camp(" / ".join(f"{dt._f(b[x])} kW" for x in ("Pi_kW", "Pc_kW") if b.get(x)) or None)))
    date_teh.append(("Rețeaua", Camp("3 × 400/230 V, 50 Hz" if (inp.get("retea") or "tri") == "tri" else "230 V, 50 Hz")))
    date_teh.append(("Schema de legare la pământ", camp(rz.get("schema_pamant") or inp.get("schema_pamant"))))
    doc.h("Date tehnice principale", 2)
    doc.campuri(date_teh)
    doc.h("2. Standarde și normative aplicabile", 1)
    doc.p("Lucrările se execută cu respectarea reglementărilor în vigoare la data execuției, în principal:")
    doc.lista(_normative(tip, inp))
    doc.h("3. Materiale și echipamente — caracteristici minime", 1)
    for t in S.CONDITII_ECHIPAMENTE:
        doc.p(t)
    rows = []
    for i, e in enumerate([e for e in echipamente(m) if e["tip"] in TIPURI_CAIET], 1):
        den = _neutru(e["denumire"], e["producator"], e["model"])
        car = _neutru(e["caracteristici"], e["producator"], e["model"])
        rows.append([Camp(str(i)), Camp(", ".join(e["ref"]) or "—"), Camp(den), Camp(car),
                     Camp(S.CERINTE_TIP.get(e["tip"], "conform listei de echipamente")), camp(e["buc"])])
    doc.tabel(["Nr.", "Ref. schemă", "Echipament", "Caracteristici (din calcul)", "Cerințe minime / standard", "Buc."], rows)
    tc = dt.tabel_cabluri(m, r)
    if tc["randuri"]:
        doc.p("Cabluri (tipul, formația și lungimile estimate — detaliate în tabelul de cabluri al proiectului):")
        doc.tabel(["Ref.", "De la → la", "Tip", "Formație", "L [m]"],
                  [[Camp(x["ref"]), Camp(f"{x['de_la']} → {x['la']}"), camp(x["tip"]), camp(x["formatie"]), camp(x["L_m"])]
                   for x in tc["randuri"]])
    cr = dt.dimensionare_carcasa(m)
    if cr["module_aparate"]:
        doc.p("Tabloul electric: ", Camp(cr["carcasa_propusa"]), f" — {cr['module_aparate']} module DIN ocupate, "
              f"rezervă ≥ {dt._f(cr['rezerva_pct'], 0)} %.")
    doc.h("4. Execuția lucrărilor", 1)
    sect = list(S.EXECUTIE) + ([S.EXECUTIE_PV] if tip in ("cef", "prosumator") else [])
    for titlu, pct in sect:
        doc.h(titlu, 2)
        doc.lista(pct)
    doc.h("5. Verificări și probe", 1)
    doc.p("Înainte de punerea în funcțiune se efectuează și se consemnează în buletine (SR HD 60364-6):")
    doc.lista(S.PROBE + (S.PROBE_PV if tip in ("cef", "prosumator") else []), numerotata=True)
    doc.h("6. Recepția lucrărilor", 1)
    for t in S.RECEPTIE:
        doc.p(t)
    doc.h("7. Punerea în funcțiune", 1)
    for t in S.PIF:
        doc.p(t)
    doc.h("8. Documentația as-built (cartea tehnică)", 1)
    doc.lista(S.AS_BUILT)
    fr = dt.fisa_reglaje(m, r)
    if fr["randuri"]:
        doc.salt()
        doc.h("Anexa B — Reglajele protecțiilor (de verificat la PIF)", 1)
        doc.tabel(["Aparat", "Circuit", "In [A]", "Curbă / decl.", "Ir [A]", "Isd [A]", "Ii [A]", "IΔn [mA]", "Ik3max [kA]"],
                  [[Camp(x["ref"]), Camp(x["amplasare"]), camp(x["In_A"]), camp(x["curba"]), camp(x["Ir_A"]),
                    camp(x["Isd_A"]), camp(x["Ii_A"]), camp(x["IdN_mA"]),
                    camp(round(x["Ik3max_kA"], 2) if isinstance(x["Ik3max_kA"], (int, float)) else None)] for x in fr["randuri"]])
    doc.p(f"Model de caiet de sarcini generat din proiect (texte verificate la {S.VERIFICAT_LA}); proiectantul îl "
          "adaptează obiectivului și îl semnează.")
    doc.semnaturi("Întocmit (proiectant)", "Verificat", "Șef proiect")
    return doc
