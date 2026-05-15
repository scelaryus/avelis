# RAPPORT D'AUDIT — APP vs BLUEPRINT v6.0

**Date** : Audit complet  
**Méthode** : Cross-référencement ligne par ligne des 3 documents de spécification contre le code source actuel  
**Verdict global** : ❌ **ÉCART CRITIQUE — L'application actuelle couvre ~15-20% des exigences du Blueprint v6.0**

---

## 1. RÉSUMÉ EXÉCUTIF

L'application actuelle est un **prototype fonctionnel générique de gestion documentaire avec IA**, mais elle ne correspond **PAS** au système GFI spécifié dans le Blueprint. La majorité des fonctionnalités métier cœur (comptabilité algérienne, 4 réalités financières, multi-entreprises, circuit espèces, etc.) sont **absentes**.

---

## 2. AUDIT PAR SOCLE — Blueprint Master Prompt v6.0

### SOCLE 1 — Architecture Globale
| Exigence | Statut | Détails |
|----------|--------|---------|
| Stack Python/FastAPI/PostgreSQL/React | ⚠️ Partiel | FastAPI ✅, React ✅, mais SQLite au lieu de PostgreSQL, pas de Docker |
| Scanner USB/Réseau (TWAIN/WIA) | ❌ Absent | Aucune intégration scanner |
| Lecteur codes-barres USB (HID) | ❌ Absent | Aucune intégration LAD |
| PWA (Progressive Web App) | ❌ Absent | App Vite classique, pas de service worker |

### SOCLE 2 — Cerveau IA : Intelligence Documentaire
| Exigence | Statut | Détails |
|----------|--------|---------|
| Google Cloud Vision API | ❌ Absent | OCR configuré pour PaddleOCR/Tesseract mais pas implémenté réellement |
| Gemini Flash / Pro | ❌ Absent | Pas d'intégration Gemini, utilise OpenAI-compatible via httpx |
| Segmentation intelligente fichiers volumineux | ❌ Absent | Agent `segment.py` existe mais segmente en régions de page, pas en chunks de PDF multi-pages |
| Analyse parallèle segments (asyncio, max 5) | ❌ Absent | |
| Consolidation inter-segments | ❌ Absent | |
| Prompts d'extraction spécialisés (facture algérienne, relevé bancaire, bulletin paie) | ❌ Absent | Un seul prompt générique d'extraction |
| Sélection modèle IA selon volume (≤30p Flash, >30p Pro) | ❌ Absent | |
| Connexion scanner (WebUSB / agent local) | ❌ Absent | |

### SOCLE 3 — Base de Données v6.0 (45+ tables)
| Exigence | Statut | Détails |
|----------|--------|---------|
| Tables Core (users, audit_log, parametres, entreprises, exercices, associes, projets, parts_projets) | ❌ Majeur | Seuls `users`, `audit_log`, `tenants` existent. Pas de: `entreprises`, `exercices`, `associes`, `projets`, `parts_projets`, `parametres` |
| Tables Documents (import_sessions, documents, versions_documents, archivage_physique) | ⚠️ Partiel | `documents` ✅, `artifacts` ✅. Pas de: `import_sessions`, `versions_documents`, `archivage_physique` |
| Tables Comptabilité (plan_comptable, journaux, ecritures_comptables, lignes_ecritures) | ⚠️ Partiel | `chart_of_accounts` ✅, `journal_entries` ✅, `journal_lines` ✅. Pas de `journaux` séparés |
| Tables Trésorerie (clients, comptes_bancaires, encaissements, fournisseurs, decaissements, echeancier_clients) | ❌ Majeur | Module ADV a `clients` mais pas: `comptes_bancaires`, `encaissements` séparés, `fournisseurs`, `decaissements`, `echeancier_clients` |
| Tables Stock & Paie (articles_stock, mouvements_stock, employes, bulletins_paie, declarations_fiscales) | ❌ Majeur | `employees` ✅, `payroll_proposals` ✅ mais simplifiés. Pas de: `articles_stock`, `mouvements_stock`, `declarations_fiscales` |
| Tables Workflow (workflow_dossiers, workflow_phases_log, demandes_completion, centre_cout, consolidation_associes/entreprises, verifications_hash) | ❌ Majeur | `workflows` ✅ mais simplifié. Pas de: `demandes_completion`, `centre_cout` temps réel, `consolidation_*`, `verifications_hash` |
| Tables v6.0 nouvelles (notaires, banques_partenaires, comptes_transitoires_notaires, lots_immobiliers, capital_associes, retraits_associes, mutations_foncieres, document_segments, ia_extraction_log, dossiers_fictifs_reference) | ❌ Tout absent | Aucune de ces tables n'existe |

