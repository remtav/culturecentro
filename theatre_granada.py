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

La grille est en mode « lazy » : le HTML initial ne contient que les 10
premiers événements. Un unique appel AJAX (``admin-ajax.php`` /
``vc_get_vc_grid_data``) renvoie l'intégralité des éléments — c'est ainsi
qu'on récupère TOUS les événements à venir (jusqu'à plus d'un an à l'avance).
Si cet appel échoue (thème modifié, nonce invalide…), on retombe
successivement sur : la grille inline (10 événements), les données
structurées schema.org ``Event`` en JSON-LD, puis les sélecteurs du plugin
« The Events Calendar ». Chaque repli émet un avertissement via ``logging``.

Utilisation en bibliothèque ::

    from theatre_granada import lister_evenements_a_venir, exporter_json
    evenements = lister_evenements_a_venir()
    exporter_json(evenements, "evenements.json")

En ligne de commande ::

    python theatre_granada.py --format csv -o evenements.csv
    python theatre_granada.py --format json
    python theatre_granada.py -v            # journalisation détaillée

Dépendances : ``requests`` et ``beautifulsoup4`` (voir requirements.txt).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import requests
from bs4 import BeautifulSoup
from urllib3.util.retry import Retry

_LOG = logging.getLogger("theatre_granada")

URL_PROGRAMMATION = "https://theatregranada.com/programmation-2/"

_ENTETES = {
    # Un User-Agent « navigateur » évite les blocages basiques.
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}

#: Colonnes utilisées pour la sérialisation CSV/JSON.
CHAMPS = ("titre", "date_debut", "lien", "lieu")


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

    def to_dict(self) -> dict[str, str | None]:
        """Représentation sérialisable (date au format ISO 8601)."""
        return {
            "titre": self.titre,
            "date_debut": self.date_debut.isoformat() if self.date_debut else None,
            "lien": self.lien,
            "lieu": self.lieu,
        }


# --------------------------------------------------------------------------- #
# Réseau
# --------------------------------------------------------------------------- #
def _creer_session() -> requests.Session:
    """Session ``requests`` avec en-têtes navigateur et reprises réseau."""
    session = requests.Session()
    session.headers.update(_ENTETES)
    reprises = Retry(
        total=3,
        backoff_factor=1.0,  # 0s, 1s, 2s, 4s
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
    )
    adaptateur = requests.adapters.HTTPAdapter(max_retries=reprises)
    session.mount("https://", adaptateur)
    session.mount("http://", adaptateur)
    return session


def _telecharger(url: str, timeout: float, session: requests.Session | None = None) -> str:
    client = session or requests
    reponse = client.get(url, headers=_ENTETES, timeout=timeout)
    reponse.raise_for_status()
    return reponse.text


# --------------------------------------------------------------------------- #
# Analyse des dates
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Extraction JSON-LD (repli)
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Extraction WPBakery (source principale)
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
        reglages = json.loads(conteneur.get("data-vc-grid-settings") or "{}")
    except (json.JSONDecodeError, TypeError):
        _LOG.debug("Réglages de grille WPBakery illisibles.")
        return None

    url_ajax = conteneur.get("data-vc-request")
    nonce = conteneur.get("data-vc-public-nonce")
    post_id = conteneur.get("data-vc-post-id")
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


# --------------------------------------------------------------------------- #
# Sélection de la source + finalisation
# --------------------------------------------------------------------------- #
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

    evenements = _extraire_depuis_jsonld(html)
    if evenements:
        _LOG.warning("Repli sur les données JSON-LD (%d événements).", len(evenements))
        return evenements

    evenements = _extraire_depuis_html(html)
    if evenements:
        _LOG.warning("Repli sur le HTML générique (%d événements).", len(evenements))
        return evenements

    _LOG.warning("Aucun événement n'a pu être extrait de la page.")
    return []


