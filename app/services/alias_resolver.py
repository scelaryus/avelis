"""GFI v7.0 — Alias Resolver service.

Resolves associate, project, and enterprise aliases.
Functions:
  - resoudre_associe(nom) — match by alias or name
  - resoudre_projet(code) — match by alias or code
  - resoudre_entite(name) — match by enterprise name
  - verifier_unicite_projet() — verify no duplicate project codes
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import Associe, Entreprise, Projet
from app.models.finance_associes import AssociateAlias
from app.services.blocking_rules import BlockingError


# Project alias mapping — canonical code → list of known aliases
# COR-005: AURÉA = AUREA = CHERAGA = PROJET CHÉRAGA
PROJECT_ALIASES: dict[str, list[str]] = {
    "CHERAGA": ["AURÉA", "AUREA", "PROJET CHÉRAGA", "PROJET CHERAGA"],
    "AUREA": ["CHERAGA", "AURÉA", "PROJET CHÉRAGA", "PROJET CHERAGA"],
    "AURÉA": ["CHERAGA", "AUREA", "PROJET CHÉRAGA", "PROJET CHERAGA"],
}


class AliasResolver:
    """Resolves entity aliases for associates, projects, and enterprises."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def resoudre_associe(self, nom: str) -> Optional[Associe]:
        """Resolve an associate by alias or name.

        1. Exact match on alias table
        2. Exact match on nom/prenom
        3. Returns None if not found (caller decides whether to error)
        """
        # 1. Exact match on alias
        alias_result = await self.db.execute(
            select(AssociateAlias).where(
                AssociateAlias.alias == nom
            )
        )
        alias_row = alias_result.scalar_one_or_none()
        if alias_row:
            result = await self.db.execute(
                select(Associe).where(Associe.id == alias_row.associe_id)
            )
            assoc = result.scalar_one_or_none()
            if assoc:
                return assoc

        # 2. Exact match on nom or (nom + prenom)
        result = await self.db.execute(
            select(Associe).where(Associe.is_active == True)
        )
        all_associes = result.scalars().all()

        for a in all_associes:
            full = f"{a.nom} {a.prenom}".strip() if a.prenom else a.nom
            if full.lower() == nom.lower() or a.nom.lower() == nom.lower():
                return a

        return None

    async def resoudre_projet(self, code: str) -> Optional[Projet]:
        """Resolve a project by code or alias.

        1. Exact match on project code
        2. Case-insensitive match on code
        3. Check PROJECT_ALIASES for known alternate names
        4. Partial match on project name
        """
        # 1. Exact match on code
        result = await self.db.execute(
            select(Projet).where(Projet.code == code)
        )
        projet = result.scalar_one_or_none()
        if projet:
            return projet

        # 2. Case-insensitive match on code
        result = await self.db.execute(
            select(Projet).where(
                sa_func.upper(Projet.code) == code.upper()
            )
        )
        projet = result.scalar_one_or_none()
        if projet:
            return projet

        # 3. Check PROJECT_ALIASES (COR-005: AURÉA = CHERAGA etc.)
        code_upper = code.upper().strip()
        for canonical, aliases in PROJECT_ALIASES.items():
            all_names = [canonical.upper()] + [a.upper() for a in aliases]
            if code_upper in all_names:
                # Try each name as a code/name match
                for name in all_names:
                    if name == code_upper:
                        continue
                    result = await self.db.execute(
                        select(Projet).where(
                            sa_func.upper(Projet.code) == name
                        )
                    )
                    projet = result.scalar_one_or_none()
                    if projet:
                        return projet
                    result = await self.db.execute(
                        select(Projet).where(
                            sa_func.upper(Projet.nom) == name
                        )
                    )
                    projet = result.scalar_one_or_none()
                    if projet:
                        return projet
                break  # Only check one alias group

        # 4. Match on name (partial)
        result = await self.db.execute(
            select(Projet).where(
                sa_func.upper(Projet.nom).contains(code.upper())
            )
        )
        projet = result.scalar_one_or_none()
        return projet

    async def resoudre_entite(self, name: str) -> Optional[Entreprise]:
        """Resolve an enterprise by name or partial match.

        1. Exact match on raison_sociale
        2. Partial match (contains)
        """
        # 1. Exact match
        result = await self.db.execute(
            select(Entreprise).where(Entreprise.raison_sociale == name)
        )
        ent = result.scalar_one_or_none()
        if ent:
            return ent

        # 2. Case-insensitive contains
        result = await self.db.execute(
            select(Entreprise).where(
                sa_func.upper(Entreprise.raison_sociale).contains(name.upper())
            )
        )
        ent = result.scalar_one_or_none()
        return ent

    async def verifier_unicite_projet(self) -> list[dict]:
        """Verify no duplicate project codes exist across all enterprises.

        Returns list of duplicate codes if any.
        """
        result = await self.db.execute(
            select(
                sa_func.upper(Projet.code).label("code_upper"),
                sa_func.count().label("cnt"),
            ).group_by(
                sa_func.upper(Projet.code)
            ).having(
                sa_func.count() > 1
            )
        )
        duplicates = result.all()
        return [
            {"code": row.code_upper, "count": row.cnt}
            for row in duplicates
        ]
