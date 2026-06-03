# Avelis System Functionalities (Detailed Specification)

This document describes the implemented functional scope of the Avelis platform across frontend modules, backend APIs, workflows, controls, and cross-cutting behavior.

It is written from the current codebase implementation snapshot and is intended as a full operational reference for product, QA, and onboarding.

---

## 1) Platform Overview

Avelis is a multi-module enterprise management platform with:

- Authentication and role/module-based access.
- Module launcher and in-app module navigation.
- Operational domains: Foundation, Finance, ADV, Stock/Suppliers, Operations, RH, Juridique, GED, and System.
- AI-assisted processing in several workflows (document reading, imports, analysis, HR agents, compliance, etc.).
- Cross-domain dashboards, alerts, auditability, and structured workflows.

Primary architecture split:

- `frontend`: React application (module UI and business flows).
- `app/api/v1`: FastAPI route surfaces grouped by domain.

---

## 2) Authentication, Session, Access Control

### 2.1 Login and Session

- User login via `/auth/login`.
- Token storage in local storage (`access_token`) and persisted `user_info`.
- Session restore on app reload from local storage.
- Logout clears persisted token/user info and resets auth state.
- Refresh/MFA endpoints exist (`/auth/refresh`, `/auth/mfa/verify`) for session lifecycle hardening.

### 2.2 User Identity and Security Context

User context includes:

- `user_id`, `email`, `name`, `role`
- `modules` (explicit module access list)
- `has_rf2` (specific capability flag)

### 2.3 Module-Level Authorization

- Frontend filters visible modules by `user.modules`.
- If no modules are present (legacy/admin/dev profile), full module list is visible.
- Unauthorized module entries are hidden from launcher/navigation.

### 2.4 Route Guarding

- Unauthenticated users are redirected to `/login`.
- Authenticated entry route is module launcher (`/`).
- Unknown paths are redirected to `/`.

---

## 3) Global Navigation and UX Structure

### 3.1 Login Experience

- Split-screen login page with:
  - Branded left panel.
  - Animated illustration.
  - Styled authentication form.
- Custom SVG logo and motion-enhanced visual components.

### 3.2 Module Launcher

- Entry page (`/`) labeled "Choisir un module".
- Card-based module selection.
- Animated background layers and card motion.
- Direct navigation from module card to module default page.

### 3.3 In-App Shell

- Left sidebar for main module switching.
- Top submenu bar for module-specific pages.
- Active route resolution drives active module and active subpage highlighting.
- Sidebar uses split module tiles; top bar provides fast sub-menu navigation.
- Global accent theme has been shifted to dark red/burgundy across launcher, login, dashboard, and module actions.

### 3.4 Branding and Display Naming

- Product brand displayed in UI is `Avelis` (replacing previous `GFI Workspace` naming in shell/login).
- Custom SVG mark is used in login and shell branding blocks.
- Legacy project codes are hidden in several user-facing surfaces via display remapping/sanitization:
  - `EDEN` -> `HORIZON`
  - `AUREA` -> `EMERAUDE`
  - `IRENE` -> `RUBIS`
  - `JASMIN` -> `AZURA`
  - `OPERA` -> `NOVA`
  - `LYS` -> `SIGMA`
  - `BAYTI` -> `ORION`
  - `ALLO_MAISON` -> `ATLAS`
  - `MAGNOLIA` -> `CELESTE`

---

## 4) Dashboard and Executive Monitoring

Primary dashboard route: `/dashboard`

Implemented dashboard capabilities include:

- Treasury global KPI.
- Projects active/total visual.
- Lot status and commercialization indicators.
- Alert severity distribution and active alert list.
- HR/Finance/Stock/ADV mini KPIs.
- Project commercialization progression bars.
- RF distribution view.
- Associate CCA balances and breakdown.
- Animated hero illustration for executive overview context.

Data sources include:

- `/system/dashboard`
- `/system/alerts`
- Related domain dashboards (Finance/ADV/CC/Stock/SPI, etc.).

---

## 5) Foundation Module (Master Data and Structuring)

Frontend routes:

- `/foundation/entities`
- `/foundation/entities/:entityId`
- `/foundation/projects`
- `/foundation/projects/:projectCode`

