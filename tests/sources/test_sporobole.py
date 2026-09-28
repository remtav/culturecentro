"""Tests de la source Sporobole (liste AJAX paginée, périodes, CLI).

Hors-ligne : le réseau est simulé.
"""

from __future__ import annotations

import io
import json
import unittest
from datetime import datetime, timezone
from unittest import mock

import requests

from culturecentro.sources import sporobole as spo
from culturecentro.sources.sporobole import (
    Evenement,
    Sporobole,
    _a_des_pages_suivantes,
    _charger_page,
    _encore_actuel,
    _extraire_depuis_fragment,
    _extraire_evenements,
    _url_ajax,
    main,
)

PAGE = """
<html><body>
<div class="standish_filters_content"></div>
<script id="child-script-js-extra">
var standish_data = {"ajax_url":"https:\\/\\/sporobole.org\\/wp-admin\\/admin-ajax.php","default_status":"","btn_reset":"R\\u00e9initialiser"};
</script>
</body></html>
"""

FRAGMENT_1 = """
<div class="standish-evenements-container standish_evenements">
 <div class="standish-single-event loop-archive clickable-column">
  <div class="image" style="background-image:url('https://x/fortin.jpg');"></div>
  <div class="content"><div class="top">
    <div><div class="cpt-subtitle">Diffusion</div></div>
    <div class="title"><h3 class="entry-title"><a href="https://sporobole.org/diffusion/fortin/">Amélie Laurence Fortin | Exposition automne 2026</a></h3></div>
    <div class="date"><span>Du</span> 02 octobre 2026 <span>au</span> 27 novembre 2026</div>
  </div><a class="kt-blocks-post-readmore" href="https://sporobole.org/diffusion/fortin/">VOIR</a></div>
 </div>
 <div class="standish-single-event loop-archive clickable-column">
  <div class="image" style="background-image:url('https://x/basanta.png');"></div>
  <div class="content"><div class="top">
    <div><div class="cpt-subtitle">Diffusion</div></div>
    <div class="title"><h3 class="entry-title"><a href="https://sporobole.org/diffusion/basanta/">Adam Basanta | Lancement</a></h3></div>
    <div class="date"><span>Le 23 octobre 2026</span></div>
  </div></div>
 </div>
 <div class="standish-single-event loop-archive clickable-column">
  <div class="image"><img src="https://x/sans-date.png"></div>
  <div class="content"><div class="top">
    <div class="title"><h3 class="entry-title"><a href="https://sporobole.org/diffusion/sans-date/">Sans date</a></h3></div>
  </div></div>
 </div>
 <div class="standish-single-event"><div class="content"><p>Bloc sans titre</p></div></div>
</div>
<div class="standish-filters-pages">
  <a class="current standish-filters-page" data-page="1" href="#">1</a>
  <a class="standish-filters-page" data-page="2" href="#">2</a>
</div>
"""

FRAGMENT_2 = """
<div class="standish-evenements-container standish_evenements">
 <div class="standish-single-event">
  <div class="image" style="background-image:url('https://x/vieux.png');"></div>
  <div class="content"><div class="top">
    <div class="title"><h3 class="entry-title"><a href="https://sporobole.org/diffusion/vieux/">Vieille expo</a></h3></div>
    <div class="date"><span>Du</span> 21 mars 2026 <span>au</span> 18 avril 2026</div>
  </div></div>
 </div>
</div>
<div class="standish-filters-pages">
  <a class="standish-filters-page" data-page="1" href="#">1</a>
  <a class="current standish-filters-page" data-page="2" href="#">2</a>
  <a class="standish-filters-page" data-page="3" href="#">3</a>
</div>
"""

JSONLD = """
<script type="application/ld+json">
{"@type":"Event","name":"Repli JSON-LD","startDate":"2027-05-01T20:00:00","url":"https://x/e/"}
</script>
"""


