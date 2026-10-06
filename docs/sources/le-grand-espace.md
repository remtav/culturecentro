# Le Grand-Espace

| | |
| --- | --- |
| Slug | `le-grand-espace` |
| Module | [`culturecentro.sources.legrandespace`](../../src/culturecentro/sources/legrandespace.py) |
| Page analysée | <https://legrandespace.ca/public/grand-public/> |
| Catégorie par défaut | `theatre` |
| Tests | [`tests/sources/test_legrandespace.py`](../../tests/sources/test_legrandespace.py) |

Fiche technique de la source. Interface, options et schéma communs à toutes
les salles : voir le [README](../../README.md#utilisation-en-ligne-de-commande).

## Utilisation

Module `culturecentro.sources.legrandespace`, même interface et mêmes options :

```bash
python -m culturecentro.sources.legrandespace --format json
```

## Fonctionnement

Le site publie sa programmation par **public** et par **édition** (saison) :
[`/public/grand-public/`](https://legrandespace.ca/public/grand-public/?edition=2026-2027)
et [`/public/jeune-public/`](https://legrandespace.ca/public/jeune-public/?edition=2026-2027),
avec un paramètre `?edition=2026-2027`. L'édition en cours est déduite de la
date (la saison commence en août) ; `--url` permet d'en viser une autre.
Chaque page contient d'abord un sélecteur de billetterie (tous les spectacles,
liens `#`, ignoré) puis la liste proprement dite (`.liste_spectacle_block`) :
blocs `.spectacle` avec l'affiche (`img.product_image`), le genre et la
compagnie (réunis en `sous_titre`), le titre, le lien de la fiche et la date de
représentation (« 18 octobre 2026 10 h 00 », « Du 7 au 17 octobre 2026 »,
« Du 29 octobre 2026 au 28 mai 2027 » → `date_debut`/`date_fin`). Les
spectacles marqués « [Terminé] » sont ignorés. Le module télécharge les deux
publics et fusionne les listes ; repli JSON-LD si aucun bloc n'est trouvé.
