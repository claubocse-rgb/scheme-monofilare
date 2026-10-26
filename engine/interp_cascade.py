"""r9: cascadele de tablouri în toate formele (rescriere ÎNAINTE de reguli; lungimea nu se păstrează, notele spun ce
s-a rescris). Forma-țintă e cea pe care lista de plecări o citește deja: „TG … plecari: TD1 (copii, TE1 (copii))”.

  * lanț de săgeți: „TG (din PT 800 kVA, TN-S) → TD1 hală (motoare 3 x 11 kW) → TE1 linie (2 benzi 2,2 kW)” — fiecare
    tablou e alimentat din cel dinainte (TE1 sub TD1, nu sub TG);
  * indentare pe rânduri: „TG⏎  - TD-A⏎     - pompă 5,5 kW⏎  - TD-B⏎     - iluminat 6 kW” — copiii = rândurile mai
    adânc indentate;
  * „Din TG pleacă …” când TG e chiar tabloul descris (nu a doua sursă) și „X alimentează la rândul lui …”.
"""
from __future__ import annotations

import re

_COD = r"(?:T[DGE][A-Z]*(?:[-\s]?[A-Za-z0-9]+)?|TGD|tablou\w*(?:\s+general)?)"
RE_SAG = re.compile(r"\s*(?:->|→|=>)\s*")
RE_COD_START = re.compile(r"\s*(?:T[DGE]\w*|TGD|TS|TDSI)\b", re.I)


def _split_top(t: str):
    """segmentele dintre săgețile de nivel 0 (în afara parantezelor)"""
    out, d, poz = [], 0, 0
    i = 0
    while i < len(t):
        ch = t[i]
        if ch == "(":
            d += 1
        elif ch == ")":
            d = max(0, d - 1)
        elif d == 0:
            m = RE_SAG.match(t, i)
            if m and m.group(0).strip():
                out.append(t[poz:i])
                poz = m.end()
                i = m.end()
                continue
        i += 1
    out.append(t[poz:])
    return out


def rescrie_lant(text: str) -> tuple[str, list[str]]:
    """„TG (sursa) → TD1 (…) → TE1 (…)” → „TG sursa, plecari: TD1 (…, TE1 (…))”."""
    # lanțul ocupă o propoziție (până la „.” / „;” / rând nou)
    out, note = [], []
    for prop in re.split(r"((?<!\d)\.(?!\d)\s*|;\s*|\n)", text):
        seg = _split_top(prop)
        if len(seg) < 3 or not all(RE_COD_START.match(s) for s in seg[1:]) or not re.match(r"\s*(?:TG\w*|TGD|[Tt]ablou)", seg[0]):
            out.append(prop)
            continue
        interior = seg[-1].strip()
        for s in reversed(seg[1:-1]):
            s = s.strip()
            if s.endswith(")"):
                interior = s[:-1].rstrip() + ", " + interior + ")"
            else:
                interior = s + " (" + interior + ")"
        rad = seg[0].strip()
        m = re.match(r"(?P<cod>.+?)\s*\((?P<sursa>[^()]*)\)\s*$", rad)
        if m and re.search(r"\bdin\b|\bPT\b|\bTN|\bTT\b|kVA", m.group("sursa"), re.I):
            rad = f"{m.group('cod')} {m.group('sursa')}"
        out.append(f"{rad}, plecari: {interior}")
        note.append("lanțul „" + " → ".join(re.match(r"\s*(\S+)", s).group(1) for s in seg) + "” = cascadă (fiecare tablou "
                    "alimentat din cel dinainte)")
    return ("".join(out), note) if note else (text, [])


RE_RAND_IND = re.compile(r"^(?P<ind>[ \t]*)(?:[-*•·–—]\s+)?(?P<txt>\S.*?)\s*$")


def rescrie_indentare(text: str) -> tuple[str, list[str]]:
    """Arborele din indentare → paranteze imbricate (doar dacă există cel puțin 3 niveluri de indentare sau un rând
    indentat sub un rând indentat cu cod de tablou)."""
    if "\n" not in text:
        return text, []
    linii = text.split("\n")
    rand = []
    for ln in linii:
        if not ln.strip():
            continue
        m = RE_RAND_IND.match(ln)
        rand.append((len(m.group("ind").expandtabs(4)), m.group("txt"), bool(re.match(r"\s*[-*•·–—]\s", ln))))
    niveluri = sorted({r[0] for r in rand})
    if len(niveluri) < 3 or not any(r[2] for r in rand):
        return text, []
    # arborele: rândurile cu indentare > 0 sunt copiii celui mai apropiat rând de deasupra cu indentare mai mică
    radacini, stiva = [], []
    for ind, txt, _ in rand:
        nod = {"txt": txt, "copii": [], "ind": ind}
        while stiva and stiva[-1]["ind"] >= ind:
            stiva.pop()
        (stiva[-1]["copii"] if stiva else radacini).append(nod)
        stiva.append(nod)

    def scrie(n):
        if not n["copii"]:
            return n["txt"]
        return f"{n['txt']} (" + ", ".join(scrie(k) for k in n["copii"]) + ")"

    parti = []
    for r in radacini:
        if r["copii"] and re.match(r"(?:TG\w*|TGD|[Tt]ablou\w*)\b", r["txt"]):
            parti.append(f"{r['txt']} plecari: " + ", ".join(scrie(k) for k in r["copii"]))
        else:
            parti.append(scrie(r))
    return ". ".join(p.rstrip(" .;") for p in parti), ["indentarea rândurilor = cascadă (rândurile mai adânci sunt "
                                                         "alimentate din tabloul de deasupra)"]


# „Din TG pleacă TD-A 80 kW și TD-B …” când TG e tabloul descris (prima mențiune, fără valoare) → „TG plecari: …”
RE_DIN_TG = re.compile(r"(?:^|(?<=[.;]\s)|(?<=[.;]))\s*(?:[Dd]in|DIN)\s+(?P<cod>TG\w*|TGD|[Tt]ablou(?:l)?(?:\s+general)?)\s+"
                       r"(?:pleac[aă]|se\s+alimenteaz[aă]|sunt\s+alimentate|porne[sș]te)\s*:?\s*")
RE_RANDUL = re.compile(r"\s+la\s+r[aâ]ndul\s+(?:lui|ei|s[aă]u|lor)\b", re.I)


def rescrie_din_tg(text: str) -> tuple[str, list[str]]:
    note = []
    t = RE_RANDUL.sub("", text)
    if t != text:
        note.append("„la rândul lui” = cascadă")
    m = RE_DIN_TG.search(t)
    if m:
        cod = m.group("cod")
        prima = re.search(rf"(?<![\w-]){re.escape(cod.split()[0])}(?![\w-])", t)
        if prima and prima.start() < m.start() and not re.match(r"\s*\d", t[prima.end():prima.end() + 3]):
            t = t[:m.start()] + (" " if m.start() else "") + "plecari: " + t[m.end():]
            note.append(f"„{m.group(0).strip()}” = plecările tabloului descris ({cod}), nu o a doua sursă")
    return (t, note) if t != text else (text, [])
