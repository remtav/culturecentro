"""Interface en ligne de commande partagée par les sources.

Chaque module de source expose un ``main`` qui délègue à :func:`executer`
avec son instance de :class:`~culturecentro.sources.base.Source`.
"""

from __future__ import annotations

import argparse
import json
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

    pages = sous.add_parser(
        "pages",
        help="Génère les pages de partage (aperçu riche) ; ajoute leurs identifiants au feed.",
    )
    pages.add_argument(
        "--feed",
        type=Path,
        default=Path("web/data/evenements.json"),
        help="Feed JSON produit par « lister » (défaut : web/data/evenements.json).",
    )
    pages.add_argument(
        "--dossier", type=Path, default=Path("web"), help="Racine du site (défaut : web)."
    )
    pages.add_argument(
        "--url-base",
        required=True,
        help="Adresse publique du site, ex. https://remtav.github.io/culturecentro/",
    )
    pages.add_argument(
        "-v", "--verbose", action="store_true", help="Journalisation détaillée (DEBUG)."
    )
    return parseur


def _generer_pages(feed_chemin: Path, dossier: Path, url_base: str) -> int:
    """Sous-commande ``pages`` : identifiants dans le feed, puis une page par événement."""
    from culturecentro.partage import attribuer_identifiants, generer_pages

    try:
        feed = json.loads(feed_chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _LOG.error("Feed illisible (%s) : %s", feed_chemin, exc)
        return 1
    if not isinstance(feed, list) or not all(isinstance(ev, dict) for ev in feed):
        _LOG.error("Feed inattendu (%s) : une liste d'événements est attendue.", feed_chemin)
        return 1
    try:
        attribuer_identifiants(feed)
        ecrites = generer_pages(feed, dossier, url_base)
    except ValueError as exc:
        _LOG.error("%s", exc)
        return 2
    feed_chemin.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _LOG.info("%d pages de partage écrites dans %s", ecrites, dossier / "e")
    return 0


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

    if args.commande == "pages":
        return _generer_pages(args.feed, args.dossier, args.url_base)

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
