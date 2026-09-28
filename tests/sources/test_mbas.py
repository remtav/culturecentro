"""Tests de la source Musée des beaux-arts de Sherbrooke (deux pages, périodes, CLI).

Hors-ligne : le réseau est simulé.
"""

from __future__ import annotations

import io
import json
import unittest
from datetime import datetime, timezone
from unittest import mock

import requests

from culturecentro.sources import mbas
from culturecentro.sources.mbas import (
    URL_A_VENIR,
    Evenement,
    MuseeDesBeauxArts,
    _extraire_depuis_blocs,
    _extraire_evenements,
    _lignes,
    main,
)

PAGE_EN_COURS = """
<main><article><div class="entry">
<div class="wp-block-columns">
 <div class="wp-block-column">
  <div id="rectangle">
   <p><a href="https://mbas.qc.ca/couleurs-manifestes-exposition-permanente/"><img src="https://x/coma-300x300.jpg" alt=""></a></p>
   <h2 style="text-align: left;"><em>COULEURS MANIFESTES</em></h2>
   <p>EXPOSITION PERMANENTE</p>
   <p>L’intensité de <em>Couleurs Manifestes</em> se révèle dans le pouvoir d’interpellation de la couleur, vu à travers une cinquantaine d’œuvres de la collection du Musée.</p>
   <div class="su-button-center"><a class="su-button" href="https://mbas.qc.ca/couleurs-manifestes-exposition-permanente/"><span>En savoir plus</span></a></div>
  </div>
 </div>
 <div class="wp-block-column">
  <div id="rectangle">
   <p><img src="https://x/centrale.jpg" srcset="https://x/centrale.jpg 224w, https://x/centrale-150x150.jpg 150w"></p>
   <h2><em><span>GALERIE ESPACE DIALOGUE</span></em></h2>
   <p>EXPO-VENTE<br>Jusqu’en octobre 2026</p>
   <p>En partenariat avec la Centrale des métiers d’arts.</p>
   <div class="su-button-center"><a class="su-button" href="https://mbas.qc.ca/espace-dialogue-metiers-darts/">En savoir plus</a></div>
  </div>
  <div id="rectangle">
   <p><img src="https://x/parcours-300x200.jpg"></p>
   <h2><em>PARCOURS PHOTO SHERBROOKE</em></h2>
   <p>EXPOSITION HORS LE MURS<br>10 septembre 2026 au 29 août 2027</p>
   <p>Une exposition photographique en plein air.</p>
   <div class="su-button-center"><a class="su-button" href="https://mbas.qc.ca/parcours-photo-sherbrooke-2026-2027/">En savoir plus</a></div>
  </div>
 </div>
</div>
</div></article></main>
"""

PAGE_A_VENIR = """
<main><div class="entry">
  <div id="rectangle">
   <p><img src="https://x/extensions-300x286.jpg"></p>
   <h2><em>EXTENSIONS.<br>Jean-Sébastien Denis</em></h2>
   <p>EXPOSITION TEMPORAIRE<br>15 octobre 2026 au 21 mars 2027</p>
   <p>Jean-Sébastien Denis repousse les limites de la peinture.</p>
   <p><span><div class="su-button-center"><a class="su-button" href="https://mbas.qc.ca/extensions-jean-sebastien-denis/">En savoir plus</a></div></span></p>
  </div>
  <div id="rectangle">
   <p><img src="https://x/baca-300x200.jpg"></p>
   <h2>BIENNALE D’ART CONTEMPORAIN AUTOCHTONE BACA – 8e édition</h2>
   <p>Iaohontso’ktá:tie / Traverser le territoire</p>
   <p>EXPOSITION TEMPORAIRE<br>15 avril au 19 septembre 2027</p>
   <p>Description longue de la biennale, qui s'étend sur plusieurs lignes et dépasse largement la longueur d'un sous-titre.</p>
   <div class="su-button-center"><a class="su-button" href="https://mbas.qc.ca/biennale-2027/">En savoir plus</a></div>
  </div>
  <div id="rectangle">
   <p><img src="https://x/habiter.jpg"></p>
   <h2>Petit guide de perception des œuvres d’art</h2>
   <p>EXPOSITION TEMPORAIRE<br>15 octobre 2026 au 21 mars 2027<br>Artiste invité : Michel Goulet</p>
   <div class="su-button-center"><a class="su-button" href="https://mbas.qc.ca/habiter/">En savoir plus</a></div>
  </div>
  <div id="rectangle"><p>Bloc sans titre</p></div>
</div></main>
"""

