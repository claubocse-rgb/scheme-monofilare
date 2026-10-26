# Runda 8 — testare industrială (TG/TD/PT/GE) — inginer proiectant

Data: 2026-10-23 · Flux: `interpretor.interpreteaza(text)` (fără LLM, ca `/api/chat`) → `constructor.genereaza` → `validare.valideaza` → `layout.build` → `render_svg` → PNG (cairosvg, 2400 px).
Fișiere: `teste/r8/industrial/fraze.json` (68 de fraze noi, cu așteptat / obținut / verdict / severitate), `pNN.png/.svg` (52 de planșe), `rezultate_brute.txt` (ieșire completă), `sumar.txt` (rezumat per frază), `res.json`, `run.py` (rulare: `python3 teste/r8/industrial/run.py [id…]`), `verdicte.py`.
Nu s-au citit tests/ și nici frazele vechi. engine/, tests/, static/ nemodificate.

Stiluri folosite: temă de proiectare, tabel Excel cu tab-uri, bilanț de puteri, emailuri (cu salut, semnătură, telefon), mesaje scurte/prescurtate, engleză, liste cu „•”, „a) b)”, „/”, cascade cu „->” și „din care”, PT ulei/uscat/PTA/2 trafo/6–10–20 kV, celule MT, măsură, GE+ATS (vitale, pompe incendiu 1+1, TDSI, desfumare, hidranți), comutator manual, compensare, cabluri impuse/paralel, contradicții, întrebări în afara scopului.

## Nota: 3,5 / 10 (r7: 4,5/10)

| | Număr | % |
|---|---|---|
| Corect | 18 | 26 % |
| Parțial | 14 | 21 % |
| Greșit | 36 | 53 % |
| **P0** | **3** | |
| **P1** | **39** | |
| P2 (verdict principal) | 17 | |

Pe scurt: **reparațiile din r7 s-au ținut pe formulările testate** (CEE, „N circuite a X kW”, „a) b)”, 690 V, cuplă NO 2/3, ștampila NEVERIFICAT, „pt”=pentru, W→kW, BMPT>250 A, DOL mare pe PT mic), dar **clasa de probleme rămâne**: pe 68 de formulări noi, interpretorul cade pe mai mult de jumătate. Cel mai grav: **P0-ul de la pompele de incendiu din r7 a fost reparat doar pentru o formă de frază** — „TDSI sprinklere”, „desfumare”, „pompa incendiu” într-un TG din PT ies toate cu DDR / releu termic de declanșare / cablu nerezistent la foc. Separatori noi (tab Excel, „•”, „/”, prescurtări), compensarea (→ CEF!), cascadele, cablurile în paralel și contradicțiile numerice rămân sistemic greșite. Motorul de calcul și desenul rămân bune când intrarea e corectă (p61, p66, p68).

---

## P0 (3) — siguranța la incendiu, aceeași clasă ca r7 #31

1. **#12 TDSI sprinklere** („electropompa 55 kW stea-triunghi, jockey 2,2 kW, normal din TG și rezervă din GE 125 kVA”). Planșa p12: **DDR-G bloc diferențial 300 mA A S pe ramura GE**, un singur circuit „Consumatori 57,2 kW”, Y/Δ pierdut, cablu ACYABY (nu NHXH FE180/E90), consumatorii nemarcați `siguranta`, nicio avertizare, planșa nu e blocată. Contextul „TDSI / sprinklere” nu e recunoscut. Încalcă P118/3 și I7 (alimentarea pompelor de incendiu fără DDR, fără protecție la suprasarcină cu declanșare).
2. **#14 TE desfumare** („2 ventilatoare desfumare 11 kW … cablu rezistent la foc”). p14: MCCB + KM + **releu termic de declanșare Ir = 20,7 A** pe ventilatoarele de desfumare, cablu CYABY 5×6, „rezistent la foc” ignorat, ks 0,7 → Q1 C32 < 2 × 20,7 A (ventilatoarele de desfumare funcționează simultan). În r7 #46 desfumarea era recunoscută doar când exista și GE.
3. **#64 TG hală din PT 630: „pompa incendiu 45 kW, pompa tehnologica 45 kW”.** p64: pompa de incendiu identică cu cea tehnologică — după Q1 general, MCCB + KM + **termic de declanșare 80,2 A**, ACYABY 4×50. Trebuia: racord înaintea întreruptorului general (sau circuit separat din PT), fără termic de declanșare (doar semnalizare), cablu FE180, fără DDR. Cuvântul „incendiu” pe un consumator dintr-un TG nu activează regulile de siguranță (le activează doar în schema GE+ATS).

**Reparare (P0):** marcarea `siguranta` trebuie făcută în interpretor pentru toate tipurile de schemă (tablou, PT, GE) pe dicționar: incendiu, PSI, sprinkler, drencer, hidrant, TDSI, desfumare, presurizare, jockey (în context PSI), lift pompieri, iluminat de siguranță/evacuare, CDI. Regula de aparataj (fără DDR amonte, termic doar semnalizare, FE180/E90, racord înaintea Q1 sau sursă separată, fără ks < 1) se aplică pe consumator, nu pe tipul schemei. Validatorul trebuie să aibă un BLOCANT dacă un consumator `siguranta` are DDR sau termic de declanșare în amonte.

## P1 sistemice (în ordinea impactului)

