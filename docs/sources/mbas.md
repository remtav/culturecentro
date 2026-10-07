# Musée des beaux-arts de Sherbrooke (MBAS)

| | |
| --- | --- |
| Slug | `mbas` |
| Module | [`culturecentro.sources.mbas`](../../src/culturecentro/sources/mbas.py) |
| Page analysée | <https://mbas.qc.ca/en-cours/> |
| Catégorie par défaut | `arts` |
| Tests | [`tests/sources/test_mbas.py`](../../tests/sources/test_mbas.py) |

Fiche technique de la source. Interface, options et schéma communs à toutes
les salles : voir le [README](../../README.md#utilisation-en-ligne-de-commande).

## Utilisation

Module `culturecentro.sources.mbas`, même interface et mêmes options :

```bash
python -m culturecentro.sources.mbas --format json
```

## Fonctionnement

Les expositions sont réparties sur deux pages,
[`/en-cours/`](https://mbas.qc.ca/en-cours/) (page par défaut) et
[`/a-venir/`](https://mbas.qc.ca/a-venir/) (téléchargée en plus). Chaque
exposition est un bloc `div#rectangle` : affiche `img`, titre `h2`, un
paragraphe « type + période » (« EXPOSITION TEMPORAIRE / 15 octobre 2026 au
21 mars 2027 », « EXPO-VENTE / Jusqu'en octobre 2026 », « EXPOSITION
PERMANENTE »), parfois un sous-titre (thème, artiste invité), et un bouton
« En savoir plus ». La période donne `date_debut` et `date_fin` : une
exposition **déjà commencée** reste listée tant qu'elle n'est pas terminée ;
une exposition permanente n'a pas de date (triée en fin de liste). Le
`sous_titre` reprend le sous-titre du bloc, sinon le type d'exposition.
Repli JSON-LD si aucun bloc n'est trouvé.
