"""r8: rescrierea textului ÎNAINTE de regulile interpretorului (lungimea NU se păstrează — notele spun ce s-a rescris).

1. tabelele copiate → fraze pe rânduri (engine/interp_tabel.py);
2. engleză / mix ro-en → vocabularul român pe care îl citesc regulile („three-phase” → „trifazat”, „heat pump” →
   „pompă de căldură”, „main LV panel” → „TG”, „zero export” → „injecție zero”, „MV metering” → „măsură MT” …);
3. cascadele scrise în propoziții („TG alimentează TD-A 250A și TD-B 160A. Din TD-A pleacă TE-1 … TD-B are …”) →
   paranteze imbricate („TD-A 250A (TE-1 … ) și TD-B 160A ( … )”), pe care lista de plecări le citește ca sub-plecări;
4. autocorecturile („scuze, de fapt SG110CX”, „corectez: 15 kW”) → valoarea dinainte se scoate, ultima câștigă.
"""
from __future__ import annotations

import re

try:
    from .interp_tabel import rescrie_tabel
    from .interp_cifre import rescrie_cifre, rescrie_termeni, rescrie_lungimi, rescrie_marire
    from .interp_cascade import rescrie_lant, rescrie_indentare, rescrie_din_tg
except ImportError:  # rulare ca script
    from engine.interp_tabel import rescrie_tabel  # type: ignore
    from engine.interp_cifre import rescrie_cifre, rescrie_termeni, rescrie_lungimi, rescrie_marire  # type: ignore
    from engine.interp_cascade import rescrie_lant, rescrie_indentare, rescrie_din_tg  # type: ignore

_DIA = str.maketrans("șşțţăâîȘŞȚŢĂÂÎ", "ssttaaiSSTTAAI")
NUM = r"\d+(?:[.,]\d+)?"

# ------------------------------------------------------------------------------------------------------- engleză
# cuvinte care arată că mesajul (sau o parte) e în engleză
RE_EN = re.compile(r"\b(?:the|and|with|for|need|import|grid|house|home|apartment|flat|three[\s-]*phase|single[\s-]*phase|approved|loads?"
                   r"|supply|panel|board|switchboard|outgoing|feeders?|inverters?|battery|transformer|substation|lighting"
                   r"|sockets?|heat\s+pump|charger|hello|hi|thanks|please|existing|new|own|metering|export|rooftop|plant"
                   r"|warehouse|circuits|pumps?|fans?|motors?|dry\s+type|breaker|busbar|oven|hob|aircon|wallbox)\b", re.I)
