"""Tests du modèle Evenement (représentation textuelle)."""

from __future__ import annotations

import unittest
from datetime import datetime

from culturecentro.models import Evenement


class TestStr(unittest.TestCase):
    def test_str_avec_sous_titre(self):
        ev = Evenement("Titre", datetime(2027, 1, 1, 20, 0), lien="https://x/", sous_titre="Sous")
        self.assertEqual(str(ev), "2027-01-01 20:00 — Titre — Sous (https://x/)")

    def test_str_sans_date_ni_lien(self):
        self.assertEqual(str(Evenement("Titre", None)), "date inconnue — Titre")

    def test_str_avec_date_fin(self):
        ev = Evenement("Expo", datetime(2026, 10, 15), date_fin=datetime(2027, 3, 21))
        self.assertEqual(str(ev), "2026-10-15 00:00 → 2027-03-21 — Expo")


class TestToDict(unittest.TestCase):
    def test_date_fin_serialisee(self):
        ev = Evenement("Expo", datetime(2026, 10, 15), date_fin=datetime(2027, 3, 21))
        d = ev.to_dict()
        self.assertEqual(d["date_debut"], "2026-10-15T00:00:00")
        self.assertEqual(d["date_fin"], "2027-03-21T00:00:00")

    def test_date_fin_absente_vaut_none(self):
        self.assertIsNone(Evenement("Titre", None).to_dict()["date_fin"])


if __name__ == "__main__":
    unittest.main()
