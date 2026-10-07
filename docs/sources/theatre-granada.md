# Théâtre Granada

| | |
| --- | --- |
| Slug | `theatre-granada` |
| Module | [`culturecentro.sources.theatre_granada`](../../src/culturecentro/sources/theatre_granada.py) |
| Page analysée | <https://theatregranada.com/programmation-2/> |
| Catégorie par défaut | `musique` |
| Tests | [`tests/sources/test_theatre_granada.py`](../../tests/sources/test_theatre_granada.py) |

Fiche technique de la source. Interface, options et schéma communs à toutes
les salles : voir le [README](../../README.md#utilisation-en-ligne-de-commande).

## Utilisation

Module `culturecentro.sources.theatre_granada` (slug `theatre-granada`), qui
suit l'interface et les options communes décrites dans le
[README](../../README.md#utilisation-en-ligne-de-commande) :

```bash
python -m culturecentro.sources.theatre_granada --format json
```

## Fonctionnement

Le site est un WordPress construit avec **WPBakery Page Builder**. Les
événements sont affichés dans une grille en mode « lazy » : le HTML initial
ne contient que 10 événements, mais un unique appel AJAX
(`admin-ajax.php` / `vc_get_vc_grid_data`) renvoie **l'intégralité** des
événements à venir. Le module reproduit cet appel, puis analyse chaque bloc
`.vc_grid-item-mini` (titre, date en français, lien).

Les catégories WordPress de chaque bloc mêlent genres (« Musique »,
« Humour »…) et **salles** : le Granada annonce aussi des spectacles qu'il
présente ailleurs, classés « La Petite Boîte Noire » ou « Le Grand-Espace -
CAJB ». Le terme de salle donne le `lieu` (et n'est pas lu comme un genre :
« Théâtre Granada » n'est pas du théâtre) ; les autres termes donnent la
catégorie.

Si cet appel échoue (thème modifié, nonce invalide…), le module se rabat
successivement sur : la grille inline (10 événements), les données
structurées schema.org `Event` (JSON-LD), puis les sélecteurs du plugin
« The Events Calendar ». Chaque repli émet un avertissement via `logging`.
