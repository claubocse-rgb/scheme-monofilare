"""Textele dosarului de racordare (prosumator / producător) — E2.

Temei (verificat la 28.10.2026 pe textul publicat de Rețele Electrice România):
* Ord. ANRE nr. 19/2022 — Procedura privind racordarea la rețelele electrice de interes public a locurilor de consum și
  de producere aparținând prosumatorilor, cu modificările și completările ulterioare: Anexa nr. 1 = cererea de
  racordare (loc nou / loc existent cu modificări care depășesc puterea aprobată), Anexa nr. 2 = notificarea pentru
  racordarea unei instalații de producere la un loc de consum existent, Anexa nr. 3 = notificarea pentru certificarea
  calității de prosumator; art. 19 — dosarul instalației de utilizare.
* Ord. ANRE nr. 59/2013 — Regulamentul privind racordarea utilizatorilor la rețelele electrice de interes public
  (producători care nu sunt prosumatori / CEF peste pragul procedurii pentru prosumatori).
* Ord. ANRE nr. 208/2018 (RfG — cerințe tehnice pentru module generatoare) și Ord. ANRE nr. 228/2018 (cerințe tehnice
  pentru prosumatori / module generatoare categoria A conectate la JT).
Formularele OD pot avea machete proprii (Distribuție Energie Electrică România, Rețele Electrice, Delgaz Grid,
Distribuție Energie Oltenia, E-Distribuție) cu același conținut minim — se verifică pe site-ul OD înainte de depunere.
"""
VERIFICAT_LA = "28.10.2026"
TEMEI_PROSUMATOR = ("Ord. ANRE nr. 19/2022 — Procedura privind racordarea la rețelele electrice de interes public a locurilor "
                    "de consum și de producere aparținând prosumatorilor, cu modificările și completările ulterioare")
TEMEI_PRODUCATOR = ("Ord. ANRE nr. 59/2013 — Regulamentul privind racordarea utilizatorilor la rețelele electrice de "
                    "interes public, cu modificările și completările ulterioare")

TITLU_CERERE = {"nou": "CERERE DE RACORDARE", "existent": "CERERE DE RACORDARE",
                "notificare": "NOTIFICARE PRIVIND RACORDAREA UNEI INSTALAȚII DE PRODUCERE LA UN LOC DE CONSUM EXISTENT"}
ANEXA = {"nou": "Anexa nr. 1 la procedura aprobată prin Ord. ANRE nr. 19/2022",
         "existent": "Anexa nr. 1 la procedura aprobată prin Ord. ANRE nr. 19/2022",
         "notificare": "Anexa nr. 2 la procedura aprobată prin Ord. ANRE nr. 19/2022",
         "producator": "conform Ord. ANRE nr. 59/2013 (cerere de racordare — loc de producere)"}

OBIECT_CERERE = {
    "nou": "racordarea unui loc de consum și de producere NOU",
    "existent": "modificarea unui loc de consum existent prin montarea unei instalații de producere, cu depășirea puterii aprobate",
    "notificare": "racordarea unei instalații de producere la un loc de consum existent, fără depășirea puterii aprobate",
    "producator": "racordarea unui loc de producere (centrală electrică)",
}

# documentele anexate cererii (Ord. 19/2022, anexa 1, lit. a–j); „cand” = nou / existent / ambele
DOCUMENTE_ANEXATE = [
    ("a", "copia actului de identitate / certificatului de înregistrare sau a altor autorizații de funcționare", "ambele"),
    ("b", "certificatul constatator (persoane juridice) din care rezultă că producerea energiei electrice nu constituie "
          "activitatea economică principală", "ambele"),
    ("c", "certificatul de urbanism (numai loc nou)", "nou"),
    ("d", "planul de situație / de încadrare în zonă (numai loc nou)", "nou"),
    ("e", "documentul de proprietate sau de folosință asupra imobilului (numai loc nou)", "nou"),
    ("f", "autorizația de construire, dacă se solicită organizare de șantier (numai loc nou)", "nou"),
    ("g", "procesul-verbal de recepție la terminarea lucrărilor (loc existent cu creștere de putere)", "existent"),
    ("h", "buletinul de verificare a prizei de pământ (loc existent cu creștere de putere)", "existent"),
    ("i", "certificatele și fișele tehnice ale invertoarelor / unităților generatoare (loc existent cu creștere de putere)",
          "existent"),
    ("j", "schema electrică monofilară cu protecțiile și reglajele (loc existent cu creștere de putere)", "existent"),
]
# dosarul instalației de utilizare (Ord. 19/2022, art. 19)
DOSAR_INSTALATIE = [
    "procesele-verbale de recepție la terminarea lucrărilor",
    "buletinul de verificare a prizei de pământ",
    "certificatele și fișele tehnice ale invertoarelor / unităților generatoare și, după caz, ale sistemului de stocare",
    "schema electrică monofilară a instalației, inclusiv tabloul general, cu protecțiile și reglajele",
]

