"""Tax declaration computation engine.

Implements EX-SCF-005:
  - G50 (monthly): TVA collectée - TVA déductible, TAP, IBS acompte
  - CNAS (quarterly): from payroll data
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


async def compute_g50(
    db: AsyncSession,
    tenant_id: str,
    entreprise_id: str,
    mois: int,
    annee: int,
) -> dict:
    """Compute G50 monthly declaration from committed journal entries.

    G50 includes:
      - TVA collectée (account 4457) - TVA déductible (account 4456) = TVA nette
      - TAP (account 4471)
      - IBS acompte (account 441)
      - Timbre fiscal (account 4473)

    Returns a dict with all computed amounts.
    """
    period_start = f"{annee}-{mois:02d}-01"
    if mois == 12:
        period_end = f"{annee + 1}-01-01"
    else:
        period_end = f"{annee}-{mois + 1:02d}-01"

    # Sum credits on 4457 (TVA collectée)
    tva_collectee = await _sum_account(
        db, tenant_id, entreprise_id, "4457", period_start, period_end, "credit"
    )
    # Sum debits on 4456 (TVA déductible)
    tva_deductible = await _sum_account(
        db, tenant_id, entreprise_id, "4456", period_start, period_end, "debit"
    )
    tva_nette = tva_collectee - tva_deductible

    # TAP — sum credits on 4471
    tap = await _sum_account(
        db, tenant_id, entreprise_id, "4471", period_start, period_end, "credit"
    )
    # If no TAP entries yet, compute from revenue * taux_tap
    if tap == 0:
        revenue = await _sum_account(
            db, tenant_id, entreprise_id, "70", period_start, period_end, "credit"
        )
        taux_tap = await _get_entity_rate(db, entreprise_id, "taux_tap", Decimal("0.02"))
        tap = revenue * taux_tap

    # IBS acompte — sum on 441
    ibs = await _sum_account(
        db, tenant_id, entreprise_id, "441", period_start, period_end, "debit"
    )

    # Timbre
    timbre = await _sum_account(
        db, tenant_id, entreprise_id, "4473", period_start, period_end, "credit"
    )

    # Chiffre d'affaires (revenue accounts 70x)
    ca_ht = await _sum_account(
        db, tenant_id, entreprise_id, "70", period_start, period_end, "credit"
    )

    # IRG retenu (4472)
    irg = await _sum_account(
        db, tenant_id, entreprise_id, "4472", period_start, period_end, "credit"
    )

    return {
        "type_declaration": "G50",
        "entreprise_id": entreprise_id,
        "periode": f"{annee}-{mois:02d}",
        "mois": mois,
        "annee": annee,
        "ca_ht": float(ca_ht),
        "tva_collectee": float(tva_collectee),
        "tva_deductible": float(tva_deductible),
        "tva_nette": float(tva_nette),
        "tap": float(tap),
        "ibs_acompte": float(ibs),
        "irg": float(irg),
        "timbre": float(timbre),
        "total_a_payer": float(tva_nette + tap + ibs + irg + timbre),
    }


async def compute_cnas_trimestrielle(
    db: AsyncSession,
    tenant_id: str,
    entreprise_id: str,
    trimestre: int,
    annee: int,
) -> dict:
    """Compute CNAS quarterly declaration from payroll entries.

    CNAS = sum of account 431 (CNAS) + 635 (cotisations) for the quarter.
    """
    mois_debut = (trimestre - 1) * 3 + 1
    mois_fin = trimestre * 3
    period_start = f"{annee}-{mois_debut:02d}-01"
    if mois_fin == 12:
        period_end = f"{annee + 1}-01-01"
    else:
        period_end = f"{annee}-{mois_fin + 1:02d}-01"

    # Masse salariale brute (account 631)
    masse_salariale = await _sum_account(
        db, tenant_id, entreprise_id, "631", period_start, period_end, "debit"
    )
    # Cotisations CNAS patronales (account 635)
    cnas_patronale = await _sum_account(
        db, tenant_id, entreprise_id, "635", period_start, period_end, "debit"
    )
    # CNAS salariale (account 431)
    cnas_salariale = await _sum_account(
        db, tenant_id, entreprise_id, "431", period_start, period_end, "credit"
    )

    return {
        "type_declaration": "CNAS",
        "entreprise_id": entreprise_id,
        "periode": f"{annee}-T{trimestre}",
        "trimestre": trimestre,
        "annee": annee,
        "masse_salariale_brute": float(masse_salariale),
        "cotisation_patronale": float(cnas_patronale),
        "cotisation_salariale": float(cnas_salariale),
        "total_cotisations": float(cnas_patronale + cnas_salariale),
    }


async def _sum_account(
    db: AsyncSession,
    tenant_id: str,
    entreprise_id: str,
    account_prefix: str,
    date_start: str,
    date_end: str,
    side: str,  # "debit" or "credit"
) -> Decimal:
    """Sum debit or credit for account codes starting with prefix in date range."""
    result = await db.execute(
        text(f"""
            SELECT COALESCE(SUM(jl.{side}), 0)
            FROM journal_lines jl
            JOIN journal_entries je ON jl.entry_id = je.id
            WHERE je.tenant_id = :tid
              AND je.entreprise_id = :eid
              AND je.status IN ('COMMITTED', 'VALIDATED')
              AND je.entry_date >= :d1
              AND je.entry_date < :d2
              AND jl.account_code LIKE :prefix
        """),
        {
            "tid": tenant_id,
            "eid": entreprise_id,
            "d1": date_start,
            "d2": date_end,
            "prefix": f"{account_prefix}%",
        },
    )
    return Decimal(str(result.scalar() or 0))


async def _get_entity_rate(
    db: AsyncSession, entreprise_id: str, field: str, default: Decimal
) -> Decimal:
    """Get a tax rate from the entreprise record."""
    result = await db.execute(
        text(f"SELECT {field} FROM entreprises WHERE id = :eid"),
        {"eid": entreprise_id},
    )
    val = result.scalar()
    return Decimal(str(val)) if val else default
