"""r12 — clasele găsite la testarea pe proiecte REALE (texte de proiectant: memorii, ATR-uri, devize copiate), pe
INTERPRETORUL LOCAL (engine/interp_reale.py + regulile vechi), fără Claude.

Frazele de aici sunt NOI și anonimizate (alte nume, alte valori), cu aceeași structură și același vocabular ca textele
reale — datele proiectelor reale nu se copiază în teste. Pe clase (SPEC §F.16):
1. cablurile legate pe segment (invertor → tablou, tablou → PT / TEG / stație = C0, LES / MT = cablu_MT, „în paralel”
   doar pe segmentul lui, fără context → întrebare);
2. stringurile și invertoarele pe rânduri („INV1: …”, „Invertorul 2 - …”);
3. racordul existent („PTAb existent”, „barele JT ale postului”, „stația 0,4 kV a fabricii”, „TEG beneficiar alimentat
   din PT …”, „separator vertical … existent”);
4. capcanele de vocabular (TT de măsură, AAR, „Ir = kA”, „buc N”, „Pi kW”, „Putere nominală totală invertoare”, ATR
   kVA / kW, „0,4 kV” după model, „puterea instalată panouri”);
5. cheile noi pentru motor (QG, protecția invertoarelor, monitorizare, tablouri intermediare, Q0 din TDRI, fișa modulului).

Rulare: cd /home/claude/sm && python3 -m pytest -q tests/test_interpretor_reale.py
"""
import sys
from pathlib import Path

import pytest

RAD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAD))

from engine.calc import chei  # noqa: E402
from engine.interpretor import interpreteaza  # noqa: E402


def R(text):
    return interpreteaza(text)


def I(text):
    return R(text)["intrare_fizica"]


def Q(text):
    return " | ".join(R(text)["intrebari"])


def n_inv(i):
    return sum(g.get("n") or 1 for g in i.get("invertoare") or [])


# ================================================================================================= 1. cabluri pe segment
def test_cablu_pe_randul_invertorului_si_c0():
    t = ("CEF 60 kWp, retea trifazata.\n"
         "INV1 hala nord: Sungrow SG30CX 30 kW, cablu NYY-J 5x16 18 m pana la TD-PV.\n"
         "INV2 hala sud: Sungrow SG30CX 30 kW, cablu NYY-J 5x16 42 m pana la TD-PV.\n"
         "Legatura TD-PV - PT existent 630 kVA: CYABY 3x95+50 Cu, 75 m.")
    i = I(t)
    assert [g.get("L_m") for g in i["invertoare"]] == [18, 42]
    assert all(g["cablu"]["S_fortat"] == 16 for g in i["invertoare"])
    assert i["cablu_C0"]["S_fortat"] == 95 and i["L_racord_m"] == 75
    assert i["pt_existent"] is True and i["pt_Sn_kVA"] == 630


def test_cablu_fiecare_invertor_si_paralel_doar_pe_c0():
    i = I("Centrala 250 kW: 5 x SUN2000-50KTL-M3, fiecare invertor cu cablu ACYABY 4x35 Al 40 m pana la tabloul de "
          "interfata. Legatura tablou interfata - TG beneficiar: 2 cabluri ACYABY 3x185+95 in paralel, 90 m.")
    assert i["cablu_inv"]["S_fortat"] == 35 and i["L_inv_m"] == 40 and "n_fortat" not in i["cablu_inv"]
    assert i["cablu_C0"]["S_fortat"] == 185 and i["cablu_C0"]["n_fortat"] == 2 and i["L_racord_m"] == 90
    assert i["racord"] == "tg_existent"


def test_cablu_les_mt_nu_e_c0():
    i = I("CEF 300 kWp cu 3 x SUN2000-100KTL-M1, PTAb nou 400 kVA, LES 20 kV A2XS(FL)2Y 3x1x150 220 m pana la PTAb")
    assert i["cablu_MT"]["S_mm2"] == 150 and i["cablu_MT"]["L_m"] == 220
    assert (i.get("cablu_C0") or {}).get("S_fortat") != 150 and i.get("L_racord_m") != 220


