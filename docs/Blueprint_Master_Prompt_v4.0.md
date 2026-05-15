# BLUEPRINT GFI SYSTEM v6.0
# « Cerveau Digital » — Système Ultra-Intelligent d'Archivage, Comptabilité et Gestion Immobilière Multi-Entreprises

**Version** : 6.0 — Mars 2026
**Auteur** : Ahmed D.
**Classification** : Confidentiel — Document Stratégique
**Philosophie** : L'humain connecte les équipements. Le système fait tout le reste.

---

# TABLE DES MATIÈRES

- SOCLE 1 — Philosophie et Architecture Globale
- SOCLE 2 — Le Cerveau IA : Intelligence Documentaire (remplace l'OCR)
- SOCLE 3 — Base de Données v6.0 Corrigée et Complète
- SOCLE 4 — Les 4 Réalités Financières
- SOCLE 5 — Structure Multi-Entreprises (corrigée)
- SOCLE 6 — Structure Multi-Associés (corrigée) + Capital & Retraits
- SOCLE 7 — Cartographie des Projets (corrigée)
- SOCLE 8 — Mutations Foncières
- SOCLE 9 — Comptes Transitoires Notaires & Banques Partenaires
- SOCLE 10 — Encaissements Clients
- SOCLE 11 — Décaissements
- SOCLE 12 — Stock, Magasin & Automatisation LAD
- SOCLE 13 — Centre de Coût Ultra-Réel
- SOCLE 14 — Consolidation et Répartition des Bénéfices
- SOCLE 15 — Pipeline Conditionnel 7 Phases (implémenté réellement)
- SOCLE 16 — Blocage Intelligent & Cycle de Résolution 7 Étapes
- SOCLE 17 — Vérification Extrême à 8 Niveaux
- SOCLE 18 — API, RBAC, Audit Trail
- SOCLE 19 — Frontend React
- SOCLE 20 — Automatisation Maximale : Le Système Donne les Instructions
- SOCLE 21 — Règles de Livraison et Tests
- ANNEXE A — Corrections v5.0 → v6.0 (erreurs identifiées)
- ANNEXE B — Architecture Technique Détaillée

---

# SOCLE 1 — PHILOSOPHIE ET ARCHITECTURE GLOBALE

## 1.1 — Le Principe Fondamental

L'humain fait le minimum. Le système fait le maximum.

L'humain connecte un scanner → le système numérise, segmente, analyse, classe, vérifie, saisit, consolide, et archive automatiquement.

L'humain connecte un lecteur de codes-barres (LAD) → le système identifie l'article, met à jour le stock, recalcule le CUMP, imprime le ticket, impute au projet, et met à jour le centre de coût.

L'humain importe un fichier de 500 pages → le système découpe en segments intelligents, analyse chaque segment avec l'IA appropriée selon le volume, consolide les analyses, extrait chaque donnée, et reconstruit le tout sans perdre un seul détail.

Le système ne demande à l'humain que quand il ne sait pas à 100%. Et même là, il propose des suggestions intelligentes pour que l'humain n'ait qu'à cliquer.

## 1.2 — Architecture Technique

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND — React + Dashboard                  │
│  Scanner USB/Réseau  ←→  Interface Web  ←→  LAD Codes-barres   │
└──────────────────────────────┬────────────────────────────────────┘
                               │ API REST (FastAPI)
                               │ RBAC 9 rôles + Audit Trail
┌──────────────────────────────┴────────────────────────────────────┐
│                     CERVEAU IA — Intelligence Documentaire         │
│  ┌──────────────┐ ┌──────────────┐ ┌───────────────────────────┐ │
│  │ Google Vision │ │ Gemini Flash │ │ Gemini Pro / 1.5 Pro      │ │
│  │ (Scan/Image) │ │ (< 30 pages) │ │ (30-500 pages, segments)  │ │
│  └──────────────┘ └──────────────┘ └───────────────────────────┘ │
│  Segmentation → Analyse parallèle → Consolidation → Extraction   │
└──────────────────────────────┬────────────────────────────────────┘
                               │
┌──────────────────────────────┴────────────────────────────────────┐
│                     SERVICES MÉTIER                                │
│  Structuration │ Comptabilité │ Trésorerie │ Stock │ Consolidation│
│  Transit Notaire │ Capital Associés │ Workflow │ Reporting        │
└──────────────────────────────┬────────────────────────────────────┘
                               │
┌──────────────────────────────┴────────────────────────────────────┐
│                     PostgreSQL 16                                  │
│  40+ tables │ Triggers │ Contraintes │ Vues │ Hash Non-Régression │
└───────────────────────────────────────────────────────────────────┘
```

## 1.3 — Stack Technique

- **Backend** : Python 3.11, FastAPI, psycopg2
- **Base de données** : PostgreSQL 16 avec contraintes strictes
- **Frontend** : React 18 + Tailwind CSS
- **IA Documentaire** : Google Cloud Vision API (scan/images), Gemini API (analyse documents)
- **Conteneurisation** : Docker Compose
- **Équipements physiques** : Scanner USB/réseau (TWAIN/WIA), Lecteur codes-barres USB (HID)

---

# SOCLE 2 — LE CERVEAU IA : INTELLIGENCE DOCUMENTAIRE

**L'OCR classique est éliminé.** Il est remplacé par une intelligence documentaire multi-modèle qui comprend le contenu, pas seulement le texte.

## 2.1 — Segmentation Intelligente des Fichiers Volumineux

Quand un fichier volumineux arrive (PDF multi-pages, Excel avec beaucoup d'onglets, archives ZIP), le système ne tente jamais de l'envoyer en un bloc à un modèle IA. Il segmente d'abord.

**Algorithme de segmentation :**

```
ENTRÉE : fichier (PDF, Excel, images, ZIP)

ÉTAPE 1 — Détection du type et du volume
  Si fichier = PDF :
    Compter le nombre de pages
    Si pages ≤ 10 → SEGMENT_UNIQUE (envoi direct)
    Si pages 11-50 → SEGMENTS_MOYENS (découpe par 10 pages)
    Si pages 51-200 → SEGMENTS_PETITS (découpe par 5 pages)
    Si pages > 200 → SEGMENTS_MICRO (découpe par 3 pages)
  Si fichier = Excel :
    Compter les onglets et les lignes par onglet
    Chaque onglet = un segment
    Si un onglet > 1000 lignes → sous-segmenter par 500 lignes
  Si fichier = ZIP :
    Extraire → traiter chaque fichier individuellement
  Si fichier = Image :
    SEGMENT_UNIQUE (une image = un segment)

ÉTAPE 2 — Découpe physique
  Créer les sous-fichiers dans un dossier temporaire /tmp/segments/{session_id}/
  Nommer : segment_001.pdf, segment_002.pdf, etc.
  Garder la table de correspondance (segment N = pages X à Y du fichier original)

ÉTAPE 3 — Analyse parallèle
  Pour chaque segment, lancer l'analyse IA en parallèle (asyncio)
  Maximum 5 segments simultanés pour respecter les quotas API
  Chaque segment retourne : texte extrait, métadonnées, entités détectées, classification

ÉTAPE 4 — Consolidation
  Fusionner les résultats de tous les segments dans l'ordre original
  Dédupliquer les entités (un même fournisseur détecté dans 3 segments = 1 fournisseur)
  Vérifier la cohérence inter-segments (un montant commencé page 10 finit page 11)
  Produire l'ANALYSE GLOBALE CONSOLIDÉE

SORTIE : un objet unifié contenant toutes les données extraites comme si le fichier 
         avait été analysé en un seul passage, sans aucune perte de détail.
```

## 2.2 — Sélection du Modèle IA selon le Contenu

Le système utilise **le bon modèle pour le bon travail** :

| Situation | Modèle | Raison |
|-----------|--------|--------|
| Scan papier / photo de document | **Google Cloud Vision API** | Spécialisé reconnaissance texte sur images, meilleure précision que les LLMs pour le texte dans les images |
| Document numérique ≤ 30 pages | **Gemini 2.0 Flash** | Rapide, bon marché, suffisant pour les documents courts |
| Document numérique 30-100 pages | **Gemini 1.5 Pro** | Fenêtre de contexte large (1M tokens), comprend les documents longs |
| Document > 100 pages (segmenté) | **Gemini 1.5 Pro** par segment | Chaque segment de 5-10 pages est analysé, puis consolidation |
| Tableau Excel / données structurées | **Gemini 2.0 Flash** | Extraction de données tabulaires, rapide |
| Document complexe (plans, schémas) | **Gemini 1.5 Pro** avec vision | Comprend les éléments visuels et les tableaux |

## 2.3 — Prompts d'Extraction Standardisés

Chaque type de document a un prompt spécialisé envoyé à l'IA. Le prompt demande une extraction structurée en JSON.

**Exemple — Prompt pour facture d'achat :**
```
Tu es un extracteur de données de factures algériennes. 
Extrais TOUTES les informations suivantes en JSON strict :
{
  "type_document": "FACTURE_ACHAT",
  "fournisseur": {"nom": "", "nif": "", "rc": "", "adresse": ""},
  "acheteur": {"nom": "", "nif": ""},
  "numero_facture": "",
  "date_facture": "YYYY-MM-DD",
  "lignes": [{"designation": "", "quantite": 0, "prix_unitaire": 0, "montant_ht": 0}],
  "montant_ht": 0,
  "taux_tva": 19,
  "montant_tva": 0,
  "montant_ttc": 0,
  "montant_timbre": 0,
  "mode_paiement": "",
  "projet_detecte": "",
  "certitude_extraction": 0-100 pour chaque champ
}
Si un champ n'est pas visible ou lisible, mettre null et certitude = 0.
Ne jamais inventer de données. Extraction exacte uniquement.
```

**Exemple — Prompt pour relevé bancaire :**
```
Extrais CHAQUE ligne de ce relevé bancaire algérien en JSON :
{
  "banque": "", "agence": "", "numero_compte": "", "titulaire": "",
  "periode": {"debut": "YYYY-MM-DD", "fin": "YYYY-MM-DD"},
  "solde_initial": 0, "solde_final": 0,
  "mouvements": [
    {"date": "YYYY-MM-DD", "date_valeur": "YYYY-MM-DD", "libelle": "",
     "debit": 0, "credit": 0, "solde": 0, "reference": ""}
  ]
}
CHAQUE mouvement, CHAQUE ligne, sans exception. Ne sauter aucune ligne.
```

**Exemple — Prompt pour bulletin de paie :**
```
Extrais TOUTES les données de ce bulletin de paie algérien :
{
  "employe": {"nom": "", "prenom": "", "matricule": "", "poste": "", "numero_ss": ""},
  "employeur": {"nom": "", "nif": ""},
  "periode": {"mois": 1-12, "annee": 0000},
  "salaire_base": 0, "heures_sup": 0, "primes": 0, "indemnites": 0,
  "salaire_brut": 0,
  "cnas_salarie": 0, "irg": 0, "autres_retenues": 0,
  "total_retenues": 0, "salaire_net": 0,
  "cnas_patronal": 0, "cout_total_employeur": 0
}
```

## 2.4 — Connexion Scanner : L'humain scanne, le système fait tout

**Protocole :**

1. L'humain met le document dans le scanner et appuie sur "Scanner" dans l'interface web
2. Le frontend communique avec le scanner via :
   - **WebUSB API** (scanner USB direct)
   - **Ou** un micro-agent local léger (`gfi-scanner-agent`) installé sur le PC qui expose le scanner via HTTP localhost
3. Le scanner numérise en 300 DPI couleur
4. L'image arrive au backend via l'API
5. Le backend :
   - Sauvegarde l'image originale
   - L'envoie à **Google Cloud Vision API** pour extraction du texte
   - Envoie le texte + l'image à **Gemini** pour compréhension complète
   - Extrait les métadonnées structurées (JSON)
   - Classe le document (entreprise, projet, département, type)
   - Si certitude = 100% → archivage et traitement automatique
   - Si certitude < 100% → blocage avec interface de résolution

**Le flux est entièrement automatique après le scan.** L'humain n'intervient que si le système ne reconnaît pas quelque chose à 100%.

## 2.5 — Configuration des API

```python
# config.py — Clés API à configurer au déploiement
GOOGLE_VISION_API_KEY = os.getenv("GOOGLE_VISION_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Modèles Gemini
GEMINI_MODEL_FLASH = "gemini-2.0-flash"          # Documents courts
GEMINI_MODEL_PRO = "gemini-1.5-pro"              # Documents longs

# Limites
MAX_PARALLEL_SEGMENTS = 5
SEGMENT_SIZE_PDF_SMALL = 10   # pages par segment pour PDF ≤ 50 pages
SEGMENT_SIZE_PDF_MEDIUM = 5   # pages par segment pour PDF 51-200
SEGMENT_SIZE_PDF_LARGE = 3    # pages par segment pour PDF > 200
SEGMENT_SIZE_EXCEL_ROWS = 500 # lignes par segment pour Excel
```

---

# SOCLE 3 — BASE DE DONNÉES v6.0 CORRIGÉE ET COMPLÈTE

## 3.1 — Liste complète des tables (45+ tables)

### Tables Core (existantes, corrigées)
1. `users` — Utilisateurs avec RBAC 9 rôles
2. `audit_log` — Traçabilité absolue de chaque action
3. `parametres` — Configuration système
4. `entreprises` — 6 entités juridiques
5. `exercices` — Exercices comptables par entreprise
6. `associes` — Avec aliases et type (PERSONNE_PHYSIQUE/MORALE) **← AJOUT type**
7. `projets` — 12 projets
8. `parts_projets` — Pourcentages (somme = 100%) + montant_apport
9. `mutations_foncieres` — Avec cedant_id et cessionnaire_id **← CORRECTION**
10. `departements` — Par entreprise

### Tables Documents & Archivage (existantes)
11. `import_sessions` — Sessions d'import
12. `documents` — Documents avec classification IA
13. `versions_documents` — Versioning
14. `archivage_physique` — Localisation physique

### Tables Comptabilité (existantes)
15. `plan_comptable` — SCF algérien classes 1-7
16. `journaux` — Journaux comptables par entreprise
17. `ecritures_comptables` — Avec 4 réalités
18. `lignes_ecritures` — Détail des écritures

### Tables Trésorerie (existantes, enrichies)
19. `clients` — Avec surface, lot_code structuré **← ENRICHI**
20. `comptes_bancaires` — Comptes de l'entreprise
21. `encaissements` — Avec reference_contrat **← ENRICHI**
22. `fournisseurs` — Fournisseurs
23. `decaissements` — Avec sous_categorie, beneficiaire_id, sens **← ENRICHI**
24. `echeancier_clients` — Alertes retard 30/60/90

### Tables Stock & Paie (existantes)
25. `articles_stock` — Avec CUMP automatique
26. `mouvements_stock` — Entrées/sorties avec trigger
27. `employes` — Registre employés
28. `bulletins_paie` — Avec vérification arithmétique
29. `declarations_fiscales` — G50, IBS, etc.

### Tables Workflow & Blocage (existantes)
30. `workflow_dossiers` — Pipeline 7 phases
31. `workflow_phases_log` — Historique transitions
32. `demandes_completion` — Blocage intelligent enrichi **← ENRICHI**
33. `centre_cout` — Par projet avec calcul ultra-réel
34. `consolidation_associes` — Vue par associé
35. `consolidation_entreprises` — Vue par entreprise
36. `verifications_hash` — Non-régression SHA-256

### NOUVELLES Tables v6.0
37. `notaires` — Notaires partenaires
38. `banques_partenaires` — Banques qui débloquent les crédits
39. `comptes_transitoires_notaires` — Fonds en transit
40. `projet_notaires` — Rattachement dynamique projet ↔ notaire
41. `projet_banques` — Rattachement dynamique projet ↔ banque
42. `capital_associes` — Apports en capital par associé par projet
43. `retraits_associes` — Prélèvements par associé
44. `lots_immobiliers` — Stock EDD : Projet/Bloc/Étage/Lot **← NOUVEAU**
45. `dossiers_fictifs_reference` — Résultats attendus des tests fictifs **← NOUVEAU**
46. `projet_entreprise_historique` — Transition d'entité (OPERA) **← NOUVEAU**
47. `imputation_paie_projets` — Répartition RH multi-projets **← NOUVEAU**
48. `document_segments` — Segments de fichiers volumineux **← NOUVEAU**
49. `ia_extraction_log` — Log de chaque appel IA avec résultat **← NOUVEAU**

## 3.2 — Tables nouvelles — Définitions SQL

### `lots_immobiliers` — Stock EDD
```sql
CREATE TYPE statut_lot_enum AS ENUM (
    'DISPONIBLE', 'RESERVE', 'VENDU', 'LIVRE', 'LITIGE'
);

CREATE TABLE lots_immobiliers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    projet_id UUID NOT NULL REFERENCES projets(id),
    bloc VARCHAR(10) NOT NULL,
    etage VARCHAR(10) NOT NULL,
    numero_lot VARCHAR(20) NOT NULL,
    type_bien VARCHAR(50) NOT NULL,        -- F2, F3, F4, LOCAL_COMMERCIAL, PARKING
    surface NUMERIC(8,2) NOT NULL CHECK (surface > 0),
    prix NUMERIC(15,2) NOT NULL CHECK (prix >= 0),
    statut statut_lot_enum NOT NULL DEFAULT 'DISPONIBLE',
    client_id UUID REFERENCES clients(id),
    date_reservation DATE,
    date_vente DATE,
    date_livraison DATE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(projet_id, bloc, etage, numero_lot)
);
CREATE INDEX idx_lots_projet ON lots_immobiliers(projet_id);
CREATE INDEX idx_lots_statut ON lots_immobiliers(statut);
```

### `projet_entreprise_historique` — Transition OPERA
```sql
CREATE TABLE projet_entreprise_historique (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    projet_id UUID NOT NULL REFERENCES projets(id),
    entreprise_id UUID NOT NULL REFERENCES entreprises(id),
    date_debut DATE NOT NULL,
    date_fin DATE,                          -- NULL = toujours actif
    type_transition VARCHAR(50),            -- DONATION, CESSION, CREATION
    reference_acte VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(projet_id, entreprise_id, date_debut)
);
```

### `imputation_paie_projets` — RH multi-projets
```sql
CREATE TABLE imputation_paie_projets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bulletin_id UUID NOT NULL REFERENCES bulletins_paie(id),
    projet_id UUID NOT NULL REFERENCES projets(id),
    pourcentage NUMERIC(6,2) NOT NULL CHECK (pourcentage > 0 AND pourcentage <= 100),
    montant_impute NUMERIC(12,2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(bulletin_id, projet_id)
);
-- Contrainte : somme des pourcentages par bulletin = 100%
```

### `document_segments` — Segmentation fichiers volumineux
```sql
CREATE TABLE document_segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id),
    numero_segment INTEGER NOT NULL CHECK (numero_segment >= 1),
    nombre_total_segments INTEGER NOT NULL,
    -- Plage dans le fichier original
    page_debut INTEGER,
    page_fin INTEGER,
    onglet_excel VARCHAR(100),
    ligne_debut INTEGER,
    ligne_fin INTEGER,
    -- Résultat IA
    modele_ia_utilise VARCHAR(50) NOT NULL,     -- gemini-2.0-flash, gemini-1.5-pro, google-vision
    texte_extrait TEXT,
    donnees_extraites JSONB,                     -- JSON structuré
    certitude_globale NUMERIC(5,2),
    temps_traitement_ms INTEGER,
    tokens_utilises INTEGER,
    -- Consolidation
    est_consolide BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(document_id, numero_segment)
);
```

### `ia_extraction_log` — Traçabilité IA
```sql
CREATE TABLE ia_extraction_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id),
    segment_id UUID REFERENCES document_segments(id),
    modele VARCHAR(50) NOT NULL,
    type_requete VARCHAR(50) NOT NULL,        -- EXTRACTION, CLASSIFICATION, VALIDATION
    prompt_resume TEXT,                         -- Résumé du prompt (pas le prompt entier)
    reponse_json JSONB,
    tokens_input INTEGER,
    tokens_output INTEGER,
    cout_estime NUMERIC(8,4),                  -- En USD
    temps_ms INTEGER,
    succes BOOLEAN NOT NULL DEFAULT TRUE,
    erreur TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

