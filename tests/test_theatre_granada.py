"""Tests unitaires pour theatre_granada (sans accès réseau).

Les tests couvrent l'analyse des dates françaises, l'extraction de la grille
WPBakery à partir d'un fragment HTML figé, la finalisation (déduplication,
filtrage des événements à venir, tri) et les exports CSV/JSON.

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
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from theatre_granada import (  # noqa: E402
    Evenement,
    _extraire_depuis_wpbakery,
    _finaliser,
    _parse_date_fr,
    exporter_csv,
    exporter_json,
)

# Fragment reproduisant la structure réelle de deux items de la grille.
FRAGMENT_GRILLE = """
<div class="vc_grid-item-mini vc_clearfix">
  <img alt="Jesse Cook" class="vc_gitem-zone-img" src="https://theatregranada.com/img/jesse-cook.jpg"/>
  <div class="vc_gitem-zone-c">
    <div class="vc_gitem-acf home-artist">dimanche 27 septembre 2026 à 20:00</div>
    <div class="vc_gitem-acf home-soustitre"></div>
    <div class="vc_custom_heading home-date vc_gitem-post-data-source-post_title">
      <h4>Jesse Cook</h4>
    </div>
    <a class="vc_gitem-link vc_general vc_btn3" href="https://theatregranada.com/jesse-cook/">En savoir plus</a>
  </div>
</div>
<div class="vc_grid-item-mini vc_clearfix">
  <img alt="Alain-François" class="vc_gitem-zone-img" src="https://theatregranada.com/img/alain-francois.jpg"/>
  <div class="vc_gitem-zone-c">
    <div class="vc_gitem-acf home-artist">jeudi 10 décembre 2026 à 20:30</div>
    <div class="vc_gitem-acf home-soustitre">Souper-spectacle des Fêtes</div>
    <div class="vc_custom_heading home-date vc_gitem-post-data-source-post_title">
      <h4>Alain-François | Souper-spectacle</h4>
    </div>
    <a class="vc_gitem-link vc_general vc_btn3" href="https://theatregranada.com/alain-francois/">En savoir plus</a>
  </div>
</div>
"""


class TestParseDateFr(unittest.TestCase):
    def test_date_complete(self):
        self.assertEqual(
            _parse_date_fr("dimanche 27 septembre 2026 à 20:00"),
            datetime(2026, 9, 27, 20, 0),
        )

    def test_premier_du_mois_et_heure_h(self):
        self.assertEqual(_parse_date_fr("1er octobre 2026 à 20h30"), datetime(2026, 10, 1, 20, 30))

    def test_sans_heure(self):
        self.assertEqual(_parse_date_fr("8 août 2026"), datetime(2026, 8, 8, 0, 0))

    def test_accents_et_minuscules(self):
        self.assertEqual(_parse_date_fr("jeudi 4 février 2027 à 9:05"), datetime(2027, 2, 4, 9, 5))

    def test_entrees_invalides(self):
        for valeur in (None, "", "texte sans date", "32 septembre 2026"):
            self.assertIsNone(_parse_date_fr(valeur), valeur)


class TestExtractionWPBakery(unittest.TestCase):
    def setUp(self):
        self.evenements = _extraire_depuis_wpbakery(FRAGMENT_GRILLE)

    def test_nombre_et_ordre(self):
        self.assertEqual([e.titre for e in self.evenements], ["Jesse Cook", "Alain-François | Souper-spectacle"])

    def test_champs_du_premier(self):
        ev = self.evenements[0]
        self.assertEqual(ev.date_debut, datetime(2026, 9, 27, 20, 0))
        self.assertEqual(ev.lien, "https://theatregranada.com/jesse-cook/")
        self.assertEqual(ev.image, "https://theatregranada.com/img/jesse-cook.jpg")
        self.assertIsNone(ev.sous_titre)  # champ home-soustitre vide

    def test_heure_avec_minutes(self):
        self.assertEqual(self.evenements[1].date_debut, datetime(2026, 12, 10, 20, 30))

    def test_sous_titre(self):
        self.assertEqual(self.evenements[1].sous_titre, "Souper-spectacle des Fêtes")


class TestFinaliser(unittest.TestCase):
    def test_filtre_passe_deduplique_et_trie(self):
        seuil = datetime(2026, 10, 1, tzinfo=timezone.utc)
        brut = [
            Evenement("Futur B", datetime(2026, 11, 5, 20, 0)),
            Evenement("Passé", datetime(2026, 9, 1, 20, 0)),  # exclu (avant le seuil)
            Evenement("Futur A", datetime(2026, 10, 2, 20, 0)),
            Evenement("Futur A", datetime(2026, 10, 2, 20, 0)),  # doublon
            Evenement("Sans date", None),  # conservé
        ]
        resultat = _finaliser(brut, seuil)
        self.assertEqual(
            [e.titre for e in resultat],
            ["Futur A", "Futur B", "Sans date"],
        )


class TestExports(unittest.TestCase):
    def setUp(self):
        self.evenements = [
            Evenement(
                "Jesse Cook",
                datetime(2026, 9, 27, 20, 0),
                "https://x/jesse-cook/",
                sous_titre="Live in Concert",
                image="https://x/jesse.jpg",
            ),
            Evenement("Sans date", None, None),
        ]

    def test_json_roundtrip(self):
        donnees = json.loads(exporter_json(self.evenements))
        self.assertEqual(len(donnees), 2)
        self.assertEqual(donnees[0]["titre"], "Jesse Cook")
        self.assertEqual(donnees[0]["date_debut"], "2026-09-27T20:00:00")
        self.assertEqual(donnees[0]["sous_titre"], "Live in Concert")
        self.assertEqual(donnees[0]["image"], "https://x/jesse.jpg")
        self.assertIsNone(donnees[1]["date_debut"])

    def test_csv_entete_et_lignes(self):
        flux = io.StringIO(exporter_csv(self.evenements))
        lecteur = csv.DictReader(flux)
        self.assertIn("sous_titre", lecteur.fieldnames)
        self.assertIn("image", lecteur.fieldnames)
        lignes = list(lecteur)
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[0]["titre"], "Jesse Cook")
        self.assertEqual(lignes[0]["date_debut"], "2026-09-27T20:00:00")
        self.assertEqual(lignes[0]["lien"], "https://x/jesse-cook/")
        self.assertEqual(lignes[0]["image"], "https://x/jesse.jpg")

    def test_json_ecrit_fichier(self):
        import tempfile

        with tempfile.TemporaryDirectory() as rep:
            chemin = os.path.join(rep, "ev.json")
            exporter_json(self.evenements, chemin)
            with open(chemin, encoding="utf-8") as flux:
                self.assertEqual(len(json.load(flux)), 2)


if __name__ == "__main__":
    unittest.main()
