# Sporobole

| | |
| --- | --- |
| Slug | `sporobole` |
| Module | [`culturecentro.sources.sporobole`](../../src/culturecentro/sources/sporobole.py) |
| Page analysée | <https://sporobole.org/programmation/> |
| Catégorie par défaut | `arts` |
| Tests | [`tests/sources/test_sporobole.py`](../../tests/sources/test_sporobole.py) |

Fiche technique de la source. Interface, options et schéma communs à toutes
les salles : voir le [README](../../README.md#utilisation-en-ligne-de-commande).

## Utilisation

Module `culturecentro.sources.sporobole`, même interface et mêmes options :

```bash
python -m culturecentro.sources.sporobole --format json
```

## Fonctionnement

La page [`/programmation/`](https://sporobole.org/programmation/) ne contient
aucun événement : la liste est injectée par un appel AJAX du thème
(`admin-ajax.php` / `standish_select_refresh`), filtrable par type de contenu
(« Diffusions », projets, créations, ateliers) et paginé. Seules les
**diffusions** (expositions, lancements, résidences ouvertes…) portent des
dates : le module les interroge page après page, tant que les événements
restent en cours ou à venir (la liste est triée du plus récent au plus
ancien). Chaque bloc `.standish-single-event` fournit l'affiche (fond CSS), la
catégorie (`sous_titre`), le titre, le lien et la période (« Du 02 octobre
2026 au 27 novembre 2026 » → `date_debut`/`date_fin`, « Le 23 octobre 2026 »).
Repli JSON-LD si l'appel AJAX échoue.
