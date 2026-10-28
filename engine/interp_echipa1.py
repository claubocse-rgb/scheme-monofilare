"""echipa1 (P1-6) — formulări uzuale pe care regulile le pierdeau; rescrise ÎNAINTE de reguli, cu notă.

* „iluminat birouri 3 circuite” (numărul DUPĂ nume) → „3 circuite iluminat birouri”;
* „4 pompe de 5,5 kW” / „3 motoare de 7,5 kW” → „4 x pompe 5,5 kW” (N receptoare identice, câte o plecare);
* „alimentare normală (din rețea) 80 kW” la GE + ATS = sursa normală a ATS-ului, NU un consumator → scoasă din lista
  consumatorilor, cu notă (puterea rămâne informativă).
"""
from __future__ import annotations

import re

NUM = r"\d+(?:[.,]\d+)?"
_GEN = r"(?:iluminat\w*|ilum\.?|priz\w*|circuite?\s+(?:de\s+)?(?:iluminat|priz\w*))"

RE_N_DUPA = re.compile(rf"(?<![\w.,])(?P<nume>{_GEN}(?:\s+(?!de\b|cu\b|si\b|și\b)[a-zăâîșțA-ZĂÂÎȘȚ]{{3,}}){{0,2}})\s+(?P<n>\d+)\s+circuite\b",
                       re.I)
RE_N_DE_P = re.compile(rf"(?<![\w.,×x])(?P<n>[2-9]|[1-9]\d)\s+(?P<ce>pomp\w*|motoar\w*|ventilat\w*|compresoar\w*|"
                       rf"unit[aă][tț]\w*|aparate?|statii|stații|încărc[aă]toare|incarcatoare|boilere|aeroterme)"
                       rf"(?P<cal>(?:\s+(?!de\b)[a-zăâîșț]+){{0,2}})\s+de\s+(?P<p>{NUM})\s*(?P<u>kw|cp)\b", re.I)
RE_ALIM_NORMALA = re.compile(rf"[,;]?\s*\b(?:alimentare\w*|sursa|sursă)\s+(?:normal\w*|de\s+baz\w*|principal\w*)"
                             rf"(?:\s+(?:din|de\s+la)\s+(?:re[tț]ea\w*|bmpt|tg|pt)\w*)?\s*(?::|=|de)?\s*(?P<p>{NUM})\s*(?P<u>kw)\b",
                             re.I)


def rescrie(text: str) -> tuple[str, list[str]]:
    note: list[str] = []
    t = text

    def n_dupa(m):
        note.append(f"„{m.group(0).strip()}” = {m.group('n')} circuite „{m.group('nume').strip()}”")
        return f"{m.group('n')} circuite {m.group('nume').strip()}"
    if not re.search(r"plec[aă]r\w*\s*:", t, re.I):      # cu „plecări:” regulile citesc deja „NUME N circuite”
        t = RE_N_DUPA.sub(n_dupa, t)

    def n_de_p(m):
        note.append(f"„{m.group(0).strip()}” = {m.group('n')} receptoare identice de {m.group('p')} {m.group('u')}, "
                    "câte o plecare")
        inainte = m.string[:m.start()]
        leg = "" if (not inainte.strip() or re.search(r"(?:\bcu|\bsi|\bși|\bplus|[:,;(])\s*$", inainte, re.I)) else "cu "
        return f"{leg}{m.group('n')} x {m.group('ce')}{m.group('cal')} {m.group('p')} {m.group('u')}"
    t = RE_N_DE_P.sub(n_de_p, t)

    if re.search(r"\bgrup\w*\s+electrogen\w*|\bge\b|\bats\b|\baar\b", t, re.I):
        def alim(m):
            note.append(f"„{m.group(0).strip(' ,;')}” = sursa normală (rețeaua) a ATS-ului — nu e un consumator al GE "
                        "(puterea rămâne informativă)")
            return ""
        t = RE_ALIM_NORMALA.sub(alim, t)
    return (t, note) if t != text else (text, [])
