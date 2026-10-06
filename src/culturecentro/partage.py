"""Pages de partage : un aperçu riche pour chaque événement.

Les réseaux sociaux (Facebook, Messenger, WhatsApp…) n'exécutent pas le
JavaScript et ignorent la requête des liens qu'ils prévisualisent : pour qu'un
lien partagé affiche l'affiche, le titre et la date d'un événement, il faut une
page HTML statique qui porte les balises Open Graph.

:func:`generer_pages` écrit une telle page par événement du feed
(``e/<id>/index.html``). Elle renvoie aussitôt le visiteur vers l'agenda
(``?e=<id>``), où l'événement est mis en évidence. Les identifiants sont
attribués par :func:`attribuer_identifiants` puis reportés dans le feed, que la
page publique lit pour construire ses liens de partage.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import unicodedata
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

#: Image d'aperçu quand l'événement n'a pas d'affiche (relative à la racine du site).
IMAGE_DEFAUT = "img/partage.png"

_JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_MOIS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_HEURE = re.compile(r"T(\d{2}):(\d{2})")
_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_URL = re.compile(r"https?://", re.IGNORECASE)


def slugifier(texte: str) -> str:
    """« Les Belles-Sœurs » → ``les-belles-soeurs`` (même règle que la page publique)."""
    decompose = unicodedata.normalize("NFD", texte)
    sans_accents = "".join(c for c in decompose if not "̀" <= c <= "ͯ")
    minuscules = sans_accents.lower().replace("œ", "oe").replace("æ", "ae")
    return re.sub(r"[^a-z0-9]+", "-", minuscules).strip("-")


def _jour(ev: dict[str, Any]) -> str | None:
    """Jour de début ``AAAA-MM-JJ``, ou ``None`` (la page publique écarte ces événements)."""
    debut = str(ev.get("date_debut") or "")[:10]
    return debut if _DATE.fullmatch(debut) else None


def _heure(iso: str) -> str:
    """``HHMM`` d'un horodatage ISO ; vide à minuit (heure inconnue, comme à l'affichage)."""
    m = _HEURE.search(iso)
    return m.group(1) + m.group(2) if m and m.group(0) != "T00:00" else ""


def attribuer_identifiants(feed: list[dict[str, Any]]) -> None:
    """Renseigne ``id`` pour chaque événement daté du feed, dans l'ordre du feed.

    ``<titre en slug, 60 caractères au plus>-<AAAA-MM-JJ>`` ; un même titre deux
    fois le même jour est distingué par l'heure (``-1930``), sinon par ``-2``,
    ``-3``… C'est la règle de la page publique (``assignerIds``) : les liens
    ``?e=<id>`` déjà partagés restent valides.
    """
    vus: set[str] = set()
    for ev in feed:
        jour = _jour(ev)
        if jour is None:
            ev.pop("id", None)
            continue
        titre = slugifier(str(ev.get("titre") or "Sans titre"))[:60].rstrip("-") or "evenement"
        ident = f"{titre}-{jour}"
        if ident in vus:
            heure = _heure(str(ev.get("date_debut") or ""))
            if heure and f"{ident}-{heure}" not in vus:
                ident += f"-{heure}"
            else:
                n = 2
                while f"{ident}-{n}" in vus:
                    n += 1
                ident += f"-{n}"
        vus.add(ident)
        ev["id"] = ident


def _jour_fr(d: date) -> str:
    return ("1er" if d.day == 1 else str(d.day)) + " " + _MOIS[d.month - 1]


def quand(ev: dict[str, Any]) -> str:
    """« Samedi 17 octobre · 20 h 00 », « Du 21 au 22 octobre »… ; vide sans date."""
    jour = _jour(ev)
    if jour is None:
        return ""
    fin_txt = str(ev.get("date_fin") or "")[:10]
    try:
        debut = date.fromisoformat(jour)
        fin = date.fromisoformat(fin_txt) if _DATE.fullmatch(fin_txt) else None
    except ValueError:
        return ""
    if fin is not None and fin > debut:
        meme_mois = (debut.year, debut.month) == (fin.year, fin.month)
        du = _jour_fr(debut).split()[0] if meme_mois else _jour_fr(debut)
        return f"Du {du} au {_jour_fr(fin)}"
    texte = f"{_JOURS[debut.weekday()].capitalize()} {_jour_fr(debut)}"
    heure = _heure(str(ev.get("date_debut")))
    return texte + (f" · {heure[:2]} h {heure[2:]}" if heure else "")


def description(ev: dict[str, Any]) -> str:
    """Date, partenaire, lieu s'il diffère, puis le sous-titre."""
    partenaire = str(ev.get("partenaire") or ev.get("lieu") or "")
    lieu = str(ev.get("lieu") or "")
    morceaux = [quand(ev), partenaire]
    if lieu and lieu != partenaire:
        morceaux.append(lieu)
    texte = " · ".join(m for m in morceaux if m)
    sous_titre = str(ev.get("sous_titre") or "").strip()
    if sous_titre:
        texte += f" — {sous_titre}" if texte else sous_titre
    return texte if len(texte) <= 200 else texte[:199].rstrip() + "…"


