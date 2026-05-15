"""Workflows Métier Spécifiques Dendani — Section 13.

8 historical business workflows that must be traced in the system.
Provides read-only status + ability to record entries for each workflow.
"""
import uuid as _uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.core import User, AuditLog
from app.models.financial import Entreprise, Projet, Transaction

router = APIRouter(tags=["Workflows Dendani"])


# ── WF data (from spec Section 13) ──────────────────────────────────────

WORKFLOWS = [
    {
        "code": "WF-01",
        "titre": "Origine du Capital — AMENFORT Béton",
        "description": "Tracer l'origine du capital fondateur provenant de la dissolution de SARL AMENFORT Béton. "
                       "Fonds transférés vers ETS Dendani Khadidja pour financer JASMIN et EDEN.",
        "entites": ["SARL-AMF", "ETS-DK"],
        "projets": ["JASMIN", "EDEN"],
        "exigence": "EX-WF-001",
        "actions_attendues": [
            "Créer les écritures d'apport en capital (D 512 / C 101)",
            "Rattacher les écritures au CC des projets JASMIN et EDEN",
            "Tracer la dissolution AMENFORT comme source",
        ],
        "categorie_cc": "CAPITAL",
    },
    {
        "code": "WF-02",
        "titre": "Avance GACEB 120M DA (Matériel AMENFORT)",
        "description": "GACEB Abderazak a reçu 120M DA de matériel d'AMENFORT (dissoute). "
                       "Créance déduite progressivement des situations de travaux GACEB sur EDEN.",
        "entites": ["SARL-AMF", "ETS-DK"],
        "projets": ["EDEN"],
        "exigence": "EX-WF-002",
        "actions_attendues": [
            "Créer créance de 120 000 000 DA sur GACEB",
            "À chaque situation GACEB/EDEN, déduire la part correspondante",
            "Suivre le solde restant jusqu'à apurement",
            "Imputer au CC EDEN, catégorie 03-GROS_OEUVRE",
        ],
        "montant": 120000000,
        "categorie_cc": "03-GROS_OEUVRE",
    },
    {
        "code": "WF-03",
        "titre": "Véhicules Cédés à GACEB",
        "description": "Véhicules cédés à GACEB en déduction de ses situations de travaux.",
        "entites": ["ETS-DK"],
        "projets": ["EDEN"],
        "exigence": "EX-WF-003",
        "actions_attendues": [
            "Range Rover (4 000 000 DA) — bénéficiaire Ahmed → cession GACEB → déduction EDEN",
            "Passat (6 500 000 DA) — bénéficiaire Yazid → cession GACEB → déduction EDEN",
            "Tracer : achat → immatriculation → cession → déduction situation → imputation CC",
        ],
        "montant": 10500000,
        "categorie_cc": "03-GROS_OEUVRE",
    },
    {
        "code": "WF-04",
        "titre": "Prélèvements d'Appartements JASMIN",
        "description": "Chaque associé a prélevé des appartements sur JASMIN. "
                       "Valorisés et déduits de la quote-part dans le CC.",
        "entites": ["ETS-DK"],
        "projets": ["JASMIN"],
        "exigence": "EX-WF-004",
        "actions_attendues": [
            "Ahmed : F3 + F2 → 25 000 000 DA — déduction quote-part Ahmed CC JASMIN",
            "Mohamed : F3 → 25 000 000 DA — déduction quote-part Mohamed CC JASMIN",
            "Yazid : F3 → 25 000 000 DA — déduction quote-part Yazid CC JASMIN",
        ],
        "montant": 75000000,
        "categorie_cc": "PRELEVEMENT_ASSOCIE",
    },
    {
        "code": "WF-05",
        "titre": "Appartements JASMIN Donnés à GACEB",
        "description": "Appartements JASMIN cédés à GACEB en avance sur fourniture béton pour OPÉRA. "
                       "Flux inter-projets JASMIN → OPÉRA.",
        "entites": ["ETS-DK", "SARL-DP"],
        "projets": ["JASMIN", "OPERA"],
        "exigence": "EX-WF-005",
        "actions_attendues": [
            "Tracer le flux inter-projets JASMIN → OPÉRA",
            "Imputer correctement dans les deux CC",
        ],
        "categorie_cc": "03-GROS_OEUVRE",
    },
    {
        "code": "WF-06",
        "titre": "Aménagement Oued JASMIN (20M DA)",
        "description": "Travaux d'aménagement de l'oued sur le site JASMIN — 20M DA.",
        "entites": ["ETS-DK"],
        "projets": ["JASMIN"],
        "exigence": "EX-WF-006",
        "actions_attendues": [
            "Imputer 20 000 000 DA au CC JASMIN",
            "Catégorie : 02-TERRAIN_ET_VRD",
        ],
        "montant": 20000000,
        "categorie_cc": "02-TERRAIN_ET_VRD",
    },
    {
        "code": "WF-07",
        "titre": "Bureau BBZ — Charge Commune Groupe",
        "description": "Le bureau BBZ (Bab Ezzouar) est le siège administratif. "
                       "Charges (loyer, électricité, salaires siège) ventilées sur tous les projets actifs.",
        "entites": ["SARL-DP"],
        "projets": [],
        "exigence": "EX-WF-007",
        "actions_attendues": [
            "Paramétrer la clé de répartition des charges communes (Socle S-31)",
            "Ventiler loyer, électricité, salaires siège sur projets actifs",
            "Catégorie CC : CHARGES_COMMUNES_SIEGE",
        ],
        "categorie_cc": "CHARGES_COMMUNES_SIEGE",
    },
    {
        "code": "WF-08",
        "titre": "Factures RF3 Inter-Groupe",
        "description": "Détection et traitement automatique des factures RF3 entre entités du groupe. "
                       "Chaque facture RF3 déclenche le moteur CFF (Section 3).",
        "entites": ["SARL-AMF", "EURL-BAY", "ETS-DK", "SARL-DP", "SARL-OC"],
        "projets": [],
        "exigence": "EX-WF-008",
        "actions_attendues": [
            "Détecter factures RF3 inter-groupe automatiquement",
            "Déclencher moteur CFF pour chaque facture RF3",
            "Imputer CFF selon % ENTREPRISE (jamais % projet)",
        ],
        "categorie_cc": "DOSSIER_FISCAL_FICTIF",
    },
]


