"""Tests de la source La Petite Boîte Noire (découverte + extraction, CLI).

Hors-ligne : le réseau est simulé.
"""

from __future__ import annotations

import io
import json
import unittest
from datetime import datetime, timezone
from unittest import mock

import requests

from culturecentro.sources import lapetiteboitenoire as lpbn
from culturecentro.sources.lapetiteboitenoire import (
    URL_BILLETTERIE_DEFAUT,
    Evenement,
    LaPetiteBoiteNoire,
    _extraire_depuis_lepointdevente,
    _extraire_evenements,
    _trouver_url_billetterie,
    main,
    normaliser_lieu,
)

FRAGMENT_LISTE = """
<div id="events-list" class="feature feature-grid">
  <div class="feature-row">
    <div class="feature-col is-small" data-tpos-event="529998" style="cursor: pointer">
      <article class="feature-canvas has-tag">
        <div class="feature-content">
          <img itemprop="image" src="https://tpos.s3.amazonaws.com/events/PBN/26/09/30/001/pbn260930001-1152x648-fr.png" alt="Juste Miben">
          <h3 class="feature-title"><div class="tag-attendance-offline" title="Événement en personne"></div>Juste Miben (supplémentaire)</h3>
          <div class="feature-date">30 septembre 2026, 20h00</div>
          <div class="feature-city">La Petite boite noire, Sherbrooke, QC</div>
          <div class="feature-tag">Complet</div>
        </div>
      </article>
    </div>
    <div class="feature-col is-small tpos-add-to-cart" data-tpos-event="541978" style="cursor: pointer">
      <article class="feature-canvas has-button show-queue">
        <div class="feature-content">
          <h3 class="feature-title">Les Frayeurs d&#039;ailleurs</h3>
          <div class="feature-date">1er octobre 2026, 20h00</div>
          <div class="feature-city">La Petite boite noire, Sherbrooke, QC</div>
        </div>
      </article>
    </div>
  </div>
</div>
"""

JSONLD = """
<script type="application/ld+json">
{"@type":"Event","name":"Repli JSON-LD","startDate":"2027-05-01T20:00:00","url":"https://x/e/"}
</script>
"""

URL_BASE = "https://lepointdevente.com/billets/programmationavenir"


class TestTrouverUrlBilletterie(unittest.TestCase):
    def test_lien_direct(self):
        page = (
            '<a href="https://lepointdevente.com/billets/programmationavenir">'
            "Programmation complète</a>"
        )
        self.assertEqual(_trouver_url_billetterie(page, 5.0, None), URL_BASE)

    def test_lien_avec_parametres_nettoye(self):
        page = '<a href="https://lepointdevente.com/billets/programmationavenir?lang=fr">x</a>'
        self.assertEqual(_trouver_url_billetterie(page, 5.0, None), URL_BASE)

    def test_repli_sur_defaut(self):
        self.assertEqual(
            _trouver_url_billetterie("<p>rien ici</p>", 5.0, None),
            URL_BILLETTERIE_DEFAUT,
        )

    def test_decouverte_via_widget_js(self):
        page = '<script src="https://lepointdevente.com/plugins/widget.js?group=6603"></script>'
        script = "document.write('<iframe src=\"https://lepointdevente.com/billets/pbn?a=1\">')"
        with mock.patch.object(lpbn, "telecharger", return_value=script):
            url = _trouver_url_billetterie(page, 5.0, mock.Mock())
        self.assertEqual(url, "https://lepointdevente.com/billets/pbn")

    def test_widget_js_injoignable_repli_defaut(self):
        page = '<script src="https://lepointdevente.com/plugins/widget.js"></script>'
        with mock.patch.object(lpbn, "telecharger", side_effect=requests.RequestException("x")):
            url = _trouver_url_billetterie(page, 5.0, mock.Mock())
        self.assertEqual(url, URL_BILLETTERIE_DEFAUT)


class TestExtractionLepointdevente(unittest.TestCase):
    def setUp(self):
        self.evenements = _extraire_depuis_lepointdevente(FRAGMENT_LISTE, URL_BASE)

    def test_nombre_et_ordre(self):
        self.assertEqual(
            [e.titre for e in self.evenements],
            ["Juste Miben (supplémentaire)", "Les Frayeurs d'ailleurs"],
        )

    def test_champs_du_premier(self):
        ev = self.evenements[0]
        self.assertEqual(ev.date_debut, datetime(2026, 9, 30, 20, 0))
        self.assertEqual(ev.lien, "https://lepointdevente.com/billets/programmationavenir/529998")
        self.assertEqual(ev.lieu, "La Petite Boîte Noire")  # ville retirée, graphie unifiée
        self.assertEqual(
            ev.image,
            "https://tpos.s3.amazonaws.com/events/PBN/26/09/30/001/pbn260930001-1152x648-fr.png",
        )
        self.assertIsNone(ev.sous_titre)  # LPBN n'expose pas de sous-titre

    def test_lien_du_second(self):
        self.assertEqual(
            self.evenements[1].lien,
            "https://lepointdevente.com/billets/programmationavenir/541978",
        )

    def test_image_absente_vaut_none(self):
        self.assertIsNone(self.evenements[1].image)

    def test_image_repli_fond_css(self):
        fragment = """
        <div class="feature-col" data-tpos-event="1">
          <div class="feature-canvas" style="background-image:url('https://x/fond.png')">
            <h3 class="feature-title">Fond</h3>
          </div>
        </div>
        """
        evs = _extraire_depuis_lepointdevente(fragment, URL_BASE)
        self.assertEqual(evs[0].image, "https://x/fond.png")


