"""GFI v7.0 — Hierarchical Cost Center API endpoints.

Provides:
- /cc/arbre — Full CC tree (hierarchical)
- /cc/{id} — Node detail + aggregates + quote-parts
- /cc/{id}/double-vue — Official vs internal view
- /cc/dashboard/daf — DAF dashboard
- /cc/consolidation/groupe — Group consolidation
- /cc/consolidation/associe/{id} — Per-associate consolidation
- /cc/build — Force rebuild of CC tree
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.core import User
from app.services.cc_hierarchique_engine import (
    build_cc_tree,
    get_cc_tree,
    compute_node_aggregates,
    get_dashboard_data,
    get_double_vue,
    _get_associate_consolidation,
)

router = APIRouter(tags=["Centre de Coût Hiérarchique"])


@router.get("/arbre")
async def get_arbre(
    entreprise_id: Optional[str] = Query(None),
    projet_id: Optional[str] = Query(None),
    max_niveau: int = Query(5, ge=0, le=5),
    x_entreprise_id: Optional[str] = Header(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Auto-scope to active entreprise
    if not entreprise_id and x_entreprise_id:
        entreprise_id = x_entreprise_id
    """Get the hierarchical CC tree (flat list with parent references)."""
    # Ensure tree exists
    await build_cc_tree(db, user.tenant_id)
    await db.commit()

    tree = await get_cc_tree(
        db, user.tenant_id,
        entreprise_id=entreprise_id,
        projet_id=projet_id,
        max_niveau=max_niveau,
    )
    return tree


@router.get("/dashboard/daf")
async def get_daf_dashboard(
    periode: Optional[str] = Query(None, description="Format YYYY-MM"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """DAF Dashboard — Group consolidation with per-associate breakdown."""
    data = await get_dashboard_data(db, user.tenant_id, periode)
    await db.commit()
    return data


@router.get("/node/{node_id}")
async def get_node_detail(
    node_id: str,
    periode: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detail + aggregates + quote-parts for a single CC node."""
    agg = await compute_node_aggregates(db, user.tenant_id, node_id, periode)
    if not agg:
        raise HTTPException(status_code=404, detail="CC node not found")
    return agg


@router.get("/node/{node_id}/double-vue")
async def get_node_double_vue(
    node_id: str,
    periode: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Double vue: official (RF1+RF3) vs internal (all RF)."""
    data = await get_double_vue(db, user.tenant_id, node_id, periode)
    return data


@router.get("/consolidation/groupe")
async def get_consolidation_groupe(
    periode: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Group-level consolidation across all enterprises."""
    from app.models.cc_hierarchique import CCNode
    from sqlalchemy import select

    await build_cc_tree(db, user.tenant_id)
    await db.commit()

    root_result = await db.execute(
        select(CCNode).where(
            CCNode.tenant_id == user.tenant_id,
            CCNode.code == "CC-GROUPE",
        )
    )
    root = root_result.scalar_one_or_none()
    if not root:
        raise HTTPException(status_code=404, detail="No CC tree found")

    return await compute_node_aggregates(db, user.tenant_id, root.id, periode)


@router.get("/consolidation/associes")
async def get_consolidation_associes(
    periode: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Per-associate consolidation across all projects."""
    await build_cc_tree(db, user.tenant_id)
    await db.commit()

    return await _get_associate_consolidation(db, user.tenant_id, periode)


@router.post("/build")
async def force_build_tree(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Force rebuild of the CC tree from enterprises and projects."""
    result = await build_cc_tree(db, user.tenant_id)
    await db.commit()
    return {"status": "ok", **result}
