# Théâtre Granada — événements à venir

Récupère la liste des **événements à venir** de la programmation du
[Théâtre Granada](https://theatregranada.com/programmation-2/) et permet de
les exporter en texte, CSV ou JSON.

## Installation

```bash
pip install -r requirements.txt
```

Dépendances : `requests` et `beautifulsoup4`.

## Utilisation en ligne de commande

```bash
python theatre_granada.py                        # liste texte sur la sortie standard
python theatre_granada.py --format json          # JSON
python theatre_granada.py --format csv -o evenements.csv
python theatre_granada.py -v                      # journalisation détaillée (DEBUG)
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
from theatre_granada import lister_evenements_a_venir, exporter_json, exporter_csv

evenements = lister_evenements_a_venir()
for ev in evenements:
    print(ev)                     # 2026-09-27 20:00 — Jesse Cook (https://…)

exporter_json(evenements, "evenements.json")
exporter_csv(evenements, "evenements.csv")
```

Chaque `Evenement` expose `titre`, `date_debut` (`datetime` ou `None`),
`lien`, `lieu`, ainsi que `to_dict()` pour la sérialisation.

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

## Tests

Les tests sont hors-ligne (aucun accès réseau requis) :

```bash
python -m unittest discover -s tests -v
```

Ils sont également exécutés en intégration continue (GitHub Actions) sur
Python 3.10, 3.11 et 3.12 — voir [`.github/workflows/tests.yml`](.github/workflows/tests.yml).
