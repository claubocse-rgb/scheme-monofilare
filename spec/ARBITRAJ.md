# ARBITRAJ: discrepanțe spec ↔ golden ↔ implementare (12.10.2026)

**Arbitru:** inginerul care a scris specificația.
**Surse:** `spec/DISCREPANTE.md`, `spec/DISCREPANTE_CHAT.md`.
**Fișiere de date modificate:**
- `spec/SPEC_TEHNIC.md`: v1.1, istoricul în §H.5;
- `engine/calc/norme.py`;
- `tests/date/cazuri_golden.json`: `_schema.istoric`, 74 de cazuri;
- `tests/date/fraze_chat.json`: `_schema.istoric`.

**Verificare.** Valorile noi sau modificate au fost recalculate cu calculatorul de referință și verificate independent pentru ΔU, Iz' și Ib ≤ Ip. Rezultat: 125 de ramuri, 0 abateri. Câteva valori le-am verificat și de mână:
- B24: Ib = 25 000/692,82 = 36,08 A; ΔU = 1,57 %;
- G03: In_G = 115,47 A, MCCB 125 A cu Ir 118,75 A;
- T16: Ik3 la bara de 400 kVA = 15,22 kA, identic cu P02.

**Motor față de golden-ul nou:** B20, P07, X01 și B24 trec deja. Pică doar cazurile care cer cod nou: B23, K03, T15, T16, G01–G03. Mai pică testele de test-cod: xfail strict și numărul de cazuri.

## Decizii

