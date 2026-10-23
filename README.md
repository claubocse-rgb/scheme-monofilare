# Scheme monofilare — generator

Aplicație locală care generează scheme electrice monofilare (planșe A3/A2) din date structurate:
previzualizare live în browser, export **DXF R2018** (AutoCAD 2018–2025, simboluri ca blocuri cu atribute),
**PDF** și **SVG**. Cartușul se completează din profilul tău de firmă (tab-ul Proiect).

## Pornire

```bash
python3 app.py
```

apoi deschide <http://localhost:8765> (sau dublu-clic pe `start.command`). Cerințe: Python 3.10+, `ezdxf` (DXF), `openpyxl` (Excel)
și Google Chrome / Chromium / Edge pentru PDF (detectat automat; altfel setează variabila `CHROME`).

## Interfața

* **Planșa** — rotiță / trackpad pentru zoom, tragere pentru deplasare, „Încadrează”, „1:1”; tastele `+ − 0 1` când planșa are focus.
  Clic pe un aparat din planșă îl deschide în formular; hover pe un aparat din formular îl evidențiază pe planșă.
* **Schemă nouă, pas cu pas** — un ecran mare de editor, fără planșă: (1) ce proiectezi (casă / apartament, branșament, tablou general,
  prosumator, CEF, PT, grup electrogen — sau descriere în cuvinte), (2) datele de intrare, (3) proiect și firmă, (4) verificare.
  Planșa apare abia la „Generează planșa”; „Sari la planșă” o arată oricând. Schemele vechi se redeschid din *Recente*.
* **Tabloul locuinței** — alimentarea (rețea, putere aprobată, Q branșament, coloană, TN-C-S / TT) și circuitele casei, alese dintr-o
  paletă de receptori (iluminat, prize, bucătărie, baie, plită, cuptor, boiler, pompă de căldură, încărcător VE …) sau dintr-un tablou
  tipic (apartament, casă parter, casă P+1, casă cu pompă de căldură și mașină electrică). Puterea și lungimea goale = valori uzuale;
  aplicația alege MCB, cablu, grupele DDR 30 mA și faza fiecărui circuit și arată rezultatul pe rând.
* **Tab-uri** — *Schemă* (intrări → bară → plecări, cu aparate și aparate auxiliare), *Proiect* (cartuș, format, profilul firmei), *Note*, *JSON*.
* **Profilul firmei** — completează proiectantul o dată și apasă „Salvează ca profil”; se aplică automat la fiecare schemă nouă.
* **Scurtături** — `Ctrl/⌘ Z` anulează, `Ctrl/⌘ Shift Z` reface, `Ctrl/⌘ S` salvează proiectul (.json), `Ctrl/⌘ O` deschide, `Ctrl/⌘ E` exportă DXF,
  `Ctrl/⌘ Enter` generează din descriere.

Planul de îmbunătățiri rezultat din testare: [`FEEDBACK.md`](FEEDBACK.md); rapoartele complete: `teste/`.

## Corectitudine tehnică (SPEC v1.2)

Schemele se generează din **calcul**, nu se desenează de mână:

* **Tab-ul Calcul** (primul) primește datele fizice: puteri, lungimi, rețea, schema de legare la pământ, date ATR.
  Motorul `engine/calc` dimensionează conform `spec/SPEC_TEHNIC.md`: Ib, protecții și reglaje, secțiuni Iz', I2 ≤ 1,45·Iz', N/PE, ΔU cumulat I7,
  Ik3max/Ik1min SR EN 60909, deconectare automată, Icu, selectivitate, DDR/TT, BMPT/BMPM, PT, CEF, prosumator, GE + ATS.
* **Desenul, lista de echipamente și notele** se reconstruiesc din calcul la fiecare previzualizare și export
  (`engine/constructor.py`, `engine/validare.py`), deci nu pot contrazice dimensionarea.
