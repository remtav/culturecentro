# Partenaires culturels du centre-ville de Sherbrooke

Liste des principaux lieux et organismes culturels du centre-ville de
Sherbrooke, avec le lien vers leur page de programmation. Les URLs de
programmation ont été vérifiées le **2026-09-27**.

La colonne **Statut d'implémentation** indique si un extracteur (scraper)
existe pour ce lieu dans le dépôt, à l'état de la branche par défaut
(`claude/tender-rubin-apkjew`) au 2026-09-27.

## Cœur du centre-ville

| Lieu / organisme | Type | Lien URL vers programmation | Statut d'implémentation |
| --- | --- | --- | --- |
| Théâtre Granada | Salle de spectacle | https://theatregranada.com/programmation-2/ | ✅ Implémenté (`theatre_granada.py`) |
| Le Grand-Espace — Centre des arts de la scène Jean-Besré | Salle (théâtre / danse) | https://legrandespace.ca/public/grand-public/ | ❌ Non implémenté |
| Musée des beaux-arts de Sherbrooke (MBAS) | Musée | https://mbas.qc.ca/en-cours/ | ❌ Non implémenté |
| Sporobole | Centre en art actuel / galerie | https://sporobole.org/programmation/ | ❌ Non implémenté |
| La Petite Boîte Noire | Salle indépendante | https://lapetiteboitenoire.com/evenements/ | ✅ Implémenté (`lapetiteboitenoire.py`) |
| Café 440 | Café-spectacle | https://lecafe440sherbrooke.com/programmation | ❌ Non implémenté |
| Théâtre du Double signe | Compagnie / théâtre de création | https://www.doublesigne.ca/les-productions-du-double-signe/ | ❌ Non implémenté |
| Le Petit Théâtre de Sherbrooke | Théâtre (jeune public) | https://www.petittheatre.qc.ca/spectacles/ | ❌ Non implémenté |
| Le Tremplin 16-30 | Salle multifonctionnelle / art social | https://tremplin16-30.com/evenements/ | ❌ Non implémenté |
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
- **Statut d'implémentation** : au 2026-09-27, seuls le **Théâtre Granada**
  (`theatre_granada.py`) et **La Petite Boîte Noire** (`lapetiteboitenoire.py`)
  disposent d'un extracteur dans le dépôt ; les autres lieux ne sont pas
  encore couverts.
- **Culture Estrie** ne publie pas de calendrier régional unique ; le lien
  renvoie vers la section « Nouvelles / Écho des membres ».
- **ACVS** n'a pas de programmation propre : l'organisme gère le Théâtre
  Granada (voir la ligne correspondante).
- L'URL du **Grand-Espace** mène au calendrier « Grand public » ; la saison
  affichée dépend de l'édition en cours.
