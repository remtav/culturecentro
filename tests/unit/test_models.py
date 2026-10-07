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

    def test_str_fin_le_meme_jour_sans_fleche(self):
        ev = Evenement("Soir", datetime(2026, 10, 15, 20), date_fin=datetime(2026, 10, 15, 22))
        self.assertEqual(str(ev), "2026-10-15 20:00 — Soir")


class TestToDict(unittest.TestCase):
    def test_date_fin_serialisee(self):
        ev = Evenement("Expo", datetime(2026, 10, 15), date_fin=datetime(2027, 3, 21))
        d = ev.to_dict()
        self.assertEqual(d["date_debut"], "2026-10-15T00:00:00")
        self.assertEqual(d["date_fin"], "2027-03-21T00:00:00")

    def test_date_fin_absente_vaut_none(self):
        self.assertIsNone(Evenement("Titre", None).to_dict()["date_fin"])

    def test_partenaire_serialise(self):
        d = Evenement("Titre", None, lieu="Café 440", partenaire="Maison des arts").to_dict()
        self.assertEqual((d["lieu"], d["partenaire"]), ("Café 440", "Maison des arts"))
        self.assertIsNone(Evenement("Titre", None).to_dict()["partenaire"])


if __name__ == "__main__":
    unittest.main()


class TestFromDict(unittest.TestCase):
    def test_aller_retour(self):
        ev = Evenement(
            "Expo",
            datetime(2026, 10, 15, 19, 30),
            lien="https://x/",
            lieu="Sporobole",
            sous_titre="Vernissage",
            image="https://x/a.jpg",
            date_fin=datetime(2027, 3, 21),
            partenaire="Sporobole",
            categorie="arts",
        )
        self.assertEqual(Evenement.from_dict(ev.to_dict()), ev)

    def test_cles_inconnues_ignorees_et_champs_absents(self):
        ev = Evenement.from_dict({"titre": "Concert", "id": "concert-2026-10-01"})
        self.assertEqual(ev, Evenement("Concert", None))

    def test_titre_absent_ou_date_invalide(self):
        with self.assertRaises(KeyError):
            Evenement.from_dict({"date_debut": "2026-10-01T20:00:00"})
        with self.assertRaises(ValueError):
            Evenement.from_dict({"titre": "Concert", "date_debut": "1er octobre"})
