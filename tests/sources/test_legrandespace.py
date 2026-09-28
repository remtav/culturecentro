"""Tests de la source Le Grand-Espace (édition, deux publics, dates, CLI).

Hors-ligne : le réseau est simulé.
"""

from __future__ import annotations

import io
import json
import unittest
from datetime import date, datetime, timezone
from unittest import mock

import requests

from culturecentro.sources import legrandespace as ge
from culturecentro.sources.legrandespace import (
    URL_GRAND_PUBLIC,
    URL_JEUNE_PUBLIC,
    Evenement,
    LeGrandEspace,
    _extraire_depuis_liste,
    _extraire_evenements,
    edition_courante,
    main,
    url_edition,
)

PAGE_GRAND = """
<div id="calendrier_step_liste_spectacle"><div class="row three_col">
  <div class="colonne spectacle">
    <div class="spectacle_image"><img class="product_image" src="https://x/picker.png"></div>
    <div class="spectacle_content"><h2 class="titre_spectacle">Ismène</h2>
      <div class="tuxedo--representation__date"><span>Du 7 <span><span>au 17 octobre 2026</span></span></span></div></div>
    <a class="cover_link calendrier_availlability" data-spectacle="5563" href="#"></a>
  </div>
</div></div>
<div class="liste_spectacle_block">
  <div class="colonne spectacle" data-public="grand-public">
    <div class="spectacle_image_cont"><div class="spectacle_image">
      <img class="product_image" src="https://x/ismene.png" srcset="https://x/ismene.png 2560w, https://x/ismene-366x275.png 366w">
      <img class="product_image_hover" src="https://x/ismene-hover.png">
    </div></div>
    <div class="spectacle_content"><div>
      <h2 class="titre_spectacle">Ismène</h2>
      <span class="sous_titre_spectacle">Théâtre classique revisité</span>
      <div><div class="tuxedo--representation"><div><div class="tuxedo--representation__date">
        <span>Du 7 <span><span>au 17 octobre 2026 <span></span></span></span></span>
      </div></div></div></div>
    </div></div>
    <a class="cover_link" href="https://legrandespace.ca/spectacle/ismene/"></a>
  </div>
  <div class="colonne spectacle" data-public="grand-public">
    <div class="spectacle_image"><img class="product_image" src="https://x/impro.jpg"></div>
    <div class="spectacle_content"><div>
      <span class="subtitle_spectacle">Création improvisée en danse, musique et lumière</span>
      <h2 class="titre_spectacle">ImproDanse</h2>
      <span class="compagnie_spectacle">ZemmourBallet</span>
      <div class="tuxedo--representation__date"><span>Du 29 octobre 2026 <span><span>au 28 mai 2027</span></span></span></div>
    </div></div>
    <a class="cover_link" href="https://legrandespace.ca/spectacle/improdanse/"></a>
  </div>
  <div class="colonne spectacle" data-public="grand-public">
    <div class="spectacle_image_cont"><span class="promotion">COMPLET</span>
      <div class="spectacle_image"><img class="product_image" src="https://x/funk.png"></div></div>
    <div class="spectacle_content"><div>
      <span class="subtitle_spectacle">Spectacle d'improvisation</span>
      <h2 class="titre_spectacle">Duo Funk Poggetti</h2>
      <div class="tuxedo--representation__date">[Terminé]</div>
    </div></div>
    <a class="cover_link" href="https://legrandespace.ca/spectacle/duo-funk-poggetti/"></a>
  </div>
  <div class="colonne spectacle"><div class="spectacle_content"><p>Sans titre</p></div><a class="cover_link" href="https://x/sans-titre/"></a></div>
</div>
"""

PAGE_JEUNE = """
<div class="liste_spectacle_block">
  <div class="colonne spectacle" data-public="jeune-public">
    <div class="spectacle_image"><img class="product_image" src="https://x/gout.png"></div>
    <div class="spectacle_content"><div>
      <span class="subtitle_spectacle">Spectacle de conte</span>
      <h2 class="titre_spectacle">Le goût des mots</h2>
      <span class="compagnie_spectacle">Najoua Darwiche</span>
      <div class="tuxedo--representation__date"><span>18 octobre 2026</span><span>10 h 00</span></div>
    </div></div>
    <a class="cover_link" href="https://legrandespace.ca/spectacle/le-gout-des-mots/"></a>
  </div>
  <div class="colonne spectacle" data-public="jeune-public">
    <div class="spectacle_image" style="background-image:url(https://x/fond.png)"></div>
    <div class="spectacle_content"><div>
      <h2 class="titre_spectacle">Sans date ni genre</h2>
    </div></div>
    <a class="cover_link" href="https://legrandespace.ca/spectacle/sans-date/"></a>
  </div>
</div>
"""

JSONLD = """
<script type="application/ld+json">
{"@type":"Event","name":"Repli JSON-LD","startDate":"2027-05-01T20:00:00","url":"https://x/e/"}
</script>
"""


class TestEdition(unittest.TestCase):
    def test_saison_commence_en_aout(self):
        self.assertEqual(edition_courante(date(2026, 9, 28)), "2026-2027")
        self.assertEqual(edition_courante(date(2026, 8, 1)), "2026-2027")
        self.assertEqual(edition_courante(date(2027, 3, 15)), "2026-2027")
        self.assertEqual(edition_courante(date(2027, 7, 31)), "2026-2027")
        self.assertEqual(edition_courante(date(2027, 8, 1)), "2027-2028")

    def test_url_edition(self):
        self.assertEqual(
            url_edition(URL_GRAND_PUBLIC, "2025-2026"),
            "https://legrandespace.ca/public/grand-public/?edition=2025-2026",
        )
        with mock.patch.object(ge, "edition_courante", return_value="2026-2027"):
            self.assertTrue(url_edition(URL_JEUNE_PUBLIC).endswith("?edition=2026-2027"))
            self.assertTrue(LeGrandEspace().url_defaut.endswith("grand-public/?edition=2026-2027"))


