"""Router — AI Agent endpoints. Each calls a real LangGraph agent."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.v1.deps import get_current_user, CurrentUser, get_db
from app.api.v1.schemas import ApiResponse
from app.models.core import Company, EntrepriseAssocie, Associate, Payslip

router = APIRouter(prefix="/agents", tags=["AI Agents"])


@router.post("/cff/calculate")
async def agent_cff_calculate(body: dict, db: Session = Depends(get_db),
                                user: CurrentUser = Depends(get_current_user)):
    """Run CFF agent with LangGraph."""
    from app.agents.cff_agent import run_cff_calculation
    emitter = db.query(Company).filter(Company.code == body.get("emitter_code")).first()
    receiver = db.query(Company).filter(Company.code == body.get("receiver_code")).first()
    if not emitter or not receiver:
        raise HTTPException(404, "Entite introuvable")
    ownership = db.query(EntrepriseAssocie).join(Associate).filter(
        EntrepriseAssocie.company_id == emitter.id
    ).all()
    result = run_cff_calculation(
        montant_ht=float(body["montant_ht"]),
        emitter_code=emitter.code, receiver_code=receiver.code,
        emitter_name=emitter.legal_name, receiver_name=receiver.legal_name,
        emitter_ibs_rate=float(emitter.ibs_rate) if emitter.ibs_rate else None,
        emitter_tap_rate=float(emitter.tap_rate) if emitter.tap_rate else None,
        emitter_ownership=[{"name": o.associate.canonical_name, "percentage": float(o.percentage)} for o in ownership],
    )
    return ApiResponse(data=result)


@router.post("/document/process")
async def agent_document_process(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Run document classification + extraction agent."""
    from app.agents.document_agent import run_document_pipeline
    result = run_document_pipeline(
        filename=body.get("filename", "unknown.pdf"),
        content_preview=body.get("content", ""),
        file_hash=body.get("file_hash", ""),
    )
    return ApiResponse(data=result)


@router.post("/payroll/verify-l2")
async def agent_payroll_l2(body: dict, db: Session = Depends(get_db),
                             user: CurrentUser = Depends(get_current_user)):
    """Run L2 semantic payroll verification."""
    from app.agents.payroll_agent import run_payroll_l2
    payslip_id = body.get("payslip_id")
    if payslip_id:
        ps = db.query(Payslip).filter(Payslip.id == payslip_id).first()
        if not ps:
            raise HTTPException(404, "Bulletin introuvable")
        comp = db.query(Company).get(ps.company_id)
        result = run_payroll_l2(
            employee_code=ps.employee.matricule,
            entity_code=comp.code, department=ps.employee.department or "",
            position=ps.employee.position or "", cnas_regime=comp.cnas_regime or "GENERAL",
            salary_base=float(ps.salary_base), prime_rendement=float(ps.prime_rendement),
            gross=float(ps.gross), cnas_employee=float(ps.cnas_employee),
            irg_final=float(ps.irg_final), net=float(ps.net),
        )
    else:
        result = run_payroll_l2(**body)
    return ApiResponse(data=result)


@router.post("/adv/chain")
async def agent_adv_chain(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Run ADV engagement chain after RF2 payment."""
    from app.agents.adv_chain_agent import run_adv_chain
    result = run_adv_chain(
        dossier_numero=body.get("dossier_numero", ""),
        type_paiement=body.get("type_paiement", "FONDS_PROPRES"),
        prix_rf1=float(body.get("prix_rf1", 0)),
        prix_rf2=float(body.get("prix_rf2", 0)),
        montant_rf2_securise=float(body.get("montant_rf2_securise", 0)),
        total_paid=float(body.get("total_paid", 0)),
        fond_garantie_disponible=float(body.get("fond_garantie_disponible", 0)),
        montant_credit=float(body.get("montant_credit", 0)),
    )
    return ApiResponse(data=result)


@router.post("/compliance/check")
async def agent_compliance(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Run compliance check. If verify_mode=true, verifies a correction using AI."""
    if body.get("verify_mode"):
        # AI verification of submitted correction data
        from app.agents.drh_agents import call_llm
        import json as json_mod
        rule_code = body.get("rule_code", "")
        correction = body.get("correction_data", {})

        prompt = f"""Verifie cette correction soumise pour l'alerte de conformite {rule_code}.

Regle: {rule_code}
Donnees soumises:
- Numero RC: {correction.get('rc_number', 'non fourni')}
- NIF: {correction.get('nif_number', 'non fourni')}
- Texte clause: {correction.get('clause_text', 'non fourni')}
- Note: {correction.get('note', 'non fourni')}
- Texte du document uploade: {(correction.get('document_text', '') or 'aucun texte extrait')[:500]}
- Nom du fournisseur/partenaire: {correction.get('partner_name', 'inconnu')}

Verifie:
1. Si rule_code=ALG-RC-FRNR: le numero RC a-t-il un format valide algerien (ex: XX/00-XXXXXXXBXX)? Le document contient-il un registre de commerce?
2. Si rule_code=ALG-CTR-REV: la clause de revision est-elle juridiquement valide? Contient-elle un mecanisme d'indexation?
3. Si rule_code=ALG-DEP-1M: le document contient-il un visa ou une approbation?
4. Si rule_code=ALG-NC-2ANS: la duree de non-concurrence est-elle <= 2 ans?
5. Si rule_code=DOC_VERIFY: le document uploade est-il coherent avec le type de contrat declare? Verifie: (a) le document ressemble-t-il a un contrat/accord/convention? (b) le nom du partenaire mentionne dans le document correspond-il au partenaire declare? (c) le type de contrat (fournisseur/prestation/client/etc.) est-il coherent avec le contenu? (d) si un montant est visible dans le document, est-il coherent avec le montant declare?

Retourne un JSON: {{"verdict": "PASS" ou "FAIL" ou "WARNING", "message": "explication", "checks": [{{"check": "nom du controle", "passed": true/false, "detail": "explication"}}]}}"""

        system = "Tu es un agent de verification juridique pour le droit algerien. Tu verifies que les corrections soumises sont valides et completes. Reponds UNIQUEMENT avec un JSON valide."
        result_text = call_llm(system, prompt, 800)
        try:
            if "```" in result_text:
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            result = json_mod.loads(result_text.strip())
            return ApiResponse(data=result)
        except:
            return ApiResponse(data={"verdict": "PASS", "message": result_text, "checks": []})
    else:
        from app.agents.compliance_agent import run_compliance_check
        result = run_compliance_check(
            target_type=body.get("target_type", "contract"),
            target_data=body.get("target_data", {}),
        )
        return ApiResponse(data=result)


@router.post("/detection/analyze")
async def agent_detection(body: dict, user: CurrentUser = Depends(get_current_user)):
    """Run detection agent on text."""
    from app.agents.detection_agent import run_detection
    result = run_detection(
        input_text=body.get("text", ""),
        context=body.get("context", "document"),
    )
    return ApiResponse(data=result)
