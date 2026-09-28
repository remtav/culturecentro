"""Utilitaires d'analyse HTML partagés (BeautifulSoup)."""

from __future__ import annotations

import re

from bs4 import Tag

#: Attributs d'une ``<img>`` susceptibles de porter l'URL réelle, par priorité.
#: Les thèmes « lazy » mettent un pixel transparent dans ``src`` et l'URL
#: réelle dans un attribut ``data-*`` ; on essaie donc ceux-ci d'abord.
_ATTRIBUTS_IMG = ("data-src", "data-lazy-src", "data-original", "src")

_ATTRIBUTS_SRCSET = ("data-srcset", "srcset")

# url("…"), url('…') ou url(…) dans un attribut ``style``.
_URL_CSS = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""", re.IGNORECASE)


def attribut(element: Tag, nom: str) -> str | None:
    """Valeur d'un attribut HTML, normalisée en ``str`` (ou ``None``).

    BeautifulSoup renvoie une **liste** pour les attributs multivalués
    (``class``, ``rel``…) ; pour les attributs simples (``href``, ``src``,
    ``datetime``, ``data-*``…) on veut une chaîne. On renvoie la valeur si
    c'est une chaîne, le premier élément d'une liste non vide, sinon ``None``.
    """
    valeur = element.get(nom)
    if isinstance(valeur, str):
        return valeur
    if isinstance(valeur, list) and valeur:
        premier = valeur[0]
        return premier if isinstance(premier, str) else None
    return None


def _est_url_utilisable(url: str | None) -> bool:
    """Écarte les valeurs vides et les pixels de substitution (``data:``)."""
    if not url:
        return False
    url = url.strip()
    return bool(url) and not url.lower().startswith("data:")


def _premiere_source_srcset(srcset: str) -> str | None:
    """Première URL d'un ``srcset`` (« url 366w, url2 732w »)."""
    for candidat in srcset.split(","):
        url = candidat.strip().split(" ", 1)[0]
        if _est_url_utilisable(url):
            return url
    return None


def url_image(element: Tag | None) -> str | None:
    """URL de l'image portée par ``element``, quel que soit son mécanisme.

    Gère les ``<img>`` classiques (``src``), les images chargées à la demande
    (``data-src``, ``data-lazy-src``, ``data-original``, ``srcset``) et les
    éléments dont l'image est un fond CSS (``style="background-image:url(…)"``).
    Renvoie ``None`` si aucune URL exploitable n'est trouvée.
    """
    if element is None:
        return None

    for nom in _ATTRIBUTS_IMG:
        valeur = attribut(element, nom)
        if _est_url_utilisable(valeur):
            return (valeur or "").strip()

    for nom in _ATTRIBUTS_SRCSET:
        valeur = attribut(element, nom)
        if valeur:
            url = _premiere_source_srcset(valeur)
            if url:
                return url

    style = attribut(element, "style")
    if style:
        m = _URL_CSS.search(style)
        if m and _est_url_utilisable(m.group(1)):
            return m.group(1).strip()

    return None


def premiere_image(conteneur: Tag | None) -> str | None:
    """Première image exploitable dans ``conteneur`` (``<img>`` ou fond CSS).

    Repli pratique pour les sources qui n'ont pas de balise d'image dédiée :
    on parcourt le conteneur et l'on renvoie la première URL trouvée.
    """
    if conteneur is None:
        return None
    url = url_image(conteneur)
    if url:
        return url
    for element in conteneur.find_all(True):
        if not isinstance(element, Tag):
            continue
        if element.name == "img" or element.get("style"):
            url = url_image(element)
            if url:
                return url
    return None
