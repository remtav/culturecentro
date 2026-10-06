"""Tests de la catégorisation automatique (libellés, mots-clés, fiche, cache)."""

from __future__ import annotations

import unittest
from unittest import mock

import requests

from culturecentro.categories import (
    AGE_MAX_JEUNESSE,
    CATEGORIES,
    Categorisation,
    categoriser,
    depuis_libelle,
    depuis_page,
    deviner,
    est_age_jeunesse,
)
from culturecentro.models import Evenement

FICHE_WORDPRESS = """
<html><head><title>Salebarbes - Théâtre Granada</title></head><body>
<nav><a href="/">Accueil</a></nav>
<article><h1>Salebarbes</h1>
  <span class="cat-btn">Categories</span>
  <a rel="category tag" href="/category/programmation/">Programmation</a>
  <a rel="category tag" href="/category/programmation/theatre-granada/humour/">Humour</a>
</article></body></html>
"""

FICHE_JSONLD = """
<html><head><script type="application/ld+json">
{"@context":"https://schema.org","@type":"DanceEvent","name":"Gala","startDate":"2027-01-01"}
</script></head><body><p>rien</p></body></html>
"""

FICHE_TEXTE = """
<html><head><title>Soirée</title>
<meta name="description" content="Un concert intime, chansons et guitare acoustique.">
</head><body><main><p>Le groupe présente son nouvel album en concert.</p></main></body></html>
"""


class TestCategories(unittest.TestCase):
    def test_jeunesse_et_humour_presentes(self):
        self.assertIn("jeunesse", CATEGORIES)
        self.assertIn("humour", CATEGORIES)


class TestDepuisLibelle(unittest.TestCase):
    def test_taxonomie_wordpress(self):
        self.assertEqual(depuis_libelle("Musique"), "musique")
        self.assertEqual(depuis_libelle("Humour"), "humour")
        self.assertEqual(depuis_libelle("Hommage"), "musique")
        self.assertEqual(depuis_libelle("Souper-spectacle"), "musique")

    def test_schema_org(self):
        self.assertEqual(depuis_libelle("MusicEvent"), "musique")
        self.assertEqual(depuis_libelle("TheaterEvent"), "theatre")
        self.assertEqual(depuis_libelle("ChildrensEvent"), "jeunesse")

    def test_libelle_compose(self):
        self.assertEqual(depuis_libelle("Exposition temporaire"), "arts")
        self.assertEqual(depuis_libelle("Théâtre jeune public"), "theatre")

    def test_inconnu(self):
        self.assertIsNone(depuis_libelle("Programmation"))
        self.assertIsNone(depuis_libelle(None))
        self.assertIsNone(depuis_libelle(""))


class TestDeviner(unittest.TestCase):
    def test_genres(self):
        self.assertEqual(deviner("Ismène", "Théâtre classique revisité"), "theatre")
        self.assertEqual(deviner("Respublica", "Danse épaissiste — ZemmourBallet"), "danse")
        self.assertEqual(deviner("Contes afro-antillais", None), "litt")
        self.assertEqual(deviner("Cathy Gauthier", "En rodage"), "humour")
        self.assertEqual(deviner("Sherbrooke Comédie Club"), "humour")
        self.assertEqual(deviner("Illusion Floyd", "Hommage à Pink Floyd"), "musique")
        self.assertEqual(deviner("EXTENSIONS.", "Exposition temporaire"), "arts")
        self.assertEqual(deviner("Petit guide de perception des œuvres d’art"), "arts")
        self.assertEqual(deviner("Festival de Danse Contemporaine"), "festival")

    def test_jeunesse_prioritaire(self):
        self.assertEqual(deviner("Nora la trotteuse", "Théâtre, dès 4 ans"), "jeunesse")
        self.assertEqual(deviner("Heure du conte", "pour les tout-petits"), "jeunesse")
        # « enfant » seul n'est pas un public (titre d'humoriste).
        self.assertEqual(deviner("Daniel Grenier", "Cœur d'enfant"), None)

    def test_age_minimal_d_enfant_vaut_jeunesse(self):
        for texte in (
            "dès 4 ans",
            "8 ans et plus",
            "12 ans et +",
            "de 6 à 12 ans",
            "à partir de 3 ans",
        ):
            with self.subTest(texte=texte):
                self.assertEqual(deviner("Spectacle", texte), "jeunesse")

    def test_age_minimal_d_ado_ou_d_adulte_n_est_pas_jeunesse(self):
        # « 15 ans et plus » restreint l'accès : c'est l'inverse d'un jeune public.
        for texte in (
            "15 ans et plus",
            "18 ans et +",
            "à partir de 16 ans",
            "pour les 13 à 17 ans",
        ):
            with self.subTest(texte=texte):
                self.assertIsNone(deviner("Spectacle", texte))
        self.assertEqual(deviner("Le songe d'une nuit d'été", "Théâtre, 15 ans et plus"), "theatre")

    def test_seuil_age_jeunesse(self):
        self.assertEqual(AGE_MAX_JEUNESSE, 12)
        self.assertTrue(est_age_jeunesse(12))
        self.assertFalse(est_age_jeunesse(13))

    def test_egalite_departagee_et_seuil(self):
        # théâtre + lecture : priorité à la littérature.
        self.assertEqual(
            deviner("Architectures de la joie", "Spectacle • Théâtre • Lecture"), "litt"
        )
        self.assertIsNone(deviner("5@7", "avec Michèle Nguyen"))
        self.assertIsNone(deviner("Concert", seuil=2))
        self.assertIsNone(deviner(None, ""))

    def test_public_desactive(self):
        self.assertEqual(deviner("Théâtre pour les tout-petits", public=False), "theatre")


