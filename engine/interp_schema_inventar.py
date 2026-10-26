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
"tipuri": [
"tablou"
]
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
"cef"
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
"backup.circuite[].nume": {
"t": [
"string"
],
"v": [
"Centrală termică",
"Frigider",
"Iluminat"
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
"iluminat"
],
"tipuri": [
"prosumator"
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
"tipuri": []
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
"SBH"
],
"tipuri": [
"cef"
]
},
"bess.n_module": {
"t": [
"number"
],
"v": [],
"tipuri": []
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
"Huawei",
"Sungrow"
],
"tipuri": [
"cef"
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
"cablu_C0.N_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"cablu_C0.S_fortat": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
]
},
"cablu_C0.izolatie": {
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
"cablu_C0.material": {
"t": [
"string"
],
"v": [
"Al",
"Cu"
],
"tipuri": [
"cef"
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
"pt"
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
"circuite[].nume": {
"t": [
"string"
],
"v": [
"Aer condiționat",
"Boiler",
"Centrală termică",
"Iluminat",
"Iluminat exterior",
"Iluminat interior",
"Mașină de spălat rufe",
"Plită",
"Pompă de căldură",
"Prize",
"Prize baie",
"Prize bucătărie",
"Prize camere",
"Prize exterior",
"Prize living",
"Încărcare VE"
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
"boiler",
"centrala_termica",
"cuptor",
"iluminat",
"incalzire_electrica",
"masina_spalat_rufe",
"masina_spalat_vase",
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
"circuite_casa[].P_kW": {
"t": [
"number"
],
"v": [],
"tipuri": [
"prosumator"
]
},
"circuite_casa[].nume": {
"t": [
"string"
],
"v": [
"Pompă de căldură"
],
"tipuri": [
"prosumator"
]
},
"circuite_casa[].receptor": {
"t": [
"string"
],
"v": [
"pompa_caldura"
],
"tipuri": [
"prosumator"
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
"Centrala termica",
"Clapete",
"Electropompa",
"Frig",
"Hidrofor",
"Iluminat",
"Iluminat siguranta",
"Pompa jockey",
"Pompa pilot",
"Pompa principala",
"Pompa rezerva",
"Pompe de incendiu",
"Pompe incendiu",
"Pompe x",
"Server",
"Ventilatoare desfumare"
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
"deschisa"
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
"excitatie_sustinuta": {
"t": [
"boolean"
],
"v": [],
"tipuri": []
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
"cef"
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
"MAX 30KTL3",
"MAX 50KTL3",
"S5-GC50K",
"SG110CX",
"SG125CX",
"SG50CX",
"SH25T",
"STP",
"SUN2000-100KTL",
"SUN2000-100KTL-M2",
"SUN2000-115KTL",
"SUN2000-50KTL",
"SUN2000-50KTL-M3",
"Sunny Tripower Core2",
"Symo",
"Tauro"
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
"invertoare[].sectie": {
"t": [
"number"
],
"v": [],
"tipuri": []
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
"8KTL",
"MID 25KTL3-X",
"Primo 5.0-1",
"S6-EH3P15K",
"SG50CX",
"SH10RT",
"SH25T",
"SUN-10 kW-SG04LP3-EU",
"SUN2000 10KTL M1",
"SUN2000-10KTL",
"SUN2000-10KTL-M1",
"SUN2000-15KTL-M2",
"SUN2000-20KTL-M2",
"SUN2000-30KTL-M3",
"SUN2000-50KTL-M3",
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
"locuinta"
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
"directa",
"semidirecta"
],
"tipuri": [
"bransament",
"pt"
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
"modul.model": {
"t": [
"string"
],
"v": [
"Hi-MO 6",
"JAM72D40",
"JAM72D40-575",
"TSM-NEG21C.20",
"Tiger Neo",
"Vertex",
"vertex S"
],
"tipuri": [
"cef"
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
"pt",
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
"plecari[].h3": {
"t": [
"number"
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
"plecari[].n_circuite": {
"t": [
"number"
],
"v": [],
"tipuri": [
"tablou"
]
},
"plecari[].nume": {
"t": [
"string"
],
"v": [
"Atelier",
"Birouri",
"Compresor",
"Cuptor",
"Depozit",
"Grajd",
"Hală",
"Hală 1",
"Hală 2",
"Iluminat",
"Iluminat hală",
"Iluminat parcare",
"Moară",
"Motoare 1",
"Motoare 2",
"Motoare 3"
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
"prize"
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
"tablou"
]
},
"plecari[].rezerva": {
"t": [
"boolean"
],
"v": [],
"tipuri": [
"pt",
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
"cef"
]
},
"string.gpv_In_A": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
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
"cef"
]
},
"string.n_stringuri_paralel": {
"t": [
"number"
],
"v": [],
"tipuri": [
"cef"
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
"tablouri_secundare[].L_m": {
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
"v": [],
"tipuri": []
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
"tablouri_secundare[].circuite[].nume": {
"t": [
"string"
],
"v": [
"Aer condiționat 1",
"Aer condiționat 2",
"Compresor",
"Iluminat",
"Iluminat 1",
"Iluminat 2",
"Plita",
"Prize",
"Prize 1",
"Prize 2",
"Prize 3",
"Prize 4",
"Strung"
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
"iluminat",
"motor",
"prize"
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
"TD Atelier",
"TD Garaj",
"TE Etaj"
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
"TE desfumare",
"Tablou desfumare",
"Tablou pompe incendiu",
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
"xd": {
"t": [
"number"
],
"v": [],
"tipuri": []
}
}