class TestNormaliserLieu(unittest.TestCase):
    """Le lieu Lepointdevente varie en casse/accents et porte un suffixe de ville."""

    def test_variantes_ramenees_au_nom_canonique(self):
        for variante in (
            "La Petite boite noire, Sherbrooke, QC",
            "La Petite Boite Noire, Sherbrooke, QC",
            "La Petite Boîte Noire, Sherbrooke, QC",
            "LA PETITE BOÎTE NOIRE , Sherbrooke",
            "  La  Petite   boite noire  ",
            "La Petite Boîte Noire",
        ):
            with self.subTest(variante=variante):
                self.assertEqual(normaliser_lieu(variante), "La Petite Boîte Noire")

    def test_autre_lieu_conserve_sans_ville(self):
        self.assertEqual(normaliser_lieu("Lieu à confirmer"), "Lieu à confirmer")
        self.assertEqual(normaliser_lieu("Salle du Parvis, Sherbrooke, QC"), "Salle du Parvis")

    def test_vide_vaut_none(self):
        self.assertIsNone(normaliser_lieu(None))
        self.assertIsNone(normaliser_lieu(""))
        self.assertIsNone(normaliser_lieu("  , Sherbrooke, QC"))

    def test_nom_canonique_est_celui_de_la_source(self):
        self.assertEqual(normaliser_lieu("la petite boite noire"), LaPetiteBoiteNoire.nom)


class TestExtraireEvenements(unittest.TestCase):
    def test_source_principale(self):
        page = '<a href="https://lepointdevente.com/billets/programmationavenir">x</a>'
        with mock.patch.object(lpbn, "telecharger", return_value=FRAGMENT_LISTE):
            evs = _extraire_evenements(page, 5.0, mock.Mock())
        self.assertEqual(len(evs), 2)

    def test_repli_jsonld_si_liste_vide(self):
        page = '<a href="https://lepointdevente.com/billets/programmationavenir">x</a>'
        # La liste téléchargée ne contient aucune carte -> repli sur le JSON-LD
        # de la page « evenements » d'origine.
        page_avec_jsonld = page + JSONLD
        with mock.patch.object(lpbn, "telecharger", return_value="<html></html>"):
            with self.assertLogs(lpbn._LOG.name, level="WARNING"):
                evs = _extraire_evenements(page_avec_jsonld, 5.0, mock.Mock())
        self.assertEqual([e.titre for e in evs], ["Repli JSON-LD"])

    def test_telechargement_liste_echoue(self):
        page = '<a href="https://lepointdevente.com/billets/programmationavenir">x</a>' + JSONLD
        with mock.patch.object(lpbn, "telecharger", side_effect=requests.RequestException("boom")):
            with self.assertLogs(lpbn._LOG.name, level="WARNING"):
                evs = _extraire_evenements(page, 5.0, mock.Mock())
        self.assertEqual([e.titre for e in evs], ["Repli JSON-LD"])

    def test_aucun_evenement(self):
        with mock.patch.object(lpbn, "telecharger", return_value="<html></html>"):
            with self.assertLogs(lpbn._LOG.name, level="WARNING"):
                evs = _extraire_evenements("<p>rien</p>", 5.0, mock.Mock())
        self.assertEqual(evs, [])


class TestListerEvenements(unittest.TestCase):
    def test_bout_en_bout_hors_ligne(self):
        page = '<a href="https://lepointdevente.com/billets/programmationavenir">x</a>'
        seuil = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with (
            mock.patch("culturecentro.sources.base.telecharger", return_value=page),
            mock.patch.object(lpbn, "telecharger", return_value=FRAGMENT_LISTE),
        ):
            evs = lpbn.lister_evenements_a_venir(a_partir_de=seuil)
        self.assertEqual(
            [e.titre for e in evs],
            ["Juste Miben (supplémentaire)", "Les Frayeurs d'ailleurs"],
        )


class TestCli(unittest.TestCase):
    def test_json_stdout(self):
        evenements = [Evenement("Juste Miben", datetime(2026, 9, 30, 20, 0))]
        sortie = io.StringIO()
        with mock.patch.object(
            LaPetiteBoiteNoire, "lister_evenements_a_venir", return_value=evenements
        ):
            with mock.patch("sys.stdout", sortie):
                code = main(["--format", "json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(sortie.getvalue())[0]["titre"], "Juste Miben")


if __name__ == "__main__":
    unittest.main()