# (regex, înlocuire) — ordinea contează (expresiile lungi întâi); se aplică pe textul original, fără a schimba restul
EN = [
    (r"\b(?:hello|hi|dear\s+\w+|thanks|thank\s+you|please|regards|best\s+regards)\b[,!.]?", ""),
    (r"\bI\s+need\s+(?:an?\s+)?|\bneed\s+(?:an?\s+)?|\bwe\s+need\s+(?:an?\s+)?", ""),
    (r"\bsingle[\s-]*line\s+diagram\b|\bSLD\b", "schema monofilara"),
    (r"\b(?:connection|connected|tie[\s-]*in)\s+to\s+(?:the\s+)?existing\s+main\s+(?:lv\s+)?(?:board|panel|switchboard)\b",
     "racord in TG existent"),
    (r"\b(?:new|existing)\s+(" + NUM + r"\s*kva)\s+([^,;]*?)\btransformer\b",
     lambda m: ("PT nou " if m.group(0).lower().startswith("new") else "PT existent ") + m.group(1) + " " + m.group(2)),
    (r"\bmain\s+(?:lv\s+)?(?:distribution\s+)?(?:panel|switchboard|board)\b|\bMSB\b|\bMDB\b", "TG"),
    (r"\bsub[\s-]*(?:panel|board|distribution\s+board)\b|\bdistribution\s+(?:panel|board)\b|\bDB\b", "TD"),
    (r"\bpanel\b|\bswitchboard\b|\bboard\b", "tablou"),
    (r"\boutgoings?(?:\s+feeders?)?\b|\bfeeders\b", "plecari"),
    # r9 (industrial #66): „fed from DNO cut-out 100A” = branșamentul (BMPT), nu o plecare
    (r"\b(?:dno|utility|supplier'?s?|network)\s+(?:service\s+)?cut[\s-]*out\b|\bservice\s+cut[\s-]*out\b", "BMPT"),
    (r"\bloads\b|\bconsumers\b", "consumatori"),
    (r"\bthree[\s-]*phase\b|\b3[\s-]*phase\b|\b3ph\b|\btri[\s-]*phase\b", "trifazat"),
    (r"\bsingle[\s-]*phase\b|\b1[\s-]*phase\b|\bmono[\s-]*phase\b|\b1ph\b", "monofazat"),
    (r"\b(?:approved|max(?:imum)?)\s+export(?:\s+(?:capacity|power))?\b|\bexport\s+capacity\b", "putere evacuata aprobata"),
    (r"\b(?:approved|max(?:imum)?)\s+import(?:\s+(?:capacity|power))?\b|\bimport\s+capacity\b", "putere absorbita aprobata"),
    (r"\bexisting\s+(?:main\s+)?(?:lv\s+)?(?:board|panel|switchboard)\b", "TG existent"),
    (r"\bapproved\s+power\b|\bcontracted\s+power\b", "putere aprobata"),
    (r"\bapproved\b|\bcontracted\b", "aprobat"),
    (r"\bheat\s+pumps?\b", "pompa de caldura"),
    (r"\binduction\s+(?:hob|cooktop|stove)\b", "plita inductie"),
    (r"\b(?:hob|cooktop|stove)\b", "plita"),
    (r"\boven\b", "cuptor"),
    (r"\b(?:ev|car)\s+chargers?\b|\bcharging\s+station\b|\bev\s+charging\b|\bev\s+charger\b", "statie de incarcare VE"),
    (r"\bair[\s-]+conditioners?\b|\bair[\s-]+conditioning\b|\ba/c\b|\baircon\w*\b", "aer conditionat"),
    (r"\blights\b|\blighting\b", "iluminat"),
    (r"\bsockets?\b|\boutlets?\b|\breceptacles?\b|\bpower\s+points?\b", "prize"),
    (r"\bwater\s+heater\b|\bhot\s+water\s+tank\b", "boiler"),
    (r"\bdishwasher\b", "masina de spalat vase"), (r"\bwashing\s+machine\b", "masina de spalat"),
    (r"\b(?:tumble\s+)?dryer\b", "uscator"), (r"\bfridge\b|\brefrigerator\b", "frigider"),
    (r"\bfire\s+pumps?\b", "pompa incendiu"), (r"\bjockey\s+pump\b", "pompa jockey"),
    (r"\bsmoke\s+(?:exhaust|extraction)\s+fans?\b", "ventilator desfumare"),
    (r"\bpumps\b", "pompe"), (r"\bpump\b", "pompa"), (r"\bfans\b", "ventilatoare"), (r"\bfan\b", "ventilator"),
    (r"\bmotors\b", "motoare"), (r"\bair\s+handling\s+units?\b|\bAHUs?\b", "CTA"),
    (r"\bno\s+batter(?:y|ies)\b|\bwithout\s+batter(?:y|ies)\b", "fara baterie"),
    (r"\binverters\b", "invertoare"), (r"\binverter\b", "invertor"),
    (r"\bbatter(?:y|ies)\b(?![\s-]*box)", "baterie"),
    (r"\btransformers\b", "transformatoare"), (r"\btransformer\b", "trafo"),
    (r"\bown\s+substation\b|\bprivate\s+substation\b", "PT propriu"),
    (r"\bsubstation\b", "post trafo"),
    (r"\b(?:supply|supplied|fed)\s+from\b", "alimentat din"), (r"\bsupply\b", "alimentare"),
    (r"\bdry[\s-]*type\b|\bcast[\s-]*resin\b", "uscat"), (r"\boil[\s-]*(?:immersed|filled|type)\b", "ulei"),
    (r"\b(?:zero|no)\s+(?:export|injection|feed[\s-]*in)\b", "injectie zero"),
    (r"\bexport\s+limit(?:ed|ation)?\s*(?:to|at|of)?\s*", "injectie limitata "),
    (r"\bmv\s+metering\b|\bmetering\s+(?:at|on)\s+(?:the\s+)?mv(?:\s+side)?\b|\bmv[\s-]+side\s+metering\b",
     "masura MT"),
    (r"\blv\s+metering\b|\bmetering\s+(?:at|on)\s+(?:the\s+)?lv(?:\s+side)?\b|\blv[\s-]+side\s+metering\b",
     "masura JT"),
    (r"\bmain\s+(?:circuit\s+)?breaker\b|\bincomer\b|\bmain\s+switch\b", "intrerupator general"),
    (r"\bat\s+(?:the\s+)?(?:busbar|bus)\b", "la bara"),
    (r"\bcables\b", "cabluri"), (r"\bcable\b", "cablu"),
    (r"\bcircuits\b", "circuite"),
    (r"\bwarehouse\b", "hala depozit"), (r"\bfactory\b", "fabrica"), (r"\boffice\b", "birou"),
    (r"\bhouse\b|\bhome\b|\bvilla\b", "casa"), (r"\bapartment\b|\bflat\b", "apartament"),
    (r"\bgarage\b", "garaj"), (r"\bfloor\b", "etaj"),
    (r"\b(?:earthing|grounding)(?:\s+system)?\b", "schema"),
    (r"(\d+(?:[.,]\d+)?\s*kva)\s+(?:diesel\s+)?(?:generator|gen[\s-]?set)\b", lambda m: "grup electrogen " + m.group(1)),
    (r"\bgenerator\b|\bgen[\s-]?set\b|\bdiesel\s+generator\b", "grup electrogen"),
    (r"\brooftop\b|\broof\b", "acoperis"), (r"\bcommercial\b", "comercial"), (r"\bresidential\b", "rezidential"),
    (r"\bPV\s+plant\b|\bsolar\s+plant\b|\bsolar\s+park\b", "CEF"),
    (r"\bexisting\b", "existent"), (r"\bnew\b", "nou"), (r"\bown\b", "propriu"),
    (r"\bmodules\b|\bpanels\b", "module"),
    (r"\beach\b", "fiecare"), (r"\bwith\b", "cu"), (r"\band\b", "si"), (r"\bfor\b", "pentru"), (r"\bfrom\b", "din"),
    (r"\bin\s+Romania\b", ""), (r"\bmy\b|\bour\b|\bthe\b|\ba\b(?=\s+[a-z])", ""),
    (r"\bsmall\b", "mic"), (r"\bonly\b", "doar"),
]
EN = [(re.compile(rx, re.I), rep) for rx, rep in EN]
# termeni englezești folosiți și în mesajele românești („heat pump”, „ev charger”, „zero export”) — se traduc mereu
EN_MEREU = {r"\bheat\s+pumps?\b", r"\b(?:ev|car)\s+chargers?\b|\bcharging\s+station\b|\bev\s+charging\b|\bev\s+charger\b",
            r"\bair[\s-]+conditioners?\b|\bair[\s-]+conditioning\b|\ba/c\b|\baircon\w*\b",
            r"\bsingle[\s-]*phase\b|\b1[\s-]*phase\b|\bmono[\s-]*phase\b|\b1ph\b",
            r"\bthree[\s-]*phase\b|\b3[\s-]*phase\b|\b3ph\b|\btri[\s-]*phase\b",
            r"\b(?:zero|no)\s+(?:export|injection|feed[\s-]*in)\b", r"\bexport\s+limit(?:ed|ation)?\s*(?:to|at|of)?\s*",
            r"\bmv\s+metering\b|\bmetering\s+(?:at|on)\s+(?:the\s+)?mv(?:\s+side)?\b|\bmv[\s-]+side\s+metering\b",
            r"\blv\s+metering\b|\bmetering\s+(?:at|on)\s+(?:the\s+)?lv(?:\s+side)?\b|\blv[\s-]+side\s+metering\b", r"\bno\s+batter(?:y|ies)\b|\bwithout\s+batter(?:y|ies)\b",
            r"\bdry[\s-]*type\b|\bcast[\s-]*resin\b"}


