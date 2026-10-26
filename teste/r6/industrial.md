# Runda 6 — rol „industrial” (TG, PT, GE+ATS, combinații) — 23.10.2026

**Scor: 4/10** (runda 5: 3/10).

**Pe scurt:** frazele din runda 5 sunt aproape toate reparate: 43 corecte din 54 (în r5: 16). Pe 54 de fraze noi, cu formulări puțin diferite, interpretorul cade însă din nou: 11 corecte · 15 parțiale · 28 greșite. **11 dintre ele sunt P0**: schemă greșită, fără BLOCANT, exportabilă. Reparațiile din r5 au acoperit formulările testate, nu clasa de probleme.

Ce iese bine:
- motorul de calcul și planșele, când intrarea e bine înțeleasă (PT, Y/Δ, VFD, TT, mono, cascade simple);
- refuzurile și blocantele cu explicație: V27, V40, V61, V86, I05.

Fișiere:
- `teste/r6/industrial/fraze.json` — 54 de fraze noi, cu rezultatul real și verdictul;
- `reverificare_r5.json` — cele 54 de fraze din r5, rerulate;
- `fraze_in.py`, `ruleaza.py`, `verdicte.py` — scripturile;
- `png/` și `svg/` — 94 de planșe randate (r5_NN, r6_NN).

Rulare: `python3 teste/r6/industrial/ruleaza.py r5|r6`. Nu s-a modificat nimic în engine/, tests/, static/.

## 1. Reverificare r5 (54 de fraze): 43 C · 10 P · 1 G

**Reparat:**

