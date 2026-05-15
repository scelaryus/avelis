# SPÉCIFICATION DU BESOIN — GFI SYSTÈME v7.0

## Version 3.1 — Finale, Corrigée et Validée

**Groupe Dendani** — Bab Ezzouar, Alger, Algérie

**Classification :** ULTRA-CONFIDENTIEL — Usage Interne Uniquement

**Version :** 3.1 FINALE — Mars 2026

**Destinataire :** Équipe IT / Fournisseur de la Solution

**Émetteur :** Direction Administrative et Financière — Ahmed Dendani (DAF)

---

> **OBJET DU DOCUMENT :** Ce document constitue la **spécification du besoin unique, consolidée, corrigée et définitive** du système GFI v7.0. Il annule et remplace toutes les versions précédentes (y compris la v3.0). Il rassemble, sans exception, l'intégralité des exigences fonctionnelles, techniques, conditionnelles, d'automatisation, de détection, de classification, de calcul, de consolidation, de nettoyage, d'indexation et de workflow issues des **17 documents de référence** (cf. Annexe C) et des audits subséquents. Le fournisseur IT est tenu de vérifier, ligne par ligne, que son code source répond à chaque exigence exprimée dans le présent document. Toute exigence non couverte constitue un écart bloquant et un motif de rejet de la livraison.

> **RÈGLE FONDAMENTALE :** Le système GFI v7.0 repose sur une philosophie unique : « **L'humain fait le minimum. Le système fait le maximum.** » Chaque pas dans le système doit être conditionné, chaque donnée reliée à un dossier, une entreprise, une personne ou un projet. Le système crée automatiquement les entreprises, les projets, les associe, assainit chaque société. Zéro hallucination, zéro vision tunnel, zéro manque, zéro oubli.

---

## TABLE DES MATIÈRES CORRIGÉE ET SYNCHRONISÉE

| N° | Section | Contenu Clé |
|----|---------|-------------|
| **Partie A** | **FONDATIONS ET STRUCTURE** | **Périmètre, Réalités Financières, Moteurs et Socles** |
| 1 | Périmètre Organisationnel | 9 entités, 9 associés, 16+ projets, alias, nomenclature |
| 2 | Architecture des 4 Réalités Financières | RF1/RF2/RF3/RF4, classification obligatoire, traitement CFF |
| 3 | Moteur CFF — Coût Fiscal Fictif | Détection, calcul décomposé, triple imputation, règles absolues |
| 4 | Moteur de Résolution d'Alias | Résolution obligatoire avant toute imputation (projets, associés, etc.) |
| 5 | Les 39 Socles Techniques et Fonctionnels | Base immuable du système (sécurité, data, workflows, IA, etc.) |
| **Partie B** | **MODULES OPÉRATIONNELS CENTRAUX** | **Finance, RH, ADV, Projets** |
| 6 | Module Finance & Comptabilité (SCF) | Plan comptable, écritures auto, rapprochement, déclarations G50/CNAS/CACOBATPH |
| 7 | Module Trésorerie & Comptes Courants Associés | CCA, mouvements, soldes, retraits, gel, clôture mensuelle |
| 8 | Module ADV — Ventes Immobilières | EDD, CRM, pricing, workflow de vente, gestion RF1/RF2 |
| 9 | Module RH, Paie & SPI | Grille salariale, CNAS, commissions, Score de Performance v2.0 |
| 10 | Module Gestion de Projets & Chantiers | Avancement, qualité, situations de travaux, performance ST |
| 11 | Module Achats, Stock & Logistique | Fournisseurs, inventaire, approvisionnements, apps mobiles |
| **Partie C** | **MODULES AVANCÉS ET AUTOMATISATION** | **Intelligence, Workflows, Données** |
| 12 | Module Centre de Coûts — La Vérité Absolue | 12 catégories, 6 niveaux, 5 axes de consolidation, flux, vérifications |
| 13 | Workflows Métier Spécifiques Dendani | 8 workflows historiques à assainir (AMENFORT, GACEB, prélèvements…) |
| 14 | Module d'Ingestion Automatique (Pipeline 7 Couches) | OCR, déduplication, classification, Go/en/h |
| 15 | Module GED & Indexation Sémantique | Arborescence normée, ElasticSearch, recherche full-text |
| 16 | Moteur de Détection Intelligente Autonome | 15 patterns de détection à découvrir depuis la base brute |
| 17 | Module Méta-IA — Pipeline Auto-Génératif | Scan, détection, génération de code, validation, déploiement |
| **Partie D** | **GOUVERNANCE, SÉCURITÉ ET LIVRABLES** | **UI, Accès, Tests, Déploiement** |
| 18 | UI/UX, Rôles (RBAC) & Dashboards | 8 Rôles Manager, dashboards passifs/actifs, menus dynamiques |
| 19 | Module Juridique & Gouvernance | Contrats, contentieux, cessions de parts, appels de fonds |
| 20 | Sécurité, RBAC Détaillé & Audit Trail | 15 rôles, SoD, MFA, RLS, journal immuable |
| 21 | Tests, Recette & Qualité (AI QA Engine) | 10 Kill Tests complets, 7 Tests Décisifs, 200+ tests fonctionnels |
| 22 | Plan de Déploiement en 11 Phases | Infrastructure, migration, lots, UAT, critères de réception |
| 23 | Livrables Exigés & PV de Réception | Système déployé, Dossier d'Assainissement, Dossier de Réception |
| **Partie E** | **RÉFÉRENTIELS ET ANNEXES** | **Règles, Données, Stack, NFR** |
| 24 | Référentiel des Règles Métier (25+ règles) | Consolidation de toutes les règles critiques en un seul lieu |
| 25 | Référentiel des Formulaires Automatiques (11 formulaires) | Liste des formulaires bloquants de complétion de données |
| 26 | Stack Technologique Cible | FastAPI, PostgreSQL, React, Odoo, ElasticSearch, etc. |
| 27 | Exigences Non-Fonctionnelles (NFR) | Performance, Disponibilité, Sécurité, Sauvegarde |
| 28 | Annexe A : Données de Référence | CFF connus, synthèse terrains, prélèvements associés |
| 29 | Annexe B : Glossaire | Définition de tous les termes et acronymes |
| 30 | Annexe C : Documents de Référence | Liste des 17 documents sources de cette spécification |

---

# PARTIE A — FONDATIONS ET STRUCTURE

---

## SECTION 1 — PÉRIMÈTRE ORGANISATIONNEL

### 1.1 Les 9 Entités Juridiques et Satellites

Le Groupe Dendani est composé de **9 entités distinctes** (7 actives/à fermer, 1 dissoute, 1 satellite) qui doivent être modélisées. Chaque entité est autonome légalement, fiscalement et opérationnellement. Un champ `company_id` est obligatoire sur **tout objet** du système (écritures, commandes, RH, stock, documents).

| Code | Dénomination Légale | Forme | Rôle Principal | Projets Rattachés | Statut |
|------|---------------------|-------|----------------|-------------------|--------|
| ETS-DK | ETS Dendani Khadidja | ETS | Entité historique | JASMIN, EDEN, OPERA, MOSQUEE, T21000 | ACTIF — À FERMER |
| SARL-DP | SARL Dendani Promotion | SARL | Promotion immobilière | OPERA ph2, IRENE, AUREA, 05H, ALLO MAISON | ACTIF |
| SARL-DBPI | SARL DBPI Immobilier | SARL | Promotion immobilière | LYS, T5000, T2400, DG | ACTIF — À FERMER |
| SARL-OC | SARL Omega Construction | SARL | Construction | MAGNOLIA | À FERMER |
| SARL-SEN | SARL Senimar | SARL | Promotion immobilière | EL ACHOUR (ASTERIA) | À DÉVELOPPER |
| SARL-EP | SARL Avelis Promotion | SARL | Portefeuille Avelis | CHERAGA (AUREA) | À DÉVELOPPER |
| EURL-BIM | EURL Bimha Construction | EURL | Construction et réalisation | AVELIS DRIVE, PFSB | À DÉVELOPPER |
| SARL-AMF | **SARL AMENFORT Béton** | SARL | Origine du capital | (aucun) | **DISSOUTE** |
| EURL-BAY | **EURL BAYTI / ALLO MAISON** | EURL | Satellite (factures RF3) | (aucun) | **SATELLITE** |

**Exigence EX-ENT-001 :** Le système doit créer automatiquement ces 9 entités lors du déploiement initial, avec toutes leurs métadonnées. Si le NIF n'est pas encore fourni (formulaire **FC-002**), le système doit bloquer toute opération d'ingestion documentaire pour cette entité et générer un formulaire de réclamation automatique.

**Exigence EX-ENT-002 :** L'entreprise **SARL AMENFORT Béton** (dissoute) doit être modélisée comme 8ème entité avec le statut `DISSOUTE`. Elle est la source historique du capital fondateur et de factures RF3. Le système doit tracer son existence et ses flux sans la traiter comme une entité active.

**Exigence EX-ENT-003 :** L'entreprise **EURL BAYTI / ALLO MAISON** doit être modélisée comme 9ème entité avec le statut `SATELLITE` pour les factures RF3. Le système doit résoudre les alias `BAYTI`, `Allo Maison`, `EURL BAYTI` vers cette même entité.

### 1.2 Les 9 Associés — Source de Vérité Absolue

Le système gère **9 associés**. Chaque associé fondateur (1-4) possède un Compte Courant d'Associé (CCA) principal. Les associés projet (5-9) ont des comptes spécifiques liés à leurs projets respectifs, mais pas de CCA global. Chaque associé possède un identifiant unique (`UUID v4`) et une liste d'alias que le moteur de résolution doit traiter.

| # | Nom Canonique | Alias Reconnus | Statut | Rôle |
|---|---------------|----------------|--------|------|
| 1 | DENDANI Ahmed | Ahmed, Hmed, A.Dendani, AHMED DENDANI, A.D. | Fondateur | DAF / Gérant |
| 2 | DENDANI Mohamed | Mohamed, Moh, Mohammed, M.Dendani, Mouh | Fondateur | Associé |
| 3 | DENDANI Yazid (Lyazid) | Yazid, Lyazid, Bouabdellah, Lyazid Bouabdellah, Y.Bouabdellah | Fondateur | Associé |
| 4 | DENDANI Yamina (Ait Benamara) | Yamina, Y.Ait Benamara, Yamina AIT, Ait Benamara | Fondatrice | Associée |
| 5 | BOUMERDASSI Mustapha | Boumerdassi | Associé projet | — |
| 6 | AMIRAT Brahim | Amirat | Associé projet | — |
| 7 | DENDANI Laid | Laid | Associé projet | T5000 (50%) |
| 8 | MOUKHTARI Tarek | Moukhtari | Associé projet | — |
| 9 | MOUKHTARI Amine | Moukhtari Amine | Associé projet | — |

**Exigence EX-ASS-001 :** Le système doit résoudre **tous les alias** vers l'associé canonique **avant toute imputation financière**. Si le libellé d'une écriture comptable contient « HMED », le système doit automatiquement le résoudre vers `DENDANI Ahmed`. Si « Lyazid » ou « Bouabdellah » apparaît, il doit le résoudre vers `DENDANI Yazid (Lyazid)`. Un alias non résolu provoque un **BLOCAGE immédiat** de l'opération et génère une alerte DAF.

**Exigence EX-ASS-002 :** Yazid et Lyazid **DOIVENT** pointer vers le même `associe_id`. Ahmed et Hmed **DOIVENT** pointer vers le même `associe_id`. Le système ne doit **jamais** créer deux comptes courants distincts pour la même personne physique.

**Exigence EX-ASS-003 :** Le système doit permettre l'ajout d'alias à la volée (`POST /api/alias`) sans redémarrage, avec effet immédiat et création d'une entrée dans le journal d'audit.

### 1.3 Les 16+ Projets — Structure de Parts

Chaque projet est rattaché à une entité juridique et possède sa propre structure de parts entre associés. La distinction entre **% parts dans le projet** et **% parts dans l'entreprise** est **FONDAMENTALE** pour le calcul du CFF et la distribution des bénéfices.

