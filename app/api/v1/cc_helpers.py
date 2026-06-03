"""Shared CC imputation helper. Used by ADV, Stock, Supplier, CFF, SPI, DIS modules.
Includes dedup guard: same source_doc_id won't create duplicate entries.
Includes proximity check: warns if similar amount+type exists within ±7 days."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.core import CostCenterNode, CostCenterEntry, Company


def impute_cc(
    db: Session,
    *,
    entite_code: str | None = None,
    projet_code: str | None = None,
    rf_type: str = "RF1",
    montant: Decimal | str,
    label: str,
    source_type: str,
    source_doc_id: str | None = None,
) -> dict | None:
    """
    Create a CostCenterEntry and update node totals up the tree.
    Includes dedup: same source_doc_id + source_type won't create duplicates.
    Includes proximity warning: flags similar entries within ±7 days.
    """
    montant = Decimal(str(montant))
    if montant == 0:
        return None

    # ── DEDUP GUARD: exact source_doc_id match ────────────────────────────
    if source_doc_id:
        existing = db.query(CostCenterEntry).filter(
            CostCenterEntry.source_doc_id == source_doc_id,
            CostCenterEntry.source_type == source_type,
            CostCenterEntry.is_deleted == False,
        ).first()
        if existing:
            existing_node = db.query(CostCenterNode).filter(
                CostCenterNode.id == existing.node_id
            ).first()
            return {
                "node_code": existing_node.code if existing_node else "?",
                "entry_montant": str(existing.montant),
                "rf_type": existing.rf_type,
                "source_type": existing.source_type,
                "deduplicated": True,
            }

    # ── PROXIMITY CHECK: similar amount + type within ±7 days ─────────────
    similar_warning = None
    now = datetime.now(timezone.utc)
    date_low = now - timedelta(days=7)
    date_high = now + timedelta(days=7)
    similar = db.query(CostCenterEntry).filter(
        CostCenterEntry.source_type == source_type,
        CostCenterEntry.montant == montant,
        CostCenterEntry.is_deleted == False,
        CostCenterEntry.created_at >= date_low,
        CostCenterEntry.created_at <= date_high,
    ).first()
    if similar and str(similar.source_doc_id) != str(source_doc_id or ""):
        similar_warning = (
            f"Ecriture similaire detectee: {similar.montant} DA, "
            f"type={similar.source_type}, "
            f"date={similar.created_at.date() if similar.created_at else '?'}, "
            f"source={similar.source_doc_id}"
        )

    # ── Find the best matching CC node ────────────────────────────────────
    node = None
    if entite_code and projet_code:
        node = db.query(CostCenterNode).filter(
            CostCenterNode.code.ilike(f"%{entite_code}%{projet_code}%"),
            CostCenterNode.is_deleted == False,
        ).first()
    if not node and entite_code:
        node = db.query(CostCenterNode).filter(
            CostCenterNode.code.ilike(f"%{entite_code}%"),
            CostCenterNode.is_deleted == False,
        ).order_by(CostCenterNode.level.desc()).first()
    if not node:
        node = db.query(CostCenterNode).filter(
            CostCenterNode.is_deleted == False,
        ).order_by(CostCenterNode.level).first()
    if not node:
        # No CC nodes exist — create a root node so entries are never lost
        company = db.query(Company).first()
        node = CostCenterNode(
            company_id=company.id if company else None,
            code="CC-GENERAL",
            label="Centre de Cout General (auto-cree)",
            level=0,
        )
        db.add(node)
        db.flush()

    company = db.query(Company).first()

    # ── Create entry ──────────────────────────────────────────────────────
    entry = CostCenterEntry(
        company_id=company.id if company else node.company_id,
        node_id=node.id,
        rf_type=rf_type,
        montant=montant,
        label=label[:300] if label else "",
        source_type=source_type,
        source_doc_id=source_doc_id,
    )
    db.add(entry)

    # ── Update node totals (ascending consolidation) ──────────────────────
    rf_col = f"montant_{rf_type.lower()}"
    current = node
    while current:
        old_val = getattr(current, rf_col, None) or Decimal("0")
        setattr(current, rf_col, old_val + montant)
        current.montant_total = (
            (current.montant_rf1 or 0) + (current.montant_rf2 or 0) +
            (current.montant_rf3 or 0) + (current.montant_rf4 or 0)
        )
        if current.parent_id:
            current = db.query(CostCenterNode).filter(
                CostCenterNode.id == current.parent_id
            ).first()
        else:
            break

    result = {
        "node_code": node.code,
        "entry_montant": str(montant),
        "rf_type": rf_type,
        "source_type": source_type,
    }
    if similar_warning:
        result["similar_exists"] = True
        result["similar_warning"] = similar_warning
    return result
