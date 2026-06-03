"""
GFI v7.0 — Payroll Engine: 10-step calculation for all 12 entities.

Handles both GENERAL (34%) and BTPH (34.75%) CNAS regimes.
BTPH rates INCLUDE CACOBATPH surcharge — NOT added separately.

Core API:
  calculate_payslip(employee_id, month, year) -> Payslip
  calculate_irg(taxable) -> (irg_brut, abatement, irg_final)
  run_monthly_payroll(company_id, month, year) -> list[Payslip]
"""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _floor(v: Decimal) -> Decimal:
    """Round DOWN to nearest DZD (for CNAS)."""
    return v.quantize(Decimal("1"), rounding=ROUND_DOWN)


# ── IRG monthly brackets (Step 5) ────────────────────────────────────────────
IRG_BRACKETS = [
    (Decimal("20000"),  Decimal("0")),
    (Decimal("40000"),  Decimal("0.23")),
    (Decimal("80000"),  Decimal("0.27")),
    (Decimal("160000"), Decimal("0.30")),
    (Decimal("320000"), Decimal("0.33")),
    (None,              Decimal("0.35")),
]


def calculate_irg(taxable: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """
    Steps 5-6: Calculate IRG with 40% abatement.

    Returns: (irg_brut, abatement, irg_final)
    """
    taxable = Decimal(str(taxable))

    # Special rule: total exemption if taxable <= 30,000
    if taxable <= Decimal("30000"):
        return Decimal("0"), Decimal("0"), Decimal("0")

    # Step 5: Progressive brackets
    irg = Decimal("0")
    prev_limit = Decimal("0")

    for limit, rate in IRG_BRACKETS:
        if limit is None:
            irg += (taxable - prev_limit) * rate
            break
        if taxable <= limit:
            irg += (taxable - prev_limit) * rate
            break
        else:
            irg += (limit - prev_limit) * rate
            prev_limit = limit

    irg_brut = _r2(irg)

    # Step 6: 40% abatement with floor 1000 / ceiling 1500
    abatement = _r2(irg_brut * Decimal("0.40"))
    if abatement < Decimal("1000"):
        abatement = Decimal("1000")
    if abatement > Decimal("1500"):
        abatement = Decimal("1500")

    irg_final = irg_brut - abatement
    if irg_final < 0:
        irg_final = Decimal("0")

    return irg_brut, abatement, _r2(irg_final)


def calculate_payslip(
    session: Session,
    *,
    employee_id: UUID,
    company_id: UUID,
    period_month: int,
    period_year: int,
    salary_base: Decimal | None = None,
    overtime_hours: Decimal = Decimal("0"),
    prime_rendement: Decimal = Decimal("0"),
    prime_nuisance: Decimal = Decimal("0"),
    prime_panier: Decimal = Decimal("0"),
    indemnite_transport: Decimal = Decimal("0"),
    prime_iep: Decimal = Decimal("0"),
    prime_chantier: Decimal = Decimal("0"),
    advance_repayment: Decimal = Decimal("0"),
    loan_installment: Decimal = Decimal("0"),
    other_deductions: Decimal = Decimal("0"),
    spi_score: Decimal | None = None,
    created_by: UUID | None = None,
) -> object:
    """Execute the full 10-step payroll calculation."""
    from app.models.payroll import Payslip
    from app.models.company import Company

    # ── Step 1: CNAS regime ──────────────────────────────────────────────
    company = session.get(Company, company_id)
    if company is None:
        raise ValueError(f"Company {company_id} not found.")

    regime = company.cnas_regime or "GENERAL"
    if regime == "BTPH":
        emp_rate = Decimal("9.375")   # includes CACOBATPH 0.375%
        pat_rate = Decimal("25.375")  # includes CACOBATPH 0.375%
    else:
        emp_rate = Decimal("9")
        pat_rate = Decimal("25")

    # Get salary from contract if not provided
    if salary_base is None:
        from app.models.hr import EmployeeContract
        contract = (
            session.query(EmployeeContract)
            .filter(
                EmployeeContract.employee_id == employee_id,
                EmployeeContract.status == "ACTIVE",
                EmployeeContract.is_deleted.is_(False),
            )
            .first()
        )
        if contract:
            salary_base = Decimal(str(contract.salary_base))
        else:
            raise ValueError("No active contract found and no salary_base provided.")

    salary_base = Decimal(str(salary_base))

    # ── Step 2: Gross ────────────────────────────────────────────────────
    # Overtime: hours * (base / 173.33) * 1.50, capped at 8h/week
    ot_hours = min(Decimal(str(overtime_hours)), Decimal("32"))  # 8h * 4 weeks
    hourly = salary_base / Decimal("173.33")
    ot_amount = _r2(ot_hours * hourly * Decimal("1.50"))

    gross = _r2(
        salary_base
        + Decimal(str(prime_rendement))
        + Decimal(str(prime_nuisance))
        + Decimal(str(prime_panier))
        + Decimal(str(indemnite_transport))
        + Decimal(str(prime_iep))
        + Decimal(str(prime_chantier))
        + ot_amount
    )

    # ── Step 3: CNAS employee ────────────────────────────────────────────
    cnas_emp = _floor(gross * emp_rate / Decimal("100"))

    # ── Step 4: Taxable ──────────────────────────────────────────────────
    taxable = gross - cnas_emp

    # ── Steps 5-6: IRG ───────────────────────────────────────────────────
    irg_brut, abatement, irg_final = calculate_irg(taxable)

    # ── Step 7: Deductions ───────────────────────────────────────────────
    adv = Decimal(str(advance_repayment))
    loan = Decimal(str(loan_installment))
    other = Decimal(str(other_deductions))
    total_ded = adv + loan + other

    # ── Step 8: Net ──────────────────────────────────────────────────────
    net = _r2(gross - cnas_emp - irg_final - total_ded)

    # ── Step 9: Employer charges ─────────────────────────────────────────
    cnas_pat = _r2(gross * pat_rate / Decimal("100"))
    formation = _r2(gross * Decimal("0.01"))
    apprentissage = _r2(gross * Decimal("0.01"))
    total_employer = _r2(gross + cnas_pat + formation + apprentissage)

    # ── Step 10: Create record ───────────────────────────────────────────
    payslip = Payslip(
        company_id=company_id,
        employee_id=employee_id,
        period_month=period_month,
        period_year=period_year,
        cnas_regime=regime,
        cnas_employee_rate=emp_rate,
        cnas_employer_rate=pat_rate,
        salary_base=salary_base,
        prime_rendement=Decimal(str(prime_rendement)),
        prime_nuisance=Decimal(str(prime_nuisance)),
        prime_panier=Decimal(str(prime_panier)),
        indemnite_transport=Decimal(str(indemnite_transport)),
        prime_iep=Decimal(str(prime_iep)),
        prime_chantier=Decimal(str(prime_chantier)),
        overtime_hours=ot_hours,
        overtime_amount=ot_amount,
        gross_salary=gross,
        cnas_employee_amount=cnas_emp,
        taxable_income=taxable,
        irg_brut=irg_brut,
        irg_abatement=abatement,
        irg_final=irg_final,
        advance_repayment=adv,
        loan_installment=loan,
        other_deductions=other,
        total_deductions=total_ded,
        net_salary=net,
        cnas_employer_amount=cnas_pat,
        formation_contribution=formation,
        apprentissage_contribution=apprentissage,
        total_employer_cost=total_employer,
        status="CALCULATED",
        spi_score=spi_score,
        created_by=created_by,
    )
    session.add(payslip)
    session.flush()
    return payslip


def run_monthly_payroll(
    session: Session,
    *,
    company_id: UUID,
    period_month: int,
    period_year: int,
    created_by: UUID | None = None,
) -> list:
    """Run payroll for all active employees in an entity."""
    from app.models.hr import Employee, EmployeeContract

    employees = (
        session.query(Employee)
        .filter(
            Employee.company_id == company_id,
            Employee.status == "ACTIVE",
            Employee.is_deleted.is_(False),
        )
        .all()
    )

    payslips = []
    for emp in employees:
        contract = (
            session.query(EmployeeContract)
            .filter(
                EmployeeContract.employee_id == emp.id,
                EmployeeContract.status == "ACTIVE",
                EmployeeContract.is_deleted.is_(False),
            )
            .first()
        )
        if contract:
            ps = calculate_payslip(
                session,
                employee_id=emp.id,
                company_id=company_id,
                period_month=period_month,
                period_year=period_year,
                salary_base=Decimal(str(contract.salary_base)),
                created_by=created_by,
            )
            payslips.append(ps)

    return payslips