Backend foundation capabilities:

- Entity listing/detail/create/update.
- Project listing/detail/create/update.
- Ownership structure retrieval and transfer.
- Associates listing/detail.
- Alias management and alias resolution.
- Formulaires listing/detail/response submission.

API surface:

- `/foundation/entities*`
- `/foundation/projects*`
- `/foundation/associates*`
- `/foundation/aliases*`
- `/foundation/formulaires*`

---

## 6) Finance Module

Frontend routes:

- `/finance/cc`
- `/finance/cc/:nodeCode`
- `/finance/cca`
- `/finance/cca/:associateId`
- `/finance/cca/:associateId/withdraw`
- `/finance/cff`
- `/finance/cff/new`
- `/finance/gaceb`
- `/finance/journal`
- `/finance/rapprochement`

Core capabilities:

### 6.1 CFF

- Calculation workflow.
- History retrieval.
- Record creation.

### 6.2 Journal and Accounting Ingestion

- Journal entries listing.
- Document reading for journal extraction.
- AI-assisted import processing.

### 6.3 Rapprochement (Bank Reconciliation)

- Statement upload.
- Automatic matching.
- Manual matching.
- Statement listing/detail.
- Journal-rapprochement combined matching flows.

### 6.4 CCA (Associate Current Accounts)

- CCA balances view.
- Associate movement history.
- Withdraw and deposit transactions.

### 6.5 Period Closing

- Period listing.
- Closing start.
- Closing state retrieval.
- Step-by-step validation in closing pipeline.

### 6.6 Cost Center + GACEB + Rules

- Cost center tree/dashboard references.
- RF rules retrieval.
- GACEB RAP retrieval.

API surface (Finance router):

- `/finance/cff/*`
- `/finance/journal/*`
- `/finance/rapprochement/*`
- `/finance/journal-rapprochement*`
- `/finance/cca/*`
- `/finance/closing/*`
- `/finance/cc/*`
- `/finance/rf/rules`
- `/finance/gaceb/rap`

---

## 7) Cost Center (CC) Domain

Dedicated router: `/cc`

Capabilities:

- Cost center tree retrieval.
- Drill-down by node.
- Dashboard views.
- Project margin/distribution analytics.
- Verification and alert outputs.
- GACEB situations and vehicle outputs.

API surface:

- `/cc/tree*`
- `/cc/dashboard*`
- `/cc/project/*`
- `/cc/verifications`
- `/cc/alerts`
- `/cc/gaceb/*`

---

## 8) ADV (Administration des Ventes)

Frontend routes:

- `/adv/lots`
- `/adv/lots/new`
- `/adv/edd/import`
- `/adv/pipeline`
- `/adv/dossiers/new`
- `/adv/dossiers/:id`
- `/adv/dossiers/:id/payment`
- `/adv/payments`
- `/adv/pricing`

Core capabilities:

### 8.1 EDD Lots and Pricing

- Lot listing/detail.
- Lock/unlock lot states.
- Lot creation.
- Pricing grid read/update/calculate.
- Document reading and AI lot import (including file import).
- Project/lot display text includes UI-level sanitization to avoid showing legacy project labels directly.

### 8.2 Dossier Lifecycle

- Dossier listing/detail/create.
- Tier updates and transition workflow.
- Transition history retrieval.

### 8.3 Commission Management

- Commission listing.
- Claim/validate commission actions.
- Pending and unclaimed queues.

### 8.4 Payment Workflow

- Payment listing and creation.
- Cheque analysis.
- Validation and rejection.

### 8.5 Credit Tier and Disbursement Chain

- Credit tiers retrieval/initiation.
- Expert report submission and validation.
- Tier disbursement actions.

### 8.6 Wire Orders and Schedules

- Wire-order creation and signing.
- Echeancier retrieval/creation/payment.

### 8.7 Escrow Operations

- Escrow retrieval.
- VSP-20 and release-5 actions.

### 8.8 Dossier Documents

- Dossier document listing.
- Document receipt confirmation.

### 8.9 ADV Analytics

- ADV dashboard endpoints.
- EDD dashboard endpoint.

