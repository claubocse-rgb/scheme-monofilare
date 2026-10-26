# Runda 5 — rol „locuinte” (branșamente, case/apartamente, tablouri de locuință, prosumatori mici)

**Scor: 5/10.** Tabloul de locuință (receptori cu kW/m, TT/RA, întrebarea despre rețea) și branșamentele simple funcționează bine.
Prosumatorii pe case și câteva formulări uzuale („pompa caldura”, „kVA”, „Pi/Pa”, „mono” scris lângă un receptor) duc la scheme greșite.

**Statistici:** 58 de fraze (48 planificate + 10 sonde). **Corect 26 · parțial 18 · greșit 14.**
Am randat și am inspectat 14 planșe: L02, L06, L07, L16, L17, L18, L23, L26, L27, L29, L30, L35, L42, L45.
Fișiere: `teste/r5/locuinte/fraze.json` (toate frazele, intrarea fizică, rezultatul motorului și verdictul), `planse/*.svg|png`, `run.py`, `fraze_in.py`.
Am verificat și prin API (`/api/chat`, port 8801), pe L30: rezultat identic cu `interpreteaza_local`.

## P0 — greșit tehnic / periculos

1. **Prosumatorul pe casă devine branșament (consum).**
   - L26 „prosumator casa 5 kW invertor monofazat, bransament mono 7 kW” → tip `bransament`, P = 5 kW (puterea invertorului luată drept consum).
   - L28 „prosumator pe casa, 8 kW, cablu 25 m pana la BMPT” → branșament de 8 kW.
   - Cauza: în `detecteaza_tip`, ordinea BMPM > branșament > prosumator. Cuvântul „prosumator” trebuie să aibă prioritate față de „bransament/BMPT”.
   - Remediere: prosumator înaintea branșamentului; „bransament … X kW” → P aprobată sau Q, iar invertorul se ia din „invertor”.
2. **Instalațiile PV de casă fără cuvântul „prosumator” devin CEF.**
   - L30 „panouri pe casa 3 kWp, invertor 3 kW mono” → CEF cu invertor **trifazat** („mono” ignorat), MCCB 16 A cu PI externă pe bobină, TC 50/5 cu măsură semidirectă, SPD T1+T2. Planșa e absurdă pentru 3 kW.
   - L31 „casa P+1 tri 15 kW + fotovoltaic 10 kW” → CEF cu invertor de 15 kW (puterea casei); cei 10 kW sunt pierduți, rețeaua = None.
   - Remediere: casă/locuință + PV ≤ 15 kW (sau ≤ 400 kW fără PT) → `prosumator`. La CEF/prosumator, rețeaua se ia din `retea_declarata`.
3. **„22 kVA” la o casă dă tip PT.** L37 „Casa P+1 trifazat 22 kVA, coloana 30m” → post trafo de 100 kVA plus întrebarea „Confirmați 100 kVA?”.
   - Remediere: la locuință/branșament, kVA înseamnă puterea S a branșamentului. Regula „kVA ⇒ PT” se aplică doar fără context de casă sau la valori ≥ 100 kVA.
4. **Pompa de căldură scrisă fără „de” e ignorată în tăcere.**
   - L08 „pompa caldura 8 kW”, L47 „pompa caldura 3 kW monofazata”, E02 „PC aer-apa 9kW”: receptorul dispare din tablou.
   - E01 „pompa caldura 6 kw, 7 kw aprobat”: pompa dispare **și** P aprobată = 6 kW (puterea pompei).
   - Remediere: regexul `pomp\w*\s+(?:de\s+)?caldur\w*|\bpc\s+aer|aer[- ]apa`. Un kW rămas lângă un receptor nerecunoscut → întrebare, nu P aprobată.
5. **Contradicția de rețea se rezolvă în tăcere.** L15 „casa monofazata cu pompa de caldura trifazata 10 kW” → rețea `tri`, fără I08 (`tri` are prioritate față de `mono_decl` în `extrage_locuinta`).
   - Remediere: „mono…” declarat pentru casă + „trifazat” la un receptor → I08 (codul există deja, dar se aplică doar dacă rețeaua a ieșit mono).
