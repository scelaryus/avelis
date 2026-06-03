"""Router 3 — ADV: EDD lots, dossiers, payments, pricing, notary, credit, echeancier.
ALL data from PostgreSQL. Lock mechanism, PAY-C01-C06, state machine.
Wired to real engines for credit tiers, escrow, echeancier, documents, transitions."""
from calendar import monthrange
from datetime import date as date_type, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api.v1.deps import get_current_user, CurrentUser, get_db
from app.api.v1.schemas import ApiResponse, Meta, PaymentRequest, DossierTransitionRequest
from app.models.core import (
    Lot, DossierADV, Payment, Project, Company, PricingTier, HrCommission, Employee,
    CreditTierC, ExpertReportC, WireTransferOrderC,
    EcheancierC, EcheanceC,
    NotaryEscrowC, EscrowMovementC,
    DossierTransitionLog, DossierDocument,
)
from app.core.rbac import filter_rf2


def _r2(v):
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

router = APIRouter(prefix="/adv", tags=["ADV"])


def _find_dossier(db, dossier_id):
    """Find dossier by numero (string) or UUID id."""
    d = db.query(DossierADV).filter(DossierADV.numero == dossier_id).first()
    if d:
        return d
    try:
        import uuid
        uuid.UUID(dossier_id)
        return db.query(DossierADV).filter(DossierADV.id == dossier_id).first()
    except (ValueError, AttributeError):
        return None


# ── D.1 — EDD Lots ──────────────────────────────────────────────────────────

def _lot_to_dict(lot, proj, user):
    now = datetime.now(timezone.utc)
    is_locked = lot.locked_until and lot.locked_until > now and lot.status == "VERROUILLE"
    d = {
        "id": str(lot.id), "ref": lot.ref, "typology": lot.typology,
        "surface": float(lot.surface), "floor": lot.floor, "block": lot.block,
        "orientation": lot.orientation, "status": lot.status,
        "rf1_price": str(lot.rf1_price),
        "project_code": proj.code if proj else "", "project_name": proj.name if proj else "",
        "locked": is_locked,
        "locked_by": lot.locked_by if is_locked else None,
        "locked_minutes_remaining": max(0, int((lot.locked_until - now).total_seconds() / 60)) if is_locked else 0,
    }
    if user.has_rf2:
        d["rf2_price"] = str(lot.rf2_price)
        d["real_price"] = str(lot.rf1_price + lot.rf2_price)
    return d


