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
import math
import re
from .canvas import *
from . import symbols as S
from . import desen_e2  # noqa: F401  (E2: straturile noi — conductoare colorate, tablou, curbe)

FORMATS = {"A3": (420.0, 297.0), "A2": (594.0, 420.0), "A1": (841.0, 594.0), "A4": (297.0, 210.0)}
GAP = 4.0
CABLE_SEG = 22.0          # lungimea segmentului de cablu (cu marcaj) între cutie și primul aparat
BOX_H = 12.0
LAT_W = {"contor": 28, "cleme": 12, "cutie": 28, "fuzibil": 8}
LEFT_EXT = {"string_pv": 11, "invertor": 9, "convertor_bess": 9, "trafo": 6, "contor_direct": 9, "sep_mt": 13, "generator": 7, "motor": 7,
            "sep_fuzibil": 2.5, "mcb": 2.5, "mccb": 2.5, "rccb": 3.5, "mccb_dif": 3.5, "rcbo": 3.5, "acb": 2.5, "separator": 2.5,
            "separator_cc": 2.5, "intreruptor_mt": 2.5, "fuzibil": 2.5, "gpv": 2.5, "contact": 2.5, "sigurante_mt": 2.5,
            "releu_termic": 3.5, "convertizor": 9, "pornitor_yd": 8, "ups": 7}
POZ_DX = {"tc": 9.0}
BN_DX = 34.0              # distanța baretei de nul / traseului PE față de coloană
CH = 1.45                 # lățime medie caracter (mm) la 2,1 mm înălțime text
SURSE_TIP = {"string_pv", "invertor", "convertor_bess", "baterie", "generator"}
SPD_TIP = {"spd", "spd_cc", "descarcator_mt"}
BD_TIP = {"mccb", "mcb", "mccb_dif", "rccb", "rcbo", "acb", "intreruptor_mt"}
SUB_HEAD = 10.0           # capul carcasei unui tablou secundar (titlu + spațiu până la bară)
GRUP_GAP = 6.0          # bara scurtă a unei grupe (DDR → circuite) în același tablou
SEG_MAX = 50.0
RAND_MAX_PLECARI = 16     # r8 (p38): peste atâtea plecări simple pe bară, plecările se desenează pe mai multe rânduri
RAND_GAP = 16.0           # spațiul dintre caseta plecărilor unui rând și carcasa rândului următor


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


def _titlu_cutie(l):
    """r13: titlul casetei laterale care conține deja simbolul ei („PE”, „SB”, „BAT”, „FB · c.c.”) — eticheta separată
    deasupra casetei ar fi dublată (și se încalecă cu derivațiile / SPD-urile din rândul de sus). Întoarce titlul cu
    simbolul complet („SB1”, „FB1 · c.c.”) sau None când simbolul nu se regăsește în titlu (eticheta rămâne separată)."""
    ref, et = (l.get("ref") or "").strip(), (l.get("eticheta") or "").strip()
    if not ref or not et: return None
    tok = et.split(" ")[0]
    if tok == ref: return et
    if re.sub(r"[\d.\-]+$", "", ref) == tok:          # SB1 / SB, BAT2 / BAT, FB1 / FB · c.c.
        nou = ref + et[len(tok):]
        if text_width(nou, 2.6, True) <= (l.get("w") or LAT_W["cutie"]) - 2:
            return nou
    return None


