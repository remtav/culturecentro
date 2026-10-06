"""Agrégation de la programmation de plusieurs salles.

Interroge chaque source indépendamment, tolère qu'une salle échoue (réseau,
structure modifiée) sans faire échouer les autres, renseigne le partenaire et
le lieu manquant avec le nom de la salle, ramène les lieux à leur nom
canonique, écarte les événements hors du centre-ville, puis déduplique et
trie l'ensemble. Enfin, la catégorie artistique de chaque événement est
déterminée automatiquement (:mod:`culturecentro.categories`).

Une salle en panne réseau est interrogée de nouveau après une attente ; si
elle reste indisponible, ses derniers événements connus (feed précédent) sont
conservés et l'échec est consigné (:class:`Echec`) pour être signalé.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

import requests

from culturecentro.categories import Categorisation
from culturecentro.filtrage import finaliser, minuit_utc
from culturecentro.http import creer_session
from culturecentro.lieux import est_centre_ville, normaliser_lieu
from culturecentro.models import Evenement
from culturecentro.sources import Source, toutes

_LOG = logging.getLogger(__name__)


@dataclass
class Echec:
    """Une salle restée en échec après toutes les tentatives."""

    slug: str
    nom: str
    #: Message de la dernière erreur rencontrée.
    erreur: str
    #: Nombre de tentatives effectuées.
    tentatives: int
    #: Événements repris du feed précédent à la place de ceux de la salle.
    conserves: int = 0


def agreger(
    sources: Iterable[Source] | None = None,
    *,
    a_partir_de: datetime | None = None,
    timeout: float = 20.0,
    lire_fiches: bool = True,
    tentatives: int = 1,
    attente: float = 60.0,
    precedents: Iterable[Evenement] | None = None,
    echecs: list[Echec] | None = None,
) -> list[Evenement]:
    """Agrège les événements à venir de plusieurs salles.

    Args:
        sources: salles à interroger (défaut : toutes celles enregistrées).
        a_partir_de: seuil temporel ; par défaut minuit du jour courant (UTC).
        timeout: délai d'attente réseau par salle, en secondes.
        lire_fiches: lire la fiche des événements dont la catégorie n'a pu
            être déterminée autrement (une requête par fiche).
        tentatives: nombre d'essais au plus pour une salle en panne réseau.
        attente: délai avant le 2e essai, en secondes ; il double ensuite.
        precedents: événements du feed précédent ; ceux d'une salle restée
            en échec sont repris tels quels.
        echecs: liste complétée avec chaque salle restée en échec.

    Returns:
        La liste fusionnée, dédupliquée et triée par date. ``partenaire`` et,
        s'il est absent, ``lieu`` sont renseignés avec le nom de la salle ;
        les lieux sont ramenés à leur nom canonique
        (:func:`~culturecentro.lieux.normaliser_lieu`) et les événements hors
        du centre-ville (:func:`~culturecentro.lieux.est_centre_ville`) sont
        écartés. ``categorie`` est déterminée automatiquement
        (:class:`~culturecentro.categories.Categorisation`) avec, en dernier
        recours, la catégorie par défaut de la salle.

    Une salle qui échoue (``requests.RequestException``) est interrogée de
    nouveau, jusqu'à ``tentatives`` fois ; une erreur d'un autre type
    (structure du site modifiée…) n'est pas réessayée. Une salle restée en
    échec ne fait pas échouer l'agrégation : ses événements de ``precedents``
    sont conservés et l'échec est ajouté à ``echecs``.
    """
    sources = list(toutes() if sources is None else sources)
    if a_partir_de is None:
        a_partir_de = minuit_utc()

    bruts, erreurs, essais = _interroger(sources, a_partir_de, timeout, tentatives, attente)
    precedents = list(precedents or [])

    session = creer_session() if lire_fiches else None
    categorisation = Categorisation(session=session, timeout=timeout)
    evenements: list[Evenement] = []
    for i, source in enumerate(sources):  # ordre du registre : il départage les doublons
        if i not in bruts:
            repris = [ev for ev in precedents if ev.partenaire == source.nom]
            _LOG.warning(
                "Salle « %s » en échec après %d tentative(s) : %d événements repris du feed "
                "précédent.",
                source.nom,
                essais[i],
                len(repris),
            )
            if echecs is not None:
                echecs.append(Echec(source.slug, source.nom, erreurs[i], essais[i], len(repris)))
            evenements.extend(repris)
            continue
        evs = bruts[i]
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


def _interroger(
    sources: list[Source],
    a_partir_de: datetime,
    timeout: float,
    tentatives: int,
    attente: float,
) -> tuple[dict[int, list[Evenement]], dict[int, str], dict[int, int]]:
    """Interroge les salles ; celles en panne réseau sont réessayées après une attente.

    Renvoie, par indice de salle : ses événements bruts (si elle a répondu),
    sa dernière erreur (sinon) et le nombre d'essais effectués.
    """
    bruts: dict[int, list[Evenement]] = {}
    erreurs: dict[int, str] = {}
    essais: dict[int, int] = {}
    a_tenter = list(range(len(sources)))
    for essai in range(1, max(tentatives, 1) + 1):
        if essai > 1:
            delai = attente * 2 ** (essai - 2)
            _LOG.warning(
                "%d salle(s) en panne réseau : nouvel essai (%d/%d) dans %.0f s.",
                len(a_tenter),
                essai,
                tentatives,
                delai,
            )
            time.sleep(delai)
        en_panne: list[int] = []
        for i in a_tenter:
            source = sources[i]
            essais[i] = essai
            try:
                bruts[i] = source.lister_evenements_a_venir(
                    a_partir_de=a_partir_de, timeout=timeout
                )
            except requests.RequestException as exc:
                _LOG.warning(
                    "Salle « %s » indisponible (essai %d/%d) : %s",
                    source.nom,
                    essai,
                    tentatives,
                    exc,
                )
                erreurs[i] = str(exc)
                en_panne.append(i)
            except Exception as exc:  # structure modifiée, bogue d'extraction : pas de reprise
                _LOG.exception("Salle « %s » : échec de l'extraction.", source.nom)
                erreurs[i] = f"{type(exc).__name__} : {exc}"
        a_tenter = en_panne
        if not a_tenter:
            break
    return bruts, erreurs, essais