API surface:

- `/adv/edd/*`
- `/adv/dossiers/*`
- `/adv/commissions*`
- `/adv/payments*`
- `/adv/dashboard`
- `/adv/edd/dashboard`

---

## 9) Stock and Supplier Module

Frontend routes:

- `/stock`
- `/stock/new`
- `/stock/consume`
- `/fournisseurs`

### 9.1 Stock Capabilities

- Item identification.
- Zones CRUD (list/create/delete).
- Item CRUD (list/create/update/detail).
- Barcode generation and label retrieval.
- Barcode lookup.
- Stock consumption operation.
- Stock dashboard metrics.

API surface:

- `/stock/identify`
- `/stock/zones*`
- `/stock/items*`
- `/stock/lookup/*`
- `/stock/consume`
- `/stock/dashboard`

### 9.2 Supplier Capabilities

- Supplier listing/create/detail.
- Supplier contracts creation.
- Supplier payment registration.

API surface:

- `/suppliers*`

---

## 10) Operations Module

Frontend routes:

- `/operations`
- `/operations/new`
- `/operations/:id`

Capabilities:

- Operation list/detail/create/update.
- Status transition and treasury visa action.
- Budget retrieval and manual budget input.
- Planning retrieval.
- Planning task creation/update.
- Critical path and S-curve retrieval.
- Planning snapshots.
- WBS template retrieval and template deployment.
- Budget refresh for single and all operations.

API surface:

- `/operations/*`

---

## 11) RH (Human Resources) Module

Frontend routes:

- `/rh/employees`
- `/rh/employees/new`
- `/rh/payroll`
- `/rh/payroll/payslips/:id/verify`
- `/rh/leave`
- `/rh/onboarding`
- `/rh/offboarding`
- `/rh/spi360`
- `/rh/spi360/:employeeId`
- `/rh/spi360/tasks/needs`
- `/rh/spi360/config`
- `/rh/commissions`
- `/rh/recruitment`
- `/rh/recruitment/listing`
- `/rh/discipline`
- `/rh/visitors`

### 11.1 Core HR (DRH Router)

- Employee list/detail/create/import.
- Payroll batch calculate and fetch.
- Payslip detail/verification/approve/reject.
- Leave request list/create/approve.
- Onboarding pipeline.
- Offboarding checklist.

API surface:

- `/drh/employees*`
- `/drh/payroll/*`
- `/drh/leave/*`
- `/drh/onboarding/*`
- `/drh/offboarding/*`

### 11.2 SPI / SPI360 Performance Systems

SPI (`/drh/spi`):

- Base SPI list/detail.
- Evaluate/validate/contest SPI.
- Commissions endpoint.

SPI360 (`/drh/spi360`):

- Dashboard and employee detail.
- Daily calculations.
- Task retrieval and manager validation.
- Needs creation/listing/decomposition.
- Assignment proposals, DAF responses, proof submission, finalization.
- Config read/update by position.

---

## 12) Juridique Module

Frontend routes:

- `/juridique`
- `/juridique/contracts`
- `/juridique/contracts/new`
- `/juridique/cases`
- `/juridique/cases/:caseId`
- `/juridique/compliance`

Capabilities:

### 12.1 Cases

- Case listing/detail/create/update.
- Stage transitions.
- Event logging on case timeline.
- Case feedback and reporting.

### 12.2 Contracts

- Contract list/detail/create/update.
- Supplier contract checks.

### 12.3 Compliance

- Compliance dashboard and alerts.
- Compliance rules retrieval.
- Feedback listing.

API surface:

- `/juridique/cases*`
- `/juridique/contracts*`
- `/juridique/compliance/*`
- `/juridique/feedback`
- `/juridique/cases/{case_id}/report`

---

## 13) GED and Document Intelligence

Frontend routes:

- `/documents`
- `/documents/search`

### 13.1 GED Router

- Document upload.
- Document listing/detail.
- Pipeline status.
- GED project selectors keep backend project codes for filtering, but expose user-facing project labels via mapped display names.

API surface:

- `/ged/upload`
- `/ged/documents*`
- `/ged/pipeline/status`

