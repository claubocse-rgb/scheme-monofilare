"""Motor de layout: din modelul schemei (dict) -> Canvas.
Model (JSON):
{
  "format": "A3" | "A2",
  "cartus": {...},
  "carcasa": {"titlu": "BMPTi-250", "sub": "..."}  | null,
  "intrari": [ {"sursa": {"titlu","sub"}, "cablu": {"ref","cond","text"}, "cablu_ca": {...}, "aparate": [aparat,...]} ],
  "bara":    {"afisare": true, "forteaza": false, "eticheta": "...", "laterale": [aparat_lateral,...]},
  "plecari": [ {"aparate": [...], "cablu": {...}, "sarcina": {"titlu","sub"}, "copii": [plecare, ...]} ],
  "note": ["..."], "abrevieri": ["..."], "lista_auto": true, "legenda": true, "titlu_lista": "..."
}
aparat = {"tip": "mccb", "ref": "Q", "spec": ["4P · 250 A"], "lista": ["denumire", "detalii"], "buc": 1,
          "bd": false, "in_carcasa": true|false,
          "laterale": [ {"tip": "contor", "ref": "P", "eticheta": "kWh · kVArh", "spec": [...], "lista": [...],
                         "legatura": "masura" | "comanda",
                         "intrare_contor": "curent" | "tensiune", "sursa_legatura": "amonte" | "aval"} ] }

Laterale:
* lanțul din dreapta aparatului (măsură, albastru): TC → K → contor P (circuitul de CURENT);
* `legatura: "comanda"` (roșu): cutia de protecție (DPST, PI, releu F>) comandă aparatul — săgeata pleacă de la cutie
  și intră în bobina de declanșare BD a aparatului (BD se desenează automat la întreruptoare);
* circuitul de TENSIUNE al contorului (`intrare_contor: "tensiune"`; implicit pentru `fuzibil`) este o derivație separată:
  se ia de pe conductorul de forță în amonte de aparat (`sursa_legatura: "amonte"`, implicit) sau în aval (`"aval"`),
  trece prin siguranțele F și intră pe a doua intrare a contorului din lanț;
* `spd`, `spd_cc`, `descarcator_mt`: derivație spre pământ; `bareta_nul`: BN cu traseul PE → PS → PPL.

Carcase: carcasa modelului (tabloul principal) cuprinde numai aparatele de protecție / comutație. Sursele (câmp PV, invertor,
PCS, baterie, generator) — și tot ce e deasupra lor pe aceeași intrare — se desenează în afara ei, deasupra; un aparat
se poate forța afară cu `"in_carcasa": false`. O plecare cu `copii` este un tablou secundar desenat sub tabloul părinte,
în propria carcasă.
"""
from .canvas import *
from . import symbols as S

FORMATS = {"A3": (420.0, 297.0), "A2": (594.0, 420.0), "A1": (841.0, 594.0)}
GAP = 4.0
CABLE_SEG = 22.0          # lungimea segmentului de cablu (cu marcaj) între cutie și primul aparat
BOX_H = 12.0
LAT_W = {"contor": 28, "cleme": 12, "cutie": 28, "fuzibil": 8}
LEFT_EXT = {"string_pv": 11, "invertor": 9, "convertor_bess": 9, "trafo": 6, "contor_direct": 9, "sep_mt": 13, "generator": 7, "motor": 7,
            "sep_fuzibil": 2.5, "mcb": 2.5, "mccb": 2.5, "rccb": 3.5, "mccb_dif": 3.5, "rcbo": 3.5, "acb": 2.5, "separator": 2.5,
            "separator_cc": 2.5, "intreruptor_mt": 2.5, "fuzibil": 2.5, "gpv": 2.5, "contact": 2.5, "sigurante_mt": 2.5}
POZ_DX = {"tc": 9.0}
BN_DX = 34.0              # distanța baretei de nul / traseului PE față de coloană
CH = 1.45                 # lățime medie caracter (mm) la 2,1 mm înălțime text
SURSE_TIP = {"string_pv", "invertor", "convertor_bess", "baterie", "generator"}
SPD_TIP = {"spd", "spd_cc", "descarcator_mt"}
BD_TIP = {"mccb", "mcb", "mccb_dif", "rccb", "rcbo", "acb", "intreruptor_mt"}
SUB_HEAD = 10.0           # capul carcasei unui tablou secundar (titlu + spațiu până la bară)
GRUP_GAP = 6.0          # bara scurtă a unei grupe (DDR → circuite) în același tablou
SEG_MAX = 50.0


def _tw(s, h=2.1): return len(s or "") * CH * h / 2.1


def _sym_right(tip, d):
    """marginea din dreapta a geometriei simbolului (mm față de axă)"""
    prims = S.draw(tip if tip in S.SYMBOLS else "nod", d)
    bb = block_bbox(BlockRef("x", (0, 0), {}, prims))
    return bb[2] if bb else 0.0


def _poz_dx(a):
    """distanța de la axă la cercul de poziție al aparatului"""
    tip = a.get("tip", "nod")
    bd = bool(a.get("bd")) or any(l.get("legatura") == "comanda" for l in a.get("laterale", []) or [])
    return POZ_DX.get(tip, max(8.5, _sym_right(tip, dict(a, bd=bd and tip in BD_TIP)) + 3.4))


def _e_tensiune(l):
    """lateralul face parte din circuitul de tensiune al contorului (derivație separată, nu din lanțul TC → K → P)"""
    if l.get("intrare_contor") == "tensiune": return True
    return l.get("tip") == "fuzibil" and l.get("intrare_contor") != "curent"


def _split_intrare(b, cu_carcasa):
    """(aparate în afara carcasei, aparate în carcasă) pentru o intrare"""
    ap = b.get("aparate", []) or []
    if not cu_carcasa: return [], ap
    k = -1
    for i, a in enumerate(ap):
        if a.get("tip") in SURSE_TIP or a.get("in_carcasa") is False: k = i
    return ap[:k + 1], ap[k + 1:]