JSONLD = """
<script type="application/ld+json">
{"@type":"Event","name":"Repli JSON-LD","startDate":"2027-05-01T20:00:00","url":"https://x/e/"}
</script>
"""


class TestLignes(unittest.TestCase):
    def test_br_separe_les_lignes_et_em_ne_coupe_pas(self):
        from bs4 import BeautifulSoup

        bloc = BeautifulSoup(
            "<div><p>EXPO-VENTE<br>Jusqu’en octobre 2026</p><p>L’intensité de <em>Couleurs</em> se révèle.</p></div>",
            "html.parser",
        ).div
        self.assertEqual(
            _lignes(bloc),
            ["EXPO-VENTE", "Jusqu’en octobre 2026", "L’intensité de Couleurs se révèle."],
        )


class TestExtractionEnCours(unittest.TestCase):
    def setUp(self):
        self.evenements = _extraire_depuis_blocs(PAGE_EN_COURS)

    def test_titres(self):
        self.assertEqual(
            [e.titre for e in self.evenements],
            ["COULEURS MANIFESTES", "GALERIE ESPACE DIALOGUE", "PARCOURS PHOTO SHERBROOKE"],
        )

    def test_permanente_sans_date_sous_titre_type(self):
        ev = self.evenements[0]
        self.assertIsNone(ev.date_debut)
        self.assertIsNone(ev.date_fin)
        self.assertEqual(ev.sous_titre, "Exposition permanente")
        self.assertEqual(ev.lien, "https://mbas.qc.ca/couleurs-manifestes-exposition-permanente/")
        self.assertEqual(ev.image, "https://x/coma-300x300.jpg")

    def test_jusqu_en_donne_une_fin_seule(self):
        ev = self.evenements[1]
        self.assertIsNone(ev.date_debut)
        self.assertEqual(ev.date_fin, datetime(2026, 10, 31))
        self.assertEqual(ev.sous_titre, "Expo-vente")
        self.assertEqual(ev.image, "https://x/centrale.jpg")

    def test_periode_complete(self):
        ev = self.evenements[2]
        self.assertEqual(ev.date_debut, datetime(2026, 9, 10))
        self.assertEqual(ev.date_fin, datetime(2027, 8, 29))
        self.assertEqual(ev.sous_titre, "Exposition hors le murs")


class TestExtractionAVenir(unittest.TestCase):
    def setUp(self):
        self.evenements = _extraire_depuis_blocs(PAGE_A_VENIR)

    def test_titre_multiligne_et_periode(self):
        ev = self.evenements[0]
        self.assertEqual(ev.titre, "EXTENSIONS. Jean-Sébastien Denis")
        self.assertEqual(
            (ev.date_debut, ev.date_fin), (datetime(2026, 10, 15), datetime(2027, 3, 21))
        )
        self.assertEqual(ev.lien, "https://mbas.qc.ca/extensions-jean-sebastien-denis/")

    def test_sous_titre_avant_le_type(self):
        ev = self.evenements[1]
        self.assertEqual(ev.sous_titre, "Iaohontso’ktá:tie / Traverser le territoire")
        self.assertEqual(
            (ev.date_debut, ev.date_fin), (datetime(2027, 4, 15), datetime(2027, 9, 19))
        )

    def test_sous_titre_apres_la_periode(self):
        ev = self.evenements[2]
        self.assertEqual(ev.sous_titre, "Artiste invité : Michel Goulet")
        self.assertEqual(ev.date_debut, datetime(2026, 10, 15))

    def test_bloc_sans_titre_ignore(self):
        self.assertEqual(len(self.evenements), 3)


