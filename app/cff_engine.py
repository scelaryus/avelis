"""
GFI v7.0 — CFF (Coût Fiscal Fictif) Calculation Engine.

The most error-prone calculation in the system because the distribution
rule is counterintuitive: CFF costs are distributed based on the
EMITTING COMPANY's ownership percentages, NOT the project's, NOT the
receiving company's.

Trigger (R-018): Any RF3 invoice where both emitter and receiver are
group entities -> automatically launch CFF calculation.

Calculation — 5 sequential steps (R-027):
  1. TVA = montant_HT * 19%
  2. TAP = montant_HT * taux_TAP of EMITTING company (1% or 2%)
  3. IBS_base = montant_HT - TAP_amount
  4. IBS = IBS_base * taux_IBS of EMITTING company (19% or 26%)
  5. Stamp duty = based on TTC and bareme_timbre schedule

CFF_TOTAL = TVA + TAP + IBS + Stamp duty

Distribution (R-001, KT-02): CFF_TOTAL distributed to associates of
the EMITTING company using entreprise_associe percentages. NEVER
from part_projet. NEVER from the receiving company.

Post-calculation verifications:
  V6: Verify percentages came from entreprise_associe (emitter)
  V7: Verify Yamina = 0 for protected companies (Y5)

Example (TD-02): Ahmed CFF in GFI Promo = 25% (company share),
NOT 60% (his project share in CHERAGA).
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.formulaire_engine import generate_if_not_exists, OperationBlocked
from app.ownership import (
    OperationType,
    OwnershipSource,
    get_ownership_source,
    get_percentages,
    validate_yamina_rules,
    YaminaViolation,
)


class CffCalculationError(Exception):
    """Raised when CFF calculation cannot proceed."""

    pass


class CffVerificationError(Exception):
    """Raised when post-calculation verification fails."""

    def __init__(self, message: str, verification: str):
        super().__init__(message)
        self.verification = verification


# ── Constants ────────────────────────────────────────────────────────────────
TVA_RATE = Decimal("19")


def _round2(value: Decimal) -> Decimal:
    """Round to 2 decimal places (standard financial rounding)."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_stamp_duty(
    session: Session,
    ttc: Decimal,
    invoice_date: date,
    emitter_company_id: UUID,
) -> Decimal:
    """
    Calculate stamp duty based on the bareme_timbre schedule in effect.

    Rules:
      - TTC <= exemption_threshold -> 0 DA (exempt)
      - TTC > threshold -> TTC * rate, capped at cap_amount (if any)
      - No schedule for date -> BLOCK, generate FC-011

    Returns the stamp duty amount.
    """
    from app.models.bareme_timbre import BaremeTimbre

    bareme = (
        session.query(BaremeTimbre)
        .filter(
            BaremeTimbre.effective_from <= invoice_date,
            BaremeTimbre.is_deleted.is_(False),
            (BaremeTimbre.effective_to.is_(None))
            | (BaremeTimbre.effective_to >= invoice_date),
        )
        .order_by(BaremeTimbre.effective_from.desc())
        .first()
    )

    if bareme is None:
        # BLOCK: no schedule available
        generate_if_not_exists(
            session,
            code="FC-011",
            company_id=emitter_company_id,
            context={"date": str(invoice_date)},
            blocked_resource_type="cff_calculation",
        )
        raise CffCalculationError(
            f"No stamp duty schedule (bareme_timbre) available for "
            f"date {invoice_date}. FC-011 generated."
        )

    if ttc <= bareme.exemption_threshold:
        return Decimal("0.00")

    duty = _round2(ttc * bareme.rate_percent / Decimal("100"))

    if bareme.cap_amount is not None and duty > bareme.cap_amount:
        duty = bareme.cap_amount

    return duty