**Tables dans l'app : 21. Exigées par le Blueprint : 49+. Manquantes : ~28+ tables.**

### SOCLE 4 — Les 4 Réalités Financières (RD/RND/FD/FND)
| Exigence | Statut | Détails |
|----------|--------|---------|
| Champ `statut_fiscal` ENUM(REEL_DECLARE, REEL_NON_DECLARE, FICTIF_DECLARE, FICTIF_NON_DECLARE, EN_ATTENTE) sur TOUTES les tables financières | ❌ Absent | Aucune table ne porte ce champ |
| Double réalité D/ND sur chaque flux | ❌ Absent | Concept complètement absent |
| Décision manuelle REEL/FICTIF (unique action manuelle) | ❌ Absent | |
| Centre de coût 3 colonnes (DECLARE / NON_DECLARE / TOTAL REEL) | ❌ Absent | |

### SOCLE 5 — Multi-Entreprises (6 entités)
| Exigence | Statut | Détails |
|----------|--------|---------|
| 6 entités juridiques (ETS-DK, SARL-DP, SARL-DBPI, SARL-OC, SARL-SEN, EURL-BBT) | ❌ Absent | Modèle `Tenant` est générique, pas les 6 entreprises spécifiques |
| Rattachement correct projets ↔ entreprises | ❌ Absent | Pas de table `projets` |
| Seeds des 6 entreprises + 12 projets | ❌ Absent | Seul un tenant + admin sont seedés |

### SOCLE 6 — Multi-Associés + Capital & Retraits
| Exigence | Statut | Détails |
|----------|--------|---------|
| 9 associés avec aliases | ❌ Absent | |
| Résolution aliases (Levenshtein) | ❌ Absent | |
| Capital versé et retraits par projet | ❌ Absent | |
| Position nette par associé | ❌ Absent | |

### SOCLE 7 — Cartographie des 12 Projets
| Exigence | Statut | Détails |
|----------|--------|---------|
| 12 projets (JASMIN, EDEN, OPERA, LYS, T21000, T5000, T2400, IRENE, MAGNOLIA, AUREA, ASTERIA, MOSQUEE) | ❌ Absent | |
| Parts d'associés par projet | ❌ Absent | |
| 1 454 clients | ❌ Absent | |

### SOCLE 8 — Mutations Foncières
| ❌ Complètement absent | Pas de table ni de logique |

### SOCLE 9 — Comptes Transitoires Notaires & Banques Partenaires
| ❌ Complètement absent | Pas de table ni de logique |

### SOCLE 10 — Encaissements Clients (4 réalités)
| ❌ Complètement absent | Les `payments` ADV sont un simple enregistrement, sans 4 réalités |

### SOCLE 11 — Décaissements (8 catégories)
| ❌ Complètement absent | Pas de table `decaissements` |

### SOCLE 12 — Stock, Magasin & LAD
| ❌ Complètement absent | Aucun module stock |

### SOCLE 13 — Centre de Coût Ultra-Réel
| Exigence | Statut | Détails |
|----------|--------|---------|
| Calcul temps réel par projet/mois | ❌ Absent | `cost_center_allocations` existe mais ne fait pas de calcul GFI |
| Répartition charges communes au prorata CA | ❌ Absent | |
| Double computation obligatoire | ❌ Absent | |
| Montants en transit notaire | ❌ Absent | |

### SOCLE 14 — Consolidation Bénéfices (par projet/associé/entreprise)
| ❌ Complètement absent |

