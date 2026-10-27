# Runda 11 — testare industrială (inginer proiectant ANRE III/IV), FĂRĂ cheie API

Motor: `interpretor.interpreteaza(text, foloseste_llm=False)` → `constructor.genereaza(intrare_fizica, cartus=…)` exact ca în `app.py /api/chat` → `validare` → `layout`/`render_svg` → PNG (cairosvg, 2400 px).
66 de fraze complet noi (`teste/r11/industrial/fraze_src.py`, id-uri j01…j66), rezultate brute în `teste/r11/industrial/fraze.json` (inclusiv `intelegere` = textul tabelului de confirmare și `neconsumat`), planșe `jNN.svg` (51) și `jNN.png` (23). Reproducere: `python3 teste/r11/industrial/run.py [jNN …]`.
Nu s-au citit `tests/` sau fraze.json vechi; engine/, tests/, static/ nemodificate.

## Notă: **4,0 / 10** (r10: 4,0)

| | nr. | % |
|---|---|---|
| corect | 22 | 33 % |
| parțial | 18 | 27 % |
| greșit | 26 | 39 % |
| **P0** | **9** | j05, j08, j30, j33, j41, j45, j46, j55, j57 |
| P1 | 33 | |
| P2 | ~16 + observații sistemice | |

Frazele au fost voit „de proiect real” și cu capcane: PT 2 trafo (separat / paralel / cuplă MT+JT), PTA, celule MT, GE izolat, comutator 1-0-2, ATS doar pe vitali, ATS între trafo, pompe de incendiu, desfumare, UPS, compensare, cabluri impuse și în paralel, Excel cu tab și cu „;”, liste numerotate, cascade cu „->”, autocorecturi, mesaje scurte, EN.

**Ce s-a îmbunătățit față de r10** (verificat pe fraze noi, echivalente ca temă):
- 2 trafo 1600 kVA **în paralel**: 2 celule trafo, cuplă QC normal închisă, **Ik3 = 75,2 kA** la bara TGJT, ACB Icu 85 kA (j06) — r10 i30 avea 1 trafo / 31 kA.
- GE **„fără rețea”**: sursă unică, fără ATS, notă „site izolat” pe planșă (j10) — r10 i43 inventa rețea. (dar vezi j45: „izolat” singur NU e recunoscut)
- PTA pe stâlp cu separator + MPR, măsură semidirectă TC 250/5 pe JT (j07).
- Comutator manual I-0-II desenat corect cu interblocaj (j09).
- Tablou sprinklere / desfumare / pompă incendiu: fără DDR, RT „doar semnalizare”, NHXH FE180/E90, Y-Δ cu RT pe ramura Δ (j13, j14, j64) — și refuză tăcut cererea greșită „DDR 30 mA + RT care declanșează” (j13).
- Rețea MT 6 kV / 10 kV (j27, j28), cablu MT 12/20 kV nu mai e contradicție (j60), autocorectura „630… de fapt 800 kVA” (j22), uk declarat la j06/j59 (2500 kVA → **60,1 kA**), kVA→kW la CNC (j61), V60 Q JT < In trafo (j42), cablu impus subdimensionat blocat cu remediere (j63, j54), GE subdimensionat refuzat cu întrebare utilă (j31), contradicțiile TT/TN-S și mono/tri (j11, j12), IT medical refuzat cinstit (j34), IT industrial blocat cu întrebare (j35).

**Ce trage nota în jos**: aceleași familii P0 din r10 **nu sunt reparate** pe formulări noi (uk/Ucc, vitali/nevitali, GE izolat, contor/BMPT ca plecări, „6 stații EV” → 1 plecare), plus topologii inexistente în motor „turtite” într-o schemă GE+ATS (j05, j57) sau PT (j33). Parserul cade la cascade („->”, „TD1 alimentează TD1.1”), liste numerotate, Excel cu „;” și coloană de faze, „TGJT cu 6 plecări NH: 3 x 250 A…”.

## P0 (planșă falsă care arată „bună” sau periculoasă)