def rescrie_en(text: str) -> tuple[str, list[str]]:
    """Mesaj (parțial) în engleză → vocabular român. Cu ≥ 2 cuvinte englezești se traduce tot vocabularul; altfel
    doar termenii tehnici englezești uzuali și în mesajele românești („heat pump”, „ev charger”, „zero export”)."""
    gas = {m.group(0).lower() for m in RE_EN.finditer(text)}
    tot = len(gas) >= 2
    out = text
    for rx, rep in EN:
        if not tot and rx.pattern not in EN_MEREU:
            continue
        out = rx.sub(rep, out)
    if out == text:
        return text, []
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out, ["termenii în engleză au fost citiți ca vocabularul român echivalent"
                 + (" (mesaj în engleză)" if tot else "")]


# ------------------------------------------------------------------------------------------------------- cascade
_COD = r"(?:T[DGE][A-Z]*-?[A-Za-z0-9]+(?:-[A-Za-z0-9]+)?|T[DGE]\d*)"
RE_DIN_COD = re.compile(rf"(?:^|(?<=[.;]\s)|(?<=[.;]))\s*(?:[Dd]in|DIN)\s+(?P<cod>{_COD})\s+(?:pleac[aă]|se\s+alimenteaz[aă]|alimenteaz[aă]"
                        rf"|sunt\s+alimentate|porne[sș]te|are)\s*:?\s*(?P<lista>[^.;]+)[.;]?")
