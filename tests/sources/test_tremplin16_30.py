"""Tests de la source Le Tremplin 16-30 (blocs « média + texte », dates libres, CLI).

Hors-ligne : le réseau est simulé.
"""

from __future__ import annotations

import io
import json
import unittest
from datetime import datetime, timezone
from unittest import mock

import requests

from culturecentro.sources import tremplin16_30 as tr
from culturecentro.sources.tremplin16_30 import (
    Evenement,
    Tremplin1630,
    _dates_du_bloc,
    _extraire_depuis_blocs,
    _extraire_evenements,
    main,
)

PAGE = """
<main id="main">
  <div class="wp-block-media-text alignwide is-image-fill has-media-on-the-right">
    <figure class="bg-center" style="background-image:url(https://x/jams.png);background-position:center;background-size:cover "></figure>
    <div class="wp-block-media-text__content">
      <h2 class="wp-block-heading">Jamlab du Tremplin – automne 2026</h2>
      <p class="event-data">Jeudis 17 septembre, 29 octobre, 26 novembre et 17 décembre         - 18h30 à 20h30</p>
      <p class="event-data"><a href="https://goo.gl/maps/KDYU4jrG3iZK4azNA" target="_blank">Salle multifonctionnelle du Tremplin</a></p>
      <p class="event-data">Gratuit!</p>
      <div class="wp-block-buttons"><div class="wp-block-button">
        <a class="more-info wp-block-button__link" href="https://tremplin16-30.com/evenements/jamlab-du-tremplin-automne-2026/">Plus d'infos</a>
      </div></div>
    </div>
  </div>
  <div class="wp-block-media-text alignwide is-image-fill">
    <figure class="bg-center" style="background-image:url(https://x/mali.png)"></figure>
    <div class="wp-block-media-text__content">
      <h2 class="wp-block-heading">Souper du monde – Mali</h2>
      <p class="event-data">Mardi 29 septembre 2026         - 17h</p>
      <p class="event-data"><a href="https://goo.gl/maps/KDYU4jrG3iZK4azNA">Salle multifonctionnelle du Tremplin</a></p>
      <p class="event-data">Contribution volontaire (5$ suggéré)</p>
      <div class="wp-block-buttons">
        <div class="wp-block-button"><a class="booking wp-block-button__link" href="https://forms.gle/x">Réserver</a></div>
        <div class="wp-block-button"><a class="more-info wp-block-button__link" href="https://tremplin16-30.com/evenements/souper-mali/">Plus d'infos</a></div>
      </div>
    </div>
  </div>
  <div class="wp-block-media-text alignwide">
    <figure><img src="https://x/ruches.png" alt=""></figure>
    <div class="wp-block-media-text__content">
      <h2 class="wp-block-heading">Les Ruches d’art du Tremplin – automne 2026</h2>
      <p class="event-data">Tous les mercredis du 9 septembre au 16 décembre         - 18h30 à 20h30</p>
      <p class="event-data">Salle multifonctionnelle du Tremplin</p>
      <a href="https://tremplin16-30.com/evenements/les-ruches-dart-du-tremplin-automne-2026/">Plus d'infos</a>
    </div>
  </div>
  <div class="wp-block-media-text"><div class="wp-block-media-text__content"><p>Bloc sans titre</p></div></div>
</main>
"""

JSONLD = """
<script type="application/ld+json">
{"@type":"Event","name":"Repli JSON-LD","startDate":"2027-05-01T20:00:00","url":"https://x/e/"}
</script>
"""

AUJOURDHUI = datetime(2026, 9, 28)


class TestDatesDuBloc(unittest.TestCase):
    def test_liste_de_dates_un_couple_par_date(self):
        couples = _dates_du_bloc(
            "Jeudis 17 septembre, 29 octobre, 26 novembre et 17 décembre - 18h30 à 20h30",
            "Jamlab – automne 2026",
            AUJOURDHUI,
        )
        self.assertEqual(
            couples,
            [
                (datetime(2026, 9, 17, 18, 30), None),
                (datetime(2026, 10, 29, 18, 30), None),
                (datetime(2026, 11, 26, 18, 30), None),
                (datetime(2026, 12, 17, 18, 30), None),
            ],
        )

    def test_date_unique_avec_annee(self):
        self.assertEqual(
            _dates_du_bloc("Mardi 29 septembre 2026 - 17h", "Souper", AUJOURDHUI),
            [(datetime(2026, 9, 29, 17, 0), None)],
        )

    def test_plage_serie(self):
        self.assertEqual(
            _dates_du_bloc(
                "Tous les mercredis du 9 septembre au 16 décembre - 18h30 à 20h30",
                "Ruches – automne 2026",
                AUJOURDHUI,
            ),
            [(datetime(2026, 9, 9, 18, 30), datetime(2026, 12, 16))],
        )

    def test_annee_manquante_prise_dans_l_annee_courante(self):
        self.assertEqual(
            _dates_du_bloc("Samedi 5 décembre - 19h", "Sans année", AUJOURDHUI),
            [(datetime(2026, 12, 5, 19, 0), None)],
        )

    def test_annee_manquante_date_loin_passee_reportee(self):
        # « 15 janvier » vu le 28 septembre 2026 : plus de 120 jours en arrière → 2027.
        self.assertEqual(
            _dates_du_bloc("15 janvier - 19h", "Sans année", AUJOURDHUI),
            [(datetime(2027, 1, 15, 19, 0), None)],
        )

    def test_plage_a_cheval_sur_deux_annees(self):
        self.assertEqual(
            _dates_du_bloc("du 10 décembre au 20 janvier", "Hiver", AUJOURDHUI),
            [(datetime(2026, 12, 10), datetime(2027, 1, 20))],
        )

    def test_sans_date(self):
        self.assertEqual(_dates_du_bloc("Gratuit!", "Titre", AUJOURDHUI), [])
        self.assertEqual(_dates_du_bloc("du 9 au 16 brumaire", "Titre", AUJOURDHUI), [])


