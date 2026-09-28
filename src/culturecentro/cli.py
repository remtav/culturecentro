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
from culturecentro.models import Evenement
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

    _sortir(evenements, args.format, args.sortie)
    return 0


def _sortir(evenements: list[Evenement], format_: str, sortie: Path | None) -> None:
    """Sérialise les événements dans le format demandé (fichier ou stdout)."""
    if format_ == "csv":
        contenu = exporter_csv(evenements, sortie)
    elif format_ == "json":
        contenu = exporter_json(evenements, sortie)
    else:
        contenu = exporter_texte(evenements, sortie)
    if sortie is None:
        print(contenu)


# --------------------------------------------------------------------------- #
# CLI unifiée (python -m culturecentro / commande « culturecentro »)
# --------------------------------------------------------------------------- #
def _construire_parseur_principal() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(
        prog="culturecentro",
        description="Agrège la programmation des salles du centre-ville de Sherbrooke.",
    )
    sous = parseur.add_subparsers(dest="commande", required=True)

    sous.add_parser("sources", help="Liste les salles disponibles.")

    lister = sous.add_parser(
        "lister", help="Liste les événements à venir (toutes les salles par défaut)."
    )
    lister.add_argument(
        "--source",
        action="append",
        metavar="SLUG",
        help="Limiter à cette salle (répétable). Par défaut : toutes.",
    )
    lister.add_argument(
        "--format",
        choices=("texte", "csv", "json"),
        default="texte",
        help="Format de sortie (défaut : texte).",
    )
    lister.add_argument("-o", "--sortie", type=Path, help="Fichier de sortie (défaut : stdout).")
    lister.add_argument("--timeout", type=float, default=20.0, help="Délai réseau en secondes.")
    lister.add_argument(
        "--sans-fiches",
        action="store_true",
        help="Ne pas lire la fiche des événements pour déterminer leur catégorie.",
    )
    lister.add_argument(
        "-v", "--verbose", action="store_true", help="Journalisation détaillée (DEBUG)."
    )
    return parseur


def principal(argv: Sequence[str] | None = None) -> int:
    """Point d'entrée de la CLI unifiée ``culturecentro``."""
    # Imports différés : évite tout cycle d'import au chargement du module.
    from culturecentro.aggregate import agreger
    from culturecentro.sources import SOURCES, obtenir

    args = _construire_parseur_principal().parse_args(argv)

    if args.commande == "sources":
        for slug, source in sorted(SOURCES.items()):
            print(f"{slug}\t{source.nom}")
        return 0

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.source:
        try:
            sources = [obtenir(slug) for slug in args.source]
        except KeyError as exc:
            _LOG.error("Salle inconnue : %s (voir « culturecentro sources »).", exc.args[0])
            return 2
    else:
        sources = None  # toutes

    try:
        evenements = agreger(sources, timeout=args.timeout, lire_fiches=not args.sans_fiches)
    except requests.RequestException as exc:
        _LOG.error("Échec de l'agrégation : %s", exc)
        return 1

    _sortir(evenements, args.format, args.sortie)
    return 0