def _reponse(contenu, statut=200):
    rep = mock.Mock()
    rep.status_code = statut
    rep.raise_for_status.return_value = None
    rep.json.return_value = {"content": contenu, "filters": ""}
    return rep


class TestUrlAjax(unittest.TestCase):
    def test_depuis_la_page(self):
        self.assertEqual(_url_ajax(PAGE), "https://sporobole.org/wp-admin/admin-ajax.php")

    def test_repli(self):
        self.assertEqual(
            _url_ajax("<p>rien</p>", "https://sporobole.org/programmation/"),
            "https://sporobole.org/wp-admin/admin-ajax.php",
        )


class TestChargerPage(unittest.TestCase):
    def test_requete_et_contenu(self):
        session = mock.Mock()
        session.post.return_value = _reponse("<p>x</p>")
        self.assertEqual(_charger_page("https://x/ajax", 2, 5.0, session), "<p>x</p>")
        appel = session.post.call_args
        self.assertEqual(appel.args[0], "https://x/ajax")
        self.assertEqual(appel.kwargs["data"]["action"], "standish_select_refresh")
        self.assertEqual(appel.kwargs["data"]["type[]"], "evenements")
        self.assertEqual(appel.kwargs["data"]["page"], "2")

    def test_reponse_sans_contenu(self):
        session = mock.Mock()
        rep = _reponse("")
        rep.json.return_value = {"filters": ""}
        session.post.return_value = rep
        self.assertIsNone(_charger_page("https://x/ajax", 1, 5.0, session))

    def test_json_invalide_ou_reseau(self):
        session = mock.Mock()
        rep = _reponse("")
        rep.json.side_effect = ValueError("pas du JSON")
        session.post.return_value = rep
        self.assertIsNone(_charger_page("https://x/ajax", 1, 5.0, session))
        session.post.side_effect = requests.ConnectionError("hors-ligne")
        self.assertIsNone(_charger_page("https://x/ajax", 1, 5.0, session))


class TestExtractionFragment(unittest.TestCase):
    def setUp(self):
        self.evenements = _extraire_depuis_fragment(FRAGMENT_1)

    def test_titres(self):
        self.assertEqual(
            [e.titre for e in self.evenements],
            [
                "Amélie Laurence Fortin | Exposition automne 2026",
                "Adam Basanta | Lancement",
                "Sans date",
            ],
        )

    def test_periode(self):
        ev = self.evenements[0]
        self.assertEqual(
            (ev.date_debut, ev.date_fin), (datetime(2026, 10, 2), datetime(2026, 11, 27))
        )
        self.assertEqual(ev.lien, "https://sporobole.org/diffusion/fortin/")
        self.assertEqual(ev.sous_titre, "Diffusion")
        self.assertEqual(ev.image, "https://x/fortin.jpg")

    def test_date_simple(self):
        ev = self.evenements[1]
        self.assertEqual((ev.date_debut, ev.date_fin), (datetime(2026, 10, 23), None))

    def test_sans_date_ni_categorie_image_img(self):
        ev = self.evenements[2]
        self.assertIsNone(ev.date_debut)
        self.assertIsNone(ev.sous_titre)
        self.assertEqual(ev.image, "https://x/sans-date.png")


class TestPagination(unittest.TestCase):
    def test_pages_suivantes(self):
        self.assertTrue(_a_des_pages_suivantes(FRAGMENT_1, 1))
        self.assertFalse(_a_des_pages_suivantes(FRAGMENT_1, 2))
        self.assertFalse(_a_des_pages_suivantes("<p>rien</p>", 1))

    def test_encore_actuel(self):
        seuil = datetime(2026, 9, 27)
        self.assertTrue(_encore_actuel(_extraire_depuis_fragment(FRAGMENT_1), seuil))
        self.assertFalse(_encore_actuel(_extraire_depuis_fragment(FRAGMENT_2), seuil))
        self.assertFalse(_encore_actuel([], seuil))
        self.assertTrue(_encore_actuel([Evenement("Sans date", None)], seuil))


