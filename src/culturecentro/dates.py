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


# --------------------------------------------------------------------------- #
# Dates multiples et plages (« du 7 au 17 octobre 2026 », « jusqu'en mai »…)
# --------------------------------------------------------------------------- #

#: Nom de mois → numéro (accents facultatifs). Exposé pour les sources.
MOIS_FR = _MOIS_FR

# « 17 septembre », « 1er octobre 2026 », « 02 oct. 2026 » : le jour, le mois
# (abrégé ou non) et, facultativement, l'année.
_JOUR_MOIS = re.compile(
    r"(?<![\d/])(?P<jour>\d{1,2})\s*(?:er)?\s+"
    r"(?P<mois>[a-zàâäéèêëîïôöùûüç]{3,})\.?"
    r"(?:\s+(?P<annee>\d{4}))?",
    re.IGNORECASE,
)

# « du 7 au 17 octobre 2026 » : le premier jour n'a pas de mois.
_DU_JOUR_AU = re.compile(
    r"(?:\bdu\s+)?(?<![\d/])(?P<jour1>\d{1,2})\s*(?:er)?\s+au\s+(?P<jour2>\d{1,2})\s*(?:er)?\s+"
    r"(?P<mois>[a-zàâäéèêëîïôöùûüç]{3,})\.?(?:\s+(?P<annee>\d{4}))?",
    re.IGNORECASE,
)

# « jusqu'en octobre 2026 », « jusqu'au 31 mai » (traité comme une fin).
_JUSQU_MOIS = re.compile(
    r"jusqu['’]?\s*(?:en|à|a)\s+(?P<mois>[a-zàâäéèêëîïôöùûüç]{3,})\.?(?:\s+(?P<annee>\d{4}))?",
    re.IGNORECASE,
)

# « 18h30 », « 17h », « 19 h 00 », « 20:00 » (mais pas « 2026 »).
_HEURE = re.compile(r"(?<![\d:])(?P<heure>\d{1,2})\s*(?:h|:)\s*(?P<minute>\d{2})?(?![\d:])")


def _numero_mois(nom: str) -> int | None:
    """Numéro d'un mois français, abréviations comprises (« oct. », « sept »)."""
    nom = nom.lower().rstrip(".")
    if nom in MOIS_FR:
        return MOIS_FR[nom]
    if len(nom) >= 3:
        candidats = {num for n, num in MOIS_FR.items() if n.startswith(nom)}
        if len(candidats) == 1:
            return candidats.pop()
    return None


def _construire(jour: int, mois: int, annee: int | None) -> datetime | None:
    if annee is None:
        return None
    try:
        return datetime(annee, mois, jour)
    except ValueError:
        return None


def parse_heure_fr(valeur: str | None) -> tuple[int, int] | None:
    """Première heure d'un texte (« 18h30 » → ``(18, 30)``), ou ``None``."""
    if not valeur:
        return None
    m = _HEURE.search(valeur)
    if not m:
        return None
    heure = int(m.group("heure"))
    if heure > 23:
        return None
    return heure, int(m.group("minute") or 0)


def trouver_dates_fr(valeur: str | None, annee_defaut: int | None = None) -> list[datetime]:
    """Toutes les dates « jour mois [année] » d'un texte, dans l'ordre, sans heure.

    Une date sans année reçoit ``annee_defaut`` ; si celle-ci est absente, la
    date est ignorée. Les jours qui ne sont pas suivis d'un mois (« du 7 au 17
    octobre ») ne sont pas des dates.
    """
    if not valeur:
        return []
    dates: list[datetime] = []
    for m in _JOUR_MOIS.finditer(valeur):
        mois = _numero_mois(m.group("mois"))
        if mois is None:
            continue
        annee = int(m.group("annee")) if m.group("annee") else annee_defaut
        date = _construire(int(m.group("jour")), mois, annee)
        if date is not None:
            dates.append(date)
    return dates


def plage_dates_fr(
    valeur: str | None, annee_defaut: int | None = None
) -> tuple[datetime | None, datetime | None]:
    """Analyse une période française et renvoie ``(debut, fin)``.

    Formes reconnues :

    * « du 7 au 17 octobre 2026 » (premier jour sans mois) ;
    * « 15 avril au 19 septembre 2027 », « du 29 octobre 2026 au 28 mai 2027 »,
      « 15 octobre 2026 au 21 mars 2027 » (l'année manquante du début est
      déduite de la fin) ;
    * « 18 octobre 2026 10 h 00 », « le 23 octobre 2026 » (début seul, avec
      l'heure si elle suit la date) ;
    * « jusqu'en octobre 2026 » (fin seule : dernier jour du mois).

    Une date sans année reçoit ``annee_defaut`` (ou l'année de l'autre borne).
    Renvoie ``(None, None)`` si rien n'est reconnu.
    """
    if not valeur:
        return None, None
    texte = " ".join(valeur.split())

    m = _DU_JOUR_AU.search(texte)
    if m:
        mois = _numero_mois(m.group("mois"))
        if mois is not None:
            annee = int(m.group("annee")) if m.group("annee") else annee_defaut
            debut = _construire(int(m.group("jour1")), mois, annee)
            fin = _construire(int(m.group("jour2")), mois, annee)
            if debut is not None:
                return _avec_heure(debut, texte[m.end() :]), fin

    m = _JUSQU_MOIS.search(texte)
    if m and not _JOUR_MOIS.search(texte):
        mois = _numero_mois(m.group("mois"))
        if mois is not None:
            annee = int(m.group("annee")) if m.group("annee") else annee_defaut
            if annee is not None:
                dernier = _construire(28, mois, annee)
                while dernier is not None:
                    suivant = _construire(dernier.day + 1, mois, annee)
                    if suivant is None:
                        break
                    dernier = suivant
                return None, dernier

    bornes = [
        (int(mm.group("jour")), _numero_mois(mm.group("mois")), mm.group("annee"), mm.end())
        for mm in _JOUR_MOIS.finditer(texte)
    ]
    bornes = [b for b in bornes if b[1] is not None]
    if not bornes:
        return None, None

    jour_d, mois_d, annee_d, fin_d = bornes[0]
    jour_f, mois_f, annee_f, _ = bornes[-1]
    if len(bornes) == 1:
        debut = _construire(jour_d, mois_d or 1, int(annee_d) if annee_d else annee_defaut)
        if debut is None:
            return None, None
        if texte.lower().startswith(("jusqu", "jusqu'")):
            return None, debut
        return _avec_heure(debut, texte[fin_d:]), None

    an_f = int(annee_f) if annee_f else annee_defaut
    an_d = int(annee_d) if annee_d else an_f
    debut = _construire(jour_d, mois_d or 1, an_d)
    fin = _construire(jour_f, mois_f or 1, an_f)
    if debut is not None and fin is not None and an_d is not None and not annee_d and fin < debut:
        debut = _construire(jour_d, mois_d or 1, an_d - 1)  # « du 15 décembre au 10 janvier 2027 »
    if debut is None:
        return None, fin
    return _avec_heure(debut, texte[fin_d:]), fin


def _avec_heure(date: datetime, reste: str) -> datetime:
    """Applique l'heure trouvée dans ``reste`` (texte après la date) à ``date``."""
    heure = parse_heure_fr(reste)
    if heure is None:
        return date
    return date.replace(hour=heure[0], minute=heure[1])
