# Runda 6 — rol „locuințe” (branșamente, case/apartamente, prosumatori casnici)

**Scor: 6,5/10** (runda 5: 5/10).
Aproape toate P0-urile din runda 5 sunt reparate:
- prosumatorul pe casă nu mai devine branșament sau CEF;
- „22 kVA” nu mai dă PT;
- pompa de căldură scrisă „pompa caldura”, „PC aer-apa” sau „heat pump” e recunoscută;
- contradicția mono/tri dă I08;
- Pa are prioritate față de Pi;
- bateria are port separat cu FB c.c.;
- regula OD „> 27 kW → tablou cu releu anti-insularizare” funcționează corect la prag: 27 kW dă PI integrată, 28, 30, 40 și 50 kW dau PI externă.

Au apărut însă P0-uri noi pe formulări pe care runda 5 nu le acoperea: prescurtări, litere mici, mărire de putere, tablou secundar. Familia „BLOCANT pe Q presupus” din runda 5 (#10) a rămas aproape neatinsă.

## Statistici

| Set | Fraze | Corect | Parțial | Greșit | P0 | P1 | P2 |
|---|---|---|---|---|---|---|---|
| Runda 5 reluată | 58 | 40 (R5: 26) | 18 (R5: 18) | 0 (R5: 14) | 0 | 10 | 8 |
| Fraze noi R6 | 55 | 28 | 12 | 15 | 6 | 18 | 3 |
| **Total** | **113** | **68** | **30** | **15** | **6** | **28** | **11** |

Am verificat 14 planșe randate în PNG, ca la avizare:

| | Planșe |
|---|---|
| Din runda 5 | L01, L27, L30 |
| Noi, branșament și locuință | N04, N06, N29, N34, N38, N50, N51 |
| Noi, prosumator | N18, N20, N22, N45 |

Celelalte SVG/PNG randate (L02, L06, L26, L31, L37, L42, N03, N15, N21, N44) sunt în `teste/r6/locuinte/planse/`.

Fișiere:
- `teste/r6/locuinte/fraze.json` — 113 fraze, cu așteptat / obținut (intrare fizică, motor, blocante, avertismente) / verdict / gravitate;
- `fraze_noi.py` — frazele noi;
- `run.py`, `compact.py`, `verdicte.py`, `randeaza.py`, `shot.js` — scripturile;
- `raw_r5.json`, `raw_noi.json` — rezultatele brute.

Fluxul folosit e același ca în `/api/chat`: `interpreteaza_local` → `constructor.genereaza(intrare_fizica, cartus)` → `validare.valideaza`.

## Runda 5 — ce s-a reparat și ce nu

**Reparat** (R5 → R6):

| Nr. R5 | Ce era greșit | Fraze | Acum |
|---|---|---|---|
| P0-1 | prosumatorul devenea branșament | L26, L28 | prosumator |
| P0-2 | PV fără cuvântul „prosumator” devenea CEF | L30, L31 | prosumator; la L30 planșa mono e corectă: QI 2P C20 + DDR 30 mA tip A, fără PI externă sau TC |
| P0-3 | 22 kVA dădea PT | L37 | locuință |
| P0-4 | pompa de căldură se pierdea | L08, L47, E01, E02 | recunoscută, iar E01 are P = 7 kW |
| P0-5 | contradicția mono/tri trecea | L15 | I08 |
| P0-6 | Pi luat drept P aprobată | L46 | Pa = 8 kW |
| P0-7 | bateria desenată în serie | L27 | BAT pe portul de baterie, cu FB c.c. |
| P1-8 | Pa, Pev și lungimea invertorului se pierdeau | N15, N21 | Pa și Pev ajung la motor; L_inv ajunge când e numită „cablu invertor” |
| P1-9 | Q declarat ignorat | L01 | Q 32 A păstrat |
| P1-10 (parțial) | setul tipic | E03, E04 | „gaz” și negația respectate; plita și cuptorul nu mai intră nenumite |
| P1-11 | VE monofazată ignorată | L42 | VE 1F pe L1 |
| P1-12 | multiplicatori pierduți | L10, L35, L40, E05 | 2 boilere, 3 AC, 3 prize, 5 prize |
| P1-13 | mesaj V46 incoerent | L04 | Q din P cerută |
| P1-14 (parțial) | RCCB BMPT 300 mA tip AC | — | trifazat: acum tip A, S |

**Nereparat:**
- **R5 #10.** BLOCANT V46 pe un Q presupus (nedeclarat) la case banale: L07 (4 kW), L09 (garsonieră 3 kW), L39, N36 (garsonieră 2 kW), N07, N41, N54. Q presupus ar trebui să dea AVERTISMENT + întrebare, nu BLOCANT.
- **cosφ 0,9 la branșament:**
  - 7 kW mono → Q 40 A (L18);
  - 25 kW tri → Q 50 A (L17);
  - BMPM 32 A + 7 kW → BLOCANT V04 (N11);
  - 9 kW mono → peste BMPM 40 A (L10, L44, N52).

  La locuință se folosește cosφ 0,95, la branșament 0,9 — inconsecvent.
- **Mono.** BMPM cu RCBO 300 mA instantaneu (tip A, la branșament chiar AC) neselectiv cu DDR-urile de 30 mA. Aplicația își semnalează singură V43 la fiecare prosumator mono (L26, L29, L30, N14, N23, N55).
- **Prosumator: coloana dintre BMPT și TE se pierde.** Apare pe planșă ca „existent” / „conform releveu” la L27, L32, L33, N18 și N20.
- **P2 rămase:**
  - „întrerupător general 32A” e luat drept Q (L12);
  - presupunerile vorbesc de BMPT când rețeaua e nedeclarată (L05);
  - etichetele PE/SB/FB/BAT/AR/EMS apar dublate deasupra casetelor (L27, N20, N45).

## P0 — greșit tehnic / periculos (fraze noi)

1. **N06 „casa veche, tt, priza pamant 40 ohm, mono, 5 kw…”**
   - Obținut: „tt” cu litere mici nu e recunoscut. Planșa e TN-C-S: C1 L+PEN, separare PEN în BMPM, Rp ≤ 4 Ω. RA = 40 Ω e reținut în intrare, dar ignorat. (Cu „TT” scris mare iese corect.)
   - Corect: TT, ca la L06/N38.
   - Remediere: regexul pentru TT/TN fără sensibilitate la majuscule. Plus regula: RA declarat + schemă TN → I08 (contradicție).
2. **N51 „marire putere bmpm 7kw -> bmpt 15 kw tri, coloana noua 4x10 Cu 25m”**
   - Obținut: branșament BMPM-40 monofazat 7 kW, coloană CYABY 3×6. Planșa e exact situația existentă, nu cea proiectată.
   - Corect: BMPT 15 kW tri, coloană 4×10 Cu.
   - Remediere: tipar „de la X la Y” / „X → Y” / „marire … la Y”. Ținta (Y și rețeaua ei) devine proiectul, sursa e informativă.
3. **N09 „marire putere de la 7 kw mono la 15 kw tri…”** — aceeași cauză ca N51. Aici aplicația refuză cu I08 (contradicție) și ia P = 7 kW. Nu e periculos, dar e inutilizabil (clasat P1).
4. **N29 „bransament monofazat existent 7 kw, pompa de caldura 9 kw trifazata”**
   - Obținut: contradicția nu e semnalată (I08 merge doar cu „casă”), iar PC 9 kW tri dispare.
   - Planșa: BMPM-40 cu coloană implicită ACYABY 3×25 Al de 50 m.
5. **N04 „casa P+1 tri 20 kw, pc 10kw, ac 3 buc x 1.2 kw, wallbox 11kw”**
   - Obținut: „pc 10kw” se pierde în tăcere, deci pompa de 10 kW lipsește din tablou și din bilanț. („pdc” merge, „pc” nu.)
   - Planșa A1 e comprimată în jumătatea de sus, cu text ilizibil.
6. **N08 / N50 — atelier în curte.**
   - N08: strungul 4 kW și compresorul 3 kW de la 40 m dispar în tăcere.
   - N50 („tablou secundar atelier … cablu 50m din TG casa”): schemă de casă cu BMPT, contor OD și set tipic (living, baie, boiler, centrală). Polizorul și compresorul se pierd, iar alimentarea din TG nu e modelată.
   - Remediere: „atelier/anexă/garaj/tablou secundar” → circuit 3F cu TD secundar (L, receptoare), respectiv tip `tablou` cu origine `tg_existent`.

## P1 — important

7. **Q presupus sub Ib** (L13, N42): la 11 kW tri, Ib = 16,71 A, dar Q presupus = 16 A, iar mesajul spune „calibrul standard ≥ Ib”. Rezultă BLOCANT.
8. **L37: 22 kVA e înțeles în text (Ib 31,8 A), dar nu ajunge la motor.** Q e presupus 16 A din bilanț.
9. **BESS fără cuvântul „hibrid” e presupusă cuplată în c.a.**, cu PCS separat de 0,5C, și se adună la invertor. La casă, „prosumator X kW cu baterie Y kWh” înseamnă aproape mereu invertor hibrid.
   - N44 (6 kW mono + 5 kWh): V53 BLOCANT.
   - N18 (20 kW + 20 kWh): Σ 30 kW > 27 kW, dar PI e integrată; Σ 30 kW > Pa 20 kW fără EMS.
   - N22 (50 kW + 30 kWh): QG 125 A pe un branșament de 50 kW, fără limitare.
   - Remediere: implicit cuplaj c.c. la prosumator. Dacă Σ(PV + PCS) > Pa sau Pev → avertisment + EMS. Pragul PI trebuie aplicat aceleiași puteri care se compară cu Pa.
10. **Prescurtări și formatări nerecunoscute:**
    - „ap 2 cam” → I01 (N01);
    - „Q40A” lipit → Q = 0 → refuz I06 (N43);
    - „AC 3x2.5kw” → un singur AC (N39);
    - „trif” → nerecunoscut (N53, aici cel puțin întreabă);
    - „inc in pardoseala” pierdut (N53);
    - „pompa piscina” pierdută (N34).
11. **Ambiguitate rezolvată în tăcere:**
    - „7 kW sau 10 kW” → 7 kW (N31);
    - „TT dar și TN-C-S” → TT, cu RA presupus 4 Ω (N30).

    Ambele trebuie să dea întrebare.
12. **„apt bloc vechi … schimbare tablou”** (N37) → tip `tablou` fără plecări → BLOCANT. Coloana Al 2,5 mm² existentă nu e semnalată (I7: Al numai la secțiuni mari).
13. **Repartizarea pe faze făcută de aplicație dă V47** (dezechilibru 38–60 %; L45, N07, N38, N41, N50): o grupă DDR de 5 circuite pusă întreagă pe L1. Din cauza asta apare BLOCANT V46 la N07/N41.
14. **VE: DDR 30 mA tip A fără RDC-DD 6 mA c.c. pe planșă** (N34, L42). Modelul are alternativa „tip A-EV + RDC-DD” (HD 60364-7-722), dar ea nu ajunge în etichetă sau în listă.

## P2

- N14: „fara baterie” → aplicația întreabă capacitatea BESS.
- N47: „nu știu mono sau tri” → rețea pusă mono, apoi refuz I09 (în fapt întreabă).
- N32: Q 50 A mono e semnalat, dar planșa arată Q C40 „presupus”.
- La prosumator, cutia „CÂMP PV” are subtitlul „invertor hibrid 10 kW” (L27, L30).
- N20: DDR de 30 mA pe un invertor de 30 kW, risc de declanșări intempestive; uzual 100–300 mA tip A/B, conform fișei.
- PI externă desenată fără intrare de măsură de tensiune (N20, N22).
- L30: SPD F3 cu „protecție amonte 63 A gG” în listă, deși QI e C20.
- Cutia „RED 0,4 kV” are un subtitlu ilizibil (N06, N38, N50). În listă, coloana „Simbol” are text minuscul (N34, poz. 19–20).

## Ce arată planșele (judecate ca la avizare)

- **Tablourile de locuință** (L01, N38, N34) sunt de nivel avizabil:
  - SF → contor → QB/RCCB → C2 → QG separator;
  - SPD T2 cu F2 de rezervă, BPE / PS / PPL;
  - grupe DDR ≤ 5 circuite, RCBO pe baie, bucătărie și exterior;
  - secțiuni și calibre corecte (1,5 mm²/B10, 2,5 mm²/C16, 5×6/C32 VE 22 kW);
  - la TT tri: 3L+N, RCCB 300 mA S, RA·IΔn = 30 V.
- **Prosumatorii** (L27, L30, N20, N45) sunt corecți ca topologie:
  - S c.c., SPD c.c./c.a., QI + DDR tip A;
  - TD-PV cu PI U/f pe bobina BD a QG peste 27 kW;
  - injecție zero cu TC 50/5 + analizor + EMS.
- **Planșele greșite** (N06, N29, N50, N51) arată profesionist, deci un proiectant grăbit le-ar putea semna. Asta face P0-urile de interpretare mai periculoase decât cele de calcul.
