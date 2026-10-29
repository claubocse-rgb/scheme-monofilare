# SPECIFICAȚIE TEHNICĂ — motor de dimensionare JT, validator blocant și interpretor de text

**Aplicație:** generator de scheme monofilare (`/home/claude/sm`) — rescriere de la zero a `engine/dimensionare.py`, a validatorului și a `engine/chat.py`
**Versiune:** 1.13 · 28.10.2026 (v1.13: verificarea normelor și cele 15 decizii ale proiectantului, §H.2a; v1.11: §F.11 — Claude interpretor principal, regulile locale verificare încrucișată / rezervă, schema intrării generată; v1.7: runda 4c de testare a locuinței, §C.8 — Q în afara seriei și câmpuri globale invalide ca rezultat parțial, Zb rurală presupusă, VE sub DDR tip AC al branșamentului, etichete românești centralizate, plafonul circuitelor la ΔU, prizele pe niveluri, VE dimensionat normal, cosφ în ipoteze; v1.6: runda 4b de testare a locuinței, §C.8 — buget ΔU coloană, repartizare pe curentul de calcul, Q / Pa presupuse vizibile, iluminat pe niveluri, rezerva SPD, zona rurală, TT pe coloană, rezultate parțiale, câmpul `camp`; v1.5: runda 4 de testare a locuinței, §C.8, și rețeaua obligatorie la branșament / prosumator / locuință, §A.1; v1.4: tipul de schemă „locuinta”, §C.8; v1.1 arbitraj: `spec/ARBITRAJ.md`; v1.2: defectele verificării independente `verif2/RAPORT_VERIFICARE.md` §3; v1.3: priza de pământ §C.7 și selectivitatea DDR în serie §B.18.1, vezi §H.5) · date normative: `norme.py` (aceeași versiune)
**Livrabile asociate:** `norme.py` (tabele), `cazuri_golden.json` (68 de cazuri calculate), `fraze_chat.json` (60 de fraze)
**Bază:** raportul de audit `/home/claude/reviews/inginer.md` (P0-1…P0-10, P1-1…P1-14, P2)

> **Cum se citește.** Programatorul implementează EXACT pașii din secțiunea B, în ordinea dată, cu datele din `norme.py`. Unde scrie „DECIZIE”, valoarea e o alegere de proiectare (normativul lasă libertate) și se aplică ca atare. Unde scrie „[NEVERIFICAT]”, valoarea e folosită, dar trebuie afișată în memoriul de calcul ca ipoteză. Orice abatere de la cazurile din `cazuri_golden.json` este o eroare a implementării, nu a testului. Dacă un test pare greșit, se discută cu inginerul, nu se modifică testul.

---

## Cuprins

- A. Domeniu și ipoteze
- B. Lanțul de dimensionare al unei ramuri (B.0–B.22; B.18.1 selectivitatea DDR, v1.3)
- C. Reguli specifice pe tip de schemă (C.1–C.8; C.7 priza de pământ, v1.3; C.8 locuința, v1.4 / v1.5 / v1.6)
- D. Catalogul de verificări (V01…V90)
- E. Lista de echipamente generată din parametri
- F. Interpretorul de text liber
- G. Ce se scrie pe planșă
- H. Anexe: trasabilitatea constatărilor din audit, valori [NEVERIFICAT], contractul de date, cerințe de testare

---

## A. Domeniu și ipoteze

### A.1 Rețele acoperite

| Rețea | Tensiune | Conductoare | Unde se folosește |
|---|---|---|---|
| trifazată | 3 × 400/230 V, 50 Hz | L1, L2, L3, N, PE (sau PEN în amonte de separare) | implicit |
| monofazată | 230 V, 50 Hz | L, N, PE | BMPM, circuite finale, prosumator monofazat, CEF monofazat (v1.2, C.3 pct. 11) |

- Tensiuni de calcul: Un = 400 V, U0 = 230 V (`norme.U_N_V`, `norme.U_0_V`). Nu se calculează la 380/220 V.
- **Câmpul `retea` (v1.2):** se acceptă numai „tri” și „mono”, plus sinonimele evidente „trifazat”/„trifazic” și „monofazat”/„monofazic”, fără diferență de majuscule. Orice altă valoare („bi”, „3f+N”, număr) → **V12 BLOCANT** (nu se mai face calcul amestecat Ib monofazat / bloc trifazat). **R2:** `null` la orice câmp enumerat (`retea`, `schema_pamant`, `pornire`, `receptor`, `origine`, `masura_ceruta`, `material`, `metoda` …) = câmp absent (valoarea implicită, declarată); tip non-text → V12. Valorile enumerate invalide (`pornire` ∉ {directa, stea_triunghi, soft, vfd}, `receptor`, `prot_tip`, `curba`, `celula_trafo`, `PE_loc`, `rol`) → **V12 „camp”**; material/izolație/metodă → V10.
- **v1.5 — rețeaua obligatorie** la `bransament`, `prosumator` și `locuinta`: lipsă sau `null` → **V07 BLOCANT** pe obiectul „retea” („rețeaua nu este specificată”), remediere „alege monofazat 230 V (BMPM) sau trifazat 3 × 400 V (BMPT), conform ATR”; nu se mai presupune „tri” (BMPM / BMPT, Q, DDR 2P / 4P și fazele depind de ea). Tabloul, PT, CEF și GE rămân trifazate implicit (JT industrial, declarat). Sinonime acceptate în plus (fără diacritice, fără diferență de majuscule): „trifazată”, „trifazică”, „3f”, „monofazată”, „monofazică”, „1f”. Locuința întoarce rețeaua normalizată în `rez["retea"]` (constructorul o citește de acolo).
- Rețeaua MT pentru PT: 20 kV (`norme.MT_UN_KV`). Alte tensiuni MT (6, 10, 110 kV) sunt în afara domeniului.

### A.2 Scheme de legare la pământ

| Schemă | Unde | Reguli |
|---|---|---|
| TN-C-S | branșamente DEER | PEN-ul OD intră în BMPT/BMPM și se separă pe bareta de nul (BN) în N + PE. În aval se lucrează în TN-S. |
| TN-S | toată instalația din aval de BN și instalațiile alimentate din PT propriu | PE separat de N pe tot traseul. |
| TN-C (porțiuni) | doar dacă utilizatorul o cere explicit, între PT propriu și un tablou | PEN ≥ 10 mm² Cu / 16 mm² Al, numai în instalații fixe și **niciodată în aval de un DDR** (I7-2011 art. 3.3.2.11.1, SR HD 60364-5-54 art. 543.4) → altfel V27 BLOCANT. |
| TT | doar la cerere (ex. instalații rurale fără PEN fiabil) | DDR obligatoriu pe fiecare circuit; RA·IΔn ≤ 50 V (V34). |

IT nu este acoperit. **v1.2:** `schema_pamant` se normalizează (majuscule, „_”/spațiu → „-”). Valori acceptate pe tip de schemă: branșament TN-C-S, TT; tablou TN-C-S, TN-S, TT, TN-C; prosumator și CEF fără PT TN-C-S, TN-S, TT; CEF cu PT și GE TN-S, TN-C-S; PT TN-S, TN-C-S, TN-C. Orice altă valoare (IT, „TN-C” la GE/CEF, text necunoscut) → **V28 BLOCANT** „schemă neacoperită”. TN-C la branșament/prosumator sau la un tablou alimentat din rețeaua publică (în aval de RCCB-ul BMPT) → **V27 BLOCANT**. TN-C admis: tablou cu `origine = "pt_propriu"` fără DDR în amonte (C1 = PEN ≥ 10 Cu / 16 Al, altfel V27) și plecările nivel 0 din TGJT (fără DDR pe circuit, PEN ≥ 10/16). Nota 3 de pe planșă (G.1) se generează din valoarea efectivă (câmpurile de rezultat `schema_pamant`, `nota_schema_pamant`).

### A.3 Ce NU acoperă aplicația. Se declară pe planșă ca notă fixă (vezi G.1)

1. Dimensionarea racordului OD (C1, LEA/LES JT, celula de racord MT): aparține OD și se ia din ATR.
2. Legătura trafo → TGJT în PT (bare sau cabluri monopolare): se preia din documentația producătorului PT.
3. Partea MT în afara celulei trafo: protecții de linie, reglaje, selectivitatea cu OD, tensiunile de atingere/pas (NTE 001, STAS 12604). **v1.3:** rezistența de dispersie a prizei (electrozi în linie + platbandă) se calculează la cerere (cheia `priza`, §C.7); priza în contur/plasă a PT și verificarea tensiunilor de atingere și pas rămân în afara domeniului.
4. Posturi cu mai mult de un trafo, Sn > 2500 kVA, CEF cu S > 2500 kVA (interpretorul refuză, vezi F.7).
5. Calculul instalației de paratrăsnet și dimensionarea SPD prin analiză de risc (SR EN 62305-2). Aplicația pune SPD T1+T2 la intrare și T2 pe c.c. cu valori tip.
6. Selectivitatea „totală” între aparate de producători diferiți. Aplicația aplică regulile simplificate din B.18 și cere confirmarea cu tabelele producătorului.
7. Regimurile tranzitorii: pornirea motoarelor > 30 kW cu soft-starter/VFD, armonici peste armonica 3, rezonanță cu bateria de condensatoare.
8. Compensarea puterii reactive (doar simbolul, fără dimensionare).
9. Protecția de interfață a CEF de categorie B…D (reglajele se iau din ATR și din Ord. ANRE 208/2018).
10. Rețele IT, c.c. de distribuție, rețele navale și medicale (grupa 2).

### A.4 Ipoteze generale de calcul

- Regim permanent simetric. Sarcinile trifazate sunt echilibrate. Pentru monofazat se folosește bucla fază + neutru.
- Iz se ia din SR HD 60364-5-52:2011 (= IEC 60364-5-52:2009, tab. B.52.2–B.52.13), cu factorii de corecție din tab. B.52.14–B.52.19. **Nu** se folosesc tabelele vechi (metoda D la 1 K·m/W): aceasta e constatarea P1-1.
- Scurtcircuit după SR EN 60909-0 (metoda tensiunii echivalente), cu c_max = 1,10 și c_min = 0,95.
- Toate valorile implicite sunt **declarate** în răspunsul interpretorului, în memoriul de calcul și în nota de ipoteze de pe planșă (G.2).

---

## B. Lanțul de dimensionare al unei ramuri

O **ramură** = aparat de protecție + cablul pe care îl protejează + sarcina de la capăt (receptor sau tablou). Fiecare ramură se calculează cu **contextul de amonte** (valorile la bara de origine).

### B.0 Valori implicite (se folosesc doar dacă utilizatorul nu dă altceva; toate se declară)

