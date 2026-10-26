# Runda 5 — scheme generate din text (chat / „Descrie instalația”), 23.10.2026

## Aplicația
Generator de scheme electrice monofilare românești. Cod: /home/claude/sm (citește README.md; spec/SPEC_TEHNIC.md §F = interpretorul de text).
NU modifica codul aplicației — scrii doar în teste/r5/<rolul tău>/ și raportul teste/r5/<rol>.md.

Fluxul testat: proiectantul scrie în cuvinte ce are de proiectat → aplicația interpretează (engine/interpretor.py; API: POST /api/chat
{text, model:{}} → {interpretare, model, validare}) → motorul dimensionează → planșa (SVG/DXF/PDF), lista, devizul, memoriul.
Din Python: `from engine.interpretor import interpreteaza_local; from engine import constructor, validare, layout, render_svg`
`r = interpreteaza_local(text); m, rez = constructor.genereaza(r["intrare_fizica"])` (dacă actiune != "refuza").
Server: `cd /home/claude/sm && python3 app.py <PORT>` (în fundal; oprește-l la final). Playwright: `NODE_PATH=$(npm root -g) node script.js`.
Ca să vezi planșele: render_svg.render(layout.build(m)) → .svg → PNG cu Playwright (screenshot) și uită-te la ele.

## Ce faci
1. Scrie CEL PUȚIN 40 de descrieri realiste, cum le-ar scrie un proiectant român grăbit (diacritice sau nu, prescurtări, greșeli de tastare,
   unități amestecate, „cca”, „aprox”, ordine aleatoare, date lipsă, date contradictorii, cifre cu virgulă/punct), din domeniul tău.
2. Pentru fiecare: ce a înțeles aplicația (tip, rețea, puteri, lungimi, circuite, cartuș), ce a presupus, ce a întrebat/refuzat;
   apoi dacă schema rezultată e CORECTĂ TEHNIC și COMPLETĂ (ca proiectant cu experiență: ai semna-o?). Tabel: frază | așteptat | obținut | verdict.
3. Randează cel puțin 10 planșe și uită-te la ele (lizibilitate, aparate lipsă, texte greșite, modele, protecții).
4. Caută ce strică interpretorul: fraze care dau tip greșit, valori luate de la alt receptor, unități greșite (kW vs kVA vs A), lungimi
   ignorate, presupuneri periculoase făcute în tăcere (mai ales rețeaua — regula: rețeaua NU se presupune), refuzuri inutile.

## Raport
teste/r5/<rol>.md — română, concis: scor /10, statistici (câte fraze: corect / parțial / greșit), apoi constatări numerotate P0 (greșit tehnic
/ periculos) · P1 (important) · P2, fiecare cu fraza exactă, ce s-a obținut, ce era corect, remediere propusă. Anexă: toate frazele + rezultatul
(JSON) în teste/r5/<rol>/fraze.json.
