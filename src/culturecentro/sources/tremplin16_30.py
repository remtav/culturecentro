"""Source d'événements : Le Tremplin 16-30.

La page https://tremplin16-30.com/evenements/ (WordPress, blocs Gutenberg)
liste les événements à venir sous forme de blocs « média + texte »
(``.wp-block-media-text``) : un titre ``h2``, une ``figure`` dont l'image est
un fond CSS, puis des paragraphes ``p.event-data`` — le premier porte la ou
les dates, le second le lieu, le suivant le tarif — et un bouton
« Plus d'infos » (``a.more-info``) vers la fiche.

Les dates sont libres et souvent **sans année** (celle-ci figure alors dans le
titre : « automne 2026 ») :

* « Mardi 29 septembre 2026 - 17h » → un événement ;
* « Jeudis 17 septembre, 29 octobre, 26 novembre et 17 décembre - 18h30 à
  20h30 » → **un événement par date** (même titre, même lien) ;
* « Tous les mercredis du 9 septembre au 16 décembre - 18h30 à 20h30 » → un
  événement avec ``date_debut`` et ``date_fin``.

L'année manquante est prise dans le titre, sinon dans l'année de la page
(argument ``annee_defaut``, par défaut l'année courante), avec passage à
l'année suivante si la date est déjà loin derrière. Repli JSON-LD si aucun
bloc n'est trouvé.

Utilisation en bibliothèque ::

    from culturecentro.sources.tremplin16_30 import lister_evenements_a_venir
    evenements = lister_evenements_a_venir()

En ligne de commande ::

    python -m culturecentro.sources.tremplin16_30 --format json
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup, Tag

from culturecentro import cli
from culturecentro.dates import parse_heure_fr, plage_dates_fr, trouver_dates_fr
from culturecentro.exporters import exporter_csv, exporter_json  # noqa: F401 (API publique)
from culturecentro.jsonld import extraire_depuis_jsonld
from culturecentro.models import Evenement
from culturecentro.scraping import attribut, premiere_image, url_image
from culturecentro.sources.base import Source

_LOG = logging.getLogger(__name__)

URL_EVENEMENTS = "https://tremplin16-30.com/evenements/"

#: Une date sans année, antérieure de plus de ce délai à aujourd'hui, est
#: reportée à l'année suivante (la page ne liste que l'actualité).
_TOLERANCE_PASSE = timedelta(days=120)

_ANNEE = re.compile(r"\b(20\d{2})\b")
_PLAGE = re.compile(r"\bdu\s+\d{1,2}\s*(?:er)?\s+\S+\s+au\s+\d{1,2}", re.IGNORECASE)


def _annee_du_titre(titre: str) -> int | None:
    m = _ANNEE.search(titre)
    return int(m.group(1)) if m else None


def _ajuster_annee(date: datetime, sans_annee: bool, aujourdhui: datetime) -> datetime:
    """Reporte à l'année suivante une date sans année déjà loin dans le passé."""
    if sans_annee and date < aujourdhui - _TOLERANCE_PASSE:
        return date.replace(year=date.year + 1)
    return date


def _dates_du_bloc(
    texte: str, titre: str, aujourdhui: datetime
) -> list[tuple[datetime | None, datetime | None]]:
    """Les couples ``(debut, fin)`` décrits par le paragraphe de dates.

    Une liste de dates (« 17 septembre, 29 octobre… ») donne un couple par
    date ; une plage (« du 9 septembre au 16 décembre ») un seul couple avec
    fin ; une date simple un seul couple sans fin.
    """
    sans_annee = not _ANNEE.search(texte)
    annee = _annee_du_titre(titre) or aujourdhui.year
    heure = parse_heure_fr(texte.split("-", 1)[1] if "-" in texte else "")

    if _PLAGE.search(texte):
        debut, fin = plage_dates_fr(texte, annee)
        if debut is None:
            return []
        debut = _ajuster_annee(debut, sans_annee, aujourdhui)
        if fin is not None:
            fin = _ajuster_annee(fin, sans_annee, aujourdhui)
            if fin < debut:
                fin = fin.replace(year=fin.year + 1)
        return [(debut, fin)]

    dates = trouver_dates_fr(texte, annee)
    if not dates:
        return []
    resultat: list[tuple[datetime | None, datetime | None]] = []
    for date in dates:
        date = _ajuster_annee(date, sans_annee, aujourdhui)
        if heure is not None:
            date = date.replace(hour=heure[0], minute=heure[1])
        resultat.append((date, None))
    return resultat


