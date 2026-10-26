"""verificari.py — catalogul de verificări V01…V90 (SPEC §D): coduri, niveluri, mesaje în română și remedieri.

Fiecare rezultat are forma {cod, nivel, obiect, mesaj, remediere}. Mesajele se construiesc din șabloanele de mai jos,
cu numerele formatate românește (`texte.fmt_ro`, SPEC §E.2).
"""
from .texte import fmt_ro, curata_text

BLOCANT, AVERTISMENT, INFO = "BLOCANT", "AVERTISMENT", "INFO"

# cod → (descriere, {varianta: șablon mesaj}, remediere)  — SPEC §D, tabelul catalogului
CATALOG = {
    "V01": ("Cablu nedimensionabil",
            {"": "{obiect}: nicio secțiune ≤ 240 mm² × 4 în paralel (nici 6 sisteme monopolare Cu XLPE ≤ 300 mm², metoda F) "
                 "nu satisface Iz' ≥ {Iz_min} A"},
            "bare capsulate, alt punct de racord sau împărțirea sarcinii"),
    "V02": ("Ip > Iz' (secțiune impusă)",
            {"": "{obiect}: Ip = {Ip} A > Iz' = {Iz} A (Ib ≤ In ≤ Iz' încălcat)"},
            "mărirea secțiunii sau reducerea calibrului"),
    "V03": ("I2 > 1,45·Iz'", {"": "{obiect}: I2 = {I2} A > 1,45·Iz' = {lim} A"},
            "mărirea secțiunii sau reducerea calibrului"),
    "V04": ("Ib > Ip (calibru impus)", {"": "{obiect}: Ib = {Ib} A > protecție {Ip} A",
                                         "atr": "{obiect}: P = {P} kW cu Q {Ip} A — perechea ATR (Pa = U·In, cosφ 1: "
                                                "Ib = {Iatr} A ≤ {Ip} A); la cosφ {cos} Ib = {Ib} A > {Ip} A, dar ≤ "
                                                "1,13·In = {lim} A (nu declanșează convențional) — fără rezervă"},
            "calibru mai mare"),
    "V05": ("Calibru inexistent",
            {"": "{obiect}: calibrul {In} A nu există în seria {tip}",
             "trafo": "{obiect}: Sn = {Sn} kVA nu există în seria standard de transformatoare"},
            "alegeți din serie: {vecini}"),
    "V06": ("Ib > In maxim", {"": "{obiect}: Ib = {Ib} A depășește calibrul maxim / impus ({tip})"},
            "împărțirea sarcinii sau alt nivel de tensiune"),
    "V07": ("P absentă/≤ 0 / date de intrare invalide",
            {"": "{obiect}: P = {P} kW ≤ 0", "lipsa": "{obiect}: lipsește puterea (kW) sau calibrul (A)",
             "tip": "{obiect}: tip de schemă necunoscut ({tip}) — se acceptă: {acceptate}",
             "plecari": "{obiect}: {tablou} fără nicio plecare — nu există ce dimensiona",
             "param": "{obiect}: {camp} = {x} — {conditie}",
             "intern": "{obiect}: date de intrare incomplete sau invalide ({detaliu})",
             "string_generic": "{obiect}: stringurile nu sunt descrise (module / string, stringuri / MPPT) — câmpul PV e "
                               "desenat generic „conform proiect DC”; Voc(Tmin), SPD c.c. și gPV de verificat în "
                               "proiectul de c.c."},
            "introduceți puterea / valori numerice plauzibile"),
    "V08": ("cosφ absurd", {"B": "{obiect}: cosφ = {x} în afara intervalului (0; 1]",
                            "AV": "{obiect}: cosφ = {x} < 0,7 — verificați datele"}, "0,9 uzual"),
    "V09": ("Lungime absurdă", {"B": "{obiect}: lungime {L} m ≤ 0", "AV": "{obiect}: lungime {L} m > 1000 m — verificați datele"},
            "verificați lungimea traseului"),
    "V10": ("Pozare în afara tabelelor", {"": "{obiect}: {parametru} în afara tab. {tabel}"},
            "studiu termic dedicat"),
    "V11": ("Valoare implicită folosită", {"": "Am presupus: {lista}"}, ""),
    "V12": ("Rețea inconsistentă / date contradictorii",
            {"": "{obiect}: aparat {poli} pe rețea {retea}",
             "necunoscut": "{obiect}: câmpul „{camp}” nu este cunoscut și a fost ignorat (câmpuri acceptate: {acceptate})",
             "ddr_s": "{obiect}: DDR {IdN} mA de tip S (selectiv) nu există — tipul S se fabrică de la 100 mA",
             "retea": "{obiect}: rețea „{retea}” necunoscută — se acceptă numai „tri” (3 × 400/230 V) sau „mono” (230 V)",
             "camp": "{obiect}: valoarea „{valoare}” a câmpului {camp} nu este acceptată",
             "surse": "{obiect}: mai multe surse de putere în aceeași intrare ({surse}) — se acceptă una singură",
             "contradictie": "{obiect}: date contradictorii — {detaliu}",
             "limita": "{obiect}: R_limita_ohm = {x} Ω > limita normată {lim} Ω ({motiv}) — limita normată nu poate "
                       "fi ridicată (se poate doar coborî)"},
            "aparat cu numărul corect de poli / o singură sursă de putere (P_kW, S_kVA sau Ib_A)"),
    "V13": ("Secțiune inexistentă / nepermisă", {"": "{obiect}: secțiunea {S} mm² {mat} nu există / nu e permisă",
                                                  "loc": "{obiect}: secțiunea impusă {S} mm² < minimul {Smin} mm² pentru "
                                                         "{rec} ({sursa})"},
            "Cu sau Al ≥ 16 mm²"),
    "V15": ("Date de scurtcircuit inconsistente",
            {"": "{obiect}: Ik1min {ik1} A > Ik3max {ik3} A — impedanțele introduse sunt incoerente"},
            "verificați Ik3 OD și impedanța buclei din ATR (|Zbuclă| ≥ 2·|Z_Q|)"),
    "V14": ("P declarată < bilanț",
            {"": "P declarată {P} kW < Pc din bilanț {Pc} kW — se folosește P declarată (Pa din ATR)"},
            "ATR nou sau ks justificat"),
    "V20": ("ΔU peste I7 (receptor final / bara tabloului / invertor)",
            {"": "{obiect}: ΔU cumulat {x} % > {lim} %",
             "bara": "{obiect}: ΔU cumulat la bara tabloului {x} % > {lim} % (limita I7 pentru forță){detaliu} — niciun "
                     "receptor din aval nu se mai poate încadra",
             "inv": "{obiect}: ΔU pe cablul invertorului {x} % > {lim} %{detaliu} — invertorul declanșează la "
                    "supratensiune"},
            "secțiune mai mare / cabluri în paralel / mutarea tabloului"),
    "V21": ("ΔU la bara tabloului / CEF", {"": "{obiect}: ΔU cumulat {x} % > {lim} %"},
            "secțiune mai mare sau rezervă mai mică pentru circuitele finale"),
    "V22": ("ΔU la pornire motor", {"": "{obiect}: ΔU la pornire directă {x} % > {lim} % (Ip = {k}·Ib, cosφ 0,35)"},
            "soft-starter / VFD / stea-triunghi, secțiune mai mare"),
    "V23": ("Protecție motor la pornirea directă",
            {"INFO": "{obiect}: calibru ales pentru pornirea directă: {prot} suportă Ip = {Ip} A ({t} s)",
             "AV": "{obiect}: {prot} poate declanșa la pornirea directă (Ip ≈ {Ip} A, {t} s; prag {prag} A)"},
            "calibru mai mare, siguranțe aM + releu termic, întreruptor-motor sau MCCB"),
    "V24": ("Protecția neutrului (h3 > 33 %)",
            {"": "{obiect}: armonica 3 = {h3} % > 33 % — curentul din neutru depășește curentul de fază: detecția "
                 "supracurentului în neutru, aparat 4P cu N protejat (SR HD 60364-4-43 art. 431.2.3)"},
            "aparat 4P cu protecția neutrului (4P4D / reglaj N = 100…160 %)"),
    "V25": ("Neutru subdimensionat", {"": "{obiect}: neutru redus {N} mm² nepermis ({motiv}) — N = {S} mm²"}, "N = S"),
    "V26": ("PE sub tab. 54.2", {"": "{obiect}: PE {S_PE} mm² < {S_tab} mm² (SR HD 60364-5-54 tab. 54.2)"},
            "PE mai mare"),
    "V27": ("PEN incorect", {"": "{obiect}: PEN {detaliu}"}, "separarea N/PE înainte de DDR"),
    "V28": ("Schemă de legare la pământ neacoperită",
            {"": "{obiect}: schema de legare la pământ „{spl}” nu este acoperită pentru {tip} (acceptate: {acceptate}) — "
                 "calculul nu se face"},
            "TN-C-S / TN-S (sau TT la branșament / tablou / prosumator / CEF fără PT)"),
    "V29": ("Circuit de prize fără DDR 30 mA",
            {"B": "{obiect}: circuit de prize In {In} A ≤ 32 A fără DDR 30 mA (SR HD 60364-4-41 art. 411.3.3)",
             "INFO": "{obiect}: circuit de prize In {In} A ≤ 32 A → DDR 30 mA tip A adăugat automat "
                     "(SR HD 60364-4-41 art. 411.3.3)"},
            "DDR 30 mA tip A (RCBO sau RCCB pe grup)"),
    "V30": ("Deconectare automată TN",
            {"INFO": "{obiect}: deconectare automată îndeplinită: Ik1min {ik1} A ≥ Ia {ia} A ({t} s)",
             "INFO_marit": "{obiect}: secțiune mărită la {S} mm² pentru deconectare: Ik1min {ik1} A ≥ Ia {ia} A",
             "B": "{obiect}: deconectare automată neîndeplinită: Ik1min {ik1} A < Ia {ia} A",
             "AV": "{obiect}: Ia pentru {prot} la {t} s nu este tabelat — verificați curba producătorului",
             "TT": "{obiect}: TT — protecția la defect (contact indirect) prin {ddr}: RA·IΔn = {x} V (≤ 50 V cerut, "
                   "SR HD 60364-4-41 art. 411.5.3); MCB-ul nu asigură deconectarea la defect prin pământ. Scurtcircuit "
                   "fază–nul la capăt: Ik1 {ik1} A ≥ Ia {ia} A (protecție la scurtcircuit prin MCB)",
             "TT_AV": "{obiect}: TT — protecția la defect (contact indirect) prin {ddr}: RA·IΔn = {x} V (≤ 50 V cerut, "
                      "SR HD 60364-4-41 art. 411.5.3). Scurtcircuit fază–nul la capăt: Ik1 {ik1} A < Ia {ia} A — "
                      "MCB-ul deconectează pe zona termică; verificați stabilitatea termică / curba B"},
            "secțiune mai mare, curbă B, Isd mai mic sau DDR"),
    "V31": ("Deconectare prin DDR",
            {"INFO": "{obiect}: Ik1min {ik1} A < Ia {ia} A — deconectarea se asigură prin DDR propriu (Zs·IΔn ≤ U0)",
             "AV": "{obiect}: Ik1min {ik1} A < Ia {ia} A — deconectarea se bazează pe DDR din amonte "
                   "(un defect pe plecare deconectează toată instalația)"},
            "DDR pe plecare"),
    "V32": ("Deconectare nesigură, Zb implicit",
            {"": "{obiect}: Ik1min {ik1} A < Ia {ia} A cu impedanța OD IMPLICITĂ — cereți valoarea reală"},
            "cerere către OD pentru impedanța buclei la punctul de delimitare"),
    "V33": ("Icu insuficient",
            {"": "{obiect}: Icu {icu} kA < Ik3max {ik3} kA la bara aparatului",
             "rezerva": "{obiect}: Icu {icu} kA < Ik3max {ik3} kA — protecție de rezervă gG în amonte; "
                        "confirmați combinația în tabelele de coordonare ale producătorului",
             "bmpt": "{obiect}: Icn {icu} kA < Ik3max {ik3} kA — SF 50 kA în amonte (ST 4-JT / ST 3-JT)",
             "ok": "{obiect}: Icu {icu} kA ≥ Ik3max {ik3} kA",
             "nedecl": "{obiect}: Icu nedeclarat — trebuie ≥ Ik3max {ik3} kA la bara TG existent",
             "cond": "{obiect}: {aparat} — capacitate condiționată {icu} kA ≥ Ik3max {ik3} kA la bara TE (cu protecția din "
                     "amonte: {amonte})",
             "cond_AV": "{obiect}: {aparat} — Ik3max {ik3} kA la bara TE > {icu} kA (capacitatea condiționată uzuală) — "
                        "confirmați coordonarea cu {amonte} în tabelele producătorului"},
            "Icu mai mare"),
    "V34": ("TT neconform", {"": "TT: RA·IΔn = {RA}·{IdN} = {x} V > 50 V", "lipsa": "TT: lipsește DDR pe {obiect}",
                             "amonte": "TT: DDR din amonte (originea alimentării) IΔn {IdN} mA: RA·IΔn = {RA}·{IdN}/1000 = "
                                       "{x} V > 50 V — segmentul C1 (până la primul DDR al tabloului) nu e protejat",
                             "ra": "TT: RA nedeclarat — s-a presupus {RA} Ω; introduceți rezistența măsurată a prizei "
                                   "de pământ (valoarea implicită e neconservatoare)",
                             "cef_amonte": "TT: racord fără BMPT și fără DDR declarat în amonte — QG are bloc diferențial "
                                           "reglabil, dar segmentul C0 dintre QG și punctul de racord nu e protejat "
                                           "diferențial: DDR la originea alimentării conform ATR (declarați "
                                           "IdN_amonte_mA) sau C0 cu izolație dublă / clasa II"},
            "priză de pământ mai bună sau DDR 100/30 mA în amonte (la originea alimentării) — declarați IdN_amonte_mA"),
    "V35": ("Stabilitate termică fază",
            {"B": "{obiect}: fază {n}×{S} mm² < {x} mm² la Ik3max",
             "AV": "{obiect}: fază {n}×{S} mm² < {x} mm² la Ik3max IMPLICIT {ik3} kA — introduceți Ik3 real sau I²t producător",
             "INFO": "{obiect}: stabilitate termică fază asigurată ({detaliu})",
             "INFO_marit": "{obiect}: secțiune mărită la {n}×{S} mm² pentru stabilitatea termică (necesar {x} mm²)"},
            "secțiune mai mare sau I²t din fișa producătorului"),
    "V36": ("Stabilitate termică PE",
            {"B": "{obiect}: PE {S} mm² < {x} mm² necesar la scurtcircuit (k²S² < I²t)",
             "AV": "{obiect}: PE {S} mm² < {x} mm² la Ik3max IMPLICIT — introduceți Ik3 real sau I²t producător",
             "INFO": "{obiect}: stabilitate termică PE asigurată (S ≥ {x} mm²)",
             "INFO_marit": "{obiect}: PE mărit la conductor separat FY 1×{S} mm² (necesar {x} mm² la scurtcircuit)",
             "INFO_cablu": "{obiect}: cablu mărit la {S} mm² cu PE în cablu (necesar {x} mm² la scurtcircuit)"},
            "PE mai mare"),
    "V37": ("Priză de pământ (v1.3)",
            {"INFO": "{obiect}: Rp = {Rp} Ω ≤ {lim} Ω ({n} electrozi × {L} m{Lp}, ρ = {rho} Ω·m, ψ = {psi})",
             "INFO_marit": "{obiect}: cu n = {n0} electrozi Rp = {Rp0} Ω > {lim} Ω → necesar n = {n} electrozi: Rp = {Rp} Ω ≤ "
                           "{lim} Ω ({n} electrozi × {L} m{Lp})",
             "B": "{obiect}: Rp = {Rp} Ω > {lim} Ω chiar cu {n} electrozi × {L} m în linie{Lp} (ρ = {rho} Ω·m, "
                  "ψ = {psi}) — priza nu se poate realiza în configurația de calcul"},
            "măsurați ρ; electrozi mai lungi / priză de adâncime, contur închis, tratarea solului sau priză comună"),
    "V43": ("Selectivitate DDR în serie (v1.3)",
            {"INFO": "{obiect}: selectivitate DDR realizată: {am} {IdN_am} mA{S_am} → {av} {IdN_av} mA{S_av} "
                     "(IΔn amonte ≥ 3·IΔn aval, Δt ≥ 0,15 s)",
             "AV": "{obiect}: selectivitate DDR nerealizată: {am} {IdN_am} mA{S_am} → {av} {IdN_av} mA{S_av} ({motiv}) "
                   "— un defect în aval poate deconecta și DDR-ul din amonte",
             "egal": "{obiect}: {am} și {av} au același IΔn = {IdN_am} mA și aceeași temporizare ({T_am}) — nu există "
                     "selectivitate (declanșează amândouă la orice defect în aval)",
             "TT": "{obiect}: selectivitate DDR nerealizată în TT: {am} {IdN_am} mA{S_am} → {av} {IdN_av} mA{S_av} — "
                   "RA = {RA} Ω limitează IΔn la ≤ {lim} mA (RA·IΔn ≤ 50 V), iar seria 300/100/30 mA nu mai oferă o "
                   "treaptă aval ≤ IΔn amonte/3",
             "ve_dc": "{obiect}: circuitul VE ({av}, DDR tip {tip_av}) e în aval de {am} {IdN_am} mA tip {tip_am} — un "
                      "curent de defect c.c. neted al stației de încărcare poate „orbi” DDR-ul din amonte (SR HD "
                      "60364-5-53:2015 art. 531.3.2, IEC 60364-7-722:2018 art. 722.531.3.101){detaliu}"},
            "{rem}"),
    "V44": ("Racord CEF în TG existent (v1.3)",
            {"B": "{obiect}: Ip {x} A < Σ Iac {y} A — protecția din TG declanșează la injecția CEF",
             "iz": "{obiect}: Ip Q TG {x} A > Iz' C0 {iz} A — C0 e protejat la suprasarcină doar de QG (curentul vine din "
                   "invertoare); TGD-CF nu trebuie să alimenteze consumatori",
             "INFO": "{obiect}: Ip Q TG {x} A ≤ Iz' C0 {iz} A",
             "deconectare": "{obiect}: defect la capătul C0 (bara TGD-CF): Ik1min {ik1} A < Ia(Q TG, 5 s) {ia} A — "
                            "nu e deconectat de protecția din TG"},
            "calibru Q TG între Σ Iac și Iz' C0, secțiune C0 mai mare sau DDR pe plecarea din TG"),
    "V46": ("Putere locuință peste branșament / ATR (v1.4)",
            {"pc": "{obiect}: Pc din bilanț {Pc} kW > puterea aprobată (ATR) {P} kW — Pc din ks e informativ; Ib general "
                   "se ia din puterea aprobată",
             "ib": "{obiect}: Ib de calcul pe {faza} {Ib} A > 1,13·In Q branșament = {lim} A (In {In} A) — Q-ul de "
                   "branșament declanșează la sarcina de calcul",
             "cont": "{obiect}: Ib de calcul pe {faza} {Ib} A > In Q branșament {In} A, iar faza alimentează sarcini "
                     "continue ({cont} A: VE / pompă de căldură / saună / încălzire) — curentul rămâne peste In ore în "
                     "șir, Q declanșează",
             "av": "{obiect}: Ib de calcul pe {faza} {Ib} A > In Q branșament {In} A — sub 1,13·In = {lim} A nu "
                   "declanșează convențional (SR EN 60898-1), fără rezervă de exploatare",
             "pa": "{obiect}: puterea aprobată {P} kW → Ib {Ib} A > 1,13·In Q branșament = {lim} A — datele ATR "
                   "(P aprobată / Q) sunt incoerente",
             "bloc": "{obiect}: Q branșament nedeclarat — Ib {Ib} A cere un Q peste limita blocului {bloc} ({lim} A)",
             "q_pres": "{obiect}: Q branșament existent nedeclarat — presupus {Q} A (calibrul standard ≥ Ib {Ib} A{baza}); "
                       "se completează din ATR / certificatul de racordare",
             "pc_nou": "{obiect}: Pc din bilanț {Pc} kW > puterea cerută pentru branșamentul nou {P} kW — Q ales pe "
                       "puterea cerută; ATR pentru {Pc} kW sau simultaneitate confirmată?",
             "pa_pres": "{obiect}: puterea aprobată (ATR) nedeclarată — presupusă din bilanț, Pc {Pc} kW (Ib {Ib} A); "
                        "se completează din ATR / certificatul de racordare"},
            "{rem}"),
    "V47": ("Dezechilibru între faze (v1.4)",
            {"": "{obiect}: dezechilibru {x} % > {lim} % (Imax − Imed)/Imed"},
            "mută circuite monofazate pe faza cea mai puțin încărcată (câmpul „faza”) sau folosește receptoare trifazate"),
    "V49": ("DDR obligatoriu refuzat (v1.4)",
            {"": "{obiect}: circuitul „{rec}” al unei locuințe trebuie protejat de DDR 30 mA (SR HD 60364-4-41 art. "
                 "411.3.3 / 411.3.4, -7-701, -7-722)",
             "idn": "{obiect}: DDR impus IΔn {IdN} mA > 30 mA pe circuitul „{rec}” — în locuințe toate circuitele finale "
                    "au DDR ≤ 30 mA (SR HD 60364-4-41:2017 art. 411.3.3, -7-701)",
             "ve_tip": "{obiect}: DDR impus tip {tip} pe circuitul VE — admis numai dacă stația de încărcare are detecție "
                       "c.c. 6 mA (RDC-DD, SR HD 60364-7-722); altfel DDR tip B",
             "tip_ac": "{obiect}: DDR tip AC pe circuitul „{rec}” — practica actuală (SR HD 60364-5-53) cere minimum tip A "
                       "pentru circuitele finale ale locuinței"},
            "DDR 30 mA (VE: tip B sau A-EV + RDC-DD 6 mA c.c.)"),
    "V40": ("Amonte < aval", {"": "{obiect}: amonte {a} A < aval {b} A",
                              "loc": "{obiect}: {aparat} In {b} A > In Q branșament {a} A — aparatul nu poate fi selectiv, "
                                     "iar Q branșament declanșează înaintea lui"},
            "calibru amonte mai mare"),
    "V41": ("Amonte = aval / raport < 1,6",
            {"raport": "{obiect}: raport Ip amonte/aval {r} < 1,6 — selectivitate nesigură la suprasarcină",
             "egal": "{obiect}: amonte = aval = {a} A — fără selectivitate",
             "bmpt": "{obiect}: coordonare SF–Q fixată prin ST 4-JT / ST 3-JT (SF aparține OD)",
             "un_generator": "{obiect}: QG și protecția unicului invertor / PCS ({a} A / {b} A) sunt în serie pe același "
                             "curent de injecție — selectivitatea între ele nu e necesară (un singur generator)",
             "pt_serie": "{obiect}: QG (Ir {a} A) și Q JT (Ir {b} A) în serie pe legătura C0 — selectivitate prin "
                         "temporizare: tsd Q JT = {t} s > tsd QG",
             "gg": "{obiect}: raport gG amonte/aval {r} < 1,6 (SR EN 60269-2)",
             "inversat": "{obiect}: Ir QG {a} A > Ir Q JT {b} A (Q JT al trafo reglat cel mult {lim} A = {k}·In_T) — "
                         "selectivitate inversată: Q JT declanșează înaintea QG",
             "ordonat": "{obiect}: Ir Q JT reglat la {b} A ≥ Ir QG {a} A (≤ {k}·In_T = {lim} A, Σ Iac {i} A ≤ In_T) — "
                        "reglajele cresc spre amonte"},
            "calibru amonte mai mare"),
    "V42": ("Selectivitate la scurtcircuit",
            {"INFO": "{obiect}: selectivitate totală (Ik3max {Ik} kA ≤ Is {Is} kA)",
             "INFO_gg": "{obiect}: selectivitate totală gG–gG (raport {r} ≥ 1,6)",
             "AV": "{obiect}: selectivitate parțială până la {Is} kA (Ik3max {Ik} kA) — confirmați cu tabelele producătorului"},
            "confirmare cu tabelele de selectivitate ale producătorului"),
    "V45": ("Material/izolație schimbate automat",
            {"": "{obiect}: {mat} {iz} nu ajunge la 4×240 mm² → s-a trecut pe {mat2} {iz2}",
             "F": "{obiect}: cablurile multipolare {mat} {iz} nu ajung (4×240 mm², nici Cu XLPE) → {n} sisteme de cabluri "
                  "monopolare Cu XLPE 1×{S} mm² în treflă pe pat perforat (metoda F) — POZARE ÎN AER, de confirmat",
             "Fsol": "{obiect}: cablurile multipolare {mat} {iz} nu ajung → {n} sisteme de cabluri monopolare Cu XLPE "
                     "1×{S} mm² în treflă, metoda {met} (în pământ)"}, ""),
    "V48": ("Al → Cu", {"": "{obiect}: secțiune mică — Al înlocuit cu Cu {S} mm²"}, ""),
    "V50": ("BMPT inexistent",
            {"tip": "{tip} nu există în ST 4-JT Rev. 3/2024 (gama: BMPTd-16/-40/-100, BMPTi-250)",
             "ib": "Ib = {Ib} A > 250 A: nu există BMPT; racord din PT (măsură în PT) sau PT propriu",
             "mic": "{tip} impus are Imax {Imax} A < Ib = {Ib} A — blocul nu poate alimenta sarcina"},
            "BMPT corect sau schema PT"),
    "V51": ("Semidirectă sub 100 A",
            {"": "măsură semidirectă cerută la Ib = {Ib} A: ST 4-JT prevede BMPTi-250 doar peste 100 A → {bloc}"}, ""),
    "V52": ("Q > SF", {"": "In Q {q} A > In SF {sf} A"}, "Q mai mic sau SF mai mare"),
    "V53": ("Monofazat > 40 A",
            {"": "Ib = {Ib} A > 40 A: nu există BMPM; branșament trifazat (BMPT)",
             "inv": "Iac,max = {Ib} A > 40 A (BMPM): invertor monofazat prea mare — trifazat"},
            "branșament / invertor trifazat"),
    "V54": ("Borne BMPTi", {"": "C2 {S} mm² > 150 mm² (bornele BMPTi-250)"}, "cabluri în paralel de secțiune mai mică"),
    "V55": ("TC", {"B": "TC: Ib = {Ib} A > primar maxim {p} A", "AV": "TC: sarcina secundară {S} VA > Sn {Sn} VA"},
            "conductor 2,5 mm² sau TC 10 VA"),
    "V56": ("Contor direct > 100 A", {"": "contor direct pe Ib = {Ib} A > 100 A"}, "BMPTi"),
    "V57": ("Circuitul de tensiune al contorului în serie cu TC",
            {"": "F (tensiune contor) legat în circuitul secundar al TC"}, "derivație din bare"),
    "V60": ("Q trafo sub In_T",
            {"B": "Q JT {x} A < In_T {y} A — întreruptorul general sub puterea trafo",
             "AV": "Ir QG {x} A > In_T {y} A — trafo neprotejat la suprasarcină",
             "sigma": "Σ Iac {x} A > Σ Ir Q JT {y} A ({n} trafo) — injecția maximă declanșează Q JT"},
            "Q JT ≥ In_T"),
    "V61": ("Siguranțe MT > 1000 kVA",
            {"": "celulă trafo cu siguranțe MT la {Sn} kVA > 1000 kVA — întreruptor + releu 50/51, 50N/51N"},
            "întreruptor + releu"),
    "V62": ("Bilanț > Sn", {"": "Sc = {x} kVA > Sn = {y} kVA",
                            "ge": "sarcina consumatorilor {x} kVA > Sn PT {y} kVA — PT-ul nu acoperă regimul rețea"},
            "trafo mai mare / ks justificat"),
    "V63": ("PT incomplet", {"": "PT: lipsește {element}",
                             "INFO": "PT: generate automat — {element}"}, "completarea modelului"),
    "V64": ("Iac,max din fișă neplauzibil",
            {"": "{obiect}: Iac,max = {x} A < Pn/U = {y} A (minimul fizic pentru Pn = {P} kW la {U}) — valoare neplauzibilă"},
            "verificați fișa invertorului (Iac,max ≥ Pn/(√3·400) la trifazat, ≥ Pn/230 la monofazat)"),
    "V65": ("QG < ΣIac", {"": "QG {x} A < Σ Iac invertoare + PCS = {y} A"}, "QG mai mare"),
    "V66": ("Racord JT al CEF",
            {"B": "S = {x} kVA > 400 kVA la 0,4 kV fără PT propriu și fără ATR pentru racord JT",
             "AV": "S = {x} kVA > 173 kVA: racord JT doar direct din PT OD conform ATR",
             "bmpt": "racord JT prin BMPT: Ip QG {x} A > In Q BMPTi-250 = {y} A — QG nu se coordonează cu Q din BMPT"},
            "PT propriu"),
    "V67": ("Trafo CEF sub S", {"": "Sn trafo {x} kVA < S invertoare+PCS {y} kVA",
                                "n": "Σ Sn trafo {n} × {sn} = {x} kVA < S invertoare+PCS {y} kVA",
                                "sectie": "secția {k}: Sn T{k} {x} kVA < S invertoare+PCS ale secției {y} kVA ({inv})"},
            "trafo mai mare"),
    "V68": ("Voc(Tmin)", {"B": "Voc la Tmin {x} V > Umax {y} V", "INFO": "Voc la Tmin {x} V ≤ Umax {y} V",
                          "beta": "β(Voc) = {x} %/K neplauzibil — coeficientul de temperatură al Voc este negativ "
                                  "(c-Si: −0,25…−0,35 %/K); Voc(Tmin) nu se poate verifica"},
            "mai puține module pe string"),
    "V69": ("gPV", {"": "nu există gPV în [{a}; {b}] A",
                    "generic": "{obiect}: siguranțe gPV necesare pe fiecare string ({motiv}), dar Isc al modulului lipsește — "
                               "desenate „conform proiect DC”; calibrul In ∈ [1,5·Isc; min(2,4·Isc; Irev)] se alege "
                               "din fișa modulului"},
            "alt modul / alt invertor; introduceți Isc / fișa modulului"),
    "V70": ("Categorie RfG / prosumator",
            {"INFO": "modul generator categoria {X} (Pn = {P} kW)",
             "AV": "modul generator categoria {X} (Pn = {P} kW) — cerințe RfG tip {X} (Ord. ANRE 208/2018), PI conform ATR",
             "B": "peste 400 kW nu e prosumator — schema CEF"}, ""),
    "V71": ("Invertor mono > 3,68 kW",
            {"": "invertor monofazat {P} kW > 3,68 kW — verificați cerința OD privind dezechilibrul",
             "dezechilibru": "invertoare monofazate pe rețea trifazată: S pe faze {det} — dezechilibru {d} kVA > {lim} kVA "
                             "(prag DECIZIE, practica OD; cerința exactă în ATR)",
             "faze": "invertoare monofazate repartizate pe faze: {det} — dezechilibru {d} kVA ≤ {lim} kVA"}, "trifazat"),
    "V72": ("Injecție > Q branșament",
            {"AV": "Iac,max {x} A > Q branșament {y} A — limitați injecția (setare invertor) sau solicitați ATR nou",
             "INFO": "Iac,max {x} A ≤ Q branșament {y} A"}, "limitarea injecției"),
    "V73": ("Tip DDR invertor",
            {"": "DDR în circuitul invertorului: tip A (sau B dacă fișa invertorului nu exclude curenți de defect c.c.)",
             "mare": "{obiect}: DDR {IdN} mA pe un invertor de {P} kW — curentul capacitiv de scurgere al câmpului PV "
                     "îl declanșează; IΔn ≥ 100 mA conform fișei invertorului / ATR"},
            "confirmați tipul DDR din fișa invertorului"),
    "V74": ("SPD c.c.", {"": "SPD c.c. Ucpv {x} V < Voc,max {y} V"}, "SPD cu Ucpv mai mare"),
    "V75": ("PI citat greșit", {"": "PI: pentru CEF ne-prosumator se aplică Ord. ANRE 208/2018 + ATR"}, ""),
    "V76": ("Putere injectabilă > puterea aprobată",
            {"": "puterea injectabilă ({ce}) {x} kW > puterea aprobată / evacuată din ATR {y} kW — limitați injecția "
                 "la Pa (EMS / setare invertor + analizor la punctul de racord) sau solicitați ATR nou",
             "INFO": "puterea injectabilă {x} kW ≤ puterea aprobată / evacuată {y} kW"},
            "limitare_injectie_kW = Pa (EMS) sau ATR nou"),
    "V80": ("Listă ≠ desen", {"": "{ref}: lista „{a}” ≠ parametri „{b}”"}, "regenerarea listei"),
    "V81": ("Notă ≠ model", {"": "nota {k}: „{a}” ≠ model „{b}”"}, "regenerarea notelor"),
    "V82": ("Tablou desenat în carcasa altui tablou", {"": "{td} desenat în interiorul {tg}"}, ""),
    "V83": ("Legătură de comandă inversată", {"": "săgeata {x}→{y} inversată"}, ""),
    "V85": ("GE: deconectare în regim generator",
            {"": "în regim GE Ik ≈ {x} A < Ia(Q_G) {y} A — deconectare prin DDR / protecția generatorului (51V)",
             "ramura": "{obiect}: în regim GE Ik1 ≈ {x} A < Ia {y} A — fără DDR, deconectarea automată nu este asigurată",
             "B": "în regim GE Ik1 ≈ {x} A < Ia(Q_G) {y} A și fără DDR — deconectarea automată nu este asigurată "
                  "(SR HD 60364-4-41 art. 411.4, -5-55 art. 551.4)",
             "DDR": "în regim GE Ik1 ≈ {x} A < Ia(Q_G) {y} A — deconectarea se asigură prin blocul diferențial "
                    "{IdN} mA S asociat Q_G (Zs·IΔn ≤ U0)"},
            "DDR, protecție 51V"),
    "V86": ("GE subdimensionat", {"": "sarcina {x} A > In_G {y} A — GE minim {Sn} kVA",
                                  "ir": "sarcina {x} A > Ir Q_G {y} A (Q_G reglat ≤ In_G) — GE minim {Sn} kVA",
                                  "supra": "GE {Sn_GE} kVA față de sarcina {P} kW (GE minim {Sn} kVA): QR {qr} A pe "
                                           "sarcină, ATS {ats} A pe GE — sarcina vitală e completă (toți consumatorii, "
                                           "pornirea motoarelor)?"},
            "GE din seria GE_SN_KVA ≥ P/cosφ: minim {Sn} kVA"),
    "V87": ("ATS neconform", {"": "ATS {detaliu}"}, "ATS 4P cu interblocaj mecanic + electric"),
    "V96": ("Nesuportat de motor",
            {"": "nesuportat: {ce} — {detaliu}"},
            "{remediere}"),
    "V97": ("Circuite de siguranță (I7/2011, P118-3)",
            {"": "{obiect}: circuit de siguranță ({nume}) — fără DDR, cablu rezistent la foc (E90), alimentare "
                 "prioritară; DDR-G pe Q_G înlocuit cu monitorizare diferențială (RCM, doar semnalizare)",
             "ge": "regim GE: Ik1 ≈ {x} A < Ia(Q_G) {y} A, iar circuitele de siguranță nu pot trece prin DDR — "
                   "contactul indirect se asigură prin legături echipotențiale suplimentare (SR HD 60364-4-41 "
                   "art. 415.2) și RCM cu alarmă; de confirmat (sau GE cu excitație susținută și Q_G electronic)",
             "plecare": "{obiect}: circuit de siguranță ({nume}) — fără DDR pe ramură și în amonte, cablu rezistent la "
                        "foc NHXH FE180/E90, releu termic doar de semnalizare (nu declanșează), ks = 1, pornirea declarată "
                        "păstrată",
             "ddr": "{obiect}: consumator de siguranță ({nume}) cu DDR pe calea lui ({ddr}) — interzis (I7/2011, "
                    "P118-3, SR HD 60364-5-56 art. 560.7): un DDR poate întrerupe alimentarea pompei / ventilatorului de "
                    "incendiu",
             "tt": "{obiect}: consumator de siguranță ({nume}) în schemă TT — fără DDR, protecția la contact indirect nu "
                   "este asigurată (în TT deconectarea se face numai prin DDR)",
             "amonte_q1": "circuitele de siguranță ({nume}) racordate înaintea întreruptorului general Q1 (la bornele "
                          "de intrare ale tabloului) — nu sunt deconectate de Q1 / de deconectarea generală (I7/2011)",
             "tablou": "tablou de siguranță: {detaliu}"},
            "proiect de specialitate pentru instalația de stingere (P118-3) / ATR; fără DDR pe calea consumatorilor de "
            "siguranță (racord înaintea DDR-ului / întreruptorului general, RCM doar alarmă)"),
    "V98": ("Compensarea puterii reactive",
            {"": "baterie de condensatoare {Q} kvar: In = {In} A, întreruptor ≥ 1,43·In = {Imin} A (armonici + "
                 "toleranța capacității, SR EN 60831-1), cablu dimensionat la 1,43·In",
             "mare": "baterie de condensatoare {Q} kvar > 60 % din Sn PT {Sn} kVA — supracompensare posibilă, "
                     "verificați factorul de putere țintă"},
            "regulator automat de factor de putere pe trepte, conform fișei producătorului"),
    "V88": ("CEF fără protecții c.c.", {"": "INV-{i}: lipsește {element} c.c."}, ""),
    "V89": ("Compatibilitate modul–invertor (fișe tehnice)",
            {"min": "string {n} module: Vmpp la 70 °C ≈ {x} V < MPPT min {y} V — invertorul iese din MPPT vara",
             "max": "string {n} module: Vmpp (STC) {x} V > MPPT max {y} V — funcționare limitată în afara MPPT",
             "ok": "Vmpp string {x} V (70 °C) … {z} V (STC) în fereastra MPPT {a}…{b} V",
             "isc": "Isc pe intrarea MPPT = {np}·Isc = {x} A > Isc max invertor {y} A",
             "kwp": "stringurile descrise (module × stringuri × MPPT × Pmax din fișă) dau {x} kWp ≠ puterea c.c. declarată {y} kWp",
             "idc": "Impp pe intrarea MPPT = {np}·Impp = {x} A > Idc max invertor {y} A — limitare de curent (clipping)"},
            "alt număr de module pe string / de stringuri pe MPPT, conform fișelor"),
    "V90": ("Ipoteze de calcul", {"": "{lista}"}, ""),
    "V91": ("Putere declarată ≠ Σ invertoare",
            {"": "Σ Pn invertoare = {x} kW ≠ puterea totală declarată {y} kW — confirmați numărul și puterea invertoarelor",
             "alias": "Pn_inv_kW = {y} kW ≠ Σ invertoare[] = {x} kW — se folosește lista invertoarelor",
             "monofazat": "rețea monofazată declarată, dar {detaliu} — confirmați rețeaua (monofazat / trifazat)",
             "bess_kwh": "capacitatea BESS {n} × {k} kWh = {x} kWh ≠ kWh declarat {y} kWh — se folosește {x} kWh",
             "bess_pcs": "puterea BESS {n} × PCS {k} kW = {x} kW ≠ P declarată {y} kW — se folosește {x} kW"},
            "corectați lista invertoarelor (n × Pn) sau puterea totală declarată"),
    "V92": ("Limitarea injecției",
            {"": "injecția în rețea limitată la {P} kW{z}: analizor / contor de control cu TC la punctul de racord + "
                 "controller EMS cu comandă către {n} {ce}",
             "fara_efect": "limitarea injecției {P} kW ≥ Σ Pn {Pn} kW — limitarea nu are efect",
             "zero_aprobat": "injecție zero declarată, dar puterea aprobată / evacuată din ATR este {y} kW — confirmați: "
                             "injecție zero (EMS limitează la 0 kW) sau injecție până la {y} kW (limitare_injectie_kW = {y})"},
            "reglaje EMS și timp de răspuns conform ATR"),
}


