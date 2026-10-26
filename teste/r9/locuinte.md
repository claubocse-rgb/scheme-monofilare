# Runda 9 — locuințe, branșamente, prosumatori casnici (testare ca proiectant ANRE gr. II/III)

**Notă: 6 / 10** (r8: 5). 69 de fraze complet noi (`locuinte/fraze.json`, cu așteptat / obținut / verdict), doar reguli locale (fără cheie API), fluxul din `/api/chat`: `interpreteaza_local` → `constructor.genereaza` → `validare` → PNG (`locuinte/fNN.png`, 59 de planșe). Rezultate brute: `locuinte/rezultate.json`; scripturi: `fraze_src.py`, `run9.py`, `compact.py`, `verdicte.py`.

Stiluri: emailuri de client (ro/en), WhatsApp, tabele Excel (tab, „;”, „|”, CSV, markdown), extrase ATR / certificat de racordare, typo-uri, autocorecturi, MAJUSCULE, cratimă Unicode, încercări de păcălire.

**Pe scurt:** cele 4 P0 din r8 nu mai apar (puterea receptorului nu mai devine Pa din tabele, TD monofazat nu mai primește 3×240, Ik în kA nu mai devine Q, RCCB tip A la branșament). Engleza merge. Rămân P1-uri de citire: tablourile secundare complexe, mărirea mono→tri formulată ca „vrem să trecem pe…”, P termică vs P electrică, GE fără „kVA/ATS”, hibrid + EPS, apartamentul scris „ap. la bloc”, lungimea unui circuit pusă pe coloană.

## Statistici

| verdict | nr. | | severitate | nr. |
|---|---|---|---|---|
| corect | 38 (55 %) | | P0 | **0** |
| parțial | 20 (29 %) | | P1 | 21 |
| greșit | 11 (16 %) | | P2 | 26 |

