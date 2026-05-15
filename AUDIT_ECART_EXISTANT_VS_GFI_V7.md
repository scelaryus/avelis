# AUDIT ÉCART — Solution Existante vs gfi_v7/

**Date** : 2026-03-13
**Périmètre** : `avelis-promo/app/` (existant) vs `avelis-promo/gfi_v7/` (Blueprint GFI v7.0)

---

## 1. FICHIERS MANQUANTS DE CHAQUE CÔTÉ

### 1.1 Fichiers présents dans `gfi_v7/` mais ABSENTS de l'existant

| Fichier gfi_v7 | Rôle | Impact |
|---|---|---|
| `app/models/cff.py` | Tables `cff_factures`, `cff_imputation_associes` | **CRITIQUE** — Aucun modèle CFF dans l'existant |
| `app/models/entreprises.py` | Table `entreprises` dédiée + `entreprise_associes` + `origine_capital_detail` | L'existant fusionne dans `financial.py` |
| `app/models/associes.py` | Table `associes` dédiée + `associes_alias` + `comptes_courants_associes` | L'existant éclate entre `financial.py` et `finance_associes.py` |
| `app/models/projets.py` | Tables `projets`, `projet_associes`, `projets_alias`, `clients`, `appels_de_fonds`, `cessions_parts` | L'existant éclate entre `financial.py`, `registry.py`, `finance_associes.py` |
| `app/models/rh.py` | Tables `employes`, `contrats_travail`, `fiches_paie` avec `realite_financiere` RF1-RF4 | L'existant a `hr.py` sans RF |
| `app/models/juridique_mg.py` | Tables `dossiers_juridiques`, `permis_autorisations`, `fournisseurs`, `commandes_achats`, `stock_materiel` | L'existant a `legal.py` partiel |
| `app/models/meta_ia.py` | 6 tables méta-IA : `meta_objets_metier_detectes`, `meta_rapports_lacunes`, `meta_specifications_generees`, `meta_code_genere`, `meta_resultats_tests`, `meta_feedback_apprentissage` | **ABSENT** — 0 tables méta-IA dans l'existant |
| `app/services/cff_engine.py` | Classe `CFFEngine`, fonctions `calculer()`, `verifier_kt01()`, `verifier_kt02()` | **CRITIQUE** — Aucun moteur CFF dans l'existant |
| `app/services/alias_resolver.py` | Classe `AliasResolver` : `resoudre_associe()`, `resoudre_projet()`, `resoudre_entite()`, `verifier_unicite_projet()` | L'existant a `blocking_rules.py:validate_associate_exact_match()` (partiel) |
| `app/api/v1/endpoints/transactions.py` | CRUD transactions avec RF1-RF4 obligatoire | **ABSENT** |
| `app/api/v1/endpoints/cff.py` | Endpoints `POST /cff/calculer`, `GET /cff/verifier-kt01/{code}` | **ABSENT** |
| `app/api/v1/endpoints/cloture.py` | Endpoint `POST /cloture/executer` | L'existant a `api/finance_associes.py` |
| `app/api/v1/endpoints/associes.py` | CRUD associés + résolution alias | **ABSENT** (endpoint dédié) |
| `app/api/v1/endpoints/entreprises.py` | CRUD entreprises + participations | **ABSENT** (endpoint dédié) |
| `app/api/v1/endpoints/projets.py` | CRUD projets + participations | **ABSENT** (endpoint dédié) |
| `app/api/v1/endpoints/health_check.py` | Health check + META_AUTO_DEPLOY flag | **ABSENT** |
| `app/core/rbac.py` | RBAC avec 15 rôles GFI-spécifiques | L'existant a `services/rbac.py` avec rôles génériques |
| `seeds/seed_all.py` | Seed master : 9 associés / 12 projets / 15 rôles / UUID fixes | L'existant a `services/seed_import.py` (structure différente) |
| `tests/test_kill_tests.py` | Kill tests KT-01 → KT-09 + sanity checks + VSR-01 | **ABSENT** |
| `Dockerfile` | Conteneurisation | **ABSENT** |
| `docker-compose.yml` | PostgreSQL + Redis + API | **ABSENT** |
| `alembic.ini` | Config Alembic PostgreSQL | **ABSENT** (l'existant utilise Alembic mais SQLite) |

### 1.2 Fichiers présents dans l'existant mais ABSENTS de `gfi_v7/`

| Fichier existant | Rôle | Décision fusion |
|---|---|---|
| `app/agents/*.py` (22 fichiers) | Pipeline IA : OCR, extraction, normalisation, segmentation, etc. | **CONSERVER** — absent de v7 par design |
| `app/orchestrator/engine.py`, `graphs.py` | Orchestrateur workflow LanGraph | **CONSERVER** |
| `app/services/cost_center_engine.py` | Moteur centre de coût | **CONSERVER** — v7 stocke mais ne calcule pas |
| `app/services/edd_service.py`, `edd_excel_import.py`, `edd_ocr_service.py` | BIM/EDD (état descriptif détaillé) | **CONSERVER** |
| `app/services/pricing_service.py` | Pricing BIM lots immobiliers | **CONSERVER** |
| `app/services/spi_engine.py`, `spi_scheduler.py` | SPI 360° scoring + scheduler | **CONSERVER** |
| `app/services/proof_evaluator.py` | Évaluation preuves IA | **CONSERVER** |
| `app/services/document_classifier.py` | Classification documents IA | **CONSERVER** |
| `app/services/journal_matcher.py` | Rapprochement écritures | **CONSERVER** |
| `app/services/google_drive.py` | Import Google Drive | **CONSERVER** |
| `app/services/llm_graph.py` | Graphe LLM | **CONSERVER** |
| `app/services/task_planner.py` | Planificateur tâches | **CONSERVER** |
| `app/models/bim_edd.py` | 7 tables BIM/EDD (re_projects → re_validations) | **CONSERVER** |
| `app/models/spi.py` | Tables SPI (scores, rules, KPIs, bonus_malus) | **CONSERVER** |
| `app/models/adv.py` | Tables ADV (clients, contrats, créances, paiements) | **CONSERVER** |
| `app/models/treasury.py` | Tables trésorerie (journaux, comptes bancaires, bulletins paie) | **CONSERVER** — v7 les a inline |
| `app/models/integrations.py` | Tables intégrations | **CONSERVER** |
| `app/api/bim.py` | Endpoints BIM/EDD | **CONSERVER** |
| `app/api/spi.py` | Endpoints SPI | **CONSERVER** |
| `app/api/cost_center.py` | Endpoints centre coût | **CONSERVER** |
| `app/api/hr.py` | Endpoints RH (plus riche que v7) | **CONSERVER** |
| `app/api/mfa.py` | Endpoints MFA TOTP | **CONSERVER** |
| `app/api/imports.py` | Import documents | **CONSERVER** |
| `app/api/treasury.py` | Endpoints trésorerie | **CONSERVER** |
| `app/api/workflows.py` | Endpoints workflows | **CONSERVER** |
| `app/storage/service.py` | Service S3/MinIO | **CONSERVER** |
| `frontend/` | Frontend React/Vite/Tailwind | **CONSERVER** |
| `alembic/versions/001-006` | 6 migrations SQLite | Migrer vers PostgreSQL |
| `tests/` (9 fichiers) | Tests existants | **CONSERVER** + ajouter kill tests |

---

## 2. TABLES DB MANQUANTES + COLONNES DIFFÉRENTES

### 2.1 Tables présentes dans `gfi_v7/` mais ABSENTES de l'existant

| Table gfi_v7 | Modèle gfi_v7 | Colonnes clés absentes |
|---|---|---|
| `cff_factures` | `app/models/cff.py:CFFFacture` | `entreprise_id`, `cff_tva`, `cff_ibs`, `cff_tap`, `cff_cnas`, `cff_timbre`, `cff_total` |
| `cff_imputation_associes` | `app/models/cff.py:CFFImputationAssocie` | `pourcentage_entreprise` (% entreprise, PAS projet) |
| `entreprise_associes` | `app/models/entreprises.py:EntrepriseAssocie` | `pourcentage` (% dans l'entreprise), `date_entree`, `date_sortie` |
| `origine_capital_detail` | `app/models/entreprises.py:OrigineCapitalDetail` | `realite_financiere` RF1-RF4, `montant`, `document_reference` |
| `transactions` | `app/models/finance.py:Transaction` | `realite_financiere` (Enum RF1-RF4 **OBLIGATOIRE**), `type_transaction`, `hash_sha256` |
| `flux_inter_projets` | `app/models/finance.py:FluxInterProjet` | `realite_financiere` RF1-RF4, `nature` (PRET_REMBOURSABLE, etc.), `source_externe` |
| `compensations_st` | `app/models/finance.py:CompensationST` | `sortie_cash_512` (KT-05), `type_ecriture`, `compte_debit/credit` |
| `centre_cout_mensuel` | `app/models/finance.py:CentreCoutMensuel` | `tnm_rf1/rf2/rf3/rf4`, `est_verrouille` |
| `clotures_mensuelles_repartitions` | `app/models/finance.py:ClotureMensuelleRepartition` | Table séparée pour distribution (v7 normalise) |
| `vehicules_groupe` | `app/models/finance.py:VehiculeGroupe` | Cycle complet : `cede_a_st_id`, `situation_deduction_id`, `prix_revente` |
| `projet_associes` | `app/models/projets.py:ProjetAssocie` | Table dédiée % projet (séparée de % entreprise) |
| `projets_alias` | `app/models/projets.py:ProjetAlias` | Alias projets structuré |
| `clients` | `app/models/projets.py:Client` | `numero_lot`, `surface_m2`, `prix_vente`, `montant_verse`, `montant_restant` |
| `contrats_travail` | `app/models/rh.py:ContratTravail` | `type_contrat` (CDI/CDD/ANEM/STAGE/JOURNALIER) |
| `fiches_paie` | `app/models/rh.py:FichePaie` | `realite_financiere` RF1/RF2, `cnas_salarial`, `cnas_patronal`, `irg_retenu` |
| `dossiers_juridiques` | `app/models/juridique_mg.py:DossierJuridique` | `est_succession` (FC-002), `montant_litige` |
| `permis_autorisations` | `app/models/juridique_mg.py:PermisAutorisation` | `type_permis`, `date_expiration` |
| `fournisseurs` | `app/models/juridique_mg.py:Fournisseur` | `est_gaceb`, `solde_avances` |
| `commandes_achats` | `app/models/juridique_mg.py:CommandeAchat` | `realite_financiere`, `est_avance_materiel` (KT-05) |
| `stock_materiel` | `app/models/juridique_mg.py:StockMateriel` | `code_article`, `quantite`, `valeur_unitaire` |
| `roles` | `app/models/rbac.py:Role` | 15 rôles GFI-spécifiques + `permissions` JSON |
| `utilisateurs` | `app/models/rbac.py:Utilisateur` | `associe_id`, `company_id` (Row Level Security) |
| `utilisateur_roles` | `app/models/rbac.py:UtilisateurRole` | Relation M:N user↔role par entreprise |
| `audit_log` | `app/models/rbac.py:AuditLog` | `realite_financiere`, `est_sensible`, `hash_sha256` |
| `meta_objets_metier_detectes` | `app/models/meta_ia.py` | Score confiance, type objet |
| `meta_rapports_lacunes` | `app/models/meta_ia.py` | Impact, résolution |
| `meta_specifications_generees` | `app/models/meta_ia.py` | Validation humaine |
| `meta_code_genere` | `app/models/meta_ia.py` | `auto_deploy = FALSE` (invariant critique) |
| `meta_resultats_tests` | `app/models/meta_ia.py` | Kill tests, couverture |
| `meta_feedback_apprentissage` | `app/models/meta_ia.py` | Boucle feedback IA |

### 2.2 Colonnes DIFFÉRENTES sur tables communes

| Table | Colonne | Existant | gfi_v7 | Écart |
|---|---|---|---|---|
| `clotures_mensuelles` | `ecart_computation` | **ABSENTE** | `Numeric(15,2)` — doit être 0.00 | **CRITIQUE** |
| `clotures_mensuelles` | `tnm_calcul_1` / `tnm_calcul_2` | **ABSENTES** | Stocke les 2 computations | **CRITIQUE** |
| `clotures_mensuelles` | `etape_courante` | **ABSENTE** | `Integer` 1-7 | Manque traçabilité étape |
| `clotures_mensuelles` | `statut` | `EN_COURS/SUCCES/ECHEC/ANNULEE` | `INITIEE/VALIDE/BLOQUE/ERREUR` | Enum différent |
| `mouvements_comptes_courants` | `realite_financiere` | **ABSENTE** | `String(4)` RF1-RF4 | **CRITIQUE** |
| `comptes_courants_associes` | `entreprise_id` | **ABSENTE** | `UUID FK` | v7 lie CCA à l'entreprise |
| `comptes_courants_associes` | `solde_bloque` | **ABSENTE** | `Numeric(15,2)` | Solde bloqué séparé |
| `employes` | `realite_financiere` | **ABSENTE** | `String(4)` RF1 si déclaré, RF2 sinon | **CRITIQUE** |
| `employes` | `nin` | **ABSENTE** | `String(20) unique` | NIN obligatoire dans v7 |
| `employes` | `est_declare_cnas` | **ABSENTE** | `Boolean` | Pilote RF1 vs RF2 |
| `entreprises` | `taux_ibs/taux_tap/taux_tva` | **ABSENTES** | `Numeric(5,4)` chacun | Nécessaire pour CFF |
| `entreprises` | `nif/nis/rc` | **ABSENTES** | `String` unique | Identifiants fiscaux |
| `projets` | `nb_clients_total` | **ABSENTE** | `Integer` | Comptage clients |
| `projets` | `est_abandonne` / `passif_residuel` | **ABSENTES** | `Boolean` / `Numeric` | Gestion projets abandonnés |
| `associes` | `ordre_priorite` | **ABSENTE** | `String(10)` A-I | Ordre hiérarchique associés |
| `associes` | `est_fondateur` | **ABSENTE** | `Boolean` | Distinction fondateur/non-fondateur |
| `associes` | `nin` | **ABSENTE** | `String(20) unique` | NIN obligatoire |
| `appels_de_fonds` | `socle_17_bloque` | **ABSENTE** | `Boolean` | Blocage si impayé |
| `cessions_parts` | `somme_parts_post` | **ABSENTE** | `Numeric(6,4)` doit = 100% (KT-09) | **CRITIQUE** |
| `cessions_parts` | `preemption_exerce` | **ABSENTE** | `Boolean` | Droit de préemption |

### 2.3 Tables présentes dans l'existant mais ABSENTES de `gfi_v7/`

| Table existant | Modèle existant | Décision |
|---|---|---|
| `re_projects`, `re_blocks`, `re_levels`, `re_units`, `re_unit_annexes` | `app/models/bim_edd.py` | **CONSERVER** |
| `re_pricing_rules`, `re_validations`, `re_edd_documents` | `app/models/bim_edd.py` | **CONSERVER** |
| `spi_scores`, `spi_rules`, `spi_kpis`, `spi_bonus_malus_rules` | `app/models/spi.py` | **CONSERVER** |
| `departments`, `ownership_relations`, `remuneration_baremes` | `app/models/spi.py` | **CONSERVER** |
| `tenants` | `app/models/core.py` | **CONSERVER** — multi-tenancy |
| `documents`, `workflows`, `artifacts` | `app/models/core.py` | **CONSERVER** — pipeline IA |
| `journal_entries`, `journal_lines` | `app/models/core.py` | **CONSERVER** |
| `chart_of_accounts`, `cost_centers`, `cost_center_allocations` | `app/models/core.py` | **CONSERVER** |
| `hr_tasks`, `task_notifications` | `app/models/hr.py` | **CONSERVER** |
| `payroll_proposals` | `app/models/hr.py` | **CONSERVER** — complémentaire à `fiches_paie` |
| `journaux`, `comptes_bancaires`, `bulletins_paie` | Migration 003 | **CONSERVER** |
| `declarations_fiscales`, `echeancier_clients` | Migration 003 | **CONSERVER** |
| `consolidation_associes`, `consolidation_entreprises` | Migration 003 | **CONSERVER** |
| `notaires`, `banques_partenaires`, `projet_notaires`, `projet_banques` | `app/models/registry.py` | **CONSERVER** |
| `lots_immobiliers` | Migration 003 | **CONSERVER** |
| `mutations_foncieres` | Migration 003 | **CONSERVER** |
| `import_sessions`, `versions_documents`, `archivage_physique` | Migration 003 | **CONSERVER** |
| `document_segments`, `ia_extraction_log` | Migration 003 | **CONSERVER** |
| `verifications_hash`, `workflow_dossiers`, `workflow_phases_log` | Migration 003 | **CONSERVER** |
| `demandes_completion` | Migration 003 | **CONSERVER** |
| `user_permissions` | Migration 006 | Remplacer par RBAC v7 |

---

## 3. RÈGLES MÉTIER — PRÉSENCE PAR CODEBASE

### 3.1 CFF = % entreprise (jamais % projet) + Yamina=0 dans DBPI/OC/EP/SEN/BIM

| Aspect | Existant | gfi_v7 | Verdict |
|---|---|---|---|
| **Table `cff_factures`** | **ABSENTE** | `gfi_v7/app/models/cff.py:9-30` | MANQUANT |
| **Table `cff_imputation_associes`** | **ABSENTE** | `gfi_v7/app/models/cff.py:33-44` | MANQUANT |
| **Moteur CFF (`CFFEngine`)** | **ABSENT** | `gfi_v7/app/services/cff_engine.py:40-152` | MANQUANT |
| **`CFFEngine.calculer()`** | **ABSENT** | `gfi_v7/app/services/cff_engine.py:66-118` — utilise `participations_entreprise` (jamais projet) | MANQUANT |
| **`CFFEngine.verifier_kt01()`** | **ABSENT** | `gfi_v7/app/services/cff_engine.py:120-133` — Yamina dans `{SARL-DBPI, SARL-OC, SARL-EP, SARL-SEN, EURL-BIM}` → 0 DA | MANQUANT |
| **`CFFEngine.verifier_kt02()`** | **ABSENT** | `gfi_v7/app/services/cff_engine.py:135-148` — Ahmed SARL-DP = 25% entreprise, PAS 60% projet | MANQUANT |
| **Table `entreprise_associes`** | **ABSENTE** (l'existant a `parts_projets` uniquement) | `gfi_v7/app/models/entreprises.py` — `pourcentage` = part dans l'ENTREPRISE | MANQUANT |
| **Seed Yamina 0%** | `seed_import.py:432-438` — DBPI/OC/EP/SEN shareholders **n'incluent PAS** Yamina | `gfi_v7/seeds/seed_all.py:111-128` — PARTICIPATIONS_ENTREPRISES **exclut** explicitement Yamina de DBPI/OC/EP/SEN/BIM | IMPLICITE vs EXPLICITE |
| **Endpoint CFF** | **ABSENT** | `gfi_v7/app/api/v1/endpoints/cff.py` | MANQUANT |

**Conclusion Règle CFF** : **0% implémenté dans l'existant**. Le moteur CFF entier est absent. L'existant n'a aucune table, aucun service, aucun endpoint CFF.

### 3.2 RF1/RF2/RF3/RF4 sur chaque transaction

| Aspect | Existant | gfi_v7 | Verdict |
|---|---|---|---|
| **Enum `RealiteFinanciere`** | **ABSENT** — l'existant utilise `StatutFiscal` (`REEL_DECLARE/REEL_NON_DECLARE/FICTIF`) dans `app/models/financial.py:29-39` | `gfi_v7/app/models/finance.py:12-17` — `RealiteFinanciere(RF1, RF2, RF3, RF4)` | **INCOMPATIBLE** — 3 valeurs (RD/RND/F) vs 4 (RF1/RF2/RF3/RF4) |
| **Colonne `realite_financiere` sur `transactions`** | **Table `transactions` ABSENTE** | `gfi_v7/app/models/finance.py:34` — `Column(SAEnum(RealiteFinanciere), nullable=False)` | MANQUANT |
| **RF sur `mouvements_comptes_courants`** | **ABSENTE** | `gfi_v7/app/models/associes.py` — `realite_financiere = Column(String(4))` | MANQUANT |
| **RF sur `flux_inter_projets`** | **ABSENTE** | `gfi_v7/app/models/finance.py:60` — `Column(SAEnum(RealiteFinanciere), nullable=False)` | MANQUANT |
| **RF sur `employes`** | **ABSENTE** | `gfi_v7/app/models/rh.py` — `realite_financiere = Column(String(4), default="RF1")` | MANQUANT |
| **RF sur `fiches_paie`** | **Table ABSENTE** | `gfi_v7/app/models/rh.py` — `realite_financiere = Column(String(4), default="RF1")` | MANQUANT |
| **RF sur `commandes_achats`** | **Table ABSENTE** | `gfi_v7/app/models/juridique_mg.py` — `realite_financiere = Column(String(4))` | MANQUANT |
| **RF sur `audit_log`** | **Table ABSENTE** | `gfi_v7/app/models/rbac.py` — `realite_financiere = Column(String(4))` | MANQUANT |
| **RF3 → CFF auto** | **ABSENT** | `gfi_v7/app/models/finance.py:16` — commentaire : "RF3 = Fictif Déclaré → génère CFF obligatoirement" | MANQUANT |
| **Endpoint transactions + RF** | **ABSENT** | `gfi_v7/app/api/v1/endpoints/transactions.py` | MANQUANT |

**Conclusion Règle RF1-RF4** : **0% implémenté dans l'existant**. L'existant utilise un modèle fiscal à 3 niveaux (RD/RND/F) incompatible avec le modèle à 4 réalités financières de v7.

### 3.3 Double computation clôture, écart = 0.00 DA

| Aspect | Existant | gfi_v7 | Verdict |
|---|---|---|---|
| **Service clôture** | `app/services/cloture_service.py:40-272` — `executer_cloture_mensuelle()` | `gfi_v7/app/services/cloture_engine.py:20-153` — `ClotureMensuelleEngine.executer()` | Les deux existent |
| **Étape 1 — Extraction TNM** | `cloture_service.py:52-66` — query `CentreCoutMensuel.resultat_ultra_reel` | `cloture_engine.py:44-47` — `_etape1_extraction_tnm()` | OK dans les deux |
| **Étape 2 — Double computation** | `cloture_service.py:68-93` — recompose TNM via 11 composantes (enc_rd, enc_rnd, gains_cnt, lib_transit - dec_rd, dec_rnd, cout_fd, pertes_cnt, stock_cump, masse_sal, cc_montant), vérifie `abs(TNM - TNM_verif) <= 0.01` | `cloture_engine.py:52-71` — appelle `_computations()` 2 fois, vérifie `ecart <= ECART_MAX` avec `ECART_MAX = Decimal("0.00")` | **DIFFÉRENCE CRITIQUE** : existant tolère ±0.01 DA, v7 exige exactement 0.00 DA |
| **Stockage écart** | **NON STOCKÉ** — `double_computation_ok` = booléen seulement | `cloture_engine.py:128` — colonne `ecart_computation` `Numeric(15,2)` | MANQUANT dans l'existant |
| **Stockage calcul_1 / calcul_2** | **NON STOCKÉS** | colonnes `tnm_calcul_1`, `tnm_calcul_2` sur `clotures_mensuelles` | MANQUANT dans l'existant |
| **Étape 3 — Montant libéré** | `cloture_service.py:96-100` — `TNM × 50%` si TNM > 0 | `cloture_engine.py:73-76` — `TNM × LIBERATION_RATIO(0.50)` | OK dans les deux |
| **Étape 4 — Distribution** | `cloture_service.py:103-121` — utilise `PartProjet.pourcentage` (% **PROJET**) | `cloture_engine.py:79-81` — utilise `participations[].pourcentage_entreprise` (% **ENTREPRISE**) | **ERREUR CRITIQUE** : l'existant distribue sur % projet au lieu de % entreprise |
| **Étape 5 — Solde disponible** | `cloture_service.py:190-228` — recalcule depuis mouvements, 50% du positif | `cloture_engine.py` — via `verifier_kt08()` | OK dans l'existant |
| **Étape 6 — Hash SHA-256** | `cloture_service.py:231-235` | `cloture_engine.py:83-91` | OK dans les deux |
| **Étape 7 — Verrouillage** | `cloture_service.py:237-260` — INSERT `ClotureMensuelle` | `cloture_engine.py:93-99` | OK dans les deux |
| **KT-08 — Blocage retrait** | `blocking_rules.py:22-47` — `validate_retrait_associe()` | `cloture_engine.py:139-150` — `verifier_kt08()` | OK dans les deux |
| **Scheduler** | `cloture_service.py:275-317` — `run_monthly_clotures_all()` | Non implémenté (config `CLOTURE_HEURE=2` seulement) | L'existant est plus avancé |

**Conclusion Règle Clôture** :
- **Existant** : implémenté mais avec **2 défauts critiques** :
  1. Tolérance 0.01 DA au lieu de 0.00 DA (`cloture_service.py:88`)
  2. Distribution sur `PartProjet.pourcentage` (% projet) au lieu de `entreprise_associes.pourcentage` (% entreprise) (`cloture_service.py:104-106`)
- **gfi_v7** : correct par design (0.00 DA, % entreprise)

---

## 4. SEEDS : 9 ASSOCIÉS / 12 PROJETS / 15 RÔLES

### 4.1 gfi_v7 — `seeds/seed_all.py`

| Donnée | Attendu | Réel | Vérifié |
|---|---|---|---|
| Associés | 9 | `len(ASSOCIES) = 9` (ligne 55-64) | **OK** |
| Projets | 12 | `len(PROJETS) = 12` (ligne 131-144) | **OK** |
| Rôles RBAC | 15 | `len(ROLES) = 15` (ligne 209-225) | **OK** |
| Entreprises | 7 | `len(ENTREPRISES) = 7` (ligne 87-95) | **OK** |
| Alias associés | 11 | `len(ALIAS_ASSOCIES) = 11` (ligne 67-85) | **OK** |
| Alias projets | 10 | `len(ALIAS_PROJETS) = 10` (ligne 146-157) | **OK** |
| Parts entreprise | 21 | `len(PARTICIPATIONS_ENTREPRISES) = 21` (ligne 100-129) | **OK** |
| Parts projet | 27 | `len(PARTICIPATIONS_PROJETS) = 27` (ligne 160-207) | **OK** |
| UUID fixes | Oui | `ID = {...}` (ligne 20-52) reproductibles | **OK** |

**9 Associés** : Ahmed (A), Mohamed (B), Yazid (C), Yamina (D), Mustapha (E), Brahim (F), Laid (G), Tarek (H), Amine (I)

**12 Projets** : JASMIN, EDEN, OPERA, LYS, T21000, T5000, T2400, IRENE, MAGNOLIA, AUREA, ASTERIA, MOSQUEE

**15 Rôles** : PDG_SUPER_ADMIN, CHARGE_MISSION, DAF, CHARGE_FINANCE, MARKETING, PROJECT_MANAGER, TELECONSEILLERE, RH, ARCHIVISTE, SECURITE, MAGASINIER, ACHATS, OPERATIONS_TECH, ARCHITECTE, CHEF_PROJET_EXT

### 4.2 Existant — `app/services/seed_import.py`

| Donnée | Réel | Conforme ? |
|---|---|---|
| Associés | Extraits dynamiquement de COMPANIES_DATA shareholders — noms longs : "AHMED DENDANI KHADIDJA", "YAMINA AIT BENAMARA", "LYAZID BOUABDELLAH" | **NON** — pas d'UUID fixes, noms différents de v7 |
| Projets | Extraits de COMPANIES_DATA projects — noms différents : "LES JASMINS" (vs JASMIN), "LES JARDIN DE LOPERA" (vs OPERA), "05 HECTARE BOUMERDES" (vs IRENE) | **NON** — noms/codes différents |
| Rôles | `users.role` enum : `admin/accountant/hr_manager/sales/viewer` (5 rôles) | **NON** — 5 au lieu de 15 |
| Entreprises | 7 entreprises (ETS DENDANI KHADIDJA, SARL DENDANI PROMOTION, SARL DBPI IMMOBILIER, SARL OMEGA CONSTRUCTION, SARL AVELIS PROMOTION, + 2 autres) | Compte OK mais noms non normalisés |
| Séparation % entreprise / % projet | **NON** — mélangés dans le même seed | **NON CONFORME** |

---

## 5. SCORE /100 PAR CODEBASE VS BLUEPRINT GFI v7.0

### Grille de notation

| Critère (pondération) | Existant | gfi_v7 | Détail existant | Détail gfi_v7 |
|---|---|---|---|---|
| **CFF Engine** (15 pts) | **0/15** | **15/15** | Aucun modèle, aucun service, aucun endpoint | `CFFEngine`, `calculer()`, `verifier_kt01()`, `verifier_kt02()`, tables, endpoint |
| **RF1-RF4 sur transactions** (15 pts) | **0/15** | **15/15** | Utilise RD/RND/F (3 valeurs incompatibles) | Enum 4 valeurs, colonnes RF sur 8+ tables |
| **Double computation 0.00 DA** (10 pts) | **5/10** | **10/10** | Implémenté mais tolérance=0.01 et % projet | 0.00 DA strict + % entreprise |
| **Seeds conformes** (10 pts) | **3/10** | **10/10** | 7 entreprises OK, mais noms/codes non normalisés, 5 rôles, pas d'UUID fixes | 9/12/15 exacts, UUID fixes, KT vérifiés |
| **RBAC 15 rôles** (5 pts) | **1/5** | **5/5** | 5 rôles génériques | 15 rôles GFI-spécifiques |
| **Clôture 7 étapes** (10 pts) | **7/10** | **8/10** | 7 étapes implémentées avec scheduler, mais % projet | 7 étapes correctes, pas de scheduler |
| **Kill Tests** (5 pts) | **0/5** | **5/5** | Aucun kill test | KT-01 → KT-09, VSR-01, sanity checks |
| **Alias Resolver** (5 pts) | **2/5** | **5/5** | `validate_associate_exact_match()` partiel | `AliasResolver` complet (associés + projets + entreprises) |
| **Pipeline IA/OCR/Agents** (10 pts) | **10/10** | **0/10** | 22 agents, orchestrateur, OCR, extraction | Absent par design |
| **BIM/EDD** (5 pts) | **5/5** | **0/5** | 7 tables, 3 services, pricing | Absent |
| **SPI 360°** (5 pts) | **5/5** | **0/5** | Moteur complet, scheduler, KPIs | Absent |
| **Frontend** (5 pts) | **5/5** | **0/5** | React/Vite/Tailwind | Absent |

### SCORES FINAUX

| Codebase | Score | Profil |
|---|---|---|
| **Existant** | **43/100** | Fort sur pipeline IA/OCR/BIM/SPI. **Zéro** sur CFF, RF1-RF4, kill tests. Clôture buguée. |
| **gfi_v7** | **73/100** | Fort sur règles métier financières. **Zéro** sur pipeline IA, BIM, SPI, frontend. |
| **Fusion cible** | **100/100** | Combinaison des deux |

---

## 6. PLAN DE FUSION ORDONNÉ

### Phase 0 — Pré-requis infra (bloquant)

| # | Action | Fichiers source | Fichiers cible |
|---|---|---|---|
| 0.1 | Migrer DB de SQLite vers PostgreSQL | `gfi_v7/docker-compose.yml`, `gfi_v7/alembic.ini` | `alembic.ini` (nouveau), `app/config.py` → `DATABASE_URL` |
| 0.2 | Ajouter `Dockerfile` + `docker-compose.yml` | `gfi_v7/Dockerfile`, `gfi_v7/docker-compose.yml` | Racine projet |
| 0.3 | Fusionner `requirements.txt` | `gfi_v7/requirements.txt` | `requirements.txt` (racine) — ajouter `asyncpg`, `psycopg2-binary`, `celery`, `redis` |

### Phase 1 — Modèles de base GFI v7.0 (bloquant pour Phase 2-4)

| # | Action | Source gfi_v7 | Cible existant | Détail |
|---|---|---|---|---|
| 1.1 | Ajouter `GFIBase` + mixins | `gfi_v7/app/models/base.py` | `app/models/base_gfi.py` (nouveau) | `TimestampMixin`, `SoftDeleteMixin` |
| 1.2 | Créer enum `RealiteFinanciere(RF1,RF2,RF3,RF4)` | `gfi_v7/app/models/finance.py:12-17` | `app/models/financial.py` — remplacer `StatutFiscal` par mapping RF1=RD, RF2=RND, RF3=FD, RF4=FND |
| 1.3 | Ajouter colonnes `taux_ibs/taux_tap/taux_tva/nif/nis/rc` sur `entreprises` | `gfi_v7/app/models/entreprises.py` | `app/models/financial.py:Entreprise` |
| 1.4 | Ajouter colonnes `est_fondateur/ordre_priorite/nin` sur `associes` | `gfi_v7/app/models/associes.py` | `app/models/financial.py:Associe` |
| 1.5 | Créer table `entreprise_associes` (% entreprise) | `gfi_v7/app/models/entreprises.py:EntrepriseAssocie` | `app/models/financial.py` — nouvelle table |
| 1.6 | Ajouter colonnes `nb_clients_total/est_abandonne/passif_residuel` sur `projets` | `gfi_v7/app/models/projets.py` | `app/models/financial.py:Projet` |
| 1.7 | Migration Alembic `007_gfi_v7_base.py` | — | `alembic/versions/007_gfi_v7_base.py` | Toutes les colonnes/tables Phase 1 |

### Phase 2 — CFF Engine (bloquant pour Phase 3)

| # | Action | Source gfi_v7 | Cible existant |
|---|---|---|---|
| 2.1 | Copier modèle CFF | `gfi_v7/app/models/cff.py` | `app/models/cff.py` (nouveau) — tables `cff_factures`, `cff_imputation_associes` |
| 2.2 | Copier moteur CFF | `gfi_v7/app/services/cff_engine.py` | `app/services/cff_engine.py` (nouveau) — `CFFEngine`, `calculer()`, `verifier_kt01()`, `verifier_kt02()` |
| 2.3 | Créer endpoint CFF | `gfi_v7/app/api/v1/endpoints/cff.py` | `app/api/cff.py` (nouveau) — `POST /cff/calculer`, `GET /cff/verifier-kt01/{code}` |
| 2.4 | Migration `008_cff_tables.py` | — | `alembic/versions/008_cff_tables.py` |

### Phase 3 — RF1-RF4 + Transactions (bloquant pour Phase 4)

| # | Action | Source gfi_v7 | Cible existant |
|---|---|---|---|
| 3.1 | Créer table `transactions` | `gfi_v7/app/models/finance.py:Transaction` | `app/models/financial.py` — avec `realite_financiere` obligatoire |
| 3.2 | Ajouter `realite_financiere` sur `mouvements_comptes_courants` | `gfi_v7/app/models/associes.py` | `app/models/finance_associes.py` |
| 3.3 | Créer tables `flux_inter_projets`, `compensations_st`, `centre_cout_mensuel` | `gfi_v7/app/models/finance.py` | `app/models/financial.py` |
| 3.4 | Ajouter `realite_financiere` sur `employes`, créer `fiches_paie`, `contrats_travail` | `gfi_v7/app/models/rh.py` | `app/models/hr.py` |
| 3.5 | Créer endpoint transactions | `gfi_v7/app/api/v1/endpoints/transactions.py` | `app/api/transactions.py` (nouveau) |
| 3.6 | Migration `009_rf_transactions.py` | — | `alembic/versions/009_rf_transactions.py` |

### Phase 4 — Clôture correctif (CRITIQUE)

| # | Action | Fichier | Modification |
|---|---|---|---|
| 4.1 | Changer tolérance `0.01` → `0.00` | `app/services/cloture_service.py:88` | `abs(TNM - TNM_verif) <= Decimal("0.01")` → `abs(TNM - TNM_verif) <= Decimal("0.00")` |
| 4.2 | Changer source % : `PartProjet` → `EntrepriseAssocie` | `app/services/cloture_service.py:103-106` | Remplacer `select(PartProjet).where(PartProjet.projet_id == projet_id)` par query `EntrepriseAssocie` via `Projet.entreprise_id` |
| 4.3 | Ajouter colonnes `ecart_computation`, `tnm_calcul_1`, `tnm_calcul_2`, `etape_courante` | `app/models/finance_associes.py:ClotureMensuelle` | ALTER TABLE |
| 4.4 | Stocker les 2 computations + écart | `app/services/cloture_service.py` | Avant le hash, écrire `tnm_calcul_1`, `tnm_calcul_2`, `ecart_computation` |
| 4.5 | Migration `010_cloture_fix.py` | — | `alembic/versions/010_cloture_fix.py` |

### Phase 5 — RBAC + Juridique + Véhicules

| # | Action | Source gfi_v7 | Cible existant |
|---|---|---|---|
| 5.1 | Créer modèle RBAC 15 rôles | `gfi_v7/app/models/rbac.py` | `app/models/rbac_gfi.py` (nouveau) — `roles`, `utilisateurs`, `utilisateur_roles`, `audit_log` |
| 5.2 | Créer tables juridique | `gfi_v7/app/models/juridique_mg.py` | `app/models/juridique.py` (nouveau) — `dossiers_juridiques`, `permis_autorisations`, `fournisseurs`, `commandes_achats`, `stock_materiel` |
| 5.3 | Copier alias resolver | `gfi_v7/app/services/alias_resolver.py` | `app/services/alias_resolver.py` (nouveau) |
| 5.4 | Migration `011_rbac_juridique.py` | — | `alembic/versions/011_rbac_juridique.py` |

### Phase 6 — Seeds unification

| # | Action | Détail |
|---|---|---|
| 6.1 | Fusionner seeds dans `seed_import.py` | Intégrer les 9 associés / 12 projets / 15 rôles / UUID fixes de `gfi_v7/seeds/seed_all.py` dans `app/services/seed_import.py` |
| 6.2 | Normaliser noms : "YAMINA AIT BENAMARA" → "Dendani Yamina" | Aligner avec v7 |
| 6.3 | Ajouter seed `entreprise_associes` (% entreprise) | Depuis `PARTICIPATIONS_ENTREPRISES` de `seed_all.py:100-129` |
| 6.4 | Vérifier KT-01 en seed | Yamina absente de DBPI/OC/EP/SEN/BIM dans `entreprise_associes` |

### Phase 7 — Meta-IA (optionnel, basse priorité)

| # | Action | Source gfi_v7 |
|---|---|---|
| 7.1 | Copier modèle meta-IA | `gfi_v7/app/models/meta_ia.py` → `app/models/meta_ia.py` |
| 7.2 | **INVARIANT** : `auto_deploy = FALSE` partout | Jamais de déploiement automatique de code généré |

### Phase 8 — Kill Tests + Validation

| # | Action |
|---|---|
| 8.1 | Implémenter kill tests KT-01 → KT-09 depuis `gfi_v7/tests/test_kill_tests.py` |
| 8.2 | Ajouter sanity checks P1-C1, P1-C2, P1-C4, P1-C5 |
| 8.3 | Ajouter VSR-01 (soldes de référence CCA) |
| 8.4 | Ajouter endpoint `/kt/sanity` + `/kt/kill-tests` + `/kt/vsr` |
| 8.5 | CI : tous les kill tests doivent passer avant merge |

---

**FIN DU RAPPORT**
