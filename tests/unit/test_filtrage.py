"""Tests de la finalisation : déduplication, filtrage et tri."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from culturecentro.filtrage import finaliser, minuit_utc
from culturecentro.models import Evenement


class TestFinaliser(unittest.TestCase):
    def test_filtre_passe_deduplique_et_trie(self):
        seuil = datetime(2026, 10, 1, tzinfo=timezone.utc)
        brut = [
            Evenement("Futur B", datetime(2026, 11, 5, 20, 0)),
            Evenement("Passé", datetime(2026, 9, 1, 20, 0)),  # exclu (avant le seuil)
            Evenement("Futur A", datetime(2026, 10, 2, 20, 0)),
            Evenement("Futur A", datetime(2026, 10, 2, 20, 0)),  # doublon
            Evenement("Sans date", None),  # conservé, trié en fin
        ]
        resultat = finaliser(brut, seuil)
        self.assertEqual([e.titre for e in resultat], ["Futur A", "Futur B", "Sans date"])

    def test_evenement_en_cours_conserve_grace_a_date_fin(self):
        seuil = datetime(2026, 10, 1, tzinfo=timezone.utc)
        brut = [
            Evenement("Expo en cours", datetime(2026, 9, 1), date_fin=datetime(2026, 12, 31)),
            Evenement("Expo terminée", datetime(2026, 8, 1), date_fin=datetime(2026, 9, 30)),
            Evenement("Passé sans fin", datetime(2026, 9, 1)),
            Evenement("Futur", datetime(2026, 11, 1)),
        ]
        resultat = finaliser(brut, seuil)
        self.assertEqual([e.titre for e in resultat], ["Expo en cours", "Futur"])

    def test_seuil_est_minuit_jour_courant(self):
        # Un événement plus tôt aujourd'hui est conservé ; hier est exclu.
        maintenant = datetime.now(timezone.utc)
        tot_aujourdhui = maintenant.replace(hour=0, minute=1, second=0, microsecond=0)
        hier = maintenant - timedelta(days=1)
        brut = [Evenement("Tôt aujourd'hui", tot_aujourdhui), Evenement("Hier", hier)]
        resultat = finaliser(brut, minuit_utc())
        self.assertEqual([e.titre for e in resultat], ["Tôt aujourd'hui"])


class TestMinuitUtc(unittest.TestCase):
    def test_minuit_utc(self):
        m = minuit_utc()
        self.assertEqual((m.hour, m.minute, m.second, m.microsecond), (0, 0, 0, 0))
        self.assertEqual(m.tzinfo, timezone.utc)


if __name__ == "__main__":
    unittest.main()
