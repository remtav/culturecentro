"""Tests de la finalisation : déduplication, filtrage et tri."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from culturecentro.filtrage import finaliser, fusionner, fusionner_doublons, minuit_utc
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
            Evenement("Jusqu'en décembre", None, date_fin=datetime(2026, 12, 31)),
            Evenement("Jusqu'en septembre", None, date_fin=datetime(2026, 9, 30)),
        ]
        resultat = finaliser(brut, seuil)
        self.assertEqual(
            [e.titre for e in resultat], ["Expo en cours", "Futur", "Jusqu'en décembre"]
        )

    def test_seuil_est_minuit_jour_courant(self):
        # Un événement plus tôt aujourd'hui est conservé ; hier est exclu.
        maintenant = datetime.now(timezone.utc)
        tot_aujourdhui = maintenant.replace(hour=0, minute=1, second=0, microsecond=0)
        hier = maintenant - timedelta(days=1)
        brut = [Evenement("Tôt aujourd'hui", tot_aujourdhui), Evenement("Hier", hier)]
        resultat = finaliser(brut, minuit_utc())
        self.assertEqual([e.titre for e in resultat], ["Tôt aujourd'hui"])


GRANADA, PBN = "Théâtre Granada", "La Petite Boîte Noire"
MAP, GE = "Maison des arts de la parole", "Le Grand-Espace"
SOIR = datetime(2026, 10, 13, 20, 0)


class TestFusionnerDoublons(unittest.TestCase):
    def test_presente_par_un_partenaire_chez_un_autre(self):
        # Le Granada annonce un spectacle qu'il présente à La Petite Boîte Noire.
        granada = Evenement(
            "Maxime Gervais",
            SOIR,
            lien="https://granada/maxime-gervais/",
            sous_titre="Les découvertes de La Petite Boite Noire",
            image="https://granada/mg.jpg",
            lieu=PBN,
            partenaire=GRANADA,
        )
        pbn = Evenement(
            "Maxime Gervais : C’était Magnifique",
            SOIR,
            lien="https://lepointdevente/pbn",
            image="https://lepointdevente/mg.png",
            lieu=PBN,
            partenaire=PBN,
        )
        for ordre in ([granada, pbn], [pbn, granada]):
            with self.assertLogs("culturecentro.filtrage", level="INFO"):
                (ev,) = fusionner_doublons(ordre)
            # L'annonce du Granada est la plus complète (sous-titre) : elle fait foi...
            self.assertEqual(ev.partenaire, GRANADA)
            self.assertEqual(ev.lien, "https://granada/maxime-gervais/")
            self.assertEqual(ev.image, "https://granada/mg.jpg")
            self.assertEqual(ev.sous_titre, "Les découvertes de La Petite Boite Noire")
            self.assertEqual(ev.lieu, PBN)
            # ... avec le titre le plus complet, celui de la billetterie.
            self.assertEqual(ev.titre, "Maxime Gervais : C’était Magnifique")

    def test_festival_accueilli_complete_par_l_autre_annonce(self):
        cloture = datetime(2026, 10, 25, 20, 0)
        map_ = Evenement(
            "Spectacle de clôture",
            cloture,
            lien="https://map/cloture/",
            sous_titre="avec Najoua Darwiche, Marien Guillé",
            image="https://map/cloture.png",
            date_fin=datetime(2026, 10, 25, 22, 30),
            lieu=GE,
            partenaire=MAP,
        )
        ge = Evenement(
            "Spectacle de clôture du festival Les jours sont contés",
            cloture,
            lien="https://ge/cloture/",
            sous_titre="Spectacle de conte",
            image="https://ge/tortue.png",
            lieu=GE,
            partenaire=GE,
        )
        with self.assertLogs("culturecentro.filtrage", level="INFO"):
            (ev,) = fusionner_doublons([map_, ge])
        self.assertEqual(ev.partenaire, MAP)  # fin connue : annonce la plus complète
        self.assertEqual(ev.titre, "Spectacle de clôture du festival Les jours sont contés")
        self.assertEqual(ev.sous_titre, "avec Najoua Darwiche, Marien Guillé")
        self.assertEqual(ev.date_fin, datetime(2026, 10, 25, 22, 30))
        self.assertEqual(ev.lien, "https://map/cloture/")

    def test_champs_manquants_completes_et_heure_inconnue(self):
        date_seule = Evenement(
            "Ismène", datetime(2026, 10, 7), sous_titre="Théâtre", lien="https://ge/", partenaire=GE
        )
        a_l_heure = Evenement(
            "Ismène", datetime(2026, 10, 7, 19, 30), image="https://img", partenaire=MAP
        )
        ev = fusionner(date_seule, a_l_heure)
        self.assertEqual(ev.partenaire, GE)  # deux champs + texte plus long
        self.assertEqual(ev.date_debut, datetime(2026, 10, 7, 19, 30))  # heure reprise
        self.assertEqual(ev.image, "https://img")  # affiche manquante reprise
        self.assertEqual(ev.sous_titre, "Théâtre")

    def test_egalite_premiere_annonce_conservee(self):
        a = Evenement("Concert", SOIR, lien="https://a", partenaire="A")
        b = Evenement("Concert", SOIR, lien="https://b", partenaire="B")
        self.assertEqual(fusionner(a, b).partenaire, "A")
        self.assertEqual(fusionner(b, a).partenaire, "B")

    def test_evenements_distincts_conserves(self):
        cas = {
            "même soir, autres spectacles": [
                Evenement("Fallait être là", SOIR, partenaire=GRANADA),
                Evenement("Bonne nuit, chérie", SOIR, partenaire=PBN),
            ],
            "même partenaire : deux représentations": [
                Evenement("P'tit Belliveau", SOIR, partenaire=PBN),
                Evenement("P'tit Belliveau - Supplémentaire", SOIR, partenaire=PBN),
            ],
            "autre heure": [
                Evenement("Contes", datetime(2026, 10, 13, 14, 0), partenaire=MAP),
                Evenement("Contes", SOIR, partenaire=GE),
            ],
            "autre jour": [
                Evenement("Kaïn", SOIR, partenaire=GRANADA),
                Evenement("Kaïn", SOIR + timedelta(days=1), partenaire=PBN),
            ],
            "soirée et série du même nom": [
                Evenement("Ismène", datetime(2026, 10, 7, 20, 0), partenaire=MAP),
                Evenement(
                    "Ismène", datetime(2026, 10, 7), date_fin=datetime(2026, 10, 17), partenaire=GE
                ),
            ],
            "titres sans mot significatif": [
                Evenement("A + B", SOIR, partenaire=MAP),
                Evenement("C et D", SOIR, partenaire=GE),
            ],
            "sans date": [
                Evenement("Exposition", None, partenaire="A"),
                Evenement("Exposition", None, partenaire="B"),
            ],
        }
        for nom, evenements in cas.items():
            with self.subTest(nom):
                self.assertEqual(fusionner_doublons(evenements), evenements)

    def test_finaliser_fusionne_les_annonces_de_deux_partenaires(self):
        seuil = datetime(2026, 10, 1, tzinfo=timezone.utc)
        brut = [
            Evenement("Kaïn", SOIR, partenaire=GRANADA),
            Evenement("Autre", SOIR + timedelta(days=1), partenaire=PBN),
            Evenement("Kaïn : 25 ans", SOIR, partenaire=PBN),
        ]
        with self.assertLogs("culturecentro.filtrage", level="INFO"):
            resultat = finaliser(brut, seuil)
        self.assertEqual([e.titre for e in resultat], ["Kaïn : 25 ans", "Autre"])


class TestMinuitUtc(unittest.TestCase):
    def test_minuit_utc(self):
        m = minuit_utc()
        self.assertEqual((m.hour, m.minute, m.second, m.microsecond), (0, 0, 0, 0))
        self.assertEqual(m.tzinfo, timezone.utc)


if __name__ == "__main__":
    unittest.main()
