# Architecture

`culturecentro` agrège la programmation des salles de spectacle du centre-ville
de Sherbrooke en une liste unique, exportable et publiable. Le paquet est conçu
pour **passer à l'échelle** : ajouter une salle ne touche qu'un fichier de
source, tout le reste étant mutualisé.

## Vue d'ensemble

```
    page(s) HTML d'une salle
            │  Source.extraire()      (logique propre au site)
            ▼
      list[Evenement]  ──► finaliser()  (dédup + filtre + tri)
            │
            ▼
        agreger()      (toutes les salles, tolérant aux pannes)
            │
   ┌────────┴─────────┐
   ▼                  ▼
exporters          web/data/evenements.json  ──► web/index.html (GitHub Pages)
(texte/csv/json)        (feed généré en CI)
```

## Disposition du paquet (`src/culturecentro/`)

| Module | Rôle |
| --- | --- |
| `models.py` | `Evenement` (schéma unique) et `CHAMPS`. |
| `http.py` | Session `requests` et `telecharger()` (en-têtes, reprises). |
| `dates.py` | Analyse ISO 8601 et dates françaises : date simple, heure, listes de dates et plages (« du 7 au 17 octobre 2026 », « jusqu'en mai »). |
| `jsonld.py` | Extraction schema.org `Event` (repli commun). |
| `scraping.py` | `attribut()`, `url_image()`, `premiere_image()` : accès normalisé aux attributs HTML et aux images (lazy, `srcset`, fonds CSS). |
| `filtrage.py` | `finaliser()` (dédup/filtre/tri) et `minuit_utc()`. |
| `categories.py` | Catégorie artistique automatique : libellés de taxonomie, mots-clés, fiche de l'événement (`Categorisation`). |
| `lieux.py` | `normaliser_lieu()` (noms canoniques, alias) et `est_centre_ville()` (périmètre du centre-ville : lieux connus, rues, marqueurs hors périmètre). |
| `exporters.py` | Exports texte / CSV / JSON. |
| `aggregate.py` | `agreger()` : fusion multi-salles, tolérante aux pannes. |
| `cli.py` | CLI par-source (`executer`) et CLI unifiée (`principal`). |
| `__main__.py` | Point d'entrée `python -m culturecentro`. |
| `sources/base.py` | `Source` (ABC) + orchestration `lister_evenements_a_venir`. |
| `sources/__init__.py` | Registre `SOURCES {slug: Source}` + `obtenir`/`toutes`. |
| `sources/*.py` | Une salle par module (extraction propre au site). |

## L'interface `Source`

Chaque salle est une sous-classe de `Source` qui déclare `slug`, `nom`,
`url_defaut` et implémente **uniquement** `extraire(html, timeout, session)`.
L'orchestration (session, téléchargement, seuil temporel par défaut,
déduplication, tri) est fournie par la classe de base et donc identique pour
toutes les salles. Le registre `SOURCES` permet à la CLI et à l'agrégation de
découvrir les salles automatiquement.

## Schéma d'événement unifié

Toutes les sources produisent le même `Evenement` (`titre`, `sous_titre`,
`date_debut`, `date_fin`, `lien`, `image`, `lieu`, `partenaire`, `categorie`). Un champ non exposé par une
salle vaut `None`. Cette homogénéité est ce qui rend l'agrégation et les
exports uniformes. `date_fin` sert aux événements qui s'étalent dans le temps
(expositions, séries) : `finaliser()` les conserve tant qu'ils sont en cours.

## Du code au site public

1. `agreger()` interroge toutes les salles, renseigne le `partenaire`, remplit
   le `lieu` manquant avec le nom de la salle, ramène les lieux à leur nom
   canonique, écarte les événements hors du centre-ville, détermine la
   catégorie artistique, déduplique et trie.
2. La CLI écrit le feed : `python -m culturecentro lister --format json -o web/data/evenements.json`.
3. `web/index.html` charge ce feed (repli sur des données de démo s'il est
   absent) et l'affiche.
4. Le workflow `publish.yml` régénère le feed et déploie `web/` sur GitHub Pages.

## Qualité

`ruff` (lint + format), `mypy --strict` et `pytest` (couverture ≥ 85 %) sont
configurés dans `pyproject.toml` et exécutés en intégration continue. Les
versions de `ruff` et `mypy` sont épinglées pour un CI reproductible.
