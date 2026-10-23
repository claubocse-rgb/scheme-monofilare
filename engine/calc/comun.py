"""comun.py — utilitare comune motorului de dimensionare (comparații cu toleranță, serii, jurnalul de calcul).

Implementează regula SPEC §B.22: calculele se fac în virgulă mobilă, fără rotunjiri intermediare,
iar comparațiile se fac cu toleranța 1e-9.
"""
import math

from . import norme

EPS = 1e-9
SQRT3 = norme.SQRT3
UN = norme.U_N_V
U0 = norme.U_0_V


def _tol(a, b):
    """Toleranța de comparare (SPEC §B.22): 1e-9, relativ la mărimea operanzilor (cel puțin absolut 1e-9)."""
    return EPS * max(1.0, abs(a), abs(b))


def ge(a, b):
    """a ≥ b cu toleranță (SPEC §B.22)."""
    return a >= b - _tol(a, b)


def gt(a, b):
    """a > b cu toleranță (SPEC §B.22)."""
    return a > b + _tol(a, b)


def le(a, b):
    """a ≤ b cu toleranță (SPEC §B.22)."""
    return ge(b, a)


def lt(a, b):
    """a < b cu toleranță (SPEC §B.22)."""
    return gt(b, a)


def eq(a, b):
    """a = b cu toleranță (SPEC §B.22)."""
    return abs(a - b) <= _tol(a, b)


def prima_din_serie(serie, valoare):
    """Cea mai mică valoare din serie ≥ valoare (SPEC §B.4/§B.5 pct. 1), sau None dacă nu există."""
    for s in sorted(serie):
        if ge(s, valoare):
            return s
    return None


def vecini(serie, valoare):
    """Valorile din serie imediat sub și imediat peste o valoare inexistentă (remedierea V05, SPEC §D)."""
    s = sorted(serie)
    jos = [x for x in s if x < valoare]
    sus = [x for x in s if x > valoare]
    return (jos[-1] if jos else None, sus[0] if sus else None)


def modul(z):
    """|Z| pentru Z = (R, X) [Ω] (SPEC §B.13/§B.14)."""
    return math.hypot(z[0], z[1])


def u_calcul(retea):
    """Tensiunea de calcul a curentului: √3·400 V la trifazat, 230 V la monofazat (SPEC §A.1, §B.2)."""
    return SQRT3 * UN if retea == "tri" else U0


class Jurnal:
    """Colectorul rezultatelor de verificare (SPEC §D: {cod, nivel, obiect, mesaj, remediere}), al valorilor
    implicite folosite (SPEC §B.0 / V11), al pașilor de calcul (SPEC §H.3) și al ipotezelor (SPEC §G.2)."""

    def __init__(self):
        """Jurnal gol pentru o schemă (SPEC §D, §B.0, §G.2)."""
        self.verificari = []
        self.info = []
        self._presupus = []          # [(text, [elemente])], în ordinea declarării
        self.pasi = []
        self.ipoteze_folosite = {}

    def emite(self, cod, nivel, obiect, mesaj, remediere=""):
        """Adaugă un rezultat de verificare în ordinea producerii (SPEC §D)."""
        if nivel == "INFO":
            self.info.append({"cod": cod, "nivel": "INFO", "obiect": obiect, "mesaj": mesaj})
        else:
            self.verificari.append({"cod": cod, "nivel": nivel, "obiect": obiect, "mesaj": mesaj,
                                    "remediere": remediere})

    def presupune(self, text, element=None):
        """Declară o valoare implicită folosită (SPEC §B.0, „toate se declară”; V11). Declarațiile repetate pentru
        mai multe ramuri se grupează: „lungime plecări 50 m (P1·A, P2·B)”."""
        from .texte import curata_text
        text = curata_text(text)
        for t, el in self._presupus:
            if t == text:
                if element is not None and element not in el:
                    el.append(element)
                return
        self._presupus.append((text, [element] if element is not None else []))

    @property
    def presupus(self):
        """Lista valorilor implicite folosite, în română (SPEC §F.6 „Am presupus: …”)."""
        return [f"{t} ({', '.join(el)})" if el else t for t, el in self._presupus]

    def pas(self, text):
        """Adaugă un pas de calcul pentru memoriul de calcul (SPEC §H.3)."""
        self.pasi.append(text)

    def ipoteza(self, cheie, valoare, implicit):
        """Reține o ipoteză efectiv folosită, pentru nota G.2 (SPEC §G.2)."""
        lst = self.ipoteze_folosite.setdefault(cheie, [])
        if (valoare, implicit) not in lst:
            lst.append((valoare, implicit))

    def are_blocant(self, de_la=0):
        """True dacă există un BLOCANT emis după indexul `de_la` (SPEC §D, „BLOCANT = exportul este refuzat”)."""
        return any(v["nivel"] == "BLOCANT" for v in self.verificari[de_la:])
