"""Fișe tehnice sintetice pentru testele importului de echipamente (tests/test_echipamente.py) și pentru verificarea în
browser. Textele copiază STRUCTURA uzuală a fișelor (JA Solar JAM72S30 …/MR, Huawei SUN2000-100KTL-M2, Fronius Symo
GEN24 Plus, BYD Battery-Box Premium HVS, DEHNguard YPV) — valorile sunt plauzibile, nu copiate din fișele oficiale.

`pdf_simplu(randuri)` scrie un PDF valid doar cu biblioteca standard (Helvetica, flux comprimat FlateDecode), cu
textul așezat pe coloane (ca tabelele din fișe); `pdf_reportlab(...)` — același conținut cu reportlab (font TrueType
cu /ToUnicode, dacă biblioteca și fontul există).
"""
import zlib

# fiecare rând = listă de celule; prima celulă = eticheta, celelalte = coloanele (variantele)
JA_SOLAR = [
    ["JA SOLAR"],
    ["JAM72S30 540-560/MR   Harvest the Sunshine"],
    ["MBB Half-cell Module   Percium cell technology   1500 V system voltage"],
    ["ELECTRICAL PARAMETERS AT STC"],
    ["TYPE", "JAM72S30-540/MR", "JAM72S30-545/MR", "JAM72S30-550/MR", "JAM72S30-555/MR", "JAM72S30-560/MR"],
    ["Rated Maximum Power(Pmax) [W]", "540", "545", "550", "555", "560"],
    ["Open Circuit Voltage(Voc) [V]", "49.60", "49.75", "49.90", "50.05", "50.20"],
    ["Maximum Power Voltage(Vmp) [V]", "41.64", "41.80", "41.96", "42.12", "42.28"],
    ["Short Circuit Current(Isc) [A]", "13.86", "13.93", "14.00", "14.07", "14.14"],
    ["Maximum Power Current(Imp) [A]", "12.97", "13.04", "13.11", "13.18", "13.25"],
    ["Module Efficiency [%]", "20.9", "21.1", "21.3", "21.5", "21.7"],
    ["Power Tolerance", "0~+5W"],
    ["Temperature Coefficient of Isc(α_Isc)", "+0.045%/℃"],
    ["Temperature Coefficient of Voc(β_Voc)", "-0.275%/℃"],
    ["Temperature Coefficient of Pmax(γ_Pmp)", "-0.350%/℃"],
    ["STC", "Irradiance 1000W/m², cell temperature 25℃, AM1.5G"],
    ["ELECTRICAL PARAMETERS AT NOCT"],
    ["TYPE", "JAM72S30-540/MR", "JAM72S30-545/MR", "JAM72S30-550/MR", "JAM72S30-555/MR", "JAM72S30-560/MR"],
    ["Rated Max Power(Pmax) [W]", "408", "412", "416", "420", "424"],
    ["Open Circuit Voltage(Voc) [V]", "46.85", "46.99", "47.13", "47.27", "47.41"],
    ["Max Power Voltage(Vmp) [V]", "39.04", "39.19", "39.34", "39.49", "39.64"],
    ["Short Circuit Current(Isc) [A]", "11.13", "11.19", "11.25", "11.31", "11.37"],
    ["Max Power Current(Imp) [A]", "10.45", "10.51", "10.57", "10.63", "10.69"],
    ["NOCT", "Irradiance 800W/m², ambient temperature 20℃, wind speed 1m/s, AM1.5G"],
    ["OPERATING CONDITIONS"],
    ["Maximum System Voltage", "1000V/1500V DC"],
    ["Operating Temperature", "-40℃~+85℃"],
    ["Maximum Series Fuse Rating", "25A"],
    ["Maximum Static Load,Front / Back", "5400Pa/2400Pa"],
]

HUAWEI = [
    ["HUAWEI"],
    ["SUN2000-100KTL-M2   Smart String Inverter"],
    ["Technical Specification"],
    ["Efficiency"],
    ["Max. Efficiency", "98.8%"],
    ["European Efficiency", "98.6%"],
    ["Input"],
    ["Max. Input Voltage", "1,100 V"],
    ["Max. Current per MPPT", "30 A"],
    ["Max. Short-circuit Current per MPPT", "40 A"],
    ["Start Voltage", "200 V"],
    ["MPPT Operating Voltage Range", "200 V ~ 1,000 V"],
    ["Rated Input Voltage", "600 V"],
    ["Number of Inputs", "20"],
    ["Number of MPP Trackers", "10"],
    ["Output"],
    ["Rated AC Active Power", "100,000 W"],
    ["Max. AC Apparent Power", "110,000 VA"],
    ["Max. AC Active Power (cosφ=1)", "110,000 W"],
    ["Rated Output Voltage", "230 V / 400 V, 3W + N + PE"],
    ["Rated AC Grid Frequency", "50 Hz / 60 Hz"],
    ["Rated Output Current", "144.4 A"],
    ["Max. Output Current", "160.4 A"],
    ["Adjustable Power Factor Range", "0.8 LG ... 0.8 LD"],
    ["Protection"],
    ["DC Surge Arrester", "Type II"],
    ["AC Surge Arrester", "Type II"],
]

