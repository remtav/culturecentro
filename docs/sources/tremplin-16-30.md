# Le Tremplin 16-30

| | |
| --- | --- |
| Slug | `tremplin-16-30` |
| Module | [`culturecentro.sources.tremplin16_30`](../../src/culturecentro/sources/tremplin16_30.py) |
| Page analysée | <https://tremplin16-30.com/evenements/> |
| Catégorie par défaut | `musique` |
| Tests | [`tests/sources/test_tremplin16_30.py`](../../tests/sources/test_tremplin16_30.py) |

Fiche technique de la source. Interface, options et schéma communs à toutes
les salles : voir le [README](../../README.md#utilisation-en-ligne-de-commande).

## Utilisation

Module `culturecentro.sources.tremplin16_30`, même interface et mêmes options :

```bash
python -m culturecentro.sources.tremplin16_30 --format json
```

## Fonctionnement

La page [`/evenements/`](https://tremplin16-30.com/evenements/) liste les
événements à venir sous forme de blocs Gutenberg « média + texte »
(`.wp-block-media-text`) : titre `h2`, `figure` dont l'affiche est un fond
CSS, paragraphes `p.event-data` (dates, lieu, tarif) et bouton « Plus
d'infos » vers la fiche. Les dates sont en texte libre et souvent **sans
année** (celle-ci figure dans le titre, ex. « automne 2026 ») ; l'analyseur
partagé `culturecentro.dates.plage_dates_fr` / `trouver_dates_fr` gère :

- « Mardi 29 septembre 2026 - 17h » → un événement ;
- « Jeudis 17 septembre, 29 octobre, 26 novembre et 17 décembre - 18h30 à 20h30 »
  → **un événement par date** (même titre, même lien) ;
- « Tous les mercredis du 9 septembre au 16 décembre - 18h30 à 20h30 » → un
  événement avec `date_debut` et `date_fin` (série en cours conservée).

Le texte des dates est repris en `sous_titre`. Repli JSON-LD si aucun bloc
n'est trouvé.
