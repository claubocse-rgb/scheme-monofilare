"""pdftext.py — extragerea textului din fișele tehnice PDF (pentru importul echipamentelor în catalog).

`text_din_pdf(data)` → (text, motor):
  * „pypdf” dacă biblioteca e instalată (mod „layout”, păstrează coloanele tabelelor);
  * altfel un extractor minimal, doar cu biblioteca standard (merge și în versiunea web, Pyodide): obiectele PDF
    (inclusiv fluxurile de obiecte /ObjStm), filtrele FlateDecode / ASCIIHex / ASCII85, fonturile simple
    (WinAnsi, /Differences) și compuse (Identity-H) cu /ToUnicode, lățimile glifelor (/Widths, /W) și operatorii de
    text (Tj, TJ, ', ", Td, TD, Tm, T*, cm, q/Q, Do pentru formulare). Fragmentele se așază pe rânduri după poziție;
    spațiile mari dintre fragmente (coloane de tabel) devin „   ”.

Limite: fișele scanate (imagini, fără text) nu au text de extras; fonturile Type3 și codările CJK predefinite
(altele decât Identity-H) nu sunt acoperite; filtrele LZW / JBIG2 / DCT nu se decodează (nu conțin text uzual).
"""
import base64, binascii, re, zlib

# ------------------------------------------------------------------------------------------------ obiecte PDF
_WS = b" \t\r\n\f\x00"
_DELIM = b"()<>[]{}/%"


class Ref(tuple):
    """referință indirectă „n g R”"""
    pass


class Nume(str):
    """nume PDF (/Font)"""
    pass


class Op(str):
    """operator dintr-un flux de conținut"""
    pass


