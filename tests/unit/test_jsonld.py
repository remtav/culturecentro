"""Tests de l'extraction JSON-LD (schema.org Event)."""

from __future__ import annotations

import unittest
from datetime import datetime

from culturecentro.jsonld import extraire_depuis_jsonld

JSONLD = """
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
  {"@type":"Event","name":"Concert JSON-LD","startDate":"2027-03-01T20:00:00",
   "endDate":"2027-03-01T22:00:00",
   "url":"https://x/concert/","location":{"@type":"Place","name":"Salle X"},
   "image":["https://x/affiche.jpg"]},
  {"@type":"WebPage","name":"pas un événement"}
]}
</script>
"""


class TestExtraireDepuisJsonld(unittest.TestCase):
    def setUp(self):
        self.evenements = extraire_depuis_jsonld(JSONLD)

    def test_un_seul_event(self):
        self.assertEqual(len(self.evenements), 1)

    def test_champs(self):
        ev = self.evenements[0]
        self.assertEqual(ev.titre, "Concert JSON-LD")
        self.assertEqual(ev.date_debut, datetime(2027, 3, 1, 20, 0))
        self.assertEqual(ev.date_fin, datetime(2027, 3, 1, 22, 0))
        self.assertEqual(ev.lien, "https://x/concert/")
        self.assertEqual(ev.lieu, "Salle X")
        self.assertEqual(ev.image, "https://x/affiche.jpg")

    def test_html_sans_jsonld(self):
        self.assertEqual(extraire_depuis_jsonld("<p>rien</p>"), [])

    def test_jsonld_invalide_ignore(self):
        html = '<script type="application/ld+json">{pas du json}</script>'
        self.assertEqual(extraire_depuis_jsonld(html), [])


if __name__ == "__main__":
    unittest.main()
