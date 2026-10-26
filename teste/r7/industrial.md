# Runda 7 — testare industrială (TG/TD/PT/GE) — inginer proiectant

Data: 2026-10-23 · Flux testat: `interpretor.interpreteaza(text)` (fără LLM, ca `/api/chat`) → `constructor.genereaza` → `validare.valideaza` → `layout.build` → `render_svg` → PNG (cairosvg, 2400 px).
Fișiere: `teste/r7/industrial/fraze.json` (70 de fraze noi), `pNN.png/.svg` (51 de planșe), `rezultate_brute.txt` (ieșirea completă per frază), `res.json`, `run.py` (harness, rulare: `python3 teste/r7/industrial/run.py [id…]`).
Nu s-au citit tests/ și nici frazele din rundele anterioare. engine/, tests/ și static/ nu au fost modificate.

## Nota: 4,5 / 10 (r6: 4/10)

| | Număr | % |
|---|---|---|
| Corect | 19 | 27 % |
| Parțial | 23 | 33 % |
| Greșit | 28 | 40 % |
| **P0** | **1** | |
| **P1** | **35** | |
| P2 (verdict principal) | 15 (+ observații P2 la cazurile corecte) | |

Pe scurt: **motorul de dimensionare și desenul sunt bune** când interpretorul înțelege fraza. PT cu un trafo, MT 6/10/15 kV, măsura MT/JT, Y/Δ, convertizor, soft-starter, TT cu DDR, GE+ATS din PT/BMPT/TGD și pompe de incendiu fără DDR (când sunt numite explicit) ies avizabile, cu observații. **Interpretorul rămâne punctul slab.** Formatările uzuale (liniuțe, tab-uri, enumerări „1) 2)”, „a câte”, „2 x 18,5 kW Y/D”, „N de X kW”, CEE, prescurtări) cad în „Nu am folosit…” sau în refuz. Sursa „din BMPT 70 kW” devine o plecare fantomă. Cascadele TG→TD→TE nu sunt suportate. Contradicțiile numerice (kW vs A, 20 vs 15 kV, 250 A vs 160 A, PT 160 kVA vs 300 kW, 400 kW din BMPT) nu sunt detectate. Plasa de siguranță funcționează (nimic nu e desenat „pe tăcute” din textul neînțeles), dar acoperă prea multe fraze clare, care ar fi trebuit înțelese.

---

## P0 (1)

1. **#31 Pompe de incendiu alimentate prin DDR.** Fraza: „tablou pompe incendiu: pompa principala 45 kW, pompa rezerva 45 kW, pompa pilot 2,2 kW, alimentare din doua surse retea si GE 150 kVA”. Contextul „tablou pompe incendiu” este aruncat („Nu am folosit…”). Consumatorii nu sunt marcați `siguranta`, iar planșa (p31) are **bloc diferențial 300 mA pe ramura GE**, un singur circuit „Consumatori 92,2 kW”, cablu ACYABY (nu rezistent la foc) și releu termic neprecizat. În plus, pompa de rezervă e însumată cu cea principală (92,2 kW în loc de 45 + 2,2). Încalcă P118/3 și I7 (alimentarea pompelor de incendiu nu trece prin DDR). Detectarea funcționează doar când apare literal „pompe incendiu” pe consumator (#30 e corect).

## P1 sistemice (în ordinea impactului)

