"""Tests de la source Maison des arts de la parole (EventON : page + AJAX, CLI).

Hors-ligne : le réseau est simulé.
"""

from __future__ import annotations

import io
import json
import unittest
from datetime import datetime, timezone
from unittest import mock

import requests

from culturecentro.sources import maisondesartsdelaparole as madlp
from culturecentro.sources.maisondesartsdelaparole import (
    Evenement,
    MaisonDesArtsDeLaParole,
    _charger_mois_suivant,
    _construire_requete,
    _extraire_depuis_eventon,
    _extraire_evenements,
    _lire_calendrier,
    main,
)

# Page de programmation réduite : calendrier EventON (mois courant vide),
# filtres actifs (saison) et script portant l'URL AJAX + le nonce.
PAGE = """
<html><body>
<div id="evcal_calendar_435" class="ajde_evcal_calendar boxy">
  <div class="evo-data" data-cmonth="9" data-cyear="2026" data-sort_by="sort_date"
       data-filters_on="true" data-runajax="1"></div>
  <div class="calendar_header" id="evcal_head">
    <div class="cal_arguments" data-event_order="ASC" data-hide_past="no" data-lang="L1"
         data-show_limit="yes" data-tiles="yes" data-s="" style="display:none"></div>
  </div>
  <div class="eventon_sorting_section">
    <div class="eventon_filter_line">
      <div class="eventon_filter" data-filter_field="event_past_future" data-filter_type="custom"
           data-filter_val="all"></div>
      <div class="eventon_filter" data-filter_field="event_type" data-filter_type="tax"
           data-filter_val="173" data-fl_o="IN"></div>
      <div class="eventon_filter" data-filter_field="event_type_2" data-filter_type="tax"
           data-filter_val="9" data-fl_o="NOT"></div>
    </div>
  </div>
  <div id="evcal_list" class="eventon_events_list">
    <div class="eventon_list_event"><p class="no_events">Aucun événement</p></div>
  </div>
</div>
<script id="evcal_ajax_handle-js-extra">
var the_ajax_script = {"ajaxurl":"https://maisondesartsdelaparole.com/wp-admin/admin-ajax.php","postnonce":"b1a93ea530"};
</script>
</body></html>
"""

FRAGMENT_OCTOBRE = """
<div class="eventon_list_event evo_eventtop event hasbgimg" data-event_id="25989" data-time="1792090800-1792101600" itemscope itemtype="http://schema.org/Event">
  <div class="evo_boxtop" style="background-image: url(https://x/bal-fond.png);"></div>
  <div class="evo_event_schema" style="display:none">
    <a href="https://maisondesartsdelaparole.com/events/bal-chante-5/" itemprop="url"></a>
    <span itemprop="name">Bal chanté</span>
    <meta itemprop="image" content="https://x/bal.png"/>
    <meta itemprop="startDate" content="2026-10-15T19:00"/>
    <meta itemprop="endDate" content="2026-10-15T22:00"/>
    <item itemprop="location" itemscope itemtype="http://schema.org/Place">
      <span itemprop="name">Café 440</span>
    </item>
  </div>
  <p class="desc_trig_outter"><a class="desc_trig evcal_list_a" href="#">
    <span class="evcal_desc evo_info" data-location_name="Café 440">
      <span class="evcal_desc2 evcal_event_title" itemprop="name">Bal chanté</span>
      <span class="evo_below_title"><span class="evcal_event_subtitle">avec Toumani Kouyaté</span></span>
      <span class="evcal_desc_info"><em class="evcal_location"><em class="event_location_name">Café 440</em></em></span>
    </span>
  </a></p>
</div>
<div class="eventon_list_event" data-time="1792170000-1792177200">
  <p class="desc_trig_outter"><a class="desc_trig evcal_list_a" href="https://x/5a7/">
    <span class="evcal_desc evo_info" data-location_name="Café du Couvent">
      <span class="evcal_desc2 evcal_event_title">5@7</span>
    </span>
  </a></p>
  <div class="event_description"><img src="https://x/5a7.png"></div>
</div>
<div class="eventon_list_event" data-time="1792256400-1792260000">
  <div class="evo_event_schema" style="display:none">
    <a href="https://x/richmond/" itemprop="url"></a><span itemprop="name">En région</span>
    <meta itemprop="startDate" content="2026-10-17T20:00"/>
    <item itemprop="location"><span itemprop="name">Centre d'art de Richmond</span>
      <span itemprop="address"><item itemprop="streetAddress">1010 rue Principale Nord, Richmond</item></span></item>
  </div>
  <p class="desc_trig_outter"><a class="desc_trig evcal_list_a" href="#">
    <span class="evcal_desc evo_info" data-location_name="Centre d'art de Richmond" data-location_address="1010 rue Principale Nord, Richmond">
      <span class="evcal_desc2 evcal_event_title">En région</span>
    </span>
  </a></p>
</div>
<div class="eventon_list_event"><p class="no_events">Aucun événement</p></div>
"""

