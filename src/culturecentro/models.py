"""Modèle de données partagé par toutes les sources.

Un unique :class:`Evenement` sert de schéma commun : quelle que soit la salle,
un événement expose les mêmes champs, ce qui rend l'agrégation et les exports
uniformes. Les sources qui n'ont pas de sous-titre laissent simplement ce
champ à ``None`` ; ``date_fin`` n'est renseignée que pour ce qui s'étale dans
le temps (exposition, série d'ateliers, spectacle à l'affiche plusieurs jours).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

#: Colonnes utilisées pour la sérialisation CSV/JSON, dans l'ordre.
CHAMPS = (
    "titre",
    "sous_titre",
    "date_debut",
    "date_fin",
    "lien",
    "image",
    "lieu",
    "partenaire",
    "categorie",
)


@dataclass
class Evenement:
    """Un événement de la programmation d'une salle.

    ``image`` (URL de l'affiche), ``sous_titre`` et ``date_fin`` sont toujours
    présents dans la sérialisation, avec la valeur ``None`` lorsque la source
    ne les expose pas. ``date_fin`` (dernier jour d'une exposition, d'une
    série…) permet de conserver un événement **en cours** dont le début est
    déjà passé.

    ``partenaire`` est l'organisme qui programme l'événement (le nom de la
    source) ; ``lieu`` est l'endroit où il se tient, qui peut différer
    (programmation hors les murs). La source renseigne ``partenaire`` ;
    l'agrégation complète ``lieu`` avec le nom du partenaire s'il manque.

    ``categorie`` est la catégorie artistique (clé de
    :data:`culturecentro.categories.CATEGORIES`) : une source la renseigne
    quand le site l'expose ; sinon l'agrégation la détermine automatiquement.
    """

    titre: str
    date_debut: datetime | None
    lien: str | None = None
    lieu: str | None = None
    sous_titre: str | None = None
    image: str | None = None
    date_fin: datetime | None = None
    partenaire: str | None = None
    categorie: str | None = None

    def __str__(self) -> str:
        quand = self.date_debut.strftime("%Y-%m-%d %H:%M") if self.date_debut else "date inconnue"
        if self.date_fin and (
            self.date_debut is None or self.date_fin.date() != self.date_debut.date()
        ):
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
            "partenaire": self.partenaire,
            "categorie": self.categorie,
        }

    @classmethod
    def from_dict(cls, donnees: Mapping[str, Any]) -> Evenement:
        """Relit un événement sérialisé par :meth:`to_dict` (ex. : un feed JSON).

        Les clés inconnues (``id`` des pages de partage…) sont ignorées.

        Raises:
            KeyError: ``titre`` absent.
            ValueError: date qui n'est pas au format ISO 8601.
        """

        def texte(cle: str) -> str | None:
            valeur = donnees.get(cle)
            return None if valeur is None else str(valeur)

        def date(cle: str) -> datetime | None:
            valeur = donnees.get(cle)
            return datetime.fromisoformat(str(valeur)) if valeur else None

        return cls(
            titre=str(donnees["titre"]),
            date_debut=date("date_debut"),
            lien=texte("lien"),
            lieu=texte("lieu"),
            sous_titre=texte("sous_titre"),
            image=texte("image"),
            date_fin=date("date_fin"),
            partenaire=texte("partenaire"),
            categorie=texte("categorie"),
        )
