"""Tests de l'analyse des dates (ISO 8601 et français)."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from culturecentro.dates import (
    parse_date_fr,
    parse_date_iso,
    parse_heure_fr,
    plage_dates_fr,
    trouver_dates_fr,
)


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


class TestParseHeureFr(unittest.TestCase):
    def test_formes(self):
        self.assertEqual(parse_heure_fr("18h30"), (18, 30))
        self.assertEqual(parse_heure_fr("Mardi - 17h"), (17, 0))
        self.assertEqual(parse_heure_fr("19 h 00"), (19, 0))
        self.assertEqual(parse_heure_fr("20:15"), (20, 15))

    def test_annee_n_est_pas_une_heure(self):
        self.assertIsNone(parse_heure_fr("29 septembre 2026"))
        self.assertIsNone(parse_heure_fr(""))
        self.assertIsNone(parse_heure_fr(None))
        self.assertIsNone(parse_heure_fr("99h"))


class TestTrouverDatesFr(unittest.TestCase):
    def test_liste_sans_annee(self):
        texte = "Jeudis 17 septembre, 29 octobre, 26 novembre et 17 décembre - 18h30"
        self.assertEqual(
            trouver_dates_fr(texte, 2026),
            [
                datetime(2026, 9, 17),
                datetime(2026, 10, 29),
                datetime(2026, 11, 26),
                datetime(2026, 12, 17),
            ],
        )

    def test_annee_explicite_et_abreviation(self):
        self.assertEqual(trouver_dates_fr("le 1er oct. 2027 puis 3 mai"), [datetime(2027, 10, 1)])

    def test_sans_annee_ni_defaut_ignoree(self):
        self.assertEqual(trouver_dates_fr("17 septembre"), [])
        self.assertEqual(trouver_dates_fr(None), [])

    def test_mois_inconnu_ou_jour_invalide(self):
        self.assertEqual(trouver_dates_fr("31 février 2026 et 12 brumaire 2026"), [])


class TestPlageDatesFr(unittest.TestCase):
    def test_du_jour_au_jour_mois(self):
        self.assertEqual(
            plage_dates_fr("Du 7 au 17 octobre 2026"),
            (datetime(2026, 10, 7), datetime(2026, 10, 17)),
        )

    def test_deux_dates_completes(self):
        self.assertEqual(
            plage_dates_fr("Du 29 octobre 2026 au 28 mai 2027"),
            (datetime(2026, 10, 29), datetime(2027, 5, 28)),
        )
        self.assertEqual(
            plage_dates_fr("Du 02 octobre 2026 au 27 novembre 2026"),
            (datetime(2026, 10, 2), datetime(2026, 11, 27)),
        )

    def test_annee_du_debut_deduite_de_la_fin(self):
        self.assertEqual(
            plage_dates_fr("15 avril au 19 septembre 2027"),
            (datetime(2027, 4, 15), datetime(2027, 9, 19)),
        )
        # Le début tombe avant la fin dans le calendrier : année précédente.
        self.assertEqual(
            plage_dates_fr("du 15 décembre au 10 janvier 2027"),
            (datetime(2026, 12, 15), datetime(2027, 1, 10)),
        )

    def test_date_seule_avec_heure(self):
        self.assertEqual(
            plage_dates_fr("18 octobre 2026 10 h 00"), (datetime(2026, 10, 18, 10), None)
        )
        self.assertEqual(plage_dates_fr("Le 23 octobre 2026"), (datetime(2026, 10, 23), None))
        self.assertEqual(
            plage_dates_fr("Mardi 29 septembre 2026 - 17h"), (datetime(2026, 9, 29, 17), None)
        )

    def test_serie_avec_heure(self):
        self.assertEqual(
            plage_dates_fr(
                "Tous les mercredis du 9 septembre au 16 décembre - 18h30 à 20h30", 2026
            ),
            (datetime(2026, 9, 9, 18, 30), datetime(2026, 12, 16)),
        )

    def test_jusqu_en(self):
        self.assertEqual(plage_dates_fr("Jusqu’en octobre 2026"), (None, datetime(2026, 10, 31)))
        self.assertEqual(plage_dates_fr("jusqu'en février 2028"), (None, datetime(2028, 2, 29)))
        self.assertEqual(plage_dates_fr("Jusqu'au 31 mai 2027"), (None, datetime(2027, 5, 31)))

    def test_sans_annee_ni_defaut(self):
        self.assertEqual(plage_dates_fr("Du 7 au 17 octobre"), (None, None))
        self.assertEqual(plage_dates_fr("jusqu'en mai"), (None, None))

    def test_rien(self):
        self.assertEqual(plage_dates_fr("[Terminé]"), (None, None))
        self.assertEqual(plage_dates_fr(""), (None, None))
        self.assertEqual(plage_dates_fr(None), (None, None))