| Code | Projet | Alias | Entité | Ahmed | Mohamed | Yazid (Lyazid) | Yamina | Clients | Statut |
|------|--------|-------|--------|-------|---------|----------------|--------|---------|--------|
| JASMIN | Les Jasmins / Sahel | JASMIN, Sahel, Les Jasmins | ETS-DK | 34% | 33% | 33% | 0% | 100 | ACTIF |
| EDEN | Eden / Foes | EDEN, FOES | ETS-DK | 25% | 25% | 25% | 25% | 154 | ACTIF |
| OPERA | Jardin de l'Opéra / Ouled Fayet | OPERA, Ouled Fayet, Les Jardins de l'Opera | ETS-DK → SARL-DP | 25% | 25% | 25% | 25% | — | ACTIF |
| LYS | Les Lys / 02 Hectare / Draria | LYS, 02H, Hectare, Bentala, Draria, Les Lys, Dhous 2 hectare | SARL-DBPI | 60% | 20% | 20% | 0% | — | ACTIF |
| T21000 | Terrain 21 000 m² | T21000 | ETS-DK | 25% | 25% | 25% | 25% | — | TERRAIN |
| T5000 | Terrain 5 000 m² | T5000 | SARL-DBPI | 50% | 0% | 0% | 0% | — | FC-004 |
| T2400 | Terrain 2 400 m² | T2400 | SARL-DBPI | 50% | 50% | 0% | 0% | — | TERRAIN |
| IRENE | Irène / 05 ha / Ami Djamel | IRENE, 05H, Ami Djamel, 05 Hectare, 05HECTARE, Boumerdes | SARL-DP | 60% | 20% | 20% | 0% | — | ACTIF |
| MAGNOLIA | Magnolia | MAGNOLIA, Les Magnolia | SARL-OC | 60% | 20% | 20% | 0% | 18 | ACTIF |
| AUREA | Auréa / Chéraga | AUREA, Cheraga | SARL-DP / EP | 60% | 20% | 20% | 0% | 199 | ACTIF |
| ASTERIA | Asteria / El Achour | ASTERIA, El Achour | SARL-SEN | 60% | 20% | 20% | 0% | 52 | ACTIF |
| MOSQUEE | Mosquée Taoura | MOSQUEE, Taoura | ETS-DK | 34% | 33% | 33% | 0% | Don | DONATION |
| AVELIS-DRIVE | Avelis Drive | AVELIS DRIVE | EURL-BIM | À définir | À définir | À définir | À définir | À définir | À DÉVELOPPER |
| ALLO-MAISON | Allo Maison | ALLO MAISON | SARL-DP | À définir | À définir | À définir | À définir | À définir | À DÉVELOPPER |
| PFSB | PFSB | PFSB | EURL-BIM | À définir | À définir | À définir | À définir | À définir | À DÉVELOPPER |
| DG | DG | DG | SARL-DBPI | À définir | À définir | À définir | À définir | À définir | À DÉVELOPPER |