def _extraire_depuis_blocs(html: str, aujourdhui: datetime | None = None) -> list[Evenement]:
    """Analyse les blocs « média + texte » de la page des événements."""
    aujourdhui = aujourdhui or datetime.now()
    soup = BeautifulSoup(html, "html.parser")
    evenements: list[Evenement] = []

    for bloc in soup.select(".wp-block-media-text"):
        titre_el = bloc.select_one("h1, h2, h3")
        titre = titre_el.get_text(" ", strip=True) if titre_el else None
        if not titre:
            continue

        donnees = [
            " ".join(p.get_text(" ", strip=True).split()) for p in bloc.select("p.event-data")
        ]
        donnees = [d for d in donnees if d]
        texte_dates = donnees[0] if donnees else ""
        lieu = _lieu(bloc, donnees)

        lien_el = bloc.select_one("a.more-info[href]") or bloc.select_one("a[href*='/evenements/']")
        lien = attribut(lien_el, "href") if lien_el else None

        image = url_image(bloc.select_one("figure")) or premiere_image(bloc)

        couples = _dates_du_bloc(texte_dates, titre, aujourdhui) or [(None, None)]
        for debut, fin in couples:
            evenements.append(
                Evenement(
                    titre=titre,
                    date_debut=debut,
                    date_fin=fin,
                    lien=lien,
                    lieu=lieu,
                    sous_titre=texte_dates or None,
                    image=image,
                )
            )

    return evenements


def _lieu(bloc: Tag, donnees: list[str]) -> str | None:
    """Le lieu : le paragraphe portant un lien de carte, sinon le deuxième."""
    for p in bloc.select("p.event-data"):
        lien = p.select_one("a[href*='maps'], a[href*='goo.gl']")
        if lien:
            texte = str(lien.get_text(" ", strip=True))
            if texte:
                return texte
    return donnees[1] if len(donnees) > 1 else None


def _extraire_evenements(html: str, timeout: float, session: requests.Session) -> list[Evenement]:
    """Blocs de la page, sinon repli JSON-LD."""
    evenements = _extraire_depuis_blocs(html)
    if evenements:
        _LOG.info("Page des événements analysée : %d événements.", len(evenements))
        return evenements

    evenements = extraire_depuis_jsonld(html)
    if evenements:
        _LOG.warning("Repli sur les données JSON-LD (%d événements).", len(evenements))
        return evenements

    _LOG.warning("Aucun événement n'a pu être extrait de la page.")
    return []


# --------------------------------------------------------------------------- #
# Source + API module
# --------------------------------------------------------------------------- #
class Tremplin1630(Source):
    slug = "tremplin-16-30"
    nom = "Le Tremplin 16-30"
    url_defaut = URL_EVENEMENTS

    def extraire(self, html: str, timeout: float, session: requests.Session) -> list[Evenement]:
        return _extraire_evenements(html, timeout, session)


SOURCE = Tremplin1630()


def lister_evenements_a_venir(
    url: str = URL_EVENEMENTS,
    *,
    a_partir_de: datetime | None = None,
    timeout: float = 20.0,
) -> list[Evenement]:
    """Raccourci module vers :meth:`Tremplin1630.lister_evenements_a_venir`."""
    return SOURCE.lister_evenements_a_venir(url, a_partir_de=a_partir_de, timeout=timeout)


def main(argv: Sequence[str] | None = None) -> int:
    return cli.executer(SOURCE, argv)


if __name__ == "__main__":
    raise SystemExit(main())
