# Runda 7 — fotovoltaic (CEF / prosumatori / BESS / PT)

Tester: inginer proiectant ANRE gr. II/III, CEF 20 kW – 5 MW. Fluxul testat este cel din `/api/chat` fără LLM: `interpretor.interpreteaza(text)`, apoi `constructor.genereaza`, `validare.valideaza`, `layout` și `render_svg`. PNG-urile au fost randate cu cairosvg la 2400 px.
70 de fraze complet noi (nu s-au citit `tests/` și nici frazele vechi). Datele sunt în `teste/r7/fotovoltaic/fraze.json`: frază, așteptat, obținut, verdict și prioritate. Planșele sunt în `teste/r7/fotovoltaic/fNN.png` (49 de planșe).

## Notă: 6/10 (r6: 5/10)

| | nr. | % |
|---|---|---|
| corect | 35 | 50 % |
| parțial | 27 | 39 % |
| greșit | 8 | 11 % |
| P0 (fraze) | 6 | 3 defecte distincte |
| P1 | 22 | |
| P2 | 12 | |

Față de r6 s-au îmbunătățit:
- **Plasa de siguranță.** Funcționează în majoritatea cazurilor: textul neînțeles apare în „Nu am folosit…” și se pune o întrebare (#3, #12, #22, #48).
- **Regula OD 27 kW.** E aplicată corect: 25 kW fără releu, iar 30/35/40/50 kW cu tablou și releu PI extern (#17, #32–#35, #62). Cazul de 28 vs 27 kW declarat primește întrebare (#31).
- **Verificările c.c.** Voc la Tmin (V68), gPV în afara intervalului 1,5–2,4·Isc (V69) și gPV automate la 3 stringuri în paralel sunt corecte (#7, #8, #52, #53, #54).
- **Contradicții simple.** Sunt prinse: mono 20 kW, Symo pe branșament monofazat, TN-S și TT, 3 declarate vs 2 modele, limitare peste puterea instalată, raport c.c./c.a. de 4 (#26, #27, #44, #58, #63, #51).
- **Rețeaua nu se mai presupune la prosumator.** Pentru #36 și #69 se pune întrebarea și exportul e blocat (V07).
- **PT nou.** E desenat ca post separat, cu celulă de linie, celulă trafo, descărcătoare MT și QJT (#13, #46, #65).

Nota nu urcă mai mult din cauza a trei defecte P0 de interpretare. Toate produc planșe cu aspect profesional, dar fizic greșite.

## P0 — de reparat înainte de orice utilizare

1. **„N x” dintr-un cablu sau dintr-o baterie e citit ca număr de invertoare.**
   - #28 „cablu impus CYABY 5x16 … Sungrow SG33CX” dă 5 × SG33CX = 165 kW. Pe planșă, fiecare invertor primește 4 × (ACYABY 4×240), adică 630 m de Al pentru 165 kW, iar C0 = 5×16 (impus).
   - #30 „STP 50-40 cu cablu CYY-F 5x6” dă 5 invertoare.
   - #15 „Deye SUN-12K-SG04LP3 cu 4 x Pylontech US5000” dă 4 × Deye = 48 kW, fără baterie (planșa f15).
   - Depinde de ordinea cuvintelor: „Sungrow SG33CX, cablu CYABY 5x16” e interpretat corect (n = 1). Regula: „N x” după care urmează o secțiune (mm²) sau un model de baterie nu e niciodată număr de invertoare.
2. **Numărul de transformatoare e ignorat pe ramura CEF/BESS.**
   - `n_trafo` e citit doar în `extrage_tablou` (r6, industrial), nu și în `extrage_cef`.
   - #21 „PT nou cu 2 trafo 1000 kVA” și „PT nou 2x1000 kVA” dau un singur trafo de 1000 kVA, BLOCANT fals V67 și propunerea „măriți la 2000 kVA”, deși utilizatorul a declarat deja 2 × 1000.
   - #60 „PT nou 2 x 630 kVA” dă un singur trafo de 630 kVA, cu QG 2000 A în aval de QJT 1000 A (selectivitate inversată pe planșă).
   - Aceeași cauză apare la #3 (2 × 1250 desenat ca un trafo de 2500 kVA, cu întrebare) și la #56 (4 × 1600).
   - Nu există niciun caz de CEF cu 2 trafo care să funcționeze.
3. **Invertoarele de 800 V c.a. sunt tratate ca invertoare de 400 V.**
   - #46: Sungrow SG250HX cu „PT nou 1250 kVA 20/0,8 kV” e desenat la 3 × 400 V + N, cu trafo 20/0,4 kV, 3 × (ACYABY 4×240) pe invertor și 4P. SG250HX nu are neutru. SPD-ul c.c. e de 1100 V, deși sistemul e de 1500 V c.c.
   - #45 (3 × SUN2000-330KTL-H1 în TG 400 V) e blocat doar pentru Sn, nu pentru incompatibilitatea de tensiune.
   - Trebuie: tensiunea c.a. citită din catalog sau fișă (800 V / 1500 V c.c.), trafo 20/0,8 kV, cabluri 3 + PE și BLOCANT la racordul unui invertor de 800 V într-un TG de 0,4 kV.

## P1 — cele mai importante

- **Tipul de schemă nu e detectat fără cuvânt-cheie** (6 fraze: #14, #19, #25, #59, #66 și #61, unde e luat drept tablou de consumator).
  - Exemple: „Fronius Primo GEN24 6.0 Plus monofazat cu BYD…”, „6 kW mono, Growatt MIN 6000TL-X, retea TT”, „solar 10 kw tri tn-c-s TG”.
  - Un model de invertor recunoscut, „panouri”, „solar” sau „PV” ar trebui să ducă la prosumator/CEF.
- **BESS-ul declarat prin model se pierde sau e întrebat inutil:**
  - LUNA2000-15-S0 (#11), LUNA2000-10-S0 (#55), Sunny Boy Storage + BYD HVS 10.2 (#67) și Pylontech;
  - la #12, „CEF 100 kW + BESS PowerStack” lasă pe planșă doar BESS-ul, iar CEF-ul dispare.
  - Capacitatea se poate deduce din cod (LUNA2000-**15**, HVS **10.2**, US5000 = 4,8 kWh).
- **Baterie-fantomă.** Invertoarele care pot fi hibride (SUN2000-xKTL-M1/L1) primesc automat BAT și FB, deși nu s-a cerut baterie (#24, #33, #62).
  - La #33 bateria apare doar pe INV-1 din 3 invertoare identice (f33).
  - Pe o planșă de avizare, asta înseamnă un echipament inexistent în BOM.
- **Contradicții nedetectate:**
  - injecție zero vs 15 kW aprobat în ATR, rezolvată tacit ca zero (#20);
  - baterie cuplată în c.c. cu Sunny Island, care e cuplat în c.a. (#16);
  - racord simultan în TG existent și în PT nou (#43);
  - Sunny Boy Storage monofazat pe un sistem trifazat (#67).
- **Injecție zero: TC și analizorul sunt pe plecarea PV, nu la PCC.**
  - În f17 și f55, TCA și AR sunt desenate în TD-PV, în aval de QG. Eticheta spune „P la PCC”, dar măsoară doar producția PV.
  - Funcțional, schema ar opri producția, nu injecția. Pentru aviz, TC-urile trebuie desenate pe intrarea instalației (în aval de BMPT sau pe sosirea TG).
- **„Măsura pe MT în celula de măsură” e ignorată tacit** (#65: contorul rămâne pe JT, iar lista de text neconsumat e goală). Plasa de siguranță a fost ocolită. Funcția există (`masura`), dar nu e legată la CEF.
- **Selectivitate pe planșă:**
  - Q invertor = QG ca valoare apare sistematic (V41 pe aproape toate planșele);
  - QB = QG = QJT = 1000 A, cu Ir 950 A > In trafo 909 A (#13, V60 generată chiar de aplicație);
  - QG 2000 A în aval de QJT 1000 A (#60).
  - Constructorul își generează singur avertismentele, în loc să aleagă alte valori.
- **Lizibilitate la peste 8 invertoare.**
  - Toate invertoarele sunt desenate pe un singur rând: 16 invertoare la scara 30 % (f21), 20 invertoare la 24 % (#3), 8 invertoare la 60 % (f65). Peste 60 % din foaie rămâne goală.
  - Lipsește gruparea „1 ramură tip × N identice” sau dispunerea pe 2 rânduri.
- **Întrebări stâlcite:**
  - #41: „Invertorul este SUN2000-100KTL-M2 dar puterea totala (100 kW) sau un model de 500 kW?”;
  - #64: „Nu am folosit: racord in PT existent”, deși racordul a fost folosit, iar presupunerea „BMPT” contrazice racordul în PT.
- **#55, monofazat 6 kW:**
  - eticheta „TCA 3 × 50/5 A”, deși lista de echipamente spune 1 buc;
  - titlul „CEF 6 kW” în loc de prosumator;
  - PI externă la 6 kW (nu e cerută de OD sub 27 kW);
  - „racord prin BMPT” pentru monofazat (corect: BMPM).

## P2

- Numărul de module × Pmax nu e folosit la kWp (#1: 40 × 500 W, „kWp nedeclarat”). Din această cauză, la #15 raportul 10,8 kWp / 48 kW nu e semnalat.
- Racordul nedeclarat al unei CEF de 165 kVA e presupus BMPT fără întrebare (#6).
- Întrebări inutile:
  - 9 × 100 = 900 kW (#57);
  - „pv 8kw” întreabă puterea, deși e dată (#37);
  - BMPT 3x200A (#22);
  - substation 630 kVA (#48);
  - „huawey 20ktl” (#49).
- Mesajul V20 „ΔU > 3 % chiar la 4 × 240 mm²” e înșelător: depășirea vine din C0 impus, nu din cablul invertorului (#28, #29, #30).
- Modelul preia text din frază: „PowerStack 255CS cuplat” (#12).
- DDR de 30 mA pe invertoare de 30 kW (#17). Producătorii recomandă 100–300 mA, altfel apar declanșări intempestive.

## Planșe judecate ca la avizare (15)

| f | caz | invertor + protecții | c.c. (gPV / sep. / SPD) | c.a. (SPD / PI / contor) | BESS / PT | lizibilitate | verdict |
|---|---|---|---|---|---|---|---|
| 01 | CEF 20 kW TG | INV + Q1 + SPD T2 ✔ | S1, SB, SPD 1100 V ✔ | F1 T1+T2, PI→BD QG, TC + contor ✔ | – | A3 foarte bună | bun (V41 Q1 = QG) |
| 04 | 7 inv. mixte, PT existent | fiecare cu Q și SPD ✔, modele corecte | ✔ | ✔ TC 1250/5 | – | A1, 45 % gol | bun |
| 09 | gPV 15 A | ✔ | gPV 15 A (12 buc ±) ✔ | ✔ | – | foarte bună | bun |
| 12 | CEF + BESS c.a. | – | – | ✔ | doar BESS, **CEF lipsă** | bună | greșit conținut |
| 13 | BESS 500 kW + PT nou | PCS + QB ✔ | SB-B, SPD c.c. 1000 V ✔ | ✔ | PT: QL + CLP, SF 40 A, FV, T1, QJT ✔ | bună | bun (selectivitate QB = QG = QJT, Ir > In_T) |
| 15 | Deye + 4 Pylontech | **4 invertoare** | ✔ | ✔ | **fără baterie** | bună | P0 |
| 17 | prosumator 30 kW, injecție 0 | ✔ QI + DDR | ✔ | PI externă ✔, **TC injecție pe plecarea PV** | – | bună | parțial |
| 21 | 16 × 100 kW, 2 trafo | ✔ | ✔ | ✔ | **1 trafo** | **ilizibilă (30 %)** | P0 |
| 24 | prosumator mono TT | ✔ QI C32 + DDR 30 mA | ✔ | TE existent, contor OD ✔ | **BAT fantomă** | foarte bună | parțial |
| 28 | cablu impus 5x16 | **5 invertoare**, 4 × (4×240)/inv. | ✔ | ✔ | – | A1 | P0 |
| 33 | 3 × 10 kW prosumator | ✔ Q + DDR pe fiecare | ✔ | PI externă ✔ | **BAT doar pe INV-1** | bună | parțial |
| 46 | 4 × SG250HX, 20/0,8 kV | **3 × 400 V + N** | **SPD 1100 V pe 1500 V** | ✔ | trafo **20/0,4** | bună | P0 |
| 55 | mono 6 kW TT, LUNA | ✔ Q1 + DDR 100 mA | ✔ | DDR-G 300 mA S ✔, **TCA „3×” pe mono**, PI inutilă | **LUNA lipsă** | bună | parțial |
| 60 | BESS 1 MW, 2 × 630 | PCS + QB 2000 A | ✔ | ✔ | **1 trafo**, QG 2000 A după QJT 1000 A | bună | P0 |
| 65 | 8 × 100 kW, măsură MT | ✔ | ✔ | contor JT (**MT ignorat**) | PT nou ✔ | 60 %, 55 % gol | parțial |

Ce iese bine pe toate planșele:
- simbolistica: SPD c.c. cu „=”, PI cu legătură roșie la bobina BD, TC cu linie de măsură albastră;
- poziționarea în listă, legenda, cartușul și notele;
- echipotențializarea ramelor (PE) și cutia SB.

## Recomandări (în ordine)

1. Contextul „N x” în interpretor: secțiune de cablu sau model de baterie înseamnă că nu e număr de invertoare.
2. `n_trafo`, `masura` și `U_ca` (800 V) pe ramura CEF/BESS din `extrage_cef` și `_cef`.
3. Detectarea tipului după model de invertor, „panouri”, „solar” sau „PV”.
4. Hibrid ≠ baterie: BAT se desenează numai la baterie declarată. Capacitatea se citește din codul modelului.
5. TC-urile pentru injecție zero se desenează la PCC (intrarea instalației).
6. Gruparea invertoarelor identice când sunt mai mult de 8 pe aceeași planșă.
