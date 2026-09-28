"""Source d'événements : Théâtre Granada.

Le site https://theatregranada.com est un WordPress construit avec WPBakery
Page Builder. La page de programmation affiche ses événements dans une grille
« vc_basic_grid » en mode « lazy » : le HTML initial ne contient que 10
événements, mais un unique appel AJAX (``admin-ajax.php`` /
``vc_get_vc_grid_data``) renvoie l'intégralité des éléments.

Si cet appel échoue (thème modifié, nonce invalide…), on retombe
successivement sur : la grille inline (10 événements), les données
structurées schema.org ``Event`` (JSON-LD), puis les sélecteurs du plugin
« The Events Calendar ». Chaque repli émet un avertissement via ``logging``.

Utilisation en bibliothèque ::

    from culturecentro.sources.theatre_granada import lister_evenements_a_venir
    evenements = lister_evenements_a_venir()

En ligne de commande ::

    python -m culturecentro.sources.theatre_granada --format json
"""

from __future__ import annotations

import json
import logging

import requests
from bs4 import BeautifulSoup

from culturecentro import cli
from culturecentro.dates import parse_date_fr, parse_date_iso
from culturecentro.exporters import exporter_csv, exporter_json  # noqa: F401 (API publique)
from culturecentro.jsonld import extraire_depuis_jsonld
from culturecentro.models import Evenement
from culturecentro.scraping import attribut
from culturecentro.sources.base import Source

_LOG = logging.getLogger(__name__)

URL_PROGRAMMATION = "https://theatregranada.com/programmation-2/"