class _Lexer:
    def __init__(self, b, i=0):
        self.b = b
        self.i = i
        self.n = len(b)

    def _sari(self):
        b, n = self.b, self.n
        while self.i < n:
            c = b[self.i]
            if c in _WS:
                self.i += 1
            elif c == 0x25:            # % comentariu
                while self.i < n and b[self.i] not in b"\r\n":
                    self.i += 1
            else:
                break

    def token(self):
        """următorul obiect sau operator; None la sfârșit"""
        self._sari()
        b, n = self.b, self.n
        if self.i >= n:
            return None
        c = b[self.i]
        if c == 0x2F:                  # /Nume
            j = self.i + 1
            while j < n and b[j] not in _WS and b[j] not in _DELIM:
                j += 1
            s = b[self.i + 1:j].decode("latin-1")
            s = re.sub(r"#([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), s)
            self.i = j
            return Nume(s)
        if c == 0x28:                  # (șir literal)
            return self._sir()
        if c == 0x3C:
            if self.i + 1 < n and b[self.i + 1] == 0x3C:
                self.i += 2
                return self._dict()
            j = b.find(b">", self.i)
            if j < 0:
                j = n
            h = re.sub(rb"[^0-9A-Fa-f]", b"", b[self.i + 1:j])
            if len(h) % 2:
                h += b"0"
            self.i = j + 1
            return bytes(binascii.unhexlify(h))
        if c == 0x5B:                  # [
            self.i += 1
            out = []
            while True:
                t = self.token()
                if t is None or t == Op("]"):
                    return self._refuri(out)
                out.append(t)
        if c == 0x5D:
            self.i += 1
            return Op("]")
        if c == 0x3E and self.i + 1 < n and b[self.i + 1] == 0x3E:
            self.i += 2
            return Op(">>")
        if c in b"{}":
            self.i += 1
            return Op(chr(c))
        j = self.i
        while j < n and b[j] not in _WS and b[j] not in _DELIM:
            j += 1
        if j == self.i:
            self.i += 1
            return Op(chr(c))
        w = b[self.i:j].decode("latin-1")
        self.i = j
        if re.fullmatch(r"[+-]?(\d+\.?\d*|\.\d+)", w):
            return float(w) if "." in w else int(w)
        if w == "true":
            return True
        if w == "false":
            return False
        if w == "null":
            return None
        return Op(w)

    def _sir(self):
        b, n = self.b, self.n
        self.i += 1
        out = bytearray()
        adanc = 1
        while self.i < n:
            c = b[self.i]
            if c == 0x5C:              # \
                self.i += 1
                if self.i >= n:
                    break
                c = b[self.i]
                esc = {0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12, 0x28: 0x28, 0x29: 0x29, 0x5C: 0x5C}
                if c in esc:
                    out.append(esc[c])
                    self.i += 1
                elif 0x30 <= c <= 0x37:
                    j = self.i
                    while j < n and j - self.i < 3 and 0x30 <= b[j] <= 0x37:
                        j += 1
                    out.append(int(b[self.i:j], 8) & 0xFF)
                    self.i = j
                elif c in b"\r\n":     # continuare de rând
                    self.i += 1
                    if c == 0x0D and self.i < n and b[self.i] == 0x0A:
                        self.i += 1
                else:
                    out.append(c)
                    self.i += 1
                continue
            if c == 0x28:
                adanc += 1
            elif c == 0x29:
                adanc -= 1
                if adanc == 0:
                    self.i += 1
                    break
            out.append(c)
            self.i += 1
        return bytes(out)

    def _dict(self):
        d = {}
        cheie = None
        val = []
        while True:
            t = self.token()
            if t is None or t == Op(">>"):
                break
            if isinstance(t, Nume) and cheie is None:
                cheie = t
                continue
            if cheie is not None:
                # valoare: poate fi „n g R”
                if isinstance(t, int) and not isinstance(t, bool):
                    poz = self.i
                    t2 = self.token()
                    t3 = self.token() if isinstance(t2, int) else None
                    if isinstance(t2, int) and t3 == Op("R"):
                        d[str(cheie)] = Ref((t, t2))
                        cheie = None
                        continue
                    self.i = poz
                d[str(cheie)] = t
                cheie = None
        return d

    @staticmethod
    def _refuri(lst):
        out = []
        i = 0
        while i < len(lst):
            if i + 2 < len(lst) and isinstance(lst[i], int) and isinstance(lst[i + 1], int) and lst[i + 2] == Op("R"):
                out.append(Ref((lst[i], lst[i + 1])))
                i += 3
            else:
                out.append(lst[i])
                i += 1
        return out


def _decodeaza(dct, data):
    """aplică filtrele fluxului; întoarce None dacă un filtru nu e suportat"""
    f = dct.get("Filter")
    filtre = f if isinstance(f, list) else [f] if f else []
    parm = dct.get("DecodeParms")
    for k, fl in enumerate(filtre):
        fl = str(fl)
        if fl in ("FlateDecode", "Fl"):
            try:
                data = zlib.decompress(data)
            except zlib.error:
                try:
                    data = zlib.decompressobj().decompress(data)
                except zlib.error:
                    return None
            p = parm[k] if isinstance(parm, list) and k < len(parm) else parm
            if isinstance(p, dict) and isinstance(p.get("Predictor"), int) and p["Predictor"] >= 10:
                data = _png_predictor(data, int(p.get("Columns", 1)) * int(p.get("Colors", 1)) * int(p.get("BitsPerComponent", 8)) // 8)
        elif fl in ("ASCIIHexDecode", "AHx"):
            h = re.sub(rb"[^0-9A-Fa-f]", b"", data.split(b">")[0])
            data = binascii.unhexlify(h + (b"0" if len(h) % 2 else b""))
        elif fl in ("ASCII85Decode", "A85"):
            t = data.strip()
            if t.startswith(b"<~"):
                t = t[2:]
            t = t.split(b"~>")[0]
            try:
                data = base64.a85decode(re.sub(rb"\s", b"", t))
            except ValueError:
                return None
        else:
            return None
    return data


def _png_predictor(data, lat):
    out = bytearray()
    prev = bytearray(lat)
    i = 0
    while i + lat < len(data) + 1 and i < len(data):
        ft = data[i]
        row = bytearray(data[i + 1:i + 1 + lat])
        if len(row) < lat:
            break
        for x in range(lat):
            a = row[x - 1] if x else 0
            if ft == 1:
                row[x] = (row[x] + a) & 0xFF
            elif ft == 2:
                row[x] = (row[x] + prev[x]) & 0xFF
            elif ft == 3:
                row[x] = (row[x] + ((a + prev[x]) >> 1)) & 0xFF
            elif ft == 4:
                b_, c_ = prev[x], prev[x - 1] if x else 0
                pa, pb, pc = abs(b_ - c_), abs(a - c_), abs(a + b_ - 2 * c_)
                row[x] = (row[x] + (a if pa <= pb and pa <= pc else b_ if pb <= pc else c_)) & 0xFF
        out += row
        prev = row
        i += 1 + lat
    return bytes(out)


class Document:
    """obiectele unui PDF (fără xref: se caută toate „n g obj”, apoi fluxurile de obiecte)"""

    def __init__(self, data):
        self.data = data
        self.obj = {}        # (n, g) → valoare
        self.flux = {}       # (n, g) → bytes decodate (sau None)
        for m in re.finditer(rb"(\d+)\s+(\d+)\s+obj\b", data):
            cheie = (int(m.group(1)), int(m.group(2)))
            lx = _Lexer(data, m.end())
            try:
                v = lx.token()
            except (IndexError, ValueError):
                continue
            self.obj[cheie] = v
            if isinstance(v, dict):
                lx._sari()
                if data.startswith(b"stream", lx.i):
                    st = lx.i + 6
                    if data[st:st + 2] == b"\r\n":
                        st += 2
                    elif data[st:st + 1] in (b"\n", b"\r"):
                        st += 1
                    L = v.get("Length")
                    end = None
                    if isinstance(L, int) and 0 <= L and b"endstream" in data[st + L:st + L + 20]:
                        end = st + L
                    if end is None:
                        e = data.find(b"endstream", st)
                        end = e if e >= 0 else len(data)
                        while end > st and data[end - 1] in b"\r\n":
                            end -= 1
                    self.flux[cheie] = (v, data[st:end])
        # fluxurile de obiecte (PDF 1.5+): fonturile și paginile sunt adesea comprimate aici
        for cheie, (d, raw) in list(self.flux.items()):
            if str(d.get("Type")) == "ObjStm":
                dec = _decodeaza(d, raw)
                if not dec:
                    continue
                try:
                    N, first = int(d.get("N", 0)), int(d.get("First", 0))
                    hdr = [int(x) for x in dec[:first].split()]
                except ValueError:
                    continue
                for k in range(min(N, len(hdr) // 2)):
                    num, off = hdr[2 * k], hdr[2 * k + 1]
                    if (num, 0) in self.obj:
                        continue
                    try:
                        self.obj[(num, 0)] = _Lexer(dec, first + off).token()
                    except (IndexError, ValueError):
                        pass
        self._cache = {}

    def r(self, v):
        """rezolvă o referință"""
        k = 0
        while isinstance(v, Ref) and k < 20:
            v = self.obj.get(tuple(v))
            k += 1
        return v

    def continut(self, ref):
        """fluxul decodat al unui obiect (cache)"""
        if not isinstance(ref, Ref):
            return None
        k = tuple(ref)
        if k not in self._cache:
            f = self.flux.get(k)
            self._cache[k] = _decodeaza(f[0], f[1]) if f else None
        return self._cache[k]


# ------------------------------------------------------------------------------------------------ fonturi
_WINANSI = {0x80: "€", 0x82: "‚", 0x84: "„", 0x85: "…", 0x8A: "Š", 0x8C: "Œ", 0x91: "‘", 0x92: "’", 0x93: "“",
            0x94: "”", 0x95: "•", 0x96: "–", 0x97: "—", 0x99: "™", 0x9A: "š", 0x9C: "œ", 0x9F: "Ÿ"}
_GLIFE = {"space": " ", "hyphen": "-", "minus": "−", "period": ".", "comma": ",", "colon": ":", "semicolon": ";",
          "slash": "/", "percent": "%", "parenleft": "(", "parenright": ")", "bracketleft": "[", "bracketright": "]",
          "plus": "+", "equal": "=", "less": "<", "greater": ">", "degree": "°", "endash": "–", "emdash": "—",
          "asciitilde": "~", "underscore": "_", "quotesingle": "'", "quotedbl": '"', "ampersand": "&", "at": "@",
          "numbersign": "#", "asterisk": "*", "multiply": "×", "mu": "µ", "plusminus": "±", "periodcentered": "·",
          "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
          "eight": "8", "nine": "9", "ellipsis": "…", "bullet": "•", "Omega": "Ω", "beta": "β", "alpha": "α",
          "gamma": "γ", "Delta": "Δ", "quoteright": "’", "quoteleft": "‘", "quotedblleft": "“", "quotedblright": "”",
          "twosuperior": "²", "threesuperior": "³", "uni2103": "℃"}


def _nume_glifa(n):
    if n in _GLIFE:
        return _GLIFE[n]
    if len(n) == 1:
        return n
    m = re.fullmatch(r"uni([0-9A-Fa-f]{4})", n) or re.fullmatch(r"u([0-9A-Fa-f]{4,6})", n)
    if m:
        try:
            return chr(int(m.group(1), 16))
        except ValueError:
            return ""
    return ""


def _cmap(txt):
    """ToUnicode: {cod: text}, lățimea codului în octeți"""
    harta = {}
    lat = None
    for m in re.finditer(rb"begincodespacerange(.*?)endcodespacerange", txt, re.S):
        h = re.findall(rb"<([0-9A-Fa-f]+)>", m.group(1))
        if h:
            lat = max(len(x) for x in h) // 2

    def uni(h):
        try:
            return binascii.unhexlify(h if len(h) % 4 == 0 else h.rjust((len(h) + 3) // 4 * 4, b"0")).decode("utf-16-be", "replace")
        except (binascii.Error, ValueError):
            return ""
    for m in re.finditer(rb"beginbfchar(.*?)endbfchar", txt, re.S):
        for a, b in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", m.group(1)):
            harta[int(a, 16)] = uni(b)
            lat = lat or len(a) // 2
    for m in re.finditer(rb"beginbfrange(.*?)endbfrange", txt, re.S):
        for a, b, rest in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f]*>)", m.group(1)):
            lo, hi = int(a, 16), int(b, 16)
            lat = lat or len(a) // 2
            if hi - lo > 65535:
                continue
            if rest.startswith(b"["):
                for k, h in enumerate(re.findall(rb"<([0-9A-Fa-f]*)>", rest)):
                    harta[lo + k] = uni(h)
            else:
                h = rest[1:-1]
                base = int(h, 16) if h else 0
                n = len(h)
                for k in range(hi - lo + 1):
                    harta[lo + k] = uni(format(base + k, "0%dX" % max(n, 4)).encode())
    return harta, lat or 1


class Font:
    def __init__(self, doc, d):
        d = doc.r(d) or {}
        self.compus = str(d.get("Subtype")) == "Type0"
        self.lat = 2 if self.compus else 1
        self.harta = None
        self.latimi = {}
        self.implicit = 500.0
        tu = d.get("ToUnicode")
        if isinstance(tu, Ref):
            c = doc.continut(tu)
            if c:
                self.harta, lat = _cmap(c)
                if self.compus:
                    self.lat = max(lat, 1)
        self.dif = {}
        enc = doc.r(d.get("Encoding"))
        if isinstance(enc, dict):
            cod = 0
            for x in enc.get("Differences") or []:
                if isinstance(x, int):
                    cod = x
                elif isinstance(x, str):
                    self.dif[cod] = _nume_glifa(str(x))
                    cod += 1
        if self.compus:
            df = doc.r((doc.r(d.get("DescendantFonts")) or [None])[0])
            if isinstance(df, dict):
                self.implicit = float(df.get("DW", 1000))
                w = doc.r(df.get("W")) or []
                i = 0
                while i < len(w):
                    a = w[i]
                    b = doc.r(w[i + 1]) if i + 1 < len(w) else None
                    if isinstance(b, list):
                        for k, x in enumerate(b):
                            if isinstance(x, (int, float)):
                                self.latimi[a + k] = float(x)
                        i += 2
                    elif i + 2 < len(w):
                        for k in range(int(a), int(b) + 1):
                            self.latimi[k] = float(w[i + 2])
                        i += 3
                    else:
                        break
        else:
            fc = d.get("FirstChar")
            ws = doc.r(d.get("Widths"))
            if isinstance(fc, int) and isinstance(ws, list):
                for k, x in enumerate(ws):
                    x = doc.r(x)
                    if isinstance(x, (int, float)):
                        self.latimi[fc + k] = float(x)
                vals = [v for v in self.latimi.values() if v > 0]
                if vals:
                    self.implicit = sum(vals) / len(vals)

    def decodeaza(self, s):
        """bytes → [(text, lățime/1000, e_spațiu)]"""
        out = []
        L = self.lat
        for i in range(0, len(s) - L + 1, L):
            cod = int.from_bytes(s[i:i + L], "big")
            if self.harta is not None and cod in self.harta:
                t = self.harta[cod]
            elif cod in self.dif:
                t = self.dif[cod]
            elif self.compus:
                t = ""
            else:
                t = _WINANSI.get(cod) or bytes([cod]).decode("latin-1")
            w = self.latimi.get(cod, self.implicit) / 1000.0
            out.append((t, w, L == 1 and cod == 32))
        return out


# ------------------------------------------------------------------------------------------------ conținut
def _mul(a, b):
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3], a[2] * b[0] + a[3] * b[2],
            a[2] * b[1] + a[3] * b[3], a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]


class _Pagina:
    def __init__(self, doc):
        self.doc = doc
        self.frag = []          # (x, y, x_final, înălțime, text)
        self._fonturi = {}

    def font(self, res, nume):
        fd = (self.doc.r((self.doc.r(res) or {}).get("Font")) or {}).get(nume)
        k = tuple(fd) if isinstance(fd, Ref) else id(fd)
        if k not in self._fonturi:
            self._fonturi[k] = Font(self.doc, fd)
        return self._fonturi[k]

    def ruleaza(self, cont, res, ctm, adanc=0):
        if not cont or adanc > 6:
            return
        lx = _Lexer(cont)
        st = []
        ops = []
        stiva = []
        gs = {"ctm": list(ctm)}
        ts = {"font": None, "size": 10.0, "Tc": 0.0, "Tw": 0.0, "Tz": 1.0, "TL": 0.0, "Ts": 0.0}
        tm = [1, 0, 0, 1, 0, 0]
        tlm = list(tm)
        while True:
            try:
                t = lx.token()
            except (IndexError, ValueError):
                break
            if t is None:
                break
            if not isinstance(t, Op) or t in ("]", ">>"):
                ops.append(t)
                continue
            op = str(t)
            a = ops
            ops = []
            if op == "ID":                 # imagine inline: datele binare până la „EI”
                m = re.compile(rb"\sEI(?=[\s/]|$)").search(cont, lx.i)
                lx.i = m.end() if m else len(cont)
                continue
            try:
                if op == "q":
                    stiva.append((list(gs["ctm"]), dict(ts)))
                elif op == "Q":
                    if stiva:
                        gs["ctm"], ts = stiva.pop()
                elif op == "cm" and len(a) >= 6:
                    gs["ctm"] = _mul([float(x) for x in a[-6:]], gs["ctm"])
                elif op == "BT":
                    tm = [1, 0, 0, 1, 0, 0]
                    tlm = list(tm)
                elif op == "Tf" and len(a) >= 2:
                    ts["font"] = self.font(res, str(a[-2]))
                    ts["size"] = float(a[-1])
                elif op == "Tc" and a:
                    ts["Tc"] = float(a[-1])
                elif op == "Tw" and a:
                    ts["Tw"] = float(a[-1])
                elif op == "Tz" and a:
                    ts["Tz"] = float(a[-1]) / 100.0
                elif op == "TL" and a:
                    ts["TL"] = float(a[-1])
                elif op == "Ts" and a:
                    ts["Ts"] = float(a[-1])
                elif op in ("Td", "TD") and len(a) >= 2:
                    tx, ty = float(a[-2]), float(a[-1])
                    if op == "TD":
                        ts["TL"] = -ty
                    tlm = _mul([1, 0, 0, 1, tx, ty], tlm)
                    tm = list(tlm)
                elif op == "Tm" and len(a) >= 6:
                    tlm = [float(x) for x in a[-6:]]
                    tm = list(tlm)
                elif op == "T*":
                    tlm = _mul([1, 0, 0, 1, 0, -ts["TL"]], tlm)
                    tm = list(tlm)
                elif op in ("Tj", "'", '"', "TJ"):
                    if op in ("'", '"'):
                        if op == '"' and len(a) >= 3:
                            ts["Tw"], ts["Tc"] = float(a[-3]), float(a[-2])
                        tlm = _mul([1, 0, 0, 1, 0, -ts["TL"]], tlm)
                        tm = list(tlm)
                    arg = a[-1] if a else b""
                    elems = arg if op == "TJ" and isinstance(arg, list) else [arg]
                    tm = self._arata(elems, ts, tm, gs["ctm"])
                elif op == "Do" and a:
                    xo = self.doc.r((self.doc.r((self.doc.r(res) or {}).get("XObject")) or {}).get(str(a[-1])))
                    ref = (self.doc.r((self.doc.r(res) or {}).get("XObject")) or {}).get(str(a[-1]))
                    if isinstance(xo, dict) and str(xo.get("Subtype")) == "Form":
                        mt = xo.get("Matrix")
                        m2 = _mul([float(x) for x in mt], gs["ctm"]) if isinstance(mt, list) and len(mt) == 6 else gs["ctm"]
                        self.ruleaza(self.doc.continut(ref), xo.get("Resources") or res, m2, adanc + 1)
            except (TypeError, ValueError, IndexError, ZeroDivisionError):
                continue

    def _arata(self, elems, ts, tm, ctm):
        f = ts["font"]
        if f is None:
            return tm
        fs, tz = ts["size"], ts["Tz"]
        trm = _mul([fs * tz, 0, 0, fs, 0, ts["Ts"]], _mul(tm, ctm))
        x0, y0 = trm[4], trm[5]
        h = abs(_mul([0, 0, 0, fs, 0, 0], _mul(tm, ctm))[3]) or abs(fs)
        txt = []
        for e in elems:
            if isinstance(e, (int, float)):
                d = -float(e) / 1000.0 * fs * tz
                if -float(e) > 250 and txt and not txt[-1].endswith(" "):
                    txt.append(" ")
                tm = _mul([1, 0, 0, 1, d, 0], tm)
                continue
            if not isinstance(e, bytes):
                continue
            for t, w, sp in f.decodeaza(e):
                txt.append(t)
                adv = (w * fs + ts["Tc"] + (ts["Tw"] if sp else 0.0)) * tz
                tm = _mul([1, 0, 0, 1, adv, 0], tm)
        s = "".join(txt)
        if s.strip():
            xe = _mul(tm, ctm)[4]
            self.frag.append((x0, y0, xe, h, s))
        return tm

    def randuri(self):
        """fragmentele → rânduri de text (sus → jos, stânga → dreapta); coloanele separate prin 3 spații"""
        fr = sorted(self.frag, key=lambda f: (-f[1], f[0]))
        linii = []
        for f in fr:
            for L in linii:
                if abs(L[0] - f[1]) <= max(1.0, 0.45 * min(L[1], f[3] or L[1])):
                    L[2].append(f)
                    break
            else:
                linii.append([f[1], f[3] or 10.0, [f]])
        linii.sort(key=lambda L: -L[0])
        out = []
        for _, h, fs in linii:
            fs.sort(key=lambda f: f[0])
            s = ""
            xe = None
            for x, y, x2, hh, t in fs:
                if xe is not None:
                    gol = x - xe
                    if gol > 1.6 * max(hh, 1.0):
                        s = s.rstrip() + "   "
                    elif gol > 0.18 * max(hh, 1.0) and not s.endswith(" ") and not t.startswith(" "):
                        s += " "
                s += t
                xe = max(x2, x) if xe is None else max(xe, x2)
            out.append(s.rstrip())
        return out


def _pagini(doc):
    """paginile în ordine (arborele /Pages din /Root dacă există; altfel ordinea obiectelor)"""
    root = None
    for m in re.finditer(rb"/Root\s+(\d+)\s+(\d+)\s+R", doc.data):
        root = doc.r(Ref((int(m.group(1)), int(m.group(2)))))
    pag = []
    vazut = set()

    def mergi(n, res, adanc=0):
        nd = doc.r(n)
        if not isinstance(nd, dict) or adanc > 30 or id(nd) in vazut:
            return
        vazut.add(id(nd))
        res = nd.get("Resources", res)
        if str(nd.get("Type")) == "Pages" or "Kids" in nd:
            for k in doc.r(nd.get("Kids")) or []:
                mergi(k, res, adanc + 1)
        else:
            pag.append((nd, res))
    if isinstance(root, dict):
        mergi(root.get("Pages"), None)
    if not pag:
        for v in doc.obj.values():
            if isinstance(v, dict) and str(v.get("Type")) == "Page":
                res = v.get("Resources")
                p = v
                k = 0
                while res is None and isinstance(p, dict) and k < 20:
                    p = doc.r(p.get("Parent"))
                    res = p.get("Resources") if isinstance(p, dict) else None
                    k += 1
                pag.append((v, res))
    return pag


def text_stdlib(data):
    doc = Document(data)
    pagini = []
    for nd, res in _pagini(doc):
        c = doc.r(nd.get("Contents"))
        refs = c if isinstance(c, list) else [nd.get("Contents")]
        cont = b"\n".join(x for x in (doc.continut(r) for r in refs) if x)
        p = _Pagina(doc)
        p.ruleaza(cont, res, [1, 0, 0, 1, 0, 0])
        pagini.append("\n".join(p.randuri()))
    return "\n\f\n".join(pagini)


def text_pypdf(data):
    import io
    import pypdf
    r = pypdf.PdfReader(io.BytesIO(data))
    out = []
    for p in r.pages:
        try:
            t = p.extract_text(extraction_mode="layout")
        except TypeError:          # pypdf vechi, fără modul „layout”
            t = p.extract_text()
        out.append(t or "")
    return "\n\f\n".join(out)


def text_din_pdf(data, motor=None):
    """(text, motor). `motor` = "stdlib" forțează extractorul propriu (testele / versiunea web)."""
    if not data[:1024].lstrip().startswith(b"%PDF") and b"%PDF" not in data[:1024]:
        raise ValueError("fișierul nu este PDF")
    if motor != "stdlib":
        try:
            t = text_pypdf(data)
            if len(re.sub(r"\s", "", t)) >= 40:
                return t, "pypdf"
        except ImportError:
            pass
        except Exception:          # PDF pe care pypdf nu-l citește → extractorul propriu
            pass
    return text_stdlib(data), "stdlib"
