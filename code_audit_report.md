# CODE AUDIT REPORT — Solution Existante vs Architecture Cible GFI v7.0

**Date** : 2026-03-13
**Codebase** : `C:\Users\BARACHE\Desktop\avelis-promo`
**Architecture cible** : `gfi_v7/` (Blueprint GFI v7.0 — Groupe Dendani)

---

## 1. PROJECT STRUCTURE COMPARISON

### 1.1 Current Directory Tree

```
avelis-promo/
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_initial.py
│       ├── 002_company_workflow.py
│       ├── 003_blueprint_v6.py
│       ├── 004_gap_remediation.py
│       ├── 005_bim_edd_v2.py
│       ├── 006_user_permissions.py
│       └── 007_gfi_v7_base.py
├── app/
│   ├── __init__.py
│   ├── main.py                          # 239 lines
│   ├── config.py                        # 101 lines
│   ├── database.py                      # 51 lines
│   ├── models/
│   │   ├── __init__.py
│   │   ├── core.py                      # 656 lines — 30 tables
│   │   ├── hr.py                        # 150 lines — 4 tables
│   │   ├── financial.py                 # 740 lines — 18 tables + 2 new (Phase 1)
│   │   ├── finance_associes.py          # 265 lines — 5 tables
│   │   ├── adv.py                       # 111 lines — 4 tables
│   │   ├── spi.py                       # 403 lines — 8 tables
│   │   ├── registry.py                  # 285 lines — 9 tables
│   │   ├── treasury.py                  # 314 lines — 8 tables
│   │   ├── bim_edd.py                   # 302 lines — 7 tables
│   │   ├── legal.py                     # 53 lines — 2 tables
│   │   └── integrations.py             # 34 lines — 1 table
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── api.py
│   │   └── artifacts.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── accounting.py                # 17 endpoints
│   │   ├── admin.py                     # 13 endpoints
│   │   ├── adv.py                       # 9 endpoints
│   │   ├── auth.py                      # 7 endpoints
│   │   ├── bim.py                       # 18 endpoints
│   │   ├── cost_center.py               # 24 endpoints
│   │   ├── documents.py                 # 9 endpoints
│   │   ├── finance_associes.py          # 11 endpoints
│   │   ├── hr.py                        # 16 endpoints
│   │   ├── imports.py                   # 10 endpoints
│   │   ├── legal.py
│   │   ├── mfa.py                       # 2 endpoints
│   │   ├── registry.py
│   │   ├── spi.py
│   │   ├── treasury.py
│   │   └── workflows.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── blocking_rules.py            # 5 functions
│   │   ├── cloture_service.py           # 2 functions
│   │   ├── cost_center_engine.py        # 4 functions
│   │   ├── document_classifier.py
│   │   ├── edd_excel_import.py
│   │   ├── edd_ocr_service.py
│   │   ├── edd_service.py
│   │   ├── employee_import.py           # 9 functions
│   │   ├── google_drive.py
│   │   ├── import_orchestrator.py
│   │   ├── journal_matcher.py
│   │   ├── legal_case_summary.py
│   │   ├── llm_graph.py
│   │   ├── pricing_service.py           # 2 functions
│   │   ├── proof_evaluator.py
│   │   ├── rbac.py
│   │   ├── scheduler.py
│   │   ├── seed_import.py               # 10 seed functions
│   │   ├── spi_engine.py               # 8 functions
│   │   ├── spi_scheduler.py
│   │   └── task_planner.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── adv_agents.py
│   │   ├── anomaly.py
│   │   ├── commit.py
│   │   ├── cost_center.py
│   │   ├── doc_type_router.py
│   │   ├── extraction.py
│   │   ├── hr_agents.py
│   │   ├── ingest.py
│   │   ├── ledger_structuring.py
│   │   ├── matching.py
│   │   ├── module_router.py
│   │   ├── normalization.py
│   │   ├── ocr.py
│   │   ├── ocr_merge.py
│   │   ├── packaging.py
│   │   ├── render.py
│   │   ├── resolution.py
│   │   ├── segment.py
│   │   ├── spi_agents.py
│   │   ├── text_layer.py
│   │   └── verification.py
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   └── graphs.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── dependencies.py
│   │   └── security.py
│   └── storage/
│       ├── __init__.py
│       └── service.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_bim_edd.py
│   ├── test_blocking_rules.py
│   ├── test_cloture_service.py
│   ├── test_employee_import.py
│   ├── test_hr_task_proof.py
│   ├── test_platform.py
│   ├── test_spi_scheduler.py
│   └── test_user_permissions.py
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   └── src/
├── docs/                                # 12 documentation files
├── storage_data/
├── .vscode/tasks.json
└── gfi_v7/                              # Target architecture (separate)
```

### 1.2 Expected Architecture (GFI v7.0)

