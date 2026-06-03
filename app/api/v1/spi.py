"""Router — SPI (Score de Performance Integre) v3.0 + Commissions.
All data from PostgreSQL. Formulas enforced server-side."""
from decimal import Decimal
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api.v1.deps import get_current_user, CurrentUser, get_db
from app.api.v1.schemas import ApiResponse
from app.models.core import (
    SpiProfile, SpiObjective, SpiEvaluation, SpiObjectiveResult,
    HrCommission, Employee, DossierADV, Company,
)

router = APIRouter(prefix="/drh/spi", tags=["SPI"])


@router.get("")
async def spi_dashboard(period: str = None, db: Session = Depends(get_db),
                        user: CurrentUser = Depends(get_current_user)):
    """SPI Dashboard: KPIs, distribution histogram, employee table."""
    if not period:
        period = datetime.now().strftime("%Y-%m")
    # Try current period, fall back to previous if no evaluations
    evals = db.query(SpiEvaluation).filter(SpiEvaluation.period == period).all()
    if not evals:
        # Try previous month
        y, m = int(period[:4]), int(period[5:])
        m -= 1
        if m < 1: m = 12; y -= 1
        prev_period = f"{y:04d}-{m:02d}"
        evals = db.query(SpiEvaluation).filter(SpiEvaluation.period == prev_period).all()
        period = prev_period

    scores = [float(e.spi_total) for e in evals]
    avg_spi = sum(scores) / len(scores) if scores else 0
    under70 = sum(1 for s in scores if s < 70)
    top90 = sum(1 for s in scores if s >= 90)
    pending = db.query(SpiEvaluation).filter(
        SpiEvaluation.status.in_(["BROUILLON", "EVALUE"])
    ).count()

    # Distribution histogram: 0-40, 40-60, 60-80, 80-100
    histogram = [
        {"range": "0-40", "count": sum(1 for s in scores if s < 40), "color": "#FF6B6B"},
        {"range": "40-60", "count": sum(1 for s in scores if 40 <= s < 60), "color": "#E17055"},
        {"range": "60-80", "count": sum(1 for s in scores if 60 <= s < 80), "color": "#FDCB6E"},
        {"range": "80-100", "count": sum(1 for s in scores if s >= 80), "color": "#00B894"},
    ]

    # Employee table
    employees = []
    for e in evals:
        emp = db.query(Employee).filter(Employee.id == e.employee_id).first()
        if not emp: continue
        # Get previous month for trend
        y, m = int(period[:4]), int(period[5:])
        m -= 1
        if m < 1: m = 12; y -= 1
        prev = f"{y:04d}-{m:02d}"
        prev_eval = db.query(SpiEvaluation).filter(
            SpiEvaluation.employee_id == e.employee_id, SpiEvaluation.period == prev
        ).first()
        prev_spi = float(prev_eval.spi_total) if prev_eval else None
        trend = float(e.spi_total) - prev_spi if prev_spi is not None else None

        employees.append({
            "employee_id": str(emp.id), "matricule": emp.matricule,
            "name": f"{emp.last_name} {emp.first_name}", "position": emp.position,
            "entity": db.query(Company).filter(Company.id == emp.company_id).first().code if emp.company_id else "",
            "spi": str(e.spi_total), "quant": str(e.quantitative_score),
            "qual": str(e.qualitative_score),
            "prime": str(e.prime_rendement_calculated),
            "status": e.status, "trend": trend,
            "alert": "UNDERPERFORM" if float(e.spi_total) < 70 else "TOP" if float(e.spi_total) >= 90 else None,
        })

    return ApiResponse(data={
        "period": period,
        "kpis": {
            "spi_moyen": round(avg_spi, 1),
            "en_alerte": under70,
            "top_performers": top90,
            "evaluations_pending": pending,
            "total_employees": len(evals),
        },
        "histogram": histogram,
        "employees": sorted(employees, key=lambda x: -float(x["spi"])),
    })