def test_cablu_mt_cu_tronsoane():
    i = I("CEF 500 kWp, 5 x SG100CX, PT nou 630 kVA, LES 20 kV NA2XS2Y 3x1x95 140 m + aerian 40 m + 90 m pana la PT")
    assert i["cablu_MT"]["S_mm2"] == 95 and [x["L_m"] for x in i["cablu_MT"]["tronsoane"]] == [140, 40, 90]
    assert i["cablu_MT"]["L_m"] == 270 and not (i.get("cablu_C0") or {}).get("S_fortat")


def test_c0_in_statie_paralel():
    i = I("6 x SG110CX, 800 kWp. Legatura tablou CEF - statia 0,4 kV a halei: 3 cabluri NA2XY 4x240 in paralel, 60 m.")
    assert i["cablu_C0"]["n_fortat"] == 3 and i["cablu_C0"]["S_fortat"] == 240 and i["L_racord_m"] == 60
    assert i["racord"] == "tg_existent" and not i.get("cablu_inv", {}).get("n_fortat")


def test_c0_din_doua_tronsoane():
    i = I("CEF 1250 kWp, 10 x SG125CX. Legatura TGD-CF - post existent 1600 kVA: 3 x NA2XY 4x240 Al 120 m, apoi "
          "N2XY 1x300 Cu pe faza 20 m.")
    tr = i["cablu_C0"]["tronsoane"]
    assert [(x["S_fortat"], x["material"], x["L"]) for x in tr] == [(240, "Al", 120), (300, "Cu", 20)]
    assert tr[0]["n_fortat"] == 3 and i["L_racord_m"] == 140 and i["pt_existent"] is True


def test_cabluri_fara_context_intrebare():
    r = R("CEF 100 kW 2 x SG50CX, racord TG existent\nNYY 5x25 m 60\nNA2XY 4x150 m 160")
    assert "Unde se leagă" in " ".join(r["intrebari"])
    assert not (r["intrare_fizica"].get("cablu_C0") or {}).get("S_fortat")


def test_cablu_unic_fara_context_ramane_c0():
    i = I("CEF 40 kWp, invertor Huawei SUN2000-40KTL-M3, cablu CYABY 5x25 Cu 35 m, TG existent")
    assert i["cablu_C0"]["S_fortat"] == 25 and i["L_racord_m"] == 35


def test_cantitate_din_lista_nu_e_lungime():
    r = R("CEF 100 kWp: 2 buc. invertor cu puterea de 50 kW, tip Huawei SUN2000-50KTL-M3; 80m conductor NA2XY 4x35 "
          "de la invertoare la tabloul TE-PV; 180 m conductor 2x NA2XY 4x95 de la TE-PV la postul existent 630 kVA.")
    i = r["intrare_fizica"]
    assert n_inv(i) == 2 and i["L_inv_m"] == 40 and i["L_racord_m"] == 90 and i["cablu_C0"]["n_fortat"] == 2
    assert "cantitatea din listă" in " ".join(r["intrebari"])


# ================================================================================================= 2. stringuri pe rânduri
def test_stringuri_pe_randuri_invertor():
    i = I("CEF 75 kWp, trifazat.\n"
          "INV1 hala A: Huawei SUN2000-40KTL-M3 40 kW, 96 module 545 W in 6 stringuri x 16, 3 MPPT\n"
          "INV2 hala B: Huawei SUN2000-40KTL-M3 40 kW, 72 module 545 W in 4 stringuri x 18")
    s1, s2 = (g["string"] for g in i["invertoare"])
    assert (s1["n_module"], s1["n_stringuri_paralel"], s1["n_MPPT"]) == (16, 2, 3)
    assert (s2["n_module"], s2["n_stringuri_paralel"], s2["n_MPPT"]) == (18, 2, 2)


def test_invertorul_k_liniuta():
    i = I("CEF 120 kWp\nInvertorul 1 - Growatt MAX 60KTL3-X 60 kW, 6 stringuri x 20, 6 MPPT\n"
          "Invertorul 2 - Growatt MAX 60KTL3-X 60 kW, 9 stringuri x 20, 6 MPPT")
    assert n_inv(i) == 2 and len(i["invertoare"]) == 2
    assert i["invertoare"][0]["string"]["n_stringuri_paralel"] == 1 and i["invertoare"][1]["string"]["n_stringuri_paralel"] == 2


def test_stringuri_global_impartite_pe_mppt():
    i = I("CEF 110 kW: 1 x SG110CX, 12 stringuri x 18 module 550 W, 9 MPPT, TG existent")
    assert (i["string"]["n_stringuri_paralel"], i["string"]["n_MPPT"]) == (2, 6)


