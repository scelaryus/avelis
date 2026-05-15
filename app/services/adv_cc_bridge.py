"""ADV → Centre de Coût bridge.

Automatically creates Encaissement records when ADV payments are received,
and Décaissement records when payroll is finalized.
These records are then visible in the CC hierarchy via the existing CC engine.
"""
from __future__ import annotations

import uuid
import structlog
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.adv import Payment, Contract, Client
from app.models.financial import (
    Encaissement, Decaissement, StatutFiscal,
    CategorieDepense, TypeCharge,
)
from app.models.cc_hierarchique import (
    CCImputation, CCNode, TypeImputation, SensImputation,
)

logger = structlog.get_logger(__name__)


async def create_encaissement_from_payment(
    payment: Payment,
    db: AsyncSession,
    *,
    created_by: str | None = None,
) -> Encaissement:
    """Create an Encaissement record from an ADV Payment.

    This bridges ADV → Financial → CC automatically.
    Uses payment.realite_financiere to determine StatutFiscal.
    """
    rf = getattr(payment, "realite_financiere", "RF1") or "RF1"
    rf_to_statut = {
        "RF1": StatutFiscal.REEL_DECLARE,
        "RF2": StatutFiscal.REEL_NON_DECLARE,
        "RF3": StatutFiscal.FICTIF_DECLARE,
        "RF4": StatutFiscal.FICTIF_NON_DECLARE,
    }
    statut_fiscal = rf_to_statut.get(rf, StatutFiscal.REEL_DECLARE)

    enc = Encaissement(
        id=str(uuid.uuid4()),
        tenant_id=payment.tenant_id,
        entreprise_id=payment.entreprise_id or "",
        projet_id=payment.projet_id,
        date_encaissement=payment.payment_date,
        montant=payment.amount,
        statut_fiscal=statut_fiscal,
        moyen_paiement=payment.payment_method,
        reference=payment.payment_ref or f"ADV-PAY-{payment.id[:8]}",
        banque=payment.bank_ref,
        description=f"Paiement client ADV - {payment.notes or ''}".strip(),
        created_by=created_by,
    )
    db.add(enc)
    await db.flush()

    # Also create CC imputation if we can find the right CC node
    await _create_cc_imputation_for_encaissement(enc, db, created_by=created_by)

    logger.info(
        "adv_payment_to_encaissement",
        payment_id=payment.id,
        encaissement_id=enc.id,
        montant=str(payment.amount),
    )
    return enc


async def create_decaissement_from_payroll(
    tenant_id: str,
    entreprise_id: str,
    projet_id: str | None,
    montant: Decimal,
    employee_name: str,
    period_label: str,
    db: AsyncSession,
    *,
    created_by: str | None = None,
) -> Decaissement:
    """Create a Décaissement record from a payroll payment.

    This bridges Payroll → Financial → CC automatically.
    """
    dec = Decaissement(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        entreprise_id=entreprise_id,
        projet_id=projet_id,
        date_decaissement=date.today(),
        montant=montant,
        statut_fiscal=StatutFiscal.REEL_DECLARE,
        type_charge=TypeCharge.COMMUNE if not projet_id else TypeCharge.PROJET,
        categorie_depense=CategorieDepense.MAIN_OEUVRE,
        description=f"Salaire {employee_name} - {period_label}",
        created_by=created_by,
    )
    db.add(dec)
    await db.flush()

    # Create CC imputation
    await _create_cc_imputation_for_decaissement(dec, db, created_by=created_by)

    logger.info(
        "payroll_to_decaissement",
        decaissement_id=dec.id,
        montant=str(montant),
        employee=employee_name,
    )
    return dec


