"""Tests unitaires pour theatre_granada (sans accès réseau).

Les tests couvrent l'analyse des dates françaises, l'extraction de la grille
WPBakery à partir d'un fragment HTML figé, la finalisation (déduplication,
filtrage des événements à venir, tri) et les exports CSV/JSON.

Exécution ::

    python -m unittest discover -s tests
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import theatre_granada as tg  # noqa: E402
from theatre_granada import (  # noqa: E402
    Evenement,
    _extraire_depuis_html,
    _extraire_depuis_jsonld,
    _extraire_depuis_wpbakery,
    _extraire_evenements,
    _finaliser,
    _parse_date,
    _parse_date_fr,
    exporter_csv,
    exporter_json,
    main,
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
            self.assertEqual(len(lignes), 2)
            self.assertEqual(lignes[0]["titre"], "Jesse Cook")


class TestParseDateIso(unittest.TestCase):
    def test_iso_avec_z(self):
        self.assertEqual(
            _parse_date("2027-01-01T20:00:00Z"),
            datetime(2027, 1, 1, 20, 0, tzinfo=timezone.utc),
        )

    def test_iso_simple(self):
        self.assertEqual(_parse_date("2027-01-01T20:00:00"), datetime(2027, 1, 1, 20, 0))

    def test_invalide(self):
        for valeur in (None, "", "pas une date"):
            self.assertIsNone(_parse_date(valeur))


JSONLD = """
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
  {"@type":"Event","name":"Concert JSON-LD","startDate":"2027-03-01T20:00:00",
   "url":"https://x/concert/","location":{"@type":"Place","name":"Salle X"},
   "image":["https://x/affiche.jpg"]},
  {"@type":"WebPage","name":"pas un événement"}
]}
</script>
"""

TRIBE = """
<div class="tribe-events-calendar-list__event">
  <a class="tribe-events-calendar-list__event-title-link" href="https://x/e/">Événement Tribe</a>
  <time datetime="2027-04-02T19:00:00">2 avril</time>
