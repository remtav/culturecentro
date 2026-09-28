"""Source d'événements : Sporobole (centre en art actuel).

La page https://sporobole.org/programmation/ (WordPress, thème Kadence) ne
contient aucun événement : la liste est injectée par un appel AJAX du thème
(``admin-ajax.php`` / ``standish_select_refresh``) filtrable par type de
contenu (« Diffusions » = ``evenements``, projets, créations, ateliers) et
paginé. Seules les **diffusions** (expositions, lancements, résidences
ouvertes…) portent des dates ; ce sont elles que la source interroge, page
après page, tant que les événements restent en cours ou à venir (la liste
est triée du plus récent au plus ancien).

Chaque bloc ``.standish-single-event`` fournit l'affiche (fond CSS), la
catégorie (``.cpt-subtitle``), le titre et le lien (``h3 a``) et la période
(``.date`` : « Du 02 octobre 2026 au 27 novembre 2026 », « Le 23 octobre
2026 »). Repli JSON-LD de la page si l'appel AJAX échoue.

Utilisation en bibliothèque ::

    from culturecentro.sources.sporobole import lister_evenements_a_venir
    evenements = lister_evenements_a_venir()

En ligne de commande ::

    python -m culturecentro.sources.sporobole --format json
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from culturecentro import cli
from culturecentro.dates import plage_dates_fr
from culturecentro.exporters import exporter_csv, exporter_json  # noqa: F401 (API publique)
from culturecentro.jsonld import extraire_depuis_jsonld
from culturecentro.models import Evenement
from culturecentro.scraping import attribut, premiere_image, url_image
from culturecentro.sources.base import Source

_LOG = logging.getLogger(__name__)

URL_PROGRAMMATION = "https://sporobole.org/programmation/"

#: Type de contenu interrogé (onglet « Diffusions » du filtre).
TYPE_CONTENU = "evenements"

#: Nombre maximal de pages parcourues (garde-fou ; en pratique 1 ou 2).
PAGES_MAX = 6

# var standish_data = {"ajax_url":"https://sporobole.org/wp-admin/admin-ajax.php",…};
_AJAX_URL = re.compile(r'"ajax_url"\s*:\s*"([^"]+admin-ajax\.php)"')


def _url_ajax(page_html: str, url_page: str = URL_PROGRAMMATION) -> str:
    """URL ``admin-ajax.php`` déclarée dans la page (repli : ``/wp-admin/admin-ajax.php``)."""
    m = _AJAX_URL.search(page_html)
    if m:
        return m.group(1).replace("\\/", "/")
    return urljoin(url_page, "/wp-admin/admin-ajax.php")


def _charger_page(
    url_ajax: str, page: int, timeout: float, session: requests.Session
) -> str | None:
    """Fragment HTML d'une page de diffusions, ou ``None`` si l'appel échoue."""
    donnees = {
        "action": "standish_select_refresh",
        "default_status": "",
        "default_categories": "",
        "type[]": TYPE_CONTENU,
        "page": str(page),
    }
    try:
        reponse = session.post(
            url_ajax,
            data=donnees,
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": URL_PROGRAMMATION},
            timeout=timeout,
        )
        reponse.raise_for_status()
        corps: Any = reponse.json()
    except (requests.RequestException, ValueError) as exc:
        _LOG.debug("Appel AJAX Sporobole (page %d) échoué : %s", page, exc)
        return None
    contenu = corps.get("content") if isinstance(corps, dict) else None
    return contenu if isinstance(contenu, str) else None


def _extraire_depuis_fragment(html: str) -> list[Evenement]:
    """Analyse les blocs ``.standish-single-event`` d'un fragment AJAX."""
    soup = BeautifulSoup(html, "html.parser")
    evenements: list[Evenement] = []

    for bloc in soup.select(".standish-single-event"):
        titre_el = bloc.select_one(".title a, h3 a, h3")
        titre = " ".join(titre_el.get_text(" ", strip=True).split()) if titre_el else None
        if not titre:
            continue

        lien_el = bloc.select_one(".title a[href], h3 a[href], a.kt-blocks-post-readmore[href]")
        lien = attribut(lien_el, "href") if lien_el else None

        date_el = bloc.select_one(".date")
        texte_date = " ".join(date_el.get_text(" ", strip=True).split()) if date_el else ""
        debut, fin = plage_dates_fr(texte_date)

        categorie_el = bloc.select_one(".cpt-subtitle")
        categorie = categorie_el.get_text(" ", strip=True) if categorie_el else None

        image = url_image(bloc.select_one(".image")) or premiere_image(bloc)

        evenements.append(
            Evenement(
                titre=titre,
                date_debut=debut,
                date_fin=fin,
                lien=lien,
                sous_titre=categorie or None,
                image=image,
            )
        )
    return evenements