6. **Pi luat drept P aprobată.** L46 „Pi 18 kW, Pa 8 kW” → P aprobată = 18 kW, de unde Ib 82 A și BLOCANT.
   - Remediere: „Pa / P aprobat” au prioritate; „Pi / instalat” → `Pi_kW`, informativ.
7. **Prosumator cu baterie: topologie greșită pe planșă (L27).** Bateria e desenată în serie pe linia c.c. PV → separator → BAT → INV.
   - Lipsesc portul de baterie separat și protecția c.c. a bateriei (siguranță sau întreruptor c.c.). Nu aș semna planșa.

## P1 — important

8. **Prosumator: datele ATR se pierd.** „P aprobată”, „P evacuată” și „coloana X m” (L27, L29, L32, L33) nu ajung la motor.
   - Lungimea invertorului rămâne implicit 15 m.
   - Lipsește verificarea Pn invertor ≤ P aprobată/evacuată.
   - Remediere: mapare către `L_inv_m`, `In_Q_bransament_A` și un câmp nou de P aprobată pentru V72.
9. **Q-ul declarat la branșament e ignorat când există și kW.** L01 „P aprobata 7 kW, Q bransament 32A” → Q 40 A.
   - În plus, 7 kW mono → Q 40 A (L18) și 25 kW tri → Q 50 A în BMPTd-100 (L17), din cauza cosφ 0,9. Uzual, din ATR, sunt 32 A și 40 A.
10. **Setul tipic ajunge să blocheze aproape orice casă.** Setul presupus adaugă plită 7,2 kW, cuptor 3,5 kW, boiler și centrală. Împreună cu Q presupus din Pa, rezultă V46 BLOCANT la 13 fraze simple (L03, L06, L07, L09, L36…).
    - „plita gaz” (E03) și „fara plita electrica, fara cuptor” (E04) adaugă totuși plită și cuptor electrice.
    - Remediere:
      - negația și „gaz” trebuie respectate;
      - plita și cuptorul intră în setul tipic doar dacă sunt numite;
      - la Q presupus, BLOCANT-ul devine AVERTISMENT cu întrebare.
11. **„monofazată” la receptor e ignorat la rețea tri.** L42: VE 7,4 kW monofazată → 3F, 5×4, C20. Wallbox-ul de 7,4 kW e 1F 32 A.
12. **Multiplicatorii se pierd:** „3 aparate AC”, „2 băi cu boiler … fiecare”, „3 circuite prize de 16A”, „5 circuite prize”, „mas spalat vase” (L10, L35, L40, E05).
13. **Branșament nou, puterea cerută depășită de Pc fără semnalare (L04).** La 25 kW s-a ales BMPTd-100 cu Q 80 A, dar V46 spune „Ib se ia din puterea aprobată”.
    - Mesajul trebuie corectat; Pc > P cerută → întrebare.
14. **DDR-urile alese de aplicație avertizează împotriva propriilor alegeri.**
    - RCCB 300 mA tip AC în BMPT în amonte de VE cu DDR tip B (V43).
    - RCBO 300 mA instantaneu în BMPM, neselectiv cu DDR-urile de 30 mA, la fiecare casă mono.
    - Remediere: alegerea implicită să fie tip A/S (selectiv).

**P2:**
- nota greșită „Saună 6 kW > 7,4 kW” (L43);
- „întrerupător general 32A” luat drept Q branșament (L12);
- presupunerile vorbesc despre „BMPT” când rețeaua e nedeclarată (L05, L48);
- Ik3 OD implicit de 25 kA produce avertismente V33 la case;
- planșa L06 e comprimată în jumătatea de sus, iar textul din lista de echipamente (poz. 15) e ilizibil;
- L27: etichetele „SB”/„PE” sunt duplicate, iar casetele „Receptoare fixe”/„Forță 3F” se suprapun.
