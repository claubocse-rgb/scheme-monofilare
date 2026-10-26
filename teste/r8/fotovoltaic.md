# Runda 8 — fotovoltaic (CEF / prosumatori / BESS / PT)

**Tester:** inginer proiectant ANRE gr. II/III.

**Fluxul testat:** `/api/chat` fără LLM, adică `interpretor.interpreteaza_local`, apoi `constructor.genereaza`, `validare.valideaza`, `layout` și `render_svg`. PNG-urile sunt randate cu cairosvg la 2400 px.

**Frazele:** 68 de fraze complet noi. Nu am citit `tests/` și nici frazele vechi. Stilurile folosite:
- extrase din ATR / aviz tehnic de racordare copiate;
- ofertă cu tabel Excel (tab-uri);
- tabel CSV (`;`);
- emailuri de la beneficiar;
- mesaje scurte;
- engleză și ro/en.

Am încercat activ să păcălesc sistemul cu: număr de telefon, dată, dimensiuni de modul, „Hala 2 / TG2”, autocorectură, „2 x 50 kWp … fiecare cu câte un”, „N baterii x kWh”, mono pe 3 faze și mixuri de 800 V cu 400 V.

**Fișiere în `teste/r8/fotovoltaic/`:**
- `fraze_r8.py`: frazele și ce se așteaptă;
- `ruleaza.py`: harness-ul (scrie `brut.json` și SVG-urile);
- `anexa.py`: verdictele (scrie `fraze.json`);
- `fraze.json`: frază, așteptat, intrare fizică, presupuneri, întrebări, neconsumat, ce apare pe planșă, verificări, verdict, prioritate, observație;
- `r8_out.txt`: ieșirea brută;
- `fNN.svg/png`: 56 de planșe;
- `p1_*`, `p2_*`: sonde suplimentare.

## Notă: 6/10 (r7: 6/10)

| | nr. | % |
|---|---|---|
| corect | 31 | 46 % |
| parțial | 28 | 41 % |
| greșit | 9 | 13 % |
| P0 | 5 fraze | 4 clase distincte |
| P1 | 20 | |
| P2 | 12 (+ observații P2 la frazele corecte) | |

