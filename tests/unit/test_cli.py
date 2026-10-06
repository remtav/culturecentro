"""Tests de la CLI unifiée (``culturecentro``)."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime
from unittest import mock

import requests

from culturecentro.cli import principal
from culturecentro.models import Evenement

EVENEMENTS = [Evenement("Concert", datetime(2026, 10, 1, 20, 0), lieu="Salle X")]


def _lancer(argv):
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = principal(argv)
    return code, sortie.getvalue()


class TestCommandeSources(unittest.TestCase):
    def test_liste_les_salles(self):
        code, sortie = _lancer(["sources"])
        self.assertEqual(code, 0)
        self.assertIn("theatre-granada", sortie)
        self.assertIn("la-petite-boite-noire", sortie)


class TestCommandeLister(unittest.TestCase):
    def test_json_toutes_salles(self):
        with mock.patch("culturecentro.aggregate.agreger", return_value=EVENEMENTS) as agreger:
            code, sortie = _lancer(["lister", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(sortie)[0]["titre"], "Concert")
        # Sans --source, agreger reçoit None (toutes les salles).
        self.assertIsNone(agreger.call_args.args[0])

    def test_source_unique(self):
        with mock.patch("culturecentro.aggregate.agreger", return_value=EVENEMENTS) as agreger:
            code, _ = _lancer(["lister", "--source", "theatre-granada", "--format", "json"])
        self.assertEqual(code, 0)
        sources = agreger.call_args.args[0]
        self.assertEqual([s.slug for s in sources], ["theatre-granada"])

    def test_source_inconnue_retourne_2(self):
        code, _ = _lancer(["lister", "--source", "salle-inexistante"])
        self.assertEqual(code, 2)

    def test_echec_reseau_retourne_1(self):
        with mock.patch(
            "culturecentro.aggregate.agreger", side_effect=requests.RequestException("boom")
        ):
            code, _ = _lancer(["lister"])
        self.assertEqual(code, 1)

    def test_ecrit_fichier(self):
        with tempfile.TemporaryDirectory() as rep:
            chemin = os.path.join(rep, "tout.json")
            with mock.patch("culturecentro.aggregate.agreger", return_value=EVENEMENTS):
                code, _ = _lancer(["lister", "--format", "json", "-o", chemin])
            self.assertEqual(code, 0)
            with open(chemin, encoding="utf-8") as flux:
                self.assertEqual(json.load(flux)[0]["titre"], "Concert")


class TestReprisesEtRapport(unittest.TestCase):
    def test_options_transmises_et_feed_precedent_relu(self):
        with tempfile.TemporaryDirectory() as rep:
            precedent = os.path.join(rep, "precedent.json")
            with open(precedent, "w", encoding="utf-8") as flux:
                json.dump([dict(EVENEMENTS[0].to_dict(), id="concert-2026-10-01")], flux)
            with mock.patch("culturecentro.aggregate.agreger", return_value=[]) as agreger:
                code, _ = _lancer(
                    ["lister", "--tentatives", "3", "--attente", "120", "--precedent", precedent]
                )
        self.assertEqual(code, 0)
        kwargs = agreger.call_args.kwargs
        self.assertEqual((kwargs["tentatives"], kwargs["attente"]), (3, 120.0))
        self.assertEqual(kwargs["precedents"], EVENEMENTS)

    def test_sans_reprise_ni_repli_par_defaut(self):
        with mock.patch("culturecentro.aggregate.agreger", return_value=[]) as agreger:
            code, _ = _lancer(["lister"])
        self.assertEqual(code, 0)
        self.assertEqual(agreger.call_args.kwargs["tentatives"], 1)
        self.assertIsNone(agreger.call_args.kwargs["precedents"])

    def test_feed_precedent_illisible_ignore(self):
        with tempfile.TemporaryDirectory() as rep:
            precedent = os.path.join(rep, "precedent.json")
            for contenu in (
                "pas du json",
                '{"titre": "pas une liste"}',
                '[{"lieu": "sans titre"}]',
            ):
                with open(precedent, "w", encoding="utf-8") as flux:
                    flux.write(contenu)
                with mock.patch("culturecentro.aggregate.agreger", return_value=[]) as agreger:
                    with self.assertLogs("culturecentro.cli", level="WARNING"):
                        code, _ = _lancer(["lister", "--precedent", precedent])
                self.assertEqual(code, 0)
                self.assertEqual(agreger.call_args.kwargs["precedents"], [])
            manquant = os.path.join(rep, "absent.json")
            with mock.patch("culturecentro.aggregate.agreger", return_value=[]) as agreger:
                with self.assertLogs("culturecentro.cli", level="WARNING"):
                    _lancer(["lister", "--precedent", manquant])
            self.assertEqual(agreger.call_args.kwargs["precedents"], [])

    def test_rapport_des_salles_en_echec(self):
        from culturecentro.aggregate import Echec

        def agreger_avec_echec(sources, **kwargs):
            kwargs["echecs"].append(Echec("ko", "KO", "Connection refused", 3, conserves=5))
            return EVENEMENTS

        with tempfile.TemporaryDirectory() as rep:
            rapport = os.path.join(rep, "rapport.json")
            with mock.patch("culturecentro.aggregate.agreger", side_effect=agreger_avec_echec):
                code, _ = _lancer(["lister", "--format", "json", "--rapport", rapport])
            self.assertEqual(code, 0)  # le feed est produit malgré l'échec
            with open(rapport, encoding="utf-8") as flux:
                self.assertEqual(
                    json.load(flux),
                    [
                        {
                            "slug": "ko",
                            "nom": "KO",
                            "erreur": "Connection refused",
                            "tentatives": 3,
                            "conserves": 5,
                        }
                    ],
                )
            with mock.patch("culturecentro.aggregate.agreger", return_value=EVENEMENTS):
                _lancer(["lister", "--rapport", rapport])
            with open(rapport, encoding="utf-8") as flux:
                self.assertEqual(json.load(flux), [])  # aucun échec : liste vide


class TestSansFiches(unittest.TestCase):
    def test_option_transmise_a_agreger(self):
        from culturecentro.cli import principal

        with mock.patch("culturecentro.aggregate.agreger", return_value=[]) as agreger:
            with mock.patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(principal(["lister", "--sans-fiches"]), 0)
                self.assertFalse(agreger.call_args.kwargs["lire_fiches"])
                self.assertEqual(principal(["lister"]), 0)
                self.assertTrue(agreger.call_args.kwargs["lire_fiches"])


class TestCommandePages(unittest.TestCase):
    URL = "https://remtav.github.io/culturecentro/"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rep = self._tmp.name
        self.feed = os.path.join(self.rep, "evenements.json")

    def tearDown(self):
        self._tmp.cleanup()

    def _ecrire_feed(self, contenu):
        with open(self.feed, "w", encoding="utf-8") as flux:
            flux.write(contenu)

    def _pages(self, url=URL):
        return _lancer(["pages", "--feed", self.feed, "--dossier", self.rep, "--url-base", url])[0]

    def test_identifiants_dans_le_feed_et_pages(self):
        self._ecrire_feed(json.dumps([EVENEMENTS[0].to_dict(), {"titre": "Sans date"}]))
        self.assertEqual(self._pages(), 0)
        with open(self.feed, encoding="utf-8") as flux:
            feed = json.load(flux)
        self.assertEqual(feed[0]["id"], "concert-2026-10-01")
        self.assertNotIn("id", feed[1])
        self.assertTrue(
            os.path.isfile(os.path.join(self.rep, "e", "concert-2026-10-01", "index.html"))
        )
        self.assertTrue(os.path.isfile(os.path.join(self.rep, "404.html")))

    def test_feed_vide(self):
        self._ecrire_feed("[]\n")
        self.assertEqual(self._pages(), 0)
        with open(self.feed, encoding="utf-8") as flux:
            self.assertEqual(flux.read(), "[]\n")

    def test_feed_illisible_ou_inattendu(self):
        self.assertEqual(self._pages(), 1)  # absent
        self._ecrire_feed("{pas du json")
        self.assertEqual(self._pages(), 1)
        self._ecrire_feed('{"titre": "pas une liste"}')
        self.assertEqual(self._pages(), 1)

    def test_url_base_invalide(self):
        self._ecrire_feed("[]")
        self.assertEqual(self._pages("remtav.github.io/culturecentro"), 2)


if __name__ == "__main__":
    unittest.main()