def _a_des_pages_suivantes(html: str, page: int) -> bool:
    """Vrai si la pagination du fragment annonce une page après ``page``."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select(".standish-filters-page[data-page]"):
        try:
            if int(attribut(a, "data-page") or "0") > page:
                return True
        except ValueError:
            continue
    return False


def _encore_actuel(evenements: list[Evenement], seuil: datetime) -> bool:
    """Vrai si le dernier événement daté de la page est encore en cours ou à venir."""
    for ev in reversed(evenements):
        fin = ev.date_fin or ev.date_debut
        if fin is not None:
            return fin >= seuil
    return bool(evenements)  # aucune date : on ne sait pas, on continue


def _extraire_evenements(html: str, timeout: float, session: requests.Session) -> list[Evenement]:
    """Diffusions (AJAX, pages successives), sinon repli JSON-LD."""
    url_ajax = _url_ajax(html)
    seuil = datetime.now() - timedelta(days=1)
    evenements: list[Evenement] = []

    for page in range(1, PAGES_MAX + 1):
        fragment = _charger_page(url_ajax, page, timeout, session)
        if fragment is None:
            if page == 1:
                _LOG.warning("Liste des diffusions Sporobole indisponible (AJAX).")
            else:
                _LOG.warning("Page %d des diffusions indisponible : arrêt.", page)
            break
        de_la_page = _extraire_depuis_fragment(fragment)
        _LOG.debug("Page %d : %d diffusions.", page, len(de_la_page))
        evenements.extend(de_la_page)
        if not de_la_page or not _a_des_pages_suivantes(fragment, page):
            break
        if not _encore_actuel(de_la_page, seuil):
            break  # la suite est plus ancienne encore

    if evenements:
        _LOG.info("Diffusions Sporobole : %d événements.", len(evenements))
        return evenements

    evenements = extraire_depuis_jsonld(html)
    if evenements:
        _LOG.warning("Repli sur les données JSON-LD (%d événements).", len(evenements))
        return evenements

    _LOG.warning("Aucun événement n'a pu être extrait.")
    return []


# --------------------------------------------------------------------------- #
# Source + API module
# --------------------------------------------------------------------------- #
class Sporobole(Source):
    slug = "sporobole"
    nom = "Sporobole"
    url_defaut = URL_PROGRAMMATION

    def extraire(self, html: str, timeout: float, session: requests.Session) -> list[Evenement]:
        return _extraire_evenements(html, timeout, session)


SOURCE = Sporobole()


def lister_evenements_a_venir(
    url: str = URL_PROGRAMMATION,
    *,
    a_partir_de: datetime | None = None,
    timeout: float = 20.0,
) -> list[Evenement]:
    """Raccourci module vers :meth:`Sporobole.lister_evenements_a_venir`."""
    return SOURCE.lister_evenements_a_venir(url, a_partir_de=a_partir_de, timeout=timeout)


def main(argv: Sequence[str] | None = None) -> int:
    return cli.executer(SOURCE, argv)


if __name__ == "__main__":
    raise SystemExit(main())