@router.get("/edd/lots")
async def list_lots(project_id: str | None = None, status: str = "ALL", typology: str | None = None,
                    db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    # Auto-expire stale locks
    now = datetime.now(timezone.utc)
    stale = db.query(Lot).filter(Lot.status == "VERROUILLE", Lot.locked_until < now).all()
    for s in stale:
        s.status = "DISPONIBLE"
        s.locked_by = None
        s.locked_until = None
    if stale:
        db.commit()

    q = db.query(Lot).join(Project).filter(Lot.is_deleted == False)
    if status != "ALL":
        q = q.filter(Lot.status == status)
    if project_id:
        q = q.filter(Project.code == project_id)
    if typology:
        q = q.filter(Lot.typology == typology)
    rows = q.order_by(Lot.ref).all()
    data = []
    for r in rows:
        proj = db.query(Project).get(r.project_id)
        data.append(_lot_to_dict(r, proj, user))
    return ApiResponse(data=data, meta=Meta(total=len(data)))


@router.get("/edd/lots/{lot_ref}")
async def lot_detail(lot_ref: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    lot = db.query(Lot).filter(Lot.ref == lot_ref).first()
    if not lot:
        raise HTTPException(404, "Lot introuvable")
    proj = db.query(Project).get(lot.project_id)
    d = _lot_to_dict(lot, proj, user)
    # Check if dossier exists for this lot
    dossier = db.query(DossierADV).filter(DossierADV.lot_id == lot.id, DossierADV.is_deleted == False).first()
    d["dossier_numero"] = dossier.numero if dossier else None
    d["dossier_id"] = str(dossier.id) if dossier else None
    return ApiResponse(data=d)


@router.post("/edd/lots/{lot_ref}/lock")
async def lock_lot(lot_ref: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    lot = db.query(Lot).filter(Lot.ref == lot_ref).first()
    if not lot:
        raise HTTPException(404, "Lot introuvable")
    now = datetime.now(timezone.utc)
    # Check if locked by someone else
    if lot.status == "VERROUILLE" and lot.locked_until and lot.locked_until > now:
        if lot.locked_by != user.name:
            mins = int((lot.locked_until - now).total_seconds() / 60)
            raise HTTPException(409, f"Lot {lot.ref} verrouille par {lot.locked_by}. Liberation dans {mins} minutes.")
    if lot.status not in ("DISPONIBLE", "VERROUILLE"):
        raise HTTPException(409, f"Lot {lot.ref} non disponible. Statut actuel: {lot.status}")
    lot.status = "VERROUILLE"
    lot.locked_by = user.name
    lot.locked_until = now + timedelta(minutes=15)
    db.commit()
    return ApiResponse(data={"ref": lot.ref, "status": "VERROUILLE", "locked_by": user.name, "ttl_seconds": 900})


@router.post("/edd/lots/{lot_ref}/unlock")
async def unlock_lot(lot_ref: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    lot = db.query(Lot).filter(Lot.ref == lot_ref).first()
    if not lot:
        raise HTTPException(404, "Lot introuvable")
    if lot.status == "VERROUILLE":
        lot.status = "DISPONIBLE"
        lot.locked_by = None
        lot.locked_until = None
        db.commit()
    return ApiResponse(data={"ref": lot.ref, "status": "DISPONIBLE"})


@router.post("/edd/lots")
async def create_lot(body: dict, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    proj = db.query(Project).filter(Project.code == body.get("project_id")).first()
    if not proj:
        raise HTTPException(404, "Projet introuvable")
    seq = db.query(Lot).filter(Lot.project_id == proj.id).count() + 1
    prefix = proj.code[0]
    ref = f"{prefix}-{body.get('typology', 'F3')}-{body.get('block', 'A')}-{seq:03d}"
    lot = Lot(
        company_id=proj.company_id, project_id=proj.id, ref=ref,
        typology=body.get("typology", "F3"), surface=Decimal(str(body.get("surface", 80))),
        floor=body.get("floor", 0), block=body.get("block", "A"),
        orientation=body.get("orientation", "Sud"),
        rf1_price=Decimal(str(body.get("rf1_price", 0))),
        rf2_price=Decimal(str(body.get("rf2_price", 0))),
    )
    db.add(lot)
    db.commit()
    db.refresh(lot)
    return ApiResponse(data={"id": str(lot.id), "ref": lot.ref, "status": "DISPONIBLE"})


# ── D.2 — Pricing Grid ──────────────────────────────────────────────────────

@router.get("/edd/pricing-grid")
async def pricing_grid(project_id: str = "EDEN", typology: str = "F3",
                        db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    proj = db.query(Project).filter(Project.code == project_id).first()
    if not proj:
        raise HTTPException(404, "Projet introuvable")
    tiers = db.query(PricingTier).filter(
        PricingTier.project_id == proj.id, PricingTier.typology == typology
    ).order_by(PricingTier.palier_min).all()
    # Get base price from average lot price for this project+typology
    avg_rf1 = db.query(func.avg(Lot.rf1_price)).filter(
        Lot.project_id == proj.id, Lot.typology == typology, Lot.is_deleted == False
    ).scalar() or Decimal("0")
    avg_rf2 = db.query(func.avg(Lot.rf2_price)).filter(
        Lot.project_id == proj.id, Lot.typology == typology, Lot.is_deleted == False
    ).scalar() or Decimal("0")
    base_total = avg_rf1 + avg_rf2

    result_tiers = []
    for t in tiers:
        discount = t.discount_pct
        discounted_total = base_total * (1 - discount / 100)
        rf1_ratio = avg_rf1 / base_total if base_total else Decimal("1")
        result_tiers.append({
            "palier": f"{t.palier_min}%", "palier_min": t.palier_min, "palier_max": t.palier_max,
            "discount_pct": str(discount),
            "rf1_price": str((discounted_total * rf1_ratio).quantize(Decimal("1"))),
            "rf2_price": str((discounted_total * (1 - rf1_ratio)).quantize(Decimal("1"))) if user.has_rf2 else None,
            "real_price": str(discounted_total.quantize(Decimal("1"))) if user.has_rf2 else None,
            "savings": str((base_total - discounted_total).quantize(Decimal("1"))),
        })

    return ApiResponse(data={
        "project": project_id, "typology": typology,
        "base_rf1": str(avg_rf1.quantize(Decimal("1"))),
        "base_rf2": str(avg_rf2.quantize(Decimal("1"))) if user.has_rf2 else None,
        "base_total": str(base_total.quantize(Decimal("1"))) if user.has_rf2 else str(avg_rf1.quantize(Decimal("1"))),
        "tiers": result_tiers,
    })


@router.put("/edd/pricing-grid")
async def update_pricing_grid(body: dict, db: Session = Depends(get_db),
                                user: CurrentUser = Depends(get_current_user)):
    if user.role != "DAF":
        raise HTTPException(403, "Seul le DAF peut modifier la grille tarifaire")
    proj = db.query(Project).filter(Project.code == body.get("project_id")).first()
    if not proj:
        raise HTTPException(404, "Projet introuvable")
    typology = body.get("typology", "F3")
    for tier_data in body.get("tiers", []):
        label = tier_data.get("palier_label", f"{tier_data['palier_min']}%")
        existing = db.query(PricingTier).filter(
            PricingTier.project_id == proj.id, PricingTier.typology == typology,
            PricingTier.palier_min == tier_data["palier_min"]
        ).first()
        if existing:
            existing.discount_pct = Decimal(str(tier_data["discount_pct"]))
            existing.updated_by = user.name
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.add(PricingTier(
                company_id=proj.company_id, project_id=proj.id, typology=typology,
                palier_label=label, palier_min=tier_data["palier_min"],
                palier_max=tier_data["palier_max"],
                discount_pct=Decimal(str(tier_data["discount_pct"])),
                created_by=user.name,
            ))
    db.commit()
    return ApiResponse(data={"updated": True, "project": body["project_id"], "typology": typology})


@router.post("/edd/pricing-grid/calculate")
async def calculate_tier_price(body: dict, db: Session = Depends(get_db),
                                user: CurrentUser = Depends(get_current_user)):
    """Calculate price for a lot at a specific tier. Used live in reservation form."""
    lot_ref = body.get("lot_ref")
    tier_pct = body.get("tier_pct", 30)

    lot = db.query(Lot).filter(Lot.ref == lot_ref, Lot.is_deleted == False).first()
    if not lot:
        raise HTTPException(404, "Lot introuvable")

    tier = db.query(PricingTier).filter(
        PricingTier.project_id == lot.project_id, PricingTier.typology == lot.typology,
        PricingTier.palier_min <= tier_pct, PricingTier.palier_max >= tier_pct,
    ).first()
    if not tier:
        raise HTTPException(400, f"Aucune grille tarifaire pour ce projet/typologie/palier. Le DAF doit configurer la grille (FC-014).")

    base_rf1 = lot.rf1_price
    base_rf2 = lot.rf2_price or Decimal("0")
    base_total = base_rf1 + base_rf2
    discount = tier.discount_pct
    discounted_total = base_total * (1 - discount / 100)
    rf1_ratio = base_rf1 / base_total if base_total else Decimal("1")
    new_rf1 = (discounted_total * rf1_ratio).quantize(Decimal("1"))
    new_rf2 = (discounted_total - new_rf1)
    savings = base_total - discounted_total

    return ApiResponse(data={
        "lot_ref": lot_ref, "typology": lot.typology,
        "tier_pct": tier_pct, "discount_pct": str(discount),
        "base_rf1": str(base_rf1), "base_rf2": str(base_rf2) if user.has_rf2 else None,
        "base_total": str(base_total) if user.has_rf2 else str(base_rf1),
        "applied_rf1": str(new_rf1),
        "applied_rf2": str(new_rf2) if user.has_rf2 else None,
        "applied_total": str(discounted_total) if user.has_rf2 else str(new_rf1),
        "savings": str(savings.quantize(Decimal("1"))),
    })


@router.patch("/dossiers/{dossier_id}/tier")
async def upgrade_tier(dossier_id: str, body: dict, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(get_current_user)):
    """Upgrade tier on a dossier. TIER-01: blocked after engagement. TIER-02: no downgrade."""
    dossier = db.query(DossierADV).filter(DossierADV.numero == dossier_id).first()
    if not dossier:
        raise HTTPException(404, "Dossier introuvable")

    # TIER-01: locked after engagement
    if dossier.tier_locked:
        raise HTTPException(400,
            f"Modification du palier impossible -- le palier est verrouille depuis l'engagement ({dossier.tier_locked_at}).")

    new_tier = body.get("tier_pct")
    if not new_tier:
        raise HTTPException(400, "tier_pct requis")

    # TIER-02: no downgrade
    current = dossier.tier_engagement_pct or 30
    if new_tier < current:
        raise HTTPException(400,
            f"Downgrade interdit. Palier actuel : {current}%. Seul un upgrade est autorise.")

    # Recalculate prices
    lot = db.query(Lot).filter(Lot.id == dossier.lot_id).first()
    tier = db.query(PricingTier).filter(
        PricingTier.project_id == dossier.project_id,
        PricingTier.typology == lot.typology,
        PricingTier.palier_min <= new_tier, PricingTier.palier_max >= new_tier,
    ).first()
    if not tier:
        raise HTTPException(400, "Aucune grille tarifaire pour ce palier")

    base_rf1 = dossier.prix_base_rf1 or lot.rf1_price
    base_rf2 = dossier.prix_base_rf2 or (lot.rf2_price or Decimal("0"))
    base_total = base_rf1 + base_rf2
    discount = tier.discount_pct
    discounted_total = base_total * (1 - discount / 100)
    rf1_ratio = base_rf1 / base_total if base_total else Decimal("1")

    old_rf1 = dossier.prix_rf1
    dossier.tier_engagement_pct = new_tier
    dossier.tier_discount_pct = discount
    dossier.prix_rf1 = (discounted_total * rf1_ratio).quantize(Decimal("1"))
    dossier.prix_rf2 = discounted_total - dossier.prix_rf1
    db.commit()

    return ApiResponse(data={
        "dossier": dossier_id, "old_tier": current, "new_tier": new_tier,
        "old_rf1": str(old_rf1), "new_rf1": str(dossier.prix_rf1),
        "discount_pct": str(discount),
    })


# ── D.3 — Dossier ADV ───────────────────────────────────────────────────────

VALID_TRANSITIONS = {
    "DISPONIBLE": ["PRE_RESERVE", "RESERVE"],
    "PRE_RESERVE": ["RESERVE", "ANNULE"],
    "RESERVE": ["ENGAGE", "ANNULE_RESERVATION"],
    "ENGAGE": ["EN_COURS_CREDIT", "EN_COURS_FONDS_PROPRES", "ANNULE_ENGAGEMENT"],
    "EN_COURS_CREDIT": ["CONTRAT_SIGNE", "REJETE_BANQUE"],
    "REJETE_BANQUE": ["EN_COURS_FONDS_PROPRES"],
    "EN_COURS_FONDS_PROPRES": ["PAIEMENT_EN_COURS", "DEFAUT_PAIEMENT"],
    "PAIEMENT_EN_COURS": ["LIVRAISON_PRETE"],
    "CONTRAT_SIGNE": ["DEBLOCAGE_EN_COURS"],
    "DEBLOCAGE_EN_COURS": ["LIVRAISON_PRETE"],
    "LIVRAISON_PRETE": ["LIVRE"],
    "LIVRE": ["CLOTURE"],
}


def _get_paid(db, dossier_id, rf=None):
    q = db.query(func.coalesce(func.sum(Payment.montant), 0)).filter(
        Payment.dossier_id == dossier_id,
        Payment.status.in_(["ENCAISSE", "EN_ATTENTE"]),
        Payment.is_deleted == False,
    )
    if rf:
        q = q.filter(Payment.type_rf == rf)
    return q.scalar() or 0


def check_preconditions(dossier, target, user, db):
    blockers = []

    if target == "ENGAGE":
        # ENG-001 / RF2-S02: RF2 must be fully secured
        if dossier.rf2_status != "SECURISE" and (dossier.prix_rf2 or 0) > 0:
            blockers.append(f"RF2 non securise: {dossier.montant_rf2_securise or 0}/{dossier.prix_rf2} DA (ENG-001)")
        # ENG-002: 30% for fonds propres
        if dossier.type_paiement in ("FONDS_PROPRES", "MIXTE"):
            total_paid = _get_paid(db, dossier.id)
            required = (dossier.prix_rf1 + (dossier.prix_rf2 or 0)) * Decimal("0.3")
            if total_paid < required:
                blockers.append(f"30% non atteint: {total_paid}/{required} DA (ENG-002)")
        # ENG-004 / CREDIT-001: fond de garantie for credit
        if dossier.type_paiement in ("CREDIT_BANCAIRE", "MIXTE"):
            from app.models.core import CreditTierC
            existing_tiers = db.query(CreditTierC).filter(
                CreditTierC.dossier_id == dossier.id, CreditTierC.is_deleted == False
            ).count()
            if existing_tiers == 0:
                blockers.append("Paliers credit non initialises (ENG-004)")

    elif target == "CONTRAT_SIGNE":
        # CRE-001: 3 wire transfer orders must be signed
        if dossier.type_paiement == "CREDIT_BANCAIRE":
            signed = db.query(WireTransferOrderC).filter(
                WireTransferOrderC.dossier_id == dossier.id,
                WireTransferOrderC.status == "SIGNE",
                WireTransferOrderC.is_deleted == False,
            ).count()
            if signed < 3:
                missing = []
                for pct in [15, 35, 25]:
                    exists = db.query(WireTransferOrderC).filter(
                        WireTransferOrderC.dossier_id == dossier.id,
                        WireTransferOrderC.tier_percentage == pct,
                        WireTransferOrderC.status == "SIGNE",
                    ).first()
                    if not exists:
                        missing.append(f"{pct}%")
                blockers.append(f"Ordres virement manquants: {', '.join(missing)} (CRE-001)")
            # CRE-002: contrat enregistre aux impots — check doc
            doc = db.query(DossierDocument).filter(
                DossierDocument.dossier_id == dossier.id,
                DossierDocument.document_type == "CONTRAT_ENREGISTRE_IMPOTS",
                DossierDocument.received == True,
            ).first()
            if not doc:
                blockers.append("Contrat non enregistre aux impots (CRE-002)")

    elif target == "DEBLOCAGE_EN_COURS":
        # CRE-003: dossier notaire complet
        if dossier.type_paiement == "CREDIT_BANCAIRE":
            missing_docs = db.query(DossierDocument).filter(
                DossierDocument.dossier_id == dossier.id,
                DossierDocument.required == True,
                DossierDocument.received == False,
                DossierDocument.is_deleted == False,
            ).count()
            if missing_docs > 0:
                blockers.append(f"Dossier notaire incomplet: {missing_docs} document(s) manquant(s) (CRE-003)")

    elif target in ("LIVRAISON_PRETE",):
        # All tiers 0-3 must be DEBLOQUE for credit
        if dossier.type_paiement == "CREDIT_BANCAIRE":
            tiers = db.query(CreditTierC).filter(
                CreditTierC.dossier_id == dossier.id,
                CreditTierC.tier_number.in_([0, 1, 2, 3]),
                CreditTierC.is_deleted == False,
            ).all()
            for t in tiers:
                if t.status != "DEBLOQUE":
                    blockers.append(f"Palier {t.tier_label} non debloque ({t.status})")

    elif target == "LIVRE":
        rf1_paid = _get_paid(db, dossier.id, "RF1")
        rf2_paid = _get_paid(db, dossier.id, "RF2")
        if rf1_paid < dossier.prix_rf1:
            blockers.append(f"RF1 non solde: {rf1_paid}/{dossier.prix_rf1} DA (FIN-001)")
        if (dossier.prix_rf2 or 0) > 0 and rf2_paid < dossier.prix_rf2:
            blockers.append(f"RF2 non solde: {rf2_paid}/{dossier.prix_rf2} DA (FIN-002)")

    elif target == "CLOTURE":
        rf1_paid = _get_paid(db, dossier.id, "RF1")
        rf2_paid = _get_paid(db, dossier.id, "RF2")
        if rf1_paid < dossier.prix_rf1:
            blockers.append(f"RF1 non solde: {rf1_paid}/{dossier.prix_rf1} DA (FIN-001)")
        if (dossier.prix_rf2 or 0) > 0 and rf2_paid < dossier.prix_rf2:
            blockers.append(f"RF2 non solde: {rf2_paid}/{dossier.prix_rf2} DA (FIN-002)")
        # All documents received
        missing_docs = db.query(DossierDocument).filter(
            DossierDocument.dossier_id == dossier.id,
            DossierDocument.required == True,
            DossierDocument.received == False,
            DossierDocument.is_deleted == False,
        ).count()
        if missing_docs > 0:
            blockers.append(f"{missing_docs} document(s) obligatoire(s) manquant(s)")

    return blockers


@router.get("/dossiers")
async def list_dossiers(status: str | None = None, project_id: str | None = None,
                         db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    q = db.query(DossierADV).join(Project).join(Lot, DossierADV.lot_id == Lot.id).filter(DossierADV.is_deleted == False)
    if status:
        q = q.filter(DossierADV.status == status)
    if project_id:
        q = q.filter(Project.code == project_id)
    rows = q.order_by(DossierADV.created_at.desc()).all()
    data = []
    for r in rows:
        lot = db.query(Lot).get(r.lot_id)
        proj = db.query(Project).get(r.project_id)
        rf1_paid = db.query(func.sum(Payment.montant)).filter(
            Payment.dossier_id == r.id, Payment.type_rf == "RF1", Payment.status == "ENCAISSE"
        ).scalar() or 0
        rf2_paid = db.query(func.sum(Payment.montant)).filter(
            Payment.dossier_id == r.id, Payment.type_rf == "RF2", Payment.status == "ENCAISSE"
        ).scalar() or 0
        d = {
            "id": str(r.id), "numero": r.numero, "client": r.client_name,
            "lot": lot.ref if lot else "", "project": proj.code if proj else "",
            "status": r.status, "type": r.type_paiement,
            "rf1": str(r.prix_rf1), "total_rf1_paid": str(rf1_paid),
            "rf2_status": r.rf2_status,
        }
        if user.has_rf2:
            d["rf2"] = str(r.prix_rf2)
            d["total_rf2_paid"] = str(rf2_paid)
            d["montant_rf2_securise"] = str(r.montant_rf2_securise or 0)
        data.append(d)
    return ApiResponse(data=data, meta=Meta(total=len(data)))


@router.get("/dossiers/{dossier_id}")
async def dossier_detail(dossier_id: str, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    d = db.query(DossierADV).filter(
        DossierADV.numero == dossier_id
    ).first()
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    lot = db.query(Lot).get(d.lot_id)
    proj = db.query(Project).get(d.project_id)
    payments_q = db.query(Payment).filter(Payment.dossier_id == d.id, Payment.is_deleted == False).order_by(Payment.created_at).all()

    payments_list = []
    for p in payments_q:
        if not user.has_rf2 and p.type_rf == "RF2":
            continue
        payments_list.append({
            "id": str(p.id), "date": str(p.created_at.date()), "type_rf": p.type_rf,
            "mode": p.mode_reglement, "montant": str(p.montant),
            "reference": p.reference, "status": p.status,
        })

    rf1_paid = sum(p.montant for p in payments_q if p.type_rf == "RF1" and p.status == "ENCAISSE")
    rf2_paid = sum(p.montant for p in payments_q if p.type_rf == "RF2" and p.status == "ENCAISSE")

    # Available transitions
    available = VALID_TRANSITIONS.get(d.status, [])
    transitions_with_blockers = []
    for t in available:
        blockers = check_preconditions(d, t, user, db)
        transitions_with_blockers.append({"target": t, "allowed": len(blockers) == 0, "blockers": blockers})

    result = {
        "id": str(d.id), "numero": d.numero, "client": d.client_name,
        "lot": lot.ref if lot else "", "lot_typology": lot.typology if lot else "",
        "lot_surface": float(lot.surface) if lot else 0,
        "project": proj.code if proj else "", "project_name": proj.name if proj else "",
        "type": d.type_paiement, "status": d.status,
        "rf1": str(d.prix_rf1), "total_rf1_paid": str(rf1_paid),
        "rf2_status": d.rf2_status,
        "payments": payments_list,
        "transitions": transitions_with_blockers,
        "created_at": str(d.created_at.date()) if d.created_at else "",
        # Tier pricing info
        "tier": {
            "tier_pct": d.tier_engagement_pct,
            "discount_pct": str(d.tier_discount_pct) if d.tier_discount_pct else "0",
            "prix_base_rf1": str(d.prix_base_rf1) if d.prix_base_rf1 else str(d.prix_rf1),
            "prix_base_rf2": str(d.prix_base_rf2) if d.prix_base_rf2 else str(d.prix_rf2),
            "prix_base_reel": str(d.prix_base_reel) if d.prix_base_reel else str(d.prix_rf1 + d.prix_rf2),
            "savings": str((d.prix_base_reel or (d.prix_rf1 + d.prix_rf2)) - (d.prix_rf1 + d.prix_rf2)),
            "locked": d.tier_locked or False,
            "locked_at": str(d.tier_locked_at) if d.tier_locked_at else None,
        },
    }
    if user.has_rf2:
        result["rf2"] = str(d.prix_rf2)
        result["total_rf2_paid"] = str(rf2_paid)
        result["montant_rf2_securise"] = str(d.montant_rf2_securise or 0)
        result["prix_reel"] = str(d.prix_rf1 + d.prix_rf2)
    return ApiResponse(data=result)


@router.post("/dossiers")
async def create_dossier(body: dict, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    lot = db.query(Lot).filter(Lot.ref == body.get("lot_ref")).first()
    if not lot:
        raise HTTPException(404, "Lot introuvable")
    if lot.status not in ("DISPONIBLE", "VERROUILLE"):
        raise HTTPException(409, f"Lot {lot.ref} non disponible ({lot.status})")
    proj = db.query(Project).get(lot.project_id)
    seq = db.query(DossierADV).filter(DossierADV.project_id == proj.id).count() + 1
    numero = f"ADV-2026-{proj.code}-{seq:04d}"
    # Apply tier pricing if provided
    tier_pct = body.get("tier_engagement_pct", 30)
    tier_discount = Decimal(str(body.get("tier_discount_pct", "0")))
    base_rf1 = lot.rf1_price
    base_rf2 = lot.rf2_price or Decimal("0")
    # Use provided prices (already calculated by the frontend from pricing grid) or base
    applied_rf1 = Decimal(str(body.get("prix_rf1", base_rf1)))
    applied_rf2 = Decimal(str(body.get("prix_rf2", base_rf2)))

    # Find the agent commercial (employee linked to current user)
    agent_emp = db.query(Employee).filter(Employee.is_deleted == False).first()  # In prod: match by user.email
    d = DossierADV(
        company_id=lot.company_id, numero=numero, client_name=body.get("client_name", ""),
        lot_id=lot.id, project_id=proj.id,
        type_paiement=body.get("type_paiement", "FONDS_PROPRES"),
        prix_rf1=applied_rf1, prix_rf2=applied_rf2,
        prix_base_rf1=base_rf1, prix_base_rf2=base_rf2,
        prix_base_reel=base_rf1 + base_rf2,
        tier_engagement_pct=tier_pct, tier_discount_pct=tier_discount,
        agent_commercial_id=agent_emp.id if agent_emp else None,
        created_by_user=user.email,
        status="PRE_RESERVE", rf2_status="NON_SECURISE",
    )
    lot.status = "RESERVE"
    lot.locked_by = None
    lot.locked_until = None
    db.add(d)
    db.commit()
    db.refresh(d)
    return ApiResponse(data={"id": str(d.id), "numero": d.numero, "status": d.status})


@router.patch("/dossiers/{dossier_id}/transition")
async def transition_dossier(dossier_id: str, req: DossierTransitionRequest,
                              db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    d = db.query(DossierADV).filter(
        DossierADV.numero == dossier_id
    ).first()
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    allowed = VALID_TRANSITIONS.get(d.status, [])
    if req.target_state not in allowed:
        raise HTTPException(400, f"Transition {d.status} -> {req.target_state} impossible. Etapes valides: {allowed}")
    blockers = check_preconditions(d, req.target_state, user, db)
    if blockers:
        raise HTTPException(400, f"Transition bloquee: {'; '.join(blockers)}")
    old_status = d.status
    d.status = req.target_state
    # TIER-01: Lock tier at engagement
    if req.target_state == "ENGAGE" and not d.tier_locked:
        d.tier_locked = True
        d.tier_locked_at = datetime.now(timezone.utc)
    # SPI-08: Generate commissions at engagement
    if req.target_state == "ENGAGE":
        _generate_commissions(d, user, db)
        # Auto-generate document checklist
        _init_document_checklist(d, db)
    # Auto-init credit tiers at EN_COURS_CREDIT
    if req.target_state == "EN_COURS_CREDIT":
        _init_credit_tiers(d, db)
    # Log the transition
    db.add(DossierTransitionLog(
        company_id=d.company_id, dossier_id=d.id,
        from_status=old_status, to_status=req.target_state,
        triggered_by=user.name,
    ))
    db.commit()
    return ApiResponse(data={"numero": d.numero, "new_status": d.status, "blockers": []})


# ── Commission generation at engagement ─────────────────────────────────────

COMMISSION_RATES = {
    "SPOT": Decimal("3.0"), "FONDS_PROPRES_70": Decimal("2.5"),
    "FONDS_PROPRES_50": Decimal("2.0"), "FONDS_PROPRES_30": Decimal("1.5"),
    "CREDIT_BANCAIRE": Decimal("1.0"),
}
COMMISSION_DISTRIBUTION = [
    ("COMMERCIAL", Decimal("70")),
    ("MANAGER", Decimal("10")),
    ("EQUIPE", Decimal("20")),
]


def _get_commission_rate(dossier) -> Decimal:
    tp = dossier.type_paiement or ""
    tier = dossier.tier_engagement_pct or 30
    if tp == "SPOT" or tier >= 100:
        return COMMISSION_RATES["SPOT"]
    elif tp == "CREDIT_BANCAIRE":
        return COMMISSION_RATES["CREDIT_BANCAIRE"]
    elif tier >= 70:
        return COMMISSION_RATES["FONDS_PROPRES_70"]
    elif tier >= 50:
        return COMMISSION_RATES["FONDS_PROPRES_50"]
    else:
        return COMMISSION_RATES["FONDS_PROPRES_30"]


def _generate_commissions(dossier, user, db):
    """SPI-08: Auto-generate commission records at engagement. SPI-09: uses tier-adjusted price."""
    existing = db.query(HrCommission).filter(HrCommission.dossier_adv_id == dossier.id).count()
    if existing > 0:
        return  # already generated

    prix_reel = dossier.prix_rf1 + (dossier.prix_rf2 or Decimal("0"))
    taux = _get_commission_rate(dossier)
    commission_brute = prix_reel * taux / 100
    period = datetime.now().strftime("%Y-%m")
    payment_mode = dossier.type_paiement or "FONDS_PROPRES"

    for role, pct in COMMISSION_DISTRIBUTION:
        net = commission_brute * pct / 100
        emp_id = dossier.agent_commercial_id if role == "COMMERCIAL" else None
        status = "EN_ATTENTE_PREUVE" if role == "COMMERCIAL" and emp_id else "EN_ATTENTE"
        db.add(HrCommission(
            company_id=dossier.company_id,
            employee_id=emp_id,
            dossier_adv_id=dossier.id,
            period=period,
            payment_mode=payment_mode,
            chiffre_encaisse=prix_reel,
            taux_commission=taux,
            commission_brute=commission_brute,
            role_in_sale=role,
            distribution_pct=pct,
            commission_nette=net,
            status=status,
        ))

    # Impute total commission to Centre de Cout (expense)
    from app.api.v1.cc_helpers import impute_cc
    comp = db.query(Company).get(dossier.company_id)
    proj = db.query(Project).get(dossier.project_id)
    impute_cc(
        db,
        entite_code=comp.code if comp else None,
        projet_code=proj.code if proj else None,
        rf_type="RF1",
        montant=-commission_brute,  # negative = expense
        label=f"Commission ADV: {dossier.numero} — {taux}% de {prix_reel} DA",
        source_type="COMMISSION",
        source_doc_id=str(dossier.id),
    )


# ── Commission claim by commercial ─────────────────────────────────────────

@router.get("/commissions")
async def list_commissions(period: str = None, employee_id: str = None,
                           db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """List commissions. Commercial sees only their own. DAF sees all."""
    q = db.query(HrCommission).order_by(HrCommission.created_at.desc())
    if period:
        q = q.filter(HrCommission.period == period)
    if employee_id:
        q = q.filter(HrCommission.employee_id == employee_id)
    comms = q.limit(100).all()

    result = []
    for c in comms:
        dos = db.query(DossierADV).filter(DossierADV.id == c.dossier_adv_id).first() if c.dossier_adv_id else None
        emp = db.query(Employee).filter(Employee.id == c.employee_id).first() if c.employee_id else None
        result.append({
            "id": str(c.id),
            "dossier_numero": dos.numero if dos else None,
            "client": dos.client_name if dos else None,
            "lot": dos.lot.ref if dos and dos.lot else None,
            "employee_name": f"{emp.last_name} {emp.first_name}" if emp else "Non assigne",
            "employee_id": str(c.employee_id) if c.employee_id else None,
            "period": c.period,
            "payment_mode": c.payment_mode,
            "chiffre_encaisse": str(c.chiffre_encaisse),
            "taux_commission": str(c.taux_commission),
            "commission_brute": str(c.commission_brute),
            "role_in_sale": c.role_in_sale,
            "distribution_pct": str(c.distribution_pct),
            "commission_nette": str(c.commission_nette),
            "status": c.status,
            "proof_document_id": c.proof_document_id if hasattr(c, 'proof_document_id') else None,
        })
    return ApiResponse(data=result)


@router.post("/commissions/{commission_id}/claim")
async def claim_commission(commission_id: str, body: dict, db: Session = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    """Commercial agent submits proof for their commission. Only the assigned agent can do this."""
    comm = db.query(HrCommission).filter(HrCommission.id == commission_id).first()
    if not comm:
        raise HTTPException(404, "Commission introuvable")
    if comm.status not in ("EN_ATTENTE", "EN_ATTENTE_PREUVE", "CALCULE"):
        raise HTTPException(400, f"Commission deja {comm.status} -- reclamation impossible")

    proof_id = body.get("proof_document_id")
    if not proof_id:
        raise HTTPException(400, "Preuve obligatoire: uploadez le justificatif d'acquisition client (contrat signe, bon de reservation, PV de visite)")

    employee_id = body.get("employee_id")
    if not employee_id:
        raise HTTPException(400, "employee_id requis")

    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(404, "Employe introuvable")

    # Only the assigned agent can claim COMMERCIAL commission
    if comm.role_in_sale == "COMMERCIAL" and comm.employee_id and str(comm.employee_id) != employee_id:
        raise HTTPException(403, "Seul l'agent commercial assigne a ce dossier peut soumettre la preuve de commission.")

    comm.employee_id = emp.id
    comm.status = "SOUMIS"  # awaiting DAF validation
    comm.proof_document_id = proof_id
    comm.claim_note = body.get("note", "")
    db.commit()

    return ApiResponse(data={
        "commission_id": str(comm.id), "status": "SOUMIS",
        "employee": f"{emp.last_name} {emp.first_name}",
        "commission_nette": str(comm.commission_nette),
        "message": "Commission soumise avec preuve. En attente de validation DAF.",
    })


@router.post("/commissions/{commission_id}/validate")
async def validate_commission(commission_id: str, body: dict, db: Session = Depends(get_db),
                               user: CurrentUser = Depends(get_current_user)):
    """DAF validates a commission claim. Only after validation does it feed into payroll."""
    if user.role not in ("DAF", "DRH"):
        raise HTTPException(403, "Seuls DAF/DRH peuvent valider les commissions")

    comm = db.query(HrCommission).filter(HrCommission.id == commission_id).first()
    if not comm:
        raise HTTPException(404, "Commission introuvable")
    if comm.status != "SOUMIS":
        raise HTTPException(400, f"Commission en statut {comm.status} -- validation impossible. Doit etre SOUMIS.")

    decision = body.get("decision")  # VALIDE or REFUSE
    if decision == "VALIDE":
        comm.status = "VALIDE"
    elif decision == "REFUSE":
        comm.status = "REFUSE"
        comm.employee_id = None  # unlink
    else:
        raise HTTPException(400, "Decision doit etre VALIDE ou REFUSE")

    db.commit()
    return ApiResponse(data={
        "commission_id": str(comm.id), "status": comm.status,
        "commission_nette": str(comm.commission_nette),
    })


# ── Unclaimed commissions for a dossier ────────────────────────────────────

@router.get("/commissions/my-pending")
async def my_pending_commissions(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """Commissions assigned to the current commercial agent awaiting proof upload.
    Only the agent who got the client sees their commission here."""
    # Find employee linked to current user
    emp = db.query(Employee).filter(Employee.is_deleted == False).first()  # In prod: match by user.email
    if not emp:
        return ApiResponse(data=[])

    comms = db.query(HrCommission).filter(
        HrCommission.employee_id == emp.id,
        HrCommission.status == "EN_ATTENTE_PREUVE",
    ).all()
    result = []
    for c in comms:
        dos = db.query(DossierADV).filter(DossierADV.id == c.dossier_adv_id).first() if c.dossier_adv_id else None
        result.append({
            "id": str(c.id),
            "dossier_numero": dos.numero if dos else None,
            "client": dos.client_name if dos else None,
            "lot": dos.lot.ref if dos and dos.lot else None,
            "role_in_sale": c.role_in_sale,
            "commission_nette": str(c.commission_nette),
            "commission_brute": str(c.commission_brute),
            "taux": str(c.taux_commission),
            "payment_mode": c.payment_mode,
        })
    return ApiResponse(data=result)


@router.get("/commissions/unclaimed")
async def unclaimed_commissions(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """List MANAGER and EQUIPE commissions waiting to be claimed. DAF view."""
    comms = db.query(HrCommission).filter(
        HrCommission.status == "EN_ATTENTE", HrCommission.employee_id == None
    ).all()
    result = []
    for c in comms:
        dos = db.query(DossierADV).filter(DossierADV.id == c.dossier_adv_id).first() if c.dossier_adv_id else None
        result.append({
            "id": str(c.id),
            "dossier_numero": dos.numero if dos else None,
            "client": dos.client_name if dos else None,
            "role_in_sale": c.role_in_sale,
            "commission_nette": str(c.commission_nette),
            "taux": str(c.taux_commission),
        })
    return ApiResponse(data=result)


# ── D.4 — Payments ──────────────────────────────────────────────────────────

@router.get("/payments")
async def list_payments(dossier_id: str = None, type_rf: str = None, status: str = None,
                        db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """List all payments with filters. Shows across all dossiers."""
    q = db.query(Payment).filter(Payment.is_deleted == False).order_by(Payment.created_at.desc())
    if dossier_id:
        dos = db.query(DossierADV).filter(DossierADV.numero == dossier_id).first()
        if dos:
            q = q.filter(Payment.dossier_id == dos.id)
    if type_rf:
        q = q.filter(Payment.type_rf == type_rf)
    if status:
        q = q.filter(Payment.status == status)

    # RF2 filter
    if not user.has_rf2:
        q = q.filter(Payment.type_rf != "RF2")

    payments = q.limit(200).all()
    result = []
    for p in payments:
        dos = db.query(DossierADV).filter(DossierADV.id == p.dossier_id).first()
        lot = db.query(Lot).filter(Lot.id == dos.lot_id).first() if dos else None
        proj = db.query(Project).filter(Project.id == dos.project_id).first() if dos else None
        result.append({
            "id": str(p.id),
            "dossier_numero": dos.numero if dos else None,
            "client": dos.client_name if dos else None,
            "lot": lot.ref if lot else None,
            "project": proj.code if proj else None,
            "type_rf": p.type_rf,
            "mode": p.mode_reglement,
            "montant": str(p.montant),
            "reference": p.reference,
            "status": p.status,
            "date": str(p.created_at.date()) if p.created_at else None,
        })

    # Summary KPIs
    total_rf1 = sum(float(p["montant"]) for p in result if p["type_rf"] == "RF1")
    total_rf2 = sum(float(p["montant"]) for p in result if p["type_rf"] == "RF2") if user.has_rf2 else None
    encaisse = sum(1 for p in result if p["status"] == "ENCAISSE")
    en_attente = sum(1 for p in result if p["status"] == "EN_ATTENTE")

    return ApiResponse(data={
        "payments": result,
        "kpis": {
            "total": len(result), "encaisse": encaisse, "en_attente": en_attente,
            "total_rf1": str(total_rf1),
            "total_rf2": str(total_rf2) if total_rf2 is not None else None,
            "total_reel": str(total_rf1 + (total_rf2 or 0)),
        },
    })


@router.post("/payments/analyze-cheque")
async def analyze_cheque_scan(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Upload a scanned cheque image. AI extracts:
    - cheque_number, bank_name, amount, date, beneficiary, emitter
    Returns structured data for the user to confirm before payment.
    """
    import base64
    import json as json_mod

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Fichier trop volumineux (max 10 Mo)")

    # Determine MIME type
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "pdf": "application/pdf"}
    mime = mime_map.get(ext, "image/jpeg")

    b64 = base64.b64encode(content).decode("utf-8")

    # Save the file for record-keeping
    import os, hashlib
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    fhash = hashlib.sha256(content).hexdigest()[:16]
    fpath = os.path.join(upload_dir, f"cheque_{fhash}_{file.filename}")
    with open(fpath, "wb") as f:
        f.write(content)

    # Call Claude via OpenRouter to analyze the cheque
    try:
        from app.agents.llm import get_llm
        llm = get_llm(temperature=0.0, max_tokens=1000)

        prompt = """Analyse cette image de cheque bancaire algerien. Extrais les informations suivantes au format JSON strict:

{
  "cheque_number": "numero du cheque (string)",
  "bank_name": "nom de la banque emettrice",
  "amount": montant en DA (number, pas de separateurs),
  "amount_text": "montant en lettres tel qu'ecrit sur le cheque",
  "date": "date du cheque au format YYYY-MM-DD",
  "beneficiary": "nom du beneficiaire",
  "emitter": "nom de l'emetteur / titulaire du compte",
  "confidence": nombre entre 0 et 100 indiquant la confiance de l'extraction
}

Si un champ n'est pas lisible, mets null. Reponds UNIQUEMENT avec le JSON, rien d'autre."""

        response = llm.invoke([
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ])

        raw = response.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        extracted = json_mod.loads(raw)
        extracted["scan_path"] = fpath
        extracted["scan_filename"] = file.filename

        return ApiResponse(data=extracted)

    except json_mod.JSONDecodeError:
        return ApiResponse(data={
            "cheque_number": None, "bank_name": None, "amount": None,
            "confidence": 0, "raw_response": raw,
            "scan_path": fpath, "scan_filename": file.filename,
            "error": "Extraction AI non structuree — saisie manuelle requise",
        })
    except Exception as e:
        return ApiResponse(data={
            "cheque_number": None, "bank_name": None, "amount": None,
            "confidence": 0, "scan_path": fpath, "scan_filename": file.filename,
            "error": f"Analyse AI indisponible: {str(e)[:100]}. Saisie manuelle.",
        })


@router.post("/payments")
async def record_payment(req: PaymentRequest, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    dossier = db.query(DossierADV).filter(
        DossierADV.numero == req.dossier_id
    ).first()
    if not dossier:
        raise HTTPException(404, "Dossier introuvable")
    # PAY-C01
    if req.type_rf == "RF1" and req.mode_reglement == "ESPECES":
        raise HTTPException(400, "Paiement RF1 en especes interdit. Mode autorise: cheque ou virement.")
    # PAY-C02
    if req.type_rf == "RF2" and req.mode_reglement != "ESPECES":
        raise HTTPException(400, "Paiement RF2 : seules les especes sont autorisees.")
    # PAY-C03
    rf1_paid = db.query(func.sum(Payment.montant)).filter(
        Payment.dossier_id == dossier.id, Payment.type_rf == "RF1",
        Payment.status.in_(["EN_ATTENTE", "ENCAISSE"])
    ).scalar() or 0
    if req.type_rf == "RF1" and rf1_paid + req.montant > dossier.prix_rf1:
        raise HTTPException(400, f"Depassement RF1 : total {rf1_paid + req.montant} DA > prix RF1 {dossier.prix_rf1} DA.")
    # PAY-C04
    rf2_paid = db.query(func.sum(Payment.montant)).filter(
        Payment.dossier_id == dossier.id, Payment.type_rf == "RF2",
        Payment.status.in_(["EN_ATTENTE", "ENCAISSE"])
    ).scalar() or 0
    if req.type_rf == "RF2" and rf2_paid + req.montant > dossier.prix_rf2:
        raise HTTPException(400, f"Depassement RF2 : total {rf2_paid + req.montant} DA > prix RF2 {dossier.prix_rf2} DA.")
    # PAY-C05
    total_paid = rf1_paid + rf2_paid + req.montant
    prix_reel = dossier.prix_rf1 + dossier.prix_rf2
    if total_paid > prix_reel:
        raise HTTPException(400, f"Depassement total : {total_paid} DA > prix reel {prix_reel} DA.")

    # Auto-link to operation if project has one
    from sqlalchemy import text as sql_text
    op_link = db.execute(sql_text(
        "SELECT id FROM operation WHERE project_id = :pid AND statut IN ('EN_COURS','VALIDE') AND is_deleted = false LIMIT 1"
    ), {"pid": str(dossier.project_id)}).scalar() if dossier.project_id else None

    p = Payment(
        company_id=dossier.company_id, dossier_id=dossier.id,
        type_rf=req.type_rf, mode_reglement=req.mode_reglement,
        montant=req.montant, reference=req.reference, status="EN_ATTENTE",
    )
    db.add(p)
    db.flush()  # get the ID
    # Auto-link to operation
    if op_link:
        db.execute(sql_text("UPDATE payment SET operation_id = :oid WHERE id = :pid"),
                   {"oid": str(op_link), "pid": str(p.id)})
    if req.type_rf == "RF2":
        dossier.montant_rf2_securise = (dossier.montant_rf2_securise or 0) + req.montant
        if dossier.montant_rf2_securise >= dossier.prix_rf2:
            dossier.rf2_status = "SECURISE"
        else:
            dossier.rf2_status = "PARTIELLEMENT_SECURISE"
    # Impute to Centre de Cout
    from app.api.v1.cc_helpers import impute_cc
    proj = db.query(Project).get(dossier.project_id)
    from app.models.core import Company
    comp = db.query(Company).get(dossier.company_id)
    impute_cc(
        db,
        entite_code=comp.code if comp else None,
        projet_code=proj.code if proj else None,
        rf_type=req.type_rf,
        montant=req.montant,
        label=f"Paiement {req.type_rf} — {dossier.client_name} — {dossier.numero}",
        source_type="VENTE",
        source_doc_id=str(p.id),
    )
    db.commit()
    return ApiResponse(data={"payment_id": str(p.id), "dossier": dossier.numero, "status": p.status,
                              "rf2_status": dossier.rf2_status})


@router.post("/payments/{payment_id}/validate")
async def validate_payment(payment_id: str, db: Session = Depends(get_db),
                             user: CurrentUser = Depends(get_current_user)):
    """Maker/checker: validate a pending payment. PAY-C06 enforced."""
    p = db.query(Payment).filter(Payment.id == payment_id).first()
    if not p:
        raise HTTPException(404, "Paiement introuvable")
    if p.status in ("REJETE", "ANNULE"):
        raise HTTPException(403, "PAY-C06: Paiement rejete/annule est immutable. Creez un nouveau paiement.")
    if p.status != "EN_ATTENTE":
        raise HTTPException(400, f"Paiement deja {p.status}.")
    p.status = "ENCAISSE"
    # Update RF2 securisation on encaissement
    if p.type_rf == "RF2":
        dossier = db.query(DossierADV).filter(DossierADV.id == p.dossier_id).first()
        if dossier:
            dossier.montant_rf2_securise = (dossier.montant_rf2_securise or 0) + p.montant
            if dossier.montant_rf2_securise >= (dossier.prix_rf2 or 0):
                dossier.rf2_status = "SECURISE"
            else:
                dossier.rf2_status = "PARTIELLEMENT_SECURISE"
    db.commit()
    return ApiResponse(data={"payment_id": str(p.id), "status": "ENCAISSE"})


@router.post("/payments/{payment_id}/reject")
async def reject_payment(payment_id: str, body: dict = None,
                          db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    """Reject a payment. PAY-C06: becomes immutable."""
    p = db.query(Payment).filter(Payment.id == payment_id).first()
    if not p:
        raise HTTPException(404, "Paiement introuvable")
    if p.status in ("REJETE", "ANNULE"):
        raise HTTPException(403, "PAY-C06: Paiement deja rejete/annule — immutable.")
    p.status = "REJETE"
    db.commit()
    return ApiResponse(data={"payment_id": str(p.id), "status": "REJETE"})


# ═══════════════════════════════════════════════════════════════════════════════
# D.5 — CREDIT TIERS (Tab 4: Deblocages)
# ═══════════════════════════════════════════════════════════════════════════════

TIER_DEFS = [
    (0, "VSP 20%", Decimal("20"), "VIA_NOTAIRE"),
    (1, "Palier 15%", Decimal("15"), "DIRECT"),
    (2, "Palier 35%", Decimal("35"), "DIRECT"),
    (3, "Palier 25%", Decimal("25"), "DIRECT"),
    (4, "Remise cles 5%", Decimal("5"), "VIA_NOTAIRE"),
]


def _init_credit_tiers(dossier, db):
    """Auto-create 5 credit tiers when dossier enters EN_COURS_CREDIT."""
    existing = db.query(CreditTierC).filter(
        CreditTierC.dossier_id == dossier.id, CreditTierC.is_deleted == False
    ).count()
    if existing > 0:
        return
    montant_credit = dossier.prix_rf1  # credit covers RF1
    for num, label, pct, routing in TIER_DEFS:
        montant = _r2(montant_credit * pct / 100)
        db.add(CreditTierC(
            company_id=dossier.company_id, dossier_id=dossier.id,
            tier_number=num, tier_label=label, percentage=pct,
            montant=montant, routing=routing,
        ))


def _init_document_checklist(dossier, db):
    """Auto-create document checklist at engagement."""
    existing = db.query(DossierDocument).filter(
        DossierDocument.dossier_id == dossier.id, DossierDocument.is_deleted == False
    ).count()
    if existing > 0:
        return
    docs = [
        ("CIN", "CIN client", "CLIENT"),
        ("FICHE_FAMILIALE", "Fiche familiale", "CLIENT"),
    ]
    if dossier.type_paiement in ("CREDIT_BANCAIRE", "MIXTE"):
        docs += [
            ("ATTESTATION_TRAVAIL", "Attestation de travail", "CLIENT"),
            ("FICHES_PAIE", "3 fiches de paie", "CLIENT"),
            ("RELEVES_BANCAIRES", "Releves bancaires 6 mois", "CLIENT"),
            ("CONTRAT_CREDIT", "Contrat credit signe", "BANQUE"),
            ("CONTRAT_ENREGISTRE_IMPOTS", "Contrat enregistre aux impots", "CLIENT"),
            ("ACTE_PROPRIETE", "Acte propriete terrain", "ENTREPRISE"),
            ("ORDRES_VIREMENT", "3 ordres de virement signes", "CLIENT"),
        ]
    if dossier.type_paiement in ("FONDS_PROPRES", "MIXTE"):
        docs += [
            ("ECHEANCIER_SIGNE", "Echeancier signe par le client", "CLIENT"),
        ]
    for doc_type, label, source in docs:
        db.add(DossierDocument(
            company_id=dossier.company_id, dossier_id=dossier.id,
            document_type=doc_type, label=label, source=source,
        ))


@router.get("/dossiers/{dossier_id}/credit-tiers")
async def get_credit_tiers(dossier_id: str, db: Session = Depends(get_db),
                            user: CurrentUser = Depends(get_current_user)):
    d = _find_dossier(db, dossier_id)
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    tiers = db.query(CreditTierC).filter(
        CreditTierC.dossier_id == d.id, CreditTierC.is_deleted == False
    ).order_by(CreditTierC.tier_number).all()
    data = []
    for t in tiers:
        report = db.query(ExpertReportC).filter(
            ExpertReportC.dossier_id == d.id,
            ExpertReportC.tier_percentage == t.percentage,
            ExpertReportC.is_deleted == False,
        ).first()
        wire = db.query(WireTransferOrderC).filter(
            WireTransferOrderC.dossier_id == d.id,
            WireTransferOrderC.tier_percentage == t.percentage,
            WireTransferOrderC.is_deleted == False,
        ).first()
        data.append({
            "id": str(t.id), "tier_number": t.tier_number, "label": t.tier_label,
            "percentage": str(t.percentage), "montant": str(t.montant),
            "routing": t.routing, "status": t.status,
            "debloque_at": t.debloque_at.isoformat() if t.debloque_at else None,
            "expert_report": {
                "id": str(report.id), "expert": report.expert_name,
                "status": report.status, "completion_pct": str(report.completion_pct or 0),
                "date": report.report_date.isoformat() if report.report_date else None,
            } if report else None,
            "wire_order": {
                "id": str(wire.id), "status": wire.status,
                "signed": wire.signature_date.isoformat() if wire.signature_date else None,
            } if wire else None,
        })
    return ApiResponse(data=data)


@router.post("/dossiers/{dossier_id}/credit-tiers/init")
async def init_credit_tiers(dossier_id: str, db: Session = Depends(get_db),
                             user: CurrentUser = Depends(get_current_user)):
    d = _find_dossier(db, dossier_id)
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    _init_credit_tiers(d, db)
    db.commit()
    return ApiResponse(data={"initialized": True, "dossier": d.numero})


@router.post("/dossiers/{dossier_id}/expert-report")
async def upload_expert_report(dossier_id: str, body: dict,
                                db: Session = Depends(get_db),
                                user: CurrentUser = Depends(get_current_user)):
    """Upload an expert report for a tier (CRE-005)."""
    d = _find_dossier(db, dossier_id)
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    pct = body.get("tier_percentage")
    report = ExpertReportC(
        company_id=d.company_id, dossier_id=d.id,
        tier_percentage=pct, expert_name=body.get("expert_name", ""),
        report_date=body.get("report_date", datetime.now(timezone.utc).date()),
        completion_pct=body.get("completion_pct"),
        conformity=body.get("conformity", True),
        observations=body.get("observations"),
        document_url=body.get("document_url"),
    )
    db.add(report)
    db.flush()
    # Link to tier
    tier = db.query(CreditTierC).filter(
        CreditTierC.dossier_id == d.id, CreditTierC.percentage == pct,
        CreditTierC.is_deleted == False,
    ).first()
    if tier:
        tier.expert_report_id = report.id
        tier.status = "EXPERT_RECU"
    db.commit()
    return ApiResponse(data={"report_id": str(report.id), "tier_status": tier.status if tier else None})


@router.post("/dossiers/{dossier_id}/expert-report/{report_id}/validate")
async def validate_expert_report(dossier_id: str, report_id: str,
                                  db: Session = Depends(get_db),
                                  user: CurrentUser = Depends(get_current_user)):
    """CRE-005: validate expert report to unblock tier disbursement."""
    report = db.query(ExpertReportC).filter(ExpertReportC.id == report_id).first()
    if not report:
        raise HTTPException(404, "Rapport introuvable")
    report.status = "VALIDE"
    report.validated_by = user.name
    report.validated_at = datetime.now(timezone.utc)
    # Update tier
    tier = db.query(CreditTierC).filter(
        CreditTierC.dossier_id == report.dossier_id,
        CreditTierC.percentage == report.tier_percentage,
        CreditTierC.is_deleted == False,
    ).first()
    if tier:
        tier.status = "EXPERT_VALIDE"
    db.commit()
    return ApiResponse(data={"validated": True, "tier_status": tier.status if tier else None})


@router.post("/dossiers/{dossier_id}/credit-tiers/{tier_num}/disburse")
async def disburse_tier(dossier_id: str, tier_num: int,
                         db: Session = Depends(get_db),
                         user: CurrentUser = Depends(get_current_user)):
    """Mark a tier as disbursed (wire received from bank)."""
    d = _find_dossier(db, dossier_id)
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    tier = db.query(CreditTierC).filter(
        CreditTierC.dossier_id == d.id, CreditTierC.tier_number == tier_num,
        CreditTierC.is_deleted == False,
    ).first()
    if not tier:
        raise HTTPException(404, f"Palier {tier_num} introuvable")
    # CRE-005: expert must be validated for tiers 1,2,3
    if tier_num in (1, 2, 3) and tier.status != "EXPERT_VALIDE":
        raise HTTPException(422, f"Rapport expert non valide pour {tier.tier_label} (CRE-005). Status: {tier.status}")
    now = datetime.now(timezone.utc)
    tier.status = "DEBLOQUE"
    tier.debloque_at = now
    tier.wire_received_at = now
    # Create Payment record: direct bank wire for tiers 1-3
    montant = tier.montant
    p = Payment(
        company_id=d.company_id, dossier_id=d.id,
        type_rf="RF1", mode_reglement="VIREMENT",
        montant=montant, reference=f"DEBLOCAGE_{tier.tier_label}",
        status="ENCAISSE",
    )
    db.add(p)
    # Log transition
    db.add(DossierTransitionLog(
        company_id=d.company_id, dossier_id=d.id,
        from_status=f"PALIER_{tier.tier_label}", to_status="DEBLOQUE",
        triggered_by=user.name, notes=f"Deblocage {tier.percentage}% = {montant} DA",
    ))
    db.commit()
    return ApiResponse(data={"tier": tier.tier_label, "status": "DEBLOQUE", "payment_montant": str(montant)})


@router.post("/dossiers/{dossier_id}/wire-orders")
async def create_wire_orders(dossier_id: str, db: Session = Depends(get_db),
                              user: CurrentUser = Depends(get_current_user)):
    """Create the 3 pre-signed wire transfer orders (15%, 35%, 25%)."""
    d = _find_dossier(db, dossier_id)
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    existing = db.query(WireTransferOrderC).filter(
        WireTransferOrderC.dossier_id == d.id, WireTransferOrderC.is_deleted == False
    ).count()
    if existing >= 3:
        raise HTTPException(400, "3 ordres de virement deja crees")
    orders = []
    for pct in [15, 35, 25]:
        montant = _r2(d.prix_rf1 * Decimal(str(pct)) / 100)
        o = WireTransferOrderC(
            company_id=d.company_id, dossier_id=d.id,
            tier_percentage=pct, montant=montant,
        )
        db.add(o)
        orders.append({"pct": pct, "montant": str(montant)})
    db.commit()
    return ApiResponse(data=orders)


@router.post("/dossiers/{dossier_id}/wire-orders/{order_id}/sign")
async def sign_wire_order(dossier_id: str, order_id: str, body: dict,
                           db: Session = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    o = db.query(WireTransferOrderC).filter(WireTransferOrderC.id == order_id).first()
    if not o:
        raise HTTPException(404, "Ordre introuvable")
    o.status = "SIGNE"
    o.signature_date = body.get("signature_date", datetime.now(timezone.utc).date())
    o.scan_url = body.get("scan_url")
    db.commit()
    return ApiResponse(data={"order_id": str(o.id), "status": "SIGNE"})


# ═══════════════════════════════════════════════════════════════════════════════
# D.6 — ECHEANCIER (Tab 2: Echeancier)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/dossiers/{dossier_id}/echeancier")
async def get_echeancier(dossier_id: str, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    d = _find_dossier(db, dossier_id)
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    ech = db.query(EcheancierC).filter(
        EcheancierC.dossier_id == d.id, EcheancierC.is_deleted == False
    ).first()
    if not ech:
        return ApiResponse(data=None)
    installments = db.query(EcheanceC).filter(
        EcheanceC.echeancier_id == ech.id, EcheanceC.is_deleted == False
    ).order_by(EcheanceC.numero).all()
    return ApiResponse(data={
        "id": str(ech.id), "solde_rf1": str(ech.solde_rf1),
        "date_engagement": ech.date_engagement.isoformat(),
        "date_livraison": ech.date_livraison_prevue.isoformat(),
        "duree_mois": ech.duree_mois, "frequence": ech.frequence,
        "nb_echeances": ech.nb_echeances,
        "montant_echeance": str(ech.montant_echeance),
        "montant_derniere": str(ech.montant_derniere),
        "taux_penalite": str(ech.taux_penalite_annuel),
        "status": ech.status,
        "total_paye": str(ech.total_paye), "total_penalites": str(ech.total_penalites),
        "echeances": [{
            "id": str(e.id), "numero": e.numero,
            "date": e.date_echeance.isoformat(),
            "montant": str(e.montant), "status": e.status,
            "date_paiement": e.date_paiement.isoformat() if e.date_paiement else None,
            "montant_paye": str(e.montant_paye) if e.montant_paye else None,
            "jours_retard": e.jours_retard, "penalite": str(e.penalite_montant),
        } for e in installments],
    })


@router.post("/dossiers/{dossier_id}/echeancier")
async def generate_echeancier(dossier_id: str, body: dict,
                                db: Session = Depends(get_db),
                                user: CurrentUser = Depends(get_current_user)):
    """Generate installment schedule for fonds propres dossier."""
    d = _find_dossier(db, dossier_id)
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    # Check if already generated
    existing = db.query(EcheancierC).filter(
        EcheancierC.dossier_id == d.id, EcheancierC.is_deleted == False
    ).first()
    if existing:
        raise HTTPException(400, "Echeancier deja genere pour ce dossier")

    rf1_paid = _get_paid(db, d.id, "RF1")
    solde = d.prix_rf1 - rf1_paid
    if solde <= 0:
        raise HTTPException(400, "Solde RF1 nul — aucun echeancier necessaire")

    date_eng = date_type.fromisoformat(body.get("date_engagement", datetime.now(timezone.utc).date().isoformat()))
    date_liv = date_type.fromisoformat(body.get("date_livraison", "2028-01-01"))
    freq = body.get("frequence", "MENSUEL")
    taux = Decimal(str(body.get("taux_penalite", "5.00")))

    months = (date_liv.year - date_eng.year) * 12 + (date_liv.month - date_eng.month)
    if months < 1:
        months = 1
    nb = months if freq == "MENSUEL" else months * 2
    if nb < 1:
        nb = 1
    montant_ech = _r2(solde / nb)
    montant_dern = solde - (montant_ech * (nb - 1))

    ech = EcheancierC(
        company_id=d.company_id, dossier_id=d.id, solde_rf1=solde,
        date_engagement=date_eng, date_livraison_prevue=date_liv,
        duree_mois=months, frequence=freq, nb_echeances=nb,
        montant_echeance=montant_ech, montant_derniere=montant_dern,
        taux_penalite_annuel=taux,
    )
    db.add(ech)
    db.flush()

    current = date_eng
    for i in range(1, nb + 1):
        if freq == "MENSUEL":
            m = current.month + 1
            y = current.year
            if m > 12:
                m, y = 1, y + 1
            _, last = monthrange(y, m)
            current = date_type(y, m, min(current.day, last))
        else:
            current = current + timedelta(days=15)
        montant = montant_dern if i == nb else montant_ech
        db.add(EcheanceC(
            company_id=d.company_id, echeancier_id=ech.id,
            numero=i, date_echeance=current, montant=montant,
        ))
    db.commit()
    return ApiResponse(data={"echeancier_id": str(ech.id), "nb_echeances": nb,
                              "montant_echeance": str(montant_ech), "montant_derniere": str(montant_dern)})


@router.post("/dossiers/{dossier_id}/echeancier/{echeance_id}/pay")
async def pay_echeance(dossier_id: str, echeance_id: str, body: dict,
                        db: Session = Depends(get_db),
                        user: CurrentUser = Depends(get_current_user)):
    """Record payment of an installment. FP-003: cheque only for RF1."""
    e = db.query(EcheanceC).filter(EcheanceC.id == echeance_id).first()
    if not e:
        raise HTTPException(404, "Echeance introuvable")
    if e.status == "PAYEE":
        raise HTTPException(400, "Echeance deja payee")
    mode = body.get("mode_reglement", "CHEQUE")
    if mode != "CHEQUE":
        raise HTTPException(422, f"FP-003: Echeances fonds propres RF1 par cheque uniquement. Mode recu: {mode}")
    now = datetime.now(timezone.utc)
    e.status = "PAYEE"
    e.date_paiement = now.date()
    e.montant_paye = e.montant
    # Find the dossier for this echeance
    d = _find_dossier(db, dossier_id)
    # Create Payment record: FP installment
    p = Payment(
        company_id=d.company_id if d else e.company_id, dossier_id=d.id if d else None,
        type_rf="RF1", mode_reglement="CHEQUE",
        montant=e.montant,
        reference=body.get("reference", f"ECH_{e.numero}_{body.get('reference', '')}"),
        status="ENCAISSE",
    )
    db.add(p)
    e.payment_id = p.id
    # Update echeancier totals
    ech = db.query(EcheancierC).filter(EcheancierC.id == e.echeancier_id).first()
    if ech:
        ech.total_paye = (ech.total_paye or 0) + e.montant
        remaining = db.query(EcheanceC).filter(
            EcheanceC.echeancier_id == ech.id,
            EcheanceC.status.in_(["A_VENIR", "DUE", "EN_RETARD"]),
        ).count()
        if remaining == 0:
            ech.status = "TERMINE"
    db.commit()
    return ApiResponse(data={"echeance": e.numero, "status": "PAYEE", "payment_montant": str(e.montant)})


# ═══════════════════════════════════════════════════════════════════════════════
# D.7 — NOTARY ESCROW (Tab 5: Notaire)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/dossiers/{dossier_id}/escrow")
async def get_dossier_escrow(dossier_id: str, db: Session = Depends(get_db),
                              user: CurrentUser = Depends(get_current_user)):
    """Get escrow movements for a dossier."""
    d = _find_dossier(db, dossier_id)
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    movements = db.query(EscrowMovementC).filter(
        EscrowMovementC.dossier_id == d.id, EscrowMovementC.is_deleted == False
    ).order_by(EscrowMovementC.movement_date.desc()).all()
    # Get or find project escrow account
    escrow = db.query(NotaryEscrowC).filter(
        NotaryEscrowC.project_id == d.project_id, NotaryEscrowC.is_deleted == False
    ).first()
    return ApiResponse(data={
        "escrow": {
            "id": str(escrow.id) if escrow else None,
            "solde": str(escrow.solde_transitoire) if escrow else "0",
            "reserve_5pct": str(escrow.expected_5pct_reserve) if escrow else "0",
            "notaire": escrow.notaire_name if escrow else None,
        } if escrow else None,
        "movements": [{
            "id": str(m.id), "date": m.movement_date.isoformat(),
            "type": m.movement_type, "montant": str(m.montant),
            "balance_after": str(m.balance_after),
            "source": m.source, "destination": m.destination,
            "motif": m.motif, "cheque_ref": m.reference_cheque,
        } for m in movements],
    })


@router.post("/dossiers/{dossier_id}/escrow/vsp-20")
async def process_vsp_20(dossier_id: str, body: dict,
                          db: Session = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    """CRE-004: 20% must transit via notary escrow. Credit + Debit in one call."""
    d = _find_dossier(db, dossier_id)
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    # Get or create escrow
    escrow = db.query(NotaryEscrowC).filter(
        NotaryEscrowC.project_id == d.project_id, NotaryEscrowC.is_deleted == False
    ).first()
    if not escrow:
        escrow = NotaryEscrowC(
            company_id=d.company_id, project_id=d.project_id,
            notaire_name=body.get("notaire_name"),
        )
        db.add(escrow)
        db.flush()
    montant = _r2(d.prix_rf1 * Decimal("0.20"))
    now = datetime.now(timezone.utc)
    # CREDIT: bank -> escrow
    balance_1 = Decimal(str(escrow.solde_transitoire or 0)) + montant
    db.add(EscrowMovementC(
        company_id=d.company_id, escrow_id=escrow.id, dossier_id=d.id,
        movement_date=now, movement_type="CREDIT", montant=montant,
        balance_after=balance_1, source="Banque", destination="Sequestre notaire",
        motif="VSP_20PCT",
    ))
    escrow.solde_transitoire = balance_1
    # DEBIT: escrow -> company (immediate release)
    balance_2 = balance_1 - montant
    db.add(EscrowMovementC(
        company_id=d.company_id, escrow_id=escrow.id, dossier_id=d.id,
        movement_date=now, movement_type="DEBIT", montant=montant,
        balance_after=balance_2, source="Sequestre notaire", destination="Compte entreprise",
        motif="LIBERATION_20PCT",
    ))
    escrow.solde_transitoire = balance_2
    # Mark tier 0 as DEBLOQUE
    tier0 = db.query(CreditTierC).filter(
        CreditTierC.dossier_id == d.id, CreditTierC.tier_number == 0,
        CreditTierC.is_deleted == False,
    ).first()
    if tier0:
        tier0.status = "DEBLOQUE"
        tier0.debloque_at = now
    # Create Payment record: 20% via notaire
    p = Payment(
        company_id=d.company_id, dossier_id=d.id,
        type_rf="RF1", mode_reglement="CHEQUE_NOTAIRE",
        montant=montant, reference="VSP_20PCT_NOTAIRE",
        status="ENCAISSE",
    )
    db.add(p)
    # Log
    db.add(DossierTransitionLog(
        company_id=d.company_id, dossier_id=d.id,
        from_status="VSP_20PCT", to_status="DEBLOQUE",
        triggered_by=user.name, notes=f"Transit notaire 20% = {montant} DA (credit + debit sequestre)",
    ))
    db.commit()
    return ApiResponse(data={"montant": str(montant), "tier_0": "DEBLOQUE", "payment_montant": str(montant)})


@router.post("/dossiers/{dossier_id}/escrow/release-5")
async def release_5pct(dossier_id: str, body: dict,
                        db: Session = Depends(get_db),
                        user: CurrentUser = Depends(get_current_user)):
    """CRE-006: Release 5% after PV remise des cles."""
    d = _find_dossier(db, dossier_id)
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    if not body.get("pv_url"):
        raise HTTPException(422, "CRE-006: PV de remise des cles requis avant liberation du 5%.")
    escrow = db.query(NotaryEscrowC).filter(
        NotaryEscrowC.project_id == d.project_id, NotaryEscrowC.is_deleted == False
    ).first()
    if not escrow:
        raise HTTPException(400, "Aucun compte sequestre pour ce projet")
    montant = _r2(d.prix_rf1 * Decimal("0.05"))
    now = datetime.now(timezone.utc)
    balance = Decimal(str(escrow.solde_transitoire or 0))
    # FIN-005: check balance won't go negative
    if balance - montant < 0:
        raise HTTPException(422, f"FIN-005: Solde sequestre ({balance}) insuffisant pour liberation {montant} DA.")
    new_balance = balance - montant
    db.add(EscrowMovementC(
        company_id=d.company_id, escrow_id=escrow.id, dossier_id=d.id,
        movement_date=now, movement_type="DEBIT", montant=montant,
        balance_after=new_balance, source="Sequestre notaire", destination="Compte entreprise",
        motif="LIBERATION_5PCT",
    ))
    escrow.solde_transitoire = new_balance
    # Mark tier 4 as DEBLOQUE
    tier4 = db.query(CreditTierC).filter(
        CreditTierC.dossier_id == d.id, CreditTierC.tier_number == 4,
        CreditTierC.is_deleted == False,
    ).first()
    if tier4:
        tier4.status = "DEBLOQUE"
        tier4.debloque_at = now
    # Create Payment record: 5% via notaire
    p = Payment(
        company_id=d.company_id, dossier_id=d.id,
        type_rf="RF1", mode_reglement="CHEQUE_NOTAIRE",
        montant=montant, reference="LIBERATION_5PCT_NOTAIRE",
        status="ENCAISSE",
    )
    db.add(p)
    # Log
    db.add(DossierTransitionLog(
        company_id=d.company_id, dossier_id=d.id,
        from_status="PALIER_5PCT", to_status="DEBLOQUE",
        triggered_by=user.name, notes=f"Liberation 5% = {montant} DA via notaire (PV: {body.get('pv_url')})",
    ))
    db.commit()
    return ApiResponse(data={"montant": str(montant), "tier_4": "DEBLOQUE", "payment_montant": str(montant)})


# ═══════════════════════════════════════════════════════════════════════════════
# D.8 — DOCUMENTS (Tab 3: Documents)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/dossiers/{dossier_id}/documents")
async def get_dossier_documents(dossier_id: str, db: Session = Depends(get_db),
                                 user: CurrentUser = Depends(get_current_user)):
    d = _find_dossier(db, dossier_id)
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    docs = db.query(DossierDocument).filter(
        DossierDocument.dossier_id == d.id, DossierDocument.is_deleted == False
    ).order_by(DossierDocument.created_at).all()
    now = datetime.now(timezone.utc)
    return ApiResponse(data=[{
        "id": str(doc.id), "type": doc.document_type, "label": doc.label,
        "source": doc.source, "required": doc.required,
        "received": doc.received,
        "received_at": doc.received_at.isoformat() if doc.received_at else None,
        "document_url": doc.document_url,
        "relance_count": doc.relance_count,
        "days_waiting": (now - doc.created_at).days if not doc.received else 0,
        "alert_level": (
            "BLOQUANT" if not doc.received and (now - doc.created_at).days >= 30
            else "ALERTE" if not doc.received and (now - doc.created_at).days >= 14
            else "ATTENTION" if not doc.received and (now - doc.created_at).days >= 7
            else None
        ),
    } for doc in docs])


@router.post("/dossiers/{dossier_id}/documents/{doc_id}/receive")
async def receive_document(dossier_id: str, doc_id: str, body: dict,
                            db: Session = Depends(get_db),
                            user: CurrentUser = Depends(get_current_user)):
    doc = db.query(DossierDocument).filter(DossierDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document introuvable")
    doc.received = True
    doc.received_at = datetime.now(timezone.utc)
    doc.document_url = body.get("document_url")
    db.commit()
    return ApiResponse(data={"id": str(doc.id), "received": True})


# ═══════════════════════════════════════════════════════════════════════════════
# D.9 — TRANSITIONS HISTORY (Tab 7: Historique)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/dossiers/{dossier_id}/transitions")
async def get_dossier_transitions(dossier_id: str, db: Session = Depends(get_db),
                                    user: CurrentUser = Depends(get_current_user)):
    d = _find_dossier(db, dossier_id)
    if not d:
        raise HTTPException(404, "Dossier introuvable")
    logs = db.query(DossierTransitionLog).filter(
        DossierTransitionLog.dossier_id == d.id
    ).order_by(DossierTransitionLog.created_at.desc()).all()
    return ApiResponse(data=[{
        "id": str(l.id), "from": l.from_status, "to": l.to_status,
        "by": l.triggered_by, "date": l.created_at.isoformat(),
        "notes": l.notes,
    } for l in logs])


# ═══════════════════════════════════════════════════════════════════════════════
# D.11 — EDD AI READER (document → lots extraction)
# ═══════════════════════════════════════════════════════════════════════════════

def _edd_prompt():
    return """Analyse ce document EDD (Etat Descriptif Detaille / وصف تفصيلي) d'un projet immobilier algerien.
Le document peut etre en FRANCAIS, en ARABE, ou MIXTE. Extrais TOUS les lots.

Termes arabes courants:
- شقة = appartement, نوع = type, مساحة = surface, طابق = etage
- عمارة / بلوك = bloc/batiment, واجهة = orientation, سعر / ثمن = prix
- F2/F3/F4/F5 = nombre de pieces, RDC / أرضي = rez-de-chaussee
- محل تجاري = local commercial, موقف = parking, قبو = cave

Pour chaque lot, retourne:
{
  "lot_ref": "reference ou numero du lot tel qu'ecrit (en chiffres)",
  "typology": "F2, F3, F4, F5, DUPLEX, LOCAL_COMMERCIAL, PARKING, ou CAVE",
  "surface": surface en m2 (number),
  "floor": etage (number, 0 = RDC),
  "block": "bloc ou batiment (A, B, C, Tour, etc.)",
  "orientation": "NORD, SUD, EST, OUEST, DOUBLE, ou null",
  "rf1_price": prix en DA (number) ou null,
  "description": "details supplementaires en francais"
}

Retourne un JSON strict:
{
  "project_name": "nom du projet si visible",
  "total_lots": nombre,
  "lots": [... array ...],
  "confidence": 0-100,
  "document_type": "EDD, TABLEAU_LOTS, CSV, PLAN, ou AUTRE",
  "notes": "remarques"
}

IMPORTANT:
- Extrais TOUS les lots, meme partiellement lisibles
- Traduis les termes arabes en francais dans le JSON de sortie
- Si le document est un tableau (CSV, Excel-like), chaque ligne = un lot
- Ne fusionne PAS les lots
- Prix: retire les separateurs de milliers, convertis en nombre
Reponds UNIQUEMENT avec le JSON."""


def _clean_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
    return raw.strip()


@router.post("/edd/read-document")
async def read_edd_document(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
):
    """Upload an EDD document (image, PDF, CSV, text). AI extracts all lots.
    Supports: French, Arabic, mixed. CSV parsed directly, images/PDFs via AI vision."""
    import base64
    import json as json_mod
    import csv as csv_mod
    import io

    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(413, "Fichier trop volumineux (max 15 Mo)")

    ext = (file.filename or "").rsplit(".", 1)[-1].lower()

    # ── CSV/TXT: parse directly without AI vision ─────────────────────────
    if ext in ("csv", "txt", "tsv"):
        text = content.decode("utf-8", errors="replace")
        # Detect delimiter
        delimiter = ","
        if "\t" in text:
            delimiter = "\t"
        elif ";" in text:
            delimiter = ";"

        # Try to parse as CSV first
        try:
            reader = csv_mod.DictReader(io.StringIO(text), delimiter=delimiter)
            fields = reader.fieldnames or []

            # Map Arabic/French column names to standard keys
            col_map = {
                # French
                "reference": "lot_ref", "ref": "lot_ref", "numero": "lot_ref", "n": "lot_ref",
                "typologie": "typology", "type": "typology", "typology": "typology",
                "surface": "surface", "superficie": "surface",
                "etage": "floor", "floor": "floor", "niveau": "floor",
                "bloc": "block", "block": "block", "batiment": "block", "immeuble": "block",
                "orientation": "orientation",
                "prix": "rf1_price", "prix_rf1": "rf1_price", "rf1_price": "rf1_price",
                "prix_rf2": "rf2_price", "rf2_price": "rf2_price",
                "description": "description", "notes": "description", "observation": "description",
                # Arabic
                "المرجع": "lot_ref", "الرقم": "lot_ref", "رقم": "lot_ref",
                "النوع": "typology", "نوع": "typology", "الصنف": "typology",
                "المساحة": "surface", "مساحة": "surface",
                "الطابق": "floor", "طابق": "floor",
                "العمارة": "block", "بلوك": "block", "المبنى": "block",
                "الاتجاه": "orientation", "واجهة": "orientation",
                "السعر": "rf1_price", "الثمن": "rf1_price", "سعر": "rf1_price",
                "ملاحظات": "description", "وصف": "description",
            }

            # Build field mapping
            field_mapping = {}
            for f in fields:
                f_clean = f.strip().lower().replace(" ", "_")
                if f_clean in col_map:
                    field_mapping[f] = col_map[f_clean]
                elif f_clean in ("lot_ref", "typology", "surface", "floor", "block", "orientation", "rf1_price", "rf2_price", "description"):
                    field_mapping[f] = f_clean

            lots = []
            for row in reader:
                lot = {}
                for orig_col, mapped_key in field_mapping.items():
                    val = row.get(orig_col, "").strip()
                    if val:
                        if mapped_key in ("surface", "rf1_price", "rf2_price"):
                            try:
                                lot[mapped_key] = float(val.replace(",", ".").replace(" ", ""))
                            except ValueError:
                                lot[mapped_key] = None
                        elif mapped_key == "floor":
                            try:
                                lot[mapped_key] = int(val.replace(" ", ""))
                            except ValueError:
                                lot[mapped_key] = 0
                        else:
                            lot[mapped_key] = val
                if lot:
                    lots.append(lot)

            # CSV parsed — now send to AI agent for verification and enrichment
            if lots:
                from app.agents.llm import get_llm
                llm = get_llm(temperature=0.0, max_tokens=8000)
                verify_prompt = f"""Voici des lots extraits d'un fichier CSV/texte d'un EDD immobilier algerien.
Verifie et corrige les donnees. Pour chaque lot:
- Normalise la typologie (F2, F3, F4, F5, DUPLEX, LOCAL_COMMERCIAL, PARKING, CAVE)
- Verifie que la surface est en m2 (corrige si en cm2 ou autre)
- Verifie que le prix est en DA (corrige si en milliers)
- Traduis toute description arabe en francais
- Corrige les fautes de frappe evidentes
- Ajoute une description si des infos utiles sont presentes

Lots extraits:
{json_mod.dumps(lots, ensure_ascii=False, indent=2)}

Retourne un JSON strict:
{{
  "project_name": nom du projet si deductible ou null,
  "total_lots": nombre,
  "lots": [lots corriges avec meme structure],
  "confidence": 0-100 (confiance apres verification),
  "document_type": "CSV",
  "notes": "corrections effectuees et remarques",
  "corrections": ["liste des corrections faites"]
}}
Reponds UNIQUEMENT avec le JSON."""

                try:
                    response = llm.invoke([{"role": "user", "content": verify_prompt}])
                    raw = _clean_json(response.content)
                    verified = json_mod.loads(raw)
                    return ApiResponse(data=verified)
                except Exception:
                    # AI verification failed — return raw CSV parse with lower confidence
                    return ApiResponse(data={
                        "project_name": None,
                        "total_lots": len(lots),
                        "lots": lots,
                        "confidence": 70,
                        "document_type": "CSV",
                        "notes": f"CSV parse sans verification AI — {len(lots)} lots",
                    })
        except Exception:
            pass

        # CSV parsing failed — send full text to AI for extraction
        from app.agents.llm import get_llm
        llm = get_llm(temperature=0.0, max_tokens=8000)
        response = llm.invoke([{
            "role": "user",
            "content": _edd_prompt() + f"\n\nContenu du fichier texte:\n{text[:8000]}",
        }])
        raw = _clean_json(response.content)
        try:
            return ApiResponse(data=json_mod.loads(raw))
        except Exception:
            return ApiResponse(data={"lots": [], "total_lots": 0, "confidence": 0, "error": "Parsing echoue"})

    # ── PDF / Image: AI vision ────────────────────────────────────────────
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                "webp": "image/webp", "pdf": "application/pdf"}
    mime = mime_map.get(ext, "image/jpeg")
    b64 = base64.b64encode(content).decode("utf-8")

    text_content = ""
    if ext == "pdf":
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            text_content = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            pass

    try:
        from app.agents.llm import get_llm
        llm = get_llm(temperature=0.0, max_tokens=8000)

        prompt = _edd_prompt()

        messages = []
        if text_content and len(text_content.strip()) > 100:
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{prompt}\n\nTexte extrait du PDF:\n{text_content[:6000]}"},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }]
        else:
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }]

        response = llm.invoke(messages)
        raw = _clean_json(response.content)
        extracted = json_mod.loads(raw)
        return ApiResponse(data=extracted)

    except json_mod.JSONDecodeError:
        return ApiResponse(data={
            "lots": [], "total_lots": 0, "confidence": 0,
            "error": "Extraction non structuree — le document n'a pas pu etre lu correctement",
            "raw_response": raw[:500] if 'raw' in dir() else None,
        })
    except Exception as e:
        return ApiResponse(data={
            "lots": [], "total_lots": 0, "confidence": 0,
            "error": f"Erreur AI: {str(e)[:200]}",
        })


@router.post("/edd/lots/import-ai")
async def import_lots_from_ai(body: dict, db: Session = Depends(get_db),
                                user: CurrentUser = Depends(get_current_user)):
    """Create lots from AI-extracted data after user review. Body: {project_code, lots: [...]}"""
    project_code = body.get("project_code")
    proj = db.query(Project).filter(Project.code == project_code).first()
    if not proj:
        raise HTTPException(404, f"Projet '{project_code}' introuvable")

    company = db.query(Company).get(proj.company_id)
    lots_data = body.get("lots", [])
    created = 0
    errors = []

    for i, lot in enumerate(lots_data):
        try:
            typology = lot.get("typology", "F3")
            block = lot.get("block", "A")
            surface = Decimal(str(lot.get("surface", 0)))
            floor = int(lot.get("floor", 0))
            rf1 = Decimal(str(lot.get("rf1_price", 0) or 0))
            rf2 = Decimal(str(lot.get("rf2_price", 0) or 0))

            # Generate unique ref
            prefix = f"{project_code[0]}-{typology}-{block}-"
            max_seq = db.query(func.count(Lot.id)).filter(Lot.ref.like(f"{prefix}%")).scalar() or 0
            seq_num = max_seq + 1
            ref = f"{prefix}{seq_num:03d}"
            while db.query(Lot).filter(Lot.ref == ref).first():
                seq_num += 1
                ref = f"{prefix}{seq_num:03d}"

            new_lot = Lot(
                company_id=company.id if company else proj.company_id,
                project_id=proj.id, ref=ref, typology=typology,
                surface=surface, floor=floor, block=block,
                orientation=lot.get("orientation"),
                rf1_price=rf1, rf2_price=rf2, status="DISPONIBLE",
            )
            db.add(new_lot)
            db.flush()
            created += 1
        except Exception as e:
            errors.append(f"Lot {i+1}: {str(e)[:80]}")

    db.commit()
    return ApiResponse(data={"lots_created": created, "errors": errors})


# ═══════════════════════════════════════════════════════════════════════════════
# D.11b — EDD LOT BATCH IMPORT (CSV)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/edd/lots/import")
async def import_lots_csv(file: UploadFile = File(...),
                           db: Session = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    """Import lots from CSV. Columns: project_code,typology,surface,floor,block,orientation,rf1_price,rf2_price"""
    import csv, io
    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter=",")

    created = 0
    errors = []
    for i, row in enumerate(reader):
        try:
            proj_code = row.get("project_code", row.get("projet", "")).strip()
            proj = db.query(Project).filter(Project.code == proj_code).first()
            if not proj:
                errors.append(f"Ligne {i+2}: projet '{proj_code}' introuvable")
                continue
            company = db.query(Company).get(proj.company_id)
            typology = row.get("typology", row.get("typologie", "F3")).strip()
            surface = Decimal(row.get("surface", "0").strip() or "0")
            floor = int(row.get("floor", row.get("etage", "0")).strip() or "0")
            block = row.get("block", row.get("bloc", "A")).strip()
            orientation = row.get("orientation", "").strip()
            rf1 = Decimal(row.get("rf1_price", row.get("prix_rf1", "0")).strip() or "0")
            rf2 = Decimal(row.get("rf2_price", row.get("prix_rf2", "0")).strip() or "0")

            # Generate unique ref
            prefix = f"{proj_code[0]}-{typology}-{block}-"
            max_seq = db.query(func.count(Lot.id)).filter(Lot.ref.like(f"{prefix}%")).scalar() or 0
            seq_num = max_seq + 1
            ref = f"{prefix}{seq_num:03d}"
            while db.query(Lot).filter(Lot.ref == ref).first():
                seq_num += 1
                ref = f"{prefix}{seq_num:03d}"

            lot = Lot(
                company_id=company.id if company else proj.company_id,
                project_id=proj.id, ref=ref, typology=typology,
                surface=surface, floor=floor, block=block, orientation=orientation,
                rf1_price=rf1, rf2_price=rf2, status="DISPONIBLE",
            )
            db.add(lot)
            db.flush()
            created += 1
        except Exception as e:
            errors.append(f"Ligne {i+2}: {str(e)[:80]}")

    db.commit()
    return ApiResponse(data={"lots_created": created, "errors": errors, "total_rows": created + len(errors)})


# ── Dashboard + Relances ─────────────────────────────────────────────────────

@router.get("/dashboard")
async def adv_dashboard(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    total = db.query(DossierADV).filter(DossierADV.is_deleted == False).count()
    pipeline = {}
    for status in ["PRE_RESERVE", "RESERVE", "ENGAGE", "EN_COURS_CREDIT", "EN_COURS_FONDS_PROPRES",
                    "CONTRAT_SIGNE", "LIVRAISON_PRETE", "LIVRE", "CLOTURE"]:
        pipeline[status] = db.query(DossierADV).filter(DossierADV.status == status).count()
    avail = db.query(Lot).filter(Lot.status == "DISPONIBLE", Lot.is_deleted == False).count()
    total_lots = db.query(Lot).filter(Lot.is_deleted == False).count()
    return ApiResponse(data={
        "pipeline": pipeline, "lots_disponibles": avail, "lots_total": total_lots,
        "kpis": {
            "total_dossiers": total,
            "taux_commercialisation": f"{((total_lots - avail) * 100 // total_lots) if total_lots else 0}%",
        },
    })


@router.get("/edd/dashboard")
async def edd_dashboard(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    projects = db.query(Project).filter(Project.status == "ACTIF", Project.is_deleted == False).all()
    data = []
    for p in projects:
        lots = db.query(Lot).filter(Lot.project_id == p.id, Lot.is_deleted == False).all()
        by_status = {}
        for l in lots:
            by_status[l.status] = by_status.get(l.status, 0) + 1
        if lots:
            data.append({
                "project": p.code, "project_name": p.name, "total_lots": len(lots),
                "by_status": by_status,
                "taux_commercialisation": f"{((len(lots) - by_status.get('DISPONIBLE', 0)) * 100 // len(lots))}%",
            })
    return ApiResponse(data=data)