RE_COD_ARE = re.compile(rf"(?:^|(?<=[.;]\s)|(?<=[.;]))\s*(?P<cod>{_COD})\s+(?:are|alimenteaz[aă]|cuprinde|con[tț]ine|include)\s*:?\s*"
                        rf"(?P<lista>[^.;]+)[.;]?")
RE_TG_ALIM = re.compile(r"\b(?P<tg>TG\w*|TGD|[Tt]ablou\w*(?:\s+general)?)(?P<par>\s*\([^)]*\))?\s+alimenteaz[aă]\s+(?=T[DGE])")


def rescrie_cascade(text: str) -> tuple[str, list[str]]:
    """„Din TD-A pleacă TE-1 …” / „TD-B are …” → lista se mută în paranteză după prima apariție „TD-A <valoare>”."""
    note = []
    t = text
    m = RE_TG_ALIM.search(t)
    if m:
        t = t[:m.start()] + m.group("tg") + (m.group("par") or "") + " plecari: " + t[m.end():]
    for _ in range(6):
        gasit = False
        for rx in (RE_DIN_COD, RE_COD_ARE):
            for mm in rx.finditer(t):
                cod = mm.group("cod")
                # prima apariție a codului urmată de o valoare (calibru / putere), înaintea propoziției
                ma = re.search(rf"(?<![\w-]){re.escape(cod)}(?![\w-])\s*(?:{NUM}\s*(?:A|kW|kVA)\b)?", t[:mm.start()])
                if not ma or ma.group(0).strip() == cod and not re.search(r"\d", ma.group(0)):
                    continue
                lista = mm.group("lista").strip()
                ins = f"{ma.group(0)} ({lista})"
                t = t[:ma.start()] + ins + t[ma.end():mm.start()] + t[mm.end():]
                note.append(f"„{mm.group(0).strip(' .;')}” = sub-plecările lui {cod} (cascadă)")
                gasit = True
                break
            if gasit:
                break
        if not gasit:
            break
    return (t, note) if t != text else (text, [])


# ------------------------------------------------------------------------------------------------- autocorecturi
_RE_MARCATOR_CORECTURA = re.compile(
    r"(?:\.{2,}|…|[,;:!]|\s)\s*(?:"
    r"(?:(?:scuze|pardon|sorry|am\s+gresit|greseala|gresit)\s*[,!.:]*\s*)?"
    r"(?:de\s+fapt|corectez|corectie|corect\s+este|corect\s+e|(?:ba\s+)?nu\s*[,:]|adica\s+(?=\d))"
    r"|(?:scuze|pardon|sorry|am\s+gresit|greseala|gresit)\s*[,!.:]+(?:\s*(?:e|este)\b)?"
    r")\s*:?\s*", re.I)
_RE_SP_TOKEN = re.compile(r"\b(?:tn-?c-?s|tn-?s|tn-?c|tt|it)\b(?![\w-])", re.I)
_RE_RETEA_TOKEN = re.compile(r"\b(?:monofaz\w*|trifaz\w*|mono|tri)\b", re.I)
_RE_VAL_U = re.compile(rf"(?<![\w.,])({NUM})\s*(kwp|kwh|kva|kvar|kw|mw|mva|a|m|ohm)\b", re.I)


