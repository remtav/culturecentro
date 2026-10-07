"""Finalisation d'une liste d'événements : dédup, filtrage et tri.

Partagé par les sources (sur leur propre liste) et par l'agrégation (sur la
liste fusionnée de toutes les salles). Sur la liste fusionnée, un même
spectacle annoncé par deux partenaires (l'un le présente, l'autre
l'accueille) est ramené à un seul événement : voir :func:`fusionner_doublons`.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from culturecentro.lieux import cle
from culturecentro.models import Evenement

_LOG = logging.getLogger(__name__)

#: Mots ignorés pour comparer deux titres.
_MOTS_VIDES = frozenset(
    "le la les de du des et au aux en un une pour par avec sur the of and".split()
)


#: Fuseau des salles. Les dates « naïves » des sources sont des heures locales.
FUSEAU = ZoneInfo("America/Toronto")


def minuit_local(maintenant: datetime | None = None) -> datetime:
    """Minuit du jour courant à Sherbrooke (seuil « jour courant ou futur »).

    Le seuil suit le fuseau des salles, comme les dates des sources : en UTC,
    le soir (dès 20 h en heure d'été), le jour serait déjà le lendemain et les
    spectacles du soir même seraient écartés. ``maintenant`` (avec fuseau)
    remplace l'heure courante, pour les tests.
    """
    local = (maintenant or datetime.now(FUSEAU)).astimezone(FUSEAU)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def _en_aware(date: datetime) -> datetime:
    """Date « naïve » supposée en heure locale (:data:`FUSEAU`), pour les comparaisons."""
    return date if date.tzinfo is not None else date.replace(tzinfo=FUSEAU)


def _mots(titre: str) -> frozenset[str]:
    """Mots significatifs d'un titre (sans casse, accents, ponctuation ni mots vides)."""
    return frozenset(
        mot
        for mot in re.findall(r"[a-z0-9]+", cle(titre))
        if (len(mot) > 1 or mot.isdigit()) and mot not in _MOTS_VIDES
    )


def _a_une_heure(ev: Evenement) -> bool:
    """Vrai si l'heure de début est connue (minuit = date seule)."""
    return ev.date_debut is not None and ev.date_debut.time() != time(0, 0)


def _s_etale(ev: Evenement) -> bool:
    """Vrai pour ce qui dure plusieurs jours (exposition, série…)."""
    return (
        ev.date_debut is not None
        and ev.date_fin is not None
        and _en_aware(ev.date_fin) - _en_aware(ev.date_debut) >= timedelta(days=1)
    )


def sont_doublons(a: Evenement, b: Evenement) -> bool:
    """Vrai si deux partenaires annoncent le même événement.

    Il faut, à la fois :

    * deux partenaires différents (un partenaire qui annonce deux fois le même
      titre le même jour donne deux représentations, à garder) ;
    * le même jour et la même heure de début, ou une heure inconnue (minuit)
      d'un côté ;
    * la même nature : deux représentations ponctuelles, ou deux événements
      qui s'étalent sur plusieurs jours (une soirée n'est pas fondue dans
      l'exposition ou la série du même nom) ;
    * des titres compatibles : les mots significatifs de l'un figurent tous
      dans l'autre (« Maxime Gervais » / « Maxime Gervais : C'était
      magnifique »).
    """
    if a.partenaire == b.partenaire or a.date_debut is None or b.date_debut is None:
        return False
    if a.date_debut.date() != b.date_debut.date():
        return False
    if _a_une_heure(a) and _a_une_heure(b) and a.date_debut.time() != b.date_debut.time():
        return False
    if _s_etale(a) != _s_etale(b):
        return False
    mots_a, mots_b = _mots(a.titre), _mots(b.titre)
    return bool(mots_a and mots_b) and (mots_a <= mots_b or mots_b <= mots_a)


def _richesse(ev: Evenement) -> tuple[int, int]:
    """Quantité d'information d'un événement : champs renseignés, puis longueur du texte."""
    champs = sum(v is not None for v in (ev.sous_titre, ev.date_fin, ev.image, ev.lien))
    return champs + _a_une_heure(ev), len(ev.titre) + len(ev.sous_titre or "")


def fusionner(a: Evenement, b: Evenement) -> Evenement:
    """Un seul événement à partir de deux annonces du même spectacle.

    L'annonce la plus complète (:func:`_richesse` ; à égalité, la première)
    est conservée : son partenaire, son lieu, son lien et sa catégorie font
    foi. Elle est complétée par ce que seule l'autre apporte : le titre le
    plus complet (celui dont les mots englobent ceux de l'autre),
    l'heure de début si elle lui manque, et le sous-titre, la fin ou
    l'affiche absents.
    """
    garde, autre = (a, b) if _richesse(a) >= _richesse(b) else (b, a)
    titre = autre.titre if _mots(garde.titre) < _mots(autre.titre) else garde.titre
    heure_manquante = _a_une_heure(autre) and not _a_une_heure(garde)
    debut = autre.date_debut if heure_manquante else garde.date_debut
    return replace(
        garde,
        titre=titre,
        date_debut=debut,
        sous_titre=garde.sous_titre or autre.sous_titre,
        date_fin=garde.date_fin or autre.date_fin,
        image=garde.image or autre.image,
        lien=garde.lien or autre.lien,
    )


def fusionner_doublons(evenements: Sequence[Evenement]) -> list[Evenement]:
    """Ramène à un seul événement ce que plusieurs partenaires annoncent.

    Un spectacle peut figurer sur la page du partenaire qui le présente et sur
    celle du partenaire qui l'accueille (le Granada annonce les spectacles
    qu'il présente à La Petite Boîte Noire, la Maison des arts de la parole
    ceux de son festival au Grand-Espace…). Les doublons (:func:`sont_doublons`)
    sont fusionnés (:func:`fusionner`) ; l'ordre des autres est conservé.
    """
    resultat: list[Evenement] = []
    for ev in evenements:
        for i, deja in enumerate(resultat):
            if sont_doublons(deja, ev):
                resultat[i] = fusionner(deja, ev)
                _LOG.info(
                    "Doublon fusionné : « %s » (%s) et « %s » (%s), le %s.",
                    deja.titre,
                    deja.partenaire,
                    ev.titre,
                    ev.partenaire,
                    ev.date_debut.date() if ev.date_debut else "?",
                )
                break
        else:
            resultat.append(ev)
    return resultat


def finaliser(evenements: Sequence[Evenement], a_partir_de: datetime) -> list[Evenement]:
    """Déduplique, filtre les événements à venir et trie par date.

    Les doublons exacts (titre + date) sont retirés, puis ce que plusieurs
    partenaires annoncent est fusionné (:func:`fusionner_doublons`). Un
    événement est « à venir » si son début est postérieur au seuil **ou**
    s'il est encore en cours (``date_fin`` postérieure au seuil : exposition,
    série…) ; une fin connue et passée l'exclut même sans date de début. Les
    événements sans aucune date connue sont conservés et triés en fin de liste.
    """
    vus: set[tuple[str, str]] = set()
    uniques: list[Evenement] = []
    for ev in evenements:
        cle_ev = (ev.titre, ev.date_debut.isoformat() if ev.date_debut else "")
        if cle_ev not in vus:
            vus.add(cle_ev)
            uniques.append(ev)
    uniques = fusionner_doublons(uniques)

    def _est_a_venir(ev: Evenement) -> bool:
        if ev.date_fin is not None:
            # Fin connue : conservé tant qu'elle n'est pas passée (même si le
            # début l'est déjà, ou est inconnu — « jusqu'en octobre »).
            return _en_aware(ev.date_fin) >= a_partir_de
        if ev.date_debut is None:
            return True  # date inconnue : on ne l'exclut pas
        return _en_aware(ev.date_debut) >= a_partir_de

    lointain = datetime.max.replace(tzinfo=timezone.utc)  # trie les dates inconnues en fin

    a_venir = [ev for ev in uniques if _est_a_venir(ev)]
    a_venir.sort(key=lambda ev: _en_aware(ev.date_debut) if ev.date_debut else lointain)
    return a_venir
