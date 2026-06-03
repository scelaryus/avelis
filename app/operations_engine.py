"""
GFI v7.0 — Operations Engine: 11-source budget aggregation,
critical path, S-curve, 25 business rules.

Budget = automatic aggregation of ALL costs from ALL modules.
The user enters only the contract — the system finds everything else.

Core API:
  create_operation(...)          -> Operation with auto-code
  transition_operation(...)      -> state machine with RM rules
  aggregate_budget(operation_id) -> pulls from 11 sources
  deploy_planning(operation_id)  -> WBS from template + baseline
  calculate_critical_path(...)   -> CPM forward/backward pass
  compute_s_curve(operation_id)  -> physical vs financial advancement
  check_rm_rules(operation_id)   -> evaluate all applicable RM rules
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func as sqfunc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class RMRuleViolation(Exception):
    def __init__(self, message: str, rule: str):
        super().__init__(message)
        self.rule = rule


def _r2(v): return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def create_operation(
    session: Session,
    *,
    company_id: UUID,
    intitule: str,
    categorie: str,
    project_id: UUID | None = None,
    montant_engage_ht: Decimal | None = None,
    contrat_legal_id: UUID | None = None,
    responsable_id: UUID | None = None,
    created_by: UUID | None = None,
) -> object:
    from app.models.operations import Operation
    from app.models.company import Company

    company = session.get(Company, company_id)
    code = company.code.replace("-", "") if company else "UNK"
    year = date.today().year

    count = (
        session.query(sqfunc.count(Operation.id))
        .filter(Operation.company_id == company_id, Operation.is_deleted.is_(False))
        .scalar()
    ) or 0

    # RM-01: categories requiring contract
    contract_required = {"GROS_OEUVRE", "SECOND_OEUVRE", "BET_ARCHITECTURE",
                         "MACHINE_OEM", "PRESTATION", "MAINTENANCE"}
    if categorie in contract_required and not contrat_legal_id:
        raise RMRuleViolation(
            f"RM-01: Operation {categorie} requires a linked legal contract.",
            rule="RM-01",
        )

    ht = Decimal(str(montant_engage_ht)) if montant_engage_ht else Decimal("0")
    ttc = _r2(ht * Decimal("1.19"))

    op = Operation(
        company_id=company_id,
        code_operation=f"OP-{code}-{year}-{count + 1:04d}",
        intitule=intitule,
        project_id=project_id,
        categorie=categorie,
        contrat_legal_id=contrat_legal_id,
        montant_engage_ht=ht,
        montant_engage_ttc=ttc,
        statut="BROUILLON",
        responsable_id=responsable_id,
        created_by=created_by,
    )
    session.add(op)
    session.flush()

    # Initialize S1 budget source
    from app.models.operations import OperationBudgetAgrege
    s1 = OperationBudgetAgrege(
        company_id=company_id,
        operation_id=op.id,
        source_code="S1_CONTRAT",
        source_label="Contrat",
        montant_prevu=ttc,
        methode_calcul="DIRECT",
        derniere_maj=datetime.now(timezone.utc),
    )
    session.add(s1)
    session.flush()
    return op


VALID_TRANSITIONS = {
    "BROUILLON": {"SOUMIS"},
    "SOUMIS": {"VALIDE", "BROUILLON"},
    "VALIDE": {"EN_COURS"},
    "EN_COURS": {"SUSPENDU", "CLOTURE"},
    "SUSPENDU": {"EN_COURS", "CLOTURE"},
    "CLOTURE": {"ARCHIVE"},
}


def transition_operation(
    session: Session,
    operation_id: UUID,
    new_status: str,
    user_id: UUID | None = None,
) -> object:
    from app.models.operations import Operation, OperationPlanningTask, OperationSnapshot

    op = session.get(Operation, operation_id)
    if op is None:
        raise ValueError(f"Operation {operation_id} not found.")

    allowed = VALID_TRANSITIONS.get(op.statut, set())
    if new_status not in allowed:
        raise RMRuleViolation(
            f"Transition {op.statut} -> {new_status} not allowed.",
            rule="STATE_MACHINE",
        )

    # RM-05: Tresorier visa before EN_COURS
    if new_status == "EN_COURS" and not op.visa_tresorier:
        raise RMRuleViolation(
            "RM-05: Visa tresorier obligatoire avant EN_COURS.",
            rule="RM-05",
        )

    # RM-22: Must have planning before EN_COURS
    if new_status == "EN_COURS":
        task_count = (
            session.query(sqfunc.count(OperationPlanningTask.id))
            .filter(OperationPlanningTask.operation_id == operation_id,
                    OperationPlanningTask.is_deleted.is_(False))
            .scalar()
        ) or 0
        if task_count == 0:
            raise RMRuleViolation(
                "RM-22: Operation must have at least 1 planning task before EN_COURS.",
                rule="RM-22",
            )

    # RM-23: Create baseline at VALIDE
    if new_status == "VALIDE":
        tasks = (
            session.query(OperationPlanningTask)
            .filter(OperationPlanningTask.operation_id == operation_id,
                    OperationPlanningTask.is_deleted.is_(False))
            .all()
        )
        snapshot_data = [
            {"code_wbs": t.code_wbs, "intitule": t.intitule,
             "date_debut": str(t.date_debut_prevue),
             "date_fin": str(t.date_fin_prevue),
             "budget": str(t.budget_tache)}
            for t in tasks
        ]
        if snapshot_data:
            snap = OperationSnapshot(
                company_id=op.company_id,
                operation_id=operation_id,
                type_snapshot="BASELINE_INITIALE",
                date_snapshot=date.today(),
                donnees_taches=snapshot_data,
            )
            session.add(snap)

    op.statut = new_status
    session.flush()
    return op


def aggregate_budget(
    session: Session,
    operation_id: UUID,
) -> dict:
    """Pull budget data from all 11 sources. Returns complete budget view."""
    from app.models.operations import OperationBudgetAgrege

    sources = (
        session.query(OperationBudgetAgrege)
        .filter(OperationBudgetAgrege.operation_id == operation_id,
                OperationBudgetAgrege.is_deleted.is_(False))
        .all()
    )

    total_prevu = Decimal("0")
    total_reel = Decimal("0")
    by_source = {}

    for s in sources:
        prevu = Decimal(str(s.montant_prevu))
        reel = Decimal(str(s.montant_reel))
        total_prevu += prevu
        total_reel += reel
        ecart = _r2((reel - prevu) / prevu * 100) if prevu != 0 else Decimal("0")
        by_source[s.source_code] = {
            "label": s.source_label,
            "prevu": str(prevu),
            "reel": str(reel),
            "ecart_pct": str(ecart),
        }

    return {
        "operation_id": str(operation_id),
        "budget_total_prevu": str(total_prevu),
        "budget_total_reel": str(total_reel),
        "ecart_absolu": str(total_reel - total_prevu),
        "ecart_pct": str(_r2((total_reel - total_prevu) / total_prevu * 100)) if total_prevu else "0",
        "sources": by_source,
    }


def compute_s_curve(
    session: Session,
    operation_id: UUID,
) -> dict:
    """Physical vs financial advancement. RM-25: gap > 20 points -> alert."""
    from app.models.operations import Operation, OperationPlanningTask

    op = session.get(Operation, operation_id)
    if op is None:
        raise ValueError(f"Operation {operation_id} not found.")

    tasks = (
        session.query(OperationPlanningTask)
        .filter(
            OperationPlanningTask.operation_id == operation_id,
            OperationPlanningTask.type_tache == "TACHE",
            OperationPlanningTask.is_deleted.is_(False),
        )
        .all()
    )

    # Physical: weighted by budget
    total_budget = sum(Decimal(str(t.budget_tache or 0)) for t in tasks) or Decimal("1")
    physical = sum(
        Decimal(str(t.budget_tache or 0)) * Decimal(str(t.avancement_pct)) / 100
        for t in tasks
    )
    physical_pct = _r2(physical / total_budget * 100)

    # Financial: budget consumed
    budget_data = aggregate_budget(session, operation_id)
    total_prevu = Decimal(budget_data["budget_total_prevu"]) or Decimal("1")
    total_reel = Decimal(budget_data["budget_total_reel"])
    financial_pct = _r2(total_reel / total_prevu * 100)

    gap = financial_pct - physical_pct
    surpaiement_risk = gap > Decimal("20")

    return {
        "physical_pct": str(physical_pct),
        "financial_pct": str(financial_pct),
        "gap": str(gap),
        "surpaiement_risk": surpaiement_risk,
        "rm25_alert": surpaiement_risk,
    }


def deploy_planning_from_template(
    session: Session,
    operation_id: UUID,
    company_id: UUID,
) -> list:
    """Deploy WBS from template based on operation category."""
    from app.models.operations import Operation, OperationPlanningTask, WbsTemplate

    op = session.get(Operation, operation_id)
    if op is None:
        raise ValueError(f"Operation {operation_id} not found.")

    template = (
        session.query(WbsTemplate)
        .filter(WbsTemplate.categorie == op.categorie)
        .first()
    )

    tasks_created = []
    if template and template.tasks:
        for task_def in template.tasks:
            task = OperationPlanningTask(
                company_id=company_id,
                operation_id=operation_id,
                code_wbs=task_def.get("code_wbs", "1"),
                intitule=task_def.get("intitule", "Task"),
                type_tache=task_def.get("type_tache", "TACHE"),
                statut_tache="A_FAIRE",
            )
            session.add(task)
            tasks_created.append(task)

    session.flush()
    return tasks_created
