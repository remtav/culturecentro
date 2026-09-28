"""Source d'événements : Maison des arts de la parole.

La page https://maisondesartsdelaparole.com/programmation/ (WordPress, thème
Divi) affiche un calendrier **EventON** chargé mois par mois : le HTML initial
ne contient que le mois courant, et le changement de mois passe par un appel
AJAX (``admin-ajax.php`` / ``the_ajax_hook``) dont la requête reprend les
réglages du calendrier (``.cal_arguments``, ``.evo-data``, filtres actifs) et
un ``nonce`` inscrit dans la page.

On lit donc le mois courant dans la page, puis on rejoue l'appel AJAX
« mois suivant » pour les :data:`NOMBRE_DE_MOIS` mois à venir. Chaque bloc
``.eventon_list_event`` fournit titre, sous-titre, dates (``itemprop``
schema.org), affiche, lieu et lien de la fiche.

La programmation se donne en partie hors les murs, jusqu'en région
(festival) : les événements dont le lieu ou l'adresse n'est pas au
centre-ville de Sherbrooke (:func:`culturecentro.lieux.est_centre_ville`)
sont écartés.

Si le calendrier est introuvable, on retombe sur les données schema.org
``Event`` (JSON-LD) de la page. Chaque repli émet un avertissement via
``logging``.

Utilisation en bibliothèque ::

    from culturecentro.sources.maisondesartsdelaparole import lister_evenements_a_venir
    evenements = lister_evenements_a_venir()

En ligne de commande ::

    python -m culturecentro.sources.maisondesartsdelaparole --format json
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

from culturecentro import cli
from culturecentro.dates import parse_date_iso
from culturecentro.exporters import exporter_csv, exporter_json  # noqa: F401 (API publique)
from culturecentro.jsonld import extraire_depuis_jsonld
from culturecentro.lieux import est_centre_ville
from culturecentro.models import Evenement
from culturecentro.scraping import attribut, premiere_image, url_image
from culturecentro.sources.base import Source

_LOG = logging.getLogger(__name__)

URL_PROGRAMMATION = "https://maisondesartsdelaparole.com/programmation/"

#: Nombre de mois à venir interrogés via AJAX, en plus du mois courant.
NOMBRE_DE_MOIS = 12

# var the_ajax_script = {"ajaxurl":"https://…/wp-admin/admin-ajax.php","postnonce":"b1a93ea530"};
_AJAX_URL = re.compile(r'"ajaxurl"\s*:\s*"([^"]+admin-ajax\.php)"')
_NONCE = re.compile(r'"postnonce"\s*:\s*"([0-9a-zA-Z]+)"')


# --------------------------------------------------------------------------- #
# Lecture du calendrier EventON dans la page
# --------------------------------------------------------------------------- #
@dataclass
class Calendrier:
    """Réglages d'un calendrier EventON, tels que lus dans la page."""

    url_ajax: str
    nonce: str
    mois: int
    annee: int
    shortcode: dict[str, str] = field(default_factory=dict)
    evodata: dict[str, str] = field(default_factory=dict)
    filtres: list[dict[str, str]] = field(default_factory=list)
    sort_by: str = "sort_date"


def _attributs_data(element: Tag) -> dict[str, str]:
    """Les attributs ``data-*`` d'un élément, sans le préfixe ``data-``."""
    resultat: dict[str, str] = {}
    for nom in element.attrs:
        if nom.startswith("data-"):
            valeur = attribut(element, nom)
            if valeur is not None:
                resultat[nom[5:]] = valeur
    return resultat


def _lire_calendrier(page_html: str) -> Calendrier | None:
    """Lit le premier calendrier EventON de la page, ou ``None`` s'il n'y en a pas."""
    soup = BeautifulSoup(page_html, "html.parser")
    calendrier = soup.select_one(".ajde_evcal_calendar")
    evo = calendrier.select_one(".evo-data") if calendrier else None
    if calendrier is None or evo is None:
        _LOG.debug("Aucun calendrier EventON dans la page.")
        return None

    m_url = _AJAX_URL.search(page_html)
    m_nonce = _NONCE.search(page_html)
    if not m_url or not m_nonce:
        _LOG.debug("URL AJAX ou nonce EventON introuvable dans la page.")
        return None

    evodata = _attributs_data(evo)
    try:
        mois = int(evodata.get("cmonth", ""))
        annee = int(evodata.get("cyear", ""))
    except ValueError:
        _LOG.debug("Mois courant du calendrier EventON illisible.")
        return None

    shortcode: dict[str, str] = {}
    for args in calendrier.select(".cal_arguments"):
        shortcode.update({k: v for k, v in _attributs_data(args).items() if v != ""})

    # Filtres actifs (saison, passé/futur…) : même logique que le script
    # eventon_functions.js (evoGetFilters) — « all » signifie « sans filtre ».
    filtres: list[dict[str, str]] = []
    for filtre in calendrier.select(".eventon_filter_line .eventon_filter"):
        valeur = attribut(filtre, "data-filter_val")
        if not valeur or valeur == "all":
            continue
        entree = {
            "filter_type": attribut(filtre, "data-filter_type") or "",
            "filter_name": attribut(filtre, "data-filter_field") or "",
            "filter_val": valeur,
        }
        if attribut(filtre, "data-fl_o") == "NOT":
            entree["filter_op"] = "NOT IN"
        filtres.append(entree)

    return Calendrier(
        url_ajax=m_url.group(1),
        nonce=m_nonce.group(1),
        mois=mois,
        annee=annee,
        shortcode=shortcode,
        evodata=evodata,
        filtres=filtres,
        sort_by=evodata.get("sort_by") or "sort_date",
    )


