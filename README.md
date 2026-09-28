# Événements à venir — salles de spectacle

[![Tests](https://github.com/remtav/culturecentro/actions/workflows/tests.yml/badge.svg)](https://github.com/remtav/culturecentro/actions/workflows/tests.yml)
![Couverture](coverage.svg)

Récupère la liste des **événements à venir** de la programmation de salles de
spectacle et permet de les exporter en texte, CSV ou JSON. Deux salles sont
prises en charge, chacune dans son propre module partageant la même interface
(`lister_evenements_a_venir`, `exporter_json`, `exporter_csv`) :

| Salle | Module | Source |
| --- | --- | --- |
| [Théâtre Granada](https://theatregranada.com/programmation-2/) | `culturecentro.sources.theatre_granada` | WPBakery (grille AJAX) |
| [La Petite Boîte Noire](https://lapetiteboitenoire.com/evenements/) | `culturecentro.sources.lapetiteboitenoire` | billetterie Lepointdevente |

## Théâtre Granada

## Installation

```bash
pip install -e .          # ou : pip install -e ".[dev]" pour les outils de dév
```

Le paquet `culturecentro` est installé (layout `src/`). Dépendances :
`requests` et `beautifulsoup4`.

## Utilisation en ligne de commande

Chaque source s'exécute comme un module du paquet :

```bash
python -m culturecentro.sources.theatre_granada                     # liste texte
python -m culturecentro.sources.theatre_granada --format json       # JSON
python -m culturecentro.sources.theatre_granada --format csv -o evenements.csv
python -m culturecentro.sources.theatre_granada -v                  # journalisation DEBUG
```

Options principales :

| Option | Description |
| --- | --- |
| `--url` | Page de programmation à analyser (défaut : la page officielle). |
| `--format {texte,csv,json}` | Format de sortie (défaut : `texte`). |
| `-o`, `--sortie FICHIER` | Écrit dans un fichier (sinon : sortie standard). |
| `--timeout SECONDES` | Délai réseau (défaut : 20). |
| `-v`, `--verbose` | Journalisation niveau DEBUG. |

## Utilisation en bibliothèque

```python
from culturecentro.sources.theatre_granada import (
    lister_evenements_a_venir,
    exporter_json,
    exporter_csv,
)

evenements = lister_evenements_a_venir()
for ev in evenements:
    print(ev)                     # 2026-09-27 20:00 — Jesse Cook (https://…)

exporter_json(evenements, "evenements.json")
exporter_csv(evenements, "evenements.csv")
```

Chaque `Evenement` expose :

| Champ | Description |
| --- | --- |
| `titre` | Nom de l'événement. |
| `sous_titre` | Mention / sous-titre (ex. « SUPPLÉMENTAIRE », nom de tournée), ou `None`. |
| `date_debut` | `datetime` (naïf, supposé heure locale) ou `None`. |
| `lien` | URL de la fiche de l'événement. |
| `image` | URL de l'affiche. |
| `lieu` | Nom du lieu (généralement `None` : toujours le Théâtre Granada). |

`to_dict()` renvoie ces champs sérialisables (date au format ISO 8601), et
les exports CSV/JSON reprennent les mêmes colonnes.

## Fonctionnement

Le site est un WordPress construit avec **WPBakery Page Builder**. Les
événements sont affichés dans une grille en mode « lazy » : le HTML initial
ne contient que 10 événements, mais un unique appel AJAX
(`admin-ajax.php` / `vc_get_vc_grid_data`) renvoie **l'intégralité** des
événements à venir. Le module reproduit cet appel, puis analyse chaque bloc
`.vc_grid-item-mini` (titre, date en français, lien).

Si cet appel échoue (thème modifié, nonce invalide…), le module se rabat
successivement sur : la grille inline (10 événements), les données
structurées schema.org `Event` (JSON-LD), puis les sélecteurs du plugin
« The Events Calendar ». Chaque repli émet un avertissement via `logging`.

## La Petite Boîte Noire

Même interface, dans le module `culturecentro.sources.lapetiteboitenoire` :

```bash
python -m culturecentro.sources.lapetiteboitenoire                     # liste texte
python -m culturecentro.sources.lapetiteboitenoire --format json
python -m culturecentro.sources.lapetiteboitenoire --format csv -o evenements.csv
```

```python
from culturecentro.sources.lapetiteboitenoire import (
    lister_evenements_a_venir,
    exporter_json,
)

evenements = lister_evenements_a_venir()
exporter_json(evenements, "evenements.json")
```

Les options (`--url`, `--format`, `-o/--sortie`, `--timeout`, `-v`) sont
identiques à celles du Théâtre Granada. Chaque `Evenement` expose `titre`,
`date_debut`, `image`, `lien` et `lieu` (plus `to_dict()`). Le champ `image`
(URL de l'affiche) est **obligatoire** dans le modèle : il est toujours
présent, avec la valeur `None` si la source n'expose aucune affiche.

### Fonctionnement

La page [`/evenements/`](https://lapetiteboitenoire.com/evenements/) n'affiche
pas elle-même les spectacles : elle charge un **widget de la billetterie
[Lepointdevente.com](https://lepointdevente.com)**. Le module télécharge la
page, y découvre l'URL de la liste Lepointdevente (lien « Programmation
complète » ou, à défaut, `widget.js`), télécharge cette liste et analyse
chaque carte `.feature-col[data-tpos-event]` (titre, date en français, lieu).
Le lien de la fiche est reconstruit à partir de l'identifiant de l'événement.

Si la découverte échoue, le module retombe sur l'URL de billetterie connue,
puis sur les données JSON-LD de la page. Chaque repli émet un avertissement
via `logging`.

## Maquette web

Le dossier [`maquette/`](maquette/) contient une **maquette de page publique**
(`index.html`, autonome, sans dépendance) illustrant le guichet unique
d'agrégation de la programmation culturelle du centre-ville : agenda
filtrable par discipline et par période, fil chronologique par mois, bande
« En ce moment » pour les expositions longue durée. Les données affichées
sont fictives et servent uniquement à la démonstration ; il suffit d'ouvrir
`maquette/index.html` dans un navigateur.

## Tests

Les tests sont hors-ligne (aucun accès réseau requis) :

```bash
python -m unittest discover -s tests -v
```

Ils sont également exécutés en intégration continue (GitHub Actions) sur
Python 3.10, 3.11 et 3.12 — voir [`.github/workflows/tests.yml`](.github/workflows/tests.yml).
