"""culturecentro — agrégation de la programmation culturelle du centre-ville.

Ce paquet regroupe les *scrapers* d'événements des salles de spectacle
(sous-paquet :mod:`culturecentro.sources`, une source par salle inscrite au
registre :data:`~culturecentro.sources.SOURCES`) et le cœur commun qu'ils
partagent : modèle d'événement (:mod:`~culturecentro.models`), client HTTP
(:mod:`~culturecentro.http`), analyse des dates françaises
(:mod:`~culturecentro.dates`), filtrage (:mod:`~culturecentro.filtrage`),
exports (:mod:`~culturecentro.exporters`) et agrégation
(:mod:`~culturecentro.aggregate`). Chaque source n'implémente que
l'extraction propre à son site.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
