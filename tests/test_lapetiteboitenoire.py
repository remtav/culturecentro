"""Tests unitaires pour lapetiteboitenoire (sans accès réseau).

Les tests couvrent l'analyse des dates françaises, la découverte de l'URL de
la billetterie, l'extraction des cartes Lepointdevente à partir d'un fragment
HTML figé, la finalisation (déduplication, filtrage, tri) et les exports.

Exécution ::

    python -m unittest discover -s tests
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lapetiteboitenoire as lpbn  # noqa: E402
from lapetiteboitenoire import (  # noqa: E402
    URL_BILLETTERIE_DEFAUT,
    Evenement,
    _extraire_depuis_lepointdevente,
    _finaliser,
    _parse_date_fr,
    _trouver_url_billetterie,
    exporter_csv,
    exporter_json,
)

# Fragment reproduisant deux cartes réelles de la liste Lepointdevente.
# L'entité HTML (d&#039;) et la balise interne ``tag-attendance`` du titre
# sont présentes pour vérifier qu'elles sont bien gérées.
FRAGMENT_LISTE = """
<div id="events-list" class="feature feature-grid">
  <div class="feature-row">
    <div class="feature-col is-small" data-tpos-event="529998" style="cursor: pointer">
      <article class="feature-canvas has-tag">
        <div class="feature-content">
          <img itemprop="image" src="https://tpos.s3.amazonaws.com/events/PBN/26/09/30/001/pbn260930001-1152x648-fr.png" alt="Juste Miben">
          <h3 class="feature-title"><div class="tag-attendance-offline" title="Événement en personne"></div>Juste Miben (supplémentaire)</h3>
          <div class="feature-date">30 septembre 2026, 20h00</div>
          <div class="feature-city">La Petite boite noire, Sherbrooke, QC</div>
          <div class="feature-tag">Complet</div>
        </div>
      </article>
    </div>
    <div class="feature-col is-small tpos-add-to-cart" data-tpos-event="541978" style="cursor: pointer">
      <article class="feature-canvas has-button show-queue">
        <div class="feature-content">
          <h3 class="feature-title">Les Frayeurs d&#039;ailleurs</h3>
          <div class="feature-date">1er octobre 2026, 20h00</div>
          <div class="feature-city">La Petite boite noire, Sherbrooke, QC</div>
        </div>
      </article>
    </div>
  </div>
