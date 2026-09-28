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


if __name__ == "__main__":
    unittest.main()
