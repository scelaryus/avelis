"""Moteur de Détection Intelligente — Section 16.

15 detection patterns that scan the database autonomously.
Each pattern returns detected items with severity and recommended actions.
"""
from sqlalchemy import select, text, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal


PATTERNS = [
    {"id": 1, "code": "ENTREPRISES", "nom": "Détection d'entreprises", "description": "Entités juridiques dans les documents"},
    {"id": 2, "code": "ASSOCIES", "nom": "Détection d'associés", "description": "Noms d'associés et résolution d'alias"},
    {"id": 3, "code": "PROJETS", "nom": "Détection de projets", "description": "Projets et résolution d'alias"},
    {"id": 4, "code": "FACTURES_RF3", "nom": "Détection de factures RF3", "description": "Factures inter-groupe sans prestation réelle"},
    {"id": 5, "code": "FLUX_RF2", "nom": "Détection de flux RF2", "description": "Mouvements en espèces non déclarés"},
    {"id": 6, "code": "DOUBLONS", "nom": "Détection de doublons", "description": "Documents et écritures en double"},
    {"id": 7, "code": "FLUX_INTER_PROJETS", "nom": "Détection de flux inter-projets", "description": "Transferts entre projets via caisse commune"},
    {"id": 8, "code": "PRELEVEMENTS", "nom": "Détection de prélèvements associés", "description": "Retraits en nature (appartements, véhicules)"},
    {"id": 9, "code": "CESSIONS", "nom": "Détection de cessions de parts", "description": "Changements d'actionnariat"},
    {"id": 10, "code": "ANOMALIES_COMPTA", "nom": "Détection d'anomalies comptables", "description": "Écritures déséquilibrées ou incohérentes"},
    {"id": 11, "code": "RETARDS_PAIEMENT", "nom": "Détection de retards de paiement", "description": "Échéances non honorées"},
    {"id": 12, "code": "SOUS_TRAITANTS", "nom": "Détection de sous-traitants", "description": "ST et leurs spécialités"},
    {"id": 13, "code": "TERRAINS", "nom": "Détection de terrains", "description": "Acquisitions foncières"},
    {"id": 14, "code": "VEHICULES", "nom": "Détection de véhicules", "description": "Achats et cessions de véhicules"},
    {"id": 15, "code": "FOURNISSEURS", "nom": "Détection de fournisseurs", "description": "Fournisseurs et résolution d'alias"},
]


async def run_all_detections(tenant_id: str, db: AsyncSession) -> list[dict]:
    """Run all 15 detection patterns and return results."""
    results = []
    for p in PATTERNS:
        try:
            count, items = await _run_pattern(p["code"], tenant_id, db)
            results.append({
                **p,
                "count": count,
                "items": items[:10],  # top 10 per pattern
                "statut": "ALERTE" if count > 0 else "OK",
            })
        except Exception as exc:
            results.append({**p, "count": 0, "items": [], "statut": "ERREUR", "erreur": str(exc)})
    return results


