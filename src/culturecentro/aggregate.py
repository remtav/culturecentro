"""Agrégation de la programmation de plusieurs salles.

Interroge chaque source indépendamment, tolère qu'une salle échoue (réseau,
structure modifiée) sans faire échouer les autres, renseigne le partenaire et
le lieu manquant avec le nom de la salle, ramène les lieux à leur nom
canonique, écarte les événements hors du centre-ville, puis déduplique et
trie l'ensemble.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime

import requests

from culturecentro.filtrage import finaliser, minuit_utc
from culturecentro.lieux import est_centre_ville, normaliser_lieu
from culturecentro.models import Evenement
from culturecentro.sources import Source, toutes

_LOG = logging.getLogger(__name__)


def agreger(
    sources: Iterable[Source] | None = None,
    *,
    a_partir_de: datetime | None = None,
    timeout: float = 20.0,
) -> list[Evenement]:
    """Agrège les événements à venir de plusieurs salles.

    Args:
        sources: salles à interroger (défaut : toutes celles enregistrées).
        a_partir_de: seuil temporel ; par défaut minuit du jour courant (UTC).
        timeout: délai d'attente réseau par salle, en secondes.

    Returns:
        La liste fusionnée, dédupliquée et triée par date. ``partenaire`` et,
        s'il est absent, ``lieu`` sont renseignés avec le nom de la salle ;
        les lieux sont ramenés à leur nom canonique
        (:func:`~culturecentro.lieux.normaliser_lieu`) et les événements hors
        du centre-ville (:func:`~culturecentro.lieux.est_centre_ville`) sont
        écartés.

    Une salle qui échoue (``requests.RequestException``) est ignorée avec un
    avertissement : l'agrégation renvoie les événements des autres salles.
    """
    if sources is None:
        sources = toutes()
    if a_partir_de is None:
        a_partir_de = minuit_utc()

    evenements: list[Evenement] = []
    for source in sources:
        try:
            evs = source.lister_evenements_a_venir(a_partir_de=a_partir_de, timeout=timeout)
        except requests.RequestException as exc:
            _LOG.warning("Salle « %s » indisponible : %s", source.nom, exc)
            continue
        conserves: list[Evenement] = []
        for ev in evs:
            ev.partenaire = ev.partenaire or source.nom
            ev.lieu = normaliser_lieu(ev.lieu) or source.nom
            if not est_centre_ville(ev.lieu):
                _LOG.debug("Hors centre-ville, écarté : %s (%s)", ev.titre, ev.lieu)
                continue
            conserves.append(ev)
        _LOG.info(
            "Salle « %s » : %d événements (%d hors centre-ville écartés).",
            source.nom,
            len(conserves),
            len(evs) - len(conserves),
        )
        evenements.extend(conserves)

    return finaliser(evenements, a_partir_de)
