"""Récupération des événements à venir de La Petite Boîte Noire.

La page de programmation https://lapetiteboitenoire.com/evenements/ est un
site WordPress, mais elle n'affiche PAS elle-même la liste des spectacles :
ceux-ci sont injectés par un widget de la billetterie
`Lepointdevente.com <https://lepointdevente.com>`_. Le HTML de la page ne
contient qu'un script ::

    <script src="https://lepointdevente.com/plugins/widget.js?group=6603…">

qui insère une iframe pointant vers la vraie liste :
``https://lepointdevente.com/billets/programmationavenir``. C'est cette page
qu'on télécharge et qu'on analyse pour obtenir TOUS les événements à venir.

Sur cette page de billetterie, chaque spectacle est un bloc
``.feature-col[data-tpos-event="<id>"]`` contenant :

* le titre dans ``.feature-title`` ;
* la date en français dans ``.feature-date`` (ex. « 30 septembre 2026, 20h00 ») ;
* le lieu dans ``.feature-city`` ;
* l'affiche dans ``img[itemprop="image"]`` ;
* l'identifiant de l'événement (``data-tpos-event``), d'où l'on reconstruit
  le lien de la fiche : ``<url_billetterie>/<id>``.

La source est déterminée ainsi :

1. on télécharge la page ``evenements`` de La Petite Boîte Noire ;
2. on y découvre l'URL de la liste Lepointdevente (lien ``/billets/…`` ou,
   à défaut, ``group`` du widget, via ``widget.js``) ;
3. on télécharge et on analyse cette liste.

Si la découverte échoue, on retombe sur l'URL de billetterie connue, puis sur
l'analyse directe de la page ``evenements`` (données schema.org ``Event`` en
JSON-LD). Chaque repli émet un avertissement via ``logging``.

Utilisation en bibliothèque ::

    from lapetiteboitenoire import lister_evenements_a_venir, exporter_json
    evenements = lister_evenements_a_venir()
    exporter_json(evenements, "evenements.json")

En ligne de commande ::

    python lapetiteboitenoire.py --format csv -o evenements.csv
    python lapetiteboitenoire.py --format json
    python lapetiteboitenoire.py -v            # journalisation détaillée

Dépendances : ``requests`` et ``beautifulsoup4`` (voir requirements.txt).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from urllib3.util.retry import Retry

_LOG = logging.getLogger("lapetiteboitenoire")

URL_EVENEMENTS = "https://lapetiteboitenoire.com/evenements/"

#: URL de secours de la liste Lepointdevente, si on ne parvient pas à la
#: découvrir dans la page (``group=6603`` = La Petite Boîte Noire).
URL_BILLETTERIE_DEFAUT = "https://lepointdevente.com/billets/programmationavenir"

_ENTETES = {
    # Un User-Agent « navigateur » évite les blocages basiques.
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}

#: Colonnes utilisées pour la sérialisation CSV/JSON.
CHAMPS = ("titre", "date_debut", "lien", "image", "lieu")


@dataclass
class Evenement:
    """Un événement de la programmation.

    ``image`` (URL de l'affiche) est un champ **obligatoire** du modèle : il
    doit être fourni à la construction. Sa valeur peut être ``None`` lorsque
    la source n'expose réellement aucune image, mais le champ est toujours
    présent dans la sérialisation.
    """

    titre: str
    date_debut: datetime | None
    image: str | None
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
            "image": self.image,
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

# Ex. : « 30 septembre 2026, 20h00 », « 1er octobre 2026, 20h00 » ou
# « 8 août 2026 ». Le nom du jour et l'heure sont facultatifs.
_DATE_FR = re.compile(
    r"(?P<jour>\d{1,2})\s*(?:er)?\s+"
    r"(?P<mois>[a-zàâäéèêëîïôöùûüç]+)\s+"
    r"(?P<annee>\d{4})"
    r"(?:\D+(?P<heure>\d{1,2})\s*[h:]\s*(?P<minute>\d{2})?)?",
    re.IGNORECASE,
)


def _parse_date_fr(valeur: str | None) -> datetime | None:
    """Analyse une date française (« 30 septembre 2026, 20h00 »).

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


def _extraire_image(noeud: dict) -> str | None:
    image = noeud.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        return image.get("url")
    if isinstance(image, str):
        return image
    return None


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
        href = lien["href"]
        if "lepointdevente.com/billets/" in href:
            return href.split("?", 1)[0]

    # 2. Le widget : on lit ``widget.js`` pour en extraire l'URL de l'iframe.
    for balise in soup.find_all("script", src=True):
        src = balise["src"]
        if "lepointdevente.com/plugins/widget.js" not in src:
            continue
        try:
            script = _telecharger(src, timeout, session=session)
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
# Extraction Lepointdevente (source principale)
# --------------------------------------------------------------------------- #
def _extraire_depuis_lepointdevente(html: str, url_base: str) -> list[Evenement]:
    """Analyse la liste de spectacles d'une page Lepointdevente.

    C'est la structure réellement utilisée par la billetterie de
    La Petite Boîte Noire.
    """
    soup = BeautifulSoup(html, "html.parser")
    evenements: list[Evenement] = []

    for item in soup.select(".feature-col[data-tpos-event]"):
        titre_el = item.select_one(".feature-title")
        titre = titre_el.get_text(" ", strip=True) if titre_el else None
        if not titre:
            continue

        date_el = item.select_one(".feature-date")
        date_debut = _parse_date_fr(date_el.get_text(" ", strip=True)) if date_el else None

        lieu_el = item.select_one(".feature-city")
        lieu = lieu_el.get_text(" ", strip=True) if lieu_el else None

        # L'affiche : <img itemprop="image" src="..."> (repli sur toute <img>).
        img_el = item.select_one("img[itemprop=image]") or item.select_one("img")
        image = img_el.get("src") if img_el else None

        # Pas d'ancre dans la carte : le lien de la fiche se reconstruit à
        # partir de l'identifiant ``data-tpos-event`` (ex. .../<slug>/529998).
        event_id = item.get("data-tpos-event")
        lien = urljoin(url_base.rstrip("/") + "/", event_id) if event_id else None

        evenements.append(
            Evenement(titre=titre, date_debut=date_debut, image=image, lien=lien, lieu=lieu)
        )

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
                    image=_extraire_image(noeud),
                    lien=noeud.get("url"),
                    lieu=_extraire_lieu(noeud),
                )
            )
    return evenements


