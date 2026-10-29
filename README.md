# Market Insight AI

Application locale d’étude des offres Fibre B2C des opérateurs marocains.
La connexion Windows SQL Server fonctionnelle est conservée, avec mssql-python,
Trusted_Connection=yes et la base MarketInsight. Aucun changement de schéma.

## Lancer

Prérequis : Python 3.10+, SQL Server local, schéma et vue existants selon
`sql/MarketInsight_export.sql`, accès Windows à la base.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Si `.venv` existe, ignorez sa création. Si `.env` est absent, copiez `.env.example`
vers `.env` et adaptez DB_SERVER et DB_DATABASE. En leur absence, les valeurs sont
localhost et MarketInsight. DB_DRIVER, DB_USERNAME et DB_PASSWORD ne sont pas utilisés.
Le certificat du serveur local est accepté par TrustServerCertificate=yes.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Redémarrez Streamlit après une modification du thème. Le serveur est limité à
127.0.0.1. Les espaces correspondent à un parcours local pédagogique, sans
système d’authentification ni gestion de rôles de production.

Adresse locale : http://127.0.0.1:8502. Le terminal qui exécute Streamlit doit
rester ouvert pendant l’utilisation. Vous pouvez aussi lancer `.\lancer.ps1`
depuis la racine du projet ; ce lanceur utilise le Python du projet et le bon port.

## Parcours disponible

- **Accueil** : accès à l’étude et à l’import, compteurs SQL réels. Les erreurs
  de connexion sont distinguées des listes vides.
- **Étude comparative** : lecture automatique de dbo.v_OffresValidees uniquement,
  périmètre Fibre B2C, filtres opérateurs/éditions/débits, choix de votre opérateur,
  tableau métier, preuves, conditions et sources. Une seule offre ou un seul
  opérateur ne déclenche aucun graphique ni classement concurrentiel.
- **Indicateurs** : prix par 100 Mbps ; médiane des prix connus par débit exact,
  écart et rang du meilleur prix de chaque opérateur seulement lorsqu’au moins
  deux opérateurs ont un prix connu au même débit. Rang dense avec ex æquo.
  Les paliers non couverts sont limités au périmètre sélectionné.
- **Rapport** : aperçu et téléchargements Markdown/HTML, reflétant les filtres,
  offres, calculs, conditions, éditions, pages et limites. Il est descriptif,
  sans synthèse IA ni recommandations automatiques.
- **Analyste / Import** : PDF, opérateur enregistré, édition, URL ; extraction
  PyMuPDF avec mots, tableaux et coordonnées, puis LLM configuré ou règles de
  secours sur les colonnes. Les trois PDF du dossier Data peuvent être sélectionnés
  directement. L’extraction ne démarre que sur clic. Les pages lues, candidats,
  offres acceptées, motifs de rejet et états LLM sont consultables et exportables.
- **Analyste / Vérifier** : modification du brouillon, preuve et texte de page,
  enregistrement en attente, correction des offres SQL, validation explicite
  avec est_validee=1. Le rejet supprime uniquement une offre non validée,
  après une confirmation dans l’interface ; le schéma n’a pas de statut rejeté.
- **Analyste / Catalogues** : documents, édition, nombres d’offres validées et
  en attente, liens et téléchargement des PDF conservés localement.
- **Diagnostic technique** : lecture de contrôle dans un panneau secondaire
  de l’espace analyste ; aucun détail de connexion sensible affiché.

## Données et conservation

Les champs et requêtes respectent le schéma existant. Les requêtes avec valeurs
variables sont paramétrées. Pydantic contrôle les types, bornes et longueurs avant
écriture. Les citations sont vérifiées dans leur zone PDF (ou dans le texte original
pour une saisie manuelle), y compris après correction. Les nouvelles preuves sont
stockées en JSON dans le champ extrait_source existant : empreinte, pages, rectangles,
citations, paramètres tarifaires et points à vérifier. Aucun champ SQL n’est ajouté.
L’interface et les rapports présentent ces preuves sous une forme lisible.
Le prix de comparaison est le prix normal TTC hors promotion, le débit est le débit
permanent. Promotion, durée, débit temporaire, installation et équipement restent
distincts dans les conditions et les preuves. Les valeurs inconnues restent null.
La présence d’une citation prouve sa provenance, pas à elle seule l’exactitude
sémantique de tous les champs : la relecture humaine reste indispensable.