| # | Problemă | Fraze |
|---|---|---|
| S1 | **Separatori și formate de listă noi nu sunt citiți.** Tabel Excel cu tab-uri (#2: refuz), „•” (#30: plecare fantomă 567 kW), „/” (#32), prescurtări „mot 22kw x3, comp, ilum, plec” (#51), „2 motoare 11 kW” după „tg pt hala:” (#44), „chiller 90 kW si CTA 18,5 kW” după „se adauga 2 plecari noi:” (#45), „24 corpuri x 150 W pe 3 circuite” (#37), „8 plecari NH 250A” (#59: NH = nume), „cuptor … 250 kW rezistiv” (#34), „pompa 7,5 kW cu CYABY 4x4 la 80 m” (#26 — cablul pe plecare omoară plecarea), VRV + UI mono (#58) | 2, 26, 30, 32, 34, 37, 44, 45, 51, 58, 59 |
| S2 | **Puterea/sursa devine plecare fantomă** (r7 S2 reparat doar pentru „din BMPT X kW”): „din PT propriu 400 kVA” într-o temă (#1: 360 kW), „alimentare PT propriu 630 kVA” după listă (#30: 567 kW), „TG din PT 400” (#33: plecare „TG” 400 kW), „ACB 1600A”/„ACB 3200A” la PT (#18, #22: plecare „ACB”), „pompa 15 kW, 10 A” (#56: „Circuit 2” 10 A), „pompa de circulatie … condensator” → compensare (#4) | 1, 4, 18, 22, 30, 33, 56 |
| S3 | **Compensarea = CEF.** „baterie 300 kvar” într-un PT cu 2 trafo (#17), „baterie automata 250 kvar … în TG din PT 1000” (#27), calculul Qc din cosφ (#28) → toate tip CEF, refuz „lipsesc invertoarele”. Aceeași eroare ca r6 #25, nereparată | 17, 27, 28 |
| S4 | **Cascade.** „TG alimentează TD-A … Din TD-A pleacă TE-1 … TD-B are …” → nume-gunoi și TD-A gol (#15, p15). „TGD -> TD -> TE” recunoscut în presupus ca cascadă, dar desenat cu frați (#16, p16). Reușește doar „din care X alimentează Y” (#62) | 15, 16 |
| S5 | **Contradicții și supraîncărcări nedetectate.** 300 kW pe PT 250 kVA: Q1 Ir 450 A > In_T 361 A, fără V62 la tablou și fără BLOCANT (#7, p07). Q1 125 A pentru Pc 99 kW doar V14 (#63, p63). „15 kW, 10 A” (#56). Cablu impus 5x16 / 150 m pentru 80 kW pierdut (#57). PT 400 cu trafo 630 → întrebare generică (#23) | 7, 23, 56, 57, 63 |
| S6 | **Sursa declarată se pierde.** „din PT 630” → cere kVA (#62, #64), „pt 250” (#5), PT 400 în temă (#1), „PT propriu 630 kVA” după listă (#30). Sursă nedeclarată la 290 kW → **BMPT presupus cu Q1 500 A**, fără întrebare (#55, aceeași ca r6). TG cu 2 intrări PT1/PT2 + cuplă → o singură intrare (#49) | 1, 5, 30, 49, 55, 62, 64 |
| S7 | **Rutare greșită către locuință.** „TE apartament de serviciu 230V din TG” → BMPM-40 + contor + circuite inventate (#36, p36). Bucătărie restaurant din BMPT 80 A → locuință cu boiler/mașină de spălat/centrală inventate, friteuze și hotă pierdute (#65). Clasa r7 #47, nereparată | 36, 65 |
| S8 | **Cabluri impuse alterate.** 2 × NA2XY 4x240 în paralel → un singur cablu, V02/V03 (#25, aceeași ca r7 #7). Cablu CYABY 3x120+70 din email → CYABY 5×35 (#4). Pozitiv: „2x (3x240+120) Al” e citit corect la #34 | 4, 25, 57 |
| S9 | **Comutator manual desenat ca ATS automat.** Avertismentul „comutare manuală — verificați simbolul” a fost adăugat, dar p48 tot are „ATS 4P AC-33B” și „tablou de anclanșare automată” (r7 #63, reparat doar în text) | 48 |
| S10 | **PTA pe stâlp desenat ca PT de interior** (LES, celulă de linie + CLP, anvelopă beton în listă) — avertisment text, desen neschimbat (r6 #26) | 21 |
| S11 | **Circuite mono pe 4P / ks pe circuite finale** (r7 S11, nereparat): 20 × iluminat 0,8 kW și 24 × prize 2 kW → toate 4P B6; ks 0,6 pe planșă → Q1 80 A pentru ≈ 92 A. 44 de plecări pe un rând: planșa p38 e **ilizibilă** (31 % pe A1) — lipsește împărțirea pe rânduri/planșe | 38 |
| S12 | **Mixt 230/400 V = contradicție falsă.** „prize 230V 6 circ, prize 400V 2x32A” → I08 „mono și tri”, refuz (#53). Situația e normală în orice TG | 53 |
| S13 | **Schema GE.** „TG-normal 300 kW” pus pe GE → V86 cu sugestia greșită „GE ≥ 400 kVA” (#46). Pompa de incendiu 1+1 → o singură plecare numită „De”, jockey pe DDR 300 mA etichetat „Consumatori normali”, gG 63 A < In real al unui motor de 37 kW (#11, p11) | 11, 46 |
| S14 | **Motoare.** Ib tot fără η: 45 kW → 80,2 A (real ≈ 84–86 A), releu termic = Ib (#64, #52). Motoare în HP ignorate **fără mesaj** (#29 — singura pierdere tăcută din rundă). Turn de răcire 11 kW și motoarele de macara 2,2/1,5 kW fără demaror (#68) | 29, 52, 64, 68 |

## P2 (selecție)

- **Text presupus contradictoriu:** „trafo 20/0,4 kV, S"kQ 500 MVA rețea 20 kV” la 10 kV (#18); „Scc 250 MVA declarată” + „500 MVA implicit” (#19); nota 3 „TN-S din PT” când TN-C-S e declarat (#3, #25); „în paralel pe barele JT” lângă cupla NO (#61); nota 3 „Rp ≤ 4 Ω, aval de separarea PEN” la sursă PT (#64).
- **Întrebări inutile:** „Pi = 320 kW / Pc = 224 kW?” (#3), „putere instalată?” (#61), „cu DDR 30mA?” deși DDR-ul e desenat (#39), kVA cerut deși e în text (#24, #62, #64).
- **În afara scopului tratat ca date lipsă:** preț TG (#54), motor MT 6 kV (#41: I01 generic).
- **Mărunțișuri de aparataj:** iluminat/sarcini de 0,1–0,5 kW pe 3 × 2–4 A gG cu CYABY 5×6 (#14, #35); CEE pe curba B (#39); Q general MCCB 1600/3200 A deși ACB e cerut explicit (#18, #22); TD/TE desenate cu titlul „TG” (#4, #14, #63).

## Ce funcționează bine (confirmat pe planșe)

- **PT 2 × 1000 kVA (p61):** bară MT, 2 trafo, secții 1/2, cuplă QC NO cu interblocaj 2/3, V62 pe secție — clasa r7 S12 reparată.
- **Ștampila „NEVERIFICAT — CALCUL BLOCAT”** și nota 0 pe planșele blocate (p18, p25) — clasa r7 S10 reparată.
- **TT (p66):** DDR 100 mA pe forță, 30 mA pe prize, RA·IΔn = 9 V verificat.
- **PT 1000 kVA cu 12 plecări (p68):** VFD 160 kW, soft-starter, Y/Δ cu releu pe ramura Δ (Ib/√3), macara ca sub-tablou, măsură JT semidirectă.
- **Întrebări bune:** TN-S/TT (#8), IT (#10), 690 V (#40), DOL 110 kW pe PT 250 (#42), BMPT > 250 A (#43), GE subdimensionat (#47), GE monofazat (#67), mono/tri la sarcină mică (#9).
- **Parsare reparată:** CEE 32/16 A (#39), „20 de circuite iluminat a 0,8 kW” (#38), „a) b) c)” (#31), W → kW (#52), „1,6 MVA” (#60), „pt” = „pentru” și telefonul ignorat în email (#63), 6/10 kV pe aparate (#18, #22).

---

## Rezultate per frază

Legendă: C = corect, P = parțial, G = greșit. ⏎ = rând nou, ⇥ = tab în frază.

| # | Frază (prescurtat) | Așteptat | Obținut | Verdict | Sev. |
|---|---|---|---|---|---|
| 1 | Tema de proiectare: hala depozitare 2400 mp, P+0. Alimentare din PT propriu 400 kVA (ul… | TG din PT 400 TN-S; il 6 circ, rampe 4 mot, usi 4 mot, CDI (siguranta, fara DDR), 6 prize DDR, TD birouri | Refuz I02 „lipsește kVA” deși PT 400 kVA e declarat; plecare fantomă „P+0. Alimentare din PT propriu” 360 kW; toți consumatorii pierduți | G | P1 |
| 2 | Nr ⇥ Denumire ⇥ P[kW] ⇥ Buc ⏎ 1 ⇥ Strung CNC ⇥ 18,5 ⇥ 2 ⏎ 2 ⇥ Freza ⇥ 11 ⇥ 1 ⏎ 3 ⇥ Comp… | 5 plecari (2 strunguri 18,5, freza 11, compresor 30, iluminat 6), origine TG existent | Tabel Excel cu tab-uri: refuz I02, nicio plecare citită | G | P1 |
| 3 | Bilant puteri: Pi = 320 kW, ku = 0,7, Pc = 224 kW, cos fi = 0,92. Sursa: PT 400 kVA pro… | TG din PT 400, 4 TD; Pi/Pc nu devin plecari | PT 400 + 4 TD corecte; Pi/Pc întrebate (inutil); nota 3 spune TN-S deși TN-C-S declarat | C | P2 |
| 4 | Buna ziua, va rog sa ne trimiteti schema monofilara pentru tabloul TE-Chiller. Chilleru… | TE din TG, cablu impus 3x120+70 L60, 2 comp SS 42, pompa VFD 5,5, 4 vent 1,5 | Plecare numită cu textul emailului; „ventilatoare condensator” tratate drept compensare; pompa VFD pierdută; cablul impus 3x120+70 → CYABY 5×35; P tablou = 5,5 kW; titlu TG | G | P1 |
| 5 | tg 3 pompe 7,5kw din pt 250 | TG din PT 250 kVA, 3 pompe motor; schema de legare la pamant: presupusa declarat TN-S sau intrebare | „pt 250” nerecunoscut ca kVA; cele 3 pompe pierdute (P tablou 7,5 kW); întreabă mono/tri deși sursa e PT; V07 | G | P1 |
| 6 | Main LV panel for warehouse, supply from own substation 630 kVA dry type 20/0.4 kV, TN-… | TG din PT 630 uscat; 2 chiller, 4 AHU VFD, iluminat, 12 prize (putere intrebata/presupusa) | PT 630 + chillere + 4 AHU VFD corecte; „12 sockets circuits” aruncate fără mesaj; „dry type” ignorat (ulei presupus) | P | P1 |
| 7 | TG din PT 250 kVA, TN-S, plecari: compresor 160 kW, cuptor 120 kW, iluminat 20 kW | avertisment/intrebare: 300 kW pe PT 250 kVA supraincarcat | 300 kW pe PT 250 kVA: Q1 500 A Ir 450 A > In_T 361 A, fără V62/BLOCANT; compresor 160 kW DOL; planșa exportabilă | G | P1 |
| 8 | tablou TN-S alimentat din retea TT, 2 pompe 4 kW | contradictie TN-S vs TT -> intrebare | Contradicție TN-S/TT → întrebare | C | — |
| 9 | tablou atelier: flex 2 kW, bormasina 1 kW, iluminat 0,5 kW | retea nedeclarata, sarcina mica -> intrebare mono/tri | Întreabă mono/tri; desenează între timp tri cu 3×4 A gG pe flex 2 kW | C | P2 |
| 10 | tablou in schema IT cu controlul izolatiei, 3 pompe 4 kW, din trafo de separare | IT -> refuz/intrebare, nu TN tacut | IT → întrebare + V28 BLOCANT | C | — |
| 11 | doua pompe de incendiu 1+1 de 37 kW si pompa jockey 1,5 kW, alimentate din PT 630 kVA s… | pompe incendiu siguranta, fara DDR, FE180, 1+1 nu insumat (~38,5 kW), GE+ATS | Pompa de incendiu corectă (fără DDR, FE180) dar numită „De”; 1+1 → o singură plecare; jockey pe DDR 300 mA etichetat „Consumatori normali”; gG 63 A < In real 37 kW; QR 63 A la limită | P | P1 |
| 12 | tablou TDSI sprinklere: electropompa 55 kW stea-triunghi, jockey 2,2 kW, alimentare nor… | siguranta din context TDSI/sprinklere: fara DDR, Y/D, FE180 | TDSI sprinklere pe GE+ATS: DDR-G 300 mA pe ramura GE, consumatori nemarcați siguranță, un singur „Consumatori” 57,2 kW, Y/Δ pierdut, cablu ACYABY (nu FE180); planșa nu e blocată | G | P0 |
| 13 | statie hidranti interiori: 2 pompe 15 kW (una activa una rezerva), sursa TGD + GE, TN-S | siguranta, fara DDR; intrebare kVA GE | Hidranți: cere kVA GE (refuz cu întrebare corectă) | C | — |
| 14 | TE desfumare: 2 ventilatoare desfumare 11 kW si 4 clapete 0,1 kW, din TG pe circuit sep… | siguranta, fara DDR, FE180; termic doar semnalizare | Desfumare: ventilatoarele pe MCCB+KM+releu termic de declanșare, cablu CYABY (nu FE180), „cablu rezistent la foc” ignorat; ks 0,7 → Q1 C32 < 2×20,7 A; titlu TG | G | P0 |
| 15 | TG (din PT 1000 kVA, TN-S) alimenteaza TD-A 250A si TD-B 160A. Din TD-A pleaca TE-1 63A… | cascada 3 niveluri TG->TD-A->TE-1/TE-2, TD-B cu copii | Cascadă distrusă: nume „TD-B 160A. Din TD-A pleaca TE-1 63A”, „. TD-B are compresor”, TD-A gol, TE-1 contopit; 6 prize pierdute; Q1 320 A ≈ Q2 250 A | G | P1 |
| 16 | TGD -> TD-Hala1 125A -> TE-Linie1 (3 motoare 5,5 kW), retea TN-S, TGD din PT 400 kVA | cascada TG->TD->TE | Lanțul „->” recunoscut ca cascadă în presupus, dar TD-Hala1 și TE-Linie1 desenate frați sub TG | G | P1 |
| 17 | PT 2 x 1600 kVA uscat 20/0,4 kV, cupla longitudinala JT normal deschisa, semibara A: TD… | 2 trafo, 2 semibare, cupla NO, 6 plecari repartizate | PT 2×1600 cu semibare + baterie 300 kvar → tip CEF, refuz „lipsesc invertoarele” | G | P1 |
| 18 | PT 1000 kVA ulei 10/0,4 kV, celule MT: intrare linie, iesire linie, masura MT, protecti… | PT 10 kV, 2L+M+T intreruptor, ACB 1600, 6x250 | „ACB 1600A” = plecare fantomă „ACB” 1600 A (V40 BLOCANT, ștampila NEVERIFICAT vizibilă); celula de ieșire lipsește; Q general MCCB, nu ACB; presupus „20/0,4 kV, 500 MVA rețea 20 kV” la 10 kV | G | P1 |
| 19 | post de transformare 800 kVA 20/0,4 uk 6%, Scc 250 MVA, uscat, plecari TG 1250A 10m | uk 6% si Scc 250 MVA folosite; TG 1250 A | Scc 250 MVA declarată, dar presupus listează și „500 MVA implicit” (contradictoriu); TG 1250 A pe Q 1250 Ir 1187 → V40 BLOCANT corect | P | P2 |
| 20 | PT 630 kVA 20/0,4 cu masura semidirecta pe JT, TC 1000/5, plecari 4 x 160A | masura JT cu TC 1000/5; 4 plecari | Măsură JT TC 1000/5, 4 plecări | C | — |
| 21 | PTA 250 kVA pe stalp 20/0,4 kV, plecari 3 x 125A | PTA aerian: separator + sigurante MT pe stalp, fara celule de interior; 3 plecari | PTA pe stâlp desenat cu LES + celulă de linie + CLP + anvelopă beton în listă; doar avertisment text | P | P1 |
| 22 | statie 6 kV existenta, trafo nou 2000 kVA 6/0,4 kV uscat, celula cu intreruptor in vid,… | PT 6 kV, aparate 7,2 kV, ACB 3200, 4x630 | „ACB 3200A” = plecare fantomă (V40 BLOCANT); 6 kV corect (7,2 kV) | G | P1 |
| 23 | PT 400 kVA 20/0,4 kV cu trafo 630 kVA, plecari 3 x 250A | contradictie 400 vs 630 kVA -> intrebare | 400 vs 630 kVA: „Nu am folosit…” generic, desenează 400 kVA (ar trebui întrebare de contradicție) | P | P2 |
| 24 | TG cu intreruptor general 100A pentru 120 kW, din PT 400, TN-S, plecari: TD1 60 kW, TD2… | contradictie 100 A < ~200 A -> intrebare/blocant | V04 BLOCANT corect (100 A < 192 A), dar cere kVA deși „din PT 400” | P | P2 |
| 25 | TG din PT 800 kVA, alimentare 2 x NA2XY 4x240 in paralel, 90 m, TN-C-S, plecari TD1 400… | 2 cabluri in paralel impuse (Al 240) | 2×NA2XY 4x240 în paralel → un singur AC2XABY 4×240 → V02/V03 BLOCANT (vizibil pe planșă); NA2XY → armat | G | P1 |
| 26 | TG din BMPT 100A TN-C-S: pompa 7,5 kW cu CYABY 4x4 la 80 m, iluminat 3 kW CYY-F 3x2,5 l… | cabluri impuse per plecare + L per plecare; prize putere intrebata | Plecările cu cablu impus și L pe plecare pierdute toate; tablou gol | G | P1 |
| 27 | baterie automata 250 kvar cu filtru 7%, 8 trepte, in TG din PT 1000 kVA, TN-S, plus ple… | TG cu plecare compensare 250 kvar + 2 TD | Baterie 250 kvar în TG → tip CEF, refuz „invertoare” | G | P1 |
| 28 | factor de putere actual 0,78, se doreste 0,95, P = 400 kW, ce baterie imi trebuie in TG… | Qc ~190 kvar; plecare compensare sau raspuns calcul | Calcul Qc (cosφ 0,78→0,95) → tip CEF, refuz „invertoare” | G | P1 |
| 29 | TG atelier din TG existent TN-S: 2 motoare de 10 HP, unul de 25 HP stea-triunghi, macar… | 2x7,46 kW, 18,6 kW Y/D, 2x5,5 | Motoarele în HP (2×10 HP, 25 HP Y/Δ) pierdute FĂRĂ mesaj; doar macaraua desenată; Q1 C20 | G | P1 |
| 30 | • chiller 180 kW ⏎ • CTA 2 x 22 kW (VFD) ⏎ • pompe 4 x 3 kW ⏎ • iluminat 15 kW ⏎ alimen… | TG din PT 630, 8 plecari | Listă cu „•”: plecare fantomă „alimentare PT propriu” 567 kW; refuz „lipsește kVA” deși 630 declarat | G | P1 |
| 31 | TG brutarie, din BMPT 63A trifazat, TN-C-S: a) cuptor 27 kW b) malaxor 4 kW c) dospitor… | 5 plecari, Q1 63, malaxor motor, frigider/iluminat 1P+N | Enumerare a) b) … corectă, Q1 63 A, frigider mono; iluminat 1,5 kW pe 3×4 A gG 5 conductoare | C | P2 |
| 32 | TG: pompa 5,5kW / vent 3kW / iluminat 2kW / prize 4x16A, din TGD, TN-S | 4+ plecari (prize 4 circ 16A) | Separator „/”: nimic citit; Q1 16 A din „4x16A” | G | P1 |
| 33 | 3 aparate de sudura 20 kVA fiecare + polizor 2,2 kW, TG din PT 400, TN-S | 3 sudura (S 20 kVA), polizor motor | „TG din PT 400” → plecare fantomă „TG” 400 kW → refuz I03 „400 fără unitate”; sudura 3×20 kVA → 18 kW OK | G | P1 |
| 34 | cuptor electric tratament termic 250 kW rezistiv, din PT 400 kVA, TN-S, cablu 2x (3x240… | TG/plecare cuptor 250 kW, 2 cabluri paralel impuse | Cuptor 250 kW pierdut; tablou gol (cablul 2×(3x240+120) citit corect) | G | P1 |
| 35 | tablou lift: motor lift 15 kW, iluminat put 0,5 kW, priza camera masini, din TG cladire… | TD lift 3 plecari; priza putere presupusa/intrebata; NU locuinta | Tablou lift corect; priză întrebată; iluminat puț 0,5 kW pe 3×2 A gG + CYABY 5×6 | C | P2 |
| 36 | TE apartament de serviciu 230V din TG, 3 circuite iluminat 10A, 5 circuite prize 16A, a… | tablou mono 10 circuite | TE „din TG” → locuință cu BMPM-40, contor 5(60) A, RCCB 300 mA; circuite inventate (prize bucătărie/baie); TN-S → TN-C-S | G | P1 |
| 37 | iluminat hala 24 corpuri x 150 W pe 3 circuite monofazate, din TD existent, TN-S, trifazat | 3 x 1P+N 1,2 kW, Q1 tri | „24 corpuri x 150 W pe 3 circuite” nefolosit; P tablou 0,15 kW; tablou gol | G | P1 |
| 38 | TD birouri din TG, TN-S, trifazat: 20 de circuite iluminat a 0,8 kW si 24 circuite priz… | 44 circuite mono | 44 circuite citite corect, dar toate 4P (iluminat 0,8 kW, prize 2 kW pe B6 4P); ks 0,6 pe planșă → Q1 80 A pentru ~92 A; planșă ilizibilă (31 % pe A1, V95) | P | P1 |
| 39 | TD hala din TG, TN-S: 6 prize industriale CEE 3P+N+PE 32A si 4 prize CEE 16A, cu DDR 30mA | 10 circuite CEE cu DDR 30 mA | CEE 6×32 A + 4×16 A cu DDR 30 mA corecte (reparat din r7); întrebare inutilă „cu DDR 30mA”; curba B la CEE | C | P2 |
| 40 | TG cu motor 315 kW la 690 V cu convertizor, din PT 1000 kVA | 690 V -> intrebare/refuz | 690 V → întrebare + V96 BLOCANT | C | — |
| 41 | motor MT 6 kV 800 kW alimentat din celula de motor | MT motor in afara domeniului -> refuz | Motor MT 6 kV → I01 generic, nu „în afara domeniului” | P | P2 |
| 42 | pompa 110 kW pornire directa din PT 250 kVA, TN-S | avertizare pornire DOL vs trafo 250 (In_p ~1,3 kA) | Întrebare corectă DOL 110 kW pe PT 250 + V22 | C | — |
| 43 | hala 250 kW din BMPT trifazat, TN-C-S, plecari: TD1 125 kW, TD2 125 kW | BMPT > 250 A -> refuz/intrebare | Întrebare BMPT > 250 A corectă; planșa provizorie cu Q1 500 A | C | P2 |
| 44 | tg pt hala: 2 motoare 11 kW, din retea trifazata TN-S | pt = pentru, nu PT; sursa presupusa declarat sau intrebare | „2 motoare 11 kW” pierdut; „pt”=„pentru” corect; tablou gol | G | P1 |
| 45 | in TG existent (In 400A, TN-S) se adauga 2 plecari noi: chiller 90 kW si CTA 18,5 kW | TG existent cu 2 plecari noi | Chiller 90 + CTA 18,5 pierdute; P tablou 90 kW; tablou gol | G | P1 |
| 46 | PT 630 kVA, TN-S. TG-normal: productie 300 kW. TG-vital cu GE 250 kVA si ATS: server ro… | PT->TGN+TGV; GE pe vitale; PI fara DDR, 1+1 | TG-normal 300 kW pus pe GE → refuz V86 cu sugestie greșită „GE ≥ 400 kVA”; structura TGN/TGV ignorată | G | P1 |
| 47 | GE 50 kVA cu ATS pentru consumatori vitali 120 kW, din PT 400, TN-S | contradictie GE subdimensionat -> avertisment/intrebare | GE 50 kVA < 120 kW → refuz V86 cu întrebare corectă | C | — |
| 48 | comutator manual retea/GE 3 pozitii (I-0-II) pentru ferma, GE 40 kVA, consumatori: muls… | comutator manual (nu ATS), 3 plecari | Avertisment „comutare manuală — verificați simbolul”, dar planșa are ATS 4P AC-33B + TAR „anclanșare automată”; consumatori comasați | P | P1 |
| 49 | TG cu doua intrari din PT1 si PT2, fiecare 1000 kVA, cupla cu interblocaj 2 din 3, TN-S… | 2 intrari + cupla sau intrebare | 2 intrări PT1/PT2 + cuplă ignorate: o singură intrare, sursă nedeclarată; „fiecare 1000 kVA” nefolosit | G | P1 |
| 50 | TG din PT 400, schema TN-S, alimentare cablu 4x240 Cu | TN-S cu 4 conductoare -> avertisment; plecari lipsa -> intrebare | Cere plecările; TN-S cu cablu 4x240 (fără PE separat) nesemnalat | P | P2 |
| 51 | tg hla prdctie din pt 630kva tns plec: mot 22kw x3, comp 37kw vfd, ilum 8kw | prescurtari: 3 mot 22, comp VFD 37, il 8 | Prescurtări (mot, comp, ilum, plec): doar 22 kW ca P tablou, nimic desenat | G | P1 |
| 52 | iluminat 4500 W, prize 3600 W, motor 2200 W, trifazat, din TGD, TN-S | 3 plecari W->kW | W → kW corect; releu termic Ir 4,5 A pentru 2,2 kW (In real ≈ 4,8 A) | C | P2 |
| 53 | TD service auto din TG 100A, TN-S: elevator 2 coloane 3 kW, compresor 5,5 kW, prize 230… | elevator motor, compresor, 6 prize mono, 2 CEE 32A, iluminat | „prize 230V” + „prize 400V” → contradicție mono/tri falsă (I08), refuz | G | P1 |
| 54 | calculeaza-mi pretul unui TG cu 10 plecari | in afara scopului / nu am inteles | Preț → cere puterile celor 10 plecări (ar trebui „în afara scopului”) | P | P2 |
| 55 | TG cu chiller 200 kW si 3 CTA 30 kW | sursa/schema nedeclarate -> intrebare; nu BMPT presupus | Sursă nedeclarată la 290 kW → BMPT presupus cu Q1 500 A, fără întrebare (BMPT max 250 A) | G | P1 |
| 56 | TD din TG, TN-S: pompa 15 kW, 10 A | contradictie 15 kW vs 10 A -> intrebare | „pompa 15 kW, 10 A” → plecare fantomă „Circuit 2” 10 A, fără contradicție | G | P1 |
| 57 | TD 80 kW alimentat cu CYABY 5x16 pe 150 m din TG, TN-S, plecari: TE1 40 kW, TE2 40 kW | cablu impus insuficient -> blocant vizibil | Cablu impus CYABY 5x16 / 150 m pierdut (doar material Cu) — nicio verificare | G | P1 |
| 58 | VRV exterior 3 unitati x 28 kW si 12 unitati interioare de 0,1 kW alimentate monofazat,… | 3 plecari tri + circuit(e) mono UI | VRV 3×28 kW + UI mono → tot tabloul monofazat, P 28 kW, gol | G | P1 |
| 59 | PTAB 1x630 kVA, 20 kV, celule L+L+M+T (sigurante), JT: 8 plecari NH 250A | PT 630 cu 2L+M+T sig., 8 plecari | „8 plecari NH 250A” → refuz I05 „găsit 1” (NH luat drept nume) | G | P1 |
| 60 | PT 1,6 MVA uscat 20/0,4, plecari TG1 1600A, TG2 800A | 1600 kVA; TG1 1600 + TG2 800 > In trafo 2309? ok | 1,6 MVA → 1600 kVA, celulă cu întreruptor, Q 2500 A | C | — |
| 61 | putere instalata 1.250 kW, PT 2 x 1.000 kVA, TN-S, plecari TD1 1000A, TD2 800A, TD3 630A | 2 x 1000 kVA, Pi nu e plecare | 2×1000 kVA, secții + cuplă NO interblocaj 2/3 (reparat din r7); presupus „în paralel pe barele JT” contrazice cupla NO; Pi întrebat | C | P2 |
| 62 | TG cladire birouri din PT 630, TN-S: TE-P 80A, TE-E1 63A, TE-E2 63A, din care TE-E2 ali… | cascada: TE-Server sub TE-E2 | Cascada TE-Server sub TE-E2 corectă, nume „TE-E2 alimenteaza TE-Server”; „PT 630” pierdut → întreabă kVA | P | P2 |
| 63 | Salut, ⏎ Am nevoie de schema pt tabloul compresoarelor: 2 compresoare de 55 kW cu VFD s… | TD din TG L70, 2 comp VFD 55, uscator 3; telefon ignorat | Email: telefon ignorat, „pt”=pentru, 2 comp VFD OK; uscătorul 3 kW devine P tablou → Q1 125 A Ir 106 A pentru Pc 99 kW (doar V14, nu BLOCANT) | P | P1 |
| 64 | TG hala din PT 630 TN-S: pompa incendiu 45 kW, pompa tehnologica 45 kW, iluminat 10 kW | PI siguranta fara DDR, inainte de general/separat; tehnologica motor normal | Pompă de incendiu 45 kW în TG din PT, după Q1, cu MCCB + KM + releu termic de declanșare, cablu ACYABY, identică cu pompa tehnologică; „PT 630” pierdut (cere kVA) | G | P0 |
| 65 | cuptor pizza 12 kW, friteuza 2 x 9 kW, plita inductie 14 kW, hota 1,5 kW, din BMPT 80A … | 5 plecari, Q1 80 | Bucătărie restaurant → locuință cu circuite inventate (boiler, mașină de spălat, centrală, prize baie); friteuze și hota pierdute; mesaj „Ib 25 A > 80 A” | G | P1 |
| 66 | TG TT din BMPT 100A, RA 30 ohm: pompa 11 kW, 2 ventilatoare 4 kW, prize 4 circuite 16A | TT, DDR pe toate, RA*Idn | TT corect: DDR 100 mA pe forță, 30 mA pe prize, RA·IΔn = 9 V; prize 16 A pe 3×16 gG 4P | C | P2 |
| 67 | GE 10 kVA monofazat cu ATS pentru centrala termica 0,2 kW si pompa circulatie 0,1 kW si… | GE mono + ATS 2P, 3 circuite mono | GE monofazat → V96 + întrebare | C | — |
| 68 | TG productie, sursa PT 1000 kVA 20/0,4 kV, TN-S. Utilaje: linie extrudare 160 kW (VFD),… | ~12 plecari corecte cu demaroare | PT 1000 + 12 plecări cu VFD/soft/Y-Δ corecte; macara ca sub-tablou; turn răcire și motoarele 2,2/1,5 kW fără demaror; prize întrebate | P | P2 |

## Planșe judecate ca la avizare (17)

| Planșă | Verdict avizare | Observații |
|---|---|---|
| p07 | Respins | 300 kW pe PT 250 kVA, Q1 Ir 450 A > In_T 361 A, compresor 160 kW DOL — fără BLOCANT, planșa arată finală |
| p11 | Avizabil cu observații / respins pe PI | Ramura pompei de incendiu e corectă (fără DDR, FE180, RCM doar alarmă), dar numită „De”; 1+1 = o singură plecare; jockey pe DDR 300 mA; gG 63 A sub In real 37 kW |
| p12 | **Respins (P0)** | DDR-G 300 mA în amontele pompei de sprinklere; un singur „Consumatori”; fără Y/Δ; cablu nerezistent la foc |
| p14 | **Respins (P0)** | Ventilatoare de desfumare cu termic de declanșare, cablu CYABY; Q1 C32 sub suma; titlu TG pentru TE |
| p15 | Respins | Cascadă cu nume-gunoi („TD-B 160A. Din TD-A pleaca TE-1 63A”), TD-A gol, prize pierdute, Q1 320 A ≈ Q2 250 A |
| p16 | Respins | TE-Linie1 desenat frate cu TD-Hala1, nu în aval |
| p18 | Respins (blocat corect) | Plecare fantomă „ACB” 1600 A; ștampila NEVERIFICAT vizibilă (bine); lipsește celula de ieșire buclă; Q JT ar trebui ACB |
| p21 | Respins | PTA pe stâlp cu LES, celulă de linie + CLP, anvelopă beton |
| p25 | Respins (blocat corect) | 2 cabluri în paralel impuse → 1 cablu, V02/V03; nota 3 TN-S vs TN-C-S declarat |
| p36 | Respins | TE din TG desenat ca locuință cu BMPM-40 și contor; circuite inventate |
| p38 | Respins | 44 de plecări pe un rând, text ≈ 0,7 mm, 85 % din foaie goală; toate 4P; Q1 80 A sub Ib |
| p48 | Respins | Comutator manual I-0-II desenat ca ATS AC-33B în „tablou de anclanșare automată” |
| p61 | Avizabil cu observații | 2 × 1000 kVA corect, cuplă NO 2/3; secția 1 cu 1800 A de plecări pe 1443 A (V62 avertizat) |
| p63 | Respins | Q1 125 A Ir 106 A pentru 2 × 55 kW VFD (Pc 99 kW) — doar avertisment V14; uscătorul lipsește |
| p64 | **Respins (P0)** | Pompa de incendiu după Q1, cu termic de declanșare și ACYABY, identică cu cea tehnologică |
| p66 | Avizabil | TT complet și verificat; prize 16 A pe separator cu fuzibile 3P (uzual MCB) |
| p68 | Avizabil cu observații | PT + 12 plecări cu demaroare corecte; turn răcire și motoarele mici ale macaralei fără demaror; text mic pe A1, dar lizibil |

Lizibilitate: bună până la ≈ 15 plecări (p68, p15). Peste ≈ 30 de plecări (p38) planșa nu se poate citi — trebuie împărțire pe rânduri sau pe mai multe planșe.

## Comparativ cu r7 (4,5/10)

- **Reparat și confirmat:** cuplă PT 2 trafo NO 2/3 (p61), ștampila BLOCAT pe planșă (p18, p25), CEE, „N circuite a X kW”, enumerare „a) b)”, 690 V, întrebare DOL mare/PT mic, BMPT > 250 A întrebat, „pt” = pentru, W → kW.
- **Reparat doar pe forma testată (aceeași clasă cade din nou):** pompe de incendiu (r7 #31 → acum #12, #14, #64 = 3 × P0), plecare fantomă din sursă (BMPT → acum PT/ACB/„TG din PT”), comutator manual (doar textul avertismentului), cascade (merge doar „din care”), separatori de listă (tab-urile din r7 #68 tot nu merg: #2 cade).
- **Neatins:** compensare → CEF (din r6), cabluri în paralel (r7 #7), rutare la locuință (r7 #47), circuite mono pe 4P + ks pe circuite finale (r7 S11), Ib motor fără η (r7 S8), sursă nedeclarată → BMPT presupus (r6), contradicții numerice.
- **Nou găsit:** planșa ilizibilă la 44 de circuite; contradicție falsă 230 V + 400 V (#53); motoarele în HP pierdute fără mesaj (#29); „TG-normal” pus pe GE (#46); ACB declarat devine plecare.

Nota scade de la 4,5 la 3,5 pentru că frazele de data asta au fost mai „de birou” (teme, emailuri, Excel) și pentru că P0-ul de siguranță la incendiu s-a întors în trei forme noi.

## Recomandări (prioritate)

1. **P0 — dicționar de siguranță la incendiu pe consumator**, în toate tipurile de schemă (vezi mai sus) + BLOCANT în validare pentru DDR sau termic de declanșare în amontele unui consumator `siguranta`.
2. **Compensare ≠ CEF:** „kvar”, „baterie (de) condensatoare”, „compensare”, „cosφ … se dorește” → plecare de compensare (sau calcul Qc), niciodată tip CEF.
3. **Tokenizare:** tab-uri (tabel cu antet „Denumire / P / Buc”), „•”, „/”, prescurtări (mot, comp, ilum, plec, vent), „N buc x”, „X corpuri x Y W pe N circuite”, „NH 250A”, cablu + L pe plecare fără să piardă plecarea.
4. **Fraze de sursă și aparataj, nu plecări:** „din/alimentare PT … kVA”, „TG din PT X”, „ACB/MCCB/întreruptor general X A” → Q general/origine. „X kW, Y A” → verificare de coerență.
5. **Cascade:** „alimentează”, „din TD-A pleacă”, „TD-B are”, „->” → `copii`, pe orice nivel.
6. **Contradicții → BLOCANT/întrebare:** Q1 < Ib (și cu P declarată), Q1 > In_T sau Sc > Sn la tablou din PT propriu, cablu impus cu S și n paralel păstrate.
7. **Locuință doar la cuvinte de locuință** (casă, apartament, vilă) fără „din TG”/restaurant/bucătărie profesională.
8. **Mono în tablou tri:** iluminat/prize ≤ 3,7 kW → 1P+N, repartiție pe faze; ks = 1 pe iluminat; „230 V” + „400 V” în același TG nu e contradicție.
9. **Planșă cu > 25 de plecări:** împărțire pe rânduri / planșe.
10. **Desen conform textului:** comutator manual (simbol I-0-II, fără „anclanșare automată”), PTA (separator + MPR pe stâlp, fără celule/anvelopă).