| Problema din r5 | Unde se vede acum |
|---|---|
| TT la tablou (P0-1) | #42, #47: DDR 100 mA pe plecări, RA·IΔn în note |
| „monofazat” la tablou (P0-2) | #53: aparate 2P, L+N+PE; #11 dă I08 |
| kVA-ul PT-ului luat drept putere a GE (P0-3) | #36, #38, #49: GE corect + întrebare „desenez doar GE+ATS?” |
| Sarcina vitală a GE | #32: 73 kW; #50: 35 kW |
| „kVA” pe o plecare inventa un PT (#19) | S convertit în P |
| Cifra din codul TD lipită de calibru (#16, #44) | Calibrul se citește corect |
| „tg birouri P+2” devenea locuință (#4) | Tablou cu 6 plecări |
| Plecări pierdute (lot P1-8) | Se parsează: „stea-triunghi”/„convertizor” (#15: KM linie + KΔ/KY + releu pe ramura Δ, corect), cascada cu „;” (#13), listă fără „plecari” (#43), „15 CP” (#48), „In=100A L=60m” (#51), „cosfi 1” (#20), „3x185+95 Al” (#52) |
| „PT” ca origine | #1, #5, #52 (+ întrebare kVA); „faza PT” (#40) nu mai devine PT; cartușul e completat |
| Date ignorate | Celule intrare-ieșire + măsură MT (#23), trafo uscat (#28), cablu 3×150+70 impus (#41: V02 BLOCANT corect), L GE–ATS 15 m (#33, verificat în SVG), „retea 125A” (#31), pozare per plecare (#44) |
| Strung/freză ca motor | Contactor + releu termic la toate motoarele |
| Multiplicatori de circuite | „Iluminat 1…5”, „Prize 1…4” |
| „cca 150A” | 160 A + întrebare |
| GE 500 kVA din PT (#34) | Întrebare despre sursă în loc de V50 |
| Suprapuneri de casete (f01, f12, f14) | Dispărute |

**Rămas din r5:**
- #17 „1 000 m” dă tot I03 „Valoarea 1 nu are unitate” (P2).
- Iluminatul de hală iese în continuare pe separatoare 3P cu fuzibil, nu pe MCB 1P curba B (#14).
- Motor 18,5 kW DOL pe MCB C40 în sub-tablou (#12).
- Consumatorii vitali ai GE nu devin plecări. Pompele de incendiu trec prin DDR-G 300 mA (#32, #50).
- **Sursa TG nedeclarată nu se întreabă.** Se calculează ca BMPT presupus și se marchează „PRESUPUS” pe planșă, într-un font ilizibil. V31 avertizează corect că DDR-ul presupus nu contează la deconectare. Rămâne totuși o generare fără întrebare (P1).

## 2. Fraze noi (54): 11 C · 15 P · 28 G — 11 P0, 26 P1, 6 P2

| # | Frază | Așteptat | Obținut | Verdict | Grav. |
|---|---|---|---|---|---|
| 1 | TG hala sudura, din PT propriu 400 kVA TN-S, plecari: aparat sudura 3x25 kVA, compresor 22kw 40m, pod rulant 2x7,5kW, iluminat hala 6 circuite 16A, prize 400V 4x32A | tablou, origine pt_propriu 400, TN-S; sudura 3 plecari S=25 kVA; compresor motor; pod rulant 2 motoare; iluminat 6 circ MCB B16; prize 4x32A | TG din PT 400 TN-S corect; sudura 3×25 kVA→22,5 kW; dar iluminatul hală iese pe 6 separatoare 3P cu fuzibil 16 A + CYABY 5×6 (nu MCB 1P B16), pod rulant nerecunoscut ca motor | parțial | P2 |
| 2 | tg-1 atelier tamplarie din tgd existent 60m cablu cyaby 5x25, plecari: circular 5,5 kw, rindea 4 kw, exhaustor 7,5kw stea triunghi, iluminat 2 kw monofazat, prize 3 circ 16A | tablou origine tg_existent L60 CYABY 5x25 impus; circular/rindea motoare; exhaustor Y/D; iluminat 1P; prize 3x16A cu DDR | „iluminat 2 kw monofazat” face TOT tabloul monofazat; P TG=2 kW, Q1=16 A din „3 circ 16A”; prizele dispar; CYABY 5×25 impus nepreluat (doar Cu); Y/D pe motor 1~ → V12/V40 BLOCANT | greșit | P1 |
| 3 | TD-2 hala, alimentat din TG, 3x400V TN-S, 8 circuite iluminat B10, 6 circuite prize 16A cu DDR 30mA, 2 prize trifazate 32A | tablou TD-2 origine tg_existent; 8 iluminat B10; 6 prize 16A DDR 30mA; 2x32A 3P | „8 circuite iluminat B10, 6 circuite prize… 2 prize trifazate 32A” → nicio plecare, Q1=16 A; V07 BLOCANT | greșit | P1 |
| 4 | TE-P1 birouri monofazat 230V din TG parter 25m, iluminat 4 circ 10A, prize 6 circ 16A, AC 2 x 3,5 kW | tablou mono, origine tg_existent L25; 4 il B10, 6 prize B16+DDR, 2 AC 3,5 kW; aparate 1P+N/2P | mono + origine tg_existent L25 corect, dar „4 circ”/„6 circ” nu se multiplică („Iluminat 4 circ” = o plecare); AC 3,5 kW pe ACYABY 3×35 Al, iluminat 10 A pe CYABY 3×10 | parțial | P1 |
| 5 | tablou pompe statie epurare: 2 pompe submersibile 11 kW cu softstarter, suflanta 15 kW cu convertizor, iluminat 1 kW; alimentare din PT 250 kVA, 120 m Al | tablou origine pt_propriu 250, L 120 Al; 2 pompe softstarter; suflanta VFD; iluminat | „alimentare din PT 250 kVA” devine PLECARE de 225 kW cu 3×400 A gG; cele 2 pompe softstarter dispar; Q1 = 500 A pe un trafo de 250 kVA (In 361 A) — fără blocant, se exportă | greșit | P0 |
| 6 | TG supermarket TN-C-S din BMPT 250A: HVAC chiller 75 kW, frig comercial 45 kW, iluminat 25 kW, prize casa marcat 10 circuite 16A, TD-depozit 63A 40m | tablou BMPT, Q1 250; 5 tipuri plecari, 10 circ prize; chiller motor/compresor | supermarket → tip LOCUINȚĂ cu circuite de casă inventate (baie, boiler, centrală); iluminat 25 kW pe 1P+N B125 + CYY-F 3×50; chiller, frig, 10 circ. prize și TD-depozit pierdute; doar întrebare despre Pa | greșit | P0 |
| 7 | tg ferma, din retea, plecari: hranitor 3 CP, ventilatoare 12 x 0,75 kw, pompa apa 4 kW 120m, iluminat grajd 3 circuite | tablou; 3 CP=2,2 kW; 12 vent; pompa L120; iluminat fara putere → intrebare/presupunere declarata | 3 CP→2,21 kW, 12 ventilatoare OK; „iluminat grajd 3 circuite” (fără putere) dispare fără mesaj; hrănitor 2,2 kW nerecunoscut ca motor; MCCB 16 A pe motoare de 0,75 kW | parțial | P1 |
| 8 | TG 3x400V plecari motor 55kW pornire directa 25m, motor 22 kW soft-starter 30m | 2 motoare: DOL 55 kW (ΔU pornire!), 22 kW softstarter; sursa nedeclarata → intrebare | 2 motoare corecte (DOL 55 kW KM 95 A + releu; soft-starter 22 kW) dar ambele numite „Motor”; nicio verificare ΔU la pornirea DOL 55 kW pe sursă presupusă BMPT; sursa nu se întreabă | parțial | P2 |
| 9 | TG hala, din PT propriu 1000 kVA uscat, In 1600 A, plecari TD-1 400A 80m, TD-2 400A 120m, TD-3 250A, TD-4 160A, compresor 90 kW VFD | tablou origine pt 1000; Q1 1600 ACB; 5 plecari; compresor VFD | TG din PT 1000 kVA, Q1 1600 A, 4 TD + compresor VFD corecte; Q1 1600 A desenat ca MCCB (uzual ACB) | corect | P2 |
| 10 | TG cu 3 plecari: TD-1 63A, TD-2 40A, TD-3 32A, schema TT, priza de pamant 10 ohm, din BMPT | TT, RA 10, DDR pe plecari (sau DDR general S), origine bmpt | TG cu 3 plecări TT → schemă BRANȘAMENT BMPTd-100 cu TE generic; plecările dispar; în TT se desenează separarea PEN pe BN | greșit | P0 |
| 11 | tablou TT ferma RA 50 ohm, plecari prize 3x16A, iluminat 2x10A | TT RA 50; retea nedeclarata, sarcina mica (~68A?) → intrebare retea; DDR | TT RA 50 + DDR pe plecări corect; rețeaua trifazată presupusă FĂRĂ întrebare și fără presupunere afișată (Σ 68 A) | parțial | P1 |
| 12 | TG TN-C cu plecari TD-1 100A, TD-2 63A | TN-C: PEN, fara DDR, S≥10 Cu/16 Al; sau intrebare/avertisment | TN-C → V27 BLOCANT cu explicație (PEN după DDR-ul BMPT); acceptabil | corect | — |
| 13 | TG schema IT, plecari TD-1 63A | IT in afara domeniului → refuz/intrebare | „schema IT” ignorată tăcut → TN-C-S desenat, fără întrebare/refuz | greșit | P0 |
| 14 | TG din PT, TN-C-S, plecari TD-1 160A, TD-2 100A | origine PT fara kVA → intrebare kVA; TN-C-S | origine PT fără kVA → întrebare; TN-C-S | corect | — |
| 15 | TG alimentat din BMPT trifazat 3x63A, plecari: pompa 5,5kw, iluminat 2kW, prize 3,5 kW | Q1 63, origine bmpt; pompa motor; prize DDR | „TG alimentat din BMPT 3x63A, plecari: pompa, iluminat, prize” → schemă BRANȘAMENT (BMPTd-100) cu TE generic; plecările pierdute | greșit | P0 |
| 16 | TG plecari TD-1 16A, TD-2 10A | sarcina mica (26 A) — rețeaua NU se presupune → intrebare mono/tri | sarcină mică: întreabă mono/tri („Rețeaua nu se presupune”) — reparat | corect | — |
| 17 | tablou general monofazat 230V, plecari: iluminat 1,5 kW, prize 2 kW, centrala 0,2 kW, pompa caldura 9 kW | tablou mono; pompa caldura 9 kW mono ~43A; Q1 ~63A 2P; avertisment/limita mono | mono corect, aparataj 2P; dar iluminat 1,5 kW pe ACYABY 3×95 Al cu MCB B10 (absurd, nu intră în bornă); pompă căldură tratată ca motor DOL cu contactor | parțial | P1 |
| 18 | tablou monofazat cu motor 7,5 kW trifazat | contradictie mono vs motor trifazat → I08/intrebare | „monofazat cu motor 7,5 kW trifazat” → fără I08; P=7,5 kW pe tablou, fără plecări, V07 | greșit | P1 |
| 19 | TG trifazat cu plecari monofazate: iluminat 3 kW, prize 3,6 kW, boiler 2 kW, plus pompa 4 kW trifazata | tri; 3 plecari 1P+N, pompa 3P motor | „TG trifazat cu plecări monofazate…” → rețea MONO, plecări pierdute, V07 | greșit | P1 |
| 20 | TG 230V, plecari TD-1 63A 3P, TD-2 32A | contradictie 230V vs 3P → intrebare | „230V … TD-1 63A 3P” nedetectat ca contradicție; TD-2 32 A devine Q1; TD-1 pe 3×(ACYABY 3×185); V40 BLOCANT | greșit | P1 |
| 21 | TG hala: TD-1 160A 70m (pompa 30kW, compresor 18,5 kW, iluminat 3 kW); TD-2 100A 50m (prize 6x16A, sudura 20 kVA); TD-3 63A | cascada 3 TD, copii cu motoare; sudura kVA | cascadă cu paranteze și „;” corectă; motoare 30 / 18,5 kW DOL pe MCB C63/C40 (risc declanșare la pornire); TD-urile fără întreruptor-separator general de intrare | parțial | P1 |
| 22 | TG -> TD-P (parter) 63A 20m cu iluminat 3 circ, prize 4 circ; TD-E1 (etaj) 40A 35m cu iluminat 2 circ, prize 3 circ, AC 5 kW | cascada TD-P, TD-E1 cu copii; circuite fara putere → presupus/intrebare | cascada cu „->” și „cu …” → nicio plecare, P=5 kW, Q1=63 A, V07 | greșit | P1 |
| 23 | TG birouri din TG existent cladire, alimentare CYY-F 5x35 30m, plecari TE-P1 32A, TE-P2 32A, TE-P3 32A, server 16A cu UPS 10 kVA | origine tg_existent; cablu impus CYY-F 5x35; 4 plecari; UPS mentionat | CYY-F 5×35 impus desenat ca CYABY 5×35; „server 16A cu UPS 10 kVA” → nume „server 16A cu UPS”, P din kVA (16 A ignorat) | parțial | P2 |
| 24 | PT zidit 2x630 kVA, plecari TG1 800A, TG2 800A | 2 trafo → in afara domeniului / intrebare; NU un trafo 630 tacut | „PT zidit 2x630 kVA” → UN trafo 630; 2×800 A pe Q3 1000 A; doar V62 avertisment; se exportă | greșit | P0 |
| 25 | PTAB 630 kva cu trafo uscat, celule: 2 linie, masura, protectie trafo cu intreruptor, masura pe MT, plecari TG1 800A 30m, TG2 250A 60m, baterie condensatoare 150 kvar | pt 630 uscat; celule 2L+M+T intreruptor; masura MT; compensare 150 kvar | PTAB 630 uscat cu celule + „baterie condensatoare 150 kvar” → tip CEF, refuz I02 „lipsesc invertoarele” | greșit | P1 |
| 26 | post trafo aerian PTA 160 kVA pe stalp, masura pe JT directa, plecari 2 x 100A | PTA 160; masura directa la 231 A nepermis → semidirecta/intrebare | PTA pe stâlp desenat cu celule MT de interior (celulă linie + CLP); „măsură JT directă” ignorată (pune TC 250/5) fără mesaj | parțial | P1 |
| 27 | PT 400 kVA ulei 20/0,4, uk 4%, Scc retea 350 MVA, plecari TG 630A 15m | Scc 350 MVA folosit; plecare 630A (In trafo 577A) → avertisment | Scc 350 MVA ignorat (500 MVA presupus); TG 630 A > Q3 598 A → V40 BLOCANT (corect) | parțial | P2 |
| 28 | PT 1250 kVA, celula trafo cu siguranta, plecari TD-1 1000A, TD-2 800A | 1250 kVA cu sigurante MT → avertisment (>1000 kVA intreruptor) / respecta cerinta cu nota | 1250 kVA cu siguranțe MT → V61 BLOCANT cu explicație | corect | — |
| 29 | PT 630 kVA 6/0,4 kV plecari TD-1 400A | MT 6 kV (nu 20 kV) — sigurante 6 kV / intrebare | „6/0,4 kV” ignorat: PT desenat 20 kV, siguranțe 24 kV SF 40 A (la 6 kV ar fi ~100 A); fără mesaj | greșit | P0 |
| 30 | post de transformare 400 kVA, tensiune MT 20 kV, masura MT, plecari TG hala 630A 25m, TD exterior 63A 200m, GE 150 kVA cu ATS pe TD-vital 100 kW | combinatie PT + GE → intrebare explicita; nu GE 400 | PT 400 + GE 150: întrebare explicită, GE 150 (nu 400), P 100 kW | corect | — |
| 31 | GE 150 kVA cu ATS in TGD, sursa retea din BMPT 200A, consumatori vitali 90 kW, cablu GE 25 m | ge_ats Sn150, retea bmpt QR 200, P 90, L GE 25 | „sursa retea din BMPT 200A” → sursă TGD, QR 160 A în loc de 200 A; „cablu GE 25 m” ignorat (20 m implicit) | parțial | P1 |
| 32 | grup electrogen 80kVA, AAR, alimentare normala din PT 400kVA, sarcina 55 kW, L GE-AAR 20m | ge_ats 80, sursa pt 400, P 55, L 20 | GE 80 / PT 400 / P 55 / L 20 — toate preluate | corect | — |
| 33 | GE 40 kVA monofazat cu ATS, sarcina 25 kW | GE mono 40 kVA → 174A; ATS 2P; sau intrebare (GE mono >20 kVA rar) | „GE 40 kVA monofazat” → GE trifazat 3P+N, ATS 4P; fără întrebare | greșit | P0 |
| 34 | GE 250 kVA in paralel cu reteaua, sincronizare | in afara domeniului → refuz | GE în paralel cu rețeaua (sincronizare) → desenează ATS (comutare), întreabă doar sursa; trebuia refuz (în afara domeniului) | greșit | P1 |
| 35 | GE 200kVA ATS pentru pompe incendiu 2 x 45 kW stea triunghi si hidrofor 7,5 kW | P vital 97,5 kW, pornire Y/D; pompe incendiu fara DDR; sursa retea → intrebare | P 97,5 kW corect, dar pornirea Y/D și cele 3 receptoare se pierd („Consumatori”); pompele de incendiu trec prin DDR-G 300 mA | parțial | P1 |
| 36 | GE cu ATS pt TG existent 400A, sarcina vitala 150 kW | Sn GE lipsa → intrebare/refuz (I02) | Sn GE lipsă → I02 | corect | — |
| 37 | GE 100kVA ATS, retea din TGD existent | sarcina lipsa → intrebare; sursa tg_existent | sarcina lipsă: Ib = In GE presupus, fără întrebare | parțial | P2 |
| 38 | TG din PT propriu 630 kVA, coloana 2x(NA2XY 4x240) 90 m, In 400A, plecari TD-1 160A, TD-2 160A | cablu impus 2x NA2XY 4x240 Al XLPE; Q1 400 | „2x(NA2XY 4x240)” → se pierde „2x”: 1×240 la 400 A → V02/V03 BLOCANT fals | greșit | P1 |
| 39 | TG plecari: TD-1 63A cablu CYABY 5x10 80m, TD-2 32A CYY-F 5x6 30m | cablu impus pe plecare; 5x10 la 63A → BLOCANT Iz | cabluri impuse per plecare → plecările dispar, primul calibru devine Q1, cablul 5×10 merge pe coloană; V07 | greșit | P1 |
| 40 | TG plecari TD-1 100A cu cablu 4x16 Cu | cablu impus subdimensionat → BLOCANT | „TD-1 100A cu cablu 4x16 Cu” → cablul impus e pus pe COLOANĂ (5×16), TD-1 primește 2×(4×120 Cu); blocant, dar pe cablul greșit | parțial | P1 |
| 41 | TG TN-S si TT, plecari TD-1 40A | contradictie schema pamant → intrebare | „TN-S si TT” nedetectat; TN-S ales tăcut (întreabă doar mono/tri) | greșit | P1 |
| 42 | PT 630 kVA cu plecare TG 1600A | plecare > In trafo 909 A → blocant/intrebare | plecare 1600 A pe PT 630 → V40 BLOCANT | corect | — |
| 43 | TG 3 plecari: TD-1 63A, TD-2 40A, TD-3 25A, TD-4 16A | I05 3 cerute 4 gasite | I05 3 vs 4 | corect | — |
| 44 | tablou monofazat 3x400V | contradictie I08 | „monofazat 3x400V” → I02 în loc de I08 (refuză oricum) | parțial | P2 |
| 45 | TG din BMPT 100A plecari TD-1 125A | plecare 125 > sursa 100 → blocant/intrebare | „TG din BMPT 100A plecari TD-1 125A” → schemă BRANȘAMENT; TD-1 125 > 100 nesemnalat | greșit | P0 |
| 46 | GE 100 kVA ATS sarcina 120 kW | V86 refuz | V86 | corect | — |
| 47 | TG hala alimentat din PT propriu si din BMPT, plecari TD-1 63A | doua surse → intrebare | „din PT propriu si din BMPT” (2 surse) → BRANȘAMENT BMPTd-100, fără întrebare | greșit | P0 |
| 48 | tg hala prod, sursa tgd exist., td-1 125 a/60 m, td-2 80a/45m, td-3 50A/30m, tn-s | origine tg_existent; 3 plecari cu L (format a/m); TN-S; 50A nestandard? | format „125 a/60 m” + „sursa tgd exist.” → plecările dispar, Q1 = 125 A, L col = 60; V07 | greșit | P1 |
| 49 | TG; plecari: 3 x TD 63A (TD-1..TD-3) + 2 x pompa 7,5kW | 3 TD 63A + 2 pompe motor | „3 x TD 63A (TD-1..TD-3) + 2 x pompa 7,5kW” → o plecare „3 x TD 63A” goală; V07 | greșit | P1 |
| 50 | TD-2 din TG 50 m CYABY 5x16, 3x400V, plecari: masina spalat industriala 12 kW, uscator 9 kW, calandru 6 kW, iluminat 4x10A | tablou TD-2, origine tg, cablu impus 5x16; 3 utilaje + 4 il | „3x400V” citit ca secțiune → cablu impus 400 mm² (V13 BLOCANT); CYABY 5×16 pierdut | greșit | P1 |
| 51 | TE-P1 230V din TG 20m, 8 circuite: 3 iluminat 10A, 4 prize 16A, 1 boiler 2kW | tablou mono 8 circuite; il B10 x3, prize B16 x4 DDR, boiler | „8 circuite: 3 iluminat 10A, 4 prize 16A, 1 boiler 2kW” → nicio plecare, Q1 10 A; V07 | greșit | P1 |
| 52 | TG hala din PT 630 kVA, compensare factor putere baterie condensatoare 120 kvar automata, plecari TD-1 250A, TD-2 160A | origine pt 630; plecare BC 120 kvar (~173A, Q ≥1,43·In) | TG + „baterie condensatoare 120 kvar” → tip CEF, refuz I02 invertoare | greșit | P1 |
| 53 | TG 125A din BMPT, SPD T2, plecari: incarcator EV 22 kW, incarcator EV 11 kW, iluminat parcare 2 kW 150m | Q1 125; SPD T2; EV cu DDR tip B / A-EV 6mA; il L150 | TG 125 A cu 2 încărcătoare EV + iluminat → BRANȘAMENT BMPTi-250, TE generic, P=22 kW; EV (DDR tip B / 6 mA c.c.) pierdute | greșit | P0 |
| 54 | TG fabrica, TN-S din PT 1600 kVA, motor compresor 160 kW cu softstarter, motor 75 kW stea-triunghi, TD-uri: TD-1 400A, TD-2 250A | origine pt 1600; 2 motoare mari; 2 TD | „TN-S din PT 1600 kVA” devine plecare de 1440 kW (ACB 2500 A), TD-1/TD-2 pierdute, TD-1 400 A → Q1; V40 BLOCANT | greșit | P1 |
## 3. Planșe verificate „ca la avizare” (13)

| Planșa | Judecată |
|---|---|
| r5_01 TG din PT 630 | **Bună.** Q1 MCCB 250 / 237,5 A, TD-uri pe separator-fuzibil, compresor 37 kW MCCB 63 + KM 65 + releu 62,8 A, SPD T1+T2. Fără suprapuneri. |
| r5_15 motoare | Y/Δ corect ca aparataj (KM linie 65 A, KΔ 32, KY 18, releu 29,4 A pe ramura Δ). **Plecarea Y/Δ e desenată cu UN cablu 4×25 „3+N+PE”**, deși lista spune „2 cabluri spre motor” (P1). Motoarele primesc N inutil. Cablul VFD e desenat ACYABY, iar lista cere „ecranat”. Textul sursei e ilizibil (font micșorat). |
| r5_23 PTAB 400, măsură MT | **Bună.** Celule L + M + T, FV ZnO, contor indirect, fără TC pe JT. Bucla intrare-ieșire e simplificată la o singură celulă „2×”. Etichetele cablurilor plecărilor au ~1 mm (ilizibile). |
| r5_32 GE 250 + ATS | Desen clar. Sarcinile vitale sunt comasate în „Consumatori”. **Pompele de incendiu sunt alimentate prin DDR-G 300 mA** (nepermis, P1). Ieșirea TAR nu are aparat propriu (protecție doar prin QR/QG). |
| r5_42 TT | DDR 100 mA pe plecări, RA·IΔn = 3 V. **Q1 și bara TG se bazează pe un DDR amonte PRESUPUS** (notă 3). În TT aceasta e o lipsă de protecție la contact indirect până la DDR-urile plecărilor (P1). |
| r5_53 mono | **Corectă și lizibilă:** 2P, L+N+PE, DDR 30 mA pe prize. |
| r6_01 TG 17 plecări (A1) | Fără suprapuneri, dar desenul ocupă jumătatea de sus a unui A1. Textele sunt ~1,5 mm. Iluminatul e pe 6 separatoare 3P cu fuzibil 16 A și CYABY 5×6. Coloana „Simbol” din listă e trunchiată (poz. 12). |
| r6_05 stație epurare | **P0 vizibil:** plecare „alimentare din PT” 3×400 A gG; **Q1 500 A pe trafo 250 kVA**; pompele lipsesc; iluminat 1 kW pe fuzibil 2 A + ACYABY 4×16. |
| r6_06 supermarket | **P0:** planșă de LOCUINȚĂ. **Iluminat 25 kW pe MCB modular 1P+N B125** (nu există) + CYY-F 3×50 sub un bloc DDR 30 mA de 135 A. Boiler, baie, centrală sunt inventate. |
| r6_10 TG TT din BMPT | **P0:** BMPTd-100 + „TE consumator generic”. Planșa spune TT, dar desenează separarea PEN → N + PE pe BN (incoerent). |
| r6_17 mono cu pompă de căldură | Aparataj 2P corect. **Iluminat 7,2 A pe ACYABY 3×95 Al cu MCB B10** (secțiune absurdă, nu intră în bornă). Centrală 0,2 kW pe 3×6. Q1 80 A față de C63 aval: selectivitate slabă. |
| r6_21 cascadă 3 TD | Topologie corectă și lizibilă. **TD-1/TD-2 fără întreruptor-separator de intrare.** Motoare 30 / 18,5 kW DOL pe MCB C63/C40. Jumătatea de jos a A1 e goală. |
| r6_24 „2×630 kVA” | **P0:** un singur trafo 630. 2 × 800 A pe Q3 1000 A, doar avertisment V62. Etichetele cablurilor TG1/TG2 sunt ilizibile. |

Constatări comune pe planșe:
- (P2) Textul sub titlul sursei („SURSĂ NEDECLARATĂ — presupus…”) e scalat până la ilizibil. Tocmai informația critică nu se poate citi.
- (P2) Etichetele verticale ale cablurilor groase (2×, 3×) sunt de ~1 mm.
- (P2) Pe A1 desenul nu umple foaia.
- Selectivitatea e tratată corect ca avertisment V41/V42 („confirmă cu tabelele producătorului”).
- Contactoarele și releele sunt dimensionate corect (AC-3 ≥ Ib, Ir = Ib).
- SPD T1+T2 apare peste tot, inclusiv la TD din TG (ar fi T2).

## 4. Top P0 rămase (planșă greșită, fără BLOCANT)

1. **Tablou numit explicit „TG” devine BRANȘAMENT** când textul conține „din BMPT” (#10, #15, #45, #47, #53). Plecările se înlocuiesc cu un TE generic.
   - Remediere: „TG/tablou/TD” + listă de plecări are prioritate; „din BMPT” înseamnă `origine=bmpt`.
2. **„din PT X kVA” în mijlocul listei devine PLECARE** de X·0,9 kW (#5, #54).
   - În #5 rezultă Q1 500 A pe trafo 250 kVA, fără blocant. Lipsește verificarea „In Q1 ≤ In trafo” la `origine=pt_propriu`.
3. **Tablou comercial/industrial devine locuință** (#6 „supermarket”), cu circuite inventate. Generatorul de locuință acceptă un MCB 1P+N B125.
4. **Date explicite ignorate tăcut:**
   - schema IT (#13);
   - 6/0,4 kV (#29);
   - 2×630 kVA (#24);
   - GE monofazat (#33).
   - Toate trebuie refuzate sau întrebate, niciodată înlocuite cu valoarea implicită.

## 5. Top P1

1. **Liste de plecări pierdute (V07):**
   - „8 circuite: 3 iluminat 10A, 4 prize 16A…” (#3, #51);
   - „4 circ”/„6 circ” (#4);
   - „->” + „cu …” (#22);
   - „125 a/60 m” (#48);
   - „3 x TD 63A (TD-1..TD-3)” (#49);
   - un cablu per plecare (#39);
   - „cu plecări monofazate” (#19).
2. **Contradicții nedetectate:**
   - mono + motor trifazat (#18);
   - 230 V + 3P (#20);
   - TN-S + TT (#41);
   - „monofazat 3x400V” dă I02, nu I08 (#44);
   - un singur „monofazat” pe un receptor face tot TG-ul mono (#2).
3. **Cabluri impuse greșit:**
   - „2x(NA2XY 4x240)” pierde „2x”, cu blocant fals (#38);
   - „3x400V” citit ca secțiune 400 mm² (#50);
   - cablul plecării pus pe coloană (#40);
   - CYY-F înlocuit cu CYABY (#23).
4. **„baterie condensatoare … kvar” trimite la tip CEF**, cu refuz „lipsesc invertoarele” (#25, #52).
5. **GE:**
   - funcționarea în paralel e desenată ca ATS (#34);
   - Y/Δ și receptoarele vitale se pierd (#35);
   - **DDR-G 300 mA pe alimentarea pompelor de incendiu** (#32, #35);
   - „BMPT 200A” devine TGD 160 A (#31).
6. **Dimensionare absurdă pe circuite mici:**
   - ACYABY 3×95 / 3×35 Al la 7–17 A (#17, #4);
   - MCCB 16 A pe motoare de 0,75–1,5 kW;
   - motoare DOL ≥ 18,5 kW pe MCB curba C în sub-tablouri.
7. **Sursa TG și rețeaua:**
   - sursa nedeclarată nu se întreabă (BMPT presupus);
   - în TT, Q1 se sprijină pe acest DDR presupus;
   - la #11 rețeaua tri e presumată fără întrebare (la #16 se întreabă — inconsecvent).
8. **PTA pe stâlp desenat cu celule MT de interior;** „măsură JT directă” ignorată (#26).

## 6. Comparativ cu runda 5

| | r5 | r6 (aceleași fraze) | r6 (fraze noi) |
|---|---|---|---|
| Corecte | 16 | 43 | 11 |
| Parțiale | 12 | 10 | 15 |
| Greșite | 26 | 1 | 28 |
| P0 exportabile | 9–10 | 0 | 11 |

Reparațiile sunt reale. Motorul de calcul (Y/Δ, TT, mono, combinații GE/PT) a crescut vizibil. Interpretorul generalizează însă slab: aceleași clase de defecte reapar pe formulări noi.
- Tipul se alege după un cuvânt („BMPT”, „supermarket”, „kvar”).
- „din PT X kVA” se lipește de listă.
- Datele explicite neacceptate (IT, 6 kV, 2×trafo, GE mono) se înlocuiesc tăcut cu implicite.

Recomandare: o plasă de siguranță generică în interpretor. Orice cifră sau unitate din text care nu ajunge în `intrare_fizica`, și orice cuvânt-cheie de domeniu nerecunoscut (IT, kvar, 6 kV, 2×…, paralel), trebuie să producă o întrebare, niciodată o generare tăcută.
