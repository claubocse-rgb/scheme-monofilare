# Runda 10 — testare industrială (inginer proiectant ANRE III/IV), FĂRĂ cheie API

Motor: `interpretor.interpreteaza(text, foloseste_llm=False)` (= `interpreteaza_local`) → `constructor.genereaza(intrare_fizica, cartus=…)` exact ca în `app.py /api/chat` → `validare` → `layout`/`render_svg` → PNG (cairosvg).
68 de fraze noi (`teste/r10/industrial/fraze_src.py`), rezultate brute în `teste/r10/industrial/fraze.json`, planșe `iNN.svg` (46) și `iNN.png` (23). Reproducere: `python3 teste/r10/industrial/run.py [iNN …]`.
Nu s-au citit `tests/`, fraze.json vechi sau rapoartele r5–r9; engine/, tests/, static/ nemodificate.

## Notă: **4,0 / 10** (r9: 4,5)

| | nr. | % |
|---|---|---|
| corect | 24 | 35 % |
| parțial | 18 | 26 % |
| greșit | 26 | 38 % |
| **P0** | **11** | i03, i08, i12, i30, i41, i43, i45, i47, i61, i65, i67 |
| P1 | 29 | |
| P2 | ~20 | |

Frazele din r10 au fost voit mai „de proiect real” (PT cu 2 trafo, GE insular, vitali/nevitali, ATS între trafo, tabele Excel, bilanțuri, e-mailuri). Ce e bun: întrebările la contradicții clare (i07, i26), refuzurile cinstite în afara domeniului (IT medical i19, 690 V/IT i55, GE subdimensionat i63), cascada TG→TD→TE (i20), Y-Δ cu RT pe ramura Δ = Ib/√3 (i29, i56), stația sprinklere (i29: fără DDR, RT doar semnalizare, NHXH E90, RCM), PT 1600 kVA uscat cu întreruptor MT + 50/51 + măsură MT + compensare (i11), CP/HP→kW (i50), cablu impus în paralel verificat și blocat corect (i17), Sc > Sn blocat (i42). Ce trage nota în jos: **topologiile care nu există în motor sunt „turtite” în tăcere** într-o schemă plauzibilă dar falsă (al doilea trafo dispare, rețea/GE inventate, vitali amestecați cu nevitali) și **parserul cade la notații uzuale** („(1+1)”, „ks 0.7”, „2 x 11 kW”, tabel Excel cu coloana U).

## P0 (planșă falsă care arată „bună” sau periculoasă)

| id | text (scurt) | obținut | de ce e P0 |
|---|---|---|---|
| i03 | TG magazin, TT, **BMPT 63A trifazat**, … | BMPT desenat ca **plecare** (sep. fuzibil 63 A + DDR); sursă „NEDECLARATĂ”; Q1 = 160 A > BMPT 63 A; întreabă „din ce sursă?” | sursa declarată devine consumator; Q general mai mare decât protecția OD |
| i08 | PT cu **2 trafo 1000 kVA**, cuplă JT, 2L+M+2T, TG cu 2 semibare | 1 trafo, 1 celulă trafo, fără cuplă, fără celula de măsură (deși „măsura pe MT (declarată)”) | al doilea trafo dispare fără nicio mențiune (blocat azi doar de V07 — după completarea plecărilor rămâne greșit) |
| i30 | **2 × 1250 kVA în paralel** pe aceeași bară | 1 trafo, Ik3 = 31,4 kA | Ik real ≈ 60 kA → Icu ales neconservator; întrebare inutilă „TG 4000 A?” |
| i47 | **ATS între 2 transformatoare** 630 kVA | schemă GE + ATS cu **„GE 630 kVA” inventat**, cele 4 TD comasate în „Consumatori” | echipament inexistent pe planșă, nevalidat ca eroare |
| i43 | **GE 500 kVA, fără rețea (site izolat)** | ATS cu ramură „REȚEA · TGD existent” inventată; plecările comasate | contrazice textul explicit |
| i12, i67 | vitali / nevitali separați explicit, GE + ATS | **refuz**: „sarcina 529 A > In GE” — adună și nevitalii; cere GE ≥ 400 kVA (i12) / 200 kVA (i67); i12 avertizează „consumatori de incendiu pe GE” fără să existe | ignoră exact distincția pe care se proiectează GE-ul (I7, NP-015) |
| i41 | car wash (EN), 3×63 A, TT | clasat **locuință**: „Prize baie”, „Prize bucătărie”, Boiler 24 kW **monofazat C125**, uscător 15 kW mono C80, cele 3 pompe comasate în „Pompă” mono 42 A, aspiratoarele lipsă, BMPTd-100 în loc de 63 A | planșă absurdă (blocată de V40, dar din motive secundare) |
| i45 | plecare EV 22 kW, 5x10 Cu, 45 m, **RCD tip B** | niciun DDR pe circuitul EV; nume plecare „nouă pentru stație de încărcare EV”; 45 m pus pe alimentare + 50 m pe plecare | DDR 30 mA obligatoriu (HD 60364-7-722), cerut explicit |
| i61 | **pompă de incendiu** 45 kW + diesel (1+1) | DOL cu **releu termic care declanșează**, ACYABY obișnuit, întrebare „ce e Rezervă 1+1…?” | contextul „incendiu” e recunoscut doar la „sprinklere” (i29), nu la „pompă de incendiu” |
| i65 | PT 1000 kVA **uk 4 %** | folosește uk 6 % din tabel (Ik3 25,3 kA în loc de ≈ 36 kA), doar notat în „presupus” | valoare declarată înlocuită cu una mai puțin acoperitoare la scurtcircuit |