def _corectura(text: str, m) -> tuple[str, str] | None:
    """O singură autocorectură la marcatorul `m`; întoarce (text nou, notă) sau None (marcatorul nu e o corectură)."""
    n = _norm(text)
    marcator = n[m.start():m.end()]
    inainte, dupa = text[:m.start()], text[m.end():]
    # clauza veche: de la ultimul separator puternic (. ; sau început) — corectura nu sare peste propoziții
    s0 = max([x.end() for x in re.finditer(r"(?<!\d)\.(?!\d)(?!\.)\s|;|\n", inainte)] or [0])
    zona = inainte[s0:]
    mc = re.match(r"\s*(?P<nou>[^,;\n]+?)(?=\s*(?:[,;\n]|\.\s|\.$|\.{2,}|$))", dupa)
    if not mc:
        return None
    nou = mc.group("nou").strip()
    rest = dupa[mc.end():]
    nn = _norm(nou)
    slab = re.search(r"\badica\b|(?:^|\s)(?:e|este)\s*$", marcator.strip()) is not None and not re.search(
        r"scuze|pardon|sorry|gresit|greseala|de\s+fapt|corect", marcator)
    # (1) grup cu cantitate: „4 invertoare de 30 kW... nu, 5 invertoare de 30 kW” → toată sintagma veche se înlocuiește
    mg = re.match(r"(\d+)\s*(?:x\s*)?([a-z]{3,})", nn)
    if mg and mg.group(2) not in ("kw", "kva", "kwp", "kwh", "mw", "ohm", "kvar"):
        stem = mg.group(2)[:5]
        cand = list(re.finditer(rf"(?<![\w.,])\d+\s*(?:x\s*)?{re.escape(stem)}\w*", _norm(zona)))
        if cand:
            v = cand[-1]
            vechi = zona[v.start():].rstrip(" .…,;:!")
            out = inainte[:s0 + v.start()] + nou + rest
            return out, f"autocorectură: „{vechi.strip()}” → „{nou}” (ultima valoare scrisă câștigă)"
    # (2) schema de legare la pământ / (3) rețeaua
    for rx in (_RE_SP_TOKEN, _RE_RETEA_TOKEN):
        mt = rx.match(nou)
        if mt:
            cand = list(rx.finditer(zona))
            if not cand:
                return None
            v = cand[-1]
            out = inainte[:s0 + v.start()] + mt.group(0) + inainte[s0 + v.end():] + nou[mt.end():] + rest
            return out, f"autocorectură: „{v.group(0)}” → „{mt.group(0)}” (ultima valoare scrisă câștigă)"
    # (4) o valoare cu unitate (eventual precedată de nume: „plita 5 kw”) → ultima valoare cu aceeași unitate
    mv = _RE_VAL_U.search(nou)
    if mv and len(nou[:mv.start()].split()) <= 2:
        u = mv.group(2).lower()
        cand = [x for x in _RE_VAL_U.finditer(zona) if x.group(2).lower() == u]
        if not cand:
            return None
        v = cand[-1]
        if slab and (abs(len(inainte) - (s0 + v.end())) > 40 or v.group(1) == mv.group(1)):
            return None
        out = inainte[:s0 + v.start()] + mv.group(0) + inainte[s0 + v.end():] + nou[mv.end():] + rest
        return out, f"autocorectură: „{v.group(0)}” → „{mv.group(0)}” (ultima valoare scrisă câștigă)"
    if slab or re.search(r"\bnu\s*[,:]", marcator):
        if not re.match(r"[A-Za-z]{1,6}[\s-]?\d", nou):
            return None
    # (5) un model (litere + cifre)
    cand = list(re.finditer(r"\b[A-Za-z]{1,6}[\s-]?\d+[\w.\-]*\b", zona))
    if not cand:
        return None
    v = cand[-1]
    out = inainte[:s0 + v.start()] + nou + inainte[s0 + v.end():] + rest
    return out, f"autocorectură: „{v.group(0)}” → „{nou}” (ultima valoare scrisă câștigă)"