| Mărime | Valoare implicită | Sursă / motiv |
|---|---|---|
| cosφ forță, iluminat, prize, tablou | 0,90 | DECIZIE conservatoare (cosφ mai mic → Ib mai mare); `COSFI_IMPLICIT` |
| cosφ motor | 0,85 | DECIZIE |
| cosφ invertor / PCS | 1,0, dar curentul se ia din Smax (B.2) | — |
| ks tablou | IEC 61439-2 tab. 101: 1 plecare → 1; 2–3 → 0,9; 4–5 → 0,8; 6–9 → 0,7; ≥ 10 → 0,6 | `ks_implicit()` |
| material, izolație | cabluri în pământ: Al, PVC (ACYAbY); circuite interioare: Cu, PVC | DECIZIE: PVC are Iz mai mic (conservator) |
| metodă de pozare | în pământ: **D1** (tub); sub-plecări interioare: **C**; „pat de cabluri/aer”: **E** | DECIZIE (B.7.3) |
| temperatură | aer 30 °C, sol 20 °C | condițiile de referință |
| rezistivitate termică sol | 2,5 K·m/W | condiția de referință (sol uscat, conservator) |
| grupare | fără (trasee separate) | se declară; textul „același traseu/pat/șanț” activează gruparea |
| lungime coloană BMPT (C2), alimentare tablou, plecări | 50 m | se declară + V11 |
| lungime sub-plecări (circuite din TD) | 25 m | se declară |
| lungime cablu invertor CEF | 30 m; prosumator 15 m | se declară |
| armonica 3 (h3) | necunoscută → neutru = fază | conservator (B.10) |
| rețea OD la delimitare: Ik3max | 25 kA, R/X = 0,1 | majorant (trafo OD ≤ 630 kVA, uk 4 %, la borne) — [DECIZIE proiectant 28.10.2026, Î7] |
| rețea OD: impedanța buclei fază–PEN | Zb = 0,2683 + j0,1342 Ω (\|Z\| = 0,30 Ω, urban LES); rural (`alimentare.zona`) 0,8 Ω | [DECIZIE proiectant 28.10.2026, Î2] — calculul verificatorului (raport #2–#3); înainte 0,201 / 0,45 Ω |
| Zb implicit când Ik3 OD e dat (v1.2, M9) | Zb = (max(0,2683; 2·R_Q) ; max(0,1342; 2·X_Q)) | bucla dus–întors pe aceeași rețea; garantează Ik1min ≤ Ik3max pe orice ramură; declarat |
| Zb OD dat ca modul \|Z\| (v1.2, M2) | R/X = 2 (ca la valoarea implicită): R = \|Z\|·0,894, X = \|Z\|·0,447 | ATR-urile dau de regulă doar modulul; declarat |
| lungimi GE + ATS (v1.2) | C1 rețea → ATS și C3 ATS → consumatori: `L_C1_m` / `L_C3_m` sau `L_m`, altfel 50 m; C2 GE → ATS: `L_C2_m`, altfel 20 m | se declară |
| pornire motor (v1.2) | directă (Ip = 6·Ib, cosφ 0,35, tp ≤ 10 s) | B.3.1 |
| rețea MT (PT propriu) | S"kQ = 500 MVA, R/X = 0,1 | majorant — DEPENDENT DE OD [practică, raport #4] |
| trafo | după `norme.TRAFO`: uk 4 % ≤ 630 kVA, 6 % ≥ 800 kVA; Pk Tier 2 | SR EN 50588-1, Reg. UE 548/2014 |
| origine ΔU | punctul de delimitare (rețea publică) sau bara JT a PT propriu | I7-2011 |

> **Principiul valorilor implicite (DECIZIE).** O valoare implicită pentru rețeaua OD **nu are voie** să ducă la mărirea automată a cablului. Dacă o verificare pică doar din cauza ei, rezultatul e AVERTISMENT, cu cererea de a introduce valoarea reală (V32, V35, V36). Excepție: Icu. Acolo implicitul e majorant și aparatul se alege automat ≥ Ik3max.

### B.1 Date de intrare ale unei ramuri

```
ramura = {
  "rol":        "plecare" | "final" | "intrare" | "invertor" | "qg" | "q_trafo",
  "receptor":   "iluminat" | "prize" | "forta" | "motor" | "tablou" | "invertor" | "pcs",
  "retea":      "tri" | "mono",
  # sarcina — exact una din:
  "P_kW": float,            # putere activă instalată Pi
  "In_A": int,              # plecare dată prin calibru („plecare de 63 A”)
  "Pn_kW": float, "Iac_max_A": float|None,   # invertor/PCS
  "ks": float (implicit 1), "cosfi": float (implicit B.0), "h3_pct": float|None,
  # protecție (opțional — altfel se alege automat, B.3)
  "prot_tip": "MCB"|"MCCB"|"ACB"|"gG", "curba": "B"|"C"|"D", "In_fortat": int, "Icu_fortat": float,
  # cablu
  "cablu": {"L": m, "material": "Cu"|"Al", "izolatie": "PVC"|"XLPE",
            "metoda": "C"|"D1"|"D2"|"E", "theta": °C, "rho_sol": K·m/W,
            "n_alte": circuite vecine pe traseu, "distanta": "atingere"|0.25|0.5|1.0,
            # secțiune impusă de utilizator (opțional):
            "S_fortat": mm², "n_fortat": int, "N_fortat": mm², "PE_fortat": mm², "PE_loc": "cablu"|"separat"}
}
context_amonte = {
  "Zq": (R, X) Ω       # impedanța de secvență pozitivă până la bara de origine, pentru Ik3max
  "Zb": (R, X) Ω       # impedanța buclei fază–PE până la bara de origine, pentru Ik1min
  "Ik3_kA": float      # Ik3max la bara de origine
  "dU_pct": float      # ΔU cumulat la bara de origine
  "origine": "retea_publica" | "pt_propriu"
  "z_implicit": bool   # Zb provine din valoarea implicită OD
  "ik3_implicit": bool # Ik3 provine din valoarea implicită OD
  "ddr_amonte": bool   # există DDR în amonte (ex. RCCB din BMPT)
  "ddr_ramura": str|None # DDR propriu al ramurii (ex. RCBO în BMPM)
  "are_aval": bool     # ramura alimentează un tablou cu aparate în aval
}
```

### B.1.1 Contractul de intrare al schemei (câmpuri adăugate la arbitraj, v1.1)
Pe lângă câmpurile folosite în `cazuri_golden.json` v1.0, motorul TREBUIE să accepte:

| Schemă | Câmp | Tip | Ce face motorul | Caz golden |
|---|---|---|---|---|
| `bransament` | `Ib_A` | float > 0 | Ib = Ib_A direct (fără P și fără cosφ). Blocul, Q, TC și C2 se aleg cu acest Ib. cosφ (implicit 0,9) se folosește doar la ΔU. Nu se scrie „Pa = … kW” pe planșă (Pa necunoscut). Exclusiv cu `P_kW`/`S_kVA`: mai multe date simultan → V12 BLOCANT. | B23 |
| `bransament` | `S_kVA` | float > 0 | Ib = S·1000/(√3·400) (tri) sau S·1000/230 (mono), fără cosφ. cosφ doar pentru ΔU. | B24 |
| `tablou` | `circuite_finale` | bool (implicit false) | Tabloul e un TD cu **circuite finale**: toate plecările au rol „final” (B.3 rândul 2: MCB B pentru iluminat/prize, C pentru restul; MCCB peste 63 A), receptorul din `receptor` sau din nume (C.2), implicit „forță”. Cablurile implicite sunt Cu PVC metoda C la 30 °C, L = 25 m. Timpul de deconectare e 0,4 s pentru circuitele ≤ 63 A. Q1 și alimentarea se tratează ca la TG (C.2 pct. 4–7); estimarea Ip_aval folosește seria MCB. Circuitele de prize primesc DDR 30 mA tip A (C.2 pct. 10). | K03 |
| `tablou` | `origine` | `"retea_publica"` (implicit) \| `"pt_propriu"` | `pt_propriu`: limitele ΔU sunt 6 %/8 % (bara tabloului secundar 6 %), **fără** DDR în amonte (`ddr_amonte = false`). Sursa: dacă `pt_Sn_kVA` e dat, contextul e bara JT a trafo (B.13, B.14, ca la C.5, cu ik3_implicit = z_implicit = false). Altfel Ik3max = 25 kA și Zb = 0,18 + j0,09 Ω implicite (ik3_implicit = z_implicit = true → V32/V35/V36 AVERTISMENT, fără mărire automată). | T15 (fără Sn), T16 (cu Sn) |
| `tablou` | `pt_Sn_kVA` | int ∈ `TRAFO_SN_KVA` | numai cu `origine = "pt_propriu"`: sursa e trafo-ul. Altă valoare → V05. | T16 |
| `ge_ats` | (ieșire) `Sn_GE_minim_kVA` | int | `norme.ge_sn_minim(P_sarcina_kW)` (C.6 pct. 5) | G01–G03 |
| `bransament` | `cablu` (v1.2) | dict B.1 (`material`, `izolatie`, `metoda`, `theta`, `rho_sol`, `n_alte`, `S_fortat`, `n_fortat`, `N_fortat`, `PE_fortat`, `PE_loc`) | coloana C2 se calculează cu el ca orice plecare de tablou (V02/V03/V13 la `S_fortat`). Câmpurile la nivelul schemei rămân acceptate; `cablu` are prioritate. Material nedat și `S_fortat` < 16 → Cu. | test_verificare2 M1 |
| `bransament` | `Q_In_A` (v1.2) | int | Q impus: trebuie ≥ Ib (altfel V04) și în seria unui bloc ST 4-JT (altfel V05); blocul se alege astfel încât să-l conțină | M-minore |
| `bransament` | `bmpt_fortat` (v1.2) | tip ST 4-JT | Imax bloc < Ib → **V50 BLOCANT** (nu se mai înlocuiește tacit) | idem |
| toate | `Zb_OD_ohm` (v1.2) | (R, X), {R, X} sau număr \|Z\| | B.0; valori ≤ 0 → V07 BLOCANT | M2 |
| `tablou`/`pt` | `plecari[].DDR` = false (v1.2) | bool | refuz explicit al DDR pe un circuit de prize ≤ 32 A → V29 BLOCANT | C4 |
| `tablou`/`pt` | `plecari[].pornire` (v1.2) | „directa” (implicit la motor), „stea_triunghi”, „soft”, „vfd” | B.3.1 (Ip/Ib = 6 / 2 / 3 / 1) | M10 |
| `cef` | `retea` (v1.2) | „tri” \| „mono” | C.3 pct. 11 | C3 |
| `ge_ats` | `L_C1_m`, `L_C2_m`, `L_C3_m`, `L_m`, `cablu`, `Ib_sarcina_A`, `In_Q_retea_A`, `In_QG_A` (v1.2) | | C.6 pct. 6 | C1/minore |
| `cef` | `racord`, `L_racord_m`, `cablu_C0`, `racord_In_Q_A`, `racord_Q_tip`, `racord_Icu_kA`, `Ik3_TG_kA`, `Zb_TG_ohm`, `invertoare[].L_m`, `invertoare[].cablu` (v1.3, P0-2) | | C.3 pct. 12 | tests/test_cef_racord.py |
| `locuinta` | `retea` (obligatoriu), `alimentare` {tip, In_Q_bransament_A, P_aprobata_kW, L_coloana_m, cablu, pozare_coloana (v1.5), zona: „urban” | „rural” (v1.6)}, `circuite[]` {nume, receptor, P_kW, L_m, faza, cablu, In_A, DDR, cosfi, curba}, `ks`, `Q_general_tip` (v1.4) | | C.8 | tests/test_locuinta.py |
| toate | `priza` (v1.3) | dict §C.7 | calculul prizei de pământ (rez["priza"], V37); fără cheie → nu rulează, nota 2 rămâne „priza de pământ (calcul separat)” | tests/test_pamant.py |
| `tablou` | `Q1_DDR` (v1.3) | {IdN_mA ∈ {10, 30, 100, 300, 500, 1000}, selectiv: bool (tip S, implicit false), dt_s: (0; 1] s (releu / bloc diferențial reglabil, R5), tip: AC/A/F/B} | DDR general impus pe Q1 (verificat, nu modificat); IdN_mA în afara seriei → V12 | tests/test_selectivitate_ddr.py |
| `tablou`/`pt` | `plecari[].DDR` = dict (v1.3) | ca `Q1_DDR` | DDR impus pe plecare / circuit; prize ≤ 32 A cu IΔn > 30 mA → V29 BLOCANT; TT cu RA·IΔn > 50 V → V34 BLOCANT | idem |
| `tablou`/`prosumator`/`cef` | `IdN_amonte_mA` (v1.3: și în TN), `DDR_amonte_selectiv` (bool, implicit true; la BMPM implicit false) | | DDR-ul din amonte pentru §B.18.1 (altfel RCCB BMPT 300 mA S / RCBO BMPM 300 mA) | idem |

### B.2 Puterea și curentul de calcul

**Validări prealabile** (în ordinea aceasta; prima care pică oprește ramura):
1. `cosfi` ∉ (0; 1] → V08 BLOCANT.
2. `L` ≤ 0 → V09 BLOCANT. `L` > 1000 m → V09 AVERTISMENT (continuă).
3. `P_kW` ≤ 0 → V07 BLOCANT.
4. `ks` ∉ (0; 1] → V10 BLOCANT.

**Validarea intrării schemei (v1.2, înainte de orice calcul):** fiecare câmp numeric trebuie să fie un număr finit (text, NaN, ∞ → V07 BLOCANT „valoare nenumerică”) și plauzibil: P, S, Ib, In, Pn, Iac, kWh, P_sarcina, Ib_sarcina, Sn_GE, Ik3_OD, S"kQ, RA, calibre impuse > 0 (V07); Sn trafo > 0 (V05); lungimi > 0 (V09); cosφ ∈ (0; 1] (V08); ks ∈ (0; 1] (V10, inclusiv `ks` la nivelul tabloului); x"d ∈ (0; 1] u.r. (V07); h3 ∈ [0; 100] %; n (invertoare), n_module, n_stringuri, n_fortat întregi ≥ 1; kWp ≥ 0 și > 0 când există invertoare PV; ρ sol > 0, n_alte întreg ≥ 0 (V10). Material ∉ {Cu, Al}, izolație ∉ {PVC, XLPE}, metodă ∉ `METODE_POZARE` → V10; tip protecție ∉ {MCB, MCCB, ACB, gG}, curbă ∉ {B, C, D} → V07. Tip de schemă necunoscut → V07 „tip de schemă necunoscut”. Tablou/PT fără plecări → V07. Nicio valoare absurdă nu se mai înlocuiește tacit (ex. x"d = 0 → 0,12, Ik3 = −3 → 3). Eroarea internă rămasă (dacă apare) se raportează ca V07 „date de intrare incomplete sau invalide (câmpul … lipsește)”, niciodată ca text Python brut.

**Curentul de calcul Ib [A]:**

| Caz | Formulă |
|---|---|
| sarcină în kW, trifazat | Pc = ks·Pi ; **Ib = Pc·1000 / (√3·400·cosφ)** |
| sarcină în kW, monofazat | **Ib = Pc·1000 / (230·cosφ)** |
| sarcină în kVA (ex. „BMPT 25 kVA”, câmpul `S_kVA`) | Ib = S·1000/(√3·400) (fără cosφ) |
| curent dat direct (câmpul `Ib_A`, ex. „BMPT 200A”) | Ib = Ib_A |
| plecare dată prin calibru | **Ib = In_A** (DECIZIE conservatoare: „Ib presupus = In”), declarat |
| invertor / PCS (tri) | Iac,max = valoarea din fișă; dacă lipsește: **Iac,max = 1,1·Pn·1000/(√3·400)**. Ib = Iac,max |
| invertor (mono) | Iac,max = 1,1·Pn·1000/230 |

**Curentul minim al protecției Ip,min:**
- general: Ip,min = Ib;
- invertor/PCS: **Ip,min = max(Iac,max ; 1,25·Pn·1000/U)**, cu U = √3·400 sau 230 (DECIZIE: regim continuu de durată, aparat în carcasă; `FACTOR_IP_INVERTOR`);
- intrare de tablou: Ip,min = max(Ib_tablou ; Ip_max,aval + 0,01 A) — vezi C.2 (amontele strict mai mare decât cel mai mare aval).

Exemplu (cazul C04): invertor 110 kW → Iac,max = 1,1·110 000/692,82 = 174,65 A; 1,25·110 000/692,82 = 198,46 A → Ip,min = 198,46 A.

### B.3 Alegerea tipului de protecție (când utilizatorul nu îl impune)

| Rol | Ip,min ≤ 63 A | 63 < Ip,min ≤ 630 A | 630 < Ip,min ≤ 1600 A | Ip,min > 1600 A |
|---|---|---|---|---|
| plecare dintr-un TG / TGJT (distribuție) | gG (separator cu siguranțe NH) | gG | MCCB | ACB |
| circuit final într-un TD | MCB: **B** pentru iluminat și prize, **C** pentru restul (D doar la cerere) | MCCB | MCCB | ACB |
| intrare tablou (Q1), invertor, PCS | MCB C | MCCB | MCCB | ACB |
| QG CEF, Q JT trafo | MCCB | MCCB | MCCB | ACB |
| branșament BMPT / BMPM | conform C.1 (ST 4-JT / ST 3-JT) | | | |

Seria maximă: MCB 125 A, gG 1250 A, MCCB 1600 A, ACB 4000 A. Dacă Ib depășește calibrul maxim al tipului impus sau 4000 A → **V06 BLOCANT** „Ib > In maxim”.

### B.3.1 Motor cu pornire directă (v1.2, M10; R2: ΔU_sursă se calculează cu (Ip − Ib), fără dubla numărare a ΔU_origine)
Receptor „motor” cu `pornire` „directa” (implicit): Ip = 6·Ib (stea-triunghi 2·Ib, soft-starter 3·Ib, VFD fără verificare), tp ≤ 10 s (`norme.MOTOR_*`). Protecția trebuie să NU declanșeze la Ip:
- tip neimpus pe o plecare (unde B.3 ar da gG) → **MCCB TM** (întreruptor-motor): prag 0,8·Im = 8·In ≥ 6·Ib; Ir ≥ Ib, cablul la Ir (DECIZIE: fără supradimensionarea cablului cerută de o siguranță gG mărită);
- MCB (circuit final): pragul instantaneu inferior (B 3·In, C 5·In, D 10·In) ≥ Ip — In crește în serie, curba rămâne;
- gG impus: poarta Imin(10 s) din SR EN 60269-1 (`GG_PORTI_A[In][0]`) ≥ Ip — In crește (ex. 45 kW, Ib 76,4 A → gG 160 A);
- calibru impus (In_A / In_fortat) care nu satisface condiția → **V23 AVERTISMENT**; calibru ales/mărit → V23 INFO.
- ΔU la pornire (V22): ΔU_porn = ΔU_origine + ΔU_sursă(Ip, Z_Q al barei) + ΔU_cablu(Ip), cu cosφ 0,35 (conservator). > 12 % → **V22 AVERTISMENT**. Rezultatul ramurii primește `pornire`, `Ip_pornire_A`, `dU_pornire_pct`.

### B.4 Seriile standard (în `norme.py`)

| Tip | Serie In [A] | Capacitate de rupere [kA] |
|---|---|---|
| MCB (SR EN 60898-1) | 6, 10, 13, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125 | Icn: 6, 10, 15, 25 (min. 6) |
| MCCB (SR EN 60947-2) | 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250, 320, 400, 500, 630, 800, 1000, 1250, 1600 | Icu: 25, 36, 50, 70, 100, 150 |
| ACB | 630, 800, 1000, 1250, 1600, 2000, 2500, 3200, 4000 | Icu: 42, 50, 65, 85, 100, 130 |
| gG NH (SR EN 60269-1/-2) | 2, 4, 6, 10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250 | **120 kA** (v1.2, SR EN 60269-2; înainte 50 kA, ceea ce bloca plecările unui PT 2500 kVA). SF din BMPT rămâne „50 kA” (cerința ST 4-JT). |
| gPV (SR EN 60269-6) | 1…32 (`GPV_IN_A`) | — |
| RCCB | 16, 25, 40, 63, 80, 100, 125. **Peste 125 A nu există RCCB modular:** bloc diferențial asociat MCCB-ului (In = In MCCB) — câmpul `aparat = "bloc_diferential"`, șablonul E.3 „Bloc diferențial” (v1.2, M11). DDR general (300 mA, BMPT) în amontele DDR-urilor de 30 mA → **selectiv, tip S** (`selectiv = true`). | IΔn: 10, 30, 100, 300, 500, 1000 mA |
| TC (SR EN 61869-2) | `TC_PRIMAR_A`, secundar 5 A | Sn: 2,5 / 5 / 10 / 15 VA |

Gabaritul NH după In: ≤ 100 A NH000, ≤ 160 NH00, ≤ 250 NH1, ≤ 400 NH2, ≤ 630 NH3, ≤ 1250 NH4a.

### B.5 Alegerea calibrului (In, Ir) și a capacității de rupere

1. **MCB, gG:** In = cea mai mică valoare din serie ≥ Ip,min. Ip = In.
2. **MCCB:** In = cea mai mică valoare din serie ≥ Ip,min.
   - In ≤ 250 A → declanșator **termomagnetic (TM)**: Ir ∈ {0,70; 0,75; …; 1,00}·In, **Im = 10·In** (fix), dar **cel puțin 500 A la In ≤ 50 A** (`norme.im_tm`) [VERIFICAT: ABB Tmax T1/XT1 TMD, Schneider TM-D — raport #29]. La motorul cu pornire directă (MCCB „întreruptor-motor” în locul gG) Im = min(13·In; im_tm) (GV2 / 3RV2, raport #53).
   - In ≥ 320 A → **electronic (EL, LSI)**: Ir ∈ {0,40; 0,45; …; 1,00}·In; Isd ∈ {1,5; 2; 2,5; 3; 4; 5; 6; 7; 8; 10}·Ir; Ii = 12·In; tsd = 0,1 s când există aparate în aval.
   - Ir = (cel mai mic multiplu din treaptă ≥ Ip,min/In)·In. **Ip = Ir.**
3. **ACB:** ca MCCB electronic.
4. **Isd (electronic):** cel mai mare multiplu m din serie cu 1,2·m·Ir ≤ Ik1min la capătul cablului protejat (B.15). Dacă niciunul nu satisface condiția, m = 1,5 și deconectarea pică (V30).
5. **Calibru impus de utilizator:** trebuie să existe în serie, altfel **V05 BLOCANT** „calibru inexistent”. Dacă Ib > Ip → **V04 BLOCANT**.
6. **Capacitatea de rupere:** cea mai mică valoare din serie ≥ Ik3max la bara pe care e montat aparatul (B.13). MCB: dacă Ik3max > 25 kA → se trece pe MCCB (dacă tipul nu e impus).

Exemplu: Ib = 240,56 A, MCCB → In = 250; 240,56/250 = 0,962 → treapta 1,00 → Ir = 250 A.

### B.6 Condiția de coordonare cablu–protecție (SR HD 60364-4-43 art. 433.1)

```
Ib ≤ Ip ≤ Iz'      și      I2 ≤ 1,45·Iz'
```

| Aparat | I2 (curent convențional de funcționare) | Sursă |
|---|---|---|
| MCB | 1,45·In | SR EN 60898-1 |
| MCCB, ACB | 1,30·Ir | SR EN 60947-2 tab. 6 |
| gG, In ≥ 16 A | 1,60·In | SR EN 60269-1 tab. 2 |
| gG, 4 < In < 16 A | 1,90·In | IEC 60269-1 (ed. 2006 tab. 2 / ed. 2024 tab. 3) [VERIFICAT: raport #32] |
| gG, In ≤ 4 A | 2,10·In | idem [VERIFICAT] |
| gPV | 1,45·In | SR EN 60269-6 |

**Iz' minim cerut:** `Iz_min = max(Ip ; I2/1,45)`. Rezultă: MCB → Iz_min = In; MCCB → Iz_min = Ir; gG ≥ 16 A → Iz_min = 1,1034·In.

Dacă utilizatorul declară armonica 3 între 15 % și 33 %: Iz_min = Iz_min/0,86. Peste 33 %: vezi B.10.

### B.7 Curentul admisibil corectat Iz' = n·Iz·kθ·kgrup·ksol

#### B.7.1 Iz din tabel
`Iz = norme.iz_tabel(material, izolatie, metoda, n_incarcate, S)`: n_incarcate = 3 pentru trifazat, 2 pentru monofazat. Tabelele (Prysmian 2024, reproducere IEC 60364-5-52:2009) sunt verificate, cu excepția Al 16 mm² [NEVERIFICAT].

Valori de control (3 conductoare încărcate, PVC):

| S [mm²] | Cu C | Cu D1 | Cu D2 | Cu E | Al D1 | Al D2 | Al E |
|---|---|---|---|---|---|---|---|
| 16 | 76 | 64 | 70 | 80 | 49* | 52* | 61* |
| 50 | 144 | 116 | 130 | 153 | 91 | 99 | 117 |
| 120 | 259 | 192 | 220 | 276 | 150 | 169 | 212 |
| 240 | 403 | 280 | 320 | 430 | 218 | 250 | 330 |
(* [NEVERIFICAT])

> Codul vechi folosea pentru „D” valorile pentru **2** conductoare încărcate (Cu PVC 16 mm² = 81 A, Al 240 = 283 A) și le aplica la trifazat. Tabelul corect dă 64 A, respectiv 218 A.

#### B.7.2 Factorii de corecție
- **kθ**: B.52.14 (aer; metodele C, E, F) sau B.52.15 (sol; D1, D2), după izolație. Pentru temperaturi intermediare se ia **rândul cu temperatura imediat superioară**, fără interpolare. Peste maximul tabelului → V10 BLOCANT.
- **ksol**: B.52.16, doar pentru D1/D2; rezistivitatea intermediară → rândul imediat superior; peste 3 K·m/W → V10 BLOCANT.
- **kgrup**: numărul de circuite = **n_paralel + n_alte**. Fiecare cablu din paralel contează ca un circuit.
  - D1 → B.52.19 (tuburi, „atingere” implicit); D2 → B.52.18; C → B.52.17 rândul „perete”; E → B.52.17 „pat_perforat” (sau „scară” la cerere).
  - n intermediar (ex. 10, 13) → rândul cu n imediat superior. Pentru C/E peste 9 circuite → valoarea de la 9 (nota tabelului). n > 20 → V10 BLOCANT.
- k = kθ·ksol·kgrup; **Iz' = n·Iz·k**.

#### B.7.3 Metoda de pozare implicită — DECIZIE
Un cablu în pământ trece la DEER prin tuburi de protecție la subtraversări și la intrarea în clădire. Conform SR HD 60364-5-52 art. 523, Iz se stabilește pentru porțiunea cea mai defavorabilă, deci implicitul este **D1**. D2 se folosește numai dacă utilizatorul scrie „direct în pământ” și confirmă că nu există tuburi.
**v1.4:** metoda **B2** (cablu multipolar în tub pe perete / îngropat în perete, numai Cu, grupare după B.52.17 „strâns”) e implicită la circuitele de locuință (§C.8).

### B.8 Tipuri de cablu și secțiuni

| Material | Izolație | Armat (pământ) | Nearmat (aer) | Secțiuni multipolare permise [mm²] |
|---|---|---|---|---|
| Cu | PVC | CYAbY | CYY-F | 1,5 … 240 |
| Cu | XLPE | C2XAbY [practică, raport #9] | N2XY | 1,5 … 240 |
| Al | PVC | ACYAbY | ACYY [VERIFICAT: ST 80-6 DEER] | 16 … 240 |
| Al | XLPE | AC2XAbY | NA2XY | 16 … 240 |

**E2 (raportul verificatorului #9):** notația după standardul de produs / ST 80-6 DEER — „Ab” = armătură din bandă de oțel, cu
„b” mic: **CYAbY, ACYAbY** (și C2XAbY, AC2XAbY), peste tot (planșă, listă, memoriu, deviz, documente). Citirea textelor
(denumirea impusă, V80, FE180) nu ține cont de majuscule, deci proiectele vechi cu „CYABY” se citesc la fel.

Secțiunile minime:
- **Cu** iluminat 1,5; prize, forță, motor, invertor 2,5; coloane spre tablouri 4; **orice cablu în pământ ≥ 6** (DECIZIE mecanică).
- **Al** ≥ 16 (cablu armat). Regula Al → Cu de mai jos.

**Algoritmul de căutare a secțiunii:**
```
pentru n = 1, 2, 3, 4:                      # N_PARALEL_MAX_MULTIPOLAR = 4 (DECIZIE)
    k = kθ·ksol·kgrup(n + n_alte)
    pentru S în SECTIUNI_MULTIPOLAR[material] crescător, S ≥ S_min:
        dacă n·Iz(S)·k ≥ Iz_min: → soluția (n, S); STOP
```
Se ia cel mai mic n, apoi cea mai mică S.

**Dacă nu există soluție** (nici la 4 × 240 mm²), se încearcă pe rând, sărind combinația curentă: (material, XLPE) → (Cu, PVC) → (Cu, XLPE). Prima care reușește se folosește, cu **V45 AVERTISMENT** „s-a trecut pe …”. Dacă nu reușește niciuna → **V01 BLOCANT** „ramura nu poate fi dimensionată” (remediere: bare capsulate, alt punct de racord sau împărțirea sarcinii). Nu se scrie niciodată „300 mm²” tăcut (P0-1).

**Regula Al → Cu (DECIZIE, cerință din temă):** se fac ambele calcule complete, pentru Al (cu S_min = 16) și pentru Cu, inclusiv bucla ΔU (B.12). Dacă soluția Al este 1 × 16 mm² și soluția Cu este 1 × S ≤ 10 mm², se alege **Cu** și se emite V48 INFO. Altfel rămâne Al.

**Secțiune impusă de utilizator** (`S_fortat`): nu se caută și nu se mărește nimic. Se verifică doar:
- S există în `SECTIUNI_MULTIPOLAR[material]` → altfel V13 BLOCANT;
- Ip ≤ Iz' → altfel **V02 BLOCANT**;
- I2 ≤ 1,45·Iz' → altfel **V03 BLOCANT**;
- ΔU, deconectarea și stabilitatea termică → BLOCANT dacă pică (fără mărire automată).

**R3 (N3-C1):** trecerea în aer (metoda F) e permisă numai dacă metoda nu a fost cerută explicit (sau a fost cerută în aer: C/E). La metoda cerută în pământ (D1/D2) sistemele monopolare Cu XLPE în treflă se dimensionează cu tabelele metodei (Iz D1/D2, ≤ 300 mm²) și gruparea B.52.18/B.52.19 (fiecare treflă = un circuit), ≤ 6 sisteme; altfel V01 BLOCANT. La metoda implicită, nota de ipoteze (G.2) conține explicit „pozare pe pat de cabluri în aer, monopolare în treflă … pentru {ramuri}”. Codul de metodă „F” fără variantă e respins (V10); se acceptă `F_trefla`, `F_atingere`. Rezultatul ramurii are `monopolar: true`.
**R2 (N-M5) — cabluri monopolare:** dacă nicio combinație multipolară (≤ 4 × 240 mm², inclusiv fallback-ul Cu XLPE) nu satisface Iz_min, la trifazat se încearcă automat sisteme de cabluri monopolare Cu XLPE (N2XY) în treflă pe pat perforat, distanțate ≥ 2·De (metoda `F_trefla`), secțiuni 25…300 mm², până la **6 sisteme** în paralel (`norme.N_PARALEL_MAX_MONOPOLAR`, factor de grupare `K_GRUP_F_DISTANTAT`, B.52.21 [NEVERIFICAT]; 2 sisteme: 0,97 — raport #17). Alegerea se declară (V45 AVERTISMENT varianta F + „Am presupus”). Abia apoi V01 (remediere: bare capsulate). Text: „5 × (N2XY 4×1×300 mm² + FY 1×150 mm² (PE))”. (4 sisteme nu ajung la GE 2000 kVA: Ir 2880 A > 4·703·0,93 = 2615 A.)

### B.9 Cabluri în paralel
- n_max = 4 cabluri multipolare identice (același tip, secțiune, lungime și traseu, fără derivații). Peste 4 → V01. SR HD 60364-5-52 art. 523.7 cere ca împărțirea curentului să fie egală, deci secțiuni egale.
- Gruparea: n cabluri paralele = n circuite în kgrup (B.7.2).
- Fiecare cablu din paralel are **propriul conductor PE** (în cablu sau FY alăturat). S_PE se raportează pe cablu; în verificări se folosește totalul n·S_PE.
- Impedanțele (R, X) ale ramurii se împart la n.
- Textul pentru listă: `2 × (ACYAbY 4×120 mm² + FY 1×35 mm² (PE))`.

### B.10 Secțiunea neutrului (SR HD 60364-5-52 art. 524.2; I7-2011 anexa 5.29)
1. Monofazat: N = S.
2. Trifazat Cu S ≤ 35 mm²: cablu cu 5 conductoare egale (N = PE = S).
3. Trifazat, implicit: **N = S** („4×S”).
4. N redus este permis **numai dacă sunt îndeplinite toate condițiile**: utilizatorul declară h3 ≤ 15 %; receptorul nu este invertor, iluminat LED sau VFD; S > 16 mm² Cu / S > 25 mm² Al; N ≥ 16 mm² Cu / N ≥ 25 mm² Al; combinația există în `COMBINATII_N_REDUS` (3×25+16, 3×35+16, 3×50+25, 3×70+35, 3×95+50, 3×120+70, 3×150+70, 3×185+95, 3×240+120). La Al, 3×25+16 și 3×35+16 nu sunt permise.
5. h3 între 15 % și 33 %: N = S, iar Iz_min se împarte la 0,86.
6. h3 > 33 %: curentul în neutru este I_N = 3·(h3/100)·Ib. Iz_min = max(Iz_min ; I_N/0,86) pentru 33 % < h3 ≤ 45 % sau max(Iz_min ; I_N) pentru h3 > 45 %. N = S.
7. N impus mai mic decât S fără condițiile de la pct. 4 → **V25 BLOCANT** (remediere: N = S).

### B.11 Conductorul de protecție PE / PEN
**Compunere:**
- monofazat: cablu 3×S (L, N, PE egale), PE în cablu, k după tab. A.54.3;
- trifazat Cu S ≤ 35 mm²: 5×S, PE în cablu;
- altfel: cablu 4×S sau 3×S+N **plus** un conductor PE separat, FY Cu galben-verde, pozat lângă fiecare cablu. Se aplică k după tab. A.54.2: Cu PVC = 143.

**Secțiunea după tab. 54.2** (SR HD 60364-5-54), pe secțiunea totală de fază S_tot = n·S:
```
S_tab = S_tot            dacă S_tot ≤ 16
      = 16               dacă 16 < S_tot ≤ 35
      = S_tot/2          dacă S_tot > 35
dacă faza e Al și PE e Cu:  S_tab = S_tab · k_faza(Al, izolație) / 143    # 76/143 PVC, 94/143 XLPE
S_PE (pe cablu) = cea mai mică secțiune standard ≥ max(S_tab/n ; 4 mm²)
```
Exemplu (B11): 2 × Al 120 → S_tot = 240 → S_tab = 120 Al·76/143 = 63,8 mm² Cu → pe cablu 31,9 → **FY 1×35**.

**Verificarea adiabatică** (art. 543.1.2): `S_PE_total ≥ √(I²·t)/k`, cu `S_PE_total = n·S_PE`:
- la Ik1min de la capătul cablului, cu t din B.17;
- pentru MCCB/ACB și la Ik3max de la origine, cu t = 0,02 s (+0,1 s dacă e electronic cu tsd).

Dacă pică și S nu e impusă: un PE din cablu se mută în conductor separat și se mărește la secțiunea standard necesară (V36 INFO). Dacă singura condiție care pică e cea la Ik3max implicit → V36 AVERTISMENT. Dacă S e impusă → V36 BLOCANT. PE impus sub S_tab → **V26 BLOCANT**.

**k** (SR HD 60364-4-43 tab. 43A și SR HD 60364-5-54 tab. A.54.2/A.54.3, verificat):

| | Cu PVC | Al PVC | Cu XLPE | Al XLPE |
|---|---|---|---|---|
| fază; PE ca conductor în cablu | 115 | 76 | 143 | 94 |
| PE izolat separat, inițial 30 °C | 143 | 95 | 176 | 116 |

**PEN:** ≥ 10 mm² Cu / 16 mm² Al și ≥ S_tab; numai în instalații fixe; interzis în aval de DDR → V27 BLOCANT.

**R2:** în TN-C (`PE_loc = "PEN"`) conductorul PEN este neutrul cablului: 4 conductoare, fără PE separat, rezultatul ramurii are `PE = "PEN"`, `S_PE_mm2 = S_N_mm2`, textul „ACYAbY 4×70 mm² (PEN)”; PEN insuficient termic → V36 BLOCANT. Pentru Cu ≤ 35 mm² cu PE în cablu, dacă PE-ul nu rezistă termic, se mărește întâi secțiunea cablului (5×S, PE în cablu) și abia apoi se trece pe FY separat. Energia la Ik1min pentru aparatele limitatoare: gG în zona Ik1 ≥ Imax(0,1 s) → I²t = 2·I²t prearc max (`GG_I2T_PREARC_KA2S`); MCB B/C ≤ 32 A în zona instantanee → I²t clasa 3 (SR EN 60898-1 anexa ZA, `MCB_I2T_CLASA3_A2S`, **tabele separate pe curba B / C**, până la 10 kA; peste 10 kA — let-through-ul producătorului, fără limitare) [VERIFICAT: anexa ZA, catalogul IPD — raport #43].

### B.12 Căderea de tensiune
**Rezistența la temperatura maximă de regim** (θ = 70 °C PVC, 90 °C XLPE):
`R' = R20(S) · [1 + α·(θ − 20)]` [Ω/km], cu R20 din IEC 60228 (`R20_OHM_KM`, verificat), α_Cu = 0,00393, α_Al = 0,00403.
Reactanța: X' = 0,08 Ω/km [VERIFICAT: Schneider EIG cap. G — raport #13]. R' și X' se împart la n.

```
trifazat:   ΔU% = 100 · √3 · Ib · (L/1000) · (R'·cosφ + X'·sinφ) / 400
monofazat:  ΔU% = 100 ·  2 · Ib · (L/1000) · (R'·cosφ + X'·sinφ) / 230
cumulat:    ΔU_cum = ΔU_origine + ΔU_ramură
```
Pentru invertor/PCS, ΔU_origine = 0 la bara TGD (creștere de tensiune invertor → PCC).

**Limite (I7-2011 art. 5.2.5 / SR HD 60364-5-52 anexa G), măsurate de la punctul de delimitare sau de la bara JT a PT propriu:**

| Receptor | Rețea publică JT | PT propriu | Nivel la depășire |
|---|---|---|---|
| iluminat | 3 % | 6 % | V20 BLOCANT |
| forță, prize, motor (regim permanent) | 5 % | 8 % | V20 BLOCANT |
| bara unui tablou secundar (receptori necunoscuți) | 3 % | 6 % | V21 AVERTISMENT (DECIZIE: rezervă 2 % pentru circuitele finale) |
| motor la pornire (Ip = 6·Ib, cosφ 0,35, dacă e declarat) | 12 % | 12 % | V22 AVERTISMENT |
| CEF: invertor → PCC | 1 % | 1 % | V21 AVERTISMENT (DECIZIE, recomandare) |
| CEF/prosumator: cablul invertorului (v1.2) | 3 % | 3 % | mărire automată până la 3 %; dacă nici la 4×240 mm² (sau la S impusă) nu se încadrează → **V20 BLOCANT** (invertorul declanșează la supratensiune) |
| bara unui tablou / capătul coloanei C2 (v1.2) | peste 5 % | peste 8 % | mărirea automată se face întâi la 3 % / 6 %; dacă la secțiunea și paralelul maxim (sau la S impusă) ΔU_cum rămâne peste limita I7 de forță → **V20 BLOCANT** „niciun receptor din aval nu se mai poate încadra” |

**Mărirea automată** se face dacă ΔU_cum > limită, S nu e impusă (invertor/PCS: doar peste 3 %, v1.2):
```
cât timp ΔU_cum > limită:
    dacă există S mai mare în listă: S = următoarea
    altfel, dacă n < 4: n = n+1, S = cea mai mică secțiune care satisface Iz_min la n
    altfel: STOP → V20 / V21
```
ΔU se calculează **cu Ib, nu cu Ip** (P1-5: cumulat, nu pe ramură izolată).

### B.13 Curentul de scurtcircuit maxim Ik3max la bara fiecărui tablou
Toate impedanțele sunt raportate la 0,4 kV, în Ω.

**Sursa „rețea publică OD”:**
```
Z_Q = c_max·Un / (√3·Ik3_OD)      # Ik3_OD din ATR/aviz OD; implicit 25 kA
X_Q = Z_Q/√(1+0,1²),  R_Q = 0,1·X_Q
```
Utilizatorul introduce `Ik3_OD_kA` (câmp „Ik3max la punctul de delimitare, din ATR”). Câtă vreme valoarea e implicită, `ik3_implicit = true`.

**Sursa „trafo propriu”** (SR EN 60909-0):
```
Z_Q = c_max·Un²/S"kQ ;  X_Q = Z_Q/√1,01 ;  R_Q = 0,1·X_Q          # S"kQ implicit 500 MVA
Z_T = (uk/100)·Un²/Sn ;  R_T = Pk·Un²/Sn² ;  X_T = √(Z_T² − R_T²)  # Sn în VA, Pk în W
x_T = X_T/(Un²/Sn) ;  K_T = 0,95·c_max/(1 + 0,6·x_T)
Z_k(bara JT) = (R_Q + K_T·R_T) + j(X_Q + K_T·X_T)
```
Exemplu (P03, 630 kVA): Z_T = 1,854 + j9,988 mΩ, K_T = 1,0209 → Ik3max = 23,69 kA.

**Sursa „grup electrogen”:** `Ik3" = c_max·In_G/x"d`, cu x"d = 0,12 dacă lipsește din fișă.

**De-a lungul cablurilor** (R la 20 °C, pentru maxim):
```
Z_capăt = Z_origine + (R20·L/n , X'·L/n)          # L în km
Ik3max = c_max·Un / (√3·|Z|)       c_max = 1,10
```

### B.14 Curentul de scurtcircuit minim Ik1min la capăt de linie (bucla fază–PE)
```
Z_bucla,origine:  OD → Zb (din ATR; implicit 0,18 + j0,09 Ω, z_implicit = true)
                  trafo Dyn → Z_T + (2/3)·Z_Q     # fără K_T
                  GE → vezi C.6
Z_bucla,capăt = Z_bucla,origine + ( (R20_fază·f + R20_PE·f_PE)·L/n , 2·X'·L/n )
Ik1min = c_min·U0 / |Z_bucla,capăt|                c_min = 0,95
```
- f_faza = 1,20 (PVC) / 1,28 (XLPE): rezistența conductoarelor active la temperatura maximă de regim; f_PE = 1,38 (PVC) / 1,60 (XLPE): conductorul PE / PEN la temperatura medie dintre regim și finalul scurtcircuitului (PE separat: 1,38) [VERIFICAT: CLC/TR 50480:2011 — raport #12; înainte 1,38 / 1,60 și pe fază].
- f_PE = f dacă PE e în cablu; 1,38 dacă PE e conductor FY separat.
- **Coerență (v1.2, M9):** Ik1min ≤ Ik3max la capătul oricărei ramuri. Zb implicit se ridică la ≥ 2·Z_Q (B.0). Dacă datele introduse de utilizator dau totuși Ik1min > Ik3max → **V15 BLOCANT** „date de scurtcircuit inconsistente”.

### B.15 Deconectarea automată (SR HD 60364-4-41)
**Timpul cerut (TN, U0 = 230 V):**
- circuit final cu Ip ≤ 63 A (receptor ≠ tablou): **0,4 s** (DECIZIE: se aplică tuturor circuitelor finale ≤ 63 A, nu doar celor cu prize);
- circuit de distribuție sau final > 63 A: **5 s**.

**TT** (`schema_pamant = "TT"`, se propagă la toate ramurile din aval): circuit final ≤ 63 A **0,2 s**, distribuție și final > 63 A **1 s** (SR HD 60364-4-41 tab. 41.1; `norme.T_DECONECTARE_S[("TT", …)]`). DDR obligatoriu, RA·IΔn ≤ 50 V (V34). Câmpul `t_deconectare_s` raportează timpul TT (ex. B20: C2 = 1 s). Ia se calculează și se raportează ca în TN (informativ), dar condiția de deconectare în TT e îndeplinită prin DDR (V31 INFO).

**Curentul de deconectare Ia:**

| Aparat | Ia |
|---|---|
| MCB B / C / D | 5·In / 10·In / 20·In |
| MCCB TM | 1,2·Im = 12·In (toleranța de ±20 %, SR EN 60947-2 art. 8.3.3.1.2) |
| MCCB EL, ACB | 1,2·Isd (Isd ales conform B.5 pct. 4) |
| gG | tabel `GG_IA_0_4S_A` (0,4 s) sau `GG_IA_5S_A` (5 s) |

Valori gG [A]. **Regula de sursă unică (arbitraj):** Ia(5 s) = max(DIN VDE 0100-600 Bbl. NB.1 ; poarta Imax(5 s) din SR EN 60269-1). La 50 A și 80 A valorile VDE (260/440 A) depășesc porțile (250/425 A) și se păstrează, fiind conservatoare (cer un Ik1 mai mare). Peste 80 A tabelul este chiar poarta. `norme._autoverificare()` impune Ia(5 s) ≥ poartă. Ia(0,4 s) provine numai din VDE NB.1:

| In | 16 | 20 | 25 | 32 | 40 | 50 | 63 | 80 | 100 | 125 | 160 | 200 | 250 | 315 | 400 | 500 | 630 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Ia(0,4 s) | 107 | 145 | 180 | 265 | 310 | 460 | 550 | 960 | — | — | — | — | — | — | — | — | — |
| Ia(5 s) | 65 | 85 | 110 | 150 | 190 | 260 | 320 | 440 | 580* | 715* | 950* | 1250* | 1650 | 2200* | 2840* | 3800* | 5100* |
(* [NEVERIFICAT] individual)

**Algoritmul:**
1. Dacă Ik1min ≥ Ia → V30 INFO.
2. Altfel, dacă `z_implicit = false` și S nu e impusă și ramura nu are DDR: S crește pas cu pas (același n, PE recalculat după B.11) până la Ik1min ≥ Ia. Dacă se reușește → V30 INFO + pasul de calcul „secțiune mărită pentru deconectare”.
3. Dacă tot nu se îndeplinește condiția:
   - DDR propriu pe ramură (`ddr_ramura`): V31 INFO (Zs·IΔn ≤ U0);
   - DDR în amonte (`ddr_amonte`, ex. RCCB 300 mA din BMPT): **V31 AVERTISMENT** („un defect pe plecare deconectează toată instalația”);
   - Zb OD implicit: **V32 AVERTISMENT** („cereți OD impedanța buclei”);
   - altfel **V30 BLOCANT** „deconectare automată neîndeplinită”.
4. Dacă Ia nu există pentru calibru și timp (ex. gG 100 A la 0,4 s): V30 AVERTISMENT.

### B.16 Capacitatea de rupere: Icu ≥ Ik3max la bara aparatului
- Icu se alege automat conform B.5 pct. 6.
- Icu impus < Ik3max:
  - dacă în **același tablou**, în amonte, există o siguranță gG (protecție de rezervă, SR EN 60947-2 anexa A) → V33 AVERTISMENT „confirmați combinația în tabelele de coordonare ale producătorului”;
  - excepție: Q din BMPT/BMPM (Icn ≥ 6 kA cerut de ST 4-JT/ST 3-JT, cu SF 50 kA în amonte) → V33 INFO;
  - altfel → **V33 BLOCANT**.

### B.17 Stabilitatea termică: k²S² ≥ I²t
**Timpul t la Ik1min:**
- MCB, MCCB/ACB în zona instantanee: 0,1 s;
- gG: 0,1 s dacă Ik1min ≥ Imax(0,1 s) din porți; 0,4 s dacă Ik1min ≥ Ia(0,4 s); altfel 5 s;
- deconectare prin DDR: 0,3 s;
- deconectare neîndeplinită: 5 s.

**Faza:**
- MCB și gG (aparate limitatoare) care respectă B.6 și au capacitatea de rupere ≥ Ik3max: protecția la scurtcircuit a cablului este asigurată (SR HD 60364-4-43 art. 435.1) → V35 INFO.
- MCCB/ACB: `n·S ≥ Ik3max·√t/k`, cu t = 0,02 s (o perioadă; +0,1 s pentru electronic cu tsd). Dacă nu se respectă:
  - S impusă → V35 BLOCANT;
  - Ik3 implicit → V35 AVERTISMENT („introduceți Ik3 real sau I²t din fișa producătorului”);
  - altfel S crește la secțiunea standard necesară → V35 INFO.

**PE:** conform B.11.

### B.18 Selectivitatea amonte–aval (regulă simplificată)
Pentru fiecare pereche (aparat amonte, aparat aval), cu Ik = Ik3max la bara pe care e montat aparatul aval:
1. Ip_amonte < Ip_aval → **V40 BLOCANT** „amonte < aval”.
2. Ip_amonte = Ip_aval → V41 AVERTISMENT „fără selectivitate”. Excepție: SF/Q în BMPT/BMPM → V41 INFO (coordonare fixată prin ST 4-JT; SF aparține OD).
3. gG–gG: raportul In_amonte/In_aval ≥ 1,6 (SR EN 60269-2) → V42 INFO „selectivitate totală”; altfel V41 AVERTISMENT.
4. Celelalte combinații:
   a. raportul Ip_amonte/Ip_aval < 1,6 → V41 AVERTISMENT (zona de suprasarcină);
   b. limita de selectivitate Is = pragul inferior instantaneu al aparatului amonte: MCB B 3·In, C 5·In, D 10·In; MCCB TM 0,8·10·In; electronic/ACB cu tsd 0,8·Ii = 0,8·12·In; gG Imin(0,1 s) din porți;
   c. Ik ≤ Is → V42 INFO „selectivitate totală”; altfel **V42 AVERTISMENT** „selectivitate parțială până la Is kA, confirmați cu tabelele producătorului”.

Tablourile de selectivitate ale producătorilor **nu** se includ în aplicație. Avertismentul cere confirmarea lor.

### B.18.1 Selectivitatea DDR în serie (v1.3, `ddr.py`)
Pentru **orice** DDR aflat în aval de alt DDR (RCCB BMPT → DDR pe plecare; Q1 cu DDR → plecări; DDR general → circuite finale; TT; CEF/prosumator) se verifică (SR HD 60364-5-53 art. 535.3; SR EN 61008-1/61009-1 pentru tipul S):

- **IΔn amonte ≥ 3·IΔn aval și t amonte − t aval ≥ 0,15 s** → **V43 INFO**. Temporizări (v1.3 R5, M5-4): instantaneu (G) = 0 s; tip S = 0,15 s echivalent (DECIZIE, `norme.DDR_T_ECHIVALENT_S`; SR EN 61008/61009: nefuncționare ≥ 0,13 s, deconectare ≤ 0,5 s); releu / bloc diferențial reglabil = Δt reglat (`dt_s`). Deci S → instantaneu e selectiv, **S → S nu** (aceeași fereastră de timp), reglabil 0,3 s → S da;
- același IΔn și aceeași temporizare → **V43 AVERTISMENT** „egal”, cu remedierea concretă: „DDR amonte {prima treaptă ≥ 3·IΔn} mA temporizat sau DDR aval {cea mai mare treaptă ≤ IΔn/3} mA”;
- TT, iar IΔn amonte necesar (≥ 3·IΔn aval) ar depăși RA·IΔn ≤ 50 V → **V43 AVERTISMENT** „TT”, cu explicația (RA limitează IΔn, seria 300/100/30 mA nu mai are treaptă) și remedierea „RA ≤ 50/IΔn_necesar Ω”;
- altfel → **V43 AVERTISMENT** cu motivul (amonte instantaneu; aceeași temporizare S → S; Δt < 0,15 s; IΔn amonte < 3·IΔn aval) și remedierea (aval instantaneu / releu reglabil în amonte cu Δt ≥ t_aval + 0,15 s / IΔn).

Obiectul verificării: `{obiect aval} vs {denumire amonte}` (ex. „P1·Prize vs RCCB BMPT”, „P2·Hala vs DDR Q1/C1”, „QG vs RCCB BMPT”, „INV vs RCBO BMPM”). Lanțul se urmărește prin contextul ramurii (`ddr_sus` = cel mai apropiat DDR din amonte). DDR-ul din amonte al schemei: `IdN_amonte_mA` declarat (tip S după `DDR_amonte_selectiv`, implicit S) sau RCCB BMPT 300 mA S (§C.1, M11) / RCBO BMPM 300 mA instantaneu (`norme.BMPM_RCBO_SELECTIV` [VERIFICAT: ST 3-JT §4.2.4 m]). **La locuință (Î1, proiectant 28.10.2026)** și RCCB-ul din BMPT e presupus instantaneu, tip AC (ST 4-JT §4.2.6 i): V43 apare la casele cu DDR 30 mA, cu remedierea „declarați blocul real” (`alimentare.DDR_bransament_tip` / `DDR_bransament_selectiv`).

**DDR-urile alese de motor sunt selective (DECIZIE):** DDR 30 mA instantaneu pe prize sub RCCB BMPT 300 S; în TT alegerea `ddr.alege_tt` (§C.2 pct. 13, v1.3 R5). Rămân AVERTISMENT doar perechile impuse de date: RCBO BMPM instantaneu (prosumator / tablou monofazat), DDR declarat în amonte cu IΔn prea mic, RA prea mare, DDR impus de utilizator.

### B.19 Transformatoare de curent
- **Primar:** cea mai mică valoare din `TC_PRIMAR_A` ≥ max(Ib ; In_Q/1,2), unde 1,2 = domeniul extins 120 % (DECIZIE). Pentru BMPTi-250: doar 125, 150, 200, 250 A (ST 4-JT). Ib > primarul ales → V55 BLOCANT.
- **Clasa:** 0,5 (ST 4-JT pentru BMPTi) sau 0,5S (măsură în TGD/PT, CEF). Secundar 5 A. Sn = 5 VA.
- **Sarcina secundară:**
  `S_sec = 5²·(2·L_sec·0,021/s_sec) + 1,0 + 0,1` [VA] (circuit dus–întors, Cu la ~75 °C, consum contor 1,0 VA [practică, raport #71 — majorant IEC 62053-22], contacte 0,1 VA). L_sec implicit 3 m, s_sec = 1,5 mm² (CYEAbY-F 2×1,5, ST 4-JT). S_sec > Sn → V55 AVERTISMENT (remediere: 2,5 mm² sau TC 10 VA).
- Desen: circuitul de curent TC → K → contor. Circuitul de tensiune se ia **din bare, în amonte de TC**, prin F 3 × 2 A gG, ca derivație separată. Altfel → V57 BLOCANT (P0-8).

### B.20 Contor direct sau semidirect
- Ib ≤ 100 A → direct (BMPTd). Contorul aparține OD (BMPT / BMPM se livrează fără contor — ST 4-JT §4.2.3, ST 3-JT §4.2.3); pe planșă scrie „contor electronic …, conexiune directă / prin TC, furnizat și montat de OD”, **fără curent nominal** [DECIZIE proiectant 28.10.2026, Î15; VERIFICAT: raport #64, #66].
- 100 A < Ib ≤ 250 A → semidirect prin TC (BMPTi-250).
- Contor direct pe un circuit cu Ib > 100 A → V56 BLOCANT.

### B.21 Ordinea pașilor (pseudocod complet pentru o ramură)
```
1  validări B.2                               → V07/V08/V09/V10 BLOCANT ⇒ STOP ramura
2  Ib, Ip,min                                 (B.2)
3  tip protecție                              (B.3)
4  In, Ir, reglaj                             (B.5)            → V05/V06/V04 ⇒ STOP
5  I2, Iz_min                                 (B.6, B.10 pct. 5–6)
6  dacă S impusă: verifică V13, V02, V03; altfel caută (n, S) (B.7, B.8) → fallback V45 / V01 ⇒ STOP
7  regula Al→Cu                               (B.8)            → V48 INFO
8  ΔU și mărirea pentru ΔU                    (B.12)           → V20/V21
9  compunere N, PE                            (B.10, B.11)     → V25/V26 dacă impuse
10 Ik3max la capăt, Ik1min la capăt           (B.13, B.14)
11 Isd pentru electronic, Ia                  (B.5, B.15)
12 deconectare (+ mărire dacă e permisă)      (B.15)           → V30/V31/V32
13 Icu                                        (B.16)           → V33
14 stabilitate termică fază și PE             (B.17, B.11)     → V35/V36
15 selectivitate față de aparatul amonte      (B.18)           → V40/V41/V42
16 contextul pentru bara din aval: Zq = Z_capăt, Zb = Z_bucla,capăt, Ik3 = Ik3max,capăt,
   dU = ΔU_cum, plus flagurile z_implicit, ik3_implicit, ddr_amonte moștenite
```
Dacă un pas ulterior mărește S (pașii 12 și 14), se recalculează ΔU, Iz', N, PE, Ik3 și Ik1 pentru S nou.

### B.22 Rotunjiri
- Calculele se fac în virgulă mobilă, fără rotunjiri intermediare.
- Comparațiile se fac cu toleranță 1e-9.
- Afișare (E.1): Ib și Iz' cu 1 zecimală, ΔU cu 2 zecimale, Ik3 cu 2 zecimale în kA, Ik1 întreg în A.

---

## C. Reguli specifice pe tip de schemă

### C.1 Branșament DEER

**Alegerea blocului** (ST 4-JT Ed. U1 Rev. 3/2024 și ST 3-JT Ed. U1 Rev. 3/2026, verificate):

| Ib (din Pa sau din A) | Bloc | Q (seria ST) | SF | Măsură | RCD |
|---|---|---|---|---|---|
| mono, Ib ≤ 40 A | **BMPM-In** | RCBO 1P+N curba C, In ∈ {16, 20, 25, 32, 40}, Icn ≥ 6 kA | separator monopolar, fuzibil 40 A gG, gabarit 00, 50 kA | direct | în RCBO: 300 mA, tip AC, instantaneu (ST 3-JT §4.2.4 l–m; Î1) |
| mono, Ib > 40 A | — **V53 BLOCANT**, propune trifazat | | | | |
| tri, Ib ≤ 16 A | **BMPTd-16** | MCB C, In = 16 | soclu 160 A, fuzibil 40 A (00) | direct | RCCB 4P 300 mA AC |
| 16 < Ib ≤ 40 A | **BMPTd-40** | MCB C ∈ {20, 25, 32, 40} | soclu 160 A, fuzibil 40 A (00) | direct | idem |
| 40 < Ib ≤ 100 A | **BMPTd-100** | MCB C ∈ {50, 63, 80, 100} | soclu 160 A, fuzibil 100 A (00) | direct | idem |
| 100 < Ib ≤ 250 A | **BMPTi-250** | MCCB ∈ {125, 160, 200, 250}, Ir după Ib (TM) | soclu 250 A, fuzibil 250 A (NH1) | semidirectă, TC 125…250/5 A, cl. 0,5, 5 VA | idem |
| Ib > 250 A | — **V50 BLOCANT**: „nu există BMPT peste 250 A; racord din PT (măsură în PT) sau PT propriu”. Se propune schema PT. | | | | |

Reguli suplimentare:
- **Nu există BMPTd-25, BMPTd-63, BMPTi-500.** Un tip impus inexistent → V50 BLOCANT (P0-6).
- In_Q ≤ In_SF. Altfel V52 BLOCANT.
- RCCB In = cea mai mică valoare din {16, 25, 40, 63, 80, 100, 125, 160, 200, 250} ≥ In_Q.
- DPST: Uf = 270 ± 10 V (f-n), Ul = 467 ± 10 V (f-f), t = 0,13…0,2 s, comandă BD pe Q.
- Măsură semidirectă cerută la Ib ≤ 100 A → se generează BMPTd și se emite **V51 AVERTISMENT** (P0-6, testul 12).
- TC după B.19, limitat la 125…250 A.
- **C1 (racord OD) nu se dimensionează.** Pe desen scrie „racord OD — conform ATR”.
- **C2 (coloana BMPT → tabloul consumatorului):** ramură cu Q ca protecție (Ip = In MCB sau Ir MCCB), receptor „tablou” (bara TE ≤ 3 %, BLOCANT peste 5 %, v1.2), DDR propriu = RCCB-ul BMPT (deconectarea → V31 INFO), protecție de rezervă la Icu = SF (V33 INFO). Icu Q: MCB 6 kA; **MCCB (BMPTi) 25 kA** = prima valoare din seria MCCB ≥ 6 kA (v1.2, M12: aceeași valoare în calcul, memoriu, listă și desen; `Q.Icu_kA`). Cablul C2 respectă dicționarul `cablu` (B.1.1, M1).
- **v1.2:** `bmpt_fortat` cu Imax < Ib → V50 BLOCANT; `Q_In_A` < Ib → V04, inexistent în seriile ST 4-JT → V05. Mesajul V51 numește blocul efectiv ales. RCCB-ul BMPT: tip AC (ST 4-JT §4.2.6 i; Î1 — înlocuiește „tip A” r8), `selectiv = true` (S) la tablouri (M11), **instantaneu la locuință** (Î1); la In_Q > 125 A → bloc diferențial asociat MCCB Q (B.4).
- Secțiunea C2 > 150 mm² la BMPTi-250 → V54 AVERTISMENT (bornele de intrare sunt pentru 150 mm²). Remediere: cabluri în paralel de secțiune mai mică.
- Conductoare interne minime: 6 / 10 / 35 / 150 mm² (v1…v4); BMPM 6 mm² (≤ 32 A) / 10 mm² (40 A).
- TT: RA·0,3 A ≤ 50 V, altfel V34 BLOCANT (RA implicit 4 Ω, valoarea cerută de OD pentru PPL).

### C.2 Tablou general cu bilanț de puteri
1. Pentru fiecare plecare: Pi = P_kW, sau (dacă e dată în A) Pi = √3·400·In·cosφ/1000. Pentru o plecare cu sub-plecări, Pi = ks(n_copii)·Σ Pi_copii (recursiv).
2. ks = valoarea declarată sau ks_implicit(n_plecari). Pc = ks·Σ Pi.
3. Puterea de calcul a tabloului:
   - utilizatorul a dat P (ex. „TG 200 kW” = Pa din ATR) → **P declarată are prioritate**; dacă P < Pc → V14 AVERTISMENT (P0-5);
   - altfel, P = Pc. **Nu se ia niciodată prima valoare kW din text** (P0-5).
4. Se calculează **întâi** protecțiile plecărilor (doar Ip; nu depind de bara TG).
5. Q1: Ip,min = max(Ib_tablou ; max(Ip_plecări) + 0,01 A), deci amontele e strict mai mare decât cel mai mare aval. Un Q1 impus mai mic decât un aval → V40 BLOCANT.
6. Alimentarea (C1, coloana) e protejată de Q1; sursa e rețeaua publică prin BMPT, cu RCCB 300 mA în amonte (ddr_amonte = true), dacă nu se spune altfel.
7. Bara TG: Ik3, Zb și ΔU de la capătul C1.
8. Plecările se dimensionează cu contextul barei, plus selectivitatea față de Q1 (B.18).
9. Plecările cu sub-plecări (tablouri secundare, **cascadă**) au receptor „tablou”. Sub-plecările sunt circuite finale (rol „final”, receptor „forță” dacă numele nu indică iluminat/prize/motor), Cu PVC metoda C, L = 25 m. Recursiv, fără limită de adâncime (planșa limitează la 3 niveluri).
10. **Circuite de prize** (v1.2: orice plecare sau circuit final cu receptor „prize” — din `receptor` sau din numele care conține „priz” — și In ≤ 32 A, SR HD 60364-4-41 art. 411.3.3): DDR 30 mA, tip A (RCBO sau RCCB pe grup), adăugat automat cu **V29 INFO**. Ramura primește `ddr_ramura` (deconectare → V31 INFO dacă Ia nu e atins), iar în rezultat plecarea primește `"DDR": {"IdN_mA": 30, "tip": "A", "In_A": ≥ In din seria RCCB, "poli": "2P" | "4P"}`. DDR refuzat explicit (`"DDR": false`) → **V29 BLOCANT**.
13. **R3 (N3-C2, N3-M2) — TT în toate schemele:** RA nedeclarat → 4 Ω presupus + V34 AVERTISMENT. Segmentul dintre originea alimentării și primul DDR al schemei (C1 → Q1 la tablou, QG → PCC la CEF) e protejat de DDR-ul din amonte: `IdN_amonte_mA` declarat sau RCCB 300 mA din BMPT (§C.1); RA·IΔn > 50 V → **V34 BLOCANT** (obiect „C1 (amonte)”, remediere „DDR 100/30 mA în amonte”); din PT propriu fără valoare declarată → V34 (lipsă DDR). **v1.3 R5 (M5-4), `ddr.alege_tt`:** (1) dacă DDR-ul din amonte (RCCB BMPT 300 mA S sau `IdN_amonte_mA` declarat, tip după `DDR_amonte_selectiv`) e temporizat și RA·IΔn_amonte ≤ 50 V, **intrarea (Q1 / QG) nu primește DDR propriu** (protejată de amonte), iar circuitele (plecări, circuite finale, invertoare/PCS) primesc DDR **instantaneu** y = cea mai mare treaptă 300/100/30 mA cu RA·y ≤ 50 V și 3·y ≤ IΔn amonte — prizele ≤ 32 A 30 mA (ex. RA ≤ 166 Ω: 300 S → 100 / 30 instantaneu); (2) altfel (amonte instantaneu sau fără treaptă), intrarea primește un **bloc diferențial reglabil** x ∈ {300, 100} mA (x ≤ limita RA, x ≤ IΔn amonte) cu **Δt = 0,15 s** explicit în rezultat (`DDR.dt_s`, `reglabil`, `aparat = bloc_diferential`), iar circuitele cea mai mare treaptă ≤ x/3, instantaneu; (3) RA permite doar 30 mA → intrarea fără DDR, circuite 30 mA (V43 „TT” dacă amontele nu e selectiv). Alimentările tablourilor secundare (plecări cu circuite în aval) nu primesc DDR propriu în TT (un al doilea DDR temporizat în serie nu ar fi selectiv); circuitele lor primesc aceeași treaptă instantanee. Nota 3 (TT, tablou și CEF) enumeră DDR-urile reale: amonte, intrarea (fără DDR / bloc reglabil cu Δt) și IΔn-urile distincte ale circuitelor, plus RA·IΔn_max; nu mai scrie „IΔn … pe fiecare circuit”. DDR-urile din aval ≤ IΔn/3 (SR HD 60364-5-53 art. 535.3). Perechile neselective rămase → V43 (§B.18.1). Prosumator TT: DDR 30 mA tip A pe invertor (`INV.DDR`, prezent și în TN). CEF TT: `QG.DDR` (S) + `DDR` pe fiecare invertor/PCS. PT și GE în TT → V28. Rezultatul are `IdN_amonte_mA`, `DDR_TT_IdN_mA` (maximul folosit, în nota 3).
12. **R2 (N-C2) — tablou TT:** RA (implicit 4 Ω, declarat) → IΔn = cel mai mare din {300, 100, 30} mA cu RA·IΔn ≤ 50 V (altfel V34 BLOCANT); fiecare circuit (Q1 și toate plecările/circuitele, prizele ≤ 32 A cu 30 mA) primește `DDR = {IdN_mA, tip: "A", In_A, poli, aparat: RCCB|bloc_diferential, selectiv}`; deconectarea se asigură prin DDR (Ia informativ). DDR refuzat → V34 BLOCANT. Nota 3 conține IΔn și RA·IΔn reale; rezultatul are `DDR_TT_IdN_mA`.
11. **v1.2:** tablou fără plecări → V07 BLOCANT. h3 > 33 % → neutrul se dimensionează după curentul din N (B.10) și se emite **V24 AVERTISMENT** „protecția neutrului” (SR HD 60364-4-43 art. 431.2.3; câmpul `protectie_neutru = true`).

**Receptorul după nume** (fără diacritice, litere mici):
- „ilumin” → iluminat;
- „priz” → prize;
- „motor”, „pomp”, „compresor”, „ventila”, „moar”, „concasor”, „malaxor” → motor;
- altfel → tablou (nivel 0) sau forță (nivel ≥ 1).

### C.3 CEF (c.a. + c.c.)
1. **Invertoare și PCS:** câte o ramură fiecare (rol invertor), cu Ip,min după B.2. Curentul din fișa invertorului (Iac,max) are prioritate față de 1,1·Pn.
2. **Sume:** ΣIac = Σ Iac,max(invertoare) + Σ Iac,max(PCS). S_total = √3·400·ΣIac/1000 [kVA]. P_total = ΣPn [kW].
3. **QG:** Ip,min = max(ΣIac ; max Ip_invertor). QG impus cu Ip < ΣIac → **V65 BLOCANT** (P0-7: BESS intră în sumă).
4. **Pragurile de racord** (DECIZIE de proiectare, nu normă; ATR-ul prevalează):

   | S_total | Racord | Verificare |
   |---|---|---|
   | ≤ 173 kVA (250 A) | JT, BMPT | — |
   | 173 < S ≤ 400 kVA | JT, direct din PT OD, conform ATR | V66 AVERTISMENT |
   | > 400 kVA, fără PT propriu și fără „racord JT conform ATR” | — | **V66 BLOCANT**; interpretorul adaugă PT propriu Sn = cea mai mică ≥ S_total și întreabă |
   | > 2500 kVA | în afara domeniului | interpretorul refuză (F.7) |

5. **Cu PT propriu:** Sn < S_total → **V67 BLOCANT**. QG = Q JT trafo; Ir_QG > In_T → V60 AVERTISMENT (trafo neprotejat la suprasarcină).
6. **Categoria RfG** (după P_total; BESS inclus): < 1 MW → A (V70 INFO); ≥ 1 MW → B (V70 AVERTISMENT „cerințe tip B, Ord. ANRE 208/2018, PI și reglaje din ATR”). Pragurile A/B 1 MW, B/C 5 MW și C/D 20 MW [VERIFICAT: Ord. ANRE 79/2016 anexa — clasificarea; Ord. 208/2018 = norma de cerințe — raport #83–#85].
7. **Protecția de interfață:** prosumator → Ord. ANRE 228/2018; CEF care nu e prosumator → Ord. ANRE 208/2018 + ATR. Notele cu „Ord. 228” la CEF ne-prosumator → V75 AVERTISMENT (P2-10).
8. **TC măsură:** B.19, cu Ib = ΣIac, cl. 0,5S.
9. **C.c. (pe fiecare intrare MPPT):**
   - `Voc(Tmin) = N_module·Voc_STC·[1 + (β_Voc/100)·(Tmin − 25)]`, cu Tmin = −25 °C (DECIZIE) și β din fișa modulului (implicit −0,27 %/K [VERIFICAT: majorant module actuale, raport #77]). Voc(Tmin) > Umax invertor (implicit **1000 V** — minorantul Fronius / SMA când fișa lipsește [VERIFICAT: raport #78]; Huawei / Sungrow 1100 V se declară) sau > tensiunea maximă de sistem a modulului → **V68 BLOCANT**.
   - Siguranțe gPV pe fiecare string, obligatorii de la 3 stringuri în paralel pe aceeași intrare: 1,5·Isc_STC ≤ In ≤ min(2,4·Isc_STC ; I_MOD_REVERSE). Nu există calibru în interval → V69 BLOCANT.
   - SPD c.c. tip 2: Ucpv = cea mai mică din {600, 1000, 1100, 1200, 1500} V ≥ Voc(Tmin); Ucpv mai mic → V74 BLOCANT.
   - Separator c.c. sub sarcină pe fiecare intrare (sau integrat în invertor, declarat). Lipsa protecțiilor c.c. pe model → V88 BLOCANT.
   - Cablu string: H1Z2Z2-K, Iz ≥ 1,25·Isc_STC fără siguranțe, Iz ≥ In_gPV cu siguranțe.
10. **Desen:** câmpurile PV, invertoarele și BESS se desenează **în afara** TGD-CF (V82, P1-10).
11. **v1.2 (verificarea independentă):**
   - **Iac,max din fișă** < Pn·1000/(√3·400) (tri) sau < Pn·1000/230 (mono) → **V64 BLOCANT** „Iac,max neplauzibil” (pe fiecare invertor/PCS).
   - **S_total = max(U·ΣIac/1000 ; ΣPn)** (U = √3·400 sau 230); se folosește la pragurile de racord (V66) și la verificarea trafo (V67). Rezultatul raportează și `S_din_Iac_kVA`.
   - **CEF monofazat** (`retea = "mono"`): Iac = 1,1·Pn/230, Ip,min = 1,25·Pn/230, protecții 1P+N, cabluri cu 3 conductoare, ΔU pe 230 V; ΣIac > 40 A → V53 BLOCANT (BMPM); ΣPn > 3,68 kW → V71 AVERTISMENT; măsură directă monofazată (fără TC); cu PT propriu → V12 BLOCANT. QG are `poli = "2P"`.
   - **Racord JT prin BMPT** (S ≤ 173 kVA, fără PT): Ip QG ≤ 250 A (In Q BMPTi-250; la mono 40 A, BMPM), altfel **V66 BLOCANT** (QG nu se coordonează cu Q din bloc). Câmpul `racord` descrie soluția („JT prin BMPT”, „JT direct din PT OD conform ATR”, „MT prin PT propriu”, „JT monofazat prin BMPM”).
   - **β_Voc ≥ 0** (sau < −1 %/K) → **V68 BLOCANT** „β neplauzibil”; nu se ia în modul. kWp ≤ 0 cu invertoare, n_module < 1 → V07.
   - QG electronic: `Isd_A`, `Isd_multiplu`, `tsd_s`, `Ii_A` în rezultat (Isd după Ik1min la bara QG).
12. **v1.3 (UX r3, P0-2) — punctul de racord, C0 și cablurile invertoarelor:**
   - `racord` ∈ {„tg_existent” (sinonim „tg”), „bmpt”, „pt”} (altfel V12; „pt” fără `pt_Sn_kVA` → V07). Punctul de racord (BMPT existent / PT) se verifică după puterea totală, ca în pct. 4–5 (V66/V67, M4).
   - **TG existent:** QG se leagă pe o plecare a TG-ului existent al consumatorului. Bara TG: `Ik3_TG_kA` (+ opțional `Zb_TG_ohm`; Zb implicit = 2·Z_Q, declarat) sau, lipsind, bara TG = punctul de racord (majorant pentru Icu, `ik3_implicit`, declarat — DECIZIE). Protecția existentă `racord_In_Q_A` (+ `racord_Q_tip`, implicit MCB ≤ 63 A / MCCB, `racord_Icu_kA`) → `Q_TG` {tip, In_A, Ir_A, curba, Icu_kA}: calibru în serie (V05), **Ip Q TG ≥ Σ Iac** (altfel **V44 BLOCANT**, declanșează la injecție), Icu ≥ Ik3 TG (V33 BLOCANT; nedeclarat → V33 AVERTISMENT), selectivitatea Q TG (amonte) → QG (aval) după B.18 (obiect „Q TG vs QG”, V40–V42), Ip Q TG ≤ Iz' C0 (altfel **V44 AVERTISMENT**: C0 e protejat la suprasarcină doar de QG) și deconectarea unui defect la capătul C0 prin Q TG în 5 s (V44 AVERTISMENT cu Ik/Zb implicite, altfel BLOCANT). Fără `racord_In_Q_A` → presupunere declarată.
   - **C0 (TGD-CF → punctul de racord)** se dimensionează ÎNTOTDEAUNA când `L_racord_m` e dat (cu sau fără TG existent): ramură B.21 completă, Ib = Σ Iac, protejată de QG (In, Ir, Icu impuse), contextul (Ik3, Zb) = punctul de racord (bara TG / BMPT / PT), cablu `cablu_C0` > `cablu` global > implicit D1 Al; obiect „C0”, rezultat `C0` (+ `descriere`) și `bara_TGD_CF` {Ik3max_kA, dU_pct}. Invertoarele se calculează apoi cu contextul capătului C0, iar ΔU invertor → punctul de racord se cumulează (ΔU_inv + ΔU_C0, limitele 1 % / 3 %). QG: Ip,min din protecțiile invertoarelor calculate întâi (doar Ip).
   - **Cablurile invertoarelor/PCS:** câmpurile cablului se iau, în ordinea priorității, din `invertoare[].cablu`, `cablu_inv` / `cablu_pcs`, `cablu` global (material, izolație, metodă, θ, ρ_sol, grupare); lungimea din `invertoare[].L_m`, `invertoare[].cablu.L`, `L_inv_m` / `L_pcs_m`, altfel 30 m (declarat). Fără material: Al în pământ, Cu în aer.

13. **v1.8 — echipamente din fișe tehnice (modele pe planșă și în listă):**
   - Intrare: `modul` (sau `string.modul`) {producator, model, Pmax_W, Voc_V, Isc_A, Vmpp_V, Impp_A, beta_Voc_pct_K, Umax_sistem_V, I_rev_A}; fiecare grup din `invertoare[]` și `invertor` (prosumator) {producator, model, Pn_kW, Iac_max_A, Umax_dc_V, MPPT_min_V, MPPT_max_V, Idc_max_A, Isc_max_A, nr_MPPT, separator_cc_integrat, hibrid}; `bess` / `baterie` {producator, model, P_kW, kWh, Iac_max_A, U_nom_V, chimie} (opțional `bess.pcs`, `bess.baterie`); `spd_cc` {producator, model, tip (T2 | T1+T2)}; `gpv` {producator, model}.
   - Datele de fișă înlocuiesc presupunerile, cu sursa declarată în pașii de calcul: Voc / Isc / β(Voc) / Umax sistem / siguranța maximă în serie din fișa modulului; Umax c.c. = minimul Umax_dc_V al invertoarelor; Iac,max din fișa invertorului / PCS. Cheile vechi `string.Uoc_V`, `string.beta`, `string.Umax_inv_V` rămân alias (`string.Voc_V`, `string.beta_Voc_pct_K`); explicitul din `string` are prioritate față de fișă. În texte se scrie **Voc**.
   - Stringuri: `string` {n_module, n_stringuri_paralel (pe MPPT), n_MPPT, gpv (siguranțe pe string cerute oricum)}; fiecare grup poate avea `string` / `modul` propriu (calculul c.c. se face pe grup: `cc_grupuri`). gPV: de la 3 stringuri în paralel pe MPPT sau cu `string.gpv`.
   - **V89 AVERTISMENT** (din fișe): Vmpp string la 70 °C < MPPT min; Vmpp STC > MPPT max; n·Isc > Isc max/MPPT; n·Impp > Idc max/MPPT; puterea din stringuri (module × stringuri × MPPT × Pmax) ≠ kWp declarat cu peste 5 %. INFO când stringul e în fereastra MPPT.
   - Desen: FIECARE invertor e o ramură proprie (fără „× n”): câmpul PV (stringuri × MPPT, modelul modulului), conductorul de echipotențializare a ramelor (PE), siguranțele gPV (dacă rezultă), cutia de joncțiune (SB), separatorul de c.c. (sau „integrat în invertor”), SPD c.c., invertorul cu modelul, protecția și DDR-ul de c.a., cablul până la TGD-CF.
11. **v1.9 (R5 fotovoltaic) — reguli comune CEF / prosumator / BESS:**
   - **Rețeaua nu se presupune în tăcere:** la CEF fără `retea` se calculează trifazat, dar se scrie în „Am presupus”; `retea: "mono"` se respectă (230 V, BMPM, V53 / V71 / V12 cu PT); un grup din `invertoare[]` declarat `retea: "tri"` la CEF monofazat → **V91 AVERTISMENT** (variantă „monofazat”). Schema de legare la pământ (`schema_pamant` TN-C-S / TN-S / TT + `RA_ohm`) intră în calcul și în nota 3.
   - **Racord** (`racord`: `"tg_existent"` | `"bmpt"` | `"pt"`): `pt_Sn_kVA` cu `racord = "tg_existent"` sau cu `pt_existent: true` = **PT existent** — sursa pentru Ik (context PT), fără transformator desenat; planșa arată „TG EXISTENT … alimentat din PT existent” sau „PT EXISTENT Sn kVA”. Un trafo nou (T1) se desenează numai pentru PT propriu nou (`pt_Sn_kVA` fără TG / fără `pt_existent`). V67 rămâne BLOCANT și la PT existent (injecția depășește trafo-ul). Protecția din TG (`racord_In_Q_A`, `racord_Q_tip`, `racord_Icu_kA`) și `Ik3_TG_kA` / `Zb_TG_ohm` se folosesc pentru C0 și Icu.
   - **DDR pe invertor / PCS — numai unde e cerut** (DECIZIE, `norme.DDR_INVERTOR_PRAG_KW = 30`, `DDR_INVERTOR_IDN_MARE_MA = 100`): (1) declarat pe grup `ddr: {IdN_mA, tip}` (fișa invertorului / ATR, ex. 300 mA tip B) — desenat și verificat; `ddr: false` = exclus (nu în TT); (2) TT: DDR obligatoriu, 30 mA ≤ 30 kW, ≥ 100 mA peste 30 kW (dacă RA·IΔn ≤ 50 V), selectiv cu amontele; (3) TN, prosumator ≤ 30 kW: 30 mA tip A (sau `IdN_min_mA` / `tip_ddr` din fișă); (4) TN, > 30 kW și CEF: **fără DDR** — deconectarea prin întreruptor (V32 / V44). DDR < 100 mA pe un invertor > 30 kW → **V73 AVERTISMENT** (varianta „mare”: curentul capacitiv de scurgere al câmpului PV). V73 generic se emite doar dacă există DDR.
   - **SPD c.a. la invertor / PCS** (SR HD 60364-7-712 art. 712.534, `norme.SPD_CA_INVERTOR_L_M = 10`): cablul invertor → tablou > 10 m sau `spd_ca: true` pe grup → SPD T2 la bornele c.a. ale invertorului (`SPD_ca_invertor` în rezultat, desenat ca derivație sub invertor, F{k}.3); `spd_ca: false` = exclus.
   - **Limitarea injecției** (`limitare_injectie_kW`, 0 = injecție zero): `limitare_injectie` {P_kW, zero, I_inj_A, n_comandate} → **V92** (INFO; AVERTISMENT „fără efect” dacă P ≥ Σ Pn). Desen: TC proprii (TCA) + analizor de rețea (AR) + controller EMS la punctul de racord, și legătura de comandă EMS → fiecare invertor / PCS. La prosumator, V72 compară Q branșament cu min(Σ Iac; I_inj).
   - **BESS cuplat în c.a.** (CEF și prosumator): BAT → separator-siguranță c.c. (SB-B) cu SPD c.c. (FB.2) → PCS → (SPD c.a.) → QB. **BESS de sine stătător**: `tip_schema: "bess"` (alias, normalizat la `cef`) sau `cef` doar cu `bess` (fără invertoare / kWp 0) — acceptat, `bess_singur: true`, titlul „BESS P kW / E kWh”.
   - **Puterea declarată** `Pn_total_kW` ≠ Σ n·Pn invertoare (> 1 %) → **V91 AVERTISMENT**; se calculează cu lista.
   - **gPV declarat** (`string.gpv_In_A` sau `gpv.In_A`): cu Isc cunoscut se verifică în [1,5·Isc; min(2,4·Isc; Irev)] (altfel V69 BLOCANT); fără Isc se ia ca atare (presupus). Stringuri declarate fără Voc modul (n_module + n_stringuri_paralel / n_MPPT / gpv): se desenează, Voc(Tmin) și SPD c.c. rămân neverificate (presupus, Ucpv 1100 V) — nu mai blochează.

**C.3 E2 — limitarea puterii la punctul de racord (PCC), decizia proprietarului 28.10.2026.** Sn trafo (Σ Sn, sau al
secției) < S invertoare + PCS → **V67 BLOCANT** cu propunerea `{"camp": "limitare_PCC_kW", "valoare": P}`, unde
**P = Sn × cosφ_PCC × factor** (`norme.PCC_COSFI` = 0,9 — capabilitatea de putere reactivă la PCC; `norme.PCC_FACTOR` =
0,95 — rezervă pentru pierderile trafo și precizia buclei EMS), rotunjită în jos la 5 kW (1000 kVA → 855 kW). Cu
`limitare_PCC_kW` declarată și S_lim = P_lim / cosφ_PCC ≤ Sn → **V67 AVERTISMENT** explicit (varianta „pcc”: EMS /
controller de putere, TC + analizor la PCC, invertoarele nu pot debita simultan puterea instalată; remediere: confirmare
ATR, fail-safe EMS), notă pe planșă, capitol în memoriu; S_lim > Sn → V67 BLOCANT „pcc_insuf” cu propunerea. Pe secții
(PT nou cu 2 trafo) limita se împarte egal. Limitarea se realizează cu lanțul limitării injecției (`limitare_injectie_kW`
= min(declarată, limitare_PCC_kW) — TC + analizor la PCC → EMS → invertoare / PCS, V92). Rezultat: `limitare_PCC`
{Sn_kVA, S_necesar_kVA, propunere_kW, cosfi, factor, formula, P_kW, S_kVA, aplicata}.

**C.3 E2 — CEF cu putere în kW fără invertoare declarate (D4).** `Pn_total_kW` fără `invertoare` (și fără BESS) →
invertoare de tip implicit: n = ⌈P / 100 kW⌉ egale (trifazate, fără fișă: Iac,max = 1,1·Pn/(√3·U)), declarate în
„presupus” — nu întrebare blocantă (`scheme.invertoare_implicite`). Interpretorul: „CEF 50 kW” → `Pn_total_kW: 50`.

### C.4 Prosumator (mono/tri)
- Prosumator = P invertor ≤ 400 kW pe loc de consum (Ord. ANRE 95/2022, se verifică la data proiectului). Peste → V70 BLOCANT „schema CEF”.
- Mono: Iac,max > 40 A → **V53 BLOCANT** (BMPM; invertor mono maxim ≈ 8,36 kW cu factorul 1,1). Generare monofazată cu Smax (= 230·Iac,max) > 16 A ≈ **3,68 kVA** → V71 AVERTISMENT (comparația pe kVA; Ord. ANRE 228/2018 art. 12(3), excepțiile art. 12(4)–(5) în ATR) [VERIFICAT: raport #87; DECIZIE proiectant 28.10.2026, Î4]. Invertoarele monofazate pe rețea trifazată: dezechilibrul între faze > 3,68 kVA (înainte 4,6 kVA, VDE-AR-N 4105) → V71.
- Iac,max > Ip_Q al branșamentului existent → V72 AVERTISMENT „limitați injecția sau solicitați ATR nou”.
- DDR pe circuitul invertorului: **doar la cerere** (`ddr` {IdN_mA, tip} / `ddr: true` / `IdN_min_mA` din fișă) [DECIZIE proiectant 28.10.2026, Î6 — „nu prea se pun diferențiale la invertoare”]; fără cerere, în TN, fără DDR (deconectare prin întreruptor). La cerere fără IΔn: după producător — Huawei ≥ 100 mA la orice putere (manualul SUN2000-3…10KTL-M1), altfel 30 mA ≤ 10 kW / 100 mA peste [raport #93]. În **TT** DDR-ul rămâne protecția la defect (30 / 100 mA cât permite RA). Cu DDR: tip A, sau B dacă fișa nu exclude curenți de defect c.c. → V73 AVERTISMENT până se confirmă tipul.
- Invertor hibrid cu baterie: bateria e cuplată în c.c. (fără PCS separat), dacă nu se spune altfel.
- Contor bidirecțional, furnizat de OD. PI integrată în invertor, certificată, cu reglaje conform ATR.
- **v1.9 (R5):**
  - **Mai multe invertoare:** `invertoare[]` ca la CEF ({n, Pn_kW, Iac_max_A, hibrid, producator, model, L_m, cablu, ddr, spd_ca, IdN_min_mA, tip_ddr}); `Pn_inv_kW` (+ `invertor`) rămâne alias pentru un singur invertor; ambele declarate și diferite → V91 AVERTISMENT. Fiecare invertor e desenat separat (câmp PV, c.c. complet, invertor, Q, DDR dacă e cazul). Notații: un invertor → PV, S, INV, QI, DDR (istoric); mai multe → PV{k}, S{k}, INV-{k}, QI{k}. Limitele (400 kW, 40 A mono) se aplică pe Σ.
  - **Stocare** (`bess` {P_kW, kWh, producator, model, U_nom_V, cuplaj} sau `baterie` / `baterie_kWh`): cuplaj `bess.cuplaj` explicit („cc” / „ca”); altfel invertor hibrid declarat sau `baterie` → **c.c.**: bateria pe **portul de baterie** al invertorului hibrid (lateral de forță din invertor: FB separator-siguranță c.c. → BAT), NU în serie pe linia c.c. PV → invertor; protecția c.c. In ≥ 1,25·P/U_nom (seria `SIGURANTE_CC_BATERIE_A`), fără U_nom → „conform fișei” (presupus). `bess` fără invertor hibrid → **c.a.**: PCS separat (ramură ca la CEF: BAT → SB-B + SPD c.c. → PCS → QB), P = kWh/2 dacă lipsește (presupus).
  - **TD-PV la toți prosumatorii** [DECIZIE proiectant 28.10.2026, Î5]: la toate casele există tablou separat pentru fotovoltaic (TD-PV cu QG, plecare spre „TE EXISTENT” / „TG EXISTENT” / „BMPT EXISTENT” / „PT EXISTENT”), indiferent de putere — `rez.td_pv`. Aplicația **întreabă** dacă există protecții pe partea de c.c. (cutie c.c.: separator de c.c. sub sarcină + SPD c.c.) și pe c.a. (SPD c.a. la invertor / pe bara TD-PV): câmpurile `protectii_cc` / `protectii_ca` (da / nu; nedeclarat = da, presupus și întrebat în panoul de confirmare — `engine/confirmare.intrebari_confirmare`, câmpuri în panou și în tab-ul Calcul). „nu” → planșa nu desenează SPD-ul / cutia c.c. (rămâne separatorul integrat în invertor), respectiv SPD-urile c.a.; protecția la supracurent a circuitului invertorului rămâne.
  - **Prosumator comercial** (Σ Pn > `PROSUMATOR_COMERCIAL_KW` = 27 kW — cerință OD confirmată de proiectant —, sau `comercial: true`): nu se desenează ca tablou de casă (fără iluminat / prize / boiler) — TD-PV cu QG (Ip,min = max(Σ Iac; Ip invertoare)), C0 opțional (`L_racord_m`, `cablu_C0`) până la „TG EXISTENT” / „BMPT EXISTENT” / „PT EXISTENT” după `racord`. Prosumatorul de casă (≤ 27 kW): tot TD-PV cu QG (Î5), legat în „TE EXISTENT”; circuitele generice ale TE nu se mai desenează.
  - **PI externă** (Σ Pn > `PROSUMATOR_PI_EXTERNA_KW` = 27 kW — OD cere tablou cu releu anti-insularizare peste 27 kW, confirmat de proiectant; **păstrat la 27 kW, nu 30 kVA** (Ord. 228/2018 art. 14), DECIZIE proiectant 28.10.2026, Î3; `PI_externa: true/false` din ATR are prioritate): releu de interfață extern (U/f, ROCOF) cu declanșare pe bobina BD a QG; sub prag PI integrată în invertor.
  - DDR, SPD c.a. la invertor, limitarea injecției, racordul — ca la §C.3 pct. 11.

### C.5 Post de transformare 20/0,4 kV
1. Sn ∈ `TRAFO_SN_KVA`. O valoare nestandard → interpretorul întreabă (F.7); în model → V05 BLOCANT.
2. **In_T = Sn·1000/(√3·400)** (1,4434·Sn).
3. **Q JT:** Ip,min = In_T → MCCB (≤ 1600 A) sau ACB, Ir = treapta ≥ In_T. Q impus cu In < In_T sau Ir < In_T → **V60 BLOCANT** (P0-2). Valori rezultate: 250 kVA → 400 A; 400 → 630; 630 → 1000; 1000 → 1600; 1600 → ACB 2500 A.
4. Ik3max și Ik1min la bara TGJT după B.13 și B.14.
5. Bilanț: Sc = ks·ΣPi/0,9 > Sn → V62 AVERTISMENT.
6. **Celula trafo:** Sn ≤ **630 kVA** → implicit separator de sarcină + siguranțe MT (SR EN 62271-105), cu In siguranță din `TRAFO_SIGURANTA_MT_A` [practică, raport #58]. Sn > 630 kVA → întreruptor + releu 50/51, 50N/51N + TC MT (sau senzori) [DECIZIE proiectant 28.10.2026, Î10 — înainte 1000 kVA]. Siguranțe impuse la Sn > 630 kVA → **V61 BLOCANT**. Câmpul `celula_trafo` din rezultat: `"intreruptor"` (cod), `"separator de sarcină + siguranțe MT {In} A"`, sau, când siguranțele sunt impuse peste 630 kVA, `"separator de sarcină + siguranțe MT (nepermis peste 630 kVA — întreruptor + releu 50/51)"`. Textul „None” sau valori inventate sunt interzise (caz P07). Textul pentru listă și desen se ia din E.3.
7. **Obligatoriu pe model** (altfel V63 BLOCANT): neutrul trafo legat la priza de pământ comună MT/JT (TN; R „conform ANRE” — §C.7, `norme.PRIZA_PT_ANRE`: 1 Ω țintă + verificarea tensiunilor de atingere); TC (sau senzori) pentru releul MT când există întreruptor; descărcătoare ZnO 24 kV la trecerea LEA–LES; servicii proprii PT; punct de măsură conform ATR (MT sau JT).
8. Plecările se dimensionează ca în C.2 pct. 8, cu origine „pt_propriu” (limite ΔU 6/8 %).
9. Grupa de conexiuni implicită: Dyn5 [DECIZIE proiectant 28.10.2026, Î9] (se confirmă cu OD; la unele OD Dyn11).
11. **R2 (N-M4):** serviciile proprii (plecare generată, 16 A, L 10 m) sunt Cu PVC metoda C; protecția MCB dacă Ik3 bară ≤ 25 kA, altfel siguranță gG 16 A (120 kA, limitatoare) — nu MCCB pe cablu mărit termic.
10. **v1.2:** Q JT electronic: rezultatul conține `decl`, `Isd_A` (cel mai mare m cu 1,2·m·Ir ≤ Ik1min bara), `Isd_multiplu`, `tsd_s` (0,1 s), `Ii_A` (12·In), pentru listă și desen (E.3). PT fără plecări → V07 BLOCANT. Plecările gG au Icu 120 kA (B.4).

### C.6 Grup electrogen + ATS
1. In_G = Sn_GE·1000/(√3·400). Q_G: MCCB, Ip,min = In_G. Sarcina Ib > In_G → **V86 BLOCANT**, cu remedierea „GE minim {Sn_GE_minim_kVA} kVA”.
5. **Puterea minimă GE (arbitraj F42):** `Sn_GE_minim_kVA = norme.ge_sn_minim(P_kW, cosφ)` = cea mai mică valoare din `GE_SN_KVA` (10 … 2000 kVA [NEVERIFICAT, serie comercială]) cu Sn ≥ P/cosφ, adică In_G ≥ Ib. Se raportează totdeauna (G01–G03). Pornirea directă a motoarelor mari și sarcinile neliniare **nu** sunt incluse: se declară ca ipoteză. Exemplu: 60 kW / 0,9 = 66,7 kVA → 80 kVA.
2. ATS: 4 poli (comută și N) în TN-S cu neutrul GE legat la pământ local; interblocaj mecanic + electric; categoria AC-33B; In ≥ max(In Q_rețea ; In Q_G). Cu mai puțin de 4 poli sau fără interblocaj → **V87 BLOCANT**.
3. Ik3" = 1,1·In_G/x"d (Icu).
4. Deconectarea în regim GE: Ik1 ≈ 3·In_G dacă excitația susținută (PMG/AREP) e declarată, altfel ≈ In_G. Ik1 < Ia(Q_G) → V85 AVERTISMENT „deconectare prin DDR sau protecția generatorului (51V)”.
6. **v1.2 (C1, M3, minore):**
   - **Q_G:** MCCB până la In_G ≤ 1600 A, ACB peste (GE ≥ 1250 kVA → ACB, ex. In_G 1804 A → ACB 2000 A, Ir 1800 A). In = cel mai mic calibru ≥ In_G; **Ir = cel mai mare reglaj ≤ In_G** (protecție strictă la suprasarcină; ex. 100 kVA: 0,90·160 = 144 A ≤ 144,34 A). Icu Q_G ≥ Ik3" GE. Sarcina Ib > Ir Q_G → V86 BLOCANT (varianta „Ir”). In_G > 4000 A → V06.
   - **Q rețea (QR):** MCCB/ACB, Ir ≥ Ib sarcină, Icu ≥ Ik3max rețea (OD).
   - **Cablurile** se dimensionează ca ramuri B.21 și apar în rezultat ca `C1` (rețea → ATS, intrarea I, protejat de QR, contextul OD), `C2` (GE → ATS, intrarea II, protejat de Q_G, Ib = Ir Q_G, sursa GE: Z = j·x"d·Un²/Sn, buclă cu Ik1 = Ik1 regim GE, `regim_ge`: deconectarea se raportează prin V85, fără mărire) și `C3` (ATS → consumatori, Ib sarcină, protejat prin ATS de QR sau Q_G — se dimensionează la cel mai mare Ip; contextul = capătul C1; `C3.regim_GE` = ΔU cumulat și Ik1/Ik3 cu sursa GE, ΔU în regim GE peste 5 % → V20, peste 3 % → V21). Implicit Al PVC D1 (cablu `cablu` la nivelul schemei).
   - **R3 (N3-M1) — rețeaua normală:** fără `origine` = rețea publică prin branșament: Ib sarcină > 250 A → **V50 BLOCANT** („racord din PT”). Cu `origine = "pt_propriu"` + `pt_Sn_kVA`: Z și Ik din PT (B.13/B.14, ca la tablou), `PT_retea` în rezultat; √3·400·Ib > Sn PT → **V62 BLOCANT**. Fără `pt_Sn_kVA`: implicitele OD, limite 6/8 %.
   - **R2 (N-C1):** în regim GE (Ik1 ≈ In_G ≪ Ia Q_G) protecția la contact indirect se face cu **bloc diferențial 300 mA tip A, selectiv, asociat Q_G** (`Q_G.DDR`, SR HD 60364-4-41 art. 411.4.5, -5-55 art. 551.4); V85 INFO. `DDR_GE: false` → V85 BLOCANT. C3 se calculează separat în ambele regimuri, cu aceeași secțiune (cea mai mare): `C3` = regim rețea (QR, sursa = capătul C1), `C3.regim_GE` = ramură completă în regim GE (Q_G, sursa = capătul C2, obiect „C3 (regim GE)”); deconectarea se verifică în regimul cel mai defavorabil.
   - ATS: intrări distincte I (rețea) / II (GE), ieșire comună C3 (`ATS.intrari`, `ATS.iesire`); In ≥ max(In QR; In Q_G) din seriile MCCB/ACB; neutrul GE legat la pământ local (`neutru_GE`).
7. **E2 — protecția la defect în regim GE fără asigurare (decizia proprietarului 28.10.2026).** Când în regim GE
   Ik1 < Ia(Q_G) și nu există bloc diferențial aplicabil (V85 „B” / „ramura”, V97 „ge” — circuite de siguranță),
   motorul oferă AMBELE soluții, fiecare cu explicație (`scheme.GE_PROTECTIE_OPTIUNI`: când se folosește, ce implică, ce
   se desenează) în câmpul `optiuni` al verificării (`camp` = „ge_protectie”):
   (a) **`ge_protectie: "excitatie"`** — excitație susținută: curent de scurtcircuit susținut **≥ 3·In_G timp de ≥ 2 s**
   (`norme.GE_IK_SUSTINUT_MULTIPLU`, `GE_IK_SUSTINUT_T_S`), Q_G cu declanșator electronic, Isd reglat sub Ik1 din regim
   GE; calculul se reface cu Ik1 = 3·In_G; dacă nici așa nu deconectează → BLOCANT cu remediere (Isd, C2/C3, varianta b);
   (b) **`ge_protectie: "echipotential"`** — legături echipotențiale suplimentare (SR HD 60364-4-41 art. 415.2,
   R ≤ 50 V/Ia măsurat la PIF) → verificările devin INFO.
   Fără alegere → BLOCANT cu cele două opțiuni. Câmpurile vechi `excitatie_sustinuta` / `legaturi_echipotentiale` (true)
   rămân echivalente. Rezultat: `protectie_regim_GE` {solutie, necesara, titlu, implica, desen, Ik_sustinut_A,
   t_sustinut_s, optiuni}; nota §G.3 pe planșă și capitolul „Măsuri și evaluări suplimentare” din memoriu.

### C.7 Priza de pământ (v1.3, `pamant.py`)
Calculul rulează **numai** dacă intrarea schemei are cheia `priza`; altfel nota 2 de pe planșă rămâne „priza de pământ (calcul separat)”. Dispunerea calculată: n electrozi verticali **în linie**, la distanța a, legați cu platbandă orizontală (sau fără platbandă, `"platbanda": false`).

```
priza = {"rho_ohm_m": 100, "electrozi": {"n": 2, "L_m": 3, "d_m": 0.0635, "distanta_m": 6},
         "platbanda": {"L_m": 12, "latime_m": 0.04, "grosime_m": 0.004, "adancime_m": 0.8} | false,
         "R_limita_ohm": null, "sezon": "I"|"II"|"III"|număr|"implicit"|"k_sezon", "psi": număr}
```

**Valori implicite (declarate ca presupuse, V11):** ρ = 100 Ω·m (sol argilos-nisipos; prudent față de 80 Ω·m din ST 42 [VERIFICAT: raport #107]); 2 electrozi țeavă OL-Zn **Ø 60 × 3,6 mm** × 3 m (ST 42 DEER anexa 3 [VERIFICAT: raport #109]; înainte 2½″ = 63,5 mm); a = 2·L = 6 m; platbandă OL-Zn 40 × 4 mm la 0,8 m, **L_p = (n − 1)·a + L_racord** (racord la piesa de separație `platbanda.L_racord_m`, implicit 5 m; v1.3 R5, M5-1). **Coeficienți sezonieri distincți (v1.3 R5, M5-1)** [NEVERIFICAT, 1.RE-Ip 30-2004 / STAS 12604/5]: electrozi verticali ψ_e = I 1,8 / II 1,6 / III 1,4; platbandă orizontală la 0,5…0,8 m ψ_pl = I 4,5 / II 3,5 / III 2,5; implicit zona II (`sezon` = „I”/„II”/„III” le alege pe amândouă; `psi` / `sezon` numeric → ψ_e ∈ [1; 3]; `psi_platbanda` ∈ [1; 7]).

**Formule** (1.RE-Ip 30-2004 / STAS 12604/5-90; forma 0,366·ρ/L·lg = ρ/(2πL)·ln):

| Mărime | Formulă |
|---|---|
| ρ de calcul | ρ_e = ψ_e·ρ (electrozi), ρ_pl = ψ_pl·ρ (platbandă) |
| electrod vertical, capul la adâncimea h | R_e = ρ_e/(2πL)·[ln(2L/d) + ½·ln((4t + L)/(4t − L))], t = h + L/2 |
| platbandă orizontală (lățime b, adâncime h) | R_pl = ρ_pl/(2πL_p)·ln(2L_p²/(b·h)) |
| combinația | Rp = R_e·R_pl/(R_e·η_p + n·R_pl·η_e) |
| fără platbandă | Rp = R_e/(n·η_e) |

η_e, η_p = `norme.PRIZA_ETA_ELECTROZI` / `PRIZA_ETA_PLATBANDA` (electrozi în linie, a/L = 1, 2, 3; n = 1…30) [VERIFICAT: tabelul clasic Karyakin / PUE — raport #118–#119]: interpolare liniară în n, rândul a/L **imediat inferior** (conservator); a/L > 3 → rândul 3; n = 1 → η = 1.

**Limita Rp (normată):** TT → 50 V / IΔn_max (cel mai mare IΔn din rezultat, inclusiv RCCB BMPT; SR HD 60364-4-41 art. 411.5.3); PT și CEF cu PT propriu → **„conform ANRE”** [DECIZIE proiectant 28.10.2026, Î8]: priză comună MT/JT, `norme.PRIZA_PT_ANRE` — metoda: Rp ≤ 1 Ω (priză folosită în comun pentru protecție și paratrăsnet, curs TUIASI §5.3.1 din tematica ANRE) **și** verificarea tensiunilor de atingere și de pas cu curentul de defect la pământ din tratarea neutrului MT (STAS 12604/5-90, 1.RE-Ip 30-2004); ST 3-JT / ST 4-JT trimit la 1.RE-Ip 30 fără valoare, ST 42 DEER §3.5 dă 4 / 10,8 / 0,26 Ω pe tipuri de stâlpi. Textul normativ ANRE (1.RE-Ip 30-2004) nu a putut fi citit public → **valoare neclară: se păstrează 1 Ω**, cu nota „conform ANRE … — valoare de confirmat cu OD / ATR” în motivul limitei; branșament, tablou, prosumator, CEF JT, GE → 4 Ω [Î8]. **v1.3 R5 (M5-2):** `R_limita_ohm` poate doar **coborî** limita normată; o valoare mai mare → **V12 BLOCANT** „limita normată nu poate fi ridicată” (calculul continuă cu limita normată).

**Dimensionarea automată:** dacă Rp(n) > limită, n crește până la `PRIZA_N_MAX` = 30; platbanda crește cu a la fiecare electrod adăugat (L_p impus + (n − n_dat)·a, altfel (n − 1)·a + L_racord). Primul n cu Rp ≤ limită = `n_necesar` → **V37 INFO** (cu Rp inițial); nici la 30 → **V37 BLOCANT**, `n_necesar = null`, `ok = false`.

**TT:** fără `RA_ohm`, RA = Rp calculat (declarat „RA = Rp calculat …”, fără V34 „RA nedeclarat”); dacă Rp depășește limita, schema se recalculează cu Rp al prizei dimensionate.

**Validare (BLOCANT, obiect „priza de pământ”; schema se calculează în continuare):** `L_racord_m` < 0 → V07; `psi_platbanda` ∉ [1; 7] → V10; `priza`/`electrozi`/`platbanda` neobiect, ρ, L, d, a, L_p, b, g, h, R_limita ≤ 0 sau nenumerice, n nu e întreg ≥ 1 (ex. n = 0) → **V07**; ρ > 10 000 Ω·m, n > 30, L > 30 m, d ≥ L, a/L < 1 (n > 1), h > 5 m, ln(2L_p²/(b·h)) ≤ 1, ψ ∉ [1; 3] → **V10**; `sezon` necunoscut → **V12**.

**Rezultat** `rez["priza"]`: `Rp_ohm`, `R_limita_ohm`, `limita_motiv`, `ok`, `n_electrozi` (adoptat), `n_initial`, `Rp_initial_ohm`, `n_necesar`, `L_electrod_m`, `d_electrod_m`, `distanta_m`, `a_pe_L`, `adancime_m`, `t_m`, `L_platbanda_m`, `latime_platbanda_m`, `grosime_platbanda_m`, `rho_ohm_m`, `psi` (ψ_e), `psi_platbanda`, `rho_calcul_ohm_m`, `rho_calcul_platbanda_ohm_m`, `L_racord_m`, `eta_e`, `eta_p`, `R_electrod_ohm`, `R_platbanda_ohm`, `dispunere`, `RA_din_priza`, `materiale` = [{ref, denumire, cantitate, um, ore_u}] — cantități întregi; `ore_u` = manoperă orientativă pe unitate (`norme.PRIZA_ORE_U`, DECIZIE): PP-E electrozi buc (0,8 h); PP-PL platbandă m = ⌈1,1·L_p⌉ (0,1 h/m); PS piesă de separație 1 buc (0,5 h — aceeași cu PS din blocul BN·PS·PPL, nu se dublează în listă); PP-SUD îmbinări sudate = n + 1 + (bare de 6 m − 1) (0,3 h); PP-VOP vopsea bitum ⌈0,1 kg·îmbinări⌉, min. 1 kg (0,5 h/kg); PP-SAP săpătură șanț m = ⌈L_p⌉ (0,6 h/m), `pasi` (și în `pasi` generali) și `nota` (textul pentru planșă). Memoriul primește capitolul 4 „Priza de pământ”. **v1.3 (P0-2):** valorile presupuse ale prizei se declară cu valorile ADOPTATE după dimensionare („priză: 11 electrozi (mărit automat de la 2 …)”, „platbandă 65 m = (n − 1)·a + racord … (inițial 11 m)”). Memoriul, cap. 1: datele de intrare cu etichete românești și unități (`memoriu.ETICHETE`), structurile imbricate „etichetă: valoare; …”, tabele pentru plecări, grupuri de invertoare și datele prizei.

### C.8 Locuința — tabloul casei / apartamentului (v1.4, `locuinta.py`)
Lanțul: branșament (BMPM / BMPT; `alimentare.tip` „bransament_existent” implicit sau „bransament_nou”) → coloana C2 → tabloul locuinței (TE): Q general, SPD T2, grupe DDR 30 mA, circuite finale. `schema_pamant` ∈ {TN-C-S, TT} (altfel V28); `retea` **obligatorie** (lipsă → V07 BLOCANT „retea”, §A.1).

**Receptorii** (`norme.LOCUINTA_RECEPTORI`, valori implicite declarate ca presupuse [NEVERIFICAT individual — practică verificată prin sondaj, raport #123; DECIZIE după I7-2011, SR HD 60364-4-41 art. 411.3.3/411.3.4, -7-701, -7-722 și practica RO]):

| Receptor | P mono / tri [kW] | cosφ | MCB | S min Cu [mm²] | L [m] | Grupă DDR | DDR |
|---|---|---|---|---|---|---|---|
| iluminat | 0,5 | 0,9 | B10 | 1,5 | 20 | general | obligatoriu (411.3.4) |
| prize | 2 | 0,9 | C16 | 2,5 | 20 | general | obligatoriu (411.3.3) |
| prize_bucatarie / prize_baie / prize_exterior | 2,5 / 2 / 1,5 | 0,9 | C16 | 2,5 | 15 / 15 / 25 | bucătărie / baie / exterior | obligatoriu |
| masina_spalat_rufe / masina_spalat_vase / uscator | 2,2 / 2,2 / 2,5 | 1 | C16 | 2,5 | 15 | general / bucătărie / general | obligatoriu |
| boiler / cuptor | 2 / 3,5 | 1 | C16 / **C16** (v1.5) | 2,5 | 15 | general / bucătărie | obligatoriu |
| plita | 7,2 / 7,5 (3F) | 1 | C32 / C16 3P+N | 6 / 2,5 | 15 | bucătărie | obligatoriu |
| aer_conditionat / centrala_termica / incalzire_electrica | 2,5 / 0,2 / 3 | 0,9 / 0,9 / 1 | C16 / C10 / C16 | 2,5 / **1,5** / 2,5 | 20 / 10 / 20 | general | obligatoriu |
| pompa_caldura (**putere electrică absorbită**, v1.5) | **3,5 / 6** (3F) | 0,95 | **C20 / C16** 3P+N | **2,5** / 2,5 | 20 | general | obligatoriu |
| vehicul_electric | 7,4 / 11 (3F) | 1 | C40 / C20 3P+N | **4 / 4** (v1.7, minim; secțiunea din Iz / ΔU / Ik) | 25 | **proprie** | obligatoriu, **tip B** (sau A-EV + RDC-DD 6 mA c.c., -7-722) |
| pompa_apa (motor, pornire directă) / poarta_automata | 1,1 / 0,5 | 0,85 | C16 / C10 | 2,5 / **1,5** | 30 | exterior | obligatoriu |
| sauna | 6 / 9 (3F) | 1 | C32 / C16 3P+N | 6 / 2,5 | 15 | **proprie** (v1.5) | obligatoriu; cablu termorezistent SiHF în cabină (-7-703) |
| alt_circuit | 2 | 0,9 | C16 | 2,5 | 20 | general | obligatoriu |

**v1.5 — secțiunea 1,5 mm² la centrală / poartă:** regula generală §B.8 (forță ≥ 2,5 mm²) dădea 2,5 mm², deși tabelul cere 1,5 (constatarea m1 a verificatorului). Se aliniază codul la tabel: receptoarele fixe ≤ 10 A ale locuinței (`norme.LOCUINTA_S_MIN_FIX_MM2`: centrală termică, poartă automată) primesc 1,5 mm² Cu (I7-2011 admite 1,5 mm² pe receptoare fixe ≤ 10 A); ΔU și Ik1 se verifică normal (secțiunea crește automat dacă e nevoie). În pământ rămâne minimul de 6 mm².
**v1.7 (N17) — VE dimensionat normal, minim 4 mm² (DECIZIE):** v1.4–v1.6 impuneau 6 mm² fix (11 kW 3F pe CYY-F 5×6 — rezervă tacită pentru 22 kW). Acum circuitul VE se dimensionează ca orice circuit (Ib / In, Iz' ≥ In, I2 ≤ 1,45·Iz', ΔU 5 %, Ik1 ≥ Ia), cu minimul 4 mm² Cu: sarcină continuă la curentul nominal ore în șir, fără simultaneitate (IEC 60364-7-722 art. 722.311), iar la B2 cu 3 conductoare încărcate 2,5 mm² are Iz ≈ In (20 A) — fără rezervă termică. Rezultat: 11 kW 3F → C20, 5×4 mm²; 7,4 kW mono → C40, Iz cere 10 mm². `presupus[]` o spune explicit și cere secțiunea impusă (`cablu.S_fortat`) dacă se dorește rezervă pentru 22 kW.
**v1.5 — DDR obligatoriu pe toate circuitele:** în locuințe toate circuitele finale au DDR ≤ 30 mA (SR HD 60364-4-41:2017 art. 411.3.3 — prize și iluminat în locuințe, 411.3.4; -7-701 baie, inclusiv boilerul; -7-722 VE). Coloana „DDR” a tabelului `LOCUINTA_RECEPTORI` e „obligatoriu” peste tot.

La rețea trifazată, plita, pompa de căldură, VE și sauna sunt implicit 3F (3P+N), dacă `faza` nu e dată. Circuitul e ramură B.21 completă (rol „final”, MCB cu curba din tabel, `In_minim` = calibrul uzual, `S_min` = secțiunea minimă, Cu, **metoda B2** = tub pe/în perete, nouă în `norme.IZ` [NEVERIFICAT, IEC 60364-5-52 col. B2]); ΔU cumulat de la punctul de delimitare (inclusiv coloana): iluminat 3 %, restul 5 % (V20). Câmpurile `cablu`, `In_A` (calibru impus), `L_m`, `P_kW` ale circuitului au prioritate.

**1. Bilanț (v1.5):** Pi = Σ P; Pc = ks·Σ P_general + Σ P_continuu, cu ks după numărul receptoarelor generale (≤ 3: 0,8; 4–5: 0,6; 6–9: 0,4; 10–15: 0,35; > 15: 0,3 — **regulă proprie a aplicației, [DECIZIE proiectant 28.10.2026, Î11 — seria actuală]**; NU IEC 61439-2 tab. 101, care e factorul de diversitate al ansamblurilor) și ks = 1 pentru sarcinile continue (VE, pompă de căldură, încălzire electrică, saună); `ks` dat → Pc = ks·Pi. Ib(Pc) = Pc/(U·0,95) (cosφ mediu al locuinței, DECIZIE).
- **P aprobată declarată (P0-1):** Ib general = Pa/(U·0,95) — sarcina contractată din ATR; coloana, Q general și Q-ul presupus se dimensionează pe ea. Pc din ks e **informativ**: Pc > Pa → **V46 AVERTISMENT** (obiect „schema”; remediere: ATR, ks = Pa/Pi justificat, DLM la VE). Pa/(U·0,95) > 1,13·In Q declarat → **V46 BLOCANT** „pa” (ATR incoerent); între In și 1,13·In nu se semnalează (Pa și Q vin amândouă din ATR — ex. 7 kW / 32 A dă 32,04 A).
- `rez["bilant"]`: `Ib_A` = Ib general (din Pa dacă e declarată, altfel din Pc), `Ib_Pc_A` (informativ), `Ib_baza` („P aprobată (ATR)” | „Pc din bilanț”).

**1a. V46 pe faza cea mai încărcată (C1, v1.5):** după repartizare (pct. 4–5), curentul de calcul pe fiecare fază I_f = ks·Σ Ib_general(f) + Σ Ib_continuu(f) (Ib cu cosφ-ul fiecărui circuit; 3F încarcă toate fazele; `ks` declarat → ks·Σ Ib(f)). Față de In Q branșament (declarat, presupus sau ales):
- I_f > 1,13·In (curentul convențional de nedeclanșare, SR EN 60898-1) → **V46 BLOCANT** „ib”;
- In < I_f ≤ 1,13·In și faza alimentează sarcini continue → **V46 BLOCANT** „cont” (curentul rămâne peste In ore în șir);
- In < I_f ≤ 1,13·In fără sarcini continue → **V46 AVERTISMENT** „av” („sub 1,13·In nu declanșează convențional, fără rezervă”);
- se emite o singură dată (obiect „Q”), pentru faza cu nivelul cel mai grav. `rez["faze"]` primește `L1_calc_A`, `L2_calc_A`, `L3_calc_A` (curent de calcul, cu simultaneitate), `L1_continuu_A` … (partea continuă), `faza_max`, `I_calc_max_A`, `definitie_calc`, pe lângă curentul instalat `L1_A` … și `dezechilibru_pct`.

**2. Branșament și coloană (v1.5):**
- **existent cu Q declarat** (`In_Q_bransament_A`, seria BMPM/BMPT, altfel V05): coloana poartă min(In Q, I_dim);
- **existent fără Q (P0-2):** Q presupus = calibrul standard ≥ I_dim (declarat în `presupus[]`, `alimentare.Q_presupus = true`), cu I_dim = Ib general din Pa (dacă e declarată), altfel max(Ib(Pc), I_f,max). Nu se mai deduce un Q mai mic decât sarcina. I_dim peste limita blocului (BMPM 40 A la mono, BMPTd-100 100 A la tri) → **V46 BLOCANT** „bloc” cu remedierea (Q real / ATR trifazat / BMPTi) și calculul se oprește. Apoi se aplică aceeași regulă 1a ca la Q declarat (comportament coerent);
- **nou:** blocul §C.1 la max(Ib general, Ib(Pc), I_f,max) (mono > 40 A → V53, se propune trifazat).
- **v1.6 (m8) — curentul coloanei la branșament existent:** min(In Q, max(I_dim, I_f,max)) — faza cea mai încărcată, nu Ib echilibrat din Pa (ΔU și Iz ale coloanei nu mai sunt subestimate la dezechilibru; neutrul nu se încarcă suplimentar în calcul — aproximare declarată).
- **v1.6 (N5, m-n5) — Q / Pa nedeclarate la branșament EXISTENT:** Q-ul și puterea aprobată ale unui branșament existent sunt **date**, nu se aleg. Fără `In_Q_bransament_A` → pe lângă `presupus[]`, **V46 AVERTISMENT „q_pres”** (obiect „Q”, `camp` = „alimentare.In_Q_bransament_A”): „Q branșament existent nedeclarat — presupus X A …; se completează din ATR / certificatul de racordare”; fără `P_aprobata_kW` → **V46 AVERTISMENT „pa_pres”** (obiect „schema”), `alimentare.Q_presupus` / `alimentare.Pa_presupus = true` (pentru mențiunea de pe planșă). **DECIZIE: AVERTISMENT, nu BLOCANT** — spre deosebire de rețea (care schimbă tot tabloul), Q / Pa presupuse acoperă sarcina calculată, iar orice depășire e blocată de V46 „ib” / „cont”. Mesajele V46 BLOCANT / AV calculate pe Q presupus încep cu „Q branșament presupus X A (nedeclarat) — …”, iar prima remediere e „introdu Q branșament real din BMPM / BMPT”. Q nedeclarat peste limita blocului: V46 BLOCANT „bloc”, dar calculul **continuă** cu Q = limita blocului (rezultat parțial, exportul refuzat).
- **v1.6 (N2) — bugetul de ΔU al coloanei: `norme.LOCUINTA_DU_COLOANA_BUGET_PCT` = 1,5 % (DECIZIE).** Coloana se calculează întâi normal; dacă ΔU pe coloană > 1,5 %, secțiunea coloanei nu e impusă și **cel puțin un circuit final ar ieși cu secțiune mai mare decât cu coloana la buget** (probă cu jurnal temporar), coloana primește ținta ΔU ≤ buget (ramura B.21 cu `tinta_dU`: mărirea §B.12 până la țintă; limita V20 / V21 rămâne cea normată) și abia apoi circuitele se dimensionează (cresc doar dacă ΔU o cere și după mărirea coloanei). Circuitele rămân la secțiunea uzuală (1,5 iluminat / 2,5 prize) acolo unde ΔU permite. `coloana.marit_buget_dU` = {buget_pct, dU_initial_pct, S_initial_mm2, circuite}; pas în memoriu. Exemplu (runda 4b caz 10): coloana 3×6 (2,45 %) → 3×10 (1,46 %), iluminatul de 60 m 2,5 mm² (nu 6), prizele de 55 m 4 mm².
- **v1.7 (m-c6) — plafonul circuitelor finale la ΔU: `norme.LOCUINTA_S_MAX_CIRCUIT_DU_MM2` = 16 mm² (DECIZIE).** Mărirea automată pentru ΔU (§B.12) a unui circuit final al locuinței (fără secțiune impusă) se oprește la 16 mm², fără cabluri în paralel (ramura B.21 cu `S_max_dU`): peste, problema e coloana sau poziția tabloului, nu circuitul (cazul verificatorului: coloana impusă 6 mm² / 60 m, ΔU la bară 5,89 % → circuitele de lumină / prize urcau la 4 × 240 mm²). Circuitul rămâne la plafon, `dU_plafonat_mm2` = 16 în rezultatul lui, iar V20 BLOCANT spune „secțiunea circuitului plafonată la 16 mm² (ΔU la bara TE x %)”, cu remedierea „mărește coloana C2 / mută tabloul; altfel scurtează / împarte circuitul (tablou secundar)”. Secțiunile cerute de Iz (nu de ΔU) nu sunt plafonate.
- **v1.7 (M-c1) — Q branșament în afara seriei** (ex. 33 A; 63 A la monofazat; seria BMPM 16…40 A, respectiv toate treptele BMPT 16…250 A): **V05 BLOCANT** (obiect „Q”, `camp` „alimentare.In_Q_bransament_A”, cu vecinii din serie), valoarea se ignoră și calculul **continuă** cu Q presupus = calibrul standard imediat superior, limitat la limita blocului (BMPM 40 A; BMPTi-250 250 A), `alimentare.Q_presupus = true`, explicat în `presupus[]`; nu se mai emite V46 „q_pres” (V05 acoperă câmpul). Înainte: rezultat gol, planșă goală, fără `camp`.
- **v1.6 (P1-10) — `alimentare.zona`** ∈ {„urban”, „rural”} (sinonime „oras”, „sat”; altfel V12 BLOCANT, câmpul ignorat): fără `Zb_OD_ohm`, „rural” → Zbuclă OD implicită `norme.LOCUINTA_ZB_OD_RURAL_OHM` = **0,8 Ω** (R/X ca la valoarea implicită) **[DECIZIE proiectant 28.10.2026, Î2; înainte 0,45 Ω]**, declarată; nedeclarată → 0,30 Ω (urban), iar `presupus[]` spune explicit valoarea urbană folosită și cum se declară zona rurală. `alimentare.zona` apare în rezultat.
- **v1.6 (N3) — conductoarele racordului și ale coloanei:** `alimentare.C1_conductoare` = „L + PEN” / „3L + PEN” (TN-C-S) sau „L + N” / „3L + N” (TT). `coloana.conductoare`: TN-C-S „L + N + PE” / „3L + N + PE”, `PE_origine` „bloc”, `legatura_BPE` true; **TT** „L + N” / „3L + N”, `PE` = „fara”, `S_PE_mm2` = null, `PE_origine` „priza_locala”, `legatura_BPE` false, cablul fără conductor PE (ex. „CYAbY 2×6 mm²” / „CYAbY 4×6 mm²”); `PE_nota` explică. PE-ul instalației TT pornește numai din priza locală (PPL → BPE).
- **Coloana C2** = ramură completă protejată de Q branșament (Cu implicit, L 15 m implicit), `rez["coloana"]`. Metoda: `alimentare.cablu.metoda` (B2 / C / D1 …) sau câmpul nou **`alimentare.pozare_coloana`** ∈ {„pamant” → D1 (CYAbY), „cladire” / „tub” → B2 (CYY-F), „aparent” → C (CYY-F)}; nespecificat → D1, declarat ca presupus (cu indicația pentru apartament / tablou în clădire). Valoare necunoscută → V12 BLOCANT pe „C2”.

**3. Q general TE:** implicit **întreruptor-separator** (`norme.IS_IN_A`) 2P/4P cu In ≥ In Q branșament — nu declanșează (selectiv față de Q) și e protejat la suprasarcină de Q; Ib > In Q nu mai mărește IS-ul (e V46). `Q_general_tip = "MCB"`: cel mai mare MCB C ≤ In Q branșament și ≥ min(Ib, In Q), verificat cu B.18 („Q general vs Q branșament”); MCB > In Q → V40 BLOCANT. **SPD T2** la intrare (In 20 kA, Up ≤ 1,5 kV, Uc 275 V, 1P+N / 3P+N; `configuratie`: CT1 la TN, CT2 „1+1”/„3+1” la TT, SR HD 60364-5-534). **v1.6 (N4, m-n2) — protecția de rezervă a SPD-ului (F2):** `SPD.protectie_rezerva` = {tip „MCB”, In_A, curba „C”, poli (= poli SPD), Icu_kA, ref „F2”, text}; In = cel mai mare MCB ≤ min(25 A, In Q branșament, In Q general MCB) — **DECIZIE** după fișele uzuale ale SPD T2 In 20 kA (rezervă admisă MCB C ≤ 25…32 A sau gG ≤ 32…125 A; `norme.LOCUINTA_SPD_REZERVA`, [NEVERIFICAT] pe fișa SPD-ului ales). Pentru șablonul §E.3 `spd_ca`: `SPD.In_amonte_A`, `SPD.prot_tip` („MCB”), `SPD.curba_amonte` („C”); conductorul de pământ al SPD-ului la BPE (`SPD.PE_la`).

**3a. V40 (M2, v1.5) — DECIZIE:** MCB / RCBO de circuit cu In > In Q branșament → **V40 BLOCANT** „loc” (aparatul nu poate fi selectiv, Q declanșează înaintea lui); idem Q general MCB. **Nu** se emite V40 pentru IS și RCCB cu In > In Q: aparatele fără protecție la supracurent trebuie să aibă In ≥ In-ul protecției din amonte, care le protejează (SR HD 60364-5-53 art. 531.2) — In mai mare e direcția corectă.

**3b. Capacitatea de rupere a RCCB / IS (m10, v1.5) — DECIZIE pragmatică:** Ik3max la bara TE (după coloană) se compară cu capacitatea **condiționată** uzuală (`norme.LOCUINTA_INC_KA` = 6 / 10 kA [NEVERIFICAT: tabelele producătorului, raport #129]: Inc RCCB SR EN 61008-1, Icc condiționat IS SR EN 60947-3, cu protecția din amonte — Q branșament + SF gG). Se alege prima treaptă ≥ Ik3 (`DDR.Inc_kA`, `Q_general.Icc_kA`) → V33 INFO „cond”; Ik3 > 10 kA → **V33 AVERTISMENT** „cond_AV” (confirmarea coordonării în tabelele producătorului). Icw-ul IS-ului (≈ 12·In / 1 s) nu e criteriul la scurtcircuit cu protecție limitatoare în amonte. RCBO: Icn = Icu-ul MCB-ului ales (§B.16, `DDR.Icn_kA`).

**4. Grupe DDR 30 mA (v1.5):**
- cel mult `LOCUINTA_CIRCUITE_PE_DDR` = **5** circuite pe un DDR (DECIZIE: scurgerea a ~5 circuite casnice < 9 mA ≤ 0,3·IΔn, SR HD 60364-5-53 art. 531.3.2);
- **v1.7 (N16) — prizele (și celelalte categorii) pe niveluri (DECIZIE):** în categoriile general / bucătărie / baie / exterior, dacă numele circuitelor dau **cel puțin două niveluri** distincte (aceleași reguli ca la iluminat), fiecare nivel formează un lot propriu (⌈n/5⌉ grupe), iar circuitele fără nivel deductibil completează, în ordinea intrării, lotul cel mai mic; fără niveluri sau cu un singur nivel, gruparea rămâne cea din v1.6 („când se poate” = nu se amestecă nivelurile, fără grupe suplimentare pentru circuitele fără nivel). Exemplu P+1: „Prize living / hol parter” + „Prize birou” pe DDR-ul parterului, „Prize dormitor 1–3 etaj” pe altul;
- **v1.6 (P1-4) — iluminatul pe niveluri (DECIZIE):** cel mult `LOCUINTA_ILUMINAT_PE_DDR` = **2** circuite de iluminat pe un DDR; nivelul dedus din nume (fără diacritice: „subsol” / „demisol” → subsol, „parter”, „etaj N” / „et. N” → etajN, „mansard…”, „exterior” / „ext” / „curte” / „grădină” / „fațadă” / „terasă” / „gard” → exterior, „pod”) formează loturi separate — circuitele de pe niveluri diferite nu stau pe același DDR (un defect nu stinge parterul și etajul); circuitele fără nivel deductibil formează un lot propriu. Un singur lot cu ≥ 2 circuite → cel puțin 2 grupe (ca în v1.5). `grupe_DDR[].nivel` pentru grupele de iluminat;
- categorii, în ordine: **iluminat** (separat de prize; ≥ 2 circuite de iluminat → cel puțin 2 grupe, ca un defect să nu lase toată casa în întuneric), general, bucătărie, baie, exterior; apoi grupe proprii, câte una pe circuit, în ordinea intrării: **saună**, VE (DDR tip B, alternativ A-EV + RDC-DD 6 mA), circuitele cu `DDR` impus; la final „fără DDR” (`DDR: false`: prize → V29 BLOCANT, orice alt circuit → **V49 BLOCANT**);
- o categorie se împarte în ⌈n/5⌉ grupe cât mai egale (ordinea intrării);
- **trifazat:** circuitele 3F ale unei categorii formează grupe **4P** (completate până la 5 cu monofazate ale categoriei, repartizate individual pe faze); restul monofazatelor formează grupe pe **o singură fază → DDR 2P**: fazele impuse se grupează pe faza lor, grupele libere se repartizează pe faza cea mai puțin încărcată (Σ Ib descrescător, după circuitele 3F și cele cu faza impusă); `grupe_DDR[].faza` = L1 | L2 | L3 | 3F;
- **circuit singur în grupă → RCBO** (`DDR.aparat = "RCBO"`, `DDR.In_A` = In MCB, `DDR.curba`, `DDR.Icn_kA`; protecția circuitului `protectie.tip = "RCBO"` cu `IdN_mA`, `tip_ddr`, `poli` „1P+N” | „4P”, păstrând In, curba, Icu). Excepție — VE: RCCB tip B + MCB (RCBO tip B e aparat rar, DECIZIE);
- In RCCB = cea mai mică treaptă ≥ max(In MCB max; min(In Q branșament, Σ In MCB pe faza cea mai încărcată a grupei)), minimum 25 A (`LOCUINTA_RCCB_IN_MIN_A`, RCCB comerciale);
- DDR impus cu IΔn > 30 mA → V29 BLOCANT (prize) / **V49 BLOCANT** „idn” (orice alt circuit); tip AC → V49 AVERTISMENT „tip_ac”; VE cu tip ≠ B impus → V49 AVERTISMENT „ve_tip” (se păstrează, cu condiția RDC-DD); `selectiv: true` cu IΔn < 100 mA → V12 BLOCANT „ddr_s” (DDR 30 mA S nu există);
- **v1.7 (M-c3) — VE sub DDR-ul 300 mA al branșamentului (DECIZIE):** tipul DDR-ului din branșament = `alimentare.DDR_bransament_tip` ∈ {AC, A, F, B} (nou; altfel V12 BLOCANT „camp”, ignorat), implicit tipul din ST 3-JT / ST 4-JT (`norme.BMPM.rcd_tip` / `BMPT_RCCB.tip` = AC, declarat în `presupus[]`); `alimentare.DDR_bransament_tip` apare în rezultat. Un curent de defect c.c. neted al stației de încărcare trece și prin DDR-ul din amonte și îl poate „orbi” (SR HD 60364-5-53:2015 art. 531.3.2; IEC 60364-7-722:2018 art. 722.531.3.101). Regula: amonte **B** → în regulă; amonte **A / F** cu DDR-ul VE tip A / F (stația are RDC-DD 6 mA, deci c.c. ≤ 6 mA, pe care tipul A / F îl tolerează) → în regulă; altfel (amonte AC, sau amonte A / F cu DDR VE tip B) → **V43 „ve_dc”** (obiect „DDR{k} vs RCBO BMPM / RCCB BMPT”, `camp` „alimentare.DDR_bransament_tip”): **AVERTISMENT la TN-C-S**, **BLOCANT la TT** (doar cu tipul DECLARAT; tipul presupus AC din ST DEER rămâne AVERTISMENT și în TT, cu remedierea „declarați blocul real” — Î1, 28.10.2026) — în TT DDR-ul 300 mA al branșamentului e protecția la defect (RA·IΔn ≤ 50 V) a coloanei C2 și a intrării TE, iar „orbirea” lui lasă aceste părți fără deconectare automată (art. 411.5). Remediere: DDR amonte tip B (F-B / B+), sau declararea tipului real dacă e deja B; alimentarea VE dintr-un circuit fără DDR AC / A în amonte, conform producătorului; sau stație cu RDC-DD 6 mA + DDR VE tip A sub un amonte cel puțin tip A. **Articolele se confirmă de proiectant** (verificatorul le-a marcat de confirmat);
- fiecare grupă se verifică față de DDR-ul branșamentului (V43; RCBO BMPM instantaneu → AVERTISMENT); **v1.6 (P2-1):** verificările cu același mesaj se agregă într-una singură („DDR1–DDR4 vs RCBO BMPM: selectivitate DDR nerealizată … DDR1–DDR4 …”; listă „DDR1, DDR3” dacă nu sunt consecutive);
- fiecare circuit primește `protectie_defect` (text): TN — „MCB: Ik1min ≥ Ia” (+ DDR protecție suplimentară) sau „DDR … — Ik1min < Ia”; TT — „DDR … — TT: RA·IΔn = … V ≤ 50 V; Ik1/Ia doar pentru scurtcircuitul L–N”. Saună: `cablu_nota` (cablu termorezistent SiHF / silicon în cabină, -7-703). Circuitele au și `continuu`.

**5. Faze (tri):** circuitele 3F încarcă toate fazele; repartizarea monofazatelor se face odată cu grupele (pct. 4); `faza` impusă se respectă (la mono doar L1, altfel V12). **v1.6 (m-n3) — repartizarea se face pe curentul de CALCUL** (ks·Ib pentru receptoarele generale, Ib pentru sarcinile continue; `ks` declarat → ks·Ib), în ordinea fixă: (1) circuitele 3F; (2) circuitele cu faza impusă; (3) toate unitățile monofazate libere — grupele 2P întregi și monofazatele din grupele 4P / „fără DDR”, individual — **descrescător după curentul de calcul** (la egalitate, ordinea intrării), fiecare pe faza cu cel mai mic curent de calcul (la egalitate L1 < L2 < L3). Exemplu K02 (verificator): 37,05 / 37,05 / 40,24 A → Q C50 în v1.5; v1.6: maxim 38,31 A → Q C40. Dezechilibrul = (Imax − Imed)/Imed din Ib instalat; > 30 % → **V47 AVERTISMENT**; informativ `faze.dezechilibru_calc_pct` (din curentul de calcul), `faze.repartizare`.

**6. TT (P0-3, v1.5):** RA (implicit 4 Ω, V34 AV) — RCCB-ul / RCBO-ul branșamentului 300 mA verificat (V34 BLOCANT peste 50 V), grupele 30 mA, timpii TT (0,2 s), nota 3 din valorile reale. **Protecția la defect (contact indirect) în TT = DDR-ul** (RA·IΔn ≤ 50 V, SR HD 60364-4-41 art. 411.5.3): curentul de defect prin pământ (≈ U0/(RA + RB), câțiva amperi) nu acționează MCB-ul. Pe fiecare circuit și pe coloană se emite **V30 „TT”** (INFO; AVERTISMENT „TT_AV” când Ik1 < Ia), care spune explicit asta; Ik1 / Ia rămân doar pentru protecția la scurtcircuit fază–nul. În TT nu se mai emite „deconectare automată îndeplinită: Ik1min ≥ Ia”. Memoriul are coloana „Protecția la defect” și paragraful TT. (Regula se aplică prin contextul `tt_ddr_defect` setat de locuință; celelalte tipuri de schemă TT rămân deocamdată ca în v1.3.)

**7. Validare (v1.5, minore):** numele circuitului se convertește la text (m3); `cablu` cu „cu” / „b2” se normalizează și se păstrează normalizat (m4); cheile necunoscute ale circuitului → V12 AVERTISMENT „necunoscut” (m12); `S_fortat` sub secțiunea minimă a receptorului → V13 „loc” (BLOCANT la prize < 2,5 mm², AVERTISMENT în rest, m11); receptor fără variantă trifazată declarat „3F” → P implicit = 3 × P mono (valorile monofazate pe fază, m5); VE cu `DDR: false` apare o singură dată (în „fără DDR”, m2).

**8a. v1.7 (m-c4, m-c5, N11, N13):** câmpurile globale **`Zb_OD_ohm`, `RA_ohm`, `Ik3_OD_kA`** invalide (≤ 0, nenumerice, Zb ca pereche negativă / nulă) → **V07 BLOCANT** cu `camp` = numele câmpului și mesaj românesc („impedanța buclei OD = −0,2 Ω — trebuie > 0 … — valoarea se ignoră, calculul continuă cu valoarea implicită (presupusă)”), valoarea se **ignoră** (Zb după zonă, RA 4 Ω cu V34 AV, Ik3 25 kA) și calculul continuă (`locuinta.prevalideaza`, apelată înaintea validării generale) — nu mai opresc tot calculul. Text în loc de număr la `P_aprobata_kW` / `In_Q_bransament_A` → „valoare nenumerică”, fără V46 „nedeclarat” pentru același câmp; V09 pe lungimea coloanei și V46 „bloc” primesc `camp`. **Etichete centralizate:** `locuinta.ETICHETE` (câmp → denumire) și **`locuinta.ETICHETE_RECEPTOR`** (receptor → denumire, aceeași listă ca interfața `RECEPTOR_LOC`), folosite în mesaje, remedieri, `presupus[]` („Prize bucătărie: P = 2,5 kW”, „Plită: lungime circuit 15 m”), V13 / V49 („„Încărcător vehicul electric””) și memoriu; o trecere finală (`fara_chei_receptor`) înlocuiește orice cheie de receptor rămasă; V34 în locuință nu mai cere câmpul inexistent „IdN_amonte_mA” (remediere: RA mai mic); V12 „retea” are remedierea despre rețea; eticheta „zona (urban / rural)” nu se mai dublează. Circuitele au **`receptor_eticheta`**. **Nota de ipoteze (G.2):** Ik3 / Zb implicite — „(valoare implicită, presupusă — se confirmă cu OD / ATR)”; declarate — „(declarat)” (nu „din ATR”); Zb rurală — „0,8 Ω presupus (zonă rurală, DECIZIE proiectant 28.10.2026) — se confirmă cu OD / ATR” (N11: înainte apărea „(din ATR)” pe planșă și în memoriu); cosφ grupat pe valoare cu receptoarele și sursa corectă: „cosφ = 0,95 (coloana C2, cosφ mediu al locuinței) (presupus); 0,9 (Iluminat, Prize) (presupus); 0,8 (Pompă apă / hidrofor) (declarat)” (N13: înainte toate „(declarat)”, fără receptor). **Bilanț:** fără receptoare generale ks = 1, iar `presupus[]` spune „numai sarcini continue … ks = 1” (nu „ks după 0 receptoare … 0,8”).

**8. Rezultate parțiale și câmpul `camp` (v1.6, UX 12–13):** o eroare **locală** nu mai golește rezultatul: câmpul invalid al alimentării (Q, Pa, L coloană ≤ 0 / nenumeric, `cablu`, `pozare_coloana`, `zona`, `tip`) se emite (BLOCANT) și se ignoră (valoarea implicită, declarată); un circuit invalid (P ≤ 0 sau > 30 kW, L ≤ 0, receptor / fază / DDR / cablu / curbă invalide, calibru inexistent V05 / V04) se emite BLOCANT, se calculează cu valorile implicite ale receptorului (receptor necunoscut → „alt_circuit”) și rămâne în grupa lui cu `blocat: true` (+ `blocat_coduri` la erorile de validare); protecția lui are In din intrare / calibrul uzual (`protectie.neverificat: true`), deci RCBO-ul / DDR-ul grupei au mereu `In_A` (M-n1). `rez["circuite_blocate"]` = obiectele blocate. Exportul rămâne refuzat. Doar lipsa rețelei / a circuitelor și coloana blocată opresc calculul. **Mesajele locuinței nu conțin chei interne:** „P_kW” → „puterea circuitului”, „alimentare.P_aprobata_kW” → „puterea aprobată (ATR)”, „In_Q_bransament_A” → „Q branșament” etc. (`locuinta.ETICHETE`); calea tehnică a câmpului se pune în cheia separată **`camp`** a verificării („alimentare.In_Q_bransament_A”, „circuite[3].P_kW” — index de la 0 în lista de intrare, „circuite[0].DDR.In_A”), pentru marcarea câmpului în interfață. Cheile necunoscute din `DDR` impus → **V12 AVERTISMENT** „necunoscut” (m-n4); `"retea": ""` la locuință → **V07** „nu este specificată” (m-n4; la branșament / prosumator rămâne V12, contract v1.2).

**Rezultat:** `retea` (v1.5, normalizată), `alimentare` {tip, bloc, Q, SF, RCCB?, TC?, contor, Ib_A, Pa_kW?, Q_presupus?, Pa_presupus? (v1.6), zona (v1.6), C1_conductoare (v1.6), DDR_bransament_tip (v1.7)}, `coloana` (ramură + `descriere`; v1.6: conductoare, PE_origine, legatura_BPE, PE_nota, marit_buget_dU?), `Q_general` {tip: IS|MCB, In_A, poli, curba?, Icu_kA?, Icc_kA? (IS), descriere?}, `SPD` {tip, In_kA, Imax_kA, Up_kV, Uc_V, poli, configuratie, loc, protectie; v1.6: protectie_rezerva, In_amonte_A, prot_tip, curba_amonte, PE_la}, `circuite_blocate` (v1.6), `grupe_DDR` = [{obiect „DDR{k}” | „fără DDR”, grupa (iluminat | general | bucătărie | baie | exterior | saună | vehicul electric | propriu | fără DDR), DDR {IdN_mA, tip, In_A, poli (2P|4P), aparat (RCCB|RCBO), temporizare, selectiv, Inc_kA? (RCCB), curba? + Icn_kA? (RCBO), alternativa?} | null, faza (L1|L2|L3|3F), circuite: [ramură completă + nume, receptor, receptor_eticheta (v1.7), receptor_calcul, faza, P_kW, DDR_grupa, DDR_obligatoriu, continuu, protectie_defect, cablu_nota?]}], `faze` {L1_A, L2_A, L3_A (instalat), L1_calc_A, L2_calc_A, L3_calc_A, L1_continuu_A, L2_continuu_A, L3_continuu_A, faza_max, I_calc_max_A, dezechilibru_pct (null la mono), definitie, definitie_calc}, `bilant` {Pi_kW, P_general_kW, P_continuu_kW, ks, ks_regula, Pc_kW, cosfi, Ib_A, Ib_Pc_A, Ib_baza, P_aprobata_kW, n_circuite}, `schema_pamant`, `nota_schema_pamant`. Memoriul: capitolul „Bilanț și repartizarea pe faze”.

---

## D. Catalogul de verificări

**Niveluri:**
- **BLOCANT** = exportul (DXF/PDF/Excel) este refuzat; elementul se colorează cu roșu pe planșă și în chat.
- **AVERTISMENT** = exportul e permis; avertismentul apare în memoriu și pe planșă, ca notă.
- **INFO** = se scrie doar în memoriul de calcul.

Fiecare rezultat de verificare are forma `{cod, nivel, obiect, mesaj, remediere}`. **v1.3 (P0-2):** mesajul nu mai repetă obiectul la început (e în câmpul `obiect`); după „1” substantivele sunt la singular („1 electrod”, „1 plecare”); imperativele din mesaje și remedieri sunt la persoana a II-a singular, ca în interfață („verifică”, „introdu”, „mărește”) — `texte.curata_text`. `obiect` e eticheta ramurii: `C2`, `Q1/C1`, `P{i}·{nume}`, `P{i}·{nume}.{j}·{nume}`, `INV-{i}`, `PCS`, `QG vs INV-{i}`, `{obiect} vs amonte`, `Q`, `TC`, `nota {k}` sau `schema`.

| Cod | Descriere | Formulă / condiție | Nivel | Mesaj (RO) | Remediere sugerată |
|---|---|---|---|---|---|
| V01 | Cablu nedimensionabil | nicio (n ≤ 4, S ≤ 240) cu n·Iz·k ≥ Iz_min, nici după fallback | BLOCANT | „{obiect}: nicio secțiune ≤ 240 mm² × 4 în paralel nu satisface Iz' ≥ {Iz_min} A” | bare capsulate, alt punct de racord, împărțirea sarcinii |
| V02 | Ip > Iz' (secțiune impusă) | Ip > n·Iz·k | BLOCANT | „{obiect}: Ip = {Ip} A > Iz' = {Iz'} A (Ib ≤ In ≤ Iz' încălcat)” | mărire secțiune / reducere calibru |
| V03 | I2 > 1,45·Iz' | I2 > 1,45·Iz' | BLOCANT | „{obiect}: I2 = {I2} A > 1,45·Iz' = {…} A” | idem |
| V04 | Ib > Ip (calibru impus) | Ib > Ip | BLOCANT | „{obiect}: Ib = {Ib} A > protecție {Ip} A” | calibru mai mare |
| V05 | Calibru inexistent | In ∉ serie (sau Sn ∉ TRAFO) | BLOCANT | „{obiect}: calibrul {In} A nu există în seria {tip}” | alegeți din serie (se afișează vecinii) |
| V06 | Ib > In maxim | Ib > max(serie) sau > 4000 A | BLOCANT | „{obiect}: Ib = {Ib} A depășește calibrul maxim ({tip})” | împărțirea sarcinii, alt nivel de tensiune |
| V07 | P absentă/≤ 0 / date invalide | P ≤ 0 sau lipsă și fără In; v1.2: orice câmp numeric nenumeric/neplauzibil (B.2), tip de schemă necunoscut, tablou/PT fără plecări, Zb ≤ 0 | BLOCANT | „{obiect}: P = {P} kW ≤ 0” / „{obiect}: {câmp} = {x} — {condiție}” / „tip de schemă necunoscut (…)” | introduceți puterea / valori plauzibile |
| V08 | cosφ absurd | cosφ ∉ (0;1] (BLOCANT); cosφ < 0,7 (AVERTISMENT) | BLOCANT/AV | „{obiect}: cosφ = {x} în afara intervalului (0; 1]” | 0,9 uzual |
| V09 | Lungime absurdă | L ≤ 0 (BLOCANT); L > 1000 m (AVERTISMENT) | BLOCANT/AV | „{obiect}: lungime {L} m ≤ 0” / „> 1000 m — verificați datele” | |
| V10 | Pozare în afara tabelelor | θ > max tabel, ρ > 3 K·m/W, n circuite > 20, ks ∉ (0;1] | BLOCANT | „{obiect}: {parametru} în afara tab. B.52.x” | studiu termic dedicat |
| V11 | Valoare implicită folosită | orice câmp din B.0 nespecificat | INFO | „Am presupus: {listă}” | |
| V12 | Rețea inconsistentă / date contradictorii | aparat 1P/2P pe ramură trifazată; mono cu bloc trifazat etc.; v1.2: `retea` ∉ {tri, mono} (după sinonime, A.1); v1.3 R5: `priza.R_limita_ohm` > limita normată; v1.5 (§C.8): DDR 30 mA selectiv („ddr_s”, BLOCANT), cheie necunoscută a circuitului sau a `DDR` impus (v1.6) („necunoscut”, AVERTISMENT) | BLOCANT (AV „necunoscut”) | „{obiect}: aparat {poli} pe rețea {retea}” / „rețea „{x}” necunoscută” | |
| V15 | Date de scurtcircuit inconsistente (v1.2) | Ik1min > Ik3max la capătul unei ramuri | BLOCANT | „{obiect}: Ik1min {x} A > Ik3max {y} A — impedanțele introduse sunt incoerente” | Ik3 și Zb din ATR |
| V13 | Secțiune inexistentă / nepermisă | S ∉ SECTIUNI_MULTIPOLAR[mat] (ex. Al 10); v1.5 „loc”: `S_fortat` < S min receptor locuință (BLOCANT la prize, AV în rest) | BLOCANT | „{obiect}: secțiunea {S} mm² {mat} nu există / nu e permisă” | Cu sau Al ≥ 16 |
| V14 | P declarată < bilanț | P_decl < ks·ΣPi | AVERTISMENT | „P declarată {P} kW < Pc din bilanț {Pc} kW — se folosește P declarată (Pa din ATR)” | ATR nou sau ks justificat |
| V20 | ΔU peste I7 (receptor final; v1.2: și bara tabloului > 5/8 %, cablu invertor > 3 %) | ΔU_cum > limită (B.12) după mărire | BLOCANT | „{obiect}: ΔU cumulat {x} % > {lim} %” | secțiune/paralel, mutarea tabloului |
| V21 | ΔU la bara tabloului / CEF | ΔU_cum > lim_forță − 2 % / > 1 % (CEF) | AVERTISMENT | idem | |
| V22 | ΔU la pornire motor | > 12 % (B.3.1, calculat totdeauna la motor cu pornire directă, v1.2) | AVERTISMENT | „{obiect}: ΔU la pornire directă {x} % > 12 %” | soft-starter, secțiune |
| V23 | Protecție motor la pornire (v1.2) | prag protecție < Ip pornire (B.3.1) | AVERTISMENT (calibru impus) / INFO (ales) | „{obiect}: {prot} poate declanșa la pornirea directă (Ip ≈ {x} A)” | calibru mai mare, aM + releu, MCCB |
| V24 | Protecția neutrului (v1.2) | h3 > 33 % | AVERTISMENT | „{obiect}: armonica 3 = {h3} % > 33 % — … SR HD 60364-4-43 art. 431.2.3” | aparat 4P cu N protejat |
| V25 | Neutru subdimensionat | N < S fără condițiile B.10 pct. 4 | BLOCANT | „{obiect}: neutru redus {N} mm² nepermis ({motiv}) — N = {S} mm²” | N = S |
| V26 | PE sub tab. 54.2 | n·S_PE < S_tab | BLOCANT | „{obiect}: PE {S_PE} mm² < {S_tab} mm² (SR HD 60364-5-54 tab. 54.2)” | PE mai mare |
| V27 | PEN incorect | PEN < 10 Cu/16 Al, sau în aval de DDR, sau instalație mobilă (A.2, v1.2) | BLOCANT | „{obiect}: PEN {…}” | separare N/PE înainte de DDR |
| V28 | Schemă de legare la pământ neacoperită (v1.2) | `schema_pamant` în afara listei A.2 pentru tipul schemei (IT, necunoscută) | BLOCANT | „schema de legare la pământ „{x}” nu este acoperită …” | TN-C-S / TN-S / TT |
| V29 | Circuit de prize fără DDR 30 mA (v1.2) | prize ≤ 32 A cu DDR refuzat (BLOCANT); DDR adăugat automat (INFO) | BLOCANT / INFO | „{obiect}: circuit de prize In {In} A ≤ 32 A fără DDR 30 mA” | DDR 30 mA tip A |
| V30 | Deconectare automată TN | Ik1min ≥ Ia (INFO); < Ia cu Zb cunoscut, fără DDR (BLOCANT); Ia lipsă (AV); v1.5 „TT” / „TT_AV” (locuință TT): protecția la defect prin DDR, Ik1/Ia doar pentru scurtcircuitul L–N (§C.8 pct. 6) | INFO/BLOCANT/AV | „{obiect}: deconectare automată neîndeplinită: Ik1min {x} A < Ia {y} A” | secțiune mai mare, curbă B, Isd mai mic, DDR |
| V31 | Deconectare prin DDR | DDR propriu (INFO) / DDR amonte (AV) | INFO/AV | „{obiect}: deconectarea se bazează pe DDR din amonte” | DDR pe plecare |
| V32 | Deconectare nesigură, Zb implicit | Ik1min < Ia cu z_implicit | AVERTISMENT | „{obiect}: Ik1min {x} A < Ia {y} A cu impedanța OD IMPLICITĂ — cereți valoarea reală” | cerere către OD |
| V33 | Icu insuficient | Icu < Ik3max la bară; v1.5 „cond” / „cond_AV”: capacitatea condiționată RCCB / IS la bara TE (§C.8 pct. 3b) | BLOCANT (AV cu rezervă gG, INFO la ST 4-JT; AV „cond_AV”) | „{obiect}: Icu {x} kA < Ik3max {y} kA la bara aparatului” | Icu mai mare |
| V34 | TT neconform | lipsă DDR sau RA·IΔn > 50 V | BLOCANT | „TT: RA·IΔn = {x} V > 50 V” | priză de pământ mai bună, IΔn mai mic |
| V35 | Stabilitate termică fază | B.17 | BLOCANT (impus) / AV (Ik3 implicit) / INFO | „{obiect}: fază {n}×{S} mm² < {x} mm² la Ik3max” | |
| V36 | Stabilitate termică PE | B.11 | BLOCANT (impus) / AV (Ik3 implicit) / INFO | „{obiect}: PE {S} mm² < {x} mm² necesar la scurtcircuit (k²S² < I²t)” | |
| V37 | Priză de pământ (v1.3) | §C.7: Rp ≤ limită (INFO, inclusiv după mărirea automată a lui n); Rp > limită și la 30 de electrozi (BLOCANT) | INFO/BLOCANT | „priza de pământ: Rp = {x} Ω ≤ {lim} Ω …” / „cu n = {n0} electrozi Rp = … → necesar n = {n}” / „Rp = {x} Ω > {lim} Ω chiar cu 30 electrozi …” | ρ măsurat, electrozi mai lungi, contur, tratarea solului |
| V43 | Selectivitate DDR în serie (v1.3; R5: și în timp); v1.7: VE sub DDR tip AC / A / F („ve_dc”, §C.8 pct. 4) | §B.18.1: IΔn am ≥ 3·IΔn av și t am − t av ≥ 0,15 s (S → S neselectiv); „ve_dc”: amonte ≠ B, iar nu (amonte A / F și VE A / F) | INFO/AVERTISMENT (ve_dc: AV la TN-C-S, BLOCANT la TT) | „{obiect} vs {amonte}: selectivitate DDR nerealizată …” / „… același IΔn = {x} mA și niciunul nu e de tip S” / „… în TT: RA = {RA} Ω limitează IΔn …” | DDR amonte S cu IΔn ≥ 3·IΔn aval / DDR aval mai mic / RA mai mic |
| V44 | Racord CEF în TG existent (v1.3) | C.3 pct. 12: Ip Q TG < Σ Iac (BLOCANT); Ip Q TG > Iz' C0 (AV); defect la capătul C0 nedeconectat de Q TG în 5 s (AV/BLOCANT) | BLOCANT/AV/INFO | „Ip {x} A < Σ Iac {y} A — protecția din TG declanșează la injecția CEF” / … | calibru Q TG între Σ Iac și Iz' C0, secțiune C0 mai mare |
| V46 | Putere locuință peste ATR / Q branșament (v1.4, v1.5) | §C.8 pct. 1, 1a, 2: Pc > P aprobată (AV, „pc”); faza cea mai încărcată I_f > 1,13·In Q („ib”) sau > In Q cu sarcini continue („cont”) → BLOCANT, In < I_f ≤ 1,13·In fără continue („av”) → AV; Pa/(U·0,95) > 1,13·In Q („pa”) → BLOCANT; Q nedeclarat peste limita blocului („bloc”) → BLOCANT; v1.6: Q existent nedeclarat („q_pres”) / P aprobată nedeclarată („pa_pres”) → AV, mesajele pe Q presupus îl numesc (§C.8 pct. 2) | AV/BLOCANT | „Pc din bilanț {x} kW > puterea aprobată (ATR) {y} kW” / „Ib general {x} A > In Q branșament {y} A …” | ATR pentru mărirea puterii, trifazat, sarcini simultane mai mici |
| V47 | Dezechilibru între faze (v1.4) | §C.8 pct. 5: (Imax − Imed)/Imed > 30 % | AVERTISMENT | „dezechilibru {x} % > 30 %” | mută circuite pe altă fază |
| V49 | DDR obligatoriu refuzat (v1.4, v1.5) | §C.8 pct. 4: orice circuit al locuinței (în afară de prize → V29) cu `DDR: false` sau cu DDR impus > 30 mA („idn”) → BLOCANT; tip AC („tip_ac”) / VE cu tip ≠ B impus („ve_tip”) → AV | BLOCANT / AV | „circuitul „{rec}” al unei locuințe trebuie protejat de DDR 30 mA” | DDR 30 mA |
| V40 | Amonte < aval | Ip_am < Ip_av; v1.5 „loc”: MCB / RCBO de circuit sau Q general MCB cu In > In Q branșament (§C.8 pct. 3a) | BLOCANT | „{obiect}: amonte {a} A < aval {b} A” | |
| V41 | Amonte = aval / raport < 1,6 | B.18 | AVERTISMENT (INFO la BMPT) | „{obiect}: raport {r} < 1,6” | |
| V42 | Selectivitate la scurtcircuit | B.18 pct. 4 | INFO/AVERTISMENT | „{obiect}: selectivitate parțială până la {Is} kA (Ik3max {Ik} kA) — confirmați cu tabelele producătorului” | |
| V45 | Material/izolație schimbate automat | fallback B.8 | AVERTISMENT | „{obiect}: {mat} {iz} nu ajunge la 4×240 mm² → s-a trecut pe {mat2} {iz2}” | |
| V48 | Al → Cu | regula B.8 | INFO | „{obiect}: secțiune mică — Al înlocuit cu Cu {S} mm²” | |
| V50 | BMPT inexistent / insuficient | tip ∉ ST 4-JT sau Ib > 250 A; v1.2: `bmpt_fortat` cu Imax < Ib | BLOCANT | „{tip} nu există în ST 4-JT Rev. 3/2024” / „Ib = {x} A > 250 A: nu există BMPT…” / „{tip} impus are Imax {y} A < Ib” | BMPT corect / schema PT |
| V51 | Semidirectă sub 100 A | cerere BMPTi cu Ib ≤ 100 | AVERTISMENT | „măsură semidirectă cerută la Ib = {x} A … → {blocul ales}” (v1.2) | |
| V52 | Q > SF | In_Q > In_SF | BLOCANT | „In Q > In SF” | |
| V53 | Monofazat > 40 A | Ib (sau Iac,max) > 40 A | BLOCANT | „Ib = {x} A > 40 A: nu există BMPM; branșament trifazat” | trifazat |
| V54 | Borne BMPTi | S_C2 > 150 mm² | AVERTISMENT | „C2 {S} mm² > 150 mm² (bornele BMPTi-250)” | paralel |
| V55 | TC | Ib > Ip_TC (BLOCANT); Ip_TC ∉ 125…250 la BMPTi (BLOCANT); S_sec > Sn (AV) | BLOCANT/AV | „TC: …” | |
| V56 | Contor direct > 100 A | | BLOCANT | „contor direct pe Ib = {x} A > 100 A” | BMPTi |
| V57 | Circuitul de tensiune al contorului în serie cu TC | topologie model (P0-8) | BLOCANT | „F (tensiune contor) legat în circuitul secundar al TC” | derivație din bare |
| V60 | Q trafo sub In_T | In_Q < In_T sau Ir < In_T (BLOCANT); Ir_QG > In_T la CEF (AV) | BLOCANT/AV | „Q JT {x} A < In_T {y} A — întreruptorul general sub puterea trafo” | |
| V61 | Siguranțe MT > 630 kVA (Î10) | | BLOCANT | „celulă trafo cu siguranțe MT la {Sn} kVA > 630 kVA” | întreruptor + releu 50/51 |
| V62 | Bilanț > Sn | Sc > Sn | AVERTISMENT | „Sc = {x} kVA > Sn = {y} kVA” | trafo mai mare / ks justificat |
| V63 | PT incomplet | lipsă neutru la pământ / TC releu / descărcătoare / servicii proprii | BLOCANT (INFO când e generat automat) | „PT: lipsește {element}” | |
| V64 | Iac,max din fișă neplauzibil (v1.2) | Iac,max < Pn/U (C.3 pct. 11) | BLOCANT | „{obiect}: Iac,max = {x} A < Pn/U = {y} A …” | fișa invertorului |
| V65 | QG < ΣIac | Ip_QG < ΣIac (cu PCS) | BLOCANT | „QG {x} A < Σ Iac invertoare + PCS = {y} A” | |
| V66 | Racord JT al CEF | C.3 pct. 4; v1.2: racord prin BMPT cu Ip QG > 250 A (C.3 pct. 11) | BLOCANT/AV | „S = {x} kVA > 400 kVA la 0,4 kV fără PT propriu și fără ATR pentru racord JT” / „racord JT prin BMPT: Ip QG {x} A > In Q BMPTi-250” | PT propriu / racord din PT OD |
| V67 | Trafo CEF sub S | Sn < S_total | BLOCANT | „Sn trafo {x} kVA < S invertoare+PCS {y} kVA” | |
| V68 | Voc(Tmin) | > Umax; v1.2: β(Voc) ≥ 0 sau < −1 %/K | BLOCANT | „Voc la Tmin {x} V > Umax invertor {y} V” / „β(Voc) = {x} %/K neplauzibil” | mai puține module pe string / fișa modulului |
| V69 | gPV | interval vid sau lipsă la ≥ 3 stringuri | BLOCANT | „nu există gPV în [{a}; {b}] A” | |
| V70 | Categorie RfG / prosumator | C.3 pct. 6; C.4 (prosumator > 400 kW) | INFO/AV/BLOCANT | „modul generator categoria {X}” | |
| V71 | Invertor mono > 3,68 kW | | AVERTISMENT | „invertor monofazat {P} kW > 3,68 kW — verificați cerința OD” | trifazat |
| V72 | Injecție > Q branșament | Iac,max > Ip_Q | AVERTISMENT | „Iac,max {x} A > Q branșament {y} A” | limitare injecție |
| V73 | Tip DDR invertor | tip nedeclarat / AC | AVERTISMENT | „DDR tip A (sau B) pentru invertor” | |
| V74 | SPD c.c. | Ucpv < Voc(Tmin) | BLOCANT | „SPD c.c. Ucpv {x} V < Voc,max {y} V” | |
| V75 | PI citat greșit | CEF ne-prosumator cu notă „Ord. 228” | AVERTISMENT | „PI: pentru CEF ne-prosumator se aplică Ord. ANRE 208/2018 + ATR” | |
| V80 | Listă ≠ desen | text listă ≠ șablon E din parametri | BLOCANT | „{ref}: lista „…” ≠ parametri „…”” | regenerare listă |
| V81 | Notă ≠ model | valoare numerică din notă ≠ model | BLOCANT | „nota {k}: „…” ≠ model „…”” | regenerare note |
| V82 | Tablou/sursă desenat(ă) în carcasa altui tablou | topologie | BLOCANT | „{TD} desenat în interiorul {TG}” | |
| V83 | Legătură de comandă inversată | sursa comenzii ≠ releu/PI/DPST | BLOCANT | „săgeata {X}→{Y} inversată” | |
| V85 | GE: deconectare în regim generator | Ik1_GE < Ia | AVERTISMENT | „în regim GE Ik ≈ {x} A < Ia(Q_G) {y} A …” | DDR, 51V |
| V86 | GE subdimensionat | Ib > In_G; v1.2: Ib > Ir Q_G (Ir ≤ In_G) | BLOCANT | „sarcina {x} A > In_G {y} A — GE minim {Sn} kVA” | GE din `GE_SN_KVA` ≥ P/cosφ |
| V87 | ATS neconform | < 4 poli în TN-S / fără interblocaj | BLOCANT | „ATS …” | |
| V89 | Compatibilitate modul–invertor (fișe) | v1.8: MPPT, Isc/Idc pe MPPT, kWp din stringuri | AVERTISMENT | „string {n} module: Vmpp la 70 °C ≈ {x} V < MPPT min {y} V” … | alt număr de module / stringuri |
| V88 | CEF fără protecții c.c. | lipsă separator/SPD c.c. pe intrare | BLOCANT | „INV-{i}: lipsește {element} c.c.” | |
| V90 | Ipoteze de calcul | totdeauna | INFO | lista din G.2 | |
| V91 | Putere declarată ≠ Σ invertoare | v1.9: `Pn_total_kW` ≠ Σ n·Pn (> 1 %); `Pn_inv_kW` ≠ Σ `invertoare[]`; grup trifazat la CEF monofazat | AVERTISMENT | „Σ Pn invertoare = {x} kW ≠ puterea totală declarată {y} kW” | corectați lista sau totalul |
| V92 | Limitarea injecției | v1.9: `limitare_injectie_kW` declarat | INFO / AVERTISMENT (P ≥ Σ Pn: fără efect) | „injecția limitată la {P} kW: analizor + EMS cu comandă către {n} invertoare” | reglaje EMS conform ATR |

**Acoperirea cerințelor din temă:**

| Cerință | Coduri |
|---|---|
| toate P0/P1 din raport | tabelul H.1 |
| calibru inexistent | V05 |
| Ib > In max | V06 |
| amonte ≤ aval | V40, V41 |
| BMPT inexistent | V50 |
| Q trafo sub Sn | V60 |
| QG CEF sub suma invertoarelor | V65 |
| neutru/PE subdimensionate | V25, V26, V27, V36 |
| deconectare automată neîndeplinită | V30, V31, V32, V34 |
| Icu insuficient | V33 |
| listă ≠ desen | V80, V81 |
| parametri lipsă/absurzi | V07, V08, V09, V10, V13 |
| priza de pământ (v1.3) | V37 (V07/V10/V12 la date absurde) |
| selectivitate DDR în serie (v1.3) | V43 |

---

## E. Lista de echipamente: generată din parametri

### E.1 Principiu (P0-3)
1. Modelul stochează **doar parametri** (`tip`, `poli`, `In_A`, `Ir_A`, `curba`, `Icu_kA`, `IdN_mA`, `primar_A`, …). Textul de pe desen (`spec`) și textul din listă (`lista`) **nu se stochează**. Se generează la fiecare randare cu funcțiile de mai jos.
2. Interpretorul și formularul scriu numai parametri.
3. La import, un model vechi cu texte libere trece prin validare: dacă textul diferă de cel regenerat → V80 BLOCANT, iar textul se înlocuiește.
4. Notele cu valori (G.3) se generează la fel. O notă editată manual care conține numere diferite de model → V81.
5. Aparatele identice (aceleași parametri) se **agregă** în listă și în BOM: „Q4…Q7 — 4 buc.”. U.M.: buc, m (cabluri, cu +5 % rezervă rotunjit la metru), set.

### E.2 Formatare RO
- Separator zecimal **virgulă** („0,95”, „1,29 %”). Fără separator de mii sub 10 000 („2500 A”, „1600 kVA”). De la 10 000 în sus, spațiu fin („12 500 A”).
- Înmulțire „×” (U+00D7), nu „x”. Produs de simboluri „·” (U+00B7). Interval „…”.
- Unitate separată de număr prin spațiu (non-breaking): „250 A”, „35 mm²”, „0,4 kV”, „Ω”, „°C”. Excepție: curbele „C32”, fuzibilele „3 × 250 A gG”.
- Afișare: Ib, Iz' cu 1 zecimală; ΔU cu 2 zecimale; Ik3 în kA cu 1 zecimală pe desen și 2 în memoriu; Ik1 în A, întreg; Ir ca multiplu cu 2 zecimale („0,95·In”).
- Funcție unică `fmt_ro(x, zecimale)`, cu zerourile finale eliminate: 250,0 → „250”.

### E.3 Șabloane (denumire | caracteristici | simbol pe desen)
**Reguli de compunere (arbitraj D-03):**
1. Textul „listă” pe o singură coloană (câmpul `text_lista_regenerat`, nota din planșă, verificarea V80) = `denumire + ", " + caracteristici`. În BOM Excel, cele două merg pe coloane separate.
2. Un fragment al cărui parametru lipsește din model se **omite** cu tot cu eticheta lui („, Isd = …” dispare dacă Isd nu e în model). Nu se inventează valori.
3. Pentru TC, sufixul „— {n} buc.” face parte din caracteristici.
4. Exemple de referință (cazul X01):
   - MCCB 4P In 500 A, Ir 475 A, Icu 36 kA, fără Isd/tsd/Ii → `Întreruptor automat MCCB 4P, In 500 A, declanșator electronic LSI, Ir = 0,95·In = 475 A, Icu 36 kA`;
   - TC 600/5 A, cl. 0,5S, 5 VA → `Transformator de curent JT 600/5 A, cl. 0,5S, 5 VA, Fs 5, 0,72 kV, capac sigilabil, SR EN 61869-2 — 3 buc.`


| Tip | Denumire (col. „Denumire”) | Caracteristici | Text pe desen |
|---|---|---|---|
| MCB | `Întreruptor automat modular {poli}P, curba {curba}, In {In} A` | `Icn {Icn} kA, {U} V c.a., SR EN 60898-1` | `{poli}P · {curba}{In} · {Icn} kA` |
| MCCB TM | `Întreruptor automat compact MCCB {poli}P, In {In} A, declanșator termomagnetic` | `Ir = {Ir/In}·In = {Ir} A, Im = 10·In = {Im} A, Icu {Icu} kA, 400 V c.a., SR EN 60947-2` (+ `, bobină de declanșare BD` dacă `bd`) | `{poli}P · {In} A · Ir {Ir} A · {Icu} kA` |
| MCCB EL / ACB | `Întreruptor automat {MCCB\|ACB} {poli}P, In {In} A, declanșator electronic LSI` | `Ir = {k}·In = {Ir} A, Isd = {m}·Ir = {Isd} A, tsd {tsd} s, Ii = {Ii} A, Icu {Icu} kA` | `{poli}P · {In} A · Ir {Ir} A · Isd {Isd} A` |
| Separator cu siguranțe (plecare) | `Separator {poli}P cu siguranțe fuzibile NH {gabarit}, {In} A gG` | `400 V c.a., {Icu = 120} kA, separare vizibilă, SR EN 60947-3 / SR EN 60269-2` (v1.2) | `3 × {In} A gG` |
| SF branșament | `Separator tripolar cu siguranțe fuzibile {gabarit}, soclu {soclu} A, fuzibil {In} A gG` | `400 V, 50 kA, sigilabil (ST 4-JT)` | `3 × {In} A gG` |
| RCCB (In ≤ 125 A) | `Întreruptor diferențial {poli}P, In {In} A, IΔn {IdN} mA, tip {tip}{, S dacă selectiv}` | `Icn ≥ 6 kA, fără protecție la supracurenți` | `{poli}P · {In} A · IΔn {IdN} mA {tip}{ S}` (v1.2: S și pe desen) (v1.6: la IΔn ≤ 30 mA „IΔn 30 mA tip A”) |
| Bloc diferențial (v1.2: RCCB cu In > 125 A sau `aparat = "bloc_diferential"`) | `Bloc diferențial asociat întreruptorului {asociat=Q} (MCCB {poli}P, In {In} A), IΔn {IdN} mA, tip {tip}{, S}` | `IΔn și Δt reglabile, declanșare prin bobina MCCB, SR EN 60947-2 anexa B` | `Bloc dif. · {In} A · IΔn {IdN} mA {tip}{ S}` |
| RCBO (BMPM) | `Întreruptor automat cu protecție diferențială 1P+N, curba C, In {In} A, IΔn 300 mA, tip AC` | `Icn ≥ 6 kA (ST 3-JT)` | `1P+N · C{In} · 300 mA` (v1.6: tipul ≠ AC se scrie „30 mA tip A”) |
| TC | `Transformator de curent JT {primar}/5 A, cl. {clasa}, {Sn} VA, Fs 5` | `0,72 kV, capac sigilabil, SR EN 61869-2 — {n} buc.` | `3 × {primar}/5 A · cl. {clasa}` |
| Contor | `Contor electronic {tri\|mono}fazat de energie activă și reactivă, {direct\|semidirect}{, bidirecțional}` | `{3 × 230/400 V \| 230 V}, {conexiune directă \| conexiune prin TC}, telecitire, furnizat și montat de OD` (fără curent nominal — Î15) | `kWh · kVArh` |
| DPST | `Dispozitiv de protecție la supratensiuni de frecvență industrială, trifazat` | `Uf = 270 ± 10 V, t = 0,13…0,2 s, comandă BD pe Q` | `DPST · U> 50 Hz` |
| SPD c.a. | `Descărcător SPD tip {T1+T2\|T2}, {poli}P` | `{Iimp 12,5 kA/pol (10/350) \| In 20 kA (8/20)}, Up ≤ 1,5 kV, protecție amonte {In} A gG` (v1.6: cu `prot_tip` ≠ gG → „protecție amonte {prot_tip} {curba}{In} A”, ex. „MCB C25 A”) | `SPD {tip} · {poli}P` |
| SPD c.c. | `Descărcător SPD c.c. tip 2, Ucpv {Ucpv} V` | `In 20 kA (8/20), SR EN 61643-31` | `SPD c.c. · {Ucpv} V` |
| Siguranță gPV | `Siguranță fuzibilă gPV {In} A, 10×38 mm, {U} V c.c.` | `SR EN 60269-6 — {n} buc. (+ și −)` | `gPV {In} A` |
| Cablu | `Cablu {tip} {conductoare} mm² {material}{, în paralel n×}` | `0,6/1 kV, L ≈ {L} m, Iz' = {Iz'} A (metoda {metoda}, k = {k}), ΔU = {dU} %` | `{text cablu} · L ≈ {L} m` |
| Conductor PE | `Conductor de protecție FY 1×{S_PE} mm² Cu, galben-verde` | `pozat lângă cablul {ref}, L ≈ {L} m` | (pe eticheta cablului) |
| Trafo | `Transformator de putere {Sn} kVA, 20 ± 2×2,5 % / 0,4 kV, {grupa}` | `uk {uk} %, Pk ≤ {Pk} W, P0 ≤ {P0} W (Reg. UE 548/2014 Tier 2), ulei` | `{Sn} kVA · 20/0,4 kV · {grupa}` |
| Celulă trafo (siguranțe) | `Celulă MT de transformator cu separator de sarcină și siguranțe MT {In} A` | `24 kV, SR EN 62271-105, CLP` | `24 kV · SF {In} A` |
| Celulă trafo (întreruptor) | `Celulă MT de transformator cu întreruptor în vid 24 kV, 630 A, 16 kA` | `releu 50/51, 50N/51N, TC MT {raport}` | `24 kV · Q · F>` |
| Invertor | `Invertor trifazat {Pn} kW c.a., 3 × 400 V, 50 Hz{ — producător model}` | `Iac,max {Iac} A{, Umax c.c. …, MPPT …, n MPPT, Idc,max …}, PI integrată, certificat conform {Ord. 228 \| RfG}` | `{Pn} kW · 3 × 400 V` + rândul cu modelul |
| Câmp PV (v1.8) | `Câmp fotovoltaic {kWp} kWp{, N module producător model Pmax Wp}` | `{n} module/string × {s} stringuri/MPPT × {m} MPPT, Voc …, Isc …, Vmpp …, Impp …, β(Voc) …` | `{kWp} kWp` + modelul |
| PCS | `Convertor bidirecțional BESS {Pn} kW` | `Iac,max {Iac} A, grid-forming/following` | `{Pn} kW` |
| Baterie | `Baterie LiFePO₄ {kWh} kWh cu BMS` | — | `{kWh} kWh` |
| ATS | `Comutator automat de sursă (ATS) 4P, {In} A, AC-33B` | `interblocaj mecanic + electric, SR EN 60947-6-1` | `ATS 4P · {In} A` |
| GE | `Grup electrogen {Sn} kVA, 3 × 400/230 V` | `x"d {xd} %, In {In_G} A` | `GE {Sn} kVA` |
| Bare tablou | `Sistem de bare Cu {3P+N+PE}, {In_bara} A` | `Icw ≥ {Ik3} kA/1 s` | (eticheta barei) |

**Test automat obligatoriu:** pentru fiecare model din `cazuri_golden.json` și pentru fiecare preset, `lista == sablon(parametri)` și `spec_desen == sablon_desen(parametri)`. Orice nepotrivire pică build-ul.

---

## F. Interpretorul de text liber (chat)

### F.1 Contract
Intrare: text în română (cu sau fără diacritice). Ieșire: `{actiune, intrare_fizica, presupus[], intrebari[], refuz_motiv, intelegere}`, unde:
- `intrare_fizica` are aceeași formă ca `intrare` din `cazuri_golden.json` și trece prin motorul B–C;
- `intelegere` e rezumatul pe care utilizatorul îl vede („Am înțeles: …”).

Interpretorul (local sau LLM) nu dimensionează nimic. Dimensionează motorul. Rezultatul unui LLM trece prin **același** validator și nu îl poate ocoli.

### F.2 Normalizare
1. Se păstrează textul original (pentru nume, beneficiar, localitate).
2. Copia de lucru: litere mici; ș/ş → s, ț/ţ → t, ă/â → a, î → i; „×”, „x” sau „*” între numere → `×`; „~”, „cca”, „circa”, „aprox.”, „aproximativ”, „cam” → marcaj `≈` (valoarea se păstrează; se declară „aproximativ”).
3. Numere:
   - virgula e separator zecimal („7,5”);
   - punctul urmat de exact 3 cifre e separator de mii („2.500 kWp” = 2500), altfel e zecimal („2.5 MWp”);
   - spațiul ca separator de mii se acceptă **doar în afara listelor** („1 000 kWp”). În liste, „hală 1 100 A” = nume „Hală 1” + 100 A.
4. Tokenii cu majuscule se verifică **în textul original**: „PT” = post de transformare; „pt” = „pentru”. „Cu” majuscul = cupru; „cu” = prepoziție. „Al” = aluminiu; „al” e ignorat.
   **Excepție (arbitraj F26):** „al” și „cu” scrise cu literă mică înseamnă material numai ca token izolat la sfârșitul unui segment (urmat de „,”, „.”, „;” sau de sfârșitul textului), imediat după o lungime („25m al”) sau după cuvântul „cablu” („cablu cu,”). „al doilea”, „cu 2 plecări”, „cu invertor” rămân ignorate.

5. **(r5)** Autocorectura „X?? nu, Y” („1.000 m cablu?? nu, 100 m”): clauza dinaintea lui „? nu,” se ignoră (declarat). Prefixele „In=”, „L=” din fața valorilor se elimină („TD-1 In=100A L=60m”).
6. **(r5)** Cifra unui cod de tablou nu se lipește de valoarea următoare: „td-2 160 A” = TD-2 + 160 A (nu 2160 A); codurile „td-1” se scriu „TD-1”.

### F.3 Unități
| Text | Normalizat |
|---|---|
| W, kW, MW | P [kW] (×0,001 / ×1 / ×1000) |
| Wp, kWp, MWp | P_cc [kWp]. „Wp” < 1000 lângă „modul/panou” = puterea modulului |
| VA, kVA, MVA | S [kVA] |
| kWh, MWh | energie BESS [kWh] |
| A, kA | curent [A] |
| m, metri, ml, km | lungime [m] („0,3 km” = 300 m) |
| mm², mmp, mm2 | secțiune |
| V, kV | tensiune (doar „230 V” → mono, „400 V” → tri, „20 kV” → PT) |
| CP | P [kW] (×0,7355) — r5, declarat |
| W / Wp între 100 și 999 lângă o marcă de modul / „module” / „panouri” | Pmax modul (`modul.Pmax_W`), **nu** putere de invertor (r5) |

### F.4 Gramatica minimă (EBNF simplificat, pe textul normalizat)
```
fraza        := { segment (","|";"|".") }
segment      := tip_schema | putere | lista_plecari | lungime | material | izolatie | pozare
              | retea | beneficiar | adresa | plansa | faza | invertoare | bess | trafo | atr | ...
lista_plecari:= ("plecari"|"plecare"|"circuite") [ "de" | ":" ] item { sep item }
              | NUM "plecari" "de" valoare unitate                 # „4 plecări de 63 A”
sep          := "," | " si " | " și " | "+" | ";"
item         := [nume] [ NUM ("×"|"x") ] valoare [unitate] [lungime] [ "cu sub-plecari" "(" ? lista ")" ? ]
              | nume "(" item {sep item} ")"
nume         := cuvânt { cuvânt | NUM_index } | COD (ex. „TD-1”, „HVAC”)
valoare      := NUM
unitate      := "A" | "kW"
```
**Reguli de liste:**
1. **Unitate comună:** într-o listă, un item fără unitate primește unitatea primului item următor care are unitate („160, 63 și 40 A” → toate în A). Dacă niciun item nu are unitate după el → I03 (întrebare).
2. **Multiplicator:** „N plecări de X A”, „N × X A”, „N x X A”, „N×X kW” → N itemi identici. Numele: „TD-1…TD-N” la plecări din TG/PT, „Circuit 1…N” sau „{Receptor} 1…N” la circuitele finale („5 circuite de 16 A iluminat” → „Iluminat 1…5”). „3×63 A” **nu** înseamnă 189 A.
3. **Cascadă:** „NUME cu sub-plecări LISTA”, „NUME cu circuitele LISTA”, „NUME (LISTA)” sau „NUME: LISTA” în interiorul unei liste → `copii`. Lista copiilor se termină la următorul item de nivel superior. Acesta e recunoscut după cod de tablou (TD-k) sau după separator „;”.
4. **Numele** se păstrează ca în textul original. Dacă e scris integral cu litere mici, prima literă devine majusculă; codurile (TD-1, HVAC) rămân neschimbate. Nu se aplică `.capitalize()` pe tot șirul (P1-14).
5. **Numărul de plecări cerut** („cu 3 plecări: …”) se compară cu numărul obținut. Dacă diferă → refuz I05 („S-au cerut 3 plecări, dar s-au găsit 2”).
6. Lungimea scrisă **imediat după** valoarea unui item aparține itemului („TD-1 250A 120m”).
7. **(r5) Coada unui item:** după valoare pot urma, în orice ordine, lungimea, `cosφ X` (→ `plecari[].cosfi`, nu cosφ-ul tabloului), pornirea („stea-triunghi” → `pornire = stea_triunghi`, „cu convertizor” → `convertizor`, „soft-start”, „directă”), materialul (Al/Cu), izolația (XLPE/PVC) și pozarea („pozat aparent” → C, „în aer pe pat” → E, „în tub” → D1) → `plecari[].cablu`. Atributele de cablu scrise doar după ULTIMUL item se aplică tuturor plecărilor.
8. **(r5) Listă fără cuvântul „plecări”:** începe la prima bucată „nume valoare unitate” care nu e antetul tabloului (TG/tablou…), dacă urmează cel puțin încă un item („tg birouri P+2: TE parter 40A, …”, „tablou … , ventilatoare 10 x 1,1 kW, …”). „+” din „P+2” nu e separator.
9. **(r5) „NUME N circuite de X”** („iluminat 5 circuite de 16 A”) = o plecare cu `n_circuite = N` (motorul o desface în „NUME 1…N”); „N circuite” precedat de un nume nu deschide lista.
10. **(r5) Cascada „NUME [valoare] [L] (LISTA); …”**: părintele poate avea calibru și lungime; „;” din interiorul parantezelor NU închide cascada, „)” o închide; „TD-1 cu sub-plecări (…)” → numele „TD-1”.
11. **(r5)** „30 kVA” pe o plecare = S → `P_kW = S·0,9` (declarat); „15 CP” → 11,03 kW; calibrul nestandard („60 A”, „cca 150 A” la Q1) → treapta superioară + întrebare I07.
12. **(r5) Cablu impus:** „3x150+70 Cu”, „3x185+95 Al”, „3x(4x150)Al” lângă „cablu/alimentare/coloană” sau urmat de material = `cablu{S_fortat, N_fortat, n_fortat, material}` (tablou: alimentarea; CEF: `cablu_C0`), nu plecări.

### F.5 Recunoașterea elementelor
| Element | Tipare (pe textul normalizat; * = în original, case-sensitive) | Rezultat |
|---|---|---|
| tip: branșament | `bmpm` → mono; `bmpt`, `bmpt[di]`, `bransament`, `firida` | `bransament` |
| tip: prosumator | `prosumator` (are prioritate față de CEF) | `prosumator` |
| tip: CEF | `cef`, `fotovoltaic`, `kwp`, `mwp`, `invertor(ul\|i\|ii\|ul)?`, `invertoare`, `bess`, `stocare`, `panouri` | `cef` |
| tip: PT | *`PT`*, `post (de )?(transformare\|trafo)`, `transformator`, `20/0,4 kv`, `kva`/`mva` fără „grup” | `pt` |
| tip: GE | `grup electrogen`, `generator`, *`GE`*, `ats`, `aar` | `ge_ats` |
| tip: tablou | `tablou`, *`TG`*, *`TD`*, `plecari` | `tablou` |
| ordinea de decizie (r5) | prosumator > CEF/BESS (cu casă → prosumator; cu GE → GE + I14; cu TG și plecări → CEF + `racord = tg_existent` + I14) > GE (cu PT/TG → GE + I14) > locuință > BMPM/BMPT/branșament > PT > tablou; dacă nimic → I01. „BMPT”, „din PT”, „până la PT”, „faza PT”, „PT … existent” sunt **atribute** (racord / sursă), nu tipul | |
| locuință (r5) | `casă`, `locuință`, `apartament`, `garsonieră`, `vilă`, `duplex`; `P+n` / `parter` / `mansardă` doar fără TG/TE/TD/plecări/hală/birouri; casa numită ÎNAINTEA branșamentului sau cu circuite → locuință, altfel branșament; „22 kVA” la casă = S branșament (nu PT, nu P aprobată) | `locuinta` |
| invertoare (r5) | pe clauze (separatori „,” „;” „:” „+” „și”): fiecare clauză cu „invertor/invertoare/inv”, cu o marcă/model de invertor sau „N × P kW” = un **grup** {n, Pn_kW, producator, model}. n: „N invertoare”, „N x model”, „N inv x P”, „invertor k =” → 1. Pn: kW/kVA de după cuvântul „invertor” > puterea din codul modelului (SUN2000-**100**KTL, SG**110**CX, SH**25**T, MAX **50**KTL3, S5-GC**50**K — declarat) > kW din fața lui. „N invertoare [diferite]: A, B” = antet (Σ n verificat, altfel I05). Un kW nu se împarte la n fără întrebare. Puterea totală scrisă („total 80 kW”, „prosumator 100 kW”) ≠ Σ grupuri → I08. kWp/ΣPn ∉ [0,8; 1,6] → întrebare (nu la hibrid) | `invertoare[]` |
| mărci / modele (r5) | invertoare: Huawei SUN2000, Sungrow SG/SH, SMA STP / Sunny Tripower, Fronius Tauro/Symo, Growatt MAX/MID, Solis, GoodWe, SolarEdge…; module: LONGi Hi-MO, JA Solar, Trina Vertex, Jinko Tiger Neo…; BESS: LUNA2000, PowerStack, BYD Battery-Box HVS/HVM. Codul modelului se maschează (cifrele lui nu sunt valori) | `producator`, `model` în `invertoare[]`, `modul`, `bess` |
| BESS (r5) | `(bess\|stocare\|baterie\|acumulator)` + până la ~6 cuvinte (marcă, model) + `X kWh [/ Y kW]` sau `Y kW / X kWh`, până la primul separator. Cuvântul fără valori → întrebare I02. BESS fără invertoare PV → CEF doar cu PCS + BESS (declarat) | kWh, P_PCS; P lipsă → P = kWh/2 (0,5C), declarat. Prosumator hibrid → `baterie_kWh` (+ `baterie`), altfel `bess` |
| limitare injecție (r5) | `limitare injecție (la) X kW`, `injecție limitată (la) X kW`, `injecție zero`, `fără injecție`, `limitată la 0` | `limitare_injectie_kW` (0 = injecție zero) |
| stringuri / gPV (r5) | `N module pe string`, `N stringuri`, `N pe MPPT`, `gPV X A (pe string)` | `string{n_module, n_stringuri_paralel, gpv}`, `gpv_In_A` |
| racord CEF/prosumator (r5) | `TG/TGD/tablou existent`, `în/la/până la TG` → `tg_existent`; `BMPT`, `branșament` → `bmpt`; `din/până la/în PT` (CEF) → `pt`. `Q X A` / `BMPT existent X A` / „TG hală X A” → `racord_In_Q_A` (prosumator / BMPT: `In_Q_bransament_A`); `Ik … X kA` → `Ik3_TG_kA`; „PT propriu X kVA existent” → `pt_Sn_kVA` + `pt_existent` (sursa TG-ului, fără trafo nou). Cu `tg_existent` și S > 400 kVA **nu** se adaugă PT (I11 doar întreabă) | |
| prosumator ATR (r5) | `P aprobată/Pa/Paprobat/aprobat X kW`, `X kW aprobat`, `branșament … X kW` → `P_aprobata_kW`; `P evacuată X kW` → `P_evacuata_kW`; `coloana X m` / `X m până la BMPT` → `L_coloana_m`; alt cablu → `L_inv_m`; „casă … X kW + fotovoltaic Y kW” → P aprobată X (declarat), invertor Y | |
| mono/tri (r5) | `monofazat/ic`, `mono`, `1f`, `230 v` / `trifazat/ic`, `tri`, `3f`, `400 v`, `bmpt`, `3x400`. „monofazată/trifazată” scris lângă un receptor de locuință ține de receptor (`faza` L1–L3 / 3F), nu de rețea. Nedeclarată → se presupune trifazat **doar** dacă sarcina nu încape fizic în monofazat (> 40 A), declarat; altfel întrebare (branșament, prosumator, locuință, tablou, CEF). „monofazat” + receptor/listă trifazată sau CEF > 40 A → I08 | `retea` (și la tablou / CEF) |
| schema de legare la pământ (r5) | `TN-C-S`, `TN-S`, `TN-C`, *`TT`*, `schemă/rețea TT`, `priză de pământ proprie`; `RA/Rp/priză … X Ω` — la **toate** tipurile | `schema_pamant`, `RA_ohm`; nedeclarată → presupunere declarată |
| material | `cupru`, *`Cu`*, `cyaby`, `cyy`, `n2xy`, `c2xaby` → Cu; `aluminiu`, *`Al`*, `acyaby`, `ac2xaby`, `na2xy` → Al | |
| izolație | `xlpe`, `2x`, `pe reticulat` → XLPE; `pvc` → PVC | |
| pozare | `direct in pamant` → D2; `pamant`, `ingropat`, `sant`, `tub`, `teava`, `canalizatie` → D1; `pat de cabluri`, `jgheab perforat`, `scara de cabluri`, `in aer` → E; `aparent`, `pe perete`, `pe zid`, `plafon` → C | |
| grupare | `acelasi traseu`, `acelasi sant`, `acelasi pat`, `impreuna`, `pat comun`; **și** `pat de cabluri` / `jgheab` / `scara de cabluri` când tabloul are > 1 plecare (arbitraj F11: plecările pleacă pe același pat) | n_alte = n_plecări − 1, aranjament „pat_perforat” (sau „scara”) |
| sursa tabloului (r5) | `din PT (propriu) [X kVA]`, `din PT ATR` → `pt_propriu` (+ `pt_Sn_kVA`; fără Sn → I07); `din TG/TGD (existent)` → `tg_existent`; `din rețea`, `prin BMPT` → `bmpt`; `Ik … X kA` → `Ik3_sursa_kA`. Nedeclarată → presupunere declarată (DDR-ul din BMPT nu se ia în calcul) | `origine` |
| PT (r5) | `uscat`/`rășină` / `ulei` → `trafo_izolatie`; `celulă de linie intrare-ieșire` → `celule_mt` [linie_intrare, linie_iesire], `N celule de linie`; `măsură pe MT/JT` → `masura` | |
| GE (r5) | kVA-ul aparține cuvântului cel mai apropiat dinaintea lui (PT/trafo vs GE/grup); sarcina vitală = Σ consumatorilor listați („2x30 kW”, „2 pompe x 15 kW” × n); `GE-ATS X m` → `L_GE_ATS_m`; `rețea X A` → `In_Q_retea_A`; sursa ramurii de rețea `sursa_retea` (pt/tgd/bmpt; In GE > 250 A fără sursă → pt + întrebare) | |
| racord JT CEF | `racord jt (conform\|cf\.?) atr` | `atr_jt = true` |
| semidirect | `bmpti`, `semidirect`, `indirect`, `transformatoare de curent`, *`TC`* | `masura_ceruta = semidirecta` |
| beneficiar | `beneficiar(ul)?[: ]+X`, `client(ul)?[: ]+X`, `pentru\|pt (S\.?C\.? )?X (SRL\|SA\|PFA\|II\|IF)` | X din textul original, până la virgulă / „în” / „din” / „jud” |
| adresă | `(in\|din\|la\|loc\.?\|localitatea\|com\.?\|comuna\|sat\|oras\|mun\.?) X[, ]+(jud\.?\|judetul) Y`, sau `X jud Y` după o virgulă | localitate X și județ Y din textul original; fără diacritice adăugate |
| planșă | `plan[sș]a E\s*-?\s*\d+` | „E02” |
| fază | `faza (SF\|PT\|DTAC\|DDE\|PTh\|DE)` | |
| lungime | item → item; `lungime\|cablu\|coloana\|traseu\|pana la` + L → coloana/alimentarea; L singur la final → alimentarea (declarat); la PT, L general → toate plecările (declarat) | |
| sol umed/uscat | nu se convertește (ρ rămâne 2,5); se declară „introduceți rezistivitatea numeric” | |

### F.6 Valori implicite declarate
Pentru fiecare câmp din B.0 folosit implicit, răspunsul conține o linie „Am presupus: …”.
- Interpretorul **poate** anunța estimări derivate cu aceleași constante din `norme.py` (S = 1,1·ΣPn, categoria RfG, tipul de aparat după B.3, PT adăugat), marcate ca presupuneri (arbitraj F13/F15/F16/F35). Valorile autoritare sunt cele calculate de motor; la nepotrivire contează motorul.
- Rezultatele de dimensionare (secțiuni mărite, calibre alese) **nu** se scriu ca presupuneri. Ele apar în verificări sau în rezumatul rezultatului (arbitraj F05).
- **Câmpurile de ieșire** (`intrare_fizica`) folosesc contractul B.1.1:
  - „N A” la branșament → `Ib_A`; „N kVA” la branșament → `S_kVA` (nu un P echivalent);
  - „TD … : circuite …” → `circuite_finale = true`;
  - „din PT propriu” → `origine = "pt_propriu"` (+ `pt_Sn_kVA` dacă e dată).

Exemplu pentru F01:
> Am înțeles: branșament trifazat, P = 15 kW, coloana C2 20 m, beneficiar SC Test SRL, Ciumeghiu, jud. Bihor.
> Am presupus: cosφ 0,9; coloană Al PVC în tub în pământ (D1), cu trecere pe Cu sub 16 mm²; TN-C-S; Ik3max OD 25 kA și Zbuclă OD 0,30 Ω (valori implicite — introduceți datele din ATR).

### F.7 Când refuză sau întreabă (coduri de interpretor I01…I13)
**Regula R1 (arbitraj F07/F29):** `actiune` = `refuza` dacă nu se generează schema; `genereaza_cu_intrebare` dacă se generează **și** există cel puțin o întrebare (indiferent de cauză: I07, I11, I13, V51 …); `genereaza` doar dacă nu există nicio întrebare.

**Regula R2 (arbitraj F29/B18):** un tip BMPT/BMPM impus din text care **nu există** în ST 4-JT/ST 3-JT (I13) **nu** se transmite motorului. Interpretorul pune doar `extras.bmpt_cerut`, motorul alege blocul din Ib, iar răspunsul întreabă. Un tip existent se transmite în `bmpt_fortat`. Câmpul `bmpt_fortat` cu tip inexistent ajunge la motor doar din model sau formular și dă V50 BLOCANT (cazul B18).

| Cod | Situație | Acțiune |
|---|---|---|
| I01 | tipul schemei nu se poate determina | refuz + întrebare |
| I02 | nicio putere și niciun curent (ex. „tablou cu 3 plecări”) | refuz + întrebare |
| I03 | listă de numere fără unitate | refuz + întrebare |
| I04 | unitate necunoscută / incompatibilă (ex. „kWh” la tablou) | refuz |
| I05 | numărul de plecări cerut ≠ numărul găsit | refuz + întrebare |
| I06 | valori absurde (P ≤ 0, L ≤ 0, cosφ ∉ (0;1]) | refuz, cu codul V corespunzător |
| I07 | Sn trafo nestandard | generează cu Sn standard imediat superior + întrebare |
| I08 | contradicție (ex. „monofazat 3×63 A”, „BMPTd 200 A”) | refuz + întrebare |
| I09 | branșament mono > 40 A | refuz, propune trifazat |
| I10 | branșament > 250 A | refuz, propune PT |
| I11 | CEF S > 400 kVA fără PT/ATR | generează cu PT propriu adăugat + întrebare |
| I12 | CEF/PT S > 2500 kVA | refuz (în afara domeniului) |
| I13 | tip BMPT/BMPM impus inexistent (ex. „BMPTd-63”) | generează cu tipul din ST + întrebare (R2) |
| I14 (r5) | frază cu mai multe instalații (PT + TG + GE, TG + CEF, PT + GE …) | generează schema principală (GE + ATS, respectiv CEF racordat în TG) + întrebare; celelalte se generează separat — niciodată alegere tăcută |
| I15 (r6) | informație din text neconsumată (plasa de siguranță, §F.9) | generează + întrebare + „Nu am înțeles: …” |

**(r5)** Alte întrebări: I07 pentru Q1 / plecare cu calibru nestandard, PT declarat cu Sn < 1,1·ΣPn (înainte de V67) și PT-sursă fără Sn; I02 pentru rețea nedeclarată care încape în monofazat, kW total împărțit la n invertoare, BESS fără valori; I08 pentru Σ invertoare ≠ total scris și „monofazat” la CEF > 40 A. Refuz I02 la PT cu „N plecări” fără valori (ca la tablou).

### F.9 (r6) Plasa de siguranță și contradicțiile
**Regula R3:** nimic din text nu se pierde în tăcere. După interpretare, fiecare **număr cu unitate** (kW, kVA, kvar, A, mA, mm², m, kV, V, Ω, kWh, kWp, W, CP), fiecare **cuvânt-cheie de domeniu** (TT, TN-*, IT, „în paralel cu rețeaua” / sincronizare, compensare / kvar, MT / „X/0,4 kV”, uscat, BMPT/BMPM, „PT nou / existent”, ATS/AAR, hibrid, cuplaj c.c./c.a.) și fiecare **nume de receptor / tablou** (pompă, compresor, strung, polizor, saună, boiler, TD-x, „tablou secundar” …) trebuie să fie „consumat”: în intervalele interpretate (`Ctx.consumat` / `Ctx.citit`) sau regăsit ca valoare la o cheie de aceeași mărime din `intrare_fizica` (un „N×” în față cere intervalul, nu valoarea). Restul = `neconsumat[]` (fragmentele de clauză) → întrebarea **I15** („Nu am folosit în schemă: …”) și linia „Nu am înțeles: …” în `intelegere`; acțiunea nu poate rămâne `genereaza`. Itemii de listă fără putere / calibru („iluminat grajd 3 circuite”) nu se desenează și se întreabă (I02).

**Contradicții → întrebare (I08), niciodată alegere tăcută:** două scheme de pământ incompatibile (TT cu TN-*), mono și tri în afara listei („tablou monofazat 3x400V”, „230V … 3P”), tablou monofazat cu plecare trifazată, „X sau Y” cu aceeași unitate („7 kW sau 10 kW”), două surse ale tabloului („din PT propriu și din BMPT”), două racorduri („în TG existent și prin BMPT nou”), Σ invertoare ≠ puterea scrisă (și la prosumator), putere scrisă ≠ puterea din codul modelului („SUN2000-100KTL-M2 de 50 kW”). Un „monofazat” scris la o plecare / un receptor ține de acel element (`plecari[].retea`, `circuite[].faza`), nu de tablou. „nu știu dacă e mono sau tri” = rețea nedeclarată (întrebare).

**Clase reparate (r6):** multiplicitate „N x MODEL”, „MODEL xN”, „N bucăți …”, „N MARCĂ MODEL”, „P kW xN”; Pn din catalogul motorului (`catalog_invertoare.cauta`, inclusiv „hibrid”); „PT nou” ≠ existent, „PT existent / al beneficiarului / al OD” = existent (`pt_existent`, `atr_jt` la OD), „până la TGD” ≠ TG existent; „TG … din BMPT” = tablou cu `origine = bmpt` (calibrul BMPT → Q1, declarat); sursa tabloului („alimentare din PT 250 kVA”) se citește înaintea listei și nu devine plecare; TG/TD + magazin / hală / supermarket / birouri ≠ locuință („casa de marcat” ≠ casă); listele „8 circuite: 3 iluminat 10A …”, „N circ”, „B10”, „->”, „TD-uri:”, „a/m”, „3 x TD 63A (TD-1..TD-3)”, cascade „TD-P 63A 20m cu …”, paranteze descriptive; cablul unei plecări („TD-1 63A cablu CYAbY 5x10”) rămâne pe plecare, „2x(NA2XY 4x240)” = 2 în paralel, „4x(1x240)” = monopolare, „3x400V” nu e secțiune; mărirea de putere „X → Y” / „de la X la Y” (X informativ); „tt”, „Q40A”, „trif”, „ap/apt”, „pc 10kw”, „pompă piscină”, „inc pardoseală”, numerele fără unitate după un receptor de locuință (= kW, declarat), „AC 3x2.5kw”, „în curte la 30 m”; atelier / garaj / anexă → `tablouri_secundare`; baterie fără „hibrid” la prosumator → c.c. desenat + întrebare de cuplaj; `bess.cuplaj` din text / catalog („cuplaj c.c.”, „cuplat în c.a.”, „X kWh fiecare”); stringuri `string{n_module, n_stringuri_paralel, n_MPPT, Uoc_V, Isc_A, gpv_In_A}`; V72 și la CEF (Iac > Q BMPT → întrebare).

**Chei emise (r6):** `plecari[].retea`, `plecari[].curba`, `bess.cuplaj`, `string.Uoc_V/Isc_A/n_MPPT/gpv_In_A`, `compensare_kvar`, `compensare_L_m`, `U_MT_kV`, `n_trafo`, `SkQ_MVA`, `masura_ceruta = directa` (PT), `pt_aerian`, `pt_existent: false` explicit la PT nou, `ge_paralel`, `retea = mono` la GE (motorul blochează), `consumatori[]{nume, P_kW, n, pornire, siguranta}`, `tablouri_secundare[]`, `schema_pamant = IT` (motorul: V28). Rezultatul interpretorului are cheia nouă `neconsumat[]`.

### F.10 (r7) Normalizare înainte de regex, legarea valorilor, contradicții numerice
**Normalizarea formatului** (`engine/interp_text.py`, păstrează lungimea textului): rând nou / tab / liniuță-bullet / „1) 2)” / „a) b)” → separator de listă; „a câte”, „câte”, „fiecare de” → eliminate („15 plecări a câte 25 kW”); „N de circuite / plecări / motoare” → „N circuite …”; „3P+N+PE” nu e separator; „din care” = sub-plecările itemului dinainte; lanțul „TG -> TD … -> TE …” = cascadă; greșeli / englezisme uzuale de aceeași lungime („huawey”, „exsitent”, „existing substation”). Virgula între cifre nu separă nici lista, nici clauza plasei („5x2,5”, „13,5 kW și 13,5 kW”). Unități: „W” la plecări (÷1000), „CP”, „1.1kw”.
**Legarea valorii de entitate:** fiecare valoare ține de cuvântul-cheie cel mai apropiat din stânga în aceeași clauză (`_ancora`: Pa / total / invertor / baterie / PV / limitare). La locuință, P aprobată = „Pa / aprobat” sau un kW precedat DOAR de cuvinte despre casă/rețea/branșament („trifazat 16 kW”) — niciodată kW-ul unui receptor („pompa filtrare 1.1kw” → plasa). La prosumator „casa / branșament / Pa X kW” = `P_aprobata_kW` (nu invertor), „putere aprobată de injectare X kW” = `P_evacuata_kW`; o putere rămasă fără cuvânt-cheie > invertoare = P aprobată (presupus, declarat). „N x” urmat de baterie / modul / cablu nu e număr de invertoare; „N invertoare X kW și X kW” = grupuri pe valori. PV fără „CEF/prosumator”: „pv / solar / fotovoltaice / panouri N kW” sau o marcă / un model de invertor sau baterie → prosumator (casă, BMPT, ≤ 100 kW) sau CEF (PT, TG, hală, BESS, MW, > 100 kW); „pv N kW” = 1 invertor (presupus). Bateria după model (LUNA2000-15-S0, BYD HVS 10.2, „4 x Pylontech US5000” = 4 × 4,8 kWh); Sunny Island / Sunny Boy Storage = PCS (`bess.pcs`, cuplaj c.a.). Invertor care POATE fi hibrid, fără baterie declarată → `hibrid: false` (fără baterie-fantomă). Rețeaua din modelul invertorului (…LP3 = tri, MIN …TL-X = mono). Lungimea și cablul scrise după o plecare („pe 120 m”, „cu cablu CYY-F 5x2,5”) rămân pe plecare. „din BMPT 70 kW” = P tablou (nu plecare); „din care”, „->” = cascadă; „2 de 3 kW”, „unul de 15 CP” moștenesc numele; „pompe: 2 x 18,5 kW Y/D …” (etichetă de grup); un singur receptor cu sursă = o plecare.
**Contradicții numerice → I08 (refuz cu întrebare) sau întrebare:** receptor de durată (VE, PdC, saună, încălzire) > P aprobată, orice receptor > 1,5·Pa sau > Q; VE > 7,4 kW / receptor > 9,2 kW pe monofazat; P aprobată monofazată > 9,2 kW (I09, se generează și se întreabă); „X kW Y A” incompatibile; două tensiuni MT; TD > întreruptorul din amonte (`In_Q_amonte_A`); „din BMPT” > 250 A (I10); PT existent < 1,1·ΣPn; limitare > Pn; injecție zero vs `P_evacuata_kW`; TT + „PEN comun”; „fără pământ / doar fază și nul” (PE lipsă); TN-C cu prize; invertor 800 V în TG / BMPT 0,4 kV; Sunny Boy Storage monofazat pe sistem trifazat; c.c. declarat cu Sunny Island; două puncte de racord (TG + PT nou); 690 V (`U_V`, I12); off-grid (I12); pornire directă > 0,15·Sn PT; prosumator Iac > 100 A (semidirectă) / > 250 A (PT). Fără întrebări inutile: „casa X kW” la prosumator, „N × P = total”, modelul cu P din catalog.
**Plasa (extinsă):** TE/TD „la etaj / mansardă / garaj / corp 2”, „tablou secundar”, frigider, mașina de vase/rufe, backup/EPS, generator, PEN, off-grid intră în intrare sau în `neconsumat`. Tablou fără plecări → întrebare (nu „genereaza” tăcut). Tabloul secundar al casei → `tablouri_secundare` cu circuitele lui (sau întrebare dacă nu are circuite); circuitele casnice fără putere dintr-un tablou secundar → calibre uzuale declarate (prize 16 A, iluminat 10 A, AC 16 A), rețeaua NU se deduce din „3x2.5”.
**Chei emise (r7):** `n_trafo` (CEF/BESS, 1–4) + `pt_Sn_kVA` pe trafo; `masura` (CEF); `U_ca_V` / `U_inv_ca_V` / `U_JT_V` = 800; `P_evacuata_kW`; `bess.la` (["INV-2"]); `bess.pcs` {producator, model, P_kW}; `hibrid: false`; `circuite_casa`, `backup.circuite` (prosumator); `ge_rezerva` {Sn_kVA, P_kW?, comutare manual|ATS} (locuință); `comutare: manual` (GE); `siguranta_tablou`, `titlu_tablou`, `consumatori[].rezerva`, `plecari[].rezerva`; `cablu.n_paralel`; `In_Q_amonte_A`; `U_V`; PT: `plecari_pe_sectie`, `plecari[].sectie`, `cupla`; `plecari[].randament`; `tablouri_secundare[].cablu`.

### F.11 (v1.11) Claude = interpretorul principal; regulile locale = verificare încrucișată și rezervă
**Decizie (proiectant, 23.10.2026):** rundele r5–r8 arată că regulile nu țin pasul cu formulările reale (tabele Excel/CSV,
ATR copiat, emailuri, engleză). Când există cheie API, citirea textului o face Claude; regulile locale rulează mereu.

1. **Schema** (`engine/interp_schema.py`, inventar generat în `engine/interp_schema_inventar.py` cu
   `python3 -m engine.interp_schema --genereaza`): cheile `intrare_fizica` ale tuturor tipurilor (locuinta, bransament,
   tablou, pt, ge_ats, cef/bess, prosumator) din (a) intrările golden, (b) ieșirile interpretorului local pe tot corpusul
   de fraze, (c) cheile citite de motor (`inp.get`, `pl.get` în `calc/scheme.py`, `calc/locuinta.py`, `constructor.py`),
   (d) cheile normalizării interpretorului, (e) căile imbricate citite de motor și nevăzute în corpus (`CAI_MOTOR`:
   `bess.n_pcs`, `bess.pcs`, `bess.n_module`, `bess.kWh_modul`, `invertoare[].faza/sectie`, `tablouri_secundare[].cablu`,
   `Ik3_bara_kA`). Tipurile și domeniile vin din `scheme.CAMPURI_NUMERICE` / `ENUMERARI` și mulțimile interpretorului;
   plecarea (cu `copii` recursiv) e o definiție comună. Aceeași schemă e: `input_schema` a uneltei `intrare_fizica`,
   lista de chei pe tip din promptul de sistem, validarea de formă (`valideaza_forma` → `interp_schema.valideaza`:
   chei, tipuri, enumerări; domeniile > 0 / ≤ 1 rămân la F.7 – I06) și curățarea (`normalizeaza_intrare`).
2. **Apelul** (`interpretor.cerere_llm`, același corp pe server și în browser): `claude-opus-5-5`, antet beta
   `server-side-fallback-2026-07-01`, `fallbacks: "default"`, `output_config.effort: "medium"`, unealta `intrare_fizica`
   (`tool_choice: auto`, promptul cere un singur apel). Ieșirea: `{intrare_fizica, cartus?, intrebari[], neinteles[]}` —
   modelul pune ambiguitățile / contradicțiile în `intrebari` și fragmentele nefolosite în `neinteles`, în loc să ghicească.
   Promptul (`_REGULI_LLM` + 8 exemple din cazurile grele r5–r7): legarea valorii de entitate, P aprobată / evacuată din
   ATR (evacuare < Σ invertoare → `limitare_injectie_kW`), „N x MODEL” (nu după secțiune / baterie), cantitatea din
   tabele, kW total vs pe invertor (ambiguu → variantă + întrebare), Pn din catalog când nu e scris, rețeaua nu se
   presupune, pragul OD 27 kW, consumatorii de siguranță la incendiu, nu dimensiona nimic.
3. **Fuziunea** (`interpretor.fuzioneaza`): intrarea lui Claude e baza (normalizată; Pn lipsă din catalog; locuința
   primește setul de bază / tipic pentru receptorii necitiți, declarat; „TN-S” la locuință / branșament = TN-C-S;
   rețeaua dedusă doar fizic, ca la reguli). Diferențele pe chei critice — `tip_schema`, `retea`, `schema_pamant`, P
   aprobată, Q branșament, invertoare (n × Pn), `n_trafo`, `origine`, consumatorii de siguranță — devin întrebarea
   **I17** cu ambele variante („citirea avansată → …; regulile locale → …”, se generează cu prima), nu o alegere tăcută;
   o valoare care la reguli lipsește (None) nu produce întrebare, iar „tri” implicit al regulilor față de rețea
   nedeclarată la Claude nici atât. Întrebările lui Claude → **I16**; `neinteles` → I15 + „Nu am înțeles”. Verificările
   F.7 rulează pe intrarea lui Claude (aceleași refuzuri / întrebări), „Am presupus” rămâne. Refuzul local I12 (în afara
   domeniului) se păstrează. Formă invalidă → rezultatul local + întrebările lui Claude + mențiune în „presupus”.
   Rezultatul are `motor: "llm"` și `verificare_incrucisata {diferente[], actiune_reguli, tip_reguli, ignorate?}`.
4. **Fără cheie** → exact F.1–F.10 (`motor: "reguli"`); `/api/chat` întoarce `citire.mesaj` „citire avansată
   indisponibilă …”, afișat discret sub răspuns. La eroarea apelului: rezultatul local + „(LLM indisponibil: …)”.
5. **Cheia:** server — `engine/cheie_api.py`: câmpul din interfață (`POST /api/setari/cheie {cheie, pastreaza}`, doar în
   memoria procesului; cu `pastreaza` și în `~/.config/scheme-monofilare/anthropic_api_key`, 0600), apoi
   `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN`. `/api/info.claude` = există cheie (cheia nu se întoarce niciodată).
   `/api/chat` folosește Claude implicit când există cheie (`claude: false` îl oprește). Web (Pyodide): `web/shim.js` ține
   cheia în browser (memorie / `localStorage` la cerere, cu try/catch), cere corpul de la worker (`/api/chat/cerere`), face
   `fetch` la `api.anthropic.com` cu `anthropic-dangerous-direct-browser-access: true` și trimite răspunsul worker-ului
   (`/api/chat` cu `raspuns_llm`); eroarea → `eroare_llm` și regulile locale.
6. **Teste:** `tests/test_interpretor_claude.py` (schemă la zi, acoperirea ieșirilor locale, fuziune, I16/I17, F.7, cheie,
   endpoint-uri, shim). Evaluarea promptului: `teste/r8/eval_llm.py` pe 60 de fraze r8 greșite/parțiale, cu răspunsuri
   **simulate** (`teste/r8/llm_simulat.json` — scrise în rolul modelului înainte de a citi rezultatele așteptate; v2 = după
   ajustarea promptului, neorb). Rezultat: reguli locale 4 C / 16 P / 40 G (54/162 verificări) → Claude simulat + fuziune
   52 C / 8 P / 0 G (154/162), v2 57 C / 3 P / 0 G (159/162). Nu e o măsurătoare a modelului real.

### F.12 (r8) Rescrierea textului, legarea pe clase, contextul tabloului — regulile locale
Rulează mereu (cu sau fără cheie API; fără cheie e singura citire). Corecțiile sunt pe **clase de formulări**, nu pe fraze.

1. **Rescrierea** (`engine/interp_rescriere.rescrie`, *schimbă* lungimea, rulează înaintea normalizării F.10; ce a
   rescris intră în „Am presupus”): tabele copiate (`engine/interp_tabel.py`: tab / CSV `;` `,` `|`, cu / fără antet,
   numerotate, bullet, ghilimele „”) cu semantica coloanelor (nr., denumire, model, producător, P[kW] — unitatea din
   antet —, L, faze, I, UM, obs.) și cantitatea aplicată („N x …”, UM m → lungime, module → Wp, corpuri de iluminat →
   un circuit cu P totală, rândurile fără consum — structură, cablu solar — scoase cu notă; virgula zecimală nu e
   separator CSV); engleză (listă de termeni; poarta = ≥ 2 cuvinte englezești, termenii tehnici mereu); prescurtări /
   greșeli de tastare („15k” = 15 kW, BTU); email (salut, cerere, semnătură, „X are N” → „X: N”); cascade („TG …
   alimentează”, „din TD-A pleacă …” → paranteze sub TD-A); autocorecturi („scuze, de fapt”, „corectez:” — ultima
   valoare câștigă); „N corpuri x P pe k circuite” → k circuite.
2. **Legarea valorii de entitate:** puterea unui receptor nu e niciodată P aprobată; ATR: evacuată → `P_evacuata_kW`,
   absorbită → `P_aprobata_kW`, evacuare < Σ invertoare → `limitare_injectie_kW`; Ik3 / Zs din ATR → `Ik3_OD_kA` /
   `Zb_OD_ohm` (≠ Q, ≠ RA); „prize 4 circ” = 4 circuite; „P kW cu N invertoare” = total (variantă + întrebare);
   „N invertoare: a×… + b×…” cu a+b ≠ N → I05; „fiecare cu câte un”; 3f / trif / 400 V = trifazat; ACB / MCCB /
   întrerupător general → `In_Q_JT_A` / `In_Q1_A`; PT / ACB ca sursă, nu plecare; BESS „4 x PCS 250 kW” → `bess.n_pcs`,
   „4 x 5,12 kWh” → `n_module` × `kWh_modul`.
3. **Contextul tabloului:** consumatori de siguranță (TDSI, sprinklere, desfumare, hidranți, jockey, lift de pompieri) →
   `siguranta` pe plecare; Y/Δ; GE „1+1”; cascade imbricate; secțiuni de bare (semibara A/B → `sectie`); lift / bloc ≠
   locuință; compensare (baterie de condensatoare, kvar, cos φ → Qc, I14) ≠ CEF / BESS; PTA / PT aerian; cablu
   rezistent la foc; circuite finale mono în tablou trifazat; contradicții (Q1 < Ib, ΣP plecări > Sn PT, două intrări).
   TD-ul locuinței: circuitele fără putere („prize 4 circ, AC 2, iluminat”) se emit câte unul, fără calibru, iar puterea
   implicită o pune motorul (declarată „PRESUPUS”).
4. **Fotovoltaic fără cuvânt-cheie:** prosumator din casă + Pa / ATR loc de consum și producere; modele mono (Primo -1,
   Sunny Boy, Growatt …TL-X) repartizate pe L1/L2/L3; LUNA2000-NNNKWH, BYD + SBS, PowerStack, Pylontech; zero export,
   limitare, măsura pe MT.
5. **Plasa:** ce nu e consumat → `neconsumat` → I15 („Nu am înțeles”); niciun fragment numeric pierdut tăcut. Fără
   întrebări inutile (o valoare absentă la reguli nu întreabă; prize fără calibru → 16 A presumat + o singură întrebare).
6. **Chei noi emise:** `tablouri_secundare[].circuite[].receptor` fără `In_A` / `P_kW` (puterea din `_p_implicit_td` al
   motorului); inventarul regenerat.
7. **Teste / reverificare:** `tests/test_interpretor_r8.py` (fiecare frază P0/P1 r8 + plasa pe tot r8 + teste de clasă
   pe formulări noi), `teste/r8/reverificare.py` (r5 + r6 + r7 + r8; tabel înainte / după pe r8). r8 (207 fraze,
   C/P/G): înainte 98/67/42 → după 206/1/0, P0/P1 90/91; r5–r7 fără regresii; `eval_llm` reguli locale 58 C / 2 P / 0 G
   (160/162). Rămas: I25 — motorul dă V02/V03 BLOCANT la 2 × NA2XY 4x240 în paralel (problemă de motor, nu de citire).

### F.13 (r9) Clasele r9 — regulile locale (calea principală a versiunii publice, fără cheie API)
Rescrierea are acum, în ordine: indentare → tabel → engleză → scurt → email → **autocorecturi** → **cifre** → **termeni**
→ **lungimi** → **mărire** → **lanț de săgeți** → „din TG pleacă” → cascade → corpuri (`engine/interp_rescriere.py`,
`interp_cifre.py`, `interp_cascade.py`; fiecare rescriere lasă o notă în „Am presupus”).

1. **Autocorecturi** („nu,”, „scuze,”, „pardon”, „de fapt”, „corectez”, „adică <valoare>”, „greșit, e …”): marcatorul
   înlocuiește, în aceeași propoziție, ultima entitate de același fel — grup cu cantitate („4 invertoare de 30 kW… nu, 5
   invertoare de 30 kW” → doar 5 × 30), valoare cu aceeași unitate, schema de pământ, rețeaua, modelul; fără dublare.
   Un model fără număr cu aceeași putere ca un grup numărat e modelul acelui grup (nu încă un invertor).
2. **Cascade:** lanț „A → B (…) → C (…)” = C sub B; indentarea pe rânduri (≥ 3 niveluri) = arbore; „Din TG pleacă …”
   când TG e tabloul descris = plecările lui (nu a doua sursă); „la rândul lui” ignorat. Locuință: mai multe TD / TE
   („TE-etaj”, „TD mansardă: …. TD anexă: …”), fiecare cu cablul („alimentat 5x4 15m”), lungimea și circuitele lui
   („4 circuite prize”, „2 AC 3,5 kW”, „flex 2,2 kW”); cu TE la etaj / mansardă, TG-ul casei ia setul parterului.
3. **Nu sunt plecări:** P instalată / Pi (informativă când există Pa / P absorbită — Pa câștigă; în PV „Puterea
   instalată a CEF: X kW.” e sumă de control); „DNO cut-out” = BMPT; „TT și TC” = transformatoare de măsură (nu schema
   TT); „celulă întreruptor în vid / 50/51” → `celula_trafo: intreruptor`; „(1+1)”, „rezervă” → `rezerva`, aceeași
   pornire ca unitatea activă; „Consumatori principali:” = lista plecărilor; compensare fixă trafo = notă, plecarea =
   bateria automată.
4. **Cifre:** „12 și 12 kW”, „10, 10 și 8 kW” = fiecare cu unitatea; „15 sau 25” (fără unitate) → întrebare; „N baterii
   (X kWh fiecare)” = N × X; „P kW termic (Q kW electric)” = Q; „am doar 11 kW tri”; „limitate la 100 kW” lângă
   invertoare = Pmax per invertor (notă), nu `limitare_injectie_kW`; invertor tri + mono → rețea tri, monofazatul pe
   faza declarată (`invertoare[].faza`), Iac verificat pe fază; „metering at MV side” → `masura: MT`; codul „12K” din
   model nu se rescrie în kW.
5. **Lungimi:** „VE 3,7 kW, 60 m”, „la 30 m de tablou”, „Distanța până la saună 25 m” → `circuite[].L_m`, nu coloana;
   „ap. la bloc” = apartament.
6. **GE / backup:** GE la casă cu comutare manuală (și „pe tot tabloul”) = `ge_rezerva`; „pe circuitele de bază (…)”
   → `ge_rezerva.circuite` (cheie nouă); hibrid + EPS / backup + Pa ≤ 30 kW = prosumator cu `backup.circuite`; „UPS /
   EPS, fără panouri” = locuință + circuit UPS + întrebare; invertor „existent” → `invertoare[].existent` (cheie nouă).
7. **Mărire:** „branșament mono 4 kW, vrem să trecem pe trifazat 15 kW” = mărire mono → tri 15 kW.
8. **Siguranță:** tablou mixt → consumatorii de siguranță `siguranta: true`, ceilalți `siguranta: false` explicit
   (rampe, iluminat normal, CTA); „stație de pompare PSI / grup de pompare incendiu” pe GE + ATS → `siguranta_tablou`,
   „N pompe (1A+1R)” → `n: "1+1"`; „TE lift pompieri 18 kW” = plecarea lui; cablu „NHXH FE180 E90 4x10 la 70 m” pe
   plecare (`cablu.tip_cablu`, `rezistent_foc`, `L_m`); GE + ATS: „Normali: …” → `consumatori[].vital: false`.
9. **Contradicții întrebate:** Q1 impus < Ib din plecările în kW (I08); BMPM + tablou trifazat (I08); Q branșament >
   1,6 × Q uzual pentru Pa (întrebare); sursă nedeclarată a unui tablou ≥ 100 kW fără P / Q1 declarat → întrebare
   (sub — „Am presupus” BMPT); racord CEF nedeclarat → întrebare peste 100 kW, avertisment sub; BESS fără PCS →
   întrebare; IT medical → I12; magazin / farmacie + TT ≠ locuință; cabluri „2 cabluri CYAbY 3x185+95 în paralel” →
   `cablu.n_paralel`, `cablu.tip_cablu` (+ `izolatie: XLPE` la N2XY / NA2XY) — verificat până în motor (Q1_C1).
10. **Teste / reverificare:** `tests/test_interpretor_r9.py` (fiecare frază P0/P1 r9, amprenta frazelor corecte, plasa
   pe tot r9, teste de clasă pe formulări noi), `teste/r9/reverificare.py` (r5…r9). r9 (208 fraze, verificări C/P/G):
   înainte 145/41/22 → după 208/0/0, P0/P1 69/69; r5–r8 fără regresii.

### F.14 (r10) Clasele r10 — regulile locale + întrebările din verificarea motorului
Rescrieri noi (`engine/interp_r10.py`, înaintea și după autocorecturile r9; fiecare lasă o notă în „Am presupus”):
`rescrie_inainte` (engleză r10: „existing LV switchboard / MDB” = TG existent, „utility transformer” = PT al OD,
„new 630kVA substation” = PT nou, car wash / blower / vacuum; autocorecturi: „(400 kW, nu 300)”, „nu 400, ci 630 kVA”,
„VE nu e 11 kW, e 7,4 kW; restul rămâne”, „16 kW electric? nu, …”, „rectific”, „mai exact”, „scuze, sunt 3 x …”,
„Corectez:” fără valoare veche) și `rescrie_dupa` (TD-ul anexei, „3x6mm” = secțiune, greșeli de tastare pe numele
receptorilor urmate de valoare, VFD, „+” între plecări, „motoare: 2 x 11 kW și 4 x 2,2 kW”, „N stații VE 2x22 kW”,
„pompă electrică X kW + pompă diesel”, „sursă dublă PT1/PT2”, „2 semibare cu câte N plecări”, „una X kW și una Y kW”,
„N circ prize M ilum” = circuite, „(1+1 rezervă)” / „+ 1 de rezervă”, „interblocaj 2 din 3”, „pt uscat 630” = PT,
„18/30 kV” = izolația cablului MT, „PTA” = PT aerian, „TG cu Q 3x32A” / „branșament 3x32” = Q branșament, „deci X kW”
după corectură = total, „N invertoare (A … și B …)” = lista din paranteză, „(40 kW existenți)” = sumă de control,
„avem deja 20 kW (model)” = existent, „ATR permite doar X kW evacuare”, „N baterii X kWh” = N × X).

1. **Faze monofazate:** repartizarea L1→L2→L3 nu se mai suprascrie (regresia r9 #7); „pe L1, L2, L3” / „pe fazele R și T”
   = ordinea scrisă; un invertor monofazat (sau un model mono: -L1, Primo, Sunny Boy, MIN …TL-X) pe casă trifazată →
   `retea: "tri"` + `invertoare[].faza`; Iac verificat pe faza cea mai încărcată; BMPT declarat ≥ Iac > 100 A = notă.
2. **Existent + nou:** grupul din propoziția cu „deja / existent / există / nu se modifică / montat” = `existent: true`,
   cel din „adaug / nou / se montează” rămâne nou („TG / PT / BMPT existent” nu contează); propozițiile separă grupurile.
3. **Topologii (cheile motorului):** PT: `n_trafo: 2`, `cupla` (în paralel = „inchisa”; ATS între trafo = „deschisa”),
   `sursa_rezerva: "trafo"` + `comutare: "ATS"`, `uk_pct`, `In_Q_JT_A` din „TG 4000 A” / cutia BMPT a PTA, `cablu_MT`;
   GE: `fara_retea: true`, `consumatori[].vital` din „Vitali: … Nevitali: …” (sarcina GE = vitalii), sursa BMPT; tablou:
   `ks` / `cosfi` / `P_kW` (Pc) globale, plecarea unică din TG existent poartă cablul / L / `ddr: {tip}`, UPS cu bypass
   (`ups`, `bypass`, PDU-urile în aval), `separare_PEN`, `cablu.existent`, TN-C cu secțiuni < 10 mm² → întrebare;
   CEF: `bara`, `racord_In_Q_A` + `racord_Q_tip` (MPR = gG), `invertoare[].tgd` + `n_tgd_cf`, `pt_od`, limitarea
   „X %” = X % × Σ invertoare, cablul impus fără L → L = 30 m presupus + întrebare, „cablu … de la invertor” = `cablu_inv`.
4. **Locuință:** hibrid + baterie + tablou EPS = prosumator cu `backup.circuite` (și receptori necunoscuți: router);
   EPS pe toată casa = `backup {toata_casa, comutare, N_comutat}`; GE casă (și monofazat, `ge_rezerva.retea: "mono"`);
   AC multisplit = un circuit `multisplit` / `unitati_interioare`; TD piscină / TE pe niveluri cu camerele lor / corpuri
   (TD Corp B cu circuit echivalent + întrebare); „15 kVA” = Pa 0,9 × S și Q din kVA; coloana „cablu 3x6 de 45 m”;
   TN-C (rețea) → TN-C-S cu `separare_PEN: "BMPT"` + întrebare; RA > 4 Ω în TN-C-S → întrebare; Q < Ib(Pa) și Q fără Pa
   cu receptoare mari → întrebare; „cuptor 72 kW”, spălătorie auto, magazin ≠ locuință.
5. **Nimic blocat fără întrebare** (`interpretor.interpreteaza`, calea aplicației; `verifica_motor=True`): rezultatul
   trece prin `constructor.genereaza` + `validare.valideaza`; fiecare BLOCANT fără întrebare devine o întrebare concretă
   cu opțiunile de remediere (șabloane V04 / V46 / V28 / V53 / V96, altfel mesaj + `remediere` din verificare), acțiunea
   devine „genereaza_cu_intrebare”; întrebările adăugate sunt și în `intrebari_motor`.
6. **Teste / reverificare:** `tests/test_interpretor_r10.py` (P0/P1 r10 + P2 din clasele reparate, plasa și blocajul
   întrebat pe toate frazele r10, 5–10 formulări noi pe clasă), `teste/r10/reverificare.py` (r5…r10). r10 (204 fraze,
   verificări C/P/G): înainte 106/73/25 → după 204/0/0, P0/P1 94/94; r5–r9 fără regresii (r6 N55: invertorul monofazat
   pe casă trifazată = trifazat, decizie r10).

### F.15 (r11) Dicționarul central de sinonime + clasele r11 — regulile locale
Concluzia r11: reparațiile anterioare acopereau cuvântul testat, nu sinonimele lui. De aceea:

1. **Dicționarul central** `engine/interp_sinonime.py` (`SINONIME[concept]`, `RX`, `are` / `cauta`, `alternanta`,
   `canonizeaza`, `fara_retea`, `grupa_conexiuni`): uk (Ucc / usc / u_k / tensiunea / impedanța de scurtcircuit / Zk /
   impedance voltage); fără rețea (izolat / insular / off-grid / autonom / stand-alone / singura sursă / no grid — „izolat”,
   „autonom”, „stand-alone” doar lângă GE, nu „neutru / cablu izolat”, „BESS stand-alone”); BMPT (contor / firidă / cutie
   de branșament / grup de măsură / DNO cut-out — doar cu calibru: „contor 3x63A” = BMPT 3x63A, „1x32A” / „monofazat” =
   BMPM); ATS (AAR / A.A.R. / anclanșare automată a rezervei / comutator / inversor automat / transfer automat); GE (grup
   electrogen / generator / genset / grup diesel / DG / motogenerator); PT (post trafo / post de transformare / cabină de
   transformare / substation); grupa de conexiuni (Dyn11 / Dyn 11 / DYn-11 / D/yn-11 / Δyn11 / Yzn5 / Yyn0 →
   `grupa_conexiuni`); iluminat („N lumini / spoturi / corpuri de iluminat / lights / ilum / l” = N circuite; „8p 6l”);
   tablou (sub-tablou / subpanel / panou electric secundar); VE (wallbox / charger / stație EV / punct de încărcare); UPS
   (U.P.S. / sursă neîntreruptibilă); fără GE; fără PV; limitarea injecției (export cap / limit / plafon); ks; ku.
   `canonizeaza` rulează în `rescrie` după engleză / mesaj scurt; regulile noi folosesc dicționarul (nu cuvinte fixe).
2. **Clase r11** (`engine/interp_r11.py`: `rescrie_inainte`, `rescrie_dupa`, `corecteaza_tip`, `post`): paranteza
   „N invertoare (k × A și m × B)” cu Σk = N; „N tablouri TGD-CF, fiecare cu k × M” → N·k în `n_tgd_cf` / `invertoare[].tgd`;
   „N stații EV de P kW” = N plecări; „AAR / ATS între T1 și T2” fără GE = `n_trafo: 2`, cupla deschisă, `aar: true`;
   UPS … kVA = plecare `receptor: "ups"` (Sn_kVA, bypass, intrari_separate, copii), nu PT; vitali / nevitali („pe bara
   vitală: …; pe bara normală: …”, „ATS pe consumatorii vitali (…). Nevitalii (…) doar pe rețea”) → `vital` +
   `bara_vitala`; cascade („->”, „X alimentează Y”, „TE din TD-2 care e din TG, iar TG din PT” = o sursă); liste numerotate,
   tabel „cod;destinație;P;faze;L”, „N plecări NH: a × I, b × I”, „N circuite de iluminat de câte P”, „N pompe în schema
   a+b”; CSV cu virgulă; ku × Pi; autocorecturi pe racord / existent / rețea / schema de pământ; „3 noi și 2 existente”;
   „(75 kW)” = suma de control (Pn din catalog); fișa în paranteză („SG350HX (320 kW, …)”) = Pn declarat; „fără panouri” =
   BESS fără câmp PV (PCS = hibridul); „N baterii MODEL X kWh” = N·X; „N stringuri a câte M module” → kWp din Pmax (fără
   Pmax → întrebare); „Avem PT propriu” = `pt_existent`; cablul solar = `cablu_cc` (nu C0); „fiecare invertor cu cablu …”
   = `cablu_inv`; Ik3 / impedanța buclei la racord = `Ik3_OD_kA` / `Zb_OD_ohm`. Locuință: „pompa … e la 120 m” = L-ul
   circuitului; „prizele pe C25 cu 2,5 mm²” = circuitele de prize; CEE trifazată = circuit 3F; „doar TE baie” / „TE nou din
   tabloul existent cu C32” = tablou secundar; vilă cu N apartamente → întrebare; generator pe intrarea GEN ≠ invertor;
   mărire mono → tri; contradicția mono / tri doar pe ALIMENTARE (TE / receptoarele monofazate dintr-o casă trifazată nu).
3. **Rețeaua dedusă:** dedusă (din „3 × … A”, 400 V, BMPT, model, putere, PT) → mențiune „REȚEA DEDUSĂ” în `presupus[]`
   și `_deduse: ["retea"]` (în `intrare_fizica` și în rezultat; panoul o marchează); doar din „BMPT” și cu o putere care
   încape în monofazat → și întrebare; tablou fără sursă → `_deduse` include „origine”.
4. **Cheile motorului (engine/calc/chei.py):** la final, cheile nefolosite de schema aleasă se mapează (PT: ATS între trafo
   → `aar`, măsura semidirectă → `masura: JT`) sau rămân doar ca metadate `_cheie` (nu V96 „nesuportat”).
   Întrebările din blocajele V46 / V53 folosesc `remediere` / `propunere` din verificare; „altă fază” doar la trifazat.
5. **Teste / reverificare:** `tests/test_interpretor_r11.py` (P0/P1 r11, plasa + blocaj întrebat + chei acceptate pe tot r11,
   sinonimele pe concept, 5–10 formulări noi pe clasă), `teste/r11/reverificare.py` (r5…r11).

### F.16 (r12) Texte de proiectant (memorii, ATR-uri, devize copiate) — `engine/interp_reale.py`
Testarea pe proiecte reale a arătat că textele lungi „ca de proiectant” leagă greșit cablurile, nu recunosc racordul
existent și cad în capcane de vocabular. `preextrage(text)` rulează ÎNAINTEA regulilor vechi: citește pe SEGMENTE (rând,
„;”, „. ”), scoate din text fragmentele pe care le-a interpretat (sau le rescrie canonic: „PT existent”, „racord in TG
existent”, „Icu N kA”, „N x MODEL”) și le păstrează structurat; `aplica` le scrie în `intrare_fizica` după reguli.
Fiecare fragment scos lasă o notă în „Am presupus” sau o întrebare.

1. **Cablurile pe segment.** Contextul propoziției decide: invertor → tablou („INVk: … cablu …”, „fiecare invertor cu
   cablu …”, „de la invertor…”) = `invertoare[k].cablu` + `L_m` pe rândul INVk, altfel `cablu_inv` + `L_inv_m`; tablou →
   PT / TEG beneficiar / stație / TDRI / BMPT / tabloul consumatorului („Legătura X - PT …:”, „de la TE la PTAb”) =
   `cablu_C0` + `L_racord_m`, „…, apoi …” = `cablu_C0.tronsoane[]` (L_racord_m = Σ); LES / A2XS(FL)2Y / NA2XS… / „cablu MT”
   = `cablu_MT` {S_mm2, material, tip, L_m, tronsoane[]} — niciodată C0; TE secundar → TEG = `tablouri_intermediare[].cablu`;
   trafo → TDRI = informativ; spre contorul de producție = `monitorizare.contor_productie.cablu`; branșament / coloană
   (prosumator) = `L_coloana_m`. „N cabluri … în paralel”, „2x TYIR …”, „N x … 1xS pe fază” = `n_fortat` DOAR pe cablul
   segmentului; „în paralel” fără număr → întrebare. Lungimea: „(10-120 m)” = cea mai mare; „L=”, „cca”, „lungime traseu”;
   „m 600” după cablu (deviz) = cantitate, nu lungime; „70m conductor …” (listă de cantități) = total → ÷ cabluri în
   paralel / invertoare, cu întrebare. Mai multe cabluri fără context → I05 „Unde se leagă …” (nu C0 implicit); un singur
   cablu fără context rămâne la regula veche (C0, cu notă).
2. **Invertoarele pe rânduri.** „INV1 …:”, „Invertorul 2 - …” (≥ 2 rânduri) = câte un grup `n = 1` pe rând, cu `string`
   propriu; „N stringuri × M (module)” = N stringuri PE INVERTOR, împărțite pe MPPT: `n_stringuri_paralel = ⌈N / K⌉`,
   `n_MPPT = N / paralel` (K = „K MPPT” din rând, din rândul-frate cu același model sau întrebare); „pe MPPT” scris →
   neschimbat. Module ≠ stringuri × M → I08; rânduri ≠ invertoare → I05.
3. **Racordul existent.** „PTAb / PT / post(ul de transformare) … existent”, „barele JT ale postului (existent)”,
   „TDRI” fără PT nou → `racord: pt`, `pt_existent: true`, `pt_Sn_kVA` din preajmă; „TEG / TG beneficiar(ului)
   (alimentat din PT N kVA)”, „stația / secția de 0,4 kV a fabricii / uzinei / halei” → `racord: tg_existent` (+
   `pt_Sn_kVA` = sursa TG); cu „trafo existent N kVA” → PT existent; „… cu întreruptor nou N A” / „Întrerupător N A …
   în secția 0,4 kV” → `racord_In_Q_A` (ACB ≥ 1000 A, altfel MCCB); „pe separator vertical MPR N A existent” →
   `racord_In_Q_A`, `racord_Q_tip: gG`. PT NOU doar cu „nou / proiectat / (pr)”. Cu PT / TG existent, „BMPT semidirect”
   = grupul de măsură al CEF (`monitorizare.contor_productie`), nu racordul.
4. **Vocabular.** „N TT …”, „TT 20/0,1 kV”, „TT cl …” = transformatoare de tensiune (nu schema TT); „AAR” la celulele MT
   / PC și „în paralel” la cabluri ≠ GE + ATS (text PV fără GE → `cef`); „Ir = 36 kA”, „Ir-16kA” = Icu; „MODEL buc N”
   (rând de deviz, nu tabel) și „N buc. invertor …” = N × MODEL; „Pi X kW” la CEF cu X > Σ Pn și fără kWp = X kWp;
   „Putere nominală totală invertoare X kW” / „putere maximă în AC X MW” = `Pn_total_kW` (sumă de control, I08 dacă
   ≠ Σ); „puterea instalată panouri X kW” = X kWp; „evacuată A kVA / B kW” = B kW (`P_evacuata_kW`); „absorbită A kVA” =
   informativ; „0,4 kV” după un cod de model nu intră în model; modulul „panouri 203,32” nu e Pmax 203 W.
5. **Chei noi pentru motor** (formele din `engine/calc/scheme.py::config_q`, `normalizeaza_cascada`):
   `QG` {In_A, electronic, motorizat, Icu_kA, Ir_reglat [A]} + `In_QG_A` („întreruptor de interfață / general …”); Q0
   „întreruptor general” din TDRI la PT nou = `In_Q_JT_A`, „plecare Q1 N A spre TE … CEF” = QG; `invertoare[].prot_tip`
   (gG / MCB / MCCB) + `invertoare[].protectie` {In_A, Icu_kA, Ir_reglat, electronic} (tablou de protecție / separator
   cu siguranțe / întreruptor „pe fiecare invertor”, sau N aparate = N invertoare); `tablouri_intermediare[]` {nume,
   cablu, L_m, prot_tip, In_A, Icu_kA} + `invertoare[].tablou` = 1…N („grupate câte M pe N tablouri secundare /
   intermediare”); `monitorizare` {smart_meter {model, TC_primar_A} | true, smartlogger {model} | true, rs485,
   contor_productie {tip, cablu, L_m, TC_primar_A}} (la prosumator `contor_productie` la nivel 1); `protectie_interfata`
   {releu, ups_VA}; `punct_conexiune` {celule_linie, aar, servicii_proprii_kVA, scada}; `dg_intreruptor`;
   `cablu_C0.tronsoane[].L`; `Iac_max_A` pe invertor („Iac max …”, „(25 A max)”); fișa
   modulului (`modul.Vmpp_V`, `Impp_A`, `I_rev_A`, `Umax_sistem_V`); celulele MT („celule: linie, măsură …”, „2 celule
   de linie”) = `celule_mt`, „dispozitiv general / protecție trafo cu întrerupător (SF6)” = `celula_trafo: intreruptor`.
   Prosumator: „branșament existent N A” / „BMPM OD … N A” = `In_Q_bransament_A`, „TE-AC invertor cu RCBO N A” =
   `In_QG_A`, aparatele tabloului consumatorului = informativ. Cheile pe care schema nu le citește încă se păstrează ca
   metadate `_cheie` (inclusiv pe elementele listelor, ex. `invertoare[]._cheie`), nu ca V96.
6. **Teste:** `tests/test_interpretor_reale.py` (fraze NOI anonimizate, 5–10 pe clasă; plasa + chei acceptate). Textele
   proiectelor reale nu se copiază în teste sau în cod.

### F.8 Răspunsul
Totdeauna conține:
1. „Am înțeles:” cu tipul schemei, puterile, numărul și lista plecărilor, lungimile și cartușul;
2. „Am presupus:” (F.6);
3. verificările BLOCANT/AVERTISMENT cu remedierea;
4. întrebarea, dacă există.

Suita `fraze_chat.json` (60 de fraze, inclusiv cele 25 din audit) trebuie trecută integral.
**(r6)** Dacă `neconsumat[]` nu e gol, răspunsul conține și „Nu am înțeles: …” (după „Am înțeles”) și întrebarea I15.

---

## G. Ce se scrie pe planșă

### G.1 Note fixe (totdeauna)
1. „Schemă electrică monofilară de principiu, fază {faza}. Dimensionare conform I7-2011, SR HD 60364-4-41, -4-43, -5-52 (2011), -5-54, SR EN 60909-0; branșament conform ST 4-JT / ST 3-JT (DEER).”
2. „Nu fac obiectul prezentei planșe: racordul OD (C1) conform ATR nr. {nr_ATR}; legătura trafo–TGJT; partea MT din amonte de celula trafo; priza de pământ (calcul separat); analiza de risc la trăsnet.” (A.3) **v1.3:** când rezultatul are `priza`, „priza de pământ (calcul separat)” dispare din nota 2 și se adaugă nota `rez["priza"]["nota"]` (dispunere, Rp calculat față de limită, ρ, ψ, confirmare prin măsurare); materialele prizei intră în listă din `rez["priza"]["materiale"]`.
3. „Schemă de legare la pământ: {TN-C-S cu separarea PEN pe BN în {bloc} | TN-S | TT}. Rp ≤ {4 Ω branșament | 1 Ω PT, conform calcul}.” **v1.2:** textul se ia din rezultatul motorului (`nota_schema_pamant`, `texte.nota_schema_pamant`), generat din schema efectivă (TT: DDR pe fiecare circuit și RA; TN-C: PEN din PT propriu și separarea la bară; GE: neutrul GE la pământ local, ATS 4P). Valorile neacoperite (IT) nu ajung pe planșă (V28).
4. „Secțiunile cablurilor sunt dimensionate la Iz' = Iz·kθ·kgrup·ksol (SR HD 60364-5-52 tab. B.52.x), la ΔU (I7-2011) și la stabilitatea termică; reglajele protecțiilor sunt cele din tabelul de pe planșă.”

### G.2 Nota de ipoteze (generată din valorile efectiv folosite)
„Ipoteze de calcul:
- cosφ = {..};
- ks = {..} ({motiv});
- pozare {metoda} ({descriere}), θ = {..} °C, ρ sol = {..} K·m/W, grupare {n} circuite;
- Ik3max la punctul de delimitare = {..} kA {(din ATR) | (valoare implicită — se confirmă cu OD)};
- impedanța buclei OD = {..} Ω {…};
- S"kQ = {..} MVA;
- trafo uk = {..} %, Pk = {..} W;
- c_max = 1,10, c_min = 0,95;
- limite ΔU: {3/5 % | 6/8 %} de la {punctul de delimitare | bornele JT ale PT}.”

Lista se scrie integral. Orice ipoteză implicită apare cu sufixul „(presupus)”.

### G.3 Note generate din parametri (nu text liber)
- Branșament (forma de referință e cazul X02; arbitraj obs. 3): „{k}. Măsurare {directă (contor furnizat și montat de OD) | semidirectă prin TC 3 × {p}/5 A, cl. 0,5, 5 VA}; Q {MCB C{In} | MCCB 4P In {In} A}[ reglat la Ir = {Ir} A][ (Pa = {Pa} kW din ATR) | (Pa din ATR)]; {bloc} conform ST 4-JT Ed. U1 Rev. 3/2024, varianta {v}.”
  - „ reglat la Ir = {Ir} A” apare doar dacă Ir există în model (parametrul `Q_Ir_A` sau Ir calculat). Nu se deduce Ir din limitele blocului.
  - „(Pa = {Pa} kW din ATR)” apare doar dacă Pa este cunoscut (intrare `P_kW`). Altfel, cu Ir prezent, apare „(Pa din ATR)”.
  - La MCB, porțiunea cu Ir lipsește.
- PT: „Trafo {Sn} kVA, In_T = {In_T} A; Q JT {tip} {In} A, Ir = {Ir} A; Ik3max bara TGJT = {Ik3} kA; celula trafo {…}.”
- CEF: „Σ Pn = {P} kW, S = {S} kVA, categoria {X} RfG; PI conform {Ord. ANRE 228/2018 | Ord. ANRE 208/2018 și ATR}; Voc(−25 °C) = {U} V ≤ {Umax} V.”

### G.4 Tabelul de calcul de pe planșă (sau anexă de calcul)
Pentru fiecare ramură se scrie un rând:

| Ramură | Pi | ks | Pc | cosφ | Ib | Protecție | In/Ir | Icu | Cablu | L | Iz' | ΔU ramură | ΔU cumulat | Ik3 bară | Ik1 capăt | Ia | t | Verificări |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

Rândurile cu BLOCANT se scriu cu roșu. Pe planșa de export nu pot exista rânduri BLOCANT, pentru că exportul e refuzat.

### G.5 Cartuș (P2-3)
Câmpuri obligatorii:
- beneficiar, adresă (localitate, județ, CF), titlu proiect, nr. proiect, fază, planșă, revizie, dată, scară;
- proiectant (firma, J, CUI), șef proiect, proiectat, desenat, verificat (cu semnături);
- nr. și tipul atestatului ANRE al proiectantului — atestat de **proiectare** al firmei (vezi mai jos);
- nr. ATR / aviz.

Un câmp lipsă se lasă gol, **nu** se completează cu text de exemplu.

#### G.5.1 Atestate ANRE (V58) [VERIFICAT online 29.10.2026]
**Firme** — Regulamentul pentru atestarea operatorilor economici care proiectează, execută și verifică instalații electrice,
aprobat prin **Ord. ANRE nr. 134/15.12.2021** (MO 1216/22.12.2021), art. 9 alin. (1) lit. a)–q), competențele în anexa nr. 6.
Codurile exacte (singurele acceptate în selector, `ATESTATE_ANRE` în `engine/constructor.py` și `static/index.html`):

| Tip | Acoperă | Include |
|---|---|---|
| A / A1 / A2 / A3 | încercări: toate / JT / JT+MT / certificarea conformității tehnice a centralelor | A ⊃ A2 ⊃ A1 |
| B | proiectare + executare instalații ext./int. pentru incinte/construcții civile și industriale, branșamente aeriene și subterane 0,4 kV | Bp, Be, Bi, A1 |
| Bp | proiectare, același domeniu ca B (anexa 6: branșamente ale locurilor de consum și de producere) | — |
| Be | executare, același domeniu ca B | Bi, A1 |
| Bi | executare instalații ext./int. pentru incinte/construcții | A1 |
| C1A / C2A | proiectare / executare linii 0,4–20 kV, PT cu tensiunea superioară ≤ 20 kV, stații MT | C1A ⊃ Bp; C2A ⊃ Be, Bi, A2, A1 |
| C1B / C2B | proiectare / executare linii 0,4–110 kV, PT ≤ 20 kV, stații MT și 110 kV | C1B ⊃ C1A, Bp; C2B ⊃ C2A, Be, Bi, A2, A1 |
| D1 / D2 | proiectare / executare linii, orice tensiune | D1 ⊃ C1B, C1A, Bp; D2 ⊃ C2B, C2A, Be, Bi, A2, A1 |
| E1 / E2 | proiectare / executare PT, stații, partea electrică a centralelor, orice tensiune | E1 ⊃ C1B, C1A, Bp; E2 ⊃ E2PA, C2B, C2A, Be, Bi, A2, A1 |
| E2PA | executare protecții și automatizări în stații | — |

„Ap”, „Ep”, „Ep1” **nu există** (versiunile anterioare ofereau „Ap” — eliminat; o valoare veche rămâne vizibilă, marcată „nu e cod ANRE”).

**Electricieni** — Regulamentul pentru autorizarea electricienilor…, aprobat prin **Ord. ANRE nr. 66/10.05.2023** (MO 417/16.05.2023),
modificat prin Ord. ANRE nr. 65/2024; art. 8 alin. (2): tip A = proiectare, tip B = executare; art. 9: **I** — executare instalații
interioare ≤ 10 kW, < 1 kV; **IIA / IIB** — proiectare / executare, orice putere, < 1 kV; **IIIA / IIIB** — idem, ≤ 20 kV;
**IVA / IVB** — idem, orice tensiune standardizată. [NEVERIFICAT: forma consolidată după Ord. 65/2024 nu a putut fi citită;
art. 9 e luat din forma inițială.]

**Regula „atestatul cerut de lucrare”** (`constructor.atestate_necesare`):
- JT (locuință, branșament, tablouri, GE, prosumator, CEF fără PT propriu): proiectare **Bp + electrician IIA**, executare **Be + IIB**;
- PT 20/0,4 kV și CEF cu PT propriu (≤ 20 kV): proiectare **C1A + IIIA**, executare **C2A + IIIB** (aerian sau subteran nu schimbă tipul).
  [NEVERIFICAT: dacă la CEF se cere E1/E2 („partea electrică a centralelor”) — regulamentul nu tratează explicit fotovoltaicul.]
- Cartușul e al proiectantului → V58 AVERTISMENT dacă tipul declarat (cu incluziunile din tabel, comparate pe cod exact, nu pe subșir)
  nu acoperă atestatul de **proiectare** cerut; câmpul `cartus.atestat_necesar` = cel de proiectare, `cartus.atestat_necesar_executie`
  = cel de executare (în caietul de sarcini, „Atestat ANRE necesar executantului”).

---

## I. Documente și vederi derivate (E2, 28.10.2026)

Toate pleacă din planșă (model: referințele de pe desen) + calcul (valorile); nu schimbă dimensionarea.

| Funcție | Modul | Endpoint |
|---|---|---|
| Tabel de cabluri (ref, de la → la, tip, formație, L, pozare, Ib, Iz', ΔU ramură / cumulat, protecție, Ik) | `documente_tabele.tabel_cabluri` | `/api/documente`, `/api/export/tabel_cabluri[?format=pdf]` |
| Fișa de reglaje (Ir, tr, Isd, tsd, Ii, curbă, IΔn, Icu) + Ik3max / Ik1min pe noduri + reglajele PI | `documente_tabele.fisa_reglaje` | `/api/documente`, `/api/export/fisa_reglaje`, `/api/export/tabele` |
| Carcasa tabloului: module DIN, rezervă 20–30 % (implicit 25 %), rânduri, carcasa propusă | `documente_tabele.dimensionare_carcasa` | `/api/documente` |
| Pierderi în cabluri c.c. / c.a. (kW, %), energie anuală pierdută (factor de formă 0,5) | `documente_tabele.pierderi_cabluri` | `/api/documente`, memoriu |
| Evaluarea SPD: SR HD 60364-4-443 (art. 443.4 consecințe; 443.5 CRL = fenv/(LP·Ng) < 1000), SR HD 60364-7-712 (Lcrit = 115 / 200 / 450 / Ng) | `documente_protectii.evaluare_spd` | `/api/spd`, `/api/documente`, memoriu |
| Curbe timp-curent generice (MCB B/C/D, gG, MCCB TM, electronic LSI) + perechi amonte / aval | `documente_protectii.curbe_timp_curent` | `/api/curbe` (desenul le randează) |
| Producție PVGIS (JRC v5.3, cache, offline → valoarea proiectantului) | `pvgis` | `/api/pvgis`, `/api/pvgis/url`, `/api/pvgis/raspuns` |
| „Tipic pentru N” (invertoare identice) | `documente_tabele.grupuri_tipice` → `model.grupuri_tipice` | (date în model) |
| Import circuite Excel / CSV + model .xlsx | `import_circuite` | `GET /api/import/model_circuite`, `POST /api/import/circuite?destinatie=` |
| Galerie personală (date/galerie.json) | `galerie` | `GET/POST /api/galerie` |
| Dosar de racordare (cerere Ord. ANRE 19/2022 anexa 1 / 2 sau Ord. 59/2013, fișa tehnică, lista echipamentelor cu certificate, declarația instalatorului, planșa) | `documente_racordare` + `sabloane/racordare.py` | `/api/export/dosar_racordare` (.zip: .docx + .pdf) |
| Caiet de sarcini (8 capitole, caracteristici minime neutre de marcă) | `documente_caiet` + `sabloane/caiet_sarcini.py` | `/api/export/caiet_sarcini[?format=pdf]` |

**Tab-ul „Documente” (interfața):** `POST /api/documente/<cheie>` (previzualizare: JSON {titlu, coloane, randuri, note} /
{titlu, tabele[]}, SVG la `curbe`, HTML la `spd`) și `POST /api/export/<cheie>` pentru cheile cabluri (.xlsx), reglaje,
curbe, spd, carcasa, productie (PDF; HTML fără Chrome / în Pyodide), pierderi (.xlsx), etichete (PDF A4, benzi de 18 mm ×
module·17,5 mm + etichetele „două surse”), racordare (PV: .zip dosar; consum: cererea loc de consum .docx), caiet (.docx)
— `engine/documente_vederi.py`. Producția PVGIS salvată de interfață în `calc.productie` {lat, lon, unghi, azimut,
pierderi_pct, kWh_kWp_an, lunar[12], sursa, data} e folosită la `productie`, la pierderi și în memoriu.

Câmpurile formularelor: completate din date = fond albastru, de completat manual = „…… (de completat)” pe fond galben
(`documente_doc.Camp`). Pachetul de predare include tabelele (.xlsx), caietul de sarcini și, la PV, dosarul de racordare.

## H. Anexe

### H.1 Trasabilitatea constatărilor din audit
| Constatare | Unde se rezolvă |
|---|---|
| P0-1 cablu subdimensionat tăcut | B.8 (căutare n ≤ 4, fallback, V01), B.6, V02/V03 |
| P0-2 calibre oprite la 1600 A | B.4 (ACB până la 4000 A), C.5 pct. 3, V06, V60 |
| P0-3 listă ≠ desen | E.1, V80, V81, test automat E.3 |
| P0-4 liste de numere pierdute | F.4 (unitate comună, multiplicator), I05 |
| P0-5 P din primul kW | C.2 pct. 3 (bilanț), V14, V40 |
| P0-6 BMPT inexistente | C.1, V50, V51, V56 |
| P0-7 CEF: calibre, BESS, MWp | B.2 (invertor), B.5 (serie), C.3 pct. 3–4, V65, V66, F.3 |
| P0-8 circuit de tensiune în serie cu TC | B.19, V57 |
| P0-9 PT fără neutru la pământ / TC releu | C.5 pct. 7, V63 |
| P0-10 monofazat tratat ca trifazat | B.2, B.12 (formula mono /230), C.1 BMPM, C.4, V53 |
| P1-1 tabele Iz vechi | B.7, `norme.IZ` |
| P1-2 factori de corecție neaplicați | B.7.2 |
| P1-3 neutru redus la Al ≤ 25 | B.10, V25 |
| P1-4 PE lipsă | B.11, V26, V36 |
| P1-5 ΔU necumulat | B.12 |
| P1-6 fără Ik3/Ik1 | B.13, B.14, B.15, B.16 |
| P1-7 selectivitate | B.18, V40–V42 |
| P1-8 raport TC | B.19, C.1 |
| P1-9 bloc DXF cu geometria primei inserări | în afara motorului: randare DXF, cu nume de bloc pe variante (`SYM_MCCB_BD`). Cerință pentru renderer. |
| P1-10 carcase greșite / lipsă c.c. | C.3 pct. 9–10, V82, V88 |
| P1-11 săgeți inversate | V83 |
| P1-12 aceeași lungime peste tot | F.5 „lungime”, B.0, C.1 (C1 nedimensionat) |
| P1-13 PDF 500 | în afara motorului (export) |
| P1-14 parser: „cu 2”, „TD-1”, adresă, km | F.2 pct. 4, F.4 pct. 4, F.5 |
| P2-5 MCB „gG” | E.3 (MCB cu curbă + Icn) |
| P2-6 separator zecimal | E.2 |
| P2-8 BOM | E.1 pct. 5 |
| P2-9 Al 10 mm², I2 gG < 16 A | B.8 (Al → Cu), B.6 |
| P2-10 Ord. 228 la CEF | C.3 pct. 7, V75 |

### H.2 Valori [NEVERIFICAT] rămase
Lista completă e în `norme.NEVERIFICAT` (afișată în memoriu). După verificarea din 28.10.2026 rămân numai pozițiile care nu se pot verifica public (standard cu plată / document inaccesibil), cu valoarea din practica de proiectare confirmată ca plauzibilă de verificator: Iz Al 16 mm² și Iz Cu B2; uk trafo (SR EN 50588-1); siguranțele MT ale celulei trafo; consumul contorului 1,0 VA; factorii de grupare F distanțat (0,97 la 2 sisteme); denumirea C2XAbY; x"d GE; Im minim 500 A (valoarea exactă din fișa MCCB); I²t total gG ≈ 2·prearc; ψ_e / ψ_pl, racordul platbandei și orele de manoperă ale prizei; limita prizei PT „conform ANRE” (1 Ω păstrat, vezi §C.7); DDR S = 0,15 s echivalent; tabelul receptorilor de locuință, Inc RCCB / IS 6/10 kA, cosφ 0,95, rezerva SPD T2, plafonul de 16 mm²; regulile r8b de denumire / calibru. Deciziile proiectantului sunt în `norme.DECIZII_PROIECTANT_28_10_2026` și în §H.2a.

### H.2a Verificarea normelor (28.10.2026) — tabelul de valori
Surse: `teste/verificare_norme/raport.md` (141 de rânduri, verdicte CONFIRMAT / CORECTAT / DEPENDENT DE OD / NU SE POATE VERIFICA PUBLIC) și `teste/verificare_norme/raspunsuri_proiectant.md` (15 decizii, toate obligatorii; **proiectantul are prioritate** față de verificator). Marcaje în `norme.py`: „[VERIFICAT: sursă]”, „[DECIZIE proiectant 28.10.2026, Îk]”, „[practică, raport #n]”.

| Mărime (`norme.py`) | Valoare | Marcaj / sursă | Înainte |
|---|---|---|---|
| DDR din BMPM / BMPT la locuință, nedeclarat (`LOCUINTA_DDR_BRANSAMENT_IMPLICIT`, `BMPT_RCCB.tip`) | 300 mA, tip AC, instantaneu | DECIZIE proiectant Î1; VERIFICAT ST 3-JT §4.2.4 l–m, ST 4-JT §4.2.6 i | tip A, selectiv (r5 / r8) |
| `BMPM_RCBO_SELECTIV` | False | VERIFICAT ST 3-JT §4.2.4 m | [NEVERIFICAT] |
| `OD_ZBUCLA_IMPLICIT_OHM` / `LOCUINTA_ZB_OD_RURAL_OHM` | \|Z\| 0,30 Ω (R/X = 2) / 0,8 Ω | DECIZIE proiectant Î2 (calculul verificatorului #2–#3) | 0,201 / 0,45 Ω |
| `PROSUMATOR_PI_EXTERNA_KW` | > 27 kW | DECIZIE proiectant Î3 (cerința OD) | idem (verificatorul propunea 30 kVA — neaplicat) |
| `DEZECHILIBRU_FAZE_MAX_KVA`, `MONOFAZAT_S_INVERTOR_AVERTISMENT_KVA` | 16 A ≈ 3,68 kVA, pe kVA | DECIZIE Î4; VERIFICAT Ord. ANRE 228/2018 art. 12(3) | 4,6 kVA (VDE-AR-N 4105); 3,68 kW pe kW |
| `PROSUMATOR_TD_PV_INTOTDEAUNA` + `protectii_cc` / `protectii_ca` | TD-PV la orice putere; întrebare da/nu pe c.c. și c.a. | DECIZIE Î5 | TD-PV doar > 27 kW |
| `DDR_INVERTOR_DOAR_LA_CERERE` | fără DDR implicit (TN); TT neschimbat; Huawei ≥ 100 mA la cerere | DECIZIE Î6; VERIFICAT HW1 / SMA (#93–#94) | 30 mA ≤ 10 kW, 100 mA ≤ 30 kW |
| `OD_IK3MAX_IMPLICIT_KA` | 25 kA (trafo OD ≤ 630 kVA) | DECIZIE Î7 | idem |
| `PRIZA_R_LIMITA_OHM` / `PRIZA_PT_ANRE` | 4 Ω utilizare / branșament; PT „conform ANRE”: 1 Ω + tensiuni de atingere (valoare neclară public → 1 Ω cu notă) | DECIZIE Î8 | 4 / 1 Ω (NTE 001) |
| `TRAFO_GRUPA_CONEXIUNI` | Dyn5 | DECIZIE Î9 | idem |
| `TRAFO_SN_MAX_SIGURANTE_MT_KVA` | 630 kVA | DECIZIE Î10 | 1000 kVA |
| `LOCUINTA_KS_GENERAL` | 0,8 / 0,6 / 0,4 / 0,35 / 0,3 | DECIZIE Î11 | idem |
| `IZ_CABLU_SOLAR_A` (fără grupare) | EN 50618 tab. A.3 | VERIFICAT valorile; DECIZIE Î12 (fără grupare) | idem |
| `PRAG_RACORD_JT_MAX_KVA` | 400 kVA | DECIZIE Î13 | idem |
| `LOCUINTA_I_NEDECLANSARE` (Q nou, In < Ib ≤ 1,13·In) | AVERTISMENT | DECIZIE Î14 (verificatorul propunea BLOCANT — neaplicat) | idem |
| `CONTOR_DIRECT_*` | „furnizat și montat de OD”, fără curent nominal | DECIZIE Î15; VERIFICAT ST 4-JT §4.2.3 / §4.2.8 d | 5(100) A / 5(60) A |
| `FACTOR_R_IK1MIN` / `FACTOR_R_IK1MIN_PE` | fază 1,20 / 1,28; PE 1,38 / 1,60 | VERIFICAT CLC/TR 50480 (#12) | 1,38 / 1,60 pe fază și PE |
| `MCB_I2T_CLASA3_A2S` | tabele B / C separate, ≤ 10 kA | VERIFICAT anexa ZA (#43) | o serie (B), rând extrapolat 25 kA |
| `im_tm` (MCCB TM) | max(10·In; 500 A) la In ≤ 50 A | VERIFICAT ABB / Schneider (#29) | 10·In |
| `catalog_invertoare` Huawei …KTL-M1 | hibrid doar 3…10 kW; 100KTL-M1 = de rețea | VERIFICAT HW2 (#99) | hibrid la orice Pn |
| `PV_UMAX_INVERTOR_IMPLICIT_V` | 1000 V | VERIFICAT fișe Fronius / SMA (#78) | 1100 V |
| `PRIZA_ELECTROD_D_IMPLICIT_M` | 0,060 m (ø60 × 3,6) | VERIFICAT ST 42 anexa 3 (#109) | 0,0635 m |
| `TC_CONSUM_CONTOR_VA` / `K_GRUP_F_DISTANTAT[2]` | 1,0 VA / 0,97 | practică (#71 / #17) | 0,5 VA / 0,98 |
| `RFG_PRAG_TIP_B/C/D_KW` | 1 / 5 / 20 MW | VERIFICAT Ord. ANRE 79/2016 (citare corectată, #83–#85) | [NEVERIFICAT], citat 208/2018 |
| `X_CABLU_OHM_KM`, porțile gG, i2_gg, Ia(5 s) gG, η prize, seriile MCB/MCCB/ACB/gPV/IS/TC/GE, BMPT/BMPM, uk/Pk/P0, RCCB tip AC la BMPT | neschimbate | VERIFICAT (raportul, coloana „Sursă”) | [NEVERIFICAT] |

**Corecturi ale verificatorului neaplicate (contrazic proiectantul sau sunt cosmetice):** PI externă la 30 kVA (#91, Î3); TD-PV la 30 kVA (#90, Î5); DDR invertor implicit după producător (#93 — aplicat doar la cerere, Î6); factori de grupare pentru cablurile solare (#18, Î12); BLOCANT la Q nou cu Ib > In (#126, Î14); notația „CYAbY / ACYAbY” (#9 — cosmetică, ar schimba toate textele de cablu); S_min VE mono 10 mm² (#123 — fără efect, motorul mărește pe Iz).

### H.3 Contractul de date al rezultatului unei ramuri
Câmpurile și unitățile sunt exact cele din `cazuri_golden.json` → `_schema.chei_caz.asteptat`. Motorul întoarce în plus `pasi[]` (șiruri, ca în `calcul`), pentru memoriul de calcul.

### H.4 Cerințe de testare
1. `python3 -c "import sys; sys.path.insert(0,'/home/claude/spec'); import norme; norme._autoverificare()"` trece.
2. Toate cele 74 de cazuri din `cazuri_golden.json` (68 inițiale + 6 adăugate la arbitraj) trec cu toleranțele din `_schema.toleranta_implicita`. BLOCANT/AVERTISMENT se compară ca multiset (cod, nivel, obiect).
3. Toate cele 60 de fraze din `fraze_chat.json` trec (comparare structurală, F.8).
3b. (v1.3) `tests/test_pamant.py` (formule cu valori calculate de mână, η, dimensionare automată, limite pe tip de schemă, TT cu RA = Rp, materiale, memoriu, valori absurde V07/V10/V12) și `tests/test_selectivitate_ddr.py` (regula S + 3×, variantele V43, DDR alese de motor selective — test de proprietate, DDR impuse, validare).
3a. (v1.2) `tests/test_verificare2.py`: câte un caz pentru fiecare defect din verificarea independentă (C2–C10, M1–M4, M8–M12, minore), cu valorile calculate de mână în comentarii.
3c. (r7) `tests/test_interpretor_r7.py`: toate cele 208 fraze r7 (P0/P1 separat), plasa de siguranță pe toate, clasele pe formulări noi; `teste/r7/reverificare.py` (r5 + r6 + r7) fără regresii.
4. Pentru fiecare preset: export → reimport → același model (idempotență) și `lista == șablon`.
5. Test de proprietate (fuzz) pe 10 000 de ramuri aleatoare (P 0,5…2000 kW, L 1…1500 m, toate metodele):
   - nu există niciodată rezultat cu Ip > Iz' fără V02, sau cu ΔU_cum > limită fără V20/V21;
   - nicio protecție în afara seriei;
   - nicio excepție necapturată.
6. Orice modificare a `norme.py` re-rulează 1–5. Valorile golden se schimbă **doar** cu acordul inginerului, iar motivul se notează în istoricul fișierului.

### H.5 Istoric modificări ale specificației
| Data | Versiune | Modificare |
|---|---|---|
| 28.10.2026 | 1.14b norme | Corecturile `teste/verificare_norme/raport_b3.md` §2: Iz Al 16 mm² (9 rânduri), `K_GRUP_F_DISTANTAT` (5–8 sisteme: 0,89/0,89/0,86/0,86), `LOCUINTA_SPD_REZERVA` C40, `PRIZA_ORE_U` platbandă 0,17, curățarea `NEVERIFICAT` și a marcajelor; `PRIZA_ELECTROD_L_IMPLICIT_M` rămâne 3 m (ST 42 Ed. 2025 dă 1,5 m — decizie de proprietar, citarea corectată). Golden B08 (C2 Al 25 → Cu 10, V48), golden v1.14. |
| 28.10.2026 | 1.14 E2 | Deciziile proprietarului: §C.6 pct. 7 (GE — `ge_protectie` „excitatie” ≥ 3·In ≥ 2 s / „echipotential” art. 415.2, BLOCANT cu ambele opțiuni explicate), §C.3 (limitarea la PCC `limitare_PCC_kW`, propunerea Sn × 0,9 × 0,95, V67 AVERTISMENT „pcc”; CEF kW fără invertoare → invertoare implicite presupuse), §B.8 (notația CYAbY / ACYAbY), §I nou (documente și vederi derivate). Constructor: `lista_pe` PTA nu mai e suprascrisă. Teste: `tests/test_motor_e2.py`; golden / texte actualizate la notația CYAbY. |
| 28.10.2026 | 1.13 norme | Verificarea normelor (`teste/verificare_norme/raport.md`) + cele 15 decizii ale proiectantului (`raspunsuri_proiectant.md`): §B.0 (Zbuclă 0,30 / 0,8 Ω, Ik3 25 kA), §B.5 (Im MCCB TM ≥ 500 A la In ≤ 50 A), §B.6, §B.8, §B.11 (I²t clasa 3 pe curbe B/C, ≤ 10 kA), §B.12, §B.14 (factorii CLC/TR 50480 fază / PE), §B.18.1 și §C.1 (DDR BMPM / BMPT AC instantaneu la locuință, V43 cu „declarați blocul real”), §B.19 (contor 1,0 VA), §B.20 și §E.3 (contor fără curent nominal), §C.3 (RfG Ord. 79/2016, Umax 1000 V), §C.4 (TD-PV la toți prosumatorii, întrebarea „protecții pe c.c. / c.a.”, DDR invertor doar la cerere, V71 16 A ≈ 3,68 kVA pe kVA), §C.5 (siguranțe MT ≤ 630 kVA, V61), §C.7 (electrod ø60, PT „conform ANRE”), §C.8 (VE: `limitare_kW` + propunerea V46 `propunere_ve`), §H.2 / §H.2a nou (tabelul de valori). Golden: 49 de cazuri actualizate (`_schema.istoric`, golden v1.13); `fraze_chat.json` F01–F47 (Zbuclă, celula trafo). Interfață: `confLipsa` din regula serverului (BESS fără PV nu mai e blocat), câmpul „Limitare VE”, eticheta „nu intră în deviz” (aparate generice / existente / furnizate de OD — `deviz.motiv_exclus_auto`), titlul TD la tabloul alimentat din TG. Teste: `tests/test_verificare_norme.py`. |
| 27.10.2026 | 1.12 r12-reale | §F.16 nou: texte de proiectant (memorii, ATR, devize) — cablurile legate pe segment (C0 / invertor / MT / tablouri intermediare / tronsoane), invertoarele pe rânduri INVk, racordul existent (PT / TG / stație), capcanele de vocabular (TT de măsură, AAR, „Ir = kA”, „buc N”, „Pi kW”, Pn total, ATR kVA / kW), cheile noi pentru motor (QG, protecția invertoarelor, monitorizare, tablouri intermediare, cablu_MT). `engine/interp_reale.py`; teste `tests/test_interpretor_reale.py`. |
| 12.10.2026 | 1.0 | versiunea inițială |
| 23.10.2026 | 1.11 claude | §F.11 nou: Claude (`claude-opus-5-5`, unealta `intrare_fizica`) e interpretorul principal când există cheie API; schema generată `engine/interp_schema.py` (+ inventar), fuziunea cu regulile locale (I16 întrebările lui Claude, I17 diferențe critice cu ambele variante), cheia (`engine/cheie_api.py`, `/api/setari/cheie`, `/api/chat/cerere`), versiunea web (apel direct din browser, `web/shim.js`). Fără cheie: comportamentul F.1–F.10 neschimbat. Teste: `tests/test_interpretor_claude.py`; `test_interpretor_locuinta::test_llm_locuinta_normalizare` actualizat (setul tipic completat și la Claude). Evaluare simulată: `teste/r8/eval_llm.py`. |
| 23.10.2026 | 1.10 r7-chat | Runda 7 (`teste/r7/*.md`, 68 + 70 + 70 fraze): §F.10 nou — normalizarea formatului înainte de regex (`engine/interp_text.py`), legarea valorii de entitate, PV fără cuvânt-cheie, baterii după model, contradicții numerice, plasa extinsă, chei noi (vezi §F.10). Teste: `tests/test_interpretor_r7.py`; reverificare r5+r6+r7: `teste/r7/reverificare.py`. `test_interpretor_locuinta::test_mono_13kw` actualizat (mono > 9,2 kW → se generează ȘI se întreabă). |
| 23.10.2026 | 1.9 r6-chat | Runda 6 (`teste/r6/*.md`, 113 + 94 + 54 fraze): §F.9 nou — plasa de siguranță (R3, `neconsumat[]`, I15), contradicțiile → I08, clasele reparate și cheile emise (vezi §F.9). Teste: `tests/test_interpretor_r6.py` (nou: toate frazele r5 + r6, plasa pe toate, clasele pe formulări noi). Reverificare: `teste/r6/reverificare.py`. Golden neschimbat. |
| 23.10.2026 | 1.8 r5-chat | Runda 5 de testare din text (`teste/r5/locuinte.md`, `fotovoltaic.md`, `industrial.md`, 158 de fraze), §F: ordinea tipurilor (prosumator > CEF/BESS > GE > locuință > branșament > PT > tablou; BMPT / „din PT” / „faza PT” = atribute; „tg birouri P+2” = tablou; casă + PV = prosumator; kVA pe plecare ≠ PT); combinații → I14; grupuri de invertoare cu mărci / modele (Pn din cod, fără împărțire la n), module, stringuri, gPV, BESS cu marcă, limitarea injecției, racord TG/BMPT/PT cu Q și Ik, PT existent; prosumator: `invertoare[]`, `bess`, P aprobată / evacuată, `L_coloana_m` / `L_inv_m`; liste: coadă de atribute (L, cosφ, pornire, material, pozare), liste fără „plecări”, `n_circuite`, cascade „NUME valoare (LISTA)”, CP, kVA pe plecare, cablu impus, coduri „td-2 160 A”, „In= L=”, autocorectura „? nu,”; rețeaua și schema de pământ nu se presupun în tăcere la nicio schemă (I02 / I08 / presupunere declarată), sursa tabloului declarată; locuință: „pompa caldura”, „PC aer-apă”, multiplicatori („3 aparate AC”, „2 băi cu boiler … fiecare”, „5 circuite prize”), „monofazată” la receptor, Pi / Pa, „7 kW aprobat”, negație / „gaz”, setul tipic fără plită / cuptor nenumite. Chei noi emise: `schema_pamant`, `RA_ohm`, `retea` (tablou, CEF), `origine` (tg_existent, bmpt), `Ik3_sursa_kA`, `cablu.S_fortat/N_fortat/n_fortat`, `plecari[].pornire/cosfi/n_circuite/cablu`, `trafo_izolatie`, `celule_mt`, `masura`, `L_GE_ATS_m`, `In_Q_retea_A`, `sursa_retea`, `limitare_injectie_kW`, `racord`, `racord_In_Q_A`, `Ik3_TG_kA`, `pt_existent`, `cablu_C0`, `modul`, `string`, `gpv_In_A`, `invertoare[].producator/model`, `bess.producator/model`, prosumator `invertoare[]`, `invertor`, `bess`, `baterie`, `P_aprobata_kW`, `P_evacuata_kW`, `L_coloana_m`, `L_inv_m`; branșament `Q_In_A` (Q declarat lângă P). `fraze_chat.json` F54: `genereaza_cu_intrebare` (kW împărțit la n → întrebare). Teste: `tests/test_interpretor_r5.py` (nou), `test_interpretor_locuinta.py` (set tipic fără plită). Reverificare: `teste/r5/reverificare.py`. Golden neschimbat. |
| 23.10.2026 | 1.7 | Runda 4c de testare (`teste/r4/proiectant_c.md`, `teste/r4/verificator_c.md`, `teste/r4/ux_c.md`), §C.8: M-c1 — Q branșament în afara seriei → V05 cu `camp`, Q ignorat, calcul continuat cu Q presupus (treapta superioară / limita blocului); m-c4 — `Zb_OD_ohm` / `RA_ohm` / `Ik3_OD_kA` invalide → V07 cu `camp`, ignorate (`locuinta.prevalideaza`, apelată din `scheme._ruleaza`); N11 — Zb rurală „presupus (zonă rurală, [NEVERIFICAT]) — se confirmă cu OD / ATR”, ipotezele Ik3 / Zb fără „(din ATR)” (implicit: „presupusă — se confirmă cu OD / ATR”, declarat: „(declarat)”), și pentru celelalte tipuri de schemă; M-c3 — V43 „ve_dc” (AV TN-C-S, BLOCANT TT), câmp nou `alimentare.DDR_bransament_tip`, `norme.LOCUINTA_DDR_TIPURI`; m-c5 / UX C3 — `ETICHETE_RECEPTOR` + `ETICHETE` centrale, `fara_chei_receptor`, V34 / V12 „retea” cu remedieri corecte, `receptor_eticheta`; ks fără „după 0 receptoare” (ks = 1); m-c6 — `norme.LOCUINTA_S_MAX_CIRCUIT_DU_MM2` = 16 (ramura B.21: `S_max_dU`, rezultat `dU_plafonat_mm2`), V20 cu „mărește coloana”; N16 — prizele / celelalte categorii pe niveluri; N17 — VE minim 4 mm² (tabelul receptorilor), dimensionat pe Iz / ΔU / Ik; N13 — cosφ în ipoteze grupat, cu receptorul și „presupus” / „declarat” corect (ramura B.21: `_cosfi_eticheta`, `_cosfi_implicit`); memoriu: denumirea receptorului. Golden neschimbat. `tests/test_locuinta.py` (VE 4 mm², textele presupunerilor, TT cu VE → `DDR_bransament_tip` „B”) actualizat, `tests/test_locuinta_r4c.py` nou. |
| 22.10.2026 | 1.6 | Runda 4b de testare (`teste/r4/proiectant_b.md`, `teste/r4/verificator_b.md`, `teste/r4/ux_b.md`), §C.8: N2 — bugetul ΔU al coloanei 1,5 % (coloana se mărește întâi, `tinta_dU` în ramura B.21, `coloana.marit_buget_dU`); m8 — coloana pe faza cea mai încărcată; m-n3 — repartizarea pe curentul de calcul, ordinea fixată (3F, impuse, monofazatele descrescător, inclusiv din 4P), `faze.dezechilibru_calc_pct` / `repartizare`; N5 / m-n5 — V46 AV „q_pres” / „pa_pres”, `alimentare.Pa_presupus`, mesajele BLOCANTE pe Q presupus, Q peste bloc continuă cu limita blocului; P1-4 — iluminat max. 2 pe DDR, separat pe niveluri deduse din nume (`grupe_DDR[].nivel`); P2-1 — V43 agregat; P2-6 — „30 mA tip A” (§E.3 rccb / rcbo la IΔn ≤ 30 mA; 300 mA neschimbat); N4 / m-n2 — `SPD.protectie_rezerva` (MCB C25 ≤ In Q), `spd_ca` cu `prot_tip` (implicit gG); P1-10 — `alimentare.zona` (rural 0,45 Ω [NEVERIFICAT]); m-n4 — chei `DDR` necunoscute V12 AV, `retea: ""` → V07 la locuință; N3 — TT: `alimentare.C1_conductoare`, `coloana.conductoare` „L + N”, `PE` = „fara”, cablu fără PE, `PE_origine` / `legatura_BPE`; UX 12 — rezultate parțiale (`blocat`, `circuite_blocate`, protecție cu In pe circuitele blocate — M-n1); UX 13 — mesaje fără chei interne, cheia `camp` a verificării. Memoriu: rezerva SPD, conductoarele coloanei, bugetul ΔU. Golden neschimbat. `tests/test_locuinta.py` (V43 agregat; K02 → Q C40, 38,31 A) și `tests/test_locuinta_r4.py` (textul presupunerii de pozare) actualizate, `tests/test_locuinta_r4b.py` nou. |
| 22.10.2026 | 1.5 | Runda 4 de testare (`teste/r4/proiectant.md`, `teste/r4/verificator.md`), §C.8: C1 — V46 pe faza cea mai încărcată (Ib de calcul pe fază cu ks; BLOCANT > 1,13·In sau > In cu sarcini continue, AV între), `faze.L*_calc_A` / `L*_continuu_A` / `faza_max`; P0-1 — cu P aprobată, Ib general / coloană / Q general din Pa, Pc informativ (V46 AV), V46 „pa”; P0-2 — Q nedeclarat presupus ≥ Ib, peste limita blocului V46 BLOCANT „bloc”; P0-3 — TT: protecția la defect prin DDR, V30 „TT” pe circuite și coloană, `protectie_defect`, memoriu; M1 — DDR ≤ 30 mA pe toate circuitele (V49 „idn”, toate receptoarele „obligatoriu”); M2 — V40 „loc” (MCB / RCBO / Q general MCB > In Q; IS / RCCB nu); M4 — `NameError` în `_ruleaza` (intrare non-obiect → V07); grupe DDR (5 circuite, iluminat separat, 2P pe fază / 4P cu 3F, circuit singur → RCBO, saună proprie, RCCB ≥ 25 A); valori implicite (pompă de căldură 3,5 / 6 kW electric, cuptor C16, centrală / poartă 1,5 mm², ks 0,8/0,6/0,4/0,35/0,3); saună `cablu_nota`; textele ks fără IEC 61439-2 (și V10 „ks ∈ (0; 1]” la toate schemele); coloana `alimentare.pozare_coloana` / `cablu.metoda`; capacitatea condiționată RCCB / IS (V33 „cond”); SPD `configuratie`; minore m2–m5, m9, m11, m12; `rez["retea"]` normalizat. **§A.1: rețeaua obligatorie** și la `bransament` / `prosumator` (lipsă / null → V07 BLOCANT „retea”, nu se mai presupune „tri”; cerință explicită a utilizatorului). Golden: doar intrările B04–B24 primesc `"retea": "tri"` (rezultatele așteptate neschimbate); `test_verificare2` / `test_integrare` / `test_pamant` / `test_texte` / `test_cef_racord` / `test_deviz`: `"retea": "tri"` la intrările de branșament, R2-NC3[retea] așteaptă acum V07. `tests/test_locuinta.py` actualizat la valorile v1.5, `tests/test_locuinta_r4.py` nou. |
| 22.10.2026 | 1.4 | §C.8 nou: tipul de schemă „locuinta” (`locuinta.py`) — bilanț cu ks pe receptoare generale / sarcini continue, branșament existent/nou + coloană, Q general (IS / MCB), SPD T2, grupe DDR 30 mA (max 4 circuite, grupe dedicate, VE tip B propriu), repartizare greedy pe faze, TT; metoda de pozare B2 (Cu) în `norme.IZ`; `In_minim` și `cablu.S_min` în ramură; Q_In_A la BMPM; §D V46, V47, V49; memoriul: capitolul „Bilanț și repartizarea pe faze”, etichete pentru câmpurile locuinței. Golden neschimbat. |
| 22.10.2026 | 1.3 UX | `reviews/r3/ux-flux-proiectant.md` P0-2: §C.3 pct. 12 (racord în TG existent, `Q_TG`, V44; C0 dimensionat ori de câte ori are lungime, ΔU invertor cumulat cu C0; cablurile invertoarelor din `cablu` global și pe grup); §C.7 presupunerile prizei cu valorile adoptate; memoriu cap. 1 cu etichete; §D mesaje fără obiect repetat, singular după „1”, persoana a II-a singular. Golden neschimbat. |
| 22.10.2026 | 1.3 R5 | `verif2/RAPORT_VERIFICARE_R5.md`: M5-1 (ψ distinct electrozi / platbandă, L_p = (n − 1)·a + racord 5 m — Rp nu mai e subestimat: exemplul 2 → 11 electrozi, 3,76 Ω), M5-2 (R_limita_ohm doar coboară limita normată, altfel V12 BLOCANT), M5-4 (selectivitate DDR și în timp: S → S neselectiv; TT: intrarea fără DDR sub amonte S, altfel bloc diferențial reglabil cu Δt 0,15 s; circuite instantanee; nota 3 din DDR-urile reale), minore (`ore_u`, `ref`, cantități întregi). Golden R02: doar textul mesajului V43. `test_verificare2` / `test_integrare`: Q1/QG TT fără DDR propriu, plecări/invertoare 100 mA. M5-3/M5-5 (deviz, dublarea PS în listă) sunt în afara motorului. |
| 22.10.2026 | 1.3 | §C.7 nou (priza de pământ, `pamant.py`: electrozi în linie + platbandă, ψ, η, limite 4/1 Ω și TT 50 V/IΔn, dimensionare automată până la 30 de electrozi, materiale, V37; TT: RA = Rp calculat); §B.18.1 nou (selectivitatea DDR în serie, `ddr.py`, V43); §C.2 pct. 13 (IΔn Q1/QG ales selectiv: 300 S → 100 S → 30; plecarea spre TD fără DDR propriu când seria e epuizată); §B.1.1 câmpuri noi (`priza`, `Q1_DDR`, `plecari[].DDR` dict, `DDR_amonte_selectiv`, `IdN_amonte_mA` și în TN); §A.3 pct. 3; §D (V37, V43); §G.1 nota 2; §H.2 pct. 16–19; §H.4 pct. 3b. Golden: R02 (V43 AVERTISMENT nou, RCBO BMPM instantaneu, `_schema.istoric`). `test_verificare2`: Q1/QG TT 300 → 100 mA, plecări/invertoare 100 → 30 mA. |
| 12.10.2026 | 1.2 R3 | `verif2/RAPORT_VERIFICARE_R3.md`: N3-C1 (metoda explicită în pământ păstrată, monopolare D1/D2; trecerea în aer scrisă în ipoteze), N3-C2/N3-M2 (TT în toate schemele, DDR din amonte verificat, selectivitate DDR ≤ IΔn/3, test-proprietate), N3-M1 (GE: V50 peste 250 A fără PT, rețea din PT propriu, V62). |
| 12.10.2026 | 1.2 R2 | reverificarea (`verif2/RAPORT_VERIFICARE_R2.md` §3): N-C1 (bloc diferențial pe Q_G, C3 în ambele regimuri), N-C2 (TT: DDR pe fiecare circuit, V34), N-C3/N-M3 (null = absent, enumerări invalide V12/V10), N-M2 (PEN în cablu), N-M4 (servicii proprii gG/MCB pe cablu mic; PE în cablu înainte de FY; I²t limitat gG/MCB), N-M5 (cabluri monopolare metoda F, ≤ 6 sisteme), `verifica_cablu()` pentru modelele manuale; minore (toleranță V64 0,1 %, „socket” = prize, ks la branșament declarat, ΔU pornire). Golden: T13, G01–G03 (`_schema.istoric`). |
| 12.10.2026 | 1.2 | verificarea independentă (`/home/claude/verif2/RAPORT_VERIFICARE.md` §3): §A.1/A.2 (rețea și schema de legare la pământ validate, V12/V27/V28, nota 3 din valoarea reală); §B.0 (Zb coerent cu Ik3, Zb ca modul, lungimi GE, pornire motor); §B.1.1 (câmpuri noi); §B.2 (validarea completă a intrării); §B.3.1 nou (motor cu pornire directă, V22/V23); §B.4 (gG 120 kA, bloc diferențial > 125 A, DDR general S); §B.12 (ΔU bară > 5/8 % și invertor > 3 % → V20 BLOCANT după mărire); §B.14 (V15); §C.1 (Icu MCCB BMPTi 25 kA, cablu C2 din `cablu`, Q_In_A, bmpt_fortat); §C.2 pct. 10–11 (DDR pe orice circuit de prize ≤ 32 A, V29; fără plecări V07; V24); §C.3 pct. 11 (V64, S = max, CEF mono, M4, β); §C.5 pct. 10 (Isd/tsd/Ii); §C.6 pct. 6 (Q_G Ir ≤ In_G, ACB, C1–C3, Icu); §D coduri noi V15, V23, V24, V28, V29, V64; §E.3; §G.1. Golden: vezi `_schema.istoric` (Icu gG 120, Icu Q BMPTi 25, motoare, GE). |
| 12.10.2026 | 1.1 | arbitraj (`spec/ARBITRAJ.md`): §B.1.1 câmpuri noi de contract (Ib_A, S_kVA, circuite_finale, origine, pt_Sn_kVA, Sn_GE_minim_kVA); §B.2; §B.15 timpi TT și regula sursei unice Ia gG; §C.2 pct. 10 DDR 30 mA pe prize; §C.5 pct. 6 textul celulei trafo; §C.6 pct. 5 seria GE; §E.3 reguli de compunere; §G.3 nota de branșament; §F.2, F.5, F.6, F.7 (R1, R2, I13); §H.4 număr de cazuri. Modificările valorilor golden sunt în `_schema.istoric`. |