**Reparat față de r7 (verificat pe planșă):**
- **800 V.** Bara JT e la 3 × 800 V, cu trafo 20/0,8 kV, cabluri 3 + PE, aparate 3P la 800 V și SPD c.c. de 1500 V (f66, f67). Un invertor de 800 V racordat într-un TG de 0,4 kV primește I08 (#8).
- **Măsura pe MT** e desenată în celula QM, cu TT + TC și contor MT (f13, p1).
- **Injecția zero / limitarea:** TCA + AR sunt pe sosirea TG, adică la PCC, iar EMS comandă invertoarele (f14, f68, #64).
- **„N x” din cablu sau din baterie** nu mai e citit ca număr de invertoare (#19, #20, #21).
- **Modelul fără cuvânt-cheie** e recunoscut ca prosumator (#54).
- **Gruparea „idem”** se aplică peste 8 invertoare (f35, p1).
- **2 trafo:** sunt desenate T1 + T2 + cuplă, pentru PT nou 2 × 1250 kVA (p1).
- **Fără baterie-fantomă** la SUN2000-M1 (#4) și la „fara baterie” (#38).

**De ce nota nu urcă:** au apărut 4 clase noi de P0 de interpretare. Toate produc planșe curate, fără nicio întrebare, cu numărul de invertoare greșit. În plus, frazele în stil ATR sunt aproape sistematic refuzate pe baza unei „contradicții” care nu există.

## P0

1. **Tabele (Excel / CSV) — coloana de cantitate e ignorată.**
   - #61 (`SUN2000-100KTL-M2;6;100`) dă **1 invertor**, iar cele 1000 de module sunt ignorate. Se desenează un PT nou de 630 kVA pentru 100 kW, fără nicio întrebare (f61).
   - Sondă: „SUN2000-100KTL-M2\t3 buc” dă tot n = 1.
   - În #26 (Excel) se citesc 1 + 1 invertoare în loc de 3 + 2. Aici refuzul vine doar din întâmplare.
   - Ofertele și BOM-urile copiate sunt sursa reală cea mai frecventă de date, deci clasa asta e critică.
   - *Remediere:*
     - pe rânduri cu separatori (`\t`, `;`), un număr întreg izolat (sau „N buc”) din aceeași linie cu modelul înseamnă `n`;
     - antetul „Buc/Cant/Qty” fixează coloana.
2. **„CEF P kW cu N invertoare [model necunoscut]” — P e luat ca putere pe fiecare invertor.**
   - #58 și sonda „CEF 100 kW cu 2 invertoare” dau 2 × 100 = 200 kW, fără întrebare (p2).
   - E inversul bug-ului din r5 (acolo P se împărțea la N), la fel de periculos: QG, TC și C0 ies dimensionate la dublu.
   - *Remediere:* „CEF P kW cu N invertoare” fără „de X kW” înseamnă P = total. Se presupune N × P/N, cu presupunere declarată, sau se pune întrebare.
3. **Antetul „N invertoare:” urmat de lista de modele creează invertoare fantomă.**
   - #28: „CEF 300 kW cu 3 invertoare: 2 x SG110CX si 2 x SG50CX” dă [3 × 300 kW] + 2 × 110 + 2 × 50.
   - Rezultă 7 invertoare și 1220 kW. Aplicația adaugă singură un PT 1600 kVA, iar singura întrebare e „confirmați PT” (f28).
   - Contradicția 3 vs 4 nu e detectată.
4. **„2 x 50 kWp … fiecare cu câte un SG50CX” dă un singur invertor și 50 kWp, fără întrebare** (#51).
   - Forma „fiecare cu câte un” și multiplicatorul pe kWp nu se propagă.
   - Sonda „CEF 100 kWp: 2 x 50 kWp, fiecare cu un SG50CX” prinde problema doar prin plasa de raport c.c./c.a. și prin textul neconsumat.
5. **Invertoare monofazate (sufixul „-1”: Primo 8.2-1, câte unul pe fiecare fază) desenate trifazat** (#33, f33).
   - Pe planșă apar 3 × 400 V, 4P C16, CYY-F 5 × 2,5 și Iac 13 A. Valoarea reală e ≈ 37 A pe fază.
   - Q-ul ar declanșa la prima zi însorită.
   - Modelul preia text din frază („Primo 8.2-1 conectate cate unul”).
   - Întrebarea pusă e despre putere, nu despre faze.

## P1 (cele mai importante)

- **ATR-ul copiat e citit greșit** (#1, #15, #56). „Puterea aprobată pentru evacuare / maximă evacuată / maximă simultan absorbită X kW” e luată drept putere totală, iar rezultatul e refuz I08.
  - Corect: puterea evacuată înseamnă limitarea injecției (EMS + AR la PCC), iar valoarea 0 înseamnă injecție zero. Puterea absorbită ține de consum și nu are legătură cu CEF.
  - Sondă: „puterea aprobata 80 kW” ajunge doar în textul neconsumat.
  - Formatul ATR e exact cel din care proiectantul lucrează zilnic.
- **Contradicții nedetectate** (moștenite din r7):
  - injecție zero vs 20 kW aprobat (#16);
  - BMPT existent vs PT nou (#29);
  - autocorectura „scuze, de fapt SG110CX” e ignorată și se desenează ambele invertoare (#37).
- **CEF cu 2 trafo > ~2,2 MW nu se poate desena** (#9, #45). Există un singur TGD cu un singur QG pentru toată puterea, deci BL V06 (Ib 4763 / 6350 A > ACB maxim) și planșă goală.
  - La 2 trafo trebuie 2 TGD-CF, câte unul pe trafo.
  - În p1 măsura MT (QM) apare numai pe ramura T1, iar T2 pleacă separat spre o „BARA MT 20 kV”. Topologia măsurii trebuie să fie comună, în amonte de ambele celule trafo.
- **Acțiune „genereaza” cu planșă goală și fără întrebare:**
  - #25: 800 V + 400 V pe același trafo, BL V12 corect, dar nicio întrebare;
  - #53: „Ik 30 kA la bara” e parsat ca **Ik3_TG_kA = 0**, apoi BL V07 cu mesaj intern.
- **Pn pentru Huawei -H1/-H3 luat din cod:** SUN2000-330KTL-H1 dă 330 kW (real: 300 kW / 330 kVA), iar 215KTL-H3 dă 215 kW (real: 200 kW) (#7, #66, #67). La Huawei, numărul din cod = Smax.
- **Selectivitate inversată generată de aplicație:**
  - QJT Ir 288 A < QG Ir 304 A (f66);
  - QJT Ir 1800 A < QG/QB Ir 1900 A (f13).
  - QJT trebuie ales ≥ QG sau QG limitat la In trafo.
- **Măsura pe MT în engleză („MV metering”) e ignorată**, iar contorul rămâne pe JT (#67). Același lucru pentru „new 630 kVA … transformer” (neconsumat, deși desenat).
- **BESS:**
  - LUNA2000-200KWH-2H1 nu e recunoscut (#26, #68);
  - „4 x PCS 250 kW” devine 1 PCS (#13), iar „8 x 250 kW PCS” se pierde fără mesaj (#45);
  - „4 x baterii BOS-G 5,12 kWh” dă 5,12 kWh în loc de 20,5 kWh (#48, f48);
  - la #45, întrebarea „limitare 3 MW > 2 MW instalat” ignoră BESS-ul de 2 MW.
- **PT existent cu 2 trafo:** la racord pe bara T2 nu se verifică S ≤ Sn T2, deși 1100 kVA > 1000 kVA. Ik se calculează cu trafo-urile în paralel (#35).
- **BMPT 40 A cu Iac 79 A** e doar avertisment V72, fără întrebare (#24). Era deja recomandare în r6.
- **Engleză** (#34): „zero export” ignorat, adică fără AR/EMS; „existing main LV board” e citit ca racord JT din PT OD; „main breaker 400 A” rămâne neconsumat.

## P2

- **Întrebări inutile sau greșite:**
  - „18 module în total vs 54” la „3 stringuri x 18 module” (#17);
  - „120 kw panouri” e kWp, nu total c.a. → I08 (#27);
  - „Nu am folosit: CEF 330 kVA cu 3 invertoare de 110 kVA”, deși presupunerea arată că a fost folosit (#36);
  - „BMPTi-250” la racord în TG existent (#64).
- **V69 „nu există gPV în [21,3; 34] A”** e fals: există gPV de 25 / 32 A (#17).
- **BLOCANT V35/V36 pe Ik3 implicit la C0** (#20). La circuitul invertorului aceeași verificare e doar avertisment.
- **V25 blochează N redus 120 mm²** la cablul impus 3 × 240 + 120 Al, deși SG125CX nu încarcă neutrul (#65).
- **Cablu impus preluat inexact:**
  - NYY-J 4 × 95 e redenumit CYABY, cu PE separat (#19);
  - Al cerut, schimbat în Cu XLPE (#10);
  - „cablu solar 6 mm²” (c.c.) luat drept C0 impus (#2).
- **Nota 1 „branșament conform ST 4-JT / ST 3-JT”** apare pe toate planșele CEF cu PT (din r6).
- **Nota 2 „PT-ul propriu existent”** apare deși PT-ul e al OD (f65).
- **Titluri:** „CEF 300 kW + BESS” pentru 100 kW PV + 200 kW BESS (f12); invertoarele existente nu sunt marcate „existent” (#12, #42).
- **DDR 30 mA tip A** la invertoare de 20–30 kW (din r7). QI = QG = C63 în serie, fără avertisment (f48).
- **TCA la PCC dimensionat după Iac PV**, nu după sosirea TG (f14: 75/5 A).
- **kWp nu se calculează** din număr de module × Wp (#2, #61).
- **Punct rămas la sfârșitul modelului** („SUN2000-100KTL-M2.”, „SG125CX-P2.”).

## Planșe judecate ca la avizare (15)

| f | caz | invertoare / protecții | c.c. | c.a. (SPD / PI / măsură) | BESS / PT | verdict |
|---|---|---|---|---|---|---|
| 02 | ofertă 50 kW, TG | 1 × SG50CX, Q1 + SPD T2 ✔ | SB, S, SPD 1100 V ✔ | F1 T1+T2, PI → BD, TC 100/5 ✔ | – | bun (Q1 = QG ca valoare) |
| 10 | 5 × 100, PT nou 630 | ✔ | ✔ | ✔ TC 800/5 | PT separat: QL, FV, SF 40 A, T1, QJT 1000 ✔ | bun, aș semna |
| 12 | 2 × SG50CX + PowerStack | ✔ | ✔ | ✔ | SB-B, SPD c.c., PCS, QB 400 A ✔ | bun (titlu, „existent”) |
| 13 | BESS 1 MW, PT nou, MT | 1 PCS în loc de 4 | ✔ | QM + contor MT ✔ | **QG Ir 1900 > QJT Ir 1800** | parțial |
| 14 | prosumator 40 kW, injecție 0 | ✔ Q + DDR | ✔ | PI ext ✔, **TCA + AR la PCC** ✔ | – | bun |
| 28 | „3 invertoare: 2 + 2” | **3 × 300 kW fantomă** | ✔ | ✔ | PT 1600 adăugat singur | **P0** |
| 33 | 3 × Primo 8.2-1 mono | **3 × 400 V, C16 4P, 5 × 2,5** | ✔ | – | – | **P0** |
| 35 | 10 × 100, PT existent 2 × 1000, MT | ✔ idem, lizibil | ✔ | măsură MT existentă ✔ | T2 1000 < 1100 kVA neverificat | parțial |
| 48 | Deye 30 kW + 4 × BOS-G | ✔ | FB + BAT | PI ext ✔ | **BAT 5,12 kWh** | parțial |
| 61 | CSV 6 × 100 kW | **1 invertor** | ✔ | ✔ | PT 630 pentru 100 kW | **P0** |
| 65 | PT OD, cablu 2 × (3 × 240 + 120) | ✔ | ✔ | ✔ | banner „NEVERIFICAT — V02, V25” ✔ | corect blocat (V25 prea strict) |
| 66 | 330KTL-H1, 20/0,8 kV | 3 × 800 V, 3P, SPD 800 V ✔ | SPD 1500 V ✔ | contor 3 × 800 V ✔ | **QJT Ir 288 < QG Ir 304**, Pn 330 | parțial, aproape bun |
| 67 | 2 × 215KTL-H3, MV metering | ✔ 800 V | ✔ | **contor JT** în loc de MT | T1 20/0,8 ✔ | parțial |
| 68 | 100 kW + LUNA 200 kWh, injecție 0 | ✔ | ✔ | TCA + AR + EMS ✔ | **BESS lipsă** | parțial |
| p1 | 20 × 100, PT nou 2 × 1250, MT | idem × 20, lizibil | ✔ | QM doar pe ramura T1 | T1 + T2 + QC ✔, un singur QG 3200 A | parțial |

**Constant bine:**
- simbolistica (PI cu legătură roșie la BD, TC cu linie albastră de măsură);
- PT nou desenat separat de TGD-CF;
- ramura BESS completă (BAT, SB-B, SPD c.c., PCS, SPD c.a., QB);
- lista de echipamente, legenda și cartușul;
- banner-ul „NEVERIFICAT” pe planșele blocate.

## Recomandări (în ordine)

1. Parser de tabele (`\t` / `;` / „N buc” pe linie) pentru multiplicitate.
2. „P kW cu N invertoare” fără „de X” înseamnă P total. Antetul „N invertoare:” nu e grup de invertoare, ci verificare de sumă. „fiecare cu câte un” se propagă.
3. Sufixul „-1” / „L1” / Primo / Sunny Boy înseamnă monofazat. Mai multe invertoare mono pe un sistem trifazat înseamnă repartizare L1 / L2 / L3.
4. Vocabular ATR: putere evacuată → `limitare_injectie_kW`, putere absorbită → consum (ignorată la CEF), injecție zero la 0 kW.
5. La 2 trafo: TGD-CF / QG separat pe fiecare trafo, iar măsura MT comună, în amonte.
6. Pn Huawei -H1/-H3 din catalog, nu din cod. QJT ≥ QG.
7. „MV metering” / „Ik X kA la bara” / „N x baterii Y kWh” / LUNA2000-xxxKWH.