### 13.2 DIS Router (Document Intelligence)

- Single/batch/drive ingestion.
- Document preview and detail retrieval.
- Confirmation/draft/quarantine actions.
- Search and review queue.
- Stats output.

API surface:

- `/dis/ingest*`
- `/dis/{doc_id}*`
- `/dis/search`
- `/dis/review-queue`
- `/dis/stats`

---

## 14) System Module

Frontend routes:

- `/system/alerts`
- `/system/agents`
- `/system/agents/control`
- `/system/audit`
- `/system/formulaires`
- `/system/formulaires/:code`

Capabilities:

- System dashboard and health checks.
- Agent status and controls.
- Alerts center.
- Audit trail.
- Notifications and mark-as-read.
- Meta-IA proposal retrieval.
- Formulaires browsing and response handling via foundation/system pages.

API surface:

- `/system/dashboard`
- `/system/health`
- `/system/agents/status`
- `/system/alerts`
- `/system/audit-trail`
- `/system/notifications*`
- `/system/meta-ia/proposals`

---

## 15) AI Agent Surfaces

### 15.1 Generic AI Agents (`/agents`)

- CFF calculation.
- Document processing.
- Payroll L2 verification.
- ADV chain operations.
- Compliance checks.
- Detection analysis.

### 15.2 DRH Agents (`/agents/drh`)

Supports advanced HR automations:

- Dossier checks, contract generation.
- Time aggregation.
- Recruitment listing/profile generation and CV scoring.
- Recruitment batch flows.
- Training plans.
- GED classification.
- Onboarding hardware provisioning and access setup.
- Discipline evaluation and case lifecycle.
- Messaging.
- BI generation.
- Declaration preparation.
- Loan eligibility checks.
- Vision analysis.
- Career suggestions.
- Security checks.
- Visitor registration.

---

## 16) Alerts, Notifications, and Auditability

- Alerts available at system level and surfaced in dashboard.
- Notification center with read-state updates.
- Audit trail endpoint for traceability and compliance.
- Domain-specific validations and staged transitions (ADV, Juridique, Operations, DRH, etc.) support controlled process progression.

---

## 17) Workflow and State-Machine Characteristics

The platform contains multi-step business workflows with explicit state actions:

- ADV dossier transitions and payment validation/rejection.
- Credit-tier disbursement chain and expert validation.
- Finance closing with step validation.
- Juridique case stage transitions and events.
- DRH payroll verification/approval/rejection.
- Operations transition and treasury visa.
- SPI/SPI360 assignment and validation lifecycle.

These indicate process-driven control rather than simple CRUD.

---

## 18) Reporting and Analytical Outputs

Implemented analytical/reporting dimensions include:

- Executive dashboard KPIs (cross-domain).
- Cost center analytics and drill-down.
- ADV dashboards and commercialization.
- Stock dashboard.
- SPI/SPI360 dashboards.
- Compliance and legal reporting.
- Journal/rapprochement outputs.

---

## 19) Functional Coverage Matrix (Frontend Module to Backend Domain)

- **Dashboard** -> `system`, `finance`, `adv`, `cc`, `drh`, `stock` aggregated indicators.
- **Foundation** -> `foundation`.
- **Finance** -> `finance` + `cc`.
- **ADV** -> `adv`.
- **Stock/Fournisseurs** -> `stock`, `suppliers`.
- **Operations** -> `operations`.
- **RH** -> `drh`, `spi`, `spi360`, `agents/drh`.
- **Juridique** -> `juridique`.
- **Documents** -> `ged`, `dis`.
- **System** -> `system`, plus forms and agent operational views.

---

## 20) Current Functional Notes and Boundaries

- This document reflects implemented surfaces discovered in current routes/components/endpoints.
- Some endpoints may be internal or partially wired in UI; they are still part of backend functional capability.
- "Every single functionality" is captured by:
  - frontend route inventory,
  - backend API route inventory,
  - module/workflow decomposition,
  - cross-cutting control and analytics features.

For governance-grade completeness, you can pair this with:

- endpoint request/response schemas,
- role-permission matrix per action,
- state transition diagrams per workflow,
- data dictionary by module.