* **Catalogul de verificări** V01–V90 are trei niveluri: **BLOCANT**, AVERTISMENT, INFO.
  Orice BLOCANT oprește exportul (HTTP 409); pe planșă apare mesajul și remedierea.
* **Valorile presupuse** (Ik3 la OD, impedanța buclei, RA, ks, pozare…) sunt listate pe planșă și în memoriul de calcul
  (`/api/memoriu`, buton „Deschide memoriul de calcul”). Trebuie confirmate cu ATR-ul.
* **Schemele desenate manual** („Desen manual — fără verificare”) poartă nota „NU au fost verificate”.
  Aplicația verifică totuși concordanța desen ↔ listă (V80) și cablu ↔ protecție (V02/V03), citind secțiunea din text.
* **Teste:** `python3 -m pytest -q` rulează peste 560 de teste:
  * cazuri golden calculate de mână (`tests/date/cazuri_golden.json`);
  * defectele găsite la verificarea independentă (`tests/test_verificare2.py`);
  * integrare cap-coadă, cu desen fără suprapuneri și export blocat sau permis (`tests/test_integrare.py`);
  * fuzz, texte, chat.
* **Rapoartele verificării independente** (4 runde) sunt în `teste/verificare/`.

## Deviz, pachet de predare, profile de firmă

* **Tab-ul Deviz** construiește devizul estimativ din lista de echipamente a planșei.
  * Articolele sunt aparatele, cablurile (cu 5 % rezervă), patroanele fuzibile, barele, carcasele, accesoriile de cablu și materialele prizei de pământ.
  * Prețurile vin din **catalogul tău** (`date/preturi.json`, lângă aplicație, în afara git). Un preț introdus o dată se regăsește în toate proiectele.
  * Lista de prețuri se poate importa din Excel. Se recunosc coloanele *Denumire*, *Preț unitar* și, opțional, *Ore*, *Furnizor*, *Cod*.
  * Manopera se calculează ca ore × tarif orar. Orele pe categorii sunt orientative (afișate în cursiv) și pot fi înlocuite cu normele proprii.
  * Recapitulația adaugă cheltuieli indirecte %, profit % și TVA.
  * Aplicația nu inventează prețuri: articolele fără preț apar marcate cu galben.
  * Exportul .xlsx păstrează formulele, deci devizul se poate continua în Excel.
* **Pachetul de predare** (meniul de export, prima opțiune) este un .zip care conține:
  * planșa în DXF, PDF și SVG;
  * memoriul de calcul;
  * lista de echipamente;
  * devizul;
  * proiectul JSON;
  * un fișier CITESTE.txt.

  Pachetul este blocat, ca orice export, dacă schema are erori blocante.
* **Profilele de firmă** (tab-ul Proiect) se salvează sub nume, în `date/profile.json`, deci poți avea mai multe firme. Profilul *implicit* se aplică automat pe fiecare schemă nouă.

## Tipuri de scheme (preset-uri)

| Cheie  | Schemă                                   | Referință                                      |
|--------|------------------------------------------|------------------------------------------------|
| `bmpt` | Branșament BMPTi-250 (măsură semidirectă) | ST 4-JT Ed. U1 Rev. 3/2024 (DEER), Anexa 3     |
| `bmptd`| Branșament BMPTd-100 (măsură directă)    | ST 4-JT Ed. U1 Rev. 3/2024 (DEER), Anexa 2     |
| `tg`   | Tablou general JT cu plecări             | ex. TG 146 kW cu plecări în cascadă            |
| `cef`  | CEF fotovoltaic + BESS                   | ex. CEF agricolă cu BESS                     |
| `pt`   | Post de transformare 20/0,4 kV           | celule MT + trafo + TGJT                       |

Un preset se încarcă în formular, se modifică (aparate, laterale, cabluri, cartuș, note) și se exportă.
Modelul se poate salva/deschide ca JSON (`Salvează model` / `Deschide model`).