```
gfi_v7/
├── alembic/
│   ├── env.py
│   └── versions/                        # empty — migrations TBD
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                    # 42 lines
│   │   ├── database.py
│   │   ├── security.py                  # 26 lines
│   │   └── rbac.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                      # GFIBase + TimestampMixin + SoftDeleteMixin
│   │   ├── associes.py                  # 4 tables: associes, associes_alias, comptes_courants_associes, mouvements_comptes_courants
│   │   ├── entreprises.py              # 3 tables: entreprises, entreprise_associes, origine_capital_detail
│   │   ├── projets.py                  # 6 tables: projets, projet_associes, projets_alias, clients, appels_de_fonds, cessions_parts
│   │   ├── cff.py                      # 2 tables: cff_factures, cff_imputation_associes
│   │   ├── finance.py                  # 7 tables: transactions, flux_inter_projets, compensations_st, centre_cout_mensuel, clotures_mensuelles, clotures_mensuelles_repartitions, vehicules_groupe
│   │   ├── rbac.py                     # 4 tables: roles, utilisateurs, utilisateur_roles, audit_log
│   │   ├── rh.py                       # 3 tables: employes, contrats_travail, fiches_paie
│   │   ├── juridique_mg.py            # 5 tables: dossiers_juridiques, permis_autorisations, fournisseurs, commandes_achats, stock_materiel
│   │   └── meta_ia.py                 # 6 tables: meta_objets_metier_detectes → meta_feedback_apprentissage
│   ├── services/
│   │   ├── __init__.py
│   │   ├── cff_engine.py              # CFFEngine class — 153 lines
│   │   ├── cloture_engine.py          # ClotureMensuelleEngine — 153 lines
│   │   └── alias_resolver.py          # AliasResolver class
│   └── api/
│       ├── __init__.py
│       └── v1/
│           ├── __init__.py
│           ├── router.py               # 9 router includes
│           └── endpoints/
│               ├── __init__.py
│               ├── auth.py
│               ├── associes.py
│               ├── entreprises.py
│               ├── projets.py
│               ├── transactions.py
│               ├── cff.py
│               ├── cloture.py
│               ├── rbac.py
│               └── health_check.py     # /kt/sanity, /kt/kill-tests, /kt/vsr
├── seeds/
│   ├── __init__.py
│   └── seed_all.py                     # 251 lines — master seed
├── tests/
│   └── test_kill_tests.py              # 240 lines — KT-01→KT-09, sanity, CFF, clôture
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

### 1.3 Missing Folders and Modules

| Missing in Current | Source in gfi_v7 | Purpose |
|---|---|---|
| `app/core/` | `gfi_v7/app/core/` | Centralized config, database, security, RBAC |
| `app/models/cff.py` | `gfi_v7/app/models/cff.py` | CFF tables (cff_factures, cff_imputation_associes) |
| `app/models/base.py` | `gfi_v7/app/models/base.py` | GFIBase with TimestampMixin, SoftDeleteMixin |
| `app/models/meta_ia.py` | `gfi_v7/app/models/meta_ia.py` | 6 meta-IA tables |
| `app/services/cff_engine.py` | `gfi_v7/app/services/cff_engine.py` | CFF calculation engine |
| `app/services/alias_resolver.py` | `gfi_v7/app/services/alias_resolver.py` | Entity alias resolution |
| `app/api/v1/` | `gfi_v7/app/api/v1/` | Versioned API structure |
| `app/api/v1/endpoints/transactions.py` | `gfi_v7/app/api/v1/endpoints/transactions.py` | Transaction CRUD with RF1-RF4 |
| `app/api/v1/endpoints/cff.py` | `gfi_v7/app/api/v1/endpoints/cff.py` | CFF calculation endpoints |
| `app/api/v1/endpoints/health_check.py` | `gfi_v7/app/api/v1/endpoints/health_check.py` | Kill tests + sanity checks |
| `seeds/` | `gfi_v7/seeds/` | Master seed with fixed UUIDs |
| `Dockerfile` | `gfi_v7/Dockerfile` | Container definition |
| `docker-compose.yml` | `gfi_v7/docker-compose.yml` | PostgreSQL + Redis + API |
| `requirements.txt` | `gfi_v7/requirements.txt` | Pinned Python dependencies |

| Present in Current but ABSENT in gfi_v7 | Purpose | Decision |
|---|---|---|
| `app/agents/` (22 files) | LLM/AI pipeline agents | KEEP — absent from v7 by design |
| `app/orchestrator/` | Workflow orchestration engine | KEEP |
| `app/storage/` | S3/MinIO storage service | KEEP |
| `app/models/bim_edd.py` | BIM/EDD real estate tables | KEEP |
| `app/models/spi.py` | SPI 360 scoring system | KEEP |
| `app/models/treasury.py` | Treasury management | KEEP |
| `app/services/spi_engine.py` | SPI computation engine | KEEP |
| `app/services/pricing_service.py` | BIM unit pricing | KEEP |
| `app/services/edd_*.py` (3 files) | EDD import/OCR/service | KEEP |
| `app/api/bim.py` (18 endpoints) | BIM/EDD REST API | KEEP |
| `app/api/spi.py` | SPI scoring REST API | KEEP |
| `frontend/` | React/Vite/Tailwind frontend | KEEP |

---

## 2. FILE COMPARISON

### 2.1 Existing Files — Complete Inventory

**Models** (13 files):

| File | Lines | Tables | Status |
|---|---|---|---|
| `app/models/__init__.py` | 16 | — | Updated Phase 1 |
| `app/models/core.py` | 656 | 30 | Complete |
| `app/models/hr.py` | 150 | 4 | Missing RF fields |
| `app/models/financial.py` | 740 | 20 | Updated Phase 1 — added RealiteFinanciere, EntrepriseAssocie, OrigineCapitalDetail |
| `app/models/finance_associes.py` | 265 | 5 | Updated Phase 1 — added etape_courante, tnm_calcul_1/2, ecart_computation |
| `app/models/adv.py` | 111 | 4 | Complete |
| `app/models/spi.py` | 403 | 8 | Complete |
| `app/models/registry.py` | 285 | 9 | Complete |
| `app/models/treasury.py` | 314 | 8 | Complete |
| `app/models/bim_edd.py` | 302 | 7 | Complete |
| `app/models/legal.py` | 53 | 2 | Partial — missing fields from gfi_v7 juridique_mg |
| `app/models/integrations.py` | 34 | 1 | Complete |

**API Routes** (16 files):

| File | Endpoints | Status |
|---|---|---|
| `app/api/accounting.py` | 17 | Complete |
| `app/api/admin.py` | 13 | Complete |
| `app/api/adv.py` | 9 | Complete |
| `app/api/auth.py` | 7 | Complete |
| `app/api/bim.py` | 18 | Complete |
| `app/api/cost_center.py` | 24 | Complete |
| `app/api/documents.py` | 9 | Complete |
| `app/api/finance_associes.py` | 11 | Complete |
| `app/api/hr.py` | 16 | Complete |
| `app/api/imports.py` | 10 | Complete |
| `app/api/legal.py` | partial | Incomplete |
| `app/api/mfa.py` | 2 | Complete |
| `app/api/registry.py` | partial | Incomplete |
| `app/api/spi.py` | partial | Incomplete |
| `app/api/treasury.py` | partial | Incomplete |
| `app/api/workflows.py` | partial | Incomplete |

**Services** (21 files):

| File | Functions | Status |
|---|---|---|
| `app/services/blocking_rules.py` | 5 | Complete — BlockingError, validate_retrait_associe, validate_project_shares_sum, validate_associate_exact_match, validate_share_transfer_integrity |
| `app/services/cloture_service.py` | 2 | Updated Phase 1 — executer_cloture_mensuelle, run_monthly_clotures_all |
| `app/services/cost_center_engine.py` | 4 | Complete |
| `app/services/seed_import.py` | 10 | Needs v7 alignment |
| `app/services/spi_engine.py` | 8 | Complete |
| `app/services/pricing_service.py` | 2 | Complete |
| `app/services/employee_import.py` | 9 | Complete |
| All other services | — | Complete |

**Agents** (22 files), **Orchestrator** (2 files), **Auth** (2 files), **Storage** (1 file) — all complete.

**Tests** (9 files):

| File | Status |
|---|---|
| `tests/test_bim_edd.py` | Complete |
| `tests/test_blocking_rules.py` | Complete |
| `tests/test_cloture_service.py` | Complete |
| `tests/test_employee_import.py` | Complete |
| `tests/test_hr_task_proof.py` | Complete |
| `tests/test_platform.py` | Complete |
| `tests/test_spi_scheduler.py` | Complete |
| `tests/test_user_permissions.py` | Complete |

**Migrations** (7 files): `001_initial.py` → `007_gfi_v7_base.py`

### 2.2 Missing Files

| Missing File | Source | Priority |
|---|---|---|
| `app/models/cff.py` | `gfi_v7/app/models/cff.py` | **P0 — CRITICAL** |
| `app/models/base_gfi.py` | `gfi_v7/app/models/base.py` | P1 |
| `app/models/meta_ia.py` | `gfi_v7/app/models/meta_ia.py` | P3 |
| `app/services/cff_engine.py` | `gfi_v7/app/services/cff_engine.py` | **P0 — CRITICAL** |
| `app/services/alias_resolver.py` | `gfi_v7/app/services/alias_resolver.py` | P1 |
| `app/api/cff.py` | `gfi_v7/app/api/v1/endpoints/cff.py` | **P0 — CRITICAL** |
| `app/api/transactions.py` | `gfi_v7/app/api/v1/endpoints/transactions.py` | **P0 — CRITICAL** |
| `app/api/health_check.py` | `gfi_v7/app/api/v1/endpoints/health_check.py` | P1 |
| `tests/test_kill_tests.py` | `gfi_v7/tests/test_kill_tests.py` | P1 |
| `seeds/seed_all.py` | `gfi_v7/seeds/seed_all.py` | P1 |
| `Dockerfile` | `gfi_v7/Dockerfile` | P2 |
| `docker-compose.yml` | `gfi_v7/docker-compose.yml` | P2 |
| `requirements.txt` | `gfi_v7/requirements.txt` | P2 |
| `alembic.ini` | `gfi_v7/alembic.ini` | P2 |

### 2.3 Duplicated or Unused Files

| File | Issue |
|---|---|
| `app/models/legal.py` | Duplicates partial functionality of `gfi_v7/app/models/juridique_mg.py` — merge needed |
| `app/models/integrations.py` | Only 1 table (user_integrations) — low usage, consider merging into core |
| `docs/RAPPORT_AUDIT_BLUEPRINT.md` | Superseded by this report |
| `docs/RAPPORT_TEST_BLUEPRINT.md` | Superseded — tests now in `tests/` |
| `docs/check.md` | Unclear purpose — verify if still relevant |

---

## 3. MODULE AND FUNCTION COMPARISON

### 3.1 Detected Modules (Current)

| Module | Files | Purpose |
|---|---|---|
| `app.models` | 13 | ORM models — 96 tables across SQLite |
| `app.api` | 16 | REST endpoints — 136+ routes |
| `app.services` | 21 | Business logic |
| `app.agents` | 22 | LLM/AI pipeline agents |
| `app.orchestrator` | 2 | Workflow graph engine |
| `app.auth` | 2 | Authentication |
| `app.schemas` | 2 | Pydantic request/response |
| `app.storage` | 1 | S3/MinIO file storage |

### 3.2 Expected Modules (gfi_v7)

| Module | Files | Purpose |
|---|---|---|
| `app.models` | 10 | ORM models — 40 tables across PostgreSQL |
| `app.api.v1.endpoints` | 9 | Versioned REST endpoints |
| `app.services` | 3 | CFF engine, clôture engine, alias resolver |
| `app.core` | 4 | Config, database, security, RBAC |
| `seeds` | 1 | Master seed data |
| `tests` | 1 | Kill tests |

### 3.3 Missing Modules

| Module | Functions Required | Status |
|---|---|---|
| **CFF Engine** | `CFFEngine.__init__()`, `calculer()`, `verifier_kt01()`, `verifier_kt02()` | **MISSING** — 0% implemented |
| **Alias Resolver** | `AliasResolver.__init__()`, `resoudre_associe()`, `resoudre_projet()`, `resoudre_entite()`, `verifier_unicite_projet()` | **MISSING** — partial in `blocking_rules.py:80-143` |
| **Transaction Management** | CRUD with mandatory RF1-RF4 | **MISSING** — no transactions table or endpoint |
| **Meta-IA** | 6 tables, auto_deploy=FALSE invariant | **MISSING** |
| **Kill Tests** | KT-01 through KT-09, VSR-01, P1-C1/C2/C4/C5 | **MISSING** |
| **Docker Infrastructure** | Dockerfile, docker-compose (PostgreSQL, Redis) | **MISSING** |

### 3.4 Missing Functions — Detail

**`gfi_v7/app/services/cff_engine.py`** — entirely absent:

| Function | Line | Signature | Purpose |
|---|---|---|---|
| `CFFEngine.__init__` | 50-64 | `(taux_tva=0.19, taux_ibs=0.19, taux_tap=0.02, taux_cnas_patronal=0.26, appliquer_cnas=False, appliquer_timbre=True)` | Initialize fiscal rates |
| `CFFEngine.calculer` | 66-118 | `(montant_ht: Decimal, participations_entreprise: List[Dict], entreprise_code: str) -> CFFCalculResult` | Calculate CFF and distribute to associates by **enterprise %** |
| `CFFEngine.verifier_kt01` | 120-133 | `(imputations, associe_yamina_id, entreprise_code) -> bool` | Yamina in DBPI/OC/EP/SEN/BIM → 0 DA |
| `CFFEngine.verifier_kt02` | 135-148 | `(imputations, associe_ahmed_id, entreprise_code, pourcentage_attendu) -> bool` | Ahmed SARL-DP = 25% enterprise, not 60% project |

**`gfi_v7/app/services/cloture_engine.py`** — partially covered by `cloture_service.py`:

| Function | Line | Status in Current |
|---|---|---|
| `ClotureMensuelleEngine.executer` | 22-111 | Implemented as `executer_cloture_mensuelle()` in `cloture_service.py:40` — **2 bugs fixed in Phase 1** |
| `ClotureMensuelleEngine._etape1_extraction_tnm` | 113-119 | Implemented inline at `cloture_service.py:52-66` |
| `ClotureMensuelleEngine._computations` | 121-124 | Implemented inline at `cloture_service.py:82-95` |
| `ClotureMensuelleEngine._repartir` | 126-137 | Implemented inline at `cloture_service.py:105-155` |
| `ClotureMensuelleEngine.verifier_kt08` | 139-150 | Implemented as `validate_retrait_associe()` in `blocking_rules.py:22-47` |

**`gfi_v7/app/services/alias_resolver.py`** — partially covered:

| Function | Status in Current |
|---|---|
| `AliasResolver.resoudre_associe()` | Partial — `blocking_rules.py:80-143` does exact match + fuzzy |
| `AliasResolver.resoudre_projet()` | **MISSING** |
| `AliasResolver.resoudre_entite()` | **MISSING** |
| `AliasResolver.verifier_unicite_projet()` | **MISSING** |

**`gfi_v7/app/api/v1/endpoints/`** — missing endpoints:

| Endpoint File | gfi_v7 Routes | Current Equivalent |
|---|---|---|
| `transactions.py` | `POST /transactions`, `GET /transactions` | **MISSING** |
| `cff.py` | `POST /cff/calculer`, `GET /cff/verifier-kt01/{code}` | **MISSING** |
| `cloture.py` | `POST /cloture/executer` | `finance_associes.py:334` — `POST /clotures/trigger` |
| `associes.py` | `GET /associes`, `GET /associes/{id}/alias`, `GET /associes/resoudre/{alias}` | **MISSING** (dedicated endpoints) |
| `entreprises.py` | `GET /entreprises`, `GET /entreprises/{code}/associes` | `accounting.py:34` — `GET /entreprises` (partial) |
| `projets.py` | `GET /projets`, `GET /projets/{code}/associes` | `accounting.py:61` — `GET /projets` (partial) |
| `health_check.py` | `GET /kt/sanity`, `GET /kt/kill-tests`, `GET /kt/vsr` | **MISSING** |

---

## 4. DATABASE LAYER

### 4.1 Existing Tables (Current — 96 tables)

**core.py** (30 tables):
`tenants`, `users`, `documents`, `artifacts`, `workflows`, `chart_of_accounts`, `accounting_periods`, `journal_entries`, `journal_lines`, `evidence_anchors`, `anomaly_records`, `audit_log`, `cost_centers`, `cost_center_allocations`, `import_sessions`, `versions_documents`, `archivage_physique`, `document_segments`, `ia_extraction_log`, `verifications_hash`, `user_permissions`, `workflow_dossiers`, `workflow_phases_log`, `demandes_completion`

**financial.py** (20 tables):
`entreprises`, `exercices`, `projets`, `lots`, `clients_cc`, `fournisseurs`, `encaissements`, `decaissements`, `parametres`, `ratio_charges_communes`, `centre_cout_mensuel`, `imputation_paie_projets`, `mouvements_caisse`, `comptes_transitoires_notaires`, `articles_stock`, `mouvements_stock`, `bulletin_paie_complements`, `associes`, **`entreprise_associes`** (Phase 1), **`origine_capital_detail`** (Phase 1)

**finance_associes.py** (5 tables):
`comptes_courants_associes`, `mouvements_comptes_courants`, `clotures_mensuelles`, `appels_de_fonds`, `cessions_parts`, `associate_aliases`

**hr.py** (4 tables):
`employees`, `payroll_proposals`, `hr_tasks`, `task_notifications`

**adv.py** (4 tables):
`clients`, `contracts`, `receivables`, `payments`

**spi.py** (8 tables):
`departments`, `hierarchy_relations`, `spi_rules`, `spi_kpis`, `spi_scores`, `spi_bonus_malus_rules`, `ownership_relations`, `remuneration_baremes`

**registry.py** (9 tables):
`notaires`, `banques_partenaires`, `projet_notaires`, `projet_banques`, `parts_projets`, `mutations_foncieres`, `lots_immobiliers`, `projet_entreprise_historique`, `dossiers_fictifs_reference`

**treasury.py** (8 tables):
`journaux`, `comptes_bancaires`, `bulletins_paie`, `declarations_fiscales`, `echeancier_clients`, `capital_associes`, `retraits_associes`, `consolidation_associes`, `consolidation_entreprises`

**bim_edd.py** (7 tables):
`re_projects`, `re_blocks`, `re_levels`, `re_units`, `re_unit_annexes`, `re_pricing_rules`, `re_validations`, `re_edd_documents`

**legal.py** (2 tables):
`legal_cases`, `legal_case_folders`

**integrations.py** (1 table):
`user_integrations`

### 4.2 Expected Tables (gfi_v7 — 40 tables)

**associes.py** (4): `associes`, `associes_alias`, `comptes_courants_associes`, `mouvements_comptes_courants`
**entreprises.py** (3): `entreprises`, `entreprise_associes`, `origine_capital_detail`
**projets.py** (6): `projets`, `projet_associes`, `projets_alias`, `clients`, `appels_de_fonds`, `cessions_parts`
**cff.py** (2): `cff_factures`, `cff_imputation_associes`
**finance.py** (7): `transactions`, `flux_inter_projets`, `compensations_st`, `centre_cout_mensuel`, `clotures_mensuelles`, `clotures_mensuelles_repartitions`, `vehicules_groupe`
**rbac.py** (4): `roles`, `utilisateurs`, `utilisateur_roles`, `audit_log`
**rh.py** (3): `employes`, `contrats_travail`, `fiches_paie`
**juridique_mg.py** (5): `dossiers_juridiques`, `permis_autorisations`, `fournisseurs`, `commandes_achats`, `stock_materiel`
**meta_ia.py** (6): `meta_objets_metier_detectes`, `meta_rapports_lacunes`, `meta_specifications_generees`, `meta_code_genere`, `meta_resultats_tests`, `meta_feedback_apprentissage`

### 4.3 Missing Tables

| Table | Model File in gfi_v7 | Key Columns | Priority |
|---|---|---|---|
| `cff_factures` | `models/cff.py:9` | `entreprise_id`, `montant_ht`, `cff_tva`, `cff_ibs`, `cff_tap`, `cff_cnas`, `cff_timbre`, `cff_total` | **P0** |
| `cff_imputation_associes` | `models/cff.py:33` | `facture_id`, `associe_id`, `pourcentage_entreprise`, `montant_impute` | **P0** |
| `transactions` | `models/finance.py:28` | `realite_financiere` (RF1-RF4 **MANDATORY**), `type_transaction`, `hash_sha256` | **P0** |
| `flux_inter_projets` | `models/finance.py:50` | `realite_financiere`, `nature`, `source_externe`, `solde_restant` | P1 |
| `compensations_st` | `models/finance.py:70` | `sortie_cash_512` (KT-05), `compte_debit`, `compte_credit` | P1 |
| `clotures_mensuelles_repartitions` | `models/finance.py:139` | `cloture_id`, `associe_id`, `pourcentage`, `montant` | P1 |
| `vehicules_groupe` | `models/finance.py:151` | Full lifecycle: `cede_a_st_id`, `montant_deduit`, `prix_revente` | P2 |
| `projet_associes` | `models/projets.py:57` | `pourcentage` (% projet — distinct from % entreprise) | P1 |
| `projets_alias` | `models/projets.py:73` | `projet_id`, `alias` | P1 |
| `roles` | `models/rbac.py` | 15 GFI-specific roles + `permissions` JSON | P1 |
| `utilisateurs` | `models/rbac.py` | `associe_id`, `company_id` (Row Level Security) | P1 |
| `utilisateur_roles` | `models/rbac.py` | M:N user↔role per entreprise | P1 |
| `contrats_travail` | `models/rh.py` | `type_contrat` (CDI/CDD/ANEM/STAGE/JOURNALIER) | P2 |
| `fiches_paie` | `models/rh.py` | `realite_financiere` RF1/RF2, `cnas_salarial/patronal` | P2 |
| `dossiers_juridiques` | `models/juridique_mg.py` | `est_succession` (FC-002), `montant_litige` | P2 |
| `permis_autorisations` | `models/juridique_mg.py` | `type_permis`, `date_expiration` | P2 |
| `commandes_achats` | `models/juridique_mg.py` | `realite_financiere`, `est_avance_materiel` (KT-05) | P2 |
| `stock_materiel` | `models/juridique_mg.py` | `code_article`, `quantite`, `valeur_unitaire` | P2 |
| 6 meta_ia tables | `models/meta_ia.py` | `auto_deploy = FALSE` invariant | P3 |

### 4.4 Missing Columns on Existing Tables

| Table | Column | Type | gfi_v7 Source | Priority |
|---|---|---|---|---|
| `mouvements_comptes_courants` | `realite_financiere` | `String(4)` RF1-RF4 | `models/associes.py:79` | **P0** |
| `employees` | `realite_financiere` | `String(4)` default RF1 | `models/rh.py` | P1 |
| `employees` | `nin` | `String(20) unique` | `models/rh.py` | P1 |
| `employees` | `est_declare_cnas` | `Boolean default TRUE` | `models/rh.py` | P1 |

### 4.5 Migration Status

| Migration | Rev | Tables Created/Altered |
|---|---|---|
| `001_initial.py` | 001 | tenants, users, documents, workflows, artifacts, journal_entries, journal_lines, chart_of_accounts, cost_centers, cost_center_allocations, employees, payroll_proposals, hr_tasks, clients, contracts, receivables, payments |
| `002_company_workflow.py` | 002 | Extended: tenants, users, employees, hr_tasks. New: task_notifications |
| `003_blueprint_v6.py` | 003 | 27 new tables (treasury, registry, core/document/workflow) |
| `004_gap_remediation.py` | 004 | Extended: users (MFA). New: comptes_courants_associes, mouvements_comptes_courants, clotures_mensuelles, appels_de_fonds, cessions_parts, associate_aliases. BIM tables. |
| `005_bim_edd_v2.py` | 005 | re_edd_documents, re_unit_annexes, re_pricing_rules, re_validations |
| `006_user_permissions.py` | 006 | user_permissions |
| **`007_gfi_v7_base.py`** | **007** | **New: entreprise_associes, origine_capital_detail. Extended: entreprises (+9 cols), projets (+11 cols), associes (+8 cols), clotures_mensuelles (+4 cols)** |
| `008_cff_tables.py` | — | **PENDING** — cff_factures, cff_imputation_associes |
| `009_rf_transactions.py` | — | **PENDING** — transactions, flux_inter_projets, compensations_st, centre_cout_mensuel v7 |
| `010_rbac_juridique.py` | — | **PENDING** — roles, utilisateurs, utilisateur_roles, audit_log v7, juridique tables |

---

## 5. BUSINESS LOGIC

### 5.1 Implemented Features

| Feature | File | Key Functions | Lines |
|---|---|---|---|
| Monthly closing (7-step) | `services/cloture_service.py` | `executer_cloture_mensuelle()` | 40-272 |
| Blocking rules | `services/blocking_rules.py` | `validate_retrait_associe()`, `validate_project_shares_sum()`, `validate_associate_exact_match()`, `validate_share_transfer_integrity()` | 22-171 |
| Cost center calculation | `services/cost_center_engine.py` | `calculer_ratio_charges_communes()`, `calculer_irg()` | 47-87 |
| SPI 360 scoring | `services/spi_engine.py` | `compute_spi_for_employee()`, `compute_spi_batch()`, `compute_payroll_with_spi()` | 92-150+ |
| BIM/EDD management | `services/edd_service.py` | EDD generation, validation, freeze | — |
| BIM pricing | `services/pricing_service.py` | `compute_unit_price()` | 35 |
| Employee import | `services/employee_import.py` | `parse_tabular_employee_file()`, `split_employee_name()` | 93-126 |
| Document classification | `services/document_classifier.py` | AI-powered document routing | — |
| OCR pipeline | `agents/ocr.py`, `agents/text_layer.py`, `agents/segment.py` | Multi-agent extraction pipeline | — |
| Journal matching | `services/journal_matcher.py` | Auto-matching journal entries | — |
| Google Drive import | `services/google_drive.py` | OAuth2 drive import | — |
| MFA TOTP | `api/mfa.py` | `mfa_setup()`, `mfa_verify()` | 34-57 |
| Associate current accounts | `api/finance_associes.py` | CRUD + gel/dégel | 81-365 |
| Multi-tenant auth | `auth/security.py`, `auth/dependencies.py` | JWT + tenant isolation | — |
| Seed import | `services/seed_import.py` | 10 seed functions from doc files | 43-58 |

### 5.2 Partially Implemented Features

| Feature | Current State | Missing Part | gfi_v7 Reference |
|---|---|---|---|
| **Monthly closing — distribution** | Uses `PartProjet.pourcentage` (% **project**) with fallback to `EntrepriseAssocie` | Should **always** use `EntrepriseAssocie.pourcentage` (% enterprise) | `cloture_engine.py:27` — `participations[].pourcentage_entreprise` |
| **Monthly closing — tolerance** | Changed to 0.00 DA (Phase 1, `cloture_service.py:90`) | OK after Phase 1 fix | `cloture_engine.py:16` — `ECART_MAX = Decimal("0.00")` |
| **Double computation tracking** | `tnm_calcul_1/2` + `ecart_computation` added (Phase 1) | Need to populate from both independent computations | `cloture_engine.py:60-64` |
| **Alias resolution** | `blocking_rules.py:80-143` — exact match + fuzzy for associates only | Missing: project alias resolution, entity resolution, uniqueness verification | `alias_resolver.py` — full implementation |
| **RBAC** | `users.role` enum: 5 generic roles (admin/accountant/hr_manager/sales/viewer) | Need 15 GFI-specific roles with permissions JSON | `models/rbac.py` — 15 roles, `seed_all.py:209-225` |
| **Fiscal reality enum** | `StatutFiscal` has 5 values (RD/RND/F/FD/FND) — `RealiteFinanciere` added Phase 1 | Existing tables still use `StatutFiscal` — need to add `realite_financiere` RF1-RF4 columns | `models/finance.py:12-17` |
| **Seeds** | Dynamic extraction from markdown docs — names differ from v7 | Need fixed UUIDs, normalized names, 9/12/15 counts | `seeds/seed_all.py` |

### 5.3 Missing Features

| Feature | gfi_v7 File | Functions/Classes | Priority |
|---|---|---|---|
| **CFF Engine** | `services/cff_engine.py` | `CFFEngine.calculer()` line 66, `verifier_kt01()` line 120, `verifier_kt02()` line 135 | **P0** |
| **CFF Tables** | `models/cff.py` | `CFFFacture`, `CFFImputationAssocie` | **P0** |
| **CFF Endpoints** | `api/v1/endpoints/cff.py` | `POST /cff/calculer`, `GET /cff/verifier-kt01/{code}` | **P0** |
| **Transaction CRUD** | `api/v1/endpoints/transactions.py` | `POST /transactions`, `GET /transactions` with RF1-RF4 | **P0** |
| **RF1-RF4 on transactions** | `models/finance.py:34` | `realite_financiere = Column(SAEnum(RealiteFinanciere), nullable=False)` | **P0** |
| **RF3 → auto CFF trigger** | `models/finance.py:16` | RF3 = Fictif Déclaré → generates CFF automatically | **P0** |
| **Kill tests** | `tests/test_kill_tests.py` | KT-01→KT-09, VSR-01, P1-C1/C2/C4/C5, CFF tests, clôture tests | P1 |
| **Health/KT endpoints** | `api/v1/endpoints/health_check.py` | `GET /kt/sanity`, `GET /kt/kill-tests`, `GET /kt/vsr` | P1 |
| **Inter-project flows** | `models/finance.py:50` | `FluxInterProjet` with RF, nature, source_externe | P1 |
| **Sub-contractor compensation** | `models/finance.py:70` | `CompensationST` — KT-05: no cash 512 for material advances | P1 |
| **Vehicle lifecycle** | `models/finance.py:151` | `VehiculeGroupe` — buy→register→cede→deduct→resell | P2 |
| **Employment contracts** | `models/rh.py` | `ContratTravail` (CDI/CDD/ANEM/STAGE/JOURNALIER) | P2 |
| **Payroll sheets** | `models/rh.py` | `FichePaie` with `realite_financiere` RF1/RF2 | P2 |
| **Legal dossiers v7** | `models/juridique_mg.py` | `DossierJuridique` (est_succession FC-002), `PermisAutorisation` | P2 |
| **Purchase orders** | `models/juridique_mg.py` | `CommandeAchat` with RF and `est_avance_materiel` (KT-05) | P2 |
| **Meta-IA pipeline** | `models/meta_ia.py` | 6 tables, `auto_deploy = FALSE` invariant | P3 |
| **Docker deployment** | `Dockerfile`, `docker-compose.yml` | PostgreSQL + Redis + API container | P2 |

---

## 6. CONFIGURATION

### 6.1 Current Config Parameters (`app/config.py`)

| Parameter | Default | Line |
|---|---|---|
| `APP_NAME` | `"GFI Agentic AI Platform"` | 10 |
| `APP_VERSION` | `"3.0.0"` | 11 |
| `DEBUG` | `False` | 12 |
| `SECRET_KEY` | `"CHANGE-ME-in-production..."` | 13 |
| `ALGORITHM` | `"HS256"` | 14 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | 15 |
| `ENVIRONMENT` | `"development"` | 16 |
| `DATABASE_URL` | `"sqlite+aiosqlite:///./gfi_dev.db"` | 19 |
| `DATABASE_URL_SYNC` | `"sqlite:///./gfi_dev.db"` | 20 |
| `DB_POOL_SIZE` | `20` | 21 |
| `DB_MAX_OVERFLOW` | `10` | 22 |
| `MFA_ISSUER` | `"GFI Platform"` | 25 |
| `MFA_ENFORCE` | `False` | 26 |
| `S3_ENDPOINT` | `"http://localhost:9000"` | 41 |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | `"minioadmin"` | 42-43 |
| `S3_BUCKET_DOCUMENTS/RENDERS/ARTIFACTS` | `"gfi-*"` | 44-46 |
| `OCR_ENGINE` | `"paddleocr"` | 51 |
| `OCR_DPI` | `300` | 53 |
| `LLM_PROVIDER` | `"openai"` | 57 |
| `LLM_MODEL` | `"openai/gpt-5.4"` | 58 |
| `LLM_API_BASE` | `"https://openrouter.ai/api/v1"` | 60 |
| `REDIS_URL` | `"redis://localhost:6379/0"` | 69 |
| `MAX_UPLOAD_SIZE_MB` | `100` | 83 |
| **`TVA_TAUX`** | `0.19` | 87 (Phase 1) |
| **`IBS_TAUX_DEFAULT`** | `0.19` | 88 (Phase 1) |
| **`TAP_TAUX_DEFAULT`** | `0.02` | 89 (Phase 1) |
| **`CNAS_PATRONAL`** | `0.26` | 90 (Phase 1) |
| **`CNAS_SALARIAL`** | `0.09` | 91 (Phase 1) |
| **`LIBERATION_RATIO`** | `0.50` | 92 (Phase 1) |
| **`CLOTURE_HEURE`** | `2` | 93 (Phase 1) |
| **`META_AUTO_DEPLOY`** | `False` | 94 (Phase 1) |

### 6.2 Missing Configuration Variables

| Variable | gfi_v7 Default | Source Line | Purpose |
|---|---|---|---|
| `CASNOS_TAUX` | `0.12` | `gfi_v7/app/core/config.py:28` | CASNOS contribution rate |
| `META_SCORE_CONFIANCE_MIN` | `80` | `gfi_v7/app/core/config.py:36` | Minimum AI confidence to process |
| `DATABASE_URL` (PostgreSQL) | `postgresql+asyncpg://...` | `gfi_v7/app/core/config.py:11` | Production DB — SQLite still default |

