# GAP 3 — VALIDATIONS BLOQUANTES — blocking_rules.py
"""Blocking validation rules applied at write time.

Every rule raises BlockingError if violated — never auto-validates.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession


class BlockingError(Exception):
    """Raised when a blocking business rule is violated."""
    def __init__(self, message: str, payload: dict | None = None):
        super().__init__(message)
        self.payload = payload or {}


async def validate_retrait_associe(
    associe_id: str, montant: Decimal, db: AsyncSession
) -> dict:
    """Validate withdrawal against R-003 double rule. Returns balance snapshot.

    R-003 Rule 1: retrait <= 50% of individual CCA balance
    R-003 Rule 2: global CCA balance must be positive
    Also checks: account exists, not frozen.

    Returns dict with solde_individuel, max_autorise, solde_global_cca for audit.
    Raises BlockingError if any rule is violated.
    """
    from app.models.finance_associes import CompteCourantAssocie

    # Check account exists
    result = await db.execute(
        select(CompteCourantAssocie).where(
            CompteCourantAssocie.associe_id == associe_id,
        )
    )
    compte = result.scalar_one_or_none()

    if not compte:
        raise BlockingError(
            "Compte courant introuvable pour cet associé. "
            "Le CCA doit être créé avant tout retrait.",
            payload={"rule": "CCA_NOT_FOUND"},
        )

    # Check frozen
    if compte.est_gele:
        raise BlockingError(
            f"Compte gelé : {compte.motif_gel or 'aucun motif spécifié'}",
            payload={"rule": "FROZEN"},
        )

    solde = Decimal(str(compte.solde_global or 0))
    max_autorise = solde * Decimal("0.50")

    # R-003 Rule 1: retrait <= 50% of individual balance
    if montant > max_autorise:
        raise BlockingError(
            f"BLOCAGE R-003 Règle 1 : Le retrait de {montant:,.2f} DA dépasse "
            f"50% du solde individuel ({solde:,.2f} DA). "
            f"Maximum autorisé : {max_autorise:,.2f} DA.",
            payload={
                "rule": "R003_RULE1_50PCT",
                "solde_individuel": float(solde),
                "max_autorise": float(max_autorise),
                "montant_demande": float(montant),
            },
        )

    # R-003 Rule 2: global CCA balance must be positive
    global_result = await db.execute(
        select(sa_func.coalesce(sa_func.sum(CompteCourantAssocie.solde_global), Decimal("0")))
    )
    solde_global = Decimal(str(global_result.scalar() or 0))

    if solde_global <= 0:
        raise BlockingError(
            f"BLOCAGE R-003 Règle 2 : Le solde global de tous les CCA est "
            f"négatif ou nul ({solde_global:,.2f} DA). "
            f"Aucun retrait autorisé tant que le solde global n'est pas positif.",
            payload={
                "rule": "R003_RULE2_GLOBAL_NEGATIVE",
                "solde_global_cca": float(solde_global),
            },
        )

    # Additional check: retrait shouldn't make global negative
    if (solde_global - montant) < 0:
        raise BlockingError(
            f"BLOCAGE R-003 Règle 2 : Ce retrait de {montant:,.2f} DA rendrait "
            f"le solde global négatif ({solde_global:,.2f} → {solde_global - montant:,.2f} DA).",
            payload={
                "rule": "R003_RULE2_WOULD_GO_NEGATIVE",
                "solde_global_cca": float(solde_global),
                "solde_apres_retrait": float(solde_global - montant),
            },
        )

    return {
        "solde_individuel": float(solde),
        "max_autorise": float(max_autorise),
        "solde_global_cca": float(solde_global),
    }


async def validate_project_shares_sum(
    projet_id: str,
    db: AsyncSession,
    exclude_share_id: Optional[str] = None,
    new_pourcentage: Optional[Decimal] = None,
) -> None:
    """Block if total shares for a project would exceed 100%."""
    from app.models.registry import PartProjet

    q = select(sa_func.coalesce(sa_func.sum(PartProjet.pourcentage), Decimal("0"))).where(
        PartProjet.projet_id == projet_id,
    )
    if exclude_share_id:
        q = q.where(PartProjet.id != exclude_share_id)

    result = await db.execute(q)
    current_sum = Decimal(str(result.scalar() or 0))

    if new_pourcentage is not None:
        projected_sum = current_sum + new_pourcentage
    else:
        projected_sum = current_sum

    if projected_sum > Decimal("100.00"):
        raise BlockingError(
            f"Somme des parts dépasse 100% pour ce projet "
            f"(somme projetée : {projected_sum}%)"
        )


async def validate_associate_exact_match(
    nom: str, db: AsyncSession
):
    """Resolve associate by exact match on nom_complet or alias.

    NEVER validates automatically via fuzzy match — returns suggestions only.
    """
    from app.models.financial import Associe
    from app.models.finance_associes import AssociateAlias

    # 1. Exact match on alias
    alias_result = await db.execute(
        select(AssociateAlias).where(AssociateAlias.alias == nom)
    )
    alias_row = alias_result.scalar_one_or_none()
    if alias_row:
        assoc_result = await db.execute(
            select(Associe).where(Associe.id == alias_row.associe_id)
        )
        assoc = assoc_result.scalar_one_or_none()
        if assoc:
            return assoc

    # 2. Exact match on nom or (nom + prenom)
    result = await db.execute(select(Associe).where(Associe.is_active == True))
    all_associes = result.scalars().all()

    for a in all_associes:
        full = f"{a.nom} {a.prenom}".strip() if a.prenom else a.nom
        if full.lower() == nom.lower() or a.nom.lower() == nom.lower():
            return a

    # 3. Fuzzy suggestions via Levenshtein (using rapidfuzz)
    suggestions = []
    try:
        from rapidfuzz import fuzz

        for a in all_associes:
            full = f"{a.nom} {a.prenom}".strip() if a.prenom else a.nom
            score = fuzz.ratio(nom.lower(), full.lower())
            if score >= 60:
                suggestions.append({
                    "id": a.id,
                    "nom": full,
                    "score": round(score, 1),
                })
    except ImportError:
        # rapidfuzz not installed — basic string containment fallback
        for a in all_associes:
            full = f"{a.nom} {a.prenom}".strip() if a.prenom else a.nom
            if nom.lower() in full.lower() or full.lower() in nom.lower():
                suggestions.append({
                    "id": a.id,
                    "nom": full,
                    "score": 50.0,
                })

    suggestions.sort(key=lambda s: s["score"], reverse=True)
    top_suggestions = suggestions[:3]

    raise BlockingError(
        f"Aucun associé trouvé pour '{nom}'. Résolution automatique interdite.",
        payload={"suggestions": top_suggestions},
    )


async def validate_share_transfer_integrity(
    projet_id: str, vendeur_id: str,
    pct_cedees: Decimal, db: AsyncSession
) -> None:
    """Verify vendor owns the shares and post-transfer sum stays valid."""
    from app.models.registry import PartProjet

    # Check vendor has a share in this project
    result = await db.execute(
        select(PartProjet).where(
            PartProjet.projet_id == projet_id,
            PartProjet.associe_id == vendeur_id,
        )
    )
    vendor_part = result.scalar_one_or_none()
    if not vendor_part:
        raise BlockingError(
            f"Le vendeur ne possède aucune part dans ce projet"
        )

    vendor_pct = Decimal(str(vendor_part.pourcentage))
    if pct_cedees > vendor_pct:
        raise BlockingError(
            f"Le vendeur ne possède que {vendor_pct}% mais tente de céder {pct_cedees}%"
        )


# ════════════════════════════════════════════════════════════════════════════
# Section 18/20: Separation of Duties (SoD) — Socle S-08 / EX-SEC-001
# ════════════════════════════════════════════════════════════════════════════

def validate_sod(action: str, creator_id: str, validator_id: str) -> None:
    """Block if the same person tries to create AND validate (maker/checker).

    EX-SEC-001 (KT-06): Enforces separation of duties.
    """
    if creator_id == validator_id:
        raise BlockingError(
            f"BLOCAGE Socle S-08 (KT-06) : Séparation des tâches violée — "
            f"la personne qui crée ({action}) ne peut pas la valider.",
            payload={"rule": "SOD_VIOLATION", "action": action},
        )


def validate_rf2_access(user_role: str, realite_financiere: str) -> None:
    """Block commercial users from accessing RF2 data.

    EX-UI-001: Un agent commercial ne voit JAMAIS les données RF2.
    """
    from app.services.rbac import _normalize_role

    role = _normalize_role(user_role)
    BLOCKED_RF2_ROLES = {"COMMERCIAL", "EMPLOYE", "VIEWER", "TELECONSEILLERE"}

    if role in BLOCKED_RF2_ROLES and realite_financiere == "RF2":
        raise BlockingError(
            f"BLOCAGE EX-UI-001 : Le rôle {role} n'a pas accès aux données RF2 (Réel Non Déclaré).",
            payload={"rule": "RF2_ACCESS_DENIED", "role": role},
        )


def validate_soft_delete_only(table_name: str) -> None:
    """Block physical DELETE on financial tables.

    EX-SEC-003 (KT-10): Only soft delete (is_deleted=true) is allowed.
    """
    PROTECTED_TABLES = {
        "transactions", "journal_entries", "journal_lines",
        "factures_fournisseur", "cff_factures", "situations_travaux",
        "comptes_courants_associes", "mouvements_comptes_courants",
        "clotures_mensuelles", "appels_de_fonds", "cessions_parts",
        "dossiers_vente", "retraits_associes",
    }
    if table_name in PROTECTED_TABLES:
        raise BlockingError(
            f"BLOCAGE EX-SEC-003 (KT-10) : Suppression physique interdite sur la table '{table_name}'. "
            f"Utilisez le soft delete (is_deleted = true).",
            payload={"rule": "PHYSICAL_DELETE_BLOCKED", "table": table_name},
        )
