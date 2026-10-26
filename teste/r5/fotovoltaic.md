# Runda 5 — rol „fotovoltaic” (CEF JT / PT propriu, prosumatori comerciali, BESS)

**Scor: 3/10.** 46 de fraze: **9 corecte · 12 parțiale · 25 greșite**. Am randat 14 planșe (f03, f04, f06, f11, f13, f16, f21, f22, f24, f28, f31, f39, f45, f46, în `teste/r5/fotovoltaic/*.png`) și m-am uitat la toate.
Partea de motor e bună când datele intră curat (ex. „CEF 400 kWp cu 4x100kW…” sau „1,2 MWp cu 10 invertoare de 100 kW din PT propriu 1250 kVA”). Fiecare invertor e desenat separat, cu SB, S, SPD c.c., echipotențializare, Q per invertor, SPD T1+T2, QG + PI pe BD, TC + contor.
Problema e interpretorul. **Nu înțelege nicio denumire de echipament reală.** În plus, cifrele din modele (SUN2000-**100**KTL, module **580** W) și formulările uzuale („a 50 kW”, „5 inv x 100kw”, „invertor 1 = …”) dau puteri greșite fără niciun avertisment. Iar un BESS scris cu marcă se pierde fără niciun mesaj.

Fișiere: `teste/r5/fotovoltaic/fraze.py` (frazele), `ruleaza.py` (harness), `fraze.json` (anexă: toate frazele, intrarea fizică, presupuneri, verificări, verdict), `fNN.svg/png`.

## P0 — greșit tehnic / periculos

1. **Puterea invertorului e luată de la alt număr din frază (model, modul).** Fallback-ul din `extrage_cef` („primul kW = putere c.a. totală / n”) se aplică ori de câte ori `RE_INV` nu prinde, adică la orice model între „invertoare” și „de X kW”.
   - „cef 120kwp, 1 invertor sungrow SG110CX, panouri longi 580W…” → **invertor 0,58 kW** (puterea modulului). Schema e generată fără întrebare.
   - „3 invertoare a 50 kW” → 3 × 16,7 kW.
   - „8 invertoare Huawei SUN2000-115KTL de 115 kW” la 1 MWp → 8 × 14,4 kW.
   - „4 invertoare Sungrow SG125CX 125 kW” → 4 × 31,25 kW.
   - „2 invertoare diferite: Huawei 36 kW si Huawei 20 kW” → 2 × 18 kW.

   *Corect:* N × P pe fiecare model. *Remediere:*
   - mască pentru tokenii de model (`[A-Z]{2,}[\w-]*\d+\w*`) înainte de extragere;
   - acceptă „a / de / x / ×” între număr și putere;
   - **nu** împărți niciodată un kW la n fără întrebare;
   - „W/Wp” lângă modul/panou = Pmax modul (regula F.3 există, dar nu e aplicată);
   - verificare de plauzibilitate: raport kWp/kWac în afara intervalului 0,8–1,6 → întrebare.
2. **Invertoare pierdute (mai puține desenate decât există).**
   - „2 x Huawei SUN2000-100KTL-M2 (100 kW)” → 1 × 100.
   - „1 invertor Huawei … de 100 kW si 2 invertoare Sungrow SG50CX de 50 kW” → doar 1 × 100.
   - „invertor 1 = Fronius Tauro 100 kW, invertor 2 = SMA STP 50 kW” → doar 1 × 100.
   - „5 inv x 100kw” → 1 × 100.
   - „MAX 50KTL3 + MAX 30KTL3, total 80 kw” → 1 × 80.

   Rezultă o planșă cu jumătate din putere: QG, C0, TC și PI sunt subdimensionate. *Remediere:*
   - listă de grupuri de invertoare (separator „+”, „si”, „;”, „invertor k =”);
   - prescurtarea „inv”;
   - dacă Σ invertoare găsite ≠ numărul cerut, refuz I05 (ca la plecări).
3. **BESS cu marcă / model ignorat fără niciun mesaj.** Afectează „BESS Huawei LUNA2000 215 kWh / 100 kW”, „BESS Sungrow PowerStack 200 kW / 430 kWh”, „BESS BYD Battery-Box 150 kWh” și „BESS Huawei LUNA2000 30 kWh”. `RE_BESS` cere cifra imediat după „bess”, deci schema iese fără stocare și fără întrebare. *Remediere:* permite până la ~5 cuvinte între „bess / stocare” și valoare. Dacă textul conține „bess / baterie / stocare” și nu s-a extras nimic, pune întrebare obligatorie.
4. **Transformator desenat în serie între două tablouri JT.**
   - „CEF 300 kWp, 3×100 kW, BESS 200 kWh, racord in TG existent” → I11 adaugă PT 630 kVA. T1 20/0,4 kV apare în TGD-CF, între QG și C0 → „TG EXISTENT” (f31).
   - „…racord in TG existent al fabricii (PT propriu 1000 kVA existent)” → T1 1000 kVA nou, tot în serie (f45).

   Topologia e imposibilă: JT → trafo → JT. *Remediere:*
   - `racord = tg_existent` exclude adăugarea PT (atunci I11 doar întreabă);
   - „PT … existent” → `origine = pt_propriu` + Sn pentru Ik, nu trafo desenat.
