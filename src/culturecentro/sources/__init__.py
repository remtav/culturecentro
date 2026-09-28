"""Sources d'événements, une par salle, derrière une interface commune.

Chaque source implémente :class:`~culturecentro.sources.base.Source`. Le
registre :data:`SOURCES` recense les salles disponibles par leur ``slug``,
pour que la CLI et l'agrégation les découvrent automatiquement — ajouter une
salle se limite à créer son module et à l'inscrire ici.
"""

from __future__ import annotations

from culturecentro.sources.base import Source
from culturecentro.sources.lapetiteboitenoire import LaPetiteBoiteNoire
from culturecentro.sources.theatre_granada import TheatreGranada

#: Registre des sources disponibles, indexé par ``slug``.
SOURCES: dict[str, Source] = {
    source.slug: source for source in (TheatreGranada(), LaPetiteBoiteNoire())
}


def obtenir(slug: str) -> Source:
    """Renvoie la source d'``slug`` donné, ou lève ``KeyError``."""
    return SOURCES[slug]


def toutes() -> list[Source]:
    """Renvoie toutes les sources enregistrées."""
    return list(SOURCES.values())


__all__ = [
    "Source",
    "SOURCES",
    "TheatreGranada",
    "LaPetiteBoiteNoire",
    "obtenir",
    "toutes",
]
