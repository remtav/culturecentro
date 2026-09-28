"""Tests de l'analyse des dates (ISO 8601 et français)."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from culturecentro.dates import parse_date_fr, parse_date_iso


class TestParseDateFr(unittest.TestCase):
    def test_date_complete_avec_a(self):
        self.assertEqual(
            parse_date_fr("dimanche 27 septembre 2026 à 20:00"),
            datetime(2026, 9, 27, 20, 0),
        )

    def test_date_avec_virgule(self):
        self.assertEqual(parse_date_fr("30 septembre 2026, 20h00"), datetime(2026, 9, 30, 20, 0))

    def test_premier_du_mois_et_heure_h(self):
        self.assertEqual(parse_date_fr("1er octobre 2026 à 20h30"), datetime(2026, 10, 1, 20, 30))

    def test_sans_heure(self):
        self.assertEqual(parse_date_fr("8 août 2026"), datetime(2026, 8, 8, 0, 0))

    def test_accents_et_minuscules(self):
        self.assertEqual(parse_date_fr("jeudi 4 février 2027 à 9:05"), datetime(2027, 2, 4, 9, 5))

    def test_entrees_invalides(self):
        for valeur in (None, "", "texte sans date", "32 septembre 2026"):
            self.assertIsNone(parse_date_fr(valeur), valeur)


class TestParseDateIso(unittest.TestCase):
    def test_iso_avec_z(self):
        self.assertEqual(
            parse_date_iso("2027-01-01T20:00:00Z"),
            datetime(2027, 1, 1, 20, 0, tzinfo=timezone.utc),
        )

    def test_iso_simple(self):
        self.assertEqual(parse_date_iso("2027-01-01T20:00:00"), datetime(2027, 1, 1, 20, 0))

    def test_invalide(self):
        for valeur in (None, "", "pas une date"):
            self.assertIsNone(parse_date_iso(valeur))


if __name__ == "__main__":
    unittest.main()