---

## 7. SECURITY AND VALIDATION

### 7.1 Missing Validations

| Validation | gfi_v7 Location | Current Status |
|---|---|---|
| **RF1-RF4 mandatory on every transaction** | `models/finance.py:34` — `nullable=False` | **MISSING** — no `transactions` table exists |
| **RF3 → auto-trigger CFF** | `models/finance.py:16` — comment | **MISSING** — no CFF engine |
| **KT-01: Yamina CFF = 0 DA in DBPI/OC/EP/SEN/BIM** | `services/cff_engine.py:120-133` | **MISSING** — no CFF engine |
| **KT-02: CFF uses enterprise %, never project %** | `services/cff_engine.py:135-148` | **MISSING** — no CFF engine |
| **KT-05: No cash 512 outflow for material advances** | `models/finance.py:87` — `sortie_cash_512` CheckConstraint | **MISSING** — no `compensations_st` table |
| **KT-08: Block withdrawal > available balance** | `services/cloture_engine.py:139-150` | Implemented in `blocking_rules.py:22-47` |
| **KT-09: Share cession sum = 100% exactly** | `models/projets.py:131` — `somme_parts_post` | Partially — `blocking_rules.py:50-77` checks but no `somme_parts_post` column |
| **Double computation ecart = 0.00 DA** | `services/cloture_engine.py:67` | **FIXED Phase 1** — was 0.01, now 0.00 |
| **META_AUTO_DEPLOY = FALSE invariant** | `models/meta_ia.py` — `auto_deploy = Column(Boolean, default=FALSE)` | **MISSING** — no meta-IA tables |
| **Audit log with RF tag** | `models/rbac.py` — `realite_financiere = Column(String(4))` | **MISSING** — current audit_log has no RF column |
| **Hash SHA-256 on transactions** | `models/finance.py:43` — `hash_sha256 = Column(String(64))` | **MISSING** — no transactions table |

