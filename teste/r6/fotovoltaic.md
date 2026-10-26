# Runda 6 — rol „fotovoltaic" (CEF JT / PT, prosumatori, BESS)

**Scor: 5/10** (runda 5: 3/10).

**94 de fraze rulate:**
- cele 46 din r5, rerulate: **36 corecte · 9 parțiale · 1 greșită** (în r5: 9 · 12 · 25);
- 48 noi: **18 corecte · 17 parțiale · 13 greșite**;
- total: **54 · 26 · 14**.

**Planșe:** am randat ca PNG toate cele 48 de planșe noi și 11 din r5. Le-am judecat ca la avizare pe 14 dintre ele: r5_13, r5_24, r5_28, r5_42 și f04, f08, f20, f21, f22, f25, f30, f33, f36, f38, f40.

**Fișiere:**
- `teste/r6/fotovoltaic/fraze_r6.py`: frazele noi;
- `ruleaza.py`, `r5.py`, `r6.py`: harness-ul;
- `anexa.py`: verdictele;
- `fraze.json`: anexa cu 94 de intrări (frază, intrare fizică, presupuneri, întrebări, verificări, ce apare pe planșă, verdict, gravitate, observație);
- `r5_out.txt`, `r6_out.txt`: ieșirea brută;
- `*.svg` / `*.png`: planșele.

## Ce s-a reparat față de r5 (verificat pe planșă)

- **Modele reale** (Huawei SUN2000-xxKTL, Sungrow SG/SH, Growatt MAX/MOD/MID, Solis S5/S6, SMA STP Core2, Fronius Tauro/Symo, LONGi/JA/Trina/Jinko, LUNA2000, PowerStack, BYD):
  - se extrag și apar pe planșă și în listă;
  - Pn se deduce din cod și apare ca presupunere;
  - modulul în W/Wp nu mai e luat ca invertor.
- **Grupuri mixte de invertoare** sunt desenate fiecare separat: „1 invertor … si 2 invertoare …", „invertor 1 = …", „A + B", „2 inv X + 1 Y".
- **Fiecare invertor are setul complet de aparate:**
  - SB cu S c.c. sub sarcină și SPD c.c.;
  - echipotențializare;
  - **SPD T2 c.a. la invertor** (fost P1-11);
  - Q propriu;
  - la TGD: SPD T1+T2, QG + PI pe BD, TC + contor.
- **BESS cu marcă:**
  - ramura BAT → SB-B (separator + siguranțe c.c.) → SPD c.c. → PCS → SPD c.a. → QB;
  - BESS fără PV (standalone) e acceptat.
- **Racordul:**
  - în TG existent cu S > 400 kVA, aplicația întreabă de PT și nu mai desenează trafo în serie;
  - „PT propriu … existent" e tratat ca sursă, fără trafo nou;
  - BMPT e punct de racord, nu mai trece pe branșament.
- **Limitarea / injecția zero:** analizor AR la PCC + EMS cu comandă spre invertoare/PCS, plus P_inj în listă.
- **Prosumator:**
  - N invertoare + PCS desenate separat;
  - peste 27 kW: TD-PV cu **PI externă pe bobina BD a QG** (verificat f40, f30, r5_28);
  - TG existent (nu mai e TE de locuință).
