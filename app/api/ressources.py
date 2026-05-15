"""GFI v7.0 — Ressources (Stock Materiel) API.

Independent module for material stock management with:
  - CRUD for stock items
  - AI-powered image recognition for item identification
  - Barcode generation (Code128 SVG)
"""
import base64
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.core import User
from app.models.juridique import StockMateriel

router = APIRouter(tags=["Ressources"])


# ── Schemas ────────────────────────────────────────────────────────────────

class StockCreate(BaseModel):
    entreprise_id: str
    code_article: str
    designation: str
    unite: str = "unite"
    quantite: float = 0
    valeur_unitaire: float = 0
    emplacement: Optional[str] = None
    seuil_alerte: float = 0


class StockUpdate(BaseModel):
    designation: Optional[str] = None
    unite: Optional[str] = None
    quantite: Optional[float] = None
    valeur_unitaire: Optional[float] = None
    emplacement: Optional[str] = None
    seuil_alerte: Optional[float] = None
    est_actif: Optional[bool] = None


class AIIdentifyResponse(BaseModel):
    designation: str
    code_article_suggestion: str
    unite_suggestion: str
    category: str
    confidence: float
    description: str


# ── List / Detail ──────────────────────────────────────────────────────────

@router.get("/stock")
async def list_stock(
    entreprise_id: Optional[str] = None,
    alerte_only: bool = False,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(StockMateriel).where(StockMateriel.est_actif == True)
    if entreprise_id:
        q = q.where(StockMateriel.entreprise_id == entreprise_id)
    if alerte_only:
        q = q.where(StockMateriel.quantite <= StockMateriel.seuil_alerte)
    if search:
        q = q.where(
            StockMateriel.designation.ilike(f"%{search}%")
            | StockMateriel.code_article.ilike(f"%{search}%")
        )
    q = q.order_by(StockMateriel.code_article)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [_serialize(r) for r in rows]


@router.get("/stock/{item_id}")
async def get_stock_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(StockMateriel).where(StockMateriel.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Article introuvable")
    return _serialize(item)


# ── Create / Update ────────────────────────────────────────────────────────

@router.post("/stock", status_code=201)
async def create_stock(
    body: StockCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = StockMateriel(
        id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id,
        entreprise_id=body.entreprise_id,
        code_article=body.code_article,
        designation=body.designation,
        unite=body.unite,
        quantite=body.quantite,
        valeur_unitaire=body.valeur_unitaire,
        valeur_totale=body.quantite * body.valeur_unitaire,
        emplacement=body.emplacement,
        seuil_alerte=body.seuil_alerte,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _serialize(item)


@router.patch("/stock/{item_id}")
async def update_stock(
    item_id: str,
    body: StockUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(StockMateriel).where(StockMateriel.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Article introuvable")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    # Recalculate total
    item.valeur_totale = float(item.quantite or 0) * float(item.valeur_unitaire or 0)
    await db.commit()
    await db.refresh(item)
    return _serialize(item)


# ── AI Image Identification ───────────────────────────────────────────────

@router.post("/ai-identify")
async def ai_identify_item(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Accept an image and use AI vision to identify the material/item."""
    from app.services.llm_graph import invoke_json_agent
    from app.config import get_settings

    settings = get_settings()
    if not settings.LLM_API_KEY:
        raise HTTPException(503, "AI service not configured (LLM_API_KEY missing)")

    # Read and encode image
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Image trop volumineuse (max 10 MB)")

    image_b64 = base64.b64encode(content).decode("utf-8")
    mime = file.content_type or "image/jpeg"

    system_prompt = """You are a material/stock identification expert for a construction and real estate company.
Analyze the image and identify the item shown. Return a JSON object with these fields:
{
  "designation": "Clear name of the item in French",
  "code_article_suggestion": "Suggested article code (uppercase, e.g. MAT-CIMENT-50KG)",
  "unite_suggestion": "Unit of measurement in French (e.g. unite, kg, m, m2, m3, litre, sac, palette, boite, rouleau)",
  "category": "Category in French (e.g. Matériaux de construction, Outillage, Plomberie, Électricité, Quincaillerie, Peinture, Bois, Fer, Équipement de sécurité, Fourniture bureau, Mobilier)",
  "confidence": 0.85,
  "description": "Brief description of the item and its typical use in French"
}
Be specific and practical. If you cannot identify the item, provide your best guess with a lower confidence score."""

    user_prompt = "Identify the item in this image for our stock management system."

    try:
        result = await invoke_json_agent(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_b64=image_b64,
            image_mime=mime,
        )
        parsed = result["parsed_json"]
        return {
            "designation": parsed.get("designation", "Article non identifie"),
            "code_article_suggestion": parsed.get("code_article_suggestion", "ART-001"),
            "unite_suggestion": parsed.get("unite_suggestion", "unite"),
            "category": parsed.get("category", "Divers"),
            "confidence": parsed.get("confidence", 0.5),
            "description": parsed.get("description", ""),
            "ai_model": result.get("ai_model", ""),
        }
    except Exception as exc:
        raise HTTPException(502, f"AI identification failed: {str(exc)}")


# ── Barcode Generation (Code128 SVG) ──────────────────────────────────────

@router.get("/stock/{item_id}/barcode")
async def get_barcode(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return barcode data for the stock item (code_article + id)."""
    result = await db.execute(
        select(StockMateriel).where(StockMateriel.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Article introuvable")
    return {
        "id": item.id,
        "code_article": item.code_article,
        "designation": item.designation,
        "barcode_value": f"{item.code_article}-{item.id[:8].upper()}",
        "emplacement": item.emplacement,
        "unite": item.unite,
    }


# ── Stock Reduction (scan-based, requires admin approval) ─────────────────

class StockReductionRequest(BaseModel):
    item_id: str
    quantite: float
    motif: str  # justification required


@router.post("/stock/demande-sortie", status_code=201)
async def demande_sortie_stock(
    body: StockReductionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stock agent proposes a stock reduction. Must be approved by super admin."""
    result = await db.execute(
        select(StockMateriel).where(StockMateriel.id == body.item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Article introuvable")
    if body.quantite <= 0:
        raise HTTPException(400, "Quantité doit être positive")
    if body.quantite > float(item.quantite or 0):
        raise HTTPException(400, f"Stock insuffisant ({float(item.quantite or 0)} disponibles)")
    if not body.motif or len(body.motif) < 10:
        raise HTTPException(400, "Motif obligatoire (min 10 caractères)")

    from app.models.core import AuditLog
    db.add(AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="stock_sortie_demande",
        entity_type="stock_materiel",
        entity_id=body.item_id,
        details=f"qte={body.quantite}, motif={body.motif}",
    ))
    await db.commit()

    return {
        "status": "PENDING_APPROVAL",
        "item_id": body.item_id,
        "quantite": body.quantite,
        "motif": body.motif,
        "message": "Demande de sortie soumise. En attente d'approbation admin.",
    }


@router.post("/stock/approuver-sortie")
async def approuver_sortie_stock(
    body: StockReductionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Super admin approves stock reduction and actually decreases the quantity."""
    if current_user.role not in ("SUPER_ADMIN", "admin"):
        raise HTTPException(403, "Seul le super admin peut approuver les sorties de stock")

    result = await db.execute(
        select(StockMateriel).where(StockMateriel.id == body.item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Article introuvable")
    if body.quantite > float(item.quantite or 0):
        raise HTTPException(400, f"Stock insuffisant ({float(item.quantite or 0)} disponibles)")

    item.quantite = float(item.quantite or 0) - body.quantite
    item.valeur_totale = float(item.quantite) * float(item.prix_unitaire or 0)

    from app.models.core import AuditLog
    db.add(AuditLog(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="stock_sortie_approuvee",
        entity_type="stock_materiel",
        entity_id=body.item_id,
        details=f"qte={body.quantite}, motif={body.motif}",
    ))
    await db.commit()
    await db.refresh(item)
    return _serialize(item)


# ── Stats ──────────────────────────────────────────────────────────────────

@router.get("/stats")
async def stock_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total = await db.execute(
        select(sa_func.count(StockMateriel.id)).where(StockMateriel.est_actif == True)
    )
    alerte = await db.execute(
        select(sa_func.count(StockMateriel.id)).where(
            StockMateriel.est_actif == True,
            StockMateriel.quantite <= StockMateriel.seuil_alerte,
            StockMateriel.seuil_alerte > 0,
        )
    )
    valeur = await db.execute(
        select(sa_func.coalesce(sa_func.sum(StockMateriel.valeur_totale), 0)).where(
            StockMateriel.est_actif == True
        )
    )
    return {
        "total_articles": total.scalar() or 0,
        "articles_en_alerte": alerte.scalar() or 0,
        "valeur_totale_stock": float(valeur.scalar() or 0),
    }


# ── Serialization ─────────────────────────────────────────────────────────

def _serialize(s: StockMateriel) -> dict:
    return {
        "id": s.id,
        "entreprise_id": s.entreprise_id,
        "code_article": s.code_article,
        "designation": s.designation,
        "unite": s.unite,
        "quantite": float(s.quantite) if s.quantite else 0,
        "valeur_unitaire": float(s.valeur_unitaire) if s.valeur_unitaire else 0,
        "valeur_totale": float(s.valeur_totale) if s.valeur_totale else 0,
        "emplacement": s.emplacement,
        "seuil_alerte": float(s.seuil_alerte) if s.seuil_alerte else 0,
        "est_actif": s.est_actif,
        "en_alerte": float(s.quantite or 0) <= float(s.seuil_alerte or 0) and float(s.seuil_alerte or 0) > 0,
        "created_at": str(s.created_at) if s.created_at else None,
    }
