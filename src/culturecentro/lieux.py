"""Lieux : noms canoniques et périmètre du centre-ville de Sherbrooke.

Les sources livrent des libellés de lieu hétérogènes (« Le Grand Espace » /
« Le Grand-Espace », « Salle multifonctionnelle du Tremplin »…) et certaines
programmations (Maison des arts de la parole) incluent des dates hors
Sherbrooke. Ce module fournit :

* :func:`normaliser_lieu` : ramène un libellé à son nom canonique, insensible
  à la casse, aux accents et au tiret ;
* :func:`est_centre_ville` : décide si un lieu (et son adresse, lorsqu'elle
  est connue) appartient au centre-ville — heuristique documentée, fondée sur
  une liste de lieux connus et de rues du centre-ville, et sur des marqueurs
  de lieux hors périmètre (autres municipalités, campus…).

Les listes sont volontairement simples et éditables : elles constituent la
« carte » du projet, à ajuster quand un nouveau lieu apparaît.
"""

from __future__ import annotations

import re
import unicodedata

#: Nom canonique de chaque lieu connu du centre-ville, indexé par sa clé de
#: comparaison (voir :func:`cle`). Les partenaires y figurent, ainsi que les
#: salles et cafés qui accueillent leurs programmations hors les murs.
LIEUX_CENTRE_VILLE: dict[str, str] = {}

_NOMS_CENTRE_VILLE = (
    "Théâtre Granada",
    "La Petite Boîte Noire",
    "Maison des arts de la parole",
    "Le Tremplin 16-30",
    "Musée des beaux-arts de Sherbrooke",
    "Sporobole",
    "Le Grand-Espace",
    "Centre des arts de la scène Jean-Besré",
    "Café 440",
    "Café du Couvent",
    "Café Masala",
    "Kaapeh",
    "Bibliothèque Éva-Senécal",
    "Théâtre du Double signe",
    "Le Petit Théâtre de Sherbrooke",
    "Boquébière",
    "Le Murmure",
    "Marché de la Gare",
    "Place des Moulins",
    "Parc Jacques-Cartier",
    "Hôtel de ville de Sherbrooke",
    "Basilique-cathédrale Saint-Michel",
    "Église Plymouth-Trinity",
    "Centre-ville de Sherbrooke",
)

#: Variantes de libellé → nom canonique (clés de comparaison).
_ALIAS = {
    "le grand espace": "Le Grand-Espace",
    "grand espace": "Le Grand-Espace",
    "grand-espace": "Le Grand-Espace",
    "le grand-espace - cajb": "Le Grand-Espace",
    "centre des arts de la scene jean-besre": "Le Grand-Espace",
    "salle multifonctionnelle du tremplin": "Le Tremplin 16-30",
    "tremplin 16-30": "Le Tremplin 16-30",
    "le tremplin": "Le Tremplin 16-30",
    "la petite boite noire": "La Petite Boîte Noire",
    "petite boite noire": "La Petite Boîte Noire",
    "granada": "Théâtre Granada",
    "theatre granada": "Théâtre Granada",
    "mbas": "Musée des beaux-arts de Sherbrooke",
    "musee des beaux-arts": "Musée des beaux-arts de Sherbrooke",
    "musee des beaux-arts de sherbrooke (mbas)": "Musée des beaux-arts de Sherbrooke",
    "maison des arts de la parole": "Maison des arts de la parole",
    "cafe 440": "Café 440",
}

#: Rues du centre-ville (clés de comparaison). Une adresse qui en contient
#: une est considérée au centre-ville.
RUES_CENTRE_VILLE = (
    "wellington",
    "dufferin",
    "frontenac",
    "du depot",
    "rue depot",
    "du couvent",
    "marquette",
    "belvedere",
    "meadow",
    "alexandre",
    "bank",
    "ball",
    "camirand",
    "sanborn",
    "peel",
    "grandes-fourches",
    "grandes fourches",
    "gillespie",
    "aberdeen",
    "king ouest",
    "king est",
    "lansdowne",
    "montreal",
    "de la cathedrale",
    "du moulin",
    "des fusiliers",
    "place de la gare",
    "minto",
    "bowen sud",
    "olivier",
    "laurier",
)