class TestDepuisPage(unittest.TestCase):
    def test_taxonomie(self):
        self.assertEqual(depuis_page(FICHE_WORDPRESS), "humour")

    def test_jsonld(self):
        self.assertEqual(depuis_page(FICHE_JSONLD), "danse")

    def test_texte(self):
        self.assertEqual(depuis_page(FICHE_TEXTE), "musique")

    def test_rien(self):
        self.assertIsNone(depuis_page("<html><body><p>Bonjour</p></body></html>"))

    def test_menu_ignore_et_public_non_deduit_du_corps(self):
        page = (
            "<html><head><title>5@7</title></head><body>"
            '<div id="main-header"><ul class="menu"><li>Zone scolaire</li><li>Jeune public</li></ul></div>'
            "<article><p>Une soirée de contes pour les tout-petits et les grands, avec deux conteurs.</p></article>"
            "</body></html>"
        )
        self.assertEqual(depuis_page(page), "litt")


class TestCategorisation(unittest.TestCase):
    def test_ordre_source_mots_cles_fiche_defaut(self):
        session = mock.Mock()
        with mock.patch(
            "culturecentro.categories.telecharger", return_value=FICHE_WORDPRESS
        ) as tele:
            cat = Categorisation(session=session)
            self.assertEqual(cat.categoriser(Evenement("X", None, categorie="arts")), "arts")
            self.assertEqual(
                cat.categoriser(Evenement("Concert", None, lien="https://x/1")), "musique"
            )
            self.assertEqual(cat.categoriser(Evenement("Y", None, lien="https://x/2")), "humour")
            self.assertEqual(cat.categoriser(Evenement("Y", None, lien="https://x/2")), "humour")
            self.assertEqual(cat.categoriser(Evenement("Z", None), defaut="litt"), "litt")
        tele.assert_called_once()  # la fiche https://x/2 est lue une seule fois (cache)
        self.assertEqual(cat.fiches_lues, 1)

    def test_sans_lecture_de_fiche(self):
        session = mock.Mock()
        with mock.patch("culturecentro.categories.telecharger") as tele:
            cat = Categorisation(session=session)
            self.assertEqual(
                cat.categoriser(
                    Evenement("Y", None, lien="https://x/2"), "musique", lire_fiche=False
                ),
                "musique",
            )
            self.assertEqual(
                Categorisation(session=None).categoriser(Evenement("Y", None, lien="https://x/2")),
                None,
            )
        tele.assert_not_called()

    def test_fiche_illisible_et_garde_fou(self):
        session = mock.Mock()
        with mock.patch(
            "culturecentro.categories.telecharger", side_effect=requests.ConnectionError("x")
        ):
            cat = Categorisation(session=session, maximum_fiches=1)
            self.assertEqual(
                cat.categoriser(Evenement("A", None, lien="https://x/a"), "litt"), "litt"
            )
            self.assertEqual(
                cat.categoriser(Evenement("B", None, lien="https://x/b"), "litt"), "litt"
            )
        self.assertEqual(cat.fiches_lues, 1)  # la seconde fiche n'est pas lue (maximum atteint)

    def test_raccourci_hors_ligne(self):
        self.assertEqual(categoriser(Evenement("Concert", None)), "musique")
        self.assertEqual(categoriser(Evenement("?", None, lien="https://x/"), "danse"), "danse")


if __name__ == "__main__":
    unittest.main()