## P1 — familii de cauze

1. **Parserul refuză notații banale** (refuz „Valoarea X din listă nu are unitate”): „(1+1 rezervă)” i04, i34; „ks 0.7, cos 0.85” i57; „Pi = 180 kW, ku = 0,7 … cosφ = 0,92” i22; „interblocaj 2 din 3 … câte 3 plecări” i62. „2 x 11 kW și 4 x 2,2 kW” (cu spații) nu e citit (i64); „4 stații EV 2x22 kW” nu dă plecări (i46). Tabel Excel cu coloana U[V] 400/230 → „contradicție mono/tri” (i21).
2. **Clasificare greșită**: „cuptor electric 72 kW la 400V” → locuință, refuz (i25); PTA 250 kVA cu BMPT 400 A → branșament, refuz V50 + propune „ex. 400 kVA” (i09); „pt uscat 630” → „pt = pentru” (i53); „utility transformer 400 kVA” → PT propriu cu celule MT (i05); „BMPT trifazat 32 A, tablou monofazat” → branșament **mono** fără întrebarea de contradicție (i39); cablu MT 18/30 kV → „contradicție 30 kV vs 20 kV” (i49 — 18/30 kV e izolația uzuală pe rețeaua de 20 kV).
3. **Date explicite pierdute în tăcere sau cu întrebare inutilă**: pompă 45 kW cu convertizor (i35, rămâne doar ventilatorul); UPS 100 kVA cu bypass (i36); uscător 3 kW înghițit în textul compensării (i58); pompa de rezervă (i54); „existing MDB” → BMPT presupus (i60); corectura „nu 400, ci 630 kVA” → „Care e puterea trafo?” (i68); măsura pe JT/MT declarată dar nedesenată (i31, i48, i08); separarea PEN în TG la TN-C-S nedesenată (i37); comutator 1-0-2 recunoscut dar TT neacoperit la GE → planșă goală cu nota „TN-S” (i15).
4. **Lungimea / cablul impus ajung pe alt tronson** când e un singur receptor „din TG existent”: i18 (120 m pe alimentare, „4x4” devine „5×4”), i56 (70 m), i45. Motorul ar trebui să fie plecarea din tabloul existent, nu un TG nou interpus.
5. **TN-C cu 2,5 mm²** nesemnalat (i27); denumiri cu greșeli păstrate pe planșă „Compresr / Venitlator / Ilumnat” și compresorul nerecunoscut ca motor (i23).
6. **V25 blochează** neutrul redus pe cabluri existente 3x150+70 / 3x240+120 (i37, i17) — HD 60364-5-52 §524.2.3 îl permite în condiții; ar trebui AVERTISMENT + întrebare, nu BLOCANT pe o temă reală.

## P2 (selecție)
- Dimensionare nerealistă pe motoare mici: 7,5 kW / 9 kW → **CYABY 5×25 mm²** la 50 m (i01, i05); MCCB TM 4P + contactor + RT în loc de întreruptor-motor (MPCB) 3P; cablu cu 5 conductoare (N) spre motoare; în hale „prize N circuite” și „iluminat” → separator fuzibil 3P + cablu 5×6 (i01, i03, i66).
- V42 „selectivitate parțială” pe fiecare plecare (zgomot: 30+ linii la i37).
- Y-Δ desenat cu un singur cablu „3+N+PE” deși lista spune 2 cabluri (i29, i56); fără verificarea pornirii pe GE (i29: 75 kW Y-Δ pe GE 150 kVA; i43: concasor 200 kW pe GE 500 kVA).
- Întrebări inutile: „TG 2500 A / 4000 A — ce reprezintă?” deși ACB-ul e desenat (i11, i30).
- Sursa nedeclarată nu e întrebată, doar notată în „presupus” și pe planșă (i06, i66); la i54 întreabă mono/tri dar desenează tri.
- „0,75 kW” afișat „0,8 kW” (i20, i37); i10: textul „trafo 20/0,4 kV, rețea 20 kV” deși planșa e corect 6 kV.
- 40 de plecări a câte 2 kW etichetate „TD-1…TD-40” (i38).