- **DDR:** 100 mA la invertoarele mari în TT (f36), iar în TN nu mai există DDR de 30 mA pe 100–250 kW.
- **Contradicții:** I08 la monofazat / Σ ≠ total, kVA la invertor = Sn. Apare o plasă nouă de siguranță: raport c.c./c.a. în afara 0,8–1,6 → întrebare.
- **Valori preluate:** autocorectura „1.000 m?? nu, 100 m", Q TG + Ik bară (→ V44/V40), cablu impus (3x(4x150)Al, NA2XY 3x150+70, CYABY 4x70 → V02/V03 corect).
- **Schema de legare la pământ:** nedeclarată, apare acum ca presupunere explicită („declarați TN-C-S / TN-S / TT").

## P0 — rămase / noi

1. **„N x MODEL", „N bucati MODEL" și „MODEL xN" pierd multiplicitatea: se desenează 1 invertor.** Paradoxal, „2 invertoare X" și „2 inv X" merg.
   - Exemple: „2 x SG110CX sungrow" (f03), „4 bucati SMA … 110 kW" (f05), „3 x Solis S5-GC100K + 1 x S5-GC50K" → 1 + 1 (f14), „SUN2000-30KTL-M3 x2" (f16), „2 x SUN2000-100KTL-M2 si BESS …" (f20, planșă verificată: un singur INV-1 la 200 kWp), „2 x Huawei …" (f28), „SH50T x2" (f21).
   - Singura plasă e întrebarea de raport c.c./c.a. Totuși planșa se generează cu jumătate din putere, iar QG, TC și C0 sunt subdimensionate. În f05 plasa ajunge la raport 4,55, iar la un kWp apropiat de ΣPn n-ar mai prinde nimic.
   - *Remediere:*
     - prefixele `\d+\s*[x×]\s*`, `\d+\s+(buc(ati)?|pcs)` și sufixul `[x×]\s*\d+` după cod;
     - curățat „x2" din `model`;
     - test de regresie pe toate cele 7 forme.
2. **Layout PT propriu imposibil topologic** (existent deja în r5, nesemnalat atunci). Afectează toate cazurile cu PT nou: f04, f07, f09, f22, f24, f27, f48, r5_04/09/16/32/39/40.
   - T1 20/0,4 kV e desenat **în interiorul carcasei TGD-CF**, sub TC + contor. Sub el, C0 (ex. f04: 4 × ACYABY 4×185 Al, 120 m, cablu de **0,4 kV**) merge la „PCC — rețea MT 20 kV".
   - Celula MT (separator de sarcină + siguranțe MT 25/40/63 A sau întreruptor + 50/51) apare numai în „Am presupus". Nu e desenată și nu apare în listă.
   - *Corect:* PCC MT → cablu MT → celulă trafo → T1 (în PT, în afara TGD) → legătura JT trafo–TGD-CF (aici e C0 de 120 m) → TGD-CF. Măsura se pune după ATR (MT sau JT).
3. **„PT nou" transformat în „TG existent alimentat din PT existent"** (f08: „cef 1,1 MWp – 8 inv x 125 kw, PT nou 1250 kVA, cablu 250 m pana la TGD").
   - „pana la TGD" e prins de regula de racord în TG existent. PT-ul nou (cel mai scump obiect al proiectului) dispare din planșă și din listă, iar nota 2 spune „PT-ul propriu existent … nu fac obiectul".
   - *Remediere:* „TGD" / „TGD-CF" nu înseamnă TG existent; „PT nou" are prioritate.
4. **CEF + TT cu 2 × 100 kW produce o planșă goală** (r5_42: „…SUN2000-100KTL-M2, retea TT, priza de pamant 4 ohm").
   - BL V34 „lipsește DDR pe C1 (amonte)", iar planșa are doar cartuș, legendă și note.
   - Nota 3 spune „TN-S" deși TT e declarat.
   - Același TT cu 1 invertor (f36) e corect, cu DDR 100 mA.
5. **Invertor hibrid cu baterie cuplată c.c., desenat ca BESS cuplat c.a. cu PCS fictiv:**
   - f21: „Sungrow SBH 20 kW" desenat ca PCS;
   - f38: SUN2000-10KTL-M1 + LUNA2000 10 kWh → „PCS Huawei LUNA2000 5 kW" + DDR-B + QB.
   - Topologia și lista de echipamente sunt false (aparate inexistente în ofertă). SH25T / Solis S6-EH sunt recunoscute ca hibrid, dar SH50T, SUN2000-M1 și „cuplaj c.c." scris explicit nu sunt.

## P1

6. **PT existent / PT al OD desenat ca trafo nou:**
   - „racord in PT existent 1000 kVA al beneficiarului" (f06) → T1 nou;
   - „celula JT a PT-ului existent 1000 kVA al OD conform ATR" (f33) → PT propriu nou + PCC MT.

   Se recunoaște doar forma „PT propriu … existent".
7. **Datele de string nu ajung la gPV:**
   - „16 module/string" (f02), „10 stringuri x 11" (f17), „string 18 module x 12 stringuri, Voc 49,6 V, Isc 13,9 A" (f19) și „10 mppt, 3 stringuri pe mppt" (f18) → se extrage doar n_paralel;
   - gPV declarat („gPV 20A pe fiecare string") nu apare pe planșă **în nicio planșă din 94**;
   - BL V07/V69 blochează exportul în loc să întrebe (6 cazuri).
8. **Contradicții încă neîntrebate:**
   - „TN-S si TT" → TN-S (f46);
   - „in TG existent si prin BMPT nou" → TG (f47);
   - prosumator „20 kW cu 2 invertoare de 15 kW" → 30 kW fără I08 (f45; la CEF aceeași formă dă I08);
   - „SUN2000-100KTL-M2 de 50 kW" → ia 50 kW și întreabă doar de raport (f44).
9. **Modele nerecunoscute** (refuz I02, cu întrebare: sigur, dar inutil):
   - „Fronius Tauro ECO 50-3-D", „SMA STP 110-60 / STP 50-41" (f10, f15);
   - „Symo 20 kW x2" → Σ 20 kW în mesaj (f35).
10. **V72 (Iac > Q branșament) există doar la prosumator.**
    - La CEF cu „BMPT 63 A existent" și Iac 63,5 A (f32) nu apare nimic.
    - La prosumator e doar AV (r5_25: 238 A > 200 A). Ar trebui întrebare (limitare sau ATR nou).
11. **Cablu impus „4x(1x240) Al"** (monopolare) nu e preluat (f06), doar materialul.

## P2

- **DDR 30 mA tip A** la invertoare de 20–30 kW cu c.c. mare (r5_22/24, f38, f40). Fișele Huawei/Sungrow cer ≥ 100/300 mA, deci declanșări intempestive. Trebuie aplicată pragul din fișă.
- **Nota 1 „branșament conform ST 4-JT / ST 3-JT (DEER)"** apare și la CEF cu PT propriu sau TG existent. V66 („racord JT doar direct din PT OD") e zgomot la racord în TG existent.
- **C0 „conform releveu / ATR"** nedimensionat când lungimea lipsește (f20, f21, r5_28). Ar trebui presupusă o lungime sau pusă întrebare.
- **Planșele cu 8–10 invertoare (A1):** jumătatea de jos e goală, iar textele sunt foarte mici (f08, f33). Lista e mutată în anexă .xlsx (ok).
- **„Categoria A RfG" la BESS standalone;** Smart Dongle / DTSU666-H / Logger1000 nu apar ca model la AR/EMS.
- **„PT existent 1000 kVA"** (f23): planșa e corectă, dar presupunerile listează „celulă trafo … siguranțe MT 63 A".
- **Raport c.c./c.a. 2,0** la prosumatorul hibrid (r5_24) nu e întrebat. La CEF se întreabă.

## Observații la planșe (avizare)

- **Bune, aș semna cu mici corecturi:**
  - r5_13 (3 invertoare mixte + LUNA2000);
  - r5_28 (prosumator 2 × 125 + PCS + EMS);
  - f30 (prosumator mixt, injecție zero);
  - f36 (TT, DDR 100 mA, cablu impus blocat corect);
  - f40 (30 kW, PI externă);
  - f25 (BESS standalone).
- **Nu trec de avizare:**
  - toate cele cu PT nou (P0-2);
  - f08 (PT dispărut);
  - f20 / f21 (jumătate din invertoare);
  - f21 / f38 (PCS fictiv);
  - r5_42 (goală).