Les PDF importés sont conservés dans `Data/imports/<sha256>.pdf` (hors Git).
Le nom du catalogue SQL inclut cette empreinte ; le contrôle de réimport ne
repose pas sur le seul nom fourni. Réimporter un document renommé ne duplique
pas ses offres. Des offres distinctes peuvent être ajoutées à un catalogue déjà
rempli ; un réimport complet ignore les zones déjà enregistrées. L’enregistrement
est transactionnel. Les catalogues historiques sont rapprochés par contenu si leur
PDF local est disponible. Sinon, leur identité reste à contrôler manuellement.
L’opérateur détecté, l’édition et la source sont vérifiés sans écraser des métadonnées
contradictoires. Des PDF de contenu différent conservent des catalogues distincts.
Les brouillons et corrections survivent
aux interactions et à la navigation via st.session_state, mais pas au redémarrage
du serveur ou à la perte de session avant enregistrement SQL.

Pour un catalogue historique, si le PDF original manque localement, l’analyste
voit ce manque ; la publication reste bloquée tant que la preuve ne peut pas être
recalculée. Les corrections peuvent être enregistrées sans publier l’offre.
Aucun PDF n’est reconstitué ou présenté comme vérifié automatiquement.

Les données marquées DEMO, fictives ou simulées sont conservées en base et visibles
séparément dans l’historique. L’étude charge par défaut toutes les offres validées,
réelles et simulées, depuis la vue SQL. Un sélecteur permet de ne consulter que les
catalogues réels ou les simulations. Tous les opérateurs SQL éligibles du périmètre
sont sélectionnés au premier chargement ; « Votre opérateur » ne filtre pas ses concurrents.
Les simulations portent une origine explicite et un avertissement « tarifs fictifs ».
Leurs médianes, rangs, graphiques et rapports sont séparés des données réelles.
Elles restent exclues des compteurs réels et des rapports documentaires réels.
Chaque interaction relit SQL sans cache ; « Actualiser les offres » permet une
relecture explicite. Les filtres sont réinitialisés lorsque les opérateurs ou le
contenu du périmètre changent. Aucune validation PDF automatique n’est effectuée.

Le statut TV n’est pas structuré : aucun filtre TV déduit du nom n’est appliqué.
Une évolution de schéma reste à proposer et à approuver. Les éditions peuvent
être différentes : les résultats ne décrivent pas forcément le marché actuel.

## Configuration LLM facultative

Dans `.env` uniquement : LLM_PROVIDER=openai, LLM_API_KEY (ou OPENAI_API_KEY),
OPENAI_MODEL et éventuellement OPENAI_BASE_URL (URL complète de l’endpoint Chat
Completions). LLM_PROVIDER=openai_compatible exige cet endpoint explicite pour une
API compatible. Les autres protocoles de fournisseurs ne sont pas implémentés.
Le document est envoyé au fournisseur configuré seulement
lors d’une extraction demandée. Les secrets ne sont ni affichés ni journalisés.

Les états « non configuré », échec réseau/HTTP, réponse JSON invalide, extraction
réussie et réponse valide sans offre sont distincts. Une réponse valide [] ne
déclenche jamais le secours. En cas d’échec technique ou de preuves refusées,
les règles géométriques peuvent proposer des offres, avec leur mode affiché.
Le numéro de page vient du programme. Le LLM reçoit les zones séparées et leurs
conditions, pas un texte où les colonnes sont mélangées.