### SOCLE 15 — Pipeline 7 Phases (P0-P6)
| Exigence | Statut | Détails |
|----------|--------|---------|
| 7 phases séquentielles avec triple boucle (Production/Vérification/Test) | ❌ Absent | Le graph `document_to_ledger` a 17 nœuds linéaires mais ne correspond PAS aux 7 phases du Blueprint. Pas de triple boucle. |
| P0 Import en Masse (Drive, Cloud, Scanner, ZIP, chunked) | ❌ Absent | Upload simple uniquement |
| P1 Classification IA (multi-dimensions, arbre 13 catégories) | ⚠️ Partiel | `doc_type_router` classifie en 8 types génériques par regex, pas les 13 catégories algériennes |
| P2 Import Assiette Comptable (CIEL/EBP/Sage parser) | ❌ Absent | |
| P3 Rapprochement Bancaire + Circuit Espèces | ❌ Absent | |
| P4 Diagnostic & Nettoyage | ❌ Absent | |
| P5 Centre de Coût Réel (3 colonnes D/ND/Total) | ❌ Absent | |
| P6 Gestion Tiers (CRUD masse, profil fiscal D/ND) | ❌ Absent | |
| Score 100% pour passer chaque phase | ❌ Absent | |
| Dossiers fictifs de test | ❌ Absent | |

### SOCLE 16 — Blocage Intelligent (Cycle 7 étapes)
| Exigence | Statut | Détails |
|----------|--------|---------|
| 8 étapes de résolution (DETECTE→AUDIT) | ⚠️ Partiel | Le workflow peut être BLOCKED et l'anomaly agent détecte, mais pas le cycle complet 7 étapes |
| Notifications 4h/24h/72h (scheduler asyncio) | ❌ Absent | |
| Table `demandes_completion` enrichie | ❌ Absent | |

### SOCLE 17 — Vérification 8 Niveaux
| Exigence | Statut | Détails |
|----------|--------|---------|
| 8 niveaux de vérification (unitaire → consolidation finale) | ❌ Absent | L'agent `verification.py` fait des checks basiques (HT+TVA=TTC), pas les 8 niveaux |
| Hash SHA-256 non-régression | ⚠️ Partiel | `sha256` sur documents uniquement |
| Dossiers fictifs avec résultats pré-calculés | ❌ Absent | |

### SOCLE 18 — API, RBAC 9 rôles, Audit Trail
| Exigence | Statut | Détails |
|----------|--------|---------|
| 9 rôles (SUPER_ADMIN, ADMIN, DAF, COMPTABLE, ARCHIVISTE, CHEF_PROJET, COMMERCIAL, MAGASINIER, LECTEUR) | ❌ | 5 rôles seulement (admin, accountant, hr_manager, sales, viewer) |
| Matrice de permissions par rôle × ressource | ❌ | `require_role()` vérifie le rôle mais pas de matrice détaillée |
| Audit Trail middleware automatique | ⚠️ Partiel | Table `audit_log` existe mais pas de middleware auto |
| Routes complètes (17+ domaines listés) | ❌ | 7 routers au lieu de 17+ |

### SOCLE 19 — Frontend React (12 modules)
| Exigence | Statut | Détails |
|----------|--------|---------|
| Dashboard principal (blocages, stats, positions associés, transits) | ❌ | Pas de dashboard global |
| Module Entreprises | ❌ Absent | |
| Module Projets | ❌ Absent | |
| Module Documents (upload, segmentation, classification, résolution) | ⚠️ | Page documents basique, pas de classification UI |
| Module Comptabilité (matrice 4 réalités, balance) | ⚠️ | Page comptabilité basique |
| Module Trésorerie (clients, échéancier, alertes retard) | ❌ Absent | |
| Module Stock (LAD, entrées/sorties, CUMP, tickets) | ❌ Absent | |
| Module Notaires (transits, libérations) | ❌ Absent | |
| Module Associés (capital, retraits, position nette) | ❌ Absent | |
| Module Consolidation (tableaux export) | ❌ Absent | |
| Module Workflow (pipeline visuel P0-P6) | ⚠️ | Page workflow basique |
| Module Résolution (interface blocages) | ❌ Absent | |

**Pages frontend existantes : 7 (Login, Documents, Workflows, Accounting, HR, ADV, Admin)**
**Pages frontend requises : 12+ modules spécialisés avec dashboards, filtres, export**

### SOCLE 20 — Automatisation (Actions Requises, Zéro initiative humaine)
| ❌ Complètement absent | Pas de liste d'actions requises, pas de notifications proactives |