# --------------------------------------------------------------------------- #
# Sélection de la source + finalisation
# --------------------------------------------------------------------------- #
def _extraire_evenements(html: str, timeout: float, session: requests.Session) -> list[Evenement]:
    """Choisit la meilleure source disponible et renvoie les événements bruts."""
    url_billetterie = _trouver_url_billetterie(html, timeout, session)
    try:
        liste_html = _telecharger(url_billetterie, timeout, session=session)
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
    evenements = _extraire_depuis_jsonld(html)
    if evenements:
        _LOG.warning("Repli sur les données JSON-LD de la page (%d événements).", len(evenements))
        return evenements

    _LOG.warning("Aucun événement n'a pu être extrait.")
    return []


def _finaliser(evenements: Sequence[Evenement], a_partir_de: datetime) -> list[Evenement]:
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
    url: str = URL_EVENEMENTS,
    *,
    a_partir_de: datetime | None = None,
    timeout: float = 20.0,
) -> list[Evenement]:
    """Retourne les événements à venir de la programmation, triés par date.

    Args:
        url: page d'événements de La Petite Boîte Noire à analyser.
        a_partir_de: seuil temporel ; par défaut minuit du jour courant (UTC),
            afin de lister les événements du jour courant ou à venir.
            Les événements sans date connue sont conservés.
        timeout: délai d'attente réseau, en secondes.

    Returns:
        Liste d'objets :class:`Evenement`.

    Raises:
        requests.RequestException: en cas d'échec réseau lors du
            téléchargement de la page.
    """
    if a_partir_de is None:
        # Minuit du jour courant : on conserve les événements plus tôt dans la
        # journée (« jour courant ou futur »), pas seulement ceux après l'instant présent.
        a_partir_de = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

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


def exporter_csv(evenements: Iterable[Evenement], fichier: str | Path | None = None) -> str:
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


if exporter_csv.__doc__:
    exporter_csv.__doc__ = exporter_csv.__doc__ % ", ".join(CHAMPS)


# --------------------------------------------------------------------------- #
# Interface en ligne de commande
# --------------------------------------------------------------------------- #
def _construire_parseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(
        description="Liste les événements à venir de La Petite Boîte Noire."
    )
    parseur.add_argument("--url", default=URL_EVENEMENTS, help="Page d'événements à analyser.")
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
    parseur.add_argument("--timeout", type=float, default=20.0, help="Délai réseau en secondes.")
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
