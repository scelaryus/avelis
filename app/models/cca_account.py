"""
GFI v7.0 — CcaAccount: Compte Courant d'Associe per associate per company.

Each founder has a CCA in each company where they hold shares:
- Ahmed: CCAs in all 12 entities
- Mohamed, Yazid: CCAs in all entities except EURL-BAY (TBD)
- Yamina: CCAs in ETS-DK and SARL-DP only (25% entities)

The running balance is maintained as a denormalized field updated
by triggers after each CcaMovement insert.

Uses GFIBase (company_id = the entity where the CCA lives).
"""

from sqlalchemy import Column, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class CcaAccount(GFIBase, Base):
    __tablename__ = "cca_account"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "associate_id",
            name="uq_cca_account_company_associate",
        ),
    )

    # ── Associate who owns this CCA ──────────────────────────────────────
    associate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("associate.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ── Running balance (denormalized, updated by trigger) ───────────────
    # Positive = company owes associate. Negative = associate owes company.
    balance = Column(Numeric(15, 2), nullable=False, server_default="0")

    # ── Status ───────────────────────────────────────────────────────────
    # ACTIVE, FROZEN (capital call unpaid), CLOSED
    status = Column(String(20), nullable=False, server_default="'ACTIVE'")
    freeze_reason = Column(String(255), nullable=True)

    # ── SCF account code (455 + sub-account) ─────────────────────────────
    scf_account_code = Column(String(20), nullable=False, server_default="'455'")

    # ── Relationships ────────────────────────────────────────────────────
    associate = relationship("Associate")
    company = relationship("Company")
    movements = relationship(
        "CcaMovement", back_populates="cca_account", lazy="select"
    )

    def __repr__(self):
        return (
            f"<CcaAccount associate={self.associate_id} "
            f"company={self.company_id} balance={self.balance}>"
        )
