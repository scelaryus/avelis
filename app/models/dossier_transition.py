"""
GFI v7.0 — DossierTransition: immutable log of state transitions.

Every state change on a dossier is recorded permanently.
This powers the Historique tab (tab 8) on the dossier screen.
"""

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class DossierTransition(GFIBase, Base):
    __tablename__ = "dossier_transition"

    dossier_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dossier_adv.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    from_status = Column(String(30), nullable=False)
    to_status = Column(String(30), nullable=False)
    transition_trigger = Column(String(60), nullable=True)
    transitioned_at = Column(DateTime(timezone=True), nullable=False)
    transitioned_by = Column(
        UUID(as_uuid=True),
        ForeignKey("auth_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    preconditions_met = Column(JSONB, nullable=True)
    notes = Column(Text, nullable=True)

    dossier = relationship("DossierAdv")

    def __repr__(self):
        return (
            f"<DossierTransition {self.from_status} -> {self.to_status} "
            f"@ {self.transitioned_at}>"
        )
