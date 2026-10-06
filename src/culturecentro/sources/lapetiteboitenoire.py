"""Source d'événements : La Petite Boîte Noire.

La page https://lapetiteboitenoire.com/evenements/ n'affiche pas elle-même les
spectacles : ils sont injectés par un widget de la billetterie
`Lepointdevente.com <https://lepointdevente.com>`_. On découvre l'URL de la
liste Lepointdevente dans la page (lien « Programmation complète » ou, à
défaut, ``widget.js``), puis on télécharge et analyse cette liste — chaque
carte ``.feature-col[data-tpos-event]`` donne titre, date, lieu et affiche.

Le lien pointe vers la fiche propre à l'événement sur Lepointdevente (celle
qu'affiche la fenêtre surgissante du widget), et non vers la liste générale :
``https://lepointdevente.com/billets/<code>``, où ``<code>`` (ex.
``pbn261007001``) se lit dans l'URL de l'affiche. Sans affiche, on se rabat
sur le lien permanent ``/plugins/embed/redirect?event=<id>`` — celui que charge
la fenêtre surgissante — qui redirige vers la même fiche.

Le lieu affiché par Lepointdevente (``.feature-city``) est une chaîne
« <salle>, Sherbrooke, QC » dont la graphie varie d'un événement à l'autre
(« La Petite boite noire », « La Petite Boite Noire », « La Petite Boîte
Noire »…). On la normalise : la ville est retirée et toute variante du nom de
la salle est ramenée au nom canonique :attr:`LaPetiteBoiteNoire.nom`, pour
qu'un seul lieu apparaisse dans l'agrégation et le filtre du site.

La catégorie (« Humour », « Arts littéraires »…) que l'organisateur déclare
sur Lepointdevente n'est affichée ni dans la liste ni sur la fiche : seule la
recherche du site permet de filtrer par catégorie. On y cherche donc la salle,
une catégorie non musicale à la fois (:data:`CATEGORIES_LEPOINTDEVENTE`), et
chaque événement trouvé reçoit la catégorie correspondante — y compris un
spectacle d'humour dont ni le titre ni la description ne disent « humour ».
Les autres restent au classement automatique (musique par défaut).

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

import json
import logging
import re
import unicodedata
from collections.abc import Iterable, Sequence
from datetime import datetime
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup

from culturecentro import cli
from culturecentro.dates import parse_date_fr  # noqa: F401 (réexport pratique)
from culturecentro.exporters import exporter_csv, exporter_json  # noqa: F401 (API publique)
from culturecentro.http import telecharger
from culturecentro.jsonld import extraire_depuis_jsonld
from culturecentro.models import Evenement
from culturecentro.scraping import attribut, premiere_image, url_image
from culturecentro.sources.base import Source

_LOG = logging.getLogger(__name__)

URL_EVENEMENTS = "https://lapetiteboitenoire.com/evenements/"

#: URL de secours de la liste Lepointdevente, si on ne parvient pas à la
#: découvrir dans la page (``group=6603`` = La Petite Boîte Noire).
URL_BILLETTERIE_DEFAUT = "https://lepointdevente.com/billets/programmationavenir"

#: Fiche d'un événement Lepointdevente, à partir de son code (``pbn261007001``).
URL_FICHE = "https://lepointdevente.com/billets/{code}"

#: Lien permanent vers la fiche d'un événement à partir de son identifiant
#: numérique ``data-tpos-event`` : c'est l'URL que charge la fenêtre
#: surgissante du widget ; elle redirige (302) vers :data:`URL_FICHE`.
URL_FICHE_PAR_ID = "https://lepointdevente.com/plugins/embed/redirect?event={id}"

#: Code de l'événement dans l'URL de son affiche :
#: ``…/events/PBN/26/10/07/001/pbn261007001-1152x648-fr.png``.
_CODE_DANS_IMAGE = re.compile(r"/events/[^/]+/\d{2}/\d{2}/\d{2}/\d+/([a-z0-9]+)-", re.IGNORECASE)

#: Code de l'événement dans l'URL de sa fiche (``/billets/pbn261007001``).
_CODE_DANS_LIEN = re.compile(r"/billets/([a-z0-9]+)/?$", re.IGNORECASE)

#: Recherche Lepointdevente : la seule page qui filtre les événements par
#: catégorie (paramètre ``categories``, JSON ``{"<id>": 0}``).
URL_RECHERCHE = "https://lepointdevente.com/"

#: Termes et localité (identifiant Lepointdevente de Sherbrooke) qui placent
#: les événements de la salle en tête des résultats.
RECHERCHE_SALLE = "Petite Boîte Noire"
LOCALITE_SHERBROOKE = 2238

#: Catégories Lepointdevente interrogées (identifiant → catégorie), par
#: priorité décroissante. La musique, catégorie par défaut de la salle, ne
#: l'est pas : un événement absent de ces résultats garde le classement
#: automatique.
CATEGORIES_LEPOINTDEVENTE: dict[int, str] = {
    11: "humour",
    4: "danse",
    6: "litt",  # Arts littéraires
    3: "theatre",
}

#: Garde-fou : pages de résultats lues au plus par catégorie.
_PAGES_MAX = 5

#: Nom canonique de la salle, tel qu'exposé dans le champ ``lieu``.
NOM_SALLE = "La Petite Boîte Noire"

#: Suffixe « ville, province » que Lepointdevente accole au nom du lieu.
_SUFFIXE_VILLE = re.compile(r"\s*,\s*Sherbrooke(\s*,\s*(QC|Québec|Quebec))?\s*$", re.IGNORECASE)


def _cle_comparaison(texte: str) -> str:
    """Forme insensible à la casse, aux accents et aux espaces multiples."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return " ".join(sans_accents.casefold().split())