## Planșe judecate (17) ca la avizare

| planșă | verdict | observații |
|---|---|---|
| i01 TG hală 1000 kVA | parțial | lizibil, listă și cartuș OK; motoare 7,5 kW pe 5×25 Cu, MCCB 4P; prize trifazate cu fuzibil+RCCB 4P |
| i03 TG magazin TT | respins | BMPT ca plecare, sursă „nedeclarată”, Q1 160 A |
| i08 PT 2×1000 kVA | respins | 1 trafo, fără cuplă/măsură; marcat NEVERIFICAT (V07) |
| i11 PT 1600 uscat | admis cu obs. | MT corect (L + M + Q cu 50/51), ACB 2500 A, compensare 400 kvar; fără plecări reale (întrebat) |
| i15 fermă GE 1-0-2 TT | respins | planșă goală, nota zice TN-S |
| i20 cascadă | admis | TG→TD1→TE1 + TD2 corecte, DDR doar pe prize |
| i29 sprinklere | admis cu obs. | foarte bună; Y-Δ un singur cablu, sursa rețea presupusă |
| i30 PT 2×1250 paralel | respins | 1 trafo, Ik subestimat |
| i31 PT 400 L+T | parțial | MT corect, măsura JT declarată lipsește |
| i37 temă hală 2000 mp | parțial | cartuș completat (beneficiar, Oradea, DTAC), 34 plecări pe 3 rânduri lizibile; blocat V25 pe cablul existent; separarea PEN lipsește |
| i38 40 plecări | admis cu obs. | 3 rânduri, lizibil la A2; denumiri TD-n |
| i41 car wash | respins | locuință cu prize baie, boiler 24 kW mono |
| i43 GE insular | respins | rețea inventată |
| i45 EV | respins | fără DDR |
| i47 ATS 2 trafo | respins | GE inventat |
| i56 motor 90 kW Y-Δ | parțial | aparataj Y-Δ corect; TG interpus inutil, 70 m pe tronsonul greșit, un cablu în loc de două |
| i61 pompă incendiu | respins | RT care declanșează, cablu nerezistent la foc |

## Tabel complet (așteptat → obținut)