# --------------------------------------------------------------------------- #
# Extraction WPBakery (source principale) + replis
# --------------------------------------------------------------------------- #
def _charger_grille_complete(
    page_html: str, timeout: float, session: requests.Session
) -> str | None:
    """Récupère la grille WPBakery complète via ``admin-ajax.php``.

    Renvoie le fragment HTML de la grille (tous les événements), ou ``None``
    si l'appel échoue — l'appelant retombe alors sur la grille inline.
    """
    soup = BeautifulSoup(page_html, "html.parser")
    conteneur = soup.select_one("[data-vc-request][data-vc-grid-settings]")
    if conteneur is None:
        _LOG.debug("Aucun conteneur de grille WPBakery trouvé dans la page.")
        return None

    try:
        reglages = json.loads(attribut(conteneur, "data-vc-grid-settings") or "{}")
    except (json.JSONDecodeError, TypeError):
        _LOG.debug("Réglages de grille WPBakery illisibles.")
        return None

    url_ajax = attribut(conteneur, "data-vc-request")
    nonce = attribut(conteneur, "data-vc-public-nonce")
    post_id = attribut(conteneur, "data-vc-post-id")
    if not url_ajax or not reglages:
        _LOG.debug("Grille WPBakery : URL AJAX ou réglages manquants.")
        return None

    # Format exact attendu par vc_grid.min.js : les réglages sont envoyés
    # sous la clé « data », et non « vc_grid_data ».
    donnees = {
        "action": "vc_get_vc_grid_data",
        "vc_action": "vc_get_vc_grid_data",
        "tag": reglages.get("tag", "vc_basic_grid"),
        "vc_post_id": post_id,
        "_vcnonce": nonce,
    }
    for cle, valeur in reglages.items():
        donnees[f"data[{cle}]"] = valeur

    try:
        reponse = session.post(
            url_ajax,
            data=donnees,
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": URL_PROGRAMMATION},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        _LOG.debug("Appel AJAX de la grille échoué : %s", exc)
        return None

    # admin-ajax renvoie « 0 » (corps d'un octet) en cas d'échec/nonce invalide.
    if reponse.status_code != 200 or len(reponse.text) <= 1:
        _LOG.debug(
            "Réponse AJAX inutilisable (statut %s, %d octets).",
            reponse.status_code,
            len(reponse.text),
        )
        return None
    return reponse.text


def _extraire_depuis_wpbakery(html: str) -> list[Evenement]:
    """Analyse la grille WPBakery de la page de programmation."""
    soup = BeautifulSoup(html, "html.parser")
    evenements: list[Evenement] = []

    for item in soup.select(".vc_grid-item-mini"):
        titre_el = item.select_one(".vc_gitem-post-data-source-post_title")
        titre = titre_el.get_text(" ", strip=True) if titre_el else None
        if not titre:
            continue

        date_el = item.select_one(".home-artist")
        date_debut = parse_date_fr(date_el.get_text(" ", strip=True)) if date_el else None

        lien_el = item.select_one("a.vc_gitem-link")
        lien = attribut(lien_el, "href") if lien_el else None

        # Sous-titre : plusieurs champs .home-soustitre par bloc (avant/après le
        # titre) ; on garde le premier non vide.
        sous_titre = None
        for el in item.select(".home-soustitre"):
            texte = el.get_text(" ", strip=True)
            if texte:
                sous_titre = texte
                break

        image_el = item.select_one("img.vc_gitem-zone-img")
        image = attribut(image_el, "src") if image_el else None

        evenements.append(
            Evenement(
                titre=titre,
                date_debut=date_debut,
                lien=lien,
                sous_titre=sous_titre,
                image=image,
            )
        )

    return evenements


def _extraire_depuis_html(html: str) -> list[Evenement]:
    """Repli générique (« The Events Calendar ») si aucun JSON-LD n'est présent."""
    soup = BeautifulSoup(html, "html.parser")
    evenements: list[Evenement] = []

    for article in soup.select(
        ".tribe-events-calendar-list__event, article.tribe_events, .type-tribe_events"
    ):
        lien_titre = article.select_one(
            "a.tribe-events-calendar-list__event-title-link, h3 a, h2 a, .tribe-event-url"
        )
        titre = lien_titre.get_text(strip=True) if lien_titre else None
        if not titre:
            continue

        balise_date = article.select_one("time[datetime], .tribe-event-date-start, time")
        date_debut = None
        if balise_date is not None:
            date_debut = parse_date_iso(attribut(balise_date, "datetime")) or parse_date_iso(
                balise_date.get_text(strip=True)
            )

        evenements.append(
            Evenement(
                titre=titre,
                date_debut=date_debut,
                lien=attribut(lien_titre, "href") if lien_titre else None,
            )
        )
    return evenements


def _extraire_evenements(html: str, timeout: float, session: requests.Session) -> list[Evenement]:
    """Choisit la meilleure source disponible et renvoie les événements bruts."""
    fragment = _charger_grille_complete(html, timeout, session)
    if fragment:
        evenements = _extraire_depuis_wpbakery(fragment)
        if evenements:
            _LOG.info("Grille complète chargée via AJAX : %d éléments.", len(evenements))
            return evenements

    evenements = _extraire_depuis_wpbakery(html)
    if evenements:
        _LOG.warning(
            "Chargement AJAX de la grille complète indisponible : repli sur la "
            "grille inline (%d événements visibles seulement).",
            len(evenements),
        )
        return evenements

    evenements = extraire_depuis_jsonld(html)
    if evenements:
        _LOG.warning("Repli sur les données JSON-LD (%d événements).", len(evenements))
        return evenements

    evenements = _extraire_depuis_html(html)
    if evenements:
        _LOG.warning("Repli sur le HTML générique (%d événements).", len(evenements))
        return evenements

    _LOG.warning("Aucun événement n'a pu être extrait de la page.")
    return []


# --------------------------------------------------------------------------- #
# Source + API module
# --------------------------------------------------------------------------- #
class TheatreGranada(Source):
    slug = "theatre-granada"
    nom = "Théâtre Granada"
    url_defaut = URL_PROGRAMMATION
    description = "Liste les événements à venir du Théâtre Granada."

    def extraire(self, html: str, timeout: float, session: requests.Session) -> list[Evenement]:
        return _extraire_evenements(html, timeout, session)


SOURCE = TheatreGranada()


def lister_evenements_a_venir(url: str = URL_PROGRAMMATION, **kwargs) -> list[Evenement]:
    """Raccourci module vers :meth:`TheatreGranada.lister_evenements_a_venir`."""
    return SOURCE.lister_evenements_a_venir(url, **kwargs)


def main(argv=None) -> int:
    return cli.executer(SOURCE, argv)


if __name__ == "__main__":
    raise SystemExit(main())
