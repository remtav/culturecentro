"""Tests des pages de partage (aperçu riche des liens partagés)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from culturecentro.partage import (
    attribuer_identifiants,
    description,
    generer_pages,
    quand,
    slugifier,
)

BASE = "https://remtav.github.io/culturecentro/"


def _ev(titre, debut, **autres):
    return {"titre": titre, "date_debut": debut, **autres}


class TestSlugifier(unittest.TestCase):
    def test_accents_et_ligatures(self):
        self.assertEqual(slugifier("Les Belles-Sœurs"), "les-belles-soeurs")
        self.assertEqual(slugifier("Exposition « Œuvres d'hiver »"), "exposition-oeuvres-d-hiver")
        self.assertEqual(slugifier("Ismene (English version)"), "ismene-english-version")
        self.assertEqual(slugifier("  Été 2026 !  "), "ete-2026")

    def test_vide(self):
        self.assertEqual(slugifier("« — »"), "")


class TestIdentifiants(unittest.TestCase):
    def test_titre_et_date(self):
        feed = [_ev("Les Belles-Sœurs", "2026-10-03T20:00:00")]
        attribuer_identifiants(feed)
        self.assertEqual(feed[0]["id"], "les-belles-soeurs-2026-10-03")

    def test_meme_titre_meme_jour_distingue_par_l_heure(self):
        feed = [
            _ev("Matinée contes", "2026-11-08T14:00:00"),
            _ev("Matinée contes", "2026-11-08T19:30:00"),
            _ev("Matinée contes", "2026-11-08T00:00:00"),  # heure inconnue
            _ev("Matinée contes", "2026-11-08T00:00:00"),
        ]
        attribuer_identifiants(feed)
        self.assertEqual(
            [ev["id"] for ev in feed],
            [
                "matinee-contes-2026-11-08",
                "matinee-contes-2026-11-08-1930",
                "matinee-contes-2026-11-08-2",
                "matinee-contes-2026-11-08-3",
            ],
        )

    def test_sans_date_sans_identifiant(self):
        feed = [_ev("Sans date", None, id="ancien"), _ev("Date invalide", "bientôt")]
        attribuer_identifiants(feed)
        self.assertNotIn("id", feed[0])
        self.assertNotIn("id", feed[1])

    def test_titre_long_ou_vide(self):
        feed = [
            _ev("A" * 80 + " suite", "2026-10-03"),
            _ev("« »", "2026-10-03"),
            _ev(None, "2026-10-04"),
        ]
        attribuer_identifiants(feed)
        self.assertEqual(feed[0]["id"], "a" * 60 + "-2026-10-03")
        self.assertEqual(feed[1]["id"], "evenement-2026-10-03")
        self.assertEqual(feed[2]["id"], "sans-titre-2026-10-04")


class TestTextes(unittest.TestCase):
    def test_quand_un_jour(self):
        self.assertEqual(quand(_ev("x", "2026-10-17T20:00:00")), "Samedi 17 octobre · 20 h 00")
        self.assertEqual(quand(_ev("x", "2026-11-01T00:00:00")), "Dimanche 1er novembre")
        # Fin le même jour : pas une plage.
        self.assertEqual(
            quand(_ev("x", "2026-10-17T20:00:00", date_fin="2026-10-17T22:00:00")),
            "Samedi 17 octobre · 20 h 00",
        )

    def test_quand_plage(self):
        self.assertEqual(
            quand(_ev("x", "2026-10-21T19:30:00", date_fin="2026-10-22T00:00:00")),
            "Du 21 au 22 octobre",
        )
        self.assertEqual(
            quand(_ev("x", "2026-09-20T00:00:00", date_fin="2026-11-15T00:00:00")),
            "Du 20 septembre au 15 novembre",
        )

    def test_quand_sans_date_ou_invalide(self):
        self.assertEqual(quand(_ev("x", None)), "")
        self.assertEqual(quand(_ev("x", "2026-13-45")), "")

    def test_description(self):
        ev = _ev(
            "Contes",
            "2026-10-19T20:00:00",
            partenaire="Maison des arts de la parole",
            lieu="Café 440",
            sous_titre="avec Marien Guillé",
        )
        self.assertEqual(
            description(ev),
            "Lundi 19 octobre · 20 h 00 · Maison des arts de la parole · Café 440 — avec Marien Guillé",
        )
        ev = _ev("x", "2026-10-19", partenaire="Sporobole", lieu="Sporobole", sous_titre="y" * 300)
        self.assertTrue(description(ev).startswith("Lundi 19 octobre · Sporobole — yyy"))
        self.assertLessEqual(len(description(ev)), 200)
        self.assertEqual(description(_ev("x", None, sous_titre="Seul")), "Seul")


class TestGenererPages(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _generer(self, feed, base=BASE):
        attribuer_identifiants(feed)
        return generer_pages(feed, self.dossier, base)

    def _lire(self, ident):
        return (self.dossier / "e" / ident / "index.html").read_text(encoding="utf-8")

    def test_balises_open_graph(self):
        feed = [
            _ev(
                "Les Belles-Sœurs",
                "2026-10-17T20:00:00",
                partenaire="Théâtre Granada",
                lieu="Théâtre Granada",
                lien="https://theatregranada.com/belles-soeurs",
                image="https://theatregranada.com/affiche.jpg?w=1200&h=630",
            )
        ]
        self.assertEqual(self._generer(feed), 1)
        page = self._lire("les-belles-soeurs-2026-10-17")
        url = BASE + "e/les-belles-soeurs-2026-10-17/"
        self.assertIn(f'<meta property="og:url" content="{url}">', page)
        self.assertIn(f'<link rel="canonical" href="{url}">', page)
        self.assertIn('<meta property="og:title" content="Les Belles-Sœurs">', page)
        self.assertIn(
            '<meta property="og:description" content="Samedi 17 octobre · 20 h 00 · Théâtre Granada">',
            page,
        )
        self.assertIn(
            '<meta property="og:image" content="https://theatregranada.com/affiche.jpg?w=1200&amp;h=630">',
            page,
        )
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', page)
        # Redirection immédiate vers l'agenda, où l'événement est mis en évidence.
        self.assertIn('location.replace("../../?e=les-belles-soeurs-2026-10-17")', page)
        self.assertIn('href="https://theatregranada.com/belles-soeurs"', page)

    def test_image_par_defaut(self):
        feed = [
            _ev("Sans affiche", "2026-10-17", image="/relative.jpg", lien="javascript:alert(1)")
        ]
        self._generer(feed)
        page = self._lire("sans-affiche-2026-10-17")
        self.assertIn(f'<meta property="og:image" content="{BASE}img/partage.png">', page)
        self.assertIn('<meta property="og:image:width" content="1200">', page)
        self.assertNotIn("javascript:", page)  # lien partenaire non http(s) : ignoré

    def test_echappement(self):
        feed = [_ev('<script>alert("x")</script> & cie', "2026-10-17", sous_titre="« 1 > 0 »")]
        self._generer(feed)
        page = self._lire("script-alert-x-script-cie-2026-10-17")
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; cie", page)
        self.assertIn("« 1 &gt; 0 »", page)

    def test_anciennes_pages_supprimees_et_404(self):
        self._generer([_ev("Ancien", "2026-10-01")])
        self.assertTrue((self.dossier / "e" / "ancien-2026-10-01").is_dir())
        self.assertEqual(self._generer([_ev("Nouveau", "2026-10-02"), _ev("Sans date", None)]), 1)
        self.assertFalse((self.dossier / "e" / "ancien-2026-10-01").exists())
        page_404 = (self.dossier / "404.html").read_text(encoding="utf-8")
        # Le chemin de base du site, pour renvoyer /culturecentro/e/<id>/ vers /culturecentro/?e=<id>.
        self.assertIn('location.replace("/culturecentro/" + (m ? "?e=" + m[1] : ""))', page_404)

    def test_identifiant_invalide_ignore(self):
        feed = [{"titre": "x", "date_debut": "2026-10-02", "id": "../../etc"}]
        self.assertEqual(generer_pages(feed, self.dossier, BASE), 0)
        self.assertFalse((self.dossier / "e").exists())

    def test_url_base(self):
        with self.assertRaises(ValueError):
            generer_pages([], self.dossier, "remtav.github.io/culturecentro")
        # Sans barre finale : ajoutée.
        self._generer([_ev("Concert", "2026-10-02")], base="https://exemple.org")
        self.assertIn(
            'content="https://exemple.org/e/concert-2026-10-02/"', self._lire("concert-2026-10-02")
        )
        page_404 = (self.dossier / "404.html").read_text(encoding="utf-8")
        self.assertIn('location.replace("/" + ', page_404)


if __name__ == "__main__":
    unittest.main()
