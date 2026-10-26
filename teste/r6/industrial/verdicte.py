"""Verdictele runda 6 (industrial) → fraze.json (fraze noi) și reverificare_r5.json."""
import json, pathlib
D = pathlib.Path(__file__).parent
V6 = {
1: ("P","P2","TG din PT 400 TN-S corect; sudura 3×25 kVA→22,5 kW; dar iluminatul hală iese pe 6 separatoare 3P cu fuzibil 16 A + CYABY 5×6 (nu MCB 1P B16), pod rulant nerecunoscut ca motor"),
2: ("G","P1","„iluminat 2 kw monofazat” face TOT tabloul monofazat; P TG=2 kW, Q1=16 A din „3 circ 16A”; prizele dispar; CYABY 5×25 impus nepreluat (doar Cu); Y/D pe motor 1~ → V12/V40 BLOCANT"),
3: ("G","P1","„8 circuite iluminat B10, 6 circuite prize… 2 prize trifazate 32A” → nicio plecare, Q1=16 A; V07 BLOCANT"),
4: ("P","P1","mono + origine tg_existent L25 corect, dar „4 circ”/„6 circ” nu se multiplică („Iluminat 4 circ” = o plecare); AC 3,5 kW pe ACYABY 3×35 Al, iluminat 10 A pe CYABY 3×10"),
5: ("G","P0","„alimentare din PT 250 kVA” devine PLECARE de 225 kW cu 3×400 A gG; cele 2 pompe softstarter dispar; Q1 = 500 A pe un trafo de 250 kVA (In 361 A) — fără blocant, se exportă"),
6: ("G","P0","supermarket → tip LOCUINȚĂ cu circuite de casă inventate (baie, boiler, centrală); iluminat 25 kW pe 1P+N B125 + CYY-F 3×50; chiller, frig, 10 circ. prize și TD-depozit pierdute; doar întrebare despre Pa"),
7: ("P","P1","3 CP→2,21 kW, 12 ventilatoare OK; „iluminat grajd 3 circuite” (fără putere) dispare fără mesaj; hrănitor 2,2 kW nerecunoscut ca motor; MCCB 16 A pe motoare de 0,75 kW"),
8: ("P","P2","2 motoare corecte (DOL 55 kW KM 95 A + releu; soft-starter 22 kW) dar ambele numite „Motor”; nicio verificare ΔU la pornirea DOL 55 kW pe sursă presupusă BMPT; sursa nu se întreabă"),
9: ("C","P2","TG din PT 1000 kVA, Q1 1600 A, 4 TD + compresor VFD corecte; Q1 1600 A desenat ca MCCB (uzual ACB)"),
10: ("G","P0","TG cu 3 plecări TT → schemă BRANȘAMENT BMPTd-100 cu TE generic; plecările dispar; în TT se desenează separarea PEN pe BN"),
11: ("P","P1","TT RA 50 + DDR pe plecări corect; rețeaua trifazată presupusă FĂRĂ întrebare și fără presupunere afișată (Σ 68 A)"),
12: ("C","—","TN-C → V27 BLOCANT cu explicație (PEN după DDR-ul BMPT); acceptabil"),
13: ("G","P0","„schema IT” ignorată tăcut → TN-C-S desenat, fără întrebare/refuz"),
14: ("C","—","origine PT fără kVA → întrebare; TN-C-S"),
15: ("G","P0","„TG alimentat din BMPT 3x63A, plecari: pompa, iluminat, prize” → schemă BRANȘAMENT (BMPTd-100) cu TE generic; plecările pierdute"),
16: ("C","—","sarcină mică: întreabă mono/tri („Rețeaua nu se presupune”) — reparat"),
17: ("P","P1","mono corect, aparataj 2P; dar iluminat 1,5 kW pe ACYABY 3×95 Al cu MCB B10 (absurd, nu intră în bornă); pompă căldură tratată ca motor DOL cu contactor"),
18: ("G","P1","„monofazat cu motor 7,5 kW trifazat” → fără I08; P=7,5 kW pe tablou, fără plecări, V07"),
19: ("G","P1","„TG trifazat cu plecări monofazate…” → rețea MONO, plecări pierdute, V07"),
20: ("G","P1","„230V … TD-1 63A 3P” nedetectat ca contradicție; TD-2 32 A devine Q1; TD-1 pe 3×(ACYABY 3×185); V40 BLOCANT"),
21: ("P","P1","cascadă cu paranteze și „;” corectă; motoare 30 / 18,5 kW DOL pe MCB C63/C40 (risc declanșare la pornire); TD-urile fără întreruptor-separator general de intrare"),
22: ("G","P1","cascada cu „->” și „cu …” → nicio plecare, P=5 kW, Q1=63 A, V07"),
23: ("P","P2","CYY-F 5×35 impus desenat ca CYABY 5×35; „server 16A cu UPS 10 kVA” → nume „server 16A cu UPS”, P din kVA (16 A ignorat)"),
24: ("G","P0","„PT zidit 2x630 kVA” → UN trafo 630; 2×800 A pe Q3 1000 A; doar V62 avertisment; se exportă"),
25: ("G","P1","PTAB 630 uscat cu celule + „baterie condensatoare 150 kvar” → tip CEF, refuz I02 „lipsesc invertoarele”"),
26: ("P","P1","PTA pe stâlp desenat cu celule MT de interior (celulă linie + CLP); „măsură JT directă” ignorată (pune TC 250/5) fără mesaj"),
27: ("P","P2","Scc 350 MVA ignorat (500 MVA presupus); TG 630 A > Q3 598 A → V40 BLOCANT (corect)"),
28: ("C","—","1250 kVA cu siguranțe MT → V61 BLOCANT cu explicație"),
29: ("G","P0","„6/0,4 kV” ignorat: PT desenat 20 kV, siguranțe 24 kV SF 40 A (la 6 kV ar fi ~100 A); fără mesaj"),
30: ("C","—","PT 400 + GE 150: întrebare explicită, GE 150 (nu 400), P 100 kW"),
31: ("P","P1","„sursa retea din BMPT 200A” → sursă TGD, QR 160 A în loc de 200 A; „cablu GE 25 m” ignorat (20 m implicit)"),
32: ("C","—","GE 80 / PT 400 / P 55 / L 20 — toate preluate"),
33: ("G","P0","„GE 40 kVA monofazat” → GE trifazat 3P+N, ATS 4P; fără întrebare"),
34: ("G","P1","GE în paralel cu rețeaua (sincronizare) → desenează ATS (comutare), întreabă doar sursa; trebuia refuz (în afara domeniului)"),
35: ("P","P1","P 97,5 kW corect, dar pornirea Y/D și cele 3 receptoare se pierd („Consumatori”); pompele de incendiu trec prin DDR-G 300 mA"),
36: ("C","—","Sn GE lipsă → I02"),
37: ("P","P2","sarcina lipsă: Ib = In GE presupus, fără întrebare"),
38: ("G","P1","„2x(NA2XY 4x240)” → se pierde „2x”: 1×240 la 400 A → V02/V03 BLOCANT fals"),
39: ("G","P1","cabluri impuse per plecare → plecările dispar, primul calibru devine Q1, cablul 5×10 merge pe coloană; V07"),
40: ("P","P1","„TD-1 100A cu cablu 4x16 Cu” → cablul impus e pus pe COLOANĂ (5×16), TD-1 primește 2×(4×120 Cu); blocant, dar pe cablul greșit"),
41: ("G","P1","„TN-S si TT” nedetectat; TN-S ales tăcut (întreabă doar mono/tri)"),
42: ("C","—","plecare 1600 A pe PT 630 → V40 BLOCANT"),
43: ("C","—","I05 3 vs 4"),
44: ("P","P2","„monofazat 3x400V” → I02 în loc de I08 (refuză oricum)"),
45: ("G","P0","„TG din BMPT 100A plecari TD-1 125A” → schemă BRANȘAMENT; TD-1 125 > 100 nesemnalat"),
46: ("C","—","V86"),
47: ("G","P0","„din PT propriu si din BMPT” (2 surse) → BRANȘAMENT BMPTd-100, fără întrebare"),
48: ("G","P1","format „125 a/60 m” + „sursa tgd exist.” → plecările dispar, Q1 = 125 A, L col = 60; V07"),
49: ("G","P1","„3 x TD 63A (TD-1..TD-3) + 2 x pompa 7,5kW” → o plecare „3 x TD 63A” goală; V07"),
50: ("G","P1","„3x400V” citit ca secțiune → cablu impus 400 mm² (V13 BLOCANT); CYABY 5×16 pierdut"),
51: ("G","P1","„8 circuite: 3 iluminat 10A, 4 prize 16A, 1 boiler 2kW” → nicio plecare, Q1 10 A; V07"),
52: ("G","P1","TG + „baterie condensatoare 120 kvar” → tip CEF, refuz I02 invertoare"),
53: ("G","P0","TG 125 A cu 2 încărcătoare EV + iluminat → BRANȘAMENT BMPTi-250, TE generic, P=22 kW; EV (DDR tip B / 6 mA c.c.) pierdute"),
54: ("G","P1","„TN-S din PT 1600 kVA” devine plecare de 1440 kW (ACB 2500 A), TD-1/TD-2 pierdute, TD-1 400 A → Q1; V40 BLOCANT"),
}
V5 = {i: ("C", "—", "") for i in range(1, 55)}
V5.update({
2: ("P","P2","CYABY cerut → CYY-F (pe pat E); plecări L 50 presupus"),
4: ("P","P2","6 plecări corecte; liftul primește contactor+releu termic în TG (are tablou propriu)"),
12: ("P","P1","cascadă OK; motor 18,5 kW DOL pe MCB C40 (Ip 7·31 A ≈ 220 A în zona magnetică C)"),
14: ("P","P2","multiplicatori reparați; iluminatul tot pe separatoare 3P cu fuzibil (nu MCB B 1P)"),
17: ("G","P2","„1 000 m” → tot I03 „Valoarea 1 nu are unitate”, plecare „TD-1 63A”"),
18: ("P","P2","2500 m → 4×(4×240 Al) pentru 63 A, doar avertisment V09"),
31: ("P","P2","QR 125 preluat; sursa rețelei presupusă BMPT fără întrebare (marcată PRESUPUS)"),
32: ("P","P1","P 73 kW corect; consumatorii vitali nu devin plecări; pompele incendiu pe DDR-G 300 mA"),
43: ("P","P2","listă parsată; ventilatoare 1,1 kW pe MCCB 16 A + releu; hrănire nerecunoscută ca motor"),
50: ("P","P2","P 35 kW corect; consumatorii nu devin plecări"),
52: ("P","P2","origine PT + cablu impus 3×185+95 preluate; V25 BLOCANT pe nul redus (conservator)"),
})
for tag, V, fn in (("r6", V6, "fraze.json"), ("r5", V5, "reverificare_r5.json")):
    R = json.load(open(D / f"rezultat_{tag}.json"))
    out = []
    for x in R:
        v, g, o = V[x["nr"]]
        x.update(verdict={"C": "corect", "P": "parțial", "G": "greșit"}[v], gravitate=g, obtinut=o or "conform așteptării",
                 plansa=f"png/{tag}_{x['nr']:02d}.png" if x.get("model") else None)
        out.append(x)
    json.dump(out, open(D / fn, "w"), ensure_ascii=False, indent=1, default=str)
    from collections import Counter
    print(tag, Counter(V[k][0] for k in V), Counter(V[k][1] for k in V if V[k][0] != "C"))
