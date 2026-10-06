"""Agrégation de la programmation de plusieurs salles.

Interroge chaque source indépendamment, tolère qu'une salle échoue (réseau,
structure modifiée) sans faire échouer les autres, renseigne le partenaire et
le lieu manquant avec le nom de la salle, ramène les lieux à leur nom
canonique, écarte les événements hors du centre-ville, puis déduplique et
trie l'ensemble. Enfin, la catégorie artistique de chaque événement est
déterminée automatiquement (:mod:`culturecentro.categories`).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime

import requests

from culturecentro.categories import Categorisation
from culturecentro.filtrage import finaliser, minuit_local
from culturecentro.http import creer_session
from culturecentro.lieux import est_centre_ville, normaliser_lieu
from culturecentro.models import Evenement
from culturecentro.sources import Source, toutes

_LOG = logging.getLogger(__name__)


def agreger(
    sources: Iterable[Source] | None = None,
    *,
    a_partir_de: datetime | None = None,
    timeout: float = 20.0,
    lire_fiches: bool = True,
) -> list[Evenement]:
    """Agrège les événements à venir de plusieurs salles.

    Args:
        sources: salles à interroger (défaut : toutes celles enregistrées).
        a_partir_de: seuil temporel ; par défaut minuit du jour courant (heure
            de Sherbrooke).
        timeout: délai d'attente réseau par salle, en secondes.
        lire_fiches: lire la fiche des événements dont la catégorie n'a pu
            être déterminée autrement (une requête par fiche).

    Returns:
        La liste fusionnée, dédupliquée et triée par date. ``partenaire`` et,
        s'il est absent, ``lieu`` sont renseignés avec le nom de la salle ;
        les lieux sont ramenés à leur nom canonique
        (:func:`~culturecentro.lieux.normaliser_lieu`) et les événements hors
        du centre-ville (:func:`~culturecentro.lieux.est_centre_ville`) sont
        écartés. ``categorie`` est déterminée automatiquement
        (:class:`~culturecentro.categories.Categorisation`) avec, en dernier
        recours, la catégorie par défaut de la salle.

    Une salle qui échoue (``requests.RequestException``) est ignorée avec un
    avertissement : l'agrégation renvoie les événements des autres salles.
    """
    if sources is None:
        sources = toutes()
    if a_partir_de is None:
        a_partir_de = minuit_local()

    session = creer_session() if lire_fiches else None
    categorisation = Categorisation(session=session, timeout=timeout)
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
            ev.categorie = categorisation.categoriser(
                ev, source.categorie_defaut, lire_fiche=source.fiche_categorisable
            )
            conserves.append(ev)
        _LOG.info(
            "Salle « %s » : %d événements (%d hors centre-ville écartés).",
            source.nom,
            len(conserves),
            len(evs) - len(conserves),
        )
        evenements.extend(conserves)

    if session is not None:
        session.close()
    if categorisation.fiches_lues:
        _LOG.info("Catégorisation : %d fiches d'événement lues.", categorisation.fiches_lues)
    return finaliser(evenements, a_partir_de)
