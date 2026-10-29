# Audit des catalogues locaux

Audit reproductible : `python scripts/audit_catalogues.py`. Lecture seule ; aucune écriture SQL. Sans appel API sauf option `--llm`.

## Résultats

| Document | Pages | Avant | Propositions sourcées | Pages des offres |
| --- | ---: | ---: | ---: | --- |
| Catalogue des offres fixe et internet B2C - Avril 2026.pdf | 19 | 0 | 6 | 2, 3 |
| catalogue_inwi.pdf | 62 | 0 | 4 | 49 |
| catalogue_orange.pdf | 37 | 0 | 4 | 28 |

## Causes observées avant correction

- Maroc Telecom : grille de quatre colonnes et grille TV de deux colonnes ; prix sans `/mois` dans la première grille, conditions sur la page suivante contenant une migration ADSL.
- Orange : unité « Méga » non reconnue, quatre cartes avec promotions et prix normal dans une même ligne, absence de TTC dans la grille ; services en partie dans des images.
- inwi : quatre colonnes, plusieurs débits par forfait à cause du débit temporaire ; absence de TTC dans les montants. Le texte annonce cinq offres alors que quatre colonnes sont visibles.
- L’ancien repli demandait un seul débit et un seul prix TTC/mois par page. Le résultat vide ne révélait ni l’absence de clé LLM ni ces incompatibilités.

## Contrôle des chiffres extraits

| Document | Offre descriptive | Page | Débit permanent | Tarif normal indiqué (DH) | Promo (DH) | Durée promo | Prix mensuel TTC certain |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Catalogue des offres fixe et internet B2C - Avril 2026.pdf | Fibre 100 Mbps | 2 | 100 | 400.0 | null | null | null |
| Catalogue des offres fixe et internet B2C - Avril 2026.pdf | Fibre 200 Mbps | 2 | 200 | 500.0 | null | null | null |
| Catalogue des offres fixe et internet B2C - Avril 2026.pdf | Fibre 500 Mbps | 2 | 500 | 800.0 | null | null | null |
| Catalogue des offres fixe et internet B2C - Avril 2026.pdf | Fibre 1000 Mbps | 2 | 1000 | 1000.0 | null | null | null |
| Catalogue des offres fixe et internet B2C - Avril 2026.pdf | Fibre 200 Mbps + Premium MT TV | 3 | 200 | 700.0 | null | null | 700.0 |
| Catalogue des offres fixe et internet B2C - Avril 2026.pdf | Fibre 1000 Mbps + Premium MT TV | 3 | 1000 | 1200.0 | null | null | 1200.0 |
| catalogue_inwi.pdf | Fibre 20 Mbps (50 Mbps pendant 3 mois) | 49 | 20 | 249.0 | null | null | null |
| catalogue_inwi.pdf | Fibre 20 Mbps (100 Mbps pendant 3 mois) | 49 | 20 | 349.0 | null | null | null |
| catalogue_inwi.pdf | Fibre 20 Mbps (200 Mbps pendant 3 mois) | 49 | 20 | 449.0 | null | null | null |
| catalogue_inwi.pdf | Fibre 200 Mbps | 49 | 200 | 649.0 | null | null | null |
| catalogue_orange.pdf | Fibre 20 Mbps | 28 | 20 | 249.0 | null | null | null |
| catalogue_orange.pdf | Fibre 50 Mbps | 28 | 50 | 349.0 | 249.0 | 3 | null |
| catalogue_orange.pdf | Fibre 100 Mbps | 28 | 100 | 449.0 | 349.0 | 3 | null |
| catalogue_orange.pdf | Fibre 200 Mbps | 28 | 200 | 649.0 | 449.0 | 3 | null |

## Vérification et limites

- Pages originales rendues et inspectées : Maroc Telecom 2–3, Orange 28, inwi 49. Les valeurs de référence vivent dans les tests, pas dans le moteur.
- Chaque proposition contient une preuve JSON dans le champ source existant : empreinte PDF, page, rectangle, citation native, conditions communes et informations tarifaires. Le contrôle recalcule les citations depuis le PDF.
- Le numéro de page est attribué par le programme. Les modifications sont revalidées avant écriture et avant publication.
- Orange : tarifs normaux 249/349/449/649 DH ; promotions 249/349/449 DH pendant trois mois sur les forfaits 50/100/200 Mbps. Le TTC n’est pas explicité ; ce champ reste null. Les appels en image restent à vérifier visuellement.
- inwi : les trois premiers forfaits ont un débit permanent de 20 Mbps, temporairement 50/100/200 Mbps pendant trois mois. Le quatrième conserve 200 Mbps. Les montants ne portent pas la mention TTC.
- Maroc Telecom : quatre montants TTC en page 2 sans périodicité explicite dans la grille : prix mensuel laissé null. Les deux prix TV mensuels sont explicites. La portée des conditions générales page 3 est signalée pour relecture.
- Aucun OCR ni modèle visuel n’est activé. Les pages image et les services non lisibles sont signalés. La lecture géométrique reste un mode de secours à vérifier humainement.
- Le LLM local n’avait pas de clé configurée au moment du diagnostic. Les états techniques, réponse vide valide et preuves invalides sont couverts par simulation. Une réponse vide valide n’utilise jamais le secours.
- Les 50 offres DEMO50 restent en SQL et sont exclues de la base réelle de comparaison, des compteurs réels et des rapports.
- Les métadonnées existantes et les éditions sont conservées. Un PDF renommé est reconnu par empreinte ; des offres distinctes peuvent être ajoutées au même catalogue.

Le JSON compagnon conserve les diagnostics de chaque page et l’intégralité des citations. Aucun secret de configuration n’y figure.