| id | stil | verdict | P | obținut (rezumat) |
|---|---|---|---|---|
| i01 | temă | parțial | P1 | corect structural; motoare 5×25, MCCB 4P+KM+RT |
| i02 | scurt | parțial | P2 | întreabă plecările; 25 kW mono (113 A) acceptat fără observație |
| i03 | listă | greșit | P0 | BMPT = plecare |
| i04 | e-mail | greșit | P1 | refuz „valoarea 1 fără unitate” din „(1+1)” |
| i05 | EN | parțial | P1 | „utility transformer” → PT propriu cu MT; încărcătoare = motoare DOL |
| i06 | scurt | parțial | P2 | sursă presupusă BMPT, neîntrebată |
| i07 | contradicție | corect | – | întreabă mono/tri |
| i08 | PT | greșit | P0 | 2 trafo → 1 |
| i09 | PT | greșit | P1 | PTA → branșament, refuz V50 |
| i10 | PT | corect | P2 | 6 kV corect pe planșă; texte „20 kV” în presupus |
| i11 | PT | corect | P2 | întrebare inutilă „TG 2500 A” |
| i12 | spital | greșit | P0 | vitali+nevitali adunați, refuz GE |
| i13 | incendiu | corect | – | întreabă kVA GE |
| i14 | incendiu | corect | – | întreabă kVA GE |
| i15 | fermă | greșit | P1 | TT neacoperit la GE → planșă goală |
| i16 | compensare | corect | – | cere puterea TG |
| i17 | cablu paralel | corect | P2 | 2×240 Al blocat corect (Iz); V25 prea strict |
| i18 | cablu impus | parțial | P1 | blocat, dar 120 m pe alimentare, 4x4→5×4 |
| i19 | IT medical | corect | P2 | refuz cinstit de domeniu |
| i20 | cascadă | corect | – | |
| i21 | Excel | greșit | P1 | „contradicție mono/tri” |
| i22 | bilanț | greșit | P1 | „0,9 fără unitate” |
| i23 | typo | parțial | P1 | nume cu greșeli, compresor ≠ motor |
| i24 | HVAC | corect | P2 | schema TN implicită neîntrebată |
| i25 | scurt | greșit | P1 | → locuință, refuz 72 kW |
| i26 | contradicție | corect | – | TT vs TN-S întrebat |
| i27 | TN-C | parțial | P1 | TN-C < 10 mm² nesemnalat |
| i28 | mono din PT | corect | P2 | |
| i29 | sprinklere | corect | P2 | |
| i30 | PT paralel | greșit | P0 | 1 trafo |
| i31 | PT | parțial | P1 | măsura JT lipsă |
| i32 | scurt | corect | – | |
| i33 | bucătărie | corect | – | cablu impus 5x16 30 m pe alimentare |
| i34 | HVAC | greșit | P1 | „(1+1)” |
| i35 | VFD | greșit | P1 | pompa 45 kW cu convertizor pierdută |
| i36 | UPS | parțial | P1 | UPS + bypass pierdute |
| i37 | temă | parțial | P1 | V25 blocant, PEN nedesenat |
| i38 | 40 plecări | corect | P2 | |
| i39 | contradicție | greșit | P1 | branșament mono, contradicția neîntrebată, prize pierdute |
| i40 | scurt | corect | – | |
| i41 | EN | greșit | P0 | locuință |
| i42 | Sn ≪ P | corect | P2 | blocat V62 (ideal întrebare) |
| i43 | GE insular | greșit | P0 | rețea inventată |
| i44 | lift | parțial | P2 | „iluminat cabină și puț 0,5 kW” spart greșit |
| i45 | EV | greșit | P0 | fără DDR |
| i46 | EV | greșit | P1 | plecări necitite |
| i47 | ATS 2 trafo | greșit | P0 | GE inventat |
| i48 | RM6 | parțial | P1 | măsura MT nedesenată |
| i49 | cablu MT | greșit | P1 | 18/30 kV = contradicție |
| i50 | CP/HP | corect | – | |
| i51 | kVA | corect | P2 | |
| i52 | amperi | corect | P2 | V60 Ir Q1 > In_T semnalat |
| i53 | scurt | greșit | P1 | „pt” = pentru |
| i54 | 1+1 | parțial | P1 | rezerva pierdută |
| i55 | IT 690 V | corect | – | refuz cinstit |
| i56 | Y-Δ | parțial | P1 | lungime pe tronson greșit, 1 cablu |
| i57 | bilanț | greșit | P1 | „0,8 fără unitate” |
| i58 | compensare | parțial | P1 | uscătorul pierdut |
| i59 | capcană | corect | – | nu inventează |
| i60 | ro/en | parțial | P1 | „existing MDB” → BMPT |
| i61 | incendiu | greșit | P0 | pompă incendiu ca motor normal |
| i62 | 2 surse | greșit | P1 | refuz „3 fără unitate” |
| i63 | GE mic | corect | – | |
| i64 | 2 x 11 | greșit | P1 | necitit |
| i65 | uk | greșit | P0 | uk declarat ignorat |
| i66 | sursă | parțial | P2 | sursa neîntrebată |
| i67 | GE vitali | greșit | P0 | vitali ignorați |
| i68 | corectură | parțial | P1 | corectura neaplicată |

## Priorități pentru r11
1. Topologii nesuportate (2 trafo / paralel / ATS între trafo / GE insular / bară vitali + nevitali / UPS) → **întrebare sau refuz explicit**, niciodată turtire în ce există (P0 i08, i30, i43, i47, i12, i67, i36).
2. Tokenizarea listei: ignoră „(1+1)”, „1+1 rezervă”, „ks/ku/cos/cosφ = x”, „2 din 3”, „N x P kW” cu spații, tabele cu coloana U.
3. Respectă datele declarate: BMPT/sursă, uk, RCD tip B, măsură, separare PEN, corecturi „nu X, ci Y”.
4. „pompă de incendiu / hidranți / desfumare” → aceleași reguli ca la „sprinklere” (fără DDR, RT doar semnalizare, cabluri E90).
5. Clasificare: locuința doar cu indicii de locuință; PTA ≠ branșament; „pt” minuscul urmat de kVA/uscat/ulei = PT; cablu MT „18/30 kV” = izolație.
6. Realism la motoare mici (MPCB 3P, cablu 4 conductoare, fără 5×25 la 7,5 kW) și V42 agregat.
