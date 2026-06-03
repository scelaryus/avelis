"""
GFI v7.0 — FinancialTransaction: the base financial record.

Every financial movement in GFI is classified into exactly one of 4 RFs.
This table is the foundation for: accounting entries, invoices, payments,
purchase orders, work situations, treasury movements, capital calls, etc.

Specific financial modules extend this with their own tables that FK here,
but the RF classification and amount fields live on this base record.

Database-level enforcement (via CHECK constraints in migration):
- rf_type IN ('RF1','RF2','RF3','RF4') — mandatory, non-null
- RF1 → payment_mode IN ('CHEQUE','VIREMENT','CHEQUE_NOTAIRE')
- RF2 → payment_mode = 'ESPECES'
- RF3 → payment_mode IN ('SANS_OBJET','COMPENSATION')
- RF4 → payment_mode = 'SANS_OBJET'

RF2 amounts are encrypted at rest via pgcrypto.
"""

from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class FinancialTransaction(GFIBase, Base):
    __tablename__ = "financial_transaction"

    # ── RF classification (mandatory, non-null) ──────────────────────────
    rf_type = Column(String(3), nullable=False, index=True)

    # ── Transaction identity ─────────────────────────────────────────────
    transaction_date = Column(Date, nullable=False, index=True)
    reference = Column(String(100), nullable=True)
    label = Column(Text, nullable=False)

    # ── Category ─────────────────────────────────────────────────────────
    # VENTE, ACHAT, PAIEMENT, ENCAISSEMENT, ECRITURE_COMPTABLE,
    # FACTURE, BON_COMMANDE, SITUATION_TRAVAUX, MOUVEMENT_TRESORERIE,
    # APPEL_FONDS, TRANSFERT_PARTS, ECRITURE_PAIE, CLOTURE, CFF
    category = Column(String(40), nullable=False, index=True)

    # ── Amount ───────────────────────────────────────────────────────────
    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False, server_default="'DZD'")

    # ── Payment mode (constrained by RF type) ────────────────────────────
    # ESPECES, CHEQUE, VIREMENT, CHEQUE_NOTAIRE, COMPENSATION, SANS_OBJET
    payment_mode = Column(String(20), nullable=True)

    # ── Project link (optional — not all transactions are project-bound) ─
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # ── Associate link (for CCA, withdrawals, etc.) ──────────────────────
    associate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("associate.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # ── RF3 inter-group fields ───────────────────────────────────────────
    emitter_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company.id", ondelete="RESTRICT"),
        nullable=True,
    )
    receiver_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company.id", ondelete="RESTRICT"),
        nullable=True,
    )
    cff_triggered = Column(
        String(1), nullable=False, server_default="'N'"
    )  # Y/N — set to Y when CFF engine has been notified

    # ── RF2 encrypted amount (pgcrypto) ──────────────────────────────────
    # The `amount` field holds the value for RF1/RF3/RF4.
    # For RF2, the `amount` field ALSO holds the value (for internal queries),
    # but `rf2_amount_encrypted` stores the AES-256 encrypted copy at rest.
    rf2_amount_encrypted = Column(Text, nullable=True)

    # ── Document generation tracking ─────────────────────────────────────
    document_type = Column(String(60), nullable=True)
    document_ref = Column(String(100), nullable=True)
    client_visible = Column(
        String(1), nullable=False, server_default="'N'"
    )

    # ── Metadata ─────────────────────────────────────────────────────────
    metadata_json = Column(JSONB, nullable=True)

    # ── Relationships ────────────────────────────────────────────────────
    company = relationship(
        "Company", foreign_keys="[FinancialTransaction.company_id]"
    )
    project = relationship("Project")
    associate = relationship("Associate")
    emitter = relationship(
        "Company",
        foreign_keys="[FinancialTransaction.emitter_company_id]",
    )
    receiver = relationship(
        "Company",
        foreign_keys="[FinancialTransaction.receiver_company_id]",
    )

    def __repr__(self):
        return (
            f"<FinancialTransaction {self.rf_type} {self.amount} "
            f"{self.category} @ {self.transaction_date}>"
        )
