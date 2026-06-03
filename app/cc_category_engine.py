"""
GFI v7.0 — CC Category Engine: 16 cost categories with distribution rules.

Each category has specific: data sources, distribution rule, verifications.

Distribution rules:
  PCT_PROJET:       % from part_projet (CC1,2,3,4,7,8,12,13)
  PCT_ENTREPRISE:   % from entreprise_associe (CC6,11,14,15)
  ASSOCIATE_100PCT: 100% to specific associate (CC9,10)
  CUSTOM:           Category-specific logic (CC5 BBZ)
  MIXED:            Depends on sub-type (CC11,14,15)

Core API:
  impute_to_category(category, project_id, rf_type, montant, ...)
  distribute_among_associates(category, company_id, project_id, montant)
  ventilate_bbz(company_id, period, ...)
  impute_payroll(employee_id, period, ...)
  check_cc16_reclassification(session)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.ownership import (
    OperationType, get_percentages, validate_yamina_rules,
)


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ── Category → Distribution Rule mapping ─────────────────────────────────────
CATEGORY_DISTRIBUTION = {
    "TERRAIN":      "PCT_PROJET",
    "CONSTR":       "PCT_PROJET",
    "VRD":          "PCT_PROJET",
    "ETUDES":       "PCT_PROJET",
    "NATURE_ST":    "PCT_PROJET",
    "CFF":          "PCT_ENTREPRISE",   # CRITICAL: NEVER PCT_PROJET
    "FRAIS_FIN":    "MIXED",
    "COMPENSATION": "PCT_PROJET",
    "ASSOC":        "ASSOCIATE_100PCT",
    "COMMISSION":   "ASSOCIATE_100PCT",
    "CHARGES_GEN":  "PCT_PROJET",       # after ventilation
    "VENTES_RF1":   "PCT_PROJET",
    "VENTES_RF2":   "PCT_PROJET",
    "IMPOTS":       "MIXED",
    "DIVERS":       "PCT_PROJET",
    "INTER_PROJ":   "PCT_PROJET",       # source/dest specific
}

# ── Category → Source accounts mapping ────────────────────────────────────────
CATEGORY_ACCOUNTS = {
    "TERRAIN":    ["211", "622"],
    "CONSTR":     ["612"],
    "VRD":        ["612"],
    "ETUDES":     ["621"],
    "NATURE_ST":  ["604"],
    "CFF":        [],            # Fed by CFF engine
    "FRAIS_FIN":  ["66"],
    "COMPENSATION": [],          # No cash, no accounting
    "ASSOC":      ["455"],       # CCA
    "COMMISSION": ["455"],
    "CHARGES_GEN": ["613", "625"],
    "VENTES_RF1": ["701", "704"],
    "VENTES_RF2": [],            # RF2 internal tracking
    "IMPOTS":     ["64"],
    "DIVERS":     [],
    "INTER_PROJ": ["580"],
}


def distribute_among_associates(
    session: Session,
    *,
    category: str,
    company_id: UUID,
    project_id: UUID | None = None,
    montant: Decimal,
    associate_id: UUID | None = None,
    emitter_company_id: UUID | None = None,
) -> dict[UUID, Decimal]:
    """
    Distribute a CC amount among associates using the correct rule.
    Returns {associate_id: amount}.

    CRITICAL: CC6 (CFF) uses % ENTREPRISE EMETTRICE, never % PROJET.
    CC9/CC10 go 100% to the specific associate.
    """
    montant = Decimal(str(montant))
    rule = CATEGORY_DISTRIBUTION.get(category, "PCT_PROJET")

    # ── CC9/CC10: 100% to specific associate ─────────────────────────────
    if rule == "ASSOCIATE_100PCT":
        if associate_id is None:
            raise ValueError(
                f"Category {category} requires associate_id for distribution."
            )
        return {associate_id: montant}

    # ── CC6 (CFF): % of EMITTING company ────────────────────────────────
    if category == "CFF":
        cid = emitter_company_id or company_id
        percentages = get_percentages(
            session, OperationType.CFF, company_id=cid,
        )
        return _apply_percentages(percentages, montant)

    # ── PCT_ENTREPRISE ───────────────────────────────────────────────────
    if rule == "PCT_ENTREPRISE":
        percentages = get_percentages(
            session, OperationType.COMPANY_CHARGE, company_id=company_id,
        )
        return _apply_percentages(percentages, montant)

    # ── PCT_PROJET ───────────────────────────────────────────────────────
    if rule == "PCT_PROJET" and project_id:
        percentages = get_percentages(
            session, OperationType.DIRECT_PROJECT_CHARGE, project_id=project_id,
        )
        return _apply_percentages(percentages, montant)

    # ── MIXED: depends on context ────────────────────────────────────────
    if rule == "MIXED":
        if project_id:
            percentages = get_percentages(
                session, OperationType.DIRECT_PROJECT_CHARGE,
                project_id=project_id,
            )
        else:
            percentages = get_percentages(
                session, OperationType.COMPANY_CHARGE,
                company_id=company_id,
            )
        return _apply_percentages(percentages, montant)

    # Fallback: company percentages
    percentages = get_percentages(
        session, OperationType.COMPANY_CHARGE, company_id=company_id,
    )
    return _apply_percentages(percentages, montant)


def _apply_percentages(
    percentages: dict[UUID, Decimal],
    montant: Decimal,
) -> dict[UUID, Decimal]:
    """Apply ownership percentages to an amount. Last gets remainder."""
    result = {}
    distributed = Decimal("0")
    sorted_items = sorted(percentages.items(), key=lambda x: x[1], reverse=True)

    for i, (assoc_id, pct) in enumerate(sorted_items):
        if i == len(sorted_items) - 1:
            amount = montant - distributed
        else:
            amount = _r2(montant * pct / Decimal("100"))
        result[assoc_id] = amount
        distributed += amount

    return result


def impute_to_category(
    session: Session,
    *,
    category: str,
    company_id: UUID,
    project_id: UUID | None,
    rf_type: str,
    montant: Decimal,
    entry_date: date,
    libelle: str,
    associate_id: UUID | None = None,
    emitter_company_id: UUID | None = None,
    source_type: str | None = None,
    source_id: UUID | None = None,
    created_by: UUID | None = None,
) -> object:
    """
    High-level imputation: records the amount in the CC tree at the
    correct category node and distributes among associates.
    """
    from app.cost_center_engine import impute

    config = CATEGORY_DISTRIBUTION.get(category)
    if config is None:
        raise ValueError(f"Unknown CC category: {category}")

    impact = category != "COMPENSATION"

    # Build node code
    from app.models.cost_center import CostCenterNode
    # Find the L3 category node for this project
    if project_id:
        from app.models.project import Project
        project = session.get(Project, project_id)
        proj_code = project.code if project else "UNK"
        # Find entity code mapping
        node_prefix = _find_entity_prefix(session, company_id)
        node_code = f"{node_prefix}-{proj_code}-{category}"
    else:
        node_prefix = _find_entity_prefix(session, company_id)
        node_code = f"{node_prefix}-{category}"

    return impute(
        session,
        node_code=node_code,
        rf_type=rf_type,
        montant=Decimal(str(montant)),
        entry_date=entry_date,
        libelle=libelle,
        company_id=company_id,
        project_id=project_id,
        source_type=source_type,
        source_id=source_id,
        impact_tresorerie=impact,
        created_by=created_by,
    )


def _find_entity_prefix(session: Session, company_id: UUID) -> str:
    """Find the CC entity prefix (CC-ENTn) for a company."""
    from app.models.cost_center import CostCenterNode

    node = (
        session.query(CostCenterNode)
        .filter(
            CostCenterNode.company_id == company_id,
            CostCenterNode.level == 1,
            CostCenterNode.is_deleted.is_(False),
        )
        .first()
    )
    return node.code if node else f"CC-UNK-{str(company_id)[:8]}"


# ═════════════════════════════════════════════════════════════════════════════
# CC4: PAYROLL IMPUTATION
# ═════════════════════════════════════════════════════════════════════════════

def impute_payroll(
    session: Session,
    *,
    employee_id: UUID,
    company_id: UUID,
    period_month: int,
    period_year: int,
    total_cost: Decimal,
    entry_date: date,
    created_by: UUID | None = None,
) -> list:
    """
    CC4: Split an employee's monthly cost across projects per imputation table.
    """
    from app.models.cc_category import PayrollImputation

    allocations = (
        session.query(PayrollImputation)
        .filter(
            PayrollImputation.employee_id == employee_id,
            PayrollImputation.company_id == company_id,
            PayrollImputation.effective_from <= entry_date,
            PayrollImputation.is_deleted.is_(False),
            (PayrollImputation.effective_to.is_(None))
            | (PayrollImputation.effective_to >= entry_date),
        )
        .all()
    )

    if not allocations:
        raise ValueError(
            f"No payroll imputation defined for employee {employee_id}."
        )

    total_cost = Decimal(str(total_cost))
    entries = []

    for alloc in allocations:
        pct = Decimal(str(alloc.pourcentage_temps))
        amount = _r2(total_cost * pct / Decimal("100"))

        entry = impute_to_category(
            session,
            category="CHARGES_GEN",
            company_id=company_id,
            project_id=alloc.project_id,
            rf_type="RF1",
            montant=amount,
            entry_date=entry_date,
            libelle=f"Masse salariale {alloc.employee_name} ({pct}%)",
            source_type="payroll_imputation",
            source_id=alloc.id,
            created_by=created_by,
        )
        entries.append(entry)

    return entries


# ═════════════════════════════════════════════════════════════════════════════
# CC5: BBZ VENTILATION
# ═════════════════════════════════════════════════════════════════════════════

def ventilate_bbz(
    session: Session,
    *,
    company_id: UUID,
    monthly_total: Decimal,
    entry_date: date,
    created_by: UUID | None = None,
) -> list:
    """
    CC5: Ventilate BBZ charges across active projects using allocation key.
    If no key configured -> generates FC-006.
    """
    from app.models.cc_category import AllocationKey
    from app.formulaire_engine import generate_if_not_exists

    monthly_total = Decimal(str(monthly_total))

    key = (
        session.query(AllocationKey)
        .filter(
            AllocationKey.cc_category == "BBZ",
            AllocationKey.company_id == company_id,
            AllocationKey.is_active.is_(True),
            AllocationKey.effective_from <= entry_date,
            AllocationKey.is_deleted.is_(False),
            (AllocationKey.effective_to.is_(None))
            | (AllocationKey.effective_to >= entry_date),
        )
        .first()
    )

    if key is None:
        generate_if_not_exists(
            session,
            code="FC-006",
            company_id=company_id,
            context={"type": "BBZ ventilation"},
            blocked_resource_type="bbz_ventilation",
        )
        raise ValueError(
            "No allocation key for BBZ. FC-006 generated."
        )

    entries = []

    if key.basis == "POURCENTAGE_FIXE" and key.allocations:
        from app.models.project import Project

        for proj_code, pct in key.allocations.items():
            project = (
                session.query(Project)
                .filter(Project.code == proj_code,
                        Project.company_id == company_id,
                        Project.is_deleted.is_(False))
                .first()
            )
            if project:
                amount = _r2(monthly_total * Decimal(str(pct)) / Decimal("100"))
                entry = impute_to_category(
                    session,
                    category="CHARGES_GEN",
                    company_id=company_id,
                    project_id=project.id,
                    rf_type="RF1",
                    montant=amount,
                    entry_date=entry_date,
                    libelle=f"BBZ ventile {proj_code} ({pct}%)",
                    source_type="bbz_ventilation",
                    created_by=created_by,
                )
                entries.append(entry)

    return entries


# ═════════════════════════════════════════════════════════════════════════════
# CC16: AUTO-RECLASSIFICATION CHECK
# ═════════════════════════════════════════════════════════════════════════════

def check_cc16_reclassification(
    session: Session,
    today: date | None = None,
) -> list[dict]:
    """
    Check for CC16 (Divers) entries older than 30 days without reclassification.
    Returns list of alerts.
    """
    from app.models.cost_center import CostCenterEntry
    from datetime import timedelta

    if today is None:
        today = date.today()

    threshold = today - timedelta(days=30)

    overdue = (
        session.query(CostCenterEntry)
        .filter(
            CostCenterEntry.node_code.like("%-DIVERS%"),
            CostCenterEntry.entry_date <= threshold,
            CostCenterEntry.is_deleted.is_(False),
        )
        .all()
    )

    return [
        {
            "entry_id": str(e.id),
            "node_code": e.node_code,
            "montant": str(e.montant),
            "entry_date": str(e.entry_date),
            "days_old": (today - e.entry_date).days,
            "message": (
                f"Charge non classee dans CC16 depuis "
                f"{(today - e.entry_date).days} jours: {e.libelle}"
            ),
        }
        for e in overdue
    ]