JSONLD = """
<script type="application/ld+json">
{"@type":"Event","name":"Repli JSON-LD","startDate":"2027-05-01T20:00:00","url":"https://x/e/"}
</script>
"""


def _reponse_json(donnees, statut=200):
    rep = mock.Mock()
    rep.status_code = statut
    rep.json.return_value = donnees
    rep.raise_for_status.return_value = None
    return rep


def _reponse_mois(mois, annee, contenu, total=None):
    return _reponse_json(
        {
            "status": "GOOD",
            "month": mois,
            "year": annee,
            "total_events": total if total is not None else 0,
            "content": contenu,
        }
    )


class TestLireCalendrier(unittest.TestCase):
    def setUp(self):
        self.cal = _lire_calendrier(PAGE)

    def test_url_nonce_et_mois(self):
        self.assertIsNotNone(self.cal)
        self.assertEqual(
            self.cal.url_ajax, "https://maisondesartsdelaparole.com/wp-admin/admin-ajax.php"
        )
        self.assertEqual(self.cal.nonce, "b1a93ea530")
        self.assertEqual((self.cal.mois, self.cal.annee), (9, 2026))

    def test_shortcode_sans_valeurs_vides(self):
        self.assertEqual(self.cal.shortcode["event_order"], "ASC")
        self.assertNotIn("s", self.cal.shortcode)  # data-s="" ignoré, comme dans le JS

    def test_filtres_actifs_seulement(self):
        self.assertEqual(
            self.cal.filtres,
            [
                {"filter_type": "tax", "filter_name": "event_type", "filter_val": "173"},
                {
                    "filter_type": "tax",
                    "filter_name": "event_type_2",
                    "filter_val": "9",
                    "filter_op": "NOT IN",
                },
            ],
        )

    def test_page_sans_calendrier(self):
        self.assertIsNone(_lire_calendrier("<p>rien</p>"))

    def test_page_sans_nonce(self):
        sans_script = PAGE.split("<script")[0]
        self.assertIsNone(_lire_calendrier(sans_script))

    def test_mois_illisible(self):
        self.assertIsNone(_lire_calendrier(PAGE.replace('data-cmonth="9"', 'data-cmonth="x"')))


class TestConstruireRequete(unittest.TestCase):
    def test_format_eventon(self):
        cal = _lire_calendrier(PAGE)
        donnees = _construire_requete(cal, "next")
        self.assertEqual(donnees["action"], "the_ajax_hook")
        self.assertEqual(donnees["direction"], "next")
        self.assertEqual(donnees["nonce"], "b1a93ea530")
        self.assertEqual(donnees["sort_by"], "sort_date")
        self.assertEqual(donnees["shortcode[event_order]"], "ASC")
        self.assertEqual(donnees["evodata[cmonth]"], "9")
        self.assertEqual(donnees["evodata[cyear]"], "2026")
        self.assertEqual(donnees["filters[0][filter_name]"], "event_type")
        self.assertEqual(donnees["filters[1][filter_op]"], "NOT IN")


class TestExtractionEventon(unittest.TestCase):
    def setUp(self):
        self.evenements = _extraire_depuis_eventon(FRAGMENT_OCTOBRE)

    def test_nombre_et_titres(self):
        # « En région » (Richmond) est hors du centre-ville : écarté.
        self.assertEqual([e.titre for e in self.evenements], ["Bal chanté", "5@7"])

    def test_champs_complets(self):
        ev = self.evenements[0]
        self.assertEqual(ev.date_debut, datetime(2026, 10, 15, 19, 0))
        self.assertEqual(ev.date_fin, datetime(2026, 10, 15, 22, 0))
        self.assertEqual(ev.lien, "https://maisondesartsdelaparole.com/events/bal-chante-5/")
        self.assertEqual(ev.sous_titre, "avec Toumani Kouyaté")
        self.assertEqual(ev.lieu, "Café 440")
        self.assertEqual(ev.image, "https://x/bal.png")  # meta itemprop=image prioritaire

    def test_replis_data_time_lien_lieu_image(self):
        ev = self.evenements[1]
        # data-time (unix, heure locale) : 1792170000 = 2026-10-16 17:00.
        self.assertEqual(ev.date_debut, datetime(2026, 10, 16, 17, 0))
        self.assertEqual(ev.date_fin, datetime(2026, 10, 16, 19, 0))
        self.assertEqual(ev.lien, "https://x/5a7/")
        self.assertEqual(ev.lieu, "Café du Couvent")
        self.assertEqual(ev.image, "https://x/5a7.png")
        self.assertIsNone(ev.sous_titre)

    def test_bloc_sans_evenement_ignore(self):
        self.assertEqual(
            _extraire_depuis_eventon(
                '<div class="eventon_list_event"><p class="no_events">Aucun</p></div>'
            ),
            [],
        )