### 7.2 Potential Security Risks

| Risk | Location | Severity | Mitigation |
|---|---|---|---|
| **SQLite in development** | `config.py:19` — default DB URL | Medium | Validator blocks SQLite in prod/staging (`config.py:28-38`) but dev has no integrity checks |
| **Hardcoded secrets** | `config.py:13` — `SECRET_KEY = "CHANGE-ME-..."` | High | Must use `.env` in production |
| **S3 default credentials** | `config.py:42-43` — `minioadmin/minioadmin` | High | Must override in production |
| **No Row Level Security** | Current `users` table has no `company_id` | Medium | gfi_v7 has `utilisateurs.company_id` for RLS |
| **5 generic roles vs 15 GFI roles** | `core.py` — User.role enum | Medium | Insufficient granularity for financial operations |
| **No transaction hash verification** | No `hash_sha256` on financial mutations | Medium | gfi_v7 hashes every transaction |
| **MFA optional** | `config.py:26` — `MFA_ENFORCE = False` | Low | Toggle to True for production |

---

## 8. PERFORMANCE

### 8.1 Inefficient Code Areas

| File | Line | Issue | Impact |
|---|---|---|---|
| `cloture_service.py:156-164` | N+1 query in CCA balance recalculation | For each associate in distribution, queries `CompteCourantAssocie` then sums all movements | Medium — O(n*m) where n=associates, m=movements |
| `cloture_service.py:204-219` | `sa_func.sum()` per associate inside loop | Should batch-query all CCA balances in one query | Medium |
| `cost_center_engine.py:87` | `calculer_ratio_charges_communes()` executes multiple sequential queries | Could be parallelized or joined | Low |
| `blocking_rules.py:104-135` | `select(Associe).where(is_active == True)` loads all associates for fuzzy match | Should use indexed lookup first | Low |
| `seed_import.py` | Entire file parses markdown docs at runtime | Should use structured seed data like `gfi_v7/seeds/seed_all.py` | Low |
| `main.py:21-120` | `_apply_sqlite_dev_patches()` runs 60+ ALTER TABLE on every startup | Should be removed when migrating to PostgreSQL | Medium |
| `database.py:19-25` | SQLite WAL + FK pragma on every connection | Irrelevant overhead after PostgreSQL migration | Low |

