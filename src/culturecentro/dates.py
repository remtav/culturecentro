"""Analyse des dates : ISO 8601 (JSON-LD) et dates françaises (affichage).

Les dates françaises sont renvoyées « naïves » (sans fuseau) ; le filtrage les
suppose en UTC.
"""

from __future__ import annotations

import re
from datetime import datetime

_MOIS_FR = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}

# Ex. : « dimanche 27 septembre 2026 à 20:00 », « 30 septembre 2026, 20h00 »,
# « 1er octobre 2026 ». Le nom du jour de la semaine et l'heure sont facultatifs.
_DATE_FR = re.compile(
    r"(?P<jour>\d{1,2})\s*(?:er)?\s+"
    r"(?P<mois>[a-zàâäéèêëîïôöùûüç]+)\s+"
    r"(?P<annee>\d{4})"
    r"(?:\D+(?P<heure>\d{1,2})\s*[h:]\s*(?P<minute>\d{2})?)?",
    re.IGNORECASE,
)


def parse_date_iso(valeur: str | None) -> datetime | None:
    """Analyse une date ISO 8601 (format renvoyé par le JSON-LD)."""
    if not valeur:
        return None
    texte = valeur.strip()
    # Python <3.11 ne gère pas le suffixe « Z » dans fromisoformat.
    if texte.endswith("Z"):
        texte = texte[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(texte)
    except ValueError:
        return None


def parse_date_fr(valeur: str | None) -> datetime | None:
    """Analyse une date française (« dimanche 27 septembre 2026 à 20:00 »).

    Le nom du jour de la semaine et l'heure sont facultatifs. La date est
    renvoyée « naïve » (sans fuseau) ; le filtrage la suppose en UTC.
    """
    if not valeur:
        return None
    m = _DATE_FR.search(valeur.strip().lower())
    if not m:
        return None
    mois = _MOIS_FR.get(m.group("mois"))
    if mois is None:
        return None
    heure = int(m.group("heure")) if m.group("heure") else 0
    minute = int(m.group("minute")) if m.group("minute") else 0
    try:
        return datetime(int(m.group("annee")), mois, int(m.group("jour")), heure, minute)
    except ValueError:
        return None
