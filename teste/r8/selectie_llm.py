"""Alege 20 de fraze greșite/parțiale din fiecare domeniu r8 (după verdict și severitate), FĂRĂ a citi „asteptat”."""
import json, pathlib
D = pathlib.Path(__file__).parent
ORD_SEV = {"P0": 0, "P1": 1, "P2": 2}


def selectie():
    out = {}
    for dom, rele, sev in (("fotovoltaic", ("greșit", "parțial"), "prioritate"), ("industrial", ("G", "P"), "severitate"),
                           ("locuinte", ("greșit", "parțial"), "severitate")):
        F = json.loads((D / dom / "fraze.json").read_text(encoding="utf-8"))
        c = [f for f in F if f.get("verdict") in rele]
        c.sort(key=lambda f: (rele.index(f["verdict"]), ORD_SEV.get(f.get(sev), 3), f["id"]))
        out[dom] = [{"id": f["id"], "text": f["text"]} for f in c[:20]]
    return out


if __name__ == "__main__":
    s = selectie()
    for dom, L in s.items():
        print("=" * 30, dom)
        for f in L:
            print(f"[{dom[:3]}-{f['id']}] {f['text']}\n")
