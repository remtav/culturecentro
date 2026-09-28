"""Source d'événements : Le Grand-Espace (Centre des arts de la scène Jean-Besré).

Le site https://legrandespace.ca (WordPress) publie sa programmation par
**public** et par **édition** (saison) : ``/public/grand-public/`` et
``/public/jeune-public/``, avec un paramètre ``?edition=2026-2027``. Chaque
page contient d'abord un sélecteur de billetterie (liste de tous les
spectacles, liens ``#``) puis la liste proprement dite
(``.liste_spectacle_block``) : des blocs ``.spectacle`` avec l'affiche
(``img.product_image``), le genre (``.subtitle_spectacle`` ou
``.sous_titre_spectacle``), le titre, la compagnie et la date de
représentation (``.tuxedo--representation__date`` : « 18 octobre 2026 10 h
00 », « Du 7 au 17 octobre 2026 », « Du 29 octobre 2026 au 28 mai 2027 »,
« [Terminé] »).

La source télécharge les deux publics de l'édition en cours (déduite de la
date : la saison commence en août) et fusionne les listes ; les spectacles
terminés sont ignorés. Repli JSON-LD si aucun bloc n'est trouvé.

Utilisation en bibliothèque ::

    from culturecentro.sources.legrandespace import lister_evenements_a_venir
    evenements = lister_evenements_a_venir()

En ligne de commande ::

    python -m culturecentro.sources.legrandespace --format json
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date, datetime

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

URL_GRAND_PUBLIC = "https://legrandespace.ca/public/grand-public/"
URL_JEUNE_PUBLIC = "https://legrandespace.ca/public/jeune-public/"

#: Mois (inclus) à partir duquel une nouvelle saison commence.
_MOIS_DEBUT_SAISON = 8


def edition_courante(aujourdhui: date | None = None) -> str:
    """Nom de l'édition en cours (« 2026-2027 »), la saison débutant en août."""
    aujourdhui = aujourdhui or date.today()
    debut = aujourdhui.year if aujourdhui.month >= _MOIS_DEBUT_SAISON else aujourdhui.year - 1
    return f"{debut}-{debut + 1}"


def url_edition(url_public: str, edition: str | None = None) -> str:
    """URL d'une page de public pour une édition donnée (défaut : en cours)."""
    return f"{url_public}?edition={edition or edition_courante()}"


def _sous_titre(bloc: Tag) -> str | None:
    """Genre (« Théâtre », « Spectacle de conte ») et compagnie, séparés par un tiret."""
    genre_el = bloc.select_one(".subtitle_spectacle") or bloc.select_one(".sous_titre_spectacle")
    compagnie_el = bloc.select_one(".compagnie_spectacle")
    morceaux = [
        " ".join(el.get_text(" ", strip=True).split())
        for el in (genre_el, compagnie_el)
        if el is not None
    ]
    morceaux = [m for m in morceaux if m]
    return " — ".join(morceaux) if morceaux else None


def _extraire_depuis_liste(html: str, categorie: str | None = None) -> list[Evenement]:
    """Analyse les blocs ``.spectacle`` de la liste (ceux qui ont un vrai lien).

    ``categorie`` est attribuée à tous les spectacles de la page (ex. la page
    « jeune public » donne ``"jeunesse"``).
    """
    soup = BeautifulSoup(html, "html.parser")
    conteneur = soup.select_one(".liste_spectacle_block") or soup
    evenements: list[Evenement] = []

    for bloc in conteneur.select(".spectacle"):
        lien_el = bloc.select_one("a.cover_link[href]") or bloc.select_one("a[href]")
        lien = attribut(lien_el, "href") if lien_el else None
        if not lien or lien.strip() == "#":
            continue  # sélecteur de billetterie (doublon sans fiche)

        titre_el = bloc.select_one(".titre_spectacle")
        titre = " ".join(titre_el.get_text(" ", strip=True).split()) if titre_el else None
        if not titre:
            continue

        textes_dates = [
            " ".join(el.get_text(" ", strip=True).split())
            for el in bloc.select(".tuxedo--representation__date")
        ]
        if any("terminé" in t.lower() for t in textes_dates):
            continue

        sous_titre = _sous_titre(bloc)
        image = url_image(bloc.select_one("img.product_image")) or premiere_image(bloc)

        couples = [plage_dates_fr(t) for t in textes_dates if t] or [(None, None)]
        for debut, fin in couples:
            evenements.append(
                Evenement(
                    titre=titre,
                    date_debut=debut,
                    date_fin=fin,
                    lien=lien,
                    sous_titre=sous_titre,
                    image=image,
                    categorie=categorie,
                )
            )

    return evenements


def _extraire_evenements(html: str, timeout: float, session: requests.Session) -> list[Evenement]:
    """Grand public (page par défaut) + jeune public (catégorie « jeunesse »), sinon JSON-LD."""
    evenements = _extraire_depuis_liste(html)
    _LOG.info("Grand public : %d spectacles.", len(evenements))

    url_jeune = url_edition(URL_JEUNE_PUBLIC)
    try:
        page = telecharger(url_jeune, timeout, session=session)
    except requests.RequestException as exc:
        _LOG.warning("Téléchargement de %s échoué : %s", url_jeune, exc)
    else:
        jeune = _extraire_depuis_liste(page, categorie="jeunesse")
        _LOG.info("Jeune public : %d spectacles.", len(jeune))
        evenements.extend(jeune)

    if evenements:
        return evenements

    evenements = extraire_depuis_jsonld(html)
    if evenements:
        _LOG.warning("Repli sur les données JSON-LD (%d événements).", len(evenements))
        return evenements

    _LOG.warning("Aucun spectacle n'a pu être extrait.")
    return []


# --------------------------------------------------------------------------- #
# Source + API module
# --------------------------------------------------------------------------- #
class LeGrandEspace(Source):
    slug = "le-grand-espace"
    nom = "Le Grand-Espace"
    categorie_defaut = "theatre"
    description = "Liste les spectacles à venir du Grand-Espace (grand public et jeune public)."

    @property
    def url_defaut(self) -> str:  # type: ignore[override]
        """Page « grand public » de l'édition en cours (calculée à l'appel)."""
        return url_edition(URL_GRAND_PUBLIC)

    def extraire(self, html: str, timeout: float, session: requests.Session) -> list[Evenement]:
        return _extraire_evenements(html, timeout, session)


SOURCE = LeGrandEspace()


def lister_evenements_a_venir(
    url: str | None = None,
    *,
    a_partir_de: datetime | None = None,
    timeout: float = 20.0,
) -> list[Evenement]:
    """Raccourci module vers :meth:`LeGrandEspace.lister_evenements_a_venir`."""
    return SOURCE.lister_evenements_a_venir(url, a_partir_de=a_partir_de, timeout=timeout)


def main(argv: Sequence[str] | None = None) -> int:
    return cli.executer(SOURCE, argv)


if __name__ == "__main__":
    raise SystemExit(main())