| # | Punct | Decizie și argument | Ce s-a schimbat (date/spec) | Cine modifică codul |
|---|---|---|---|---|
| D-01 | B20, t în TT | **Greșea testul.** SR HD 60364-4-41 tab. 41.1: în TT, circuitul de distribuție are 1 s (TN: 5 s). Calculatorul de referință aplica TN peste tot. | golden B20 `C2.t_deconectare_s` 5 → **1,0**; SPEC §B.15 explicitează regula TT (propagare, raportarea câmpului, Ia informativ, deconectare prin DDR) | **teste**: scoaterea B20 din `DISCREPANTE` (`tests/test_golden.py`); motor: nimic |
| D-02 | P07, „None A” | **Greșea testul.** O siguranță MT peste 1000 kVA nu există (§C.5), iar „None” nu e text RO (§E.2). Se acceptă textul motorului. | golden P07 `celula_trafo` = „separator de sarcină + siguranțe MT (calibru nedefinit peste 1000 kVA)”; SPEC §C.5 pct. 6 definește cele 3 valori posibile ale câmpului (`"intreruptor"` rămâne cod, textul descriptiv vine din E.3, ceea ce rezolvă și obs. 2) | **teste**: scoaterea P07 din xfail; motor: nimic |
| D-03 | X01, texte E.3 | **Greșea testul.** Șirurile golden amestecau șablonul TM cu EL și omiteau „capac sigilabil”. Se aplică E.3. Regulă nouă: textul de listă = `denumire + ", " + caracteristici`, iar fragmentele fără parametru se omit. | golden X01 `text_lista_regenerat` Q/TC (identice cu ieșirea motorului); SPEC §E.3 „Reguli de compunere” + exemplele de referință | **teste**: scoaterea X01 din xfail; motor: nimic |
| Obs-1 | gG Ia(5 s) 50/80 A față de porți | **Ambele sunt corecte, dar se fixează o regulă:** Ia(5 s) = max(VDE NB.1 ; poarta Imax(5 s) din SR EN 60269-1). VDE (260/440 A) e conservator (cere un Ik1 mai mare), deci se păstrează. Valorile nu se schimbă. | `norme.py`: comentariu + `_autoverificare()` impune Ia(5 s) ≥ poartă; SPEC §B.15 | nimeni |
| Obs-2 | `celula_trafo = "intreruptor"` | Rămâne cod (fără diacritice); textul pentru listă/desen vine din E.3. | SPEC §C.5 pct. 6 | nimeni |
| Obs-3 | nota G.3 vs X02 | **X02 e referința.** Șablonul G.3 a fost rescris după X02. Ir **nu** se deduce din limitele blocului (deducerea 0,85·125 = 106,25 era o invenție). Ir apare doar dacă e în model. X02 primește `Q_Ir_A = 106,25` explicit. | golden X02 `intrare.parametri.Q_Ir_A`; SPEC §G.3 | **motor**: `texte.note_generate` citește `Q_Ir_A` și elimină deducerea Ir din bloc. „(Pa = … kW din ATR)” doar cu Pa cunoscut, altfel „(Pa din ATR)” |
| F26 | „al” cu literă mică | Se acceptă excepția implementată (token izolat la sfârșit de segment, după o lungime sau după „cablu”). | SPEC §F.2 pct. 4 | nimeni |
| F07/F29 | `actiune` cu întrebare | **Regula R1:** se generează **și** se întreabă ⇒ `genereaza_cu_intrebare`, indiferent de cauză. F07 era inconsecvent. | fraze F07 `actiune` → `genereaza_cu_intrebare`; SPEC §F.7 R1 | **interpretor**: R1 (F07 cu V51 + întrebare ⇒ `genereaza_cu_intrebare`) |
| F29/B18 | tip BMPT inexistent | **Ambele rămân valabile, în contexte diferite (regula R2):** din text ⇒ I13, tipul nu se transmite motorului, se generează cu tipul din ST și se întreabă; din model/formular ⇒ `bmpt_fortat` ⇒ V50 BLOCANT (B18). | SPEC §F.7 R2 + I13; textul presupunerii din F29 menționează I13 | **interpretor**: mesajul presupunerii conține „I13”; **teste**: cuvinte-cheie noi (vezi mai jos) |
| F03/B11 | `masura_ceruta` | Se adaugă în B11; rezultatul nu se schimbă (la Ib = 240,6 A se alege oricum BMPTi-250, fără V51). | golden B11 `intrare.masura_ceruta = "semidirecta"` | nimeni |
| F14/C02-C03 | „Chat cef_300” | Eticheta se mută pe **C03** (PT 630 kVA adăugat de interpretor, I11). C02 rămâne caz de motor (intrare fără PT ⇒ V66 BLOCANT). | golden: descrierile C02 și C03 (valorile nu se schimbă) | nimeni (perechea frază↔golden devine F14↔C03) |
| F16/C05 | `cablu_pcs`, `L_pcs_m` | Rămân în C05: fără ele, PCS-ul de 500 kW în pământ D1 nu se poate dimensiona (V01), iar cazul ar testa altceva. Se marchează formal. | golden C05 `campuri_nu_din_text = ["cablu_pcs","L_pcs_m"]`; cheie documentată în `_schema` | **teste** (opțional): `NU_DIN_TEXT` se citește din `campuri_nu_din_text` în loc să fie scris în cod |
| F05 | „mărit pentru ΔU” ca presupunere | Interpretorul nu dimensionează (§F.1). Elementul se mută în `rezultat_cheie`. Presupunerea devine regula „limita ΔU la bara TE = 3 %”. | fraze F05; SPEC §F.6 | **interpretor**: textul presupunerii; **teste**: cuvinte-cheie |
| F35, F15, F16, F13 | presupuneri cu alegeri de motor | **Se acceptă**, ca estimări declarate, calculate cu aceleași constante din `norme.py`. Motorul rămâne autoritar. | SPEC §F.6 | nimeni |
| F53 | „BMPT 200A” | **Câmp nou `Ib_A`.** P echivalent (124,7 kW) e pseudo-precizie: ar apărea pe planșă ca „Pa = 124,7 kW”, putere pe care ATR-ul nu o conține. | SPEC §B.1.1, §B.2; golden **B23** nou; fraze F53 `intrare_motor = {Ib_A: 200, L_coloana_m: 40}`, presupunere nouă | **motor**: branșament cu `Ib_A`; **interpretor**: emite `Ib_A` în loc de `P_kW` |
| F59 | „BMPT 25 kVA” | **Câmp nou `S_kVA`**: Ib = S/(√3·400), fără cosφ; cosφ 0,9 doar pentru ΔU. | SPEC §B.1.1, §B.2; golden **B24** nou (motorul trece deja); fraze F59 `intrare_motor = {S_kVA: 25}` | **interpretor**: emite `S_kVA` în loc de P = 22,5 kW; motor: nimic |
| F33 | „TD hală: circuite …” | **Câmp nou `circuite_finale`**: plecări cu rol „final”, MCB B/C, Cu PVC C, 25 m, 0,4 s; prizele primesc **DDR 30 mA tip A** (SR HD 60364-4-41 art. 411.3.3). | SPEC §B.1.1, §C.2 pct. 10; golden **K03** nou; fraze F33 `intrare_motor`, presupunere nouă | **motor**: `circuite_finale` + câmpul `DDR` pe plecările de prize; **interpretor**: textul presupunerii |
| F43 | „TG … din PT propriu” | **Câmp nou `origine = "pt_propriu"`** (+ opțional `pt_Sn_kVA`): limite ΔU 6/8 %, fără DDR în amonte. Fără Sn: Ik3/Zb implicite ⇒ AVERTISMENT. Cu Sn: sursa e trafo-ul și secțiunea se mărește automat pentru deconectare (T16: C1 120 → 150 mm²). | SPEC §B.1.1; golden **T15** (fără Sn), **T16** (cu Sn 400 kVA); fraze F43 `intrare_motor`, presupunere nouă | **motor**: `origine`, `pt_Sn_kVA`; **interpretor**: textul presupunerii (emite deja `origine`) |
| F11 | „pat de cabluri” ⇒ grupare | Se acceptă: „pat de cabluri”, „jgheab” sau „scară” cu mai mult de o plecare ⇒ plecările pe același pat. | SPEC §F.5 | nimeni |
| F42 | serie GE | **Serie nouă `GE_SN_KVA`** + `ge_sn_minim()`: Sn ≥ P/cosφ ⇒ 60 kW → **80 kVA** (nu 100 kVA, care venea din seria trafo). Rezultatul GE primește `Sn_GE_minim_kVA`; mesajul V86 indică minimul. | `norme.py`; SPEC §C.6 pct. 5, V86; golden G01, G02 (câmp + mesaj), **G03** nou (GE 80 kVA, fără V86); fraze F42 întrebarea „cel puțin 80 kVA” | **motor**: `Sn_GE_minim_kVA` + mesajul V86; **interpretor**: folosește `norme.ge_sn_minim` (80 kVA) |

