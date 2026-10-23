"""Chat: text liber (română) → interpretare structurală (SPEC_TEHNIC.md §F).

Wrapper subțire, păstrat pentru compatibilitate cu `app.py` (`/api/chat`). Toată logica e în
`engine/interpretor.py`: extragere, normalizare, presupuneri declarate (F.6), refuzuri/întrebări (F.7) și,
opțional, Claude (SDK `anthropic`) care produce DOAR `intrare_fizica`, validată ca și regulile locale.

Modulul NU mai construiește modelul grafic și NU mai dimensionează (F.1).

TODO(integrator): legați `r["intrare_fizica"]` → `engine.calc.calculeaza(...)` (motorul de dimensionare B–C,
în lucru la alt coleg) → modelul grafic (layout/render). Până atunci `r["model"]` este None și interfața
afișează doar `r["explicatie"]` (textul „Am înțeles / Am presupus / Întrebare”, F.8). Exportul trebuie refuzat
când `r["actiune"] == "refuza"`; la „genereaza_cu_intrebare” se generează și se afișează întrebarea.
"""
from .interpretor import interpreteaza as _interpreteaza, interpreteaza_local  # noqa: F401


def interpreteaza(text: str, foloseste_claude: bool = True) -> dict:
    """Compatibilitate: aceeași semnătură ca vechiul `chat.interpreteaza`.
    Întoarce rezultatul interpretorului (F.1) plus cheile vechi `model` (None), `explicatie`, `motor`."""
    r = _interpreteaza(text, foloseste_llm=foloseste_claude)
    # TODO(integrator): r["model"] = model_grafic(engine.calc.calculeaza(r["intrare_fizica"])) când actiune != "refuza"
    r["model"] = None
    r["explicatie"] = r["intelegere"].splitlines()
    return r
