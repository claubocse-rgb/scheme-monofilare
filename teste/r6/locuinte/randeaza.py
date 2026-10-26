import sys, json, pathlib
sys.path.insert(0, "/home/claude/sm"); sys.path.insert(0, "/home/claude/sm/teste/r5/locuinte"); sys.path.insert(0, "/home/claude/sm/teste/r6/locuinte")
from engine.interpretor import interpreteaza_local
from engine import constructor, layout, render_svg
from fraze_in import F
from fraze_noi import N
def cart_of(r):
    cart = {}; c = r.get("cartus") or {}
    if c.get("beneficiar"): cart["beneficiar"] = c["beneficiar"]
    adr = c.get("adresa")
    if isinstance(adr, dict) and adr.get("localitate"):
        cart["adresa"] = adr["localitate"] + (f", jud. {adr['judet']}" if adr.get("judet") else "")
    return cart
OUT = pathlib.Path("/home/claude/sm/teste/r6/locuinte/planse")
T = {i: t for i, t, _ in F + N}
for fid in sys.argv[1].split(","):
    r = interpreteaza_local(T[fid])
    if r["actiune"] == "refuza": print(fid, "refuz"); continue
    m, rez = constructor.genereaza(r["intrare_fizica"], cartus=cart_of(r))
    (OUT / f"{fid}.svg").write_text(render_svg.render(layout.build(m), fid), encoding="utf-8")
    print(fid, "ok", rez.get("blocheaza_export"))