### `dossiers_fictifs_reference` — Résultats attendus
```sql
CREATE TABLE dossiers_fictifs_reference (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,          -- FICTIF-001, FICTIF-002
    description TEXT NOT NULL,
    donnees_entree JSONB NOT NULL,             -- Le jeu de données fictif
    resultats_attendus JSONB NOT NULL,         -- Les résultats attendus au centime
    derniere_execution TIMESTAMP WITH TIME ZONE,
    dernier_resultat JSONB,
    dernier_statut VARCHAR(20),                -- PASS, FAIL
    ecart_detecte TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

---

# SOCLE 4 — LES 4 RÉALITÉS FINANCIÈRES

Identique au CDC v5.0, aucune modification. Les 4 réalités sont :

- **RD** (Réel Déclaré) : opérations réelles déclarées aux impôts
- **RND** (Réel Non-Déclaré) : opérations réelles non déclarées
- **FD** (Fictif Déclaré) : coût d'achat des factures fictives (ex: 5% d'une facture de 1M = 50K DA)
- **FND** (Fictif Non-Déclaré) : opérations fictives hors déclarations

Champ `statut_fiscal` : ENUM (REEL_DECLARE, REEL_NON_DECLARE, FICTIF_DECLARE, FICTIF_NON_DECLARE, EN_ATTENTE). NOT NULL sur toutes les tables. Pas de cinquième option.

Centre de coût ultra-réel : Recettes = RD + RND. Dépenses = RD + RND + coût FD. Résultat = Recettes − Dépenses.

---

# SOCLE 5 — STRUCTURE MULTI-ENTREPRISES (CORRIGÉE)

Les 6 entités juridiques et leurs projets **correctement** rattachés :

| Entreprise | Forme | Projets portés |
|-----------|-------|---------------|
| ETS Dendani Khadidja | ETS | JASMIN, EDEN, OPERA (avant 2022), T21000 |
| SARL Dendani Promotion | SARL | OPERA (après 2022 par donation), IRENE, AUREA |
| SARL DBPI Immobilier | SARL | LYS (2ha), T5000 (abandonné), T2400 |
| SARL Omega Construction | SARL | MAGNOLIA |
| SARL Senimar | SARL | ASTERIA |
| EURL BBT Immobilier | EURL | Entité tierce acheteuse (pas de projets en gestion interne) |

**CORRECTION CRITIQUE v5→v6** : EDEN revient sous ETS-DK. LYS revient sous SARL-DBPI. T21000 revient sous ETS-DK. IRENE et AUREA passent sous SARL-DP. MOSQUEE est un projet spécial (don à la Direction des Affaires Religieuses), rattaché à ETS-DK comme entité historique.

Pour OPERA (transition 2022), insertion dans `projet_entreprise_historique` :
```sql
INSERT INTO projet_entreprise_historique (projet_id, entreprise_id, date_debut, date_fin, type_transition) VALUES
  ('[OPERA_ID]', '[ETS_DK_ID]', '2015-01-01', '2022-06-30', 'CREATION'),
  ('[OPERA_ID]', '[SARL_DP_ID]', '2022-07-01', NULL, 'DONATION');
