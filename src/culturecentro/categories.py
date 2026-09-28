"""Catégorie artistique d'un événement, déterminée automatiquement.

Plutôt qu'une catégorie fixée par partenaire, chaque événement est classé à
partir de **ses propres données**, par ordre de fiabilité décroissante :

1. la catégorie que la source a pu lire sur le site même (taxonomie
   WordPress du Théâtre Granada, page « jeune public » du Grand-Espace,
   nature du partenaire pour un musée ou un centre d'art) ;
2. les mots-clés du titre et du sous-titre (genre, distribution) ;
3. la **fiche de l'événement** (page `lien`) : catégories et étiquettes du
   site, type schema.org (``MusicEvent``, ``TheaterEvent``…), description ;
4. à défaut, la catégorie par défaut du partenaire.

Ce classement est déterministe, hors ligne pour les étapes 1–2, et se contente
de requêtes HTTP ordinaires pour l'étape 3 (exécutable en intégration
continue, sans service tiers ni modèle de langage).
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections.abc import Iterable

import requests
from bs4 import BeautifulSoup

from culturecentro.http import telecharger
from culturecentro.jsonld import iterer_noeuds
from culturecentro.models import Evenement

_LOG = logging.getLogger(__name__)

#: Catégories reconnues, avec leur libellé d'affichage.
CATEGORIES: dict[str, str] = {
    "theatre": "Théâtre",
    "musique": "Musique",
    "humour": "Humour",
    "danse": "Danse",
    "arts": "Arts visuels",
    "litt": "Littérature et conte",
    "jeunesse": "Jeunesse",
    "festival": "Festivals",
}

#: Libellés de taxonomie (catégories WordPress, types schema.org, filtres de
#: billetterie…) → catégorie. Clés normalisées (voir :func:`_cle`).
LIBELLES: dict[str, str] = {
    # musique
    "musique": "musique",
    "concert": "musique",
    "concerts": "musique",
    "chanson": "musique",
    "hommage": "musique",
    "variete": "musique",
    "varietes": "musique",
    "souper-spectacle": "musique",
    "musicevent": "musique",
    "spectacle musical": "musique",
    # humour
    "humour": "humour",
    "humoriste": "humour",
    "humoristes": "humour",
    "comedyevent": "humour",
    "stand-up": "humour",
    "improvisation": "humour",
    # théâtre
    "theatre": "theatre",
    "theaterevent": "theatre",
    "piece de theatre": "theatre",
    "cirque": "theatre",
    "arts de la scene": "theatre",
    "marionnettes": "theatre",
    # danse
    "danse": "danse",
    "danceevent": "danse",
    "ballet": "danse",
    # arts visuels et numériques
    "arts visuels": "arts",
    "art visuel": "arts",
    "exposition": "arts",
    "expositions": "arts",
    "exhibitionevent": "arts",
    "visualartsevent": "arts",
    "art actuel": "arts",
    "arts numeriques": "arts",
    "art numerique": "arts",
    "residence": "arts",
    "vernissage": "arts",
    # littérature et conte
    "conte": "litt",
    "contes": "litt",
    "arts litteraires": "litt",
    "litterature": "litt",
    "poesie": "litt",
    "literaryevent": "litt",
    "lecture": "litt",
    "slam": "litt",
    "arts de la parole": "litt",
    # jeunesse
    "jeune public": "jeunesse",
    "jeunesse": "jeunesse",
    "famille": "jeunesse",
    "familial": "jeunesse",
    "enfants": "jeunesse",
    "childrensevent": "jeunesse",
    # festival
    "festival": "festival",
    "festivals": "festival",
}

# Mots-clés par catégorie (expressions régulières sur le texte normalisé, sans
# accents ni majuscules). Chaque correspondance vaut un point.
_MOTS_CLES: dict[str, tuple[str, ...]] = {
    "musique": (
        r"\bconcerts?\b",
        r"\bmusiques?\b",
        r"\bmusical",
        r"\bmusicien",
        r"\bchansons?\b",
        r"\bjazz\b",
        r"\bblues\b",
        r"\brock\b",
        r"\bfolk\b",
        r"\bpunk\b",
        r"\bmetal\b",
        r"\bhip-?hop\b",
        r"\brap\b",
        r"\bdj\b",
        r"\belectro",
        r"\borchestre",
        r"\bsymphon",
        r"\bchorale?\b",
        r"\bch(oe|o)ur\b",
        r"\balbum\b",
        r"\btournee\b",
        r"\bguitar",
        r"\bpiano",
        r"\bviolon",
        r"\btrad\b",
        r"\bcountry\b",
        r"\bsoul\b",
        r"\bfunk\b",
        r"\breggae\b",
        r"\bopera\b",
        r"\bquatuor\b",
        r"\btrio\b",
        r"\bduo\b",
        r"\bgroupe\b",
        r"\bjam\b",
        r"\bjamlab",
        r"\bhommage\b",
        r"\bvariete",
        r"\bsinger",
        r"\bvoix\b",
    ),
    "humour": (
        r"\bhumou?r",
        r"\bhumoriste",
        r"\brodage\b",
        r"\bstand-?up\b",
        r"\bone-?(man|woman)",
        r"\brire\b",
        r"\bdrole\b",
        r"\bcomique\b",
        r"\bimpro(visation)?\b",
        r"\bgags?\b",
        r"\bcomedie club\b",
        r"\bcomedy\b",
        r"\bmatch d'impro",
        r"\bligue (nationale )?d'impro",
        r"\blni\b",
    ),
    "theatre": (
        r"\btheatr",
        r"\btheater\b",
        r"\bpieces?\b",
        r"\bdramatique",
        r"\bmise en scene",
        r"\bmarionnette",
        r"\bcirque",
        r"\btragedie",
        r"\bmonologue",
        r"\bcomedie\b",
        r"\bacrobat",
        r"\bimmersi",
        r"\bscenograph",
        r"\bconference theatralis",
        r"\bthéâtral",
        r"\bobjets\b",
    ),
    "danse": (
        r"\bdanses?\b",
        r"\bballet",
        r"\bchoregraph",
        r"\bbal\b",
        r"\bkrump",
        r"\bbreak(dance)?\b",
        r"\bmouvement\b",
    ),
    "litt": (
        r"\bcontes?\b",
        r"\bconteu",
        r"\bconter\b",
        r"\bcontee?s?\b",
        r"\bpoesie",
        r"\bpoet",
        r"\bslam\b",
        r"\blectures?\b",
        r"\blittera",
        r"\blivres?\b",
        r"\broman\b",
        r"\brecits?\b",
        r"\bauteur",
        r"\bautrice",
        r"\bsalon du livre",
        r"\bhistoires?\b",
        r"\bparole\b",
        r"\bbalado",
        r"\blegendes?\b",
    ),
    "arts": (
        r"\bexpo",
        r"\bvernissage",
        r"\bgalerie",
        r"\binstallation",
        r"\bart actuel",
        r"\barts? visuel",
        r"\bpeinture",
        r"\bsculpt",
        r"\bphotograph",
        r"\bphoto\b",
        r"\bestampe",
        r"\bnumerique",
        r"\bresidence",
        r"\bbiennale",
        r"\b(oe|o)uvres?\b",
        r"\bmediation",
        r"\bruches? d'art",
        r"\bmusee",
        r"\bcollection\b",
        r"\bartistes? (visuel|peintre|photographe)",
    ),
    "festival": (r"\bfestival",),
}

# Public jeunesse : indépendant du genre, prioritaire quand il est explicite.
_JEUNESSE = (
    r"\bjeune public\b",
    r"\bjeunesse\b",
    r"\bfamilial",
    r"\ben famille\b",
    r"\bpour (les )?enfants\b",
    r"\bpour (les )?(tout-?)?petits\b",
    r"\btout-?petits\b",
    r"\bpetits et grands\b",
    r"\b(des|de|a partir de|pour les)\s+\d{1,2}\s+(a\s+\d{1,2}\s+)?ans\b",
    r"\b\d{1,2}\s+ans\s*(et\s+plus|\+)",
    r"\bmarmots?\b",
    r"\bmarionnettes? pour",
)

#: Ordre de priorité en cas d'égalité de score.
_PRIORITE = ("festival", "humour", "danse", "litt", "arts", "theatre", "musique")

_COMPILES = {cat: [re.compile(m) for m in motifs] for cat, motifs in _MOTS_CLES.items()}
_COMPILES_JEUNESSE = [re.compile(m) for m in _JEUNESSE]


def _cle(texte: str) -> str:
    """Minuscules, sans accents, espaces unifiés (les tirets sont conservés)."""
    texte = texte.replace("’", "'").replace("œ", "oe").replace("Œ", "OE").replace("æ", "ae")
    sans = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return " ".join(sans.casefold().split())


def depuis_libelle(libelle: str | None) -> str | None:
    """Catégorie d'un libellé de taxonomie exact (« Musique », « MusicEvent »…)."""
    if not libelle:
        return None
    k = _cle(libelle).strip(" .:")
    if k in LIBELLES:
        return LIBELLES[k]
    # « Exposition temporaire », « Théâtre jeune public » : premier mot-clé de la table.
    for cle_libelle, categorie in LIBELLES.items():
        if re.search(rf"\b{re.escape(cle_libelle)}\b", k):
            return categorie
    return None