def _fara_sursa(b):
    """r13 (feedback hibrid): intrarea începe direct cu câmpul PV desenat ca aparat (`string_pv`) — caseta-sursă
    „CÂMP PV / invertor …” de deasupra ar dubla componentele deja desenate (PV, INV) și nu se mai desenează; coloana
    începe cu simbolul PV, iar cablul c.c. (H1Z2Z2-K) se marchează între PV și aparatul următor."""
    ap = b.get("aparate") or []
    return (not isinstance(b.get("ramificatie"), dict)) and bool(ap) and ap[0].get("tip") == "string_pv"


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
        self._comp = {}
        self.meta = {"carcase": [], "obiecte": [], "legaturi": [], "poz": [], "scara": 1.0}
        self._cabluri = []      # etichete de cablu amânate până se cunosc carcasele
        self._titluri = []      # E2: titlurile carcaselor (texte, x1, x2, y_sus) — repoziționate la „racord sus”
        self.H_REV = 0.0        # E2: înălțimea tabelului de revizii de deasupra cartușului

    # ------------------------------------------------------------ public
    def build(self) -> Canvas:
        c = self.c
        c.rect(5, 5, self.w - 10, self.h - 10, "TABEL")
        c.rect(10, 10, self.w - 20, self.h - 20, "CHENAR")
        self._calc_note()
        self.H_REV = _h_revizii(self.m)
        i0 = len(c.items)
        sp = self.m.get("desen_special")
        if isinstance(sp, dict) and sp.get("tip"):
            # E2: planșe desenate direct (stringuri IE 07, TE de interfață multifilar IE 09, curbe timp-curent, ușa tabloului)
            from . import desen_e2
            self.x_right = (self.w - 10 - 164) if (self.m.get("lista_auto", True) or self.m.get("legenda", True)) else self.w - 24
            self.kx_ky = (1.0, 1.0)
            desen_e2.deseneaza(self, sp)
        else:
            self._schema()
            self._muta_ref_laterale(i0)
            self._scaleaza(i0, marire=self.m.get("format", "A3") in ("A2", "A1"))
            if racord_sus(self.m):
                self._rastoarna(i0)
        self.meta["schema_bbox"] = _bbox_items(c.items[i0:])
        self.meta["zona_schema"] = (15.0, (self.note_top + 6 if self.m.get("note") else 15.0), self.x_right - 2, self.h - 15)
        for mat in self.m.get("materiale") or []:      # cabluri, conductoare PE (U.M. m) — SPEC §E.1 pct. 5
            q = mat.get("cantitate", "")
            if isinstance(q, float):
                q = int(q) if q == int(q) else str(round(q, 2)).replace(".", ",")
            self.poz.append((len(self.poz) + 1, mat.get("ref", ""), mat.get("lista", []), f"{q} {mat.get('um', '')}".strip(), "material"))
        if self.m.get("lista_auto", True): self._tabel()
        if self.m.get("legenda", True): self._legenda()
        self._tabel_pi()
        self._note()
        if self.m.get("cartus_mini"):
            self._cartus_mini()
        else:
            self._cartus()
        if not self.m.get("blocaj"):
            # r9 (industrial #14, S12): ștampila apare pe ORICE planșă cu BLOCANT — și pe cele găsite doar la verificarea
            # desenului (V57 / V82 / V83, topologia), nu numai pe blocajele de calcul puse de constructor
            try:
                from . import topologie
                c.meta = self.meta
                bl = [v for v in topologie.verifica_topologie(self.m, c) if v.get("nivel") == "BLOCANT"]
            except Exception:      # noqa: BLE001 — verificarea nu oprește desenul
                bl = []
            if bl:
                cod = []
                for v in bl:
                    t_ = f"{v['cod']} ({v.get('obiect', '')})"
                    if t_ not in cod:
                        cod.append(t_)
                self.m = dict(self.m, blocaj="NEVERIFICAT — CALCUL BLOCAT: " + ", ".join(cod[:5])
                              + (f" și încă {len(cod) - 5}" if len(cod) > 5 else ""))
        if self.m.get("blocaj"):
            # r7 (S10): ștampila „NEVERIFICAT — CALCUL BLOCAT” (roșu), deasupra listei de echipamente
            t = self.m["blocaj"]
            hh = 2.6
            tw0 = text_width(t, hh, True)
            w = min(tw0 + 8, 150.0)
            hh = min(hh, hh * (w - 8) / max(tw0, 0.1))
            x0, y0 = self.w - 10 - 158, self.h - 18.4          # deasupra titlului listei, în afara zonei schemei
            if not self.m.get("lista_auto", True):
                y0 = 11 + 67.7 + self.H_REV + 1.5          # lista ca anexă: schema ocupă și dreapta sus — ștampila deasupra cartușului
            c.rect(x0, y0, w, 5.6, "COMANDA")
            c.text(x0 + w / 2, y0 + 1.8, t, hh, True, align="middle", layer="COMANDA")
            self.meta["blocaj"] = (x0, y0, x0 + w, y0 + 5.6)
        if self.m.get("filigran"):
            # E2: filigranul variantei gratuite — în banda dintre cele două rame, jos; nu e element al desenului
            # (nu intră în coliziuni / topologie), îl emit render_svg și render_dxf (strat „FILIGRAN”)
            self.meta["filigran"] = str(self.m["filigran"])
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
        if not plecare and _fara_sursa(br): box = {"titlu": "PV"}
        bw = max(28.0 if (plecare or br.get("compact")) else 40.0, max(text_width(box.get("titlu", ""), 3.0, True), text_width(box.get("sub", ""), 2.0)) + 5)
        for a in br.get("aparate_tablou") or []:        # r11: aparatele de la intrarea tabloului secundar (UPS)
            lw = max([text_width(a.get("ref", ""), 2.8, True)] + [text_width(s, 2.1) for s in a.get("spec", [])] + [0])
            left = max(left, 2 + LEFT_EXT.get(a.get("tip", ""), 4) + lw + 3.5)
            right = max(right, self._dreapta(a) + 1.0)
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
        n = len([a for a in br.get("aparate", []) or [] if not a.get("jos")])
        copii = br.get("copii") or []
        if not copii: return (n, 0.0)
        best = max((self._adancime(ch) for ch in copii), key=lambda t: t[0] * 20 + t[1])
        if br.get("grup"):          # grupă (ex. DDR + circuitele lui) în același tablou: doar o bară scurtă, fără cablu
            return (n + best[0], GRUP_GAP + best[1])
        return (n + len(br.get("aparate_tablou") or []) + best[0], self.seg_out + SUB_HEAD + best[1])

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
        # r8 (p38, 44 de circuite pe un rând = ilizibil): plecările simple (fără tablouri secundare / grupe) peste
        # RAND_MAX_PLECARI se împart pe rânduri; rândurile 2… stau sub primul, pe o continuare a barelor
        randuri = [plecari]
        if (len(plecari) > RAND_MAX_PLECARI and not has_bn and not isinstance(bara.get("cupla"), dict)
                and not m.get("jonctiune") and not any(b.get("copii") for b in plecari) and bara.get("afisare", True)):
            nr = math.ceil(len(plecari) / RAND_MAX_PLECARI)
            per = math.ceil(len(plecari) / nr)
            randuri = [plecari[i:i + per] for i in range(0, len(plecari), per)]
            plecari = randuri[0]
        self.randuri = randuri

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
        cup = bara.get("cupla") if isinstance(bara.get("cupla"), dict) else None
        sect = bara.get("sectiuni") if isinstance(bara.get("sectiuni"), list) and bara.get("sectiuni") else None
        self._sect = None
        if sect:
            # r12 (cascade CEF): N tablouri intermediare — fiecare cu intrările lui (invertoarele) deasupra unei bare
            # proprii și plecarea lui (o coloană) sub ea; tablourile stau unul lângă altul, fiecare în carcasa lui
            cup = None
            offs_i = [max(l, bw / 2 + 1) for (l, r, bw) in dims_in]
            ws_i = [off + max(r, bw / 2 + 1) for (l, r, bw), off in zip(dims_in, offs_i)]
            offs_o = [max(l, bw / 2 + 1) for (l, r, bw) in dims_out]
            ws_o = [off + max(r, bw / 2 + 1) for (l, r, bw), off in zip(dims_out, offs_o)]
            gap_s = 16.0
            grupe, i0_, o0_ = [], 0, 0
            for sc_ in sect:
                ni, no = int(sc_.get("n_in", 0)), int(sc_.get("n_out", 1))
                grupe.append((list(range(i0_, i0_ + ni)), list(range(o0_, o0_ + no))))
                i0_ += ni; o0_ += no
            lat = [max(sum(ws_i[i] for i in gi), sum(ws_o[o] for o in go)) for gi, go in grupe]
            tot = sum(lat) + gap_s * (len(lat) - 1)
            x0 = x_left + max(0.0, avail - tot) / 2
            xin, win = [0.0] * len(dims_in), [0.0] * len(dims_in)
            xout, wout = [0.0] * len(dims_out), [0.0] * len(dims_out)
            self._sect = []
            for (gi, go), L_, sc_ in zip(grupe, lat, sect):
                wi = sum(ws_i[i] for i in gi); xx = x0 + (L_ - wi) / 2
                for i in gi:
                    xin[i] = xx + offs_i[i]; win[i] = ws_i[i]; xx += ws_i[i]
                wo = sum(ws_o[o] for o in go)
                cx_in = (sum(xin[i] for i in gi) / len(gi)) if gi else x0 + L_ / 2
                xx = min(max(cx_in - wo / 2, x0), x0 + L_ - wo)
                for o in go:
                    xout[o] = xx + offs_o[o]; wout[o] = ws_o[o]; xx += ws_o[o]
                self._sect.append({"x1": x0 - 4, "x2": x0 + L_ + 4, "titlu": sc_.get("titlu", ""), "sub": sc_.get("sub", ""),
                                   "cols": [xin[i] for i in gi] + [xout[o] for o in go]})
                x0 += L_ + gap_s
        elif cup and dims_out:
            # r7 (PT 2 trafo): coloana fantomă a cuplei longitudinale între cele două secții de bare
            n1 = max(0, min(int(cup.get("n1", len(dims_out) // 2)), len(dims_out)))
            ap_cup = cup.get("aparate") or ([cup["aparat"]] if cup.get("aparat") else [])
            lq, rq, _ = self._col_dims({"aparate": ap_cup}, True) if ap_cup else (12.0, 12.0, 0)
            ph = (lq + 8.0, rq + 20.0, 0.0)
            xin, win = place(dims_in)
            xo, wo = place(dims_out[:n1] + [ph] + dims_out[n1:])
            self.x_cupla = xo[n1]
            xout, wout = xo[:n1] + xo[n1 + 1:], wo[:n1] + wo[n1 + 1:]
            self.n1_cupla = n1
            if cup.get("n1_in") is not None and dims_in:
                # r8 (CEF cu 2 trafo): grupurile de intrări (invertoarele fiecărei secții) de o parte și de alta a cuplei —
                # secția 1 la stânga, secția 2 la dreapta; plecările se deplasează ca bara să rămână centrată
                n1i = max(0, min(int(cup["n1_in"]), len(dims_in)))
                offs = [max(l, bw / 2 + 1) for (l, r, bw) in dims_in]
                ws_ = [off + max(r, bw / 2 + 1) for (l, r, bw), off in zip(dims_in, offs)]
                w1, w2 = sum(ws_[:n1i]), sum(ws_[n1i:])
                gap = max(lq + 8.0, 14.0)
                x0 = x_left + max(0.0, avail - (w1 + w2 + 2 * gap)) / 2
                dx = (x0 + w1 + gap) - self.x_cupla
                self.x_cupla += dx
                xout = [v + dx for v in xout]
                xin, win, xx = [], [], self.x_cupla - gap - w1
                for k_, (off, w_) in enumerate(zip(offs, ws_)):
                    if k_ == n1i:
                        xx = self.x_cupla + gap
                    xin.append(xx + off); win.append(w_); xx += w_
            elif len(xin) == 2:
                # intrarea 1 deasupra secției 1, intrarea 2 deasupra secției 2, cupla între ele
                (l0, r0, b0), (l1, r1, b1) = dims_in
                t0 = sum(xout[:n1]) / n1 if n1 else self.x_cupla - 30
                t1 = sum(xout[n1:]) / max(1, len(xout) - n1) if len(xout) > n1 else self.x_cupla + 30
                xin = [min(t0, self.x_cupla - max(r0, b0 / 2 + 1) - 4), max(t1, self.x_cupla + max(l1, b1 / 2 + 1) + 4)]
        elif not sect:
            cup = None
            xin, win = place(dims_in); xout, wout = place(dims_out)
        dims_rest = [[self._col_dims(b, True) for b in rd] for rd in randuri[1:]]
        self.k_min = min([1.0] + [avail / max(1e-6, sum(max(l, bw/2+1) + max(r, bw/2+1) for (l, r, bw) in d)) for d in [dims_in, dims_out] + dims_rest if d])
        if len(intrari) == 1 and len(plecari) == 1 and not show_bus:
            xc = (xin[0] + xout[0]) / 2; xin, xout = [xc], [xc]

        # --- verticală
        fara = [_fara_sursa(b) for b in intrari]
        parts = [_split_intrare(dict(b, aparate=(b.get("aparate") or [])[1:]) if f else b, bool(car)) for b, f in zip(intrari, fara)]
        # înălțimea antetului coloanelor de intrare: caseta sursei (BOX_H) sau simbolul câmpului PV (un rând de aparat)
        h_sus = max([BOX_H if not f else (S.M + GAP) * self.v_boost for f in fara] + [BOX_H])
        n_oi = max([len(o) for o, _ in parts] + [0])
        n_ii = max([len(i) for _, i in parts] + [0])
        gap_in = (CABLE_SEG + 8) if n_oi else 0.0
        deps = [self._adancime(b) for b in plecari]
        a_out, b_out = max(deps, key=lambda t: t[0] * 20 + t[1]) if deps else (0, 0.0)
        if show_bus and n_lat_bus and plecari:          # descărcătorul de pe bară coboară ~24 mm: carcasa trebuie să-l cuprindă
            b_out = max(b_out, 26.0 - a_out * (S.M + GAP) * self.v_boost)
        y_top = self.h - 20
        y_bot = (self.note_top + 2 if m.get("note") else 36.0) + (14 if has_bn else 0)
        fixed = h_sus + CABLE_SEG + gap_in + 4 + b_out + ((self.seg_out + BOX_H) if plecari else 0)
        step = (S.M + GAP) * self.v_boost
        rows = n_oi + n_ii + a_out
        n_r = len(randuri) - 1
        if n_r:
            fixed += n_r * (b_out + self.seg_out + BOX_H + RAND_GAP + 10)
            rows += n_r * a_out
        if fixed + rows * step > (y_top - y_bot):
            step = max(S.M + 0.5, (y_top - y_bot - fixed) / max(rows, 1))
        self.step = step
        y_bus = y_top - h_sus - CABLE_SEG - n_oi * step - gap_in - n_ii * step - 4
        self.y_bus = y_bus
        y_in_top = y_bus + 4 + n_ii * step          # începutul părții din carcasă a intrărilor

        ext = [1e9, -1e9, 1e9, -1e9]   # xmin xmax ymin ymax ale zonei din carcasa principală
        def grow(x1, x2, y1, y2):
            ext[0] = min(ext[0], x1); ext[1] = max(ext[1], x2); ext[2] = min(ext[2], y1); ext[3] = max(ext[3], y2)

        # --- intrări (de sus în jos)
        y_out_bot = None
        ilk = {}
        for b, x, w, (dl, dr, _), (outs, ins), f_s in zip(intrari, xin, win, dims_in, parts, fara):
            ram = b.get("ramificatie") if isinstance(b.get("ramificatie"), dict) else None
            y = y_top - h_sus
            if f_s:
                # r13: fără caseta-sursă — câmpul PV este primul element al coloanei, apoi cablul c.c.
                a0 = b["aparate"][0]
                yc = y + S.HALF
                bb = self._aparat(x, yc, a0); c.line((x, yc - S.HALF), (x, y), "FORTA")
                self.meta["obiecte"].append({"tip": "sursa", "nume": a0.get("ref") or a0.get("tip"), "bbox": bb})
            if not ram:
                if not f_s: self._box(x, y + BOX_H, b.get("sursa", {}), w, "sursa")
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
            gol = bool(ram)
            for a in ins:
                if a.get("tip") == "gol":
                    y -= step
                    continue
                if gol:
                    # r7: ramificație din bara MT a postului (T2 din aceeași bară MT ca T1, nu sursă separată)
                    gol = False
                    xp = xin[int(ram.get("din", 0))]
                    xa_, xb_ = min(xp, x), max(xp, x)
                    c.line((xa_, y), (xb_, y), "FORTA"); c.line((xa_, y - 0.7), (xb_, y - 0.7), "FORTA")
                    c.dot((xp, y), 0.9); c.dot((x, y), 0.9)
                    if ram.get("eticheta"):
                        et = ram["eticheta"]
                        c.text((xa_ + xb_) / 2, y + 1.4, et, min(2.0, 2.0 * (xb_ - xa_ - 4) / max(_tw(et, 2.0), 0.1)),
                               align="middle", layer="TEXT_GRI")
                    grow(xa_, xb_, y - 1, y + 3)
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
            if self._sect:
                segs = []
                for k_, sc_ in enumerate(self._sect):
                    u1 = min(sc_["cols"]) - 8 if sc_["cols"] else sc_["x1"] + 4
                    u2 = max(sc_["cols"]) + 8 if sc_["cols"] else sc_["x2"] - 4
                    if k_ == 0:
                        u1 = min(u1, x1)
                    c.line((u1, y_bus), (u2, y_bus), "FORTA"); c.line((u1, y_bus - 0.7), (u2, y_bus - 0.7), "FORTA")
                    segs.append(((u1, y_bus), (u2, y_bus)))
                    sc_["bara"] = (u1, u2)
                self.bus_segs = segs
            elif cup and cup.get("fara_legatura"):
                # r11: două bare separate (două tablouri TGD-CF), fără cuplă între ele
                xc = self.x_cupla
                xa_, xb_ = xc - 4.0, xc + 4.0
                for (u1, u2) in ((x1, xa_), (xb_, x2)):
                    c.line((u1, y_bus), (u2, y_bus), "FORTA"); c.line((u1, y_bus - 0.7), (u2, y_bus - 0.7), "FORTA")
                self.bus_segs = [((x1, y_bus), (xa_, y_bus)), ((xb_, y_bus), (x2, y_bus))]
                c.line((xc, y_bus + 14), (xc, y_bus - 30), "CARCASA")
                for k_, t_ in enumerate(cup.get("etichete") or []):
                    c.text((x1 + xa_) / 2 if k_ == 0 else (xb_ + x2) / 2, y_bus - 3.2, t_, 1.9, align="middle", layer="TEXT_GRI")
                grow(xa_, xb_, y_bus - 2, y_bus)
            elif cup:
                # r7: două secții de bare + cupla longitudinală QC (în „U”, sub bare), stare NO / NI pe aparat
                xc = self.x_cupla
                xa_, xb_ = xc - 7.0, xc + 12.0
                for (u1, u2) in ((x1, xa_), (xb_, x2)):
                    c.line((u1, y_bus), (u2, y_bus), "FORTA"); c.line((u1, y_bus - 0.7), (u2, y_bus - 0.7), "FORTA")
                self.bus_segs = [((x1, y_bus), (xa_, y_bus)), ((xb_, y_bus), (x2, y_bus))]
                yc_q = y_bus - 3.0 - step / 2
                c.dot((xa_, y_bus), 0.9); c.dot((xb_, y_bus), 0.9)
                c.line((xa_, y_bus), (xa_, yc_q + S.HALF), "FORTA")
                ap_cup = cup.get("aparate") or ([cup["aparat"]] if cup.get("aparat") else [])
                for k_a, a_c in enumerate(ap_cup):
                    # r11: mai multe aparate în serie pe legătura dintre secții (QV → ATS·I la TG cu bară vitală)
                    if k_a:
                        c.line((xa_, yc_q - S.HALF), (xa_, yc_q - step + S.HALF), "FORTA")
                        yc_q -= step
                    self._aparat(xa_, yc_q, a_c)
                    if a_c.get("interblocaj"):
                        self._ilk_cupla = (xa_, yc_q, a_c["interblocaj"])
                y_u = yc_q - S.HALF - 3.0
                c.line((xa_, yc_q - S.HALF), (xa_, y_u), "FORTA"); c.line((xa_, y_u), (xb_, y_u), "FORTA")
                c.line((xb_, y_u), (xb_, y_bus), "FORTA")
                for k_, t_ in enumerate(cup.get("etichete") or []):
                    c.text((x1 + xa_) / 2 if k_ == 0 else (xb_ + x2) / 2, y_bus - 3.2, t_, 1.9, align="middle", layer="TEXT_GRI")
                grow(xa_ - 12, xb_ + 4, y_u - 2, y_bus)
            else:
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
                if a.get("jos"):
                    continue          # r12: aparatul de la capătul dinspre bara comună (QFk în TEG) — desenat la joncțiune
                yc = y - step / 2
                c.line((x, y), (x, yc + S.HALF), "FORTA"); self._aparat(x, yc, a); c.line((x, yc - S.HALF), (x, y - step), "FORTA")
                gx = (x - dl, x + self._dreapta(a), yc - S.HALF, yc + S.HALF)
                if sub_ext is None: grow(*gx)
                else: sub_ext.append(gx)
                y -= step
            copii = b.get("copii") or []
            sar = b.get("sarcina", {})
            if not copii and sar.get("jonctiune"):
                # r8: coloana se unește cu altele pe o bară comună (bara MT a PT-ului cu 2 trafo), desenată după plecări
                # r12: cu cablu (C-TEk) și aparate la capătul dinspre bara comună (`aparate_jos`, QFk în TEG)
                y_end = y0 - tinta[0] * step - tinta[1]
                c.line((x, y), (x, y_end), "FORTA")
                self._jonct.append((x, y_end))
                if any(a.get("jos") for a in b.get("aparate") or []) or (b.get("cablu") or {}).get("text"):
                    self._jonct_ext[x] = b
                return
            if not copii:
                y_end = y0 - tinta[0] * step - tinta[1]
                c.line((x, y), (x, y_end - self.seg_out), "FORTA")
                self._cabluri.append({"x": x, "hi": y_end, "lo": y_end - self.seg_out, "d": b.get("cablu"), "rot": True, "carcasa": parinte})
                # caseta e centrată pe axă: lățimea = de 2 ori distanța până la cea mai apropiată margine a slotului
                # (altfel o coloană cu text lung în stânga lărgește caseta peste vecina din dreapta — r5 f01/f12/f14/f22)
                l_, r_, bw_ = self._col_dims(b, True)
                sw = 2 * min(max(l_, bw_ / 2 + 1), max(r_, bw_ / 2 + 1))
                bb = self._box(x, y_end - self.seg_out, sar, min(w, sw + 3), "tablou")
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
            ext_ap = []
            for a in b.get("aparate_tablou") or []:
                # r11: aparatele de la intrarea tabloului secundar (UPS → Q ieșire), în carcasa lui, înaintea barei
                yc = y_sub - step / 2
                c.line((x, y_sub), (x, yc + S.HALF), "FORTA"); self._aparat(x, yc, a)
                c.line((x, yc - S.HALF), (x, y_sub - step), "FORTA")
                ext_ap.append((x - 2 - LEFT_EXT.get(a.get("tip", ""), 4) - 3.5 - max(
                    [text_width(a.get("ref", ""), 2.8, True)] + [text_width(s_, 2.1) for s_ in a.get("spec", [])] + [0]),
                    x + self._dreapta(a), yc - S.HALF, yc + S.HALF))
                y_sub -= step
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
            rest = (tinta[0] - len(b.get("aparate", [])) - len(b.get("aparate_tablou") or []), tinta[1] - self.seg_out - SUB_HEAD)
            nume = sar.get("titlu", "") or "TD"
            ext_td = [(bx1, bx2, y_sub - 1, y_sub)] + ext_ap
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
        self._jonct = []
        self._jonct_ext = {}
        for b, x, w, (dl, dr, _) in zip(plecari, xout, wout, dims_out):
            plecare(b, x, w, dl, y_bus, (a_out, b_out), 0, "principala" if car else None)
        if len(randuri) > 1 and show_bus:
            self._randuri_urmatoare(randuri, dims_rest, dims_out, xout, x1, y_bus, a_out, b_out, step, place, plecare, car)
        jn = m.get("jonctiune") if isinstance(m.get("jonctiune"), dict) else None
        if jn and self._jonct:
            # r8: bara comună sub coloanele marcate „jonctiune” (bara MT a PT-ului: celulele trafo T1, T2 → celula de
            # măsură QM și celula de linie QL comune) → cablu → caseta punctului de racord, în carcasa proprie
            xs_j = sorted(x_ for x_, _ in self._jonct)
            n_jos = max([len([a for a in b_.get("aparate") or [] if a.get("jos")]) for b_ in self._jonct_ext.values()] + [0])
            y_top_j = min(y_ for _, y_ in self._jonct)
            seg_j = self.seg_out if self._jonct_ext else 0.0
            yj = y_top_j - 20 - seg_j - n_jos * step
            ext_jos = []
            for x_, y_ in self._jonct:
                b_ = self._jonct_ext.get(x_)
                if not b_:
                    c.line((x_, y_), (x_, yj), "FORTA"); c.dot((x_, yj), 0.9)
                    continue
                # cablul plecării (C-TEk) până la carcasa barei comune, apoi aparatele de la capătul ei (QFk)
                y_c = yj + n_jos * step + 8
                c.line((x_, y_), (x_, y_c), "FORTA")
                self._cabluri.append({"x": x_, "hi": y_, "lo": y_c, "d": b_.get("cablu"), "rot": True, "carcasa": None})
                y = y_c
                c.line((x_, y), (x_, yj + n_jos * step), "FORTA")
                y = yj + n_jos * step
                for a in [a for a in b_.get("aparate") or [] if a.get("jos")]:
                    yc = y - step / 2
                    c.line((x_, y), (x_, yc + S.HALF), "FORTA"); self._aparat(x_, yc, a)
                    c.line((x_, yc - S.HALF), (x_, y - step), "FORTA")
                    ext_jos.append((x_ - 6 - LEFT_EXT.get(a.get("tip"), 4) - max(
                        [text_width(a.get("ref", ""), 2.8, True)] + [text_width(s_, 2.1) for s_ in a.get("spec", [])] + [0]),
                        x_ + self._dreapta(a), yc - S.HALF, yc + S.HALF + 2))
                    y -= step
                c.line((x_, y), (x_, yj), "FORTA"); c.dot((x_, yj), 0.9)
            bx1, bx2 = xs_j[0] - 6, xs_j[-1] + 6
            c.line((bx1, yj), (bx2, yj), "FORTA"); c.line((bx1, yj - 0.7), (bx2, yj - 0.7), "FORTA")
            if jn.get("eticheta"):
                c.text(xs_j[0] + 2, yj + 1.4, jn["eticheta"], min(2.0, 2.0 * ((xs_j[-1] - xs_j[0]) / 2 - 5)
                                                                   / max(_tw(jn["eticheta"], 2.0), 0.1)), layer="TEXT_GRI")
            xm = (xs_j[0] + xs_j[-1]) / 2
            c.dot((xm, yj), 0.9)
            y = yj
            ext_j = [(bx1, bx2, yj - 1, yj + 1)]
            for a in jn.get("aparate") or []:
                yc = y - step / 2
                c.line((xm, y), (xm, yc + S.HALF), "FORTA"); self._aparat(xm, yc, a); c.line((xm, yc - S.HALF), (xm, y - step), "FORTA")
                ext_j.append((xm - 6 - LEFT_EXT.get(a.get("tip"), 4), xm + self._dreapta(a), yc - S.HALF, yc + S.HALF))
                y -= step
            ext_j += ext_jos
            ex1 = min(e[0] for e in ext_j); ex2 = max(e[1] for e in ext_j); ey1 = min(e[2] for e in ext_j)
            jc = jn.get("carcasa") or {}
            if jc:
                nume_j = jc.get("titlu", "")
                cx1, cx2, cy1, cy2 = min(ex1 - 4, xs_j[0] - 8 - _tw(nume_j, 3.0)), ex2 + 4, ey1 - 4, \
                    yj + 11 + (n_jos * step + 2 if ext_jos else 0)
                tw_ = _tw(nume_j, 3.0) + 4 + _tw(jc.get("sub", ""), 2.1) + 8
                cx2 = max(cx2, cx1 + tw_)
                c.rect(cx1, cy1, cx2 - cx1, cy2 - cy1, "CARCASA")
                self._titlu_carcasa(cx1, cx2, cy2, nume_j, jc.get("sub", ""))
                self.meta["carcase"].append({"nume": nume_j, "bbox": (cx1, cy1, cx2, cy2), "parinte": None})
                self._carcase_y[nume_j] = (cy1, cy2)
                y_c = cy1
            else:
                nume_j, y_c = None, y
            if jn.get("copii"):
                # r12: după bara comună (TEG) — C0 → tabloul de racord (TGJT / TG existent) cu aparatele lui
                c.line((xm, y), (xm, y_c), "FORTA")
                bj = {"aparate": [], "cablu": jn.get("cablu"), "sarcina": jn.get("sarcina") or {}, "copii": jn["copii"],
                      "aparate_tablou": jn.get("aparate_tablou") or []}
                plecare(bj, xm, max(60.0, bx2 - bx1), 20.0, y_c, self._adancime(bj), 1, None)
            else:
                c.line((xm, y), (xm, y_c - self.seg_out), "FORTA")
                self._cabluri.append({"x": xm, "hi": y_c, "lo": y_c - self.seg_out, "d": jn.get("cablu"), "rot": True, "carcasa": None})
                self._box(xm, y_c - self.seg_out, jn.get("sarcina") or {}, max(40.0, bx2 - bx1), "tablou")
                self.box_bottom = min(self.box_bottom, y_c - self.seg_out - BOX_H)

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
            y2 = min(y2, (y_out_bot - 10) if y_out_bot is not None else y_top - h_sus - 10)
            self.y_carcasa_jos = y1
            if car and self._sect:
                # r12: câte o carcasă pe fiecare tablou intermediar (aceeași înălțime), cu titlul lui
                for k_, sc_ in enumerate(self._sect):
                    sx1 = min(sc_["x1"], x1) if k_ == 0 else sc_["x1"]
                    sx2 = sc_["x2"]
                    c.rect(sx1, y1, sx2 - sx1, y2 - y1, "CARCASA")
                    self._titlu_carcasa(sx1, sx2, y2, sc_["titlu"], sc_["sub"])
                    self.meta["carcase"].append({"nume": sc_["titlu"] or f"TE-{k_ + 1}", "bbox": (sx1, y1, sx2, y2),
                                                 "parinte": None, "principala": k_ == 0})
                self._carcase_y["principala"] = (y1, y2)
            elif car:
                c.rect(x1, y1, x2 - x1, y2 - y1, "CARCASA")
                self._titlu_carcasa(x1, x2, y2, car.get("titlu", ""), car.get("sub", ""))
                self.meta["carcase"].append({"nume": car.get("titlu", "") or "carcasă", "bbox": (x1, y1, x2, y2), "parinte": None, "principala": True})
                self._carcase_y["principala"] = (y1, y2)
        else:
            self.y_carcasa_jos = y_bus

        # --- r12: compartimentele celulelor MT (OD hașurat / utilizator), pe grupuri de aparate vecine
        for nume_c, bbs in self._comp.items():
            grupe_c = []
            for bb in sorted(bbs, key=lambda t: (round(t[0] / 40), -t[3])):
                for g in grupe_c:
                    if bb[0] < g[1] + 30 and bb[1] > g[0] - 30 and bb[2] < g[3] + 40 and bb[3] > g[2] - 40:
                        g[0], g[1], g[2], g[3] = min(g[0], bb[0]), max(g[1], bb[1]), min(g[2], bb[2]), max(g[3], bb[3])
                        break
                else:
                    grupe_c.append(list(bb))
            for (u1, u2, v1, v2) in grupe_c:
                u1 -= 4.0
                od = nume_c.startswith("COMPARTIMENT OD")
                c.rect(u1, v1, u2 - u1, v2 - v1, "COMPARTIMENT")
                # eticheta pe latura din stânga, citită de jos în sus, în interiorul chenarului
                h_t = min(1.8, 1.8 * (v2 - v1 - 2) / max(text_width(nume_c, 1.8, True), 0.1))
                c.text(u1 + 2.3, v1 + 1.0, nume_c, h_t, True, layer="TEXT_GRI", rot=90)
                if od:
                    # hașura OD: linii oblice pe latura din dreapta a chenarului
                    k_ = 0
                    yy = v2 - 0.5
                    while yy - 2.0 > v1 and k_ < 60:
                        c.line((u2 - 2.0, yy - 2.0), (u2, yy), "HASURA")
                        yy -= 1.6; k_ += 1
                self.meta["carcase"].append({"nume": nume_c, "bbox": (u1, v1, u2, v2), "parinte": None, "compartiment": True})

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

    def _randuri_urmatoare(self, randuri, dims_rest, dims_out, xout, x1, y_bus, a_out, b_out, step, place, plecare, car):
        """r8 (p38): rândurile 2… de plecări pe continuarea barelor (aceeași carcasă, desenată pe rânduri): conductor
        de legătură vertical în stânga, bară, plecări, carcasa rândului cu titlul „(continuare, rândul k)”."""
        c = self.c
        h_rand = a_out * step + b_out + self.seg_out + BOX_H
        xb0 = min([x1] + [x - d[0] for d, x in zip(dims_out, xout)]) - 4
        yb = y_bus
        for k_r, (rd, dims_r) in enumerate(zip(randuri[1:], dims_rest), 2):
            y_r = yb - h_rand - RAND_GAP - 10
            xr, wr = place(dims_r)
            xb0 = min([xb0] + [x - d[0] - 4 for d, x in zip(dims_r, xr)])
            x2r = max(xr) + 10
            c.line((xb0, y_r), (x2r, y_r), "FORTA"); c.line((xb0, y_r - 0.7), (x2r, y_r - 0.7), "FORTA")
            for x in xr: c.dot((x, y_r), 0.9)
            c.line((xb0, yb), (xb0, y_r), "FORTA"); c.dot((xb0, yb), 0.9); c.dot((xb0, y_r), 0.9)
            if yb == y_bus:
                c.line((xb0, y_bus), (x1, y_bus), "FORTA"); c.line((xb0, y_bus - 0.7), (x1, y_bus - 0.7), "FORTA")
            key = f"rand{k_r}"
            ext_r = [(xb0 - 2, x2r, y_r - 1, y_r + 4)]
            for b, x, w, (dl, dr, _) in zip(rd, xr, wr, dims_r):
                plecare(b, x, w, dl, y_r, (a_out, b_out), 0, key if car else None, ext_r)
            if car:
                rx1 = min(e[0] for e in ext_r) - 5; rx2 = max(e[1] for e in ext_r) + 6
                ry1 = min(e[2] for e in ext_r) - 7; ry2 = y_r + 8
                c.rect(rx1, ry1, rx2 - rx1, ry2 - ry1, "CARCASA")
                c.text(rx1 + 3, ry2 - 3.6, f"{car.get('titlu', '')} — continuarea barelor, rândul {k_r} de plecări", 2.4, True)
                self._carcase_y[key] = (ry1, ry2)
                self.meta["carcase"].append({"nume": f"{car.get('titlu', '')} (rândul {k_r})",
                                             "bbox": (rx1, ry1, rx2, ry2), "parinte": None, "continuare": True})
            yb = y_r

    def _titlu_carcasa(self, x1, x2, y2, titlu, sub):
        """titlul carcasei (înregistrat pentru orientarea „racord sus”: după răsturnare titlul revine sus)"""
        n0 = len(self.c.items)
        self._titlu_carcasa0(x1, x2, y2, titlu, sub)
        txt = [it for it in self.c.items[n0:] if isinstance(it, Text)]
        if txt:
            self._titluri.append((txt, x1, x2, y2))

    def _titlu_carcasa0(self, x1, x2, y2, titlu, sub):
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
        if self.m.get("cartus_mini"):
            Y1 = 20.0
        fits = bb[0] >= X1 and bb[2] <= X2 and bb[1] >= Y1 - 1 and bb[3] <= Y2 + 3
        kx, ky = (X2 - X1) / max(bb[2] - bb[0], 1), (Y2 - Y1) / max(bb[3] - bb[1], 1)
        self.kx_ky = (kx, ky)
        k = min(1.5 if marire else 1.0, kx, ky)
        if fits and k < 1.02: return
        if not fits and k >= 1.0 and not marire: k = 1.0
        ox = (X1 + X2) / 2 - k * (bb[0] + bb[2]) / 2
        oy = Y2 - k * bb[3]
        noi = [transform_item(it, k, ox, oy) for it in items]
        c.items[i0:] = noi
        self._tr = (k, ox, oy)
        # referințele păstrate la texte (etichete laterale, titluri de carcasă) trec pe obiectele transformate
        harta = {id(a_): b_ for a_, b_ in zip(items, noi)}
        for nume_l in ("_ref_lat", "_ref_contor"):
            if hasattr(self, nume_l):
                setattr(self, nume_l, [(harta.get(id(t), t), bb_) for t, bb_ in getattr(self, nume_l)])
        self._titluri = [([harta.get(id(t), t) for t in txt], x1 * k + ox, x2 * k + ox, y2 * k + oy)
                         for txt, x1, x2, y2 in self._titluri]
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
        sub = d.get("sub", "")
        if h2 < 1.8 and sub:
            # r6: subtitlul lung (ex. „SURSĂ NEDECLARATĂ — PRESUPUS …”) pe două rânduri, nu micșorat până la ilizibil
            cw = _tw("a", 2.0) * 1.15                    # lățimea medie a unui caracter (majuscule incluse)
            n = max(12, min(int(len(sub) / 2) + 6, int((w - 4) / max(cw, 1e-6))))
            rand = _wrap(sub, n)
            if len(rand) > 2:
                rand = [rand[0], " ".join(rand[1:])]
            h2 = min([2.0] + [2.0 * (w - 3) / max(_tw(r_, 2.0) * 1.12, 1) for r_ in rand])   # majuscule: +12 %
            c.text(x, y_top - 4.0, d.get("titlu", ""), h1, True, align="middle")
            c.text(x, y_top - 7.6, rand[0], h2, align="middle", layer="TEXT_GRI")
            if len(rand) > 1:
                c.text(x, y_top - 10.4, rand[1], h2, align="middle", layer="TEXT_GRI")
        else:
            c.text(x, y_top - 4.6, d.get("titlu", ""), h1, True, align="middle")
            c.text(x, y_top - 9.6, sub, h2, align="middle", layer="TEXT_GRI")
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
        if a.get("existent"):
            return "E"          # r10: aparat existent — marcat „E”, nu intră în lista de echipamente noi
        if a.get("generic"):
            return "G"          # echipa1 P1-10: aparat generic (tabloul consumatorului, conform proiect IU) — nu se cumpără aici
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
        if a.get("compartiment"):
            # r12: compartimentul OD / utilizator al celulelor MT (chenar punctat, OD hașurat), desenat la final
            lw_ = max([text_width(a.get("ref", ""), 2.8, True)] + [text_width(s_, 2.1) for s_ in a.get("spec", [])] + [0])
            hs = max(S.HALF + 1.0, getattr(self, "step", 12.0) / 2 - 0.4)
            self._comp.setdefault(a["compartiment"], []).append(
                (x - 2 - LEFT_EXT.get(tip, 4) - lw_ - 2, x + self._dreapta(a) + 4, yc - hs, yc + hs))
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
            w = (l.get("w") if t == "cutie" and l.get("w") else LAT_W.get(t, 20)); cx = lx + 8 + w / 2
            comanda = l.get("legatura") == "comanda"
            # v1.8: „pe” = conductor de echipotențializare (verde, fără săgeată); „grup” = aparatul face parte din cutia laterală
            # v1.9: „forta” = circuit de forță lateral (portul de baterie al invertorului hibrid), fără săgeată
            lay = "COMANDA" if comanda else {"pe": "PE", "grup": "CARCASA", "forta": "FORTA",
                                             "comunicatie": "RS485"}.get(l.get("legatura"), "MASURA")
            if lay == "RS485": self.are_rs485 = True
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
            tc = _titlu_cutie(l) if t == "cutie" else None
            self._place_lateral(cx, yc, dict(l, eticheta=tc) if tc else l)
            if l.get("ref") and not tc:
                if t == "contor":       # la dreapta casetei (deasupra ei poate fi o casetă laterală din rândul de sus, ex. PI)
                    c.text(cx + w / 2 + 1.5, yc + 2.5, l["ref"], 2.6, True)
                    if not hasattr(self, "_ref_contor"): self._ref_contor = []
                    self._ref_contor.append((c.items[-1], lb))
                else:
                    c.text(cx, yc + (9.0 if t == "cutie" else 4.0), l["ref"], 2.6, True, align="middle")
                    if t == "cutie":
                        # r9 (locuințe f31/f33): eticheta deasupra casetei poate cădea pe o derivație (bara c.c. a
                        # SPD-ului) — se mută la final, după ce tot desenul e cunoscut (_muta_ref_laterale)
                        if not hasattr(self, "_ref_lat"): self._ref_lat = []
                        self._ref_lat.append((c.items[-1], lb))
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

    def _muta_ref_laterale(self, i0):
        """r9: eticheta (ref) unei casete laterale tăiată de o linie a desenului (ex. „SB” peste bara c.c. a SPD-ului)
        se mută lângă casetă: stânga, dreapta sau dedesubt — primul loc liber."""
        from .canvas import text_bbox
        lst = getattr(self, "_ref_lat", [])
        if not lst: return
        segs = []
        for it in self.c.items[i0:]:
            if isinstance(it, (Line, Polyline)):
                segs += item_segments(it)
        for t, (x1, y1, x2, y2) in lst:
            def lovit():
                bb = text_bbox(t)
                bb = (bb[0] - 0.3, bb[1] - 0.3, bb[2] + 0.3, bb[3] + 0.3)
                return any(seg_hits_box(a, b, bb) for a, b in segs)
            if not lovit(): continue
            p0, al0 = t.p, t.align
            for p, al in (((x1 - 1.2, (y1 + y2) / 2 + 2.6), "right"), ((x2 + 1.2, (y1 + y2) / 2 + 2.6), "left"),
                          (((x1 + x2) / 2, y1 - 3.4), "middle")):
                t.p, t.align = p, al
                if not lovit(): break
            else:
                t.p, t.align = p0, al0

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
        y_lim = 11 + 67.7 + self.H_REV + (29 if self.m.get("legenda", True) else 4) + self._h_tabel_pi()
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
            ref = _refs_compacte(ref)
            def _fit(s_, h_, lat, bold=False):   # corpul de literă cu care textul încape în coloană (cu marjă)
                from .canvas import text_width
                return min(h_, h_ * lat / max(text_width(s_, h_, bold) * 1.1, 0.1))
            lat_ref = cols[2] - cols[1] - 2.5
            hr = _fit(ref, 2.1, lat_ref, True)
            ref_l = [ref]
            if hr < 1.6:
                # r9 (locuințe f42/f44/f45/f61): simboluri multe / nume lungi — rânduri de 1,6 mm (cel mult 3), restul „…”
                ref_l = _rupe_refs(ref, 1.6, lat_ref)
                if len(ref_l) > 3:
                    ref_l = ref_l[:2] + [ref_l[2].rstrip(",") + " …"]
            rh = 2.2 * fh / 1.9 + step * max(len(lines), len(ref_l) if len(ref_l) > 1 else 1)
            ym = y - rh / 2 - 0.7
            c.text(x0 + 4.5, ym, str(n), 2.1, align="middle")
            if len(ref_l) == 1:
                c.text(x0 + cols[1] + 1.5, ym, ref, hr, True)
            else:
                for i, s in enumerate(ref_l):
                    c.text(x0 + cols[1] + 1.5, y - step - step * i, s, _fit(s, 1.6, lat_ref, True), True)
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
        if getattr(self, "are_rs485", False):
            items.append(("RS485", "comunicație RS485"))
        dxc = 75 if len(items) <= 6 else 52
        for i, (lay, s) in enumerate(items):
            yy = y - 4.5 * (i % 3); xx = x0 + dxc * (i // 3)
            c.line((xx, yy + 0.8), (xx + 10, yy + 0.8), lay); c.text(xx + 12, yy, s, 2.1)
        yy = y - 13.5
        c.circle((x0 + 5, yy + 0.8), 2.0); c.text(x0 + 5, yy + 0.1, "n", 1.8, True, align="middle"); c.text(x0 + 12, yy, "poziție în lista de echipamente", 2.1)
        y -= 18
        abrev = self.m.get("abrevieri")
        if abrev:
            y -= 4; c.text(x0, y, "ABREVIERI", 2.8, True); y -= 4.5
            for s in abrev[:10]: c.text(x0, y, s, 2.0); y -= 3.6
        self.y_legenda_jos = y

    PI_RAND = 2.9

    def _tabele_dreapta(self):
        """r12: tabelele din coloana dreaptă — reglajele PI (3 coloane) și fișele (modul / invertor, 2 coloane)"""
        out = []
        tp = self.m.get("tabel_pi")
        if isinstance(tp, dict) and tp.get("randuri"):
            out.append(dict(tp, coloane=tp.get("coloane") or ["Funcția", "Valoare reglaj", "Temporizare"]))
        for t in self.m.get("tabele") or []:
            if isinstance(t, dict) and t.get("randuri"):
                out.append(t)
        return out

    def _h_tabel_pi(self):
        return sum(6.0 + 4.0 + self.PI_RAND * len(t["randuri"]) + (4.5 if t.get("sursa") else 1.5) + 2
                   for t in self._tabele_dreapta())

    def _tabel_pi(self):
        """r12 (Top 15 #7): tabelul „Parametri și protecții invertoare / PI” (funcție · reglaj · temporizare) și
        tabelele de fișă („Model panou solar”, „Model invertor”), în coloana din dreapta, sub legendă"""
        tabele = self._tabele_dreapta()
        if not tabele:
            return
        c = self.c
        x0, w = self.w - 10 - 158, 150.0
        if self.m.get("lista_auto", True) or self.m.get("legenda", True):
            y = getattr(self, "y_legenda_jos", getattr(self, "y_tabel_jos", self.h - 60) - 8) - 2
        else:
            y = self.h - 20
        h_tot = self._h_tabel_pi()
        jos = 11 + 67.7 + self.H_REV + 1
        k_r = 1.0
        if y - h_tot < jos:
            # nu încape sub legendă: rândurile se strâng (cel mult la 60 %), altfel tabelele urcă peste spațiul listei
            # (antetele și sursele nu se strâng — numai rândurile)
            h_rand = sum(self.PI_RAND * len(t["randuri"]) for t in tabele)
            h_fix = h_tot - h_rand
            k_r = max(0.6, min(1.0, (y - jos - h_fix) / max(h_rand, 1)))
            if y - (h_fix + k_r * h_rand) < jos:
                y = jos + h_fix + k_r * h_rand
        rand = self.PI_RAND * k_r
        fz = 1.9 * min(1.0, k_r * 1.1)
        for tp in tabele:
            ncol = len(tp["coloane"])
            cols = (0, 92, 124, w) if ncol == 3 else (0, 70, w)
            tit = tp.get("titlu", "")
            c.text(x0, y - 3, tit, min(2.6, 2.6 * w / max(text_width(tit, 2.6, True), 1)), True)
            y -= 6
            hdr = 4.0
            c.rect(x0, y - hdr, w, hdr, "TABEL", fill="#f3f3f3")
            for i_, t_ in enumerate(tp["coloane"]):
                c.text(x0 + cols[i_] + 1.5, y - 2.9, t_, 1.9, True)
            y -= hdr
            ytop = y
            for r_ in tp["randuri"]:
                for i_, t_ in enumerate(r_[:ncol]):
                    ca, cb_ = cols[i_], cols[i_ + 1]
                    h_ = min(fz, fz * (cb_ - ca - 3) / max(text_width(str(t_), fz), 0.1))
                    c.text(x0 + ca + 1.5, y - rand * 0.8, str(t_), h_)
                y -= rand
                c.line((x0, y), (x0 + w, y), "TABEL")
            c.rect(x0, y, w, ytop - y + hdr, "TABEL")
            for cx_ in cols[1:-1]:
                c.line((x0 + cx_, ytop + hdr), (x0 + cx_, y), "TABEL")
            if tp.get("sursa"):
                c.text(x0, y - 3.2, tp["sursa"], min(1.8, 1.8 * w / max(text_width(tp["sursa"], 1.8), 0.1)), layer="TEXT_GRI")
                y -= 4.5
            else:
                y -= 1.5
            y -= 2

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
        SIG = [45.0, 48.2, 51.3, 54.4, 57.5, 60.6, 63.7]        # r12: + rândul „Aprobat” (convenția proiectantului)
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
        if not k.get("atestat_tip") and k.get("atestat_necesar"):
            at = (at + " · " if at else "") + str(k["atestat_necesar"])      # echipa1 P1-5: atestatul cerut de lucrare
        cell(C1 + 1, 33, 5, at, 1.9, maxw=XR - C1 - 2)
        cell(1, 38, 7, "DENUMIRE PLAN:", 1.9)
        T(C1 + 1, 41.0, k.get("denumire1", ""), 2.0, True, maxw=XR - C1 - 2)
        T(C1 + 1, 44.3, k.get("denumire2", ""), 2.0, True, maxw=XR - C1 - 2)
        cell(1, SIG[0], 3.2, "Funcția", 1.5, True); cell(C1 + 1, SIG[0], 3.2, "Numele", 1.5, True)
        cell((CN + CS) / 2, SIG[0], 3.2, "Semnătura", 1.5, True, al="middle"); cell((CS + XR) / 2, SIG[0], 3.2, "Data", 1.5, True, al="middle")
        for y, lab, key in zip(SIG[1:], ("Șef proiect", "Proiectat", "Desenat", "Verificat", "Aprobat"),
                               ("sef_proiect", "proiectat", "desenat", "verificat", "aprobat")):
            cell(1, y, 3.1, lab, 1.7); cell(C1 + 1, y, 3.1, k.get(key, ""), 1.7, maxw=CN - C1 - 2)
        # dreapta
        for y in (13, 25, 31, 37, 43, 51): L(XR, y, W, y)
        L(XR + 19, 13, XR + 19, 25)
        T(XR + 1, 3.0, "FAZA:", 1.7); T(XR + 21, 11.4, k.get("faza", ""), 6.0, True, al="middle", maxw=W - XR - 10)
        T(XR + 1, 16.0, "PLANȘA NR.", 1.6, maxw=17); T(XR + 9.5, 23.0, k.get("plansa", ""), 3.4, True, al="middle", maxw=17)
        T(XR + 20, 16.0, "NR. REV.", 1.6, maxw=13); T(XR + 26.5, 23.0, rev_curenta(self.m), 3.4, True, al="middle", maxw=13)
        cell(XR + 1, 25, 6, "SCARA:", 1.8); cell(XR + 15, 25, 6, k.get("scara", ""), 1.9, maxw=W - XR - 16)
        cell(XR + 1, 31, 6, "FORMAT:", 1.8); cell(XR + 15, 31, 6, "ISO " + self.m.get("format", "A3"), 1.9)
        cell(XR + 1, 37, 6, "DATA:", 1.8); cell(XR + 11, 37, 6, k.get("data", ""), 1.9, maxw=W - XR - 12)
        T(XR + 1, 46.0, "NR. PROIECT:", 1.6); T(XR + 17, 49.8, k.get("nr_pr", ""), 2.1, True, al="middle", maxw=W - XR - 3)
        T(XR + 1, 54.0, "ȘTAMPILĂ ATESTAT", 1.5, maxw=W - XR - 2)
        T(W / 2, 66.6, k.get("footer", "Acest plan este proprietatea proiectantului de specialitate și nu poate fi reprodus, copiat sau transmis fără acord scris."),
          1.7, True, al="middle", maxw=W - 3)
        self._revizii(x0, y0 + H, W)

    def _cartus_mini(self):
        """E2 (#4): antetul paginii „schemă de tablou” de pe ușă — o bandă jos: tabloul, proiectul, revizia, data"""
        c = self.c; k = self.m.get("cartus", {}) or {}
        x0, y0, w = 10.0, 10.0, self.w - 20
        c.rect(x0, y0, w, 7.0, "CARTUS", fill="#fff")
        st = k.get("denumire1", "SCHEMĂ TABLOU")
        c.text(x0 + 2, y0 + 2.4, st, fit_h(st, 2.6, w * 0.45, True), True)
        dr = " · ".join(x for x in ((k.get("titlu") or k.get("denumire2") or ""), (k.get("beneficiar") or ""),
                                      (f"nr. pr. {k['nr_pr']}" if k.get("nr_pr") else ""), f"rev. {rev_curenta(self.m)}",
                                      (k.get("data") or ""), (k.get("proiectant") or "")) if x)
        c.text(x0 + w - 2, y0 + 2.4, dr, fit_h(dr, 1.9, w * 0.5), align="right")

    REV_RAND = 3.6
    REV_COL = ((0.0, "Rev."), (12.0, "Data"), (32.0, "Descriere"), (112.0, "Întocmit"), (135.0, "Verificat"))

    def _revizii(self, x0, y0, W):
        """E2 (#5): tabelul de revizii lipit deasupra cartușului — antetul jos, reviziile în sus (cea curentă sus);
        datele din `model.revizii[]` = [{rev, data, descriere, intocmit, verificat}]"""
        rv = revizii(self.m)
        if not rv:
            return
        c, rh = self.c, self.REV_RAND
        n = len(rv)
        H = rh * (n + 1)
        c.rect(x0, y0, W, H, "CARTUS", fill="#fff")
        c.rect(x0, y0, W, rh, "TABEL", fill="#f3f3f3")
        for i in range(1, n + 1):
            c.line((x0, y0 + rh * i), (x0 + W, y0 + rh * i), "TABEL")
        xs = [cx for cx, _ in self.REV_COL] + [W]
        for cx in xs[1:-1]:
            c.line((x0 + cx, y0), (x0 + cx, y0 + H), "TABEL")
        for (cx, t), cx2 in zip(self.REV_COL, xs[1:]):
            c.text(x0 + cx + 1.0, y0 + 1.0, t, min(1.7, 1.7 * (cx2 - cx - 2) / max(text_width(t, 1.7, True), 0.1)), True)
        chei = ("rev", "data", "descriere", "intocmit", "verificat")
        for j, r in enumerate(rv):
            yb = y0 + rh * (j + 1) + 1.0
            for (cx, _), cx2, k_ in zip(self.REV_COL, xs[1:], chei):
                t = str(r.get(k_) or "")
                if not t:
                    continue
                h = min(1.8, 1.8 * (cx2 - cx - 2) / max(text_width(t, 1.8, k_ == "rev"), 0.1))
                c.text(x0 + cx + 1.0, yb, t, h, k_ == "rev")
        self.meta["revizii_bbox"] = (x0, y0, x0 + W, y0 + H)

    # ------------------------------------------------------------ E2 (#3): orientarea „racord sus”
    def _rastoarna(self, i0):
        """oglindește vertical schema (elementele de la i0): racordul / rețeaua sus, invertoarele jos (convenția
        proiectantului la CEF și prosumator). Geometria se oglindește; textele NU — fiecare grup de rânduri (ref +
        spec, titlu + subtitlu) se mută în bloc pe poziția oglindită, cu ordinea rândurilor păstrată; textele rotite
        (de-a lungul cablurilor) își schimbă alinierea. Meta (carcase, obiecte, legături, poziții) se oglindește la fel."""
        c = self.c
        items = c.items[i0:]
        bb = _bbox_items(items)
        if bb is None:
            return
        A = bb[1] + bb[3]
        # nu se răstoarnă dacă partea lată a schemei (de obicei sursele) ar ajunge peste cartuș / tabelul de revizii
        cx1, cy2 = self.w - 11 - 158.0 - 2, 11 + 67.7 + self.H_REV + 2
        for it in items:
            b_ = (text_bbox(it) if isinstance(it, Text) else block_bbox(it, texts=True) if isinstance(it, BlockRef)
                  else prim_bbox(it))
            if b_ and b_[2] > cx1 and A - b_[3] < cy2:
                return
        top = []
        for it in items:
            if isinstance(it, Text):
                top.append(it)
            elif isinstance(it, BlockRef):
                pr = [_oglinda_geom(p, 0.0) for p in it.prims]
                _oglinda_texte([p for p in pr if isinstance(p, Text)], 0.0)
                it.prims = pr
                it.p = (it.p[0], A - it.p[1])
            else:
                _oglinda_geom(it, A, inplace=True)
        _oglinda_texte(top, A)
        F = lambda b: (b[0], A - b[3], b[2], A - b[1])
        P = lambda p: (p[0], A - p[1])
        for key in ("carcase", "obiecte"):
            for o in self.meta[key]:
                if o.get("bbox"): o["bbox"] = F(o["bbox"])
        for l in self.meta["legaturi"]:
            for f in ("de_xy", "spre_xy", "sageata"):
                if l.get(f): l[f] = P(l[f])
            for f in ("de_bbox", "spre_bbox"):
                if l.get(f): l[f] = F(l[f])
        self.meta["poz"] = [(P(p), r) for p, r in self.meta["poz"]]
        self.meta["orientare"] = "racord_sus"
        # etichetele casetelor laterale (P1, SM …) care, oglindite, ating alt text: primul loc liber lângă casetă
        tx = [(it, text_bbox(it)) for it in items if isinstance(it, Text)] + \
             [(p, text_bbox(p, it.p[0], it.p[1], it.scale)) for it in items if isinstance(it, BlockRef)
              for p in it.prims if isinstance(p, Text)]
        cerc = [(p[0] - r, p[1] - r, p[0] + r, p[1] + r) for p, r in self.meta["poz"]]
        k_, ox_, oy_ = getattr(self, "_tr", (1.0, 0.0, 0.0))
        for t, (x1, y1, x2, y2) in getattr(self, "_ref_lat", []) + getattr(self, "_ref_contor", []):
            x1, x2, y1, y2 = x1 * k_ + ox_, x2 * k_ + ox_, y1 * k_ + oy_, y2 * k_ + oy_
            y1, y2 = A - y2, A - y1
            def lovit():
                b0 = text_bbox(t)
                if any(bbox_overlap(b0, cb_, 0.2) for cb_ in cerc):
                    return True
                for o, ob in tx:
                    if o is t:
                        continue
                    if bbox_overlap(b0, ob, 0.2):
                        return True
                return False
            if not lovit():
                continue
            p0, al0 = t.p, t.align
            for p, al in (((x2 + 1.5, y2 - 3.2), "left"), ((x2 + 1.2, y2 + 0.8), "left"), ((x1 - 1.2, y2 + 0.8), "right"),
                          ((x2 + 1.2, (y1 + y2) / 2 - 1.0), "left"), (((x1 + x2) / 2, y1 - 3.4), "middle")):
                t.p, t.align = p, al
                if not lovit():
                    break
            else:
                t.p, t.align = p0, al0
        # titlurile carcaselor: după oglindire ar sta jos în carcasă — revin sus (în interior, altfel deasupra ei)
        for txt, x1, x2, _ in self._titluri:
            car = next((k for k in self.meta["carcase"] if abs(k["bbox"][0] - x1) < 0.05 and abs(k["bbox"][2] - x2) < 0.05), None)
            if car is None:
                continue
            cy1, cy2 = car["bbox"][1], car["bbox"][3]
            ty1 = min(text_bbox(t)[1] for t in txt)
            ids = {id(t) for t in txt}
            for t in txt:
                b = text_bbox(t)
                d = b[1] - cy1            # distanța de la marginea de jos (oglinda distanței față de marginea de sus)
                for dy in ((cy2 - d) - b[3] + (b[3] - b[1]) - (b[3] - b[1]),          # în interior, sus
                           (cy2 + 1.6 + (b[1] - ty1)) - b[1]):                      # deasupra carcasei
                    if self._liber([(t, dy)], ids, i0):
                        t.p = (t.p[0], t.p[1] + dy)
                        break

    def _liber(self, mut, ids, i0):
        """True dacă textele `mut` (text, dy) mutate nu ating nimic altceva din schemă"""
        bxs = []
        for t, dy in mut:
            b = text_bbox(t)
            bxs.append((b[0] - 0.4, b[1] + dy - 0.4, b[2] + 0.4, b[3] + dy + 0.4))
        for it in self.c.items[i0:]:
            if id(it) in ids:
                continue
            if isinstance(it, Text):
                o = text_bbox(it)
                if any(bbox_overlap(b, o) for b in bxs): return False
            elif isinstance(it, BlockRef):
                o = block_bbox(it, texts=True)
                if o and any(bbox_overlap(b, o) for b in bxs): return False
            elif isinstance(it, Circle):
                o = prim_bbox(it)
                if any(bbox_overlap(b, o) for b in bxs): return False
            elif getattr(it, "layer", "") != "CARCASA":
                for a, b2 in item_segments(it):
                    if any(seg_hits_box(a, b2, b) for b in bxs): return False
        return True


# ---------------------------------------------------------------- E2: revizii, orientare, straturi noi
TIPURI_RACORD_SUS = ("cef", "prosumator")


def fit_h(s, h, maxw, bold=False):
    return min(h, h * maxw / max(text_width(s or "", h, bold) * 1.04, 0.1))


def racord_sus(m):
    """E2 (#3): orientarea proiectantului — la CEF și prosumator racordul / rețeaua sus, invertoarele jos.
    `orientare: "clasic"` păstrează desenul vechi (sursele sus); `"racord_sus"` o impune la orice tip."""
    o = (m or {}).get("orientare")
    if o in ("clasic", "jos", False):
        return False
    if o in ("racord_sus", "sus", True):
        return True
    return ((m or {}).get("calc") or {}).get("tip_schema") in TIPURI_RACORD_SUS and bool(m.get("plansa_pachet"))


def revizii(m):
    """lista reviziilor (cel mult ultimele 5) din `model.revizii[]` (sau `cartus.revizii`), fără rândurile goale"""
    rv = (m or {}).get("revizii")
    if not isinstance(rv, list):
        rv = ((m or {}).get("cartus") or {}).get("revizii")
    out = [r for r in rv or [] if isinstance(r, dict) and any(str(r.get(k) or "").strip() for k in
                                                                 ("rev", "data", "descriere", "intocmit", "verificat"))]
    return out[-5:]


def _h_revizii(m):
    n = len(revizii(m))
    return Layout.REV_RAND * (n + 1) if n else 0.0


def rev_curenta(m):
    """numărul reviziei curente: ultima revizie din tabel (cu număr), altfel câmpul „rev” al cartușului"""
    for r in reversed(revizii(m)):
        if str(r.get("rev") or "").strip():
            return str(r["rev"]).strip()
    return str(((m or {}).get("cartus") or {}).get("rev", ""))


def _oglinda_geom(it, A, inplace=False):
    """oglindirea verticală y → A − y a unei primitive geometrice (textele se tratează separat)"""
    from dataclasses import replace
    F = lambda p: (p[0], A - p[1])
    if isinstance(it, Line): new = dict(a=F(it.a), b=F(it.b))
    elif isinstance(it, (Polyline, Solid)): new = dict(pts=[F(p) for p in it.pts])
    elif isinstance(it, Rect): new = dict(p=(it.p[0], A - it.p[1] - it.h))
    elif isinstance(it, (Circle, Ellipse)): new = dict(c=F(it.c))
    else: return it
    if inplace:
        for k, v in new.items(): setattr(it, k, v)
        return it
    return replace(it, **new)


def _oglinda_texte(texts, A):
    """mută textele pe poziția oglindită (y → A − y) fără să le oglindească: rândurile aceluiași grup (aceeași
    abscisă și aliniere, rânduri apropiate) se mută împreună, cu ordinea păstrată"""
    simple, rot = [], []
    for t in texts:
        r = (t.rot or 0.0) % 360
        if abs(r - 90) < 1 or abs(r - 270) < 1:
            rot.append(t)
        else:
            simple.append(t)
    for t in rot:
        t.p = (t.p[0], A - t.p[1])
        t.align = {"left": "right", "right": "left"}.get(t.align, t.align)
    grupe = {}
    for t in simple:
        grupe.setdefault((t.align, round(t.p[0], 1)), []).append(t)
    for lst in grupe.values():
        lst.sort(key=lambda t: -t.p[1])
        cl = [[lst[0]]]
        for t in lst[1:]:
            pr = cl[-1][-1]
            if pr.p[1] - t.p[1] <= 1.9 * max(pr.h, t.h) + 0.3:
                cl[-1].append(t)
            else:
                cl.append([t])
        for g in cl:
            bbs = [text_bbox(t) for t in g]
            dy = A - min(b[1] for b in bbs) - max(b[3] for b in bbs)
            for t in g:
                t.p = (t.p[0], t.p[1] + dy)


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


def _rupe_refs(ref, h, lat):
    """r9: lista de simboluri „Q2, Q5.1, Iluminat exterior, …” rupt pe rânduri care încap în coloana „Simbol” la
    înălțimea h (bold); un simbol singur prea lung e trunchiat cu „…”."""
    from .canvas import text_width
    def incape(s): return text_width(s, h, True) * 1.1 <= lat
    out, cur = [], ""
    for p in [x for x in (ref or "").split(", ") if x]:
        if not incape(p + ","):
            q = p
            while len(q) > 2 and not incape(q + "…,"): q = q[:-1]
            p = q + "…"
        cand = f"{cur}, {p}" if cur else p
        if cur and not incape(cand + ","):
            out.append(cur + ","); cur = p
        else:
            cur = cand
    if cur: out.append(cur)
    return out or [ref]


def _wrap(s, n):
    words, out, cur = (s or "").split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n and cur: out.append(cur); cur = w
        else: cur = (cur + " " + w).strip()
    if cur: out.append(cur)
    return out or [""]


def _casa_anexa(model):
    """echipa1 P1-3: planșa casei fără lista de echipamente și fără legendă (ambele predate ca anexă)"""
    n = len(model.get("note") or [])
    note = list(model.get("note") or []) + [
        f"{n + 1}. Lista de echipamente și materiale se predă ca anexă la planșă (fișier .xlsx).",
        f"{n + 2}. Simbolurile grafice conform SR EN 60617; legenda se predă cu lista de echipamente."]
    return dict(model, lista_auto=False, legenda=False, note=note)


def _layout(model: dict) -> "Layout":
    L = Layout(model); L.build()
    if (getattr(L, "k_min", 1.0) < 0.85 and model.get("format", "A3") == "A3" and model.get("auto_format", True)
            and (model.get("calc") or {}).get("tip_schema") == "locuinta" and model.get("lista_auto", True)):
        # echipa1 P1-3: tabloul unei case se predă pe A3 — lista de echipamente trece în anexă (.xlsx) dacă așa încape
        m3 = _casa_anexa(model)
        L3 = Layout(m3); L3.build()
        if getattr(L3, "k_min", 1.0) >= 0.8:
            return L3
    # dacă schema a trebuit comprimată orizontal pe A3, se trece automat pe A2
    if getattr(L, "k_min", 1.0) < 0.85 and model.get("format", "A3") == "A3" and model.get("auto_format", True):
        model = dict(model, format="A2"); L = Layout(model); L.build()
    # nici pe A2 nu încape lizibil (ex. casă P+1 cu 20+ circuite) → A1
    if ((L.meta.get("scara") or 1) < 0.6 and model.get("format") == "A2" and model.get("auto_format", True)
            and (model.get("calc") or {}).get("tip_schema") == "locuinta" and model.get("lista_auto", True)):
        # echipa1 P1-3: casa rămâne cel mult pe A2 — lista și legenda în anexă, dacă așa e lizibilă
        m2 = _casa_anexa(model)
        L2 = Layout(m2); L2.build()
        if (L2.meta.get("scara") or 1) >= 0.6:
            model, L = m2, L2
    if (L.meta.get("scara") or 1) < 0.6 and model.get("format") == "A2" and model.get("auto_format", True):
        model = dict(model, format="A1"); L = Layout(model); L.build()
    # pe A1 tot prea mic (scara < 0,8 → text sub ~1,7 mm): lista de echipamente iese de pe planșă, ca anexă (.xlsx)
    if model.get("format") == "A1" and model.get("auto_format", True) and model.get("lista_auto", True) \
            and (L.meta.get("scara") or 1) < 0.7:
        note = list(model.get("note") or []) + [f"{len(model.get('note') or []) + 1}. Lista de echipamente și materiale "
                                                 "se predă ca anexă la planșă (fișier .xlsx) — nu încape lizibil pe A1."]
        if model.get("tabel_pi"):
            # r12: tabelul de reglaje PI pleacă împreună cu lista (anexă / planșa IE 09.1 a pachetului)
            note.append(f"{len(note) + 1}. Tabelul „Parametri și protecții invertoare / PI” se predă ca anexă "
                        "(și pe planșa IE 09.1/FV a pachetului de planșe).")
        model = dict(model, lista_auto=False, legenda=False, note=note, tabel_pi=None); L = Layout(model); L.build()
    # pe A2 / A1, o schemă lată și joasă (scara limitată de lățime) primește pas vertical mai mare, ca să ocupe și înălțimea
    if model.get("format") in ("A2", "A1") or model.get("plansa_pachet") or model.get("cartus_mini"):
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