| id | text (scurt) | obținut | de ce e P0 |
|---|---|---|---|
| j05 | PT anvelopă beton **2 × 800 kVA uscat**, cuplă JT + AAR, 2L+M+2T | schemă **GE 800 kVA + ATS** (rețea din „TGD existent”), un singur „Consumatori” 1125 A; PT-ul și celulele MT în „neconsumat” | „AAR” citit ca ATS cu grup electrogen; echipament inexistent pe planșă, nevalidat (doar avertismente V45/V32) |
| j57 | Hospital: **2 × 2000 kVA** trafo, bus coupler NO, **genset 1000 kVA** ATS doar pe bara esențială | GE+ATS cu **GE 2000 kVA** (puterea trafo-ului), rețea „PT propriu”, ATS 3200 A, 5×(N2XY 4×1×300) | puterea GE greșită ×2, trafo-urile și cupla dispar; nicio întrebare despre topologie |
| j33 | **UPS 200 kVA** 1+1 paralel, ieșire TD-DC 10 × 32 A | **PT 20/0,4 kV 250 kVA** cu celule MT, măsură, TGJT „iesire pe TD-DC 1…10” | UPS-ul devine transformator („200 kVA nu e standard → 250 kVA”); sursă MT inventată |
| j46 | parcare **6 stații EV 22 kW**, RCD tip B, din TG existent, PT 400 kVA | **o singură** plecare „Parcare cu 6 statii EV” Ib = 35 A (22 kW), DDR tip B 40 A; + PT complet desenat | puterea subestimată de 6× fără marcaj; 5 circuite EV lipsă (repetă r10 i46) |
| j55 | depozit, TN-C-S Delgaz, **contor 3x63A**, plecări | **„Contor 1/2/3”** = 3 plecări NH 63 A; **Q1 MCCB 200 A** pe bara alimentată prin BMPT | sursa declarată devine consumator, Q general > protecția OD (repetă r10 i03) |
| j41 | PT 1000 kVA, **Ucc 4,5 %**, **Dyn11** | uk 6 % din tabel (Ik3 25,3 kA în loc de ≈ 33 kA), simbol **Dyn5** | valori declarate înlocuite tăcut cu unele mai puțin acoperitoare („Ucc” nu e sinonim pentru uk; repetă r10 i65) |
| j45 | concasor 160 kW DOL pe **GE 250 kVA izolat** | ATS cu ramură de rețea „PT propriu” inventată + întrebare „ce Sn are PT-ul?”; motorul comasat în „Consumatori”, pornirea DOL nevalidată | „izolat” nerecunoscut (doar „fără rețea” funcționează, j10); 160 kW DOL pe 250 kVA ar trebui semnalat |
| j30 | GE 400 kVA + ATS, **bara normală / bara vitală** explicite | „Consumatori normali” 352 A **pe ieșirea ATS** (deci și pe GE); „sarcina vitală = … + 150 + 40 + 30 = 323 kW” | contrazice textul; GE ar prelua HVAC 150 kW + pornirea Y-Δ 75 kW; planșa trece fără blocare (marcat doar în „Am presupus”) |
| j08 | GE 250 kVA ATS pe vitali (enumerați); **nevitalii rămân doar pe rețea** | refuz V86 „sarcina 752 A > In GE” + „măriți GE la ≥ 630 kVA sau declarați sarcinile prioritare?” | adună nevitalii — exact distincția pe care o declarase (repetă r10 i12/i67) |

## P1 — familii de cauze

