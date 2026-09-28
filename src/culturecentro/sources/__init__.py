"""Sources d'événements, une par salle de spectacle.

Chaque module expose la même interface publique
(``lister_evenements_a_venir``, ``exporter_json``, ``exporter_csv``, ``main``).
Un registre commun et une classe de base seront introduits à une étape
ultérieure de la migration.
"""

from __future__ import annotations