| categorie | rezultat |
|---|---|
| emailuri (8) | 4 corecte; TE etaj (#3) și mărirea (#4) eșuează |
| WhatsApp (15) | 10 corecte; „12 și 12 kW” → 2×6 (#21), „am doar 11 kw tri” pierdut (#14) |
| tabele Excel/CSV/markdown (6) | **5 / 6 corecte** (r8: 0 / 5) — Pa nu mai e luată din receptor |
| extrase ATR (5) | 4 / 5 (r8: 2 / 5); Pi vs Pa confundate (#32) |
| engleză (3) | 3 / 3 (r8: 0 / 2) |
| prag 27 kW (#20, #21, #22, #33) | corect la 29, 3×10, 2×17,5; #21 greșit din citirea puterilor |
| contradicții explicite (#7, #57–59, #48) | 100 % întrebate |
| tablouri secundare (#3, #17, #35, #36, #37) | 1 / 5 utilizabil (TD garaj); TG + 2 TD și TD foișor blocate |
| GE / backup / BESS (#23, #50–53) | 1 / 5 corect; GE 5 kW manual și hibrid + EPS regresează |

## P0
Niciunul în această rundă. Cel mai aproape: #21 (Σ invertoare înjumătățită pe planșă, dar cu întrebare) și #61 (Q 100 A pe 15 kW desenat fără obiecție — supradimensionat, nu periculos).

## P1 (grupate)
- **Tablouri secundare** (clasa r8, parțial reparată):
  - #17 TD garaj mono 3×4 corect (P0 r8 reparat), dar prizele garajului pierdute tăcut;
  - #3 „TE-etaj alimentat cu CYY-F 5x6 de 18 m” → TE necreat, circuitele contopite în TG cu nume dublate, 5×6 18 m pus pe coloană → BLOCANT;
  - #35 TG + TD mansardă + TD atelier → tip „tablou” cu Q1 16 A (din „prize 400V 16A”), blocat;
  - #36 TD foișor → tip tablou cu P = Pa casei, „3x2.5” tratat ca **Al** (V13 blocant).
- **Cifra greșită devine putere / se pierde:**
  - #21 „12 și 12 kw” → 2 × 6;
  - #32 Pi 18 luat în locul Pa 14 → blocant;
  - #14 „am doar 11 kw tri tt” → tri + 11 kW pierdute;
  - #2 „contract monofazat de 6 kW” neconsumat;
  - #8 „casă tri 25 kW” neconsumat;
  - #60 „15 sau 25” → 15 folosit fără întrebare.
- **Lungime atribuită coloanei:** #42 „VE la 30 m” și #44 „60 m” → coloana branșamentului (la #44 rezultă CYABY 3×35 60 m la un apartament).
- **VE supradimensionat față de branșament:** #42, #44, #69 — VE 3,7–7,4 kW pe C40 / 3×10 sub QB C25–C32; apare doar V40, fără întrebare sau propunere de management de sarcină. (r8 #42 nereparat.)
- **Apartament nerecunoscut** în „ap. la bloc” (#44) → set de casă (iluminat/prize exterioare, centrală); „ap.” simplu (#29) merge.
- **Mărire de putere** formulată „branșament mono 4 kW, vrem să trecem pe tri 15 kW” (#4) → Pa 4 kW + întrebare mono/tri. Forma „mărire de la 7 mono la 20 tri” (#55) e corectă.
- **P termică ≠ P electrică** (#38): „16 kW termic (consum max 5 kW electric)” → 16 kW electric, întrebare de mărire absurdă (r8 #40, nereparat).
- **GE / backup:**
  - #50 GE 5 kW manual → schema ge_ats cu „Casa” și „Generator” drept consumatori (regresie la clasa din r7);
  - #23 ATS desenat bine, dar pe toată bara, nu pe circuitele de bază cerute;
  - #51 hibrid Deye + EPS → CEF, revine întrebarea inutilă „1×12 sau total 16?”;
  - #53 „UPS/EPS, fără panouri” → prosumator;
  - #52 invertorul existent desenat și listat ca nou.
- **Saună dublată** pe planșă (#8): două circuite 4P C16, la 15 m și la 25 m.
- **Q impus de client** (#61): Q 100 A pe Pa 15 kW acceptat fără obiecție; mesajul V56 e defect („Ib = 22,79 A > 80 A”).

## Planșe judecate ca la avizare (15)

| planșă | ce e bine | observații |
|---|---|---|
| f01 casă tri 16 kW | 10 circuite, plită 3F C16 5×2,5, 2 AC separate, BPE/PPL, SPD + F2; **QB 6 kA cu back-up SF gG 40 A declarat** (obs. r8 rezolvată) | „Paleu” în textul de înțelegere; AC în grup DDR cu prizele |
| f08 TT saună + jacuzzi | TT corect: fără PEN, PE local, RA·IΔn = 3,6 V | **P1**: Saună ×2 (Q7 + Q8); jacuzzi sub DDR comun cu prizele; TE fără Pa |
| f17 TD garaj | **TD mono 3×4 21 m, C16** (P0 r8 reparat); DDR 30 mA pe circuitele din TD | prizele garajului lipsesc; TD fără separator de intrare; Q11.x 2P pe circuite 1P+N |
| f22 3×10 kW | TD-PV, PI U/f pe BD QG, SPD c.c./c.a., QG C50 la 47,6 A | C0 spre TG „conform releveu” fără secțiune; Pa 32 nefigurată |
| f23 casă + GE ATS | ramura GE (Q-GE C16, K·I/K·II interblocate 4P) desenată cu casa (r8: casa dispărea) | toată bara pe ATS, nu doar circuitele de bază; ATS după QG, deci QG nu separă și GE |
| f26 tabel cu lungimi TT | L din tabel folosite (22/30/40 m), RA 7 Ω, RA·IΔn 2,1 V, RCCB tip A S | „Pompă piscină” a devenit „Pompă” |
| f31 prosumator mono TT (ATR) | TT în note, QI C40 3×6, DDR 30 mA | nota „DDR pe fiecare circuit” contrazisă de Q2/Q5 fără DDR (r8, nereparat); „SB” suprapus pe bara c.c. |
| f33 2×17,5 kW | PI externă, Q1/Q2 C32 5×4, QG C63 | „SB1/SB2” suprapuse pe bara c.c. (r8, nereparat) |
| f42 VE 7,4 1F pe tri 16 | RDC-DD 6 mA notat, DDR dedicat | **P1**: VE C40 sub QB C25; coloana 30 m (era lungimea VE); poz. 17 „Simbol” ilizibil |
| f44 apartament + VE | — | **P1**: set de casă pe apartament; coloană CYABY 3×35 60 m; VE 7,4 kW C40 în loc de 3,7 kW / 60 m |
| f45 piscină | PC piscină 5 kW C25 3×4, pompă filtrare, circuit SELV 12/24 V | transformatorul SELV nedesenat; poz. 13 „Simbol” ilizibil |
| f52 BESS AC-coupled | ramura BESS (BAT, SB-B, PCS, DDR-B) corectă | invertorul **existent** 8 kW desenat și listat ca nou; BESS protejat de aparat numit „QB” (confuzie cu Q branșament) |
| f56 branșament 50 kW | BMPTd-100, Q C100 + DPST, **RCCB tip A** (r8: AC), ACYABY 4×70 + FY 25 | contor direct la 80 A fără mențiunea V56 pe planșă |
| f61 Q 100 A forțat | — | **P1**: BMPTd-100, 4×50, QB C100 pe Pa 15 kW acceptat; avertismentul V56 are textul defect |
| f69 ap. mono 6 + VE 3,7 | 2 AC, plită C32 3×6, RDC-DD | **P1**: VE 16 A pe C40 / 3×10 > QB C32; Pi 19,2 kW pe Pa 6 fără mențiunea de limitare |

Observații transversale de desen (P2):
- coloana „Simbol” din listă e ilizibilă când se grupează circuite cu nume lungi (f42, f44, f45, f61);
- „SB” se suprapune pe bara c.c. la planșele prosumator (în f22 nu se suprapune);
- nota TT „DDR pe fiecare circuit” e în conflict cu circuitele generice fără DDR.

## Față de r8

**Reparat:**
- toate cele 4 P0 (receptor → Pa din tabele: #24, #25, #26, #28, #29; TD mono 3×240: #17; Ik3 kA ≠ Q: #30);
- engleza (#5, #40);
- „18k” / „8k” (#10);
- ATR prosumator ≠ CEF (#31);
- mărirea „de la X mono la Y tri” (#55);
- RCCB tip A la branșament (#56);
- back-up-ul MCB 6 kA declarat;
- GE + ATS desenat cu casa (#23);
- TN-C semnalat (#48).

**Rămas:**
- tablourile secundare complexe (TG + TE / 2 TD);
- VE pe C40 indiferent de putere;
- P termică vs electrică;
- lungimea circuitului pusă pe coloană;
- „ap. la bloc”;
- „SB” suprapus;
- nota DDR în TT.

**Nou / regresie:**
- GE fără „kVA/ATS” devine consumator (#50);
- hibrid + EPS → CEF cu întrebarea „1×N sau total” (#51);
- „12 și 12 kW” → 2×6 (#21);
- Pi citit ca Pa (#32);
- „3x2.5” → Al (#36);
- Q 100 A acceptat (#61);
- cratima Unicode și „ton-c-s” → schema de pământ presupusă tacit (#65, #68).

## Tabel complet

| # | cat. | frază | așteptat | obținut | verdict | sev. |
|---|---|---|---|---|---|---|
| 1 | email | `Bună ziua,⏎⏎Vă scriu pentru casa din Paleu. Branșamentul e trifazat, putere aprobată 16 kW conform avizului, schema TN-C-S. În casă avem: pl…` | tri 16 kW TN-C-S; plită 3F, cuptor, MSV, 2 AC, boiler; fără întrebări | tri 16 kW, 10 circuite (plită 3F, cuptor, MSV, 2 AC, boiler), QB C25 (Ib 24,3 A); „Paleu” apare în lista „dedicate” | **corect** | P2 |
| 2 | email | `Salut! Suntem o familie tânără și ne-am mutat într-un apartament de 3 camere, bloc din 2008. Avem contract monofazat de 6 kW. Vrem tablou no…` | mono 6 kW apartament; schema de pământ necunoscută → întrebare sau presupunere TN-C-S declarată; uscător, plită, boiler, AC | „contract monofazat de 6 kW” neconsumat → Pa presupusă 6,8 kW din bilanț; nesiguranța TN-S/TN-C-S nu e întrebată (TN-C-S tacit) | **parțial** | P1 |
| 3 | email | `Stimate domn inginer, atașat aveți lista. Casă P+1, rețea trifazată, Pa = 22 kW, TN-C-S. Parter: bucătărie (plită 3F 8 kW), centrală gaz, 6 …` | tri 22 kW; TG parter + TE etaj 5×6 18 m cu 4 prize, 2 ilum, 2 AC; cantitățile respectate | TE-etaj necreat (întrebat); circuitele etajului contopite în TG cu nume dublate (Prize 1…4 ×2, Iluminat 1–2 ×2); 5×6 18 m pus pe coloană → BLOCANT V02/V03 | **greșit** | P1 |
| 4 | email | `Buna ziua, avem o casa veche in Tileagd, bransament monofazat 4 kW, vrem sa trecem pe trifazat 15 kW pentru o pompa de caldura aer-apa de 9 …` | mărire mono 4 → tri 15 kW (nu contradicție); PC 9 kW 3F; cuptor | mărire mono 4 → tri 15: Pa = 4 kW (vechea), întreabă „mono sau tri?”; „trifazat 15 kW” la neconsumat (clasa r8 #6 nereparată pe această formulare) | **greșit** | P1 |
| 5 | email | `Hello,⏎I'm renovating a flat in Cluj. Single-phase, 7 kW contracted, TN-C-S. I need circuits for: induction hob 3.7 kW, oven 2.5 kW, washing…` | en: apartament mono 7 kW TN-C-S; plită, cuptor, MSP, MSV, 2 AC | engleză: apartament mono 7 kW TN-C-S, plită, cuptor, MSP, MSV, 2 AC (r8: tip nedeterminat) | **corect** | - |
| 6 | email | `Bună seara. Pentru avizul de prosumator: avem casă cu branșament trifazat, putere aprobată consum 11 kW, TN-C-S. Montăm invertor Huawei SUN2…` | prosumator tri 10 kW, PA 11 kW, PI integrată; 10KTL = 10 kW; L 8 m | prosumator Huawei 10KTL = 10 kW, Pa 11, PI integrată, L 8 m, 10,01 kWp | **corect** | - |
| 7 | email | `Buna ziua. In ATR scrie: putere aprobata 9 kW monofazat. Noi vrem totusi sa montam o statie de incarcare 11 kW trifazata pentru masina noua.…` | contradicție VE 11 kW 3F pe mono 9 kW → întrebare/propunere mărire; nu desenează tăcut | VE 11 kW 3F pe mono 9 → întreabă dacă e trifazat; putea propune și varianta VE 7,4 kW 1F / mărire | **corect** | P2 |
| 8 | email | `Salutare, vă scriu de la service-ul nostru. Clientul are casă tri 25 kW TT (RA măsurat 12 ohmi), vrea saună 9 kW 400V, jacuzzi exterior 3 kW…` | tri 25 kW TT RA 12 Ω; saună 9 kW 3F (L 25 m), jacuzzi, pompă piscină cu DDR 30 mA | saună desenată de DOUĂ ori (15 m și 25 m); „casă tri 25 kW” neconsumat → Pa presupusă 22,4; jacuzzi sub DDR comun cu prizele | **parțial** | P1 |
| 9 | whatsapp | `salut sefu, ap 2 cam, 1f, 5kw, tn-c-s, plita 3.5 si boiler` | apartament mono 5 kW; plită 3,5, boiler | apartament mono 5 kW; plită 3,5 kW (15 A) pe C32/3×6 > QB C25 (V40) — C20/3×4 ajungea | **corect** | P2 |
| 10 | whatsapp | `casa tri 18k tncs pc 8k` | tri 18 kW; PC 8 kW 3F; „18k”/„8k” = kW | „18k” / „8k” înțelese (r8: pierdute) | **corect** | - |
| 11 | whatsapp | `Monofazic 32A, casa, tt cu 2 tarusi` | mono 32 A ≈ 7,4 kW TT; casă | mono Q 32 A TT, RA 4 Ω presupus semnalat; Pa din bilanț 5,4 în loc de 32 A·230 V ≈ 7,4 kW | **corect** | P2 |
| 12 | whatsapp | `tri 3x32A casa tncs` | tri 3×32 A ≈ 22 kW; casă | tri 3×32 A → Q 32 A, dar Pa presupusă 5,4 kW din bilanț (≈ 21 kW din Q) | **parțial** | P2 |
| 13 | whatsapp | `boiler 2kw ac 3kw plita 7kw. casa. tn-c-s. puterea aprobata 12kw trifazat` | tri 12 kW; Pa = 12 (nu 2/3/7); boiler, AC, plită | Pa = 12 kW (nu 2/3/7), QB C20 | **corect** | - |
| 14 | whatsapp | `vreau statie ve 22kw dar am doar 11 kw tri tt` | VE 22 kW > Pa 11 kW → întrebare/limitare 11 kW | „am doar 11 kw tri tt” → tri și 11 kW pierdute, întreabă rețeaua; VE 22 > Pa 11 neabordat | **parțial** | P1 |
| 15 | whatsapp | `nu mai stiu daca e mono sau tri, cred ca tri, casa 10kw` | rețea incertă → întrebare (nu presupune tri) | „cred că tri” → întreabă (bine) dar planșa provizorie e deja trifazată | **parțial** | P2 |
| 16 | whatsapp | `AC 12000 BTU x3, apartament mono 6kw tncs` | mono 6 kW; 3 circuite AC (~1,1 kW el. fiecare) | 3 circuite AC din „12000 BTU x3”; curent tipic 12,1 A (≈ 2,6 kW) supraestimat (≈ 1,1 kW el.) | **corect** | P2 |
| 17 | whatsapp | `casa monofazata 8 kw, tncs, + garaj cu tablou separat (prize, iluminat, usa garaj), cablu 3x4 20m` | mono 8 kW; TD garaj mono 3×4 20 m cu prize, ilum, ușă — dimensionare corectă | TD Garaj mono 3×4 20 m, C16 — P0 r8 (3×240) REPARAT; dar „prize” din garaj pierdute tăcut | **parțial** | P1 |
| 18 | whatsapp | `salut! panouri 8 kw tri, pa 10, casa, tt ra 9 ohm` | prosumator tri 8 kW, PA 10 kW TT RA 9 Ω | prosumator tri 8 kW, Pa 10, TT RA 9 | **corect** | - |
| 19 | whatsapp | `pv 3.6 kw mono pe ap la bloc?? pa 5` | prosumator mono 3,6 kW la apartament, PA 5 | prosumator mono 3,6 kW pe apartament, V43 selectivitate DDR semnalată | **corect** | - |
| 20 | whatsapp | `29kw invertor tri, pa 30 tncs casa` | 29 > 27 → releu PI extern în TD | 29 kW → TD-PV cu PI externă pe BD QG; DDR 30 mA pe 29 kW | **corect** | P2 |
| 21 | whatsapp | `am 2 invertoare: 12 si 12 kw, tri, pa 25 kw` | Σ 24 ≤ 27 → PI integrată; fără releu extern | „2 invertoare: 12 și 12 kW” → 2 × 6 kW (Σ 12), întrebare cu varianta greșită; Σ real 24 kW | **greșit** | P1 |
| 22 | whatsapp | `3 invertoare de 10kw pe casa tri pa 32 tncs` | Σ 30 > 27 → releu PI extern | 3 × 10 = 30 > 27 → PI externă, QG C50 | **corect** | - |
| 23 | whatsapp | `casa tri 20 kw tncs, generator 10 kva cu ats pe circuitele de baza (centrala, frigider, iluminat)` | casă 20 kW + GE 10 kVA cu ATS pe circuite rezervate; casa nu dispare | GE 10 kVA + ATS desenat corect cu casa (progres), dar comutat pe TOATĂ bara în loc de circuitele de bază cerute; GE 10 kVA pe Pa 20 fără avertisment | **parțial** | P1 |
| 24 | excel | `Consumator⇥P (kW)⇥Faze⏎Pompa caldura⇥9⇥3⏎Boiler⇥2⇥1⏎Plita⇥7,5⇥3⏎AC dormitor⇥1,2⇥1⏎Casa trifazata, Pa 20 kW, TN-C-S` | tri 20 kW; PC 9 3F, boiler, plită 7,5 3F, AC; Pa = 20 (nu 9) | tabel cu tab: Pa = 20 (P0 r8 #17 reparat), faze din tabel respectate | **corect** | - |
| 25 | excel | `Nr;Circuit;Putere⏎1;Iluminat;0,8 kW⏎2;Prize living;2 kW⏎3;Plita;6 kW⏎4;Cuptor;3 kW⏎Retea;monofazat;9 kW` | mono 9 kW; 4 circuite; Pa = 9 (nu 0,8) | CSV „;”: Pa 9 (nu 0,8), plită 6 kW C32 3×6; Q 40 A < Ib 41,2 A (doar avertisment) | **corect** | P2 |
| 26 | excel | `Circuit \| Putere \| Lungime⏎Sauna \| 8 kW 3F \| 22 m⏎Piscina pompa \| 1,5 kW \| 30 m⏎Iluminat gradina \| 0,4 kW \| 40 m⏎---⏎bransament: 3F,…` | tri 30 kW TT RA 7 Ω; saună 8 kW 3F 22 m; pompă 30 m; ilum. grădină 40 m | tabel „|” cu lungimi: saună 22 m, pompă 30 m, ilum. grădină 40 m; TT RA 7 | **corect** | - |
| 27 | excel | `tip,cantitate,putere unitara⏎priza,8,⏎iluminat,4,⏎AC,2,2.5kW⏎boiler,1,2kW⏎locuinta mono 7kW tncs` | mono 7 kW; 8 prize / 4 ilum (grupate în circuite rezonabile), 2 AC, boiler; fără plită fantomă | „priza,8 / iluminat,4” → 8 + 4 circuite (cantitatea de aparate citită ca nr. de circuite); fără plită fantomă | **parțial** | P2 |
| 28 | excel | `Denumire⇥P⏎Incarcator VE⇥11 kW⏎Pompa de caldura⇥6 kW⏎Casa⇥3F 16 kW TN-C-S` | tri 16 kW; VE 11 kW 3F, PC 6 kW; Pa 16 | VE 11 kW 3F + PC 6 kW pe 16 kW; avertisment Pc > Pa; nicio sugestie de management de sarcină | **corect** | P2 |
| 29 | excel | `\| Receptor \| kW \|⏎\|---\|---\|⏎\| Plita \| 7 \|⏎\| Cuptor \| 3,5 \|⏎\| Boiler \| 2 \|⏎\| AC \| 2,5 \|⏎⏎ap. trifazat 11 kW, tn-c-s` | apartament tri 11 kW; tabel markdown; Pa = 11 | tabel markdown, „ap.” recunoscut ca apartament, Pa 11 | **corect** | - |
| 30 | atr | `AVIZ TEHNIC DE RACORDARE nr. 1102/2026⏎Utilizator: casa de locuit⏎Putere aprobata: 13 kW⏎Tensiune: 0,4 kV, trifazat⏎Grup de masura: BMPT mon…` | tri 13 kW, Ik 5 kA (nu Q 5000 A), BMPT la limită | ATR: Ik3 5 kA folosit corect (r8: Q 4200 A), Pa 13, QB C20 | **corect** | - |
| 31 | atr | `ATR – loc de consum si producere. Pa consum: 8 kW; Pa producere: 8 kW; monofazat 230V; schema TT, Rp <= 4 ohm; invertor 6 kW` | prosumator mono 6 kW, PA 8, TT RA ≤ 4 Ω; fără întrebări (nu CEF) | ATR prosumator mono 6 kW TT (r8: CEF + întrebare), V71 > 3,68 kW | **corect** | P2 |
| 32 | atr | `Extras ATR: Pi = 18 kW, Pa = 14 kW, racord trifazat subteran, BMPTd, protectie la bransament 3x25A, TN-C-S, coloana Cu 5x10 35m` | tri Pa 14 kW; Q 3×25 A declarat respectat; coloană 5×10 35 m | Pi 18 kW luat drept putere de calcul, Pa 14 kW neconsumat → Ib 28,9 > Q 25 A, BLOCANT | **greșit** | P1 |
| 33 | atr | `ATR: Puterea maxima simultan absorbita = 40 kW; Puterea maxima simultan evacuata = 35 kW; 0,4 kV; TN-C-S. Instalatie de producere: 2 inverto…` | prosumator tri 35 kW > 27 → TD cu releu PI; PA 40 | ATR 2 × 17,5 = 35 kW → PI externă; Pa absorbită 40 nefigurată | **corect** | P2 |
| 34 | atr | `Certificat de racordare: monofazat, Pa 6,9 kW, intrerupator bransament 1x32A, TN-C-S, locuinta` | mono 6,9 kW; Q 32 A declarat | certificat de racordare mono 6,9 kW, Q 32 A, RCBO 300 mA S tip A | **corect** | - |
| 35 | tablou | `casa tri 24 kw tncs. TG la parter. TD mansarda: 3 prize, 2 iluminat, 1 AC, alimentat 5x4 15m. TD anexa (atelier): prize 400V 16A, flex 2,2 k…` | TG + 2 TD (mansardă 5×4 15 m, atelier 5×6 40 m) cu circuitele lor | TG + 2 TD → tip „tablou” cu Q1 16 A (din „prize 400V 16A”), TD atelier și „flex 2,2 kW” pierdute, BLOCANT | **greșit** | P1 |
| 36 | tablou | `tablou secundar monofazat in foisor: priza gratar 2kw, iluminat, priza exterioara; din TG casa mono 7kw tncs, cablu 3x2.5 25m` | TD foișor mono 3×2,5 25 m — de semnalat că 2 kW + prize pe 3×2,5 e ok (C16); nu 3×240 | TD foișor → tip tablou cu P = 7 kW (Pa casei), „3x2.5” citit ca Al → BLOCANT V13; iluminat și priză ext. neconsumate | **greșit** | P1 |
| 37 | tablou | `apartament mono 6 kw, tablou TE in hol + tablou mic in baie pt incalzire pardoseala 2kw` | TE + TD baie (sau circuit dedicat); mono 6 kW | tabloul din baie întrebat; încălzire 2 kW circuit separat | **corect** | P2 |
| 38 | pc | `pompa de caldura 16 kW termic (consum max 5 kW electric) trifazata, casa tri 15 kW tt` | PC cu P electrică 5 kW 3F (nu 16) | „16 kW termic (consum max 5 kW electric)” → PC 16 kW electric, întrebare de mărire absurdă (r8 #40 nereparat) | **parțial** | P1 |
| 39 | pc | `PC aer-apa monobloc 8kw cu rezistenta de backup 6kw, casa mono 10 kw tncs` | PC + rezistență backup 6 kW: Σ 14 > 10 sau circuit separat; mono → avertisment | întreabă corect mono 10 kW > 40 A; nu pune la îndoială PC 8 kW mono (36,6 A pe C40) + rezistență 6 kW = 14 > 10 | **parțial** | P2 |
| 40 | pc | `heat pump 3-phase 10kW electrical, house 3-phase 20kW, TN-C-S, plus EV charger 11kW` | en: tri 20 kW; PC 10 kW 3F, VE 11 kW 3F | engleză: tri 20 kW, PC 10 kW 3F, VE 11 kW 3F; Σ 21 > 20 doar avertisment | **corect** | P2 |
| 41 | ac | `casa mono 9kw tncs, 4 aparate AC de 1 kW fiecare` | mono 9 kW; 4 circuite AC 1 kW | 4 AC × 1 kW, câte un circuit | **corect** | - |
| 42 | ve | `wallbox 7,4 kW monofazat la casa tri 16 kw tn-c-s, la 30 m de tablou` | tri 16 kW; VE 7,4 kW 1F (32 A, C40, 3×6/3×10 30 m), DDR A-EV/B | VE 7,4 kW 1F: „30 m de tablou” pus pe coloană (VE rămâne 25 m implicit); VE C40 sub QB C25 — doar V40 | **parțial** | P1 |
| 43 | ve | `statie incarcare 22kw la casa tri 30kw tncs` | tri 30 kW; VE 22 kW 3F (32 A) | VE 22 kW 3F C32 5×6, QB C50 | **corect** | - |
| 44 | ve | `ap. la bloc mono 7kw, vreau priza pt masina electrica in parcarea subterana, 3,7kw, 60 m` | apartament mono 7 kW; VE 3,7 kW 16 A C20 60 m (căderea de tensiune); set de apartament | „ap. la bloc” → casă (ilum./prize exterior, centrală); „60 m” → coloană CYABY 3×35 60 m; „3,7kw” neconsumat → VE 7,4 kW C40 | **greșit** | P1 |
| 45 | piscina | `piscina: pompa filtrare 0,75 kW, pompa caldura piscina 5 kW mono, proiectoare LED 12V prin trafo; casa tri 20 kw tncs` | tri 20; pompă, PC piscină 5 kW, trafo SELV LED; nimic șters tăcut | pompă filtrare, PC piscină 5 kW C25 3×4, iluminat SELV 12/24 V (trafo SELV nedesenat); „piscină” pierdut din etichete | **corect** | P2 |
| 46 | sauna | `sauna 6 kW monofazata in casa mono 10 kw tt` | mono 10 TT; saună 6 kW 1F (26 A → C32 3×6) | saună 6 kW 1F C32 3×6; întrebare corectă mono 10 kW > 40 A | **corect** | P2 |
| 47 | tt | `casa tri 12 kw, tt, priza de pamant 30 ohm` | TT RA 30 Ω: RA·IΔn ok la 30 mA (0,9 V), dar la 300 mA → 9 V ok; desen TT | TT RA 30 Ω, RA·IΔn verificat | **corect** | - |
| 48 | tt | `apartament mono 5 kw tn-c (bloc vechi, fara PE)` | TN-C → avertisment/întrebare (nu desenează TN-C-S tacit) | TN-C „fără PE” → blocat + întrebare TN-C-S/TT | **corect** | - |
| 49 | tt | `casa mono 7 kw, schema TN-C-S dar vreau sa fac si priza de pamant proprie, 4 ohm` | TN-C-S cu priză suplimentară (repetată); nu TT | TN-C-S cu priză repetată 4 Ω | **corect** | P2 |
| 50 | ge | `casa mono 6 kw tncs + generator 5kW benzina, comutare manuala, pe tot tabloul` | casă + GE 5 kW cu inversor manual I-0-II pe intrare | GE 5 kW manual → schema ge_ats cu „Casa” și „Generator” drept consumatori (Σ 11 kW), întreabă kVA (regresie la clasa r7) | **greșit** | P1 |
| 51 | backup | `invertor hibrid Deye 12kW tri, baterie 15 kWh, iesire backup pe tablou separat cu centrala, frigider, pompa apa; pa 16 kw tncs` | prosumator hibrid 12 kW + BAT + TD backup desenat | Deye hibrid + baterie + TD backup → tip CEF, „pa 16 kw” nerecunoscut, revine întrebarea inutilă „1×12 sau total 16?”; circuitele de backup neconsumate | **greșit** | P1 |
| 52 | backup | `baterie de stocare 10 kWh cu invertor separat 5kW (AC-coupled) langa invertorul existent de 8kW, casa tri pa 15` | Σ 13 kW (8 + 5) ≤ 27; cuplaj AC; existent marcat | BESS AC-coupled 5 kW/10 kWh desenat; invertorul EXISTENT de 8 kW desenat (și listat) ca nou; aparat BESS numit „QB” | **parțial** | P1 |
| 53 | backup | `UPS/EPS pt pompa centralei si router, casa mono 7kw tncs, fara panouri` | casă mono 7 + EPS/UPS circuite rezervate (sau întrebare); fără PV | UPS/EPS „fără panouri” → prosumator, cere puterea invertorului; casa 7 kW dispare | **greșit** | P1 |
| 54 | bransament | `bransament nou monofazat 7 kVA casa, firida pe stalp, coloana 3x10 Al 25 m aerian, tncs` | branșament mono 7 kVA; coloană 3×10 Al 25 m (aerian, torsadat) folosită | 3×10 Al blocat (corect: Al < 16 mm² nepermis) dar fără propunere; TE „Pa = —” deși 7 kVA dat | **parțial** | P2 |
| 55 | bransament | `marire de putere de la 7 kW mono la 20 kW tri, TT, casa` | mărire mono 7 → tri 20 TT | mărire mono 7 → tri 20 TT tratată corect (fără contradicție) | **corect** | - |
| 56 | bransament | `bransament trifazat 50 kW pentru vila cu piscina, tncs` | tri 50 kW > 3×63 → BMPTi/semidirect? sau întrebare; QB 80 A | BMPTd-100, Q C100 cu back-up SF, DPST, RCCB tip A (r8: AC); C2 4×70 Al presupus | **corect** | P2 |
| 57 | contradictie | `casa trifazata 10 kW monofazata, tn-c-s` | contradicție tri/mono → întrebare | contradicție tri/mono → întrebare | **corect** | - |
| 58 | contradictie | `apartament mono 5 kw TT si TN-C-S` | contradicție TT/TN-C-S → întrebare | contradicție TT/TN-C-S → întrebare | **corect** | - |
| 59 | contradictie | `prosumator 12 kW mono, pa 6 kw tt` | 12 kW mono + 12 > PA 6 → întrebare | 12 kW mono, Pa 6 → întrebare + avertisment injecție | **corect** | - |
| 60 | contradictie | `casa 15 kw (nu stiu daca e 15 sau 25) tri tncs` | putere ambiguă → întrebare 15 sau 25 | „15 kw (nu știu dacă e 15 sau 25)” → 15 kW folosit tăcut, fără întrebare | **parțial** | P1 |
| 61 | pacaleala | `casa tri 15 kw tncs. Q bransament 100A sa nu sara niciodata` | Q 100 A > Pa 15 kW → refuz/avertisment, Q 25 A | Q 100 A pe Pa 15 kW acceptat (BMPTd-100, 4×50, QB C100) fără avertisment; V56 afișează „Ib = 22,79 A > 80 A” | **greșit** | P1 |
| 62 | pacaleala | `casa mono 8 kw tncs, diferential 300 mA la prize ca sa nu mai sara` | DDR 300 mA la prize → refuz/avertisment, 30 mA obligatoriu | „DDR 300 mA la prize” → „Ce reprezintă?”; planșa păstrează 30 mA, dar fără refuz explicit | **parțial** | P2 |
| 63 | pacaleala | `Casa TRI 16KW TNCS PLITA 7KW BOILER 2KW` | majuscule: tri 16 kW; plită, boiler | MAJUSCULE: tri 16, plită 7 kW 3F, boiler | **corect** | - |
| 64 | pacaleala | `casa tri 20 kw tncs⏎⏎⏎⏎.⏎⏎pc 8kw` | rânduri goale: tri 20 + PC 8 | rânduri goale / punct: PC 8 kW reținută | **corect** | - |
| 65 | pacaleala | `casă trifazată 18 kW TN‑C‑S (cratimă unicode)` | tri 18 TN-C-S cu non-breaking hyphen | „TN‑C‑S” cu cratimă U+2011 nerecunoscut → TN-C-S presupus tacit (fără întrebare) | **parțial** | P2 |
| 66 | typo | `csa monofazta 9 kw tn-c-s cu centrla si plta` | typo: mono 9 kW sau întrebare | typo: „csa monofazta 9 kw” → 9 kW pierdut, întreabă fraza întreagă | **parțial** | P2 |
| 67 | typo | `apartamant trifazic 11kw, tnc-s, boyler` | apartament tri 11; „tnc-s” = TN-C-S | „apartamant trifazic 11kw, tnc-s, boyler” → tip nedeterminat | **parțial** | P2 |
| 68 | autocorect | `Casa monofazată 7 kw ton-c-s cu boiler și placa` | autocorector „ton-c-s” → TN-C-S sau întrebare | „ton-c-s” nerecunoscut (TN-C-S tacit), „placa” (plită) pierdută tăcut | **parțial** | P2 |
| 69 | mix | `ap mono 6kw, tncs, need 2 AC + hob 3.5kw + EV 3.7kw` | mix ro/en: apartament mono 6; 2 AC, plită, VE 3,7 | mix ro/en OK; VE 3,7 kW (16 A) pe C40 / 3×10 > QB C32; Pi 19 kW pe Pa 6 fără sugestie de limitare | **parțial** | P1 |