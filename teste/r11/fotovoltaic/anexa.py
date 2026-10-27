"""Runda 11 fotovoltaic — verdictele testerului; scrie fraze.json din brut.json.
Rulare: cd /home/claude/sm && python3 teste/r11/fotovoltaic/anexa.py"""
import json
from pathlib import Path
OUT = Path(__file__).parent

# id: (verdict, prioritate, observație)
V = {
 1: ("parțial", "P1", "Intrare corectă (3×100, PT OD existent, EMS ≤ 240, QPT desenat). Planșa f01: nota 2 scrie „PT-ul propriu existent” și nota 3 „TN-S din PT propriu”, deși ATR spune PT al OD; QG = QPT = 500 A (fără treaptă)."),
 2: ("parțial", "P1", "Rândul de BOM „Cablu solar 6 mmp – 1500 m” devine cablu impus C0 (6 mm² Al, 1500 m) → V13 blocant + întrebare „aplic remedierea?”. Cablul nu apare în panoul de confirmare. kWp (172 × 580 W = 99,8 kWp) necalculat."),
 3: ("parțial", "P2", "4×50 + 1×30 corect. Avertismentul spune „desenată prin BMPT (presupus)”, dar planșa are PT nou 630 kVA (întrebare separată). PCS LUNA = 200 kW nemarcat ca presupus. Titlu „CEF 430 kW + BESS”."),
 4: ("greșit", "P1", "„Avem PT propriu 400 kVA” = existent, dar e desenat PT NOU (trafo, celule MT, anvelopă în listă) — nemarcat; panoul CEF nu are comutator PT existent. TCA/EMS pentru injecție zero e în TGD-CF (măsoară producția, nu schimbul la PT). Model „Solis-110K-5G?” cu semnul întrebării în intrare. Telefonul e ignorat corect."),
 5: ("parțial", "P2", "Refuz I02 (cere invertoarele) — sigur, dar „20 kw” nu e citit deloc și nu se semnalează că 20 kW monofazat nu e realist."),
 6: ("parțial", "P1", "Intrare perfectă (990 kW, PT nou 1000, MT, ≤ 900 kW). V67 BLOCHEAZĂ cu 1,1·ΣPn = 1089 kVA (SG110CX are Smax 110 kVA → 990 kVA). În plus QG Ir 1600 A > QJT Ir 1440 A (selectivitate inversă, V60 doar avertisment)."),
 7: ("parțial", "P2", "Autocorectura „5 invertoare Fronius Tauro 50-3-D... scuze, 4 bucăți, nu 5” pierde tot invertorul → refuz I02. Fără autocorectură Tauro e citit corect (sondă)."),
 8: ("corect", "", "Σ 120 ≠ 100 → I08 cu întrebare clară."),
 9: ("greșit", "P1", "Rețea nedeclarată, invertor fără model, BMPT de calibru necunoscut → desenat TRIFAZAT fără nicio presupunere marcată (panoul nu marchează câmpul Rețea). Regula „rețeaua nu se presupune” e încălcată. Cu „monofazat” întrebarea e corectă (sondă)."),
 10: ("corect", "", "2×20, BMPT 80, PI externă (> 27 kW), fără EMS."),
 11: ("parțial", "P1", "„2 baterii BOS-G 5,12 kWh” → 5,12 kWh (nu 10,24) pe planșă și în listă, nemarcat. Fără „BOS-G” iese 10,24 (sondă). TT + DDR pe toate plecările corect (f11)."),
 12: ("corect", "P2", "BESS stand-alone 500/1000 pe PT existent corect; QB = QG = 1000/950 A fără treaptă."),
 13: ("corect", "P2", "f13 bună: TCA + AR + EMS ≤ 50 kW la intrarea TG. Titlu „CEF 200 kW + BESS” pentru 100 PV + 100 BESS."),
 14: ("parțial", "P2", "Intrare și secții corecte (8 + 8). V67 blocant la limită (1012 vs 1000 kVA, cu 1,1·Pn; Smax real 125 kVA → 1000 kVA)."),
 15: ("parțial", "P1", "SG350HX are Pn 320 kW la 800 V (Smax 352 kVA); textul e corect, dar se refuză cu I08 „350 sau 320?”, fără opțiunea „SG350HX de 320 kW”. Pentru SUN2000-215KTL-H3 (200 kW) aceeași situație e acceptată (#50) — inconsecvent."),
 16: ("parțial", "P1", "Fazele L1/L2/L3 corecte (P0 r10 reparat). Modelul e poluat: „SUN2000-5KTL-L1 repartizate L1-L2-L3” pe planșă și în listă (f16). Presupunerea „rețea mixtă: invertor trifazat + …” e falsă (nu există trifazat)."),
 17: ("parțial", "P1", "5/5/5 pe faze și PI corecte. f17: 15 invertoare monofazate desenate individual, redusă la 36 % pe A1 — ilizibilă; nu se grupează „5 × identice / fază” cum se face la CEF."),
 18: ("parțial", "P2", "Existentul (Tauro) e marcat corect, limitarea 80 kW citită; „CEF de 50 kW” existentă e luată ca total → I08 fals, dar întrebarea oferă varianta bună (1×50 + 2×30)."),
 19: ("parțial", "P1", "„3 x SMA STP 25000TL-30 (75 kW)” → Pn 75 kW/buc → refuz I08. Același tipar ca r10 #65 (paranteza = total). Fără paranteză merge (existent + nou, TG, zero)."),
 20: ("greșit", "P0", "„3 invertoare (2 x Huawei 100KTL și 1 x Sungrow SG110CX)” → 3×100 + 1×110 = 410 kW pe planșă curată (f20), fără întrebare. Sondă: „4 invertoare (3 x 50KTL + 1 x 30KTL)” → 4×50 + 30. Forma r10 (fără „k x”) și forma cu „:” sunt reparate."),
 21: ("corect", "P2", "Limitarea 60 % × 100 = 60 kW (P0 r10 reparat). QG 160 = BMPT 160."),
 22: ("parțial", "P2", "Cablul impus CYABY 4×95, 80 m e consumat corect pe C0. V02 blochează pentru că QG e ales 200 A din 1,1·Pn (Iac real SG110CX 158,8 A → 160 A ar trece)."),
 23: ("corect", "", "Cablul ACYABY 3×50+25, 120 m impus → V02/V03/V20/V25 blocante, cu remedieri explicite."),
 24: ("greșit", "P1", "„12 stringuri a câte 20 module 455 Wp” → „20 module în total” → 9,1 kWp, titlu „CEF 9,1 kWp”; stringurile sunt atribuite fiecărui invertor (V89: 218,4 kWp). Două întrebări semnalează, dar planșa și titlul sunt greșite. gPV 15 A desenate corect."),
 25: ("parțial", "P2", "6 × 18 × 550 Wp = 59,4 kWp necalculat; presupunerea spune „lipsește numărul de module pe string”, deși e dat. V69 presupune 6 stringuri în paralel pe un MPPT."),
 26: ("corect", "P2", "f26: plecare nouă QPT 250 A din TDRI (r10 #15 reparat), măsură MT existentă, fără contor JT. QG = QPT = 250 A, Icu QPT „— kA”."),
 27: ("corect", "", "PT nou 400 kVA, măsură JT, QJT 630/567 > QG 630/535."),
 28: ("corect", "P2", "Tabel cu tab-uri citit corect (2×100, 204 kWp, BMPT 315). „Baterie 0 buc” → întrebare inutilă despre baterie; două întrebări aproape identice pentru BMPT 315."),
 29: ("corect", "", "Capcana nume/CUI/nr. 110 evitată."),
 30: ("corect", "", "Nr. ATR ignorat, 2×30, BMPT 100."),
 31: ("parțial", "P1", "„injecție zero, dar ATR aprobă evacuare 100 kW” — „ATR aprobă evacuare 100 kW” dispare tăcut (nici P_evacuata, nici neconsumat, nici întrebare). Zero injecție desenat."),
 32: ("greșit", "P1", "Contradicția „racord în BMPT și în PT propriu 250 kVA” nu e întrebată: se alege PT nou, BMPT dispare tăcut. „3 x 50KTL Huawei” (marca după cod) → 1 × 150 kW (marcat „PRESUPUS”, dar greșit)."),
 33: ("parțial", "P1", "„branșament monofazat 1x40 A” ajunge doar la întrebarea generică „Nu am folosit…”. SUN2000-10KTL-M1 (trifazat, declarat) e pus în intrare ca monofazat pe L1 (V71 fals), deși planșa îl desenează 3 × 400 V."),
 34: ("corect", "P2", "Typo-urile „racrod / exsitent” rezolvate, 2 × 50, PT existent 630; „huawie” nu e recunoscut (fără marcă), întrebare de confirmare corectă. QG = QPT 160."),
 35: ("corect", "", "SolarEdge SE100K × 3, PT nou 1250 cu întreruptor MT + 50/51, măsură JT."),
 36: ("corect", "", "SG50CX + baterie c.c. → V12 blocant cu remediere clară (r10 #57 reparat)."),
 37: ("parțial", "P2", "SolaX X3-ULTRA-30K: puterea din cod („30K”) nu e citită → refuz I02. Sigur, dar ar trebui citit ca la Deye „-15K-”."),
 38: ("corect", "P2", "BESS 2 × 125 / 2 × 261 citit exact. V67 cu PT 400 legitim. Cele două întrebări dau S diferite (412,5 vs 550 kVA); titlu „CEF 500 kW + BESS”."),
 39: ("parțial", "P1", "0,5 MW → 500 kW corect; V67 blocant fals (aceeași clasă ca #6)."),
 40: ("corect", "", "„Fără injecție (doar autoconsum)” = zero."),
 41: ("corect", "P2", "Prosumator 100 kW, PI externă. Întrebarea BMPTi-250 presupune un branșament de 100 A nedeclarat; QG = QI 200/190."),
 42: ("corect", "P2", "f42 bună: PV 1–2 EXISTENT (E), BESS c.a. nou, TCA la intrarea TG, EMS zero. Titlu „CEF 200 kW + BESS”."),
 43: ("greșit", "P1", "„fiecare invertor cu cablu CYY-F 5x16, 25 m” e aplicat pe C0 (TGD-CF → TG), nu pe cablurile invertoarelor → V02/V03 blocante + „aplic remedierea?” pe cablul greșit. Cu „cablu invertor” merge (sondă)."),
 44: ("greșit", "P0", "„Două tablouri TGD-CF … fiecare cu 3 x SUN2000-50KTL-M3” → un singur grup 3 × 50 = 150 kW (f44, „CEF 150 kW”), fără întrebare și fără neconsumat — jumătate din centrală dispare."),
 45: ("parțial", "P1", "„export cap 400 kW” e luat ca putere totală → I08 fals „4 × 115 sau 400?”. Dacă utilizatorul răspunde „4 × 115”, limitarea se pierde. „export limited to 400 kW” merge (sondă)."),
 46: ("greșit", "P1", "„racord in TG existent... de fapt nu, prin BMPT nou 3x125A” → tip_schema „tablou”, invertorul dispare, refuz „tabloul are două surse”. Autocorectura nu e aplicată pe racord."),
 47: ("corect", "", "Autocorectura „250 kVA? nu, 400 kVA” și limitarea 150 kW."),
 48: ("greșit", "P1", "„BMPT 1x32A” (monofazat) → instalație TRIFAZATĂ (f48: BMPT 3+N+PE, „Forță 3F”, titlu „TRIFAZAT”); doar faza e marcată presupusă, rețeaua nu."),
 49: ("corect", "", "Tri 10 + mono 5 pe L2."),
 50: ("parțial", "P1", "„2 PT x 2500 kVA 20/0,8 kV” nu e citit ca n_trafo = 2 → refuz I12 cu întrebarea „Împărțiți pe două PT (ex. 2 × 2500)?” — exact ce s-a scris."),
 51: ("corect", "", "20 × 50 kW, PT nou 1250, JT."),
 52: ("corect", "P2", "f52: trei tipuri Sungrow corecte (766 kW), MT, QG 1250 < QJT 1440. Text mic pe A1."),
 53: ("parțial", "P1", "„Ik3 la bara 0,4 kV = 18 kA” neconsumat (întrebare generică); „impedanța buclei 0,05 ohm” intră ca RA_ohm (rezistența prizei) — sens greșit, nemarcat. „Ik3 = 18 kA la bara TG” merge (sondă)."),
 54: ("parțial", "P2", "Text foarte încâlcit („2 x SG80? Hai simplu:”): ambele grupuri păstrate → I08. Siguranțele MPR 315 A citite (racord_Q_tip gG)."),
 55: ("corect", "", "Hibrid M1 + LUNA 15 kWh c.c."),
 56: ("corect", "", "TT, RA 10 Ω, DDR 100 mA pe invertoare."),
 57: ("corect", "", "Evacuată 0 kW → injecție zero; absorbită 150 nu e luată ca putere CEF."),
 58: ("parțial", "P2", "„CEF de 50 kW” → refuz I02, tot textul neconsumat; avertismentul „desenată prin BMPT” apare deși nu se desenează nimic."),
 59: ("greșit", "P1", "„doar baterie … fără panouri” → f59 desenează CÂMP PV + SPD c.c. + câmp PV în listă. Nemarcat."),
 60: ("parțial", "P2", "Stația de 22 kW e semnalată, dar întrebarea citează toată fraza, inclusiv partea consumată (CEF 1 × 50)."),
 61: ("corect", "", "Pn 60 vs cod 50 → I08."),
 62: ("greșit", "P1", "CSV cu virgulă și ghilimele: n = 1 (coloana Qty ignorată), model „SUN2000-50KTL-M3\"”, „545W” → total 545 kW → I08 fals. Clasa r10 #47 nereparată."),
 63: ("corect", "P2", "f63 bună: 2 × 630, câte 3 SG110CX pe secție, contor JT pe fiecare secție, cuplă QC. Lista de echipamente nu e pe planșă (anexă .xlsx)."),
 64: ("corect", "", "Primo mono existent pe L1 + Deye 8K hibrid nou; întrebarea 37 A > 32 A e legitimă."),
 65: ("parțial", "P2", "„BMPT 3x630A” + 400 kW → PT nou 630 kVA adăugat (cu întrebare) și BMPT abandonat; anvelopa PT intră în listă (f65). EMS ≤ 300 corect."),
 66: ("greșit", "P1", "Autocorectura „pardon, existente sunt doar 2…” → rămân 3 × 100, cele 2 existente dispar; „PT existent 630” (fără kVA) neconsumat → PCC 0,4 kV. Sondă fără autocorectură: „3 x … noi și 2 x … existente” → 5 invertoare, cele 2 NEMARCATE existente."),
}

if __name__ == "__main__":
    brut = json.loads((OUT / "brut.json").read_text(encoding="utf-8"))
    rez = []
    for d in brut:
        v, p, o = V[d["id"]]
        rez.append({"id": d["id"], "fraza": d["text"], "asteptat": d["asteptat"], "actiune": d.get("actiune"),
                    "intrare": d.get("intrare_fizica"), "presupuneri": d.get("presupus"), "intrebari": d.get("intrebari"),
                    "refuz": d.get("refuz_cod"), "neconsumat": d.get("neconsumat"), "titlu": d.get("titlu"),
                    "plansa": d.get("plansa"), "verificari": d.get("verificari"), "blocheaza": d.get("blocheaza"),
                    "verdict": v, "prioritate": p, "observatie": o})
    (OUT / "fraze.json").write_text(json.dumps(rez, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    from collections import Counter
    print(Counter(x["verdict"] for x in rez), Counter(x["prioritate"] for x in rez))