def _construire_requete(cal: Calendrier, direction: str = "next") -> dict[str, str]:
    """Corps de la requête ``the_ajax_hook`` (format attendu par EventON)."""
    donnees = {
        "action": "the_ajax_hook",
        "direction": direction,
        "sort_by": cal.sort_by,
        "ajaxtype": "switchmonth",
        "nonce": cal.nonce,
    }
    for cle, valeur in cal.shortcode.items():
        donnees[f"shortcode[{cle}]"] = valeur
    for cle, valeur in cal.evodata.items():
        donnees[f"evodata[{cle}]"] = valeur
    donnees["evodata[cmonth]"] = str(cal.mois)
    donnees["evodata[cyear]"] = str(cal.annee)
    for i, filtre in enumerate(cal.filtres):
        for cle, valeur in filtre.items():
            donnees[f"filters[{i}][{cle}]"] = valeur
    return donnees


def _charger_mois_suivant(cal: Calendrier, timeout: float, session: requests.Session) -> str | None:
    """Charge le mois suivant via AJAX et avance ``cal`` sur ce mois.

    Renvoie le fragment HTML des événements du mois, ou ``None`` si l'appel
    échoue (réseau, réponse illisible) — l'appelant arrête alors la boucle.
    """
    try:
        reponse = session.post(
            cal.url_ajax,
            data=_construire_requete(cal, "next"),
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": URL_PROGRAMMATION},
            timeout=timeout,
        )
        reponse.raise_for_status()
        donnees: Any = reponse.json()
    except (requests.RequestException, ValueError) as exc:
        _LOG.debug("Appel AJAX EventON échoué : %s", exc)
        return None

    if not isinstance(donnees, dict) or donnees.get("status") != "GOOD":
        _LOG.debug("Réponse AJAX EventON inattendue : %r", donnees)
        return None

    try:
        cal.mois = int(donnees["month"])
        cal.annee = int(donnees["year"])
    except (KeyError, TypeError, ValueError):
        # Pas de mois renvoyé : on avance nous-mêmes d'un mois.
        cal.mois, cal.annee = (cal.mois % 12 + 1, cal.annee + (1 if cal.mois == 12 else 0))

    contenu = donnees.get("content")
    return contenu if isinstance(contenu, str) else ""


# --------------------------------------------------------------------------- #
# Extraction des blocs EventON
# --------------------------------------------------------------------------- #
def _date_depuis_unix(valeur: str | None) -> datetime | None:
    """Convertit un horodatage EventON (secondes, heure locale) en datetime naïf."""
    if not valeur:
        return None
    try:
        return datetime.fromtimestamp(int(valeur), tz=timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError, OSError):
        return None


def _contenu_meta(bloc: Tag, itemprop: str) -> str | None:
    meta = bloc.select_one(f"meta[itemprop={itemprop}]")
    return attribut(meta, "content") if meta else None