```

---

# SOCLE 6 — STRUCTURE MULTI-ASSOCIÉS (CORRIGÉE) + CAPITAL & RETRAITS

## 6.1 — Associés et aliases (corrigés)

| # | Nom | Prénom | Type | Aliases |
|---|-----|--------|------|---------|
| 1 | Dendani | Ahmed | PERSONNE_PHYSIQUE | Ahmed |
| 2 | Dendani | Mohamed | PERSONNE_PHYSIQUE | Mohamed, Moh, Mohammed |
| 3 | Dendani | Yazid | PERSONNE_PHYSIQUE | Yazid |
| 4 | Dendani | Yamina | PERSONNE_PHYSIQUE | Yamina |
| 5 | Boumerdassi | Mustapha | PERSONNE_PHYSIQUE | Boumerdassi, Boumerdassi Mustapha |
| 6 | Amirat | Brahim | PERSONNE_PHYSIQUE | Amirat, Brahim Amirat |
| 7 | Dendani | Laid | PERSONNE_PHYSIQUE | Laid |
| 8 | Moukhtari | Tarek | PERSONNE_PHYSIQUE | Moukhtari, Moukhtari Tarek |
| 9 | Moukhtari | Amine | PERSONNE_PHYSIQUE | Moukhtari Amine |

**Résolution des aliases** : recherche exacte dans `nom_complet` puis dans `aliases[]`. Si match exact → validation automatique 100%. Si aucun match → BLOCAGE + suggestion par distance de Levenshtein. Jamais de validation automatique approximative.

## 6.2 — Capital versé et retraits

Chaque associé, pour chaque projet, a un compte de position nette :

**Position Nette = Capital Versé − Retraits + Quote-part Résultat**

Tables : `capital_associes` (apports) et `retraits_associes` (prélèvements).

Les retraits proviennent de fiches papier. Le système permet l'import en lot et la saisie unitaire. La description du retrait est obligatoire. Les retraits ne bloquent jamais mais génèrent une alerte si la position nette devient négative.

Vue SQL `position_nette_associes` pour le calcul en temps réel. (Voir définitions SQL complètes dans SOCLE 3.)

---

# SOCLE 7 — CARTOGRAPHIE DES PROJETS (CORRIGÉE)

| Code | Nom | Associés (CORRIGÉS) | Entité | Clients |
|------|-----|---------------------|--------|---------|
| JASMIN | Les Jasmins (Sahel) | Ahmed 34%, Yazid 33%, Mohamed 33% | ETS-DK | 100 |
| EDEN | Eden (Foes) | Ahmed 25%, Yazid 25%, Mohamed 25%, Yamina 25% | ETS-DK | 154 |
| OPERA | Ouled Fayet | Ahmed 25%, Mohamed 25%, Yazid 25%, Yamina 25% | ETS-DK→SARL-DP (2022) | 153 |
| LYS | Les Lys (Draria, 2ha) | Ahmed 60%, Mohamed 20%, Yazid 20% | SARL-DBPI | 86 |
| T21000 | Terrain 21000m² | Ahmed 100% (actif foncier ETS-DK) | ETS-DK | — |
| T5000 | Terrains 5000m² | **Laid 50%, Ahmed 50%** | SARL-DBPI | — ABANDONNÉ |
| T2400 | Terrains 2400m² | Ahmed 50%, Mohamed 50% | SARL-DBPI | — |
| IRENE | Irène (5ha) | **Ahmed 60%, Mohamed 20%, Yazid 20%** | SARL-DP | 692 |
| MAGNOLIA | Magnolia | **Ahmed 60%, Yazid 20%, Mohamed 20%** | SARL-OC | 18 |
| AUREA | Auréa (Cheraga) | **Ahmed 60%, Yazid 20%, Mohamed 20%** | SARL-DP | 199 |
| ASTERIA | Asteria (El Achour) | **Ahmed 60%, Mohamed 20%, Yazid 20%** | SARL-SEN | 52 |
| MOSQUEE | Mosquée Taourga | **Ahmed 34%, Yazid 33%, Mohamed 33%** | ETS-DK | — Don |

**En gras = corrections par rapport à v5.0 livrée.**

Total clients tous projets : 1 454.

---

# SOCLE 8 — MUTATIONS FONCIÈRES

Table `mutations_foncieres` enrichie avec `cedant_id` et `cessionnaire_id` (FK vers une table unifiée `tiers_mutations` ou vers `entreprises`/`associes` avec un type polymorphique).

**Chaînes à insérer dans les seeds :**

### Chaîne Les Lys (4 mutations)
1. ETS-DK propriétaire terrain 2ha → type PROPRIETE_INITIALE
2. Échange ETS-DK cède 2ha ↔ Boumerdassi cède 21000m² → type ECHANGE
3. Donation Boumerdassi → SARL-DBPI pour 2ha → type DONATION
4. Vente ETS-DK du 21000m² → Brahim Amirat → type VENTE

### Chaîne Terrains 5000m² (2 mutations)
1. Achat par SARL-DBPI → type ACHAT, montage partenariat Laid
2. Désistement au propriétaire Laid → type DESISTEMENT, perte 12 000 000 DA

### Chaîne Terrains 2400m² (2 mutations)
1. Achat par SARL-DBPI de Moukhtari Tarek et Amine → type ACHAT
2. Vente à EURL BBT → type VENTE, bénéfice 20 000 000 DA

### Chaîne Ouled Fayet (1 mutation)
1. Donation ETS-DK → SARL-DP, date 2022 → type DONATION

---

# SOCLE 9 — COMPTES TRANSITOIRES NOTAIRES & BANQUES PARTENAIRES

## 9.1 — Le flux

Banque débloque crédit au nom du notaire → Notaire retient les fonds → Libération en 2 tranches conditionnelles :
- **20%** à la signature VEFA (vente sur plans)
- **5%** à la signature PV remise des clés
- **75%** versés directement par la banque à l'entreprise

## 9.2 — Notaires connus

| Notaire | Projets |
|---------|---------|
| Maître Izouine | EDEN, JASMIN |
| Maître Belkadi Kafila | JASMIN, OPERA |
| Maître Belkecem Farida | JASMIN, OPERA |

## 9.3 — Banques partenaires

| Code | Banque | Agence | Projets |
|------|--------|--------|---------|
| CNEP-BOUM | CNEP | Boumerdès | EDEN |
| BNA-BOUM | BNA | Boumerdès | EDEN, JASMIN |
| CNEP-KHB | CNEP | Khelifa Boukhalfa Alger | JASMIN |
| CNEP-SH | CNEP | Saïd Hamdine | OPERA |
| BNA-BB | BNA | Bordj El Bahri | OPERA |
| CNEP-BLV5 | CNEP | Boulevard 5 Juillet Alger | OPERA |
| CNEP-AC | CNEP | Alger Centre | OPERA |

## 9.4 — Champs dynamiques

Les notaires et banques sont dynamiques. Quand le système détecte un nouveau notaire ou banque dans un document importé :
- Match exact → rattachement automatique
- Pas de match → BLOCAGE + demande : "Nouveau notaire/banque détecté. Créer ou sélectionner ?"

L'utilisateur peut ajouter des notaires et banques à tout moment. Le système rattache automatiquement au projet concerné via `projet_notaires` et `projet_banques`.

---

# SOCLE 10 — ENCAISSEMENTS CLIENTS

1 454 clients, 8 projets de promotion. Chaque client a un contrat, un échéancier, et des paiements tracés avec les 4 réalités.

Table `clients` enrichie : ajout `surface`, `nif`, statuts spécifiques (RESERVE/EN_COURS/SOLDE/LITIGE/RESILIE).

Encaissement dépassant le montant du contrat → rejet avec message métier clair (pas une erreur PostgreSQL brute).

Alertes automatiques à 30, 60, 90 jours de retard → création automatique de `demandes_completion` de priorité CRITIQUE après 90 jours.

---

# SOCLE 11 — DÉCAISSEMENTS

Table enrichie avec `sous_categorie`, `beneficiaire_id` (FK polymorphique), `sens` pour contentieux (GAIN/PERTE).

Les 8 catégories : CHARGE_FIXE, CHARGE_VARIABLE, RH_PAIE, TAXE_FISCALE, TAXE_PARAFISCALE, CONTENTIEUX, MARCHE_BC, STOCK.

Contentieux GAIN → apparaît en recette dans le centre de coût. Contentieux PERTE → apparaît en dépense.

RH affecté à 2+ projets via `imputation_paie_projets` avec répartition proportionnelle vérifiée (somme = 100%).

---

# SOCLE 12 — STOCK, MAGASIN & AUTOMATISATION LAD

## 12.1 — Connexion du lecteur codes-barres (LAD)

L'humain branche le LAD USB. Le système fait le reste.

Le LAD USB se comporte comme un clavier (protocole HID). Il envoie le code-barres comme une séquence de touches. Le frontend écoute en permanence un champ invisible de scan :

```
FONCTIONNEMENT :
1. Le champ de scan est toujours actif (focus permanent)
2. Le LAD envoie le code-barres + touche ENTRÉE
3. Le frontend intercepte la saisie rapide (< 50ms entre les caractères = scan LAD)
4. Le code-barres est envoyé à l'API : GET /api/stock/barcode/{code}
5. L'API retourne l'article avec son stock actuel et son CUMP
6. L'interface affiche automatiquement :
   - Désignation de l'article
   - Stock actuel
   - CUMP actuel
   - Champ quantité pré-rempli à 1
   - Sélection du sens : ENTRÉE ou SORTIE
   - Sélection du projet destinataire (pour les sorties)
