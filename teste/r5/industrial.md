# Runda 5 — rol „industrial” (TG, PT, GE+ATS, combinații) — 23.10.2026

**Scor: 3/10.** PT simplu (Sn + plecări în A/kW cu lungimi) și refuzurile I02/I03/I05/I07/I12/V86 merg bine. Planșele PT sunt de calitate (celule MT, trafo, măsură JT pe TC, servicii proprii). Pe TG industrial însă interpretorul e fragil, iar la GE și la combinații dă **scheme greșite fără blocant**.

**Statistici:** 54 de fraze: 16 corecte · 12 parțiale · 26 greșite. Dintre cele 26 greșite, 9 trec de validator fără BLOCANT (#4, 19, 32, 36, 37, 39, 47, 49, 50, 53). Celelalte sunt oprite de V05/V07/V50 sau sunt refuzuri inutile.
Am randat și am verificat 17 planșe (svg/, png/). Fișiere: `teste/r5/industrial/fraze.json`, `fraze_in.py`, `ruleaza.py`.

## P0 — greșit tehnic / periculos (planșa se poate exporta)
1. **Schema de legare la pământ TT ignorată la tablou.**
   - Fraze: #42 „TG atelier 3 plecari … retea TT RA 30 ohm”, #47 „… schema TT, RA 20 ohm”.
   - Obținut: TN-S în aval de separarea PEN, fără DDR pe plecări. Se exportă.
   - Corect: `schema_pamant=TT`, `RA_ohm`, DDR pe fiecare plecare, verificarea RA·IΔn ≤ 50 V.
   - Remediere: extrageți TN-C-S/TN-S/TT/RA și pentru tablou, PT și GE, nu doar pentru locuință. Dacă schema lipsește, întrebați; nu o presupuneți.
2. **„monofazat” ignorat la tablou.**
   - Fraze: #53 „tablou general monofazat cu plecari: iluminat 2 kW, prize 3 kW” desenează 3P+N+PE, aparate 4P, CYABY 5×6. #11 „tablou monofazat 3x63A” nu dă I08.
   - Remediere: puneți `retea` în `intrare_fizica` și pentru tip=tablou. I08 trebuie aplicat și la tablou.
3. **La combinații, kVA-ul PT-ului devine puterea GE.**
   - #36 „PT 1000 kVA + TG … plus GE 200 kVA cu ATS” dă GE 1000 kVA. PT-ul, TG-ul și GE-ul de 200 kVA dispar fără niciun mesaj.
   - #49 „PT 400 kVA si GE 100 kVA …” dă GE 400 kVA, fără blocant.
   - #38 dă GE 630 kVA.
   - Remediere: kVA se leagă de cuvântul cel mai apropiat (PT/trafo vs GE/grup). Când textul are mai multe tipuri de schemă, refuz sau întrebare („desenez doar GE+ATS?”), niciodată o alegere tăcută.
4. **Sarcina vitală a GE se ia doar din primul receptor.**
   - #32 „pompe incendiu 2x30kW, iluminat siguranta 3kW, server 10kW” dă P_sarcina = 30 kW (corect: 73 kW). QR iese de 50 A, în timp ce ATS-ul e de 400 A.
   - #50 „2 pompe x 15 kW si iluminat 5 kW” dă 15 kW (corect: 35 kW).
   - Remediere: listele de consumatori la GE se adună sau devin plecări din TAR. Altfel, întrebare.
5. **kVA pe o plecare transformă TG-ul în PT inventat.**
   - #19 „tablou general cu plecari TD-1 40A si TD-2 30 kVA” dă un PT de 100 kVA (trafo, celule MT). TD-2 se pierde.
   - Remediere: când tabloul e numit explicit (TG/„tablou”), acesta are prioritate. „kVA” pe un item de listă înseamnă S-ul plecării (sau I04).
6. **Cifra din codul tabloului se lipește de calibru.**
   - #16 „td-2 160 A 0,15 km” dă Q1 = 2160 A. #44 „TD-1 125A 50m pozat aparent…” dă Q1 = 1125 A.
   - Aici V05/V07 au blocat, dar mecanismul poate produce și un calibru valid în tăcere.
   - Remediere: tokenizați întâi codurile TD-k/TG-k, înainte de extragerea numerelor.
7. **„tg birouri P+2: TE parter 40A … lift 11kW, HVAC 32 kW” (#4) devine locuință.**
   - Rezultat: 15 circuite de casă inventate (plită, cuptor, baie). Tabloul real se pierde.
   - Remediere: „TG/TE/TD” au prioritate față de „P+n”.

## P1 — important
8. **Liste de plecări care nu se parsează și se pierd în tăcere.** Prima valoare devine P sau Q1 al tabloului, apoi V07.
   - #15: „pornire stea-triunghi”, „cu convertizor”.
   - #13: cascada „NUME (LISTA); …”, cerută explicit în F.4 r.3.
   - #43: listă fără cuvântul „plecari”.
   - #48: „15 CP”.
   - #51: „In=100A L=60m”.
   - #20: „cuptor 60 kW cosfi 1” dă In = 1 A.
   - #52: „3x185+95 Al” devine 3 plecări de 185 kW.
9. **„PT” ca origine e citit ca tip PT.** Rezultatul e un refuz inutil (I02 „puterea trafo”).
   - Exemple: #5 „coloana 120 m din PT ATR”, #40 „faza PT” (încalcă F.5), #1 „din PT propriu 630 kVA”, care dă PT nou în loc de TG cu `origine=pt_propriu`.
10. **TG + CEF/invertor (#37, #39):** se desenează doar CEF-ul cu BMPT propriu. TG-ul și plecările lui dispar fără niciun mesaj. Corect: refuz cu explicație sau prosumator/TG cu plecare CEF.
11. **Sursa TG se presupune în tăcere: „rețea publică prin BMPT cu RCCB 300 mA”.**
   - V31 („deconectarea se bazează pe DDR din amonte”) se sprijină apoi pe acest RCCB presupus (#3, #9, #14).
   - Se întâmplă și când textul spune „din TGD existent” (#41) sau „din PT” (#52).
   - Remediere: sursa nu se presupune, se întreabă. Fără DDR declarat, V31 trebuie să fie BLOCANT.
12. **Date cerute explicit și ignorate fără mesaj:**
   - celule de linie intrare-ieșire și măsură pe MT (#23);
   - trafo uscat, desenat ca ulei (#28);
   - cablu impus 3x150+70 (#41);
   - L cablu GE–ATS 15 m (#33);
   - „retea 125A” la GE (#31);
   - pozare per plecare (#44).
13. **Motoare industriale:** „strung”, „freză”, „moară” nu sunt recunoscute ca motor (cosφ 0,9 „forță”). Nicio plecare de motor nu are contactor sau releu termic/disjunctor-motor (planșa f03).
14. **GE 500 kVA pentru hală (#34): V50 BLOCANT „nu există BMPT”.** Ramura de rețea ar trebui să poată veni din PT/TGD.
15. **Multiplicatorii de circuite (#14):**
   - „prize 4 circuite de 25A” dă o singură plecare numită „Prize 4 circuite de”;
   - „iluminat 5 circuite” dă „Circuit 1…5” în loc de „Iluminat 1…5” (F.4 r.2);
   - iluminatul iese pe 4P C16, deși spec-ul cere curba B.
   - Lot apropiat: „cca 150A” (#6) devine V05 BLOCANT, în loc de 160 A + întrebare.

## P2
16. Numele cascadei păstrează „TD-1 cu sub-plecari” (#12).
17. Casetele receptoarelor se suprapun: Compresor/Iluminat (f01), Prize/Forta (f14), Prize/Pompa (f12), TG1/TG2 (f22).
18. „PT 630 kVA cu 4 plecari” (#30) generează cu V07, iar „tablou general 5 plecari” (#8) refuză cu I02. Comportamentul e inconsecvent.
19. „1 000 m” în listă (#17) dă mesajul „Valoarea 1 nu are unitate”. Mesajul e conform spec, dar derutant.
20. Plecările din TG-ul unei hale primesc implicit „Al PVC D1 în pământ”. Pentru o hală e nerealist; ar trebui pat de cabluri (E) sau întrebare.