def _fmt_param(v):
    """Formatează parametrii numerici ai mesajului după SPEC §E.2."""
    if isinstance(v, float):
        return fmt_ro(v, 2)
    if isinstance(v, int) and not isinstance(v, bool):
        return fmt_ro(v, 0)
    return v


def mesaj(cod, varianta="", **param):
    """Construiește mesajul RO al verificării `cod` (SPEC §D), cu numerele formatate după SPEC §E.2."""
    sabl = CATALOG[cod][1]
    t = sabl.get(varianta) or sabl.get("") or next(iter(sabl.values()))
    return t.format(**{k: _fmt_param(v) for k, v in param.items()})


REMEDIERE_IMPLICITA = {
    "V00": "completați datele schemei (tip, sursă, plecări / circuite)",
    "V45": "confirmați materialul / izolația cablului sau declarați-le explicit",
    "V51": "măsură directă (BMPTd) sub 100 A sau Ib peste 100 A pentru BMPTi-250",
    "V70": "schema CEF (peste 400 kW nu e prosumator)",
    "V75": "Ord. ANRE 208/2018 + ATR pentru CEF ne-prosumator",
    "V80": "regenerați lista de echipamente din parametri (Calcul)",
    "V81": "regenerați notele din model (Calcul)",
    "V82": "desenați tabloul secundar în carcasa proprie (regenerare din Calcul)",
    "V83": "corectați sensul legăturii de comandă (regenerare din Calcul)",
    "V88": "completați protecțiile c.c. (siguranțe gPV, separator, SPD c.c.) ale invertorului",
}