async def _run_pattern(code: str, tid: str, db: AsyncSession) -> tuple[int, list]:
    """Execute a specific detection pattern."""

    if code == "ENTREPRISES":
        # Count documents with unresolved entreprise
        r = await db.execute(text(
            "SELECT COUNT(*) FROM documents WHERE tenant_id = :tid AND entreprise_id IS NULL"
        ), {"tid": tid})
        count = r.scalar() or 0
        return count, [{"detail": f"{count} document(s) sans entité juridique identifiée"}] if count else []

    if code == "ASSOCIES":
        r = await db.execute(text("SELECT COUNT(*) FROM associes WHERE tenant_id = :tid AND is_active = 1"), {"tid": tid})
        total = r.scalar() or 0
        r2 = await db.execute(text("SELECT COUNT(*) FROM associate_aliases"), {})
        aliases = r2.scalar() or 0
        return total, [{"detail": f"{total} associé(s) actifs, {aliases} alias configurés"}]

    if code == "PROJETS":
        r = await db.execute(text("SELECT COUNT(*) FROM documents WHERE tenant_id = :tid AND projet_id IS NULL AND entreprise_id IS NOT NULL"), {"tid": tid})
        count = r.scalar() or 0
        return count, [{"detail": f"{count} document(s) liés à une entité mais pas à un projet"}] if count else []

    if code == "FACTURES_RF3":
        r = await db.execute(text(
            "SELECT COUNT(*) FROM transactions WHERE tenant_id = :tid AND realite_financiere = 'RF3'"
        ), {"tid": tid})
        count = r.scalar() or 0
        return count, [{"detail": f"{count} transaction(s) RF3 (factures fictives inter-groupe) détectée(s)", "severity": "WARNING"}] if count else []

    if code == "FLUX_RF2":
        r = await db.execute(text(
            "SELECT COUNT(*), COALESCE(SUM(montant), 0) FROM transactions WHERE tenant_id = :tid AND realite_financiere = 'RF2'"
        ), {"tid": tid})
        row = r.one()
        return row[0], [{"detail": f"{row[0]} flux RF2 pour {float(row[1]):,.0f} DA", "severity": "INFO"}] if row[0] else []

    if code == "DOUBLONS":
        r = await db.execute(text("""
            SELECT sha256, COUNT(*) as cnt FROM documents WHERE tenant_id = :tid
            GROUP BY sha256 HAVING cnt > 1
        """), {"tid": tid})
        rows = r.fetchall()
        return len(rows), [{"detail": f"Hash {r[0][:12]}... apparaît {r[1]} fois"} for r in rows]

    if code == "FLUX_INTER_PROJETS":
        r = await db.execute(text(
            "SELECT COUNT(*) FROM transactions WHERE tenant_id = :tid AND type_transaction = 'VIREMENT_INTERNE'"
        ), {"tid": tid})
        count = r.scalar() or 0
        return count, [{"detail": f"{count} virement(s) interne(s) détecté(s)"}] if count else []

    if code == "PRELEVEMENTS":
        r = await db.execute(text("SELECT COUNT(*) FROM retraits_associes WHERE tenant_id = :tid"), {"tid": tid})
        count = r.scalar() or 0
        return count, [{"detail": f"{count} prélèvement(s)/retrait(s) enregistré(s)"}] if count else []

    if code == "CESSIONS":
        try:
            r = await db.execute(text("SELECT COUNT(*) FROM cessions_parts WHERE tenant_id = :tid"), {"tid": tid})
            count = r.scalar() or 0
        except Exception:
            count = 0
        return count, [{"detail": f"{count} cession(s) de parts détectée(s)"}] if count else []

    if code == "ANOMALIES_COMPTA":
        # Detect unbalanced journal entries
        r = await db.execute(text("""
            SELECT je.id, je.reference, ABS(SUM(jl.debit) - SUM(jl.credit)) as ecart
            FROM journal_entries je
            JOIN journal_lines jl ON jl.entry_id = je.id
            WHERE je.tenant_id = :tid
            GROUP BY je.id HAVING ecart > 0.01
        """), {"tid": tid})
        rows = r.fetchall()
        return len(rows), [{"detail": f"Écriture {r[1] or r[0][:8]} — écart {float(r[2]):,.2f} DA", "severity": "BLOCKING"} for r in rows]

    if code == "RETARDS_PAIEMENT":
        r = await db.execute(text("""
            SELECT COUNT(*) FROM dossiers_vente
            WHERE tenant_id = :tid AND statut_lot = 'DEFAUT_PAIEMENT'
        """), {"tid": tid})
        count = r.scalar() or 0
        return count, [{"detail": f"{count} dossier(s) en défaut de paiement"}] if count else []

    if code == "SOUS_TRAITANTS":
        r = await db.execute(text("SELECT COUNT(*) FROM sous_traitants WHERE tenant_id = :tid"), {"tid": tid})
        count = r.scalar() or 0
        # Low performers
        r2 = await db.execute(text("SELECT COUNT(*) FROM sous_traitants WHERE tenant_id = :tid AND score_global < 50"), {"tid": tid})
        low = r2.scalar() or 0
        items = [{"detail": f"{count} ST enregistré(s)"}]
        if low:
            items.append({"detail": f"{low} ST avec score < 50/100", "severity": "WARNING"})
        return low, items

    if code == "TERRAINS":
        r = await db.execute(text(
            "SELECT COUNT(*) FROM projets WHERE tenant_id = :tid AND (statut = 'TERRAIN' OR type_projet = 'TERRAIN')"
        ), {"tid": tid})
        count = r.scalar() or 0
        return count, [{"detail": f"{count} terrain(s) identifié(s)"}] if count else []

    if code == "VEHICULES":
        try:
            r = await db.execute(text("SELECT COUNT(*) FROM vehicules_groupe WHERE tenant_id = :tid"), {"tid": tid})
            count = r.scalar() or 0
        except Exception:
            count = 0
        return count, [{"detail": f"{count} véhicule(s) tracé(s)"}] if count else []

    if code == "FOURNISSEURS":
        r = await db.execute(text("SELECT COUNT(*) FROM fournisseurs WHERE tenant_id = :tid"), {"tid": tid})
        count = r.scalar() or 0
        fictifs = await db.execute(text("SELECT COUNT(*) FROM fournisseurs WHERE tenant_id = :tid AND est_fictif = 1"), {"tid": tid})
        f_count = fictifs.scalar() or 0
        items = [{"detail": f"{count} fournisseur(s)"}]
        if f_count:
            items.append({"detail": f"{f_count} fournisseur(s) FICTIF(S) détecté(s)", "severity": "WARNING"})
        return f_count, items

    return 0, []