class TestExtractionListe(unittest.TestCase):
    def setUp(self):
        self.evenements = _extraire_depuis_liste(PAGE_GRAND)

    def test_selecteur_termine_et_sans_titre_ignores(self):
        self.assertEqual([e.titre for e in self.evenements], ["Ismène", "ImproDanse"])

    def test_plage_du_jour_au_jour(self):
        ev = self.evenements[0]
        self.assertEqual(
            (ev.date_debut, ev.date_fin), (datetime(2026, 10, 7), datetime(2026, 10, 17))
        )
        self.assertEqual(ev.lien, "https://legrandespace.ca/spectacle/ismene/")
        self.assertEqual(ev.sous_titre, "Théâtre classique revisité")
        self.assertEqual(ev.image, "https://x/ismene.png")

    def test_genre_et_compagnie(self):
        ev = self.evenements[1]
        self.assertEqual(
            ev.sous_titre, "Création improvisée en danse, musique et lumière — ZemmourBallet"
        )
        self.assertEqual(
            (ev.date_debut, ev.date_fin), (datetime(2026, 10, 29), datetime(2027, 5, 28))
        )

    def test_date_avec_heure_et_replis(self):
        evs = _extraire_depuis_liste(PAGE_JEUNE)
        self.assertEqual(evs[0].date_debut, datetime(2026, 10, 18, 10, 0))
        self.assertIsNone(evs[0].date_fin)
        self.assertEqual(evs[0].sous_titre, "Spectacle de conte — Najoua Darwiche")
        self.assertIsNone(evs[1].date_debut)
        self.assertIsNone(evs[1].sous_titre)
        self.assertEqual(evs[1].image, "https://x/fond.png")

    def test_sans_conteneur_de_liste(self):
        html = PAGE_JEUNE.replace('class="liste_spectacle_block"', 'class="autre"')
        self.assertEqual(len(_extraire_depuis_liste(html)), 2)


class TestExtraireEvenements(unittest.TestCase):
    def test_deux_publics_fusionnes(self):
        session = mock.Mock()
        with (
            mock.patch.object(ge, "edition_courante", return_value="2026-2027"),
            mock.patch.object(ge, "telecharger", return_value=PAGE_JEUNE) as tele,
        ):
            evs = _extraire_evenements(PAGE_GRAND, 5.0, session)
        tele.assert_called_once_with(
            "https://legrandespace.ca/public/jeune-public/?edition=2026-2027", 5.0, session=session
        )
        self.assertEqual(
            [e.titre for e in evs],
            ["Ismène", "ImproDanse", "Le goût des mots", "Sans date ni genre"],
        )

    def test_jeune_public_en_echec_ignore(self):
        with mock.patch.object(ge, "telecharger", side_effect=requests.ConnectionError("x")):
            with self.assertLogs(ge._LOG.name, level="WARNING"):
                evs = _extraire_evenements(PAGE_GRAND, 5.0, mock.Mock())
        self.assertEqual(len(evs), 2)

    def test_repli_jsonld(self):
        with mock.patch.object(ge, "telecharger", return_value="<p>rien</p>"):
            with self.assertLogs(ge._LOG.name, level="WARNING"):
                evs = _extraire_evenements(JSONLD, 5.0, mock.Mock())
        self.assertEqual([e.titre for e in evs], ["Repli JSON-LD"])

    def test_rien(self):
        with mock.patch.object(ge, "telecharger", return_value="<p>rien</p>"):
            with self.assertLogs(ge._LOG.name, level="WARNING"):
                self.assertEqual(_extraire_evenements("<p>rien</p>", 5.0, mock.Mock()), [])


class TestSource(unittest.TestCase):
    def test_bout_en_bout_hors_ligne(self):
        pages = {"grand-public": PAGE_GRAND, "jeune-public": PAGE_JEUNE}

        def _page(url, timeout, session=None):
            return next(page for cle, page in pages.items() if cle in url)

        with (
            mock.patch("culturecentro.sources.base.telecharger", side_effect=_page),
            mock.patch.object(ge, "telecharger", side_effect=_page),
        ):
            evs = LeGrandEspace().lister_evenements_a_venir(
                a_partir_de=datetime(2026, 10, 20, tzinfo=timezone.utc)
            )
        # Le 20 octobre : Ismène (fin le 17) est terminé ; ImproDanse (29 oct.)
        # et Le goût des mots (18 oct., passé) → seul ImproDanse reste daté.
        self.assertEqual([e.titre for e in evs], ["ImproDanse", "Sans date ni genre"])
        self.assertIsInstance(evs[0], Evenement)


class TestCli(unittest.TestCase):
    def test_json_stdout(self):
        with (
            mock.patch.object(
                ge.SOURCE,
                "lister_evenements_a_venir",
                return_value=[
                    Evenement("Ismène", datetime(2026, 10, 7), date_fin=datetime(2026, 10, 17))
                ],
            ),
            mock.patch("sys.stdout", new_callable=io.StringIO) as sortie,
        ):
            self.assertEqual(main(["--format", "json"]), 0)
        self.assertEqual(json.loads(sortie.getvalue())[0]["titre"], "Ismène")

    def test_erreur_reseau_retourne_1(self):
        with mock.patch.object(
            ge.SOURCE, "lister_evenements_a_venir", side_effect=requests.ConnectionError("x")
        ):
            self.assertEqual(main([]), 1)


if __name__ == "__main__":
    unittest.main()