# certificatele uzuale cerute de OD pe tip de echipament (lista de echipamente cu certificate)
CERTIFICATE = {
    "invertor": "certificat de conformitate cu cerințele tehnice ANRE (Ord. 228/2018 / Ord. 208/2018 — RfG), raport de "
                "încercări SR EN 50549-1 / VDE-AR-N 4105 (PI integrată, anti-insularizare SR EN 62116), declarație de "
                "conformitate UE (LVD 2014/35/UE, EMC 2014/30/UE), fișa tehnică",
    "string_pv": "certificate SR EN IEC 61215-1/-2 și SR EN IEC 61730-1/-2, declarație de conformitate UE, fișa tehnică",
    "baterie": "certificat SR EN IEC 62619 (siguranță), UN 38.3 (transport), SR EN 62477-1 (convertor), declarație de "
               "conformitate UE, fișa tehnică",
    "convertor_bess": "certificat de conformitate cu cerințele tehnice ANRE (RfG), SR EN 62477-1, declarație de conformitate UE",
    "spd": "declarație de conformitate SR EN 61643-11, fișa tehnică",
    "spd_cc": "declarație de conformitate SR EN 61643-31, fișa tehnică",
    "gpv": "declarație de conformitate SR EN 60269-6 (gPV), fișa tehnică",
    "separator_cc": "declarație de conformitate SR EN 60947-3 (DC-PV1 / DC-PV2), fișa tehnică",
    "mcb": "declarație de conformitate SR EN 60898-1", "mccb": "declarație de conformitate SR EN 60947-2",
    "acb": "declarație de conformitate SR EN 60947-2", "rccb": "declarație de conformitate SR EN 61008-1",
    "rcbo": "declarație de conformitate SR EN 61009-1", "contor": "furnizat de OD (aprobare de model BRML)",
    "releu_pi": "certificat de conformitate al protecției de interfață (Ord. ANRE 208/2018 / 228/2018), buletin de reglaje",
}

DECLARATIE_INSTALATOR = [
    "Subsemnatul(a) ", None, ", electrician autorizat ANRE gradul ", None, ", legitimația nr. ", None,
    ", în calitate de reprezentant al operatorului economic ", None, ", atestat ANRE tip ", None, " nr. ", None,
    ", declar pe propria răspundere, cunoscând prevederile art. 326 din Codul penal privind falsul în declarații, că "
    "instalația electrică de utilizare (instalația de consum și de producere) de la adresa ", None,
    ", aparținând beneficiarului ", None, ", a fost executată conform proiectului nr. ", None, " întocmit de ", None,
    ", cu respectarea prevederilor Normativului I7/2011, SR HD 60364, SR HD 60364-7-712 (instalații fotovoltaice), "
    "ale avizului tehnic de racordare / certificatului de racordare și ale reglementărilor ANRE în vigoare.",
]
VERIFICARI_INSTALATOR = [
    "examinarea vizuală a instalației (SR HD 60364-6 art. 6.4.2)",
    "continuitatea conductoarelor de protecție și a legăturilor de echipotențializare",
    "rezistența de izolație a instalației (c.a. și c.c.) — ≥ 1 MΩ la 500 V c.c.",
    "rezistența prizei de pământ — buletin de măsurare anexat",
    "impedanța buclei de defect / deconectarea automată a alimentării",
    "funcționarea dispozitivelor diferențiale (IΔn, timp de declanșare)",
    "polaritatea și succesiunea fazelor",
    "partea de c.c.: tensiunea în gol și curentul de scurtcircuit pe stringuri (SR EN IEC 62446-1)",
    "protecția de interfață: reglajele conform avizului / certificatului de racordare și declanșarea la lipsa rețelei "
    "(anti-insularizare)",
    "funcționarea limitării injecției / injecției zero (dacă este prevăzută)",
]
