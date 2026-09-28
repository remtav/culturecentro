"""Extraction des données structurées schema.org ``Event`` (JSON-LD).

Repli commun à toutes les sources : la plupart des pages d'événements exposent
un ``<script type="application/ld+json">`` contenant des objets ``Event``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from bs4 import BeautifulSoup

from culturecentro.dates import parse_date_iso
from culturecentro.models import Evenement

#: Un nœud JSON-LD : dictionnaire à clés textuelles et valeurs arbitraires.
Noeud = dict[str, Any]


def iterer_noeuds(donnees: object) -> Iterable[Noeud]:
    """Parcourt récursivement une structure JSON-LD et livre chaque dict."""
    if isinstance(donnees, dict):
        # Cas @graph : une liste d'objets sous une clé.
        if "@graph" in donnees and isinstance(donnees["@graph"], list):
            yield from iterer_noeuds(donnees["@graph"])
        yield donnees
    elif isinstance(donnees, list):
        for element in donnees:
            yield from iterer_noeuds(element)


def est_event(noeud: Noeud) -> bool:
    """Vrai si le nœud JSON-LD est (ou dérive d')un ``Event``."""
    type_ = noeud.get("@type", "")
    types = type_ if isinstance(type_, list) else [type_]
    return any(isinstance(t, str) and "Event" in t for t in types)


def extraire_lieu(noeud: Noeud) -> str | None:
    lieu = noeud.get("location")
    if isinstance(lieu, dict):
        return lieu.get("name")
    if isinstance(lieu, str):
        return lieu
    return None


def extraire_image(noeud: Noeud) -> str | None:
    image = noeud.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        return image.get("url")
    if isinstance(image, str):
        return image
    return None


def extraire_depuis_jsonld(html: str) -> list[Evenement]:
    """Extrait les événements des blocs JSON-LD schema.org d'une page."""
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
        for noeud in iterer_noeuds(donnees):
            if not isinstance(noeud, dict) or not est_event(noeud):
                continue
            titre = noeud.get("name")
            if not titre:
                continue
            evenements.append(
                Evenement(
                    titre=titre.strip(),
                    date_debut=parse_date_iso(noeud.get("startDate")),
                    lien=noeud.get("url"),
                    lieu=extraire_lieu(noeud),
                    image=extraire_image(noeud),
                )
            )
    return evenements
