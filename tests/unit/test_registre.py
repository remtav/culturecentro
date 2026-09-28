"""Tests du registre des sources."""

from __future__ import annotations

import unittest

from culturecentro import sources
from culturecentro.sources.base import Source


class TestRegistre(unittest.TestCase):
    def test_sources_connues(self):
        self.assertIn("theatre-granada", sources.SOURCES)
        self.assertIn("la-petite-boite-noire", sources.SOURCES)

    def test_toutes_sont_des_sources(self):
        for source in sources.toutes():
            self.assertIsInstance(source, Source)

    def test_obtenir_par_slug(self):
        self.assertEqual(sources.obtenir("theatre-granada").slug, "theatre-granada")

    def test_obtenir_inconnu(self):
        with self.assertRaises(KeyError):
            sources.obtenir("salle-inexistante")


if __name__ == "__main__":
    unittest.main()
