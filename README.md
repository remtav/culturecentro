# Événements à venir — salles de spectacle

[![Tests](https://github.com/remtav/culturecentro/actions/workflows/tests.yml/badge.svg)](https://github.com/remtav/culturecentro/actions/workflows/tests.yml)
![Couverture](coverage.svg)

Récupère la liste des **événements à venir** de la programmation de salles de
spectacle et permet de les exporter en texte, CSV ou JSON. Chaque salle est
une **source** (`culturecentro.sources`) qui n'implémente que l'extraction
propre à son site ; tout le reste — client HTTP, analyse des dates françaises,
repli JSON-LD, modèle d'événement, déduplication, exports et CLI — est fourni
par un **cœur partagé** (`culturecentro.models`, `.http`, `.dates`, `.jsonld`,
`.filtrage`, `.exporters`). Ajouter une salle se limite ainsi à écrire sa
logique d'extraction et à l'inscrire au registre.

| Salle | Module | Source |
| --- | --- | --- |
| [Théâtre Granada](https://theatregranada.com/programmation-2/) | `culturecentro.sources.theatre_granada` | WPBakery (grille AJAX) |
| [La Petite Boîte Noire](https://lapetiteboitenoire.com/evenements/) | `culturecentro.sources.lapetiteboitenoire` | billetterie Lepointdevente |
| [Maison des arts de la parole](https://maisondesartsdelaparole.com/programmation/) | `culturecentro.sources.maisondesartsdelaparole` | calendrier EventON (AJAX mois par mois) |

Toutes les sources produisent le **même schéma** d'événement (colonnes
`titre`, `sous_titre`, `date_debut`, `date_fin`, `lien`, `image`, `lieu`) : un
champ non exposé par une salle vaut simplement `None` (p. ex. `sous_titre`
pour La Petite Boîte Noire). `date_fin` n'est renseignée que pour ce qui
s'étale dans le temps (exposition, série d'ateliers, spectacle à l'affiche
plusieurs jours) ; un tel événement **déjà commencé** reste listé tant que sa
fin n'est pas passée.

Chaque source récupère l'**affiche** (`image`) dès que le site en expose une :
l'utilitaire partagé `culturecentro.scraping.url_image` lit indifféremment
`src`, les attributs de chargement différé (`data-src`, `srcset`…) et les fonds
CSS (`background-image`), et `premiere_image` sert de repli sur tout le bloc de
l'événement. La page web affiche cette affiche en vignette lorsqu'elle existe.

## Agrégation — CLI unifiée

La commande `culturecentro` (ou `python -m culturecentro`) agrège toutes les
salles enregistrées en une seule liste, dédupliquée et triée par date ; le
`lieu` manquant est renseigné avec le nom de la salle. Une salle indisponible
est ignorée avec un avertissement (les autres sont conservées).

```bash
culturecentro sources                     # liste les salles enregistrées
culturecentro lister                      # agrège toutes les salles (texte)
culturecentro lister --format json        # agrège en JSON
culturecentro lister --source theatre-granada --format csv -o prog.csv
python -m culturecentro lister            # équivalent sans le script installé
```

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
    print(ev)  # 2026-09-27 20:00 — Jesse Cook (https://…)

exporter_json(evenements, "evenements.json")
exporter_csv(evenements, "evenements.csv")
```

Chaque `Evenement` expose :

| Champ | Description |
| --- | --- |
| `titre` | Nom de l'événement. |
| `sous_titre` | Mention / sous-titre (ex. « SUPPLÉMENTAIRE », nom de tournée), ou `None`. |
| `date_debut` | `datetime` (naïf, supposé heure locale) ou `None`. |
| `date_fin` | `datetime` de fin (exposition, série…) ou `None`. |
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
identiques à celles du Théâtre Granada. Les événements suivent le schéma commun
décrit plus haut ; La Petite Boîte Noire n'expose pas de `sous_titre` (toujours
`None`), et `image` (URL de l'affiche) vaut `None` si la source n'en fournit pas.

### Fonctionnement

La page [`/evenements/`](https://lapetiteboitenoire.com/evenements/) n'affiche
pas elle-même les spectacles : elle charge un **widget de la billetterie
[Lepointdevente.com](https://lepointdevente.com)**. Le module télécharge la
page, y découvre l'URL de la liste Lepointdevente (lien « Programmation
complète » ou, à défaut, `widget.js`), télécharge cette liste et analyse
chaque carte `.feature-col[data-tpos-event]` (titre, date en français, lieu,
affiche). Le lien de la fiche est reconstruit à partir de l'identifiant de
l'événement. Le lieu « <salle>, Sherbrooke, QC » est normalisé : la ville est
retirée et toute graphie du nom de la salle (casse, accents) est ramenée à
« La Petite Boîte Noire », pour qu'un seul lieu apparaisse dans l'agrégation.

Si la découverte échoue, le module retombe sur l'URL de billetterie connue,
puis sur les données JSON-LD de la page. Chaque repli émet un avertissement
via `logging`.

## Maison des arts de la parole

Module `culturecentro.sources.maisondesartsdelaparole`, même interface et mêmes
options que les autres salles :

```bash
python -m culturecentro.sources.maisondesartsdelaparole --format json
```

### Fonctionnement

La page [`/programmation/`](https://maisondesartsdelaparole.com/programmation/)
affiche un calendrier **EventON** chargé mois par mois : le HTML initial ne
contient que le mois courant, et le changement de mois passe par un appel AJAX
(`admin-ajax.php` / `the_ajax_hook`) dont la requête reprend les réglages du
calendrier (`.cal_arguments`, `.evo-data`, filtres actifs comme la saison) et
un `nonce` inscrit dans la page. Le module lit le mois courant, puis rejoue
l'appel « mois suivant » pour les 12 mois à venir. Chaque bloc
`.eventon_list_event` fournit titre, sous-titre (distribution), dates de début
et de fin (métadonnées schema.org), affiche, lieu (les spectacles se donnent
souvent hors les murs : cafés, salles partenaires…) et lien de la fiche.

Si le calendrier est introuvable, le module retombe sur les données JSON-LD de
la page ; si un appel AJAX échoue, la boucle s'arrête avec les mois déjà
chargés. Chaque repli émet un avertissement via `logging`.

## Site web (`web/`) et feed

Le dossier [`web/`](web/) contient la **page publique** (`index.html`,
autonome, sans dépendance) : agenda filtrable par discipline, période et lieu,
fil chronologique par mois, bande « En ce moment ».

La page charge le **feed agrégé** [`web/data/evenements.json`](web/data/) s'il
est présent et non vide ; sinon elle retombe sur un jeu de données de
démonstration (utile pour l'ouvrir localement). On génère le feed avec la CLI :

```bash
python -m culturecentro lister --format json -o web/data/evenements.json
```

### Publication (GitHub Pages)

Le workflow [`publish.yml`](.github/workflows/publish.yml) régénère le feed et
déploie `web/` sur **GitHub Pages** — quotidiennement (cron), à chaque `push`
sur `main` touchant `web/` ou le paquet, et à la demande. Prérequis (une seule
fois) : **Settings → Pages → Source = GitHub Actions**.

## Développement

Installer le paquet et les outils de qualité :

```bash
pip install -e ".[dev]"
pre-commit install        # facultatif : lance ruff + mypy à chaque commit
```

| Outil | Commande | Rôle |
| --- | --- | --- |
| **pytest** | `python -m pytest` | Tests (hors-ligne, aucun accès réseau) |
| **ruff** | `ruff check .` / `ruff format .` | Lint + formatage |
| **mypy** | `mypy` | Vérification de types (sur `src/`) |
| **coverage** | `python -m coverage run -m pytest && python -m coverage report` | Couverture |

La configuration de tous ces outils vit dans [`pyproject.toml`](pyproject.toml).

## Intégration continue

GitHub Actions exécute, sur chaque `push` et *pull request*
(voir [`.github/workflows/tests.yml`](.github/workflows/tests.yml)) :

- **qualité** — `ruff check`, `ruff format --check`, `mypy --strict` ;
- **tests** — `pytest` sur Python 3.10, 3.11 et 3.12 ;
- **couverture** — mesure, seuil minimal et régénération du badge.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — vue d'ensemble du paquet et du flux de données.
- [`docs/ajouter-une-source.md`](docs/ajouter-une-source.md) — guide pour brancher une nouvelle salle.
- [`docs/partenaires.md`](docs/partenaires.md) — partenaires culturels du centre-ville (feuille de route des sources).

## Licence

Sous licence [MIT](LICENSE).