def _finaliser(
    evenements: Sequence[Evenement], a_partir_de: datetime
) -> list[Evenement]:
    """Déduplique, filtre les événements à venir et trie par date."""
    # Déduplication (titre + date) en conservant l'ordre de découverte.
    vus: set[tuple[str, str]] = set()
    uniques: list[Evenement] = []
    for ev in evenements:
        cle = (ev.titre, ev.date_debut.isoformat() if ev.date_debut else "")
        if cle not in vus:
            vus.add(cle)
            uniques.append(ev)

    def _en_aware(date: datetime) -> datetime:
        # Date « naïve » : on la suppose en UTC pour permettre les comparaisons.
        return date if date.tzinfo is not None else date.replace(tzinfo=timezone.utc)

    def _est_a_venir(ev: Evenement) -> bool:
        if ev.date_debut is None:
            return True  # date inconnue : on ne l'exclut pas
        return _en_aware(ev.date_debut) >= a_partir_de

    _LOINTAIN = datetime.max.replace(tzinfo=timezone.utc)  # trie les dates inconnues en fin

    a_venir = [ev for ev in uniques if _est_a_venir(ev)]
    a_venir.sort(key=lambda ev: _en_aware(ev.date_debut) if ev.date_debut else _LOINTAIN)
    return a_venir


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

    Raises:
        requests.RequestException: en cas d'échec réseau lors du
            téléchargement de la page.
    """
    if a_partir_de is None:
        a_partir_de = datetime.now(timezone.utc)

    session = _creer_session()
    try:
        html = _telecharger(url, timeout, session=session)
        evenements = _extraire_evenements(html, timeout, session)
    finally:
        session.close()

    return _finaliser(evenements, a_partir_de)


# --------------------------------------------------------------------------- #
# Export CSV / JSON
# --------------------------------------------------------------------------- #
def exporter_json(
    evenements: Iterable[Evenement],
    fichier: str | Path | None = None,
    *,
    indent: int | None = 2,
) -> str:
    """Sérialise les événements en JSON (UTF-8).

    Écrit dans ``fichier`` s'il est fourni, et renvoie toujours la chaîne.
    """
    donnees = [ev.to_dict() for ev in evenements]
    texte = json.dumps(donnees, ensure_ascii=False, indent=indent)
    if fichier is not None:
        Path(fichier).write_text(texte + "\n", encoding="utf-8")
        _LOG.info("%d événements écrits dans %s", len(donnees), fichier)
    return texte


def exporter_csv(
    evenements: Iterable[Evenement], fichier: str | Path | None = None
) -> str:
    """Sérialise les événements en CSV (UTF-8, colonnes : %s).

    Écrit dans ``fichier`` s'il est fourni, et renvoie toujours la chaîne.
    """
    evenements = list(evenements)
    tampon = io.StringIO()
    redacteur = csv.DictWriter(tampon, fieldnames=CHAMPS)
    redacteur.writeheader()
    for ev in evenements:
        redacteur.writerow(ev.to_dict())
    texte = tampon.getvalue()
    if fichier is not None:
        # newline="" : laisse le module csv gérer les fins de ligne.
        with open(fichier, "w", encoding="utf-8", newline="") as flux:
            flux.write(texte)
        _LOG.info("%d événements écrits dans %s", len(evenements), fichier)
    return texte


exporter_csv.__doc__ = exporter_csv.__doc__ % ", ".join(CHAMPS)


# --------------------------------------------------------------------------- #
# Interface en ligne de commande
# --------------------------------------------------------------------------- #
def _construire_parseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(
        description="Liste les événements à venir du Théâtre Granada."
    )
    parseur.add_argument(
        "--url", default=URL_PROGRAMMATION, help="Page de programmation à analyser."
    )
    parseur.add_argument(
        "--format",
        choices=("texte", "csv", "json"),
        default="texte",
        help="Format de sortie (défaut : texte).",
    )
    parseur.add_argument(
        "-o",
        "--sortie",
        type=Path,
        help="Fichier de sortie (défaut : sortie standard).",
    )
    parseur.add_argument(
        "--timeout", type=float, default=20.0, help="Délai réseau en secondes."
    )
    parseur.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Journalisation détaillée (niveau DEBUG).",
    )
    return parseur


def main(argv: Sequence[str] | None = None) -> int:
    args = _construire_parseur().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        evenements = lister_evenements_a_venir(args.url, timeout=args.timeout)
    except requests.RequestException as exc:
        _LOG.error("Échec du téléchargement de %s : %s", args.url, exc)
        return 1

    if args.format == "csv":
        contenu = exporter_csv(evenements, args.sortie)
    elif args.format == "json":
        contenu = exporter_json(evenements, args.sortie)
    else:
        contenu = "\n".join(str(ev) for ev in evenements)
        if args.sortie is not None:
            Path(args.sortie).write_text(contenu + "\n", encoding="utf-8")
            _LOG.info("%d événements écrits dans %s", len(evenements), args.sortie)

    if args.sortie is None:
        print(contenu)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