7. L'humain confirme la quantité et clique "Valider"
8. Le système : enregistre le mouvement, met à jour le stock, recalcule le CUMP,
   impute au projet, génère le bon (BL ou BS), et propose l'impression du ticket
```

## 12.2 — Impression ticket

Le ticket est généré en HTML et imprimé via `window.print()` avec une feuille de style @media print dédiée (format ticket 80mm). Pas besoin de driver spécial.

## 12.3 — Stock immobilier (EDD)

Table `lots_immobiliers` : Projet → Bloc → Étage → Lot. Chaque lot a une surface, un prix, un statut (DISPONIBLE/RESERVE/VENDU/LIVRE) et un client associé. Le dashboard affiche l'état d'avancement par projet : nombre de lots disponibles, réservés, vendus, livrés.

---

# SOCLE 13 — CENTRE DE COÛT ULTRA-RÉEL

Pour chaque projet :
- **Recettes** = encaissements RD + encaissements RND + gains contentieux
- **Dépenses** = décaissements RD + décaissements RND + coût factures FD + pertes contentieux + stock consommé CUMP + charges communes prorata
- **Résultat ultra-réel** = Recettes − Dépenses

**Répartition charges communes (NOUVEAU — absent en v5)** :

Si un décaissement a `projet_id IS NULL`, c'est une charge commune. Elle est répartie au prorata du chiffre d'affaires :

```
Quote-part projet X = (CA projet X / CA total tous projets) × charge commune
```

Ceci est calculé automatiquement et stocké dans `centre_cout.charges_communes_prorata`.

**Montants en transit notaire** : affichés séparément. Encaissements effectifs ≠ encaissements en transit.

**Double computation OBLIGATOIRE** :
- Chemin 1 : agrégation des écritures comptables
- Chemin 2 : sommation des mouvements financiers (encaissements + décaissements)
- Si les deux chemins ne donnent pas le même résultat au centime → BLOCAGE SYSTÈME

---

# SOCLE 14 — CONSOLIDATION ET RÉPARTITION DES BÉNÉFICES

## 14.1 — Par projet
Tableau : recettes, dépenses, résultat, avancement, stock restant, trésorerie, montants en transit notaire.

## 14.2 — Par associé (enrichi v6)
Pour chaque associé, le tableau inclut maintenant :

| Colonne | Description |
|---------|-------------|
| Projet | Code du projet |
| % | Pourcentage de participation |
| Capital versé | Total apports dans capital_associes |
| Retraits | Total retraits dans retraits_associes |
| Quote-part recettes | Recettes projet × % |
| Quote-part dépenses | Dépenses projet × % |
| Quote-part résultat | Résultat projet × % |
| Position nette | Capital − Retraits + Quote-part résultat |
| Alerte | 🔴 si position nette < 0 |

Ligne TOTAL en bas : agrégation tous projets.

## 14.3 — Par entreprise
SARL-DP = OPERA (post-2022) + IRENE + AUREA. OPERA ne doit pas apparaître deux fois.

---

# SOCLE 15 — PIPELINE CONDITIONNEL 7 PHASES (IMPLÉMENTÉ RÉELLEMENT)

Les 7 phases avec leur logique métier réelle (plus de `None`) :

### P0 — Import et Réception
- **fn_production** : Réceptionner les fichiers, calculer hash SHA-256, vérifier les doublons, enregistrer dans `documents`
- **fn_verification** : Tous les fichiers sont lisibles, pas de corruption, hash unique
- **fn_test** : Le dossier fictif a un fichier test avec hash connu

### P1 — Classification et Intelligence IA
- **fn_production** : Segmenter si volumineux → envoyer à l'IA → extraire les données → classifier (entreprise, projet, département, type, métadonnées)
- **fn_verification** : Chaque champ de classification est à 100% de certitude. Si < 100% → blocage
- **fn_test** : Le dossier fictif a un document test dont la classification est connue

### P2 — Comptabilité et Saisie
- **fn_production** : Générer les écritures comptables à partir des données extraites. Chaque écriture porte son statut fiscal. Vérifier partie double.
- **fn_verification** : Total débits = total crédits au centime. Statut fiscal NOT NULL. Cohérence HT + TVA = TTC.
- **fn_test** : Écriture fictive avec résultat connu

### P3 — Rapprochement et Lettrage
- **fn_production** : Rapprocher les encaissements/décaissements avec les écritures et les relevés bancaires
- **fn_verification** : Chaque écriture est rapprochée ou signalée. Pas de mouvement orphelin.
- **fn_test** : Rapprochement fictif avec résultat connu

### P4 — Diagnostic et Nettoyage
- **fn_production** : Scanner toutes les incohérences : montants en suspens, écritures non lettrées, doublons, anomalies
- **fn_verification** : Chaque anomalie est soit résolue soit bloquée en attente
- **fn_test** : Des anomalies intentionnelles dans le dossier fictif sont toutes détectées

### P5 — Consolidation D/ND/FD/FND
- **fn_production** : Calculer le centre de coût par projet, consolider par associé et par entreprise, répartir les charges communes
- **fn_verification** : Double computation sur tous les calculs. Hash de non-régression. Somme parts = 100%.
- **fn_test** : Consolidation fictive avec résultat connu au centime

### P6 — Reporting et États
- **fn_production** : Générer les rapports (bilan, TCR, tableaux de bord, états par projet/associé/entreprise)
- **fn_verification** : Les rapports sont cohérents avec les données consolidées
- **fn_test** : Le rapport fictif correspond au rapport attendu

**Règle absolue** : score 100 pour passer. Si score < 100 → BLOCAGE. La triple boucle (production, vérification, test) est exécutée pour chaque phase.

---

# SOCLE 16 — BLOCAGE INTELLIGENT & CYCLE DE RÉSOLUTION 7 ÉTAPES

Identique au CDC v5.0 avec les corrections suivantes :

1. **DETECTE** — Identification précise du problème
2. **BLOQUE** — Opération suspendue, compteur visible
3. **NOTIFIE_4H** — Notification web + email après 4h (scheduler automatique)
4. **NOTIFIE_24H** — Escalade au DAF/Admin après 24h
5. **NOTIFIE_72H** — Alerte critique visible par tous
6. **EN_RESOLUTION** — Interface de résolution active
7. **RESOLU** — Réponse validée, reprise + re-vérification intégrale
8. **AUDIT** — Enregistrement complet dans audit_log

**Ajout v6 — Étape 5 validation** : quand l'utilisateur fournit une réponse, le système valide le format, la cohérence, et l'absence de conflit AVANT de reprendre.

**Ajout v6 — Scheduler** : un job asyncio tourne en permanence et escalade automatiquement les notifications selon les délais configurés.

Table `demandes_completion` enrichie : ajout `type_demande` (SAISIE_CHAMP/UPLOAD_FICHIER/VALIDATION_CHOIX), `format_attendu`, `demandeur_id`, `repondeur_id`, `fichier_joint_id`.

---

# SOCLE 17 — VÉRIFICATION EXTRÊME À 8 NIVEAUX

Tous les 8 niveaux du CDC v5.0 implémentés réellement :

1. **Unitaire** — Chaque donnée validée (type, bornes, format, NOT NULL)
2. **Intra-enregistrement** — HT + TVA = TTC exactement, somme parts = 100%
3. **Inter-enregistrements** — Encaissements ≤ contrat, stock ≥ 0, débits = crédits
4. **Double computation** — Deux chemins de calcul, delta toléré = 0.00 DA
5. **Dossiers fictifs** — Injection permanente, comparaison aux résultats attendus
6. **Non-régression** — Hash SHA-256, données clôturées inviolables
7. **Inter-entreprises** — Cohérence quand 2 entités sont impliquées (même montant, date, ref)
8. **Consolidation finale** — Vérification totale avant génération de rapports

---

# SOCLE 18 — API, RBAC, AUDIT TRAIL

## 18.1 — RBAC appliqué sur CHAQUE route

```python
@router.post("/ecritures", dependencies=[Depends(require_permission("comptabilite", "write"))])
```

Les 9 rôles : SUPER_ADMIN, ADMIN, DAF, COMPTABLE, ARCHIVISTE, CHEF_PROJET, COMMERCIAL, MAGASINIER, LECTEUR.

Matrice de permissions détaillée par rôle et par ressource.

## 18.2 — Audit Trail automatique

Middleware FastAPI qui enregistre automatiquement chaque appel API dans `audit_log` : utilisateur, action, table, ancien/nouveau, IP, horodatage. Rien ne disparaît. Jamais.

## 18.3 — Routes complètes

| Domaine | Routes |
|---------|--------|
| Auth | login, users CRUD |
| Dashboard | stats, compteurs blocages, positions associés |
| Entreprises | CRUD, projets par entreprise |
| Projets | CRUD, parts, historique entité |
| Associés | CRUD, résolution aliases, position nette |
| Capital & Retraits | apports, retraits, import fiches |
| Comptabilité | écritures, plan comptable, matrice 4 réalités, balance |
| Trésorerie | clients, encaissements, décaissements, échéancier |
| Stock | articles, mouvements, scan barcode, valorisation |
| Lots immobiliers | EDD par projet, statuts lots |
| Notaires & Transit | CRUD notaires, banques, transits, libérations |
| Workflow | dossiers, phases, blocages, résolutions |
| Consolidation | centre coût, par associé, par entreprise |
| Mutations | CRUD, chaînes, vérification cohérence |
| Vérification | double computation, hash, dossiers fictifs |
| Documents | upload, segmentation, extraction IA, classification |
| Reporting | export Excel/PDF/CSV |

---

# SOCLE 19 — FRONTEND REACT

Le frontend est construit en React 18 avec les modules suivants :

1. **Dashboard Principal** — Compteur de blocages IMPOSSIBLE À IGNORER, stats globales, positions associés, transits en cours
2. **Module Entreprises** — Liste, détail, projets associés
3. **Module Projets** — Détail, parts associés, centre de coût, lots EDD
4. **Module Documents** — Upload, segmentation automatique, classification IA, résolution blocages
5. **Module Comptabilité** — Saisie écritures, matrice 4 réalités, balance
6. **Module Trésorerie** — Clients, encaissements, décaissements, échéancier, alertes retard
7. **Module Stock** — Interface LAD, entrées/sorties, CUMP, impression tickets
8. **Module Notaires** — Transits en cours, libérations, suivi par notaire
9. **Module Associés** — Capital, retraits, position nette, historique
10. **Module Consolidation** — Tableaux par projet/associé/entreprise, export
11. **Module Workflow** — Pipeline visuel P0-P6, blocages, résolutions
12. **Module Résolution** — Interface dédiée pour chaque blocage

---

# SOCLE 20 — AUTOMATISATION MAXIMALE : LE SYSTÈME DONNE LES INSTRUCTIONS

## 20.1 — Principe : L'humain exécute, le système dirige

Le système affiche en permanence une **liste d'actions requises** classées par priorité. L'humain n'a pas à réfléchir sur ce qu'il doit faire. Le système lui dit exactement :

```
[CRITIQUE] 3 blocages en attente — Résoudre maintenant
  → Facture FAC-2024-0847 : montant TTC incohérent (Cliquer pour résoudre)
  → Document DOC-2026-1234 : entreprise non identifiée (Cliquer pour choisir)
  → Encaissement ENC-2026-0089 : projet manquant (Cliquer pour affecter)

