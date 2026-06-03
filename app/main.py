"""
GFI v7.0 — FastAPI Application Entry Point.

Serves the complete ERP system: 40 migrations, 136 models, 28 engines.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(
    title="GFI v7.0 — GFI ERP",
    version="7.0.0",
    description="ERP system managing 12 legal entities, 16 projects, 4 RF types.",
)

# ── Register API routers ──────────────────────────────────────────────────────
from app.api.v1.foundation import router as foundation_router
from app.api.v1.finance import router as finance_router
from app.api.v1.adv import router as adv_router
from app.api.v1.drh import router as drh_router
from app.api.v1.operations import router as operations_router
from app.api.v1.system import router as system_router
from app.api.v1.juridique import router as juridique_router
from app.api.v1.auth import router as auth_router
from app.api.v1.cc import router as cc_router
from app.api.v1.ged import router as ged_router
from app.api.v1.agents import router as agents_router
from app.api.v1.spi import router as spi_router
from app.api.v1.spi360 import router as spi360_router
from app.api.v1.drh_agents_api import router as drh_agents_router
from app.api.v1.dis import router as dis_router
from app.api.v1.stock import router as stock_router
from app.api.v1.supplier import router as supplier_router

app.include_router(foundation_router, prefix="/api/v1")
app.include_router(finance_router, prefix="/api/v1")
app.include_router(adv_router, prefix="/api/v1")
app.include_router(drh_router, prefix="/api/v1")
app.include_router(operations_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")
app.include_router(juridique_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(cc_router, prefix="/api/v1")
app.include_router(ged_router, prefix="/api/v1")
app.include_router(stock_router, prefix="/api/v1")
app.include_router(supplier_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(spi_router, prefix="/api/v1")
app.include_router(spi360_router, prefix="/api/v1")
app.include_router(drh_agents_router, prefix="/api/v1")
app.include_router(dis_router, prefix="/api/v1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "system": "GFI v7.0",
        "status": "running",
        "entities": 12,
        "projects": 16,
        "migrations": 40,
        "models": 136,
        "engines": 28,
    }


@app.get("/api/health")
async def health():
    """System health check."""
    from app.models import Base
    return {
        "status": "healthy",
        "tables": len(Base.metadata.tables),
        "database": "pending_connection",
    }


@app.get("/api/stats")
async def stats():
    """System statistics."""
    from app.models import Base
    tables = sorted(Base.metadata.tables.keys())
    return {
        "total_tables": len(tables),
        "tables": tables,
        "modules": {
            "foundation": ["company", "associate", "project", "auth_user"],
            "financial": ["financial_transaction", "cff_calculation", "journal_entry"],
            "adv": ["lot", "dossier_adv", "payment", "notary_escrow"],
            "cost_center": ["cost_center_node", "cost_center_entry", "margin_calculation"],
            "hr": ["employee", "employee_contract", "payslip", "leave_request"],
            "legal": ["legal_case", "legal_contract", "legal_compliance_rule"],
            "operations": ["operation", "operation_planning_task"],
            "ged": ["document", "detection_finding"],
        },
    }


@app.get("/api/entities")
async def entities():
    """List all 12 legal entities."""
    return {
        "entities": [
            {"code": "ETS-DK", "name": "ETS Alpha Immobilier", "form": "ETS", "status": "ACTIF"},
            {"code": "SARL-DP", "name": "SARL Beta Promotion", "form": "SARL", "status": "ACTIF"},
            {"code": "SARL-DBPI", "name": "SARL Gamma Construction", "form": "SARL", "status": "ACTIF"},
            {"code": "SARL-OC", "name": "SARL Delta Habitat", "form": "SARL", "status": "ACTIF"},
            {"code": "SARL-SEN", "name": "SARL Epsilon Batiment", "form": "SARL", "status": "ACTIF"},
            {"code": "SARL-EP", "name": "SARL Zeta Promotion", "form": "SARL", "status": "ACTIF"},
            {"code": "EURL-BIM", "name": "EURL Eta Construction", "form": "EURL", "status": "ACTIF"},
            {"code": "SARL-AMF", "name": "SARL Theta Beton", "form": "SARL", "status": "DISSOUTE"},
            {"code": "EURL-BAY", "name": "EURL Iota Services", "form": "EURL", "status": "SATELLITE"},
            {"code": "SARL-M60", "name": "SARL Kappa Rapide", "form": "SARL", "status": "ACTIF"},
            {"code": "SARL-ARC", "name": "SARL Lambda Design", "form": "SARL", "status": "ACTIF"},
            {"code": "SCI-DEN", "name": "SCI Mu Foncier", "form": "SCI", "status": "ACTIF"},
        ]
    }


@app.get("/api/projects")
async def projects():
    """List all 16 projects."""
    return {
        "projects": [
            {"code": "EDEN", "name": "Residence Horizon", "entity": "ETS-DK", "status": "ACTIF", "clients": 154},
            {"code": "JASMIN", "name": "Residence Soleil", "entity": "ETS-DK", "status": "ACTIF", "clients": 100},
            {"code": "OPERA", "name": "Residence Perle", "entity": "SARL-DP", "status": "ACTIF"},
            {"code": "LYS", "name": "Residence Cristal", "entity": "SARL-DBPI", "status": "ACTIF"},
            {"code": "IRENE", "name": "Residence Azur", "entity": "SARL-DP", "status": "ACTIF"},
            {"code": "MAGNOLIA", "name": "Residence Oasis", "entity": "SARL-OC", "status": "ACTIF", "clients": 18},
            {"code": "AUREA", "name": "Residence Emeraude", "entity": "SARL-DP", "status": "ACTIF", "clients": 199},
            {"code": "ASTERIA", "name": "Asteria", "entity": "SARL-SEN", "status": "ACTIF", "clients": 52},
            {"code": "MOSQUEE", "name": "Mosquée Taoura", "entity": "ETS-DK", "status": "DONATION"},
            {"code": "T21000", "name": "Terrain 21 000 m²", "entity": "ETS-DK", "status": "TERRAIN"},
            {"code": "T5000", "name": "Terrain 5 000 m²", "entity": "SARL-DBPI", "status": "EN_ATTENTE"},
            {"code": "T2400", "name": "Terrain 2 400 m²", "entity": "SARL-DBPI", "status": "TERRAIN"},
            {"code": "ELITE-DRIVE", "name": "Elite Drive", "entity": "EURL-BIM", "status": "A_DEVELOPPER"},
            {"code": "ALLO-MAISON", "name": "Allo Maison", "entity": "SARL-DP", "status": "A_DEVELOPPER"},
            {"code": "PFSB", "name": "PFSB", "entity": "EURL-BIM", "status": "A_DEVELOPPER"},
            {"code": "DG", "name": "DG", "entity": "SARL-DBPI", "status": "A_DEVELOPPER"},
        ]
    }


@app.get("/api/associates")
async def associates():
    """List the 9 associates with their ownership structures."""
    return {
        "founders": [
            {"name": "BENALI Karim", "role": "DAF / Gerant", "founder": True,
             "companies": {"ETS-DK": 25, "SARL-DP": 25, "SARL-DBPI": 60, "SARL-OC": 60,
                           "SARL-SEN": 60, "SARL-EP": 60, "EURL-BIM": 60, "SARL-AMF": 33.33,
                           "SARL-M60": 60, "SARL-ARC": 60, "SCI-DEN": 60}},
            {"name": "HAMIDI Said", "role": "Associe", "founder": True,
             "companies": {"ETS-DK": 25, "SARL-DP": 25, "SARL-DBPI": 20, "SARL-OC": 20,
                           "SARL-SEN": 20, "SARL-EP": 20, "EURL-BIM": 20, "SARL-AMF": 33.33,
                           "SARL-M60": 20, "SARL-ARC": 20, "SCI-DEN": 20}},
            {"name": "KHELIFI Omar", "role": "Associe", "founder": True,
             "companies": {"ETS-DK": 25, "SARL-DP": 25, "SARL-DBPI": 20, "SARL-OC": 20,
                           "SARL-SEN": 20, "SARL-EP": 20, "EURL-BIM": 20, "SARL-AMF": 33.33,
                           "SARL-M60": 20, "SARL-ARC": 20, "SCI-DEN": 20}},
            {"name": "MANSOURI Fatima", "role": "Associee", "founder": True,
             "companies": {"ETS-DK": 25, "SARL-DP": 25}},
        ],
        "project_associates": [
            {"name": "TOUNSI Rachid", "role": "Associe projet"},
            {"name": "SLIMANI Youcef", "role": "Associe projet"},
            {"name": "CHERIF Nabil", "role": "Associe projet"},
            {"name": "DJELLOUL Amir", "role": "Associe projet"},
            {"name": "RAHMANI Sofiane", "role": "Associe projet"},
        ],
    }


@app.get("/api/rf-rules")
async def rf_rules():
    """RF classification rules."""
    from app.rf import RealiteFinanciere, PaymentMode, RF_PAYMENT_RULES
    return {
        "rf_types": {
            "RF1": "Réel Déclaré — cheque/virement only",
            "RF2": "Réel Non Déclaré — cash only, encrypted",
            "RF3": "Fictif Déclaré — inter-group, triggers CFF",
            "RF4": "Fictif Non Déclaré — rare, DAF review",
        },
        "payment_rules": {
            rf.value: [pm.value for pm in modes]
            for rf, modes in RF_PAYMENT_RULES.items()
        },
        "views": {
            "vue_officielle": "RF1 + RF3",
            "vue_interne": "RF1 + RF2 + RF3 + RF4",
            "prix_reel": "RF1 + RF2",
            "ecart": "RF2 + RF4",
        },
    }


@app.get("/api/cff/example")
async def cff_example():
    """CFF worked example: AMENFORT 5M HT → ETS-DK for EDEN."""
    from decimal import Decimal, ROUND_HALF_UP
    def r2(v): return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    ht = Decimal("5000000")
    tva = r2(ht * Decimal("19") / 100)
    tap = r2(ht * Decimal("1") / 100)
    ibs_base = ht - tap
    ibs = r2(ibs_base * Decimal("19") / 100)
    stamp = Decimal("2500")
    cff = tva + tap + ibs + stamp

    return {
        "scenario": "AMENFORT emits 5M DA HT RF3 to ETS-DK for EDEN",
        "steps": {
            "1_TVA": f"{tva} DA (19%)",
            "2_TAP": f"{tap} DA (1%)",
            "3_IBS_base": f"{ibs_base} DA",
            "4_IBS": f"{ibs} DA (19%)",
            "5_Stamp": f"{stamp} DA (capped)",
        },
        "CFF_TOTAL": f"{cff} DA",
        "distribution": {
            "Ahmed": f"{r2(cff * Decimal('33.3334') / 100)} DA (33.33% AMENFORT)",
            "Mohamed": f"{r2(cff * Decimal('33.3333') / 100)} DA (33.33% AMENFORT)",
            "Yazid": f"{r2(cff - r2(cff * Decimal('33.3334') / 100) - r2(cff * Decimal('33.3333') / 100))} DA (33.33%)",
            "Yamina": "0 DA (NOT in AMENFORT — Y4 rule)",
        },
        "critical_rule": "Uses EMITTING COMPANY % (AMENFORT), NOT project % (EDEN)",
    }


@app.get("/api/migrations")
async def migrations():
    """Complete migration chain."""
    return {
        "total": 40,
        "chain": [
            "001: Foundation (company, associate, auth_user)",
            "002: Soft-delete triggers (KT-10)",
            "003: Projects + ownership (16 projects, 70 rows)",
            "004: RBAC (18 roles, 55 permissions, 225 mappings)",
            "005: Alias resolution (123 aliases, pg_trgm)",
            "006: Formulaire system (46 templates)",
            "007: Financial transactions (RF constraints, pgcrypto)",
            "008: CFF engine (5-step, V6/V7)",
            "009: Accounting SCF (58 accounts, journals)",
            "010: CCA treasury (36 CCAs, R-003)",
            "011: Treasury closing (7-step, SHA-256, period lock)",
            "012: EDD inventory (lot state machine)",
            "013: ADV dossier (17-state machine)",
            "014: Payment system (6 PAY-C constraints)",
            "015: Notary escrow (FIN-005, NOTAIRE-001)",
            "016: Credit workflow (9 steps, 5 tiers)",
            "017: Fonds propres (3-case, installments)",
            "018: Document generation (14 templates)",
            "019: Centre de Coûts (6-level hierarchy)",
            "020: CC categories (16 categories)",
            "021: Margin + distribution (3-step, 4 views)",
            "022: Verification (10 checks, 5-level alerts)",
            "023: GACEB (120M advance, RAP)",
            "024: Associate operations (withdrawals, founding)",
            "025: Procurement (SoD, CUMP)",
            "026: Project management (advancement, tiers)",
            "027: Legal governance (preemption, capital calls)",
            "028: HR foundation (employee, contracts)",
            "029: Payroll (10-step, IRG, CNAS)",
            "030: Payslip verification (6-level L1-L6)",
            "031: Onboarding (5 phases, 7 docs)",
            "032: Access control (S4A, badges)",
            "033: Leave management (10 types, fraud L5)",
            "034: Offboarding (STC, disciplinary)",
            "035: Compliance (ANPDP, visitor QR)",
            "036: GED pipeline (7 layers, dedup)",
            "037: Detection engine (15 patterns)",
            "038: Méta-IA (double DAF approval)",
            "039: Legal module (8 tables, 6 AI agents)",
            "040: Operations (11-source budget, Gantt, S-curve)",
        ],
    }