Pas d’OCR ni de modèle visuel intégré : les pages image et services illisibles
sont signalés. La source originale peut être affichée à côté des corrections.
Une saisie manuelle avec citation exacte reste possible. La synthèse IA contrôlée
par vérification des chiffres n’est pas implémentée.

## Résultats vérifiés sur les trois documents

| Catalogue | Pages des offres | Avant | Propositions sourcées |
| --- | --- | ---: | ---: |
| Maroc Telecom, fichier Avril 2026 | 2 et 3 | 0 | 6 |
| Orange, Juin 2023 | 28 | 0 | 4 |
| inwi, édition non précisée | 49 | 0 | 4 |

Ces résultats sont des propositions à vérifier, pas des validations automatiques.
Orange : prix normal distinct du prix promotionnel pendant trois mois. inwi :
trois débits temporairement augmentés reviennent à 20 Mbps après trois mois ;
quatre colonnes sont visibles malgré l’annonce textuelle de cinq offres.
Le TTC manque dans les grilles Orange et inwi : les tarifs documentaires sont
conservés mais le champ TTC reste null. La première grille Maroc Telecom n’explicite
pas la périodicité ; son prix mensuel reste null. La portée des conditions page 3
et les services Orange en image demandent une relecture.

Voir [l’audit détaillé](examples/audit_extraction.md) et le
[JSON des résultats et diagnostics](examples/extraction_catalogues.json).
Les montants de référence sont dans les tests ; aucune offre finale n’est codée
en dur dans le moteur d’extraction.

```powershell
.\.venv\Scripts\python.exe scripts/audit_catalogues.py
```

Cette commande n’écrit pas en SQL et ne contacte aucune API. L’option `--llm`
autorise explicitement un essai avec le fournisseur configuré.

## Vérifier

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests métier et AppTest : preuve, valeurs manquantes, paliers, extraction de
secours, sécurité HTML, trois pages, filtres, éditions, base indisponible,
vue vide, brouillons persistants et validation explicite. Les tests ordinaires
simulent SQL et le LLM, sans écrire dans votre base ni appeler une API. Les tests
de régression lisent aussi les vrais PDF. Dernier contrôle : 47 tests réussis,
2 tests SQL facultatifs ignorés par défaut et exécutés séparément avec succès.

Test facultatif sur la vraie base locale :

```powershell
$env:RUN_SQL_INTEGRATION='1'
.\.venv\Scripts\python.exe -m pytest tests/test_sql_integration.py -q
Remove-Item Env:RUN_SQL_INTEGRATION
```

Ces tests exercent import progressif, réimport renommé, ajout à un catalogue rempli,
visibilité après validation, rejet et les trois vrais PDF dans des transactions
englobantes systématiquement annulées. SQL Server peut néanmoins
consommer des valeurs d’identité, même après annulation.

Vérification manuelle : Accueil → Consulter l’étude → sources/rapport, filtres
sans résultat, puis Analyste → PDF → extraction/corrections → enregistrement
→ vérification → validation. Contrôlez que seule la validation rend l’offre
visible côté étude, et que le même PDF renommé n’ajoute aucune offre.

## Fichiers

`app.py`, `pages/`, `ui_common.py` et `.streamlit/config.toml` : interface.
`db_connection.py` : connexion et vue validée. `analyst_repository.py` : lectures
admin et vérification transactionnelle. `catalogue_storage.py` : PDF et empreintes.
`extract_pdf.py`, `extract_offers_ai.py`, `llm_client.py`, `save_offers.py` : import.
`layout_extractor.py`, `offer_evidence.py` : association par zones et preuves multi-page.
`catalogue_identity.py`, `provenance.py` : métadonnées et séparation des démonstrations.
`provenance.py` définit aussi le contrat commun `ORIGIN`, `REAL`, `SIMULATED` :
la colonne `origine_donnees` est calculée en Python, sans modification du schéma SQL.
`analyse_offers.py`, `generate_report.py` : calculs et rapports. `tests/` : contrôles.
`scripts/audit_catalogues.py`, `examples/` : audit reproductible et résultats réels.