def remediere(cod, **param):
    """Remedierea sugerată pentru `cod` (SPEC §D, ultima coloană). r10: niciodată goală / cu șablon nerezolvat —
    interpretorul o transformă în întrebare."""
    r = CATALOG[cod][2]
    try:
        r = r.format(**{k: _fmt_param(v) for k, v in param.items()})
    except (KeyError, IndexError):
        r = ""
    return r or REMEDIERE_IMPLICITA.get(cod, "")


def completeaza_remedieri(verificari):
    """r10: orice BLOCANT primește o remediere textuală (câmpul `remediere`) — din catalog sau, în lipsă, una generică
    după cod. Întoarce lista modificată pe loc."""
    for v in verificari or []:
        if v.get("nivel") != "BLOCANT":
            continue
        r = str(v.get("remediere") or "").strip()
        if not r or "{" in r:
            v["remediere"] = (REMEDIERE_IMPLICITA.get(v.get("cod")) or
                              (CATALOG[v["cod"]][2] if v.get("cod") in CATALOG and "{" not in CATALOG[v["cod"]][2] else "")
                              or f"corectați datele indicate de verificarea {v.get('cod')} ({v.get('obiect') or 'schema'}) "
                                 f"sau răspundeți la întrebarea asociată")
    return verificari


def emite(jurnal, cod, nivel, obiect, varianta="", **param):
    """Emite o verificare în jurnal (SPEC §D: {cod, nivel, obiect, mesaj, remediere})."""
    param.setdefault("obiect", obiect)
    m = mesaj(cod, varianta, **param)
    # v1.3 (P0-2, pct. 5): obiectul e deja în câmpul „obiect” — nu se repetă la începutul mesajului
    pref = f"{_fmt_param(param['obiect'])}: "
    if m.startswith(pref):
        m = m[len(pref):]
    jurnal.emite(cod, nivel, obiect, curata_text(m), curata_text(remediere(cod, **param)))