FRONIUS = [
    ["Fronius Symo GEN24 Plus"],
    ["TECHNICAL DATA", "Symo GEN24 6.0 Plus", "Symo GEN24 8.0 Plus", "Symo GEN24 10.0 Plus"],
    ["INPUT DATA"],
    ["Number of MPP trackers", "2", "2", "2"],
    ["Max. input current (Idc max1 / Idc max2)", "25.0 A / 12.5 A", "25.0 A / 12.5 A", "25.0 A / 12.5 A"],
    ["Max. array short circuit current", "37.5 A / 18.75 A", "37.5 A / 18.75 A", "37.5 A / 18.75 A"],
    ["DC input voltage range (Udc min - Udc max)", "80 - 1,000 V", "80 - 1,000 V", "80 - 1,000 V"],
    ["Feed-in start voltage (Udc start)", "80 V", "80 V", "80 V"],
    ["MPP voltage range", "163 - 800 V", "213 - 800 V", "265 - 800 V"],
    ["Battery input voltage range", "150 - 455 V", "150 - 455 V", "150 - 455 V"],
    ["OUTPUT DATA"],
    ["AC nominal output power (Pac,r)", "6,000 W", "8,000 W", "10,000 W"],
    ["Max. output power", "6,000 VA", "8,000 VA", "10,000 VA"],
    ["AC output current (Iac nom)", "8.7 A", "11.6 A", "14.5 A"],
    ["Max. output current", "9.1 A", "12.1 A", "15.2 A"],
    ["Grid connection (voltage range)", "3~NPE 400 V / 230 V", "3~NPE 400 V / 230 V", "3~NPE 400 V / 230 V"],
    ["Max. efficiency", "97.6 %", "97.6 %", "97.6 %"],
    ["Hybrid inverter with battery connection"],
]

BYD = [
    ["BYD Battery-Box Premium HVS"],
    ["Technical Data", "HVS 5.1", "HVS 7.7", "HVS 10.2", "HVS 12.8"],
    ["Battery Module", "HVS (2.56 kWh, 102.4 V, 38 kg)"],
    ["Number of Modules", "2", "3", "4", "5"],
    ["Usable Energy [1]", "5.12 kWh", "7.68 kWh", "10.24 kWh", "12.8 kWh"],
    ["Max Output Current [2]", "25 A"],
    ["Peak Output Current [2]", "50 A, 3 s"],
    ["Nominal Voltage", "204 V", "307 V", "409 V", "512 V"],
    ["Operating Voltage", "160-240 V", "240-360 V", "320-480 V", "400-600 V"],
    ["Operating Temperature", "-10 °C to +50 °C"],
    ["Cell Technology", "Lithium Iron Phosphate (cobalt-free)"],
    ["Enclosure Protection Rating", "IP55"],
    ["[1] DC Usable Energy, test conditions: 100% DOD, 0.2C at 25 °C"],
]

DEHN = [
    ["DEHN"],
    ["DEHNguard M YPV 1000 FM   Type 2 surge arrester for photovoltaic systems"],
    ["SPD according to EN 50539-11 / IEC 61643-31", "Type 2"],
    ["Max. PV voltage", "UCPV ≤ 1000 V"],
    ["Nominal discharge current (8/20 µs)", "In 12.5 kA"],
    ["Max. discharge current (8/20 µs)", "Imax 25 kA"],
    ["Voltage protection level", "Up ≤ 4 kV"],
]

FISE = {"ja_solar": JA_SOLAR, "huawei": HUAWEI, "fronius": FRONIUS, "byd": BYD, "dehn": DEHN}


def text(randuri):
    """textul ca la extragerea „layout” (coloane separate prin spații multiple)"""
    return "\n".join("   ".join(r) for r in randuri)


def _esc(s):
    b = s.encode("cp1252", "replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def pdf_simplu(randuri, titlu="Fișă tehnică"):
    """PDF minimal (stdlib): o pagină A4 landscape, Helvetica WinAnsi, conținut FlateDecode; fiecare celulă e un
    fragment de text separat (Td), coloanele la x fix — ca tabelele din fișe."""
    cont = [b"BT", b"/F1 8 Tf"]
    y = 560
    for r in randuri:
        xs = [40] + [300 + 105 * i for i in range(len(r) - 1)]
        for x, c in zip(xs, r):
            cont.append(b"1 0 0 1 %d %d Tm (" % (x, y) + _esc(c) + b") Tj")
        y -= 14
    cont.append(b"ET")
    data = zlib.compress(b"\n".join(cont))
    obj = [b"<< /Type /Catalog /Pages 2 0 R >>",
           b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
           b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
           b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(data) + data + b"\nendstream",
           b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
           b"<< /Title (" + _esc(titlu) + b") >>"]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    off = []
    for i, o in enumerate(obj, 1):
        off.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(obj) + 1)
    for o in off:
        out += b"%010d 00000 n \n" % o
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info 6 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(obj) + 1, x)
    return bytes(out)


def pdf_reportlab(randuri, cale_font=None):
    """același conținut cu reportlab și un font TrueType încorporat (subset, /ToUnicode); None dacă nu se poate"""
    try:
        import io
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.pagesizes import A4, landscape
    except ImportError:
        return None
    import os
    cale_font = cale_font or next((f for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                                               "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                                               "/Library/Fonts/Arial Unicode.ttf") if os.path.exists(f)), None)
    if not cale_font:
        return None
    pdfmetrics.registerFont(TTFont("FisaSans", cale_font))
    bio = io.BytesIO()
    c = canvas.Canvas(bio, pagesize=landscape(A4), pageCompression=1)
    c.setFont("FisaSans", 8)
    y = 560
    for r in randuri:
        xs = [40] + [300 + 105 * i for i in range(len(r) - 1)]
        for x, cel in zip(xs, r):
            c.drawString(x, y, cel)
        y -= 14
    c.showPage()
    c.save()
    return bio.getvalue()
