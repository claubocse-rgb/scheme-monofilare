# Discrepanțe SPEC_TEHNIC.md ↔ cazuri_golden.json ↔ norme.py

> **Stare (runda 2, SPEC v1.1):** toate cele trei discrepanțe de mai jos au fost **rezolvate prin arbitraj**
> (`spec/ARBITRAJ.md` D-01, D-02, D-03; observațiile 1–3 la Obs-1…Obs-3). Golden-ul v1.1 (74 de cazuri) a fost
> corectat de inginer; `tests/test_golden.py` nu mai are niciun xfail și trece 74/74. Nicio discrepanță nouă în runda 2.

**Context:** implementarea `engine/calc/` (12.10.2026). Rezultat: 65 de cazuri trec, 3 sunt marcate `xfail` în
`tests/test_golden.py` (strict: dacă golden-ul sau codul se schimbă și cazul începe să treacă, testul cere scoaterea
marcajului). Testul **nu** a fost modificat ca să treacă. Valorile golden se schimbă doar cu acordul inginerului (SPEC §H.4 pct. 6).

În toate cele trei cazuri, verificările (cod, nivel, obiect) și `blocheaza_export` coincid cu golden-ul. Diferă doar câmpul indicat.

---

## DISCREPANTA-01 — B20: timpul de deconectare în schema TT

| | |
|---|---|
| Caz | B20 „Branșament 15 kW în schema TT cu RA = 200 Ω” |
| Câmp | `asteptat.C2.t_deconectare_s` |
| Valoare așteptată | **5,0 s** |
| Valoarea motorului | **1,0 s** |

**Calculul, pas cu pas:**
1. `intrare.schema_pamant = "TT"`.
2. C2 alimentează tabloul consumatorului: receptor „tablou”, deci circuit de **distribuție**, nu circuit final (SPEC §C.1, C2; §B.15).
3. SPEC §B.15: „TN, U0 = 230 V: … circuit de distribuție … 5 s. **TT: 0,2 s / 1 s**, cu DDR obligatoriu (V34).” SPEC §A.2 trimite tot la TT.
4. `norme.T_DECONECTARE_S[("TT", "distributie")] = 1.0` (SR HD 60364-4-41, tab. 41.1).
5. Așadar t = **1 s**.

Restul câmpurilor coincid. Ia = 10·In = 10·25 = 250 A la MCB C (nu depinde de t). Ik1min = 603,24 A ≥ 250 A, deci V30 INFO.
V34 BLOCANT: RA·IΔn = 200·0,3 = 60 V > 50 V.

**Ce spune SPEC-ul:** 1 s (§B.15, §A.2, norme). Golden-ul a folosit valoarea TN (5 s).

**Propunere:** în golden, `B20.asteptat.C2.t_deconectare_s = 1.0`. Dacă inginerul vrea ca, în TT, coloana să se verifice ca în TN
(deconectarea fiind asigurată oricum de RCCB-ul BMPT), atunci §B.15 trebuie să spună asta explicit, iar `norme.T_DECONECTARE_S` nu se mai folosește pentru TT.

---

## DISCREPANTA-02 — P07: textul celulei trafo cu siguranțe impuse la 1600 kVA

| | |
|---|---|
| Caz | P07 „PT 1600 kVA cu celulă trafo cu siguranțe MT” |
| Câmp | `asteptat.celula_trafo` |
| Valoare așteptată | `"separator de sarcină + siguranțe MT None A"` |
| Valoarea motorului | `"separator de sarcină + siguranțe MT (calibru nedefinit peste 1000 kVA)"` |

**Calculul, pas cu pas:**
1. Sn = 1600 kVA > `TRAFO_SN_MAX_SIGURANTE_MT_KVA` = 1000 kVA. Siguranțele sunt impuse, deci **V61 BLOCANT** (emis; coincide cu golden-ul).
2. `norme.TRAFO_SIGURANTA_MT_A` conține doar 100…1000 kVA, deci `.get(1600)` = `None`.
3. Generatorul golden-ului a formatat `None` direct în text („None A”). Nu există un calibru de siguranță MT care să poată fi afișat.

**Ce spune SPEC-ul:** §C.5 pct. 6 prevede siguranțe numai până la 1000 kVA. SPEC §E.2 cere text în română, generat din parametri. „None” nu este o valoare.

**Propunere:** în golden, textul motorului sau omiterea calibrului (`"separator de sarcină + siguranțe MT"`). Exportul este oricum blocat de V61.

---

## DISCREPANTA-03 — X01: textul listei regenerat nu urmează șabloanele E.3

| | |
|---|---|
| Caz | X01 „Lista de echipamente contrazice desenul” |
| Câmp | `asteptat.text_lista_regenerat.Q` și `.TC` |

