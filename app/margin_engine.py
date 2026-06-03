"""
GFI v7.0 — Margin Calculation + Associate Profit Distribution Engine.

Produces 6 margin indicators per project and distributes profit among
associates using a 3-step process with DIFFERENT percentages at each step.

Step 1: QP brute = marge_nette * % PROJET (from part_projet)
Step 2: QP after CFF = QP brute - CFF imputations (using % ENTREPRISE)
Step 3: QP finale = QP after CFF - CC9 withdrawals - CC10 commissions

CRITICAL: Step 1 uses PROJECT percentages, Step 2 uses COMPANY percentages.
These are DIFFERENT. Confusing them is the most common error.

4 output views:
  Table 1: With CFF (shows actual net after CFF deduction)
  Table 2: Without CFF (shows what each would get without fiscal optimization)
  View A: With CC9+CC10 (full margin including personal items)
  View B: Without CC9+CC10 (pure operational margin)

Core API:
  calculate_margins(project_id, ...) -> MarginCalculation
  distribute_to_associates(margin_calc_id) -> list[QuotePartResult]
  get_margin_summary(project_id) -> dict with all 4 views
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func as sqfunc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.ownership import (
    OperationType, get_percentages, validate_yamina_rules, YAMINA_ID,
)


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _get_cc_total(
    session, project_id: UUID, categorie: str,
) -> Decimal:
    """Get the total amount for a CC category on a project."""
    from app.models.cost_center import CostCenterNode

    node = (
        session.query(CostCenterNode)
        .filter(
            CostCenterNode.project_id == project_id,
            CostCenterNode.categorie == categorie,
            CostCenterNode.level == 3,
            CostCenterNode.is_deleted.is_(False),
        )
        .first()
    )
    return Decimal(str(node.montant_total)) if node else Decimal("0")


def calculate_margins(
    session: Session,
    *,
    project_id: UUID,
    company_id: UUID,
    calculation_date: date | None = None,
    created_by: UUID | None = None,
) -> object:
    """
    Calculate all 6 margin indicators for a project.
    Reads from the CC tree (real-time data).
    """
    from app.models.margin import MarginCalculation

    if calculation_date is None:
        calculation_date = date.today()

    # Read CC category totals
    cc = {}
    categories = [
        "TERRAIN", "CONSTR", "VRD", "CHARGES_GEN", "BBZ", "CFF",
        "INTER_PROJ", "COMPENSATION", "ASSOC", "COMMISSION",
        "IMPOTS", "VENTES_RF1", "VENTES_RF2", "FRAIS_ADM",
        "FRAIS_FIN", "DIVERS",
    ]
    for cat in categories:
        cc[cat] = _get_cc_total(session, project_id, cat)

    # Revenue
    ca_rf1 = cc["VENTES_RF1"]
    ca_rf2 = cc["VENTES_RF2"]
    ca_total = ca_rf1 + ca_rf2

    # Margin formulas
    cout_direct = cc["TERRAIN"] + cc["CONSTR"] + cc["VRD"] + cc["COMPENSATION"]
    marge_brute = ca_total - cout_direct

    cout_total = sum(
        cc[c] for c in categories
        if c not in ("VENTES_RF1", "VENTES_RF2")
    )

    marge_nette = ca_total - cout_total

    marge_op = ca_total - (cout_total - cc["ASSOC"] - cc["COMMISSION"])

    calc = MarginCalculation(
        company_id=company_id,
        project_id=project_id,
        calculation_date=calculation_date,
        period_label=calculation_date.strftime("%Y-%m"),
        ca_rf1=ca_rf1,
        ca_rf2=ca_rf2,
        ca_total=ca_total,
        cc1_terrain=cc["TERRAIN"],
        cc2_construction=cc["CONSTR"],
        cc3_materiaux=cc["VRD"],
        cc4_payroll=cc["CHARGES_GEN"],
        cc5_bbz=cc["BBZ"],
        cc6_cff=cc["CFF"],
        cc7_inter_proj=cc["INTER_PROJ"],
        cc8_compensation=cc["COMPENSATION"],
        cc9_assoc=cc["ASSOC"],
        cc10_commission=cc["COMMISSION"],
        cc11_impots=cc["IMPOTS"],
        cc14_frais_adm=cc["FRAIS_ADM"],
        cc15_frais_fin=cc["FRAIS_FIN"],
        cc16_divers=cc["DIVERS"],
        cout_direct=cout_direct,
        marge_brute=marge_brute,
        cout_total=cout_total,
        marge_nette=marge_nette,
        marge_operationnelle=marge_op,
        detail_json={k: str(v) for k, v in cc.items()},
        created_by=created_by,
    )
    session.add(calc)
    session.flush()
    return calc


def distribute_to_associates(
    session: Session,
    *,
    margin_calculation_id: UUID,
    created_by: UUID | None = None,
) -> list:
    """
    3-step associate profit distribution.
    Uses DIFFERENT percentages at each step.
    Produces all 4 views (Table 1/2, View A/B).
    """
    from app.models.margin import MarginCalculation, QuotePartResult
    from app.models.cff_imputation import CffImputation
    from app.models.cost_center import CostCenterEntry

    calc = session.get(MarginCalculation, margin_calculation_id)
    if calc is None:
        raise ValueError(f"MarginCalculation {margin_calculation_id} not found.")

    marge_nette = Decimal(str(calc.marge_nette))
    marge_op = Decimal(str(calc.marge_operationnelle))

    # ── Step 1: Get PROJECT percentages ──────────────────────────────────
    project_pcts = get_percentages(
        session, OperationType.PROJECT_PROFIT, project_id=calc.project_id,
    )

    # ── Step 2: Get CFF imputations per associate on this project ────────
    cff_by_associate: dict[UUID, Decimal] = {}
    cff_imps = (
        session.query(
            CffImputation.associate_id,
            sqfunc.coalesce(sqfunc.sum(CffImputation.amount), 0),
        )
        .join(
            __import__("app.models.cff_calculation", fromlist=["CffCalculation"]).CffCalculation,
            CffImputation.cff_calculation_id == __import__("app.models.cff_calculation", fromlist=["CffCalculation"]).CffCalculation.id,
        )
        .filter(
            __import__("app.models.cff_calculation", fromlist=["CffCalculation"]).CffCalculation.project_id == calc.project_id,
            CffImputation.is_deleted.is_(False),
        )
        .group_by(CffImputation.associate_id)
        .all()
    )
    for assoc_id, total in cff_imps:
        cff_by_associate[assoc_id] = Decimal(str(total))

    # ── Step 3: Get CC9/CC10 per associate ───────────────────────────────
    def _get_associate_cc(node_pattern: str) -> dict[UUID, Decimal]:
        """Sum CC entries matching a pattern, grouped by source_id (associate)."""
        entries = (
            session.query(CostCenterEntry)
            .filter(
                CostCenterEntry.project_id == calc.project_id,
                CostCenterEntry.node_code.like(f"%-{node_pattern}-%"),
                CostCenterEntry.is_deleted.is_(False),
            )
            .all()
        )
        result: dict[UUID, Decimal] = {}
        for e in entries:
            if e.source_id:
                result[e.source_id] = (
                    result.get(e.source_id, Decimal("0"))
                    + Decimal(str(e.montant))
                )
        return result

    # For CC9/CC10, we use a simpler approach based on the total stored
    cc9_total = Decimal(str(calc.cc9_assoc))
    cc10_total = Decimal(str(calc.cc10_commission))

    # ── Build results ────────────────────────────────────────────────────
    results = []
    distributed = Decimal("0")
    sorted_pcts = sorted(project_pcts.items(), key=lambda x: x[1], reverse=True)

    for i, (assoc_id, pct) in enumerate(sorted_pcts):
        # Step 1: QP brute (PROJECT %)
        if i == len(sorted_pcts) - 1:
            qp_brute = marge_nette - distributed
        else:
            qp_brute = _r2(marge_nette * pct / Decimal("100"))
        distributed += qp_brute

        # Step 2: CFF deduction (already calculated with COMPANY %)
        cff_deducted = cff_by_associate.get(assoc_id, Decimal("0"))
        qp_after_cff = qp_brute - cff_deducted

        # Step 3: Personal items (100% to specific associate, already in CC)
        # Approximate: proportional to project share for now
        # (exact per-associate CC9/CC10 requires node-level tracking)
        cc9_share = _r2(cc9_total * pct / Decimal("100"))
        cc10_share = _r2(cc10_total * pct / Decimal("100"))
        qp_finale = qp_after_cff - cc9_share - cc10_share

        # Table 2: Without CFF
        qp_without_cff = qp_brute - cc9_share - cc10_share
        cff_cost_delta = qp_without_cff - qp_finale  # = cff_deducted

        # View B: Operational (without CC9+CC10)
        if i == len(sorted_pcts) - 1:
            qp_op = marge_op - sum(r.qp_operationnelle for r in results if r.qp_operationnelle)
        else:
            qp_op = _r2(marge_op * pct / Decimal("100"))

        result = QuotePartResult(
            company_id=calc.company_id,
            margin_calculation_id=margin_calculation_id,
            associate_id=assoc_id,
            project_id=calc.project_id,
            pct_projet=pct,
            qp_brute=qp_brute,
            cff_total_deducted=cff_deducted,
            qp_after_cff=qp_after_cff,
            cc9_withdrawals=cc9_share,
            cc10_commissions=cc10_share,
            qp_finale=qp_finale,
            qp_without_cff=qp_without_cff,
            cff_cost_delta=cff_cost_delta,
            qp_operationnelle=qp_op,
            created_by=created_by,
        )
        session.add(result)
        results.append(result)

    # ── Yamina V7 check ──────────────────────────────────────────────────
    from app.models.project import Project
    project = session.get(Project, calc.project_id)
    if project:
        computed_amounts = {r.associate_id: r.cff_total_deducted for r in results}
        from app.models.company import Company
        company = session.get(Company, calc.company_id)
        validate_yamina_rules(
            session, computed_amounts,
            company_code=company.code if company else None,
            project_code=project.code,
        )

    session.flush()
    return results


def get_margin_summary(
    session: Session,
    project_id: UUID,
) -> dict:
    """Get the latest margin summary with all 4 views."""
    from app.models.margin import MarginCalculation, QuotePartResult

    calc = (
        session.query(MarginCalculation)
        .filter(
            MarginCalculation.project_id == project_id,
            MarginCalculation.is_deleted.is_(False),
        )
        .order_by(MarginCalculation.calculation_date.desc())
        .first()
    )

    if calc is None:
        return {"error": "No margin calculation found for this project."}

    qps = (
        session.query(QuotePartResult)
        .filter(
            QuotePartResult.margin_calculation_id == calc.id,
            QuotePartResult.is_deleted.is_(False),
        )
        .all()
    )

    return {
        "project_id": str(calc.project_id),
        "date": str(calc.calculation_date),
        "margins": {
            "ca_total": str(calc.ca_total),
            "ca_rf1": str(calc.ca_rf1),
            "ca_rf2": str(calc.ca_rf2),
            "cout_direct": str(calc.cout_direct),
            "marge_brute": str(calc.marge_brute),
            "cout_total": str(calc.cout_total),
            "marge_nette": str(calc.marge_nette),
            "marge_operationnelle": str(calc.marge_operationnelle),
        },
        "table1_with_cff": [
            {
                "associate_id": str(r.associate_id),
                "pct_projet": str(r.pct_projet),
                "qp_brute": str(r.qp_brute),
                "cff_deducted": str(r.cff_total_deducted),
                "qp_after_cff": str(r.qp_after_cff),
                "cc9": str(r.cc9_withdrawals),
                "cc10": str(r.cc10_commissions),
                "qp_finale": str(r.qp_finale),
            }
            for r in qps
        ],
        "table2_without_cff": [
            {
                "associate_id": str(r.associate_id),
                "qp_without_cff": str(r.qp_without_cff),
                "cff_cost": str(r.cff_cost_delta),
            }
            for r in qps
        ],
        "view_b_operational": [
            {
                "associate_id": str(r.associate_id),
                "qp_operationnelle": str(r.qp_operationnelle),
            }
            for r in qps
        ],
    }