### 8.2 Optimization Opportunities

| Optimization | Current | Target | Effort |
|---|---|---|---|
| **Database: SQLite → PostgreSQL** | Single-file DB, no connection pooling benefit | `asyncpg` with pool_size=20, proper indexes | Phase 0 |
| **Batch CCA balance computation** | Per-associate query in loop | Single `GROUP BY associe_id` query | Low |
| **Caching fiscal rates** | Queried per transaction | `@lru_cache` or Redis cache | Low |
| **Background closing** | Synchronous 7-step process | Celery task with Redis broker (gfi_v7 has `celery==5.4.0`) | Medium |
| **Seed data** | Parse markdown at runtime | Static Python dict like `seed_all.py` | Low |

---

## 9. GAP ANALYSIS — ALL MISSING COMPONENTS

### 9.1 Critical Gaps (P0 — Block Financial Operations)

| # | Component | Type | gfi_v7 Source | Status |
|---|---|---|---|---|
| G-01 | `CFFEngine` class | Service | `services/cff_engine.py:40-152` | **0% — MISSING** |
| G-02 | `cff_factures` table | Model | `models/cff.py:9-30` | **0% — MISSING** |
| G-03 | `cff_imputation_associes` table | Model | `models/cff.py:33-44` | **0% — MISSING** |
| G-04 | CFF REST endpoints | API | `api/v1/endpoints/cff.py` | **0% — MISSING** |
| G-05 | `transactions` table with RF1-RF4 | Model | `models/finance.py:28-48` | **0% — MISSING** |
| G-06 | Transaction CRUD endpoints | API | `api/v1/endpoints/transactions.py` | **0% — MISSING** |
| G-07 | `RealiteFinanciere` enum used on all tables | Model | 8+ tables | **5% — enum created, not yet applied** |
| G-08 | `realite_financiere` on `mouvements_comptes_courants` | Column | `models/associes.py:79` | **0% — column MISSING** |

