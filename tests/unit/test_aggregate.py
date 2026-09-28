"""Tests de l'agrégation multi-salles."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest import mock

import requests

from culturecentro.aggregate import agreger
from culturecentro.models import Evenement
from culturecentro.sources.base import Source


class _SourceFactice(Source):
    def __init__(self, slug, nom, evenements=None, exc=None):
        self.slug = slug
        self.nom = nom
        self.url_defaut = f"https://exemple/{slug}"
        self._evenements = evenements or []
        self._exc = exc

    def extraire(self, html, timeout, session):  # pragma: no cover - non utilisé
        return []

    def lister_evenements_a_venir(self, url=None, *, a_partir_de=None, timeout=20.0):
        if self._exc is not None:
            raise self._exc
        return list(self._evenements)


SEUIL = datetime(2026, 1, 1, tzinfo=timezone.utc)


class TestAgreger(unittest.TestCase):
    def test_fusionne_trie_et_remplit_le_lieu(self):
        a = _SourceFactice("a", "Salle A", [Evenement("Tard", datetime(2026, 11, 1, 20, 0))])
        b = _SourceFactice(
            "b", "Salle B", [Evenement("Tot", datetime(2026, 9, 1, 20, 0), lieu="Ailleurs")]
        )
        res = agreger([a, b], a_partir_de=SEUIL)
        self.assertEqual([e.titre for e in res], ["Tot", "Tard"])  # tri chronologique
        self.assertEqual(res[0].lieu, "Ailleurs")  # lieu existant conservé
        self.assertEqual(res[1].lieu, "Salle A")  # lieu manquant renseigné

    def test_partenaire_et_lieu_canonique(self):
        a = _SourceFactice(
            "a",
            "Maison des arts",
            [
                Evenement("Hors les murs", datetime(2026, 10, 1, 20, 0), lieu="Le Grand Espace"),
                Evenement("Chez nous", datetime(2026, 10, 2, 20, 0)),
                Evenement(
                    "Déjà attribué", datetime(2026, 10, 3, 20, 0), partenaire="Autre organisme"
                ),
            ],
        )
        res = agreger([a], a_partir_de=SEUIL)
        self.assertEqual([e.partenaire for e in res], ["Maison des arts"] * 2 + ["Autre organisme"])
        self.assertEqual(res[0].lieu, "Le Grand-Espace")  # alias ramené au nom canonique
        self.assertEqual(res[1].lieu, "Maison des arts")  # lieu manquant = partenaire

    def test_hors_centre_ville_ecarte(self):
        a = _SourceFactice(
            "a",
            "Salle A",
            [
                Evenement("Au centre", datetime(2026, 10, 1, 20, 0), lieu="Café 440"),
                Evenement(
                    "En région", datetime(2026, 10, 2, 20, 0), lieu="Centre d'art de Richmond"
                ),
                Evenement(
                    "Sur le campus",
                    datetime(2026, 10, 3, 20, 0),
                    lieu="Centre culturel de l'Université de Sherbrooke",
                ),
            ],
        )
        res = agreger([a], a_partir_de=SEUIL)
        self.assertEqual([e.titre for e in res], ["Au centre"])

    def test_categorie_par_source_mots_cles_ou_defaut(self):
        a = _SourceFactice(
            "a",
            "Salle A",
            [
                Evenement("Déjà classé", datetime(2026, 10, 1, 20, 0), categorie="arts"),
                Evenement("Grand concert", datetime(2026, 10, 2, 20, 0)),
                Evenement("Sans indice", datetime(2026, 10, 3, 20, 0)),
            ],
        )
        a.categorie_defaut = "litt"
        res = agreger([a], a_partir_de=SEUIL, lire_fiches=False)
        self.assertEqual([e.categorie for e in res], ["arts", "musique", "litt"])

    def test_categorie_par_la_fiche(self):
        a = _SourceFactice(
            "a",
            "Salle A",
            [Evenement("Sans indice", datetime(2026, 10, 3, 20, 0), lien="https://x/f")],
        )
        fiche = '<a rel="category" href="/c/">Danse</a>'
        with mock.patch("culturecentro.categories.telecharger", return_value=fiche):
            res = agreger([a], a_partir_de=SEUIL)
        self.assertEqual(res[0].categorie, "danse")

    def test_deduplique_entre_salles(self):
        meme = datetime(2026, 10, 2, 20, 0)
        a = _SourceFactice("a", "Salle A", [Evenement("Doublon", meme)])
        b = _SourceFactice("b", "Salle B", [Evenement("Doublon", meme)])
        res = agreger([a, b], a_partir_de=SEUIL)
        self.assertEqual(len(res), 1)

    def test_une_salle_en_echec_est_ignoree(self):
        ok = _SourceFactice("ok", "OK", [Evenement("Vivant", datetime(2026, 10, 1, 20, 0))])
        ko = _SourceFactice("ko", "KO", exc=requests.RequestException("réseau"))
        with self.assertLogs("culturecentro.aggregate", level="WARNING"):
            res = agreger([ok, ko], a_partir_de=SEUIL)
        self.assertEqual([e.titre for e in res], ["Vivant"])

    def test_sources_par_defaut_sont_toutes(self):
        # Sans argument, agreger interroge toutes les sources enregistrées.
        with mock.patch("culturecentro.aggregate.toutes", return_value=[]) as toutes:
            self.assertEqual(agreger(a_partir_de=SEUIL), [])
        toutes.assert_called_once()


if __name__ == "__main__":
    unittest.main()