def rescrie_autocorectura(text: str) -> tuple[str, list[str]]:
    """„1 x SG125CX... scuze, de fapt SG110CX” → „1 x SG110CX”; „15 kW, corectez: 20 kW” → „20 kW”.
    r9: și „… nu, 5 invertoare de 30 kW”, „3 pompe de 11 kW, scuze, 15 kW”, „TN-C-S... nu, TN-S”, „greșit, e 20 kW”,
    „pardon, 3x40A”, „adică 25 kW” — ultima valoare câștigă pentru aceeași entitate (grup cu cantitate, valoare cu
    aceeași unitate, schema de pământ, rețeaua, modelul), în aceeași propoziție; fără dublare."""
    note = []
    for _ in range(6):
        gasit = None
        for m in _RE_MARCATOR_CORECTURA.finditer(_norm(text)):
            if m.start() == 0:
                continue
            r = _corectura(text, m)
            if r:
                gasit = r
                break
        if not gasit:
            break
        text, nota = gasit
        note.append(nota)
    return text, note


RE_CORPURI = re.compile(rf"(?P<n>\d+)\s*(?:corpuri|lampi|lămpi|aparate|proiectoare|spoturi|plafoniere)(?:\s+(?:de\s+)?iluminat)?\s*"
                        rf"[x×]\s*(?P<p>{NUM})\s*(?P<u>w|kw)\b\s+(?:pe|in|repartizate\s+pe|impartite\s+pe)\s+(?P<m>\d+)\s+circuite",
                        re.I)


def rescrie_corpuri(text: str) -> tuple[str, list[str]]:
    """„24 corpuri x 150 W pe 3 circuite” → „3 circuite de 1,2 kW” (puterea totală împărțită pe circuite)."""
    note = []

    def f(m):
        n, m_ = int(m.group("n")), int(m.group("m"))
        p = float(m.group("p").replace(",", ".")) * (1 if m.group("u").lower() == "kw" else 0.001)
        pc = round(n * p / m_, 3)
        note.append(f"„{m.group(0)}” = {n} × {m.group('p')} {m.group('u')} = {round(n * p, 3):g} kW pe {m_} circuite → "
                    f"{m_} circuite de {pc:g} kW".replace(".", ","))
        return f"{m_} circuite de {str(pc).replace('.', ',')} kW"
    out = RE_CORPURI.sub(f, text)
    return out, note


def _norm(t: str) -> str:
    return t.translate(_DIA).lower()


RE_SALUT = re.compile(r"^\s*(?:buna\s+ziua|buna\s+seara|buna\s+dimineata|buna|salut\w*|hello|hi|hey|stimate?\s+\w+(?:\s+\w+)?"
                      r"|stimata\s+\w+|dear\s+\w+|good\s+(?:morning|afternoon))\s*[,!.]+\s*")
RE_CERERE = re.compile(r"(?:va\s+rog\s+(?:frumos\s+)?(?:sa\s+(?:ne|imi|mi)\s+)?(?:trimiteti|faceti|realizati|intocmiti|desenati)"
                       r"|am\s+nevoie\s+(?:urgent\s+)?de|ne\s+trebuie|as\s+dori|am\s+dori|dorim|vrem|vreau)\s+(?:si\s+)?(?:o\s+)?"
                       r"schem\w*(?:\s+monofilar\w*|\s+electric\w*)?(?:\s+(?:pentru|pt\.?|la|a))?\s+")
RE_SEMNATURA = re.compile(r"(?:^|[.!\n,]\s*)(?:multumesc|multumim|mersi|cu\s+stima|cu\s+respect|toate\s+cele\s+bune|o\s+zi\s+buna"
                          r"|thanks|thank\s+you|regards|best)\b[^\n]*$")
RE_ARE = re.compile(r"\b(?P<s>[a-z][a-z\-]+)\s+are\s+(?=\d|doua\b|doi\b|trei\b|patru\b|cinci\b)")


