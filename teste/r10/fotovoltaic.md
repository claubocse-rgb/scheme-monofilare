# Runda 10 — fotovoltaic (CEF / prosumatori / BESS / PT)

**Tester:** inginer proiectant ANRE gr. II/III.

**Fluxul testat:** fără cheie API — `interpretor.interpreteaza_local`, apoi `constructor.genereaza`, `validare.valideaza`, `layout` și `render_svg`. PNG-urile sunt randate cu cairosvg la 2400 px.

**Frazele:** 68 de fraze complet noi. Nu am citit `tests/` și nici frazele vechi (doar raportul r9, pentru comparație). Stilurile folosite:
- extrase ATR / aviz (nr. + dată, „simultan evacuată / absorbită”, „putere aprobată la evacuare”, „cutie BMPT pe soclu”);
- tabele Tab (antet „Buc”, „Description / Qty”);
- CSV `;` cu antet „Pn kW”, CSV `,` cu antet „Item,Qty”;
- email de la beneficiar, mesaje scurte, engleză, typo-uri;
- autocorecturi („— greșit,”, „Scuze, sunt”, „(400 kW, nu 300)”);
- capcane: telefon, CUI, adresă „nr. 25”, „TG2”, accesorii în BOM (smart meter, dongle), invertor ne-hibrid cu baterie pe c.c., 800 V pe 0,4 kV, mono pe BMPT trifazat, procent de limitare.

**Fișiere în `teste/r10/fotovoltaic/`:**
- `fraze_r10.py`: frazele și ce se așteaptă;
- `ruleaza.py`: harness-ul (scrie `brut.json` și SVG-urile);
- `anexa.py`: verdictele (scrie `fraze.json`);
- `fraze.json`: frază, așteptat, intrare, presupuneri, întrebări, neconsumat, planșă, verificări, verdict, prioritate, observație;
- `r10_out.txt`: ieșirea brută;
- `fNN.svg/png`: 57 de planșe (16 judecate ca la avizare).

## Notă: 6/10 (r9: 7/10)

| | nr. | % |
|---|---|---|
| corect | 34 | 50 % (r9: 68 %) |
| parțial | 22 | 32 % |
| greșit | 12 | 18 % |
| P0 | 5 fraze / 4 clase | (r9: 2 / 2) |
| P1 | 20 | (r9: 11) |
| P2 | 24 (inclusiv observații la frazele corecte) | |

Frazele r10 sunt mai agresive decât în r9 (existente + noi, procente, forme ATR), deci o parte din scădere vine din acoperire. Totuși clasa #1 de mai jos e o **regresie confirmată**: fraza r9 #7 rulată acum pe motor dă rezultat greșit.