def _page(ev: dict[str, Any], ident: str, base: str) -> str:
    def e(valeur: str) -> str:
        return html.escape(valeur, quote=True)

    titre = str(ev.get("titre") or "Sans titre")
    desc = description(ev)
    url = f"{base}e/{ident}/"
    cible = f"../../?e={ident}"
    image = str(ev.get("image") or "").strip()
    if _URL.match(image):
        balises_image = f'<meta property="og:image" content="{e(image)}">'
    else:
        balises_image = (
            f'<meta property="og:image" content="{e(base + IMAGE_DEFAUT)}">\n'
            '<meta property="og:image:width" content="1200">\n'
            '<meta property="og:image:height" content="630">'
        )
    lien = str(ev.get("lien") or "").strip()
    partenaire = str(ev.get("partenaire") or ev.get("lieu") or "le partenaire")
    lien_partenaire = (
        f'<p><a href="{e(lien)}">Détails et billets : {e(partenaire)}</a></p>\n'
        if _URL.match(lien)
        else ""
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titre)} · Culture Centro</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Culture Centro Sherbrooke">
<meta property="og:locale" content="fr_CA">
<meta property="og:url" content="{e(url)}">
<meta property="og:title" content="{e(titre)}">
<meta property="og:description" content="{e(desc)}">
{balises_image}
<meta name="twitter:card" content="summary_large_image">
<script>location.replace({json.dumps(cible)});</script>
<style>
  body {{ margin: 0; font-family: system-ui, sans-serif; background: #FBF7F0; color: #16162E; }}
  main {{ max-width: 34rem; margin: 0 auto; padding: 3rem 1.25rem; line-height: 1.5; }}
  .marque {{ font-size: .8rem; letter-spacing: .14em; text-transform: uppercase; color: #6E6E85; }}
  a {{ color: #8A5512; font-weight: 600; }}
</style>
</head>
<body>
<main>
<p class="marque">Culture Centro · centre-ville de Sherbrooke</p>
<h1>{e(titre)}</h1>
<p>{e(desc)}</p>
<p><a href="{e(cible)}">Voir dans l'agenda Culture Centro</a></p>
{lien_partenaire}</main>
</body>
</html>
"""


def _page_404(base: str) -> str:
    chemin = urlsplit(base).path or "/"
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page introuvable · Culture Centro</title>
<script>
  // Lien de partage d'un événement retiré du feed (passé, renommé) : retour à
  // l'agenda, qui affiche le bandeau « n'est plus à l'affiche ».
  var m = location.pathname.match(/\\/e\\/([a-z0-9-]+)/);
  location.replace({json.dumps(chemin)} + (m ? "?e=" + m[1] : ""));
</script>
</head>
<body>
<p><a href="{html.escape(chemin, quote=True)}">Retour à l'agenda Culture Centro</a></p>
</body>
</html>
"""


def generer_pages(feed: Sequence[dict[str, Any]], dossier: str | Path, url_base: str) -> int:
    """Écrit ``<dossier>/e/<id>/index.html`` pour chaque événement identifié, et ``404.html``.

    ``url_base`` est l'adresse publique du site (``og:url`` et ``og:image``
    doivent être absolues). Les pages d'un déploiement précédent sont d'abord
    supprimées ; un lien vers un événement disparu tombe sur ``404.html``, qui
    renvoie vers l'agenda. Renvoie le nombre de pages écrites.
    """
    if not _URL.match(url_base):
        raise ValueError(f"Adresse du site invalide (http:// ou https:// attendu) : {url_base!r}")
    base = url_base.rstrip("/") + "/"
    dossier = Path(dossier)
    racine = dossier / "e"
    if racine.exists():
        shutil.rmtree(racine)
    ecrites = 0
    for ev in feed:
        ident = ev.get("id")
        if not isinstance(ident, str) or not _ID.fullmatch(ident):
            continue
        page = racine / ident / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(_page(ev, ident, base), encoding="utf-8")
        ecrites += 1
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "404.html").write_text(_page_404(base), encoding="utf-8")
    return ecrites
