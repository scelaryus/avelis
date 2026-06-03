"""
GFI v7.0 — GACEB Subcontractor Engine.

Manages the 120M in-kind advance, work situation deductions,
vehicle 5-step circuit, and RAP (Reste A Payer) calculation.

TD-04: "Combien GACEB doit encore sur les 120M?" -> exact residual
TD-10: "120M sorti de la caisse?" -> "Non, avance en nature, zero cash."

Core API:
  record_work_situation(...)   -> WorkSituation + advance deduction
  get_advance_residual(...)    -> Decimal (TD-04)
  register_vehicle_step(...)   -> Vehicle (5-step circuit)
  calculate_rap(...)           -> RAP dict with full decomposition
  get_gaceb_summary(...)       -> dashboard summary
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func as sqfunc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_advance_residual(
    session: Session,
    project_id: UUID,
    advance_type: str = "MATERIEL_120M",
) -> Decimal:
    """TD-04: exact residual of the 120M advance."""
    from app.models.gaceb import GacebAdvance

    advance = (
        session.query(GacebAdvance)
        .filter(
            GacebAdvance.project_id == project_id,
            GacebAdvance.advance_type == advance_type,
            GacebAdvance.is_deleted.is_(False),
        )
        .first()
    )
    return Decimal(str(advance.solde_restant)) if advance else Decimal("0")


def record_work_situation(
    session: Session,
    *,
    project_id: UUID,
    company_id: UUID,
    situation_number: int,
    situation_date: date,
    montant_brut: Decimal,
    deduction_avance: Decimal = Decimal("0"),
    deduction_vehicules: Decimal = Decimal("0"),
    deduction_appartements: Decimal = Decimal("0"),
    retention_garantie_5pct: Decimal | None = None,
    contract_ref: str | None = None,
    completion_pct: Decimal | None = None,
    document_url: str | None = None,
    created_by: UUID | None = None,
) -> object:
    """
    Record a GACEB work situation with deductions.
    Updates advance residual. CC2 gets gross, CC8 gets deductions.

    Always shows: Brut | Deduction | Net Cash | Solde Avance.
    """
    from app.models.gaceb import WorkSituation, GacebAdvance

    montant_brut = Decimal(str(montant_brut))
    ded_avance = Decimal(str(deduction_avance))
    ded_vehicules = Decimal(str(deduction_vehicules))
    ded_appts = Decimal(str(deduction_appartements))

    if retention_garantie_5pct is None:
        retention_garantie_5pct = _r2(montant_brut * Decimal("0.05"))
    else:
        retention_garantie_5pct = Decimal(str(retention_garantie_5pct))

    total_deductions = ded_avance + ded_vehicules + ded_appts + retention_garantie_5pct
    net_cash = montant_brut - total_deductions

    # Update advance residual
    solde_after = None
    if ded_avance > 0:
        advance = (
            session.query(GacebAdvance)
            .filter(
                GacebAdvance.project_id == project_id,
                GacebAdvance.advance_type == "MATERIEL_120M",
                GacebAdvance.is_deleted.is_(False),
            )
            .first()
        )
        if advance:
            current = Decimal(str(advance.solde_restant))
            if ded_avance > current:
                raise ValueError(
                    f"Deduction avance {ded_avance} DA > solde restant {current} DA."
                )
            advance.montant_deduit = _r2(
                Decimal(str(advance.montant_deduit)) + ded_avance
            )
            advance.solde_restant = _r2(current - ded_avance)
            solde_after = advance.solde_restant

    sit = WorkSituation(
        company_id=company_id,
        project_id=project_id,
        situation_number=situation_number,
        situation_date=situation_date,
        montant_brut=montant_brut,
        deduction_avance=ded_avance,
        deduction_vehicules=ded_vehicules,
        deduction_appartements=ded_appts,
        retention_garantie_5pct=retention_garantie_5pct,
        net_cash_verse=_r2(net_cash),
        solde_avance_apres=solde_after,
        contract_ref=contract_ref,
        completion_pct=completion_pct,
        status="SOUMISE",
        document_url=document_url,
        created_by=created_by,
    )
    session.add(sit)
    session.flush()
    return sit


def register_vehicle_step(
    session: Session,
    *,
    vehicle_id: UUID,
    step: str,
    **kwargs,
) -> object:
    """
    Progress a vehicle through the 5-step circuit.
    Steps: ACHETE -> IMMATRICULE -> CEDE -> DEDUIT -> REVENDU
    """
    from app.models.gaceb import Vehicle

    vehicle = session.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise ValueError(f"Vehicle {vehicle_id} not found.")

    now = datetime.now(timezone.utc)
    history_entry = {"step": step, "date": str(now), **kwargs}

    if vehicle.history is None:
        vehicle.history = []
    vehicle.history = vehicle.history + [history_entry]

    valid_transitions = {
        "ACHETE": "IMMATRICULE",
        "IMMATRICULE": "CEDE",
        "CEDE": "DEDUIT",
        "DEDUIT": "REVENDU",
    }

    expected = valid_transitions.get(vehicle.current_step)
    if expected and step != expected:
        raise ValueError(
            f"Vehicle at step {vehicle.current_step}, "
            f"expected next: {expected}, got: {step}"
        )

    vehicle.current_step = step

    if step == "IMMATRICULE":
        vehicle.registration_date = kwargs.get("registration_date", now.date())
        vehicle.plate_number = kwargs.get("plate_number")
        if kwargs.get("associate_id"):
            vehicle.registered_to_associate_id = kwargs["associate_id"]

    elif step == "CEDE":
        vehicle.cession_date = kwargs.get("cession_date", now.date())
        vehicle.cession_value = kwargs.get("cession_value")

    elif step == "DEDUIT":
        vehicle.deduction_date = kwargs.get("deduction_date", now.date())
        vehicle.deduction_amount = kwargs.get("deduction_amount")
        if kwargs.get("situation_id"):
            vehicle.deduction_situation_id = kwargs["situation_id"]

    elif step == "REVENDU":
        vehicle.resale_date = kwargs.get("resale_date", now.date())
        vehicle.resale_buyer = kwargs.get("buyer")
        vehicle.resale_price = kwargs.get("resale_price")

    session.flush()
    return vehicle


def calculate_rap(
    session: Session,
    project_id: UUID,
) -> dict:
    """
    RAP (Reste A Payer) for GACEB on a project.

    RAP = (contract * completion%) - advance_residual - vehicles_ceded
          - apartments_ceded - 5%_retention + recovered_advance - cash_paid
    """
    from app.models.gaceb import WorkSituation, GacebAdvance, Vehicle

    # Total gross from situations
    total_brut = Decimal(str(
        session.query(sqfunc.coalesce(sqfunc.sum(WorkSituation.montant_brut), 0))
        .filter(
            WorkSituation.project_id == project_id,
            WorkSituation.status.in_(["VALIDEE", "PAYEE"]),
            WorkSituation.is_deleted.is_(False),
        )
        .scalar()
    ))

    # Total cash already paid
    total_cash_paid = Decimal(str(
        session.query(sqfunc.coalesce(sqfunc.sum(WorkSituation.net_cash_verse), 0))
        .filter(
            WorkSituation.project_id == project_id,
            WorkSituation.status == "PAYEE",
            WorkSituation.is_deleted.is_(False),
        )
        .scalar()
    ))

    # Advance residual (120M type)
    advance_residual = get_advance_residual(session, project_id, "MATERIEL_120M")

    # Total advance deducted so far
    total_advance_deducted = Decimal(str(
        session.query(sqfunc.coalesce(sqfunc.sum(WorkSituation.deduction_avance), 0))
        .filter(
            WorkSituation.project_id == project_id,
            WorkSituation.is_deleted.is_(False),
        )
        .scalar()
    ))

    # Vehicles ceded to GACEB for this project
    vehicles_ceded = Decimal(str(
        session.query(sqfunc.coalesce(sqfunc.sum(Vehicle.cession_value), 0))
        .filter(
            Vehicle.purchase_project_id == project_id,
            Vehicle.current_step.in_(["CEDE", "DEDUIT", "REVENDU"]),
            Vehicle.is_deleted.is_(False),
        )
        .scalar()
    ))

    # Apartments ceded (from advance tracking)
    apartments_ceded = Decimal(str(
        session.query(sqfunc.coalesce(sqfunc.sum(GacebAdvance.montant_initial), 0))
        .filter(
            GacebAdvance.project_id == project_id,
            GacebAdvance.advance_type == "APARTMENT",
            GacebAdvance.is_deleted.is_(False),
        )
        .scalar()
    ))

    # 5% guarantee retention
    retention_5pct = Decimal(str(
        session.query(sqfunc.coalesce(sqfunc.sum(WorkSituation.retention_garantie_5pct), 0))
        .filter(
            WorkSituation.project_id == project_id,
            WorkSituation.is_deleted.is_(False),
        )
        .scalar()
    ))

    # RAP = gross_validated - all_deductions - cash_paid
    total_deductions = total_advance_deducted + vehicles_ceded + apartments_ceded + retention_5pct
    rap = total_brut - total_deductions - total_cash_paid

    return {
        "project_id": str(project_id),
        "total_brut_valide": str(total_brut),
        "advance_120m_residual": str(advance_residual),
        "total_advance_deducted": str(total_advance_deducted),
        "vehicles_ceded": str(vehicles_ceded),
        "apartments_ceded": str(apartments_ceded),
        "retention_5pct": str(retention_5pct),
        "total_deductions": str(total_deductions),
        "total_cash_paid": str(total_cash_paid),
        "rap": str(_r2(rap)),
        "td04_answer": f"Solde avance 120M: {advance_residual} DA",
        "td10_answer": "Non — avance en nature, aucun cash sorti de la caisse.",
    }


def get_gaceb_summary(
    session: Session,
    project_id: UUID,
) -> dict:
    """Dashboard summary for GACEB on a project."""
    from app.models.gaceb import WorkSituation

    situations = (
        session.query(WorkSituation)
        .filter(
            WorkSituation.project_id == project_id,
            WorkSituation.is_deleted.is_(False),
        )
        .order_by(WorkSituation.situation_number)
        .all()
    )

    rows = []
    for s in situations:
        rows.append({
            "numero": s.situation_number,
            "date": str(s.situation_date),
            "montant_brut": str(s.montant_brut),
            "deduction_avance": str(s.deduction_avance),
            "deduction_vehicules": str(s.deduction_vehicules),
            "net_cash_verse": str(s.net_cash_verse),
            "solde_avance_apres": str(s.solde_avance_apres) if s.solde_avance_apres else None,
            "status": s.status,
        })

    rap = calculate_rap(session, project_id)

    return {
        "situations": rows,
        "rap": rap,
        "situation_count": len(rows),
    }