def test_stringuri_pe_mppt_raman():
    i = I("CEF 50 kW: 1 x SG50CX, 20 module pe string, 2 stringuri pe MPPT, 5 MPPT, TG existent")
    assert (i["string"]["n_stringuri_paralel"], i["string"]["n_MPPT"]) == (2, 5)


def test_randuri_module_contradictie():
    q = Q("CEF 80 kWp\nINV1: SUN2000-40KTL-M3, 90 module in 6 stringuri x 16, 4 MPPT\n"
          "INV2: SUN2000-40KTL-M3, 64 module in 4 stringuri x 16, 4 MPPT")
    assert "90 module" in q and "Care e configurația" in q


def test_randuri_mai_multe_decat_invertoare():
    q = Q("CEF 60 kWp, 1 x SUN2000-60KTL-M0\nINV1: 6 stringuri x 16, 3 MPPT\nINV2: 4 stringuri x 18, 2 MPPT")
    assert "rânduri de invertoare" in q


# ================================================================================================= 3. racord existent
@pytest.mark.parametrize("text,racord,sn", [
    ("CEF 200 kWp, 2 x SUN2000-100KTL-M1, racord pe barele JT ale postului existent 800 kVA", "pt", 800),
    ("CEF 150 kWp, 3 x SG50CX. Legatura TE-PV - PTAb existent 20/0,4 kV 630 kVA: NA2XY 4x150, 40 m", "pt", 630),
    ("CEF 300 kWp, 3 x SG100CX, racord in TEG beneficiar alimentat din PT 1250 kVA", "tg_existent", 1250),
    ("CEF 900 kWp, 9 x SG100CX, racord in statia de 0,4 kV a fabricii, trafo existent 1600 kVA", "pt", 1600),
    ("CEF 250 kWp, 2 x SG125CX, Legatura TE - post de transformare PTAb 20/0,4kV existent: NA2XY 4x185 30 m, "
     "transformator 1000 kVA", "pt", 1000),
])
def test_racord_existent(text, racord, sn):
    i = I(text)
    assert i["racord"] == racord and i["pt_Sn_kVA"] == sn
    if racord == "pt":
        assert i["pt_existent"] is True
    assert "Confirmați PT propriu" not in Q(text)


def test_racord_statie_cu_intreruptor_nou():
    i = I("CEF 700 kWp, 7 x SG100CX, racord in statia de 0,4 kV a uzinei cu intreruptor nou 1250 A")
    assert i["racord"] == "tg_existent" and i["racord_In_Q_A"] == 1250 and i["racord_Q_tip"] == "ACB"


def test_racord_pe_separator_existent():
    i = I("CEF 90 kW, 3 x SG30CX. Legatura TE-PV - PTAb existent 630 kVA: NA2XY 4x70, 55 m, pe separator vertical "
          "MPR 160 A existent.")
    assert i["racord_In_Q_A"] == 160 and i["racord_Q_tip"] == "gG" and i["pt_existent"] is True


def test_pt_nou_ramane_nou():
    i = I("CEF 300 kWp, 3 x SG100CX, PTAb nou 400 kVA 20/0,4 kV, masura pe MT")
    assert i.get("pt_existent") is False and i["pt_Sn_kVA"] == 400


def test_bmpt_masura_cef_cu_pt_existent():
    i = I("CEF 100 kWp, 2 x SG50CX, racord pe barele JT ale postului existent 630 kVA, BMPT semidirect cu TC 200/5")
    assert i["racord"] == "pt" and i["monitorizare"]["contor_productie"]["tip"] == "BMPT"
    assert i["monitorizare"]["contor_productie"]["TC_primar_A"] == 200


# ================================================================================================= 4. vocabular
def test_tt_de_masura_nu_e_schema_tt():
    i = I("CEF 300 kW, 3 x SG100CX, PT nou 400 kVA, celula de masura cu 3 TT 20/0,1 kV si 3 TC 15/5 A")
    assert i.get("schema_pamant") != "TT" and i["tip_schema"] == "cef"