def rescrie_email(text: str) -> tuple[str, list[str]]:
    """Emailul clientului: salutul, formula de cerere („vă rog să ne trimiteți schema monofilară pentru”) și semnătura
    („Mulțumesc, Ing. Popescu”) nu sunt date; „Chillerul are 2 compresoare …” = lista receptoarelor (după „:”)."""
    t, n = text, _norm(text)
    note = []
    m = RE_SALUT.match(n)
    if m:
        t, n = t[m.end():], n[m.end():]
    m = RE_CERERE.search(n)
    if m:
        t, n = t[:m.start()] + t[m.end():], n[:m.start()] + n[m.end():]
    m = RE_SEMNATURA.search(n)
    if m and len(n) - m.start() <= 80 and m.start() > 0:
        t, n = t[:m.start()] + ".", n[:m.start()] + "."
        note.append("formula de încheiere / semnătura emailului ignorată")
    m = RE_ARE.search(n)
    if m and m.group("s") not in ("casa", "casei", "apartamentul", "apartament", "vila", "locuinta", "bransamentul", "nu",
                                  "care", "ce", "cine", "el", "ea", "ei", "ele", "omul", "clientul", "beneficiarul"):
        t = t[:m.end("s")] + ":" + t[m.end():].lstrip()
        t = t[:m.end("s") + 1] + " " + t[m.end("s") + 1:]
    return (t, note) if t != text else (text, [])


# greșeli de tastare uzuale (lungimea nu contează aici) și prescurtări de mesaj scurt
TYPO_R8 = [(r"\bcsaa\b", "casa"), (r"\bcaas\b", "casa"), (r"\btirfaz", "trifaz"), (r"\btrfaz", "trifaz"), (r"\btrifzat", "trifazat"),
           (r"\bmonfaz", "monofaz"), (r"\bmonofzat", "monofazat"), (r"\bboilre\b", "boiler"), (r"\bboier\b", "boiler"),
           (r"\bplta\b", "plita"), (r"\bpltia\b", "plita"), (r"\bcuptr\b", "cuptor"), (r"\bpomap\b", "pompa"),
           (r"\bprosumtor\b", "prosumator"), (r"\btn\s+c\s+s\b", "tn-c-s"), (r"\btn\s+s\b", "tn-s")]
TYPO_R8 = [(re.compile(rx, re.I), rep) for rx, rep in TYPO_R8]
# „15k”, „5k” (mesaj scurt) = kW
RE_K_KW = re.compile(r"(?<![\w.,-])(\d+(?:[.,]\d+)?)\s*k\b(?![-\w])(?!\s*(?:w|va|wh|wp|v|a)\b)", re.I)


def rescrie_scurt(text: str) -> tuple[str, list[str]]:
    """Mesajele scurte: „casa 3f 15k” → „15 kW”; greșelile de tastare uzuale („csaa tirfazata … boilre si plta”)."""
    out, note = text, []
    for rx, rep in TYPO_R8:
        out = rx.sub(rep, out)
    if out != text:
        note.append("greșelile de tastare evidente au fost corectate (" + ", ".join(
            sorted({m.group(0) for rx, _ in TYPO_R8 for m in rx.finditer(text)})) + ")")
    # r8 (locuințe #16): „AC 18000btu + 2x9000 btu” = 3 aparate de aer condiționat (fiecare cu circuitul lui)
    o1 = re.sub(r"(?i)(?<=btu)\s*\+\s*(?:(\d+)\s*[x×]\s*)?(\d{4,5})\s*btu",
                lambda m: f", {m.group(1) + ' x ' if m.group(1) else ''}AC {m.group(2)} btu", out)
    if o1 != out:
        note.append("„… btu + N x … btu” = aparate de aer condiționat separate")
        out = o1
    o2 = RE_K_KW.sub(lambda m: f"{m.group(1)} kW", out)

    if o2 != out:
        note.append("„Nk” = N kW (" + ", ".join(m.group(0) for m in RE_K_KW.finditer(out)) + ")")
    return o2, note


def rescrie(text: str) -> tuple[str, list[str]]:
    """Toate rescrierile r8, în ordine; întoarce (text, note)."""
    note = []
    for f in (rescrie_indentare, rescrie_tabel, rescrie_en, rescrie_scurt, rescrie_email, rescrie_autocorectura, rescrie_cifre, rescrie_termeni, rescrie_lungimi, rescrie_marire,
              rescrie_lant, rescrie_din_tg, rescrie_cascade, rescrie_corpuri):



        text, n = f(text)
        note += n
    return text, note
