"""Cheia API Anthropic pentru citirea avansată a textului (SPEC_TEHNIC.md §F.9).

Ordinea surselor:
  1. cheia introdusă în aplicație (Setări → Citire avansată) — ținută DOAR în memoria procesului;
  2. fișierul local ~/.config/scheme-monofilare/anthropic_api_key (doar dacă utilizatorul a bifat „ține minte”;
     drepturi 0600, în afara depozitului de cod);
  3. variabila de mediu ANTHROPIC_API_KEY (sau ANTHROPIC_AUTH_TOKEN → „Bearer …”).
Cheia nu se scrie niciodată în proiect, în exporturi sau în depozit.
"""
from __future__ import annotations

import os
import pathlib

_MEMORIE: dict = {"cheie": None}


def fisier() -> pathlib.Path:
    baza = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return pathlib.Path(baza) / "scheme-monofilare" / "anthropic_api_key"


def citeste() -> str | None:
    if _MEMORIE["cheie"]:
        return _MEMORIE["cheie"]
    try:
        f = fisier()
        if f.is_file():
            k = f.read_text(encoding="utf-8").strip()
            if k:
                return k
    except OSError:
        pass
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"].strip()
    if os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "Bearer " + os.environ["ANTHROPIC_AUTH_TOKEN"].strip()
    return None


def sursa() -> str | None:
    if _MEMORIE["cheie"]:
        return "aplicatie"
    try:
        if fisier().is_file() and fisier().read_text(encoding="utf-8").strip():
            return "fisier"
    except OSError:
        pass
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "mediu"
    return None


def seteaza(cheie: str | None, pastreaza: bool = False) -> str | None:
    """Setează (sau, cu cheie goală, șterge) cheia din aplicație. `pastreaza` → și în ~/.config (0600)."""
    cheie = (cheie or "").strip() or None
    if cheie is not None and (len(cheie) < 20 or any(c.isspace() for c in cheie)):
        raise ValueError("cheia API nu pare validă (se copiază din console.anthropic.com → API keys)")
    _MEMORIE["cheie"] = cheie
    f = fisier()
    if cheie and pastreaza:
        f.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(f), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as h:
            h.write(cheie)
    elif not cheie or not pastreaza:
        try:
            f.unlink()
        except OSError:
            pass
    return sursa()
