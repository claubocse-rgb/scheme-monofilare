# Runda 11 — locuințe, branșamente, prosumatori (reguli locale, fără cheie API)

Data: 2026-10-26 · Tester: proiectant instalații electrice (ANRE gr. II/III)
Calea testată: `interpretor.interpreteaza` (ca în `/api/chat`, fără cheie) → `constructor.genereaza(intrare_fizica)` → `layout` → `render_svg` → PNG (cairosvg), plus `validare.valideaza`.
Frazele (66, toate noi): `teste/r11/locuinte/fraze.json` · rezultatele brute: `teste/r11/locuinte/rezultate.json` · rularea: `teste/r11/locuinte/ruleaza.py` · planșele: `teste/r11/locuinte/pNN.png` (52 generate; 14 fraze au primit refuz sau întrebare fără planșă).
Nu s-au modificat `engine/`, `tests/`, `static/`. Nu s-au citit `tests/` și nici frazele vechi.

Reguli de verdict: DDR la branșament de tip A; Q presupus = calibrul standard ≥ Ib la cosφ 0,95; VE dimensionat pe 1,25 × I; rețeaua nu se presupune; peste 27 kW se cere PI externă. Tabelul de confirmare contează la severitate: o greșeală evidentă și marcată (presupusă sau „De lămurit”) e P2. O greșeală nemarcată rămâne P0/P1.

## Notă: **5 / 10** (r10: 4,5/10)

