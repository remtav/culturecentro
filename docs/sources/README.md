# Fiches des sources

Une fiche par salle : page analysée, technique d'extraction, replis et
particularités. Le registre faisant autorité est
[`culturecentro.sources.SOURCES`](../../src/culturecentro/sources/__init__.py)
(`culturecentro sources`) ; l'interface, les options et le schéma communs sont
décrits dans le [README](../../README.md).

| Salle | Slug | Fiche |
| --- | --- | --- |
| Théâtre Granada | `theatre-granada` | [theatre-granada.md](theatre-granada.md) |
| La Petite Boîte Noire | `la-petite-boite-noire` | [la-petite-boite-noire.md](la-petite-boite-noire.md) |
| Maison des arts de la parole | `maison-des-arts-de-la-parole` | [maison-des-arts-de-la-parole.md](maison-des-arts-de-la-parole.md) |
| Le Tremplin 16-30 | `tremplin-16-30` | [tremplin-16-30.md](tremplin-16-30.md) |
| Musée des beaux-arts de Sherbrooke (MBAS) | `mbas` | [mbas.md](mbas.md) |
| Sporobole | `sporobole` | [sporobole.md](sporobole.md) |
| Le Grand-Espace | `le-grand-espace` | [le-grand-espace.md](le-grand-espace.md) |

## Modèle de fiche

Pour une nouvelle salle (voir [`../ajouter-une-source.md`](../ajouter-une-source.md)),
créer `docs/sources/<slug>.md` sur ce modèle, puis l'ajouter au tableau
ci-dessus et à la section « Fonctionnement par salle » du README :

````markdown
# Ma Salle

| | |
| --- | --- |
| Slug | `ma-salle` |
| Module | [`culturecentro.sources.ma_salle`](../../src/culturecentro/sources/ma_salle.py) |
| Page analysée | <https://exemple.com/programmation> |
| Catégorie par défaut | `musique` |
| Tests | [`tests/sources/test_ma_salle.py`](../../tests/sources/test_ma_salle.py) |

## Utilisation

```bash
python -m culturecentro.sources.ma_salle --format json
```

## Fonctionnement

Structure de la page (liste statique, appel AJAX, billetterie externe…),
sélecteurs analysés, champs obtenus (titre, dates, lieu, affiche, lien) et
particularités (dates sans année, hors les murs…). Terminer par les replis
(JSON-LD…) et ce qu'ils journalisent.
````