**Q** (parametri: 4P, In 500 A, Ir 475 A, Icu 36 kA):
- așteptat: `Întreruptor automat MCCB 4P, In 500 A, Ir 475 A (0,95·In), Icu 36 kA, 400 V c.a., SR EN 60947-2`
- motor: `Întreruptor automat MCCB 4P, In 500 A, declanșator electronic LSI, Ir = 0,95·In = 475 A, Icu 36 kA`

Calculul:
1. In = 500 A ≥ 320 A, deci declanșator **electronic** (SPEC §B.5 pct. 2; `MCCB_TM_IN_MAX = 250`).
2. Șablonul E.3 pentru „MCCB EL / ACB”:
   - denumire: `Întreruptor automat MCCB {poli}P, In {In} A, declanșator electronic LSI`
   - caracteristici: `Ir = {k}·In = {Ir} A, Isd = …, tsd …, Ii = …, Icu {Icu} kA`
   - k = 475/500 = 0,95
   - Isd, tsd și Ii lipsesc din parametri și nu se inventează.
3. Șirul din golden nu corespunde niciunui șablon E.3:
   - formatul „Ir 475 A (0,95·In)” nu există în E.3;
   - coada „400 V c.a., SR EN 60947-2” aparține șablonului **MCCB TM**;
   - lipsește „declanșator electronic LSI”.

**TC** (parametri: 600/5 A, cl. 0,5S, 5 VA):
- așteptat: `… Fs 5, 0,72 kV, SR EN 61869-2 — 3 buc.`
- motor: `… Fs 5, 0,72 kV, capac sigilabil, SR EN 61869-2 — 3 buc.`

Șablonul E.3 pentru TC are caracteristicile `0,72 kV, capac sigilabil, SR EN 61869-2 — {n} buc.`. Golden-ul omite „capac sigilabil”.

Verificările V80 Q și V80 TC (BLOCANT) coincid. Și textele de desen regenerate coincid cu cele stocate: „4P · 500 A · Ir 475 A”
(fără Isd, care lipsește din parametri) și „3 × 600/5 A · cl. 0,5S”.

**Ce spune SPEC-ul:** §E.1 pct. 1 și §E.3: „lista == șablon(parametri)”. Testul E.3 este „obligatoriu; orice nepotrivire pică build-ul”.

**Propunere:** fie se regenerează șirurile golden din E.3, fie se modifică E.3 (și apoi `texte.py`) după forma din golden. Oricare ar fi
varianta aleasă, E.3 ar trebui să precizeze explicit forma textului „listă” într-o singură coloană (aici: `denumire + ", " + caracteristici`).

---

## Observații fără xfail

1. **`norme.py`, porțile gG la 50 A și 80 A.** `GG_IA_5S_A[50] = 260` și `GG_IA_5S_A[80] = 440` (DIN VDE 0100-600 Bbl. NB.1). În același
   fișier, poarta Imax(5 s) din `GG_PORTI_A` este 250 A, respectiv 425 A. Poarta de 80 A este marcată „verificat [M]”.
   - Conform porții, siguranța trebuie să funcționeze sub 5 s la 425 A, deci Ia(5 s) ≤ 425 A.
   - Valoarea 440 A este conservatoare (cere un Ik1 mai mare), deci nu produce rezultate nesigure. Cele două surse rămân totuși inconsecvente.
   - Golden-ul folosește 440 A (T05 „Pompe”). Nu am modificat `norme.py`. Recomand alegerea unei singure surse.
2. **Celula trafo > 1000 kVA.** Golden-ul cere valoarea `"intreruptor"` (cheie fără diacritice). Am respectat-o, ca să nu dublez
   discrepanța 02. Textul pentru listă și desen se generează separat, din șablonul E.3 „Celulă trafo (întreruptor)”.
   Recomand ca în rezultat să existe un câmp descriptiv în română.
3. **Nota G.3 de branșament.** Șablonul G.3 („… Ir = {Ir} A} reglat la Pa = {Pa} kW din ATR și sigilat; …”) diferă de forma din X02
   („… In 125 A reglat la Ir = 106,25 A (Pa din ATR); …”). SPEC numește X02 „exemplul de referință”, așa că am implementat forma X02,
   cu „(Pa = {Pa} kW din ATR)” când Pa este cunoscut. Fără Ir și fără Pa în model (cazul X02), Ir = 0,85·125 = 106,25 A. Este cea mai
   mică treaptă TM strict peste limita inferioară a blocului (BMPTi-250 se alege pentru Ib > 100 A), pentru că 0,80·125 = 100 A nu e > 100 A.