### SOCLE 21 — Livraison et Tests
| Exigence | Statut | Détails |
|----------|--------|---------|
| Migrations SQL réversibles | ❌ | Auto-create tables via SQLAlchemy |
| Seeds complètes (6 entreprises, 12 projets, 9 associés, parts, mutations) | ❌ | 1 tenant + 1 admin uniquement |
| Docker-compose | ❌ Absent | |
| 5+ dossiers fictifs | ❌ Absent | |
| Agent scanner | ❌ Absent | |

---

## 3. AUDIT — Blueprint Test (Blueprint_Test.md)

### 7 Phases de Workflow
| Phase | Statut | Détails |
|-------|--------|---------|
| Phase 0 — Import en Masse (Drive, Cloud, Scanner, ZIP) | ❌ | Upload simple uniquement |
| Phase 1 — Analyse, Classification, Archivage + Décision REEL/FICTIF | ❌ | Classification regex basique, pas de décision D/ND |
| Phase 2 — Import Assiette Comptable + Rapprochement | ❌ | Pas de parseur CIEL/EBP/Sage |
| Phase 3 — Rapprochement Bancaire + Circuit Espèces + 3 États d'Écarts | ❌ | |
| Phase 4 — Analyse Caisse + Consolidation | ❌ | |
| Phase 5 — Centre Coût 3 colonnes D/ND/Réel | ❌ | |
| Phase 6 — Gestion Tiers CRUD Masse | ❌ | |

### 6 Modules Métier
| Module | Statut |
|--------|--------|
| Stock/Magasin/Inventaire (code-barres photo, douchette) | ❌ Absent |
| Consommation/EDD Projet | ❌ Absent |
| RH/Paie D/ND (CNAS, IRG barème algérien) | ⚠️ Partiel (module RH simplifié, CNSS marocain, pas algérien) |
| Juridique/Contrats | ❌ Absent |
| Contentieux | ❌ Absent |
| Circuit Espèces | ❌ Absent |

### 8 Couches IA
| Couche | Statut |
|--------|--------|
| 1. OCR Adaptatif (auto-apprentissage) | ❌ |
| 2. Classification Évolutive (recalibrage) | ❌ |
| 3. Détection Anomalies Pattern | ⚠️ Partiel (agent anomaly basique) |
| 4. Prédiction Trésorerie (J+30/60/90) | ❌ |
| 5. Scoring Fournisseurs/Clients | ❌ |
| 6. Suggestions Rapprochement | ❌ |
| 7. Détection Fraude | ❌ |
| 8. Règles Métier Auto | ❌ |

### 12 Modules Transversaux
| Module | Statut |
|--------|--------|
| RBAC Multi-Utilisateurs (9 rôles) | ⚠️ 5 rôles |
| Lettrage Comptable | ❌ |
| Échéances Fourn/Client (alertes J-30/J-7) | ❌ |
| Conformité SCF Algérien (G50, G50A, Tp, C20) | ❌ |
| Recherche Full-Text | ❌ |
| Versioning (rollback) | ❌ |
| Gestion Exercices (ouverture/clôture) | ⚠️ Partiel (accounting_periods) |
| Backup/Restauration | ❌ |
| Rapports Personnalisables | ❌ |
| API Ouverte REST | ✅ FastAPI + OpenAPI |
| Notifications Multi-Canal (Email+SMS) | ❌ |
| Prédiction IA | ❌ |

### Triple Boucle (Production/Vérification/Test)
| ❌ Absent | Les agents s'exécutent séquentiellement sans triple boucle |

### Système de Vérification 3 Niveaux Croisés
| ❌ Absent | Pas d'implémentation des 3 niveaux (interne, croisée, globale) |

### 25 Livrables
| ❌ 0/25 | Aucun des 25 livrables imprimables n'est généré |

---

## 4. AUDIT — changment.md (Spécification Ultra-Détaillée v6.0-C)

### Chapitre 1 — Taxonomie Charges (Projet vs Commune)
| ❌ Absent | Pas de distinction charge projet / charge commune |

### Chapitre 2 — Ratio Répartition Charges Communes
| ❌ Absent | Pas de calcul de ratio au CA ou aux dépenses |

