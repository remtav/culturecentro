"""Tests des exports texte / CSV / JSON (schéma unifié)."""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import unittest
from datetime import datetime

from culturecentro.exporters import exporter_csv, exporter_json, exporter_texte
from culturecentro.models import Evenement


class TestExports(unittest.TestCase):
    def setUp(self):
        self.evenements = [
            Evenement(
                "Jesse Cook",
                datetime(2026, 9, 27, 20, 0),
                lien="https://x/jesse-cook/",
                sous_titre="Live in Concert",
                image="https://x/jesse.jpg",
                lieu="Théâtre Granada",
            ),
            Evenement("Sans date", None),
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
        lecteur = csv.DictReader(io.StringIO(exporter_csv(self.evenements)))
        self.assertEqual(
            lecteur.fieldnames,
            ["titre", "sous_titre", "date_debut", "lien", "image", "lieu"],
        )
        lignes = list(lecteur)
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[0]["titre"], "Jesse Cook")
        self.assertEqual(lignes[0]["lien"], "https://x/jesse-cook/")
        self.assertEqual(lignes[0]["image"], "https://x/jesse.jpg")

    def test_texte(self):
        texte = exporter_texte(self.evenements)
        lignes = texte.splitlines()
        self.assertIn("Jesse Cook", lignes[0])
        self.assertIn("Live in Concert", lignes[0])
        self.assertTrue(lignes[1].startswith("date inconnue"))

    def test_json_ecrit_fichier(self):
        with tempfile.TemporaryDirectory() as rep:
            chemin = os.path.join(rep, "ev.json")
            exporter_json(self.evenements, chemin)
            with open(chemin, encoding="utf-8") as flux:
                self.assertEqual(len(json.load(flux)), 2)

    def test_csv_ecrit_fichier(self):
        with tempfile.TemporaryDirectory() as rep:
            chemin = os.path.join(rep, "ev.csv")
            exporter_csv(self.evenements, chemin)
            with open(chemin, encoding="utf-8", newline="") as flux:
                lignes = list(csv.DictReader(flux))
            self.assertEqual(lignes[0]["titre"], "Jesse Cook")

    def test_texte_ecrit_fichier(self):
        with tempfile.TemporaryDirectory() as rep:
            chemin = os.path.join(rep, "ev.txt")
            exporter_texte(self.evenements, chemin)
            with open(chemin, encoding="utf-8") as flux:
                self.assertIn("Jesse Cook", flux.read())


if __name__ == "__main__":
    unittest.main()
