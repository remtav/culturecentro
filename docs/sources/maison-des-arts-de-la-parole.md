# Maison des arts de la parole

| | |
| --- | --- |
| Slug | `maison-des-arts-de-la-parole` |
| Module | [`culturecentro.sources.maisondesartsdelaparole`](../../src/culturecentro/sources/maisondesartsdelaparole.py) |
| Page analysée | <https://maisondesartsdelaparole.com/programmation/> |
| Catégorie par défaut | `litt` |
| Tests | [`tests/sources/test_maisondesartsdelaparole.py`](../../tests/sources/test_maisondesartsdelaparole.py) |

Fiche technique de la source. Interface, options et schéma communs à toutes
les salles : voir le [README](../../README.md#utilisation-en-ligne-de-commande).

## Utilisation

Module `culturecentro.sources.maisondesartsdelaparole`, même interface et mêmes
options que les autres salles :

```bash
python -m culturecentro.sources.maisondesartsdelaparole --format json
```

## Fonctionnement

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
