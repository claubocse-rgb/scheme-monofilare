# Runda 7 — locuințe, branșamente, prosumatori casnici (testare ca proiectant ANRE gr. II/III)

**Notă: 5,5 / 10** (r6: 6,5). 68 de fraze noi (`locuinte/fraze.json`), rulate cu `interpreteaza_local` → `constructor.genereaza` → `validare` → PNG (`locuinte/fNN.png`, 42 planșe). Rezultatele brute: `locuinte/rezultate.json`; scriptul: `locuinte/run7.py`.
Setul din r7 e mai agresiv decât r6 pe prosumatori și tablouri secundare — o parte din scădere vine de acolo, dar 2 P0 noi sunt regresii reale de siguranță.

## Statistici

| verdict | nr. | | severitate | nr. |
|---|---|---|---|---|
| corect | 27 (40 %) | | P0 | 2 |
| parțial | 25 (37 %) | | P1 | 20 |
| greșit | 16 (23 %) | | P2 | 28 (inclusiv observații pe cazuri corecte) |

Pe categorii: locuință simplă (casă/apartament cu rețea + putere) ≈ 85 % corect; contradicții explicite mono/tri și TN/TT 100 % întrebate; rețea lipsă → întrebare în toate cazurile de locuință (regula „rețeaua nu se presupune” respectată, cu excepția #64); prosumatori cu „casa X kW” / „pa X kW” în aceeași frază ≈ 20 %; tablouri secundare (garaj, atelier, etaj, corp 2, mansardă) 0 / 6.

## P0

1. **#16 — puterea unui receptor devine puterea aprobată.** „casa cu piscina: pompa filtrare 1.1kw, …, trifazat 16kw, TT” → `P_aprobata_kW = 1,1`; planșa: BMPTd-16, QB 4P C16, RCCB 16 A, cartuș TE „Pa = 1,1 kW (ATR)”. „trifazat 16kw” apare la „Nu am folosit”, dar valoarea greșită e pusă pe planșă fără nicio mențiune. Pompa de piscină și iluminatul 12 V (SELV, trafo) lipsesc.
2. **#19 — wallbox 22 kW pe branșament monofazat 7 kW** se generează fără blocare: circuit 1P+N **C100**, CYY-F **3×35**, DDR 2P 100 A, în aval de BMPM-32. Doar avertismente V40/V46. Trebuia întrebare („22 kW e trifazat — treceți pe tri sau VE 7,4 kW?”), ca la #11 / #32.

## P1 (grupate)

- **Plasa de siguranță mai scapă date** (șterse tăcut, fără „Nu am înțeles”): #8 „TE la etaj”, #41 „PEN comun” (contradicție cu TT), #50 „mașina vase, mașina rufe, frigider separat”, #59 „backup pe frigider și centrală” (EPS), #6 „iluminat ext”, #57 „al doilea corp cu TD”.
- **Prosumator + putere casă/ATR**: „casa tri 15kw”, „bransament 16 kw”, „pa 9/15/40 kw” sunt luate drept posibilă putere a invertorului → întrebare „1×N kW sau total M kW?” care blochează generarea (#25, 27, 28, 31, 34, 35, 40; „pa 35 kw” neconsumat la #38). Fiecare e P2 luat separat, dar ca tipar blochează aproape toți prosumatorii scriși natural.
- **„pv N kw” nu e recunoscut** ca putere de invertor: #26, 36, 60, 66 (tot textul ajunge la „neconsumat”). La #66 nici rețeaua necunoscută nu e întrebată.
- **Virgula zecimală într-o enumerare**: „13,5kw si 13,5kw” (#39) produce o întrebare absurdă.
- **Tablou secundar / din TG**: #21, #22, #62 se termină în V07 „tabloul fără nicio plecare”, iar la #22 și #62 fără nicio întrebare (ecran blocat, utilizatorul nu știe ce să adauge). La #21, compresorul de 2,2 kW devine puterea tabloului. La #64, „3x2.5” → rețea **tri** presupusă (un cablu cu 3 conductoare înseamnă monofazat).
- **Locuință + PV în aceeași frază** (#61): rezultă doar un prosumator generic; consumatorii (PC 9 kW) se pierd, iar mesajul „Nu am folosit” include și datele folosite (15 kW, TN-C-S).
- **TT desenat ca TN-C-S** la branșament monofazat (#52): nota 3 spune TT, desenul are BN „PEN → N+PE” și C2 L+N+PE.
- **Generator** (#54): GE de 5 kW tratat ca consumator; întreabă puterea GE, deși e dată.
- **Sarcină mare în casă** (#38 30 kW, #65 100 kW): #38 are măsură semidirectă TC 50/5 la 47,6 A (OD: directă ≤ 100 A), iar #65 are Iac 159 A pe „TG existent” al unei case, fără întrebare despre branșament/măsură.
- **#3** „doar faza si nul, fara pamant”: lipsa PE (TN-C vechi) nu e semnalată; „pamant” → metoda D1; întreabă mono/tri deși „fază și nul” = mono.

## Planșe judecate ca la avizare (15)

| planșă | ce e bine | observații |
|---|---|---|
| f01 apartament mono 6 kW | BMPM-32, PEN separat în BMPM, DDR pe grupe ≤ 5, plită C32/3×6, SPD T2 + rezervă C25, BPE/PPL | ok |
| f06 casă tri TT 20 kW | TT corect: C2 3L+N, BPE din PPL, RCCB 300 mA S, RA·IΔn în note | text ilizibil în coloana „Simbol” (poz. 17); iluminat ext lipsă |
| f10 branșament tri 30 kW | BMPTd-100, SF 100 A gG, DPST, ACYABY 4×25 + FY 10 | RCCB tip **AC**; MCB 6 kA la Ik 25 kA presupus (back-up neindicat) |
| f16 piscină TT | — | **P0**: Pa 1,1 kW, QB C16, RCCB 16 A |
| f19 VE 22 kW mono | — | **P0**: C100 / 3×35 pe BMPM-32 |
| f20 casă mono TT + VE 7,4 | RDC-DD 6 mA notat, TT corect | blocat (BMPM 40 A); QB C40 300 mA instantaneu = Q11 C40 → fără selectivitate, neavertizat aici (la #24 V43 apare) |
| f24 prosumator mono 5 kW | QI C32 2P, DDR 30 mA tip A, SPD c.c./c.a., PI integrată | „BMPT existent” la monofazat; nota 3 TN-S deși declarat TN-C-S; „Branșament existent” desenat ca plecare din bară |
| f30 prosumator 27,5 kW | **TD-PV cu PI U/f → BD pe QG** (regula OD > 27 kW respectată) | eticheta „SB” suprapusă pe bara c.c.; QI = QG = C50 (V41); DDR 30 mA pe 27,5 kW |
| f38 3×10 kW | PI externă, SPD T1+T2 | TC 50/5 + contor semidirect la 47,6 A — nejustificat; consumatorii casei lipsesc |
| f50 casă 20 circuite | 6 ilum + 8 prize separate, plită 3F | A1, text foarte mic, lista în xlsx; toate cele 6 circuite de iluminat pe L3 (dezechilibru); MSV, MSR, frigider lipsă |
| f52 branșament mono TT | Q RCBO 300 mA **S** | BN „PEN → N+PE” și C2 L+N+PE la TT — incoerent |
| f59 hibrid 15 kW + 15 kWh | port baterie c.c. corect (FB + BAT LiFePO₄) | fără ieșire backup/EPS și tablou rezervat |
| f61 casă + PV | — | prosumator generic, PC 9 kW și consumatorii casei lipsă |
| f65 prosumator 100 kW | PI externă, MCCB 200 A Ir 190, 4×95 + PE 50 | 159 A pe casă fără măsură semidirectă / branșament nou; V31 Ik1min < Ia |
| f67 casă P+M 18 kW | parter/etaj, încălzire 6 kW C32/3×6, boiler 3 kW C16 | încălzirea de 6 kW pe o singură fază (L1, sarcină continuă, V46); A1, text mic |

Observații transversale de desen (P2): nota „TN-S în aval de separarea PEN” apare la toți prosumatorii, indiferent de schema declarată; textul vertical al cablurilor și coloana „Simbol” din listă devin ilizibile la A1/A2 când sunt multe circuite; „SB” se suprapune pe bara c.c. la toate schemele PV; presupunerile mențin „BMPT” / „√3·400” când rețeaua e încă necunoscută (#3, 4, 33, 49).

## Ce merge bine (față de r6)

- Rețeaua lipsă nu mai e presupusă la locuință (#4, 5, 15, 33, 42, 49 → întrebare + V07 blocant).
- Contradicțiile explicite mono/tri și TN-C-S/TT sunt întrebate (#13, 14, 44). Cazurile mono 12 kW / 50 kW sunt redirecționate pe trifazat (#11, 32).
- Pragul de 27 kW e corect în ambele sensuri (#29 fără releu extern, #30/#65 cu PI U/f pe BD), inclusiv la 27,5 cu zecimală.
- 400 V / 230 V → tri/mono, kVA → kW, majuscule, „P+1”/„P+M”, „6 circuite iluminat”, „2 boilere”, VE > 7,4 kW → 3F, saună 3F, TT cu RA declarat.

## Tabel complet

| # | cat. | frază | așteptat | obținut | verdict | sev. |
|---|---|---|---|---|---|---|
| 1 | apartament | `apartament 2 camere la bloc, monofazat 6 kw, TN-C-S, plita inductie, cuptor, masina de spalat, boiler 2kw` | locuință mono 6 kW TN-C-S, circuite plită/cuptor/MSR/boiler; fără întrebări | mono 6 kW TN-C-S, plită C32/3×6, cuptor, MSR, boiler; Pc 8,8 > Pa 6 avertizat | **corect** | - |
| 2 | apartament | `ap 3 cam, 1f, pa 7kW, schema tns` | locuință mono 7 kW TN-C-S; generează (eventual circuite uzuale presupuse) | „1f, pa 7kW, tns” → mono 7 kW, TN-S tratat ca TN-C-S pe branșament (declarat) | **corect** | - |
| 3 | apartament | `apartament bloc vechi, am doar faza si nul, fara pamant, 5kw` | TN-C / fără PE → întrebare / avertisment (trebuie PE, TN-C-S sau TT); nu presupune rețea | „faza si nul, fara pamant” → întreabă mono/tri (deși „fază și nul” = mono); lipsa PE (TN-C) neadresată; „pamant” → metoda D1 la coloană; presupus listează BMPT | **parțial** | P1 |
| 4 | apartament | `garsoniera, 5 kw` | întrebare mono/tri (rețeaua nu se presupune) | întreabă rețeaua (corect); presupus menționează BMPT/√3 deși rețeaua e necunoscută | **corect** | P2 |
| 5 | apartament | `vreau schema pt apartamentul meu cu aer conditionat in 3 camere si plita` | întrebare rețea + putere; AC×3 + plită înțelese | întreabă rețeaua (corect), dar „AC în 3 camere” → 1 singur circuit AC | **parțial** | P2 |
| 6 | casa | `casa P+1, trifazat 20kw, tt, priza de pamant 4 ohmi, pompa caldura 12kw trifazica, boiler, plita, cuptor, 2 AC, iluminat ext` | locuință tri 20 kW TT, PC 12 kW 3P, DDR la intrare (TT), RA 4 Ω; toate circuitele | planșă TT bună (RCCB 300 mA S, PPL 4 Ω, PC 3F C20 5×2,5, plită 3F); „iluminat ext” pierdut tăcut, „P+1” nefolosit (un singur Iluminat) | **parțial** | P2 |
| 7 | casa | `casa parter bransament monofazic 9 kw tn-c-s cu centrala pe gaz, masina de spalat, uscator` | locuință mono 9 kW TN-C-S, centrală, MSR, uscător | mono 9 kW, centrală gaz 1 A, uscător; BMPM-40 la limită, avertizat | **corect** | - |
| 8 | casa | `casa cu doua tablouri: TG la parter si TE la etaj, trifazat 22kw tn-c-s` | locuință tri 22 kW, TG + tablou secundar etaj | „TG la parter și TE la etaj” ignorat tăcut: un singur tablou, nu apare TE etaj, nicio întrebare | **greșit** | P1 |
| 9 | marire | `casa veche, marire putere de la 5kw mono la 15 kw tri, tn-c-s` | locuință/branșament tri 15 kW TN-C-S (noua situație) | mărire 5 mono → 15 tri: existentul informativ, proiect tri 15 kW | **corect** | - |
| 10 | bransament | `bransament nou trifazat 30 kw pt casa, coloana 25m` | branșament tri 30 kW, coloană 25 m, BMPT | branșament tri 30 kW, BMPTd-100, ACYABY 4×25+FY10, DPST; RCCB tip AC (depășit) | **corect** | P2 |
| 11 | bransament | `bransament monofazat 12 kw` | mono 12 kW → ~52 A > 40 A BMPM: avertisment / recomandare trifazat | mono 12 kW → propune trifazat (întrebare pertinentă) | **corect** | - |
| 12 | marire | `marire putere 11->22kw, trifazic, coloana existenta al 35mmp 40m` | tri 22 kW, coloană Al 35 mm² 40 m existentă verificată | „marire putere 11->22kw ... coloana existenta al 35mmp” nerecunoscut; întreabă tipul și puterea deja date | **parțial** | P2 |
| 13 | contradictie | `casa 10kw trifazat, schema TN-C-S si TT` | contradicție TN-C-S vs TT → întrebare | TN-C-S și TT → întrebare | **corect** | - |
| 14 | contradictie | `casa 15kw monofazat trifazat` | contradicție mono/tri → întrebare | mono și tri → întrebare | **corect** | - |
| 15 | ambiguu | `casa 10 kw` | întrebare rețea (mono/tri) — nu presupune | rețea lipsă → întrebare, plan blocat (V07) | **corect** | - |
| 16 | piscina | `casa cu piscina: pompa filtrare 1.1kw, iluminat piscina 12V, trifazat 16kw, TT` | tri 16 kW TT; circuit pompă piscină cu DDR 30 mA; iluminat 12 V prin trafo SELV | „pompa filtrare 1.1kw” luat ca PUTERE APROBATĂ 1,1 kW; planșa: BMPTd-16, QB C16, RCCB 16 A, TE „Pa = 1,1 kW (ATR)”; „trifazat 16kw” neconsumat; pompă piscină / ilum. 12 V lipsă | **greșit** | P0 |
| 17 | sauna | `sauna 9 kw trifazica in casa, bransament 3f 20kw tn-c-s` | tri 20 kW, circuit saună 9 kW 3P (≈13 A → C16/C20, 5×2,5/4) | saună 9 kW 3F, RCBO 4P C16 30 mA, 5×2,5 | **corect** | - |
| 18 | VE | `statie incarcare masina electrica 11 kw la casa, tri 25 kw TN-C-S` | tri 25 kW, circuit VE 11 kW 3P, DDR tip A EV / B (6 mA cc) | VE 11 kW 3F C20 5×4, DDR 4P tip A + RDC-DD 6 mA în stație; presupus spune „tip B” — inconsecvent | **corect** | P2 |
| 19 | contradictie | `wallbox 22kw pe bransament mono 7kw` | contradicție: 22 kW VE pe mono 7 kW → întrebare/blocare | wallbox 22 kW pe mono 7 kW: circuit monofazat C100 / CYY-F 3×35 în aval de BMPM-32, fără blocare, fără întrebare (doar V40/V46) | **greșit** | P0 |
| 20 | VE | `VE 7.4 kw mono, casa monofazata 10kw tt` | mono 10 kW TT, circuit VE 7,4 kW 32 A (DDR A-EV) | mono 10 kW TT → blocat corect (Ib 45,8 A > BMPM 40 A), dar fără întrebare (la #11 întreabă); VE C40/3×10 | **parțial** | P2 |
| 21 | garaj | `garaj cu atelier separat la 30 m de casa, tablou secundar, compresor 2.2kw tri, aparat sudura, casa tri 20kw tns` | tri 20 kW, TG casă + TD garaj (30 m) cu compresor 3P + sudură | garaj/atelier: tip „tablou”, P = 2,2 kW (compresorul) ca putere a tabloului; casa ignorată; plan blocat V07 (plasa de siguranță întreabă de restul) | **greșit** | P1 |
| 22 | garaj | `atelier in curte cu TD alimentat din TG casa, cyaby 5x6 40m, 3f, 25 kw total, TT` | tri 25 kW TT, TD atelier prin CYABY 5×6 40 m | TD atelier din TG, CYABY 5×6 40 m: blocat V07 „fără plecări” și NICIO întrebare | **greșit** | P1 |
| 23 | limita | `casa mono 11kw: 2 boilere 2kw, 3 ac 3.5kw, pompa caldura 8kw mono, tn-c-s` | mono 11 kW; sarcina instalată mare → avertisment coef. simultaneitate / PC 8 kW mono | mono 11 kW → blocat (BMPM 40 A) fără întrebare; „ac 3.5kw” tratat ca putere electrică (C20/AC) | **parțial** | P2 |
| 24 | prosumator | `prosumator 5kw mono pe casa, bransament 7kw tn-c-s` | prosumator mono 5 kW, PA 7 kW | prosumator mono 5 kW; eticheta „BMPT existent” la monofazat; nota 3 „TN-S” deși declarat TN-C-S | **corect** | P2 |
| 25 | prosumator | `fotovoltaice 10kwp invertor 8kw trifazat, casa tri 15kw tn-c-s` | prosumator tri, invertor 8 kW (10 kWp), PA 15 kW | întreabă „1×8 kW sau total 15 kW?” — 15 kW e puterea casei; refuză generarea | **parțial** | P2 |
| 26 | prosumator | `pv 6 kw on grid monofazic tt` | prosumator mono 6 kW TT; PA lipsă → presupus/întrebare | „pv 6 kw on grid monofazic tt” complet neînțeles (tot textul neconsumat), întreabă nr. invertoare | **greșit** | P1 |
| 27 | baterie | `invertor hibrid 10 kw cu baterie 10 kwh, tri, casa 20kw tn-c-s` | prosumator tri hibrid, baterie pe c.c. (fără QB pe c.a.) | hibrid 10 kW + 10 kWh: întrebare inutilă „10 sau total 20 kW?” (20 = casa) | **parțial** | P2 |
| 28 | baterie | `baterie ac coupled 5 kw / 10kwh pe langa invertorul existent 8kw, tri, tn-c-s, pa 15 kw` | invertor PV 8 kW + invertor baterie 5 kW pe c.a. (două plecări) | AC-coupled: întrebare inutilă „8 sau 15 kW?” deși „pa 15 kw” e explicit | **parțial** | P2 |
| 29 | prag27 | `prosumator 27 kw trifazat, pa 30kw, tn-c-s` | 27 kW NU > 27 → fără tablou cu releu anti-insularizare (PI integrată) | 27 kW = prag → PI integrată, fără releu extern (corect); DDR 30 mA pe 27 kW (risc declanșări) | **corect** | P2 |
| 30 | prag27 | `prosumator 27.5 kw tri, pa 30 kw tn-c-s` | > 27 kW → tablou cu releu anti-insularizare (PI externă) | 27,5 kW → TD-PV cu PI U/f pe bobina BD a QG (corect OD); nota 3 TN-S vs TN-C-S; „SB” suprapus pe bară | **corect** | P2 |
| 31 | prag27 | `pv 30 kwp cu 2 invertoare de 15 kw, tri, pa 40 kw, tn-c-s` | 2×15 = 30 kW > 27 → releu PI extern + 2 invertoare | 2×15 kW, pa 40: întrebare inutilă „30 sau 40 kW?” — testul >27 kW nu ajunge la planșă | **parțial** | P2 |
| 32 | contradictie | `50kw fotovoltaic pe casa, monofazat` | mono 50 kW imposibil → întrebare/blocare | mono 50 kW → întrebare (tri sau ≤ 8 kW) | **corect** | - |
| 33 | ambiguu | `prosumator 3kw` | întrebare rețea mono/tri | rețea lipsă → întrebare; presupus calculat cu √3·400 | **corect** | P2 |
| 34 | prosumator | `Huawei sun2000 10ktl m1, 22 panouri 455w, bransament trifazat 16 kw, TN-C-S` | prosumator tri 10 kW (10 kWp), PA 16 kW | Huawei 10KTL-M1 + 22×455 W: întrebare inutilă „10 sau 16 kW?”; kWp nedemonstrat; tip CEF în loc de prosumator | **parțial** | P2 |
| 35 | prosumator | `panouri 8kwp, invertor 6kw mono, pa 9 kw, cu limitare injectie zero, tns` | prosumator mono 6 kW, smart meter / limitare export | limitare injecție zero înțeleasă, dar întrebare inutilă „6 sau 9 kW?” (9 = pa) | **parțial** | P2 |
| 36 | limita | `pv 12 kw pe bransament mono 7kw tn-c-s` | invertor 12 kW > PA 7 kW mono → avertisment/întrebare | „pv 12 kw pe bransament mono 7kw” neînțeles integral; conflictul 12 kW > 7 kW mono nedetectat | **greșit** | P1 |
| 37 | prosumator | `prosumator invertor 20 kva, trifazat, pa 25kw tns` | tri 20 kVA (≈20 kW) | 20 kVA → 20 kW declarat, C40 5×6, PI integrată | **corect** | - |
| 38 | prag27 | `3 invertoare a cate 10kw trifazate, total 30kw, tns, pa 35 kw` | 3×10 = 30 kW > 27 → releu PI | 3×10 = 30 kW: PI externă desenată (bine), dar „pa 35 kw” neconsumat; măsură semidirectă TC 50/5 la 47,6 A (OD: directă ≤ 100 A); schemă CEF fără consumatorii casei | **parțial** | P1 |
| 39 | prag27 | `doua invertoare 13,5kw si 13,5kw tri tn-c-s pa 30kw` | 27 kW exact → fără releu extern (zecimale cu virgulă) | „13,5kw si 13,5kw” — virgula zecimală + „si” rupe parsarea: întrebare absurdă „2×13,5 sau total 13,5?”, neconsumat „5kw tri tn-c-s pa 30kw” | **greșit** | P1 |
| 40 | prag27 | `invertor 25kw + baterie ac 10kw, tri, pa 40kw, tns` | 25 + 10 = 35 kW surse → >27 (releu PI) sau întrebare | invertor 25 + baterie AC 10: întrebare inutilă „25 sau 40?”; regula >27 (Σ surse 35 kW) netestată | **parțial** | P2 |
| 41 | contradictie | `casa tri 12kw, schema tt dar cu PEN comun` | contradicție TT vs PEN → întrebare | „TT dar cu PEN comun” — contradicție ignorată, „PEN comun” șters tăcut, planșă TT | **greșit** | P1 |
| 42 | ambiguu | `casa 10kw, 3 faze sau una nu stiu` | întrebare mono/tri | „3 faze sau una nu stiu” → întrebare | **corect** | - |
| 43 | ambiguu | `fa-mi o schema` | întrebare ce schemă | „fa-mi o schema” → întrebare tip | **corect** | - |
| 44 | contradictie | `casa 15 kw tri, de fapt nu, e monofazat, tns` | corecție → mono (sau întrebare) | corecție „de fapt e monofazat” → întrebare de confirmare (acceptabil) | **corect** | - |
| 45 | ambiguu | `boiler 2000w` | întrebare (circuit izolat, lipsă tablou/rețea) | „boiler 2000w” → întrebare tip | **corect** | - |
| 46 | retea | `casa 400V 10kw tn-c-s` | 400 V → trifazat (sau întrebare) | 400 V → trifazat, 10 kW, QB C16 | **corect** | - |
| 47 | retea | `casa 230v 9kw tn-c-s` | 230 V → monofazat | 230 V → monofazat 9 kW | **corect** | - |
| 48 | retea | `casa cu 3x25A, tn-c-s` | 3×25 A → tri, ~17 kW | „3x25A” folosit (tri, Q 25 A) dar raportat și ca „Nu am folosit”; Pa presupus din bilanț 5,4 kW în loc de ~17 kW din Q | **parțial** | P2 |
| 49 | retea | `1x40A, tns, casa` | 1×40 A → mono, ~9,2 kW | „1x40A” înțeles ca Q 40 A, dar întreabă mono/tri (1× = monofazat) | **parțial** | P2 |
| 50 | casa | `casa tri 15 kw tn-c-s, plita 7,2 kw, cuptor 3.5kw, ac 2.6kw in dormitor, 6 circuite iluminat, 8 circuite prize, masina vase, masina rufe, uscator, frigider separat` | tri 15 kW; toate circuitele (6 ilum + 8 prize etc.) | 20 circuite corecte (6 ilum, 8 prize, plită 3F 7,2 kW…), dar mașina vase, mașina rufe, frigider separat ȘTERSE tăcut; A1, text ilizibil, lista scoasă în xlsx | **parțial** | P1 |
| 51 | ambiguu | `casa pe sistem TN, bransament subteran 3f 12kw` | TN ambiguu (TN-C/TN-S/TN-C-S) → întrebare sau TN-C-S presupus declarat | „sistem TN” → TN-C-S implicit fără mențiunea ambiguității | **parțial** | P2 |
| 52 | bransament | `bransament aerian monofazat 5kw cu firida pe stalp, tt` | branșament mono 5 kW, aerian, BMPM pe stâlp, TT | branșament mono TT: nota spune TT, dar desenul are BN „PEN → N+PE” în BMPM și C2 L+N+PE; presupus „TN-C-S, separare PEN” | **greșit** | P1 |
| 53 | retea | `casa trifazata 15 kw TT, priza de pamant nu am inca` | tri 15 kW TT, RA necunoscut → presupus/avertisment priză nouă | TT fără priză: RA 4 Ω presupus cu avertisment V34 (ok); ar trebui notă „priză nouă de executat” | **corect** | P2 |
| 54 | limita | `casa 11kw tri tn-c-s + generator 5kw cu comutator manual` | locuință + GE cu inversor manual sau întrebare | generatorul 5 kW tratat ca CONSUMATOR (P_sarcină 16 kW) și întreabă puterea GE deja dată | **greșit** | P1 |
| 55 | limita | `pompa caldura aer apa 16kw trifazica + rezistenta 9 kw, tri 20kw tt` | tri 20 kW TT, PC 16 kW + rez. 9 kW → avertisment sarcină | PC 16 kW + rezistență 9 kW, tri 20 kW TT → „Ce tip de schemă? Care e puterea?” (puterea e dată) | **parțial** | P2 |
| 56 | casa | `Ac 12000 btu x3, mono 7kw tn-c-s` | mono 7 kW, 3 circuite AC (~3,5 kW termic, ~1,1 kW el.) | „Ac 12000 btu x3, mono 7kw” → întrebare generică de tip | **parțial** | P2 |
| 57 | contradictie | `casa 2 corpuri, al doilea cu TD legat cu cablu 4x10 al 60 m, monofazat 9kw tns` | mono cu 4×10? → întrebare sau avertisment (4 conductoare = tri) | corpul 2 cu TD ignorat; cablul 4×10 Al 60 m pus pe coloana BMPM (blocat: Al 10 mm²); 4 conductoare pe monofazat necontestat | **greșit** | P1 |
| 58 | piscina | `jacuzzi 5kw si piscina incalzita cu pompa de caldura 7 kw, tri 22kw tns` | tri 22 kW, jacuzzi + PC piscină, DDR 30 mA | jacuzzi + PC piscină, tri 22 kW → întrebare generică de tip | **parțial** | P2 |
| 59 | baterie | `prosumator 15kw tri, baterie 15kwh pe dc, backup pe circuitele frigider si centrala, tns 20 kw` | hibrid c.c. + tablou backup (EPS) cu frigider + centrală | baterie c.c. desenată corect (FB + BAT), dar „backup pe frigider și centrală” (EPS/tablou rezervat) șters tăcut; întreabă cuplajul deși „pe dc” | **parțial** | P1 |
| 60 | ambiguu | `pv 9kw mono` | mono 9 kW; PA, schema pământ lipsă → întrebare/presupus | „pv 9kw mono” neînțeles | **greșit** | P1 |
| 61 | mixt | `casa noua bransament tri 15 kw tn-c-s pompa de caldura 9 kw, fotovoltaice 10 kw` | locuință + prosumator: PC 9 kW și invertor 10 kW pe aceeași schemă (sau întrebare) | casă + PC 9 kW + PV 10 kW → doar prosumator generic; consumatorii casei pierduți; mesaj „nu am folosit” include și datele folosite (15 kW, TN-C-S) | **greșit** | P1 |
| 62 | garaj | `TD garaj 3x16A din TG, tns` | tablou secundar 3×16 A; tri; întrebare ce circuite | „TD garaj 3x16A din TG” → blocat V07, nicio întrebare | **greșit** | P1 |
| 63 | apartament | `aparatament, 1 faza, 32A, tn-c-s, inductie 7kw` | mono 32 A (~7,4 kW), plită 7 kW (avertisment sarcină) | „aparatament” (typo) → întrebare generică incl. „puterea?” deși 32 A | **parțial** | P2 |
| 64 | garaj | `mansarda noua: 4 prize, 2 iluminat, AC, alimentata din TG existent cu 3x2.5 de 25 m` | tablou mansardă din TG; 3×2,5 → mono; rețea/sch. pământ de întrebat | mansardă: rețeaua dedusă TRI din „3x2.5” (cablu 3 conductoare = mono) — presupunere interzisă; întreabă plecările deși erau listate | **greșit** | P1 |
| 65 | prag27 | `prosumator 100 kw pe casa tri tns pa 100kw` | > 27 kW → releu PI; posibil întrebare (casnic 100 kW) | 100 kW pe casă: PI externă ok, dar Iac 159 A > 100 A (măsură directă) — fără întrebare despre branșament/măsură semidirectă | **parțial** | P1 |
| 66 | ambiguu | `pv 10kw, retea: nu stiu` | întrebare rețea | „pv 10kw, retea: nu stiu” → întreabă nr. invertoare, NU rețeaua; „pv 10kw” neînțeles | **parțial** | P1 |
| 67 | casa | `CASA P+M TRIFAZAT 18KW TNCS CU INCALZIRE IN PARDOSEALA ELECTRICA 6KW SI BOILER 3KW` | tri 18 kW, încălzire pardoseală 6 kW, boiler 3 kW (majuscule) | MAJUSCULE, P+M, încălzire pardoseală 6 kW C32/3×6, boiler 3 kW; A1 cu text mic | **corect** | - |
| 68 | ambiguu | `schema casa trifazic tn-c-s` | tri TN-C-S, putere lipsă → întrebare putere (sau presupus declarat) | Pa lipsă → presupusă din bilanț cu avertisment; putea întreba puterea | **corect** | P2 |