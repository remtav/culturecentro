"""Exports partagés : texte, CSV et JSON, à partir du schéma commun."""

from __future__ import annotations

import csv
import io
import json
import logging
from collections.abc import Iterable
from pathlib import Path

from culturecentro.models import CHAMPS, Evenement

_LOG = logging.getLogger(__name__)


def exporter_texte(evenements: Iterable[Evenement], fichier: str | Path | None = None) -> str:
    """Sérialise les événements en texte (une ligne par événement).

    Écrit dans ``fichier`` s'il est fourni, et renvoie toujours la chaîne.
    """
    evenements = list(evenements)
    texte = "\n".join(str(ev) for ev in evenements)
    if fichier is not None:
        Path(fichier).write_text(texte + "\n", encoding="utf-8")
        _LOG.info("%d événements écrits dans %s", len(evenements), fichier)
    return texte


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