def calculate_cff(
    session: Session,
    *,
    montant_ht: Decimal,
    emitter_company_id: UUID,
    receiver_company_id: UUID,
    project_id: UUID | None,
    invoice_date: date,
    invoice_ref: str | None = None,
    financial_transaction_id: UUID | None = None,
    created_by: UUID | None = None,
) -> object:
    """
    Execute the full 5-step CFF calculation and distribute to associates.

    This is the core function. It:
      1. Validates emitter has IBS/TAP rates (else FC-005 + block)
      2. Validates emitter has ownership data (else FC-008 + block)
      3. Computes TVA, TAP, IBS, stamp duty
      4. Distributes CFF_TOTAL to emitter's associates
      5. Runs V6 and V7 verifications
      6. Stores everything (CffCalculation + CffImputations)

    Returns the CffCalculation object.
    """
    from app.models.company import Company
    from app.models.cff_calculation import CffCalculation
    from app.models.cff_imputation import CffImputation

    montant_ht = Decimal(str(montant_ht))

    # ── Load emitter company ─────────────────────────────────────────────
    emitter = session.get(Company, emitter_company_id)
    if emitter is None:
        raise CffCalculationError(
            f"Emitter company {emitter_company_id} not found."
        )

    # ── Check TAP rate (step 2 needs it) ─────────────────────────────────
    if emitter.tap_rate is None:
        generate_if_not_exists(
            session,
            code="FC-005",
            company_id=emitter_company_id,
            context={"entite": emitter.legal_name},
            blocked_resource_type="company",
            blocked_resource_id=emitter_company_id,
        )
        raise CffCalculationError(
            f"TAP rate for {emitter.code} is NULL. "
            f"CFF calculation blocked. FC-005 generated."
        )

    # ── Check IBS rate (step 4 needs it) ─────────────────────────────────
    if emitter.ibs_rate is None:
        generate_if_not_exists(
            session,
            code="FC-005",
            company_id=emitter_company_id,
            context={"entite": emitter.legal_name},
            blocked_resource_type="company",
            blocked_resource_id=emitter_company_id,
        )
        raise CffCalculationError(
            f"IBS rate for {emitter.code} is NULL. "
            f"CFF calculation blocked. FC-005 generated."
        )

    tap_rate = Decimal(str(emitter.tap_rate))
    ibs_rate = Decimal(str(emitter.ibs_rate))

    # ═════════════════════════════════════════════════════════════════════
    # 5-STEP CALCULATION (R-027)
    # ═════════════════════════════════════════════════════════════════════

    # Step 1: TVA
    tva_amount = _round2(montant_ht * TVA_RATE / Decimal("100"))

    # Step 2: TAP
    tap_amount = _round2(montant_ht * tap_rate / Decimal("100"))

    # Step 3: IBS base = HT - TAP (TAP is deductible)
    ibs_base = montant_ht - tap_amount

    # Step 4: IBS
    ibs_amount = _round2(ibs_base * ibs_rate / Decimal("100"))

    # Step 5: Stamp duty
    ttc = montant_ht + tva_amount
    stamp_duty = get_stamp_duty(
        session, ttc, invoice_date, emitter_company_id
    )
    stamp_exempt = "Y" if stamp_duty == Decimal("0") else "N"

    # CFF total
    cff_total = tva_amount + tap_amount + ibs_amount + stamp_duty

    # ═════════════════════════════════════════════════════════════════════
    # DISTRIBUTION (R-001, KT-02)
    # ═════════════════════════════════════════════════════════════════════

    # V6 pre-check: verify we're using entreprise_associe
    assert get_ownership_source(OperationType.CFF) == OwnershipSource.ENTREPRISE_ASSOCIE, \
        "V6 CRITICAL: CFF must use entreprise_associe, not part_projet"

    # Get EMITTER's ownership percentages
    try:
        percentages = get_percentages(
            session,
            OperationType.CFF,
            company_id=emitter_company_id,
        )
    except ValueError:
        # No ownership data -> block with FC-008
        generate_if_not_exists(
            session,
            code="FC-008",
            company_id=emitter_company_id,
            context={"entite": emitter.legal_name},
            blocked_resource_type="company",
            blocked_resource_id=emitter_company_id,
        )
        raise CffCalculationError(
            f"Ownership for {emitter.code} not defined. "
            f"CFF blocked. FC-008 generated."
        )

    # Distribute CFF_TOTAL to associates
    computed_amounts: dict[UUID, Decimal] = {}
    distributed_total = Decimal("0")
    sorted_assoc = sorted(percentages.items(), key=lambda x: x[1], reverse=True)

    for i, (assoc_id, pct) in enumerate(sorted_assoc):
        if i == len(sorted_assoc) - 1:
            # Last associate gets remainder (avoids rounding drift)
            amount = cff_total - distributed_total
        else:
            amount = _round2(cff_total * pct / Decimal("100"))
        computed_amounts[assoc_id] = amount
        distributed_total += amount

    # ═════════════════════════════════════════════════════════════════════
    # V7 — YAMINA PROTECTION (Y5)
    # ═════════════════════════════════════════════════════════════════════
    try:
        validate_yamina_rules(
            session,
            computed_amounts,
            company_code=emitter.code,
        )
    except YaminaViolation as e:
        raise CffVerificationError(
            str(e), verification="V7"
        )

    # ═════════════════════════════════════════════════════════════════════
    # PERSIST
    # ═════════════════════════════════════════════════════════════════════

    calc = CffCalculation(
        company_id=emitter_company_id,
        financial_transaction_id=financial_transaction_id,
        receiver_company_id=receiver_company_id,
        project_id=project_id,
        invoice_date=invoice_date,
        invoice_ref=invoice_ref,
        montant_ht=montant_ht,
        # Step 1
        tva_rate=TVA_RATE,
        tva_amount=tva_amount,
        # Step 2
        tap_rate=tap_rate,
        tap_amount=tap_amount,
        # Step 3+4
        ibs_base=ibs_base,
        ibs_rate=ibs_rate,
        ibs_amount=ibs_amount,
        # Step 5
        ttc_amount=ttc,
        stamp_duty_amount=stamp_duty,
        stamp_duty_exempt=stamp_exempt,
        # Total
        cff_total=cff_total,
        # Verifications
        v6_source_verified="Y",
        v7_yamina_verified="Y",
        status="VERIFIED",
        created_by=created_by,
    )
    session.add(calc)
    session.flush()

    # Create imputation rows
    for assoc_id, amount in computed_amounts.items():
        imp = CffImputation(
            company_id=emitter_company_id,
            cff_calculation_id=calc.id,
            associate_id=assoc_id,
            percentage_used=percentages[assoc_id],
            amount=amount,
            percentage_source="entreprise_associe",
            created_by=created_by,
        )
        session.add(imp)

    session.flush()
    return calc


