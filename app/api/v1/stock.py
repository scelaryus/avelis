"""Router — Stock: AI item identification, CRUD, storage zones, barcode generation.
Upload/capture image → AI identifies → user confirms + fills details → stored with barcode."""
import base64
import hashlib
import json as json_mod
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.v1.deps import get_current_user, CurrentUser, get_db
from app.api.v1.schemas import ApiResponse, Meta
from app.models.core import StockItem, StorageZone, StockMovement, Company, Project

router = APIRouter(prefix="/stock", tags=["Stock"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "uploads", "stock")


# ═══════════════════════════════════════════════════════════════════════════════
# AI ITEM IDENTIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/identify")
async def identify_item(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
):
    """Upload/capture an image. AI identifies the item and returns structured data."""
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Fichier trop volumineux (max 10 Mo)")

    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    mime = mime_map.get(ext, "image/jpeg")
    b64 = base64.b64encode(content).decode("utf-8")

    # Save image
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    fhash = hashlib.sha256(content).hexdigest()[:16]
    fname = f"item_{fhash}_{file.filename}"
    fpath = os.path.join(UPLOAD_DIR, fname)
    with open(fpath, "wb") as f:
        f.write(content)

    try:
        from app.agents.llm import get_llm
        llm = get_llm(temperature=0.0, max_tokens=1000)

        prompt = """Analyse cette image et identifie l'objet ou element visible.
Ceci est un systeme d'inventaire/stock pour une entreprise immobiliere et de construction en Algerie.
L'element peut etre n'importe quoi: materiau de construction, equipement, outil, fourniture de bureau,
appareil electronique, mobilier, piece detachee, produit chimique, EPI, ou tout autre objet physique.

Retourne un JSON strict avec:

{
  "name": "nom precis de l'element identifie en francais (marque et modele si visible)",
  "category": "categorie la plus proche parmi: MATERIAU_CONSTRUCTION, EQUIPEMENT, OUTILLAGE, PLOMBERIE, ELECTRICITE, MENUISERIE, PEINTURE, REVETEMENT, QUINCAILLERIE, SECURITE, MOBILIER, INFORMATIQUE, FOURNITURE_BUREAU, VEHICULE, EPI, AUTRE",
  "description": "description courte incluant marque, modele, couleur, taille si visible",
  "unit": "unite de mesure suggeree parmi: UNITE, KG, M, M2, M3, LITRE, SEAU, SAC, PALETTE, ROULEAU, BOITE, LOT",
  "estimated_unit_price": prix unitaire estime en Dinars Algeriens (number) ou null si inconnu,
  "confidence": nombre entre 0 et 100 indiquant la confiance dans l'identification
}

IMPORTANT: Identifie toujours l'objet meme s'il n'est pas un materiau de construction.
Un telephone, un ordinateur, un stylo, des cles — tout objet physique doit etre identifie.
Ne reponds JAMAIS "Element non identifie" sauf si l'image est completement floue/noire/vide.
Reponds UNIQUEMENT avec le JSON, rien d'autre."""

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
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        extracted = json_mod.loads(raw)
        extracted["image_path"] = fpath
        extracted["image_filename"] = fname
        return ApiResponse(data=extracted)

    except json_mod.JSONDecodeError:
        return ApiResponse(data={
            "name": None, "category": "AUTRE", "description": None,
            "unit": "UNITE", "estimated_unit_price": None, "confidence": 0,
            "image_path": fpath, "image_filename": fname,
            "error": "Identification AI non structuree — saisie manuelle requise",
        })
    except Exception as e:
        return ApiResponse(data={
            "name": None, "category": "AUTRE", "description": None,
            "unit": "UNITE", "estimated_unit_price": None, "confidence": 0,
            "image_path": fpath, "image_filename": fname,
            "error": f"AI indisponible: {str(e)[:100]}. Saisie manuelle.",
        })


# ═══════════════════════════════════════════════════════════════════════════════
# STORAGE ZONES CRUD
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/zones")
async def list_zones(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    zones = db.query(StorageZone).filter(StorageZone.is_deleted == False).order_by(StorageZone.code).all()
    return ApiResponse(data=[{
        "id": str(z.id), "code": z.code, "label": z.label,
        "location": z.location, "description": z.description,
        "is_active": z.is_active,
        "item_count": db.query(StockItem).filter(StockItem.zone_id == z.id, StockItem.is_deleted == False).count(),
    } for z in zones])


@router.post("/zones")
async def create_zone(body: dict, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    # Get first company as default
    company = db.query(Company).first()
    if not company:
        raise HTTPException(400, "Aucune entreprise configuree")
    existing = db.query(StorageZone).filter(
        StorageZone.code == body["code"], StorageZone.company_id == company.id, StorageZone.is_deleted == False
    ).first()
    if existing:
        raise HTTPException(409, f"Zone {body['code']} existe deja")
    z = StorageZone(
        company_id=company.id, code=body["code"], label=body["label"],
        location=body.get("location"), description=body.get("description"),
    )
    db.add(z)
    db.commit()
    return ApiResponse(data={"id": str(z.id), "code": z.code, "label": z.label})


@router.delete("/zones/{zone_id}")
async def delete_zone(zone_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    z = db.query(StorageZone).filter(StorageZone.id == zone_id).first()
    if not z:
        raise HTTPException(404, "Zone introuvable")
    items = db.query(StockItem).filter(StockItem.zone_id == z.id, StockItem.is_deleted == False).count()
    if items > 0:
        raise HTTPException(400, f"Zone contient {items} element(s) — deplacez-les d'abord")
    z.is_deleted = True
    db.commit()
    return ApiResponse(data={"deleted": True})


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK ITEMS CRUD
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_barcode_value(item_code: str) -> str:
    """Generate an EAN-13 compatible barcode value."""
    # Use hash of code to generate 12 digits, then add check digit
    h = hashlib.md5(item_code.encode()).hexdigest()
    digits = "".join(c for c in h if c.isdigit())[:12].ljust(12, "0")
    # EAN-13 check digit
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits))
    check = (10 - (total % 10)) % 10
    return digits + str(check)


def _next_item_code(db: Session) -> str:
    count = db.query(func.count(StockItem.id)).scalar() or 0
    return f"STK-{count + 1:06d}"


@router.get("/items")
async def list_items(
    zone_id: str | None = None, category: str | None = None,
    search: str | None = None, low_stock: bool = False,
    db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user),
):
    q = db.query(StockItem).filter(StockItem.is_deleted == False)
    if zone_id:
        q = q.filter(StockItem.zone_id == zone_id)
    if category:
        q = q.filter(StockItem.category == category)
    if search:
        q = q.filter(StockItem.name.ilike(f"%{search}%") | StockItem.code.ilike(f"%{search}%"))
    if low_stock:
        q = q.filter(StockItem.min_stock_alert.isnot(None), StockItem.quantity <= StockItem.min_stock_alert)
    items = q.order_by(StockItem.created_at.desc()).limit(200).all()

    # KPIs
    total_items = db.query(func.count(StockItem.id)).filter(StockItem.is_deleted == False).scalar() or 0
    total_value = db.query(func.coalesce(func.sum(StockItem.total_value), 0)).filter(StockItem.is_deleted == False).scalar()
    low_count = db.query(func.count(StockItem.id)).filter(
        StockItem.is_deleted == False, StockItem.min_stock_alert.isnot(None),
        StockItem.quantity <= StockItem.min_stock_alert,
    ).scalar() or 0

    return ApiResponse(
        data={
            "items": [{
                "id": str(i.id), "code": i.code, "barcode": i.barcode,
                "name": i.name, "category": i.category, "description": i.description,
                "quantity": str(i.quantity), "unit": i.unit,
                "unit_price": str(i.unit_price), "total_value": str(i.total_value),
                "zone_id": str(i.zone_id) if i.zone_id else None,
                "image_url": i.image_url, "status": i.status,
                "ai_detected_name": i.ai_detected_name, "ai_confidence": str(i.ai_confidence) if i.ai_confidence else None,
                "min_stock_alert": str(i.min_stock_alert) if i.min_stock_alert else None,
                "low_stock": i.min_stock_alert is not None and i.quantity <= i.min_stock_alert,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            } for i in items],
            "kpis": {
                "total_items": total_items,
                "total_value": str(total_value),
                "low_stock_count": low_count,
            },
        },
        meta=Meta(total=total_items),
    )


@router.post("/items")
async def create_item(body: dict, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    company = db.query(Company).first()
    if not company:
        raise HTTPException(400, "Aucune entreprise configuree")

    code = _next_item_code(db)
    barcode = _generate_barcode_value(code)
    qty = Decimal(str(body.get("quantity", 0)))
    price = Decimal(str(body.get("unit_price", 0)))
    total = (qty * price).quantize(Decimal("0.01"))

    item = StockItem(
        company_id=company.id,
        project_id=body.get("project_id"),
        zone_id=body.get("zone_id"),
        code=code, barcode=barcode,
        name=body["name"],
        category=body.get("category", "AUTRE"),
        description=body.get("description"),
        ai_detected_name=body.get("ai_detected_name"),
        ai_confidence=body.get("ai_confidence"),
        image_url=body.get("image_url"),
        quantity=qty, unit=body.get("unit", "UNITE"),
        unit_price=price, total_value=total,
        min_stock_alert=body.get("min_stock_alert"),
        created_by=user.name,
    )
    db.add(item)
    db.flush()  # get item.id before creating movement

    # Record initial ENTREE movement
    if qty > 0:
        db.add(StockMovement(
            company_id=company.id, item_id=item.id,
            movement_type="ENTREE", quantity=qty,
            unit_price=price, total_value=total,
            reason="Stock initial", created_by=user.name,
        ))

    # Impute to Centre de Cout as resource
    if total > 0:
        from app.api.v1.cc_helpers import impute_cc
        proj = db.query(Project).get(body.get("project_id")) if body.get("project_id") else None
        impute_cc(
            db,
            entite_code=company.code,
            projet_code=proj.code if proj else None,
            rf_type="RF1",
            montant=total,
            label=f"Stock: {item.name} — {qty} {item.unit} x {price} DA",
            source_type="STOCK",
            source_doc_id=str(item.id),
        )

    db.commit()
    return ApiResponse(data={
        "id": str(item.id), "code": code, "barcode": barcode,
        "name": item.name, "total_value": str(total),
    })


@router.patch("/items/{item_id}")
async def update_item(item_id: str, body: dict, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    item = db.query(StockItem).filter(StockItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Element introuvable")

    old_qty = item.quantity
    for field in ["name", "category", "description", "unit", "zone_id", "min_stock_alert", "status"]:
        if field in body:
            setattr(item, field, body[field])
    if "unit_price" in body:
        item.unit_price = Decimal(str(body["unit_price"]))
    if "quantity" in body:
        new_qty = Decimal(str(body["quantity"]))
        diff = new_qty - old_qty
        item.quantity = new_qty
        if diff != 0:
            db.add(StockMovement(
                company_id=item.company_id, item_id=item.id,
                movement_type="ENTREE" if diff > 0 else "SORTIE",
                quantity=abs(diff), unit_price=item.unit_price,
                total_value=abs(diff) * item.unit_price,
                reason="Ajustement stock", created_by=user.name,
            ))
    item.total_value = item.quantity * item.unit_price
    db.commit()
    return ApiResponse(data={"id": str(item.id), "name": item.name, "quantity": str(item.quantity), "total_value": str(item.total_value)})


@router.get("/items/{item_id}")
async def get_item(item_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    item = db.query(StockItem).filter(StockItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Element introuvable")
    zone = db.query(StorageZone).filter(StorageZone.id == item.zone_id).first() if item.zone_id else None
    movements = db.query(StockMovement).filter(
        StockMovement.item_id == item.id, StockMovement.is_deleted == False
    ).order_by(StockMovement.created_at.desc()).limit(50).all()
    return ApiResponse(data={
        "id": str(item.id), "code": item.code, "barcode": item.barcode,
        "name": item.name, "category": item.category, "description": item.description,
        "quantity": str(item.quantity), "unit": item.unit,
        "unit_price": str(item.unit_price), "total_value": str(item.total_value),
        "zone": {"id": str(zone.id), "code": zone.code, "label": zone.label} if zone else None,
        "image_url": item.image_url,
        "ai_detected_name": item.ai_detected_name,
        "ai_confidence": str(item.ai_confidence) if item.ai_confidence else None,
        "min_stock_alert": str(item.min_stock_alert) if item.min_stock_alert else None,
        "movements": [{
            "id": str(m.id), "type": m.movement_type,
            "quantity": str(m.quantity), "unit_price": str(m.unit_price) if m.unit_price else None,
            "total_value": str(m.total_value) if m.total_value else None,
            "reason": m.reason, "date": m.created_at.isoformat(), "by": m.created_by,
        } for m in movements],
    })


# ═══════════════════════════════════════════════════════════════════════════════
# BARCODE GENERATION (SVG)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/items/{item_id}/barcode")
async def get_barcode_svg(item_id: str, db: Session = Depends(get_db)):
    """Generate a printable barcode label as SVG."""
    item = db.query(StockItem).filter(StockItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Element introuvable")

    barcode_val = item.barcode
    # Generate Code128-style bars (simplified visual representation)
    bars = _encode_code128(barcode_val)

    bar_width = 2
    total_width = len(bars) * bar_width + 40
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{total_width + 20}" height="120" viewBox="0 0 {total_width + 20} 120">
  <rect width="100%" height="100%" fill="white"/>
  <text x="{(total_width + 20) // 2}" y="15" text-anchor="middle" font-family="Arial" font-size="10" font-weight="bold">{item.name[:40]}</text>
  <g transform="translate(10, 20)">"""

    x = 10
    for i, bar in enumerate(bars):
        if bar == "1":
            svg += f'\n    <rect x="{x}" y="0" width="{bar_width}" height="60" fill="black"/>'
        x += bar_width

    svg += f"""
  </g>
  <text x="{(total_width + 20) // 2}" y="100" text-anchor="middle" font-family="monospace" font-size="12">{barcode_val}</text>
  <text x="{(total_width + 20) // 2}" y="115" text-anchor="middle" font-family="Arial" font-size="9" fill="#666">{item.code}</text>
</svg>"""

    return Response(content=svg, media_type="image/svg+xml")


@router.get("/items/{item_id}/barcode-label")
async def get_barcode_label_html(item_id: str, db: Session = Depends(get_db)):
    """Generate a printable barcode label as standalone HTML page."""
    item = db.query(StockItem).filter(StockItem.id == item_id).first()
    if not item:
        raise HTTPException(404, "Element introuvable")
    zone = db.query(StorageZone).filter(StorageZone.id == item.zone_id).first() if item.zone_id else None

    barcode_val = item.barcode
    bars = _encode_code128(barcode_val)
    bar_width = 2
    total_bar_width = len(bars) * bar_width + 20

    bars_svg = ""
    x = 0
    for bar in bars:
        if bar == "1":
            bars_svg += f'<rect x="{x}" y="0" width="{bar_width}" height="50" fill="black"/>'
        x += bar_width

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Etiquette {item.code}</title>
<style>
  @media print {{ body {{ margin: 0; }} .no-print {{ display: none; }} }}
  body {{ font-family: Arial, sans-serif; padding: 20px; }}
  .label {{ border: 1px solid #ccc; padding: 15px; width: 300px; text-align: center; }}
  .label h3 {{ margin: 0 0 5px; font-size: 14px; }}
  .label .code {{ font-family: monospace; font-size: 11px; color: #666; }}
  .label .barcode {{ margin: 10px auto; }}
  .label .barcode-num {{ font-family: monospace; font-size: 12px; letter-spacing: 2px; }}
  .label .info {{ font-size: 10px; color: #888; margin-top: 5px; }}
  .print-btn {{ margin: 20px 0; padding: 10px 20px; background: #6C5CE7; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; }}
</style></head>
<body>
<button class="print-btn no-print" onclick="window.print()">Imprimer l'etiquette</button>
<div class="label">
  <h3>{item.name[:50]}</h3>
  <div class="code">{item.code}</div>
  <div class="barcode">
    <svg width="{total_bar_width}" height="50" viewBox="0 0 {total_bar_width} 50">{bars_svg}</svg>
  </div>
  <div class="barcode-num">{barcode_val}</div>
  <div class="info">{item.category or ''} | {item.unit} | {zone.label if zone else 'Sans zone'}</div>
</div>
</body></html>"""
    return Response(content=html, media_type="text/html")


def _encode_code128(data: str) -> str:
    """Simple Code128-B encoder returning a string of '0' and '1'."""
    CODE128_B = {
        ' ': '11011001100', '!': '11001101100', '"': '11001100110', '#': '10010011000',
        '$': '10010001100', '%': '10001001100', '&': '10011001000', "'": '10011000100',
        '(': '10001100100', ')': '11001001000', '*': '11001000100', '+': '11000100100',
        ',': '10110011100', '-': '10011011100', '.': '10011001110', '/': '10111001100',
        '0': '10011101100', '1': '10011100110', '2': '11001110010', '3': '11001011100',
        '4': '11001001110', '5': '11011100100', '6': '11001110100', '7': '11101101110',
        '8': '11101001100', '9': '11100101100', ':': '11100100110', ';': '11101100100',
        '<': '11100110100', '=': '11100110010', '>': '11011011000', '?': '11011000110',
        '@': '11000110110', 'A': '10100011000', 'B': '10001011000', 'C': '10001000110',
        'D': '10110001000', 'E': '10001101000', 'F': '10001100010', 'G': '11010001000',
        'H': '11000101000', 'I': '11000100010', 'J': '10110111000', 'K': '10110001110',
        'L': '10001101110', 'M': '10111011000', 'N': '10111000110', 'O': '10001110110',
        'P': '11101110110', 'Q': '11010001110', 'R': '11000101110', 'S': '11011101000',
        'T': '11011100010', 'U': '11011101110', 'V': '11101011000', 'W': '11101000110',
        'X': '11100010110', 'Y': '11101101000', 'Z': '11101100010', '[': '11100011010',
    }
    start = '11010010000'  # Start Code B
    stop = '1100011101011'  # Stop
    result = start
    for ch in data:
        result += CODE128_B.get(ch, '11011001100')  # fallback to space
    result += stop
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK CONSUME / REDUCE (barcode scan)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/lookup/{barcode}")
async def lookup_by_barcode(barcode: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """Look up a stock item by barcode or code."""
    item = db.query(StockItem).filter(
        (StockItem.barcode == barcode) | (StockItem.code == barcode),
        StockItem.is_deleted == False,
    ).first()
    if not item:
        raise HTTPException(404, f"Aucun element avec le code/barcode '{barcode}'")
    zone = db.query(StorageZone).filter(StorageZone.id == item.zone_id).first() if item.zone_id else None
    return ApiResponse(data={
        "id": str(item.id), "code": item.code, "barcode": item.barcode,
        "name": item.name, "category": item.category,
        "quantity": str(item.quantity), "unit": item.unit,
        "unit_price": str(item.unit_price), "total_value": str(item.total_value),
        "zone": {"code": zone.code, "label": zone.label} if zone else None,
        "image_url": item.image_url,
        "min_stock_alert": str(item.min_stock_alert) if item.min_stock_alert else None,
    })


@router.post("/consume")
async def consume_stock(body: dict, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """
    Reduce stock quantity by barcode/code.
    Body: { barcode, quantity, reason }
    Creates a SORTIE movement.
    """
    barcode = body.get("barcode", "").strip()
    qty = Decimal(str(body.get("quantity", 0)))
    reason = body.get("reason", "Sortie stock")

    if qty <= 0:
        raise HTTPException(422, "Quantite doit etre superieure a 0")

    item = db.query(StockItem).filter(
        (StockItem.barcode == barcode) | (StockItem.code == barcode),
        StockItem.is_deleted == False,
    ).first()
    if not item:
        raise HTTPException(404, f"Aucun element avec le code '{barcode}'")

    if item.quantity < qty:
        raise HTTPException(422,
            f"Stock insuffisant: {item.quantity} {item.unit} disponible, {qty} demande.")

    old_qty = item.quantity
    item.quantity = item.quantity - qty
    item.total_value = item.quantity * item.unit_price

    consumed_value = qty * item.unit_price
    db.add(StockMovement(
        company_id=item.company_id, item_id=item.id,
        movement_type="SORTIE", quantity=qty,
        unit_price=item.unit_price, total_value=consumed_value,
        reason=reason, created_by=user.name,
    ))
    # Negative CC entry (resource consumed)
    from app.api.v1.cc_helpers import impute_cc
    comp = db.query(Company).get(item.company_id)
    impute_cc(
        db,
        entite_code=comp.code if comp else None,
        rf_type="RF1",
        montant=-consumed_value,  # negative = consumed
        label=f"Sortie stock: {item.name} — {qty} {item.unit} ({reason})",
        source_type="STOCK",
        source_doc_id=str(item.id),
    )
    db.commit()

    low_stock = item.min_stock_alert is not None and item.quantity <= item.min_stock_alert

    return ApiResponse(data={
        "item": item.name, "code": item.code,
        "old_quantity": str(old_qty), "consumed": str(qty),
        "new_quantity": str(item.quantity), "unit": item.unit,
        "low_stock_alert": low_stock,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD / KPIs
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def stock_dashboard(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    total_items = db.query(func.count(StockItem.id)).filter(StockItem.is_deleted == False).scalar() or 0
    total_value = db.query(func.coalesce(func.sum(StockItem.total_value), 0)).filter(StockItem.is_deleted == False).scalar()
    by_category = {}
    rows = db.query(StockItem.category, func.count(StockItem.id), func.sum(StockItem.total_value)).filter(
        StockItem.is_deleted == False
    ).group_by(StockItem.category).all()
    for cat, cnt, val in rows:
        by_category[cat or "AUTRE"] = {"count": cnt, "value": str(val or 0)}
    zones = db.query(StorageZone).filter(StorageZone.is_deleted == False).count()
    return ApiResponse(data={
        "total_items": total_items, "total_value": str(total_value),
        "zones_count": zones, "by_category": by_category,
    })