#: Marqueurs (clés de comparaison) d'un lieu **hors** du centre-ville :
#: autres municipalités de l'Estrie et environs, campus universitaire,
#: arrondissements périphériques.
MARQUEURS_HORS_CENTRE_VILLE = (
    "richmond",
    "coaticook",
    "saint-adrien",
    "st-adrien",
    "frelighsburg",
    "north hatley",
    "capelton",
    "valcourt",
    "magog",
    "danville",
    "windsor",
    "bromptonville",
    "lennoxville",
    "rock forest",
    "fleurimont",
    "ascot corner",
    "east angus",
    "cookshire",
    "eastman",
    "orford",
    "sutton",
    "granby",
    "drummondville",
    "montreal, qc",
    "quebec, qc",
    "universite de sherbrooke",
    "universite bishop",
    "bishop's",
    "cegep de sherbrooke",
    "mont-bellevue",
    "base de plein air",
    "j.-a.-bombardier",
)


def cle(texte: str) -> str:
    """Clé de comparaison : minuscules, sans accents, espaces et tirets unifiés."""
    texte = texte.replace("’", "'").replace("œ", "oe").replace("Œ", "OE")
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    sans_accents = sans_accents.casefold()
    sans_accents = re.sub(r"\s*-\s*", "-", sans_accents)
    return " ".join(sans_accents.split())


for _nom in _NOMS_CENTRE_VILLE:
    LIEUX_CENTRE_VILLE[cle(_nom)] = _nom
    LIEUX_CENTRE_VILLE[cle(_nom).replace("-", " ")] = _nom
for _variante, _nom in _ALIAS.items():
    LIEUX_CENTRE_VILLE[cle(_variante)] = _nom

_SUFFIXE_VILLE = re.compile(r"\s*,\s*sherbrooke(\s*,\s*(qc|quebec))?\s*$", re.IGNORECASE)


def normaliser_lieu(texte: str | None) -> str | None:
    """Nom canonique d'un lieu, ou le libellé nettoyé s'il est inconnu.

    * retire un suffixe « , Sherbrooke, QC » ;
    * ramène les variantes connues (casse, accents, tiret, alias) au nom
      canonique de :data:`LIEUX_CENTRE_VILLE` ;
    * renvoie ``None`` pour un texte vide.
    """
    if texte is None:
        return None
    lieu = " ".join(texte.split())
    lieu = _SUFFIXE_VILLE.sub("", cle(lieu)) if _SUFFIXE_VILLE.search(cle(lieu)) else lieu
    if not lieu:
        return None
    k = cle(lieu)
    if k in LIEUX_CENTRE_VILLE:
        return LIEUX_CENTRE_VILLE[k]
    if k.replace("-", " ") in LIEUX_CENTRE_VILLE:
        return LIEUX_CENTRE_VILLE[k.replace("-", " ")]
    # Suffixe de ville retiré mais libellé inconnu : on garde le texte original
    # nettoyé (sans le suffixe), avec sa casse d'origine.
    original = " ".join(texte.split())
    m = _SUFFIXE_VILLE.search(original)
    return original[: m.start()] if m else original


def est_centre_ville(lieu: str | None, adresse: str | None = None) -> bool:
    """Vrai si l'événement se tient au centre-ville de Sherbrooke.

    Règles, dans l'ordre :

    1. un lieu connu (:data:`LIEUX_CENTRE_VILLE`) est au centre-ville ;
    2. un marqueur hors périmètre dans le lieu ou l'adresse (autre
       municipalité, campus…) exclut ;
    3. avec une adresse, il faut une rue du centre-ville ;
    4. sans adresse ni marqueur (lieu inconnu, « Lieu à confirmer »), on
       accorde le bénéfice du doute : le partenaire, lui, est au centre-ville.
    """
    if lieu and cle(lieu) in LIEUX_CENTRE_VILLE:
        return True
    texte = cle(f"{lieu or ''} {adresse or ''}")
    if any(marqueur in texte for marqueur in MARQUEURS_HORS_CENTRE_VILLE):
        return False
    if adresse:
        adresse_cle = cle(adresse)
        return any(rue in adresse_cle for rue in RUES_CENTRE_VILLE)
    return True