@router.get("/{employee_id}")
async def spi_detail(employee_id: str, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(get_current_user)):
    """Employee SPI detail: 12-month history + objectives + current evaluation."""
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(404, "Employe introuvable")

    profile = db.query(SpiProfile).filter(SpiProfile.employee_id == emp.id).first()
    if not profile:
        raise HTTPException(404, "Profil SPI non configure")

    # Last 12 evaluations
    evaluations = db.query(SpiEvaluation).filter(
        SpiEvaluation.employee_id == emp.id
    ).order_by(SpiEvaluation.period.desc()).limit(12).all()

    history = []
    for ev in reversed(evaluations):
        history.append({
            "period": ev.period, "spi": str(ev.spi_total),
            "quant": str(ev.quantitative_score), "qual": str(ev.qualitative_score),
            "prime": str(ev.prime_rendement_calculated), "status": ev.status,
        })

    # Current/latest evaluation with objective breakdown
    latest = evaluations[0] if evaluations else None
    objectives_data = []
    if latest:
        results = db.query(SpiObjectiveResult).filter(
            SpiObjectiveResult.evaluation_id == latest.id
        ).all()
        for r in results:
            obj = db.query(SpiObjective).filter(SpiObjective.id == r.objective_id).first()
            if obj:
                objectives_data.append({
                    "title": obj.title, "type": obj.type,
                    "target": str(obj.target_value), "actual": str(r.actual_value),
                    "achievement_pct": str(r.achievement_pct),
                    "weight": str(obj.weight), "weighted_score": str(r.weighted_score),
                    "source": r.data_source, "unit": obj.unit,
                })

    # Underperformance check
    recent_evals = db.query(SpiEvaluation).filter(
        SpiEvaluation.employee_id == emp.id, SpiEvaluation.status == "VALIDE"
    ).order_by(SpiEvaluation.period.desc()).limit(3).all()
    consecutive_under70 = 0
    for ev in recent_evals:
        if float(ev.spi_total) < 70:
            consecutive_under70 += 1
        else:
            break
    alerts = []
    if consecutive_under70 >= 3:
        alerts.append({"level": "CRITIQUE", "message": f"SPI < 70 pendant {consecutive_under70} mois consecutifs. Declenchement procedure."})
    elif consecutive_under70 >= 2:
        alerts.append({"level": "ALERTE", "message": "SPI < 70 pendant 2 mois consecutifs. PIP obligatoire."})
    elif consecutive_under70 >= 1:
        alerts.append({"level": "ATTENTION", "message": "SPI < 70 ce mois. Suivi requis."})

    consecutive_over90 = 0
    for ev in recent_evals:
        if float(ev.spi_total) >= 90:
            consecutive_over90 += 1
        else:
            break
    if consecutive_over90 >= 3:
        alerts.append({"level": "INFO", "message": "SPI > 90 pendant 3 mois. Candidat promotion."})

    return ApiResponse(data={
        "employee": {"id": str(emp.id), "name": f"{emp.last_name} {emp.first_name}",
                     "matricule": emp.matricule, "position": emp.position,
                     "salary_base": str(emp.salary_base)},
        "profile": {"role_type": profile.role_type, "taux_prime": str(profile.taux_prime)},
        "history": history,
        "current_evaluation": {
            "period": latest.period if latest else None,
            "spi": str(latest.spi_total) if latest else "0",
            "quant": str(latest.quantitative_score) if latest else "0",
            "qual": str(latest.qualitative_score) if latest else "0",
            "prime": str(latest.prime_rendement_calculated) if latest else "0",
            "status": latest.status if latest else "AUCUN",
        } if latest else None,
        "objectives": objectives_data,
        "alerts": alerts,
    })


@router.post("/{employee_id}/evaluate")
async def submit_evaluation(employee_id: str, body: dict, db: Session = Depends(get_db),
                            user: CurrentUser = Depends(get_current_user)):
    """Manager submits qualitative evaluation scores."""
    period = body.get("period")
    scores = body.get("objective_scores", {})  # {objective_id: actual_value}
    comment = body.get("comment", "")

    if not period:
        raise HTTPException(400, "Periode requise")
    if len(comment) < 20:
        raise HTTPException(400, "Commentaire min 20 caracteres")

    profile = db.query(SpiProfile).filter(
        SpiProfile.employee_id == employee_id
    ).first()
    if not profile:
        raise HTTPException(404, "Profil SPI introuvable")

    # Get or create evaluation
    evaluation = db.query(SpiEvaluation).filter(
        SpiEvaluation.employee_id == employee_id, SpiEvaluation.period == period
    ).first()
    if not evaluation:
        emp = db.query(Employee).filter(Employee.id == employee_id).first()
        evaluation = SpiEvaluation(
            company_id=emp.company_id, spi_profile_id=profile.id,
            employee_id=emp.id, period=period, status="BROUILLON",
        )
        db.add(evaluation)
        db.flush()

    if evaluation.status == "VALIDE":
        raise HTTPException(400, "Evaluation deja validee. Contestation uniquement.")

    # Process objective scores
    quant_total = Decimal("0")
    qual_total = Decimal("0")
    objectives = db.query(SpiObjective).filter(
        SpiObjective.spi_profile_id == profile.id, SpiObjective.period == period
    ).all()

    for obj in objectives:
        obj_id = str(obj.id)
        actual = Decimal(str(scores.get(obj_id, 0)))
        achievement = min(actual / obj.target_value * 100, Decimal("150"))
        weighted = achievement * obj.weight / 100

        # Upsert result
        result = db.query(SpiObjectiveResult).filter(
            SpiObjectiveResult.objective_id == obj.id,
            SpiObjectiveResult.evaluation_id == evaluation.id,
        ).first()
        if result:
            result.actual_value = actual
            result.achievement_pct = achievement.quantize(Decimal("0.01"))
            result.weighted_score = weighted.quantize(Decimal("0.01"))
        else:
            db.add(SpiObjectiveResult(
                company_id=evaluation.company_id, objective_id=obj.id,
                evaluation_id=evaluation.id, actual_value=actual,
                achievement_pct=achievement.quantize(Decimal("0.01")),
                weighted_score=weighted.quantize(Decimal("0.01")),
                data_source="MANUEL" if obj.type == "QUALITATIF" else "AUTOMATIQUE",
            ))

        if obj.type == "QUANTITATIF":
            quant_total += weighted
        else:
            qual_total += weighted

    evaluation.quantitative_score = quant_total.quantize(Decimal("0.01"))
    evaluation.qualitative_score = qual_total.quantize(Decimal("0.01"))
    spi = (Decimal("0.60") * quant_total + Decimal("0.40") * qual_total).quantize(Decimal("0.01"))
    evaluation.spi_total = spi
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    prime = (Decimal(str(emp.salary_base)) * profile.taux_prime / 100 * spi / 100).quantize(Decimal("0.01"))
    evaluation.prime_rendement_calculated = prime
    evaluation.status = "EVALUE"
    evaluation.evaluated_by = user.email
    evaluation.evaluated_at = datetime.now(timezone.utc)
    evaluation.manager_comment = comment
    db.commit()

    return ApiResponse(data={
        "evaluation_id": str(evaluation.id), "spi_total": str(spi),
        "prime_rendement": str(prime), "status": "EVALUE",
    })


