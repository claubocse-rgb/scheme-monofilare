"""Puntea browser ↔ aplicație pentru versiunea web (Pyodide): rulează exact handler-ul HTTP din app.py,
fără server — cererea vine din JavaScript, răspunsul se întoarce ca (status, antete, corp)."""
import io, json, os, sys, zipfile

os.environ.setdefault("SM_DATE", "/data")
os.makedirs(os.environ["SM_DATE"], exist_ok=True)
sys.path.insert(0, "/app")
import app  # noqa: E402

FISIERE_DATE = ("preturi.json", "profile.json", "echipamente.json")


class WebH(app.H):
    def __init__(self, metoda, cale, corp):            # fără socket: nu se apelează constructorul HTTP
        self.command, self.path = metoda, cale
        self.headers = {"Content-Length": str(len(corp))}
        self.rfile = io.BytesIO(corp)
        self.raspuns = (404, {}, b"not found")

    def _send(self, code, body, ctype="application/json; charset=utf-8", fname=None, extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        h = {"Content-Type": ctype}
        h.update({k: str(v) for k, v in (extra or {}).items()})
        if fname:
            import urllib.parse
            h["Content-Disposition"] = f"attachment; filename*=UTF-8''{urllib.parse.quote(fname)}"
        self.raspuns = (code, h, body)


def cerere(metoda, cale, corp=b""):
    h = WebH(metoda, cale, bytes(corp))
    (h.do_GET if metoda == "GET" else h.do_POST)()
    st, hd, body = h.raspuns
    # DXF: browserul gazdă salvează doar anumite extensii → planșa DXF vine într-o arhivă .zip
    if cale == "/api/export/dxf" and st == 200:
        nume = hd.get("Content-Disposition", "").split("''")[-1] or "schema.dxf"
        import urllib.parse
        n = urllib.parse.unquote(nume)
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(n, body)
        body = bio.getvalue()
        hd["Content-Type"] = "application/zip"
        hd["Content-Disposition"] = "attachment; filename*=UTF-8''" + urllib.parse.quote(n[:-4] + "_DXF.zip")
    return st, hd, body


def date_citeste():
    """fișierele utilizatorului (catalog de prețuri, profile) → dict, ca să fie păstrate în browser"""
    out = {}
    for f in FISIERE_DATE:
        p = os.path.join(os.environ["SM_DATE"], f)
        if os.path.exists(p):
            out[f] = open(p, encoding="utf-8").read()
    return out


def date_scrie(d):
    for f, txt in (d or {}).items():
        if f in FISIERE_DATE and txt:
            with open(os.path.join(os.environ["SM_DATE"], f), "w", encoding="utf-8") as fh:
                fh.write(txt)
