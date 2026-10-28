"""Textele caietului de sarcini (E2) — structura uzuală în RO (proiecte private, SEAP, fonduri UE):
1 Generalități · 2 Standarde și normative · 3 Materiale și echipamente (caracteristici minime, neutre de marcă) ·
4 Execuția lucrărilor · 5 Verificări și probe · 6 Recepția · 7 Punerea în funcțiune · 8 Documentația as-built.
Caracteristicile minime ale echipamentelor se generează din lista de echipamente a planșei (engine/documente_caiet.py).
"""
VERIFICAT_LA = "28.10.2026"

NORMATIVE_COMUNE = [
    "Legea nr. 10/1995 privind calitatea în construcții, republicată, cu modificările ulterioare",
    "Legea nr. 123/2012 a energiei electrice și a gazelor naturale, cu modificările și completările ulterioare",
    "HG nr. 343/2017 — Regulamentul de recepție a lucrărilor de construcții și instalații aferente acestora",
    "Normativul I7/2011 pentru proiectarea, execuția și exploatarea instalațiilor electrice aferente clădirilor",
    "SR HD 60364 (seria) — Instalații electrice de joasă tensiune; SR HD 60364-4-41, -4-43, -4-443, -5-52, -5-54, -6",
    "SR EN 61439-1/-2/-3 — Ansambluri de aparataj de joasă tensiune (tablouri electrice)",
    "SR EN 60898-1, SR EN 60947-2, SR EN 61008-1, SR EN 61009-1, SR EN 60269 — aparataj de protecție",
    "SR EN 61643-11 — Dispozitive de protecție la supratensiune (SPD) conectate la rețele de JT",
    "SR EN 62305 (seria) — Protecția împotriva trăsnetului (dacă există LPS)",
    "Legea nr. 319/2006 a securității și sănătății în muncă și HG nr. 1425/2006 (norme metodologice)",
    "Legea nr. 307/2006 privind apărarea împotriva incendiilor; P118-3/2015 (instalații de securitate la incendiu, după caz)",
    "Ord. ANRE nr. 11/2013 — Regulamentul de atestare a operatorilor economici care proiectează, execută și verifică "
    "instalații electrice; Ord. ANRE nr. 23/2013 — autorizarea electricienilor",
]
NORMATIVE_PV = [
    "SR HD 60364-7-712 — Cerințe pentru instalații sau amplasamente speciale. Sisteme de alimentare fotovoltaice (PV)",
    "SR EN IEC 62446-1 — Sisteme fotovoltaice: cerințe pentru încercări, documentație și mentenanță",
    "SR EN IEC 61215 / SR EN IEC 61730 — module fotovoltaice; SR EN 50618 — cabluri pentru sisteme PV (H1Z2Z2-K)",
    "SR EN 60269-6 (siguranțe gPV), SR EN 60947-3 (separatoare c.c.), SR EN 61643-31 (SPD c.c.)",
    "SR EN 50549-1 — Cerințe pentru centralele electrice conectate în paralel cu rețelele de distribuție (JT)",
    "Ord. ANRE nr. 208/2018 (RfG) și Ord. ANRE nr. 228/2018 — cerințe tehnice de racordare a modulelor generatoare",
    "Ord. ANRE nr. 19/2022 — procedura de racordare a prosumatorilor (după caz) / Ord. ANRE nr. 59/2013 — regulamentul "
    "de racordare",
]
NORMATIVE_BESS = ["SR EN IEC 62619 / SR EN IEC 62933 (seria) — sisteme de stocare a energiei cu baterii",
                  "SR EN 62477-1 — cerințe de securitate pentru convertoarele electronice de putere"]
NORMATIVE_PT = ["PE 101/1985, PE 101A/1985 — instrucțiuni pentru construcția instalațiilor electrice de conexiuni și transformare",
                "SR EN 62271-200 — aparataj de MT în anvelopă metalică; SR EN 60076 — transformatoare de putere",
                "Ord. ANRE nr. 59/2013 — regulamentul de racordare; normele tehnice ale OD pentru posturi de transformare"]