def test_aar_si_paralel_nu_sunt_ge():
    r = R("Centrala fotovoltaica 500 kW, 5 x SG100CX, PT nou 630 kVA. Punct de conexiune nou: 2 celule de linie "
          "motorizate cu AAR. Legatura TE - PT: 2 cabluri NA2XY 4x240 in paralel, 40 m.")
    assert r["tip_schema"] == "cef" and r["actiune"] != "refuza"
    assert r["intrare_fizica"]["celule_mt"][:2] == ["linie", "linie"]
    assert r["intrare_fizica"]["punct_conexiune"] == {"celule_linie": 2, "aar": True}


@pytest.mark.parametrize("fraza", ["Ir-36kA", "Ir = 36 kA", "Ir=36kA", "Icu 36 kA"])
def test_ir_ka_este_icu(fraza):
    i = I(f"CEF 200 kW, 2 x SUN2000-100KTL-M1, intreruptor de interfata 4P 400 A motorizat, {fraza}, TG existent")
    assert i["QG"]["Icu_kA"] == 36 and i["In_QG_A"] == 400


def test_buc_dupa_model_rand_deviz():
    i = I("INVERTOR SUNGROW SG110CX buc 4\nPANOU JA SOLAR JAM72D30-550 buc 800\nracord TG existent")
    assert n_inv(i) == 4


def test_pi_kw_mai_mare_decat_invertoarele_e_kwp():
    r = R("CEF Pi 270 kW, 400 V. 2 x Huawei SUN2000-100KTL-M1 100 kW. TG existent")
    assert r["actiune"] != "refuza" and r["intrare_fizica"]["kWp"] == 270


def test_putere_nominala_totala_invertoare():
    i = I("Putere nominala totala invertoare (c.a.) 200 kW; 2 buc. invertor SUN2000-100KTL-M1; 480 buc. panouri de "
          "545 Wp; racord TG existent")
    assert i["Pn_total_kW"] == 200 and n_inv(i) == 2 and all(g.get("model") for g in i["invertoare"])


def test_atr_kva_kw():
    i = I("CEF 110 kW, 2 x SG50CX + 1 x SG10RT. Puterea maxima simultana ce poate fi evacuata 110 kVA / 99 kW. "
          "Racord TG existent")
    assert i["P_evacuata_kW"] == 99


def test_model_nu_inghite_tensiunea():
    i = I("Invertoare: 2 SUNGROW SG50CX 0,4 kV 50 kW; 1 SUNGROW SG33CX 0,4 kV 33 kW. Racord TG existent")
    assert {g["model"] for g in i["invertoare"]} == {"SG50CX", "SG33CX"}


def test_puterea_instalata_panouri_e_kwp():
    i = I("Puterea instalata panouri 150,5 kW. Invertoare: 1 x SG125CX. Racord TG existent")
    assert i["kWp"] == 150.5 and (i.get("modul") or {}).get("Pmax_W") != 150


# ================================================================================================= 5. chei noi
def test_qg_electronic_motorizat_reglat():
    i = I("CEF 330 kW, 3 x SG110CX, TG existent. In TE-PV: intreruptor de interfata 3P 400 A, reglaj electronic, "
          "Ir=0,9xIn, motorizat, 50 kA, comandat de releu de interfata.")
    assert i["QG"] == {"In_A": 400, "electronic": True, "motorizat": True, "Icu_kA": 50, "Ir_reglat": 360}
    assert i["In_QG_A"] == 400


def test_monitorizare():
    i = I("CEF 150 kW, 3 x SG50CX, TG existent, smart meter Janitza UMG 96 cu 3 TC 800/5 A, SmartLogger 3000A, "
          "UPS 1500 VA, comunicatie RS485")
    m = i["monitorizare"]
    assert m["smart_meter"]["TC_primar_A"] == 800 and m["smartlogger"] and m["rs485"] is True
    assert i["protectie_interfata"]["ups_VA"] == 1500


def test_protectie_invertor_sigurante():
    i = I("CEF 400 kW, 4 x SUN2000-100KTL-M2, TG existent. Fiecare invertor are tablou de protectie cu separator cu "
          "sigurante 125 A, cablu ACYABY 3x95+50 30 m pana la tabloul general.")
    g = i["invertoare"][0]
    assert g["prot_tip"] == "gG" and g["protectie"]["In_A"] == 125 and i["cablu_inv"]["S_fortat"] == 95


