"""Modèle de données partagé par toutes les sources.

Un unique :class:`Evenement` sert de schéma commun : quelle que soit la salle,
un événement expose les mêmes champs, ce qui rend l'agrégation et les exports
uniformes. Les sources qui n'ont pas de sous-titre laissent simplement ce
champ à ``None`` ; ``date_fin`` n'est renseignée que pour ce qui s'étale dans
le temps (exposition, série d'ateliers, spectacle à l'affiche plusieurs jours).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

#: Colonnes utilisées pour la sérialisation CSV/JSON, dans l'ordre.
CHAMPS = ("titre", "sous_titre", "date_debut", "date_fin", "lien", "image", "lieu")


@dataclass
class Evenement:
    """Un événement de la programmation d'une salle.

    ``image`` (URL de l'affiche), ``sous_titre`` et ``date_fin`` sont toujours
    présents dans la sérialisation, avec la valeur ``None`` lorsque la source
    ne les expose pas. ``date_fin`` (dernier jour d'une exposition, d'une
    série…) permet de conserver un événement **en cours** dont le début est
    déjà passé.
    """

    titre: str
    date_debut: datetime | None
    lien: str | None = None
    lieu: str | None = None
    sous_titre: str | None = None
    image: str | None = None
    date_fin: datetime | None = None

    def __str__(self) -> str:
        quand = self.date_debut.strftime("%Y-%m-%d %H:%M") if self.date_debut else "date inconnue"
        if self.date_fin:
            quand += " → " + self.date_fin.strftime("%Y-%m-%d")
        titre = self.titre + (f" — {self.sous_titre}" if self.sous_titre else "")
        return f"{quand} — {titre}" + (f" ({self.lien})" if self.lien else "")

    def to_dict(self) -> dict[str, str | None]:
        """Représentation sérialisable (date au format ISO 8601)."""
        return {
            "titre": self.titre,
            "sous_titre": self.sous_titre,
            "date_debut": self.date_debut.isoformat() if self.date_debut else None,
            "date_fin": self.date_fin.isoformat() if self.date_fin else None,
            "lien": self.lien,
            "image": self.image,
            "lieu": self.lieu,
        }
