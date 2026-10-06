# La Petite Boîte Noire

| | |
| --- | --- |
| Slug | `la-petite-boite-noire` |
| Module | [`culturecentro.sources.lapetiteboitenoire`](../../src/culturecentro/sources/lapetiteboitenoire.py) |
| Page analysée | <https://lapetiteboitenoire.com/evenements/> |
| Catégorie par défaut | `musique` |
| Tests | [`tests/sources/test_lapetiteboitenoire.py`](../../tests/sources/test_lapetiteboitenoire.py) |

Fiche technique de la source. Interface, options et schéma communs à toutes
les salles : voir le [README](../../README.md#utilisation-en-ligne-de-commande).

## Utilisation

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
identiques à celles du [Théâtre Granada](theatre-granada.md). Les événements
suivent le [schéma commun](../../README.md#schéma-dévénement) ; La Petite Boîte
Noire n'expose pas de `sous_titre` (toujours `None`), et `image` (URL de
l'affiche) vaut `None` si la source n'en fournit pas.

## Fonctionnement

La page [`/evenements/`](https://lapetiteboitenoire.com/evenements/) n'affiche
pas elle-même les spectacles : elle charge un **widget de la billetterie
[Lepointdevente.com](https://lepointdevente.com)**. Le module télécharge la
page, y découvre l'URL de la liste Lepointdevente (lien « Programmation
complète » ou, à défaut, `widget.js`), télécharge cette liste et analyse
chaque carte `.feature-col[data-tpos-event]` (titre, date en français, lieu,
affiche). Le lien mène à la fiche propre à l'événement sur Lepointdevente
(`https://lepointdevente.com/billets/<code>`, le contenu de la fenêtre
surgissante du widget) plutôt qu'à la programmation générale ; le code est lu
dans l'URL de l'affiche, sinon on utilise le lien permanent
`/plugins/embed/redirect?event=<id>`, qui redirige vers la même fiche.
Le lieu « `<salle>, Sherbrooke, QC` » est normalisé : la ville est
retirée et toute graphie du nom de la salle (casse, accents) est ramenée à
« La Petite Boîte Noire », pour qu'un seul lieu apparaisse dans l'agrégation.

La **catégorie** que l'organisateur déclare sur Lepointdevente (« Humour »,
« Arts littéraires », « Théâtre », « Danse ») n'apparaît ni dans la liste ni
sur la fiche : seule la recherche du site filtre par catégorie. Le module y
cherche donc la salle à Sherbrooke, une catégorie à la fois (4 requêtes), et
attribue la catégorie correspondante aux événements trouvés — un spectacle
d'humour est ainsi reconnu même quand ni son titre ni sa description ne
disent « humour ». Les autres événements suivent le classement automatique
(musique par défaut). En cas d'échec de la recherche, un avertissement est
émis et ce classement automatique s'applique.

Si la découverte échoue, le module retombe sur l'URL de billetterie connue,
puis sur les données JSON-LD de la page. Chaque repli émet un avertissement
via `logging`.