**Reparat față de r9 (verificat pe intrare sau pe planșă):**
- „Putere instalată 80 kW (2 x …)” este tratată ca sumă de control, fără invertor fantomă (r9 P0, #26, #27). Planșa f26 e corectă: EMS ≤ 50 kW și PI extern.
- Autocorectura „— greșit,” (#11) funcționează. „Pardon, de fapt” funcționează și ea (sondă).
- Hibridul Deye păstrează codul „SUN-50K-SG01HP3-EU”, iar „4 baterii … 5,12 kWh fiecare” dă 20,48 kWh (#18).
- La 800 V, QJT Ir 1125 A > QG 1000 A (f13) și QJT 900 > QG 800 (#21).
- La PT existent se desenează plecarea QPT din tabloul JT al PT (f15).
- Mono + tri cu faza declarată funcționează (#32: Primo pe L1, PI la 28 kW, întrebare legitimă 54 A > 50 A).
- Încă sunt bune:
  - BESS stand-alone (#17), PV + BESS c.a. cu injecție zero (f19);
  - 2 trafo cu măsură JT pe fiecare secție (f55), respectiv MT comună (f54);
  - V68 Voc la Tmin (#22), gPV desenat (f23);
  - contradicțiile Σ ≠ total (#10, #67) și 800 V vs 0,4 kV (#14, #44);
  - capcanele telefon / CUI / adresă / dată ATR (#28–#30);
  - pragul de 27 kW (#31 fără PI, #5 / #29 / #32 cu PI);
  - rețea nedeclarată → întrebare (#60).

## P0

1. **REGRESIE: repartizarea invertoarelor monofazate pe faze e greșită** (#41, #61, f41).
   - Fraza r9 #7 („3 x Fronius Primo 6.0-1, câte unul pe fiecare fază, … BMPT 3x32 A”) dădea L1/L2/L3 în r9. Acum dă **L1, L1, L2**.
   - Sonde:
     - „3 x SUN2000-6KTL-L1” → L1, L1, L2;
     - „… pe L1, L2, L3” → L1, L1, L1;
     - „4 x …” → L1 × 3 + L2;
     - „15 x 5KTL-L1, câte 5 pe fiecare fază” → 10 / 5 / 0.
   - Urmează întrebarea falsă „Iac pe L1 ≈ 57 A > BMPT 32 A: se mărește branșamentul (ATR nou)?”, plus V71 cu dezechilibru fals.
   - Planșa și lista de echipamente au două invertoare pe L1. Cauza reală (repartizarea făcută de aplicație) nu e semnalată nicăieri.
2. **Existent + nou: un grup de invertoare dispare tăcut** (#43, #9 și sonde, f43).
   - „Avem deja 20 kW (Symo 20.0-3-M) … Adaug 1 x SUN2000-30KTL-M3” → doar Symo 20 kW, nemarcat existent, titlu „CEF 20 kW”, fără întrebare.
   - „invertor existent Symo … + invertor nou SUN2000-30KTL-M3” → doar cel nou.
   - „Adăugăm 2 x Huawei 50KTL” → doar cele 2 × 20 existente.
   - Cazul e frecvent la extinderi de CEF.
3. **„N invertoare (marcă A P1 kW și marcă B P2 kW)” → N × P1 + 1 × P2** (#62, f62).
   - „2 invertoare (Huawei 100 kW și Sungrow 110 kW)” dă 2 × 100 + 1 × 110 = **310 kW** pe o planșă curată.
   - Antetul „N invertoare” nu e verificat față de lista din paranteză (r9 îl verifica pentru „N invertoare:”).
4. **Limitarea procentuală e ignorată tăcut** (#58).
   - „injecție limitată la 70 % din putere” → fără EMS / AR / TCA și fără întrebare.
   - „limitată la 70 kW” funcționează (sondă).

## P1

- **Existente nemarcate / interpretate greșit:**
  - #56 „invertoare existente 3 x 33 kW, nu se modifică” e desenat ca nou;
  - #9 „(40 kW existenți)” e luat ca Pn per invertor → refuz fals 20 vs 40.
- **Autocorecturi și paranteze:**
  - #12 „Scuze, sunt 3 x SG30CX, deci 90 kW” → planșa rămâne 2 × 30 = 60 kW, cu întrebare pe „deci 90 kW”;
  - #65 „(400 kW, nu 300)” → Pn 400 kW/buc → refuz fals.
- **Tabele:**
  - #3: CSV cu antet „Pn kW”; valoarea din ultima coloană („20”) e citită ca putere totală → I08 fals;
  - #47: CSV cu virgulă („Item,Qty”) nu e recunoscut deloc (I01).
- **Engleză, „existing LV switchboard / board”** (#20, #66, #67): nu e recunoscut, așa că se presupune BMPT.
  - La #66 asta înseamnă BMPT la 330 kVA.
  - La #20, TCA + EMS ajung în TGD-CF: măsoară producția, nu exportul la PCC (f20).
  - „existing main board” merge (#38).
- **Forme ATR neconsumate:**
  - „ATR permite doar 800 kW evacuare” (#63, fără EMS);
  - „cutie BMPT pe soclu 3x200 A” și „Ik3 la PCC = 8,5 kA” (#53);
  - „plecare … siguranțe MPR 250 A” (#64);
  - „plecare nouă din TDRI cu întreruptor 630 A” (#15: QPT desenat 800 A, egal cu QG).
- **PT existent cu 2 trafo:** Ik3 = 48,9 kA calculat cu T1 ∥ T2, deși textul spune „bara JT a T1” (#15, rămas din r9).
- **Rețea mixtă:** la „monofazat, racord BMPT trifazat 3x25 A” se alege `retea: mono` și BMPT-ul rămâne neconsumat (#42, rămas din r9).
- **Cabluri impuse:**
  - fără L, cablul impus e ignorat tăcut (#51: CYABY 5 × 35 pentru 160 A apare ca „C0 conform ATR”, fără V02; cu L = 40 m blochează corect);
  - la #50, cablul invertorului de 30 kW e auto-dimensionat la 4 × (ACYABY 4 × 240) (f50).
- **Invertor ne-hibrid cu baterie pe c.c.:** SG110CX e desenat „hibrid + baterie c.c.” (#57, f57). Catalogul ar trebui să ridice întrebare.
- **Model poluat:** „SG50CX. Racordarea se” apare pe planșă și în listă (#46). Pe aceeași planșă, notele 2–3 scriu „PT-ul propriu”, deși emailul spune că PT-ul e al Electrica.
- **Altele:**
  - „împărțite în 2 tablouri TGD-CF a câte 10” e ignorat tăcut (#34);
  - „2 baterii 5 kwh” → 5 kWh, fără întrebare (#4);
  - zero vs ATR 40 kW: conflictul e detectat, dar întrebarea e formulată greșit („2 × 33 sau total 40?”) (#39).

## P2

- **Întrebări inutile pe text neconsumat:**
  - „BMPT 1x40A”, „BMPT 1x32A”, „BMPT trifazat 32 A” (#7, #68, #8; planșa are deja BMPT existent);
  - „Ik MT …”, „Ik3 MT …” (#16, #40);
  - „Smart meter” (#2; în schimb la #66 dongle / senzor sunt ignorate corect);
  - „new … substation” + „confirmați PT” (#21, identic cu r9).
- **Întrebări duplicate** pentru BMPT (#1, #52, #26). La #26 / #1 se întreabă și când injecția e limitată de EMS sub capacitatea BMPT.
- **Protecții fără treaptă:**
  - QG Ir > BMPT (#27: 190 > 160; #49: 95 > 80; #26: 128 > 125), nesemnalat;
  - Q1 = QG = BMPT 63 A (#29); QI = QG (#23, #33);
  - QPT = QG 800 A (f15); QG = QJT 2500 A (f54).
- **V67 cu 1,1·ΣPn**, chiar când fișa dă Smax = Pn (#35: 953 kVA real < 1000 kVA, dar se cere trafo de 1250).
- **SPD c.c.:**
  - 1500 V la invertor de 1100 V (#22);
  - 1100 V în loc de 1000 V declarat (#23).
- **kWp necalculat** din rândul de module al tabelului (#2) și din stringuri (#22).
- **Titluri:**
  - „CEF 300 kW + BESS” pentru 200 PV + 100 BESS (#19);
  - „CEF 199 kW + BESS” (#56).
- **Eticheta „CÂMP PV 1 … 30 / 30 × identice”** pe prima coloană, contrazisă de coloanele „PV 2…15 / 16…30” (f54, f55, rămas din r9). Antetul TGD-CF e ilizibil la 2 secții.
- **Racord nedeclarat** (#36): se desenează BMPT cu avertisment, nu cu întrebare.
- **Typo-uri** („hauwei … racod tg exsitent”, #48): nu sunt recunoscute; se întreabă invertoarele.
- **Nota 1 „branșament ST 4-JT / ST 3-JT”** apare și pe planșele cu PT / MT (rămas din r6).

## Planșe judecate ca la avizare (16)

| f | caz | invertoare / protecții | c.c. | c.a. (SPD / PI / măsură) | BESS / PT / racord | verdict |
|---|---|---|---|---|---|---|
| 01 | ATR 180 kW, 2 × SG110CX-P2, BMPT 315 | ✔ Q 200 A, 4 × 240 Al | SPD 1100 ✔ | PI → BD, TC 400/5, TCA + AR + EMS ≤ 180 ✔ | PCC „RED 0,4 kV”, BMPT 315 nedesenat; QG 400 > BMPT | bun (P2) |
| 05 | prosumator 3 × 10 kW, TG | C20 + DDR 30 mA ✔ | ✔ | PI extern U/f pe QG ✔ | TG existent ✔ | bun, aș semna |
| 13 | 4 × 330KTL-H1, 20/0,8, MT | 300 kW, 3P 800 V ✔ | SPD 1500 ✔ | QM + contor MT ✔ | QJT 1125 > QG 1000 ✔ | bun, aș semna |
| 15 | PT existent 2 × 1000, plecare 630 | ✔ | ✔ | TC 750/5 ✔ | QPT desenat, dar 800 A (nu 630), = QG; Ik 48,9 kA ∥ | parțial |
| 19 | 2 × 100 + LUNA 215 c.a., zero, TG + PT 630 | ✔ | ✔ | TCA / AR / EMS la intrarea TG ✔ | BESS complet ✔ | bun (titlu) |
| 20 | 3 × SMA 50, export 100 kW | ✔ | ✔ | **TCA + EMS în TGD-CF**, nu la PCC | racord BMPT presupus (era TG) | parțial (P1) |
| 23 | Solis 60 kW, gPV 15 A | QI = QG 125 | gPV ✔, SPD 1100 (≠ 1000) | PI extern ✔ | BMPT 125 ✔ | bun (P2) |
| 26 | aviz 50 / 80 kW, BMPT 125 | 40 A ✔ | ✔ | PI extern + TCA + AR + EMS ≤ 50 ✔ | 2 casete „BMPT” redundante | bun (P2) |
| 41 | 3 × 6KTL-L1, câte unul pe fază | **L1, L1, L2** | ✔ | – | lista: 2 invertoare pe L1 | **P0** |
| 43 | 20 kW existent + 30 kW nou | **doar 20 kW** | ✔ | PI ✔ | „MCCB 100 A” în TG (era BMPT) | **P0** |
| 46 | email: 2 × SG50CX, TG, PT Electrica | **model „SG50CX. Racordarea se”** | 49,5 kWp ✔ | PI, TC 200/5 ✔ | nota „PT propriu” greșită | parțial (P1) |
| 50 | SG30CX, cablu 5 × 16 / 120 m | **cablu invertor 4 × (4 × 240)** | ✔ | ✔ | C0 5 × 16 ✔, NEVERIFICAT V20 ✔ | parțial (P1) |
| 54 | 30 × SG100CX, 2 × 1600, MT | grupare 1 + 14 + 15 ✔ | ✔ | PI pe QG1 / QG2 ✔ | QC NO, QM comun ✔, V67 legitim | bun (etichete) |
| 55 | 8 × SG110CX, 2 × 630, măsură JT | ✔ | ✔ | P1 / P2 pe secții ✔ | QC NO ✔, QJT 900 > QG 720 ✔ | bun, aș semna |
| 57 | baterie c.c. pe SG110CX | **„hibrid” fals** | ✔ | ✔ | Q1 = QG 200 | greșit (P1) |
| 62 | „2 invertoare (Huawei 100, Sungrow 110)” | **3 invertoare / 310 kW** | ✔ | ✔ | PT 400 ✔ | **P0** |

**Constant bine:**
- simbolistica (PI → BD, TC / TCA cu linii de măsură, EMS cu linii de comandă spre invertoare);
- PT nou cu celulele în ordinea corectă (QL – FV – QT / QM);
- secțiile cu cuplă NO;
- banner-ul NEVERIFICAT cu nota 0;
- lista de echipamente coerentă cu planșa.

## Recomandări (în ordine)

1. Repartizarea monofazatelor: refaceți distribuția round-robin L1 → L2 → L3, cu test de regresie pe fraza r9 #7. „Pe L1, L2, L3” și „câte N pe fiecare fază” se respectă explicit.
2. Existent + nou: „deja / existent(e)” și „adaug / se adaugă / nou” înseamnă două grupuri, cel existent cu `existent: true`. Dacă suma nu e consistentă, se pune întrebare. Un grup nu se pierde niciodată tăcut.
3. „N invertoare (A … P1 și B … P2)”: lista din paranteză are prioritate, iar N se verifică față de numărul de elemente.
4. Limitarea „X %” se convertește în kW (X % · ΣPn) sau se pune întrebare. Același lucru pentru „ATR permite doar X kW evacuare”.
5. Autocorecturi: adăugați „scuze, sunt / de fapt sunt” și „(X, nu Y)” în paranteză.
6. Tabele: CSV cu `,` și antet „Item,Qty”; coloana „Pn kW” nu e putere totală.
7. Engleză: „existing (LV) switchboard / board” înseamnă `tg_existent`. Plasa „neconsumat” trebuie aplicată și aici.
8. ATR: „cutie BMPT pe soclu 3xN A”, „Ik3 la PCC = X kA”, „Ik MT”, „plecare … siguranțe MPR / întreruptor N A” se preiau în model.
9. Cablul impus fără L se desenează cu L implicit și se verifică (V02). Cablul invertorului nu se mărește peste 2 × secțiunea maximă: se blochează cu mesaj.
10. Catalog: un invertor marcat ne-hibrid + „baterie pe c.c.” duce la întrebare. Modelul se taie la punct sau la cuvânt românesc.
11. P2: întrebările duplicate pentru BMPT se comasează și se omit când EMS limitează injecția sub In BMPT; QG ≤ In BMPT; V67 cu Smax din fișă.
