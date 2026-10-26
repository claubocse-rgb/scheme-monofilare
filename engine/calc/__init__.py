"""engine.calc — motorul de dimensionare JT și validatorul blocant (SPEC_TEHNIC.md §A–§E, §G, §H).

    from engine.calc import calculeaza
    r = calculeaza(intrare)     # intrare = forma câmpului "intrare" din tests/date/cazuri_golden.json

Module: norme (date normative, nemodificat), comun, verificari (catalogul §D), protectii (§B.3–§B.6, §B.15, §B.18),
cabluri (§B.7–§B.12), scurtcircuit (§B.13–§B.14, §C.5, §C.6), ramura (lanțul §B.21), scheme (§C.1–§C.6, §E.1, §G.2),
texte (§E.2, §E.3, §G.3, V80/V81), simplu (o singură ramură, panoul „Dimensionează”), pamant (v1.3, §C.7 priza de
pământ, V37), ddr (v1.3, §B.18.1 selectivitatea DDR în serie, V43), locuinta (v1.4, §C.8 tabloul casei).
"""
from .scheme import calculeaza, receptor_dupa_nume
from .ramura import calculeaza_ramura, verifica_cablu
from .simplu import dimensioneaza_ramura_simpla
from .texte import fmt_ro, text_lista, text_desen, text_cablu, note_generate, verifica_aparat, verifica_nota

__all__ = ["calculeaza", "calculeaza_ramura", "verifica_cablu", "dimensioneaza_ramura_simpla", "receptor_dupa_nume", "fmt_ro", "text_lista", "text_desen",
           "text_cablu", "note_generate", "verifica_aparat", "verifica_nota"]
