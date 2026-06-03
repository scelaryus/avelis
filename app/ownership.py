"""
GFI v7.0 — Ownership decision function.

This module is the SINGLE SOURCE OF TRUTH for determining which percentage
table to use for any financial operation. Every module that distributes
costs or revenues MUST call get_ownership_table() before proceeding.

Decision matrix:
┌──────────────────────────────────────────┬──────────────────────────────┐
│ Operation Type                           │ Which % table                │
├──────────────────────────────────────────┼──────────────────────────────┤
│ CFF (Coût Fiscal Fictif)                 │ entreprise_associe (company) │
│ Project profit distribution              │ part_projet (project)        │
│ Direct project charge (terrain, mat.)    │ part_projet (project)        │
│ Company charge (rent, admin, HQ)         │ entreprise_associe (company) │
│ Shared charge ventilated to a project    │ part_projet (TARGET project) │
│ Associate withdrawal (apartment, cash)   │ N/A — 100% to the associate │
│ Inter-project flow (debit side)          │ part_projet (SOURCE project) │
│ Inter-project flow (credit side)         │ part_projet (DEST project)   │
└──────────────────────────────────────────┴──────────────────────────────┘

Yamina rules (Y1–Y5) are enforced after every quote-part calculation
by validate_yamina_rules().
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class OperationType(Enum):
    """Every financial operation MUST declare its type."""

    CFF = "CFF"
    PROJECT_PROFIT = "PROJECT_PROFIT"
    DIRECT_PROJECT_CHARGE = "DIRECT_PROJECT_CHARGE"
    COMPANY_CHARGE = "COMPANY_CHARGE"
    VENTILATED_CHARGE = "VENTILATED_CHARGE"
    ASSOCIATE_WITHDRAWAL = "ASSOCIATE_WITHDRAWAL"
    INTER_PROJECT_DEBIT = "INTER_PROJECT_DEBIT"
    INTER_PROJECT_CREDIT = "INTER_PROJECT_CREDIT"


class OwnershipSource(Enum):
    """Which table supplies the percentages."""

    ENTREPRISE_ASSOCIE = "entreprise_associe"
    PART_PROJET = "part_projet"
    SINGLE_ASSOCIATE = "single_associate"


# ── Yamina's associate UUID (deterministic from seed) ────────────────────
YAMINA_ID = UUID("20000000-0000-0000-0000-000000000004")

# Companies where Yamina is at 0% (Y2)
YAMINA_ZERO_COMPANY_CODES = frozenset({
    "SARL-DBPI", "SARL-OC", "SARL-EP", "SARL-SEN",
    "EURL-BIM", "SARL-M60", "SARL-ARC", "SCI-DEN",
})

# Projects where Yamina is at 0% (Y3)
YAMINA_ZERO_PROJECT_CODES = frozenset({
    "IRENE", "OPERA",  # OPERA for DP-era entries
    "ELITE-DRIVE", "ALLO-MAISON",
    "LYS", "MAGNOLIA", "AUREA", "ASTERIA",
})

# Companies where Yamina was NEVER a member (Y4)
YAMINA_NEVER_MEMBER_COMPANY_CODES = frozenset({"SARL-AMF"})


def get_ownership_source(operation: OperationType) -> OwnershipSource:
    """
    Return which ownership table to query for a given operation type.
    This is a pure function — no DB access needed.
    """
    _MAP = {
        OperationType.CFF: OwnershipSource.ENTREPRISE_ASSOCIE,
        OperationType.PROJECT_PROFIT: OwnershipSource.PART_PROJET,
        OperationType.DIRECT_PROJECT_CHARGE: OwnershipSource.PART_PROJET,
        OperationType.COMPANY_CHARGE: OwnershipSource.ENTREPRISE_ASSOCIE,
        OperationType.VENTILATED_CHARGE: OwnershipSource.PART_PROJET,
        OperationType.ASSOCIATE_WITHDRAWAL: OwnershipSource.SINGLE_ASSOCIATE,
        OperationType.INTER_PROJECT_DEBIT: OwnershipSource.PART_PROJET,
        OperationType.INTER_PROJECT_CREDIT: OwnershipSource.PART_PROJET,
    }
    return _MAP[operation]


def get_percentages(
    session: Session,
    operation: OperationType,
    *,
    company_id: UUID | None = None,
    project_id: UUID | None = None,
    associate_id: UUID | None = None,
) -> dict[UUID, Decimal]:
    """
    Return {associate_id: percentage} for the given operation context.

    Raises:
        ValueError: if required context is missing, project has no parts
                    (FC-013), or company has no ownership (FC-008).
    """
    from app.models.entreprise_associe import EntrepriseAssocie
    from app.models.part_projet import PartProjet
    from app.models.project import Project
    from app.models.company import Company

    source = get_ownership_source(operation)

    if source == OwnershipSource.SINGLE_ASSOCIATE:
        if associate_id is None:
            raise ValueError(
                "ASSOCIATE_WITHDRAWAL requires associate_id."
            )
        return {associate_id: Decimal("100.0000")}

    if source == OwnershipSource.ENTREPRISE_ASSOCIE:
        if company_id is None:
            raise ValueError(
                f"Operation {operation.value} requires company_id."
            )
        rows = (
            session.query(EntrepriseAssocie)
            .filter(
                EntrepriseAssocie.company_id == company_id,
                EntrepriseAssocie.is_deleted.is_(False),
            )
            .all()
        )
        if not rows:
            company = session.get(Company, company_id)
            code = company.code if company else str(company_id)
            raise ValueError(
                f"Entreprise {code} : structure de parts non définie. "
                f"Ownership blocked — remplissez FC-008."
            )
        return {row.associate_id: row.percentage for row in rows}

    # source == PART_PROJET
    if project_id is None:
        raise ValueError(
            f"Operation {operation.value} requires project_id."
        )
    project = session.get(Project, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found.")

    if project.status in ("A_DEVELOPPER", "EN_ATTENTE_CONFIRMATION"):
        raise ValueError(
            f"Projet {project.code} : structure de parts non définie. "
            f"Remplissez FC-013."
        )

    rows = (
        session.query(PartProjet)
        .filter(
            PartProjet.project_id == project_id,
            PartProjet.is_deleted.is_(False),
        )
        .all()
    )
    if not rows:
        raise ValueError(
            f"Projet {project.code} : structure de parts non définie. "
            f"Remplissez FC-013."
        )
    return {row.associate_id: row.percentage for row in rows}


class YaminaViolation(Exception):
    """Raised when a quote-part calculation violates Yamina rules Y2–Y5."""

    pass


def validate_yamina_rules(
    session: Session,
    computed_amounts: dict[UUID, Decimal],
    *,
    company_code: str | None = None,
    project_code: str | None = None,
) -> None:
    """
    Y5 automated check — call AFTER every quote-part calculation.

    Verifies that Yamina's imputed amount is exactly 0 DA for operations
    falling under Y2, Y3, or Y4. Raises YaminaViolation if non-zero.
    """
    yamina_amount = computed_amounts.get(YAMINA_ID, Decimal("0"))

    # Y4: Yamina was NEVER in AMENFORT
    if company_code and company_code in YAMINA_NEVER_MEMBER_COMPANY_CODES:
        if yamina_amount != Decimal("0"):
            raise YaminaViolation(
                f"CRITICAL BUG — Y4 violation: Yamina imputed "
                f"{yamina_amount} DA on {company_code}. "
                f"Yamina was NEVER in AMENFORT. Amount must be 0 DA."
            )

    # Y2: Yamina at 0% in specific companies
    if company_code and company_code in YAMINA_ZERO_COMPANY_CODES:
        if yamina_amount != Decimal("0"):
            raise YaminaViolation(
                f"CRITICAL BUG — Y2 violation: Yamina imputed "
                f"{yamina_amount} DA on company {company_code}. "
                f"Must be exactly 0 DA."
            )

    # Y3: Yamina at 0% in specific projects
    if project_code and project_code in YAMINA_ZERO_PROJECT_CODES:
        if yamina_amount != Decimal("0"):
            raise YaminaViolation(
                f"CRITICAL BUG — Y3 violation: Yamina imputed "
                f"{yamina_amount} DA on project {project_code}. "
                f"Must be exactly 0 DA."
            )