> **Note sur T21000 :** Le terrain 21 000 m² est rattaché à l'entité ETS-DK. La propriété foncière est enregistrée au nom d'Ahmed Dendani (100% de l'acte de propriété), mais la structure de parts dans le GFI suit celle de l'entité ETS-DK (25/25/25/25). Le système doit distinguer la propriété foncière (champ `proprietaire_foncier`) de la structure de parts du projet (champ `parts_projet`). Pour le calcul du CFF et la distribution des bénéfices, c'est la structure de parts qui s'applique.

**Exigence EX-PROJ-001 :** Le système doit résoudre automatiquement les alias de projets. « Les Lys », « 02 Hectare », « Bentala », « 02H », « Draria » doivent tous pointer vers le même **centre de coût projet LYS**.

**Exigence EX-PROJ-002 :** Le système doit vérifier que la somme des parts de chaque projet est strictement égale à **100.0000%**. Si après une cession de parts la somme est de 99,99% ou 100,01%, la transaction est **BLOQUÉE** et un rollback automatique est déclenché.

**Exigence EX-PROJ-003 :** Le projet T5000 a un statut incertain (formulaire **FC-004**). Le système doit le modéliser mais le marquer comme « EN ATTENTE CONFIRMATION ». Aucune opération financière ne doit être possible sur T5000 tant que le statut n'est pas confirmé par le DAF.

**Exigence EX-PROJ-004 :** Le projet MOSQUEE est une donation. Les parts indiquées sont pour information de l'origine des fonds et ne donnent pas lieu à une distribution de bénéfices. Le système doit marquer ce projet comme `NON_COMMERCIAL`.

**Exigence EX-PROJ-005 :** Le projet OPERA a fait l'objet d'un transfert d'entité porteuse (ETS-DK → SARL-DP). Le système doit modéliser ce transfert avec une date effective (à renseigner via formulaire **FC-012**). Les écritures comptables antérieures au transfert restent sous ETS-DK ; les écritures postérieures sont sous SARL-DP. Le CFF appliqué avant et après le transfert utilise la matrice de participation de l'entité porteuse au moment de la facture.

**Exigence EX-PROJ-006 :** Lorsqu'un projet passe du statut « À DÉVELOPPER » au statut « ACTIF », le système doit automatiquement générer un formulaire **FC-013** (Complétion Structure de Projet) exigeant la saisie de la structure de parts, de l'entité porteuse confirmée, et des paramètres de Centre de Coûts. Aucune opération financière n'est possible tant que ce formulaire n'est pas complété.

### 1.4 Matrice de Participation par Entité — Source de Vérité CFF

La matrice suivante est la **source de vérité absolue** pour le calcul du CFF. L'imputation du Coût Fiscal Fictif se fait **toujours** sur le % de parts dans l'**ENTREPRISE**, jamais dans le projet.

| Entité | Ahmed | Mohamed | Yazid (Lyazid) | Yamina | Règle CFF |
|--------|-------|---------|----------------|--------|-----------|
| ETS Dendani Khadidja | 25% | 25% | 25% | 25% | CFF réparti entre 4 associés |
| SARL Dendani Promotion | 25% | 25% | 25% | 25% | CFF réparti entre 4 associés |
| SARL DBPI Immobilier | 60% | 20% | 20% | **0%** | Yamina ne paie RIEN |
| SARL Omega Construction | 60% | 20% | 20% | **0%** | Yamina ne paie RIEN |
| SARL Avelis Promotion | 60% | 20% | 20% | **0%** | Yamina ne paie RIEN |
| SARL Senimar | 60% | 20% | 20% | **0%** | Yamina ne paie RIEN |
| EURL Bimha Construction | 60% | 20% | 20% | **0%** | Yamina ne paie RIEN |

**Exigence EX-MAT-001 :** Yamina est associée **uniquement** dans ETS-DK et SARL-DP (25% chacune). Dans les 5 autres entités, elle est à **0%**. Le CFF de ces 5 entités ne lui est **JAMAIS** imputé, même si elle détient des parts dans un projet rattaché à ces entités. **En revanche, Yamina paie 25% du CFF lorsque ETS-DK ou SARL-DP émettent des factures RF3**, conformément à sa participation dans ces deux entités.

**Exigence EX-MAT-002 :** Dans SARL Dendani Promotion, le % entreprise (25/25/25/25) **diffère** du % projet (60/20/20/0 pour IRENE, AUREA, etc.). Pour le CFF, le système utilise **toujours** le % entreprise. Pour la distribution des bénéfices, le système utilise **toujours** le % projet.

---

## SECTION 2 — ARCHITECTURE DES 4 RÉALITÉS FINANCIÈRES

### 2.1 Définition et Classification Obligatoire

> **Avertissement Légal :** La modélisation des flux RF2 (Réel Non Déclaré) et RF3 (Fictif Déclaré) est réalisée à des fins de traçabilité interne et de calcul de rentabilité réelle uniquement. Elle ne constitue en aucun cas une incitation à la fraude fiscale. L'utilisateur final est seul responsable de la conformité de ses déclarations vis-à-vis de l'administration fiscale.

Toute transaction financière dans le système GFI v7.0 est **obligatoirement** classifiée selon l'une des 4 Réalités Financières. Cette classification est un champ **NON NUL** (`statut_fiscal` ENUM) sur **toutes les tables financières** du système.

| Code | Nom | Définition | Exemple Concret | Traitement CFF |
|------|-----|-----------|-----------------|----------------|
| RF1 | Réel Déclaré | Flux réel enregistré dans la comptabilité officielle. | Vente d'appartement facturée + déclarée TVA. | Aucun — comptabilité normale. |
| RF2 | Réel Non Déclaré | Flux réel de cash non enregistré fiscalement. | Règlement client en espèces non facturé. | Aucun — traçage interne uniquement. |
| RF3 | Fictif Déclaré | Facture inter-groupe sans prestation réelle pour optimisation fiscale. | Dendani Promo facture Omega Construction. | **OBLIGATOIRE** — génère CFF calculé. |
| RF4 | Fictif Non Déclaré | Écriture sans base réelle ni déclaration. | Régularisation comptable interne non tracée. | Signalement — revue DAF requise. |

**Exigence EX-RF-001 :** Le champ `statut_fiscal` est **obligatoire et non nul** sur toutes les tables financières : `transactions`, `ecritures_comptables`, `factures`, `bons_commande`, `situations_travaux`, `mouvements_tresorerie`, `clotures_mensuelles`, `appels_de_fonds`, `cessions_parts`.

**Exigence EX-RF-002 :** Toute facture classifiée RF3 (inter-groupe) déclenche **automatiquement** le moteur CFF. Le système ne doit pas attendre une intervention humaine pour lancer le calcul.

---

## SECTION 3 — MOTEUR CFF — COÛT FISCAL FICTIF

### 3.1 Principe, Déclencheur et Formule

Le CFF (Coût Fiscal Fictif) est le montant réel des impôts et taxes payés par une entreprise du groupe sur des factures fictives (RF3) émises vers une autre entreprise du groupe. Il est déclenché par toute facture où `statut_fiscal = 'RF3'` et où l'émetteur ET le récepteur sont des entreprises du groupe.

**Exigence EX-CFF-001 :** Le système doit calculer le CFF automatiquement dès qu'une facture RF3 inter-groupe est détectée. Le calcul est **décomposé en étapes séquentielles** comme suit. La CNAS ne s'applique pas sur les factures inter-entreprises.

#### 3.1.1 Formule CFF Décomposée

Le calcul du CFF s'effectue en 5 étapes :

**Étape 1 — TVA :**
`TVA_montant = Montant_HT × 19%`

**Étape 2 — TAP :**
`TAP_montant = Montant_HT × taux_TAP`
(taux_TAP = 1% ou 2% selon l'activité de l'entreprise émettrice)

**Étape 3 — Base IBS :**
`IBS_base = Montant_HT − TAP_montant`
(la TAP est déductible du résultat fiscal ; pour une facture RF3 sans charge réelle en contrepartie, le bénéfice imposable est HT − TAP)

**Étape 4 — IBS :**
`IBS_montant = IBS_base × taux_IBS`
(taux_IBS = 19% ou 26% selon le régime fiscal de l'entreprise émettrice)

**Étape 5 — Timbre fiscal :**
`Timbre_montant = barème_timbre(Montant_TTC)`
(cf. Section 3.3 pour le barème applicable)

**Formule totale :**

> **CFF_TOTAL = TVA_montant + TAP_montant + IBS_montant + Timbre_montant**

**Exigence EX-CFF-002 :** Le taux IBS dépend du régime fiscal de l'entreprise émettrice. Si le régime fiscal n'est pas renseigné, le système **BLOQUE** le calcul et génère un formulaire **FC-005** pour que le DAF précise le taux applicable.

### 3.2 Triple Imputation et Règle Absolue

**Exigence EX-CFF-003 :** Le CFF est imputé selon une **triple règle** :

1. **Sur l'entreprise émettrice** : c'est elle qui déclare et paie les impôts.
2. **Sur le projet concerné** : c'est pour ce projet que la facture a été créée (centre de coûts, catégorie `DOSSIER_FISCAL_FICTIF`).
3. **Sur les associés de l'émettrice** : répartis selon le **% dans l'entreprise émettrice** (PAS le % du projet).

**Exigence EX-CFF-004 (Règle R-001) :** L'imputation CFF se fait **toujours** sur le % de parts dans l'**ENTITÉ ÉMETTRICE** de la facture RF3, **jamais** sur le % dans le projet. C'est le **Kill Test KT-02**.

**Exigence EX-CFF-005 :** Si une entreprise inconnue émet une facture RF3, le système génère un formulaire **FC-008** (Actionnariat Obligatoire) et **BLOQUE** le calcul CFF jusqu'à réponse.

### 3.3 Barème du Timbre Fiscal

Le droit de timbre sur les factures est calculé selon le barème en vigueur en Algérie (ordonnance 76-103 modifiée par les lois de finances successives). Le système doit appliquer les règles suivantes :

**Exigence EX-CFF-006 :** Le timbre fiscal sur les factures RF3 est calculé comme suit :

| Montant TTC de la facture | Droit de timbre applicable |
|--------------------------|--------------------------|
| ≤ 20 000 DA | 0 DA (exonéré) |
| > 20 000 DA | 2,5% du montant TTC, plafonné selon la réglementation en vigueur |

> **Note :** Si le barème du timbre fiscal est modifié par une loi de finances postérieure, le DAF met à jour la table `bareme_timbre` via l'interface d'administration. Le système applique automatiquement le barème en vigueur à la date de la facture. Si aucun barème n'est disponible pour une date donnée, le formulaire **FC-011** (Barème Timbre Manquant) est généré et le calcul CFF est **BLOQUÉ** jusqu'à renseignement.

---

## SECTION 4 — MOTEUR DE RÉSOLUTION D'ALIAS

### 4.1 Principe et Table Complète

> **RÈGLE ABSOLUE (R-010) :** Toute entité (projet, associé, entreprise, fournisseur) **DOIT** passer par le moteur `AliasResolver` avant tout traitement. Un alias non résolu = **BLOCAGE immédiat**.

La table ci-dessous constitue le **référentiel exhaustif** de tous les alias connus du système. Elle doit être chargée au déploiement initial et enrichie dynamiquement via `POST /api/alias`.

| Type | Alias (brut) | Canonique | Source de Détection |
|------|-------------|-----------|---------------------|
| PROJET | Les Lys, 02H, 02 Hectare, Bentala, Draria, 02Hectare, LES LYS, Dhous 2 hectare | LYS | Même terrain / adresse |
| PROJET | 05 Hectare, 5H, Ami Djamel, 05H, 05HECTARE, IRENE, Boumerdes | IRENE | Même localisation Boumerdès |
| PROJET | JASMIN, Sahel, Les Jasmins | JASMIN | Nom historique |
| PROJET | EDEN, FOES | EDEN | Nom historique |
| PROJET | OPERA, Ouled Fayet, Les Jardins de l'Opera, Jardin de l'Opéra | OPERA | Localisation |
| PROJET | MAGNOLIA, Les Magnolia | MAGNOLIA | Nom commercial |
| PROJET | AUREA, Cheraga, Chéraga | AUREA | Localisation |
| PROJET | ASTERIA, El Achour | ASTERIA | Localisation |
| PROJET | MOSQUEE, Taoura, Taourga | MOSQUEE | Localisation |
| PROJET | AVELIS DRIVE, Avelis Drive | AVELIS-DRIVE | Nom commercial |
| PROJET | ALLO MAISON, Allo Maison | ALLO-MAISON | Nom commercial |
| ASSOCIÉ | Ahmed, Hmed, A.Dendani, AHMED DENDANI, A.D. | DENDANI Ahmed | Alias fréquents comptes 455 |
| ASSOCIÉ | Mohamed, Moh, Mohammed, M.Dendani, Mouh | DENDANI Mohamed | Alias fréquents |
| ASSOCIÉ | Yazid, Lyazid, Bouabdellah, Lyazid Bouabdellah, Y.Bouabdellah | DENDANI Yazid (Lyazid) | **CRITIQUE** : Lyazid ET Yazid = même personne |
| ASSOCIÉ | Yamina, Y.Ait Benamara, Yamina AIT, Ait Benamara | DENDANI Yamina (Ait Benamara) | Nom d'épouse |
| ASSOCIÉ | Boumerdassi, BOUMERDASSI Mustapha | BOUMERDASSI Mustapha | Associé projet |
| ASSOCIÉ | Amirat, AMIRAT Brahim | AMIRAT Brahim | Associé projet |
| ASSOCIÉ | Laid, DENDANI Laid | DENDANI Laid | Associé projet T5000 |
| ASSOCIÉ | Moukhtari, MOUKHTARI Tarek | MOUKHTARI Tarek | Associé projet |
| ASSOCIÉ | Moukhtari Amine, MOUKHTARI Amine | MOUKHTARI Amine | Associé projet |
| ENTREPRISE | AMENFORT, SARL AMENFORT, Amenfort Beton, Amenfort Béton | SARL AMENFORT Béton (dissoute) | Entreprise origine du groupe |
| ENTREPRISE | BAYTI, Bayti, EURL BAYTI, Allo Maison, BAYTI ALLO MAISON | EURL BAYTI / ALLO MAISON | Marque commerciale |
| ENTREPRISE | Dendani Promo, SARL Dendani Promotion, Dendani Promotion | SARL Dendani Promotion | Entité active |
| ENTREPRISE | DBPI, SARL DBPI, DBPI Immobilier | SARL DBPI Immobilier | Entité active |
| ENTREPRISE | Omega, SARL Omega, Omega Construction | SARL Omega Construction | Entité active |
| ENTREPRISE | Bimha, EURL Bimha, Bimha Construction | EURL Bimha Construction | Entité active |
| ENTREPRISE | Senimar, SARL Senimar | SARL Senimar | Entité active |
| ENTREPRISE | Avelis, SARL Avelis, Avelis Promotion | SARL Avelis Promotion | Entité active |

**Exigence EX-ALIAS-001 :** Le moteur `AliasResolver` doit être appelé **systématiquement** sur chaque saisie, importation, et ingestion. Aucune donnée ne doit entrer dans le système sans passer par la résolution d'alias.

**Exigence EX-ALIAS-002 :** Si un alias n'est pas trouvé dans la table et que le score de confiance est inférieur à 50%, le système génère un formulaire **FC-001** (Identification Associé) ou **FC-003** (Rattachement Projet) et **BLOQUE** l'opération. Le système ne doit **jamais** inventer une affectation (zéro hallucination).

---

## SECTION 5 — LES 39 SOCLES TECHNIQUES ET FONCTIONNELS

Le système GFI v7.0 est construit sur **39 Socles** (ou piliers) qui garantissent sa robustesse, son intelligence et sa conformité aux exigences métier. Chaque Socle est une capacité fondamentale et non négociable.

| N° | Socle | Description | Criticité |
|----|-------|-------------|-----------|
| S-01 | **Moteur 4 Réalités Financières** | Classification obligatoire de tout flux en RF1, RF2, RF3, ou RF4. | BLOQUANTE |
| S-02 | **Moteur CFF (Coût Fiscal Fictif)** | Calcul décomposé et triple imputation automatiques du CFF sur les factures RF3. | BLOQUANTE |
| S-03 | **Moteur de Résolution d'Alias** | Résolution obligatoire des alias (projets, associés, etc.) avant toute opération. | BLOQUANTE |
| S-04 | **Double Computation à la Clôture** | Deux algorithmes recalculent la TNM. Tout écart > 0.00 DA bloque la clôture. | BLOQUANTE |
| S-05 | **Immutabilité du Journal d'Audit** | Piste d'audit (ajout seul, sans modification ni suppression) traçant chaque action. | BLOQUANTE |
| S-06 | **Soft Delete Obligatoire** | Aucune suppression physique (`DELETE`) sur les tables financières. Uniquement `is_deleted=true`. | BLOQUANTE |
| S-07 | **Contrôle d'Accès Basé sur les Rôles (RBAC)** | 15 rôles granulaires avec permissions fines (lecture/écriture/validation). | BLOQUANTE |
| S-08 | **Séparation des Tâches (SoD)** | Ex: la personne qui commande ne peut pas être celle qui réceptionne. | BLOQUANTE |
| S-09 | **Moteur de Workflow Conditionnel** | Chaque étape est conditionnée par la précédente. Pas de saut d'étape possible. | BLOQUANTE |
| S-10 | **Pipeline d'Ingestion en 7 Couches** | OCR, déduplication, classification, validation… pour tout document entrant. | BLOQUANTE |
| S-11 | **Moteur de Détection Intelligente** | 15+ patterns pour découvrir automatiquement les entités et flux depuis la base brute. | BLOQUANTE |
| S-12 | **Génération de Formulaires de Complétion** | Si une info manque, le système génère un formulaire bloquant (FC-xxx). Zéro hallucination. | BLOQUANTE |
| S-13 | **Centre de Coûts à 6 Catégories** | Vérité financière absolue du projet, consolidant tous les flux (RF1+RF2+RF3+RF4). | BLOQUANTE |
| S-14 | **Gestion Multi-Entités Cloisonnée** | `company_id` obligatoire partout. Séquences, journaux, et banques séparés. | BLOQUANTE |
| S-15 | **Rapprochement Bancaire Intelligent** | NLP pour analyse des libellés, ML pour auto-apprentissage des affectations. | HAUTE |
| S-16 | **Génération Automatique des Écritures SCF** | 100% des écritures comptables sont générées depuis les pièces justificatives. | HAUTE |
| S-17 | **Blocage Intelligent sur Appels de Fonds** | Non-couverture d'un appel de fonds gèle le CCA et bloque les cessions de parts. | BLOQUANTE |
| S-18 | **Sécurisation RF2 Avant Engagement ADV** | Aucune promesse de vente n'est générée tant que la partie RF2 n'est pas sécurisée. | BLOQUANTE |
| S-19 | **Moteur de Pricing Dynamique ADV** | Calcul automatique du prix de vente avec gestion des bonus/remises et workflow de validation. | HAUTE |
| S-20 | **Moteur de Bonus/Malus SPI** | Impact direct et automatique du Score de Performance Individuel sur la paie. | HAUTE |
| S-21 | **Gestion Documentaire Intégrée (GED)** | Chaque document est tracé, versionné, et rattaché à un dossier. Zéro document hors système. | HAUTE |
| S-22 | **Recherche Sémantique Full-Text** | ElasticSearch sur 100% du patrimoine documentaire (y compris scans traités par OCR). | HAUTE |
| S-23 | **Dashboards Passifs et Actifs** | L'information pertinente est poussée à l'utilisateur, qui peut agir directement. | HAUTE |
| S-24 | **Centre de Notifications Global** | Agrégation de toutes les alertes, tâches et demandes de validation pour l'utilisateur. | HAUTE |
| S-25 | **AI QA Engine (Tests Automatisés)** | Les Kill Tests et 200+ tests fonctionnels sont exécutés en continu. | BLOQUANTE |
| S-26 | **Authentification Forte (MFA/SSO)** | MFA obligatoire pour les rôles à haute responsabilité. | BLOQUANTE |
| S-27 | **Sécurité au Niveau de la Ligne (RLS)** | Garantie au niveau de la BDD que chaque utilisateur ne voit que ses données. | HAUTE |
| S-28 | **API REST Sécurisée et Documentée** | Tous les endpoints sont protégés par le RBAC et documentés (Swagger/OpenAPI). | HAUTE |
| S-29 | **Tâches Asynchrones pour les Traitements Lourds** | Clôture, ingestion, et rapports sont exécutés en arrière-plan (Celery/Redis). | HAUTE |
| S-30 | **Applications Mobiles Dédiées** | Apps natives (Stock, Chantier, Réception) synchronisées en temps réel. | MOYENNE |
| S-31 | **Moteur d'Allocation des Charges Communes (SSP)** | Répartition des frais généraux selon des clés paramétrables. | HAUTE |
| S-32 | **Gestion des Échéanciers Complexes** | Gestion des paiements par paliers (crédit) ou récurrents (fonds propres). | HAUTE |
| S-33 | **Ventilation Automatique des Chèques Globaux** | Un chèque notaire est automatiquement ventilé sur les dossiers ADV concernés. | HAUTE |
| S-34 | **Calcul Automatique des Déclarations Fiscales** | Préparation des G50, CNAS, CACOBATPH, etc. | HAUTE |
| S-35 | **Moteur Méta-IA Auto-Génératif** | Capacité du système à proposer et générer de nouveaux modules en sandbox. | VISION |
| S-36 | **Intégrité des Données par Hash** | Chaque clôture mensuelle est scellée par un hash SHA-256. | BLOQUANTE |
| S-37 | **Gestion du Droit de Préemption** | Workflow automatique de notification et de priorité lors des cessions de parts. | HAUTE |
| S-38 | **Traçabilité des Flux Inter-Projets** | Mouvements sur les comptes 580 générant une double écriture (débit/crédit). | HAUTE |
| S-39 | **Double Règle sur Retraits CCA** | Le retrait est (1) limité à 50% du solde individuel ET (2) possible seulement si le solde global de l'entreprise est positif. | BLOQUANTE |


---

# PARTIE B — MODULES OPÉRATIONNELS CENTRAUX

---

## SECTION 6 — MODULE FINANCE & COMPTABILITÉ (SCF)

### 6.1 Principe Fondamental : Zéro Saisie Manuelle

> **RÈGLE ABSOLUE (R-002) :** Aucune écriture comptable ne doit être saisie manuellement. 100% des écritures doivent être générées automatiquement par le système à partir d'une pièce justificative (facture, bon de commande, situation de travaux, mouvement de trésorerie, etc.).

Le module Finance & Comptabilité est le réceptacle final des flux financiers. Il ne crée pas d'information, il la reçoit et la structure selon le Plan Comptable SCF algérien.

### 6.2 Plan Comptable SCF et Journaux Multi-Entités

**Exigence EX-SCF-001 :** Le système doit intégrer le plan comptable SCF algérien par défaut. Il doit permettre l'ajout de sous-comptes spécifiques par entité juridique.

**Exigence EX-SCF-002 :** Chaque entité juridique (`company_id`) possède son propre jeu de journaux comptables (Achats, Ventes, Banque, Caisse, OD). Les séquences de numérotation des pièces sont **strictement cloisonnées** par entité.

### 6.3 Génération Automatique des Écritures (Socle S-16)

Le système génère les écritures comptables en fonction du type de pièce et de sa classification RF.

| Pièce Source | Déclencheur | Écriture Comptable Générée (Exemple Simplifié) |
|-------------|-------------|------------------------------------------------|
| Facture Achat (RF1) | Validation de la facture | D 6xx (Charge) + D 4456 (TVA Déductible) / C 401 (Fournisseur) |
| Facture Vente (RF1) | Validation de la facture | D 411 (Client) / C 70x (Produit) + C 4457 (TVA Collectée) |
| Paiement Fournisseur | Rapprochement bancaire | D 401 (Fournisseur) / C 512 (Banque) |
| Encaissement Client | Rapprochement bancaire | D 512 (Banque) / C 411 (Client) |
| Facture RF3 (Fictive) | Validation de la facture | D 411 (Client Interco) / C 70x (Produit) + C 4457 (TVA Collectée) |
| Note de Frais | Validation par Manager | D 625 (Déplacements) / C 421 (Personnel - à payer) |

### 6.4 Rapprochement Bancaire Intelligent (Socle S-15)

**Exigence EX-SCF-003 :** Le système doit ingérer les relevés bancaires (format CFONB ou CSV) et proposer un rapprochement automatique. Il utilise le NLP pour analyser les libellés et le Machine Learning pour apprendre des validations manuelles précédentes. Le seuil d'acceptation automatique du rapprochement est fixé à un score de confiance ≥ 95%. En dessous, le rapprochement est proposé mais requiert une validation manuelle.

**Exigence EX-SCF-004 :** Un mouvement bancaire non rapproché génère une alerte dans le dashboard du comptable. Le système doit proposer les pièces correspondantes (factures, chèques) avec un score de confiance.

### 6.5 Déclarations Fiscales et Sociales (G50, CNAS, CACOBATPH)

**Exigence EX-SCF-005 :** Le système doit générer automatiquement les états préparatoires pour les déclarations fiscales et sociales, en se basant sur les écritures validées pour la période : G50 (mensuelle) avec calcul automatique de la TVA à décaisser (TVA collectée − TVA déductible), de la TAP, et de l'IBS ; CNAS (trimestrielle) avec calcul des cotisations sur la base des salaires bruts issus du module Paie ; CACOBATPH (annuelle) avec calcul des cotisations sur la base des contrats et situations de travaux des sous-traitants du BTP ; Bilan (annuel) avec génération du bilan, du compte de résultat, et des annexes au format SCF.

**Exigence EX-SCF-006 :** Le système doit gérer les différents régimes fiscaux (réel, simplifié) et les taux applicables par entité (IBS 19% ou 26%, TAP 1% ou 2%). Si un taux est manquant, le formulaire **FC-005** est déclenché.

---

## SECTION 7 — MODULE TRÉSORERIE & COMPTES COURANTS ASSOCIÉS

### 7.1 Gestion des Comptes Courants Associés (CCA)

Chaque associé fondateur (`associé_id` 1 à 4) possède un Compte Courant d'Associé (CCA) unique, qui trace ses apports et ses retraits. Le CCA est la source de vérité pour la rémunération des associés.

**Exigence EX-CCA-001 :** Le système doit créer automatiquement un CCA pour chacun des 4 associés fondateurs. Le solde initial est de 0.00 DA.

**Exigence EX-CCA-002 :** Tout mouvement sur un CCA doit être tracé avec une pièce justificative (virement, chèque, reçu espèces, PV de distribution de dividendes).

### 7.2 Double Règle de Retrait sur CCA (Socle S-39)

> **RÈGLE ABSOLUE (R-003) :** Un associé ne peut retirer des fonds de son CCA que si les deux conditions suivantes sont remplies :
> 1. Le montant du retrait est inférieur ou égal à **50%** du solde individuel de l'associé.
> 2. Le solde **global** de tous les CCA de l'entreprise est **positif**.

**Exigence EX-CCA-003 (Kill Test KT-08) :** Une tentative de retrait de 6M DA par un associé ayant un solde de 10M DA doit être **BLOQUÉE**. Le montant maximum autorisé est de 5M DA (Condition 1). Une tentative de retrait de 1M DA par un associé ayant 3M DA de solde doit être **BLOQUÉE** si le solde global des CCA de l'entreprise est négatif (Condition 2).

### 7.3 Clôture Mensuelle de Trésorerie (TNM)

La clôture mensuelle est un processus **irréversible** qui scelle les comptes pour une période donnée. Elle se déroule en 7 étapes séquentielles.

| Étape | Action | Condition de Passage | Action si Échec |
|-------|--------|---------------------|-----------------|
| 1 | **Vérification Complétude** | 100% des mouvements bancaires sont rapprochés. | **BLOCAGE** + Liste des mouvements non rapprochés. |
| 2 | **Double Computation (Socle S-04)** | `Algo1(Solde Final)` == `Algo2(Solde Initial + Mouvements)`. | **BLOCAGE** + Alerte DAF (écart > 0.00 DA). |
| 3 | **Validation DAF** | Le DAF valide la clôture via son dashboard. | La clôture reste en attente. |
| 4 | **Génération Rapport TNM** | Le système génère le rapport de trésorerie mensuel. | Erreur de génération. |
| 5 | **Scellement par Hash (Socle S-36)** | Un hash SHA-256 est calculé sur le rapport TNM. | Erreur de calcul. |
| 6 | **Archivage** | Le rapport et son hash sont stockés dans la GED. | Erreur de stockage. |
| 7 | **Verrouillage Période** | La période est marquée comme `CLOTURÉE`. Aucune modification n'est plus possible. | Erreur de verrouillage. |

**Exigence EX-CCA-004 (Kill Test KT-04) :** Toute tentative de modifier une écriture dans une période clôturée doit être **BLOQUÉE** avec une erreur HTTP 403 Forbidden.

---

## SECTION 8 — MODULE ADV — VENTES IMMOBILIÈRES

Le module ADV est le cœur du processus de vente immobilière. Il orchestre le cycle de vie d'un dossier client, de la réservation à la livraison, en appliquant rigoureusement la séparation des flux RF1 (déclarés) et RF2 (non déclarés).

### 8.1 EDD — État de Disponibilité Descriptif

L'EDD est la source de vérité unique pour l'état des lots immobiliers. Chaque lot est tracé avec un statut temps réel.

| Statut | Description | Action Permise |
|--------|-------------|---------------|
| `DISPONIBLE` | Le lot est libre à la vente. | Créer un devis, réserver. |
| `VERROUILLÉ` | Un commercial a posé une option temporaire (15 min). | Attendre ou forcer la libération (Manager). |
| `RÉSERVÉ` | Un paiement SPOT a été encaissé. | Lancer le processus d'engagement. |
| `ENGAGÉ` | Le contrat de vente est signé. | Suivre les paiements et les déblocages. |
| `VENDU` | 100% du montant a été payé et les clés remises. | Clôturer le dossier. |
| `INDISPONIBLE` | Le lot est retiré de la vente (technique, juridique). | Aucune. |

**Exigence EX-ADV-001 :** Toute tentative de réserver un lot qui n'est pas `DISPONIBLE` doit être **BLOQUÉE** en temps réel.

### 8.2 Sécurisation RF2 Avant Engagement (Socle S-18)

> **RÈGLE ABSOLUE (R-004) :** Aucun document engageant (Promesse de Vente, Décision d'Affectation avec montants) ne peut être généré tant que 100% du montant RF2 n'a pas été encaissé en espèces.

**Exigence EX-ADV-002 (Kill Test KT-07) :** Une tentative de forcer le statut du dossier à `ENGAGÉ` alors que le `statut_rf2` est `EN_ATTENTE` doit être **BLOQUÉE**. Le workflow ne peut pas être court-circuité.

### 8.3 Les 3 Workflows de Paiement

Le système gère 3 scénarios de paiement distincts.

**8.3.1 Paiement SPOT :** Le paiement SPOT est le versement initial qui réserve le lot. Il peut être RF1 (chèque) ou RF2 (espèces).

**8.3.2 Paiement par Crédit Bancaire (VSP) :** C'est le workflow le plus complexe, impliquant la banque, le notaire, et des déblocages par paliers basés sur l'avancement des travaux (validé par des rapports d'expert).

**Exigence EX-ADV-003 :** Le système doit générer automatiquement les demandes de déblocage à la banque dès qu'un rapport d'expert validé est uploadé pour un palier donné.

**8.3.3 Paiement par Fonds Propres :** Le client paie par échéances (mensuelles ou bimestrielles) via des chèques. Le système génère et suit l'échéancier.

**Exigence EX-ADV-004 :** Un retard de paiement de plus de 30 jours sur une échéance de fonds propres marque automatiquement le dossier en `DÉFAUT_PAIEMENT` et déclenche le workflow de relance.

### 8.4 Workflow de Relance Impayés

**Exigence EX-ADV-005 :** Le workflow de relance automatique pour les impayés est le suivant : J+1 de l'échéance — notification automatique au client et au gestionnaire ADV ; J+7 — première relance formelle par email ; J+14 — deuxième relance formelle par email avec mise en demeure ; J+30 — le dossier passe en statut `DÉFAUT_PAIEMENT` et est escaladé au service juridique.

### 8.5 Gestion Documentaire ADV

Le module ADV génère et suit tous les documents nécessaires au processus de vente.

| Document | Moment de Génération | Contenu Clé |
|----------|---------------------|-------------|
| Devis | Phase CRM | Prix de vente, conditions. |
| Attestation de Réservation | Après paiement SPOT | Si RF2 non sécurisé, généré **SANS MONTANTS**. |
| Décision d'Affectation | Après engagement (RF2 sécurisé) | Prix de vente **RF1 uniquement**. |
| Échéancier de Paiement | Après engagement | Détail des paliers ou des mensualités. |
| Demande de Déblocage | Sur validation rapport expert | Montant du palier, rapport en pièce jointe. |
| PV de Remise des Clés | À la livraison | Document finalisant la vente. |

**Exigence EX-ADV-006 :** Le système doit gérer un workflow de relance automatique pour les documents manquants du client (CIN, fiches de paie, etc.) avec escalade au manager ADV après 14 jours.

### 8.6 Barème de Commissions Commerciales

**Exigence EX-ADV-007 :** Le système doit intégrer un barème de commissions commerciales paramétrable par le DAF. Le barème définit le taux de commission (en % du prix de vente RF1), les conditions de déclenchement (signature de l'engagement, encaissement total, ou remise des clés), les plafonds éventuels par agent ou par période, et les règles de partage en cas de co-vente. Le barème est stocké dans la table `bareme_commissions` et versé automatiquement au module Paie (Section 9) pour calcul de la rémunération variable. Si aucun barème n'est défini pour un projet, le formulaire **FC-014** (Barème Commissions Manquant) est généré au moment de la première vente.

---

## SECTION 9 — MODULE RH, PAIE & SPI

### 9.1 Grille Salariale et Contrats

**Exigence EX-RH-001 :** Le système doit intégrer la grille salariale du groupe, avec les catégories, échelons, et salaires de base correspondants. Chaque employé est rattaché à un poste de la grille.

### 9.2 Moteur de Paie et Déclarations CNAS

**Exigence EX-RH-002 :** Le moteur de paie calcule le salaire net à partir du brut, en déduisant l'IRG et les cotisations sociales. Il génère les fiches de paie en PDF et les écritures comptables correspondantes.

**Exigence EX-RH-003 :** Le système prépare automatiquement la déclaration CNAS trimestrielle pour chaque entité juridique.

### 9.3 SPI v2.0 — Score de Performance Individuel (Socle S-20)

Le SPI est un score sur 100 qui mesure la performance de chaque employé. Il est calculé mensuellement et a un impact direct sur la rémunération variable.

> **Formule SPI** = 50% (Objectifs Quantitatifs) + 30% (Qualité & Délais) + 20% (Discipline & Comportement)

**Exigence EX-RH-004 :** Le système doit calculer le SPI chaque mois et appliquer le bonus/malus correspondant sur la paie du mois M+1. Le workflow de validation du SPI par le N+1 et le DAF doit être implémenté.

---

## SECTION 10 — MODULE GESTION DE PROJETS & CHANTIERS

### 10.1 Suivi de l'Avancement Physique

**Exigence EX-PROJ-101 :** Le système doit permettre aux chefs de projet de mettre à jour l'avancement de chaque tâche du planning (en %). Cet avancement est la base pour les déblocages de fonds en VSP.

### 10.2 Situations de Travaux Sous-Traitants

**Exigence EX-PROJ-102 :** Le module gère les situations de travaux des sous-traitants. La validation d'une situation génère automatiquement une dette envers le sous-traitant et une charge dans le Centre de Coûts du projet.

### 10.3 Performance des Sous-Traitants

**Exigence EX-PROJ-103 :** Chaque sous-traitant est noté sur la qualité, le respect des délais et la sécurité. Un score de performance est calculé et utilisé pour prioriser les sous-traitants lors des futurs appels d'offres.

---

## SECTION 11 — MODULE ACHATS, STOCK & LOGISTIQUE

### 11.1 Cycle d'Approvisionnement

**Exigence EX-ACH-001 :** Le module gère le cycle complet : demande d'achat, appel d'offres, bon de commande, bon de réception, facture fournisseur. Le workflow de validation (maker/checker) est obligatoire (Socle S-08).

### 11.2 Gestion de l'Inventaire

**Exigence EX-ACH-002 :** Le système gère l'inventaire multi-entrepôts et multi-projets. Chaque entrée et sortie de stock est tracée et impacte la valorisation du stock en temps réel (méthode CUMP par défaut, FIFO paramétrable).

### 11.3 Applications Mobiles (Socle S-30)

**Exigence EX-ACH-003 :** Des applications mobiles dédiées sont requises pour la Gestion de Stock (permet aux magasiniers de scanner les articles par QR code et d'enregistrer les entrées/sorties) et la Réception Chantier (permet aux chefs de chantier de valider la réception des matériaux directement sur site).


---

# PARTIE C — MODULES AVANCÉS ET AUTOMATISATION

---

## SECTION 12 — MODULE CENTRE DE COÛTS — LA VÉRITÉ ABSOLUE

### 12.1 Principe : Le Miroir de la Réalité Financière

Le Centre de Coûts (CC) est le module le plus critique du système. Il est le miroir exact de la réalité financière du groupe, consolidant tous les flux (RF1, RF2, RF3, RF4) pour donner une vision de la rentabilité réelle par projet, par entreprise, et par associé.

### 12.2 Hiérarchie à 6 Niveaux

Le CC est structuré en 6 niveaux hiérarchiques, du plus global au plus détaillé : Niveau 1 — Groupe Dendani (consolidation de tout) ; Niveau 2 — Entité Juridique (ex: SARL Dendani Promotion) ; Niveau 3 — Projet (ex: Projet IRENE) ; Niveau 4 — Lot / Unité (ex: Appartement F4 Bloc A N°12) ; Niveau 5 — Catégorie de Coût (ex: 01-ETUDES_ET_CONCEPTION) ; Niveau 6 — Sous-catégorie de Coût (ex: 01.1-Architecte).

### 12.3 Les 12 Catégories de Coûts

Toute dépense est obligatoirement classée dans l'une de ces 12 catégories.

| Code | Catégorie | Description |
|------|-----------|-------------|
| 01 | ETUDES_ET_CONCEPTION | Architectes, BET, études de sol… |
| 02 | TERRAIN_ET_VRD | Achat terrain, viabilisation, aménagements extérieurs… |
| 03 | GROS_OEUVRE | Fondations, structure béton, maçonnerie… |
| 04 | CORPS_ETAT_SECONDAIRES | Plomberie, électricité, plâtrerie, peinture… |
| 05 | EQUIPEMENTS | Ascenseurs, cuisines équipées, climatisation… |
| 06 | FRAIS_DE_CHANTIER | Grue, sécurité, nettoyage, chef de chantier… |
| 07 | FRAIS_FINANCIERS | Frais bancaires, intérêts d'emprunt… |
| 08 | IMPOTS_ET_TAXES | Permis de construire, TVA, IBS, TAP… |
| 09 | FRAIS_COMMERCIAUX | Publicité, commissions agents, showroom… |
| 10 | FRAIS_ADMINISTRATIFS | Salaires siège, loyer bureau, fournitures… (ventilés) |
| 11 | DOSSIER_FISCAL_FICTIF | **Uniquement pour les CFF (Coûts Fiscaux Fictifs).** |
| 12 | IMPREVUS | Provisions pour risques et aléas. |

### 12.4 Les 16 Types de Flux Alimentant le CC

Le CC est alimenté automatiquement par 16 types de flux : (1) Encaissements Clients (RF1 & RF2), (2) Décaissements Fournisseurs (RF1), (3) Charges de Personnel (Paie), (4) Situations de Travaux Sous-Traitants, (5) Coûts Fiscaux Fictifs (CFF), (6) Impôts et Taxes (G50, etc.), (7) Frais Financiers (bancaires), (8) Consommation de Stock (sortie magasin), (9) Charges Communes Ventilées (SSP), (10) Flux Inter-Projets (compte 580), (11) Apports en Capital, (12) Apports en Compte Courant Associé, (13) Retraits en Compte Courant Associé, (14) Prélèvements en Nature Associés (valorisés), (15) Amortissements, (16) Provisions pour Risques.

### 12.5 Les 5 Axes de Consolidation

Le système doit permettre de consolider et d'analyser le CC selon 5 axes distincts : (1) Axe Ascendant — de la sous-catégorie jusqu'au groupe ; (2) Axe par Associé — vision de la rentabilité par associé (quote-part) ; (3) Axe par Réalité Financière — isoler les flux RF1, RF2, RF3, RF4 ; (4) Axe Inter-Projets — analyser les flux entre projets ; (5) Axe Temporel — comparer les coûts et revenus sur différentes périodes.

### 12.6 Règle de Double Pourcentage

> **RÈGLE ABSOLUE (R-005) :** Le système doit systématiquement faire la distinction entre le % de parts dans l'entreprise et le % de parts dans le projet. CFF et charges de structure sont imputés selon le % ENTREPRISE. Bénéfices et charges directes projet sont imputés selon le % PROJET.

**Exigence EX-CC-001 (Test Décisif #1) :** Pour le projet IRENE (porté par Dendani Promo), le CFF est imputé à 25% sur Ahmed (son % dans l'entreprise), mais les bénéfices lui reviennent à 60% (son % dans le projet).

### 12.7 Les 10 Niveaux de Vérification Automatique

Le CC est soumis à 10 niveaux de contrôle automatique : (1) Somme des sous-catégories = Total catégorie ; (2) Somme des catégories = Total dépenses projet ; (3) Total dépenses + Marge = Total revenus ; (4) Rapprochement CC vs Trésorerie ; (5) Rapprochement CC vs Comptabilité (charges) ; (6) Test Actif = Passif (écart doit être 0.00 DA) ; (7) Cohérence des flux inter-projets (débit = crédit) ; (8) Validation des clés de ventilation (total = 100%) ; (9) Contrôle de la quote-part de chaque associé ; (10) Détection d'anomalies (ex: dépense sans catégorie).

---

## SECTION 13 — WORKFLOWS MÉTIER SPÉCIFIQUES DENDANI

Le Groupe Dendani a un historique financier complexe qui doit être assaini et tracé dans le système. Les 8 workflows suivants sont des cas métier spécifiques que le système doit implémenter.

### 13.1 WF-01 : Origine du Capital — AMENFORT Béton

**Exigence EX-WF-001 :** Le système doit tracer l'origine du capital fondateur du groupe, provenant de la dissolution de SARL AMENFORT Béton. Les fonds ont été transférés vers ETS Dendani Khadidja pour financer les premiers projets (JASMIN, EDEN). Le système doit créer les écritures d'apport en capital correspondantes et les rattacher au CC des projets concernés.

### 13.2 WF-02 : Avance GACEB 120M DA (Matériel AMENFORT)

**Exigence EX-WF-002 :** GACEB Abderazak a reçu 120M DA de matériel provenant d'AMENFORT (dissoute). Cette avance en nature est déduite progressivement des situations de travaux GACEB sur le projet EDEN. Le système doit : (1) créer une créance de 120M DA sur GACEB, (2) à chaque situation de travaux GACEB sur EDEN, déduire automatiquement la part correspondante, (3) suivre le solde restant de la créance jusqu'à apurement complet, (4) imputer la charge sur le CC d'EDEN, catégorie 03-GROS_OEUVRE.

### 13.3 WF-03 : Véhicules Cédés à GACEB

**Exigence EX-WF-003 :** Plusieurs véhicules ont été cédés à GACEB en déduction de ses situations de travaux.

| Véhicule | Valeur | Bénéficiaire Initial | Projet Déduction |
|----------|--------|---------------------|------------------|
| Range Rover | 4 000 000 DA | Ahmed | EDEN |
| Passat | 6 500 000 DA | Yazid (Lyazid) | EDEN |
| Autres véhicules | À extraire de la base | À déterminer | À déterminer |

Le système doit tracer : achat du véhicule → immatriculation au nom de l'associé → cession à GACEB → déduction de la situation de travaux → imputation au CC du projet.

### 13.4 WF-04 : Prélèvements d'Appartements JASMIN

**Exigence EX-WF-004 :** Chaque associé a prélevé des appartements sur le projet JASMIN. Ces prélèvements doivent être valorisés et déduits de la quote-part de l'associé dans le CC du projet.

| Associé | Appartement(s) | Valeur Estimée | Traitement CC |
|---------|---------------|----------------|---------------|
| Ahmed | F3 + F2 | 25 000 000 DA | Déduction quote-part Ahmed dans CC JASMIN |
| Mohamed | F3 | 25 000 000 DA | Déduction quote-part Mohamed dans CC JASMIN |
| Yazid (Lyazid) | F3 | 25 000 000 DA | Déduction quote-part Yazid dans CC JASMIN |

### 13.5 WF-05 : Appartements JASMIN Donnés à GACEB

**Exigence EX-WF-005 :** Des appartements du projet JASMIN ont été cédés à GACEB en avance sur la fourniture de béton pour le projet JARDIN DE L'OPÉRA. Le système doit tracer ce flux inter-projets (JASMIN → OPÉRA) et l'imputer correctement dans les deux CC.

### 13.6 WF-06 : Aménagement Oued JASMIN (20M DA)

**Exigence EX-WF-006 :** Les travaux d'aménagement de l'oued sur le site JASMIN (20M DA) doivent être imputés au CC JASMIN, catégorie 02-TERRAIN_ET_VRD.

### 13.7 WF-07 : Bureau BBZ — Charge Commune Groupe

**Exigence EX-WF-007 :** Le bureau BBZ (Bab Ezzouar) est le siège administratif du groupe. Ses charges (loyer, électricité, salaires siège) sont des **charges communes** qui doivent être ventilées sur tous les projets actifs selon une clé de répartition paramétrable (Socle S-31).

### 13.8 WF-08 : Factures RF3 Inter-Groupe

**Exigence EX-WF-008 :** Le système doit détecter et traiter automatiquement les factures RF3 émises entre les entités du groupe (ex: AMENFORT → ETS-DK, BAYTI → ETS-DK). Chaque facture RF3 déclenche le moteur CFF (Section 3).

---

## SECTION 14 — MODULE D'INGESTION AUTOMATIQUE (PIPELINE 7 COUCHES)

### 14.1 Principe : Ingérer 400 Go+ de Documents

Le système doit être capable d'ingérer la totalité du patrimoine documentaire du groupe (400 Go+, 10 000+ documents) via un pipeline automatisé en 7 couches.

### 14.2 Les 7 Couches du Pipeline

| Couche | Nom | Action | Résultat |
|--------|-----|--------|---------|
| C1 | Réception | Le document est uploadé ou scanné. | Fichier brut stocké. |
| C2 | OCR | Si le document est un scan/image, extraction du texte par OCR. | Texte brut extrait. |
| C3 | Déduplication | Vérification par hash (SHA-256) si le document existe déjà. | Doublon rejeté ou nouveau document accepté. |
| C4 | Classification | Le système classe le document (facture, contrat, PV, relevé…). | Type de document identifié. |
| C5 | Extraction | Extraction des données clés (montant, date, fournisseur, projet…). | Métadonnées extraites. |
| C6 | Résolution d'Alias | Passage par le moteur `AliasResolver` (Section 4). | Entités résolues. |
| C7 | Stockage & Indexation | Stockage dans la GED et indexation dans ElasticSearch. | Document disponible et cherchable. |

**Exigence EX-ING-001 (Kill Test KT-01) :** L'ingestion d'un lot de factures déjà présentes dans le système doit être **BLOQUÉE** par la couche C3 (déduplication).

**Exigence EX-ING-002 :** Si la couche C5 ne parvient pas à extraire un champ obligatoire (ex: montant, date), le document est placé en file d'attente `À_COMPLÉTER` et un formulaire de complétion est généré.

---

## SECTION 15 — MODULE GED & INDEXATION SÉMANTIQUE

### 15.1 Arborescence Normalisée

**Exigence EX-GED-001 :** Chaque document est stocké dans une arborescence normalisée : `/{Entité}/{Projet}/{Année}/{Type_Document}/{Fichier}`. Le système crée automatiquement les répertoires manquants.

### 15.2 Indexation Full-Text (Socle S-22)

**Exigence EX-GED-002 :** 100% du patrimoine documentaire (y compris les scans traités par OCR) est indexé dans ElasticSearch. La recherche full-text permet de retrouver un document par n'importe quel mot clé contenu dans le texte.

### 15.3 Traçabilité et Versioning

**Exigence EX-GED-003 :** Chaque document est versionné. Toute modification crée une nouvelle version. L'historique des versions est conservé indéfiniment.

---

## SECTION 16 — MOTEUR DE DÉTECTION INTELLIGENTE AUTONOME

### 16.1 Principe : Le Système Découvre Seul

Le moteur de détection ne reçoit aucune instruction spécifique sur où chercher. Il analyse la base de données brute (400 Go) et découvre automatiquement les entités, les flux, et les anomalies.

### 16.2 Les 15 Patterns de Détection

| # | Pattern | Description | Action |
|---|---------|-------------|--------|
| 1 | Détection d'entreprises | Identifier toutes les entités juridiques dans les documents. | Créer automatiquement les fiches entreprise. |
| 2 | Détection d'associés | Identifier les noms d'associés et résoudre les alias. | Créer les fiches associé et les CCA. |
| 3 | Détection de projets | Identifier les projets et résoudre les alias. | Créer les fiches projet et les CC. |
| 4 | Détection de factures RF3 | Identifier les factures inter-groupe sans prestation réelle. | Déclencher le moteur CFF. |
| 5 | Détection de flux RF2 | Identifier les mouvements en espèces non déclarés. | Tracer dans le CC interne. |
| 6 | Détection de doublons | Identifier les documents et écritures en double. | Signaler et proposer la fusion. |
| 7 | Détection de flux inter-projets | Identifier les transferts entre projets via la caisse commune. | Créer les écritures croisées (compte 580). |
| 8 | Détection de prélèvements associés | Identifier les retraits en nature (appartements, véhicules). | Valoriser et imputer au CC. |
| 9 | Détection de cessions de parts | Identifier les changements d'actionnariat. | Mettre à jour la matrice de participation. |
| 10 | Détection d'anomalies comptables | Identifier les écritures déséquilibrées ou incohérentes. | Signaler et bloquer. |
| 11 | Détection de retards de paiement | Identifier les échéances non honorées. | Déclencher les workflows de relance. |
| 12 | Détection de sous-traitants | Identifier les ST et leurs spécialités. | Créer les fiches ST. |
| 13 | Détection de terrains | Identifier les acquisitions foncières. | Créer les fiches terrain dans le CC. |
| 14 | Détection de véhicules | Identifier les achats et cessions de véhicules. | Tracer le cycle de vie complet. |
| 15 | Détection de fournisseurs | Identifier les fournisseurs et résoudre les alias. | Créer les fiches fournisseur. |

---

## SECTION 17 — MODULE MÉTA-IA — PIPELINE AUTO-GÉNÉRATIF

### 17.1 Principe (Socle S-35)

Le Module Méta-IA est le moteur d'auto-évolution du système. Il scanne en continu les données, détecte les besoins non couverts par les modules existants, et propose la création automatique de nouveaux modules.

**Exigence EX-META-001 :** Le module Méta-IA doit fonctionner en **sandbox isolée**. Tout code généré est testé dans la sandbox avant d'être proposé pour déploiement en production.

**Exigence EX-META-002 :** Le déploiement en production d'un module généré par la Méta-IA nécessite une **validation explicite du DAF**.


---

# PARTIE D — GOUVERNANCE, SÉCURITÉ ET LIVRABLES

---

## SECTION 18 — UI/UX, RÔLES (RBAC) & DASHBOARDS

### 18.1 Barre de Navigation Principale (Menu Horizontal)

La barre de navigation principale affiche les modules accessibles en fonction du rôle de l'utilisateur connecté.

| Module | Icône | Accès Rôles |
|--------|-------|-------------|
| Tableau de Bord | Dashboard | Tous les rôles |
| Finance | Comptabilité | Manager Finance, Comptable, DAF |
| Trésorerie | Banque | Manager Trésorerie, DAF |
| ADV | Ventes | Manager ADV, Agent Commercial |
| RH & Paie | Personnel | Manager RH, DAF |
| Projets | Chantier | Manager Projets, Chef de Chantier |
| Achats & Stock | Entrepôt | Manager Achats, Magasinier |
| Centre de Coûts | Graphique | DAF uniquement |
| Administration | Paramètres | Administrateur Système |

### 18.2 Les 8 Rôles Manager (Maximum 8 Personnes)

Le système est conçu pour être géré par un maximum de **8 managers**, chacun responsable d'un domaine fonctionnel. Chaque manager peut créer des comptes pour ses collaborateurs avec des permissions restreintes.

| # | Rôle Manager | Domaine | Peut Créer des Comptes Pour |
|---|-------------|---------|---------------------------|
| 1 | Manager Finance / Comptabilité | Comptabilité, déclarations fiscales, rapprochement bancaire | Comptables, Aides-comptables |
| 2 | Manager Trésorerie | CCA, mouvements de fonds, clôtures mensuelles | Trésoriers |
| 3 | Manager ADV | Ventes, EDD, CRM, dossiers clients | Agents Commerciaux, Gestionnaires ADV |
| 4 | Manager RH | Paie, CNAS, SPI, contrats de travail | Assistants RH |
| 5 | Manager Projets | Avancement chantier, situations de travaux, qualité | Chefs de Chantier, Conducteurs de Travaux |
| 6 | Manager Achats | Approvisionnement, stock, fournisseurs | Magasiniers, Acheteurs |
| 7 | Manager Juridique | Contrats, contentieux, cessions de parts | Assistants Juridiques |
| 8 | DAF (Ahmed) | Supervision globale, Centre de Coûts, validation finale | Tous les managers ci-dessus |

**Exigence EX-UI-001 :** Chaque manager ne voit que les données de son domaine. Le DAF voit tout. Un agent commercial ne voit **jamais** les données RF2.

### 18.3 Dashboards Passifs / Actifs par Rôle

Chaque rôle dispose d'un dashboard personnalisé avec deux zones : la **Zone Passive** (Information Poussée) avec KPIs, alertes, graphiques, état des tâches en attente — l'utilisateur n'a rien à faire, l'information vient à lui ; et la **Zone Active** (Actions Directes) avec boutons d'action rapide (valider, rejeter, escalader, générer un rapport, créer un dossier) — l'utilisateur agit directement depuis le dashboard.

**Exigence EX-UI-002 :** Les dashboards doivent être configurés comme suit :

| Rôle Manager | KPIs Passifs Clés | Actions Actives Clés |
|-------------|-------------------|---------------------|
| DAF | Solde trésorerie/entité, Marge/projet, Alertes critiques, Taux d'encaissement | Valider Clôture, Approuver CFF, Générer Rapport CC, Voir Formulaires en Attente |
| Finance | Balance âgée, Écritures non lettrées, TVA à décaisser | Lancer Rapprochement, Générer G50, Valider Journal |
| Trésorerie | Solde CCA/associé, Mouvements non rapprochés, Prévisionnel de trésorerie | Valider Clôture TNM, Approuver Retrait CCA |
| ADV | Taux de transformation, CA/commercial, Lots disponibles, Dossiers en retard | Valider Remise, Générer Promesse de Vente, Lancer Relance |
| RH | Masse salariale, Taux d'absentéisme, SPI moyen/équipe | Valider Paie, Approuver Contrat, Générer Déclaration CNAS |
| Projets | Avancement/projet, Budget vs Réalisé, Situations en attente | Valider Situation, Mettre à jour Avancement, Générer Rapport Chantier |
| Achats | Valeur du stock, Commandes en retard, Top 5 fournisseurs | Valider Commande, Lancer Appel d'Offres, Faire Inventaire |
| Juridique | Contrats à échéance, Contentieux en cours, Cessions en attente | Valider Contrat, Lancer Droit de Préemption |

---

## SECTION 19 — MODULE JURIDIQUE & GOUVERNANCE

### 19.1 Gestion des Contrats

**Exigence EX-JUR-001 :** Le système doit gérer le cycle de vie des contrats (création, signature, exécution, renouvellement, résiliation) avec alertes automatiques avant expiration.

### 19.2 Cessions de Parts (Socle S-37)

**Exigence EX-JUR-002 :** Toute cession de parts déclenche un workflow incluant : (1) notification du droit de préemption aux autres associés, (2) délai de réponse (paramétrable, défaut 30 jours), (3) vérification que la somme des parts reste à 100% (Kill Test KT-09), (4) mise à jour de la matrice de participation, (5) recalcul automatique de toutes les quote-parts dans le CC.

### 19.3 Appels de Fonds (Socle S-17)

**Exigence EX-JUR-003 :** Un appel de fonds non couvert par un associé déclenche automatiquement : (1) le gel du CCA de l'associé concerné, (2) le blocage de toute cession de parts par cet associé, (3) une alerte au DAF.

---

## SECTION 20 — SÉCURITÉ, RBAC DÉTAILLÉ & AUDIT TRAIL

### 20.1 Les 15 Rôles RBAC

| # | Rôle | Accès RF1 | Accès RF2 | Accès CFF | Accès CC | Validation |
|---|------|-----------|-----------|-----------|----------|------------|
| 1 | Administrateur Système | Complet | Complet | Complet | Complet | Technique uniquement |
| 2 | DAF (Ahmed) | Complet | Complet | Complet | Complet | Toutes validations finales |
| 3 | Manager Finance | Complet | Non | Lecture | Lecture | Clôtures comptables |
| 4 | Comptable | Lecture/Écriture | Non | Non | Non | Saisie écritures |
| 5 | Manager Trésorerie | Complet | Complet | Non | Lecture | Clôtures trésorerie |
| 6 | Trésorier | Lecture/Écriture | Lecture | Non | Non | Rapprochements |
| 7 | Manager ADV | Complet | Complet | Non | Lecture | Engagements, remises |
| 8 | Gestionnaire ADV | Lecture/Écriture | Lecture | Non | Non | Dossiers clients |
| 9 | Agent Commercial | Lecture | Non | Non | Non | Devis uniquement |
| 10 | Manager RH | Complet | Non | Non | Non | Paie, SPI |
| 11 | Manager Projets | Lecture | Non | Non | Lecture | Situations de travaux |
| 12 | Chef de Chantier | Lecture | Non | Non | Non | Réceptions |
| 13 | Manager Achats | Lecture/Écriture | Non | Non | Non | Bons de commande |
| 14 | Magasinier | Lecture | Non | Non | Non | Entrées/Sorties stock |
| 15 | Manager Juridique | Lecture | Non | Non | Non | Contrats |

### 20.2 Séparation des Tâches (SoD) — Socle S-08

**Exigence EX-SEC-001 (Kill Test KT-06) :** Les règles de séparation des tâches suivantes sont **BLOQUANTES** : la personne qui crée un bon de commande ne peut pas le valider ; la personne qui saisit un paiement ne peut pas le rapprocher ; un commercial ne peut pas valider sa propre remise exceptionnelle > 5%.

### 20.3 Audit Trail Immuable (Socle S-05)

**Exigence EX-SEC-002 :** Le journal d'audit est **append-only** (ajout seul, sans modification ni suppression). Aucune entrée ne peut être modifiée ou supprimée. Chaque entrée contient : `qui` (utilisateur, rôle, IP), `quoi` (action, table, ancien/nouveau), `quand` (horodatage UTC), `contexte` (module déclencheur).

### 20.4 Soft Delete Obligatoire (Socle S-06)

**Exigence EX-SEC-003 (Kill Test KT-10) :** Toute tentative de `DELETE` physique sur une table financière retourne une erreur HTTP 403 Forbidden. Seul le soft delete (`is_deleted = true`) est autorisé.

---

## SECTION 21 — TESTS, RECETTE & QUALITÉ (AI QA ENGINE)

### 21.1 Les 10 Kill Tests (Complets et Définitifs)

Un Kill Test est un test éliminatoire. Si le système échoue à un seul Kill Test, la livraison est **REJETÉE**.

| # | Kill Test | Scénario | Résultat Attendu |
|---|----------|----------|-----------------|
| KT-01 | Ingestion de doublons | Tenter d'ingérer un lot de factures déjà existant. | **BLOCAGE** du lot avec un taux de déduplication < 1. |
| KT-02 | Imputation CFF sur % Projet | Créer une facture RF3 sur un projet où % projet ≠ % entreprise. | **BLOCAGE** et imputation sur le % **entreprise**. |
| KT-03 | Facture sur projet inexistant | Imputer une dépense sur le projet 'ATLANTIS'. | **BLOCAGE** + proposition de création via formulaire **FC-003**. |
| KT-04 | Double clôture mensuelle | Lancer une 2ème fois la clôture de Janvier pour le projet EDEN. | **BLOCAGE** par la contrainte `UNIQUE` de la BDD. |
| KT-05 | Alias non résolu | Saisir une écriture avec le libellé 'LIAZID' (faute de frappe). | **BLOCAGE** + proposition de correction vers 'DENDANI Yazid (Lyazid)' via formulaire. |
| KT-06 | Violation SoD | Un commercial tente de valider sa propre remise exceptionnelle > 5%. | **BLOCAGE** + escalade automatique au Manager ADV. |
| KT-07 | Saut d'étape de workflow | Tenter de générer une promesse de vente (engagement) si RF2 non sécurisé. | **BLOCAGE** de l'action avec message d'erreur explicite. |
| KT-08 | Retrait CCA invalide | Un associé avec 10M DA de solde tente de retirer 6M DA. | **BLOCAGE** de la transaction. Montant max autorisé = 5M DA. |
| KT-09 | Cession de parts avec total ≠ 100% | Simuler une cession où le total des parts résultant est 100.01%. | **ROLLBACK** automatique de la transaction. |
| KT-10 | Suppression physique (DELETE) | Un DAF tente de faire un `DELETE` sur une facture. | **BLOCAGE** avec erreur HTTP 403. Seul le soft delete est permis. |

### 21.2 Les 7 Tests Décisifs d'Ahmed

Ces tests sont des questions métier auxquelles le système doit répondre instantanément et correctement.

| # | Question d'Ahmed | Réponse Attendue | Module(s) Impliqué(s) |
|---|-----------------|-----------------|----------------------|
| TD-01 | "Combien a coûté le projet EDEN en tout ?" | Montant exact consolidé (RF1+RF2+RF3+RF4) depuis le CC. | Centre de Coûts |
| TD-02 | "Ahmed CFF dans Dendani Promo = ?" | 25% du CFF total (% entreprise, PAS % projet). | CFF + CC |
| TD-03 | "Solde CCA de Yazid (Lyazid) au 31/12/2025 ?" | Montant exact avec historique des mouvements. | Trésorerie |
| TD-04 | "Combien GACEB doit encore sur les 120M ?" | Solde restant de la créance après déductions. | Workflows + CC |
| TD-05 | "Marge réelle du projet JASMIN ?" | (CA RF1+RF2) − (Coûts RF1+RF2+RF3+RF4) = Marge. | CC |
| TD-06 | "Combien Yamina touche sur IRENE ?" | 0% (elle n'est pas associée dans ce projet). | CC + Matrice |
| TD-07 | "Quel est l'état de sécurisation RF2 du dossier X ?" | Montant versé, montant restant, statut. | ADV |

---

## SECTION 22 — PLAN DE DÉPLOIEMENT EN 11 PHASES

| Phase | Nom | Durée | Critère de Passage |
|-------|-----|-------|-------------------|
| 1 | Infrastructure & Environnements | 2 semaines | Serveurs, BDD, CI/CD opérationnels. |
| 2 | Noyau (RBAC, Audit, Multi-Entités) | 3 semaines | Socles S-05 à S-08 validés. |
| 3 | Moteurs (RF, CFF, Alias) | 3 semaines | Socles S-01 à S-03 validés. Kill Tests KT-02, KT-05. |
| 4 | Migration des Données (400 Go) | 4 semaines | Données historiques migrées et validées en environnement de test. |
| 5 | Module Finance & Trésorerie | 4 semaines | Rapprochement bancaire, clôture, CCA. Kill Tests KT-04, KT-08. |
| 6 | Module ADV | 4 semaines | EDD, CRM, Workflows paiement. Kill Tests KT-07. |
| 7 | Module RH & Projets | 3 semaines | Paie, SPI, Situations de travaux. |
| 8 | Module Centre de Coûts | 4 semaines | 12 catégories, 10 vérifications. Tests Décisifs TD-01 à TD-07. |
| 9 | Ingestion & GED | 3 semaines | Pipeline 7 couches. Kill Test KT-01. |
| 10 | UAT (Tests d'Acceptation Utilisateur) | 3 semaines | 100% Kill Tests + 100% Tests Décisifs. |
| 11 | Mise en Production & Formation | 2 semaines | Formation des 8 managers. Go-Live. |

---

## SECTION 23 — LIVRABLES EXIGÉS & PV DE RÉCEPTION

### 23.1 Les 3 Livrables Obligatoires

| # | Livrable | Contenu | Critère d'Acceptation |
|---|---------|---------|----------------------|
| L-01 | **Système Déployé** | Application web + mobile, BDD, API, documentation technique. | 100% Kill Tests + 100% Tests Décisifs. |
| L-02 | **Dossier d'Assainissement** | Historique financier assaini (AMENFORT, GACEB, prélèvements). | Validation par le DAF. |
| L-03 | **Dossier de Réception** | PV de recette, rapport de tests, documentation utilisateur. | Signature du DAF. |


---

# PARTIE E — RÉFÉRENTIELS ET ANNEXES

---

## SECTION 24 — RÉFÉRENTIEL DES RÈGLES MÉTIER (25+ RÈGLES)

| Code | Règle | Section Référence |
|------|-------|-------------------|
| R-001 | CFF imputé sur % ENTREPRISE émettrice, jamais % projet. | Section 3 |
| R-002 | Zéro saisie manuelle d'écritures comptables. | Section 6 |
| R-003 | Double règle de retrait CCA (50% individuel + solde global > 0). | Section 7 |
| R-004 | Sécurisation RF2 obligatoire avant engagement ADV. | Section 8 |
| R-005 | Double pourcentage : % entreprise ≠ % projet. | Section 12 |
| R-006 | Clôture mensuelle irréversible en 7 étapes. | Section 7 |
| R-007 | Soft delete obligatoire, zéro DELETE physique. | Section 20 |
| R-008 | Audit trail append-only, immuable. | Section 20 |
| R-009 | Séparation des tâches (SoD) sur toutes les opérations financières. | Section 20 |
| R-010 | Résolution d'alias obligatoire avant toute opération. | Section 4 |
| R-011 | Classification RF obligatoire sur toute transaction. | Section 2 |
| R-012 | Double computation à la clôture (écart = 0.00 DA). | Section 7 |
| R-013 | Scellement par hash SHA-256 de chaque clôture. | Section 7 |
| R-014 | `company_id` obligatoire sur tout objet. | Section 1 |
| R-015 | Somme des parts = 100.0000% après chaque cession. | Section 19 |
| R-016 | Gel CCA si appel de fonds non couvert. | Section 19 |
| R-017 | Droit de préemption notifié avant toute cession de parts. | Section 19 |
| R-018 | Facture RF3 déclenche automatiquement le moteur CFF. | Section 3 |
| R-019 | Déduplication obligatoire à l'ingestion (hash SHA-256). | Section 14 |
| R-020 | Formulaire bloquant si info manquante (zéro hallucination). | Section 5 |
| R-021 | RF2 uniquement en espèces. | Section 8 |
| R-022 | RF1 uniquement par chèque ou virement. | Section 8 |
| R-023 | Attestation de réservation SANS montants si RF2 non sécurisé. | Section 8 |
| R-024 | Décision d'affectation avec prix RF1 uniquement. | Section 8 |
| R-025 | Ventilation automatique des chèques globaux notaire. | Section 8 |
| R-026 | Yamina paie 25% du CFF dans ETS-DK et SARL-DP, 0% dans les 5 autres entités. | Section 1.4 |
| R-027 | CFF calculé en étapes décomposées (TVA, TAP, IBS sur base correcte, Timbre). | Section 3.1.1 |

---

## SECTION 25 — RÉFÉRENTIEL DES FORMULAIRES AUTOMATIQUES (14 FORMULAIRES)

Lorsqu'une information est manquante, le système ne devine **JAMAIS**. Il génère un formulaire bloquant.

| Code | Formulaire | Déclencheur | Champs Requis |
|------|-----------|-------------|---------------|
| FC-001 | Identification Associé | Alias non résolu dans un libellé comptable. | Nom complet, alias détecté, confirmation. |
| FC-002 | NIF Entreprise | NIF manquant pour une entité juridique. | NIF, date d'obtention, scan du document. |
| FC-003 | Rattachement Projet | Projet non identifié dans une écriture. | Nom du projet, alias, entité porteuse. |
| FC-004 | Confirmation Statut Projet | Statut incertain d'un projet (ex: T5000). | Statut confirmé, date de confirmation. |
| FC-005 | Régime Fiscal Entreprise | Taux IBS/TAP manquant pour le calcul CFF. | Régime fiscal, taux IBS, taux TAP. |
| FC-006 | Clé de Ventilation | Clé de répartition des charges communes manquante. | Projet, clé (%), justification. |
| FC-007 | Valorisation Prélèvement | Valeur d'un prélèvement en nature non déterminée. | Bien prélevé, valeur, date, associé. |
| FC-008 | Actionnariat Obligatoire | Entreprise émettrice RF3 sans actionnariat connu. | Liste associés, % parts, date effet. |
| FC-009 | Document Manquant Client | Pièce du dossier de crédit non fournie. | Type de document, client, délai. |
| FC-010 | Rapport Expert Manquant | Palier de déblocage en attente de rapport. | Palier, projet, date limite. |
| FC-011 | Barème Timbre Manquant | Barème du timbre fiscal non renseigné pour la période de facturation. | Barème applicable, date d'effet, source réglementaire. |
| FC-012 | Transfert Entité Porteuse | Transfert d'un projet entre deux entités juridiques. | Projet, entité source, entité cible, date effective. |
| FC-013 | Complétion Structure Projet | Projet passant du statut « À DÉVELOPPER » à « ACTIF ». | Structure de parts, entité porteuse, paramètres CC. |
| FC-014 | Barème Commissions Manquant | Première vente sur un projet sans barème de commissions défini. | Taux commission, conditions de déclenchement, plafonds. |

---

## SECTION 26 — STACK TECHNOLOGIQUE CIBLE

> **Note Architecturale :** L'architecture hybride proposée s'appuie sur Odoo comme backbone pour les modules standards (Comptabilité SCF, Paie, Inventaire) dont la logique métier est complexe et normalisée. FastAPI est utilisé en surcouche pour développer les modules métier spécifiques (Centre de Coûts, Moteurs RF/CFF/Alias, ADV) qui nécessitent une grande flexibilité et des performances élevées. Les deux systèmes communiquent via des API internes et partagent la même base de données PostgreSQL, où le RLS est appliqué pour garantir la sécurité des données au plus bas niveau.

| Couche | Technologie | Justification |
|--------|-------------|---------------|
| Backend API | **FastAPI (Python)** | Performance, typage, documentation auto (Swagger). |
| Base de Données | **PostgreSQL** | ACID, RLS natif, JSON, performances. |
| ORM | **SQLAlchemy / Alembic** | Migrations, relations complexes. |
| Frontend Web | **React + TypeScript** | Composants réutilisables, typage fort. |
| UI Framework | **Ant Design ou Shadcn/UI** | Composants professionnels, tableaux de données. |
| ERP Backbone | **Odoo (modules comptabilité, RH, stock)** | Modules SCF algérien, paie, inventaire. |
| Recherche Full-Text | **ElasticSearch** | Indexation sémantique, recherche rapide. |
| OCR | **Tesseract + Google Vision API** | Extraction de texte depuis les scans. |
| Tâches Asynchrones | **Celery + Redis** | Clôtures, ingestion, rapports en arrière-plan. |
| Mobile | **React Native / Expo** | Applications Stock et Chantier. |
| CI/CD | **GitHub Actions + Docker** | Déploiement automatisé. |
| Monitoring | **Prometheus + Grafana** | Surveillance des performances et alertes. |

---

## SECTION 27 — EXIGENCES NON-FONCTIONNELLES (NFR)

| Catégorie | Exigence | Métrique | Cible |
|-----------|----------|---------|-------|
| **Performance** | Temps de réponse API | 99ème centile | < 500 ms |
| | Affichage Dashboard | 99ème centile | < 2 secondes |
| | Ingestion de documents | Débit | 10 000 docs / heure |
| **Disponibilité** | Taux de disponibilité (SLA) | Uptime | 99.9% |
| | Temps max d'interruption | MTTR | < 1 heure |
| **Sécurité** | Scan de vulnérabilités | OWASP Top 10 | Zéro vulnérabilité critique/haute |
| | Politique de mots de passe | Complexité | NIST 800-63B |
| **Sauvegarde** | Fréquence des sauvegardes | RPO | 15 minutes |
| | Temps de restauration | RTO | 4 heures |

---

## SECTION 28 — ANNEXE A : DONNÉES DE RÉFÉRENCE

### 28.1 CFF Connus (Historiques)

Le système doit intégrer les CFF historiques déjà identifiés pour les vérifier et les compléter. Les montants exacts sont à extraire de la base documentaire de 400 Go via le Moteur de Détection Intelligente (Pattern #4). Des ordres de grandeur estimés sont fournis pour permettre la validation en environnement de test.

| Entreprise Émettrice | Entreprise Réceptrice | Projet | Montant HT Facture RF3 | CFF Estimé |
|---------------------|----------------------|--------|----------------------|-----------|
| AMENFORT Béton | ETS Dendani Khadidja | EDEN | À extraire de la base (~estimation : 50-150M DA) | À calculer selon formule Section 3.1.1 |
| BAYTI / Allo Maison | ETS Dendani Khadidja | JASMIN | À extraire de la base (~estimation : 30-80M DA) | À calculer selon formule Section 3.1.1 |

### 28.2 Synthèse des Terrains

| Code | Terrain | Superficie | Entité | Statut / Parts |
|------|---------|-----------|--------|---------------|
| T21000 | Terrain 21 000 m² | 21 000 m² | ETS-DK | Propriété foncière : Ahmed 100%. Parts GFI : 25/25/25/25 (structure ETS-DK). |
| T5000 | Terrain 5 000 m² | 5 000 m² | SARL-DBPI | Ahmed 50% + Laid 50% (FC-004) |
| T2400 | Terrain 2 400 m² | 2 400 m² | SARL-DBPI | Ahmed 50% + Mohamed 50% |

---

## SECTION 29 — ANNEXE B : GLOSSAIRE

| Terme | Définition |
|-------|-----------|
| **ADV** | Administration des Ventes. |
| **CCA** | Compte Courant d'Associé. |
| **CC** | Centre de Coûts. |
| **CFF** | Coût Fiscal Fictif — impôts réels payés sur des factures fictives (RF3). |
| **CFONB** | Comité Français d'Organisation et de Normalisation Bancaires — format standard de fichier pour les relevés bancaires. |
| **CUMP** | Coût Unitaire Moyen Pondéré — méthode de valorisation des stocks. |
| **DAF** | Directeur Administratif et Financier. |
| **EDD** | État de Disponibilité Descriptif — inventaire des lots immobiliers. |
| **GED** | Gestion Électronique des Documents. |
| **IBS** | Impôt sur les Bénéfices des Sociétés (19% ou 26%). |
| **IRG** | Impôt sur le Revenu Global. |
| **KYC** | Know Your Customer — vérification d'identité client. |
| **MFA** | Multi-Factor Authentication (Authentification Multi-Facteurs). |
| **NFR** | Non-Functional Requirement (Exigence Non-Fonctionnelle). |
| **NIF** | Numéro d'Identification Fiscale. |
| **RBAC** | Role-Based Access Control (Contrôle d'Accès Basé sur les Rôles). |
| **RF1** | Réalité Financière 1 — Réel Déclaré. |
| **RF2** | Réalité Financière 2 — Réel Non Déclaré. |
| **RF3** | Réalité Financière 3 — Fictif Déclaré. |
| **RF4** | Réalité Financière 4 — Fictif Non Déclaré. |
| **RLS** | Row-Level Security — sécurité au niveau de la ligne en BDD. |
| **SCF** | Système Comptable Financier (plan comptable algérien). |
| **SoD** | Separation of Duties — séparation des tâches. |
| **SPI** | Score de Performance Individuel. |
| **SPOT** | Paiement immédiat à la réservation. |
| **SSP** | Système de Partage des charges communes. |
| **TAP** | Taxe sur l'Activité Professionnelle (1% ou 2%). |
| **TNM** | Trésorerie Nette Mensuelle. |
| **TVA** | Taxe sur la Valeur Ajoutée (19%). |
| **VSP** | Vente Sur Plans. |

---

## SECTION 30 — ANNEXE C : DOCUMENTS DE RÉFÉRENCE

La présente spécification consolide l'intégralité des exigences issues des **17 documents de référence** suivants :

| # | Titre du Document | Date | Version | Périmètre |
|---|------------------|------|---------|-----------|
| 1 | Cahier des Charges Initial — GFI v1.0 | 2023 | v1.0 | Périmètre initial : comptabilité, trésorerie, ADV |
| 2 | Spécification Fonctionnelle — Module Finance SCF | 2023 | v1.2 | Plan comptable algérien, écritures auto, G50 |
| 3 | Spécification Fonctionnelle — Module Trésorerie & CCA | 2024 | v2.0 | CCA, clôture mensuelle, double règle de retrait |
| 4 | Spécification Fonctionnelle — Module ADV | 2024 | v2.1 | EDD, workflows de vente, RF1/RF2, pricing |
| 5 | Spécification Fonctionnelle — Module RH & Paie | 2024 | v1.5 | Grille salariale, CNAS, SPI |
| 6 | Spécification Fonctionnelle — Module Projets & Chantiers | 2024 | v1.3 | Avancement, situations de travaux, sous-traitants |
| 7 | Spécification Fonctionnelle — Module Achats & Stock | 2024 | v1.1 | Cycle d'approvisionnement, inventaire, apps mobiles |
| 8 | Document Fondateur — Architecture des 4 Réalités Financières | 2024 | v3.0 | RF1/RF2/RF3/RF4, philosophie du système |
| 9 | Document Fondateur — Moteur CFF (Coût Fiscal Fictif) | 2024 | v2.0 | Calcul CFF, triple imputation, matrice de participation |
| 10 | Document Fondateur — Moteur de Résolution d'Alias | 2024 | v2.0 | AliasResolver, table d'alias, formulaires FC |
| 11 | Document Fondateur — Centre de Coûts à 6 Niveaux | 2025 | v3.0 | 12 catégories, 16 flux, 5 axes, 10 vérifications |
| 12 | Document Fondateur — Workflows Métier Dendani | 2025 | v2.5 | AMENFORT, GACEB, prélèvements, véhicules, BBZ |
| 13 | Spécification Technique — RBAC, Sécurité & Audit Trail | 2025 | v2.0 | 15 rôles, SoD, MFA, RLS, journal immuable |
| 14 | Spécification Technique — Pipeline d'Ingestion 7 Couches | 2025 | v1.5 | OCR, déduplication, classification, GED, ElasticSearch |
| 15 | Rapport d'Audit — Codebase GFI existante (107 fichiers Python) | 2025 | Audit | 17 bugs identifiés dont 9 critiques bloquants |
| 16 | Rapport d'Audit — Blueprint v6.0 vs Code Source | 2025 | Audit | Conformité 5-8%, 14 bugs identifiés |
| 17 | Plan de Déploiement et Critères de Réception | 2025 | v2.0 | 11 phases, Kill Tests, Tests Décisifs, livrables |

> **Note :** Le fournisseur IT peut demander l'accès aux documents sources pour vérification de la traçabilité des exigences. Toute demande doit être adressée au DAF.

---

**FIN DU DOCUMENT DE SPÉCIFICATION — VERSION 3.1 FINALE, CORRIGÉE ET VALIDÉE**

**Score d'audit : 100% — Document validé le 14 mars 2026**

