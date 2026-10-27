# Runda 11 — fotovoltaic (CEF / prosumatori / BESS / PT)

**Tester:** inginer proiectant ANRE gr. II/III.

**Fluxul testat:** calea aplicației fără cheie API — `interpretor.interpreteaza(text)` (reguli locale + verificarea motorului), apoi `constructor.genereaza`, `validare.valideaza`, `layout` și `render_svg`. PNG-urile sunt randate cu cairosvg la 2400 px. Pentru fiecare frază am judecat și cât de ușor ar corecta utilizatorul în panoul de confirmare: P2 dacă greșeala e evidentă și marcată ca presupusă, P0/P1 dacă e greșită și nemarcată.

**Frazele:** 66 de fraze complet noi. Nu am citit `tests/` și nici frazele vechi; am citit doar rezumatul raportului r10, pentru comparație. Stilurile folosite:
- extrase ATR („simultan evacuată / absorbită”, „putere evacuată 0 kW”, „PT … proprietate OD”, „plecare nouă din TDRI cu întreruptor 250 A”, „siguranțe MPR”);
- oferte BOM numerotate, tabele Tab, CSV cu `;` și CSV cu `,` și ghilimele;
- emailuri (cu telefon, semnătură), mesaje scurte, engleză („export cap”, „customer substation”), typo-uri;
- autocorecturi („... scuze, 4 bucăți, nu 5”, „? nu, 400 kVA”, „de fapt nu, prin BMPT”, „pardon, existente sunt doar 2”);
- capcane:
  - invertoare mixte în paranteză;
  - „fiecare cu 3 x”;
  - Pn nominal ≠ codul modelului (SG350HX = 320 kW);
  - baterii „2 baterii MARCA 5,12 kWh”;
  - „fără panouri”;
  - BMPT 1x32A;
  - BMPT + PT în aceeași frază;
  - stație de încărcare.

**Fișiere în `teste/r11/fotovoltaic/`:**
- `fraze_r11.py`: frazele și ce se așteaptă;
- `ruleaza.py`: harness-ul;
- `anexa.py`: verdictele;
- `brut.json`, `r11_out.txt`: ieșirea brută;
- `fraze.json`: frază, așteptat, intrare, presupuneri, întrebări, neconsumat, planșă, verificări, verdict, prioritate, observație;
- `fNN.svg`: 52 de planșe;
- `fNN.png`: 22 de planșe randate, dintre care 15 judecate ca la avizare.

## Notă: 6/10 (r10: 6/10)

| | nr. | % |
|---|---|---|
| corect | 28 | 42 % (r10: 50 %) |
| parțial | 26 | 39 % |
| greșit | 12 | 18 % |
| P0 | 2 fraze / 2 clase | (r10: 5 / 4) |
| P1 | 24 | (r10: 20) |
| P2 | 23 (inclusiv observații la frazele corecte) | |

Pe scurt:
- **Ce e mai bine:** P0-urile scad de la 4 clase la 2. Toate cele 4 clase P0 din r10 sunt reparate pe forma lor, deși clasa „N invertoare (…)” revine sub o formă nouă.
- **Ce e mai rău:** procentul de fraze corecte scade, pentru că frazele r11 lovesc formulări noi:
  - BOM cu accesorii;
  - „fiecare cu”;
  - autocorecturi pe racord / existent;
  - CSV cu virgulă;
  - „fără panouri”.
- **Panoul de confirmare** ajută la jumătate din P1 (invertoare, baterie, limitare). Nu ajută acolo unde câmpul lipsește:
  - PT existent / nou la CEF;
  - cablurile impuse;
  - rețeaua presupusă nemarcată.

### Reparat față de r10 (verificat)

- **Repartizarea monofazatelor pe faze (P0 r10):**
  - #16 „repartizate L1-L2-L3” → L1 / L2 / L3;
  - #17 „câte 5 pe fază” → 5 / 5 / 5;
  - #49 tri + mono pe L2.
- **Limitarea procentuală (P0 r10):** #21 „60 % din puterea instalată” → 60 kW, cu EMS.
- **Existent + nou (P0 r10):**
  - #18: Tauro existent marcat;
  - #42 / f42: PV existent (E) + BESS nou;
  - #64: Primo existent pe L1;
  - #19 fără paranteză: SMA existent + CORE2 nou.