async def _create_cc_imputation_for_encaissement(
    enc: Encaissement,
    db: AsyncSession,
    *,
    created_by: str | None = None,
) -> CCImputation | None:
    """Find the right CC node and create an imputation for this encaissement."""
    cc_node = await _find_cc_node(db, enc.tenant_id, enc.projet_id, enc.entreprise_id)
    if not cc_node:
        logger.warning("cc_node_not_found_for_encaissement", encaissement_id=enc.id)
        return None

    rf = "RF1"
    if enc.statut_fiscal == StatutFiscal.REEL_NON_DECLARE:
        rf = "RF2"
    elif enc.statut_fiscal in (StatutFiscal.FICTIF, StatutFiscal.FICTIF_DECLARE):
        rf = "RF3"
    elif enc.statut_fiscal == StatutFiscal.FICTIF_NON_DECLARE:
        rf = "RF4"

    periode = enc.date_encaissement.strftime("%Y-%m")

    imp = CCImputation(
        id=str(uuid.uuid4()),
        tenant_id=enc.tenant_id,
        cc_node_id=cc_node.id,
        date_imputation=enc.date_encaissement,
        periode=periode,
        encaissement_id=enc.id,
        type_imputation=TypeImputation.ENCAISSEMENT,
        sens=SensImputation.CREDIT,
        montant=enc.montant,
        realite_financiere=rf,
        libelle=enc.description or f"Encaissement {enc.reference}",
        quote_parts=[],
        created_by=created_by,
    )
    db.add(imp)
    return imp


async def _create_cc_imputation_for_decaissement(
    dec: Decaissement,
    db: AsyncSession,
    *,
    created_by: str | None = None,
) -> CCImputation | None:
    """Find the right CC node and create an imputation for this décaissement."""
    cc_node = await _find_cc_node(db, dec.tenant_id, dec.projet_id, dec.entreprise_id)
    if not cc_node:
        logger.warning("cc_node_not_found_for_decaissement", decaissement_id=dec.id)
        return None

    rf = "RF1"
    if dec.statut_fiscal == StatutFiscal.REEL_NON_DECLARE:
        rf = "RF2"
    elif dec.statut_fiscal in (StatutFiscal.FICTIF, StatutFiscal.FICTIF_DECLARE):
        rf = "RF3"

    periode = dec.date_decaissement.strftime("%Y-%m")

    imp = CCImputation(
        id=str(uuid.uuid4()),
        tenant_id=dec.tenant_id,
        cc_node_id=cc_node.id,
        date_imputation=dec.date_decaissement,
        periode=periode,
        decaissement_id=dec.id,
        type_imputation=TypeImputation.DECAISSEMENT_DIRECT,
        sens=SensImputation.DEBIT,
        montant=dec.montant,
        realite_financiere=rf,
        libelle=dec.description or f"Décaissement {dec.reference_facture}",
        quote_parts=[],
        created_by=created_by,
    )
    db.add(imp)
    return imp


async def _find_cc_node(
    db: AsyncSession,
    tenant_id: str,
    projet_id: str | None,
    entreprise_id: str | None,
) -> CCNode | None:
    """Find the most specific CC node for a given projet/entreprise."""
    # Try project-level node first
    if projet_id:
        result = await db.execute(
            select(CCNode).where(
                CCNode.tenant_id == tenant_id,
                CCNode.projet_id == projet_id,
                CCNode.est_actif == True,
            ).limit(1)
        )
        node = result.scalar_one_or_none()
        if node:
            return node

    # Fall back to entreprise-level node
    if entreprise_id:
        result = await db.execute(
            select(CCNode).where(
                CCNode.tenant_id == tenant_id,
                CCNode.entreprise_id == entreprise_id,
                CCNode.projet_id == None,
                CCNode.est_actif == True,
            ).limit(1)
        )
        node = result.scalar_one_or_none()
        if node:
            return node

    # Fall back to root node
    result = await db.execute(
        select(CCNode).where(
            CCNode.tenant_id == tenant_id,
            CCNode.niveau == 0,
            CCNode.est_actif == True,
        ).limit(1)
    )
    return result.scalar_one_or_none()