### 9.2 High Priority Gaps (P1 — Required for Compliance)

| # | Component | Type | gfi_v7 Source |
|---|---|---|---|
| G-09 | Kill tests KT-01→KT-09 | Test | `tests/test_kill_tests.py:14-240` |
| G-10 | Kill test API endpoints | API | `api/v1/endpoints/health_check.py` |
| G-11 | 15 RBAC roles | Model+Seed | `models/rbac.py`, `seeds/seed_all.py:209-225` |
| G-12 | `AliasResolver` (project + entity) | Service | `services/alias_resolver.py` |
| G-13 | `projet_associes` table (% projet distinct from % entreprise) | Model | `models/projets.py:57-70` |
| G-14 | `projets_alias` table | Model | `models/projets.py:73-80` |
| G-15 | `flux_inter_projets` table | Model | `models/finance.py:50-67` |
| G-16 | `compensations_st` table (KT-05) | Model | `models/finance.py:70-88` |
| G-17 | `clotures_mensuelles_repartitions` table | Model | `models/finance.py:139-148` |
| G-18 | Fixed UUID seeds (9/12/15) | Seed | `seeds/seed_all.py:20-52` |
| G-19 | Seed `entreprise_associes` (% entreprise) | Seed | `seeds/seed_all.py:100-129` |