5. **Prosumator: BESS dispare din planșă și invertoarele sunt contopite.** Exemplu: „prosumator 250 kW cu 2 invertoare de 125 kW si BESS 200 kWh / 100 kW, injectie limitata 150 kW”.
   - Se desenează un singur INV de 250 kW, fără baterie și fără PCS (f28). `baterie_kWh` se extrage, dar nu se desenează dacă invertorul nu e „hibrid”.
   - La fel „2 invertoare Huawei SUN2000-50KTL” → un INV de 100 kW, și 20 + 10 Fronius → un INV de 30 kW.

   Încalcă direct cerința „fiecare invertor desenat separat”. *Remediere:* `extrage_prosumator` trebuie să trimită lista `invertoare[]` (nu doar Σ în `Pn_inv_kW`) și `bess{P_kW, kWh}`. Motorul de prosumator trebuie să deseneze N invertoare + PCS ca la CEF.
6. **DDR 30 mA pe circuitul invertorului de 100–250 kW** (bloc diferențial 200 A / 500 A, IΔn 30 mA). Curentul capacitiv de scurgere al câmpului PV declanșează sigur un DDR de 30 mA. În TN-S nici nu e cerut pe această plecare. *Corect:* DDR 300 mA tip A/B, sau fără DDR în TN cu deconectare prin MCCB, conform fișei (Huawei/SMA cer ≥ 100 mA per invertor). *Remediere:* IΔn după Pn (≤ 30 kW: 30 mA tip A, conform fișei; peste: 300 mA sau eliminat în TN).
7. **„monofazat” ignorat în tăcere la CEF.** „CEF 100 kWp cu 2 invertoare de 50 kW, monofazat” e desenat 3 × 400 V. Ar trebui I08 (contradicție). În general, la CEF rețeaua (tri) și schema de legare la pământ sunt presupuse și nu apar în „Am presupus”. Asta încalcă regula „rețeaua NU se presupune”.

## P1 — important

8. **Modelele (Huawei SUN2000, Sungrow SG/SH, SMA STP, Fronius Tauro/Symo, Growatt MAX, Solis, JA/LONGi/Trina/Jinko, BYD/LUNA/PowerStack) nu se extrag deloc.**
   - În 0 din 46 de planșe apare modelul, deși motorul și catalogul le suportă (`invertor.model`, `modul`, `fise`).
   - „SUN2000-100KTL-M2, retea TT, priza 4 ohm” → **refuz I02 inutil**.

   *Remediere:* un dicționar de mărci + regex de model. Puterea se deduce din model (SUN2000-**100**KTL, SG**110**CX), declarată ca presupunere, iar modelul se trimite în `invertoare[k].model`.
9. **Racordul CEF „prin BMPT” schimbă tipul în branșament și refuză.** Aceeași greșeală la „prosumator 150 kW … BMPT existent 200 A” (prosumatorul dispare). Ordinea de decizie BMPT > CEF / prosumator e greșită când textul conține „cef / kWp / invertor / prosumator”. BMPT-ul trebuie tratat ca punct de racord.
10. **Limitarea injecției / injecția zero** („limitare injectie 50 kW”, „injectie zero”, „limitata la 0”, „30 kW (ATR)”) e ignorată în 6 fraze. Pe planșă lipsesc contorul / analizorul de putere la punctul de racord, Smart Dongle / Power Manager / EMS și nota cu P_inj_max. *Remediere:* câmp `P_injectie_max_kW` + aparat „Analizor / contor de control al injecției (TC la PCC)” + verificarea V (limitarea injecției) există deja în `verificari.py`.
11. **SPD c.a. la invertor lipsește** deși cablul invertor–TGD-CF e presupus de 30 m. SR HD 60364-7-712 cere SPD și la capătul invertorului peste 10 m. Pe ramura BESS (PCS) nu există nici SPD c.c., nici separator / siguranță c.c. între BAT și PCS.
12. **Date de cablu și rețea ignorate:**
    - „cablu Cu 25 m” → ACYABY Al;
    - „3x(4x150)Al” ignorat;
    - „Q 250 A, Ik bara TG 15 kA” ignorate (schema rămâne pe Ik3 implicit de 25 kA);
    - „TN-C-S” / „TT + 4 Ω” ignorate la CEF (se recunosc doar la locuință).
13. **Datele de string** („18 module pe string, 5 stringuri”, „2 pe MPPT”) și „gPV 15 A pe string” declarat nu intră în model, deci gPV nu apare niciodată în planșele generate din text.
14. **Contradicții neîntrebate:**
    - „3 invertoare de 50 kW, total 100 kW” → se ia 3 × 50 fără nicio întrebare;
    - „invertoare de 100 kVA” → interpretat ca PT de 100 kVA și refuzat (kVA la invertor e uzual și ar trebui să însemne Sn invertor).
15. **Prosumatorul comercial e desenat cu circuite casnice** (iluminat C10, prize C16 30 mA, boiler) și „Branșament existent”, deși textul spune „TG existent”. La 100–400 kW e un TG industrial, nu un TE de locuință. Pentru Pn > 100 kW, PI integrată „conform 228/2018” trebuie confirmată (de regulă ATR cere PI externă).
16. **BESS standalone** („BESS 500 kW / 1000 kWh … langa CEF existenta”) e refuzat pentru că lipsesc invertoarele PV: refuz inutil.

## P2
17. „1.000 m cablu?? nu, 100 m” → 1000 m (se ia prima valoare, deși autocorectarea e explicită).
18. Mesaje contradictorii: „racord în TG existent”, dar în presupuneri „racord JT direct din PT OD” sau „prin BMPT”. Notele planșei spun și „branșament conform ST 4-JT” la CEF cu PT propriu.
19. V67 (Sn trafo < 1,1·ΣPn) e BLOCANT la PT 400 kVA cu 4 × 100 kW și la PT 2000 kVA cu 20 × 100 kW. Pe fișă Smax = 110 kVA, deci verificarea e corectă, dar interpretorul ar trebui să întrebe înainte, nu să genereze o planșă blocată.