1. **Cascade și surse în lanț nerecunoscute**: „TG -> TD-P1 (L=60 m): …; TD-P2 …” → 4 plecări amestecate, P declarată 5 kW, BLOCANT (j38); „TG alimentează TD1, TD1 alimentează TD1.1 și TD1.2” → V07 (j39); „din TD-statie, alimentare din PT 250 kVA” și „TE din TD-2 din TG din PT 400 kVA” → **refuz „contradicție: două surse”** (j44, j62); „2 plecări spre TD-Prod1 și TD-Prod2, 250 kW și ks 0,6” → V07 (j52).
2. **Liste / tabele**: listă numerotată „1. Iluminat hală - 12 kW; 2. Prize 3P 32A - 4 buc …” → refuz „valoarea 2 nu are unitate” (j53); CSV cu „;” și coloana Faze 1/3 → refuz „mono și trifazat” (j58); „TGJT cu 6 plecări NH: 3 x 250 A, 2 x 160 A, 1 x 400 A” → V07 (j40, deși „plecari 4 x 250 A” merge la j41); „4 circuite servere 16A și 2 circuite prize curate 16A” → refuz „4 cerute, 2 găsite” (j32); „10 circuite de iluminat de câte 1 kW” → **o plecare numită „Fa-mi o schema pentru un tablou cu 10 circuite de iluminat”** (j37); EN „3 lighting circuits, 4 socket circuits” pierdute (j20).
3. **Date explicite pierdute / folosite greșit** (marcate în „De lămurit”, deci corectabile în tabel, dar planșa e incompletă): pompele 2×22 kW ale stației de pompare lipsesc (j10 — stație de pompare fără pompe; antetul arată Pi 2 kW, Pc 3,9 kW); 6 rack-uri și bypass-urile UPS **nemarcate** (j15); motorul 45 kW cu cablu impus → V07 (j18); bateria 150 kvar declarată „plecare” în presupus, dar V07 „fără plecări” (j16); „2x300 kvar” → o baterie de 300 kvar (j06); laser 40 kVA (j61); pompă pilot 4 kW devine **P declarată a tabloului** (j64), reclama 0,5 kW devine P declarată (j03); cablu alimentare 2×NA2XY 3×240+120 pierdut și L = 90 m mutat pe plecări (j17); cablul 3x10 impus ignorat **fără marcaj** (j20, desenat 3×6); măsura MT cu TT/TC 20/5 (j26) și cupla MT (j28) nedesenate; „PT 20/0,4 kV 400 kVA” neconsumat → „Care e puterea trafo?” (j51); compresor + iluminat pierdute la „(rezerva)” (j49); prize 8 circuite la pensiune (j09).
4. **Coeficienți declarați ignorați**: „ks = 0,75” citit, dar bilanțul folosește 0,7 (j25, neconservator); „Pi = 420 kW, ku = 0,65” → Q1 dimensionat pe 420 kW (Ir 720 A în loc de ≈ 450 A), ACB cerut → MCCB (j24).
5. **Întrebări / refuzuri false**: autocorectura „compresor 55 kW, nu, 75 kW” → refuz „lipsește puterea trafo” (PT 1000 kVA era dat, j21); „ATS între T1 și T2, fără generator” → refuz „lipsește puterea GE” (j29); „cupla JT normal deschisă” declarată → întrebare deschisă/închisă + presupus „în paralel” (j28); GE+ATS în TT → V28 blocant (j56, cabinet stomatologic — caz frecvent).
6. **Rețeaua presupusă fără întrebare** când nu e declarată nimic: j36, j37 generează direct (TN-C-S + „SURSĂ NEDECLARATĂ — PRESUPUS BMPT” pe planșă), fără nicio întrebare în „De lămurit”; la PT-uri „TN-S implicit” peste tot (j06, j17, j22, …). Marcat, dar cerința era „rețeaua NU se presupune”.
7. **TN-C-S cu separarea PEN în TG declarată** (j01): sursa „TN-C-S”, dar planșa nu are punte/bornă PEN→PE+N, iar nota 3 spune „TN-S din PT propriu” (repetă r10 i37).
8. MT: cablul de racord MT „3x(1x150) NA2XS(F)2Y 12/20 kV, 450 m” citit ca **cablu JT impus 3F+N**, iar 450 m aplicat plecărilor JT (j60).

## P2 (selecție)
- Motoare nerecunoscute ca motoare (fără contactor/RT, doar NH sau MCB 4P): exhaustor 11 kW, circular, rindea (j01), pod rulant, sudură (j04), compresoare frig 4×45 kW (j19), desfumare pe bara vitală (j30), tanc lapte (j07).
- Cabluri nerealiste: muls 7,5 kW / compresor 5,5 kW pe CYABY 5×10 / 5×16 la 50 m (j07, j25); ACYABY 4×95 la 37 A (j09), 4×120 la 24 A (j66, j10); prize monofazate în tablouri de forță desenate trifazat cu NH 3P + RCCB 4P + CYABY 5×6 (j07, j55, j61).
- Y-Δ desenat cu un singur cablu 5×… (j13, j30); protecția pompei de incendiu Ir ≈ Ib (j13: MCCB 100 A pentru 97,6 A; j64: 160/158,7 A) — la pompe de incendiu protecția se supradimensionează.
- „Înainte de întreruptorul general” (j14) devine „tablou existent (TGD)”, fără reprezentarea racordului înaintea Q general.
- Schemele GE/ATS comasează mereu plecările în „Consumatori” (j09, j45, j66) — acceptabil ca „TAR”, dar pierde lista cerută.
- Autocorectura de rețea „TT … Nu, scuze, e TN-C-S” → întrebare de contradicție în loc să ia ultima valoare (j23, sigur dar inutil).
- V42 „selectivitate parțială” pe fiecare plecare (zgomot); antetul TG cu Pc diferit de presupus (j04: 61,2 vs 68,6 kW); presupus „trafo 20/0,4 kV” la j27 deși planșa e corect 6/0,4 kV; „ATS 4 poli” în presupus la GE izolat fără ATS (j10).
- j47 (PV 200 kWp pe bara TG) → refuz „câte invertoare?” — întrebare legitimă, dar ar putea desena PV ca sursă pe bară.