@router.post("/{employee_id}/validate")
async def validate_evaluation(employee_id: str, body: dict, db: Session = Depends(get_db),
                              user: CurrentUser = Depends(get_current_user)):
    """DRH validates evaluation."""
    period = body.get("period")
    evaluation = db.query(SpiEvaluation).filter(
        SpiEvaluation.employee_id == employee_id, SpiEvaluation.period == period
    ).first()
    if not evaluation:
        raise HTTPException(404, "Evaluation introuvable")
    if evaluation.status not in ("EVALUE", "CONTESTE"):
        raise HTTPException(400, f"Statut actuel {evaluation.status} — seules les evaluations EVALUE ou CONTESTE peuvent etre validees")
    # SPI-05: maker/checker
    if evaluation.evaluated_by == user.email:
        raise HTTPException(400, "Maker/checker: l'evaluateur ne peut pas valider sa propre evaluation")

    evaluation.status = "VALIDE"
    evaluation.validated_by = user.email
    evaluation.validated_at = datetime.now(timezone.utc)
    db.commit()

    return ApiResponse(data={"status": "VALIDE", "spi": str(evaluation.spi_total)})


@router.post("/{employee_id}/contest")
async def contest_evaluation(employee_id: str, body: dict, db: Session = Depends(get_db),
                             user: CurrentUser = Depends(get_current_user)):
    """Employee contests their evaluation within 48h."""
    period = body.get("period")
    comment = body.get("comment", "")
    if len(comment) < 20:
        raise HTTPException(400, "Commentaire de contestation min 20 caracteres")

    evaluation = db.query(SpiEvaluation).filter(
        SpiEvaluation.employee_id == employee_id, SpiEvaluation.period == period
    ).first()
    if not evaluation:
        raise HTTPException(404, "Evaluation introuvable")
    if evaluation.status != "VALIDE":
        raise HTTPException(400, "Seule une evaluation VALIDE peut etre contestee")

    # SPI-04: check 48h window
    if evaluation.validated_at:
        delta = datetime.now(timezone.utc) - evaluation.validated_at
        if delta.total_seconds() > 48 * 3600:
            raise HTTPException(400, "Delai de contestation depasse (48h)")

    evaluation.status = "CONTESTE"
    evaluation.employee_comment = comment
    db.commit()

    return ApiResponse(data={"status": "CONTESTE"})


# ── Commissions ──

@router.get("/commissions")
async def list_commissions(period: str = None, db: Session = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    q = db.query(HrCommission)
    if period:
        q = q.filter(HrCommission.period == period)
    comms = q.order_by(HrCommission.created_at.desc()).all()
    return ApiResponse(data=[{
        "employee_id": str(c.employee_id), "period": c.period,
        "payment_mode": c.payment_mode, "chiffre_encaisse": str(c.chiffre_encaisse),
        "taux_commission": str(c.taux_commission), "commission_brute": str(c.commission_brute),
        "role_in_sale": c.role_in_sale, "distribution_pct": str(c.distribution_pct),
        "commission_nette": str(c.commission_nette), "status": c.status,
    } for c in comms])
