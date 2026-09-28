"""Interface en ligne de commande partagée par les sources.

Chaque module de source expose un ``main`` qui délègue à :func:`executer`
avec son instance de :class:`~culturecentro.sources.base.Source`.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

import requests

from culturecentro.exporters import exporter_csv, exporter_json, exporter_texte
from culturecentro.sources.base import Source

_LOG = logging.getLogger(__name__)


def construire_parseur(description: str, url_defaut: str) -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(description=description)
    parseur.add_argument("--url", default=url_defaut, help="Page de programmation à analyser.")
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


def executer(source: Source, argv: Sequence[str] | None = None) -> int:
    """Exécute la CLI pour une source et renvoie le code de sortie du processus."""
    args = construire_parseur(source.description, source.url_defaut).parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        evenements = source.lister_evenements_a_venir(args.url, timeout=args.timeout)
    except requests.RequestException as exc:
        _LOG.error("Échec du téléchargement de %s : %s", args.url, exc)
        return 1

    if args.format == "csv":
        contenu = exporter_csv(evenements, args.sortie)
    elif args.format == "json":
        contenu = exporter_json(evenements, args.sortie)
    else:
        contenu = exporter_texte(evenements, args.sortie)

    if args.sortie is None:
        print(contenu)
    return 0