NORMATIVE_GE = ["SR ISO 8528 (seria) — grupuri electrogene", "SR EN 60947-6-1 — echipamente de comutare automată (ATS)"]
NORMATIVE_BRANSAMENT = ["Normele tehnice ale OD pentru branșamente și blocuri de măsură și protecție (BMPM / BMPT)",
                        "Ord. ANRE nr. 59/2013 — regulamentul de racordare"]

GENERALITATI = [
    "Prezentul caiet de sarcini stabilește condițiile tehnice minime pentru furnizarea materialelor și echipamentelor, "
    "execuția, verificarea, recepția și punerea în funcțiune a instalației electrice descrise în proiect (planșa "
    "schemei monofilare, memoriul tehnic și memoriul de calcul), care fac parte integrantă din documentație.",
    "Executantul va fi un operator economic atestat ANRE pentru tipul de lucrare (atestatul cerut este indicat în "
    "cartușul planșei), cu personal autorizat ANRE de gradul corespunzător.",
    "Orice abatere de la proiect (echipamente echivalente, trasee, secțiuni) se face numai cu acordul scris al "
    "proiectantului și al beneficiarului; echipamentele echivalente trebuie să aibă caracteristici cel puțin egale cu "
    "cele minime de mai jos și se aprobă pe baza fișelor tehnice și a certificatelor.",
    "Mențiunile de marcă sau model din documentație au caracter informativ și se citesc „sau echivalent” (Legea nr. "
    "98/2016, art. 156, pentru achizițiile publice).",
]
CONDITII_ECHIPAMENTE = [
    "Toate echipamentele vor fi noi, marcate CE, însoțite de declarația de conformitate UE, fișa tehnică, instrucțiunile "
    "de montaj și exploatare în limba română și certificatul de garanție.",
    "Aparatele de protecție vor avea capacitatea de rupere Icu / Icn cel puțin egală cu curentul de scurtcircuit maxim la "
    "locul de montaj (coloana Ik3max din fișa de reglaje).",
    "Cablurile vor avea marcajul tipului, secțiunii și al producătorului pe manta; secțiunile sunt cele din tabelul de "
    "cabluri; nu se admit secțiuni mai mici sau înlocuirea cuprului cu aluminiul fără recalcularea de către proiectant.",
]
EXECUTIE = [
    ("Organizarea lucrărilor", [
        "predarea amplasamentului, trasarea traseelor și a pozițiilor tablourilor în prezența dirigintelui de șantier",
        "lucrările sub tensiune sunt interzise; se aplică măsurile tehnice și organizatorice de separare, blocare, "
        "verificare a lipsei tensiunii, legare la pământ și scurtcircuitare (NSSM / IPSSM)",
        "pentru lucrările în instalațiile OD se obține acordul OD și se lucrează numai cu autorizație de lucru"]),
    ("Tablouri electrice", [
        "tablourile se execută și se încearcă conform SR EN 61439-1/-2/-3 (verificări de proiectare și individuale) de "
        "către constructorul tabloului, cu raport de încercări individuale",
        "gradul de protecție minim: IP40 la interior, IP54 la exterior / medii umede, IP65 pentru tablourile de la "
        "acoperiș; rezerva de spațiu ≥ 20 % (vezi dimensionarea carcasei)",
        "etichetarea: fiecare aparat cu referința din schemă și destinația circuitului; eticheta „Atenție: instalație "
        "alimentată din două surse” la tablourile cu producere locală"]),
    ("Cabluri și trasee", [
        "pozarea conform metodei de referință din tabelul de cabluri (D1 în tub în pământ, la 0,7–0,8 m, cu bandă de "
        "avertizare; B2 / C în clădire); distanțele față de alte rețele conform NP 061 / I7",
        "razele minime de curbură, capete terminale și manșoane conform fișei producătorului; cablurile armate se leagă "
        "la pământ la capete",
        "traversările de pereți / planșee rezistenți la foc se etanșează cu sisteme cu aceeași rezistență la foc",
        "circuitele de siguranță (dacă există) se execută cu cabluri rezistente la foc, pe trasee separate"]),
    ("Priza de pământ și echipotențializare", [
        "priza de pământ se execută conform planșei / calculului; rezistența se măsoară înainte de umplerea șanțului "
        "și se consemnează în buletin; legătura la bara principală de egalizare a potențialelor (BPE)",
        "toate masele metalice (structura PV, carcase, jgheaburi) se leagă la PE / echipotențializare"]),
]
EXECUTIE_PV = ("Instalația fotovoltaică", [
    "stringurile se execută cu cablu solar H1Z2Z2-K (SR EN 50618), conectori de același tip și producător pe fiecare "
    "pereche (MC4 sau compatibil certificat), cu polaritatea marcată; buclele induse se minimizează (conductorii + și − "
    "pozați alăturat)",
    "înainte de conectarea la invertor se măsoară Voc și Isc pe fiecare string și se compară cu valorile calculate "
    "(SR EN IEC 62446-1)",
    "structura de montaj se leagă la pământ; pe acoperiș se păstrează distanțele de separare față de LPS (dacă există)",
    "invertoarele se montează în spații ventilate, ferite de radiația solară directă, cu distanțele din fișa tehnică"])
