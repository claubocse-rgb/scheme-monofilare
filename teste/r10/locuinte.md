# Runda 10 — locuințe, branșamente, prosumatori (reguli locale, fără cheie API)

Data: 2026-10-26 · Tester: proiectant instalații electrice (ANRE gr. II/III)
Motor: `interpretor.interpreteaza_local` → `constructor.genereaza` → `layout` → `render_svg` → PNG (cairosvg), `validare.valideaza`.
Frazele (68, toate noi): `teste/r10/locuinte/fraze.json` · planșele: `teste/r10/locuinte/pNN.png` (56 generate; 12 fraze au primit refuz sau întrebare fără planșă).
Nu s-au modificat `engine/`, `tests/`, `static/`.

Reguli de verdict (confirmate de proiectant): DDR la branșament tip A implicit; Q presupus = calibrul standard ≥ Ib la cosφ 0,95; VE pe 1,25 × I (7,4 kW → C40, 11 kW tri → C20); rețeaua nu se presupune; peste 27 kW se cere tablou cu releu anti-insularizare. O întrebare inutilă e P2.

## Notă: **4,5 / 10** (r9: 6/10)

| | nr. | % |
|---|---|---|
| Corect | 17 | 25 % |
| Parțial | 30 | 44 % |
| Greșit | 21 | 31 % |
| **P0** | **3** (#2, #56, #66) | |
| **P1** | **26** | |
| P2 | 22 (+3 observații P2 la fraze corecte) | |

Frazele de runda asta sunt mai grele decât în r9: text liber de client, cu date puse „la grămadă”, autocorecturi formulate altfel, topologii noi (EPS, generator monofazat, TD-uri pe corpuri). Partea de bază e solidă: regula pentru Q, regula VE, refuzul la contradicțiile mono/tri, faptul că nu presupune rețeaua, releul de interfață peste 27 kW și toleranța la greșeli de tastare. Nota scade din trei motive: 3 planșe greșite care se pot exporta, multe date declarate care se pierd și multe scheme blocate fără nicio întrebare.

## P0 — planșe greșite, nemarcate ca blocante, care se pot exporta

1. **#2** „8 circ prize 6 ilum” → „prize 6 ilum” e citit ca *Prize 6 kW*. Rezultă **un singur circuit de prize pe C32 cu 3×6 mm²**: prize de 16 A protejate la 32 A. Lipsesc cele 8 circuite de prize și cele 6 de iluminat. Validarea dă doar V40, ca avertisment. (Același parser greșește și la #14: „5 prize 3 lumini” → prize 3 kW.)
2. **#56** „Clădire P+1, TE parter + TE etaj, TG cu Q 3x32A, total 18 kW” e clasificată „tablou”. Planșa iese absurdă: MCCB 100 A din ACYABY 4×50, **trei plecări „TG la intrare cu Q 1/2/3” pe siguranțe de 32 A**, o plecare numită „Total”, iar încălzitoarele de prosop (0,5 kW, mono) sunt pe separatoare tripolare 3×2 A cu CYABY 5×6 de 50 m. Acțiunea e `genereaza`: nicio întrebare, niciun blocaj.
3. **#66** „Hibrid 12 kW trifazat cu baterie 15 kWh și tablou de backup (EPS)…” e clasificată **CEF**. Se desenează un BESS independent de 7,5 kW (0,5C), cu TC 50/5 și contor semidirect, „TGD-CF categoria A RfG” și PI externă. Lipsesc PV-ul, invertorul hibrid de 12 kW și tabloul EPS. Exportul nu e blocat; singura întrebare e generică („nu am folosit…”).

## P1 (grupate pe cauză)

**A. Schemă blocată fără întrebare (fundătură UX).** `actiune = genereaza` și nicio întrebare, dar `validare.blocheaza = True`:
- #1 și #55: plita de 7,2 kW depășește Pa de 5/6 kW, cu blocaj V46. Practic e banal: plita de inducție are limitator de putere. Trebuia o întrebare (limitare / mărire de Pa), nu un blocaj tăcut.
- #3: Ib L2 25,14 A > Q 25 A (VE continuu). Trebuia propus DLM / mărire, prin întrebare.
- #26: Iac 47,8 A > 40 A pe BMPM. În plus, invertorul PV „existent” nu e marcat existent.
- #35: BMPT 3×25 A și 22 kW: V04 blocant, fără întrebare. Ar fi trebuit întrebat: ATR / mărire de putere?
- #36: Q 32 A mono, Pi 29 kW, Pa nedeclarat → V46 blocant, fără întrebarea despre Pa.
- #38: „rețea TN-C” → V28 „nu e acoperit”, fără întrebare. Cazul e frecvent la case de țară; răspunsul firesc era TN-C-S cu separarea PEN în BMPT.

**B. Date declarate pierdute sau ignorate.**
- #48: „casa 15 kVA trifazat” e înțeles (Ib 21,7 A), dar Q se presupune 16 A, din bilanț. Q-ul corect e 25 A.
- #49: „cablu 3x6mm de 45 m” dispare fără urmă (nu apare nici la presupuneri, nici în plasa de siguranță). Pe planșă iese CYABY 3×16, fără explicație.
- #60: „corp A 10 kW / corp B la 40 m 5 kW / un singur bransament 3x32” rămân neconsumate. Se desenează o casă tipică cu Q presupus 16 A, deși Q-ul declarat e 32 A.
- #40: „cu ATS” → pe planșă apare un **inversor manual I-0-II**. „casa 15 kW tri” e neconsumat, deci Q rețea iese 16 A în timp ce GE are 25 A.
- #67: „una 11 kW și una 7,4 kW” e neconsumat. Ambele stații VE apar ca 11 kW 3F C20, deși a doua trebuia 7,4 kW mono pe C40.
- #30: la multisplit, cele 3 unități interioare devin 3 circuite AC de 12 A, iar unitatea exterioară de 2,8 kW e neconsumată. Numele „Aer condiționat 1/2” se repetă.
- #16: „sudura 5 kVA” e raportată ca „lipsește puterea”. Se pune întrebarea despre rețea deși cablul e 5×6 și prizele sunt 16 A tri. Se inventează o casă tipică, deși cererea era doar TD-ul anexei.
- #39: TD mansardă: „3 ilum” și „AC 3,5 kW” se pierd, iar 3,5 kW ajunge puterea totală a tabloului. Tabloul e intitulat „TG — tablou general de distribuție JT”.
- #14: vezi P0 #2 (prize 3 kW, cele 3 circuite de iluminat pierdute).

**C. Invertor monofazat pe casă trifazată (#22, #43).** „casa trifazata (3x25A)” e ignorat. Planșa iese „PROSUMATOR 6 kW MONOFAZAT” cu TE monofazat și V43 „RCBO BMPM”. Faza declarată (L2 / R) nu apare nicăieri.

**D. Autocorecturi formulate altfel decât în rundele trecute.**
- #29: „16 kW electric? nu, 16 kW termic, 4,5 kW electric” → refuz I08 („PC 16 kW > 12 kW”), iar întrebarea propune mărirea de putere.
- #54: „corecție: VE nu e 11 kW, e 7,4 kW monofazat” → VE 11 kW apare de două ori, plus contradicția mono/tri.
- #12: „trifazat... adica nu, monofazat, scuze” → contradicție. E doar P2, fiindcă se întreabă.

**E. Topologii lipsă, deși răspunsul spune „am înțeles”.**
- #9: textul spune „tablou rezervat cu Frigider, Centrală”, dar **pe planșă nu există tabloul de backup**.
- #27: EPS pe toată casa: nu apare nici ATS-ul, nici legătura N-PE în regim insular.
- #10: GE monofazat cu comutare manuală e blocat (V96 „doar GE trifazat”). E cel mai frecvent caz de generator la case.
- #31: TD-ul piscinei (la 25 m) nu se creează; toate circuitele ajung în TE. Electroliza e neconsumată.

**F. Dimensionare.**
- #17: „aragaz 2 ochiuri 3 kW” → **C32 pe 3×6 mm²** (Ib 13 A). Plita pare să aibă C32 fix, indiferent de putere; pentru 3 kW trebuia C16 pe 2,5 mm².
- #51: RA = 30 Ω e citit, dar nu se emite niciun avertisment, iar nota de pe planșă spune „Rp ≤ 4 Ω”.

## P2 (pe scurt)

- Întrebări de tip „nu am folosit…” pentru Q sau date de branșament evidente: #7 „casa are 3x32 A”, #8 „3x63A”, #25 „3x100A”, #57 „3x32 A”, #58 „PI 35 kW” (PI = putere instalată), #55 „MS 2.2kW”, #62 „DDR general 40A 30mA”.
- #59: aceeași întrebare despre rețea e pusă de două ori.
- #5: mărirea de la mono la tri desenează „BMPTd-40 **existent**”, deși BMPT-ul e nou. #52 (branșament subteran nou, firidă E2-1) e tot desenat „existent”, iar cablul impus 4×16 devine 5×16 fără notă.
- #33: „cablu branșament 4x16 Al de la stâlp” e folosit drept coloană BMPT → TE (C2), nu ca racord C1.
- #15: TD Etaj („6 circuite”) lipsește, cu întrebare. Plecarea VE din TD Garaj are eticheta „trifazat cu VE” și nu are mențiunea RDC-DD 6 mA, pe care o are în TE.
- #47: VE 7,4 kW trifazat → C20; după regula 1,25 × I (14 A) ieșea C16.
- #24: QI C50 și QG C50 în serie (redundant, neselectiv), iar DDR-ul de 30 mA pe un invertor de 27,5 kW dă declanșări nedorite. #25: invertorul de 40 kW nu are DDR, deși #24 are (inconsecvent).
- #20: blocul cu 4 apartamente primește întrebarea greșită (mono/tri), nu „4 consumatori, schemă cu mai multe contoare”. #41 la fel: generator mono pe casă tri → contradicție mono/tri.
- #18: VE 7,4 kW pe Pa 7 kW → refuz. Mai util era „generează + DLM / limitare curent”.
- #37: un apartament fără circuite e clasificat „tablou” și blocat, pe când la celelalte locuințe se pune setul tipic.
- #42: „2 ventiloconvectoare” se pierd fără mesaj; pompa de puț și hidroforul se numesc ambele „Pompă apă”.
- #50: trecerea TT → TN-C-S e tratată ca contradicție.
- #61: „doar circuitul VE” → se desenează toată casa cu circuite tipice.
- #63: „plită pe 2 faze” → desenată 3F 4P.
- #64: textul spune „desenat TN-C-S”, dar schema e blocată V28 și nu se desenează nimic.
- Observații la fraze corecte: #6 iluminatul piscinei SELV 12 V e fără transformator de separație; #53 soft-starterul nu e desenat.

## Planșe judecate ca la avizare (15)

| PNG | Verdict avizare |
|---|---|
| p02 | **Respins** — circuit „Prize” pe C32 / 6 mm²; lipsesc 8 circuite de prize și 6 de iluminat. Restul (SF, P, QB C25, RCCB 300 mA S, PE / PS / PPL, SPD cu rezervă) e corect desenat. |
| p04 | **Admis** — BMPM-40, RCBO C40 300 mA S tip A, BN + PS + PPL, ACYABY 3×25 50 m, TE generic. Curat. |
| p08 | **Admis cu observații** — TD-PV cu PI (U/f, ROCOF) care comandă bobina BD a QG C50; 2 × C32 4P. Q 63 A din BMPT nu apare. |
| p09 | **Respins** — tabloul de backup (frigider, centrală) lipsește, deși răspunsul din chat îl confirmă; bateria e desenată corect pe c.c. |
| p15 | **Admis cu observații** — cascadă TE → TD Garaj (C25 4P, 5×4), compresor DOL cu KM + releu termic; lipsesc TD Etaj și nota RDC-DD; eticheta VE e greșită; format A1, text mic. |
| p17 | **Respins** — „Plită” 3 kW pe C32 / 6 mm²; Q 16 A corect. |
| p19 | **Admis** — 2 × VE C20 4P, DDR separat pentru fiecare, RDC-DD trecut în listă, PC 12 kW C20 4P, Q C40. Observație: SF 3×40 gG și QB C40 nu sunt selective (convenția OD). |
| p22 | **Respins** — casa e trifazată, dar tabloul e desenat monofazat; faza L2 nu apare. |
| p24 | **Admis cu observații** — PI cu BD pe QG; QI și QG C50 în serie; DDR 30 mA pe 27,5 kW (recomandat 300 mA, tip A/B după fișă). |
| p31 | **Respins** — nu există TD piscină; RCBO C40 pe PC piscină sub Q 25 A (V40). |
| p33 | **Admis cu observații** — cablul de branșament (racord de la stâlp) e trecut drept coloană C2; Q C16 corect. |
| p39 | **Respins** — TD mansardă: lipsesc 3 circuite de iluminat și AC-ul; titlul „TG general de distribuție”; SPD T1+T2 într-un tablou secundar. |
| p40 | **Respins** — cerința era ATS, desenul arată inversor manual; Q rețea 16 A față de GE 25 A și Pa 15 kW ignorat. Comutarea 4P cu N comutat și interblocajul sunt corect desenate. |
| p56 | **Respins (P0)** — plecări inventate („TG la intrare cu Q 1/2/3”, „Total”), MCCB 100 A. |
| p66 | **Respins (P0)** — topologie de centrală BESS (TC 50/5, RfG) în locul unui prosumator hibrid cu EPS. |

Calitatea grafică (simboluri, BOM, legendă, cartuș, note) e bună și constantă. Problemele sunt de interpretare și topologie, nu de desen.

## Tabel complet

| # | Așteptat (scurt) | Obținut | Verdict | P |
|---|---|---|---|---|
| 1 | mono, Q 25, plită C32 | corect desenat, dar blocat V46 (plită > Pa) fără întrebare | parțial | P1 |
| 2 | 8 prize + 6 ilum, Q 25 | „Prize 6 kW” pe C32; circuitele pierdute | greșit | **P0** |
| 3 | VE C20, Q 25, DLM | VE C20 + RDC-DD; blocat V46 fără întrebare | parțial | P1 |
| 4 | branșament mono Q 40 | BMPM-40, RCBO C40 300 mA S tip A | corect | – |
| 5 | tri TT Q 20 | Q C20, RCCB 300 mA S, TT; BMPT „existent” | parțial | P2 |
| 6 | Q 32, saună 4P C16, piscină | totul corect; SELV fără transformator | corect | (P2) |
| 7 | hibrid 8 kW + baterie | corect; „3x32 A” neconsumat → întrebare | parțial | P2 |
| 8 | >27 kW, PI | TD-PV + PI + BD, corect; „3x63A” neconsumat | parțial | P2 |
| 9 | EPS frigider + centrală | tablou backup lipsă (deși „înțeles”) | greșit | P1 |
| 10 | GE mono, I-0-II | nesuportat (V96), blocat | greșit | P1 |
| 11 | contradicție → întreabă | refuz I08 + întrebare | corect | – |
| 12 | autocorectură → mono | contradicție, întrebare | parțial | P2 |
| 13 | rețea → întreabă | întreabă, blocat V07 | corect | – |
| 14 | rețea → întreabă | întreabă; „prize 3 lumini” = 3 kW | parțial | P1 |
| 15 | cascadă TG → TD etaj / garaj | TD Garaj ok; TD Etaj lipsă; etichetă VE | parțial | P2 |
| 16 | TD anexă 5×6 60 m | casă tipică; sudura „fără putere”; rețeaua întrebată | greșit | P1 |
| 17 | aragaz 3 kW C16, Q 16 | aragaz pe C32 / 6 mm² | parțial | P1 |
| 18 | VE C40 + DLM | refuz I08 VE > Pa | parțial | P2 |
| 19 | 2 VE C20, PC, Q 40 | corect | corect | – |
| 20 | multi-consumator | întrebare greșită (mono/tri) | greșit | P2 |
| 21 | 10 kW mono → întreabă | refuz V53 + întrebare bună | corect | – |
| 22 | inv. mono pe L2, casă tri | totul mono, BMPM | greșit | P1 |
| 23 | 27 kW = prag, fără PI ext. | corect | corect | – |
| 24 | 27,5 kW → PI | PI ok; QI + QG C50 în serie; DDR 30 mA | parțial | P2 |
| 25 | 40 kW → PI, Q 100 | PI ok; Q neconsumat; fără DDR | parțial | P2 |
| 26 | baterie AC + PV existent | blocat V53 fără întrebare; „existent” nemarcat | parțial | P1 |
| 27 | EPS toată casa, ATS | EPS ignorat (neconsumat) | greșit | P1 |
| 28 | TT prosumator 6 kW | corect (C13 4P, RCBO-uri) | corect | – |
| 29 | autocorectură PC 4,5 kW | refuz „PC 16 kW > Pa” | greșit | P1 |
| 30 | multisplit 1 circuit | 3 circuite AC pentru unitățile interioare; exterioara neconsumată | greșit | P1 |
| 31 | TD piscină | fără TD; electroliză neconsumată | parțial | P1 |
| 32 | saună 6 kW C32 | corect | corect | – |
| 33 | cablu branșament 4×16 | folosit drept coloană | parțial | P2 |
| 34 | Q 40, 22 kW | corect | corect | – |
| 35 | Q 25 < 33 A → întreabă | blocat V04 fără întrebare | parțial | P1 |
| 36 | mono 32 A, Pi mare | blocat V46 fără întrebare | parțial | P1 |
| 37 | TE ap. din palier | „tablou”, cere circuitele, blocat | parțial | P2 |
| 38 | TN-C → TN-C-S | blocat V28 fără întrebare | greșit | P1 |
| 39 | TD mansardă 4 + 3 + AC | doar 4 prize; P = 3,5 kW; titlu TG | greșit | P1 |
| 40 | GE + ATS, Q 25 | inversor manual; Pa pierdut, Q 16 | greșit | P1 |
| 41 | GE mono, tablou critic | contradicție mono/tri | greșit | P2 |
| 42 | pompe, Q 40 | ok; ventiloconvectoare pierdute | parțial | P2 |
| 43 | inv. mono pe R, casă tri | totul mono; „3x25A” neconsumat | greșit | P1 |
| 44 | 100 kW → întreabă | întreabă rețeaua și puterea | corect | – |
| 45 | plită tri pe mono | contradicție + întrebare | corect | – |
| 46 | VE 22 kW mono | contradicție + întrebare | corect | – |
| 47 | VE 7,4 tri → C16 | C20 | parțial | P2 |
| 48 | 15 kVA → Q 25 | Q 16 (din bilanț) | greșit | P1 |
| 49 | coloană 3×6 45 m (ΔU) | cablul impus pierdut; 3×16 fără explicație | greșit | P1 |
| 50 | TT → TN-C-S | tratat ca contradicție | parțial | P2 |
| 51 | RA 30 Ω → avertisment | niciun avertisment; nota „Rp ≤ 4 Ω” | parțial | P1 |
| 52 | branșament nou 4×16 | „existent”; 5×16 | parțial | P2 |
| 53 | PC sol-apă 7 kW tri | corect (fără soft-starter desenat) | corect | (P2) |
| 54 | autocorectură VE 7,4 | VE 11 kW ×2 + contradicție | greșit | P1 |
| 55 | MS / MSV, zecimale cu punct | MS neînțeles; blocat V46 (plită) | parțial | P1 |
| 56 | TG + 2 TE | plecări inventate, MCCB 100 A | greșit | **P0** |
| 57 | 2 × 8 kW + baterie | ok + întrebare baterie; „3x32 A” neconsumat | parțial | P2 |
| 58 | 3 × 11,6 kW → PI | PI ok; „PI 35 kW” neconsumat | parțial | P2 |
| 59 | rețea → întreabă | întreabă (de două ori) | corect | – |
| 60 | 2 corpuri, Q 32 | corpuri neconsumate, Q 16 | greșit | P1 |
| 61 | doar plecarea VE | toată casa + VE C20 | parțial | P2 |
| 62 | DDR general 30 mA | neconsumat, întrebare | parțial | P2 |
| 63 | plită pe 2 faze | desenată 3F | parțial | P2 |
| 64 | TN-C fără PE | 2 întrebări bune; blocat, deși textul zice „desenat” | parțial | P2 |
| 65 | 20 kW mono → întreabă | refuz V53 + întrebare | corect | – |
| 66 | hibrid + EPS | centrală BESS cu TC / RfG | greșit | **P0** |
| 67 | VE 11 + 7,4 | 2 × 11 kW | greșit | P1 |
| 68 | greșeli de tastare | tolerate, corect | corect | – |

## Comparativ cu r9 (6/10)

- **Rămân bune:** Q presupus după regulă (25 / 20 / 16 / 40 A verificate), DDR tip A la branșament, VE 11 kW → C20 cu RDC-DD, contradicțiile mono/tri și VE / plită pe mono, rețeaua nepresupusă (#13, #14, #44, #59), PI peste 27 kW (#8, #24, #25, #58) și pragul de 27 kW (#23), greșelile de tastare (#68), regula BMPM 40 A la prosumatori.
- **Regresii sau zone noi neacoperite:** autocorecturile formulate altfel (3/3 eșuate), plasa „nu am folosit” care nu prinde date de branșament evidente („3x32 A”, „3x100A”, „PI 35 kW”), scheme blocate fără întrebare (7 cazuri) și clasificarea greșită spre „tablou” / „cef” (#56, #66), care produce planșe absurde nemarcate.

## Recomandări de reparat (prioritate)

1. **P0:** „N circ prize M ilum” / „N prize M lumini” → N circuite de prize + M de iluminat, nu „M kW”. Orice circuit cu receptor „prize” peste C16 → blocant.
2. **P0:** clasificarea locuință vs tablou / CEF: „TE parter / TE etaj / Q 3x32A / total 18 kW” = locuință cu tablouri; „hibrid … baterie … backup / EPS” = prosumator. Plecările „Total” sau „TG la intrare” nu sunt receptoare.
3. Regula R1 la blocaj: dacă `validare.blocheaza` și nu există nicio întrebare, se generează automat întrebarea de remediere (Pa / limitare, DLM, ATR, TN-C → TN-C-S).
4. „casa (are) 3x32 A”, „bransament 3x100A”, „un singur bransament 3x32”, „15 kVA” → In_Q / S branșament. „casa trifazata” + invertor mono → instalație tri cu invertorul pe faza declarată.
5. Topologii: TD backup / EPS (prosumator), GE monofazat cu inversor 2P, ATS când e scris, TD pe corpuri / piscină / mansardă.
6. Plita: calibrul după putere (nu C32 fix); VE tri după 1,25 × I; avertisment la RA > 4 Ω în TN-C-S.