## Chat — generare din text liber

În caseta „Descrie schema” scrii cerința în română, de exemplu:

* `BMPTi 150 kW, cablu 80 m, beneficiar SC Agro Vest SRL, în Ciumeghiu, jud. Bihor, planșa E02`
* `tablou general 200 kW cu plecări: hală 63 A, birouri 32 A, pompe 40 kW, lungime 120 m`
* `CEF 300 kWp cu 3 invertoare de 100 kW și BESS 200 kWh`
* `post trafo 630 kVA cu plecări de 250, 160 și 100 A`

Interpretorul local (`engine/chat.py`) recunoaște tipul schemei, puterea / curentul, lungimea și materialul cablului,
plecările (nume + kW sau A), beneficiarul, localitatea / județul, planșa și faza, apoi dimensionează (Ib, In, Ir, secțiune,
ΔU, raport TC) și construiește modelul. Dacă există SDK-ul `anthropic` și credențiale (`ANTHROPIC_API_KEY` sau
`ant auth login`), modelul este rafinat de Claude (`claude-opus-5-5`); altfel se folosește doar interpretorul local.

## Dimensionare

Butonul „⚙ dimensionează ramura” de pe fiecare intrare / plecare deschide calculul (I7-2011 / SR HD 60364-5-52):
Pa, cos φ, lungime, material (Al/Cu), izolație (PVC/XLPE), pozare (pământ / aer), ΔU max, tip protecție →
Ib, In, Ir, secțiune + neutru, Iz, ΔU, raport TC. „Aplică la ramură” scrie rezultatele în aparatul de protecție, TC și cablu.
Tabelele de Iz sunt orientative; valorile finale se verifică la PT + DDE.

## Plecări în cascadă

O plecare poate avea `copii` (sub-plecări): consumatorul ei devine un tablou secundar desenat ca bară, cu propriile
plecări dedesubt (ex. TD-1 → Hală, Birouri). În formular: „+ sub-plecare”. Dacă schema nu încape pe A3,
planșa trece automat pe A2 (dezactivabil din „Trece automat pe A2”).

## BOM Excel

„Listă Excel” exportă lista de echipamente (poz., simbol, denumire, caracteristici, buc., coloane pentru producător,
preț și valoare cu formule) în `.xlsx`.

## Structura modelului (JSON)

```json
{
  "format": "A3",
  "cartus": { "beneficiar": "...", "titlu": "...", "denumire2": "...", "faza": "PT", "plansa": "E01" },
  "carcasa": { "titlu": "BMPTi-250", "sub": "carcasă PAFS · IP54" },
  "intrari": [ { "sursa": {"titlu": "RED 0,4 kV"}, "cablu": {"ref": "C1", "cond": "3 + PEN"},
                 "aparate": [ {"tip": "sep_fuzibil", "ref": "SF", "spec": ["3 × 250 A gG"], "lista": ["..."]} ] } ],
  "bara":    { "afisare": true, "eticheta": "Bare Cu 30×5 · 3P + N + PE", "laterale": [ {"tip": "spd", "ref": "F1"} ] },
  "plecari": [ { "aparate": [...], "cablu": {...}, "sarcina": {"titlu": "TD-1"} } ],
  "note": ["..."], "abrevieri": ["..."]
}
```

Un aparat poate avea `laterale` (contor, șir de cleme K, siguranțe F, cutie DPST / PI / releu, SPD, baretă de nul).
Lista de echipamente, pozițiile numerotate, legenda și cartușul se generează automat.

### Laterale: măsură, tensiune, comandă

```json
{"tip": "tc", "ref": "TC", "laterale": [
  {"tip": "cleme",   "ref": "K"},
  {"tip": "fuzibil", "ref": "F", "spec": ["3 × 2 A gG"], "intrare_contor": "tensiune", "sursa_legatura": "amonte"},
  {"tip": "contor",  "ref": "P", "eticheta": "kWh · kVArh"} ]},
{"tip": "mccb", "ref": "Q", "laterale": [ {"tip": "cutie", "eticheta": "DPST", "legatura": "comanda"} ]}
```