[IMPORTANT] 2 transits notaire en attente de libération
  → Client Benali K. : VEFA signé le 15/02, libérer tranche 20% (Cliquer)
  → Client Hamidi S. : PV remise clés signé le 28/02, libérer tranche 5% (Cliquer)

[NORMAL] 12 documents importés hier, en attente de validation
  → 10 classés automatiquement (certitude 100%) — Valider en lot
  → 2 en attente de résolution — Cliquer pour traiter

[INFO] Phase P3 bloquée pour dossier WF-2026-042 — Score 87/100
  → 13 écritures non rapprochées — Voir détail
```

## 20.2 — Zéro initiative humaine requise

| Ce que l'humain fait | Ce que le système fait automatiquement |
|---------------------|---------------------------------------|
| Branche le scanner | Détecte le scanner, affiche le bouton "Scanner" |
| Appuie sur "Scanner" | Numérise, envoie à l'IA, extrait, classe, archive, saisit |
| Branche le LAD | Détecte le LAD, active le mode scan permanent |
| Scanne un article | Identifie, affiche stock, propose entrée/sortie |
| Importe un fichier Excel de 500 pages | Segmente, analyse chaque segment en parallèle, consolide, extrait tout |
| Clique "Valider" sur une résolution | Vérifie la réponse, reprend le traitement, re-vérifie l'étape |
| Ne fait rien | Le système rappelle, escalade, ne lâche jamais |

---

# SOCLE 21 — RÈGLES DE LIVRAISON ET TESTS

## 21.1 — Livrables exigés

1. Code source complet : backend FastAPI + frontend React
2. Migrations SQL réversibles (UP + DOWN)
3. Seeds complètes et CORRECTES (les erreurs v5 corrigées)
4. Suite de tests automatisés — une commande `make test`
5. Rapport de test complet RÉELLEMENT EXÉCUTÉ
6. Docker-compose fonctionnel — `make build && make up`
7. 5+ dossiers fictifs avec résultats pré-calculés dans la base
8. Configuration des API IA (Gemini + Vision) documentée
9. Agent scanner léger (si WebUSB non supporté)

## 21.2 — Critères de rejet (identiques v5.0 + ajouts v6)

Tout ce qui était dans v5.0 PLUS :
- Le rattachement projet-entreprise est incorrect → REJET
- Les parts d'associés ne correspondent pas à ce document → REJET
- Les mutations foncières ne sont pas dans les seeds → REJET
- Le pipeline P0-P6 n'a pas de logique métier réelle → REJET
- Le RBAC n'est pas appliqué sur les routes → REJET
- L'audit trail n'enregistre rien → REJET
- La segmentation de fichiers volumineux ne fonctionne pas → REJET
- Les dossiers fictifs ne sont pas implémentés → REJET
- Les charges communes ne sont pas réparties au prorata → REJET
- La position nette des associés n'est pas calculée → REJET

## 21.3 — Procédure de vérification

Étape 1 : `make build && make up` — démarrage en < 5 minutes avec seeds.
Étape 2 : `make test` — 100% PASS, 0 FAIL.
Étape 3 : Vérification seeds contre ce document, ligne par ligne.
Étape 4 : Import d'un fichier test de 50 pages → segmentation + analyse IA.
Étape 5 : Pipeline P0-P6 complet → chaque phase score 100.
Étape 6 : Injection données incomplètes → blocage chaque fois.
Étape 7 : Consolidation par projet/associé/entreprise → au centime.
Étape 8 : Dossiers fictifs → résultat = attendu, zéro écart.
Étape 9 : Scan document via interface → traitement automatique complet.
Étape 10 : Scan code-barres → mouvement stock automatique.

---

# ANNEXE A — CORRECTIONS v5.0 → v6.0

## A.1 — Erreurs de rattachement projets-entreprises CORRIGÉES

| Projet | v5.0 (FAUX) | v6.0 (CORRECT) |
|--------|-------------|----------------|
| EDEN | SARL-DP | ETS-DK |
| LYS | SARL-DP | SARL-DBPI |
| T21000 | SARL-DBPI | ETS-DK |
| IRENE | SARL-OC | SARL-DP |
| AUREA | SARL-SEN | SARL-DP |
| MOSQUEE | EURL-BBT | ETS-DK |

## A.2 — Erreurs de parts_projets CORRIGÉES

| Projet | v5.0 (FAUX) | v6.0 (CORRECT) |
|--------|-------------|----------------|
| T5000 | Ahmed 50%, Mohamed 50% | Laid 50%, Ahmed 50% |
| IRENE | Ahmed 60%, Boumerdassi 20%, Brahim 20% | Ahmed 60%, Mohamed 20%, Yazid 20% |
| MAGNOLIA | Ahmed 60%, Boumerdassi 20%, Brahim 20% | Ahmed 60%, Yazid 20%, Mohamed 20% |
| AUREA | Ahmed 60%, Moukhtari T. 20%, Moukhtari A. 20% | Ahmed 60%, Yazid 20%, Mohamed 20% |
| ASTERIA | Ahmed 60%, Moukhtari T. 20%, Moukhtari A. 20% | Ahmed 60%, Mohamed 20%, Yazid 20% |
| MOSQUEE | Ahmed 34%, Laid 33%, Mohamed 33% | Ahmed 34%, Yazid 33%, Mohamed 33% |

## A.3 — Aliases CORRIGÉS

| Associé | v5.0 | v6.0 (ajout) |
|---------|------|-------------|
| Boumerdassi | Boumerdassi Mustapha, Mustapha | + "Boumerdassi" seul |
| Brahim Amirat | Brahim Amirat, Brahim | + "Amirat" seul |
| Moukhtari Tarek | Moukhtari Tarek, Tarek | + "Moukhtari" seul |

---

# ANNEXE B — ARCHITECTURE TECHNIQUE DÉTAILLÉE

## B.1 — Variables d'environnement

```env
# Base de données
DB_HOST=db
DB_PORT=5432
DB_NAME=gfi_db
DB_USER=gfi_user
DB_PASSWORD=gfi_secure_password_2026