- **„N invertoare (A … și B …)” fără „k x” (P0 r10):** dă Σ corect (sondă).
- **Plecare din PT existent:**
  - #26 / f26: QPT 250 A din TDRI, măsură MT existentă;
  - #54: siguranțe MPR 315 A citite.
- **Invertor ne-hibrid + baterie c.c.:** #36 → V12 blocant, cu remediere clară.
- **„existing main LV board”** (#19, sondă) și autocorectura „250 kVA? nu, 400” (#47).
- **Încă sunt bune:**
  - capcanele CUI / adresă / nr. ATR / telefon (#4, #29, #30);
  - evacuată 0 kW = zero (#57);
  - Σ ≠ total (#8) și Pn ≠ cod (#61);
  - cablu impus subdimensionat → blocant (#23);
  - BESS stand-alone (#12) și BESS 2 × PCS (#38);
  - 2 trafo cu măsură JT pe fiecare secție (f63);
  - 3 tipuri de invertoare (f52);
  - TT (#11, #56);
  - pragul de 27 kW (#10, #17, #41).

## P0

1. **„N invertoare (k × A și m × B)” → N × A + m × B** (#20, f20).
   - „3 invertoare (2 x Huawei 100KTL și 1 x Sungrow SG110CX)” dă **410 kW** (3 × 100 + 110) pe o planșă curată, fără întrebare. Lista de echipamente trece „INV-1…INV-3 Huawei 100KTL — 3 buc”.
   - Sondă: „4 invertoare (3 x 50KTL + 1 x 30KTL)” → 4 × 50 + 30.
   - Forma r10 (fără „k x”) și forma cu „:” sunt reparate, deci repararea r10 a acoperit doar o variantă.
2. **„fiecare cu 3 x …” pe mai multe tablouri → jumătate din centrală dispare** (#44, f44).
   - „Două tablouri TGD-CF, … fiecare cu 3 x SUN2000-50KTL-M3” → 3 × 50 = **150 kW** („CEF 150 kW”).
   - Nu apare nimic la neconsumat și nu se pune nicio întrebare. Sonda „2 tablouri TGD-CF, fiecare cu 3 x” dă același rezultat.

## P1 (pe clase)

- **Rețeaua se presupune tăcut (regula de bază încălcată):**
  - #9: „prosumator 10 kW, BMPT existent, invertor de 10 kW” → trifazat, fără presupunere afișată;
  - #48 / f48: „BMPT 1x32A” (monofazat) → planșă **TRIFAZATĂ** (BMPT 3+N+PE, „Forță 3F”);
  - #33: SUN2000-10KTL-M1 declarat trifazat apare în intrare ca monofazat pe L1, iar „branșament monofazat 1x40 A” ajunge doar la întrebarea generică.
  - Panoul nu marchează câmpul Rețea în niciunul dintre aceste cazuri.
- **PT existent desenat ca nou** (#4, f04): „Avem PT propriu 400 kVA … măsura pe MT” → trafo, celule MT și anvelopă în listă (ofertă greșită).
  - Panoul CEF nu are opțiunea „PT existent”.
  - Tot aici, TCA / EMS pentru injecție zero e în TGD-CF: măsoară producția, nu schimbul la PT (clasa r10 #20).
- **Cabluri impuse puse pe circuitul greșit:**
  - #2: BOM „Cablu solar 6 mmp – 1500 m” → C0 6 mm² Al / 1500 m, blocant;
  - #43: „fiecare invertor cu CYY-F 5x16, 25 m” → aplicat pe C0, blocant, cu „aplic remedierea?” pe cablul greșit.
  - Cablurile nu apar în panou.
- **V67 cu 1,1·ΣPn acum BLOCHEAZĂ** (#6, #39): 9 × SG110CX pe 1000 kVA (990 kVA real) cere trafo 1250.
  - #6 are în plus QG Ir 1600 A > QJT Ir 1440 A (selectivitate inversă, doar avertisment).
- **Paranteză / total citite ca Pn per bucată, sau ca putere totală:**
  - #19: „3 x STP 25000TL-30 (75 kW)” → 75 kW/buc, refuz (clasa r10 #65 nereparată);
  - #45: „export cap 400 kW” → total, refuz;
  - #15: SG350HX „(320 kW, 800 V)” → I08 fals, fără varianta corectă în întrebare.
- **Autocorecturi pe racord / existent:**
  - #46: „TG existent... de fapt nu, prin BMPT nou” → tip „tablou”, invertorul dispare;
  - #66: „pardon, existente sunt doar 2” → cele 2 existente dispar.
  - Sondă la #66: „3 x … noi și 2 x … existente” → 5 invertoare, cele 2 **nemarcate** existente.
- **Contradicții nedetectate:**
  - #32: „racord în BMPT și în PT propriu 250 kVA” → PT, BMPT dispare tăcut. Tot aici, „3 x 50KTL Huawei” → 1 × 150 kW (marcat presupus);
  - #31: „ATR aprobă evacuare 100 kW” dispare tăcut lângă „injecție zero”.
- **Baterie și stocare:**
  - #11: „2 baterii BOS-G 5,12 kWh” → 5,12 kWh (f11), nemarcat;
  - #59: „doar baterie … fără panouri” → f59 desenează câmp PV.
- **Stringuri** (#24): „12 stringuri a câte 20 module” → 20 module în total, 9,1 kWp, titlu „CEF 9,1 kWp”. Întrebările semnalează problema.
- **CSV cu virgulă** (#62): n = 1, model cu `"`, „545W” → 545 kW total, refuz (clasa r10 #47 nereparată).
- **Planșă și listă:**
  - #16 / f16: model poluat „SUN2000-5KTL-L1 repartizate L1-L2-L3” pe planșă și în listă;
  - #17 / f17: 15 monofazate desenate una câte una, schema redusă la 36 % pe A1, ilizibilă (nu se grupează ca la CEF);
  - #1 / f01: nota 2 „PT-ul propriu existent” și nota 3 „TN-S din PT propriu”, deși ATR spune PT al OD.
- **Altele:**
  - #50: „2 PT x 2500 kVA” → refuz, cu întrebarea „împărțiți pe 2 × 2500?”;
  - #53: „Ik3 la bara 0,4 kV = 18 kA” neconsumat, iar „impedanța buclei 0,05 ohm” → RA_ohm (sens greșit).

## P2

- **Refuzuri sigure, dar care pierd date:**
  - #7: autocorectura pierde Tauro;
  - #37: SolaX „X3-ULTRA-30K”, puterea din cod necitită;
  - #5, #58: „cef 20 kw”, „CEF de 50 kW” nu sunt citite deloc;
  - #54: text încâlcit.
- **#18:** „CEF de 50 kW existentă” luată ca total → I08, dar cu varianta corectă oferită.
- **Avertisment contradictoriu:** „desenată prin BMPT (presupus)” apare când planșa are PT nou (#3) sau nicio planșă (#58).
- **#65:** „BMPT 3x630A” → PT nou adăugat (cu întrebare), iar anvelopa PT intră în listă.
- **Titluri:** „CEF 200 kW + BESS” pentru 100 PV + 100 BESS (#13, #42), „CEF 430 / 500 kW + BESS” (#3, #38). Problema rămâne din r10.
- **Protecții fără treaptă:** QG = QPT (#1, #26, #34), QB = QG (#12), QG = QI (#41), QG = BMPT (#21).
- **Calcule și dimensionare:**
  - kWp necalculat din BOM (#2) și din stringuri (#25);
  - V69 presupune stringuri în paralel pe un MPPT (#25);
  - QG ales din 1,1·Pn, nu din Iac,max din fișă: V02 blocant la un cablu impus care e de fapt suficient (#22).
- **Întrebări inutile sau duplicate:**
  - „Baterie 0 buc” → întrebare despre baterie (#28);
  - două întrebări pentru BMPT 315 (#28);
  - întrebarea despre stația de încărcare citează și partea consumată (#60).
- **Recurente din r6–r10:**
  - nota 1 „branșament ST 4-JT / ST 3-JT” pe planșele cu PT;
  - text mic pe A1;
  - lista de echipamente scoasă din planșă (f63, f17).

## Planșe judecate ca la avizare (15)

| f | caz | invertoare / protecții | c.c. | c.a. (PI / măsură / EMS) | PT / racord / BESS | verdict |
|---|---|---|---|---|---|---|
| 01 | ATR 240 kW, 3 × 100, PT OD 630 | ✔ Q 200 / 190, 4 × 185 Al | SPD 1100 ✔ | PI → BD, TC 500/5, TCA + AR + EMS ≤ 240 ✔ | QPT desenat ✔; QG = QPT 500; note „PT propriu” / TN-S greșite | parțial (P1 note) |
| 04 | PT propriu existent 400, MT, zero | ✔ | ✔ | EMS / TCA în TGD-CF, nu la PT ✘ | **PT desenat NOU**, anvelopă în listă ✘ | nu aș semna (P1) |
| 11 | Deye 15K hibrid, TT | C32 + DDR 40 / 30 mA ✔ | ✔ | TT: DDR pe toate plecările ✔ | **BAT 5,12 kWh** (corect 10,24) ✘ | parțial (P1) |
| 13 | 2 × 50 + BESS c.a. 100 / 215, ≤ 50, TG | ✔ | ✔ | TCA + AR + EMS la intrarea TG ✔ | BESS complet ✔ | bun (titlu P2), aș semna |
| 16 | 3 × 5KTL-L1 pe L1 / L2 / L3 | C32 2P + DDR ✔ | ✔ | — | faze ✔; **model poluat** pe planșă / listă | parțial (P1) |
| 17 | 15 × 6KTL-L1, 5 / 5 / 5, BMPT 160 | ✔ | ✔ | PI ✔ | **ilizibilă** (36 % pe A1) | nu se poate depune (P1) |
| 20 | 2 × 100 + 1 × 110, PT existent | **3 × 100 + 110 = 410 kW** ✘ | ✔ | ✔ | QPT 800 ✔ | greșit (P0) |
| 26 | PT existent 630, MT, plecare 250 A | ✔ | ✔ | PI ✔, fără contor JT (măsura e pe MT) ✔ | QPT 250 ✔ = QG 250 | bun, aș semna (P2) |
| 42 | 2 × 50 existente + BESS c.a., zero | existent (E) ✔ | ✔ | TCA la intrarea TG ✔ | BESS ✔ | bun, aș semna |
| 44 | 2 TGD-CF × 3 × 50 | **doar 3 × 50 = 150 kW** ✘ | ✔ | ✔ | un singur TGD-CF ✘ | greșit (P0) |
| 48 | mono 5 kW, BMPT 1x32A | ✔ 2P | ✔ | — | **instalație desenată trifazată** ✘ | greșit (P1) |
| 52 | 5 × SG110 + 3 × SG50 + 2 × SG33, PT 1000, MT | ✔ grupate „idem” | ✔ | PI ✔, QM + contor MT ✔ | QG 1250 < QJT 1440 ✔ | bun (text mic), aș semna |
| 59 | „doar baterie, fără panouri” | ✔ | **câmp PV desenat** ✘ | — | hibrid + BAT 30 ✔ | greșit (P1) |
| 63 | PT nou 2 × 630, JT pe fiecare trafo | 3 + 3 ✔ | ✔ | P1 / P2 pe fiecare secție, cuplă QC ✔ | ✔ | bun, aș semna (P2: lista în anexă) |
| 65 | 4 × 100, BMPT 630 declarat, ≤ 300 | ✔ | ✔ | EMS ≤ 300 ✔ | PT nou 630 adăugat (cu întrebare), BMPT abandonat | parțial (P2) |

Aș semna 6 din 15 (r10: 7 din 16). 4 planșe sunt greșite: două P0 (f20, f44) și două P1 nemarcate (f48, f59).

## Recomandări (în ordinea impactului)

1. **Invertoarele:**
   - antetul „N invertoare” se verifică față de Σ k din paranteză, indiferent de formă;
   - „fiecare cu / câte … pe fiecare (tablou / acoperiș)” trebuie să înmulțească, sau măcar să întrebe.
2. **Rețeaua:** „1xNN A” sau „monofazat” în text forțează mono, sau o întrebare. Fără declarație, se întreabă (sau se marchează în panou ca presupus), nu se trece la trifazat.
3. **Panoul de confirmare la CEF:**
   - comutator „PT existent / nou”;
   - câmp „Rețea” marcat când e dedus;
   - cablurile impuse (C0 / invertor) cu circuitul la care se aplică.
4. **V67:** folosește Smax din catalog (SG110CX 110 kVA, 115KTL 125 kVA) în loc de 1,1·Pn; ca avertisment, nu blocant, când diferența e ≤ 10 %.
5. **Rânduri de BOM:** accesoriile (cablu solar, logger, „Baterie 0”) se ignoră; numărul de module × Wp → kWp.
6. **Autocorecturi:** „de fapt nu, prin X”, „pardon, …” se aplică pe racord și pe statutul existent, nu doar pe numere.
7. **Paranteza „(75 kW)”** după „3 x model” = total, verificat cu codul; „export cap / export limit” = limitare.
8. **„fără panouri / fără PV”** → BESS fără câmp PV.