def verify_cff_calculation(
    session: Session,
    cff_calculation_id: UUID,
) -> dict:
    """
    Re-run V6 and V7 verifications on an existing CFF calculation.
    Returns {"v6": "PASS"/"FAIL", "v7": "PASS"/"FAIL", "details": ...}
    """
    from app.models.cff_calculation import CffCalculation
    from app.models.cff_imputation import CffImputation
    from app.models.company import Company

    calc = session.get(CffCalculation, cff_calculation_id)
    if not calc:
        raise ValueError(f"CffCalculation {cff_calculation_id} not found.")

    result = {"v6": "PASS", "v7": "PASS", "details": []}

    # V6: verify all imputations used entreprise_associe
    imputations = (
        session.query(CffImputation)
        .filter(
            CffImputation.cff_calculation_id == cff_calculation_id,
            CffImputation.is_deleted.is_(False),
        )
        .all()
    )

    for imp in imputations:
        if imp.percentage_source != "entreprise_associe":
            result["v6"] = "FAIL"
            result["details"].append(
                f"V6 FAIL: imputation {imp.id} used "
                f"'{imp.percentage_source}' instead of 'entreprise_associe'"
            )

    # V7: Yamina check
    emitter = session.get(Company, calc.company_id)
    computed = {imp.associate_id: imp.amount for imp in imputations}

    try:
        validate_yamina_rules(
            session,
            computed,
            company_code=emitter.code if emitter else None,
        )
    except YaminaViolation as e:
        result["v7"] = "FAIL"
        result["details"].append(f"V7 FAIL: {e}")

    return result
