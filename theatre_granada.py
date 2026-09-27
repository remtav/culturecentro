"""Récupération des événements à venir du Théâtre Granada.

Le site https://theatregranada.com est un site WordPress. Comme la plupart
des sites d'agenda WordPress (The Events Calendar, etc.), la page de
programmation expose ses événements de deux façons exploitables :

1. Des données structurées schema.org de type ``Event`` en JSON-LD
   (balise ``<script type="application/ld+json">``). C'est la source la
   plus fiable et c'est celle qu'on privilégie.
2. À défaut, on retombe sur un parcours du HTML.

La fonction ``lister_evenements_a_venir`` renvoie la liste des événements
dont la date est postérieure (ou égale) à maintenant, triés par date.

Dépendances : ``requests`` et ``beautifulsoup4``.
    pip install requests beautifulsoup4
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import requests
from bs4 import BeautifulSoup

URL_PROGRAMMATION = "https://theatregranada.com/programmation-2/"

_ENTETES = {
    # Un User-Agent « navigateur » évite les blocages basiques.
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}


@dataclass
class Evenement:
    """Un événement de la programmation."""

    titre: str
    date_debut: datetime | None
    lien: str | None = None
    lieu: str | None = None

    def __str__(self) -> str:
        quand = self.date_debut.strftime("%Y-%m-%d %H:%M") if self.date_debut else "date inconnue"
        return f"{quand} — {self.titre}" + (f" ({self.lien})" if self.lien else "")


def _telecharger(url: str, timeout: float) -> str:
    reponse = requests.get(url, headers=_ENTETES, timeout=timeout)
    reponse.raise_for_status()
    return reponse.text


def _parse_date(valeur: str | None) -> datetime | None:
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


def _iterer_noeuds_jsonld(donnees: object) -> Iterable[dict]:
    """Parcourt récursivement une structure JSON-LD et livre chaque dict."""
    if isinstance(donnees, dict):
        # Cas @graph : une liste d'objets sous une clé.
        if "@graph" in donnees and isinstance(donnees["@graph"], list):
            yield from _iterer_noeuds_jsonld(donnees["@graph"])
        yield donnees
    elif isinstance(donnees, list):
        for element in donnees:
            yield from _iterer_noeuds_jsonld(element)


def _est_event(noeud: dict) -> bool:
    type_ = noeud.get("@type", "")
    types = type_ if isinstance(type_, list) else [type_]
    return any(isinstance(t, str) and "Event" in t for t in types)


def _extraire_lieu(noeud: dict) -> str | None:
    lieu = noeud.get("location")
    if isinstance(lieu, dict):
        return lieu.get("name")
    if isinstance(lieu, str):
        return lieu
    return None


def _extraire_depuis_jsonld(html: str) -> list[Evenement]:
    soup = BeautifulSoup(html, "html.parser")
    evenements: list[Evenement] = []
    for balise in soup.find_all("script", type="application/ld+json"):
        contenu = balise.string or balise.get_text()
        if not contenu:
            continue
        try:
            donnees = json.loads(contenu)
        except json.JSONDecodeError:
            continue
        for noeud in _iterer_noeuds_jsonld(donnees):
            if not isinstance(noeud, dict) or not _est_event(noeud):
                continue
            titre = noeud.get("name")
            if not titre:
                continue
            evenements.append(
                Evenement(
                    titre=titre.strip(),
                    date_debut=_parse_date(noeud.get("startDate")),
                    lien=noeud.get("url"),
                    lieu=_extraire_lieu(noeud),
                )
            )
    return evenements


def _extraire_depuis_html(html: str) -> list[Evenement]:
    """Repli générique si aucun JSON-LD n'est présent.

    Cible les motifs les plus courants des thèmes d'agenda WordPress
    (The Events Calendar). Les sélecteurs peuvent devoir être ajustés
    si le thème du site change.
    """
    soup = BeautifulSoup(html, "html.parser")
    evenements: list[Evenement] = []

    for article in soup.select(
        ".tribe-events-calendar-list__event, article.tribe_events, .type-tribe_events"
    ):
        lien_titre = article.select_one(
            "a.tribe-events-calendar-list__event-title-link, h3 a, h2 a, .tribe-event-url"
        )
        titre = lien_titre.get_text(strip=True) if lien_titre else None
        if not titre:
            continue

        balise_date = article.select_one("time[datetime], .tribe-event-date-start, time")
        date_debut = None
        if balise_date is not None:
            date_debut = _parse_date(balise_date.get("datetime")) or _parse_date(
                balise_date.get_text(strip=True)
            )

        evenements.append(
            Evenement(
                titre=titre,
                date_debut=date_debut,
                lien=lien_titre.get("href") if lien_titre else None,
            )
        )
    return evenements


def lister_evenements_a_venir(
    url: str = URL_PROGRAMMATION,
    *,
    a_partir_de: datetime | None = None,
    timeout: float = 20.0,
) -> list[Evenement]:
    """Retourne les événements à venir de la programmation, triés par date.

    Args:
        url: page de programmation à analyser.
        a_partir_de: seuil temporel ; par défaut « maintenant » (UTC).
            Les événements sans date connue sont conservés.
        timeout: délai d'attente réseau, en secondes.

    Returns:
        Liste d'objets :class:`Evenement`.
    """
    if a_partir_de is None:
        a_partir_de = datetime.now(timezone.utc)

    html = _telecharger(url, timeout)

    evenements = _extraire_depuis_jsonld(html)
    if not evenements:
        evenements = _extraire_depuis_html(html)

    # Déduplication (titre + date) en conservant l'ordre de découverte.
    vus: set[tuple[str, str]] = set()
    uniques: list[Evenement] = []
    for ev in evenements:
        cle = (ev.titre, ev.date_debut.isoformat() if ev.date_debut else "")
        if cle not in vus:
            vus.add(cle)
            uniques.append(ev)

    def _est_a_venir(ev: Evenement) -> bool:
        if ev.date_debut is None:
            return True  # date inconnue : on ne l'exclut pas
        date = ev.date_debut
        if date.tzinfo is None:  # date « naïve » : on la suppose en UTC
            date = date.replace(tzinfo=timezone.utc)
        return date >= a_partir_de

    a_venir = [ev for ev in uniques if _est_a_venir(ev)]
    a_venir.sort(key=lambda ev: ev.date_debut or datetime.max.replace(tzinfo=timezone.utc))
    return a_venir


if __name__ == "__main__":
    for evenement in lister_evenements_a_venir():
        print(evenement)