_CLE_SALLE = _cle_comparaison(NOM_SALLE)


def normaliser_lieu(texte: str | None) -> str | None:
    """Ramène le lieu Lepointdevente à un nom de salle propre.

    * retire le suffixe « , Sherbrooke, QC » ;
    * ramène toute graphie du nom de la salle (casse, accents) au nom
      canonique :data:`NOM_SALLE` ;
    * renvoie ``None`` si le texte est vide.

    Les autres lieux (ex. « Lieu à confirmer ») sont conservés tels quels,
    sans le suffixe de ville.
    """
    if texte is None:
        return None
    lieu = _SUFFIXE_VILLE.sub("", " ".join(texte.split()))
    if not lieu:
        return None
    if _cle_comparaison(lieu) == _CLE_SALLE:
        return NOM_SALLE
    return lieu


def lien_fiche(event_id: str | None, image: str | None) -> str | None:
    """Lien vers la fiche propre à l'événement sur Lepointdevente.

    Le code de la fiche est lu dans l'URL de l'affiche quand c'est possible
    (URL canonique, sans redirection) ; sinon on construit le lien permanent
    à partir de l'identifiant ``data-tpos-event``.
    """
    m = _CODE_DANS_IMAGE.search(image) if image else None
    if m:
        return URL_FICHE.format(code=m.group(1).lower())
    if event_id:
        return URL_FICHE_PAR_ID.format(id=event_id)
    return None


def code_fiche(lien: str | None) -> str | None:
    """Code de l'événement (``pbn261007001``) lu dans le lien de sa fiche."""
    m = _CODE_DANS_LIEN.search(lien) if lien else None
    return m.group(1).lower() if m else None


# --------------------------------------------------------------------------- #
# Catégorie déclarée sur Lepointdevente
# --------------------------------------------------------------------------- #
def url_recherche(categorie_id: int) -> str:
    """Recherche Lepointdevente des événements de la salle dans une catégorie."""
    parametres = {
        "q": RECHERCHE_SALLE,
        "locality": LOCALITE_SHERBROOKE,
        "categories": json.dumps({str(categorie_id): 0}, separators=(",", ":")),
    }
    return f"{URL_RECHERCHE}?{urlencode(parametres)}"


