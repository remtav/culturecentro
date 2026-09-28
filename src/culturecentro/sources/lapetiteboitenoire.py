"""Source d'événements : La Petite Boîte Noire.

La page https://lapetiteboitenoire.com/evenements/ n'affiche pas elle-même les
spectacles : ils sont injectés par un widget de la billetterie
`Lepointdevente.com <https://lepointdevente.com>`_. On découvre l'URL de la
liste Lepointdevente dans la page (lien « Programmation complète » ou, à
défaut, ``widget.js``), puis on télécharge et analyse cette liste — chaque
carte ``.feature-col[data-tpos-event]`` donne titre, date, lieu et affiche ;
le lien de la fiche est reconstruit à partir de l'identifiant.

Si la découverte échoue, on retombe sur l'URL de billetterie connue, puis sur
les données schema.org ``Event`` (JSON-LD) de la page. Chaque repli émet un
avertissement via ``logging``.

Utilisation en bibliothèque ::

    from culturecentro.sources.lapetiteboitenoire import lister_evenements_a_venir
    evenements = lister_evenements_a_venir()

En ligne de commande ::

    python -m culturecentro.sources.lapetiteboitenoire --format json
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from culturecentro import cli
from culturecentro.dates import parse_date_fr  # noqa: F401 (réexport pratique)
from culturecentro.exporters import exporter_csv, exporter_json  # noqa: F401 (API publique)
from culturecentro.http import telecharger
from culturecentro.jsonld import extraire_depuis_jsonld
from culturecentro.models import Evenement
from culturecentro.scraping import attribut
from culturecentro.sources.base import Source

_LOG = logging.getLogger(__name__)

URL_EVENEMENTS = "https://lapetiteboitenoire.com/evenements/"

#: URL de secours de la liste Lepointdevente, si on ne parvient pas à la
#: découvrir dans la page (``group=6603`` = La Petite Boîte Noire).
URL_BILLETTERIE_DEFAUT = "https://lepointdevente.com/billets/programmationavenir"


# --------------------------------------------------------------------------- #
# Découverte de la liste Lepointdevente
# --------------------------------------------------------------------------- #
def _trouver_url_billetterie(page_html: str, timeout: float, session: requests.Session) -> str:
    """Découvre l'URL de la liste Lepointdevente dans la page ``evenements``.

    Renvoie l'URL de la page ``/billets/<slug>``. Si rien n'est trouvé, on
    retombe sur :data:`URL_BILLETTERIE_DEFAUT`.
    """
    soup = BeautifulSoup(page_html, "html.parser")

    # 1. Un lien direct vers la liste (« Programmation complète »).
    for lien in soup.find_all("a", href=True):
        href = attribut(lien, "href")
        if href and "lepointdevente.com/billets/" in href:
            return href.split("?", 1)[0]

    # 2. Le widget : on lit ``widget.js`` pour en extraire l'URL de l'iframe.
    for balise in soup.find_all("script", src=True):
        src = attribut(balise, "src")
        if not src or "lepointdevente.com/plugins/widget.js" not in src:
            continue
        try:
            script = telecharger(src, timeout, session=session)
        except requests.RequestException as exc:
            _LOG.debug("Téléchargement de widget.js échoué : %s", exc)
            continue
        # document.write('<iframe … src="https://…/billets/<slug>?…" …>')
        m = re.search(r'https://lepointdevente\.com/billets/[^"?&\']+', script)
        if m:
            return m.group(0)

    _LOG.warning(
        "URL de la billetterie introuvable dans la page : repli sur %s.",
        URL_BILLETTERIE_DEFAUT,
    )
    return URL_BILLETTERIE_DEFAUT


# --------------------------------------------------------------------------- #
# Extraction Lepointdevente (source principale) + repli
# --------------------------------------------------------------------------- #
def _extraire_depuis_lepointdevente(html: str, url_base: str) -> list[Evenement]:
    """Analyse la liste de spectacles d'une page Lepointdevente."""
    soup = BeautifulSoup(html, "html.parser")
    evenements: list[Evenement] = []

    for item in soup.select(".feature-col[data-tpos-event]"):
        titre_el = item.select_one(".feature-title")
        titre = titre_el.get_text(" ", strip=True) if titre_el else None
        if not titre:
            continue

        date_el = item.select_one(".feature-date")
        date_debut = parse_date_fr(date_el.get_text(" ", strip=True)) if date_el else None

        lieu_el = item.select_one(".feature-city")
        lieu = lieu_el.get_text(" ", strip=True) if lieu_el else None

        # L'affiche : <img itemprop="image" src="..."> (repli sur toute <img>).
        img_el = item.select_one("img[itemprop=image]") or item.select_one("img")
        image = attribut(img_el, "src") if img_el else None

        # Pas d'ancre dans la carte : le lien de la fiche se reconstruit à
        # partir de l'identifiant ``data-tpos-event`` (ex. .../<slug>/529998).
        event_id = attribut(item, "data-tpos-event")
        lien = urljoin(url_base.rstrip("/") + "/", event_id) if event_id else None

        evenements.append(
            Evenement(titre=titre, date_debut=date_debut, image=image, lien=lien, lieu=lieu)
        )

    return evenements


def _extraire_evenements(html: str, timeout: float, session: requests.Session) -> list[Evenement]:
    """Choisit la meilleure source disponible et renvoie les événements bruts."""
    url_billetterie = _trouver_url_billetterie(html, timeout, session)
    try:
        liste_html = telecharger(url_billetterie, timeout, session=session)
    except requests.RequestException as exc:
        _LOG.warning("Téléchargement de la liste Lepointdevente échoué : %s", exc)
        liste_html = None

    if liste_html:
        evenements = _extraire_depuis_lepointdevente(liste_html, url_billetterie)
        if evenements:
            _LOG.info("Liste Lepointdevente analysée : %d événements.", len(evenements))
            return evenements
        _LOG.warning("Aucun événement dans la liste Lepointdevente (structure modifiée ?).")

    # Repli : données structurées de la page « evenements » elle-même.
    evenements = extraire_depuis_jsonld(html)
    if evenements:
        _LOG.warning("Repli sur les données JSON-LD de la page (%d événements).", len(evenements))
        return evenements

    _LOG.warning("Aucun événement n'a pu être extrait.")
    return []


# --------------------------------------------------------------------------- #
# Source + API module
# --------------------------------------------------------------------------- #
class LaPetiteBoiteNoire(Source):
    slug = "la-petite-boite-noire"
    nom = "La Petite Boîte Noire"
    url_defaut = URL_EVENEMENTS

    def extraire(self, html: str, timeout: float, session: requests.Session) -> list[Evenement]:
        return _extraire_evenements(html, timeout, session)


SOURCE = LaPetiteBoiteNoire()


def lister_evenements_a_venir(
    url: str = URL_EVENEMENTS,
    *,
    a_partir_de: datetime | None = None,
    timeout: float = 20.0,
) -> list[Evenement]:
    """Raccourci module vers :meth:`LaPetiteBoiteNoire.lister_evenements_a_venir`."""
    return SOURCE.lister_evenements_a_venir(url, a_partir_de=a_partir_de, timeout=timeout)


def main(argv: Sequence[str] | None = None) -> int:
    return cli.executer(SOURCE, argv)


if __name__ == "__main__":
    raise SystemExit(main())
