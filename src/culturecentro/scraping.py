"""Utilitaires d'analyse HTML partagés (BeautifulSoup)."""

from __future__ import annotations

from bs4 import Tag


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