class TestExtraireEvenements(unittest.TestCase):
    def test_deux_pages_fusionnees(self):
        session = mock.Mock()
        with mock.patch.object(mbas, "telecharger", return_value=PAGE_A_VENIR) as tele:
            evs = _extraire_evenements(PAGE_EN_COURS, 5.0, session)
        tele.assert_called_once_with(URL_A_VENIR, 5.0, session=session)
        self.assertEqual(len(evs), 6)

    def test_page_supplementaire_en_echec_ignoree(self):
        with mock.patch.object(mbas, "telecharger", side_effect=requests.ConnectionError("x")):
            with self.assertLogs(mbas._LOG.name, level="WARNING"):
                evs = _extraire_evenements(PAGE_EN_COURS, 5.0, mock.Mock())
        self.assertEqual(len(evs), 3)

    def test_repli_jsonld(self):
        with mock.patch.object(mbas, "telecharger", return_value="<p>rien</p>"):
            with self.assertLogs(mbas._LOG.name, level="WARNING"):
                evs = _extraire_evenements(JSONLD, 5.0, mock.Mock())
        self.assertEqual([e.titre for e in evs], ["Repli JSON-LD"])

    def test_rien(self):
        with mock.patch.object(mbas, "telecharger", return_value="<p>rien</p>"):
            with self.assertLogs(mbas._LOG.name, level="WARNING"):
                self.assertEqual(_extraire_evenements("<p>rien</p>", 5.0, mock.Mock()), [])


class TestSource(unittest.TestCase):
    def test_bout_en_bout_hors_ligne(self):
        pages = {mbas.URL_EN_COURS: PAGE_EN_COURS, URL_A_VENIR: PAGE_A_VENIR}
        with mock.patch(
            "culturecentro.sources.base.telecharger",
            side_effect=lambda url, timeout, session=None: pages[url],
        ):
            with mock.patch.object(
                mbas, "telecharger", side_effect=lambda url, t, session=None: pages[url]
            ):
                evs = MuseeDesBeauxArts().lister_evenements_a_venir(
                    a_partir_de=datetime(2026, 11, 1, tzinfo=timezone.utc)
                )
        # Le 1er novembre 2026 : l'expo-vente (fin octobre) est terminée ; le
        # parcours photo et les expos d'octobre sont en cours ; la permanente
        # (sans date) ferme la liste.
        self.assertEqual(
            [e.titre[:10] for e in evs],
            ["PARCOURS P", "EXTENSIONS", "Petit guid", "BIENNALE D", "COULEURS M"],
        )
        self.assertIsInstance(evs[0], Evenement)


class TestCli(unittest.TestCase):
    def test_json_stdout(self):
        with (
            mock.patch.object(
                mbas.SOURCE,
                "lister_evenements_a_venir",
                return_value=[
                    Evenement("Expo", datetime(2026, 10, 15), date_fin=datetime(2027, 3, 21))
                ],
            ),
            mock.patch("sys.stdout", new_callable=io.StringIO) as sortie,
        ):
            self.assertEqual(main(["--format", "json"]), 0)
        self.assertEqual(json.loads(sortie.getvalue())[0]["date_fin"], "2027-03-21T00:00:00")

    def test_erreur_reseau_retourne_1(self):
        with mock.patch.object(
            mbas.SOURCE, "lister_evenements_a_venir", side_effect=requests.ConnectionError("x")
        ):
            self.assertEqual(main([]), 1)


if __name__ == "__main__":
    unittest.main()
