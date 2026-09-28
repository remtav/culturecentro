#!/usr/bin/env python3
"""Génère ``coverage.svg`` (badge de couverture) sans dépendance externe.

Lit les données de couverture déjà mesurées (fichier ``.coverage`` produit
par ``coverage run``) et écrit un badge SVG de style « flat ». Contrairement
à ``coverage-badge``, ce script ne dépend pas de ``pkg_resources`` (retiré
des versions récentes de setuptools).

Usage ::

    coverage run -m unittest discover -s tests
    python scripts/coverage_badge.py -o coverage.svg
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

import coverage

# Seuils de couleur, style shields.io.
_COULEURS = [
    (95, "#4c1"),  # brightgreen
    (90, "#97ca00"),  # green
    (75, "#a4a61d"),  # yellowgreen
    (60, "#dfb317"),  # yellow
    (40, "#fe7d37"),  # orange
    (0, "#e05d44"),  # red
]


def _pourcentage() -> int:
    """Renvoie le pourcentage de couverture total (entier arrondi)."""
    cov = coverage.Coverage()
    cov.load()
    total = cov.report(file=io.StringIO())
    return round(total)


def _couleur(pct: int) -> str:
    for seuil, couleur in _COULEURS:
        if pct >= seuil:
            return couleur
    return _COULEURS[-1][1]


def _svg(pct: int) -> str:
    label = "coverage"
    valeur = f"{pct}%"
    # Largeurs approximatives (6px par caractère + marge), suffisantes pour un
    # rendu propre sans métriques de police.
    largeur_label = 6 * len(label) + 10
    largeur_valeur = 6 * len(valeur) + 10
    largeur = largeur_label + largeur_valeur
    couleur = _couleur(pct)
    centre_label = largeur_label / 2
    centre_valeur = largeur_label + largeur_valeur / 2
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{largeur}" height="20" role="img" aria-label="{label}: {valeur}">
  <title>{label}: {valeur}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{largeur}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{largeur_label}" height="20" fill="#555"/>
    <rect x="{largeur_label}" width="{largeur_valeur}" height="20" fill="{couleur}"/>
    <rect width="{largeur}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{centre_label}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{centre_label}" y="14">{label}</text>
    <text x="{centre_valeur}" y="15" fill="#010101" fill-opacity=".3">{valeur}</text>
    <text x="{centre_valeur}" y="14">{valeur}</text>
  </g>
</svg>
"""


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument(
        "-o", "--sortie", default="coverage.svg", type=Path, help="Fichier SVG à écrire."
    )
    args = parseur.parse_args(argv)
    pct = _pourcentage()
    args.sortie.write_text(_svg(pct), encoding="utf-8")
    print(f"Badge écrit dans {args.sortie} ({pct}%).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
