"""
GFI v7.0 — Réalité Financière (RF) classification and enforcement.

Every financial transaction is classified into exactly one of 4 RFs.
This is a mandatory non-null field on ALL financial tables.

RF1 — Réel Déclaré:     Real, declared. Cheque/virement/notary only.
RF2 — Réel Non Déclaré: Real, not declared. Cash (espèces) only. Encrypted.
RF3 — Fictif Déclaré:   Inter-group fictitious invoices. Declared. Triggers CFF.
RF4 — Fictif Non Déclaré: No economic/fiscal basis. Rare. DAF review.

Prix Réel = RF1 + RF2 (what Centre de Coûts uses)
Vue Officielle = RF1 + RF3 (what tax authority sees)
Vue Interne = RF1 + RF2 + RF3 + RF4 (economic reality)
Écart = Vue Interne − Vue Officielle = RF2 + RF4

Database-level enforcement:
- CHECK constraint: rf_type IN ('RF1','RF2','RF3','RF4')
- CHECK constraint: RF1 → payment_mode IN ('CHEQUE','VIREMENT','CHEQUE_NOTAIRE')
- CHECK constraint: RF2 → payment_mode = 'ESPECES'
- Trigger: RF3 inter-group → auto-queue CFF calculation
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ═════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═════════════════════════════════════════════════════════════════════════════

class RealiteFinanciere(Enum):
    """The 4 financial realities. Mandatory on every financial record."""

    RF1 = "RF1"  # Réel Déclaré
    RF2 = "RF2"  # Réel Non Déclaré
    RF3 = "RF3"  # Fictif Déclaré
    RF4 = "RF4"  # Fictif Non Déclaré

    @property
    def is_reel(self) -> bool:
        return self in (RealiteFinanciere.RF1, RealiteFinanciere.RF2)

    @property
    def is_declare(self) -> bool:
        return self in (RealiteFinanciere.RF1, RealiteFinanciere.RF3)

    @property
    def is_fictif(self) -> bool:
        return self in (RealiteFinanciere.RF3, RealiteFinanciere.RF4)


class PaymentMode(Enum):
    """Payment modes with RF-level constraints."""

    ESPECES = "ESPECES"
    CHEQUE = "CHEQUE"
    VIREMENT = "VIREMENT"
    CHEQUE_NOTAIRE = "CHEQUE_NOTAIRE"
    COMPENSATION = "COMPENSATION"  # offset / netting
    SANS_OBJET = "SANS_OBJET"     # RF3/RF4 with no payment


# RF → allowed payment modes (hard constraint)
RF_PAYMENT_RULES: dict[RealiteFinanciere, set[PaymentMode]] = {
    RealiteFinanciere.RF1: {
        PaymentMode.CHEQUE,
        PaymentMode.VIREMENT,
        PaymentMode.CHEQUE_NOTAIRE,
    },
    RealiteFinanciere.RF2: {
        PaymentMode.ESPECES,
    },
    RealiteFinanciere.RF3: {
        PaymentMode.SANS_OBJET,
        PaymentMode.COMPENSATION,
    },
    RealiteFinanciere.RF4: {
        PaymentMode.SANS_OBJET,
    },
}

# Error messages (exact wording from spec)
RF_PAYMENT_ERROR = {
    RealiteFinanciere.RF1: (
        "Transaction RF1 : mode de règlement espèces interdit. "
        "Utilisez chèque ou virement."
    ),
    RealiteFinanciere.RF2: (
        "Transaction RF2 : seules les espèces sont autorisées."
    ),
    RealiteFinanciere.RF3: (
        "Transaction RF3 : seules la compensation et sans objet "
        "sont autorisées."
    ),
    RealiteFinanciere.RF4: (
        "Transaction RF4 : seul le mode sans objet est autorisé."
    ),
}


# ═════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ═════════════════════════════════════════════════════════════════════════════

class RFPaymentViolation(Exception):
    """Raised when RF type and payment mode are incompatible."""

    def __init__(self, message: str, rf_type: str, payment_mode: str):
        super().__init__(message)
        self.rf_type = rf_type
        self.payment_mode = payment_mode


def validate_rf_payment(
    rf_type: RealiteFinanciere | str,
    payment_mode: PaymentMode | str,
) -> None:
    """
    Validate RF type / payment mode compatibility.
    Raises RFPaymentViolation if incompatible.

    This is ALSO enforced at database level via CHECK constraint,
    but we validate in Python for better error messages.
    """
    if isinstance(rf_type, str):
        rf_type = RealiteFinanciere(rf_type)
    if isinstance(payment_mode, str):
        payment_mode = PaymentMode(payment_mode)

    allowed = RF_PAYMENT_RULES[rf_type]
    if payment_mode not in allowed:
        raise RFPaymentViolation(
            RF_PAYMENT_ERROR[rf_type],
            rf_type=rf_type.value,
            payment_mode=payment_mode.value,
        )


# ═════════════════════════════════════════════════════════════════════════════
# DOUBLE VIEW: Vue Officielle / Vue Interne / Écart
# ═════════════════════════════════════════════════════════════════════════════

# Which RF types contribute to each view
VUE_OFFICIELLE_RFS = frozenset({RealiteFinanciere.RF1, RealiteFinanciere.RF3})
VUE_INTERNE_RFS = frozenset({
    RealiteFinanciere.RF1, RealiteFinanciere.RF2,
    RealiteFinanciere.RF3, RealiteFinanciere.RF4,
})
PRIX_REEL_RFS = frozenset({RealiteFinanciere.RF1, RealiteFinanciere.RF2})
ECART_RFS = frozenset({RealiteFinanciere.RF2, RealiteFinanciere.RF4})


def compute_views(
    transactions: list[dict],
) -> dict:
    """
    Compute the double view from a list of transactions.

    Each transaction dict must have: 'rf_type' (str) and 'amount' (Decimal).

    Returns:
        {
            "vue_officielle": Decimal,  # RF1 + RF3
            "vue_interne": Decimal,     # RF1 + RF2 + RF3 + RF4
            "ecart": Decimal,           # RF2 + RF4
            "prix_reel": Decimal,       # RF1 + RF2
            "by_rf": {"RF1": Decimal, "RF2": Decimal, ...}
        }
    """
    by_rf = {rf.value: Decimal("0") for rf in RealiteFinanciere}

    for tx in transactions:
        rf = tx["rf_type"]
        if isinstance(rf, RealiteFinanciere):
            rf = rf.value
        by_rf[rf] += Decimal(str(tx["amount"]))

    vue_off = sum(by_rf[rf.value] for rf in VUE_OFFICIELLE_RFS)
    vue_int = sum(by_rf[rf.value] for rf in VUE_INTERNE_RFS)
    ecart = sum(by_rf[rf.value] for rf in ECART_RFS)
    prix_reel = sum(by_rf[rf.value] for rf in PRIX_REEL_RFS)

    return {
        "vue_officielle": vue_off,
        "vue_interne": vue_int,
        "ecart": ecart,
        "prix_reel": prix_reel,
        "by_rf": by_rf,
    }


def filter_for_export(
    transactions: list[dict],
    *,
    user_has_rf2: bool,
    export_type: str,
) -> list[dict]:
    """
    Filter transactions for export based on export type and RF2 access.

    export_type:
        "BANK"   → Vue Officielle only (RF1 + RF3)
        "TAX"    → Vue Officielle only (RF1 + RF3)
        "CLIENT" → RF1 only (no RF2, no RF3)
        "INTERNAL" → all RFs if user has RF2 access, else RF1+RF3+RF4

    RF2 data is PHYSICALLY removed, not just hidden.
    """
    if export_type in ("BANK", "TAX"):
        # Vue Officielle: RF1 + RF3 only
        return [tx for tx in transactions
                if tx["rf_type"] in ("RF1", "RF3",
                                     RealiteFinanciere.RF1,
                                     RealiteFinanciere.RF3)]

    if export_type == "CLIENT":
        # Client-facing: RF1 only, no RF2, no RF3, no RF4
        return [tx for tx in transactions
                if tx["rf_type"] in ("RF1", RealiteFinanciere.RF1)]

    # INTERNAL export
    if user_has_rf2:
        return list(transactions)  # all RFs
    else:
        # Strip RF2 entirely
        return [tx for tx in transactions
                if tx["rf_type"] not in ("RF2", RealiteFinanciere.RF2)]


def strip_rf2_from_record(record: dict) -> dict:
    """
    Remove ALL RF2-related fields from a record dict.
    Used when a user without RF2 access queries financial data.

    This PHYSICALLY removes the fields — not just nullifies values.
    """
    rf2_fields = {
        "rf2_amount", "rf2_payment_ref", "rf2_receipt_ref",
        "montant_rf2", "amount_rf2", "rf2_total",
    }
    return {k: v for k, v in record.items() if k not in rf2_fields}


# ═════════════════════════════════════════════════════════════════════════════
# RF3 CFF AUTO-TRIGGER
# ═════════════════════════════════════════════════════════════════════════════

def check_rf3_cff_trigger(
    session: Session,
    *,
    rf_type: RealiteFinanciere | str,
    emitter_company_id: UUID,
    receiver_company_id: UUID | None,
) -> bool:
    """
    Check if an RF3 transaction between two group entities should
    auto-trigger the CFF engine.

    Returns True if CFF should be triggered (both emitter and receiver
    are group entities).
    """
    if isinstance(rf_type, str):
        rf_type = RealiteFinanciere(rf_type)

    if rf_type != RealiteFinanciere.RF3:
        return False

    if receiver_company_id is None:
        return False

    from app.models.company import Company

    # Both must be group entities (exist in company table)
    emitter = session.get(Company, emitter_company_id)
    receiver = session.get(Company, receiver_company_id)

    return (emitter is not None and receiver is not None
            and not emitter.is_deleted and not receiver.is_deleted)
