"""Finalisation d'une liste d'événements : dédup, filtrage et tri.

Partagé par les sources (sur leur propre liste) et par l'agrégation (sur la
liste fusionnée de toutes les salles).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from culturecentro.models import Evenement


def minuit_utc() -> datetime:
    """Minuit du jour courant en UTC (seuil « jour courant ou futur »)."""
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _en_aware(date: datetime) -> datetime:
    """Date « naïve » supposée en UTC, pour permettre les comparaisons."""
    return date if date.tzinfo is not None else date.replace(tzinfo=timezone.utc)


def finaliser(evenements: Sequence[Evenement], a_partir_de: datetime) -> list[Evenement]:
    """Déduplique (titre + date), filtre les événements à venir et trie par date.

    Les événements sans date connue sont conservés et triés en fin de liste.
    """
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
        return _en_aware(ev.date_debut) >= a_partir_de

    lointain = datetime.max.replace(tzinfo=timezone.utc)  # trie les dates inconnues en fin

    a_venir = [ev for ev in uniques if _est_a_venir(ev)]
    a_venir.sort(key=lambda ev: _en_aware(ev.date_debut) if ev.date_debut else lointain)
    return a_venir