class TestExtractionBlocs(unittest.TestCase):
    def setUp(self):
        self.evenements = _extraire_depuis_blocs(PAGE, AUJOURDHUI)

    def test_nombre_et_titres(self):
        # 4 dates du Jamlab + 1 souper + 1 série ; le bloc sans titre est ignoré.
        self.assertEqual(len(self.evenements), 6)
        self.assertEqual(
            [e.titre for e in self.evenements][:5],
            ["Jamlab du Tremplin – automne 2026"] * 4 + ["Souper du monde – Mali"],
        )

    def test_champs_souper(self):
        ev = self.evenements[4]
        self.assertEqual(ev.date_debut, datetime(2026, 9, 29, 17, 0))
        self.assertIsNone(ev.date_fin)
        self.assertEqual(ev.lien, "https://tremplin16-30.com/evenements/souper-mali/")
        self.assertEqual(ev.lieu, "Salle multifonctionnelle du Tremplin")
        self.assertEqual(ev.image, "https://x/mali.png")
        self.assertEqual(ev.sous_titre, "Mardi 29 septembre 2026 - 17h")

    def test_serie_avec_date_fin_lieu_texte_et_img(self):
        ev = self.evenements[5]
        self.assertEqual(ev.date_debut, datetime(2026, 9, 9, 18, 30))
        self.assertEqual(ev.date_fin, datetime(2026, 12, 16))
        self.assertEqual(ev.lieu, "Salle multifonctionnelle du Tremplin")
        self.assertEqual(ev.image, "https://x/ruches.png")
        self.assertEqual(
            ev.lien,
            "https://tremplin16-30.com/evenements/les-ruches-dart-du-tremplin-automne-2026/",
        )

    def test_jamlab_partage_lien_et_image(self):
        liens = {e.lien for e in self.evenements[:4]}
        self.assertEqual(
            liens, {"https://tremplin16-30.com/evenements/jamlab-du-tremplin-automne-2026/"}
        )
        self.assertEqual({e.image for e in self.evenements[:4]}, {"https://x/jams.png"})

    def test_bloc_sans_date_conserve_sans_date(self):
        html = '<div class="wp-block-media-text"><h2>Sans date</h2><p class="event-data">Gratuit</p></div>'
        evs = _extraire_depuis_blocs(html, AUJOURDHUI)
        self.assertEqual(len(evs), 1)
        self.assertIsNone(evs[0].date_debut)


class TestExtraireEvenements(unittest.TestCase):
    def test_blocs_prioritaires(self):
        evs = _extraire_evenements(PAGE, 5.0, mock.Mock())
        self.assertEqual(len(evs), 6)

    def test_repli_jsonld(self):
        with self.assertLogs(tr._LOG.name, level="WARNING"):
            evs = _extraire_evenements(JSONLD, 5.0, mock.Mock())
        self.assertEqual([e.titre for e in evs], ["Repli JSON-LD"])

    def test_rien(self):
        with self.assertLogs(tr._LOG.name, level="WARNING"):
            self.assertEqual(_extraire_evenements("<p>rien</p>", 5.0, mock.Mock()), [])


class TestSource(unittest.TestCase):
    def test_bout_en_bout_hors_ligne(self):
        with mock.patch("culturecentro.sources.base.telecharger", return_value=PAGE):
            with mock.patch.object(tr, "datetime", wraps=datetime) as dt:
                dt.now.return_value = AUJOURDHUI
                evs = Tremplin1630().lister_evenements_a_venir(
                    a_partir_de=datetime(2026, 10, 1, tzinfo=timezone.utc)
                )
        # Le 17 septembre et le souper du 29 sont passés ; la série (en cours)
        # est conservée grâce à sa date de fin, puis les jams restants.
        self.assertEqual(
            [(e.titre[:6], e.date_debut.day) for e in evs],
            [("Les Ru", 9), ("Jamlab", 29), ("Jamlab", 26), ("Jamlab", 17)],
        )
        self.assertIsInstance(evs[0], Evenement)


class TestCli(unittest.TestCase):
    def test_json_stdout(self):
        with (
            mock.patch.object(
                tr.SOURCE,
                "lister_evenements_a_venir",
                return_value=[Evenement("Souper", datetime(2026, 9, 29, 17, 0))],
            ),
            mock.patch("sys.stdout", new_callable=io.StringIO) as sortie,
        ):
            self.assertEqual(main(["--format", "json"]), 0)
        self.assertEqual(json.loads(sortie.getvalue())[0]["titre"], "Souper")

    def test_erreur_reseau_retourne_1(self):
        with mock.patch.object(
            tr.SOURCE, "lister_evenements_a_venir", side_effect=requests.ConnectionError("x")
        ):
            self.assertEqual(main([]), 1)


if __name__ == "__main__":
    unittest.main()
