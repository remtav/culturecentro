"""Récupération des événements à venir du Théâtre Granada.

Le site https://theatregranada.com est un site WordPress construit avec
WPBakery Page Builder. La page de programmation
(https://theatregranada.com/programmation-2/) affiche ses événements dans
une grille « vc_basic_grid ». Chaque événement est un bloc
``.vc_grid-item-mini`` contenant :

* la date en français dans un champ ACF ``.home-artist``
  (ex. « dimanche 27 septembre 2026 à 20:00 ») ;
* le titre dans ``.vc_gitem-post-data-source-post_title`` ;
* le lien vers la fiche de l'événement dans ``a.vc_gitem-link``.

On analyse donc en priorité cette grille WPBakery. Par sécurité (si le
thème change un jour), on prévoit deux replis : les données structurées
schema.org ``Event`` en JSON-LD, puis les sélecteurs du plugin
« The Events Calendar ».

Remarque : la grille est en mode « lazy » (10 éléments par page) mais ne
propose ni bouton « charger plus » ni pagination visible ; les événements à
venir tiennent donc sur cette unique page. Un éventuel chargement AJAX
supplémentaire (``admin-ajax.php`` / ``vc_get_vc_grid_data``) est protégé
par un nonce et n'est pas exploitable de façon fiable hors navigateur.

La fonction ``lister_evenements_a_venir`` renvoie la liste des événements
dont la date est postérieure (ou égale) à maintenant, triés par date.

Dépendances : ``requests`` et ``beautifulsoup4``.
    pip install requests beautifulsoup4
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import requests
from bs4 import BeautifulSoup

URL_PROGRAMMATION = "https://theatregranada.com/programmation-2/"

_ENTETES = {
    # Un User-Agent « navigateur » évite les blocages basiques.
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}


@dataclass
class Evenement:
    """Un événement de la programmation."""

    titre: str
    date_debut: datetime | None
    lien: str | None = None
    lieu: str | None = None

    def __str__(self) -> str:
        quand = self.date_debut.strftime("%Y-%m-%d %H:%M") if self.date_debut else "date inconnue"
        return f"{quand} — {self.titre}" + (f" ({self.lien})" if self.lien else "")


def _telecharger(url: str, timeout: float, session: requests.Session | None = None) -> str:
    client = session or requests
    reponse = client.get(url, headers=_ENTETES, timeout=timeout)
    reponse.raise_for_status()
    return reponse.text


def _parse_date(valeur: str | None) -> datetime | None:
    """Analyse une date ISO 8601 (format renvoyé par le JSON-LD)."""
    if not valeur:
        return None
    texte = valeur.strip()
    # Python <3.11 ne gère pas le suffixe « Z » dans fromisoformat.
    if texte.endswith("Z"):
        texte = texte[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(texte)
    except ValueError:
        return None


_MOIS_FR = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}

# Ex. : « dimanche 27 septembre 2026 à 20:00 » ou « 1er octobre 2026 ».
_DATE_FR = re.compile(
    r"(?P<jour>\d{1,2})\s*(?:er)?\s+"
    r"(?P<mois>[a-zàâäéèêëîïôöùûüç]+)\s+"
    r"(?P<annee>\d{4})"
    r"(?:\D+(?P<heure>\d{1,2})\s*[h:]\s*(?P<minute>\d{2})?)?",
    re.IGNORECASE,
)


def _parse_date_fr(valeur: str | None) -> datetime | None:
    """Analyse une date française (« dimanche 27 septembre 2026 à 20:00 »).

    Le nom du jour de la semaine et l'heure sont facultatifs. La date est
    renvoyée « naïve » (sans fuseau) ; le filtrage la suppose en UTC.
    """
    if not valeur:
        return None
    m = _DATE_FR.search(valeur.strip().lower())
    if not m:
        return None
    mois = _MOIS_FR.get(m.group("mois"))
    if mois is None:
        return None
    heure = int(m.group("heure")) if m.group("heure") else 0
    minute = int(m.group("minute")) if m.group("minute") else 0
    try:
        return datetime(int(m.group("annee")), mois, int(m.group("jour")), heure, minute)
    except ValueError:
        return None


def _iterer_noeuds_jsonld(donnees: object) -> Iterable[dict]:
    """Parcourt récursivement une structure JSON-LD et livre chaque dict."""
    if isinstance(donnees, dict):
        # Cas @graph : une liste d'objets sous une clé.
        if "@graph" in donnees and isinstance(donnees["@graph"], list):
            yield from _iterer_noeuds_jsonld(donnees["@graph"])
        yield donnees
    elif isinstance(donnees, list):
        for element in donnees:
            yield from _iterer_noeuds_jsonld(element)


def _est_event(noeud: dict) -> bool:
    type_ = noeud.get("@type", "")
    types = type_ if isinstance(type_, list) else [type_]
    return any(isinstance(t, str) and "Event" in t for t in types)


def _extraire_lieu(noeud: dict) -> str | None:
    lieu = noeud.get("location")
    if isinstance(lieu, dict):
        return lieu.get("name")
    if isinstance(lieu, str):
        return lieu
    return None


def _charger_grille_complete(
    page_html: str, timeout: float, session: requests.Session
) -> str | None:
    """Récupère la grille WPBakery complète via ``admin-ajax.php``.

    La grille de la page est en mode « lazy » : le HTML initial ne contient
    que les 10 premiers événements, mais un unique appel AJAX
    (``vc_get_vc_grid_data``) renvoie l'intégralité des éléments — c'est
    ainsi qu'on obtient tous les événements à venir (bien au-delà des 10
    affichés).

    Renvoie le fragment HTML de la grille, ou ``None`` si l'appel échoue
    (l'appelant retombe alors sur la grille inline).
    """
    soup = BeautifulSoup(page_html, "html.parser")
    conteneur = soup.select_one("[data-vc-request][data-vc-grid-settings]")
    if conteneur is None:
        return None

    try:
        reglages = json.loads(conteneur.get("data-vc-grid-settings") or "{}")
    except (json.JSONDecodeError, TypeError):
        return None

    url_ajax = conteneur.get("data-vc-request")
    nonce = conteneur.get("data-vc-public-nonce")
    post_id = conteneur.get("data-vc-post-id")
    if not url_ajax or not reglages:
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
            headers={
                **_ENTETES,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": URL_PROGRAMMATION,
            },
            timeout=timeout,
        )
    except requests.RequestException:
        return None

    # admin-ajax renvoie « 0 » (corps d'un octet) en cas d'échec/nonce invalide.
    if reponse.status_code != 200 or len(reponse.text) <= 1:
        return None
    return reponse.text


def _extraire_depuis_wpbakery(html: str) -> list[Evenement]:
    """Analyse la grille WPBakery de la page de programmation.

    C'est la structure réellement utilisée par theatregranada.com.
    """
    soup = BeautifulSoup(html, "html.parser")
    evenements: list[Evenement] = []

    for item in soup.select(".vc_grid-item-mini"):
        titre_el = item.select_one(".vc_gitem-post-data-source-post_title")
        titre = titre_el.get_text(" ", strip=True) if titre_el else None
        if not titre:
            continue

        date_el = item.select_one(".home-artist")
        date_debut = _parse_date_fr(date_el.get_text(" ", strip=True)) if date_el else None

        lien_el = item.select_one("a.vc_gitem-link")
        lien = lien_el.get("href") if lien_el else None

        evenements.append(Evenement(titre=titre, date_debut=date_debut, lien=lien))

    return evenements


def _extraire_depuis_jsonld(html: str) -> list[Evenement]:
    soup = BeautifulSoup(html, "html.parser")
    evenements: list[Evenement] = []
    for balise in soup.find_all("script", type="application/ld+json"):
        contenu = balise.string or balise.get_text()
        if not contenu:
            continue
        try:
            donnees = json.loads(contenu)
        except json.JSONDecodeError:
            continue
        for noeud in _iterer_noeuds_jsonld(donnees):
            if not isinstance(noeud, dict) or not _est_event(noeud):
                continue
            titre = noeud.get("name")
            if not titre:
                continue
            evenements.append(
                Evenement(
                    titre=titre.strip(),
                    date_debut=_parse_date(noeud.get("startDate")),
                    lien=noeud.get("url"),
                    lieu=_extraire_lieu(noeud),
                )
            )
    return evenements


def _extraire_depuis_html(html: str) -> list[Evenement]:
    """Repli générique si aucun JSON-LD n'est présent.

    Cible les motifs les plus courants des thèmes d'agenda WordPress
    (The Events Calendar). Les sélecteurs peuvent devoir être ajustés
    si le thème du site change.
    """
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
            date_debut = _parse_date(balise_date.get("datetime")) or _parse_date(
                balise_date.get_text(strip=True)
            )

        evenements.append(
            Evenement(
                titre=titre,
                date_debut=date_debut,
                lien=lien_titre.get("href") if lien_titre else None,
            )
        )
    return evenements


def lister_evenements_a_venir(
    url: str = URL_PROGRAMMATION,
    *,
    a_partir_de: datetime | None = None,
    timeout: float = 20.0,
) -> list[Evenement]:
    """Retourne les événements à venir de la programmation, triés par date.

    Args:
        url: page de programmation à analyser.
        a_partir_de: seuil temporel ; par défaut « maintenant » (UTC).
            Les événements sans date connue sont conservés.
        timeout: délai d'attente réseau, en secondes.

    Returns:
        Liste d'objets :class:`Evenement`.
    """
    if a_partir_de is None:
        a_partir_de = datetime.now(timezone.utc)

    session = requests.Session()
    html = _telecharger(url, timeout, session=session)

    # Source principale : la grille WPBakery. On tente d'abord de charger la
    # grille COMPLÈTE via AJAX (tous les événements à venir) ; à défaut, on se
    # rabat sur les 10 événements présents dans le HTML initial. Replis
    # ultérieurs si le thème change (JSON-LD schema.org, « The Events Calendar »).
    fragment = _charger_grille_complete(html, timeout, session)
    evenements = _extraire_depuis_wpbakery(fragment) if fragment else []
    if not evenements:
        evenements = _extraire_depuis_wpbakery(html)
    if not evenements:
        evenements = _extraire_depuis_jsonld(html)
    if not evenements:
        evenements = _extraire_depuis_html(html)

    # Déduplication (titre + date) en conservant l'ordre de découverte.
    vus: set[tuple[str, str]] = set()
    uniques: list[Evenement] = []
    for ev in evenements:
        cle = (ev.titre, ev.date_debut.isoformat() if ev.date_debut else "")
        if cle not in vus:
            vus.add(cle)
            uniques.append(ev)

    def _est_a_venir(ev: Evenement) -> bool:
        if ev.date_debut is None:
            return True  # date inconnue : on ne l'exclut pas
        date = ev.date_debut
        if date.tzinfo is None:  # date « naïve » : on la suppose en UTC
            date = date.replace(tzinfo=timezone.utc)
        return date >= a_partir_de

    a_venir = [ev for ev in uniques if _est_a_venir(ev)]
    a_venir.sort(key=lambda ev: ev.date_debut or datetime.max.replace(tzinfo=timezone.utc))
    return a_venir


if __name__ == "__main__":
    for evenement in lister_evenements_a_venir():
        print(evenement)