</div>
"""

URL_BASE = "https://lepointdevente.com/billets/programmationavenir"


class TestParseDateFr(unittest.TestCase):
    def test_date_avec_virgule(self):
        self.assertEqual(
            _parse_date_fr("30 septembre 2026, 20h00"),
            datetime(2026, 9, 30, 20, 0),
        )

    def test_premier_du_mois(self):
        self.assertEqual(_parse_date_fr("1er octobre 2026, 20h00"), datetime(2026, 10, 1, 20, 0))

    def test_sans_heure(self):
        self.assertEqual(_parse_date_fr("8 août 2026"), datetime(2026, 8, 8, 0, 0))

    def test_entrees_invalides(self):
        for valeur in (None, "", "texte sans date", "32 septembre 2026"):
            self.assertIsNone(_parse_date_fr(valeur), valeur)


class TestTrouverUrlBilletterie(unittest.TestCase):
    def test_lien_direct(self):
        page = (
            '<a href="https://lepointdevente.com/billets/programmationavenir">'
            "Programmation complète</a>"
        )
        self.assertEqual(_trouver_url_billetterie(page, 5.0, None), URL_BASE)

    def test_lien_avec_parametres_nettoye(self):
        page = '<a href="https://lepointdevente.com/billets/programmationavenir?lang=fr">x</a>'
        self.assertEqual(_trouver_url_billetterie(page, 5.0, None), URL_BASE)

    def test_repli_sur_defaut(self):
        # Pas de lien ni de widget : on retombe sur l'URL par défaut.
        self.assertEqual(
            _trouver_url_billetterie("<p>rien ici</p>", 5.0, None),
            URL_BILLETTERIE_DEFAUT,
        )


class TestExtractionLepointdevente(unittest.TestCase):
    def setUp(self):
        self.evenements = _extraire_depuis_lepointdevente(FRAGMENT_LISTE, URL_BASE)

    def test_nombre_et_ordre(self):
        self.assertEqual(
            [e.titre for e in self.evenements],
            ["Juste Miben (supplémentaire)", "Les Frayeurs d'ailleurs"],
        )

    def test_champs_du_premier(self):
        ev = self.evenements[0]
        self.assertEqual(ev.date_debut, datetime(2026, 9, 30, 20, 0))
        self.assertEqual(ev.lien, "https://lepointdevente.com/billets/programmationavenir/529998")
        self.assertEqual(ev.lieu, "La Petite boite noire, Sherbrooke, QC")
        self.assertEqual(
            ev.image,
            "https://tpos.s3.amazonaws.com/events/PBN/26/09/30/001/pbn260930001-1152x648-fr.png",
        )

    def test_lien_du_second(self):
        self.assertEqual(
            self.evenements[1].lien,
            "https://lepointdevente.com/billets/programmationavenir/541978",
        )

    def test_image_absente_vaut_none(self):
        # La seconde carte n'a pas de balise <img> : image doit valoir None.
        self.assertIsNone(self.evenements[1].image)


class TestFinaliser(unittest.TestCase):
    def test_filtre_passe_deduplique_et_trie(self):
        seuil = datetime(2026, 10, 1, tzinfo=timezone.utc)
        brut = [
            Evenement("Futur B", datetime(2026, 11, 5, 20, 0), None),
            Evenement("Passé", datetime(2026, 9, 1, 20, 0), None),  # exclu (avant le seuil)
            Evenement("Futur A", datetime(2026, 10, 2, 20, 0), None),
            Evenement("Futur A", datetime(2026, 10, 2, 20, 0), None),  # doublon
            Evenement("Sans date", None, None),  # conservé
        ]
        resultat = _finaliser(brut, seuil)
        self.assertEqual(
            [e.titre for e in resultat],
            ["Futur A", "Futur B", "Sans date"],
        )


class TestFiltreJourCourant(unittest.TestCase):
    """Le seuil par défaut est minuit du jour courant, pas l'instant présent."""

    def test_evenement_plus_tot_aujourdhui_conserve(self):
        maintenant = datetime.now(timezone.utc)
        tot_aujourdhui = maintenant.replace(hour=0, minute=1, second=0, microsecond=0)
        hier = maintenant - timedelta(days=1)
        brut = [
            Evenement("Tôt aujourd'hui", tot_aujourdhui, None),
            Evenement("Hier", hier, None),
        ]
        with mock.patch.object(lpbn, "_telecharger", return_value=""), mock.patch.object(
            lpbn, "_extraire_evenements", return_value=brut
        ):
            resultat = lpbn.lister_evenements_a_venir()
        self.assertEqual([e.titre for e in resultat], ["Tôt aujourd'hui"])


class TestExports(unittest.TestCase):
    def setUp(self):
        self.evenements = [
            Evenement(
                "Juste Miben",
                datetime(2026, 9, 30, 20, 0),
                "https://tpos.s3.amazonaws.com/events/PBN/pbn260930001.png",
                "https://lepointdevente.com/billets/programmationavenir/529998",
                "La Petite boite noire, Sherbrooke, QC",
            ),
            Evenement("Sans date", None, None),
        ]

    def test_json_roundtrip(self):
        donnees = json.loads(exporter_json(self.evenements))
        self.assertEqual(len(donnees), 2)
        self.assertEqual(donnees[0]["titre"], "Juste Miben")
        self.assertEqual(donnees[0]["date_debut"], "2026-09-30T20:00:00")
        self.assertEqual(
            donnees[0]["image"], "https://tpos.s3.amazonaws.com/events/PBN/pbn260930001.png"
        )
        self.assertIsNone(donnees[1]["date_debut"])

    def test_csv_entete_et_lignes(self):
        lignes = list(csv.DictReader(io.StringIO(exporter_csv(self.evenements))))
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[0]["titre"], "Juste Miben")
        self.assertEqual(lignes[0]["lieu"], "La Petite boite noire, Sherbrooke, QC")
        self.assertEqual(
            lignes[0]["image"], "https://tpos.s3.amazonaws.com/events/PBN/pbn260930001.png"
        )


if __name__ == "__main__":
    unittest.main()
