# Runda 9 — fotovoltaic (CEF / prosumatori / BESS / PT)

**Tester:** inginer proiectant ANRE gr. II/III.

**Fluxul testat:** fără cheie API — `interpretor.interpreteaza_local`, apoi `constructor.genereaza`, `validare.valideaza`, `layout` și `render_svg`. PNG-urile sunt randate cu cairosvg la 2400 px.

**Frazele:** 68 de fraze complet noi. Nu am citit `tests/` și nici frazele vechi. Stilurile folosite:
- tabel Excel cu Tab și antet „Cant/Buc”;
- CSV `;` cu antet „Qty”;
- extrase ATR / aviz;
- email de la beneficiar;
- mesaje scurte;
- engleză;
- autocorecturi („pardon, de fapt”, „… nu,”, „corectie: nu 3, ci 2”).

Capcanele urmărite:
- telefon, dată, „Hala 3 / TG3”;
- „limitate la 100 kW”, „Puterea instalata a CEF:”;
- mono + tri amestecat;
- 800 V + 400 V;
- 27 kW fix.

**Fișiere în `teste/r9/fotovoltaic/`:**
- `fraze_r9.py`: frazele și ce se așteaptă;
- `ruleaza.py`: harness-ul (scrie `brut.json` și SVG-urile);
- `anexa.py`: verdictele (scrie `fraze.json`);
- `fraze.json`: frază, așteptat, intrare, presupuneri, întrebări, neconsumat, planșă, verificări, verdict, prioritate, observație;
- `r9_out.txt`: ieșirea brută;
- `fNN.svg/png`: 57 de planșe.

## Notă: 7/10 (r8: 6/10)

| | nr. | % |
|---|---|---|
| corect | 46 | 68 % (r8: 46 %) |
| parțial | 16 | 24 % |
| greșit | 6 | 9 % |
| P0 | 2 fraze | 2 clase noi (r8: 5 fraze / 4 clase) |
| P1 | 11 | (r8: 20) |
| P2 | 21 (inclusiv observații la frazele corecte) | |