## Tabelul de confirmare — cât de ușor corectează utilizatorul
- **Bine**: tot ce nu e consumat apare în „De lămurit” cu textul exact (j03, j10, j17, j26, j38…), deci pierderile marcate sunt vizibile; presupunerile de rețea/sursă sunt toate în „Am presupus”.
- **Rău**: (a) topologia nu se poate corecta din tabel — dacă motorul alege GE+ATS în loc de PT cu 2 trafo (j05, j57) sau PT în loc de UPS (j33), câmpurile sunt greșite din rădăcină; (b) pierderile **nemarcate** (j15 rack-uri, j20 cablu 3x10, j46 cele 5 stații EV, j41 uk/Dyn11, j25 ks) nu apar nicăieri; (c) la cascade (j38) „De lămurit” are 7 fragmente rupte („TN-S) -> TD-P1 (L=60 m)”) — utilizatorul trebuie să reconstruiască tot tabelul.

## Planșe judecate (17) ca la avizare

| planșă | verdict | observații |
|---|---|---|
| j01 TG tâmplărie PT 400 kVA | admis cu obs. | lizibil; separarea PEN în TG lipsește (nota 3 „TN-S” contrazice sursa TN-C-S); motoare pe MCB 4P fără contactor/RT |
| j03 TG magazin TT Oradea | admis cu obs. | BMPT 80 A sursă, Q1 80 A Ir 56 A; prize (casa de marcat + 3 circuite) lipsă; reclama lipsă; vitrine NH 4 A + DDR 4P 100 mA |
| j04 Excel hală | admis cu obs. | L-urile din tabel corecte pe fiecare plecare, prize 1P cu DDR 30 mA; pod rulant/sudură fără aparataj de motor; Pc antet ≠ presupus |
| j05 PT 2×800 kVA | **respins** | GE 800 kVA + ATS inventat; niciun trafo, nicio celulă MT |
| j06 PT 2×1600 paralel | admis cu obs. | 2 celule Q cu 50/51, cuplă QC închisă, Ik3 75,2 kA, ACB Icu 85 kA — corect; o singură baterie 300 kvar din 2×300 |
| j09 GE 40 kVA + I-0-II | admis cu obs. | comutator manual corect; rețea „presupus BMPT”; consumatorii comasați, prize camere lipsă; C3 4×95 Al la 37 A |
| j10 stație pompare GE izolat | **respins** | sursă unică corectă, dar pompele 2×22 kW lipsesc; antet Pi 2 kW / Pc 3,9 kW |
| j13 tablou sprinklere | admis cu obs. | fără DDR, RT semnalizare, E90, Y-Δ; sursă „nedeclarată – presupus BMPT”; un singur cablu la Y-Δ; MCCB 100 A pe Ib 97,6 A |
| j14 tablou desfumare | admis cu obs. | E90, RT semnalizare, fără DDR; Q1 MCB C63 (selectivitate/pornire); racordul „înainte de Q general” nereprezentat |
| j19 cold storage 1250 kVA uscat | admis cu obs. | Ik3 31,4 kA, ACB 2000 A, 250 kvar, 4 compresoare; compresoarele pe NH fără aparataj de motor |
| j30 GE 400 + bare normal/vital | **respins** | nevitalii pe ieșirea ATS; restul plecărilor de siguranță corect (RCM, NHXH, RT semnalizare) |
| j33 UPS 200 kVA 1+1 | **respins** | PT 250 kVA cu celule MT inventat |
| j41 PT 1000 kVA Ucc 4,5 % | **respins** | uk 6 % și Dyn5 în loc de 4,5 % / Dyn11; Ik3 subestimat ~25 % |
| j46 6 stații EV | **respins** | o plecare 22 kW în loc de 6; PT complet desenat deși „din TG existent” |
| j55 depozit contor 3x63A | **respins** | „Contor 1–3” ca plecări NH 63 A, Q1 200 A |
| j57 spital 2×2000 kVA + GE 1000 | **respins** | GE 2000 kVA, trafo și cuplă lipsă |
| j63 cablu 5×16 impus din PT 630 | corect (blocat) | V02/V03/V35/V36 blocante cu remediere propusă — exact ce trebuia |

## Comparativ cu r10
- Procentul de corecte e practic neschimbat (33 % vs 35 %), P0 9 vs 11. Reparațiile r10 țin pe formulări noi acolo unde regula a fost generalizată (paralel 2 trafo, „fără rețea”, PTA, sprinklere/desfumare, 6/10 kV, 12/20 kV, kVA). Nu țin acolo unde s-a reparat formularea exactă: „uk” da, **„Ucc” nu**; „fără rețea” da, **„izolat” nu**; „BMPT 63A” da, **„contor 3x63A” nu**; „vitali/nevitali” tot greșit (j08 refuz, j30 amestecat).
- Problemă structurală: lipsesc modelele PT cu 2 trafo + cuplă **normal deschisă + AAR**, ATS între trafo, UPS, GE pe bara esențială a unui TG cu 2 bare; textul care le descrie e forțat în „ge_ats” sau „pt” cu 1 trafo, în loc să fie refuzat cinstit („topologie neacoperită”).