def _analyser_resultats(html: str) -> tuple[list[str], str | None]:
    """Codes des événements d'une page de résultats, et URL de la page suivante."""
    soup = BeautifulSoup(html, "html.parser")
    codes = [
        code
        for lien in soup.select("a.feature-link[href]")
        if (code := code_fiche(attribut(lien, "href")))
    ]
    suivant = soup.select_one("a#events-pages-next")
    if suivant is None or "disabled" in suivant.get_attribute_list("class"):
        return codes, None
    href = attribut(suivant, "href")
    if not href or href == "#":
        return codes, None
    return codes, urljoin(URL_RECHERCHE, href)


def categories_lepointdevente(
    codes: Iterable[str], timeout: float, session: requests.Session
) -> dict[str, str]:
    """Catégorie déclarée sur Lepointdevente pour chacun des ``codes`` d'événement.

    Une recherche par catégorie de :data:`CATEGORIES_LEPOINTDEVENTE` ; les
    résultats étant triés par pertinence, on cesse de tourner les pages dès
    qu'une page ne contient plus aucun des ``codes``. Un code présent dans
    plusieurs catégories reçoit la première. Un échec réseau laisse les
    événements concernés au classement automatique (avertissement).
    """
    cherches = set(codes)
    categories: dict[str, str] = {}
    for categorie_id, categorie in CATEGORIES_LEPOINTDEVENTE.items():
        url: str | None = url_recherche(categorie_id)
        for _ in range(_PAGES_MAX):
            if url is None:
                break
            try:
                html = telecharger(url, timeout, session=session)
            except requests.RequestException as exc:
                _LOG.warning("Recherche Lepointdevente « %s » échouée : %s", categorie, exc)
                break
            codes_page, url = _analyser_resultats(html)
            trouves = cherches.intersection(codes_page)
            if not trouves:
                break
            for code in trouves:
                categories.setdefault(code, categorie)
    return categories


def _appliquer_categories(
    evenements: list[Evenement], timeout: float, session: requests.Session
) -> None:
    """Renseigne ``categorie`` des événements classés sur Lepointdevente."""
    codes = [code for ev in evenements if (code := code_fiche(ev.lien))]
    if not codes:
        return
    categories = categories_lepointdevente(codes, timeout, session)
    for ev in evenements:
        code = code_fiche(ev.lien)
        if code and code in categories:
            ev.categorie = categories[code]
    if categories:
        _LOG.info("Catégories Lepointdevente : %d événements classés.", len(categories))


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
def _extraire_depuis_lepointdevente(html: str) -> list[Evenement]:
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

        # Le lieu « <salle>, Sherbrooke, QC » : ville retirée, graphie unifiée.
        lieu_el = item.select_one(".feature-city")
        lieu = normaliser_lieu(lieu_el.get_text(" ", strip=True)) if lieu_el else None

        # L'affiche : <img itemprop="image" src="..."> (repli sur toute image).
        image = url_image(item.select_one("img[itemprop=image]")) or premiere_image(item)

        # Pas d'ancre dans la carte (le clic ouvre une fenêtre surgissante) :
        # on reconstruit le lien de la fiche propre à l'événement.
        lien = lien_fiche(attribut(item, "data-tpos-event"), image)

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
        evenements = _extraire_depuis_lepointdevente(liste_html)
        if evenements:
            _LOG.info("Liste Lepointdevente analysée : %d événements.", len(evenements))
            _appliquer_categories(evenements, timeout, session)
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
    nom = NOM_SALLE
    url_defaut = URL_EVENEMENTS
    categorie_defaut = "musique"
    # La catégorie déclarée sur Lepointdevente est lue par la recherche (une
    # requête par catégorie) : inutile de lire chaque fiche.
    fiche_categorisable = False

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