def deviner(*textes: str | None, seuil: int = 1, public: bool = True) -> str | None:
    """Catégorie la plus probable d'après des textes libres (titre, genre, description).

    Le public jeunesse, lorsqu'il est explicite, l'emporte sur le genre
    (désactivable avec ``public=False`` pour un texte long où la mention peut
    concerner autre chose). Sinon la catégorie au plus grand nombre de
    mots-clés gagne ; les égalités sont départagées par :data:`_PRIORITE`.
    ``None`` si aucun mot-clé (score inférieur à ``seuil``).
    """
    texte = _cle(" ".join(t for t in textes if t))
    if not texte:
        return None
    if public and any(m.search(texte) for m in _COMPILES_JEUNESSE):
        return "jeunesse"
    scores = {cat: sum(1 for m in motifs if m.search(texte)) for cat, motifs in _COMPILES.items()}
    meilleur = max(scores.values())
    if meilleur < seuil:
        return None
    for cat in _PRIORITE:
        if scores[cat] == meilleur:
            return cat
    return None


# --------------------------------------------------------------------------- #
# Fiche de l'événement
# --------------------------------------------------------------------------- #
_SELECTEURS_TAXONOMIE = (
    "a[rel~=category]",
    "a[rel~=tag]",
    ".cat-links a",
    ".categories a",
    ".category a",
    ".event-categories a",
    ".tribe-events-event-categories a",
    ".tags a",
    ".tag a",
    ".genre",
    ".discipline",
    ".evcal_event_types a",
    ".ect-event-category",
)


