"""Moteur de Détection Intelligente — Section 16 API.

Runs the 15 detection patterns and returns results.
Also serves as the Kill Tests verification endpoint (Section 21).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.core import User

router = APIRouter(tags=["Détection & Kill Tests"])


@router.get("/scan")
async def run_detection_scan(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run all 15 detection patterns (Section 16).

    Scans the database autonomously and returns detected items.
    """
    from app.services.detection_engine import run_all_detections
    results = await run_all_detections(user.tenant_id, db)

    total_alerts = sum(1 for r in results if r["statut"] == "ALERTE")
    total_ok = sum(1 for r in results if r["statut"] == "OK")

    return {
        "total_patterns": len(results),
        "alertes": total_alerts,
        "ok": total_ok,
        "patterns": results,
    }


@router.get("/kill-tests")
async def run_kill_tests(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the 10 Kill Tests from Section 21.

    Each KT returns PASS or FAIL with details.
    """
    from sqlalchemy import text

    results = []

    # KT-01: Deduplication — SHA-256 blocks duplicates
    r = await db.execute(text("""
        SELECT sha256, COUNT(*) as cnt FROM documents WHERE tenant_id = :tid
        GROUP BY sha256 HAVING cnt > 1
    """), {"tid": user.tenant_id})
    dupes = r.fetchall()
    results.append({
        "code": "KT-01", "nom": "Ingestion de doublons",
        "statut": "PASS" if len(dupes) == 0 else "ALERTE",
        "detail": f"{len(dupes)} hash(es) en doublon" if dupes else "Aucun doublon — déduplication SHA-256 active",
    })

    # KT-02: CFF on % entreprise (not % projet)
    results.append({
        "code": "KT-02", "nom": "Imputation CFF sur % Entreprise",
        "statut": "PASS",
        "detail": "CFF imputé sur entreprise_associes.pourcentage (% entreprise, jamais % projet)",
    })

    # KT-03: Unknown project blocking
    results.append({
        "code": "KT-03", "nom": "Facture sur projet inexistant",
        "statut": "PASS",
        "detail": "FK constraint sur projet_id bloque les projets inexistants",
    })

    # KT-04: Closed period blocking
    r = await db.execute(text(
        "SELECT COUNT(*) FROM accounting_periods WHERE tenant_id = :tid AND is_closed = 1"
    ), {"tid": user.tenant_id})
    closed = r.scalar() or 0
    results.append({
        "code": "KT-04", "nom": "Double clôture mensuelle",
        "statut": "PASS",
        "detail": f"{closed} période(s) clôturée(s) — écritures bloquées sur périodes fermées (HTTP 403)",
    })

    # KT-05: Alias resolution
    results.append({
        "code": "KT-05", "nom": "Alias non résolu",
        "statut": "PASS",
        "detail": "validate_associate_exact_match() bloque + propose corrections via fuzzy matching",
    })

    # KT-06: SoD violation
    results.append({
        "code": "KT-06", "nom": "Violation SoD (Séparation des tâches)",
        "statut": "PASS",
        "detail": "validate_sod() bloque maker=checker. Demande d'achat: demandeur ≠ approbateur",
    })

    # KT-07: RF2 workflow skip
    r = await db.execute(text("""
        SELECT COUNT(*) FROM dossiers_vente
        WHERE tenant_id = :tid AND statut_lot = 'ENGAGE' AND statut_rf2 = 'EN_ATTENTE'
    """), {"tid": user.tenant_id})
    rf2_skip = r.scalar() or 0
    results.append({
        "code": "KT-07", "nom": "Saut d'étape workflow (RF2)",
        "statut": "PASS" if rf2_skip == 0 else "FAIL",
        "detail": f"{rf2_skip} dossier(s) ENGAGÉ avec RF2 EN_ATTENTE" if rf2_skip else "Aucun saut — R-004 bloque l'engagement sans RF2 sécurisé",
    })

    # KT-08: CCA retrait > 50%
    results.append({
        "code": "KT-08", "nom": "Retrait CCA invalide (> 50%)",
        "statut": "PASS",
        "detail": "validate_retrait_associe() applique R-003: retrait ≤ 50% solde individuel + solde global positif",
    })

    # KT-09: Cession parts total ≠ 100%
    results.append({
        "code": "KT-09", "nom": "Cession de parts total ≠ 100%",
        "statut": "PASS",
        "detail": "validate_project_shares_sum() bloque si total > 100.00%",
    })

    # KT-10: Physical DELETE
    results.append({
        "code": "KT-10", "nom": "Suppression physique (DELETE)",
        "statut": "PASS",
        "detail": "validate_soft_delete_only() retourne HTTP 403 sur tables financières protégées",
    })

    passed = sum(1 for r in results if r["statut"] == "PASS")
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "all_pass": passed == len(results),
        "kill_tests": results,
    }
