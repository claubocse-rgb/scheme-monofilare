# Runda 9 — testare industrială (TG/TD/PT/GE) — inginer proiectant

Data: 2026-10-26 · Flux: `interpretor.interpreteaza_local(text)` (fără cheie API, ca versiunea publică) → `constructor.genereaza` → `validare.valideaza` → `layout.build` → `render_svg` → PNG (cairosvg, 2400 px).
Fișiere: `teste/r9/industrial/fraze.json` (71 de fraze noi, cu așteptat / obținut / verdict / severitate), `pNN.png/.svg` (56 de planșe), `rezultate_brute.txt` (ieșirea completă per frază), `res.json`, `run.py` (rulare: `python3 teste/r9/industrial/run.py [id…]`), `fraze_src.py` (sursa frazelor; rescrie fraze.json fără verdicte), `verdicte.py` (completează verdictele).
Nu s-au citit tests/ și nici frazele vechi; s-au citit doar rapoartele r7/r8. engine/, tests/, static/ nemodificate.

Stiluri: temă de proiectare, tabel Excel cu tab-uri, CSV cu „;”, bilanț de puteri, emailuri (RO/EN), mesaje scurte și prescurtate, autocorecturi („scuze, 15 kW”, „TN-C-S… nu, TN-S”), liste numerotate, „;” și „|”, indentare, cascade „→”, „din TG pleacă / alimentează la rândul lui”, PT ulei/uscat/2 trafo/PTA/6–10–15–35 kV, celule MT, măsură MT/JT/BMPT cu TC, GE+ATS (vitali, PSI 1A+1R, hidranți, desfumare, lift pompieri, iluminat de siguranță), comutator manual, GE în paralel, compensare (RO/EN/fixă+automată), cabluri impuse/paralel/FE180/insuficiente, contradicții (Q1 < Ib, PT mic, mono/tri, TN-S din TT, BMPM + TG trifazat, două surse), în afara scopului (preț, memoriu, IT medical, VE).

## Nota: 4,5 / 10 (r8: 3,5/10)

| | Număr | % |
|---|---|---|
| Corect | 28 | 39 % |
| Parțial | 16 | 23 % |
| Greșit | 27 | 38 % |
| **P0** | **1** | |
| **P1** | **34** | |
| P2 (verdict principal) | 21 | |
| fără observații | 15 | |

