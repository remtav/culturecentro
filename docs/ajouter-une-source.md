# Ajouter une salle

Brancher une nouvelle salle se résume à écrire sa logique d'extraction et à
l'inscrire au registre. La CLI, l'agrégation et le feed la prennent ensuite en
charge automatiquement.

## 1. Créer le module de la source

Dans `src/culturecentro/sources/`, créez `ma_salle.py` :

```python
"""Source d'événements : Ma Salle."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import requests
from bs4 import BeautifulSoup

from culturecentro import cli
from culturecentro.dates import parse_date_fr
from culturecentro.exporters import exporter_csv, exporter_json  # noqa: F401 (API publique)
from culturecentro.models import Evenement
from culturecentro.scraping import attribut
from culturecentro.sources.base import Source

_LOG = logging.getLogger(__name__)

URL_PROGRAMMATION = "https://exemple.com/programmation"


def _extraire_evenements(html: str, timeout: float, session: requests.Session) -> list[Evenement]:
    soup = BeautifulSoup(html, "html.parser")
    evenements: list[Evenement] = []
    for bloc in soup.select(".un-evenement"):
        titre_el = bloc.select_one(".titre")
        titre = titre_el.get_text(" ", strip=True) if titre_el else None
        if not titre:
            continue
        date_el = bloc.select_one(".date")
        lien_el = bloc.select_one("a")
        evenements.append(
            Evenement(
                titre=titre,
                date_debut=parse_date_fr(date_el.get_text(" ", strip=True)) if date_el else None,
                lien=attribut(lien_el, "href") if lien_el else None,
            )
        )
    return evenements


class MaSalle(Source):
    slug = "ma-salle"
    nom = "Ma Salle"
    url_defaut = URL_PROGRAMMATION

    def extraire(self, html: str, timeout: float, session: requests.Session) -> list[Evenement]:
        return _extraire_evenements(html, timeout, session)


SOURCE = MaSalle()


def lister_evenements_a_venir(url: str = URL_PROGRAMMATION, **_: object) -> list[Evenement]:
    return SOURCE.lister_evenements_a_venir(url)


def main(argv: Sequence[str] | None = None) -> int:
    return cli.executer(SOURCE, argv)


if __name__ == "__main__":
    raise SystemExit(main())
```

Vous n'implémentez que `extraire()` : la session HTTP, le seuil temporel, la
déduplication et le tri viennent de `Source`. Le repli JSON-LD est disponible
via `culturecentro.jsonld.extraire_depuis_jsonld(html)` si le site expose des
données schema.org.

## 2. Inscrire la source au registre

Dans `src/culturecentro/sources/__init__.py`, importez la classe et ajoutez une
instance à `SOURCES` :

```python
from culturecentro.sources.ma_salle import MaSalle

SOURCES = {source.slug: source for source in (TheatreGranada(), LaPetiteBoiteNoire(), MaSalle())}
```

## 3. Ajouter des tests

Créez `tests/sources/test_ma_salle.py` avec un fragment HTML figé (hors-ligne)
et vérifiez l'extraction. Inspirez-vous des tests des salles existantes.

## 4. Vérifier

```bash
ruff check . && ruff format --check . && mypy && pytest
python -m culturecentro sources        # « ma-salle » doit apparaître
python -m culturecentro lister --source ma-salle
```

C'est tout : l'agrégation (`culturecentro lister`) et le feed publié incluent
désormais la nouvelle salle.