## Lista exactă a modificărilor de cod cerute

### Motor (`engine/calc/`)
1. `scheme.py`, branșament: acceptă `Ib_A` (Ib direct; cosφ doar la ΔU; fără „Pa” în notă). Mai multe surse de putere simultan ⇒ V12 BLOCANT. Caz: B23.
2. `scheme.py`, tablou: `circuite_finale = true` ⇒ plecări cu rol „final” (§B.1.1), receptor implicit „forță”, Cu PVC C 30 °C, L 25 m; Ip_aval estimat pe seria MCB. Caz: K03.
3. `scheme.py`/`ramura.py`: circuitele finale de prize primesc `ddr_ramura` și câmpul `"DDR": {"IdN_mA": 30, "tip": "A"}` (§C.2 pct. 10).
4. `scheme.py`, tablou: `origine = "pt_propriu"` (limite 6/8 %, `ddr_amonte = false`) și `pt_Sn_kVA` (context trafo §B.13/B.14). Cazuri: T15, T16.
5. `scheme.py`, GE: câmpul `Sn_GE_minim_kVA = norme.ge_sn_minim(P)` și mesajul V86 „— GE minim {Sn} kVA”. Cazuri: G01–G03.
6. `texte.py`, nota G.3: Ir din `Q_Ir_A` (sau Ir calculat), fără deducere din limitele blocului; „(Pa = … kW din ATR)” doar cu Pa cunoscut.

### Interpretor (`engine/interpretor.py`)
1. Regula R1: F07 ⇒ `genereaza_cu_intrebare`.
2. Branșament „N A” ⇒ `intrare_fizica.Ib_A` și branșament „N kVA” ⇒ `intrare_fizica.S_kVA`, ambele în loc de `P_kW` (F53, F59).
3. GE: întrebarea folosește `norme.ge_sn_minim` (80 kVA pentru 60 kW) (F42).
4. Textele noi ale presupunerilor (F05, F29 cu „I13”, F33 cu „DDR 30 mA tip A”, F43, F53, F59), exact ca în `fraze_chat.json`.

### Teste (`tests/*.py`): de modificat de programatori, nu de mine
1. `test_golden.py`: scoaterea B20, P07 și X01 din `DISCREPANTE` (acum sunt XPASS strict); `test_numar_cazuri` 68 → **74**.
2. `test_interpretor.py`:
   - intrări noi în `CUVINTE_CHEIE` pentru presupunerile/întrebările noi:
     - F05: „limita ΔU la bara TE = 3 % …”;
     - F29: „I13: …”;
     - F33: cele 2 texte noi;
     - F43: al doilea text;
     - F53, F59: textele noi;
     - F42: întrebarea nouă;
   - verificarea opțională a `intrare_motor` (subset egal în `intrare_fizica`);
   - opțional: `NU_DIN_TEXT` citit din `campuri_nu_din_text`.

Starea curentă a testelor după modificarea datelor:
- golden: 64 trec;
- pică B23, K03, T15, T16, G01, G02, G03 (cod motor nou);
- XPASS strict: B20, P07, X01;
- pică `test_numar_cazuri`;
- interpretor: 8 fraze pică până la modificările de mai sus.