class TestChargerMoisSuivant(unittest.TestCase):
    def test_succes_avance_le_mois(self):
        cal = _lire_calendrier(PAGE)
        session = mock.Mock()
        session.post.return_value = _reponse_mois(10, 2026, "<p>x</p>")
        self.assertEqual(_charger_mois_suivant(cal, 5.0, session), "<p>x</p>")
        self.assertEqual((cal.mois, cal.annee), (10, 2026))
        appel = session.post.call_args
        self.assertEqual(appel.args[0], cal.url_ajax)
        self.assertEqual(appel.kwargs["data"]["evodata[cmonth]"], "9")

    def test_sans_mois_renvoye_avance_seul(self):
        cal = _lire_calendrier(PAGE)
        cal.mois, cal.annee = 12, 2026
        session = mock.Mock()
        session.post.return_value = _reponse_json({"status": "GOOD", "content": ""})
        self.assertEqual(_charger_mois_suivant(cal, 5.0, session), "")
        self.assertEqual((cal.mois, cal.annee), (1, 2027))

    def test_statut_inattendu(self):
        cal = _lire_calendrier(PAGE)
        session = mock.Mock()
        session.post.return_value = _reponse_json({"status": "Need updated"})
        self.assertIsNone(_charger_mois_suivant(cal, 5.0, session))

    def test_json_invalide(self):
        cal = _lire_calendrier(PAGE)
        rep = _reponse_json({})
        rep.json.side_effect = ValueError("pas du JSON")
        session = mock.Mock()
        session.post.return_value = rep
        self.assertIsNone(_charger_mois_suivant(cal, 5.0, session))

    def test_exception_reseau(self):
        cal = _lire_calendrier(PAGE)
        session = mock.Mock()
        session.post.side_effect = requests.ConnectionError("hors-ligne")
        self.assertIsNone(_charger_mois_suivant(cal, 5.0, session))


class TestExtraireEvenements(unittest.TestCase):
    def test_mois_courant_puis_suivants(self):
        session = mock.Mock()
        # Octobre (2 événements), puis 11 mois vides.
        session.post.side_effect = [_reponse_mois(10, 2026, FRAGMENT_OCTOBRE, 2)] + [
            _reponse_mois(m, a, "")
            for m, a in [(11, 2026), (12, 2026)] + [(m, 2027) for m in range(1, 10)]
        ]
        evs = _extraire_evenements(PAGE, 5.0, session)
        self.assertEqual([e.titre for e in evs], ["Bal chanté", "5@7"])
        self.assertEqual(session.post.call_count, madlp.NOMBRE_DE_MOIS)

    def test_arret_si_ajax_echoue(self):
        session = mock.Mock()
        session.post.side_effect = [
            _reponse_mois(10, 2026, FRAGMENT_OCTOBRE, 2),
            requests.ConnectionError("hors-ligne"),
        ]
        with self.assertLogs(madlp._LOG.name, level="WARNING"):
            evs = _extraire_evenements(PAGE, 5.0, session)
        self.assertEqual(len(evs), 2)
        self.assertEqual(session.post.call_count, 2)

    def test_repli_jsonld_sans_calendrier(self):
        with self.assertLogs(madlp._LOG.name, level="WARNING"):
            evs = _extraire_evenements(JSONLD, 5.0, mock.Mock())
        self.assertEqual([e.titre for e in evs], ["Repli JSON-LD"])

    def test_rien(self):
        with self.assertLogs(madlp._LOG.name, level="WARNING"):
            self.assertEqual(_extraire_evenements("<p>rien</p>", 5.0, mock.Mock()), [])


class TestSource(unittest.TestCase):
    def test_bout_en_bout_hors_ligne(self):
        session = mock.Mock()
        session.post.return_value = _reponse_mois(10, 2026, FRAGMENT_OCTOBRE, 2)
        with (
            mock.patch("culturecentro.sources.base.creer_session", return_value=session),
            mock.patch("culturecentro.sources.base.telecharger", return_value=PAGE),
        ):
            evs = MaisonDesArtsDeLaParole().lister_evenements_a_venir(
                a_partir_de=datetime(2026, 10, 1, tzinfo=timezone.utc)
            )
        # Le même mois est renvoyé 12 fois par le faux réseau : dédupliqué.
        self.assertEqual([e.titre for e in evs], ["Bal chanté", "5@7"])
        self.assertIsInstance(evs[0], Evenement)


class TestCli(unittest.TestCase):
    def _executer(self, argv):
        with (
            mock.patch.object(
                madlp.SOURCE,
                "lister_evenements_a_venir",
                return_value=[Evenement("Bal chanté", datetime(2026, 10, 15, 19, 0))],
            ),
            mock.patch("sys.stdout", new_callable=io.StringIO) as sortie,
        ):
            code = main(argv)
        return code, sortie.getvalue()

    def test_json_stdout(self):
        code, sortie = self._executer(["--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(sortie)[0]["titre"], "Bal chanté")

    def test_erreur_reseau_retourne_1(self):
        with mock.patch.object(
            madlp.SOURCE,
            "lister_evenements_a_venir",
            side_effect=requests.ConnectionError("hors-ligne"),
        ):
            self.assertEqual(main([]), 1)


if __name__ == "__main__":
    unittest.main()
