"""GENERAT de `python3 -m engine.interp_schema --genereaza` — nu se editează de mână.
Cale (a.b[].c) → tipuri JSON observate, valori text observate, tipurile de schemă la care apare."""
INVENTAR = {
"ATS_interblocaj": {
"t": [
"string"
],
"v": [],
"tipuri": []
},
"ATS_poli": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"DDR_GE": {
"t": [
"boolean"
],
"v": [],
"tipuri": []
},
"Ib_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"bransament"
]
},
"Ib_sarcina_A": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"IdN_amonte_mA": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"Ik3_OD_kA": {
"t": [
"number"
],
"v": [],
"tipuri": [
"bransament",
"cef",
"locuinta",
"prosumator"
]
},
"Ik3_TG_kA": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"Ik3_bara_kA": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"Ik3_sursa_kA": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"In_A": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"In_Q1_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"tablou"
]
},
"In_QG_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"In_Q_JT_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt"
]
},
"In_Q_amonte_A": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"In_Q_bransament_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"In_Q_retea_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"ge_ats"
]
},
"L_C1_m": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"L_C2_m": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"L_GE_ATS_m": {
"t": [
"number"
],
"v": [],
"tipuri": [
"ge_ats"
]
},
"L_alimentare_m": {
"t": [
"number"
],
"v": [],
"tipuri": [
"tablou"
]
},
"L_coloana_m": {
"t": [
"number"
],
"v": [],
"tipuri": [
"bransament",
"prosumator"
]
},
"L_inv_m": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"L_pcs_m": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"L_racord_m": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"PI_externa": {
"t": [
"boolean"
],
"v": [],
"tipuri": []
},
"P_aprobata_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"P_evacuata_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"P_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"bransament",
"tablou"
]
},
"P_sarcina_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"ge_ats"
]
},
"Pn_inv_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"prosumator"
]
},
"QG.Icu_kA": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"QG.In_A": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"QG.Ir_reglat": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"QG.Isd_reglat": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"QG.electronic": {
"t": [
"boolean"
],
"v": [],
"tipuri": []
},
"QG.motorizat": {
"t": [
"boolean"
],
"v": [],
"tipuri": []
},
"Q_In_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"bransament"
]
},
"Q_general_tip": {
"t": [
"string"
],
"v": [
"ACB"
],
"tipuri": [
"pt"
]
},
"RA_ohm": {
"t": [
"number"
],
"v": [],
"tipuri": [
"bransament",
"cef",
"locuinta",
"prosumator",
"tablou"
]
},
"S_kVA": {
"t": [
"number"
],
"v": [],
"tipuri": [
"bransament"
]
},
"SkQ_MVA": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt"
]
},
"Sn_GE_kVA": {
"t": [
"number"
],
"v": [],
"tipuri": [
"ge_ats"
]
},
"Sn_kVA": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt"
]
},
"U_JT_V": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"U_MT_kV": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt"
]
},
"U_V": {
"t": [
"number"
],
"v": [],
"tipuri": [
"tablou"
]
},
"U_ca_V": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"U_inv_ca_V": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"Zb_OD_ohm": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"locuinta"
]
},
"Zb_TG_ohm": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"aar": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"pt"
]
},
"alimentare.In_Q_bransament_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"locuinta"
]
},
"alimentare.L_coloana_m": {
"t": [
"number"
],
"v": [],
"tipuri": [
"locuinta"
]
},
"alimentare.P_aprobata_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"locuinta"
]
},
"alimentare.cablu.S_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"locuinta"
]
},
"alimentare.cablu.material": {
"t": [
"string"
],
"v": [
"Al",
"Cu"
],
"tipuri": [
"locuinta"
]
},
"alimentare.cablu.metoda": {
"t": [
"string"
],
"v": [
"D1"
],
"tipuri": [
"locuinta"
]
},
"alimentare.cablu.tip_cablu": {
"t": [
"string"
],
"v": [
"ACYABY",
"CYABY",
"CYY-F"
],
"tipuri": [
"locuinta"
]
},
"alimentare.tip": {
"t": [
"string"
],
"v": [
"bransament_existent",
"bransament_nou"
],
"tipuri": [
"locuinta"
]
},
"atr_jt": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"cef"
]
},
"backup.N_comutat": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"prosumator"
]
},
"backup.circuite[].nume": {
"t": [
"string"
],
"v": [
"Centrală termică",
"Frigider",
"Iluminat",
"Pompă apă",
"Router"
],
"tipuri": [
"prosumator"
]
},
"backup.circuite[].receptor": {
"t": [
"string"
],
"v": [
"alt_circuit",
"centrala_termica",
"iluminat",
"pompa_apa"
],
"tipuri": [
"prosumator"
]
},
"backup.comutare": {
"t": [
"string"
],
"v": [
"ATS"
],
"tipuri": [
"prosumator"
]
},
"backup.toata_casa": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"prosumator"
]
},
"bara": {
"t": [
"string"
],
"v": [
"T1",
"T2"
],
"tipuri": [
"cef"
]
},
"bara_vitala": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"ge_ats"
]
},
"baterie.kWh": {
"t": [
"number"
],
"v": [],
"tipuri": [
"prosumator"
]
},
"baterie.model": {
"t": [
"string"
],
"v": [
"LUNA2000",
"LUNA2000-10-S0",
"LUNA2000-15-S0",
"LUNA2000-5-S0",
"US5000"
],
"tipuri": [
"prosumator"
]
},
"baterie.producator": {
"t": [
"string"
],
"v": [
"BYD",
"Huawei",
"Pylontech"
],
"tipuri": [
"prosumator"
]
},
"baterie_kWh": {
"t": [
"number"
],
"v": [],
"tipuri": [
"prosumator"
]
},
"bess.P_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"bess.cuplaj": {
"t": [
"string"
],
"v": [
"ca",
"cc"
],
"tipuri": [
"cef",
"prosumator"
]
},
"bess.kWh": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"bess.kWh_modul": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"bess.model": {
"t": [
"string"
],
"v": [
"Battery-Box",
"Battery-Box Premium HVM",
"LUNA2000",
"LUNA2000-200KWH-2H1",
"LUNA2000-215-2S10",
"PowerStack",
"PowerStack 200CS",
"PowerStack 255CS",
"SBH",
"SUN-12K-SG04LP3-EU"
],
"tipuri": [
"cef",
"prosumator"
]
},
"bess.n_module": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"bess.n_pcs": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"bess.pcs.Pn_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"bess.pcs.model": {
"t": [
"string"
],
"v": [],
"tipuri": []
},
"bess.pcs.n": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"bess.pcs.producator": {
"t": [
"string"
],
"v": [],
"tipuri": []
},
"bess.producator": {
"t": [
"string"
],
"v": [
"BYD",
"Deye",
"Huawei",
"Sungrow"
],
"tipuri": [
"cef",
"prosumator"
]
},
"bmpt_fortat": {
"t": [
"string"
],
"v": [
"BMPTd-63"
],
"tipuri": [
"bransament"
]
},
"cablu.N_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"tablou"
]
},
"cablu.S_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"bransament",
"tablou"
]
},
"cablu.existent": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"tablou"
]
},
"cablu.izolatie": {
"t": [
"string"
],
"v": [
"XLPE"
],
"tipuri": [
"bransament",
"tablou"
]
},
"cablu.material": {
"t": [
"string"
],
"v": [
"Al",
"Cu"
],
"tipuri": [
"bransament",
"tablou"
]
},
"cablu.metoda": {
"t": [
"string"
],
"v": [
"C",
"D1",
"D2",
"E"
],
"tipuri": [
"bransament",
"tablou"
]
},
"cablu.n_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"tablou"
]
},
"cablu.n_paralel": {
"t": [
"number"
],
"v": [],
"tipuri": [
"tablou"
]
},
"cablu.tip_cablu": {
"t": [
"string"
],
"v": [
"ACYABY",
"CYABY",
"CYY-F",
"NA2XY"
],
"tipuri": [
"tablou"
]
},
"cablu_C0.N_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"cablu_C0.S_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"cablu_C0.izolatie": {
"t": [
"string"
],
"v": [
"PVC",
"XLPE"
],
"tipuri": [
"cef",
"prosumator"
]
},
"cablu_C0.material": {
"t": [
"string"
],
"v": [
"Al",
"Cu"
],
"tipuri": [
"cef",
"prosumator"
]
},
"cablu_C0.n_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"cablu_C0.tip_cablu": {
"t": [
"string"
],
"v": [
"ACYABY",
"CYABY",
"NA2XY",
"NYY-J"
],
"tipuri": [
"cef",
"prosumator"
]
},
"cablu_C0.tronsoane[].L": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"cablu_C0.tronsoane[].S_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"cablu_C0.tronsoane[].material": {
"t": [
"string"
],
"v": [],
"tipuri": []
},
"cablu_C0.tronsoane[].n_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"cablu_MT.L_m": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt"
]
},
"cablu_MT.S_mm2": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt"
]
},
"cablu_MT.U0_U_kV": {
"t": [
"string"
],
"v": [
"18/30"
],
"tipuri": [
"pt"
]
},
"cablu_MT.tip": {
"t": [
"string"
],
"v": [
"A2XS"
],
"tipuri": [
"pt"
]
},
"cablu_MT.tronsoane[].L_m": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"cablu_cc.S_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"cablu_cc.material": {
"t": [
"string"
],
"v": [
"Cu"
],
"tipuri": [
"cef"
]
},
"cablu_cc.tip_cablu": {
"t": [
"string"
],
"v": [
"H1Z2Z2-K"
],
"tipuri": [
"cef"
]
},
"cablu_inv.S_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"cablu_inv.izolatie": {
"t": [
"string"
],
"v": [
"PVC"
],
"tipuri": [
"cef"
]
},
"cablu_inv.material": {
"t": [
"string"
],
"v": [
"Cu"
],
"tipuri": [
"cef"
]
},
"cablu_inv.metoda": {
"t": [
"string"
],
"v": [
"E"
],
"tipuri": [
"cef",
"prosumator"
]
},
"cablu_inv.tip_cablu": {
"t": [
"string"
],
"v": [
"CYY-F",
"NYY-J"
],
"tipuri": [
"cef"
]
},
"cablu_pcs.izolatie": {
"t": [
"string"
],
"v": [
"XLPE"
],
"tipuri": [
"cef"
]
},
"cablu_pcs.material": {
"t": [
"string"
],
"v": [
"Cu"
],
"tipuri": [
"cef"
]
},
"cablu_pcs.metoda": {
"t": [
"string"
],
"v": [
"E"
],
"tipuri": [
"cef"
]
},
"celula_trafo": {
"t": [
"string"
],
"v": [
"intreruptor",
"sigurante"
],
"tipuri": [
"pt"
]
},
"celule_mt": {
"t": [
"array"
],
"v": [],
"tipuri": [
"cef",
"pt"
]
},
"circuite[].In_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"locuinta"
]
},
"circuite[].L_m": {
"t": [
"number"
],
"v": [],
"tipuri": [
"locuinta"
]
},
"circuite[].P_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"locuinta"
]
},
"circuite[].cablu.S_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"locuinta"
]
},
"circuite[].cablu.material": {
"t": [
"string"
],
"v": [
"Cu"
],
"tipuri": [
"locuinta"
]
},
"circuite[].curba": {
"t": [
"string"
],
"v": [
"C"
],
"tipuri": [
"locuinta"
]
},
"circuite[].faza": {
"t": [
"string"
],
"v": [
"3F",
"L1",
"L2",
"L3"
],
"tipuri": [
"locuinta"
]
},
"circuite[].multisplit": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"locuinta"
]
},
"circuite[].nume": {
"t": [
"string"
],
"v": [
"Aer condiționat 1",
"Aer condiționat 2",
"Boiler",
"Cuptor",
"Frigider",
"Iluminat",
"Mașină de spălat rufe",
"Plită",
"Pompă de căldură",
"Prize",
"Prize 1",
"Prize 2",
"Prize 3",
"Prize baie",
"Prize bucătărie",
"Rezistență electrică"
],
"tipuri": [
"locuinta"
]
},
"circuite[].receptor": {
"t": [
"string"
],
"v": [
"aer_conditionat",
"alt_circuit",
"boiler",
"centrala_termica",
"cuptor",
"iluminat",
"incalzire_electrica",
"masina_spalat_rufe",
"plita",
"pompa_caldura",
"prize",
"prize_baie",
"prize_bucatarie",
"prize_exterior",
"sauna",
"vehicul_electric"
],
"tipuri": [
"locuinta"
]
},
"circuite[].retea": {
"t": [
"string"
],
"v": [
"tri"
],
"tipuri": [
"locuinta"
]
},
"circuite[].unitati_interioare": {
"t": [
"number"
],
"v": [],
"tipuri": [
"locuinta"
]
},
"circuite_finale": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"tablou"
]
},
"comercial": {
"t": [
"boolean"
],
"v": [],
"tipuri": []
},
"compensare_L_m": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"compensare_kvar": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt",
"tablou"
]
},
"comutare": {
"t": [
"string"
],
"v": [
"manual"
],
"tipuri": [
"ge_ats"
]
},
"consumatori[].P_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"ge_ats"
]
},
"consumatori[].n": {
"t": [
"number",
"string"
],
"v": [
"1+1"
],
"tipuri": [
"ge_ats"
]
},
"consumatori[].nume": {
"t": [
"string"
],
"v": [
"ATI",
"Bloc operator",
"Bucătărie",
"Concasor",
"HVAC",
"Hrănire automată",
"Iluminat",
"Iluminat siguranță",
"Lifturi",
"Plus pompă jockey",
"Pompă de incendiu",
"Pompă jockey",
"Pompă principală",
"Spălătorie",
"Ventilatoare de desfumare",
"Ventilație"
],
"tipuri": [
"ge_ats"
]
},
"consumatori[].pornire": {
"t": [
"string"
],
"v": [
"convertizor",
"directa",
"stea_triunghi"
],
"tipuri": [
"ge_ats"
]
},
"consumatori[].rezerva": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"ge_ats"
]
},
"consumatori[].siguranta": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"ge_ats"
]
},
"consumatori[].vital": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"ge_ats"
]
},
"contor_productie.tip": {
"t": [
"string"
],
"v": [],
"tipuri": []
},
"cosfi": {
"t": [
"number"
],
"v": [],
"tipuri": [
"bransament",
"tablou"
]
},
"cupla": {
"t": [
"string"
],
"v": [
"deschisa",
"inchisa"
],
"tipuri": [
"pt"
]
},
"ddr_amonte": {
"t": [
"boolean"
],
"v": [],
"tipuri": []
},
"dg_intreruptor": {
"t": [
"boolean"
],
"v": [],
"tipuri": []
},
"excitatie_sustinuta": {
"t": [
"boolean"
],
"v": [],
"tipuri": []
},
"fara_retea": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"ge_ats"
]
},
"ge_paralel": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"ge_ats"
]
},
"gpv_In_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"grupa_conexiuni": {
"t": [
"string"
],
"v": [
"Dyn11"
],
"tipuri": [
"pt"
]
},
"h3": {
"t": [
"number"
],
"v": [],
"tipuri": [
"tablou"
]
},
"hibrid": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"prosumator"
]
},
"invertoare[].Iac_max_A": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"invertoare[].L_m": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"invertoare[].Pn_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"invertoare[].U_ca_V": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"invertoare[].cablu.S_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"invertoare[].cablu.material": {
"t": [
"string"
],
"v": [],
"tipuri": []
},
"invertoare[].existent": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"invertoare[].faza": {
"t": [
"string"
],
"v": [
"L1",
"L2",
"L3"
],
"tipuri": [
"cef",
"prosumator"
]
},
"invertoare[].hibrid": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"invertoare[].model": {
"t": [
"string"
],
"v": [
"MOD 10KTL3-X",
"Primo 6.0-1",
"SG110CX-P2",
"SG30CX",
"SG350HX",
"SG50CX",
"SUN-15K-SG01HP3",
"SUN2000-100KTL-M2",
"SUN2000-10KTL-M1",
"SUN2000-20KTL-M3",
"SUN2000-25KTL-M5",
"SUN2000-30KTL-M3",
"SUN2000-330KTL-H1",
"SUN2000-50KTL-M3",
"Symo 20.0-3-M",
"Tauro 50-3-D"
],
"tipuri": [
"cef",
"prosumator"
]
},
"invertoare[].n": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"invertoare[].producator": {
"t": [
"string"
],
"v": [
"Deye",
"Fronius",
"GoodWe",
"Growatt",
"Huawei",
"SMA",
"SolarEdge",
"Solis",
"Sungrow"
],
"tipuri": [
"cef",
"prosumator"
]
},
"invertoare[].prot_tip": {
"t": [
"string"
],
"v": [],
"tipuri": []
},
"invertoare[].protectie.Icu_kA": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"invertoare[].protectie.In_A": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"invertoare[].protectie.Ir_reglat": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"invertoare[].protectie.electronic": {
"t": [
"boolean"
],
"v": [],
"tipuri": []
},
"invertoare[].sectie": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"invertoare[].string.n_MPPT": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"invertoare[].string.n_module": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"invertoare[].string.n_stringuri_paralel": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"invertoare[].tablou": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"invertoare[].tgd": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"invertor.Pn_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"prosumator"
]
},
"invertor.hibrid": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"prosumator"
]
},
"invertor.model": {
"t": [
"string"
],
"v": [
"MIN 6000TL-X",
"MOD 10KTL3-X",
"Primo 6.0-1",
"S5-GC60K",
"SH25T",
"SUN-12K-SG04LP3",
"SUN-15K-SG01HP3",
"SUN-15K-SG01HP3-EU",
"SUN2000-100KTL-M2",
"SUN2000-10KTL",
"SUN2000-10KTL-M1",
"SUN2000-25KTL-M5",
"SUN2000-50KTL-M3",
"SUN2000-5KTL-L1",
"SUN2000-60KTL-M0",
"SUN2000-6KTL-L1"
],
"tipuri": [
"prosumator"
]
},
"invertor.producator": {
"t": [
"string"
],
"v": [
"Deye",
"Fronius",
"Growatt",
"Huawei",
"SMA",
"SolarEdge",
"Solis",
"Sungrow"
],
"tipuri": [
"prosumator"
]
},
"kWp": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"ks": {
"t": [
"number"
],
"v": [],
"tipuri": [
"locuinta",
"tablou"
]
},
"limitare_injectie_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"masura": {
"t": [
"string"
],
"v": [
"JT",
"MT"
],
"tipuri": [
"cef",
"pt"
]
},
"masura_ceruta": {
"t": [
"string"
],
"v": [
"semidirecta"
],
"tipuri": [
"bransament"
]
},
"material": {
"t": [
"string"
],
"v": [
"Al",
"Cu"
],
"tipuri": [
"bransament"
]
},
"modul.I_rev_A": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"modul.Impp_A": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"modul.Pmax_W": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"modul.Umax_sistem_V": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"modul.Vmpp_V": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"modul.model": {
"t": [
"string"
],
"v": [
"Hi-MO 6",
"JAM72D40",
"JAM72D40-575",
"JAM72S30",
"TSM-NEG21C.20",
"Tiger Neo",
"Vertex",
"Vertex S",
"vertex S"
],
"tipuri": [
"cef",
"prosumator"
]
},
"modul.producator": {
"t": [
"string"
],
"v": [
"JA Solar",
"Jinko Solar",
"LONGi",
"Trina Solar"
],
"tipuri": [
"cef",
"prosumator"
]
},
"monitorizare.contor_productie.tip": {
"t": [
"string"
],
"v": [],
"tipuri": []
},
"monitorizare.rs485": {
"t": [
"boolean"
],
"v": [],
"tipuri": []
},
"monitorizare.smart_meter.TC_primar_A": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"monitorizare.smart_meter.model": {
"t": [
"string"
],
"v": [
"DTSU666-H"
],
"tipuri": [
"cef"
]
},
"monitorizare.smartlogger.model": {
"t": [
"string"
],
"v": [],
"tipuri": []
},
"n_tgd_cf": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"n_trafo": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"pt"
]
},
"origine": {
"t": [
"string"
],
"v": [
"bmpt",
"pt_propriu",
"tg_existent"
],
"tipuri": [
"tablou"
]
},
"plecari[].Ib_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].Icu_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt"
]
},
"plecari[].In_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].L_m": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].P_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].S_kVA": {
"t": [
"number"
],
"v": [],
"tipuri": [
"tablou"
]
},
"plecari[].Sn_kVA": {
"t": [
"number"
],
"v": [],
"tipuri": [
"tablou"
]
},
"plecari[].bypass": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"tablou"
]
},
"plecari[].cablu.N_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"tablou"
]
},
"plecari[].cablu.PE_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].cablu.PE_loc": {
"t": [
"string"
],
"v": [
"separat"
],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].cablu.S_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].cablu.izolatie": {
"t": [
"string"
],
"v": [
"XLPE"
],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].cablu.material": {
"t": [
"string"
],
"v": [
"Al",
"Cu"
],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].cablu.metoda": {
"t": [
"string"
],
"v": [
"C",
"D1",
"E"
],
"tipuri": [
"tablou"
]
},
"plecari[].cablu.n_alte": {
"t": [
"number"
],
"v": [],
"tipuri": [
"tablou"
]
},
"plecari[].cablu.n_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt"
]
},
"plecari[].cablu.rezistent_foc": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"tablou"
]
},
"plecari[].cablu.tip_cablu": {
"t": [
"string"
],
"v": [
"CYABY",
"CYY",
"CYY-F",
"NHXH"
],
"tipuri": [
"tablou"
]
},
"plecari[].copii": {
"t": [
"array"
],
"v": [],
"tipuri": [
"tablou"
]
},
"plecari[].cosfi": {
"t": [
"number"
],
"v": [],
"tipuri": [
"tablou"
]
},
"plecari[].curba": {
"t": [
"string"
],
"v": [
"B",
"C"
],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].ddr.tip": {
"t": [
"string"
],
"v": [
"B"
],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].faza": {
"t": [
"string"
],
"v": [
"L1",
"L2",
"L3"
],
"tipuri": [
"tablou"
]
},
"plecari[].h3": {
"t": [
"number"
],
"v": [],
"tipuri": [
"tablou"
]
},
"plecari[].intrari_separate": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"tablou"
]
},
"plecari[].ks": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].n": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].n_circuite": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].nume": {
"t": [
"string"
],
"v": [
"Atelier",
"Benzi 1",
"Benzi 2",
"Birouri",
"Cuptor",
"Depozit",
"Grajd",
"Hală",
"Hală 1",
"Hală 2",
"Iluminat",
"Iluminat 1",
"Iluminat hală",
"Iluminat parcare",
"Moară",
"Motoare 1"
],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].pornire": {
"t": [
"string"
],
"v": [
"convertizor",
"directa",
"soft",
"stea_triunghi"
],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].prot_tip": {
"t": [
"string"
],
"v": [
"GG",
"MCB",
"MCCB"
],
"tipuri": [
"pt"
]
},
"plecari[].receptor": {
"t": [
"string"
],
"v": [
"iluminat",
"motor",
"prize",
"ups"
],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].retea": {
"t": [
"string"
],
"v": [
"mono",
"tri"
],
"tipuri": [
"pt",
"tablou"
]
},
"plecari[].rezerva": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"tablou"
]
},
"plecari[].sectie": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt"
]
},
"plecari[].siguranta": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"tablou"
]
},
"plecari[].ups": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"tablou"
]
},
"plecari_pe_sectie": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"pt"
]
},
"plecari_pe_semibara": {
"t": [
"boolean"
],
"v": [],
"tipuri": []
},
"protectie_interfata.releu": {
"t": [
"string"
],
"v": [],
"tipuri": []
},
"protectie_interfata.ups_VA": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"pt_Sn_kVA": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"ge_ats",
"tablou"
]
},
"pt_aerian": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"pt"
]
},
"pt_existent": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"cef"
]
},
"pt_od": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"cef"
]
},
"punct_conexiune.aar": {
"t": [
"boolean"
],
"v": [],
"tipuri": []
},
"punct_conexiune.celule_linie": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"punct_conexiune.servicii_proprii_kVA": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"racord": {
"t": [
"string"
],
"v": [
"bmpt",
"pt",
"tg_existent"
],
"tipuri": [
"cef",
"prosumator"
]
},
"racord_Icu_kA": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"racord_In_Q_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"retea": {
"t": [
"string"
],
"v": [
"mono",
"tri"
],
"tipuri": [
"bransament",
"cef",
"ge_ats",
"locuinta",
"prosumator",
"tablou"
]
},
"schema_pamant": {
"t": [
"string"
],
"v": [
"IT",
"TN-C",
"TN-C-S",
"TN-S",
"TT"
],
"tipuri": [
"bransament",
"cef",
"ge_ats",
"locuinta",
"prosumator",
"pt",
"tablou"
]
},
"separare_PEN": {
"t": [
"string"
],
"v": [
"BMPT",
"TG"
],
"tipuri": [
"locuinta",
"tablou"
]
},
"siguranta_tablou": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"ge_ats",
"tablou"
]
},
"string.I_rev_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"string.Isc_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"string.Umax_inv_V": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"string.Uoc_V": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"string.beta": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"string.gpv": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"string.gpv_In_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"string.n_MPPT": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"string.n_module": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"string.n_stringuri_paralel": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef",
"prosumator"
]
},
"sursa_retea": {
"t": [
"string"
],
"v": [
"bmpt",
"pt",
"tgd"
],
"tipuri": [
"ge_ats"
]
},
"sursa_rezerva": {
"t": [
"string"
],
"v": [
"trafo"
],
"tipuri": []
},
"tablouri_intermediare[].In_A": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"tablouri_intermediare[].L_m": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"tablouri_intermediare[].cablu.S_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"tablouri_intermediare[].cablu.material": {
"t": [
"string"
],
"v": [],
"tipuri": []
},
"tablouri_intermediare[].cablu.n_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"tablouri_intermediare[].nume": {
"t": [
"string"
],
"v": [],
"tipuri": []
},
"tablouri_intermediare[].prot_tip": {
"t": [
"string"
],
"v": [],
"tipuri": []
},
"tablouri_secundare[].L_m": {
"t": [
"number"
],
"v": [],
"tipuri": [
"locuinta"
]
},
"tablouri_secundare[].P_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"locuinta"
]
},
"tablouri_secundare[].cablu.S_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"locuinta"
]
},
"tablouri_secundare[].cablu.material": {
"t": [
"string"
],
"v": [
"Cu"
],
"tipuri": [
"locuinta"
]
},
"tablouri_secundare[].cablu.n_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": []
},
"tablouri_secundare[].circuite[].In_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"locuinta"
]
},
"tablouri_secundare[].circuite[].P_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"locuinta"
]
},
"tablouri_secundare[].circuite[].faza": {
"t": [
"string"
],
"v": [
"L1"
],
"tipuri": [
"locuinta"
]
},
"tablouri_secundare[].circuite[].nume": {
"t": [
"string"
],
"v": [
"Bai cu incalzitor prosop 1",
"Bai cu incalzitor prosop 2",
"Compresor",
"Corp B (consum total)",
"Electroliză sare",
"Iluminat bucătărie",
"Iluminat living",
"Pompă de căldură piscină",
"Pompă filtrare",
"Pompă piscină",
"Prize 1",
"Prize 2",
"Prize bucătărie",
"Prize living",
"Stație VE",
"VE"
],
"tipuri": [
"locuinta"
]
},
"tablouri_secundare[].circuite[].receptor": {
"t": [
"string"
],
"v": [
"aer_conditionat",
"alt_circuit",
"iluminat",
"incalzire_electrica",
"motor",
"plita",
"poarta_automata",
"pompa_apa",
"pompa_caldura",
"prize",
"prize_bucatarie",
"vehicul_electric"
],
"tipuri": [
"locuinta"
]
},
"tablouri_secundare[].circuite[].retea": {
"t": [
"string"
],
"v": [
"mono",
"tri"
],
"tipuri": [
"locuinta"
]
},
"tablouri_secundare[].faza": {
"t": [
"string"
],
"v": [
"3F"
],
"tipuri": [
"locuinta"
]
},
"tablouri_secundare[].nume": {
"t": [
"string"
],
"v": [
"TD Anexa",
"TD Anexă",
"TD Atelier",
"TD Corp B",
"TD Garaj",
"TD Mansarda",
"TD Piscină",
"TD piscină",
"TE Etaj",
"TE Garaj",
"TE Parter"
],
"tipuri": [
"locuinta"
]
},
"tablouri_secundare[].retea": {
"t": [
"string"
],
"v": [
"mono"
],
"tipuri": [
"locuinta"
]
},
"tip_schema": {
"t": [
"string"
],
"v": [
"bransament",
"cef",
"ge_ats",
"locuinta",
"prosumator",
"pt",
"tablou"
],
"tipuri": [
"bransament",
"cef",
"ge_ats",
"locuinta",
"prosumator",
"pt",
"tablou"
]
},
"titlu_tablou": {
"t": [
"string"
],
"v": [
"Statie hidranti",
"Stație sprinklere",
"TE desfumare",
"TE hidranti",
"TE lift pompieri",
"Tablou TDSI",
"Tablou desfumare",
"Tablou iluminat de siguranta",
"Tablou pompe incendiu",
"Tablou pompe sprinklere",
"statie pompare PSI",
"tablou TDSI"
],
"tipuri": [
"ge_ats",
"tablou"
]
},
"trafo_izolatie": {
"t": [
"string"
],
"v": [
"ulei",
"uscat"
],
"tipuri": [
"pt"
]
},
"uk_pct": {
"t": [
"number"
],
"v": [],
"tipuri": [
"pt"
]
},
"xd": {
"t": [
"number"
],
"v": [],
"tipuri": []
}
}