| | nr. | % |
|---|---|---|
| Corect | 16 | 24 % |
| Parțial | 36 | 55 % |
| Greșit | 14 | 21 % |
| **P0** | **2** (#3, #20 — aceeași cauză) | |
| **P1** | **12 fraze** + 1 defect sistemic (A: „N lumini”, 26 de fraze) | |
| P2 | ~35 | |

Ce s-a îmbunătățit față de r10:
- Hibridul cu EPS (r10 P0 #66) iese acum corect: invertor hibrid, baterie și TD-EPS cu circuitele critice (#16).
- Prosumatorul peste 27 kW are TD-PV cu PI externă și bobină BD (#8, #64).
- Blocajele V46 vin acum cu întrebare, nu mai sunt fundături tăcute.
- Funcționează: regula VE (#22, #50, #63), autocorectura „6, nu, 7” (#24, #59), TT cu RA (#36, #37), refuzul contradicțiilor reale (#10, #11, #38, #47) și refuzul „fără DDR” (DDR-ul rămâne).

Ce trage nota în jos:
1. O cauză P0 nouă: Q-ul declarat la branșament nou e ignorat.
2. Detectorul de contradicții mono/tri e prea larg. Refuză patru situații perfect normale.
3. „N lumini” se pierde sistematic, fără nicio marcare.

## P0 — planșă greșită, nemarcată, exportabilă

**#3 și #20 — branșament NOU cu Q declarat: Q-ul e înlocuit în tăcere.**
- #3 „branșament nou trifazat 3x25A, Pa 15 kW…”: tabelul arată „Q branșament 25 A”, dar pe planșă apar QB **C40**, BMPTd-40 și coloana CYABY 5×10. Singurul mesaj e V46 AVERTISMENT: „Q ales pe puterea cerută”. Mesajul e fals, pentru că Q-ul a fost ales din Pc 20,86 kW (p03.png verificată).
- #20 „Branșament nou 3x25A, nu știu încă Pa”: QB **C32** în loc de 25, fără nicio notă (p20.png verificată). Exportul nu e blocat.

Cauza e în `calc/locuinta.py` (în jurul liniei 1342). Pentru `bransament_nou`, ramura `elif pa is not None and q_decl is None` nu tratează cazul cu `q_decl` setat. Codul cade pe `else` → `Ib = max(i_dim, ib_pc, …)`, iar `_bransament` alege Q din Ib.

Aceeași cauză apare și la mono (verificare suplimentară). „Branșament nou monofazat Q 32A, Pa 7 kW, plită 7 kW, cuptor 3 kW…” ignoră Q 32 și Pa 7 și blochează V53 „nu există BMPM”. Întrebarea vorbește despre „invertor”, deși fraza nu are niciun invertor.

## P1

**A. „N lumini” se pierde în tăcere (sistemic, 26 de fraze).**
- „3 iluminat” → 3 circuite. „3 lumini”, „8 lumini”, „6l” → 1 circuit „Iluminat” sau perechea tipică interior/exterior.
- Nu apare nici în „Am presupus”, nici în „Nu am folosit”.
- Fraze afectate: #3, 9, 12, 19, 20, 21, 25, 28, 30, 31, 33, 35, 36, 37, 39, 41, 42, 48, 49, 50, 53, 56, 59, 62, 63, 65.
- Același defect apare la abrevieri: „8p 6l” (#63) dispare fără marcare.

**B. Contradicție falsă mono/tri (I08) — refuză topologii normale:**
- #5 mărire de putere „de la 6 kW monofazat la 11 kW trifazat” → „Contradicție: monofazat și 3x25A”. Cazul e foarte frecvent.
- #14 TG trifazat cu TE parter/etaj monofazate (cascadă) → refuz. În plus, apare plecarea fantomă „trifazat cu stație VE”.
- #34 casă trifazată cu un aparat de sudură monofazat → refuz.
- #9 autocorectura „trifazată 3x32A… de fapt nu, e monofazată 40 A” nu e recunoscută. Rezultatul e un refuz cu întrebare (P2 luat separat, dar tot pe această cauză).
- #55 două branșamente (mono casă + tri atelier) primesc aceeași întrebare greșită (P2).

**C. Date puse pe alt element, fără marcare:**
- #66 „pompa de apă din fântână e la 120 m” → **coloana C2 = 120 m, CYABY 3×70**. Pompa rămâne la 30 m pe 2,5 mm², iar „1,5 kW” e neconsumat. Planșa e blocată V46 (p66.png).
- #52 „prizele pe C25 cu cablu 2,5 mm²” → 2,5 mm² e aplicat **coloanei C2** (CYABY 3×2,5 sub C40). Urmează V02/V03 și o cascadă ΔU: iluminatul ajunge pe 3×16 mm² (p52.png). Cele 6 circuite de prize devin unul singur. Întrebările se referă la cablul pus greșit, nu la ce a cerut omul.
- #40 „tablou secundar monofazat cu 3 kW: 2 prize, 1 lumină, un frigider” → circuitul fantomă **„Monofazat cu” 3 kW, C16, 3×10**. Lumina se pierde. Planșa nu e blocată (p40.png).
- #41 „priză trifazată CEE 32A în garaj” → „Priză” 1P+N C16, nemarcat.
- #58 „generator de rezervă 8 kVA pe intrarea GEN” e citit ca invertor de 8 kW → contradicție falsă „1 × 8 kW ≠ 10 kW”.

**D. Topologie greșită:**
- #45 „doar TE baie, alimentat monofazat din TE apartament” → desenat ca apartament cu BMPM-32, contor și Q/Pa presupuse, nu ca tablou secundar.
- #61 „vilă cu 2 apartamente, fiecare cu contor 32 A” → un singur apartament. Al doilea se pierde nemarcat.

**E. Parsare:**
- #28 TE mansardă nou alimentat din tabloul existent → refuz „valoarea 4 nu are unitate”. Interpretarea e „tablou trifazat” (nedeclarat).
- #29 typo-uri („cas mnofazata 32 a, 7kw, 5 prz 3 ilum”) → TG trifazat cu plecarea „Cas mnofazata” 3×32 A, unde „7kw = calibrul”. Sistemul întreabă rețeaua, dar desenează 3P și **nu blochează** exportul (V07 lipsește).

## P2 (selecție)

**Q și V46:**
- Blocajul V46 „Ib de calcul > 1,13·In Q” apare și la depășiri de 0,13–0,16 A (#35, #59). Mesajul spune totodată „Ib general se ia din puterea aprobată”.
- Opțiunea „mutarea circuitelor monofazate pe altă fază” e propusă la branșamente **monofazate** (#1, 21, 22, 33, 35, 39, 59, 66).
- V46 e BLOCANT când Q e declarat și doar AVERTISMENT când Q e presupus, la aceeași situație (#49 față de #22).

**Prosumatori:**
- „Q 3x25A”, „Q 3x50A”, „branșament mono 32A” nu sunt consumate (#6, 7, 17, 26). Sunt marcate „Nu am folosit”, dar verificarea Iac ≤ Q nu se mai face.
- La #6 apare eticheta „BMPT existent” la un prosumator monofazat.

**DDR:**
- DDR 30 mA pe invertoare de 25–30 kW (#8, 26, 64): risc de declanșări intempestive. Fișele cer de regulă 100–300 mA tip A/B.
- RCBO-ul de branșament de 300 mA nu e de tip S la mono (inclusiv TT, #4), deci nu e selectiv cu DDR-urile de 30 mA.

**Echipamente și cabluri:**
- Plita pe rețea trifazată e trecută **3F 4P C16 5×2,5** fără marcare (#3, #56). Majoritatea plitelor se leagă mono sau pe 2 faze.
- Saunei îi lipsește cablul termorezistent (#12).
- Plita de 7,4 kW e pusă pe C40 / 3×10 mm². Practica obișnuită e C32 / 6 mm² (#35).
- Apare RCCB 4P de 16 A, calibru inexistent (#48).

**Generator:**
- #15: circuitele prioritare de pe GE sunt ignorate (marcate). GE de 6,88 kVA alimentează toată casa (Q 40 A) fără avertisment. În lista de materiale, GE-ul monofazat apare ca „3 × 400/230 V”.
- #44: GE de 10 kVA pentru o casă cu Pa 15 kW, fără avertisment.

**Prosumator cu PI (#8):** QI și QG sunt ambele C63 modulare în serie, deci fără selectivitate. Lipsește limitarea injecției (Pinv 30 > Pa 25 e doar notată).

**Alte probleme:**
- #51: „clientul nu vrea să-i sară siguranța” ajunge în câmpul beneficiar.
- #46: o întrebare tehnică („ce secțiune la plita de 7 kW?”) e tratată ca cerere de schemă.
- #62: „cuptor cu microunde” e citit ca „Cuptor” 3,5 kW, iar „congelator” ca „Frigider” (nume dublat).
- #39: coloana unui apartament (firidă de palier) e presupusă în pământ, CYABY D1. Presupunerea e marcată.
- #64: cablul C0 până la BMPT e trecut „conform releveu”, nedimensionat, deși Σ Iac = 79 A.

## Planșe judecate ca la avizare (15)

| Planșa | Verdict | Observații |
|---|---|---|
| p03 | **respinsă** | QB C40 / C2 5×10 cu Q declarat 25 A (P0). Plita 3F. Un singur circuit de iluminat la „6 lumini”. Restul e curat: SF, contor, RCCB 300 mA S, IS, SPD cu protecție de rezervă, grupe DDR. |
| p20 | **respinsă** | QB C32 cu Q declarat 25 A (P0). Pa presupus nemarcat pe sursă. 5 circuite de prize pe L1 (dezechilibru). |
| p16 | acceptabilă | Hibrid + baterie + TD-EPS. Caseta EPS e desenată ca derivație din cablul de c.a. al invertorului, nu ca port separat (P2). TE generic „existent”. |
| p08 | acceptabilă cu observații | TD-PV + PI U/f + BD. QI = QG = C63, fără selectivitate. DDR 30 mA la 30 kW. |
| p64 | acceptabilă cu observații | 2 × 25 kW, TD-PV, MCCB 80 A cu PI. C0 nedimensionat, DDR 30 mA. |
| p26 | acceptabilă cu observații | 27 kW injectați direct pe barele TE existente, fără verificare față de Q 3×50. DDR 30 mA. |
| p15 | parțială | ATS corect (interblocaj, 2P comută N). Circuitele prioritare lipsesc. Lista de materiale scrie „3 × 400/230 V” la un GE monofazat. Lipsește avertismentul GE < sarcină. |
| p44 | acceptabilă | ATS 4P, GE 10 kVA. Legarea la pământ a neutrului GE nu e reprezentată. |
| p12 | acceptabilă cu observații | Saună 4P C16 + RCBO, dar fără cablu termorezistent. Un singur circuit de iluminat la „8 lumini”. |
| p56 | acceptabilă cu observații | ACYABY 4×16 + FY 10 PE (bine). Plita 3F nemarcată. Iluminat 1 la „6 lumini”. |
| p22 | corectă (blocată cu întrebare) | VE C40 / 3×10 / RDC-DD 6 mA, DDR dedicat. Întrebarea DLM e pertinentă. |
| p63 | corectă (blocată cu întrebare) | PC 3F + VE mono C40, V40 cu întrebare DLM. „8p 6l” pierdute. |
| p40 | **respinsă** | Plecarea fantomă „Monofazat cu”. Prizele anexei pe C10 cu 3×10 mm². TD fără aparat general la intrare. Cablu exterior CYY-F la 80 m. |
| p52 | absurdă, dar blocată | Coloană 3×2,5 sub C40, iluminat pe 3×16 mm². |
| p66 | greșită, dar blocată | Coloană CYABY 3×70 de 120 m. Pompa la 30 m pe 2,5 mm². |

## Tabel pe fraze

| # | Situație | Verdict | Sev. |
|---|---|---|---|
| 1 | apartament TN-S, Q32 Pa7 | parțial (V46 blocant, opțiunea „altă fază” la mono) | P2 |
| 2 | garsonieră fără rețea | corect (întreabă rețeaua) | – |
| 3 | branșament nou 3x25 Pa15, PC 9 tri | **greșit** (Q 25 → C40) | **P0** |
| 4 | TT mono 40 | corect | P2 |
| 5 | mărire mono → tri + VE 11 | **greșit** (contradicție falsă) | P1 |
| 6 | prosumator Huawei 5 kW mono | parțial (Q/branșament neconsumat, „BMPT”) | P2 |
| 7 | prosumator 8 kW tri | parțial (Q neconsumat) | P2 |
| 8 | prosumator 30 kW, Pa 25 | parțial (PI ok; QI = QG, DDR 30 mA) | P2 |
| 9 | autocorectură tri → mono | parțial (refuz cu întrebare) | P2 |
| 10 | „monofazat 3x32A” | corect | – |
| 11 | mono + PC trifazată | corect | – |
| 12 | saună + jacuzzi | parțial (A, cablu saună) | P1(A) |
| 13 | tablou piscină | parțial (adaugă casa tipică, întreabă rețeaua) | P2 |
| 14 | cascadă TG tri → TE mono | **greșit** (contradicție falsă) | P1 |
| 15 | GE 5,5 kW + ATS, prioritare | parțial | P2 |
| 16 | hibrid mono + EPS | corect | P2 |
| 17 | Deye 12K, backup pe toată casa | parțial (backup marcat neconsumat) | P2 |
| 18 | TN-C, DDR-uri | parțial (3 întrebări redundante) | P2 |
| 19 | coloană Al 2×6 existentă | parțial (V13 cu întrebare; A) | P1(A) |
| 20 | branșament nou 3x25 fără Pa | **greșit** (Q 25 → C32) | **P0** |
| 21 | 3 AC cu puteri diferite | parțial (puteri neconsumate, marcate; A) | P1(A) |
| 22 | VE 7,4 mono pe Q40 | corect (C40, 10 mm², DLM) | P2 |
| 23 | VE 22 kW > Pa | corect (întreabă) | P2 |
| 24 | „6, nu, 7 circuite” | corect | – |
| 25 | baie: boiler, pardoseală, prosop | parțial (A) | P1(A) |
| 26 | prosumator 27 kW exact | parțial (Q neconsumat, DDR 30 mA) | P2 |
| 27 | prosumator 3 kW apartament | corect | – |
| 28 | existent + TE mansardă nou | **greșit** (refuz „fără unitate”) | P1 |
| 29 | typo-uri | **greșit** (TG tri absurd, neblocat) | P1 |
| 30 | 11 kVA mono | parțial (V05 cu întrebare; A) | P1(A) |
| 31 | Q 63 mono | parțial (V05 cu întrebare; A) | P1(A) |
| 32 | PV 10 kW pe mono Pa 6 | corect | – |
| 33 | PC + rezistență de rezervă | parțial (A) | P1(A) |
| 34 | atelier tri + sudură mono | **greșit** (contradicție falsă) | P1 |
| 35 | plită 7400 W | parțial (V46 la 0,13 A, C40/10 mm²; A) | P1(A) |
| 36 | TT RA 30 Ω tri | parțial (A) | P1(A) |
| 37 | TT RA 180 Ω | parțial (V34 corect; A) | P1(A) |
| 38 | mono Q32 cu Pa 20 | corect | – |
| 39 | apartament, coloană 25 m | parțial (coloană în pământ; A) | P1(A) |
| 40 | anexă la 80 m | **greșit** (plecare fantomă) | P1 |
| 41 | priză CEE 32 A tri | **greșit** (→ 1P C16) | P1 |
| 42 | 6 convectoare × 2 kW | parțial (neconsumat; A) | P1(A) |
| 43 | PV existent + baterie AC-coupled | parțial (V53 cu întrebare) | P2 |
| 44 | GE diesel 10 kVA tri + ATS | corect | P2 |
| 45 | doar TE baie | **greșit** (desenat ca branșament) | P1 |
| 46 | întrebare tehnică | parțial | P2 |
| 47 | TN-C-S și TT | corect | – |
| 48 | tri Pa10 fără Q | parțial (Q16 corect, RCCB 16 A; A) | P1(A) |
| 49 | mono Pa9 fără Q | parțial (Q40 justificat; A) | P1(A) |
| 50 | Q 50 mono, PC + VE 3,7 | parțial (VE C20 ok, V05; A) | P1(A) |
| 51 | „fără DDR” | parțial (DDR păstrat; câmpul beneficiar stricat) | P2 |
| 52 | prize C25 pe 2,5 mm² | **greșit** (2,5 aplicat coloanei) | P1 |
| 53 | plită pe 1,5 mm² | parțial (6 mm² corect, neconsumat marcat; A) | P1(A) |
| 54 | prosumator 8 kW mono pe Q50 | parțial (Q50 mono acceptat aici, refuzat la locuință) | P2 |
| 55 | două branșamente | parțial | P2 |
| 56 | ACYABY 4×16 declarat | parțial (plită 3F; A) | P1(A) |
| 57 | „3x25 monofazat” fără „casă” | parțial (I01 în loc de I08) | P2 |
| 58 | hibrid + EPS + GE pe GEN | **greșit** (GE citit ca invertor) | P1 |
| 59 | „AC 3,5 — scuze, 2,5” | parțial (autocorectură ok; V46 la 0,16 A; A) | P1(A) |
| 60 | prosumator + VE + PC | corect (cere separarea) | P2 |
| 61 | vilă cu 2 apartamente | **greșit** (al doilea pierdut) | P1 |
| 62 | electrocasnice | parțial (microunde = cuptor; A) | P1(A) |
| 63 | abrevieri „pdc, ve, 8p 6l” | parțial (8p 6l pierdute) | P1(A) |
| 64 | prosumator 50 kW pensiune | corect | P2 |
| 65 | casă fără rețea | corect | – |
| 66 | pompă de fântână la 120 m | **greșit** (120 m pe coloană) | P1 |

## Comparativ cu r10 (4,5/10)

- **P0: de la 3 la 2**, cu o singură cauză: Q-ul declarat la branșament nou e ignorat. P0-urile din r10 (#56 TG absurd, #66 hibrid ca BESS) nu se mai reproduc pe variante noi.
- **Blocajele tăcute din r10 (P1-A) sunt rezolvate:** V46, V40, V05, V13 și V34 vin acum cu întrebare și remediere.
- **Regresie / problemă nouă:** detectorul I08 mono/tri refuză cazuri legitime (#5, #14, #34) și autocorectura (#9).
- **Rămân:** date declarate pierdute fără marcare („N lumini”, CEE 32 A, al doilea apartament, a doua încadrare a lungimilor). Prosumatorul nu consumă Q.

## Remedieri recomandate, în ordinea priorității

1. `calc/locuinta.py`: la `bransament_nou` cu `In_Q_bransament_A` declarat, Q = cel declarat. Verificarea Ib ≤ 1,13·In se face pe el și, la nevoie, se pune întrebare.
2. I08 mono/tri: contradicția să privească doar **alimentarea**, nu receptoarele sau TE-urile monofazate dintr-o rețea trifazată. Recunoașterea „de la X mono la Y tri” = mărire de putere. Autocorectura „de fapt nu, e …” să fie aplicată și rețelei.
3. „N lumini / N l” = N circuite de iluminat, la fel ca „N iluminat”. Orice număr neconsumat trebuie să ajungă în „Nu am folosit”.
4. Atribuirea lungimilor și secțiunilor: „X e la 120 m” se leagă de receptorul X, nu de coloană. „Prizele pe … 2,5 mm²” se leagă de prize.
5. Prosumator: să consume Q (mono/tri) și să verifice Iac față de Q. DDR-ul invertoarelor peste ~10 kW să fie implicit 100–300 mA, conform fișei.
