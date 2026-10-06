"""Tests des lieux : noms canoniques et périmètre du centre-ville."""

from __future__ import annotations

import unittest

from culturecentro.lieux import cle, est_centre_ville, lieu_connu, normaliser_lieu


class TestCle(unittest.TestCase):
    def test_accents_casse_tirets(self):
        self.assertEqual(cle("Le Grand - Espace"), "le grand-espace")
        self.assertEqual(cle("Théâtre  Granada"), "theatre granada")


class TestNormaliserLieu(unittest.TestCase):
    def test_alias_et_variantes(self):
        self.assertEqual(normaliser_lieu("Le Grand Espace"), "Le Grand-Espace")
        self.assertEqual(normaliser_lieu("le grand-espace"), "Le Grand-Espace")
        self.assertEqual(
            normaliser_lieu("Salle multifonctionnelle du Tremplin"), "Le Tremplin 16-30"
        )
        self.assertEqual(
            normaliser_lieu("La Petite boite noire, Sherbrooke, QC"), "La Petite Boîte Noire"
        )
        self.assertEqual(normaliser_lieu("THÉÂTRE GRANADA"), "Théâtre Granada")

    def test_inconnu_conserve_sans_ville(self):
        self.assertEqual(normaliser_lieu("Centre d'art de Richmond"), "Centre d'art de Richmond")
        self.assertEqual(normaliser_lieu("Lieu à confirmer, Sherbrooke, QC"), "Lieu à confirmer")

    def test_vide(self):
        self.assertIsNone(normaliser_lieu(None))
        self.assertIsNone(normaliser_lieu("  "))


class TestLieuConnu(unittest.TestCase):
    def test_lieu_connu_ou_none(self):
        self.assertEqual(lieu_connu("Le Grand-Espace - CAJB"), "Le Grand-Espace")
        self.assertEqual(lieu_connu("la petite boite noire"), "La Petite Boîte Noire")
        self.assertIsNone(lieu_connu("Humour"))
        self.assertIsNone(lieu_connu(None))


class TestEstCentreVille(unittest.TestCase):
    def test_lieu_connu(self):
        self.assertTrue(est_centre_ville("Théâtre Granada"))
        self.assertTrue(est_centre_ville("Le Grand Espace", "250 rue du Dépôt"))
        self.assertTrue(est_centre_ville("Café 440"))

    def test_adresse_au_centre_ville(self):
        self.assertTrue(est_centre_ville("Un nouveau café", "61 rue Wellington Nord"))
        self.assertTrue(est_centre_ville("Kaapeh", "234 rue Dufferin, local 104, Sherbrooke"))

    def test_autre_municipalite_ou_campus(self):
        self.assertFalse(
            est_centre_ville("Centre d'art de Richmond", "1010 rue Principale Nord, Richmond")
        )
        self.assertFalse(
            est_centre_ville("Pavillon des arts de Coaticook", "116 Wellington, Coaticook")
        )
        self.assertFalse(est_centre_ville("La Meunerie de Saint-Adrien"))
        self.assertFalse(est_centre_ville("Centre culturel de l'Université de Sherbrooke"))

    def test_adresse_sherbrooke_hors_centre(self):
        self.assertFalse(
            est_centre_ville(
                "Centre culturel Pierre-Gobeil", "970 Rue du Haut-Bois Sud, Sherbrooke"
            )
        )
        self.assertFalse(est_centre_ville("Base de plein air André-Nadeau", "5302 Ch. Blanchette"))

    def test_inconnu_sans_adresse_benefice_du_doute(self):
        self.assertTrue(est_centre_ville("Lieu à confirmer"))
        self.assertTrue(est_centre_ville(None))


if __name__ == "__main__":
    unittest.main()