def depuis_page(html: str) -> str | None:
    """Catégorie d'après la fiche d'un événement (taxonomie, schema.org, texte)."""
    soup = BeautifulSoup(html, "html.parser")

    # 1. Catégories et étiquettes affichées par le site.
    for selecteur in _SELECTEURS_TAXONOMIE:
        for element in soup.select(selecteur):
            categorie = depuis_libelle(element.get_text(" ", strip=True))
            if categorie:
                return categorie

    # 2. Type schema.org de l'événement (MusicEvent, TheaterEvent…).
    for balise in soup.find_all("script", type="application/ld+json"):
        try:
            donnees = json.loads(balise.string or balise.get_text() or "")
        except json.JSONDecodeError:
            continue
        for noeud in iterer_noeuds(donnees):
            types = noeud.get("@type", [])
            for t in types if isinstance(types, list) else [types]:
                if isinstance(t, str) and (categorie := depuis_libelle(t)):
                    return categorie
            for cle_ in ("genre", "keywords", "category"):
                valeur = noeud.get(cle_)
                textes: Iterable[str] = valeur if isinstance(valeur, list) else [str(valeur or "")]
                for texte in textes:
                    if isinstance(texte, str) and (categorie := depuis_libelle(texte)):
                        return categorie

    # 3. Mots-clés du titre et des métadonnées (public jeunesse compris)…
    en_tete: list[str] = []
    if soup.title:
        en_tete.append(soup.title.get_text(" ", strip=True))
    for meta in soup.select(
        "meta[name=description], meta[property='og:description'], meta[name=keywords]"
    ):
        contenu = meta.get("content")
        if isinstance(contenu, str):
            en_tete.append(contenu)
    categorie = deviner(*en_tete)
    if categorie:
        return categorie

    # 4. … puis du contenu principal, sans menus ni barres latérales. Le
    # public jeunesse n'est pas déduit d'un texte long (mentions incidentes).
    for indesirable in soup.select(
        "nav, header, footer, aside, script, style, noscript, form, "
        "[role=navigation], .menu, .sidebar, .widget, #main-header, #et-top-navigation, "
        ".site-header, .site-footer, .evo_lightboxes"
    ):
        indesirable.decompose()
    principal = soup.select_one(
        ".eventon_full_description, .entry-content, .single-content, article, main, #content, body"
    )
    if principal is None:
        return None
    return deviner(principal.get_text(" ", strip=True)[:2500], seuil=2, public=False)


class Categorisation:
    """Classe les événements, avec un cache des fiches déjà lues.

    Args:
        session: session HTTP pour lire les fiches ; ``None`` désactive
            cette étape (classement hors ligne seulement).
        timeout: délai réseau par fiche.
        maximum_fiches: garde-fou sur le nombre de fiches lues par exécution.
    """

    def __init__(
        self,
        session: requests.Session | None = None,
        timeout: float = 20.0,
        maximum_fiches: int = 120,
    ) -> None:
        self.session = session
        self.timeout = timeout
        self.maximum_fiches = maximum_fiches
        self._cache: dict[str, str | None] = {}
        self.fiches_lues = 0

    def _depuis_fiche(self, lien: str) -> str | None:
        if lien in self._cache:
            return self._cache[lien]
        if self.session is None or self.fiches_lues >= self.maximum_fiches:
            return None
        self.fiches_lues += 1
        try:
            html = telecharger(lien, self.timeout, session=self.session)
        except requests.RequestException as exc:
            _LOG.debug("Fiche %s illisible : %s", lien, exc)
            self._cache[lien] = None
            return None
        categorie = depuis_page(html)
        self._cache[lien] = categorie
        return categorie

    def categoriser(
        self, ev: Evenement, defaut: str | None = None, *, lire_fiche: bool = True
    ) -> str | None:
        """Catégorie de ``ev`` : source, mots-clés, fiche (si ``lire_fiche``), puis ``defaut``."""
        if ev.categorie:
            return ev.categorie
        categorie = deviner(ev.titre, ev.sous_titre)
        if categorie is None and ev.lien and lire_fiche:
            categorie = self._depuis_fiche(ev.lien)
        return categorie or defaut


def categoriser(ev: Evenement, defaut: str | None = None) -> str | None:
    """Raccourci hors ligne (sans lecture de fiche) de :meth:`Categorisation.categoriser`."""
    return Categorisation(session=None).categoriser(ev, defaut)