</div>
"""


class TestReplis(unittest.TestCase):
    def test_jsonld(self):
        evs = _extraire_depuis_jsonld(JSONLD)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0].titre, "Concert JSON-LD")
        self.assertEqual(evs[0].lieu, "Salle X")
        self.assertEqual(evs[0].image, "https://x/affiche.jpg")

    def test_html_tribe(self):
        evs = _extraire_depuis_html(TRIBE)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0].titre, "Événement Tribe")
        self.assertEqual(evs[0].lien, "https://x/e/")

    def test_selection_repli_inline_quand_ajax_indisponible(self):
        # AJAX indisponible -> repli sur la grille inline présente dans le HTML.
        with mock.patch.object(tg, "_charger_grille_complete", return_value=None):
            with self.assertLogs("theatre_granada", level="WARNING"):
                evs = _extraire_evenements(FRAGMENT_GRILLE, timeout=5, session=mock.Mock())
        self.assertEqual([e.titre for e in evs], ["Jesse Cook", "Alain-François | Souper-spectacle"])

    def test_selection_repli_jsonld(self):
        with mock.patch.object(tg, "_charger_grille_complete", return_value=None):
            with self.assertLogs("theatre_granada", level="WARNING"):
                evs = _extraire_evenements(JSONLD, timeout=5, session=mock.Mock())
        self.assertEqual([e.titre for e in evs], ["Concert JSON-LD"])

    def test_selection_ajax_prioritaire(self):
        with mock.patch.object(tg, "_charger_grille_complete", return_value=FRAGMENT_GRILLE):
            evs = _extraire_evenements("<html></html>", timeout=5, session=mock.Mock())
        self.assertEqual(len(evs), 2)


PAGE_AVEC_GRILLE = (
    '<div data-vc-request="https://x/ajax" '
    "data-vc-grid-settings='{\"tag\":\"vc_basic_grid\",\"page_id\":1}' "
    'data-vc-public-nonce="abc" data-vc-post-id="1"></div>'
)


def _reponse_factice(texte, statut=200):
    rep = mock.Mock()
    rep.status_code = statut
    rep.text = texte
    return rep


class TestChargerGrille(unittest.TestCase):
    def test_succes(self):
        session = mock.Mock()
        session.post.return_value = _reponse_factice(FRAGMENT_GRILLE)
        fragment = tg._charger_grille_complete(PAGE_AVEC_GRILLE, 5, session)
        self.assertIn("vc_grid-item-mini", fragment)
        # Le format attendu par WPBakery : réglages sous la clé data[...].
        donnees = session.post.call_args.kwargs["data"]
        self.assertEqual(donnees["action"], "vc_get_vc_grid_data")
        self.assertIn("data[page_id]", donnees)

    def test_reponse_zero(self):
        session = mock.Mock()
        session.post.return_value = _reponse_factice("0")
        self.assertIsNone(tg._charger_grille_complete(PAGE_AVEC_GRILLE, 5, session))

    def test_sans_conteneur(self):
        self.assertIsNone(tg._charger_grille_complete("<html></html>", 5, mock.Mock()))

    def test_exception_reseau(self):
        import requests

        session = mock.Mock()
        session.post.side_effect = requests.RequestException("boom")
        self.assertIsNone(tg._charger_grille_complete(PAGE_AVEC_GRILLE, 5, session))


class TestListerEvenements(unittest.TestCase):
    def test_bout_en_bout_hors_ligne(self):
        seuil = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with mock.patch.object(tg, "_telecharger", return_value=FRAGMENT_GRILLE), mock.patch.object(
            tg, "_charger_grille_complete", return_value=None
        ):
            evs = tg.lister_evenements_a_venir(a_partir_de=seuil)
        self.assertEqual([e.titre for e in evs], ["Jesse Cook", "Alain-François | Souper-spectacle"])

    def test_creer_session(self):
        import requests

        session = tg._creer_session()
        self.assertIsInstance(session, requests.Session)
        session.close()


class TestStr(unittest.TestCase):
    def test_str_avec_sous_titre(self):
        ev = Evenement("Titre", datetime(2027, 1, 1, 20, 0), "https://x/", sous_titre="Sous")
        self.assertEqual(str(ev), "2027-01-01 20:00 — Titre — Sous (https://x/)")

    def test_str_sans_date(self):
        self.assertEqual(str(Evenement("Titre", None)), "date inconnue — Titre")


class TestCli(unittest.TestCase):
    EVENEMENTS = [Evenement("Jesse Cook", datetime(2026, 9, 27, 20, 0), "https://x/jc/")]

    def _lancer(self, args):
        sortie = io.StringIO()
        with mock.patch.object(tg, "lister_evenements_a_venir", return_value=self.EVENEMENTS):
            with contextlib.redirect_stdout(sortie):
                code = main(args)
        return code, sortie.getvalue()

    def test_texte_stdout(self):
        code, sortie = self._lancer(["--format", "texte"])
        self.assertEqual(code, 0)
        self.assertIn("Jesse Cook", sortie)

    def test_json_stdout(self):
        code, sortie = self._lancer(["--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(sortie)[0]["titre"], "Jesse Cook")

    def test_csv_fichier(self):
        with tempfile.TemporaryDirectory() as rep:
            chemin = os.path.join(rep, "out.csv")
            code, _ = self._lancer(["--format", "csv", "-o", chemin])
            self.assertEqual(code, 0)
            with open(chemin, encoding="utf-8", newline="") as flux:
                self.assertEqual(list(csv.DictReader(flux))[0]["titre"], "Jesse Cook")

    def test_erreur_reseau_retourne_1(self):
        import requests

        with mock.patch.object(
            tg, "lister_evenements_a_venir", side_effect=requests.RequestException("boom")
        ):
            code = main(["--format", "texte"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
