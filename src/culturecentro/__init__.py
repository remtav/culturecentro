"""culturecentro — agrégation de la programmation culturelle du centre-ville.

Ce paquet regroupe les *scrapers* d'événements des salles de spectacle
(sous-paquet :mod:`culturecentro.sources`) qui partageront, au fil de la
migration, un cœur commun (modèle d'événement, client HTTP, analyse des dates
françaises, exports). À ce stade, chaque source reste autonome.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