| câmp | valori | efect pe desen |
|---|---|---|
| `legatura` | `masura` (implicit) / `comanda` | `masura`: lanțul din dreapta aparatului, albastru — **circuitul de curent TC → K → P**. `comanda`: roșu punctat; săgeata pleacă de la protecție (DPST, PI, releu F>) și intră în **bobina de declanșare BD** a aparatului comandat (BD se desenează automat la întreruptoare) |
| `intrare_contor` | `curent` / `tensiune` | `tensiune` (implicit pentru `fuzibil`): **circuitul de tensiune al contorului** e o derivație separată — se ia de pe conductorul de forță, trece prin F și intră pe a doua intrare (latura de sus) a contorului din lanț. F nu mai stă niciodată între K și P. `curent` forțat pe un `fuzibil` după TC → V57 BLOCANT |
| `sursa_legatura` | `amonte` (implicit) / `aval` | locul derivației circuitului de tensiune: deasupra aparatului (pentru TC: din bare, în amonte de TC — SPEC B.19) sau dedesubt |

Compatibilitate: un model vechi cu F în lanțul `cleme → fuzibil → contor` (fără câmpurile noi) se desenează în noul mod corect.
`spd`, `spd_cc`, `descarcator_mt` legate de un aparat se desenează ca derivație spre pământ, în amonte de aparat, în dreapta.

### Carcase și tablouri secundare

* carcasa modelului (`carcasa`) cuprinde numai aparatele de protecție / comutație ale tabloului;
* **sursele** (`string_pv`, `invertor`, `convertor_bess`, `baterie`, `generator`) și tot ce e deasupra lor pe aceeași intrare
  (gPV, separator c.c., SPD c.c.) se desenează **în afara** carcasei, deasupra ei; un aparat oarecare se poate scoate afară cu
  `"in_carcasa": false`. Cablul dintre partea exterioară și carcasă se descrie cu `"cablu_ca": {...}` pe intrare;
* o plecare cu `copii` și `"grup": true` este o **grupă în același tablou** (ex. DDR 30 mA cu circuitele lui): o bară scurtă
  („pieptene”) sub aparatul grupei, fără cablu și fără carcasă proprie; `eticheta_grup` (ex. faza) se scrie lângă bară;
* o plecare cu `copii` (fără `grup`) este un **tablou secundar**: carcasa părintelui se închide sub plecări, iar tabloul secundar are propria carcasă,
  mai jos (titlu = `sarcina.titlu` + `sarcina.sub`). Cascada poate avea mai multe niveluri.

### Câmpuri noi în cartuș (SPEC G.5)

`verificator`, `referat`, `atr` (nr. ATR / aviz), `atestat_anre` + `atestat_tip` (`Bp` / `Ap`), `sef_proiect`, `proiectat`, `desenat`,
`verificat` (tabel cu coloane de semnătură și dată), pe lângă cele existente. Un câmp lipsă rămâne gol pe planșă (preset-urile nu mai
conțin text de exemplu de tipul „[BENEFICIAR]”).

### Verificări de topologie a desenului — `engine/topologie.py`

`verifica_topologie(model, canvas) -> list[dict]` întoarce `{cod, nivel, obiect, mesaj, remediere}` pentru
**V57** (circuitul de tensiune al contorului în serie cu TC), **V82** (sursă sau tablou secundar desenat în carcasa altui tablou) și
**V83** (săgeată de comandă inversată). Lucrează pe ce s-a desenat efectiv, din `canvas.meta` (carcase, surse, tablouri, legături,
poziții). `coliziuni(canvas)` raportează suprapunerile de text (casete estimate din lungime × înălțime × rotație), textele care taie
liniile cartușului / tabelului / carcaselor, cercurile de poziție peste simboluri, săgeți sau linii și PE prin caseta unui consumator.

