# Partenaires culturels du centre-ville de Sherbrooke

Liste des principaux lieux et organismes culturels du centre-ville de
Sherbrooke, avec le lien vers leur page de programmation. Les URLs de
programmation ont été vérifiées le **2026-09-27**.

La colonne **Statut d'implémentation** indique si un extracteur (scraper)
existe pour ce lieu dans le dépôt, à l'état de la branche par défaut
(`main`) au 2026-10-06. Le registre faisant autorité reste
[`culturecentro.sources.SOURCES`](../src/culturecentro/sources/__init__.py)
(`culturecentro sources`), et chaque extracteur est décrit dans
[`docs/sources/`](sources/).

## Cœur du centre-ville

| Lieu / organisme | Type | Lien URL vers programmation | Statut d'implémentation |
| --- | --- | --- | --- |
| Théâtre Granada | Salle de spectacle | https://theatregranada.com/programmation-2/ | ✅ Implémenté (`theatre_granada.py`) |
| Le Grand-Espace — Centre des arts de la scène Jean-Besré | Salle (théâtre / danse) | https://legrandespace.ca/public/grand-public/ | ✅ Implémenté (`legrandespace.py`) |
| Musée des beaux-arts de Sherbrooke (MBAS) | Musée | https://mbas.qc.ca/en-cours/ | ✅ Implémenté (`mbas.py`) |
| Sporobole | Centre en art actuel / galerie | https://sporobole.org/programmation/ | ✅ Implémenté (`sporobole.py`) |
| La Petite Boîte Noire | Salle indépendante | https://lapetiteboitenoire.com/evenements/ | ✅ Implémenté (`lapetiteboitenoire.py`) |
| Café 440 | Café-spectacle | https://lecafe440sherbrooke.com/programmation | ❌ Non implémenté |
| Théâtre du Double signe | Compagnie / théâtre de création | https://www.doublesigne.ca/les-productions-du-double-signe/ | ❌ Non implémenté |
| Le Petit Théâtre de Sherbrooke | Théâtre (jeune public) | https://www.petittheatre.qc.ca/spectacles/ | ❌ Non implémenté |
| Le Tremplin 16-30 | Salle multifonctionnelle / art social | https://tremplin16-30.com/evenements/ | ✅ Implémenté (`tremplin16_30.py`) |
| Maison des arts de la parole | Diffuseur (conte / poésie) | https://maisondesartsdelaparole.com/programmation/ | ✅ Implémenté (`maisondesartsdelaparole.py`) |
| Bibliothèque municipale Éva-Senécal | Bibliothèque | https://bibliotheques.sherbrooke.ca/horaire-activites | ❌ Non implémenté |

## À proximité et organismes de référence

| Lieu / organisme | Type | Lien URL vers programmation | Statut d'implémentation |
| --- | --- | --- | --- |
| Centre culturel de l'Université de Sherbrooke (salle Maurice-O'Bready) | Salle de spectacle | https://www.centrecultureludes.ca/programmation/ | ❌ Non implémenté |
| Culture Estrie | Organisme régional | https://cultureestrie.org/nouvelles/ | ❌ Non implémenté |
| Animation Centre-Ville Sherbrooke (ACVS) | Organisme (gère le Théâtre Granada) | *pas de programmation propre* | ➖ Sans objet (couvert par le Théâtre Granada) |

## Notes

- Toutes les URLs de programmation ci-dessus ont été confirmées comme
  existantes et pointant vers une page de programmation / calendrier /
  expositions.
- **Statut d'implémentation** : au 2026-10-06, sept lieux disposent d'un
  extracteur dans le dépôt (Théâtre Granada, La Petite Boîte Noire, Maison
  des arts de la parole, Le Tremplin 16-30, MBAS, Sporobole, Le Grand-Espace) ;
  les autres ne sont pas encore couverts.
- **Culture Estrie** ne publie pas de calendrier régional unique ; le lien
  renvoie vers la section « Nouvelles / Écho des membres ».
- **ACVS** n'a pas de programmation propre : l'organisme gère le Théâtre
  Granada (voir la ligne correspondante).
- L'URL du **Grand-Espace** mène au calendrier « Grand public » ; la saison
  affichée dépend de l'édition en cours.