| # | Problemă | Fraze |
|---|---|---|
| S1 | **Parser de liste fragil.** Liste cu liniuțe pe rânduri (#3), tab-uri (#68), enumerări „1) … 2)” (#69: „Valoarea 1 nu are unitate”), „15 plecari a cate 25 kW” (#70), „2 x 18,5 kW Y/D si 1 x 7,5 kW DOL” (#62), „3 motoare de 5,5kW, 2 de 3kW si unul de 15 CP” (#38), „30 de circuite prize de 2 kW” (#52 → un singur circuit „Prize de”), prize CEE (#41), prescurtări „alim din PT propr 800kVA, plec: … il 10kw” (#42), virgula zecimală în secțiunea cablului „CYY-F 5x2,5” → „5x2” (#55) | 3, 38, 41, 42, 52, 55, 62, 68, 69, 70 |
| S2 | **Puterea sursei devine plecare fantomă.** „din BMPT 70 kW” → plecare „TD-6 70 kW” cu 3×125 A gG, iar Q1 se dublează (160 A). La fel „BMPT 6 kW mono” → „TD-5” | 8, 12 |
| S3 | **Cascada TG→TD→TE nu e suportată.** #16 pierde toate TD-urile (tablou gol); #17 aplatizează TE sub TG, cu dublă numărare (Σ 180 kW, Q1 320 A vs Q2 250 A, raport 1,09) | 16, 17 |
| S4 | **Contradicții nedetectate.** „compresor 22 kW 16 A” (#54), „20/0,4 kV … MT 15 kV” (ia 15 fără întrebare, #58), „TD 250 A … întreruptor de 160 A” (#56), „PT 160 kVA … 300 kW” (nicio avertizare, #28), „TG 400 kW din BMPT” (generează, deși la #48 motorul știe că BMPT > 250 A nu există, #37), „690 V” ignorat (#53), „inversor manual” desenat ca ATS automat (#63) | 28, 37, 53, 54, 56, 58, 63 |
| S5 | **„genereaza” fără nimic de desenat.** Tablou fără plecări (V07 BLOCANT), fără nicio întrebare: TD cu cablu impus (#19), „motor 75 CP” (#20, motorul unic nu devine plecare), #37, #50, #53, #56 | 19, 20, 37, 50, 53, 56 |
| S6 | **Rutare greșită a tipului de schemă.** „transformator de separare 10 kVA” (IT medical) → PT 20/0,4 kV de 100 kVA (#9). „trafo 400/230” → PT, cu întrebarea „kVA?” (#10). „TG clădire: lift, hidrofor” → **locuință** cu circuite inventate (boiler, mașină de spălat, prize baie), iar lift 11 kW devine „P aprobată 11 kW” (#47). Stație de încărcare VE (#59), „din PT 400 kVA alimentam un motor de 200 kW” (#21) și „pompa 7,5 kW” → I01 | 9, 10, 21, 47, 59 |
| S7 | **Originea declarată pierdută.** „TG din PT 1000 kVA cu compensare automata” → sursă nedeclarată, PRESUPUS BMPT pentru 455 kW, cu deconectare bazată pe un RCCB presupus (#36) | 36 |
| S8 | **Motoare.** (a) Ib e calculat fără randament: 15 kW → 25,5 A (real ≈ 28–29 A), 55 kW → 93 A (real ≈ 100 A). Releul termic e reglat la „Ir = Ib”, deci declanșează la sarcină nominală (#1, #2, #6, #11, #18, #30). (b) Pluralul „Compresoare” nu e recunoscut ca motor: la #65, 3 × 75 kW au doar gG 125 A, fără demaror, iar In real ≈ 135–140 A > 125 A. (c) În modul `circuite_finale` „Motoare 1/2” primesc MCB C10, fără KM/F (#49) | 1, 6, 49, 65 (sistemic) |
| S9 | **Cablul impus e alterat.** „2 cabluri in paralel 3x240+120 Al” → un singur cablu, V02/V03 BLOCANT, Q1 = Q2 = 320 A (#7). „pompa 30 kW cu CYY 4x6 pe 120 m”: cei 120 m se aplică alimentării TG, plecarea rămâne la 50 m, iar 4x6 devine CYABY 5×6 (#18) | 7, 18 |
| S10 | **Planșa blocată nu se vede ca blocată.** p18 și p07 au V02/V03 BLOCANT în validare, dar nota 6 de pe planșă listează doar V22/V32/V41/V42. Planșa arată „finală” | 7, 18 |
| S11 | **Iluminat și circuite mono.** Circuitele declarate „230V” sunt desenate 4P, cu Ib calculat trifazat (1,2 kW → 1,9 A în loc de 5,8 A). ks = 0,6 aplicat pe 12 circuite de iluminat → Q1 C16 pentru 14,4 kW (≈ 23 A). Incomerul e subdimensionat (#40). Prize „2 kW” pe B6 4P (#52) | 40, 49, 52 |
| S12 | **PT cu 2 trafo (#24).** Se desenează doar 4 plecări din 8 („fiecare semibară cu 4”). Cupla e presupusă „normal închisă, T1 ∥ T2” fără întrebare (uzual e NO, cu interblocaj 2 din 3), iar semibarele și aparatul de cuplă lipsesc din desen. T2 apare ca sursă separată „BARA MT 20 kV”, iar măsura MT pare să fie doar pe ramura T1 | 24 |
| S13 | **Măsura declarată, ignorată.** „masura pe joasa tensiune” la PT 10 kV nu apare (#25), deși la #27 apare corect | 25 |
| S14 | **Ik3 implicit 25 kA la BMPT/TG existent supradimensionează cablurile.** Chioșc monofazat de 6 kW (C50): C1 = **ACYABY 3×95 mm²** (#12). Plecări de 0,5–2 kW pe CYABY 5×6. Valoarea e declarată ca presupusă, dar rezultatul pe planșă e absurd. Implicitul trebuie să fie realist (BMPT mono ≈ 3–6 kA) sau trebuie pusă o întrebare | 2, 5, 11, 12 |

## P2 (selecție)

- **Etichete și denumiri.** TD desenat cu titlul „TG” (#7, #39). Nume: „Iluminat a cate 1…12” (#40), „Prize de” (#52), „iluminat 230V de 1” (#49), „Noua pentru compresor” (#67), trei plecări toate „Pompa” (#6). „Consumatori normali” pe ieșirea ATS, deși sunt vitali (#30).
- **Textul din „presupus” se contrazice cu desenul.** Apare „trafo uscat 20/0,4 kV” la PT de 6 kV (#23, #65) și 15 kV (#58), iar „S"kQ = 500 MVA (rețea MT 20 kV)” la 6 kV. La #1: „„pt” minuscul = „pentru”” deși originea e PT propriu. „6 plecări de 0,8 kW” pentru 0,75 kW (#5). La #11 cartușul tabloului arată Pi = 20 kW, deși P declarată (40 kW) „are prioritate”.
- **Motoare.** 4P și cablu 5 conductoare (cu N) pe circuite de motor (#1, #2). Contactor de linie Y/Δ de 95 A (suficient 0,58·In ≈ 56 A, #6). Ramuri gG 2 A pentru rampe de 0,75 kW (motor nerecunoscut, #5).
- **#44** „cat costa un trafo de 630” → cere „puterea trafo (kVA)”, deși 630 e în text; ar trebui „Nu am înțeles / în afara scopului”.
- **#45** „fara DDR la prize” → întrebare generică „Nu am folosit…”. Corect ar fi un avertisment explicit: DDR 30 mA la prize e obligatoriu (I7 / SR HD 60364-4-41 art. 411.3.3).
- **#61** UPS: răspunde cu „puterea tabloului?”, în loc să spună că UPS-ul nu e acoperit.
- **Lista de materiale pe planșă.** Simbolurile de la poz. 12 (p07) și 14 (p65) sunt micșorate până la ilizibil, când cablul e comun mai multor circuite.

## Ce funcționează bine (confirmat pe planșe)

- **PT cu un trafo (p22, p23, p65).** Celule MT de linie (inclusiv buclă intrare-ieșire), FV ZnO, celulă de măsură MT sau măsură JT semidirectă cu TC, celulă de trafo cu SF sau cu întreruptor în vid + 50/51/50N/51N, MCCB/ACB JT corect față de In_T, servicii proprii PT, U_MT 6/10/15 kV corect pe aparate (7,2/12/17,5 kV).
- **#26** (35 kV) refuzat cu întrebare. **#64** „PT 1.000 kVA” → 1000 kVA. **#48** „PT alimentat din BMPT” → întrebare corectă.
- **Pornire Y/Δ (p06).** KΔ/KY, releu termic pe ramura Δ reglat la Ib/√3. VFD cu siguranțe gG, soft-starter cu bypass.
- **TT (p11).** DDR 100 mA pe forță, 30 mA pe prize, RA·IΔn verificat, RCCB 300 mA S amonte.
- **GE+ATS (p29, p30, p33).** ATS 4P AC-33B, interblocaj, neutrul GE la priza locală. Pompe incendiu (când sunt numite): fără DDR, NHXH FE180/E90, termic „doar semnalizare”, RCM doar alarmă pe GE.
- **Contradicțiile mono/tri (#13) și TN-S/TT (#14)** produc întrebare. Rețeaua nedeclarată produce întrebarea „Rețeaua nu se presupune” (#15, #38).
- **TN-C cu DDR din BMPT (#57)** → V27 BLOCANT, cu explicație corectă (I7 art. 3.3.2.11.1).
- **Lizibilitate.** Planșele cu ≤ 12 plecări sunt clare, fără suprapuneri. Listă de echipamente, legendă, note și cartuș sunt complete.

---

## Rezultate per frază

Legendă: C = corect, P = parțial, G = greșit. Detaliile complete (intrare, presupuneri, validare, aparataj) sunt în `industrial/rezultate_brute.txt`.

| # | Frază (prescurtat) | Așteptat | Obținut | Verdict | Sev. |
|---|---|---|---|---|---|
| 1 | tg hală din pt propriu 630kva tn-s, 4 motoare 15 kW, 2 vent., ilum., prize 6 circ. | TG + întrebare la prize | TG corect (MCCB + KM + F), întreabă puterea prizelor; termic 25,5 A < In real; presupus „pt = pentru” contradictoriu | P | P2 |
| 2 | TG atelier din TG existent, CYABY 4x95, TN-C-S, compresor 20 CP | cablu impus, 14,7 kW | Corect (14,7 kW, 95 mm² verificat); 5×6 pe polizor 2,2 kW | C | P2 |
| 3 | listă cu liniuțe pe rânduri, BMPT, TN-S | 5 tipuri de plecări | Refuz I05 „s-au găsit 1”; P = 9 kW și In_Q1 = 16 A luate greșit din text | G | P1 |
| 4 | listă cu „;”, rooftop 2 x 30, PT 400 | TG 6 plecări | Corect; Q1 200 A Ir 170 | C | — |
| 5 | paranteze, rampe 6 x 0,75, încărcătoare 3 x 15 | TG 11 plecări | Corect; schema implicită declarată; gG 2 A pe rampe-motor; „0,8 kW” | C | P2 |
| 6 | Y/Δ 55, VFD 37, soft 22 | 3 demaroare | Corect tehnic; KM linie 95 A; nume duplicate | P | P2 |
| 7 | TD HVAC, 2 cabluri paralel 3x240+120 Al | 2 × cablu, TD | Un singur cablu → V02/V03 BLOCANT; Q1 = Q2 = 320 A; titlu TG | G | P1 |
| 8 | brutărie din BMPT 70 kW | 5 plecări, Q1 ~ 125 A | Plecare fantomă „TD-6 70 kW”, Q1 160 A | G | P1 |
| 9 | bloc operator IT medical, trafo separare 10 kVA | IT medical / întrebare | Transformat în PT 20/0,4 kV de 100 kVA | G | P1 |
| 10 | IT 400 V fără N, iluminat prin trafo 400/230 | IT / întrebare | Tip PT, „puterea trafo?” | G | P1 |
| 11 | fermă TT din BMPT 40 kW | DDR pe toate plecările | Corect (p11); Pi = 20 kW în cartuș | C | P2 |
| 12 | chioșc mono din BMPT 6 kW mono | 4 circuite mono | Fantomă „TD-5”; C1 ACYABY 3×95 pentru C50 | G | P1 |
| 13 | tablou mono cu motor trifazat | întrebare | Întrebare mono/tri | C | — |
| 14 | TN-S și TT | întrebare | Întrebare | C | — |
| 15 | atelier 3 motoare 4 kW, fără rețea | întrebare | Întrebare rețea; lista de plecări pierdută | P | P2 |
| 16 | TG birouri, TD et. 1/2, TD parter din care TE | cascadă | TG gol + „Nu am folosit…” | G | P1 |
| 17 | TG -> TD hală -> TE CNC | cascadă | TE pus sub TG, dublă numărare, `circuite_finale` | G | P1 |
| 18 | pompă 30 kW, CYY 4x6 pe 120 m | avertizare cablu | 120 m aplicați pe C1, cablul devine CYABY 5×6; BLOCANT nevizibil pe planșă | P | P1 |
| 19 | TD cu CYABY 5x25, 32 kW | TD + cerere plecări | Tablou gol, V07, fără întrebare | P | P2 |
| 20 | motor 75 CP DOL din TG | plecare motor 55 kW | Tablou gol (P = 55,16), V07 | G | P1 |
| 21 | din PT 400 alimentăm motor 200 kW DOL | avertisment pornire | I01 tip nedeterminat | G | P1 |
| 22 | PT beton 630 ulei, celule MT, măsură MT, 8 × 100 A | PT complet | Corect (p22) | C | — |
| 23 | PT uscat 1600 6/0,4, celulă cu întreruptor, comp. 400 kvar | PT 6 kV | Corect (p23); text presupus „20/0,4” | C | P2 |
| 24 | 2 × 1000 kVA, cuplă, 4 plecări pe semibară | 8 plecări, 2 semibare | 4 plecări, cuplă NI presupusă, topologie MT neclară | P | P1 |
| 25 | PT 400 la 10 kV, măsură JT | 10 kV + măsură JT | 10 kV OK, măsura JT ignorată; întreabă plecările | P | P1 |
| 26 | PT 35/0,4 kV | refuz/întrebare | I12 cu întrebare | C | — |
| 27 | PT 250, măsură JT TC 400/5, 3 plecări | PT + V62 | Corect, Sc 255 > 250 avertizat | C | — |
| 28 | PT 160 pentru hală 300 kW | avertisment supraîncărcare | Doar „Nu am folosit…” + cere plecările | P | P1 |
| 29 | GE 60 + ATS din BMPT 50 kW | GE+ATS | Corect | C | — |
| 30 | PT 400, TGN/TGV, GE 100 doar pe vitale | GE pe vitale, PI fără DDR | Corect pe PI; „Consumatori normali” etichetat greșit; TGN nedesenat (întreabă) | P | P2 |
| 31 | tablou pompe incendiu, rețea + GE 150 | fără DDR, FE180 | **DDR 300 mA pe GE**, totul însumat | G | **P0** |
| 32 | TG cu GE + ATS, vitale 40 kW | întrebare kVA GE | Întrebare | C | — |
| 33 | ATS între TGD și GE 200 | GE+ATS din TGD | Corect | C | — |
| 34 | baterie 150 kVAr 6 trepte, cosφ 0,75, P 300 kW | compensare | Tablou gol; cosφ declarat 0,75 înlocuit cu 0,9 | G | P1 |
| 35 | compensare 200 kvar 7 % din PT 800 | plecare baterie | Cere puterea tabloului | P | P2 |
| 36 | TG din PT 1000 cu compensare automată | sursă PT | PT pierdut → BMPT presupus pentru 455 kW | G | P1 |
| 37 | TG 400 kW din BMPT | refuz / PT | Generează (gol), fără avertisment | G | P1 |
| 38 | 3 de 5,5 kW, 2 de 3 kW, 15 CP, 2000 W | 7 plecări | Doar 5,5 kW; restul „Nu am folosit” | G | P1 |
| 39 | TD cu 3 x 63A, 2 x 125A, 4 x 32A | 9 plecări | Corect; titlu TG | C | P2 |
| 40 | 12 circuite iluminat a câte 1,2 kW | 12 × 1P+N | 12 × 4P B6, ks 0,6, Q1 C16 < 23 A | P | P1 |
| 41 | 5 prize CEE 32A + 4 CEE 16A | 9 circuite cu DDR | „Nu am folosit…” | G | P1 |
| 42 | prescurtări (alim, propr, plec, il) | TG 3 plecări | Doar 37 kW; PT 800 nerecunoscut | G | P1 |
| 43 | schemă pentru mașina de spălat vase | întrebare | I01 + întrebare | C | — |
| 44 | cât costă un trafo de 630 | „Nu am înțeles” | Cere kVA | P | P2 |
| 45 | fără SPD și fără DDR la prize | avertisment DDR | „Nu am folosit…” (DDR desenat totuși) | P | P2 |
| 46 | desfumare din TG și GE | siguranță, kVA GE | Întrebare kVA; avertisment „pompe incendiu” pentru desfumare | C | P2 |
| 47 | TG clădire: lift, hidrofor, BMPT 30 kW | TG 3 plecări | Locuință cu circuite inventate, lift ignorat | G | P1 |
| 48 | post trafo din BMPT | întrebare | Întrebare | C | — |
| 49 | 6 circuite 230V + 2 motoare 4 kW | mono pe faze, demaroare | 4P tri, motoare fără KM/F | P | P1 |
| 50 | TG 100 kW | întrebare | Gol, fără întrebare | P | P2 |
| 51 | pompă 7,5 kW | întrebare utilă | I01 generic | P | P2 |
| 52 | 30 circuite prize 2 kW + 10 iluminat | 40 de circuite | 1 priză + 10 iluminat; Q1 C10 | G | P1 |
| 53 | motor 250 kW la 690 V | întrebare 690 V | Generează gol, 690 V ignorat | G | P1 |
| 54 | compresor 22 kW 16 A | contradicție | „Nu am folosit…” (sigur, dar nespecific) | P | P2 |
| 55 | cuptor 30 kW cu CYY-F 5x2,5 | avertisment cablu | „5x2” trunchiat, nimic desenat | G | P1 |
| 56 | TD 250 A din întreruptor 160 A | contradicție | Gol, fără întrebare | G | P1 |
| 57 | TN-C cu cablu 4x16 | blocare / întrebare | V27 BLOCANT corect, dar fără întrebare | P | P2 |
| 58 | 20/0,4 kV dar MT 15 kV | întrebare | Ia 15 kV fără întrebare | P | P1 |
| 59 | stație VE 4 × 22 AC + 50 DC din PT 400 | tablou VE | I01 | G | P1 |
| 60 | bucătărie restaurant | tablou 6 plecări | Corect | C | — |
| 61 | UPS 40 kVA cu bypass | în afara scopului | Cere puterea tabloului | P | P2 |
| 62 | 2 x 18,5 kW Y/D + 1 x 7,5 DOL | 3 plecări | Doar 18,5 kW, „5 kW Y/D…” nefolosit | G | P1 |
| 63 | GE 30 cu inversor manual | comutator manual | ATS automat | G | P1 |
| 64 | PT 1.000 kVA, TG cu 6 plecări | 1000 kVA + întrebare | Corect | C | — |
| 65 | MT 6 kV, 1000 kVA, compresoare 3 × 75 | PT + 3 motoare | PT corect; compresoare fără demaror, gG 125 A < In real | P | P1 |
| 66 | TG cu 2 alimentări din PT1/PT2 cu cuplă | 2 intrări + cuplă / întrebare | Cere doar plecările | P | P2 |
| 67 | TG existent 250 A + compresor 45 kW soft | plecare nouă | Corect tehnic, nume „Noua pentru compresor” | P | P2 |
| 68 | listă cu tab-uri | TG 3 plecări | „Nu am folosit…” tot textul | G | P1 |
| 69 | enumerare „1) … 5)” | 5 plecări | I03 „Valoarea 1 nu are unitate” | G | P1 |
| 70 | 15 plecări a câte 25 kW | 15 plecări | I05 „s-a găsit 1” | G | P1 |

## Planșe judecate ca la avizare (16)

| Planșă | Verdict avizare | Observații |
|---|---|---|
| p01 | Avizabil cu observații | Aparataj complet pe motoare (MCCB + KM + F). Termic = Ib fără η. 5 conductoare pe motor. SPD cu „protecție amonte 63 A gG” fără aparat desenat. Prizele lipsesc (se cere puterea) |
| p06 | Avizabil cu observații | Y/Δ corect desenat, VFD, soft-starter. KM linie supradimensionat. Trei plecări „Pompa” fără indice |
| p07 | Respins | BLOCANT (C1 3×240+120 singur < 320 A) nemarcat pe planșă. Q1 = Q2 = 320 A, fără selectivitate. Titlu TG pentru TD. Simbol ilizibil la poz. 12 |
| p08 | Respins | Plecare fantomă TD-6 70 kW. Q1 dublat |
| p11 | Avizabil | TT corect. Cartușul arată Pi 20 kW față de P declarată 40 kW |
| p12 | Respins | C1 ACYABY 3×95 pentru C50. Plecare fantomă TD-5 |
| p17 | Respins | Cascadă aplatizată, Σ dublat, TE pe MCB în TG |
| p18 | Respins | Cablu impus 4x6 schimbat în 5×6. L = 120 m pe C1. Q1 C63 = Q2 63 A. BLOCANT V02/V03 neafișat |
| p22 | Avizabil | PT 630 complet. Ar merita protecțiile trafo de ulei (termometru/releu de gaze) în listă |
| p23 | Avizabil | PT 6 kV uscat, întreruptor + 50/51, compensare 1,43·In. Textul presupus spune 20/0,4 |
| p24 | Respins | T2 ca sursă separată, fără bară MT. Cupla nedesenată ca aparat. 4 din 8 plecări. Măsura MT doar pe ramura T1 |
| p30 | Avizabil cu observații | Pompe incendiu corecte (fără DDR, FE180, termic doar semnalizare, RCM). Etichetă „Consumatori normali” greșită. Pornirea DOL 30 kW pe GE 100 kVA neverificată |
| p31 | Respins (P0) | DDR 300 mA în amontele pompelor de incendiu. Cablu nerezistent la foc |
| p47 | Respins | Locuință cu circuite inventate în loc de TG clădire. Lift ignorat |
| p52 | Respins | 30 de circuite de prize pierdute. Prize pe B6. Q1 C10 |
| p65 | Avizabil cu observații / respins pe motoare | PT 6 kV corect. Compresoarele 75 kW fără demaror, iar gG 125 A e sub In real |

Lizibilitate generală: bună (nicio suprapunere de text pe planșele verificate). Cartușul, nota cu normele, lista de echipamente și legenda sunt consecvente. Tabloul cu 11 plecări (p52) rămâne lizibil pe A2.

## Comparativ cu r6 (4/10)

- **Mai bine:** pompele de incendiu numite explicit (fără DDR, FE180, termic de semnalizare, RCM), MT 6/10/15 kV, celulă cu întreruptor + 50/51, 2 trafo recunoscuți, compensarea ca plecare 1,43·In, plasa de siguranță („Nu am folosit…” în loc de desen inventat), contradicțiile mono/tri și TN/TT, refuzul pentru 35 kV, TN-C cu DDR blocat.
- **La fel de slab:** robustețea la formatarea textului (liste neobișnuite), cascadele, contradicțiile numerice, Ib-ul motoarelor fără η, implicitul de Ik3 = 25 kA la BMPT.
- **Nou găsit:** P0 la pompe de incendiu descrise prin context („tablou pompe incendiu”); plecare fantomă din puterea BMPT; rutarea „TG clădire cu lift” → locuință; „genereaza” cu tablou gol fără întrebare.

## Recomandări de reparare (prioritate)

1. **P0.** Contextul „tablou pompe incendiu / desfumare / hidranți / sprinklere” trebuie să marcheze toți consumatorii ca `siguranta`. Niciun DDR pe ramura GE sau ATS care alimentează consumatori de siguranță.
2. **Tokenizare de liste.** Separatori `\n`, `\t`, `-`, `;`, `1)`/`a)`; „N de X kW”, „a câte”, „N x P <pornire>”; CEE 16/32 A; dicționar de prescurtări (alim, plec, il, comp, propr); virgula zecimală în secțiuni („5x2,5”, „3x1,5”).
3. **„din BMPT X kW” = putere aprobată/sursă, nu plecare.** Același tipar ca „din PT X kVA”.
4. **Cascadă.** „TD … din care TE …” și „->” trebuie să producă `copii` (tabloul secundar există deja în motor).
5. **Contradicții numerice → întrebare:** P vs In (±30 %), U_MT dublu, Q1 impus < In tablou, Sn PT < P/cosφ, BMPT > 250 A, U ≠ 400/230 V, „manual” vs ATS.
6. **Tablou fără plecări** → `genereaza_cu_intrebare` cu „Care sunt plecările?”, nu `genereaza`.
7. **Motoare.** Ib = P/(√3·U·cosφ·η) cu η tipic pe treaptă de putere; recunoaștere și la plural (compresoare, pompe, ventilatoare); demaror și la `circuite_finale`.
8. **Ik3 implicit la BMPT/TGD** realist (≈ 6–10 kA tri, 3–6 kA mono) sau întrebare, ca să nu mai iasă 3×95 la un chioșc.
9. **Planșa trebuie să afișeze vizibil BLOCANT-ele** (nota 6 sau ștampilă „NEVERIFICAT”).
10. **Iluminat/prize declarate 230 V** → 1P+N, Ib monofazat, repartiție pe faze; ks = 1 pentru iluminat.
