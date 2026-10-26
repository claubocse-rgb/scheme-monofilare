# Discrepanțe și clarificări — interpretorul de text (§F) vs. `fraze_chat.json` / `cazuri_golden.json`

Starea: 60/60 fraze trec, 0 xfail. Mai jos sunt locurile unde testul și specificația nu spun același lucru
sau unde interpretorul a trebuit să aleagă singur. Testele NU au fost modificate. Fiecare punct are nevoie de confirmarea inginerului.

| Id | Ce nu se potrivește | Ce face acum implementarea | Ce propun |
|---|---|---|---|
| F26 | F.2.4 spune că „al” scris cu literă mică se ignoră. Fraza „bmpt 40kw 25m al” așteaptă totuși `material = Al`. | Acceptă „al”/„cu” cu literă mică doar ca token izolat la sfârșitul unui segment, imediat după o lungime sau după „cablu” (`25m al`, `cablu cu,`). „al doilea”, „cu 2 plecări” etc. rămân ignorate. | Se adaugă excepția în F.2.4 sau se schimbă fraza în „… 25m Al”. |
| F07 vs F29 | În ambele fraze interpretorul întreabă „Confirmați BMPTd-100?”. F07 așteaptă însă `actiune = genereaza` (cu întrebare), iar F29 așteaptă `genereaza_cu_intrebare`. | Implementarea respectă testul. Măsura semidirectă cerută la Ib ≤ 100 A (V51) dă `genereaza` + întrebare + avertisment. Un tip BMPT inexistent dă `genereaza_cu_intrebare`. | Se precizează în F.7 regula „AVERTISMENT de motor + întrebare ⇒ genereaza”, sau F07 trece pe `genereaza_cu_intrebare`. |
| F29 vs B18 | B18 (golden) pune `bmpt_fortat = "BMPTd-63"` → motorul BLOCHEAZĂ (V50). F29 așteaptă ca interpretorul să genereze cu BMPTd-100 și să întrebe. | Pentru un tip inexistent, `intrare_fizica` NU conține `bmpt_fortat`, ci doar `extras.bmpt_cerut`. Motorul alege blocul, iar presupunerea se declară. Un tip existent („BMPTd-100 pentru 50 kW”) ajunge în `bmpt_fortat`. | Regula se trece în F.7 (de exemplu cod I13 „tip impus inexistent → generează cu tipul ST + întrebare”). |
| F03 vs B11 | F03 așteaptă `masura_ceruta = semidirecta` (din „BMPTi”). Cazul golden B11 („Chat bmpt_150”) nu are acest câmp. | Interpretorul pune `masura_ceruta` în intrare, conform F.5. Testul golden compară doar câmpurile prezente în cazul golden, deci trece. Rezultatul nu se schimbă: la Ib = 240 A se alege oricum BMPTi-250. | Se adaugă `"masura_ceruta": "semidirecta"` în B11. |
| F14 vs C02/C03 | C02 se numește „Chat cef_300” și NU are PT. C03 are PT 630 kVA, adăugat „cum îl propune interpretorul”. F14 (I11) cere ca interpretorul să adauge PT-ul. | `intrare_fizica` conține `pt_Sn_kVA = 630`, deci e egală cu C03. Față de C02 testul trece doar pe câmpurile comune (subset). | „Chat cef_300” se mută pe C03. C02 rămâne caz de motor (intrare fără PT → V66 BLOCANT). |
| F16 vs C05 | C05 („Chat cef_1mw_bess”) are `cablu_pcs = {Cu, XLPE, E}` și `L_pcs_m = 15`, care nu apar în textul F16. | Testul golden exclude explicit aceste două chei (`NU_DIN_TEXT`). | Se scot din C05 sau se adaugă în textul F16 („PCS la 15 m, cablu Cu XLPE pe pat”). |
| F05 | Presupunerea așteptată „secțiunea C2 mărită pentru ΔU” e un rezultat de dimensionare. Interpretorul nu dimensionează (F.1). | Se declară regula: „limita ΔU la bara TE ≤ 3 %: secțiunea C2 se mărește pentru ΔU dacă e necesar”. | Elementul se mută în `rezultat_cheie` / în verificările motorului. |
| F35, F15, F16, F13 | Presupunerile așteptate conțin alegeri de motor: MCCB pentru plecarea de 1000 A (B.3), categoria RfG, S = 1,1·ΣPn. | Interpretorul le declară ca presupuneri, cu aceleași formule (`norme.FACTOR_SMAX_INVERTOR`, `RFG_PRAG_TIP_B_KW`). Calculul real rămâne în motor. | Se acceptă (sunt informative). Altfel ar trebui mutate în verificările motorului. |
| F53 | „BMPT 200A” → `puteri.Ib_A = 200`. Forma `intrare` din golden nu are câmp Ib pentru branșament. | `intrare_fizica.P_kW = √3·400·200·0,9/1000 = 124,71` (Ib-ul echivalent e exact 200 A), declarat. | Se confirmă convenția sau se adaugă `Ib_A` în contractul de intrare al motorului. |
| F59 | „BMPT 25 kVA” → `puteri.S_kVA = 25`, cu Ib fără cosφ (B.2). | `intrare_fizica.P_kW = 25·0,9 = 22,5`. Motorul obține același Ib = 36,08 A cu cosφ 0,9. | La fel ca F53: se confirmă convenția sau se adaugă `S_kVA` în intrare. |
| F33 | „TD hală: N circuite …” descrie un tablou de distribuție cu circuite finale (B.3 rândul 2: MCB B/C, Cu C 25 m). Forma `intrare` nu are un câmp care să spună asta. | Se adaugă `intrare_fizica.circuite_finale = true`. Câmpul e nou: motorul trebuie să-l citească. | Câmpul se adaugă în contractul de intrare (sau rolul plecărilor). |
| F43 | „TG … din PT propriu” fără Sn. Contractul de intrare nu are un câmp pentru sursa unui tablou. | `intrare_fizica.origine = "pt_propriu"` (numele din B.1 `context_amonte`). Se întreabă Sn. | Câmpul se confirmă în contractul de intrare. |
| F11 | Gruparea pe „pat de cabluri” nu e în tiparele din F.5 („acelaşi pat”, „pat comun” …). Testul o cere totuși (golden T04: `n_alte = 3`). | Pozarea E pe „pat de cabluri” cu mai mult de o plecare ⇒ plecările se consideră pe același pat (grupare declarată). | Se adaugă tiparul în F.5. |
| F42 | „Măriți GE la cel puțin 100 kVA”: nu există o serie GE în `norme.py`. | Se propune puterea din seria `TRAFO_SN_KVA` ≥ P/0,9 (66,7 → 100 kVA). | Se adaugă `GE_SN_KVA` în norme. |

## Runda 2 (după `spec/ARBITRAJ.md`, SPEC v1.1)
Toate punctele de mai sus sunt arbitrate. În interpretor s-au aplicat:
- R1 (generează + întreabă ⇒ `genereaza_cu_intrebare`);
- R2/I13;
- `Ib_A` și `S_kVA` în `intrare_fizica`, în loc de P echivalent;
- `pt_Sn_kVA` lângă `origine`;
- `norme.ge_sn_minim`;
- textele noi de presupunere.

Testele citesc acum `intrare_motor` din fraze și `campuri_nu_din_text` din golden. Nu există puncte deschise.