### 9.3 Medium Priority Gaps (P2 — Feature Completeness)

| # | Component | Type | gfi_v7 Source |
|---|---|---|---|
| G-20 | `vehicules_groupe` table | Model | `models/finance.py:151-227` |
| G-21 | `contrats_travail` table | Model | `models/rh.py` |
| G-22 | `fiches_paie` with RF | Model | `models/rh.py` |
| G-23 | `dossiers_juridiques` (FC-002 succession) | Model | `models/juridique_mg.py` |
| G-24 | `permis_autorisations` | Model | `models/juridique_mg.py` |
| G-25 | `commandes_achats` with RF + KT-05 | Model | `models/juridique_mg.py` |
| G-26 | `stock_materiel` | Model | `models/juridique_mg.py` |
| G-27 | Dockerfile | Infra | `gfi_v7/Dockerfile` |
| G-28 | docker-compose.yml | Infra | `gfi_v7/docker-compose.yml` |
| G-29 | requirements.txt (pinned) | Infra | `gfi_v7/requirements.txt` |
| G-30 | PostgreSQL as default DB | Config | `gfi_v7/app/core/config.py:11` |

### 9.4 Low Priority Gaps (P3 — Future)

| # | Component | Type | gfi_v7 Source |
|---|---|---|---|
| G-31 | 6 meta-IA tables | Model | `models/meta_ia.py` |
| G-32 | `auto_deploy = FALSE` enforcement | Invariant | `models/meta_ia.py` |
| G-33 | VSR-01 reference balances | Test | `tests/test_kill_tests.py` |

---

## 10. IMPLEMENTATION ROADMAP

### Phase 0 — Infrastructure (Prerequisite)

