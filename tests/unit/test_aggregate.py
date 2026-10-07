"""Tests de l'agrégation multi-salles."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest import mock

import requests

from culturecentro.aggregate import Echec, agreger
from culturecentro.models import Evenement
from culturecentro.sources.base import Source


class _SourceFactice(Source):
    def __init__(self, slug, nom, evenements=None, exc=None, echecs_avant_succes=None):
        self.slug = slug
        self.nom = nom
        self.url_defaut = f"https://exemple/{slug}"
        self._evenements = evenements or []
        self._exc = exc
        # Nombre d'appels en échec (``exc``) avant de répondre ; None = toujours.
        self._echecs_avant_succes = echecs_avant_succes
        self.appels = 0

    def extraire(self, html, timeout, session):  # pragma: no cover - non utilisé
        return []

    def lister_evenements_a_venir(self, url=None, *, a_partir_de=None, timeout=20.0):
        self.appels += 1
        if self._exc is not None and (
            self._echecs_avant_succes is None or self.appels <= self._echecs_avant_succes
        ):
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

    def test_fusionne_un_spectacle_annonce_par_deux_salles(self):
        meme = datetime(2026, 10, 13, 20, 0)
        a = _SourceFactice(
            "a",
            "Théâtre Granada",
            [
                Evenement(
                    "Maxime Gervais",
                    meme,
                    sous_titre="Les découvertes",
                    lieu="La Petite Boîte Noire",
                )
            ],
        )
        b = _SourceFactice(
            "b", "La Petite Boîte Noire", [Evenement("Maxime Gervais : C'était magnifique", meme)]
        )
        res = agreger([a, b], a_partir_de=SEUIL, lire_fiches=False)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].titre, "Maxime Gervais : C'était magnifique")
        self.assertEqual(res[0].partenaire, "Théâtre Granada")
        self.assertEqual(res[0].lieu, "La Petite Boîte Noire")

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


class TestReprisesEtRepli(unittest.TestCase):
    PANNE = requests.ConnectionError("Connection refused")

    def test_salle_reessayee_apres_attente(self):
        ok = _SourceFactice("ok", "OK", [Evenement("Stable", datetime(2026, 10, 1, 20, 0))])
        instable = _SourceFactice(
            "instable",
            "Instable",
            [Evenement("Revenu", datetime(2026, 10, 2, 20, 0))],
            exc=self.PANNE,
            echecs_avant_succes=2,
        )
        echecs = []
        with mock.patch("culturecentro.aggregate.time.sleep") as dormir:
            with self.assertLogs("culturecentro.aggregate", level="WARNING"):
                res = agreger(
                    [ok, instable],
                    a_partir_de=SEUIL,
                    lire_fiches=False,
                    tentatives=3,
                    attente=120,
                    echecs=echecs,
                )
        self.assertEqual([e.titre for e in res], ["Stable", "Revenu"])
        self.assertEqual([c.args for c in dormir.call_args_list], [(120,), (240,)])
        self.assertEqual((ok.appels, instable.appels), (1, 3))  # seule la salle en panne
        self.assertEqual(echecs, [])

    def test_sans_reprise_par_defaut(self):
        ko = _SourceFactice("ko", "KO", exc=self.PANNE)
        with mock.patch("culturecentro.aggregate.time.sleep") as dormir:
            with self.assertLogs("culturecentro.aggregate", level="WARNING"):
                agreger([ko], a_partir_de=SEUIL)
        dormir.assert_not_called()
        self.assertEqual(ko.appels, 1)

    def test_salle_toujours_en_echec_reprend_le_feed_precedent(self):
        ok = _SourceFactice("ok", "OK", [Evenement("Neuf", datetime(2026, 10, 3, 20, 0))])
        ko = _SourceFactice("ko", "KO", exc=self.PANNE)
        precedents = [
            Evenement("Ancien de KO", datetime(2026, 10, 1, 20, 0), partenaire="KO", lieu="KO"),
            Evenement("Passé de KO", datetime(2025, 10, 1, 20, 0), partenaire="KO", lieu="KO"),
            Evenement("Ancien de OK", datetime(2026, 10, 2, 20, 0), partenaire="OK", lieu="OK"),
        ]
        echecs = []
        with mock.patch("culturecentro.aggregate.time.sleep"):
            with self.assertLogs("culturecentro.aggregate", level="WARNING"):
                res = agreger(
                    [ok, ko],
                    a_partir_de=SEUIL,
                    lire_fiches=False,
                    tentatives=2,
                    precedents=precedents,
                    echecs=echecs,
                )
        # Seuls les événements de la salle en échec sont repris (et encore à venir) ;
        # ceux d'une salle qui a répondu viennent de sa réponse du jour.
        self.assertEqual([e.titre for e in res], ["Ancien de KO", "Neuf"])
        self.assertEqual(
            echecs, [Echec("ko", "KO", "Connection refused", tentatives=2, conserves=2)]
        )

    def test_erreur_d_extraction_non_reessayee(self):
        cassee = _SourceFactice("cassee", "Cassée", exc=AttributeError("'NoneType'"))
        echecs = []
        with mock.patch("culturecentro.aggregate.time.sleep") as dormir:
            with self.assertLogs("culturecentro.aggregate", level="ERROR"):
                res = agreger([cassee], a_partir_de=SEUIL, tentatives=3, echecs=echecs)
        self.assertEqual(res, [])
        dormir.assert_not_called()
        self.assertEqual(cassee.appels, 1)
        self.assertEqual(echecs, [Echec("cassee", "Cassée", "AttributeError : 'NoneType'", 1)])

    def test_ordre_du_registre_conserve_apres_reprise(self):
        # La première salle du registre départage deux annonces aussi complètes :
        # une salle réessayée garde son rang.
        meme = datetime(2026, 10, 13, 20, 0)
        a = _SourceFactice(
            "a", "Salle A", [Evenement("Spectacle", meme)], exc=self.PANNE, echecs_avant_succes=1
        )
        b = _SourceFactice("b", "Salle B", [Evenement("Spectacle", meme)])
        with mock.patch("culturecentro.aggregate.time.sleep"):
            with self.assertLogs("culturecentro.aggregate", level="WARNING"):
                res = agreger([a, b], a_partir_de=SEUIL, lire_fiches=False, tentatives=2)
        self.assertEqual([e.partenaire for e in res], ["Salle A"])