### Chapitre 3 — Centre de Coût Temps Réel (formules complètes)
| ❌ Absent | Les formules détaillées (A1-A4, B1-B7, C1, D1-D3, E1-E5) ne sont pas implémentées |

### Chapitre 4 — RH/Paie D/ND + Assiette PC Paie
| Exigence | Statut |
|----------|--------|
| Double bulletin (déclaré + non-déclaré) | ❌ |
| Calcul IRG barème algérien | ❌ (calcul CNSS/AMO marocain actuel) |
| CNAS salarié 9%, patronal 26% | ❌ |
| Imputation paie multi-projets | ❌ |
| Table mouvements_caisse | ❌ |

### Chapitre 5 — Clients/Fournisseurs/RH D/ND
| ❌ Absent | Pas de double réalité sur les tiers |

### Chapitre 6 — Dashboard Ultra-Détaillé
| Exigence | Statut |
|----------|--------|
| Page d'accueil avec 8 compteurs + actions requises + centre de coût + positions associés | ❌ |
| Écran Centre de Coût par Projet (filtres, tableau détaillé, boutons export) | ❌ |
| Écran Consolidé tous projets | ❌ |
| Écran Employés/Paie avec fiche de paie détaillée D/ND | ❌ |
| Écran Caisse (mouvements espèces) | ❌ |
| Écran Clients par Projet (692 clients, avancement, retards) | ❌ |
| Écran Fournisseurs (4 réalités) | ❌ |

### Chapitre 7 — Éléments Imprimables
| ❌ Absent | Aucun des 16 documents imprimables n'est généré (pas de CSS @media print, pas de weasyprint/reportlab) |

### Chapitre 8 — Règles de Calcul Exhaustives
| Exigence | Statut |
|----------|--------|
| IRG barème progressif algérien | ❌ |
| CNAS 9%/26%, CACOBATPH 1.75%, CASNOS 15% | ❌ |
| TVA 19%/9% (tolérance 0 DA) | ❌ |
| CUMP calcul automatique | ❌ |
| G50 mensuel | ❌ |

### Chapitre 9 — Paramètres Système (30+ paramètres)
| ❌ Absent | La table `parametres` avec 30+ clés n'existe pas |

---

## 5. SCORECARD

| Domaine | Score |
|---------|-------|
| Architecture technique | 30% |
| Intelligence documentaire (IA) | 10% |
| Base de données (tables) | 21/49 = 43% (mais contenu incorrect) |
| 4 Réalités financières D/ND | 0% |
| Multi-entreprises (6 entités) | 0% |
| Multi-associés (9 associés) | 0% |
| Projets (12 projets) | 0% |
| Pipeline 7 phases | 0% |
| Module Stock/Magasin/LAD | 0% |
| Module RH/Paie algérien | 15% |
| Module Juridique/Contentieux | 0% |
| Circuit Espèces | 0% |
| Centre de Coût temps réel | 5% |
| Consolidation | 0% |
| RBAC 9 rôles | 55% |
| Audit Trail | 25% |
| Frontend (12 modules) | 15% |
| Livrables imprimables (25) | 0% |
| Tests/Dossiers fictifs | 10% |
| Seeds complètes | 5% |
| **TOTAL ESTIMÉ** | **~12-15%** |

---

## 6. CONCLUSION

L'application actuelle est un **framework de traitement documentaire générique** avec un pipeline d'agents (ingest→OCR→extraction→comptabilité). Elle a une bonne architecture de base (FastAPI + React + orchestrateur DAG) mais elle **ne correspond pas** au système GFI v6.0 spécifié dans le Blueprint, qui est un **ERP complet de gestion immobilière algérienne** avec :

- **Domaine métier** complètement différent (immobilier algérien vs. traitement documentaire générique)
- **Double réalité D/ND** (concept central absent)
- **30+ tables manquantes** (entreprises, projets, associés, stock, mutations, notaires, etc.)
- **6 modules métier manquants** (stock, juridique, contentieux, circuit espèces, consommation, etc.)
- **Dashboard et écrans détaillés** non implémentés
- **Conformité SCF algérien** absente (le système actuel est orienté Maroc/CNSS)
- **Livrables imprimables** totalement absents

L'application nécessite une **réécriture majeure** pour correspondre aux spécifications du Blueprint v6.0.