# JWT
JWT_SECRET=gfi-jwt-secret-key-v6-production-2026

# IA — Google Cloud
GOOGLE_VISION_API_KEY=<à fournir>
GEMINI_API_KEY=<à fournir>

# Limites IA
MAX_PARALLEL_SEGMENTS=5
GEMINI_MODEL_FLASH=gemini-2.0-flash
GEMINI_MODEL_PRO=gemini-1.5-pro
```

## B.2 — Structure des fichiers backend

```
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── core/
│   │   ├── rbac.py              — Matrice de permissions 9 rôles
│   │   ├── audit.py             — Middleware audit trail automatique
│   │   └── scheduler.py         — Job escalade notifications blocages
│   ├── services/
│   │   ├── auth.py
│   │   ├── entreprises.py
│   │   ├── comptabilite.py
│   │   ├── tresorerie.py
│   │   ├── stock.py
│   │   ├── consolidation.py
│   │   ├── workflow.py
│   │   ├── verification.py
│   │   ├── transit_notaire.py   — NOUVEAU
│   │   ├── capital_associes.py  — NOUVEAU
│   │   ├── mutations.py         — NOUVEAU
│   │   ├── lots_immobiliers.py  — NOUVEAU
│   │   ├── reporting.py         — NOUVEAU
│   │   └── ia/                  — NOUVEAU
│   │       ├── segmentation.py  — Découpe fichiers volumineux
│   │       ├── vision.py        — Google Cloud Vision
│   │       ├── gemini.py        — Gemini Flash / Pro
│   │       ├── extraction.py    — Extraction structurée JSON
│   │       ├── classification.py— Classification auto entreprise/projet/dept
│   │       └── consolidation_ia.py — Fusion résultats segments
│   ├── routers/
│   │   ├── ... (tous les routers existants + nouveaux)
│   │   ├── transit_router.py
│   │   ├── capital_router.py
│   │   ├── mutations_router.py
│   │   ├── lots_router.py
│   │   ├── documents_router.py  — Upload + segmentation + IA
│   │   └── reporting_router.py
│   └── schemas/
│       └── ... (tous les schémas Pydantic avec validations strictes)
├── migrations/
│   ├── 001_schema_core.sql      — CORRIGÉ
│   ├── 002_documents_archivage.sql
│   ├── 003_comptabilite.sql
│   ├── 004_tresorerie.sql       — ENRICHI
│   ├── 005_stock_paie_fiscal.sql
│   ├── 006_workflow_blocages.sql — ENRICHI
│   ├── 007_seeds.sql            — CORRIGÉ (rattachements + parts)
│   ├── 008_plan_comptable_scf.sql
│   ├── 009_notaires_banques.sql — NOUVEAU
│   ├── 010_capital_retraits.sql — NOUVEAU
│   ├── 011_lots_immobiliers.sql — NOUVEAU
│   ├── 012_ia_segments.sql      — NOUVEAU
│   ├── 013_dossiers_fictifs.sql — NOUVEAU
│   └── 014_seeds_mutations.sql  — NOUVEAU
└── tests/
    ├── test_layer1_database.py  — Seeds corrigées vérifiées
    ├── test_layer2_services.py  — Chaque service testé
    ├── test_layer3_verification.py — Double computation, hash, dossiers fictifs
    ├── test_layer4_api.py       — RBAC, validation, audit trail
    ├── test_layer5_frontend.py  — Tests fonctionnels
    ├── test_layer6_pipeline.py  — P0 à P6 complet
    ├── test_transit_notaire.py  — Libération tranches
    ├── test_capital_retraits.py — Position nette
    ├── test_ia_segmentation.py  — Découpe + consolidation
    └── test_corrections_v6.py   — Toutes les corrections v5→v6 vérifiées
```

---

**FIN DU BLUEPRINT GFI SYSTEM v6.0**

Ce document est la source de vérité unique. Chaque ligne de code doit être conforme à ce document.
Chaque écart est un motif de rejet. Zéro tolérance. Zéro erreur. 100% ou STOP.
