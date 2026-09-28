"""Interface commune à toutes les sources d'événements.

Une :class:`Source` n'implémente que l'extraction propre à un site
(:meth:`Source.extraire`) ; toute l'orchestration — session HTTP,
téléchargement, seuil temporel par défaut, déduplication et tri — est fournie
ici et partagée par toutes les salles.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import requests

from culturecentro.filtrage import finaliser, minuit_utc
from culturecentro.http import creer_session, telecharger
from culturecentro.models import Evenement


class Source(ABC):
    """Une salle de spectacle dont on récupère la programmation.

    Les sous-classes définissent les attributs :attr:`slug`, :attr:`nom` et
    :attr:`url_defaut`, puis implémentent :meth:`extraire`.
    """

    #: Identifiant court et stable (ex. ``"theatre-granada"``).
    slug: str
    #: Nom affichable de la salle.
    nom: str
    #: Page de programmation analysée par défaut.
    url_defaut: str
    #: Catégorie artistique retenue quand rien ne permet d'en déterminer une
    #: (clé de :data:`culturecentro.categories.CATEGORIES`).
    categorie_defaut: str | None = None
    #: Faux si la fiche d'un événement (``lien``) n'apporte rien pour le
    #: classement (ex. : lien vers la liste de la billetterie).
    fiche_categorisable: bool = True

    @property
    def description(self) -> str:
        """Description pour l'aide en ligne de commande."""
        return f"Liste les événements à venir de {self.nom}."

    @abstractmethod
    def extraire(self, html: str, timeout: float, session: requests.Session) -> list[Evenement]:
        """Extrait les événements bruts à partir du HTML de :attr:`url_defaut`.

        ``session`` et ``timeout`` permettent les requêtes secondaires (AJAX,
        billetterie…). La déduplication et le tri sont faits par l'appelant.
        """

    def lister_evenements_a_venir(
        self,
        url: str | None = None,
        *,
        a_partir_de: datetime | None = None,
        timeout: float = 20.0,
    ) -> list[Evenement]:
        """Retourne les événements à venir, dédupliqués et triés par date.

        Le ``partenaire`` de chaque événement est renseigné avec :attr:`nom`
        s'il ne l'est pas déjà.

        Args:
            url: page à analyser (défaut : :attr:`url_defaut`).
            a_partir_de: seuil temporel ; par défaut minuit du jour courant
                (UTC). Les événements sans date connue sont conservés.
            timeout: délai d'attente réseau, en secondes.

        Raises:
            requests.RequestException: en cas d'échec réseau lors du
                téléchargement de la page.
        """
        url = url or self.url_defaut
        if a_partir_de is None:
            a_partir_de = minuit_utc()

        session = creer_session()
        try:
            html = telecharger(url, timeout, session=session)
            evenements = self.extraire(html, timeout, session)
        finally:
            session.close()

        for ev in evenements:
            if not ev.partenaire:
                ev.partenaire = self.nom
        return finaliser(evenements, a_partir_de)