**Reparat față de r8 (verificat pe planșă sau pe intrare):** toate cele 5 P0 din r8 și majoritatea P1.
- **Tabele:** în Tab cu „Cant”, CSV cu „Qty”, „N buc” și „(3 buc)” multiplicitatea e corectă (#1, #2, #50, #51, #64; f01).
- **„P kW cu N invertoare”** înseamnă P total: se presupune N × P/N și se pune întrebare de confirmare (#3).
- **Antetul „N invertoare:”** e verificat: suma e consistentă (#4) sau se pune întrebare (#5). „Fiecare cu câte un” se propagă (#6).
- **Monofazat:** Primo -1, -L1, Sunny Boy sunt repartizate pe L1/L2/L3 cu 2P, inclusiv 9 invertoare grupate pe faze (f07, f54).
- **ATR:**
  - „puterea maximă aprobată pentru evacuare” înseamnă limitare cu EMS + AR la PCC;
  - „simultan absorbită” e tratată ca consum (f09);
  - „0 kW” înseamnă injecție zero (#10);
  - contradicția zero vs 30 kW e detectată (#11).
- **2 trafo:** 2 secții TGD-CF (QG1/QG2 + cuplă QC NO interblocată), măsura MT comună în amonte de QT1/QT2 (f15, f16, f43). Verificarea V67 se face pe fiecare secție (#52).
- **Huawei -H1/-H3:** Pn e luat din catalog (300 / 200 kW). La 800 V: 3P, SPD 800 V / 1500 V c.c. (f65).
- **BESS:**
  - LUNA2000-200KWH-2H1 recunoscut (f20, #50);
  - „4 x PCS 125 kW” și „8 x PCS 250 kW” desenate corect (f21, #44).
- **Engleză:** zero export, existing main LV board și main breaker 250 A (f18).
- **Diverse:**
  - BMPT 40 A < Iac 79 A dă întrebare (#23);
  - contradicția BMPT vs PT nou dă întrebare (#12);
  - autocorecturile „pardon, de fapt” (#13) și „corectie: nu 3, ci 2” (#62) sunt aplicate;
  - T2 726 kVA > 630 kVA dă întrebare (#42);
  - regula de 27 kW e respectată exact: 25 / 27 kW fără PI extern, 30 kW cu PI (#28–#30).
- **Selectivitate QJT ≥ QG** pe 400 V: corectă în f01, f21, f44, f49, f65.

**De ce nu 8:** rămân 2 P0 de interpretare, ambele cu planșă fără semnalarea cauzei reale. În plus, 11 P1, dintre care 4 sunt „presupune în tăcere ce trebuia întrebat” și 2 țin de PT existent / 800 V.

## P0

1. **Autocorectura „…, nu, …” e ignorată, iar ambele variante se cumulează** (#14).
   - Frază: „4 invertoare de 30 kW... nu, 5 invertoare de 30 kW, Sungrow SG30CX”.
   - Rezultat: [4 × 30] + [5 × 30] + [1 × SG30CX] = **10 invertoare / 300 kW**. Planșa e curată și nu se pune nicio întrebare.
   - Sondă cu total declarat: se ajunge doar întâmplător la refuzul I08 (Σ 240 vs 120).
   - Merg „pardon, de fapt” și „corectie: nu X, ci Y”, dar nu merg „nu,”, „… nu …” și probabil nici „greșit,” sau „adică”.
   - *Remediere:* un marcator de autocorectură („nu,”, „adică”, „greșit”, „scuze”) anulează grupul de invertoare dinainte cu aceeași formă. Cel puțin, două grupuri cu același Pn și fără model să ducă la întrebare.
2. **„Puterea instalată a CEF: 150 kW” creează un invertor fantomă de 150 kW** (#61, f61).
   - Frază: extras de aviz cu „Inv: 1 x SG125CX-P2 + 1 x SG25CX-P2”.
   - Rezultat: 150 + 125 + 25 = 300 kW pe planșă (INV-1 „150 kW” fără model).
   - Ambele întrebări („476 A > BMPT 250 A”) pornesc de la puterea dublată. Valoarea reală e 238 A < 250 A, deci instalația e conformă.
   - Beneficiarul ar cere un ATR nou degeaba.
   - Pe planșă, punctul de racord e „PCC — RED 0,4 kV”, fără BMPT 3 × 250 A.
   - *Remediere:* „putere instalată / Pi / P instalată :” înseamnă suma de control, ca la „CEF P kW”, nu grup de invertoare.

## P1

- **Autocorectură / multiplicitate la baterii:**
  - #22: „4 baterii Pylontech US5000 (4,8 kWh fiecare) pe un hibrid Deye SUN-12K-SG04LP3” dă 4,8 kWh și refuz „care e puterea invertorului?”.
  - Sondele arată două cauze:
    - forma „N baterii … (X fiecare)” nu se înmulțește (forma „4 x baterii … 4,8 kWh” dă 19,2);
    - „pe un hibrid Deye” nu se leagă.
  - Modelul Deye e rescris „SUN-12 kW-SG04LP3”: „12K” e înlocuit cu „12 kW” în codul modelului.
- **Email: marca înaintea lui „1 x” pierde primul invertor** (#35). „invertoare Sungrow 1 x SG125CX-P2 si 1 x SG25CX-P2” dă doar SG25CX-P2. Fără „Sungrow” merge.
  - „TG alimentat din PT-ul Electrica (630 kVA)” e citit ca racord în PT, nu ca TG existent.
  - Întrebarea rezultată („25 sau 150 kW?”) e greșită.
- **Rețea mixtă tri + mono** (#55): „1 x SUN2000-10KTL-M1 trifazat + 1 x 5KTL-L1 pe L1, BMPT 3x40 A” e trecută pe `retea: mono`. Urmează refuzul V53 cu propunerea „treceți pe trifazat” — instalația ERA trifazată.
- **„Limitate la 100 kW” per invertor e luat ca limitare de injecție TOTALĂ 100 kW** (#68, f68). Pe planșă: EMS „P inj ≤ 100 kW” la PCC, fără întrebare. „400 kWac” e ignorat.
  - Aceeași formă cu „fiecare” dă refuz I08 (400 vs 440). Nici acolo nu se înțelege limitarea de putere activă a invertorului.
- **„Metering at MV side” e ignorat fără mesaj** (#49): contorul rămâne pe JT. „MV metering” merge. Lipsește plasa „neconsumat” pentru frazele în engleză.
- **Racordul / PCS-ul se presupun fără întrebare** (#59 „CEF 80 kW 4 x 20 kW”, #60 „BESS 100 kWh”).
  - Se desenează racord BMPT (și PCS 50 kW = 0,5C), cu mențiune doar în „presupus”.
  - Racordul (BMPT / TG / PT) schimbă radical schema, deci trebuie întrebat, mai ales că „cef 50 kw” e întrebat corect (#36).
- **PT existent (propriu sau al OD): plecarea nouă din tabloul JT al PT nu e desenată** (#41, #42, f42).
  - C0 pleacă direct din caseta „PT EXISTENT”. Cablul nu are protecție la capătul sursă, iar pe planșă nu apare întreruptorul de plecare (sau siguranțele MPR).
  - La avizare se cere explicit.
  - La #42, Ik3 = 45,9 kA e calculat cu T1 ∥ T2, deși centrala e pe bara T2 cu cupla deschisă (P2).
- **Selectivitate inversată la 800 V:**
  - QJT Ir 1125 A < QG Ir 1250 A (#17, #52);
  - QJT e limitat la In trafo, iar QG nu e.
  - Planșele sunt blocate de V67, așa că acum problema e mascată, dar reapare imediat ce se mărește trafo-ul.
  - La 400 V e reparat. La #43 cele două valori sunt egale (1800 / 1800, P2).
- **Cablul impus „cablu invertor NYY-J 5x25” e atribuit lui C0** (#25). Planșa e blocată de BL V35/V36 pe Ik3 IMPLICIT 25 kA (din r8, rămas). Pe circuitul invertorului aceeași verificare e doar avertisment.
  - Un caz banal (30 kW, 5 × 25 Cu) iese „NEVERIFICAT”.

## P2

- **Întrebări inutile:**
  - „confirmați PT 1000 kVA” și „nu am folosit: nou 1000 kVA … post trafo” la un „new … substation” explicit (#19);
  - „BMPTi-250” la racord în TG existent (#47, rămasă din r8);
  - „TG3” (#40);
  - „cablu solar H1Z2Z2-K” (#63; corect că nu mai e C0, dar ar trebui recunoscut ca c.c.);
  - puterea cerută deși „10 kW” e dat (#37);
  - 600 vs 610 kW întrebat înaintea problemei reale 800/400 V (#31, două runde).
- **Forme nerecunoscute:** „Ik''= 22 kA” (#56; „Ik3 = 22 kA” merge). „Prosumator monofazat … 2 x SG10RT” nu e semnalat ca model trifazat (#57).
- **V25 blochează N redus** la cablul impus 2 × (3 × 240 + 120) Al (#26), din r8. Blocarea V02 de acolo e însă reală: 2 × 240 Al D1 nu duce 800 A.
- **Contorul P1 „furnizat și sigilat de OD” e desenat în TGD-CF** și la racord în TG existent / BMPT (f18, f20, f09). Contorul OD e la PCC. În TGD-CF e contor de producție al beneficiarului, iar textul trebuie schimbat.
- **TCA la PCC dimensionat după Iac PV** (100/5), nu după sosirea TG (QG TG 250 A) (f18, din r8).
- **Protecții identice în serie, fără treaptă:** Q1 = QG 200 A (f09, #48), QB = QG (f20). La 1 invertor, QG poate lipsi sau trebuie ales cu o treaptă mai sus.
- **DDR 30 mA tip A** la invertoare de 25–30 kW (#28, #29).
- **Titluri:** „CEF 700 kW + BESS” pentru 200 PV + 500 BESS (#21); „CEF 150 kW + BESS” (#46); „CEF 2200 kW + BESS” (#43).
- **kWp necalculat** din „1000 buc × 580 Wp” (#51), deși „220 module x 580 Wp” merge (#34).
- **Nota 1 „branșament conform ST 4-JT / ST 3-JT”** apare pe toate planșele cu PT / MT (din r6).
- **Lizibilitate:**
  - f16 (16 invertoare, 2 secții) și f43 (11 + 1 + 4 BESS) nu sunt grupate „idem” pe secție. Textul are ≈ 1,5 mm pe A1, iar 60 % din foaie e goală.
  - f15 grupează, dar eticheta „CÂMP PV 1 … 25 / 25 × identice” pe prima coloană contrazice coloanele „PV 2…13” și „PV 14…25”.
  - Antetul TGD-CF la 2 secții e ilizibil.

## Planșe judecate ca la avizare (15)

| f | caz | invertoare / protecții | c.c. | c.a. (SPD / PI / măsură) | BESS / PT | verdict |
|---|---|---|---|---|---|---|
| 01 | tabel 4 × 100, PT nou 630 | ✔ Q 200 A, cablu 4 × 185 Al | SPD 1100 V, 109 kWp/câmp ✔ | PI → BD, TC 750/5, contor JT ✔ | QJT Ir 900 > QG 640 ✔, QT SF 40 A ✔ | bun, aș semna |
| 07 | 3 × Primo mono L1/L2/L3 | 2P C40 + DDR 2P, CYY-F 3 × 6 ✔ | ✔ | fără PI (18 kW) ✔ | – | bun |
| 09 | ATR evac. 80 kW, BMPT | ✔ | ✔ | TCA + AR + EMS ≤ 80 kW la PCC ✔ | BMPT nedesenat, Q1 = QG | bun (P2) |
| 15 | 25 × 100, PT 2 × 1600, MT | grupat 1 + 12 + 12 ✔ | ✔ | PI pe QG1 / QG2 ✔ | 2 secții + QC NO, QM comun ✔ | bun (eticheta „1…25”) |
| 16 | 16 × SG250HX, 2 × 2500, 20/0,8 | 3P 250 A, 800 V ✔ | SPD 1500 V ✔ | ✔ | QJT 1800 > QG 1600 ✔ | bun, lizibilitate slabă |
| 18 | EN zero export, TG 250 A | C40 + CYABY 5 × 10 ✔ | ✔ | TCA + AR + EMS în TG ✔ | – | bun (TCA 100/5) |
| 20 | LUNA 200 kWh, TG | – | SB-B, SPD 1000 V ✔ | PI, TC 200/5 ✔ | BAT + PCS ✔ | bun (QB = QG) |
| 21 | 2 × 100 + 4 × PCS 125, PT 1000 | ✔ | ✔ | ✔ | 4 ramuri PCS, QJT 1440 > QG 1125 ✔ | bun (titlu) |
| 42 | PT existent 2 × 630, bara T2 | 6 × SG110CX ✔ | ✔ | TC 1250/5 ✔ | **fără plecare din PT**, Ik 45,9 kA (∥) | parțial |
| 43 | 12 × 100 + 4 PCS 250, 2 × 1250 MT | ✔ | ✔ | ✔ | 2 secții + QM ✔, QG = QJT 1800 | bun, ilizibil la print |
| 47 | 3 × 33 kW + PowerStack, inj. 0 | C63 ✔ | ✔ | PI ext + TCA 400/5 + AR + EMS ✔ | BESS c.a. ✔ | bun |
| 54 | 9 × 5 kW mono, 3 / fază | 2P C32, grupare pe fază ✔ | ✔ | PI (45 kW) ✔ | – | bun |
| 61 | aviz BMPT 250, 125 + 25 | **INV-1 150 kW fantomă** | ✔ | PCC fără BMPT, QG 500 A > BMPT 250 | – | **P0** |
| 65 | 4 × 215KTL-H3, 20/0,8, MT | 200 kW, 3P 800 V ✔ | SPD 1500 V ✔ | QM + contor MT ✔ | QJT 720 > QG 640 ✔ | bun, aș semna |
| 68 | 4 × SG110CX „limitate la 100” | ✔ | ✔ | **EMS ≤ 100 kW total** | PT 630 ✔ | greșit (P1) |

**Constant bine:**
- simbolistica (PI cu legătură roșie la BD, TC / TCA cu linii de măsură);
- PT nou separat, cu celulele MT în ordinea corectă;
- ramura BESS completă;
- lista de echipamente (mutată în .xlsx la A1);
- notele de ipoteze și „presupus”-ul transparent;
- banner-ul NEVERIFICAT.

## Recomandări (în ordine)

1. Marcatori de autocorectură („nu,”, „adică”, „greșit”, „scuze”): anulează grupul precedent de aceeași formă. Dacă există două grupuri cu același Pn fără model, se pune întrebare.
2. „Putere instalată / Pi : X kW” înseamnă sumă de control, nu invertor.
3. „<marcă> N x MODEL” = N × MODEL. „N baterii … (X kWh fiecare)” = N × X. „pe un hibrid <marcă> <model>” se leagă. Codul „12K” nu se rescrie în model.
4. Rețea mixtă: un invertor trifazat sau „BMPT 3x…” înseamnă `retea: tri`. Monofazatul trebuie repartizat pe faza declarată.
5. „limitat(e) la X kW” lângă invertoare înseamnă Pmax per invertor (setare), nu limitare de injecție. Dacă e ambiguu, se pune întrebare.
6. La racord nedeclarat (CEF / BESS fără TG / BMPT / PT) se pune întrebare, nu se presupune BMPT.
7. PT existent: se desenează plecarea nouă din tabloul JT al PT (Q + C0). Ik3 se calculează pe trafo-ul pe care se racordează centrala.
8. 800 V: QJT ≥ QG (sau QG limitat la In trafo). Plasa „neconsumat” trebuie aplicată și frazelor în engleză („metering at MV side”).