Pe scurt: **progres real față de r8** — compensarea nu mai e CEF (#31), PTA-ul pe stâlp e desenat corect (#19), comutatorul manual are simbol I-0-II pe planșă (#29), CP/HP se convertesc (#41), 230 V + 400 V în același TD nu mai e contradicție (#43), CSV/tab cu antet merge (#65), bucătăria profesională / patiseria / CT nu mai devin locuință (#46, #47, #51), planșa cu 54 de circuite e împărțită pe rânduri (#45), iar pompele de incendiu / desfumarea dintr-un TG nu mai au DDR sau termic de declanșare (#25, #26, #28). **Rămân însă două clase mari:** (1) interpretorul pierde structura frazelor „de birou” — cascade (3/3 greșite), autocorecturi (2/2), prescurtări, tabel Excel fără coloană kW curată, BMPT cu TC, „1+1”, „3 extrudere”; (2) plecări/surse fantomă și contradicții nedetectate (Pi/Pa ca plecări, „DNO cut-out”, „TT și TC” = schema TT, Q1 40 A impus < Ib, Q1 400 A din BMPT presupus). **P0-ul PSI a coborât de la 3 la 1**, dar pe ramura GE+ATS (#27) e același defect ca r8 #12.

---

## P0 (1)

1. **#27 Stație de pompare PSI pe GE + ATS** („statie pompare PSI: 2 electropompe 30 kW (1A+1R), pompa pilot 1,1 kW, alimentare din PT 250 kVA si GE 100 kVA, ATS”). Planșa p27: **DDR-G bloc diferențial 300 mA A S pe ramura GE**, un singur circuit „Consumatori 31,1 kW”, cablu ACYABY (nu FE180/E90), pompele **nemarcate `siguranta`**, titlul „Grup electrogen + ATS” (nu tablou de siguranță), QR 50 A Ir 50 A pentru Ib ≈ 50 A + pornire. „statie pompare PSI” și „(1A+1R)” sunt raportate ca „nefolosite”, dar planșa se generează fără blocare. Aceeași clasă ca r7 #31 și r8 #12: dicționarul de siguranță funcționează acum în TG/TD (#25, #26, #28) și pe consumatorii numiți „lift pompieri / iluminat siguranță” (#24), dar **nu pe contextul tabloului în schema GE** („PSI”, „stație pompare PSI”, „electropompe”). Lipsește în continuare un BLOCANT în validare „consumator de siguranță în aval de DDR”.

## P1 sistemice (în ordinea impactului)

| # | Problemă | Fraze |
|---|---|---|
| S1 | **Cascade.** „→” (#14: TD1 dispare, motoarele urcă la TG), „Din TG pleacă … alimentează la rândul lui” (#15: contradicție falsă „două surse”), indentare (#16: TD-A/TD-B pierdute). r8 S4 neatins pentru formulări noi | 14, 15, 16 |
| S2 | **Autocorecturi ignorate.** „3 pompe de 11 kW, scuze, 15 kW” → 11 kW + 15 kW ca P tablou + V04 (#6); „TN-C-S… nu, TN-S” → TN-C-S (#7) | 6, 7 |
| S3 | **Plecări / surse fantomă (r8 S2, altă formă).** „P instalată / P absorbită” = plecări de 866 A / 609 A (#3); „DNO cut-out 100A” = plecare (#66); „TT și TC” din celula de măsură = schema TT → V28 (#21); „(1+1)” = 2 circuite de 1 kW (#49); „compensare fixă trafo 20 kvar” mănâncă kVA-ul PT-ului (#33) | 3, 21, 33, 49, 66 |
| S4 | **Liste pierdute.** Tabel Excel (#2: Malaxor 55 kW → P tablou, Bandă VFD „ignorată”), „tg 4 vent 5.5kw y/d” (#5), prescurtări „2xM 30kW, pr 6c, alim PT 630” (#53), „;” + „\|” (#54), „4 statii incarcare 22 kW” (#50), „TE lift pompieri 18 kW” (#63), „3 x 250 A” în EN (#32), „iluminat 6 circuite a 1 kW” → 1 circuit (#43), „3 extrudere 90 kW” → 1×90 (#67) | 2, 5, 32, 43, 50, 53, 54, 63, 67 |
| S5 | **Contradicții nedetectate.** Q1 40 A impus pentru 3×11 kW: Ib forțat la 40 A, nicio verificare (#37); TG din BMPT presupus cu Q1 400 A (BMPT ≤ 250 A) fără BLOCANT (#71); „TG trifazat din BMPM 40A” → branșament mono, consumatori pierduți (#70); 2 × 500 kVA în paralel → „măriți GE la 800 kVA” (#30) | 30, 37, 70, 71 |
| S6 | **Sursa nedeclarată → BMPT presupus fără întrebare** (r6–r8, neatins): 100 kW (#8), IT medical (#12), „DNO cut-out” (#66), „TG existent 400 A” (#71). BMPT fără schemă de legare la pământ → TN-C-S tacit (#40) | 8, 12, 40, 66, 71 |
| S7 | **Siguranța la incendiu aplicată pe tot tabloul.** Odată detectat un consumator de siguranță, tot TG/TD devine „TS — fără DDR” și **toate** plecările primesc FE180 și „SIGURANȚĂ”: rampe și iluminat normal (#25), 4 CTA (#26). Consumatorii normali trebuie să rămână normali (CTA se opresc la alarmă) și separați de cei de siguranță. În plus, sprinklerul rămâne în aval de Q1 general (MCCB 200 A cu termic) — trebuie racord înaintea Q1 sau sursă separată | 25, 26 |
| S8 | **Schema GE: consumatorii normali pe GE** (r8 #46 nereparat): „Consumatori vitali pe GE … Normali: HVAC, prize” → toți pe GE → V86 refuz (#24). Consumatori comasați într-un singur „Consumatori” (#27, #29, #67) | 24, 27, 67 |
| S9 | **Cabluri în paralel / impuse** (r7 #7, r8 #25, neatins): 2 × CYABY 3x185+95 → un cablu, V02/V03 BLOCANT (#34). Cablul NHXH 4x10/70 m al pompei de incendiu omoară plecarea (#35) | 34, 35 |
| S10 | **Rutare greșită la locuință** (r7 #47, r8 S7): magazin alimentar TT din BMPT → TE locuință cu prize bucătărie/baie inventate, ventilația = „centrală termică”, vitrinele pierdute (#11). Bucătăria/patiseria/CT sunt reparate, magazinul nu | 11 |
| S11 | **MT declarat ignorat:** celula cu întreruptor în vid + 50/51 → separator + SF 200 A; ACB → MCCB (#20). BMPT 160 cu TC 200/5 → branșament BMPTi cu TC 150/5 și plecări pierdute (#52) | 20, 52 |
| S12 | **Planșă blocată fără ștampilă.** #14 are V82 BLOCANT, dar p14 nu are „NEVERIFICAT — CALCUL BLOCAT” (celelalte 11 planșe blocate o au) | 14 |
| S13 | **Mono în tablou tri.** „12 circuite … monofazate, repartizate pe faze” → tot tabloul monofazat, Q1 2P (#44). Pod rulant: 4 motoare din TG pe gG fără contactor/termic (#68) | 44, 68 |

## P2 (selecție)

- **Text presupus / note contradictorii:** „în paralel pe barele JT” la cupla NO (#18); „trafo 20/0,4 kV, S"kQ 500 MVA rețea 20 kV” la 6 kV (#20); nota 3 „TN-S” când TN-C-S e declarat (#29, #34); „ATS AC-33B” în presupus la comutator manual (#29); ks 0,9 în presupus vs 0,6 pe planșă (#45).
- **Întrebări inutile:** „TG 1000 A cu 6 plecări de 160 A” (#17), „PT 160 kVA pentru hala cu consum 350 kW” (#38), „pentru pensiune” (#29), „pod rulant 10 t” (#68).
- **În afara scopului tratat ca date lipsă:** preț ATS → „puterea GE?” (#57); memoriu PT 630 → „kVA?” (#58).
- **Aparataj / cabluri:** Q3 Ir > In_T (#1: 1520 > 1443 A; #61: 598 > 577 A); cabluri supradimensionate din Ik implicit (#1, #9); CEE pe curba B (#43); 0,25 → „0,2 kW”, 0,55 → „0,6 kW” (#51, #69); 4x16 TN-S fără PE — PE adăugat tacit, fără observație (#69); faza L1/L2/L3 nemarcată pe circuitele mono (#45); nume „Noua pentru chiller” (#71), „Motor” (#41), „M 1” duplicat (#53).

## Ce funcționează bine (confirmat pe planșe)

- **PT:** 1000 kVA cu 6 plecări VFD/Y-Δ/DOL (p01), 2×630 cu semibare și cuplă NO 2/3 (p18), PTA pe stâlp cu separator exterior + MPR + TDJT (p19, reparat), 6 kV pe aparate 7,2 kV (p20), 20/15 kV și 35 kV → întrebare.
- **Compensare** ca plecare (p31), inclusiv în engleză (#32) — reparat după trei runde.
- **Siguranță în TG/TD:** fără DDR, termic doar la semnalizare, NHXH FE180/E90, titlu „TS — fără DDR” (p25, p26, p28).
- **Comutator manual** I-0-II, AC-23B, „tablou de comutare MANUALĂ” (p29) — reparat pe planșă.
- **Blocare vizibilă:** NEVERIFICAT + nota 0 pe 11 din 12 planșe blocate (p03, p34); cablu impus insuficient → V02/V03/V20 (#36).
- **Parsare reparată:** CSV cu antet (#65), listă numerotată (#55), CP/HP (#41), kVA pe consumatori (#42), mixt 230/400 V (#43), 54 de circuite pe rânduri (p45), engleza (#4, #32).
- **Întrebări bune:** mono/motor tri (#10), TN-C+DDR (#13), DOL 400 kW (#48), TN-S din TT (#56), două surse (#59), „câteva pompe” (#60), PT 160 / 350 kW blocat (#38).

## Planșe judecate ca la avizare (16)

| Planșă | Verdict avizare | Observații |
|---|---|---|
| p01 | Avizabil cu observații | PT 1000 + 6 plecări corecte; Q3 Ir 1520 A > In_T 1443 A; compresoare 15 kW pe CYABY 5×35 (supradim.) |
| p03 | Respins (blocat corect) | Pi / Pa desenate ca plecări de 866 / 609 A, cele 3 TD lipsesc; ștampila vizibilă |
| p14 | Respins | TE1 suprapus peste carcasa TG, TD1 lipsă, motoarele la TG; V82 BLOCANT dar **fără ștampilă** |
| p18 | Avizabil | 2×630, cuplă NO interblocaj 2/3, secții separate, măsură MT |
| p19 | Avizabil | PTA: LEA, separator exterior, MPR 10 A, TDJT la stâlp, măsură semidirectă; Q3 Ir 237,5 A ≈ In_T 231 A (la limită) |
| p20 | Respins | Celula cu întreruptor în vid + 50/51 cerută, desenat separator + SF 200 A; ACB cerut, MCCB desenat |
| p25 | Avizabil cu observații importante | Sprinkler corect (Y/Δ, termic semnalizare, FE180), dar după Q1 general cu termic; rampe/iluminat normal marcate siguranță; rampe fără contactor |
| p26 | Respins pe concepție | CTA normale în tabloul de siguranță, FE180 fără DDR; desfumarea corectă |
| p27 | **Respins (P0)** | Pompe PSI pe DDR-G 300 mA, „Consumatori” unic, ACYABY, nemarcate siguranță |
| p29 | Avizabil cu observații | Comutator I-0-II corect; consumatori comasați; nota 3 TN-S vs TN-C-S |
| p31 | Avizabil cu observații | Compensare 200 kvar ca plecare, MCCB 500 A, 2×CYY-F 4×120; fără simbol baterie / regulator / filtru |
| p34 | Respins (blocat) | 2 cabluri în paralel impuse → 1 cablu → V02/V03; ștampila vizibilă |
| p43 | Avizabil cu observații | 15 plecări lizibile; iluminatul 6 circuite = 1 circuit; CEE curba B; pod rulant fără demaror |
| p45 | Avizabil cu observații | 54 circuite pe 4 rânduri (reparat față de r8 p38); fazele nemarcate; listă de materiale în anexă |
| p67 | Respins | 3 extrudere 90 kW → „Consumatori 90 kW”; QR 160 A pentru 270 kW; DDR-G pe GE |
| p71 | Respins | „TG existent” desenat ca TG nou din BMPT presupus cu Q1 400 A (> 250 A) fără BLOCANT |

Lizibilitatea e bună până la 15 plecări pe un rând (p43, A1) și acceptabilă la 54 de circuite pe 4 rânduri (p45).

## Comparativ cu r8 (3,5/10)

- **Reparat și confirmat pe planșă:** compensare ≠ CEF (r6–r8 S3), PTA (r8 S10), comutator manual pe planșă (r8 S9), siguranța la incendiu în TG/TD fără DDR / fără termic de declanșare (r8 P0 #14, #64), HP (r8 #29), 230 + 400 V (r8 #53), bucătărie → nu locuință (r8 #65), planșe > 25 plecări (r8 #38), CSV/tab cu antet (r8 #2, parțial).
- **Reparat doar pe forma testată:** PSI (în TG da, în GE+ATS nu — #27 P0), plecări fantomă din sursă (BMPT/PT/ACB da; Pi/Pa, „DNO cut-out”, „TT și TC” nu), cascade (merge doar „din care”), rutarea la locuință (bucătărie da, magazin TT nu).
- **Neatins:** cabluri în paralel (r7 #7 → r8 #25 → r9 #34), normali pe GE (r8 #46 → r9 #24), sursă nedeclarată → BMPT presupus (r6 → r9 #8), Q1 impus < Ib (r8 S5 → r9 #37), consumatori comasați în schema GE.
- **Nou găsit:** autocorecturile sunt ignorate (#6, #7); „TT și TC” = schemă TT (#21); „(1+1)” = circuite fantomă (#49); siguranța aplicată pe tot tabloul (#25, #26); ștampila lipsește la V82 (#14); BMPT presupus cu Q1 400 A (#71).

Nota crește de la 3,5 la 4,5: corectele urcă de la 26 % la 39 %, greșitele scad de la 53 % la 38 %, P0 de la 3 la 1, iar motorul de calcul și desenul rămân solide când intrarea e corectă.

## Recomandări (prioritate)

1. **P0 — siguranța în schema GE/ATS:** contextul „PSI / stație pompare PSI / sprinkler / hidranți” pe tabloul GE marchează consumatorii `siguranta`, fără DDR-G pe ramura lor, FE180, „1A+1R” = o plecare + rezervă (neînsumată). BLOCANT în validare pentru orice consumator `siguranta` în aval de DDR.
2. **Siguranța pe consumator, nu pe tablou:** în TG/TD mixt, doar consumatorii de siguranță primesc regimul special; racord înaintea Q1 (sau secție separată) pentru pompele de incendiu.
3. **Autocorecturi:** „scuze / de fapt / nu, …” înlocuiește valoarea sau termenul anterior.
4. **Cascade:** „→”, „din X pleacă”, „X alimentează (la rândul lui)”, indentarea → `copii`; „din TG” într-o frază despre TG nu înseamnă a doua sursă.
5. **Nu plecări:** „P instalată / absorbită / Pi / Pa” = bilanț; „DNO cut-out / BMPT X A” = origine; „TT și TC” lângă „celulă de măsură” = transformatoare de măsură; „(1+1)”, „1A+1R” = rezervă.
6. **Contradicții → BLOCANT:** Q1 impus < Ib din bilanț; BMPT presupus > 250 A; BMPM + tablou trifazat; „N extrudere / N buc” însumate pe GE.
7. **Cabluri în paralel impuse:** păstrează `n_paralel` (a patra rundă la rând).
8. **Sursă nedeclarată:** întrebare, nu BMPT presupus; „TG existent X A” = origine `tg_existent`, nu tablou nou.
9. **MT declarat:** „întreruptor în vid + 50/51” → celulă cu întreruptor; „ACB” → simbol și listă ACB.
10. **Ștampila NEVERIFICAT pentru orice BLOCANT** (inclusiv V82).

---

## Rezultate per frază

Legendă: C = corect, P = parțial, G = greșit. ⏎ = rând nou, ⇥ = tab.

| # | Stil | Frază (prescurtat) | Așteptat | Obținut | Verdict | Sev. |
|---|---|---|---|---|---|---|
| 1 | tema | Tema de proiectare — Hală producție mobilier, Oradea. Alimentare: PT propriu 1000 kVA 20/0… | TG din PT 1000 TN-S; 6 plecări (VFD 45, Y/Δ 30, 2×compresor 15 DOL, iluminat 12, TD birouri 25) | PT 1000 + 6 plecări corecte (VFD, Y/Δ cu termic pe ramura Δ, 2 compresoare); Q3 Ir 1520 A > In_T 1443 A; compresoare 15 kW pe CYABY 5×35 (supradim. din Ik) | C | P2 |
| 2 | excel_tab | Poz ⇥ Utilaj ⇥ Pi (kW) ⇥ Buc ⇥ Pornire ⏎ 1 ⇥ Pompa apa racire ⇥ 7,5 ⇥ 2 ⇥ DOL ⏎ 2 ⇥ Ventil… | TD din TG existent TN-S; 8 plecări cu demaroarele din coloana Pornire | Tabel Excel: Malaxor 55 kW soft devine P tablou (nedesenat), rândul Bandă 4×3 kW VFD „ignorat”; doar 3 plecări din 8 | G | P1 |
| 3 | bilant | Bilanț energetic: P instalată 540 kW, P absorbită 380 kW, cos φ mediu 0,88. Alimentare PT … | TG din PT 630 uscat; 3 TD; Pi/Pa nu devin plecări; rețea: PT → tri, schema de legare la pământ întrebată sau presupusă declarat | P instalată / P absorbită = plecări fantomă (866 A / 609 A); cele 3 TD întrebate ca „nefolosite”; blocat V04/V60/V62 | G | P1 |
| 4 | email_en | Hi, please prepare the SLD for the new MDB: incoming from existing 1250 kVA transformer, T… | TG din PT 1250; 2 chiller 220, 3 AHU VFD 15, iluminat 20, UPS 60 kVA (≈54 kW) ca plecare; semnătura ignorată | Email EN: PT 1250, 2 chiller, 3 AHU VFD, iluminat, UPS 60 kVA→54 kW; semnătura ignorată | C | — |
| 5 | scurt | tg 4 vent 5.5kw y/d tn-s din tgd | TD din TGD, TN-S, 4 ventilatoare 5,5 kW Y/Δ (sau DOL cu observație) | „tg 4 vent 5.5kw y/d …” → 0 plecări, P = 5,5 kW, V07; întreabă mono/tri | G | P1 |
| 6 | autocorectura | TG cu 3 pompe de 11 kW, scuze, 15 kW, din PT 400 kVA, TN-S | 3 pompe de 15 kW (corectura aplicată), din PT 400 | Autocorectura „scuze, 15 kW” ignorată: 3×11 kW, 15 kW → P tablou → Q1 C32, V04 BLOCANT | G | P1 |
| 7 | autocorectura | TD atelier din TG, TN-C-S... nu, TN-S. Plecari: strung 7,5 kW, freza 5,5 kW | TN-S (corectura), 2 motoare | Autocorectura „TN-C-S… nu, TN-S” ignorată: desenat TN-C-S | G | P1 |
| 8 | retea_lipsa | TG pentru hala cu 3 compresoare de 30 kW si iluminat 10 kW | sursa și rețeaua nedeclarate → întrebare (nu BMPT/TN presupus) | Sursă/rețea nedeclarate → BMPT presupus, Q1 160 A, fără întrebare (doar text presupus) | G | P1 |
| 9 | mono | tablou monofazat 230V pentru ghereta paza: iluminat 0,6 kW, prize 2 kW, aer conditionat 1,… | TD mono din TG, 3 circuite 1P+N, NU locuință (fără BMPM/contor) | TD monofazat 3 circuite 2P, DDR 30 mA pe prize, NU locuință; C1 ACYABY 3×25 pt 20 A (Ik implicit) | C | P2 |
| 10 | contradictie | tablou monofazat cu motor trifazat 4 kW si iluminat 1 kW, TN-S, din TG | contradicție mono vs motor trifazat → întrebare | Contradicție mono / motor trifazat → întrebare I08 | C | — |
| 11 | TT | magazin alimentar parter, bransament trifazat TT, BMPT 63 A: vitrine frigorifice 4 x 1,5 k… | TT cu DDR; vitrine 4 circuite mono; prize 6 circuite (putere întrebată/presupusă 30 mA); ventilație motor | Magazin TT → LOCUINȚĂ: prize bucătărie/baie inventate, ventilația = „Centrală termică”, vitrine pierdute, BMPTd-100 cu contor | G | P1 |
| 12 | IT | sala operatie: tablou IT medical din trafo de separare 8 kVA, prize 6 circuite | IT medical → în afara domeniului / întrebare, nu TN tăcut | IT medical nerecunoscut: plecare „tablou IT medical din trafo de separare” 7,2 kW + 6 prize, BMPT presupus | G | P1 |
| 13 | TN-C | tablou vechi in schema TN-C cu DDR 30 mA pe prize, motor 4 kW, din BMPT 32 A | TN-C + DDR → BLOCANT (DDR nu funcționează pe PEN) | TN-C + DDR → întrebare + V27 BLOCANT | C | — |
| 14 | cascada | TG (din PT 800 kVA, TN-S) → TD1 hala (motoare 3 x 11 kW) → TE1 linie ambalare (2 benzi 2,2… | cascadă 3 niveluri TG→TD1→TE1 | Cascadă „→”: TD1 hala pierdut (motoarele urcate la TG), TE1 sub TG; V82 BLOCANT fără ștampila NEVERIFICAT pe planșă | G | P1 |
| 15 | cascada | TG hotel din PT 630 kVA, TN-S. Din TG pleaca TD-Bucatarie 80 kW si TD-Etaje 120 kW; TD-Eta… | TG→TD-Bucătărie, TD-Etaje→TE-E1..3 (fără dublă numărare) | „Din TG pleacă TD-…” → contradicție falsă „două surse” (I08), refuz; nume „pleaca TD-Bucatarie”, „la randul lui TE-E1” | G | P1 |
| 16 | cascada_indent | TG ⏎   - TD-A ⏎      - pompa 5,5 kW ⏎      - ventilator 3 kW ⏎   - TD-B ⏎      - iluminat … | cascadă din indentare: TD-A (pompa, vent), TD-B (iluminat) | Cascadă din indentare: TD-A, TD-B și iluminatul pierdute; pompa+vent sub TG; P = 6 kW | G | P1 |
| 17 | PT_ulei | PT 630 kVA in anvelopa beton, trafo ulei 20/0,4 kV, celule: 2 linie + 1 trafo cu sigurante… | PT 630 ulei 20 kV, 2L+T sig., măsură JT, Q JT 1000 A, 6×160 A | PT 630 ulei, 2L+T sig., măsură JT, 6×160 A corect; întrebare inutilă despre „TG 1000 A cu 6 plecări” | P | P2 |
| 18 | PT_2trafo | PT 2 x 630 kVA uscat 20/0,4 kV, cupla JT normal deschisa, fiecare bara cate 3 plecari 250 … | 2 trafo, 2 semibare, cuplă NO, 3+3 plecări 250 A | 2×630 uscat, cuplă NO 2/3, 3+3 plecări corect; presupus „în paralel pe barele JT”; celulă măsură MT adăugată nedeclarat | C | P2 |
| 19 | PTA | post trafo aerian 160 kVA 20/0,4 kV pe stalp, separator tripolar + sigurante MT, cutie dis… | PTA pe stâlp: separator + MPR, fără celule/anvelopă; 3×100 A | PTA: LEA + separator exterior + MPR pe stâlp + TDJT la baza stâlpului — reparat (r6/r8) | C | — |
| 20 | MT_6kV | racord 6 kV din statia fabricii, trafo 1000 kVA 6/0,4 kV ulei, celula intreruptor vid cu p… | PT 6 kV (7,2 kV), întrerupător vid 50/51, ACB 1600 general, 2 plecări | 6 kV corect (7,2 kV), dar celula cu întreruptor în vid + 50/51 → separator + SF 200 A; ACB → MCCB; presupus „trafo 20/0,4, 500 MVA rețea 20 kV” | P | P1 |
| 21 | MT_10kV | PT 400 kVA 10/0,4 kV, masura pe medie tensiune (celula masura cu TT si TC), plecari JT: 3 … | PT 10 kV (12 kV), celulă de măsură MT, 3×200 A | „celula masura cu TT si TC” → schema TT → V28 BLOCANT; „3 x 200 A” pierdut | G | P1 |
| 22 | contradictie | PT 250 kVA 20/0,4 kV, reteaua MT este de 15 kV, plecari 2 x 160 A | contradicție 20 vs 15 kV → întrebare | 20 vs 15 kV → întrebare | C | — |
| 23 | MT_35 | PT 1600 kVA 35/0,4 kV, plecari 4 x 630 A | 35 kV în afara domeniului → refuz/întrebare | 35 kV → refuz I12 cu întrebare | C | — |
| 24 | GE_vitali | TG cladire birouri din PT 630 kVA, TN-S. Consumatori vitali pe GE 200 kVA cu ATS: server 3… | secție normală (HVAC, prize) + secție vitală pe GE/ATS; lift pompieri și iluminat de siguranță marcați siguranță (fără DDR, FE180) | Normalii (HVAC 150, prize 40) puși pe GE → V86 refuz, „măriți GE la 300 kVA” (r8 #46 nereparat); lift pompieri / il. siguranță marcate corect | G | P1 |
| 25 | PSI_TG | TG depozit din PT 400 kVA TN-S, plecari: pompa sprinkler 75 kW stea-triunghi, pompa jockey… | sprinkler + jockey siguranță: fără DDR, termic doar semnalizare, FE180, racord înaintea Q1 / circuit separat | Sprinkler: fără DDR, termic doar semnalizare, FE180 — bine; DAR racord după Q1 general (MCCB 200 A); tot TG-ul devine „TS”, rampe/iluminat normal pe FE180 fără DDR; rampe (motoare) pe gG 2 A fără contactor | P | P1 |
| 26 | desfumare | TD ventilatie din TG, TN-S: 2 ventilatoare desfumare 7,5 kW, ventilator presurizare scara … | desfumare + presurizare = siguranță (fără termic de declanșare, FE180); CTA normale | Desfumare/presurizare corecte (semnalizare, FE180); CTA normale marcate SIGURANȚĂ în același TS (nu se deconectează la incendiu), CTA fără demaror | P | P1 |
| 27 | PSI_GE | statie pompare PSI: 2 electropompe 30 kW (1A+1R), pompa pilot 1,1 kW, alimentare din PT 25… | siguranță; 1A+1R nu se însumează; fără DDR pe ramura GE; FE180 | Stație PSI pe GE+ATS: „statie pompare PSI”, „1A+1R” nefolosite, pompele NEMARCATE siguranță, DDR-G 300 mA pe ramura GE, un singur „Consumatori”, cablu ACYABY, QR 50 A < Ib | G | P0 |
| 28 | hidranti | TE hidranti exteriori: pompa 18,5 kW, din TG, TN-S, cablu rezistent la foc | siguranță, FE180, fără DDR/termic de declanșare | TE hidranți: TS, FE180, termic semnalizare; Q1 MCB C50 amonte de MCCB 40 (selectivitate) | C | P2 |
| 29 | comutator_manual | comutator manual retea-generator pentru pensiune, GE 30 kVA trifazat, consumatori: central… | comutator manual I-0-II (nu ATS), 3 plecări; NU locuință | Comutator manual desenat I-0-II, AC-23B, TCS — reparat pe planșă; consumatori comasați; presupus încă „ATS AC-33B”; nota 3 TN-S vs TN-C-S | P | P2 |
| 30 | GE_paralel | doua GE 500 kVA sincronizate in paralel pentru data center 600 kW | paralel GE în afara domeniului → întrebare/refuz | Refuz V86 corect ca rezultat, dar „măriți GE la 800 kVA” ignoră 2×500; avertisment despre „paralel cu rețeaua” (era paralel între GE) | P | P2 |
| 31 | compensare | TG din PT 1000 kVA TN-S, plecari: TD1 300 kW, TD2 200 kW, baterie condensatoare 200 kvar a… | plecare compensare 200 kvar + 2 TD; NU CEF | Compensare 200 kvar = plecare (MCCB 500 A, 2×CYY-F 4×120) — reparat (r6–r8); simbol baterie/filtru lipsă | C | P2 |
| 32 | compensare_en | add power factor correction 150 kvar detuned to the MDB fed from 800 kVA transformer, TN-S… | TG din PT 800, compensare 150 kvar cu filtru, 3×250 A | Compensare 150 kvar EN corectă, dar „3 x 250 A” pierdut + întrebare plecări | P | P1 |
| 33 | compensare_PT | compensare fixa trafo 20 kvar + baterie automata 120 kvar in PT 630 kVA 20/0,4 kV, plecari… | PT 630, compensare fixă + automată, 4×250 A | „compensare fixa trafo 20 kvar … PT 630 kVA” → refuz „lipsește kVA” (630 luat de altceva) | G | P1 |
| 34 | cablu_paralel | alimentare TG: 2 cabluri CYABY 3x185+95 in paralel, 60 m, din PT 630 kVA, TN-C-S; plecari … | C1 = 2 × CYABY 3×185+95 păstrat; TN-C-S | 2 cabluri CYABY 3x185+95 în paralel → 1 cablu → V02/V03 BLOCANT (r7 #7, r8 #25 nereparat); nota 3 TN-S vs TN-C-S | G | P1 |
| 35 | cablu_foc | TD din TG TN-S: pompa incendiu 22 kW cu cablu NHXH FE180 E90 4x10 la 70 m, iluminat 4 kW | pompa incendiu siguranță cu NHXH 4×10 / 70 m impus; iluminat normal | Pompa incendiu cu cablu impus NHXH 4x10/70 m pierdută (întrebare); 70 m mutat pe alimentare; 22 kW = P tablou | G | P1 |
| 36 | cablu_insuf | plecare compresor 55 kW cu CYABY 5x10 la 120 m, TD din TG, TN-S | cablu impus insuficient (Iz ≈ 60 A < Ib ≈ 100 A) → BLOCANT vizibil | Cablu impus 5x10/120 m pt 55 kW → V02/V03/V20 BLOCANT vizibil; CYABY → CYY-F | C | P2 |
| 37 | contradictie | TD din TG TN-S cu intrerupator general 40 A, plecari: 3 motoare 11 kW | Q1 40 A < Ib ≈ 60 A → BLOCANT/întrebare | Q1 impus 40 A pentru 3×11 kW (Ib ≈ 56 A): Ib forțat = 40 A, nicio verificare, planșă „finală” | G | P1 |
| 38 | contradictie | PT 160 kVA pentru hala cu consum 350 kW, TN-S, plecari TD1 200 kW, TD2 150 kW | 350 kW pe 160 kVA → BLOCANT/întrebare | PT 160 / 350 kW → V62 + V40 BLOCANT; întrebare inutilă pe fraza cu „consum 350 kW” | C | P2 |
| 39 | GE_subdim | GE 60 kVA cu ATS pentru pompe 2 x 37 kW pornire directa, din BMPT 160 A, TN-C-S | GE subdimensionat + DOL pe GE → întrebare/BLOCANT | GE 60 kVA / 2×37 kW DOL → refuz V86; sugestia „100 kVA” ignoră pornirea DOL | P | P2 |
| 40 | retea_lipsa | tablou din BMPT 50 A: pompa 5,5 kW, iluminat 2 kW | schema de legare la pământ nedeclarată → întrebare (TN-C-S/TT), nu presupusă | BMPT fără schemă → TN-C-S presupus fără întrebare; iluminat 2 kW mono 2P corect | P | P2 |
| 41 | HP | TD din TG TN-S: 3 motoare 15 CP si un motor de 7,5 HP | 3×11 kW + 5,5 kW (conversie CP/HP) | CP/HP convertite (11 / 5,6 kW) — reparat r8 #29; nume „Motor” | C | P2 |
| 42 | kVA_cons | UPS 40 kVA si aer conditionat 3 x 7 kW, din TG existent, TN-S | UPS 40 kVA (≈36 kW) + 3 AC 7 kW | UPS 40 kVA → 36 kW + 3 AC | C | — |
| 43 | mixt | TD hala TN-S din TG: 8 circuite prize monofazate 16A, 4 prize CEE 400V 32A, iluminat 6 cir… | 8 prize mono + 4 CEE tri + 6 iluminat mono + pod rulant; fără contradicție mono/tri | Mixt 230/400 fără contradicție falsă — reparat; „iluminat 6 circuite a 1 kW” → 1 circuit; CEE pe curba B; pod rulant fără demaror | P | P1 |
| 44 | n_circuite | 12 circuite iluminat LED de cate 0,6 kW fiecare, monofazate, repartizate pe faze, TD din T… | 12 × 1P+N 0,6 kW repartizate L1/L2/L3 | „monofazate, repartizate pe faze” → TOT tabloul monofazat (Q1 2P C40) | P | P1 |
| 45 | multe | TD birouri etaj: 36 circuite prize a 2 kW si 18 circuite iluminat a 0,5 kW, din TG, TN-S | 54 circuite mono, planșă lizibilă (împărțită) | 54 circuite mono 2P, planșa împărțită pe 4 rânduri — reparat r8 #38; ks 0,9 în presupus vs 0,6 pe planșă; faza L1/L2/L3 nemarcată | C | P2 |
| 46 | patiserie | TG patiserie din BMPT 125 A TN-C-S: cuptor convectie 18 kW, cuptor pe vatra 2 x 24 kW, mix… | TG cu 5 plecări (2 cuptoare vatră), NU locuință; Q1 125 | Patiserie din BMPT 125: 5 plecări, NU locuință | C | — |
| 47 | bucatarie | bucatarie profesionala restaurant: plita inductie 2 x 10 kW, friteuza 15 kW, cuptor combi … | TD bucătărie 6 plecări, NU locuință | Bucătărie profesională: 6 plecări, NU locuință — reparat r8 #65 | C | — |
| 48 | DOL_mare | chiller 400 kW pornire directa din PT 630 kVA, TN-S | avertisment/întrebare DOL 400 kW pe 630 kVA | DOL 400 kW / PT 630 → întrebare + V22 | C | — |
| 49 | rezerva | statie epurare: pompa 90 kW soft starter si pompa 90 kW rezerva (1+1), suflanta 45 kW VFD,… | 2 pompe soft-starter, rezerva neînsumată (ks), suflantă VFD | „(1+1)” → sub-tablou cu 2 circuite fantomă de 1 kW → refuz I03 | G | P1 |
| 50 | VE | 4 statii incarcare 22 kW si 1 statie DC 50 kW in parcarea magazinului, din TG existent, TN… | 5 plecări VE cu DDR tip A-EV/B, sau întrebare/în afara domeniului | Stații VE pierdute → V07 + întrebare | G | P1 |
| 51 | CT | tablou centrala termica din TG, TN-S: pompa de caldura aer-apa 25 kW trifazata, rezistenta… | TD CT 5 plecări, NU locuință | CT: 5 plecări, NU locuință; 0,25 → 0,2 kW; pompe circulație pe MCCB 16 A + CYABY 5×6 | C | P2 |
| 52 | masura_BMPT | BMPT 160 A cu masura indirecta cu TC 200/5, TG magazin TN-C-S: HVAC 40 kW, iluminat 20 kW,… | BMPT 160 cu TC 200/5, 4 plecări | BMPT 160 cu TC 200/5 → schemă de branșament, 4 plecări pierdute, TC 150/5, Pa = HVAC 40 kW, întrebare BMPTd-100 | G | P1 |
| 53 | prescurtari | TGD hala: 2xM 30kW Y/D, 4xM 4kW DOL, il 10kW, pr 6c, alim PT 630 uscat tns | 2 motoare Y/Δ 30, 4 motoare DOL 4, iluminat 10, 6 circuite prize; PT 630 uscat TN-S | Prescurtări: „PT 630” pierdut → refuz „lipsește kVA”; „pr 6c” pierdut; nume M 1/M 2 duplicate | G | P1 |
| 54 | separatori | TD: vent 4 kW; pompa 3 kW; il 1,5 kW / sursa TG / TN-S | 3 plecări din „;” și „/” | „;” și „/”: iluminat 1,5 kW → P tablou (V14); întrebare mono/tri deși are motoare 4 kW | G | P1 |
| 55 | lista_num | 1. Compresor surub 45 kW VFD ⏎ 2. Uscator 2,2 kW ⏎ 3. Pompa condens 0,75 kW ⏎ Alimentare d… | 3 plecări, VFD; alimentare L 70 m | Listă numerotată 1. 2. 3. + cablu 70 m pe alimentare — corect | C | — |
| 56 | contradictie | TG TN-S alimentat din BMPT, reteaua furnizorului fiind TT, plecari: pompa 4 kW, iluminat 2… | TN-S din rețea TT imposibil fără trafo propriu → întrebare | TN-S vs rețea TT → întrebare | C | — |
| 57 | scop | cat costa un ATS de 250 A? | în afara scopului (preț) | Preț ATS → „lipsește puterea GE” (trebuia I12 în afara scopului) | P | P2 |
| 58 | scop | fa-mi te rog si memoriul tehnic pentru PT-ul de 630 | în afara scopului / întrebare despre schemă, nu plecări inventate | Memoriu PT 630 → „lipsește kVA” (630 scris); memoriul nu e semnalat în afara scopului | P | P2 |
| 59 | doua_surse | TG alimentat din PT propriu 400 kVA si din BMPT 100 A, TN-S, plecari: TD1 50 kW, TD2 40 kW | două surse fără ATS/cuplă → întrebare | PT + BMPT → întrebare două surse | C | — |
| 60 | vag | TG cu cateva pompe si iluminat, din PT 400 kVA TN-S | puteri lipsă → întrebare | „câteva pompe” → întrebare puteri | C | — |
| 61 | PT_supra | PT 400 kVA 20/0,4 kV cu plecari 4 x 250 A + 2 x 160 A | 6 plecări; Σ In 1320 A > In_T 577 A → avertisment (coeficient de simultaneitate) | PT 400 cu 1320 A plecări → V62 avertisment; Q3 Ir 598 A > In_T 577 A | C | P2 |
| 62 | mono_motoare | tablou put ferma din TG, TN-S: pompa submersibila monofazata 1,5 kW si hidrofor 0,75 kW mo… | TD (mono sau tri) cu 2 motoare monofazate 1P+N; NU locuință | Motoare monofazate 2P cu KM+F; întrebare mono/tri legitimă | C | P2 |
| 63 | lift_pompieri | TE lift pompieri 18 kW din TG TN-S, cablu E90 | siguranță: fără DDR/termic, cablu E90/FE180 | „TE lift pompieri 18 kW … E90” → 0 plecări, V07, întrebare (siguranța nu e aplicată) | G | P1 |
| 64 | ilum_sig | tablou iluminat de siguranta 2 kW din TG, TN-S | siguranță, fără DDR, alimentare înaintea Q1 sau semnalizare | Tablou iluminat de siguranță recunoscut (TS), cere circuitele și mono/tri | P | P2 |
| 65 | csv | Denumire;Putere;Cantitate ⏎ Ventilator;2,2;6 ⏎ Pompa;4;2 ⏎ Incalzitor;9;3 ⏎ TD din TG, TN-… | 6 vent 2,2 + 2 pompe 4 + 3 încălzitoare 9 = 11 plecări | CSV cu „;” și antet → 11 plecări — corect | C | — |
| 66 | en_scurt | LV panel TN-C-S, fed from DNO cut-out 100A 3ph, 5 x 7.5 kW pumps DOL | BMPT 100 A tri TN-C-S, 5 pompe DOL | „DNO cut-out 100A” → plecare fantomă 100 A + sursă nedeclarată (BMPT presupus) | G | P1 |
| 67 | GE_tot | TG din PT 630 kVA cu 2 intrari: retea si GE 400 kVA, ATS, toti consumatorii pe GE: 3 extru… | ATS general rețea/GE, 3 extrudere 90 kW (GE 400 kVA ≈ 320 kW > 270 kW) | „3 extrudere 90 kW” → un consumator de 90 kW; QR 160 A pt 270 kW reali; „TG … cu 2 intrari” întrebat | G | P1 |
| 68 | pod_rulant | pod rulant 10 t: ridicare 7,5 kW, translatie 2 x 1,5 kW, directie 0,75 kW, alimentat prin … | TD pod rulant cu 4 motoare cu demaroare (sau 1 plecare pod) | Pod rulant: 4 motoare din TG pe gG fără contactor/termic; „pod rulant 10 t” întrebat | P | P1 |
| 69 | sera | TD sera: 10 ventilatoare a cate 0,55 kW, 2 pompe irigatie 3 kW, sistem umbrire 0,37 kW, di… | 13 plecări; cablul impus 4×16 TN-S fără PE separat → observație | 13 plecări corecte; 0,55 → 0,6 kW; 4x16 TN-S → PE adăugat tacit | C | P2 |
| 70 | BMPM_tri | TG trifazat din BMPM 40A, TN-C-S, pompa 4 kW, iluminat 1 kW | BMPM (mono) vs TG trifazat → întrebare | TG trifazat din BMPM → branșament monofazat, pompa/iluminat pierdute, fără contradicție | G | P1 |
| 71 | existent | Tabloul general existent 400 A, TN-S, se adauga plecare noua pentru chiller 120 kW | TG existent 400 A + plecare chiller 120 kW | „TG existent 400 A” → TG nou din BMPT presupus cu Q1 400 A (> 250 A, fără BLOCANT); nume „Noua pentru chiller” | P | P1 |