def _extraire_depuis_eventon(html: str) -> list[Evenement]:
    """Analyse les blocs ``.eventon_list_event`` d'une page ou d'un fragment AJAX."""
    soup = BeautifulSoup(html, "html.parser")
    evenements: list[Evenement] = []

    for bloc in soup.select(".eventon_list_event"):
        titre_el = bloc.select_one(".evcal_event_title") or bloc.select_one("[itemprop=name]")
        titre = titre_el.get_text(" ", strip=True) if titre_el else None
        if not titre:
            continue  # ex. bloc « Aucun événement »

        # Dates : métadonnées schema.org (heure locale), sinon data-time (unix).
        date_debut = parse_date_iso(_contenu_meta(bloc, "startDate"))
        date_fin = parse_date_iso(_contenu_meta(bloc, "endDate"))
        if date_debut is None:
            plage = (attribut(bloc, "data-time") or "").split("-")
            date_debut = _date_depuis_unix(plage[0] if plage else None)
            date_fin = _date_depuis_unix(plage[1]) if len(plage) > 1 else None

        lien_el = bloc.select_one(".evo_event_schema a[itemprop=url]") or bloc.select_one(
            "a.evcal_list_a[href]:not([href='#'])"
        )
        lien = attribut(lien_el, "href") if lien_el else None

        sous_titre_el = bloc.select_one(".evcal_event_subtitle")
        sous_titre = sous_titre_el.get_text(" ", strip=True) if sous_titre_el else None

        lieu_el = bloc.select_one(".event_location_name") or bloc.select_one(
            "[itemprop=location] [itemprop=name]"
        )
        lieu = lieu_el.get_text(" ", strip=True) if lieu_el else None
        desc = bloc.select_one("[data-location_name]")
        if not lieu:
            lieu = attribut(desc, "data-location_name") if desc else None
        adresse = attribut(desc, "data-location_address") if desc else None
        if adresse is None:
            adresse_el = bloc.select_one("[itemprop=location] [itemprop=streetAddress]")
            adresse = adresse_el.get_text(" ", strip=True) if adresse_el else None

        # Programmation en partie hors les murs, jusqu'en région : seuls les
        # rendez-vous au centre-ville de Sherbrooke sont conservés.
        if not est_centre_ville(lieu, adresse):
            _LOG.debug("Hors centre-ville, écarté : %s (%s, %s)", titre, lieu, adresse)
            continue

        image = (
            _contenu_meta(bloc, "image")
            or url_image(bloc.select_one(".evo_boxtop"))
            or premiere_image(bloc)
        )

        evenements.append(
            Evenement(
                titre=titre,
                date_debut=date_debut,
                date_fin=date_fin,
                lien=lien,
                lieu=lieu or None,
                sous_titre=sous_titre or None,
                image=image,
            )
        )

    return evenements


def _extraire_evenements(html: str, timeout: float, session: requests.Session) -> list[Evenement]:
    """Mois courant (page) + mois suivants (AJAX), avec repli JSON-LD."""
    cal = _lire_calendrier(html)
    if cal is None:
        evenements = extraire_depuis_jsonld(html)
        if evenements:
            _LOG.warning(
                "Calendrier EventON introuvable : repli sur les données JSON-LD (%d événements).",
                len(evenements),
            )
            return evenements
        _LOG.warning("Aucun événement n'a pu être extrait de la page.")
        return []

    evenements = _extraire_depuis_eventon(html)
    _LOG.info("Mois courant (%02d/%d) : %d événements.", cal.mois, cal.annee, len(evenements))

    for _ in range(NOMBRE_DE_MOIS):
        fragment = _charger_mois_suivant(cal, timeout, session)
        if fragment is None:
            _LOG.warning(
                "Chargement AJAX du mois suivant indisponible : arrêt après %02d/%d.",
                cal.mois,
                cal.annee,
            )
            break
        du_mois = _extraire_depuis_eventon(fragment)
        _LOG.debug("Mois %02d/%d : %d événements.", cal.mois, cal.annee, len(du_mois))
        evenements.extend(du_mois)

    if not evenements:
        _LOG.warning("Aucun événement dans le calendrier EventON.")
    return evenements


# --------------------------------------------------------------------------- #
# Source + API module
# --------------------------------------------------------------------------- #
class MaisonDesArtsDeLaParole(Source):
    slug = "maison-des-arts-de-la-parole"
    nom = "Maison des arts de la parole"
    url_defaut = URL_PROGRAMMATION
    categorie_defaut = "litt"

    def extraire(self, html: str, timeout: float, session: requests.Session) -> list[Evenement]:
        return _extraire_evenements(html, timeout, session)


SOURCE = MaisonDesArtsDeLaParole()


def lister_evenements_a_venir(
    url: str = URL_PROGRAMMATION,
    *,
    a_partir_de: datetime | None = None,
    timeout: float = 20.0,
) -> list[Evenement]:
    """Raccourci module vers :meth:`MaisonDesArtsDeLaParole.lister_evenements_a_venir`."""
    return SOURCE.lister_evenements_a_venir(url, a_partir_de=a_partir_de, timeout=timeout)


def main(argv: Sequence[str] | None = None) -> int:
    return cli.executer(SOURCE, argv)


if __name__ == "__main__":
    raise SystemExit(main())