PROBE = [
    "examinare vizuală (SR HD 60364-6, 6.4.2) — conformitatea cu proiectul, marcajul, accesibilitatea",
    "continuitatea conductoarelor de protecție și de echipotențializare",
    "rezistența de izolație (c.a.: ≥ 1 MΩ la 500 V c.c.; c.c. PV: conform SR EN IEC 62446-1)",
    "rezistența prizei de pământ (valoarea limită din proiect)",
    "impedanța buclei de defect și verificarea deconectării automate (SR HD 60364-4-41)",
    "încercarea dispozitivelor diferențiale (curent și timp de declanșare)",
    "polaritate, succesiunea fazelor, încercări funcționale (ATS, interblocaje, comenzi)",
    "verificarea reglajelor protecțiilor conform fișei de reglaje (Ir, Isd, tsd, Ii, IΔn)",
]
PROBE_PV = ["c.c.: Voc și Isc pe fiecare string, rezistența de izolație a câmpului PV (SR EN IEC 62446-1)",
            "protecția de interfață: verificarea reglajelor (27/59/81) și a declanșării la lipsa rețelei (anti-insularizare)",
            "limitarea injecției / puterii la punctul de racord (dacă este prevăzută): încercare funcțională cu analizorul",
            "termografie la tablouri după 1–2 h de funcționare la putere (recomandat)"]
RECEPTIE = [
    "Recepția se face conform HG nr. 343/2017: recepția la terminarea lucrărilor (comisie numită de beneficiar, cu "
    "participarea proiectantului și a executantului) și recepția finală, după perioada de garanție.",
    "Executantul pune la dispoziția comisiei: buletinele de verificări și probe, procesele-verbale de lucrări ascunse "
    "(priza de pământ, cabluri pozate în pământ), certificatele și declarațiile de conformitate ale echipamentelor, "
    "fișa de reglaje completată, schema as-built.",
    "Pentru instalațiile racordate la rețeaua publică: certificatul de racordare / procesul-verbal de punere sub "
    "tensiune se obțin de la OD, pe baza dosarului instalației de utilizare.",
]
PIF = [
    "Punerea în funcțiune se face după recepția la terminarea lucrărilor, de către executant, în prezența beneficiarului "
    "și, pentru instalațiile racordate la rețea, cu acordul / în prezența OD.",
    "Etape: verificarea stării aparatelor (deschise), punerea sub tensiune progresivă de la sursă spre receptoare, "
    "verificarea tensiunilor și a succesiunii fazelor, încercările funcționale, apoi pornirea surselor locale (invertoare, "
    "BESS, GE) conform instrucțiunilor producătorilor.",
    "La instalațiile de producere: verificarea parametrilor protecției de interfață și a puterii injectate față de "
    "puterea aprobată; înregistrarea primei citiri a contorului bidirecțional.",
    "Se întocmește procesul-verbal de punere în funcțiune, cu fișa de reglaje și valorile măsurate anexate.",
]
AS_BUILT = [
    "schema monofilară actualizată conform execuției (as-built), semnată de executant și vizată de proiectant",
    "tabelul de cabluri cu lungimile reale și fișa de reglaje a protecțiilor completată la PIF",
    "planurile de trasee ale cablurilor (inclusiv cele îngropate, cu cote) și planul prizei de pământ",
    "buletinele de verificări și probe, procesele-verbale de lucrări ascunse",
    "certificatele / declarațiile de conformitate, fișele tehnice, instrucțiunile de exploatare și garanțiile",
    "raportul de încercări individuale al tablourilor (SR EN 61439)",
    "pentru PV: documentația conform SR EN IEC 62446-1 (date de sistem, configurația stringurilor, măsurători)",
    "cartea tehnică a construcției — partea de instalații electrice (Legea 10/1995)",
]

