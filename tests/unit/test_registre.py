"""Tests du registre des sources."""

from __future__ import annotations

import unittest

from culturecentro import sources
from culturecentro.sources.base import Source


class TestRegistre(unittest.TestCase):
    def test_sources_connues(self):
        self.assertIn("theatre-granada", sources.SOURCES)
        self.assertIn("la-petite-boite-noire", sources.SOURCES)
        self.assertIn("maison-des-arts-de-la-parole", sources.SOURCES)
        self.assertIn("tremplin-16-30", sources.SOURCES)
        self.assertIn("mbas", sources.SOURCES)
        self.assertIn("sporobole", sources.SOURCES)
        self.assertIn("le-grand-espace", sources.SOURCES)

    def test_toutes_sont_des_sources(self):
        for source in sources.toutes():
            self.assertIsInstance(source, Source)

    def test_obtenir_par_slug(self):
        self.assertEqual(sources.obtenir("theatre-granada").slug, "theatre-granada")

    def test_lister_renseigne_le_partenaire(self):
        from unittest import mock

        from culturecentro.models import Evenement

        source = sources.obtenir("theatre-granada")
        with (
            mock.patch("culturecentro.sources.base.telecharger", return_value="<p></p>"),
            mock.patch.object(
                source, "extraire", return_value=[Evenement("X", None, lieu="Ailleurs")]
            ),
        ):
            evs = source.lister_evenements_a_venir()
        self.assertEqual((evs[0].partenaire, evs[0].lieu), ("Théâtre Granada", "Ailleurs"))

    def test_obtenir_inconnu(self):
        with self.assertRaises(KeyError):
            sources.obtenir("salle-inexistante")


if __name__ == "__main__":
    unittest.main()