| Step | Action | Files | Depends On |
|---|---|---|---|
| 0.1 | Create `requirements.txt` from `gfi_v7/requirements.txt` + current deps | `requirements.txt` | — |
| 0.2 | Copy `Dockerfile` | `Dockerfile` | — |
| 0.3 | Copy `docker-compose.yml` | `docker-compose.yml` | — |
| 0.4 | Copy `alembic.ini` for PostgreSQL | `alembic.ini` | — |
| 0.5 | Update `config.py` DATABASE_URL default to PostgreSQL | `app/config.py:19-20` | 0.1 |
| 0.6 | Remove `_apply_sqlite_dev_patches()` from `main.py` | `app/main.py:21-120` | 0.5 |

### Phase 1 — Base Models GFI v7.0 **[DONE]**

| Step | Status | Files Modified |
|---|---|---|
| 1.1 | **DONE** | `app/models/financial.py` — `RealiteFinanciere` enum + `RF_TO_STATUT`/`STATUT_TO_RF` mappings |
| 1.2 | **DONE** | `app/models/financial.py` — `Entreprise` extended (+9 columns) |
| 1.3 | **DONE** | `app/models/financial.py` — `Projet` extended (+11 columns) |
| 1.4 | **DONE** | `app/models/financial.py` — `Associe` extended (+8 columns) |
| 1.5 | **DONE** | `app/models/financial.py` — `EntrepriseAssocie` table created |
| 1.6 | **DONE** | `app/models/financial.py` — `OrigineCapitalDetail` table created |
| 1.7 | **DONE** | `app/models/finance_associes.py` — `ClotureMensuelle` extended (+4 columns) |
| 1.8 | **DONE** | `app/services/cloture_service.py` — Tolerance 0.01→0.00, PartProjet→EntrepriseAssocie |
| 1.9 | **DONE** | `app/config.py` — GFI v7.0 fiscal constants added |
| 1.10 | **DONE** | `alembic/versions/007_gfi_v7_base.py` — Migration created |

### Phase 2 — CFF Engine (Gaps G-01→G-04)

| Step | Action | Source → Target |
|---|---|---|
| 2.1 | Copy CFF model | `gfi_v7/app/models/cff.py` → `app/models/cff.py` |
| 2.2 | Copy CFF engine | `gfi_v7/app/services/cff_engine.py` → `app/services/cff_engine.py` |
| 2.3 | Create CFF API endpoint | `gfi_v7/app/api/v1/endpoints/cff.py` → `app/api/cff.py` |
| 2.4 | Register route in `main.py` | Add `app.api.cff` router include |
| 2.5 | Create migration `008_cff_tables.py` | `cff_factures`, `cff_imputation_associes` |

### Phase 3 — RF1-RF4 + Transactions (Gaps G-05→G-08)

| Step | Action | Source → Target |
|---|---|---|
| 3.1 | Create `transactions` table | `gfi_v7/app/models/finance.py:28-48` → `app/models/financial.py` |
| 3.2 | Add `realite_financiere` to `mouvements_comptes_courants` | `gfi_v7/app/models/associes.py:79` → `app/models/finance_associes.py` |
| 3.3 | Create `flux_inter_projets`, `compensations_st` tables | `gfi_v7/app/models/finance.py` → `app/models/financial.py` |
| 3.4 | Create `centre_cout_mensuel` v7 columns (tnm_rf1/rf2/rf3/rf4, est_verrouille) | `gfi_v7/app/models/finance.py:91-108` |
| 3.5 | Create transaction endpoint | `gfi_v7/app/api/v1/endpoints/transactions.py` → `app/api/transactions.py` |
| 3.6 | Add RF to `employees` | `gfi_v7/app/models/rh.py` — `realite_financiere`, `nin`, `est_declare_cnas` |
| 3.7 | Create migration `009_rf_transactions.py` | All Phase 3 schema changes |

### Phase 4 — RBAC + Alias Resolver (Gaps G-11, G-12)

| Step | Action | Source → Target |
|---|---|---|
| 4.1 | Create RBAC model (15 roles) | `gfi_v7/app/models/rbac.py` → `app/models/rbac_gfi.py` |
| 4.2 | Copy alias resolver | `gfi_v7/app/services/alias_resolver.py` → `app/services/alias_resolver.py` |
| 4.3 | Create migration `010_rbac.py` | `roles`, `utilisateurs`, `utilisateur_roles` |

### Phase 5 — Seeds Unification (Gaps G-18, G-19)

| Step | Action |
|---|---|
| 5.1 | Copy `gfi_v7/seeds/seed_all.py` → `seeds/seed_all.py` |
| 5.2 | Update `app/services/seed_import.py` to call seed_all data |
| 5.3 | Normalize names: "YAMINA AIT BENAMARA" → "Dendani Yamina" |
| 5.4 | Verify KT-01: Yamina absent from DBPI/OC/EP/SEN/BIM in `entreprise_associes` |

### Phase 6 — Juridique + RH v7 (Gaps G-20→G-26)

| Step | Action |
|---|---|
| 6.1 | Create `contrats_travail`, `fiches_paie` tables |
| 6.2 | Create `dossiers_juridiques`, `permis_autorisations` tables |
| 6.3 | Create `commandes_achats`, `stock_materiel` tables |
| 6.4 | Create `vehicules_groupe` table |
| 6.5 | Create migration `011_juridique_rh_v7.py` |

### Phase 7 — Meta-IA (Gaps G-31, G-32)

| Step | Action |
|---|---|
| 7.1 | Copy `gfi_v7/app/models/meta_ia.py` → `app/models/meta_ia.py` |
| 7.2 | Enforce `auto_deploy = FALSE` invariant |
| 7.3 | Create migration `012_meta_ia.py` |

### Phase 8 — Kill Tests + Validation (Gaps G-09, G-10, G-33)

| Step | Action |
|---|---|
| 8.1 | Copy `gfi_v7/tests/test_kill_tests.py` → `tests/test_kill_tests.py` |
| 8.2 | Adapt imports to use existing Base and session fixtures |
| 8.3 | Create `app/api/health_check.py` with `/kt/sanity`, `/kt/kill-tests`, `/kt/vsr` |
| 8.4 | Add VSR-01 reference balances (Ahmed: -27.5M, Mohamed: +4.45M, Yazid: +4.45M, Yamina: -5M) |
| 8.5 | CI gate: all kill tests must pass before merge |

---

**END OF REPORT**

| Metric | Current | Target | Gap |
|---|---|---|---|
| Tables | 96 | 96 + 30 new = 126 | 30 tables |
| API Endpoints | 136+ | 136 + 15 new = 151+ | 15 endpoints |
| Services | 21 | 21 + 2 new = 23 | 2 services |
| Tests (kill) | 0 | 25+ | 25 tests |
| RBAC Roles | 5 | 15 | 10 roles |
| Score | 43/100 | 100/100 | 57 points |