# caracteristicile minime suplimentare, pe tip de echipament (completează textul din lista de echipamente)
CERINTE_TIP = {
    "mcb": "întreruptor automat modular SR EN 60898-1; curba și In conform listei; Icn ≥ Ik3max la locul de montaj; "
           "clasa de limitare 3",
    "mccb": "întreruptor automat în carcasă turnată SR EN 60947-2; reglaje conform fișei de reglaje; Icu ≥ Ik3max; Ics ≥ 50 % Icu",
    "acb": "întreruptor automat deschis SR EN 60947-2; declanșator electronic LSI(G); Icw conform selectivității; acționare motorizată",
    "rccb": "dispozitiv diferențial SR EN 61008-1; IΔn și tipul (AC / A / F / B) conform listei; S = selectiv",
    "rcbo": "întreruptor automat cu protecție diferențială SR EN 61009-1; curba, In, IΔn și tipul conform listei",
    "sep_fuzibil": "separator cu siguranțe fuzibile SR EN 60947-3 / SR EN 60269-2, cu separare vizibilă",
    "fuzibil": "siguranțe fuzibile gG SR EN 60269-1/-2",
    "spd": "descărcător SPD SR EN 61643-11; tipul (T1 / T2 / T3), Up și In / Iimp conform listei; indicator de stare",
    "spd_cc": "descărcător SPD c.c. SR EN 61643-31; Ucpv ≥ Uoc,max la Tmin; In ≥ 20 kA",
    "gpv": "siguranțe gPV SR EN 60269-6, In conform listei, 1000 / 1500 V c.c.",
    "separator_cc": "separator c.c. sub sarcină SR EN 60947-3, categoria DC-PV2, tensiunea ≥ Uoc,max",
    "invertor": "invertor de rețea SR EN 62109-1/-2, SR EN 50549-1, cerințele ANRE (Ord. 228/2018 / 208/2018); PI "
                "integrată sau externă certificată; randament european ≥ 97 %; IP65 la exterior; monitorizare",
    "string_pv": "module fotovoltaice SR EN IEC 61215 / 61730; puterea, Voc, Isc conform listei; degradare ≤ 0,55 %/an; "
                 "garanție de produs ≥ 12 ani",
    "baterie": "sistem de stocare SR EN IEC 62619; capacitatea utilă conform listei; BMS integrat",
    "convertor_bess": "convertor BESS (PCS) SR EN 62477-1, cerințele ANRE (RfG)",
    "contor": "contor furnizat și montat de OD",
    "tc": "transformatoare de curent SR EN 61869-2, clasa de precizie și puterea conform listei",
    "generator": "grup electrogen SR ISO 8528, regim PRP, puterea conform listei, cu protecții proprii și rezervor",
    "separator": "comutator / separator SR EN 60947-3 (ATS: SR EN 60947-6-1, categoria AC-33B)",
}
