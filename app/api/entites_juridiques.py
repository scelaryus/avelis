"""GFI Platform — Entités Juridiques API.

Provides a consolidated view of the 9 legal entities with their associate
participation matrix (% entreprise) and attached projects.
Source of truth: SPECIFICATION_GFI7_V3.1 — Section 1.1, 1.2, 1.4.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.core import User
from app.models.financial import Entreprise, Projet, Associe, EntrepriseAssocie

router = APIRouter(tags=["Entités Juridiques"])


@router.get("/")
async def list_entites_juridiques(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all legal entities with their associate participation and projects."""

    # 1. Fetch all entreprises
    result = await db.execute(
        select(Entreprise)
        .where(Entreprise.tenant_id == user.tenant_id)
        .order_by(Entreprise.code)
    )
    entreprises = result.scalars().all()

    # 2. Fetch all entreprise-associe links
    result = await db.execute(select(EntrepriseAssocie))
    ea_links = result.scalars().all()

    # 3. Fetch all associes
    result = await db.execute(
        select(Associe).where(Associe.tenant_id == user.tenant_id)
    )
    associes = result.scalars().all()
    assoc_map = {a.id: a for a in associes}

    # 4. Fetch all projects
    result = await db.execute(
        select(Projet).where(Projet.tenant_id == user.tenant_id)
    )
    projets = result.scalars().all()

    # 5. Build response
    ea_by_ent = {}
    for ea in ea_links:
        ea_by_ent.setdefault(ea.entreprise_id, []).append(ea)

    proj_by_ent = {}
    for p in projets:
        proj_by_ent.setdefault(p.entreprise_id, []).append(p)

    items = []
    for ent in entreprises:
        participations = []
        for ea in ea_by_ent.get(ent.id, []):
            assoc = assoc_map.get(ea.associe_id)
            if assoc:
                participations.append({
                    "associe_id": ea.associe_id,
                    "nom": assoc.nom,
                    "prenom": assoc.prenom,
                    "pourcentage": float(ea.pourcentage) * 100 if ea.pourcentage else 0,
                    "est_fondateur": assoc.est_fondateur or False,
                    "ordre_priorite": assoc.ordre_priorite,
                    "est_actif": ea.est_actif,
                })
        participations.sort(key=lambda x: x.get("ordre_priorite") or "Z")

        ent_projets = [
            {
                "id": p.id,
                "code": p.code,
                "nom": p.nom,
                "statut": p.statut.value if hasattr(p.statut, "value") else str(p.statut),
            }
            for p in proj_by_ent.get(ent.id, [])
        ]

        items.append({
            "id": ent.id,
            "code": ent.code,
            "raison_sociale": ent.raison_sociale,
            "forme_juridique": ent.forme_juridique,
            "statut": ent.statut,
            "role_principal": ent.role_principal,
            "devise": ent.devise,
            "is_active": ent.is_active,
            "participations": participations,
            "projets": ent_projets,
        })

    return items
