FRAZE = [
 # A. CEF cu invertoare identice (1..10)
 "cef 50kwp un singur invertor huawei SUN2000-50KTL-M3, module JA Solar JAM72D40 575Wp, racord in TG existent, cablu 35m al, retea TN-C-S",
 "CEF 110 kWp cu invertor Sungrow SG110CX, 192 module LONGi Hi-MO 6 575 Wp, 16 module/string, 12 stringuri, racord BMPT nou 3f, L=70m",
 "pv 240 kwp, 2 x SG110CX sungrow + module trina vertex S+ 445W, racord in TG existent fabrica, Ik la bara 20 kA, intrerupator in TG 400A",
 "CEF 330 kWp la sol, 3 inv Huawei SUN2000-100KTL-M2, Jinko Tiger Neo 620Wp, PT propriu nou 400 kVA, cablu 120 m",
 "centrala fotovoltaica 500 kWp, 4 bucati SMA Sunny Tripower CORE2 110 kW, PT propriu nou 630 kVA, trifazat, TN-S",
 "CEF 600kWp cu 5 x Huawei SUN2000-115KTL-M2 115kW, racord in PT existent 1000 kVA al beneficiarului, cablu 4x(1x240) Al 180 m",
 "CEF 0,8 MWp, 6 invertoare Sungrow SG125CX-P2, module JA 580 Wp, PT nou 1000 kVA, retea trifazata",
 "cef 1,1 MWp - 8 inv x 125 kw sungrow, PT nou 1250 kVA, cablu 250 m pana la TGD",
 "CEF 1,3 MWp, 10 invertoare Huawei SUN2000-115KTL-M2, PT propriu 1600 kVA nou, Jinko 600W",
 "CEF 160 kWp, 2 invertoare Fronius Tauro ECO 50-3-D + 1 Fronius Tauro 50-3-D, racord TG existent, cablu Cu 40m",
 # B. invertoare mixte
 "CEF 150 kwp: 1x Huawei SUN2000-100KTL-M2 + 1x Huawei SUN2000-50KTL-M3, racord in TG existent, 60 m",
 "cef 270 kWp cu 2 inv Sungrow SG110CX si 1 inv SG50CX, racord in tg existent, Q TG 630 A",
 "fotovoltaic 95 kwp, invertor 1 = Growatt MAX 60KTL3-X LV, invertor 2 = Growatt MOD 15KTL3-X, racord BMPT existent 160 A",
 "CEF 400 kWp; 3 x Solis S5-GC100K + 1 x Solis S5-GC50K; PT propriu existent 630 kVA; cablu 90 m",
 "CEF 210 kWp cu 1 SMA STP 110-60 si 2 SMA STP 50-41, retea TT, priza de pamant 2 ohm, racord TG existent",
 "CEF 75 kWp cu Huawei SUN2000-30KTL-M3 x2 si SUN2000-12KTL-M5 x1, racord in TG",
 # C. stringuri / gPV declarate
 "CEF 60 kWp, invertor Huawei SUN2000-50KTL-M3, module LONGi 545Wp, 110 module, 10 stringuri x 11, gPV 20A pe fiecare string, SPD DC tip 2",
 "cef 100kwp cu 1 invertor solis 100kw cu 10 mppt, 3 stringuri pe mppt, siguranta gPV 15 A, module JA 550, racord tg existent",
 "CEF 120 kWp, SG110CX, string 18 module x 12 stringuri, Voc modul 49,6 V, Isc 13,9 A, racord BMPT",
 # D. BESS cuplat c.c. / c.a.
 "CEF 200 kWp cu 2 x SUN2000-100KTL-M2 si BESS Huawei LUNA2000-215-2S10 (108 kW / 215 kWh) cuplat in c.a., racord TG existent, PT propriu 630 kVA existent",
 "CEF 100 kWp cu invertor hibrid Sungrow SH50T x2, baterii Sungrow SBH 40 kWh fiecare (cuplaj c.c.), racord in TG existent",
 "CEF 500 kWp cu 4 x 110 kW si stocare Sungrow PowerStack 255CS 125kW/257kWh cuplata ca, PT nou 800 kVA",
 "cef 300 kwp + BESS BYD Battery-Box Premium HVM 100 kWh cu PCS 50 kW, 3 invertoare de 100kw, racord TG existent, PT existent 1000 kVA",
 "CEF 1 MWp cu 8 x 125 kW si BESS 1 MWh / 500 kW cuplaj c.a., PT nou 2000 kVA, injectie limitata la 600 kW",
 # E. BESS singur
 "BESS 250 kW / 500 kWh Huawei LUNA2000, racord in TG existent, PT propriu existent 1000 kVA, cablu 80 m",
 "sistem de stocare 100 kWh / 50 kW BYD, fara fotovoltaic, in TG existent al halei",
 "BESS standalone 1 MW / 2 MWh PowerStack, PT nou 1250 kVA",
 # F. injectie zero / limitata
 "CEF 250 kWp, 2 x Huawei SUN2000-100KTL-M2, injectie zero, Smart Dongle + contor DTSU666-H la PCC, racord TG existent, PT existent 630 kVA",
 "CEF 180 kWp cu 3 invertoare Sungrow SG50CX, injectie limitata la 50 kW conform ATR, Logger1000, racord BMPT",
 "prosumator 90 kW trifazic, 2 inv Huawei SUN2000-40KTL + 1 SUN2000-10KTL, fara injectie in retea, TG existent",
 # G. racord: TG existent / BMPT / PT existent / PT nou
 "CEF 400 kWp, 4x100 kW, racord in TG existent, fara alte date",
 "CEF 45 kWp, invertor Solis S5-GC40K, racord prin BMPT 63 A existent, L 25 m",
 "CEF 700 kWp cu 6 invertoare Sungrow SG110CX, racord in celula JT a PT-ului existent 1000 kVA al OD conform ATR",
 # H. monofazat / TT / cabluri impuse
 "prosumator monofazat 6 kW, invertor Huawei SUN2000-6KTL-L1, 12 module JA 500W, racord in TE locuinta",
 "CEF 40 kWp cu invertor Fronius Symo 20 kW x2, retea monofazata",
 "CEF 90 kWp, invertor Huawei SUN2000-100KTL-M2, retea TT Ra 10 ohm, cablu CYABY 4x70 Cu 50 m",
 "cef 130 kwp 1 x SG125CX, cablu impus NA2XY 3x150+70 Al, 110m, racord in TG existent",
 # I. prosumatori < si > 27 kW
 "prosumator 10 kW trifazat, Huawei SUN2000-10KTL-M1, baterie LUNA2000 10 kWh, casa P+1, TE existent",
 "prosumator 27 kW trifazat, invertor Growatt MID 25KTL3-X, racord in tabloul casei",
 "prosumator 30 kW trifazat 1 invertor huawei SUN2000-30KTL-M3, hala mica, racord in TG existent",
 "prosumator 50 kW trifazat, invertor Sungrow SG50CX, TG existent, Q general 125 A",
 "prosumator 15 kw hibrid Solis S6-EH3P15K cu baterie 20 kwh, 3f",
 # J. contradictii
 "CEF 200 kWp cu 2 invertoare de 100 kW, 3 x 400 V, monofazat",
 "CEF 150 kWp, invertor Huawei SUN2000-100KTL-M2 de 50 kW",
 "prosumator 20 kW cu 2 invertoare de 15 kW",
 "CEF 100 kWp cu 2 invertoare de 50 kW, retea TN-S si TT",
 "CEF 80 kWp invertor Sungrow SG110CX, racord in TG existent si prin BMPT nou",
 "cef 300 kwp, 3 invertoare de 100 kw, PT propriu 250 kVA",
]