### Planșa

* etichetele de cablu ale plecărilor se scriu **rotit la 90°**, de-a lungul cablului (tipul cablului în stânga, conductoarele în dreapta),
  între conturul carcasei și caseta consumatorului;
* coloanele nu se mai comprimă (textele s-ar suprapune): schema se **scalează uniform** în zona ei — micșorată dacă e prea lată,
  mărită pe A2 (până la 1,5×), iar pe A2 o schemă lată și joasă primește pas vertical mai mare.

## DXF

* format AC1032 (R2018), unități mm, desen 1:1 în modelspace, Layout1 configurat A3/A2 cu viewport 1:1;
* layere: `CHENAR`, `FORTA`, `SIMBOL`, `MASURA`, `COMANDA`, `MECANIC`, `COMUNIC`, `PE`, `CARCASA`, `TEXT`, `TEXT_GRI`, `TABEL`, `CARTUS`, `HASURA`;
* fiecare simbol este un bloc `SYM_<TIP>` inserat cu atributele invizibile `REF`, `SPEC`, `TIP` (extragere cu `ATTEXT` / `DATAEXTRACTION`);
  numele blocului depinde de geometria efectivă: `SYM_MCCB` vs `SYM_MCCB_BD`, `SYM_TRAFO_N`; variantele cu altă geometrie
  (de ex. `cutie` de altă mărime) primesc un sufix scurt derivat din geometrie (`SYM_CUTIE_3F9A1C`) — două inserări cu geometrie
  diferită nu partajează un bloc;
* planșa A2 scalată: blocurile se inserează cu factor de scară, textele cu înălțimea scalată; textele rotite păstrează rotația;
* stiluri text TrueType Arial (`ARIAL`, `ARIAL_B`, `ARIAL_I`).

## Structură

```
app.py                 server HTTP local (stdlib) + API: /api/preview, /api/export/{dxf,pdf,svg,json}
engine/canvas.py       primitive geometrice comune (mm) și layerele
engine/symbols.py      biblioteca de simboluri
engine/layout.py       motorul de layout (coloane, bară, carcase, PE, tabel, legendă, note, cartuș)
engine/topologie.py    verificări de topologie a desenului (V57, V82, V83) și coliziuni de text
engine/render_svg.py   Canvas -> SVG
engine/render_dxf.py   Canvas -> DXF (blocuri cu atribute)
engine/presets.py      modelele implicite (BMPTi, BMPTd, TG, CEF, PT)
engine/calc/           MOTORUL DE CALCUL (SPEC v1.2): dimensionare, scurtcircuit, verificări V01–V90, texte generate
engine/constructor.py  intrare fizică + rezultat calcul -> model grafic (aparate cu parametri, cabluri, note, materiale)
engine/validare.py     regenerare din calcul la preview/export, blocaj export, verificarea modelelor manuale
engine/memoriu.py      memoriul de calcul (HTML / PDF)
engine/deviz.py        deviz estimativ: catalog de prețuri, manoperă, recapitulație, export Excel, import listă de prețuri
date/                  datele tale locale (catalog de prețuri, profile de firmă) — nu intră în git
engine/interpretor.py  text liber -> intrare fizică (refuză când lipsesc date esențiale)
engine/dimensionare.py calcul rapid pentru panoul de dimensionare (vechi)
engine/chat.py         adaptor peste interpretor
engine/bom.py          export listă de echipamente Excel
static/index.html      interfața web (un singur fișier, fără dependențe)
static/fonts/          fonturile Barlow (OFL), servite local
test_render.py         randează toate preset-urile în out/ (svg, pdf, png, dxf)
tests/test_desen.py    teste de desen: măsură semidirectă, săgeți de comandă, carcase, blocuri DXF, coliziuni, A2, cartuș, simboluri
```
