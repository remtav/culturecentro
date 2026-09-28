"""Tests de la source Théâtre Granada (extraction WPBakery + replis, CLI).

Hors-ligne : le réseau est simulé.
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

import requests

from culturecentro.sources import theatre_granada as tg
from culturecentro.sources.theatre_granada import (
    Evenement,
    TheatreGranada,
    _charger_grille_complete,
    _extraire_depuis_html,
    _extraire_depuis_wpbakery,
    _extraire_evenements,
    main,
)

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

JSONLD = """
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
  {"@type":"Event","name":"Concert JSON-LD","startDate":"2027-03-01T20:00:00",
   "url":"https://x/concert/","location":{"@type":"Place","name":"Salle X"}}
]}
</script>
"""

TRIBE = """
<div class="tribe-events-calendar-list__event">
  <a class="tribe-events-calendar-list__event-title-link" href="https://x/e/">Événement Tribe</a>
  <time datetime="2027-04-02T19:00:00">2 avril</time>
</div>
"""

PAGE_AVEC_GRILLE = (
    '<div data-vc-request="https://x/ajax" '
    'data-vc-grid-settings=\'{"tag":"vc_basic_grid","page_id":1}\' '
    'data-vc-public-nonce="abc" data-vc-post-id="1"></div>'
)


def _reponse_factice(texte, statut=200):
    rep = mock.Mock()
    rep.status_code = statut
    rep.text = texte
    return rep


class TestExtractionWPBakery(unittest.TestCase):
    def setUp(self):
        self.evenements = _extraire_depuis_wpbakery(FRAGMENT_GRILLE)

    def test_nombre_et_ordre(self):
        self.assertEqual(
            [e.titre for e in self.evenements],
            ["Jesse Cook", "Alain-François | Souper-spectacle"],
        )

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


class TestReplis(unittest.TestCase):
    def test_html_tribe(self):
        evs = _extraire_depuis_html(TRIBE)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0].titre, "Événement Tribe")
        self.assertEqual(evs[0].lien, "https://x/e/")

    def test_selection_repli_inline_quand_ajax_indisponible(self):
        with mock.patch.object(tg, "_charger_grille_complete", return_value=None):
            with self.assertLogs(tg._LOG.name, level="WARNING"):
                evs = _extraire_evenements(FRAGMENT_GRILLE, timeout=5, session=mock.Mock())
        self.assertEqual(
            [e.titre for e in evs], ["Jesse Cook", "Alain-François | Souper-spectacle"]
        )

    def test_selection_repli_jsonld(self):
        with mock.patch.object(tg, "_charger_grille_complete", return_value=None):
            with self.assertLogs(tg._LOG.name, level="WARNING"):
                evs = _extraire_evenements(JSONLD, timeout=5, session=mock.Mock())
        self.assertEqual([e.titre for e in evs], ["Concert JSON-LD"])

    def test_selection_repli_html(self):
        with mock.patch.object(tg, "_charger_grille_complete", return_value=None):
            with self.assertLogs(tg._LOG.name, level="WARNING"):
                evs = _extraire_evenements(TRIBE, timeout=5, session=mock.Mock())
        self.assertEqual([e.titre for e in evs], ["Événement Tribe"])

    def test_aucun_evenement(self):
        with mock.patch.object(tg, "_charger_grille_complete", return_value=None):
            with self.assertLogs(tg._LOG.name, level="WARNING"):
                evs = _extraire_evenements("<html></html>", timeout=5, session=mock.Mock())
        self.assertEqual(evs, [])

    def test_selection_ajax_prioritaire(self):
        with mock.patch.object(tg, "_charger_grille_complete", return_value=FRAGMENT_GRILLE):
            evs = _extraire_evenements("<html></html>", timeout=5, session=mock.Mock())
        self.assertEqual(len(evs), 2)


class TestChargerGrille(unittest.TestCase):
    def test_succes(self):
        session = mock.Mock()
        session.post.return_value = _reponse_factice(FRAGMENT_GRILLE)
        fragment = _charger_grille_complete(PAGE_AVEC_GRILLE, 5, session)
        self.assertIn("vc_grid-item-mini", fragment)
        donnees = session.post.call_args.kwargs["data"]
        self.assertEqual(donnees["action"], "vc_get_vc_grid_data")
        self.assertIn("data[page_id]", donnees)

    def test_reponse_zero(self):
        session = mock.Mock()
        session.post.return_value = _reponse_factice("0")
        self.assertIsNone(_charger_grille_complete(PAGE_AVEC_GRILLE, 5, session))

    def test_sans_conteneur(self):
        self.assertIsNone(_charger_grille_complete("<html></html>", 5, mock.Mock()))

    def test_exception_reseau(self):
        session = mock.Mock()
        session.post.side_effect = requests.RequestException("boom")
        self.assertIsNone(_charger_grille_complete(PAGE_AVEC_GRILLE, 5, session))


class TestListerEvenements(unittest.TestCase):
    def test_bout_en_bout_hors_ligne(self):
        seuil = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with (
            mock.patch("culturecentro.sources.base.telecharger", return_value=FRAGMENT_GRILLE),
            mock.patch.object(tg, "_charger_grille_complete", return_value=None),
        ):
            evs = tg.lister_evenements_a_venir(a_partir_de=seuil)
        self.assertEqual(
            [e.titre for e in evs], ["Jesse Cook", "Alain-François | Souper-spectacle"]
        )


class TestCli(unittest.TestCase):
    EVENEMENTS = [Evenement("Jesse Cook", datetime(2026, 9, 27, 20, 0), lien="https://x/jc/")]

    def _lancer(self, args):
        sortie = io.StringIO()
        with mock.patch.object(
            TheatreGranada, "lister_evenements_a_venir", return_value=self.EVENEMENTS
        ):
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
        with mock.patch.object(
            TheatreGranada,
            "lister_evenements_a_venir",
            side_effect=requests.RequestException("boom"),
        ):
            code = main(["--format", "texte"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
