"""Tests des utilitaires HTML partagés (attributs, images)."""

from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from culturecentro.scraping import attribut, premiere_image, url_image


def _tag(html: str):
    soup = BeautifulSoup(html, "html.parser")
    return soup.find(True)


class TestAttribut(unittest.TestCase):
    def test_chaine(self):
        self.assertEqual(attribut(_tag('<a href="https://x/">x</a>'), "href"), "https://x/")

    def test_liste_multivaluee(self):
        self.assertEqual(attribut(_tag('<p class="a b">x</p>'), "class"), "a")

    def test_absent(self):
        self.assertIsNone(attribut(_tag("<p>x</p>"), "href"))


class TestUrlImage(unittest.TestCase):
    def test_src_simple(self):
        self.assertEqual(url_image(_tag('<img src="https://x/a.jpg">')), "https://x/a.jpg")

    def test_lazy_data_src_prioritaire_sur_pixel(self):
        img = _tag('<img src="data:image/gif;base64,R0lGOD" data-src="https://x/vrai.jpg">')
        self.assertEqual(url_image(img), "https://x/vrai.jpg")

    def test_data_lazy_src(self):
        self.assertEqual(
            url_image(_tag('<img data-lazy-src="https://x/l.jpg">')), "https://x/l.jpg"
        )

    def test_srcset_seul(self):
        img = _tag('<img srcset="https://x/a-366.jpg 366w, https://x/a-732.jpg 732w">')
        self.assertEqual(url_image(img), "https://x/a-366.jpg")

    def test_fond_css(self):
        div = _tag("""<div style="background-image:url('https://x/fond.png');color:red"></div>""")
        self.assertEqual(url_image(div), "https://x/fond.png")

    def test_fond_css_sans_guillemets(self):
        div = _tag(
            '<figure style="background-image:url(https://x/f.png);background-size:cover"></figure>'
        )
        self.assertEqual(url_image(div), "https://x/f.png")

    def test_espaces_nettoyes(self):
        self.assertEqual(url_image(_tag('<img src=" https://x/a.jpg ">')), "https://x/a.jpg")

    def test_rien(self):
        self.assertIsNone(url_image(_tag('<img alt="vide">')))
        self.assertIsNone(url_image(_tag('<img src="data:image/png;base64,AAAA">')))
        self.assertIsNone(url_image(None))


class TestPremiereImage(unittest.TestCase):
    def test_img_imbriquee(self):
        bloc = _tag(
            '<div><p>t</p><span><img src="https://x/1.jpg"></span><img src="https://x/2.jpg"></div>'
        )
        self.assertEqual(premiere_image(bloc), "https://x/1.jpg")

    def test_fond_css_descendant(self):
        bloc = _tag('<div><figure style="background-image:url(https://x/bg.png)"></figure></div>')
        self.assertEqual(premiere_image(bloc), "https://x/bg.png")

    def test_conteneur_lui_meme(self):
        bloc = _tag('<div style="background: url(https://x/self.png)"><p>t</p></div>')
        self.assertEqual(premiere_image(bloc), "https://x/self.png")

    def test_aucune(self):
        self.assertIsNone(premiere_image(_tag("<div><p>t</p></div>")))
        self.assertIsNone(premiere_image(None))


if __name__ == "__main__":
    unittest.main()