@router.get("/")
async def list_workflows(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all 8 Dendani historical workflows with live status."""
    results = []
    for wf in WORKFLOWS:
        # Count related transactions
        txn_count = 0
        txn_montant = 0
        try:
            for proj_code in wf.get("projets", []):
                r = await db.execute(text("""
                    SELECT COUNT(*), COALESCE(SUM(montant), 0)
                    FROM transactions t
                    JOIN projets p ON t.projet_id = p.id
                    WHERE t.tenant_id = :tid AND p.code = :pc
                """), {"tid": user.tenant_id, "pc": proj_code})
                row = r.one()
                txn_count += row[0]
                txn_montant += float(row[1])
        except Exception:
            pass

        # Count journal entries
        je_count = 0
        try:
            for ent_code in wf.get("entites", []):
                r = await db.execute(text("""
                    SELECT COUNT(*)
                    FROM journal_entries je
                    JOIN entreprises e ON je.entreprise_id = e.id
                    WHERE je.tenant_id = :tid AND e.code = :ec
                """), {"tid": user.tenant_id, "ec": ent_code})
                je_count += r.scalar() or 0
        except Exception:
            pass

        # Determine status
        has_data = txn_count > 0 or je_count > 0
        montant_attendu = wf.get("montant")
        progress = 0
        if montant_attendu and txn_montant > 0:
            progress = min(100, round(txn_montant / montant_attendu * 100))
        elif has_data:
            progress = 50  # partial

        statut = "NON_DEMARRE"
        if progress >= 100:
            statut = "TERMINE"
        elif progress > 0 or has_data:
            statut = "EN_COURS"

        results.append({
            **wf,
            "statut": statut,
            "progress": progress,
            "transactions_count": txn_count,
            "transactions_montant": txn_montant,
            "journal_entries_count": je_count,
        })

    return results


@router.get("/summary")
async def workflows_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Quick summary counts for the dashboard."""
    wf_list = await list_workflows(user=user, db=db)
    total = len(wf_list)
    termine = sum(1 for w in wf_list if w["statut"] == "TERMINE")
    en_cours = sum(1 for w in wf_list if w["statut"] == "EN_COURS")
    non_demarre = sum(1 for w in wf_list if w["statut"] == "NON_DEMARRE")
    return {
        "total": total,
        "termine": termine,
        "en_cours": en_cours,
        "non_demarre": non_demarre,
        "completion_pct": round(termine / total * 100) if total > 0 else 0,
    }