class Layout:
    def __init__(self, model: dict, v_boost: float = 1.0):
        self.m = model
        self.v_boost = v_boost      # >1: pas vertical și segmente de cablu mai lungi (A2 cu schemă lată și joasă)
        fmt = model.get("format", "A3")
        self.w, self.h = FORMATS.get(fmt, FORMATS["A3"])
        self.c = Canvas(self.w, self.h)
        self.poz = []
        self.bn_xy = None; self.bn_stanga = None; self.spd_pe = []
        self.box_bottom = 1e9
        self.meta = {"carcase": [], "obiecte": [], "legaturi": [], "poz": [], "scara": 1.0}
        self._cabluri = []      # etichete de cablu amânate până se cunosc carcasele

    # ------------------------------------------------------------ public
    def build(self) -> Canvas:
        c = self.c
        c.rect(5, 5, self.w - 10, self.h - 10, "TABEL")
        c.rect(10, 10, self.w - 20, self.h - 20, "CHENAR")
        self._calc_note()
        i0 = len(c.items)
        self._schema()
        self._scaleaza(i0, marire=self.m.get("format", "A3") in ("A2", "A1"))
        self.meta["schema_bbox"] = _bbox_items(c.items[i0:])
        self.meta["zona_schema"] = (15.0, (self.note_top + 6 if self.m.get("note") else 15.0), self.x_right - 2, self.h - 15)
        for mat in self.m.get("materiale") or []:      # cabluri, conductoare PE (U.M. m) — SPEC §E.1 pct. 5
            q = mat.get("cantitate", "")
            if isinstance(q, float):
                q = int(q) if q == int(q) else str(round(q, 2)).replace(".", ",")
            self.poz.append((len(self.poz) + 1, mat.get("ref", ""), mat.get("lista", []), f"{q} {mat.get('um', '')}".strip(), "material"))
        if self.m.get("lista_auto", True): self._tabel()
        if self.m.get("legenda", True): self._legenda()
        self._note()
        self._cartus()
        c.meta = self.meta
        return c

    # ------------------------------------------------------------ lățimi de coloană
    def _col_dims(self, br, plecare=False):
        """(stânga, dreapta, lățimea cutiei) în mm față de axa coloanei"""
        left, right = (12.0, 12.0) if plecare else (18.0, 18.0)
        for a in br.get("aparate", []):
            lw = max([text_width(a.get("ref", ""), 2.8, True)] + [text_width(s, 2.1) for s in a.get("spec", [])] + [0])
            left = max(left, 2 + LEFT_EXT.get(a.get("tip", ""), 4) + lw + 3.5)
            right = max(right, self._dreapta(a) + 1.0)
            if a.get("tip") == "string_pv": right = max(right, 11 + _tw(a.get("eticheta", "× n"), 2.4) + 8)
        for cab in (br.get("cablu") or {}, br.get("cablu_ca") or {}):
            if plecare:
                left = max(left, 5 + _tw(cab.get("ref", ""), 2.5) + 2)
                right = max(right, 8)
            else:
                left = max(left, 5 + max(_tw(cab.get("ref", ""), 2.5), _tw(cab.get("text", ""), 2.0)) + 2)
                right = max(right, 5 + _tw(cab.get("cond", ""), 2.3) + 2)
        box = br.get("sursa") or br.get("sarcina") or {}
        bw = max(28.0 if plecare else 40.0, max(text_width(box.get("titlu", ""), 3.0, True), text_width(box.get("sub", ""), 2.0)) + 5)
        copii = br.get("copii") or []
        if copii:
            wc = sum(max(l, b / 2 + 1) + max(r, b / 2 + 1) for (l, r, b) in (self._col_dims(ch, True) for ch in copii)) + 8
            left, right = max(left, wc / 2 + 1), max(right, wc / 2 + 1)
        return left, right, bw

    def _dreapta(self, a):
        """cât ocupă aparatul în dreapta axei: cercul de poziție sau lateralele"""
        return max(_poz_dx(a) + 3.0, (18 + self._lat_extent(a)) if a.get("laterale") else 0.0)

    def _lat_extent(self, a):
        ext, spd = 0.0, 0.0
        for l in a.get("laterale", []) or []:
            t = l.get("tip")
            if t in SPD_TIP:
                spd = (spd + 22 if spd else 0) + 5 + max([text_width(l.get("ref", ""), 2.8, True)] + [text_width(s, 2.1) for s in l.get("spec", [])[:2]]) + 9
            elif t in LAT_W and not _e_tensiune(l):
                ext += LAT_W[t] + 8
        return ext + ((spd + 2 + (0 if ext else 12)) if spd else 0)

    def _seg_out(self, plecari):
        """lungimea segmentului de cablu al plecărilor: încape eticheta rotită de-a lungul lui"""
        L = 0.0
        def walk(bs):
            nonlocal L
            for b in bs:
                cab = b.get("cablu") or {}
                L = max(L, _tw(cab.get("text", ""), 2.0), _tw(cab.get("cond", ""), 2.0))
                walk(b.get("copii") or [])
        walk(plecari)
        return min(SEG_MAX * self.v_boost, max(CABLE_SEG * self.v_boost, L + 26))

    def _adancime(self, br):
        """(rânduri de aparate, mm suplimentari) ocupați de o plecare până la segmentul ei de cablu"""
        n = len(br.get("aparate", []))
        copii = br.get("copii") or []
        if not copii: return (n, 0.0)
        best = max((self._adancime(ch) for ch in copii), key=lambda t: t[0] * 20 + t[1])
        if br.get("grup"):          # grupă (ex. DDR + circuitele lui) în același tablou: doar o bară scurtă, fără cablu
            return (n + best[0], GRUP_GAP + best[1])
        return (n + best[0], self.seg_out + SUB_HEAD + best[1])

    # ------------------------------------------------------------ schema
    def _schema(self):
        m, c = self.m, self.c
        intrari, plecari = m.get("intrari", []), m.get("plecari", [])
        bara = m.get("bara", {}) or {}
        car = m.get("carcasa")
        n_lat_bus = len([l for l in bara.get("laterale", []) if l["tip"] in SPD_TIP])
        ext_rz = 14 * len([l for l in bara.get("laterale", []) if l["tip"] in SPD_TIP and l.get("rezerva")])
        show_bus = bara.get("afisare", True) and (len(intrari) + len(plecari) > 2 or bara.get("forteaza", False) or bool(bara.get("laterale")))
        has_bn = any(l["tip"] == "bareta_nul" for br in intrari + plecari for a in br.get("aparate", []) for l in a.get("laterale", []))
        self.has_bn = has_bn
        self.seg_out = self._seg_out(plecari) + (12 if has_bn else 0)

        dims_out_pre = [self._col_dims(b, True) for b in plecari]
        x_left = 22.0 + (BN_DX + 6 if has_bn else 0) + ((22 * n_lat_bus + ext_rz + ((dims_out_pre[0][0] + 9) if dims_out_pre else 0)) if (show_bus and n_lat_bus) else 0)
        x_right = (self.w - 10 - 164) if (m.get("lista_auto", True) or m.get("legenda", True)) else self.w - 24
        self.x_right = x_right
        avail = max(x_right - 8 - x_left, 60)      # 8 mm: marginea carcasei în dreapta ultimei coloane

        dims_in = [self._col_dims(b) for b in intrari]
        dims_out = dims_out_pre

        def place(dims):
            offs = [max(l, bw / 2 + 1) for (l, r, bw) in dims]
            ws = [off + max(r, bw / 2 + 1) for (l, r, bw), off in zip(dims, offs)]
            tot = sum(ws); k = 1.0     # coloanele nu se comprimă (s-ar suprapune textele); schema se scalează uniform la final
            x0 = x_left + max(0.0, avail - tot) / 2
            xs, x = [], x0
            for off, w in zip(offs, ws):
                xs.append(x + off * k); x += w * k
            return xs, [w * k for w in ws]
        xin, win = place(dims_in); xout, wout = place(dims_out)
        self.k_min = min([1.0] + [avail / max(1e-6, sum(max(l, bw/2+1) + max(r, bw/2+1) for (l, r, bw) in d)) for d in (dims_in, dims_out) if d])
        if len(intrari) == 1 and len(plecari) == 1 and not show_bus:
            xc = (xin[0] + xout[0]) / 2; xin, xout = [xc], [xc]

        # --- verticală
        parts = [_split_intrare(b, bool(car)) for b in intrari]
        n_oi = max([len(o) for o, _ in parts] + [0])
        n_ii = max([len(i) for _, i in parts] + [0])
        gap_in = (CABLE_SEG + 8) if n_oi else 0.0
        deps = [self._adancime(b) for b in plecari]
        a_out, b_out = max(deps, key=lambda t: t[0] * 20 + t[1]) if deps else (0, 0.0)
        if show_bus and n_lat_bus and plecari:          # descărcătorul de pe bară coboară ~24 mm: carcasa trebuie să-l cuprindă
            b_out = max(b_out, 26.0 - a_out * (S.M + GAP) * self.v_boost)
        y_top = self.h - 20
        y_bot = (self.note_top + 2 if m.get("note") else 36.0) + (14 if has_bn else 0)
        fixed = BOX_H + CABLE_SEG + gap_in + 4 + b_out + ((self.seg_out + BOX_H) if plecari else 0)
        step = (S.M + GAP) * self.v_boost
        rows = n_oi + n_ii + a_out
        if fixed + rows * step > (y_top - y_bot):
            step = max(S.M + 0.5, (y_top - y_bot - fixed) / max(rows, 1))
        self.step = step
        y_bus = y_top - BOX_H - CABLE_SEG - n_oi * step - gap_in - n_ii * step - 4
        self.y_bus = y_bus
        y_in_top = y_bus + 4 + n_ii * step          # începutul părții din carcasă a intrărilor

        ext = [1e9, -1e9, 1e9, -1e9]   # xmin xmax ymin ymax ale zonei din carcasa principală
        def grow(x1, x2, y1, y2):
            ext[0] = min(ext[0], x1); ext[1] = max(ext[1], x2); ext[2] = min(ext[2], y1); ext[3] = max(ext[3], y2)

        # --- intrări (de sus în jos)
        y_out_bot = None
        ilk = {}
        for b, x, w, (dl, dr, _), (outs, ins) in zip(intrari, xin, win, dims_in, parts):
            self._box(x, y_top, b.get("sursa", {}), w, "sursa")
            y = y_top - BOX_H
            c.line((x, y), (x, y - CABLE_SEG), "FORTA")
            first_inside = not outs
            self._cabluri.append({"x": x, "hi": y, "lo": y - CABLE_SEG, "d": b.get("cablu"), "rot": False,
                                  "carcasa": "principala" if (first_inside and car) else None, "sus": True})
            y -= CABLE_SEG
            for a in outs:
                yc = y - step / 2
                c.line((x, y), (x, yc + S.HALF), "FORTA"); bb = self._aparat(x, yc, a); c.line((x, yc - S.HALF), (x, y - step), "FORTA")
                if a.get("tip") in SURSE_TIP: self.meta["obiecte"].append({"tip": "sursa", "nume": a.get("ref") or a.get("tip"), "bbox": bb})
                y -= step
            if outs:
                y_out_bot = y if y_out_bot is None else min(y_out_bot, y)
                c.line((x, y), (x, y_in_top), "FORTA")
                self._cabluri.append({"x": x, "hi": y, "lo": y_in_top, "d": b.get("cablu_ca"), "rot": False, "carcasa": "principala", "sus": True})
                y = y_in_top
            for a in ins:
                yc = y - step / 2
                c.line((x, y), (x, yc + S.HALF), "FORTA"); self._aparat(x, yc, a); c.line((x, yc - S.HALF), (x, y - step), "FORTA")
                if a.get("interblocaj"): ilk.setdefault(a["interblocaj"], []).append((x, yc))
                grow(x - dl, x + self._dreapta(a), yc - S.HALF, yc + S.HALF); y -= step
            c.line((x, y), (x, y_bus), "FORTA")
        # interblocaj mecanic + electric între polii aceluiași comutator de sursă (ATS: poziția I / poziția II)
        for nume, pts in ilk.items():
            pts = sorted(pts)
            for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
                yy = min(ya, yb)
                c.line((xa + 3.2, yy), (xb - 3.2, yy), "MECANIC")
                c.text((xa + xb) / 2, yy - 3.4, f"interblocaj {nume}", 1.8, align="middle", layer="TEXT_GRI")

        # --- bara
        if show_bus:
            xs_all = xin + xout
            xmin = min(xs_all)
            # descărcătoarele de pe bară stau la stânga TUTUROR textelor plecărilor (nu doar ale primei coloane)
            st = min([xmin - 10] + [x - d[0] for d, x in zip(dims_out, xout)])
            x1 = (st - 9 - 22 * n_lat_bus - ext_rz) if n_lat_bus else xmin - 10
            x2 = max(xs_all) + 10
            c.line((x1, y_bus), (x2, y_bus), "FORTA"); c.line((x1, y_bus - 0.7), (x2, y_bus - 0.7), "FORTA")
            self.bus_segs = [((x1, y_bus), (x2, y_bus)), ((x1, y_bus - 0.7), (x2, y_bus - 0.7))]
            if bara.get("eticheta"):     # eticheta barei: în primul interval liber dintre conductoarele care vin de sus
                et = bara["eticheta"]; tw = text_width(et, 2.1)
                cols = sorted(x for x in xin)
                iv = list(zip([x1 + 1] + [x + 3 for x in cols], [x - 3 for x in cols] + [x2 - 1]))
                fit = [a_ for a_ in iv if a_[1] - a_[0] >= tw]
                a_ = fit[0] if fit else max(iv, key=lambda t: t[1] - t[0])
                c.text(a_[0], y_bus + 1.6, et, min(2.1, 2.1 * (a_[1] - a_[0]) / max(tw, 0.1)))
            for x in xs_all: c.dot((x, y_bus), 0.9)
            grow(x1, x2, y_bus - 1, y_bus + 4)
            lx = x1 + 8
            for l in bara.get("laterale", []):
                if l["tip"] in SPD_TIP:
                    rz = l.get("rezerva")        # protecția de rezervă a SPD (F2), în serie, între bară și descărcător
                    ys = y_bus - 4
                    c.dot((lx, y_bus), 0.9)
                    if rz:
                        c.line((lx, y_bus), (lx, y_bus - 3), "FORTA")
                        c.rect(lx - 1.4, y_bus - 9, 2.8, 6, "FORTA"); c.line((lx, y_bus - 9), (lx, y_bus - 12), "FORTA")
                        c.text(lx + 2.6, y_bus - 5.2, rz.get("ref", "F2"), 2.6, True)
                        for i_, s_ in enumerate((rz.get("spec") or [])[:2]):
                            c.text(lx + 2.6, y_bus - 8.2 - 2.6 * i_, s_, 2.0, layer="TEXT_GRI")
                        if rz.get("lista"):
                            self._poz_mark(lx + 7 + max([_tw(s_) for s_ in rz.get("spec") or [""]] + [6]), y_bus - 6, self._poz_add(rz))
                        ys = y_bus - 12
                    else:
                        c.line((lx, y_bus), (lx, ys), "FORTA")
                    self._place_lateral(lx, ys, l)
                    self._ref_text(lx - 5, ys - 3, l)
                    self._poz_mark(lx + 7, ys - 6, self._poz_add(l))
                    if l.get("fara_pamant"):
                        self.spd_pe = getattr(self, "spd_pe", []) + [(lx, ys - 12)]
                    grow(lx - 5 - max(_tw(s) for s in l.get("spec", [""]) + [l.get("ref", "")]), lx + 10 + (18 if rz else 0), ys - 20, y_bus); lx += 22 + (14 if rz else 0)
        elif len(intrari) + len(plecari) > 2:
            c.dot((xin[0], y_bus), 0.9)

        # --- plecări (de la bară în jos); un tablou secundar (plecare cu copii) are propria carcasă, sub tabloul părinte
        def plecare(b, x, w, dl, y0, tinta, nivel, parinte, sub_ext=None):
            """tinta = (rânduri, mm) până la începutul segmentului de cablu, comune plecărilor de pe aceeași bară"""
            y = y0
            for a in b.get("aparate", []):
                yc = y - step / 2
                c.line((x, y), (x, yc + S.HALF), "FORTA"); self._aparat(x, yc, a); c.line((x, yc - S.HALF), (x, y - step), "FORTA")
                gx = (x - dl, x + self._dreapta(a), yc - S.HALF, yc + S.HALF)
                if sub_ext is None: grow(*gx)
                else: sub_ext.append(gx)
                y -= step
            copii = b.get("copii") or []
            sar = b.get("sarcina", {})
            if not copii:
                y_end = y0 - tinta[0] * step - tinta[1]
                c.line((x, y), (x, y_end - self.seg_out), "FORTA")
                self._cabluri.append({"x": x, "hi": y_end, "lo": y_end - self.seg_out, "d": b.get("cablu"), "rot": True, "carcasa": parinte})
                bb = self._box(x, y_end - self.seg_out, sar, w, "tablou")
                self.box_bottom = min(self.box_bottom, y_end - self.seg_out - BOX_H)
                return
            if b.get("grup"):
                # grupă în același tablou (DDR cu circuitele lui): bară de distribuție scurtă („pieptene”), fără cablu și carcasă
                y_sub = y - GRUP_GAP
                c.line((x, y), (x, y_sub), "FORTA")
                dims_c = [self._col_dims(ch, True) for ch in copii]
                offs = [max(l, bw / 2 + 1) for (l, r, bw) in dims_c]
                ws = [off + max(r, bw / 2 + 1) for (l, r, bw), off in zip(dims_c, offs)]; tot = sum(ws); k = min(1.0, (w - 2) / tot) if tot else 1.0
                xs, xx = [], x - tot * k / 2
                for off, wc in zip(offs, ws):
                    xs.append(xx + off * k); xx += wc * k
                if len(xs) % 2 and abs(x - xs[len(xs) // 2]) < 0.15 * w:     # nr. impar: circuitul din mijloc sub DDR, fără nod decalat
                    d = x - xs[len(xs) // 2]; xs = [v + d for v in xs]
                if len(xs) == 1:
                    xs = [x]          # un singur circuit sub DDR: continuă pe aceeași axă, fără bară
                bx1, bx2 = min(xs + [x]) - 2, max(xs + [x]) + 2
                if len(xs) > 1:
                    c.line((bx1, y_sub), (bx2, y_sub), "FORTA")
                    for cx in xs: c.dot((cx, y_sub), 0.7)
                    if all(abs(cx - x) > 0.5 for cx in xs): c.dot((x, y_sub), 0.7)
                if b.get("eticheta_grup") and len(xs) > 1:
                    c.text(bx2 + 1.5, y_sub + 0.8, b["eticheta_grup"], 1.9, layer="TEXT_GRI")
                gx = (bx1, bx2, y_sub - 1, y_sub + 1)
                if sub_ext is None: grow(*gx)
                else: sub_ext.append(gx)
                rest = (tinta[0] - len(b.get("aparate", [])), tinta[1] - GRUP_GAP)
                for ch, cx, (l, r, bw), wc in zip(copii, xs, dims_c, ws):
                    plecare(ch, cx, wc * k, l, y_sub, rest, nivel + 1, parinte, sub_ext)
                return
            # tablou secundar: cablu -> carcasa proprie (titlu, bară, plecările copiilor)
            y_ct = y - self.seg_out
            c.line((x, y), (x, y_ct - SUB_HEAD), "FORTA")
            self._cabluri.append({"x": x, "hi": y, "lo": y_ct, "d": b.get("cablu"), "rot": True, "carcasa": parinte})
            y_sub = y_ct - SUB_HEAD
            dims_c = [self._col_dims(ch, True) for ch in copii]
            offs = [max(l, bw / 2 + 1) for (l, r, bw) in dims_c]
            ws = [off + max(r, bw / 2 + 1) for (l, r, bw), off in zip(dims_c, offs)]; tot = sum(ws); k = min(1.0, (w - 2) / tot) if tot else 1.0
            xs, xx = [], x - tot * k / 2
            for off, wc in zip(offs, ws):
                xs.append(xx + off * k); xx += wc * k
            bx1, bx2 = min(xs) - 6, max(xs) + 6
            c.line((bx1, y_sub), (bx2, y_sub), "FORTA"); c.line((bx1, y_sub - 0.7), (bx2, y_sub - 0.7), "FORTA")
            for cx in xs: c.dot((cx, y_sub), 0.9)
            c.dot((x, y_sub), 0.9)
            rest = (tinta[0] - len(b.get("aparate", [])), tinta[1] - self.seg_out - SUB_HEAD)
            nume = sar.get("titlu", "") or "TD"
            ext_td = [(bx1, bx2, y_sub - 1, y_sub)]
            for ch, cx, (l, r, bw), wc in zip(copii, xs, dims_c, ws):
                plecare(ch, cx, wc * k, l, y_sub, rest, nivel + 1, nume, ext_td)
            sub_ext_ = ext_td
            # carcasa tabloului secundar
            ex1 = min(e[0] for e in sub_ext_); ex2 = max(e[1] for e in sub_ext_); ey1 = min(e[2] for e in sub_ext_)
            tw_ = _tw(nume, 3.0) + 4 + _tw(sar.get("sub", ""), 2.1) + 8
            cx1 = min(ex1 - 4, x - tw_ / 2); cx2 = max(ex2 + 4, cx1 + tw_)
            cy1, cy2 = ey1 - 7, y_ct
            c.rect(cx1, cy1, cx2 - cx1, cy2 - cy1, "CARCASA")
            self._titlu_carcasa(cx1, cx2, cy2, nume, sar.get("sub", ""))
            self.meta["carcase"].append({"nume": nume, "bbox": (cx1, cy1, cx2, cy2), "parinte": parinte})
            self.meta["obiecte"].append({"tip": "tablou", "nume": nume, "bbox": (bx1, y_sub - 1, bx2, y_sub + 0.5)})
            self._carcase_y[nume] = (cy1, cy2)

        self._carcase_y = {}
        for b, x, w, (dl, dr, _) in zip(plecari, xout, wout, dims_out):
            plecare(b, x, w, dl, y_bus, (a_out, b_out), 0, "principala" if car else None)

        # --- carcasa principală
        if ext[0] < 1e8:
            x1 = ext[0] - (BN_DX + 8 if has_bn else 5); x2 = ext[1] + 6
            if getattr(self, "bn_stanga", None):
                x1 -= 10
                xn, yn, ln = self.bn_stanga
                xb = x1 + 22 + BN_DX
                # TT: bara PE nu se leagă de conductoarele coloanei (PE local, numai de la priza proprie)
                if not ln.get("fara_legatura"): c.line((xn, yn), (xb, yn), "FORTA")
                self._place_lateral(xb, yn, ln); self.bn_xy = (xb - BN_DX, yn)
            y1 = ext[2] - 7 - (10 if has_bn else 0)
            y2 = ext[3] + 7
            y2 = min(y2, (y_out_bot - 10) if y_out_bot is not None else y_top - BOX_H - 10)
            self.y_carcasa_jos = y1
            if car:
                c.rect(x1, y1, x2 - x1, y2 - y1, "CARCASA")
                self._titlu_carcasa(x1, x2, y2, car.get("titlu", ""), car.get("sub", ""))
                self.meta["carcase"].append({"nume": car.get("titlu", "") or "carcasă", "bbox": (x1, y1, x2, y2), "parinte": None, "principala": True})
                self._carcase_y["principala"] = (y1, y2)
        else:
            self.y_carcasa_jos = y_bus

        # --- etichetele de cablu, după ce se cunosc carcasele (nu taie conturul carcasei)
        for cb in self._cabluri:
            hi, lo = cb["hi"], cb["lo"]
            cy = self._carcase_y.get(cb["carcasa"]) if cb["carcasa"] else None
            if cy:
                if cb.get("sus"): lo = max(lo, cy[1] + 1.5)
                else: hi = min(hi, cy[0] - 1.5)
            if cb["rot"]: self._cablu_rot(cb["x"], hi, lo + 1.0, cb["d"])
            else: self._cablu(cb["x"], (hi + lo) / 2 - 0.3, cb["d"])

        # --- PE: BN -> PS -> PPL
        if has_bn and self.bn_xy:
            bx, by = self.bn_xy
            for (sx, sy) in getattr(self, "spd_pe", []):          # pământul SPD → bara PE (nu priză separată)
                c.line((sx, sy), (bx, sy), "PE"); c.dot((bx, sy), 0.7)
            yps = self.y_carcasa_jos + 8
            c.line((bx, by - 1.6), (bx, yps + 3.5), "PE"); self._place_lateral(bx, yps, {"tip": "piesa_separatie"})
            yg = min(self.y_carcasa_jos - 8, self.box_bottom - 2 if self.box_bottom < 1e8 else 1e9)
            sec = [cy[1] for k_, cy in self._carcase_y.items() if k_ != "principala"]
            if sec:        # un tablou secundar desenat sub carcasa principală: priza de pământ rămâne deasupra lui
                yg = max(yg, max(sec) + 16)
                yg = min(yg, self.y_carcasa_jos - 14)
            c.line((bx, yps - 3.5), (bx, yg), "PE"); self._place_lateral(bx, yg, {"tip": "pamant"})
            c.text(bx, yg - 7.5, "PPL", 2.6, True, align="middle"); c.text(bx, yg - 10.8, m.get("rp", "Rp ≤ 4 Ω"), 2.1, align="middle")
            self._poz_mark(bx + 8, yps, self._poz_add({"ref": m.get("ref_pe", "BN·PS·PPL"), "tip": "bareta_nul",
                                                       "lista": m.get("lista_pe", ["Baretă de nul · piesă de separație · priză de pământ locală"])}))

    def _titlu_carcasa(self, x1, x2, y2, titlu, sub):
        """titlul carcasei, sus-stânga, fără să traverseze conductoarele care intră în carcasă:
        subtitlul trece pe rândul al doilea sau se micșorează dacă nu încape până la prima coloană"""
        c = self.c
        xs = [min(it.a[0], it.b[0]) for it in c.items if isinstance(it, Line) and it.layer == "FORTA"
              and abs(it.a[0] - it.b[0]) < 0.01 and min(it.a[1], it.b[1]) < y2 - 1 and max(it.a[1], it.b[1]) > y2 - 9 and x1 < it.a[0] < x2]
        xs = sorted(xs)
        iv = list(zip([x1 + 3] + [x + 3.5 for x in xs], [x - 3.5 for x in xs] + [x2 - 3]))
        tx, lim = iv[0]
        h1 = min(3.0, 3.0 * (lim - tx) / max(text_width(titlu, 3.0, True), 0.1))
        c.text(tx, y2 - 4.4, titlu, h1, True)
        if not sub: return
        sx = tx + text_width(titlu, h1, True) + 3
        tw = text_width(sub, 2.1)
        if tw <= lim - sx:
            c.text(sx, y2 - 4.4, sub, 2.1, layer="TEXT_GRI"); return
        for a_, b_ in iv[1:]:               # alt interval liber dintre coloane, pe același rând
            if tw <= b_ - a_:
                c.text(a_, y2 - 4.4, sub, 2.1, layer="TEXT_GRI"); return
        h2 = min(2.1, 2.1 * (lim - tx) / max(tw, 0.1))
        c.text(tx, y2 - 8.0, sub, h2, layer="TEXT_GRI")

    # ------------------------------------------------------------ scalare pe A2
    def _scaleaza(self, i0, marire=False):
        """încadrează schema în zona ei: o micșorează uniform dacă nu încape (multe coloane) și, pe A2 (marire=True),
        o mărește uniform — pas vertical, lățimi de coloană, simboluri și texte — ca să ocupe spațiul disponibil"""
        c = self.c
        items = c.items[i0:]
        bb = _bbox_items(items)
        if bb is None: return
        X1, X2 = 15.0, self.x_right - 2
        Y1, Y2 = (self.note_top + 6 if self.m.get("note") else 15.0), self.h - 15
        fits = bb[0] >= X1 and bb[2] <= X2 and bb[1] >= Y1 - 1 and bb[3] <= Y2 + 3
        kx, ky = (X2 - X1) / max(bb[2] - bb[0], 1), (Y2 - Y1) / max(bb[3] - bb[1], 1)
        self.kx_ky = (kx, ky)
        k = min(1.5 if marire else 1.0, kx, ky)
        if fits and k < 1.02: return
        if not fits and k >= 1.0 and not marire: k = 1.0
        ox = (X1 + X2) / 2 - k * (bb[0] + bb[2]) / 2
        oy = Y2 - k * bb[3]
        c.items[i0:] = [transform_item(it, k, ox, oy) for it in items]
        T = lambda b: (b[0] * k + ox, b[1] * k + oy, b[2] * k + ox, b[3] * k + oy)
        P = lambda p: (p[0] * k + ox, p[1] * k + oy)
        for key in ("carcase", "obiecte"):
            for o in self.meta[key]: o["bbox"] = T(o["bbox"])
        for l in self.meta["legaturi"]:
            for f in ("de_xy", "spre_xy", "sageata"):
                if l.get(f): l[f] = P(l[f])
            for f in ("de_bbox", "spre_bbox"):
                if l.get(f): l[f] = T(l[f])
        self.meta["poz"] = [(P(p), r * k) for p, r in self.meta["poz"]]
        self.meta["scara"] = k

    # ------------------------------------------------------------ elemente
    def _box(self, x, y_top, d, slot_w, rol="tablou"):
        c = self.c
        w = min(max(14.0, slot_w - 3), 64.0)
        if getattr(self, "has_bn", False): w = min(w, 2 * (BN_DX - 4))
        c.rect(x - w/2, y_top - BOX_H, w, BOX_H, "SIMBOL", fill="#f3f3f3")
        h1 = min(3.0, 3.0 * (w - 3) / max(_tw(d.get("titlu", ""), 3.0), 1)); h2 = min(2.0, 2.0 * (w - 3) / max(_tw(d.get("sub", ""), 2.0), 1))
        c.text(x, y_top - 4.6, d.get("titlu", ""), h1, True, align="middle")
        c.text(x, y_top - 9.6, d.get("sub", ""), h2, align="middle", layer="TEXT_GRI")
        bb = (x - w / 2, y_top - BOX_H, x + w / 2, y_top)
        self.meta["obiecte"].append({"tip": rol, "nume": d.get("titlu", ""), "bbox": bb})
        return bb

    def _cablu(self, x, y, d):
        """etichetă de cablu orizontală (intrări)"""
        if not d: return
        c = self.c
        c.slash(x, y, d.get("cond"))
        if d.get("ref"): c.text(x - 4.5, y + 2.2, d["ref"], 2.5, True, align="right")
        if d.get("text"): c.text(x - 4.5, y - 2.6, d["text"], 2.0, align="right", layer="TEXT_GRI")

    def _cablu_rot(self, x, hi, lo, d):
        """etichetă de cablu a unei plecări: marcaj + ref sus, tipul cablului (stânga) și conductoarele (dreapta)
        scrise rotit la 90°, de-a lungul cablului, între `hi` și `lo`"""
        if not d: return
        c = self.c
        ys = hi - 3.2
        c.line((x - 2.4, ys - 1.5), (x + 2.4, ys + 1.5))
        if d.get("ref"): c.text(x - 3.6, ys - 0.2, d["ref"], 2.5, True, align="right")
        top, bot = ys - 3.2, lo
        L = top - bot
        if L <= 2: return
        mid = (top + bot) / 2
        for s_, side, lay in ((d.get("text", ""), -1, "TEXT_GRI"), (d.get("cond", ""), 1, "TEXT")):
            if not s_: continue
            h = min(2.0, 2.0 * L / max(text_width(s_, 2.0), 0.1))
            xb = x - 0.8 - 0.22 * h if side < 0 else x + 0.8 + h
            c.text(xb, mid, s_, h, align="middle", layer=lay, rot=90)

    def _ref_text(self, x, y, a):
        c = self.c
        c.text(x, y + 1.0, a.get("ref", ""), 2.8, True, align="right")
        for i, s in enumerate(a.get("spec", [])[:3]):
            c.text(x, y - 2.6 - 3.0 * i, s, 2.1, align="right")

    def _poz_add(self, a):
        """poziție în lista de echipamente. Aparatele identice (același tip și același text de listă) primesc ACEEAȘI
        poziție, cu cantitatea însumată și notațiile reunite (SPEC §E.1 pct. 5)."""
        lista = a.get("lista") or [S.SYMBOLS.get(a.get("tip", "nod"), (None, a.get("tip", ""), ""))[1] + (" · " + " · ".join(a.get("spec", [])) if a.get("spec") else "")]
        ref = a.get("ref") or a.get("eticheta", "")
        buc = a.get("buc", 1)
        cheie = (a.get("tip", ""), tuple(lista))
        for i, (n0, ref0, lista0, buc0, tip0) in enumerate(self.poz):
            if (tip0, tuple(lista0)) == cheie and isinstance(buc0, (int, float)) and isinstance(buc, (int, float)):
                refs = ref0.split(", ") if ref0 else []
                if ref and ref not in refs: refs.append(ref)
                self.poz[i] = (n0, ", ".join(refs), lista0, buc0 + buc, tip0)
                return n0
        n = len(self.poz) + 1
        self.poz.append((n, ref, lista, buc, a.get("tip", "")))
        return n

    def _poz_mark(self, x, y, n, r=2.4):
        self.c.circle((x, y), r); self.c.text(x, y - 0.85, str(n), 2.2, True, align="middle")
        self.meta["poz"].append(((x, y), r))

    def _poz_liber(self, cands, i0, r=2.4):
        """prima poziție candidată a cercului de poziție care nu atinge nimic din ce s-a desenat de la indexul i0"""
        boxes, segs = [], []
        for it in self.c.items[i0:]:
            if isinstance(it, BlockRef): boxes.append(block_bbox(it))
            elif isinstance(it, Solid): boxes.append(prim_bbox(it))
            elif isinstance(it, Text): boxes.append(text_bbox(it))
            elif isinstance(it, Circle): boxes.append(prim_bbox(it))
            else: segs += item_segments(it)
        for p in self.meta["poz"]:
            boxes.append((p[0][0] - p[1], p[0][1] - p[1], p[0][0] + p[1], p[0][1] + p[1]))
        segs += getattr(self, "bus_segs", [])       # bara principală (desenată înaintea plecărilor)
        for (x, y) in cands:
            bb = (x - r - 0.4, y - r - 0.4, x + r + 0.4, y + r + 0.4)
            if any(b and bbox_overlap(bb, b) for b in boxes): continue
            if any(seg_hits_box(a, b, bb) for a, b in segs): continue
            return (x, y)
        return cands[0]

    def _aparat(self, x, yc, a):
        """desenează aparatul + lateralele lui; întoarce caseta geometriei simbolului"""
        c = self.c
        i0 = len(c.items)
        tip = a.get("tip", "nod")
        if tip not in S.SYMBOLS: tip = "nod"
        lats = [l for l in (a.get("laterale") or []) if isinstance(l, dict) and l.get("tip")]
        d = dict(a)
        cmd = [l for l in lats if l.get("legatura") == "comanda" and l["tip"] not in SPD_TIP and l["tip"] != "bareta_nul"]
        if cmd and tip in BD_TIP: d["bd"] = True
        prims = S.draw(tip, d)
        name = "SYM_" + tip.upper() + ("_BD" if d.get("bd") and tip in BD_TIP else "") + ("_N" if tip == "trafo" and d.get("neutru_pamant") else "")
        br = BlockRef(name, (x, yc), {"REF": a.get("ref", ""), "SPEC": " | ".join(a.get("spec", [])), "TIP": tip}, prims, uid=a.get("_uid", ""))
        c.add(br)
        sym_bb = block_bbox(br)
        if tip != "nod":
            self._ref_text(x - 2 - LEFT_EXT.get(tip, 4), yc + 2, a)
            n_ap = self._poz_add(a)        # aparatul primește numărul înaintea lateralelor lui
        anc = getattr(prims, "anc", {})
        # ---- laterale
        chain, volt, spds = [], [], []
        for l in lats:
            t = l["tip"]
            if t == "bareta_nul" and l.get("la_stanga"):
                # bara PE / N a tabloului se desenează la marginea stângă a carcasei (după ce se cunoaște carcasa):
                # traseul PE nu traversează coloanele plecărilor
                if not l.get("fara_legatura"): c.dot((x, yc), 0.9)
                self.bn_stanga = (x, yc, l)
            elif t == "bareta_nul":
                c.dot((x, yc), 0.9); self._place_lateral(x, yc, l); self.bn_xy = (x - BN_DX, yc)
            elif t in SPD_TIP:
                spds.append(l)
            elif _e_tensiune(l):
                volt.append(l)
            else:
                chain.append(l)
        lx = x + 6 if tip == "tc" else x + 12
        mx, my = anc.get("masura", (2.4, 0.0)); pin = (x + mx, yc + my)
        meter = None
        for l in chain:
            t = l["tip"]
            w = LAT_W.get(t, 20); cx = lx + 8 + w / 2
            comanda = l.get("legatura") == "comanda"
            # v1.8: „pe” = conductor de echipotențializare (verde, fără săgeată); „grup” = aparatul face parte din cutia laterală
            lay = "COMANDA" if comanda else {"pe": "PE", "grup": "CARCASA"}.get(l.get("legatura"), "MASURA")
            xe = lx + 8 - 0.5 if t != "fuzibil" else cx - w / 2
            lb = self._lat_bbox(cx, yc, l)
            if comanda:
                kx, ky = anc.get("comanda", (mx, my)); src = (x + kx, yc + ky)
                c.line((xe, src[1]), src, lay); c.arrow(src, "left", 2.2, lay)
                self.meta["legaturi"].append({"tip": "comanda", "de": l.get("ref") or l.get("eticheta", ""), "spre": a.get("ref", ""),
                                              "de_xy": (xe, src[1]), "spre_xy": src, "sageata": src, "de_bbox": lb, "spre_bbox": sym_bb})
            else:
                c.line(pin, (xe, pin[1]), lay)
                if lay == "MASURA": c.arrow((xe, pin[1]), "right", 2.2, lay)
                self.meta["legaturi"].append({"tip": "masura", "de": a.get("ref", ""), "spre": l.get("ref") or l.get("eticheta", ""),
                                              "lateral": t, "aparat_tip": tip, "de_xy": pin, "spre_xy": (xe, pin[1]), "sageata": (xe, pin[1])})
            self._place_lateral(cx, yc, l)
            if l.get("ref"):
                if t == "contor":       # la dreapta casetei (deasupra ei poate fi o casetă laterală din rândul de sus, ex. PI)
                    c.text(cx + w / 2 + 1.5, yc + 2.5, l["ref"], 2.6, True)
                else:
                    c.text(cx, yc + (9.0 if t == "cutie" else 4.0), l["ref"], 2.6, True, align="middle")
            if t in ("contor", "cutie"):
                self._poz_mark(cx + w / 2 + 4, yc - 5.5, self._poz_add(l))
            elif t == "cleme":
                self._poz_mark(cx, yc - 6.2, self._poz_add(l))
            elif t == "fuzibil":       # fuzibil forțat în lanțul de curent (V57)
                self._poz_mark(cx, yc - 6.2, self._poz_add(l))
            if t == "contor": meter = (cx, w, l)
            pin = (cx + w / 2, yc); lx = cx + w / 2
        for l in volt:
            self._tensiune(x, yc, l, meter, chain, a, i0)
        xs = (lx + 14) if chain else (x + 26)
        for l in spds:
            self._spd_aparat(x, yc, l, xs, i0); xs += 22
        # ---- poziția aparatului: primul loc liber (nu peste simboluri, săgeți sau linii de legătură)
        if tip != "nod":
            dx = _poz_dx(d)
            cands = [(x + dx, yc - 5.5), (x + dx, yc + 5.5), (x + dx, yc - 7.0), (x + dx + 3, yc - 6.0), (x + dx, yc + 1.0), (x + dx + 3, yc + 5.5)]
            px, py = self._poz_liber(cands, i0)
            self._poz_mark(px, py, n_ap)
        return sym_bb

    def _lat_bbox(self, cx, yc, l):
        t = l["tip"]
        if t == "cutie": w, h = l.get("w", 28), l.get("h", 12)
        elif t == "contor": w, h = 28, 16
        elif t == "cleme": w, h = 12, 5.2
        else: w, h = LAT_W.get(t, 8), 4
        return (cx - w / 2, yc - h / 2, cx + w / 2, yc + h / 2)

    def _tensiune(self, x, yc, l, meter, chain, a, i_t0):
        """circuitul de tensiune al contorului: derivație de pe conductorul de forță (amonte / aval de aparat),
        prin siguranțele F, pe a doua intrare a contorului"""
        c = self.c
        aval = l.get("sursa_legatura") == "aval"
        yv = yc - self.step / 2 if aval else yc + self.step / 2
        if meter:
            mcx, mw, ml = meter
            x_in = mcx - mw / 2 + 5
        # siguranța se pune între ultimul element din fața contorului și contor
        left_lim = x + 12
        right_lim = (mcx - mw / 2) if meter else x + 40
        fx = max(left_lim + 6, min((left_lim + right_lim) / 2 + 2, right_lim - 6)) if meter else x + 26
        w = LAT_W["fuzibil"]
        c.dot((x, yv), 0.9)
        c.line((x, yv), (fx - w / 2, yv), "MASURA")
        self._place_lateral(fx, yv, l)
        if l.get("ref"): c.text(fx, yv + 2.6, l["ref"], 2.6, True, align="middle")
        if meter:
            ty = yc + 8 if not aval else yc - 8
            c.line((fx + w / 2, yv), (x_in, yv), "MASURA"); c.line((x_in, yv), (x_in, ty + (2.2 if not aval else -2.2)), "MASURA")
            c.arrow((x_in, ty), "down" if not aval else "up", 2.2, "MASURA")
            tgt = ml.get("ref") or ml.get("eticheta", "contor")
        else:
            c.line((fx + w / 2, yv), (fx + w / 2 + 6, yv), "MASURA"); c.arrow((fx + w / 2 + 6, yv), "right", 2.2, "MASURA")
            tgt = ""
        cands = [(fx + w / 2 + 4.5, yv + 3.4), (fx, yv + (-4.6 if not aval else 4.6)), (fx - w / 2 - 4.5, yv + 3.4), (fx, yv + 7.6)]
        self._poz_mark(*self._poz_liber(cands, i_t0), self._poz_add(l))
        self.meta["legaturi"].append({"tip": "tensiune", "de": (a.get("ref", "") + " amonte") if not aval else (a.get("ref", "") + " aval"),
                                      "spre": tgt, "prin": l.get("ref", ""), "aparat_tip": a.get("tip"), "de_xy": (x, yv)})

    def _spd_aparat(self, x, yc, l, xs, i0):
        """descărcător legat în amonte de aparat (sus, în rândul propriu): derivație spre dreapta, descărcătorul și
        priza de pământ dedesubt, în zona liberă a rândului"""
        c = self.c
        yt = yc + self.step / 2
        c.dot((x, yt), 0.9); c.line((x, yt), (xs, yt), "FORTA")
        self._place_lateral(xs, yt, l)
        tx = xs + 5
        if l["tip"] == "descarcator_mt":
            # descărcătoarele MT stau la intrarea liniei, deasupra celulei (și a conturului postului): textele pe un
            # singur rând, deasupra derivației, ca să nu taie conturul
            ref = l.get("ref", ""); c.text(tx, yt - 8.5, ref, 2.8, True)
            sp = " · ".join(l.get("spec", [])[:2]); wr = text_width(ref, 2.8, True)
            c.text(tx + wr + 2.5, yt - 8.5, sp, 2.1)
            w = wr + 2.5 + text_width(sp, 2.1)
            cands = [(tx + w + 4.5, yt - 7.5), (tx + w + 4.5, yt - 12.0), (tx + 3, yt - 13.5)]
            self._poz_mark(*self._poz_liber(cands, i0), self._poz_add(l))
            return
        c.text(tx, yt - 5.0, l.get("ref", ""), 2.8, True)
        for i, s in enumerate(l.get("spec", [])[:2]):
            c.text(tx, yt - 8.4 - 3.0 * i, s, 2.1)
        w = max([text_width(l.get("ref", ""), 2.8, True)] + [text_width(s, 2.1) for s in l.get("spec", [])[:2]])
        cands = [(tx + w + 4, yt - 6.0), (xs - 7.5, yt - 7.0), (tx + w + 4, yt - 11.0)]
        self._poz_mark(*self._poz_liber(cands, i0), self._poz_add(l))

    def _place_lateral(self, x, y, l):
        tip = "fuzibil_lat" if l["tip"] == "fuzibil" else l["tip"]
        if tip not in S.SYMBOLS: tip = "cutie"
        prims = S.draw(tip, l)
        self.c.add(BlockRef("SYM_" + tip.upper(), (x, y), {"REF": l.get("ref", ""), "TIP": tip}, prims, uid=l.get("_uid", "")))

    # ------------------------------------------------------------ tabel, legendă, note, cartuș
    def _tabel(self):
        c = self.c
        x0 = self.w - 10 - 158; w = 150; y = self.h - 20
        c.text(x0, y - 3, self.m.get("titlu_lista", "LISTĂ DE ECHIPAMENTE ȘI MATERIALE"), 3.0, True)
        y -= 6; hdr = 5.0
        c.rect(x0, y - hdr, w, hdr, "TABEL", fill="#f3f3f3")
        cols = (0, 9, 30, 140)
        for cx_, s, al in ((4.5, "Poz.", "middle"), (cols[1] + 1.5, "Simbol", "left"), (cols[2] + 1.5, "Denumire · caracteristici", "left"), (145, "Buc.", "middle")):
            c.text(x0 + cx_, y - 3.5, s, 2.1, True, align=al)
        y -= hdr; ytop = y
        # spațiul disponibil până deasupra cartușului (+ legendă); dacă nu încape, se compactează: întâi mai puține
        # rânduri pe poziție, apoi corp de literă mai mic
        y_lim = 11 + 67.7 + (26 if self.m.get("legenda", True) else 4)
        fh, step, max_l = 1.9, 3.1, 4
        def _inalt(fh_, step_, ml):
            mc = int((cols[3] - cols[2] - 3) / (CH * fh_ / 2.1)); tot = 0
            for (_, _, lista, _, _) in self.poz:
                ln = sum((_wrap(s_, mc) for s_ in lista), [])[:ml]
                tot += 2.2 * fh_ / 1.9 + step_ * len(ln)
            return tot
        for fh, step, max_l in ((1.9, 3.1, 4), (1.9, 3.1, 3), (1.7, 2.75, 3), (1.7, 2.75, 2), (1.5, 2.4, 2), (1.4, 2.2, 1)):
            if y - _inalt(fh, step, max_l) >= y_lim: break
        self.tabel_font = fh
        maxc = int((cols[3] - cols[2] - 3) / (CH * fh / 2.1))
        for (n, ref, lista, buc, tip) in self.poz:
            lines = []
            for s in lista:
                lines += _wrap(s, maxc)
            lines = lines[:max_l]
            rh = 2.2 * fh / 1.9 + step * len(lines)
            ym = y - rh / 2 - 0.7
            ref = _refs_compacte(ref)
            def _fit(s_, h_, lat, bold=False):   # corpul de literă cu care textul încape în coloană (cu marjă)
                from .canvas import text_width
                return min(h_, h_ * lat / max(text_width(s_, h_, bold) * 1.1, 0.1))
            hr = _fit(ref, 2.1, cols[2] - cols[1] - 2.5, True)
            c.text(x0 + 4.5, ym, str(n), 2.1, align="middle"); c.text(x0 + cols[1] + 1.5, ym, ref, hr, True)
            c.text(x0 + 145, ym, str(buc), _fit(str(buc), 2.1, w - cols[3] - 1.5), align="middle")
            for i, s in enumerate(lines):
                c.text(x0 + cols[2] + 1.5, y - step - step * i, s, _fit(s, fh, cols[3] - cols[2] - 2.5), layer="TEXT_GRI" if i else "TEXT")
            y -= rh; c.line((x0, y), (x0 + w, y), "TABEL")
        c.rect(x0, y, w, ytop - y + hdr, "TABEL")
        for cx_ in cols[1:]: c.line((x0 + cx_, ytop + hdr), (x0 + cx_, y), "TABEL")
        self.y_tabel_jos = y

    def _legenda(self):
        c = self.c
        x0 = self.w - 10 - 158; y = getattr(self, "y_tabel_jos", self.h - 60) - 8
        c.text(x0, y, "LEGENDĂ", 2.8, True); y -= 5
        items = [("FORTA", "circuit de forță"), ("MASURA", "circuite de măsură"), ("COMANDA", "circuit de comandă"),
                 ("PE", "conductor de protecție PE"), ("CARCASA", "carcasă / tablou"), ("MECANIC", "legătură mecanică")]
        for i, (lay, s) in enumerate(items):
            yy = y - 4.5 * (i % 3); xx = x0 + 75 * (i // 3)
            c.line((xx, yy + 0.8), (xx + 10, yy + 0.8), lay); c.text(xx + 12, yy, s, 2.1)
        yy = y - 13.5
        c.circle((x0 + 5, yy + 0.8), 2.0); c.text(x0 + 5, yy + 0.1, "n", 1.8, True, align="middle"); c.text(x0 + 12, yy, "poziție în lista de echipamente", 2.1)
        y -= 18
        abrev = self.m.get("abrevieri")
        if abrev:
            y -= 4; c.text(x0, y, "ABREVIERI", 2.8, True); y -= 4.5
            for s in abrev[:10]: c.text(x0, y, s, 2.0); y -= 3.6

    def _calc_note(self):
        """înălțimea zonei de note (deasupra marginii de jos, la stânga cartușului): se alege cel mai mare corp de literă
        (2,0 … 1,5 mm) cu care notele încap în cel mult 40 % din înălțimea foii; zona schemei începe deasupra."""
        note = self.m.get("note") or []
        self.note_h_txt, self.note_top = 2.0, 50.0
        if not note: return
        x0 = 16
        for h in (2.0, 1.8, 1.65, 1.5):
            maxc = int((self.w - 10 - 174 - x0 - 6) / (CH * h / 2.1))
            n = sum(len(_wrap(s, maxc)) for s in note)
            top = 12 + 4.5 + n * h * 1.6 + 0.4 * len(note)
            self.note_h_txt, self.note_top = h, max(50.0, top)
            if top <= 0.4 * self.h: break

    def _note(self):
        c = self.c
        note = self.m.get("note") or []
        if not note: return
        h = self.note_h_txt
        x0, y = 16, self.note_top
        c.text(x0, y, "NOTE", 2.8, True); y -= 4.5
        maxc = int((self.w - 10 - 174 - x0 - 6) / (CH * h / 2.1))
        for s in note:
            for ln in _wrap(s, maxc):
                c.text(x0, y, ln, h); y -= h * 1.6
            y -= 0.4

    def _cartus(self):
        """cartuș (SPEC G.5): verificator, beneficiar, titlu + adresă, nr. ATR / aviz, proiectant (firmă, J, CUI) + L.S.,
        atestat ANRE (nr. + tip Bp/Ap), denumire plan, tabel de semnături (șef proiect, proiectat, desenat, verificat),
        fază, planșă, revizie, scară, format, dată, nr. proiect. Un câmp lipsă rămâne gol.
        Fiecare text se centrează vertical în rândul lui și se micșorează dacă nu încape pe lățimea celulei."""
        c = self.c; k = self.m.get("cartus", {}) or {}
        W, H = 158.0, 67.7
        x0, y0 = self.w - 11 - W, 11
        XR = 124.0                 # coloana din dreapta (fază, planșă …)
        C1 = 34.0                  # coloana de etichete
        CN, CS = 84.0, 104.0       # tabelul de semnături: nume | semnătură | dată
        def L(x1, y1, x2, y2): c.line((x0 + x1, y0 + H - y1), (x0 + x2, y0 + H - y2), "CARTUS")
        def T(x, y, s, h=2.1, b=False, i=False, al="left", maxw=None):
            s = "" if s is None else str(s)
            if maxw and s: h = min(h, h * maxw / max(text_width(s, h, b), 0.1))
            c.text(x0 + x, y0 + H - y, s, h, b, i, al, "TEXT")
        def cell(x, yt, rh, s, h=2.1, b=False, i=False, al="left", maxw=None):
            """text centrat vertical în rândul [yt, yt + rh] (y măsurat de sus în jos)"""
            s = "" if s is None else str(s)
            if maxw and s: h = min(h, h * maxw / max(text_width(s, h, b), 0.1))
            T(x, yt + (rh + h) / 2 - 0.1, s, h, b, i, al)
        c.rect(x0, y0, W, H, "CARTUS", fill="#fff")
        SIG = [45.0, 48.5, 52.3, 56.1, 59.9, 63.7]
        for y in (5, 10, 17.5, 22.5, 33, 38) + tuple(SIG[:-1]): L(0, y, XR, y)
        L(0, SIG[-1], W, SIG[-1])
        L(C1, 0, C1, SIG[-1]); L(92, 0, 92, 5); L(100, 22.5, 100, 33)
        L(CN, SIG[0], CN, SIG[-1]); L(CS, SIG[0], CS, SIG[-1]); L(XR, 0, XR, SIG[-1])
        # stânga
        cell(1, 0, 5, "VERIFICATOR:", 1.9); cell(C1 + 1, 0, 5, k.get("verificator", ""), 1.9, maxw=92 - C1 - 2)
        cell(93, 0, 5, "REFERAT NR.", 1.6); cell(109, 0, 5, k.get("referat", ""), 1.7, maxw=XR - 110)
        cell(1, 5, 5, "BENEFICIAR:", 1.9); cell(C1 + 1, 5, 5, k.get("beneficiar", ""), 2.1, True, maxw=XR - C1 - 2)
        cell(1, 10, 7.5, "TITLU PROIECT:", 1.9)
        T(C1 + 1, 13.3, k.get("titlu", ""), 2.0, True, maxw=XR - C1 - 2); T(C1 + 1, 16.6, k.get("adresa", ""), 1.7, maxw=XR - C1 - 2)
        cell(1, 17.5, 5, "NR. ATR / AVIZ:", 1.9); cell(C1 + 1, 17.5, 5, k.get("atr", ""), 1.9, maxw=XR - C1 - 2)
        T(1, 26.2, "PROIECTANT DE", 1.7); T(1, 29.0, "SPECIALITATE", 1.7); T(1, 31.8, "INSTALAȚII ELECTRICE:", 1.7, maxw=C1 - 2)
        T(C1 + 1, 25.6, k.get("proiectant", ""), 2.0, True, maxw=100 - C1 - 2)
        T(C1 + 1, 28.7, k.get("adresa_proiectant", ""), 1.6, i=True, maxw=100 - C1 - 2)
        T(C1 + 1, 31.8, k.get("reg", ""), 1.6, i=True, maxw=100 - C1 - 2)
        cell(112, 22.5, 10.5, "L.S.", 2.1, al="middle")
        cell(1, 33, 5, "ATESTAT ANRE:", 1.9)
        at = " · ".join(s_ for s_ in (("nr. " + str(k["atestat_anre"])) if k.get("atestat_anre") else "",
                                       ("tip " + str(k["atestat_tip"])) if k.get("atestat_tip") else "") if s_)
        cell(C1 + 1, 33, 5, at, 1.9, maxw=XR - C1 - 2)
        cell(1, 38, 7, "DENUMIRE PLAN:", 1.9)
        T(C1 + 1, 41.0, k.get("denumire1", ""), 2.0, True, maxw=XR - C1 - 2)
        T(C1 + 1, 44.3, k.get("denumire2", ""), 2.0, True, maxw=XR - C1 - 2)
        cell(1, SIG[0], 3.5, "Funcția", 1.5, True); cell(C1 + 1, SIG[0], 3.5, "Numele", 1.5, True)
        cell((CN + CS) / 2, SIG[0], 3.5, "Semnătura", 1.5, True, al="middle"); cell((CS + XR) / 2, SIG[0], 3.5, "Data", 1.5, True, al="middle")
        for y, lab, key in zip(SIG[1:], ("Șef proiect", "Proiectat", "Desenat", "Verificat"), ("sef_proiect", "proiectat", "desenat", "verificat")):
            cell(1, y, 3.8, lab, 1.8); cell(C1 + 1, y, 3.8, k.get(key, ""), 1.8, maxw=CN - C1 - 2)
        # dreapta
        for y in (13, 25, 31, 37, 43, 51): L(XR, y, W, y)
        L(XR + 19, 13, XR + 19, 25)
        T(XR + 1, 3.0, "FAZA:", 1.7); T(XR + 21, 11.4, k.get("faza", ""), 6.0, True, al="middle", maxw=W - XR - 10)
        T(XR + 1, 16.0, "PLANȘA NR.", 1.6, maxw=17); T(XR + 9.5, 23.0, k.get("plansa", ""), 3.4, True, al="middle", maxw=17)
        T(XR + 20, 16.0, "NR. REV.", 1.6, maxw=13); T(XR + 26.5, 23.0, str(k.get("rev", "")), 3.4, True, al="middle", maxw=13)
        cell(XR + 1, 25, 6, "SCARA:", 1.8); cell(XR + 15, 25, 6, k.get("scara", ""), 1.9, maxw=W - XR - 16)
        cell(XR + 1, 31, 6, "FORMAT:", 1.8); cell(XR + 15, 31, 6, "ISO " + self.m.get("format", "A3"), 1.9)
        cell(XR + 1, 37, 6, "DATA:", 1.8); cell(XR + 11, 37, 6, k.get("data", ""), 1.9, maxw=W - XR - 12)
        T(XR + 1, 46.0, "NR. PROIECT:", 1.6); T(XR + 17, 49.8, k.get("nr_pr", ""), 2.1, True, al="middle", maxw=W - XR - 3)
        T(XR + 1, 54.0, "ȘTAMPILĂ ATESTAT", 1.5, maxw=W - XR - 2)
        T(W / 2, 66.6, k.get("footer", "Acest plan este proprietatea proiectantului de specialitate și nu poate fi reprodus, copiat sau transmis fără acord scris."),
          1.7, True, al="middle", maxw=W - 3)


def _bbox_items(items):
    bb = None
    for it in items:
        if isinstance(it, Text): b = text_bbox(it)
        elif isinstance(it, BlockRef): b = block_bbox(it, texts=True)
        else: b = prim_bbox(it)
        bb = bbox_union(bb, b)
    return bb


def _refs_compacte(ref):
    """„Q4, Q5, Q6, Q7” → „Q4…Q7” (notațiile aparatelor identice grupate pe aceeași poziție)"""
    import re
    parts = [x for x in (ref or "").split(", ") if x]
    if len(parts) < 3: return ", ".join(parts)
    out, run = [], []
    def flush():
        if len(run) >= 3: out.append(f"{run[0][2]}…{run[-1][2]}")
        else: out.extend(r[2] for r in run)
    for x in parts:
        m = re.match(r"^(.*?)(\d+)$", x)
        k = (m.group(1), int(m.group(2)), x) if m else (x, None, x)
        if run and m and run[-1][1] is not None and k[0] == run[-1][0] and k[1] == run[-1][1] + 1:
            run.append(k)
        else:
            flush(); run = [k]
    flush()
    return ", ".join(out)


def _wrap(s, n):
    words, out, cur = (s or "").split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n and cur: out.append(cur); cur = w
        else: cur = (cur + " " + w).strip()
    if cur: out.append(cur)
    return out or [""]


def _layout(model: dict) -> "Layout":
    L = Layout(model); L.build()
    # dacă schema a trebuit comprimată orizontal pe A3, se trece automat pe A2
    if getattr(L, "k_min", 1.0) < 0.85 and model.get("format", "A3") == "A3" and model.get("auto_format", True):
        model = dict(model, format="A2"); L = Layout(model); L.build()
    # nici pe A2 nu încape lizibil (ex. casă P+1 cu 20+ circuite) → A1
    if (L.meta.get("scara") or 1) < 0.6 and model.get("format") == "A2" and model.get("auto_format", True):
        model = dict(model, format="A1"); L = Layout(model); L.build()
    # pe A1 tot prea mic (scara < 0,8 → text sub ~1,7 mm): lista de echipamente iese de pe planșă, ca anexă (.xlsx)
    if model.get("format") == "A1" and model.get("auto_format", True) and model.get("lista_auto", True) \
            and (L.meta.get("scara") or 1) < 0.7:
        note = list(model.get("note") or []) + [f"{len(model.get('note') or []) + 1}. Lista de echipamente și materiale "
                                                 "se predă ca anexă la planșă (fișier .xlsx) — nu încape lizibil pe A1."]
        model = dict(model, lista_auto=False, legenda=False, note=note); L = Layout(model); L.build()
    # pe A2 / A1, o schemă lată și joasă (scara limitată de lățime) primește pas vertical mai mare, ca să ocupe și înălțimea
    if model.get("format") in ("A2", "A1"):
        vb = 1.0
        for _ in range(3):
            kx, ky = getattr(L, "kx_ky", (1, 1))
            if ky <= 1.12 * min(kx, 1.5) or vb >= 3.0: break
            vb = min(3.0, vb * (1 + (ky / min(kx, 1.5) - 1) * 0.9))
            L = Layout(model, v_boost=vb); L.build()
    return L


def build(model: dict) -> Canvas:
    return _layout(model).c


def build_cu_pozitii(model: dict):
    L = _layout(model); return L.c, L.poz