def test_protectie_invertor_mccb_reglat():
    i = I("CEF 330 kW, 3 x SG110CX, TG existent. In TE-PV: cate un intreruptor automat 3 poli 250 A, Ir-25kA cu "
          "reglaj electronic, reglat 0,8 x In pe fiecare invertor.")
    p = i["invertoare"][0]
    assert p["prot_tip"] == "MCCB" and p["protectie"]["Icu_kA"] == 25 and p["protectie"]["Ir_reglat"] == 200


def test_tablouri_intermediare():
    i = I("CEF 1300 kWp, 12 x SG110CX grupate cate 3 pe 4 tablouri intermediare TE-1...TE-4, PT nou 1600 kVA. "
          "Fiecare TE secundar: plecare cu NA2XY 4x240 spre TEG principal 80 m, separatoare NH2 3x315 A.")
    ti = i["tablouri_intermediare"]
    assert len(ti) == 4 and all(x["cablu"]["S_fortat"] == 240 and x["L_m"] == 80 and x["In_A"] == 315 for x in ti)
    assert sorted(g["tablou"] for g in i["invertoare"]) == [1, 2, 3, 4] and all(g["n"] == 3 for g in i["invertoare"])
    assert "n_tgd_cf" not in i


def test_prosumator_contor_productie_bransament():
    i = I("prosumator 8 kW, invertor SUN2000-8KTL-M1, contor de productie separat, smart meter DTSU666-H, "
          "bransament existent 40 A trifazat")
    assert i["contor_productie"] and i["monitorizare"]["smart_meter"]["model"].upper().startswith("DTSU")
    assert i["In_Q_bransament_A"] == 40


def test_q0_tdri_pt_nou_si_plecarea_cef():
    i = I("CEF 200 kW, 4 x SG50CX, PTAb nou 400 kVA. In TDRI: intreruptor general Q0 630 A electronic, plecare Q1 250 A "
          "spre TE intermediar CEF cu releu de interfata.")
    assert i["In_Q_JT_A"] == 630 and i["In_QG_A"] == 250


def test_fisa_modulului():
    i = I("CEF 50 kW, 1 x SG50CX, TG existent. Modul: 550 W, Voc 49,6 V, Isc 14 A, Vmp 41,5 V, Imp 13,25 A, "
          "siguranta maxima 25 A, 1500 V.")
    m = i["modul"]
    assert (m["Vmpp_V"], m["Impp_A"], m["I_rev_A"], m["Umax_sistem_V"]) == (41.5, 13.25, 25, 1500)


def test_celule_din_lista_si_dg_cu_intreruptor():
    i = I("CEF 250 kW, 5 x SG50CX, PTAb nou 250 kVA, celule: linie, masura cu 2 TT 20/0,1 kV, racord utilizator, "
          "protectie trafo cu intreruptor SF6 24 kV 630 A 16 kA cu releu")
    assert i["celule_mt"] == ["linie", "masura", "trafo"] and i["celula_trafo"] == "intreruptor" and i["masura"] == "MT"


# ================================================================================================= pe toate frazele
TOATE = [
    "CEF 100 kWp, 2 x SG50CX, racord pe barele JT ale postului existent 630 kVA, smart meter DTSU666-HV, SmartLogger",
    "CEF 300 kWp cu 3 x SUN2000-100KTL-M1, PTAb nou 400 kVA, LES 20 kV A2XS(FL)2Y 3x1x150 220 m pana la PTAb",
    "6 x SG110CX, 800 kWp. Legatura tablou CEF - statia 0,4 kV a halei: 3 cabluri NA2XY 4x240 in paralel, 60 m.",
    "CEF Pi 270 kW, 400 V. 2 x Huawei SUN2000-100KTL-M1 100 kW. TG existent",
    "CEF 330 kW, 3 x SG110CX, TG existent. In TE-PV: intreruptor de interfata 3P 400 A, reglaj electronic, Ir=0,9xIn, "
    "motorizat, 50 kA.",
    "CEF 1300 kWp, 12 x SG110CX grupate cate 3 pe 4 tablouri intermediare TE-1...TE-4, PT nou 1600 kVA.",
]


@pytest.mark.parametrize("text", TOATE)
def test_plasa_si_chei(text):
    r = R(text)
    i = r["intrare_fizica"]
    assert r["actiune"] != "refuza" and not r["neconsumat"], (r["refuz_motiv"], r["neconsumat"])
    assert not chei.chei_nefolosite(i, i.get("tip_schema")), chei.chei_nefolosite(i, i.get("tip_schema"))