class TestExtraireEvenements(unittest.TestCase):
    def _session(self, *fragments):
        session = mock.Mock()
        session.post.side_effect = [_reponse(f) for f in fragments]
        return session

    def test_arret_quand_la_page_devient_ancienne(self):
        session = self._session(FRAGMENT_1, FRAGMENT_2, FRAGMENT_2)
        with mock.patch.object(spo, "datetime", wraps=datetime) as dt:
            dt.now.return_value = datetime(2026, 9, 28)
            evs = _extraire_evenements(PAGE, 5.0, session)
        # Page 1 encore actuelle → page 2 chargée ; page 2 ancienne → arrêt.
        self.assertEqual(session.post.call_count, 2)
        self.assertEqual(len(evs), 4)

    def test_arret_sans_page_suivante(self):
        session = self._session(FRAGMENT_1.replace('data-page="2"', 'data-page="1"'))
        evs = _extraire_evenements(PAGE, 5.0, session)
        self.assertEqual(session.post.call_count, 1)
        self.assertEqual(len(evs), 3)

    def test_page_suivante_en_echec_conserve_la_premiere(self):
        session = mock.Mock()
        session.post.side_effect = [_reponse(FRAGMENT_1), requests.ConnectionError("x")]
        with mock.patch.object(spo, "datetime", wraps=datetime) as dt:
            dt.now.return_value = datetime(2026, 9, 28)
            with self.assertLogs(spo._LOG.name, level="WARNING"):
                evs = _extraire_evenements(PAGE, 5.0, session)
        self.assertEqual(len(evs), 3)

    def test_repli_jsonld(self):
        session = mock.Mock()
        session.post.side_effect = requests.ConnectionError("x")
        with self.assertLogs(spo._LOG.name, level="WARNING"):
            evs = _extraire_evenements(JSONLD, 5.0, session)
        self.assertEqual([e.titre for e in evs], ["Repli JSON-LD"])

    def test_rien(self):
        session = self._session("<p>vide</p>")
        with self.assertLogs(spo._LOG.name, level="WARNING"):
            self.assertEqual(_extraire_evenements("<p>rien</p>", 5.0, session), [])


class TestSource(unittest.TestCase):
    def test_bout_en_bout_hors_ligne(self):
        session = mock.Mock()
        session.post.return_value = _reponse(FRAGMENT_1.replace('data-page="2"', 'data-page="1"'))
        with (
            mock.patch("culturecentro.sources.base.creer_session", return_value=session),
            mock.patch("culturecentro.sources.base.telecharger", return_value=PAGE),
        ):
            evs = Sporobole().lister_evenements_a_venir(
                a_partir_de=datetime(2026, 11, 1, tzinfo=timezone.utc)
            )
        # Au 1er novembre : l'expo (fin 27 novembre) est en cours, le lancement
        # du 23 octobre est passé, l'événement sans date ferme la liste.
        self.assertEqual([e.titre[:6] for e in evs], ["Amélie", "Sans d"])


class TestCli(unittest.TestCase):
    def test_json_stdout(self):
        with (
            mock.patch.object(
                spo.SOURCE,
                "lister_evenements_a_venir",
                return_value=[
                    Evenement("Expo", datetime(2026, 10, 2), date_fin=datetime(2026, 11, 27))
                ],
            ),
            mock.patch("sys.stdout", new_callable=io.StringIO) as sortie,
        ):
            self.assertEqual(main(["--format", "json"]), 0)
        self.assertEqual(json.loads(sortie.getvalue())[0]["titre"], "Expo")

    def test_erreur_reseau_retourne_1(self):
        with mock.patch.object(
            spo.SOURCE, "lister_evenements_a_venir", side_effect=requests.ConnectionError("x")
        ):
            self.assertEqual(main([]), 1)


if __name__ == "__main__":
    unittest.main()
