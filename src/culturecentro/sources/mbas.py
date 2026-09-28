"""Source d'événements : Musée des beaux-arts de Sherbrooke (MBAS).

Le site https://mbas.qc.ca (WordPress, blocs Gutenberg) présente ses
expositions sur deux pages : `En cours <https://mbas.qc.ca/en-cours/>`_ et
`À venir <https://mbas.qc.ca/a-venir/>`_. Chaque exposition est un bloc
``div#rectangle`` (identifiant répété) : affiche ``img``, titre ``h2``, un
paragraphe « type + période » (« EXPOSITION TEMPORAIRE / 15 octobre 2026 au
21 mars 2027 », « EXPO-VENTE / Jusqu'en octobre 2026 », « EXPOSITION
PERMANENTE »), parfois un sous-titre, et un bouton « En savoir plus ».

La source télécharge les deux pages et fusionne leurs blocs. Les périodes
donnent ``date_debut`` et ``date_fin`` (une exposition déjà commencée reste
listée tant qu'elle n'est pas terminée) ; une exposition permanente n'a pas
de date. Repli JSON-LD si aucun bloc n'est trouvé.

Utilisation en bibliothèque ::

    from culturecentro.sources.mbas import lister_evenements_a_venir
    evenements = lister_evenements_a_venir()

En ligne de commande ::

    python -m culturecentro.sources.mbas --format json
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import datetime

import requests
from bs4 import BeautifulSoup, Tag

from culturecentro import cli
from culturecentro.dates import plage_dates_fr
from culturecentro.exporters import exporter_csv, exporter_json  # noqa: F401 (API publique)
from culturecentro.http import telecharger
from culturecentro.jsonld import extraire_depuis_jsonld
from culturecentro.models import Evenement
from culturecentro.scraping import attribut, premiere_image, url_image
from culturecentro.sources.base import Source

_LOG = logging.getLogger(__name__)

URL_EN_COURS = "https://mbas.qc.ca/en-cours/"
URL_A_VENIR = "https://mbas.qc.ca/a-venir/"

#: Pages analysées, dans l'ordre : la page par défaut (« en cours ») puis
#: les pages supplémentaires téléchargées par la source.
URLS_SUPPLEMENTAIRES = (URL_A_VENIR,)

# Ligne « type d'exposition » : tout en capitales, commence par EXPO.
_TYPE_EXPO = re.compile(r"^EXPO[\w' ’\-]*$")


def _lignes(bloc: Tag) -> list[str]:
    """Les lignes de texte des paragraphes du bloc (``<br>`` = saut de ligne)."""
    lignes: list[str] = []
    for p in bloc.select("p"):
        for br in p.find_all("br"):
            br.replace_with("\n")
        for morceau in p.get_text("").split("\n"):
            texte = " ".join(morceau.split())
            if texte:
                lignes.append(texte)
    return lignes


def _extraire_depuis_blocs(html: str) -> list[Evenement]:
    """Analyse les blocs ``#rectangle`` d'une page d'expositions."""
    soup = BeautifulSoup(html, "html.parser")
    evenements: list[Evenement] = []

    for bloc in soup.select("div[id=rectangle]"):
        titre_el = bloc.select_one("h1, h2, h3")
        titre = " ".join(titre_el.get_text(" ", strip=True).split()) if titre_el else None
        if not titre:
            continue

        lignes = _lignes(bloc)
        type_expo = next((ligne for ligne in lignes if _TYPE_EXPO.match(ligne)), None)
        periode = None
        sous_titre = None
        for i, ligne in enumerate(lignes):
            if ligne == type_expo:
                continue
            debut, fin = plage_dates_fr(ligne)
            if periode is None and (debut or fin):
                periode = (debut, fin)
                continue
            # Le premier texte court hors type/période : sous-titre (thème,
            # artiste invité). Les paragraphes de description sont des phrases
            # (ponctuation finale) et sont plus longs.
            if (
                sous_titre is None
                and i < 4
                and len(ligne) <= 90
                and ligne != titre
                and not ligne.endswith((".", "…", "!", "?"))
            ):
                sous_titre = ligne
        debut, fin = periode or (None, None)

        lien_el = bloc.select_one("a.su-button[href]") or bloc.select_one("a[href]")
        lien = attribut(lien_el, "href") if lien_el else None

        image = url_image(bloc.select_one("img")) or premiere_image(bloc)

        evenements.append(
            Evenement(
                titre=titre,
                date_debut=debut,
                date_fin=fin,
                lien=lien,
                sous_titre=sous_titre or (type_expo.capitalize() if type_expo else None),
                image=image,
                categorie="arts",  # un musée : expositions
            )
        )

    return evenements


def _extraire_evenements(html: str, timeout: float, session: requests.Session) -> list[Evenement]:
    """Blocs de la page par défaut + pages supplémentaires, sinon repli JSON-LD."""
    evenements = _extraire_depuis_blocs(html)
    _LOG.info("Page « en cours » : %d expositions.", len(evenements))

    for url in URLS_SUPPLEMENTAIRES:
        try:
            page = telecharger(url, timeout, session=session)
        except requests.RequestException as exc:
            _LOG.warning("Téléchargement de %s échoué : %s", url, exc)
            continue
        supplement = _extraire_depuis_blocs(page)
        _LOG.info("Page %s : %d expositions.", url, len(supplement))
        evenements.extend(supplement)

    if evenements:
        return evenements

    evenements = extraire_depuis_jsonld(html)
    if evenements:
        _LOG.warning("Repli sur les données JSON-LD (%d événements).", len(evenements))
        return evenements

    _LOG.warning("Aucune exposition n'a pu être extraite.")
    return []


# --------------------------------------------------------------------------- #
# Source + API module
# --------------------------------------------------------------------------- #
class MuseeDesBeauxArts(Source):
    slug = "mbas"
    nom = "Musée des beaux-arts de Sherbrooke"
    url_defaut = URL_EN_COURS
    categorie_defaut = "arts"
    description = "Liste les expositions en cours et à venir du Musée des beaux-arts de Sherbrooke."

    def extraire(self, html: str, timeout: float, session: requests.Session) -> list[Evenement]:
        return _extraire_evenements(html, timeout, session)


SOURCE = MuseeDesBeauxArts()


def lister_evenements_a_venir(
    url: str = URL_EN_COURS,
    *,
    a_partir_de: datetime | None = None,
    timeout: float = 20.0,
) -> list[Evenement]:
    """Raccourci module vers :meth:`MuseeDesBeauxArts.lister_evenements_a_venir`."""
    return SOURCE.lister_evenements_a_venir(url, a_partir_de=a_partir_de, timeout=timeout)


def main(argv: Sequence[str] | None = None) -> int:
    return cli.executer(SOURCE, argv)


if __name__ == "__main__":
    raise SystemExit(main())
