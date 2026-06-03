"""
GFI v7.0 — GACEB subcontractor models: GacebAdvance, WorkSituation, Vehicle.

GACEB received 120M DA of physical equipment (not cash) from AMENFORT
as advance on EDEN work. Each work situation deducts from this advance.

Vehicle 5-step circuit tracks every vehicle from purchase to resale.
RAP formula computes the exact remaining amount owed to GACEB.
"""

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class GacebAdvance(GFIBase, Base):
    """Tracks the 120M in-kind advance and its deductions."""

    __tablename__ = "gaceb_advance"

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Advance details ──────────────────────────────────────────────────
    advance_type = Column(String(30), nullable=False)
    # MATERIEL_120M, VEHICLE, APARTMENT
    description = Column(Text, nullable=False)
    montant_initial = Column(Numeric(15, 2), nullable=False)
    montant_deduit = Column(Numeric(15, 2), nullable=False, server_default="0")
    solde_restant = Column(Numeric(15, 2), nullable=False)

    # ── Accounting reference ─────────────────────────────────────────────
    journal_entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("journal_entry.id", ondelete="SET NULL"),
        nullable=True,
    )
    # D 409100 / C 211800 for the 120M
    account_debit = Column(String(20), nullable=True)
    account_credit = Column(String(20), nullable=True)

    # ── Flags ────────────────────────────────────────────────────────────
    impact_tresorerie = Column(Boolean, nullable=False, server_default="false")
    # The 120M advance is NOT cash — no treasury impact

    project = relationship("Project")

    def __repr__(self):
        return (
            f"<GacebAdvance {self.advance_type} "
            f"initial={self.montant_initial} solde={self.solde_restant}>"
        )


class WorkSituation(GFIBase, Base):
    """GACEB work situation with gross/deduction/net tracking."""

    __tablename__ = "work_situation"

    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # ── Situation identity ───────────────────────────────────────────────
    situation_number = Column(Integer, nullable=False)
    situation_date = Column(Date, nullable=False, index=True)
    subcontractor_name = Column(String(255), nullable=False,
                                 server_default="'GACEB Abderazak'")

    # ── Amounts: ALWAYS show Brut | Deduction | Net | Solde ──────────────
    montant_brut = Column(Numeric(15, 2), nullable=False)
    deduction_avance = Column(Numeric(15, 2), nullable=False, server_default="0")
    deduction_vehicules = Column(Numeric(15, 2), nullable=False, server_default="0")
    deduction_appartements = Column(Numeric(15, 2), nullable=False, server_default="0")
    retention_garantie_5pct = Column(Numeric(15, 2), nullable=False, server_default="0")
    net_cash_verse = Column(Numeric(15, 2), nullable=False)
    solde_avance_apres = Column(Numeric(15, 2), nullable=True)

    # ── Contract context ─────────────────────────────────────────────────
    contract_ref = Column(String(100), nullable=True)
    completion_pct = Column(Numeric(5, 2), nullable=True)

    # ── Status ───────────────────────────────────────────────────────────
    # SOUMISE, VALIDEE, PAYEE
    status = Column(String(20), nullable=False, server_default="'SOUMISE'")
    validated_by = Column(UUID(as_uuid=True), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)

    # ── Document ─────────────────────────────────────────────────────────
    document_url = Column(Text, nullable=True)

    # ── Accounting link ──────────────────────────────────────────────────
    journal_entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("journal_entry.id", ondelete="SET NULL"),
        nullable=True,
    )

    project = relationship("Project")

    def __repr__(self):
        return (
            f"<WorkSituation #{self.situation_number} "
            f"brut={self.montant_brut} net={self.net_cash_verse}>"
        )


class Vehicle(GFIBase, Base):
    """5-step vehicle circuit: achat -> immatriculation -> cession -> deduction -> revente."""

    __tablename__ = "vehicle"

    # ── Identity ─────────────────────────────────────────────────────────
    chassis_number = Column(String(50), unique=True, nullable=False, index=True)
    make = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    plate_number = Column(String(20), nullable=True)

    # ── Step 1: Achat ────────────────────────────────────────────────────
    purchase_date = Column(Date, nullable=True)
    purchase_amount = Column(Numeric(15, 2), nullable=True)
    purchase_project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("project.id", ondelete="SET NULL"),
        nullable=True,
    )
    purchase_entry_id = Column(UUID(as_uuid=True), nullable=True)

    # ── Step 2: Immatriculation ──────────────────────────────────────────
    registered_to_associate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("associate.id", ondelete="SET NULL"),
        nullable=True,
    )
    registration_date = Column(Date, nullable=True)

    # ── Step 3: Cession a GACEB ──────────────────────────────────────────
    cession_date = Column(Date, nullable=True)
    cession_value = Column(Numeric(15, 2), nullable=True)
    cession_entry_id = Column(UUID(as_uuid=True), nullable=True)
    # D 409100 / C 218200

    # ── Step 4: Deduction sur situation ───────────────────────────────────
    deduction_date = Column(Date, nullable=True)
    deduction_situation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("work_situation.id", ondelete="SET NULL"),
        nullable=True,
    )
    deduction_amount = Column(Numeric(15, 2), nullable=True)

    # ── Step 5: Revente par GACEB (informational only) ───────────────────
    resale_date = Column(Date, nullable=True)
    resale_buyer = Column(String(255), nullable=True)
    resale_price = Column(Numeric(15, 2), nullable=True)

    # ── Current step ─────────────────────────────────────────────────────
    # ACHETE, IMMATRICULE, CEDE, DEDUIT, REVENDU
    current_step = Column(String(20), nullable=False, server_default="'ACHETE'")

    # ── Full history (JSON log of all steps) ─────────────────────────────
    history = Column(JSONB, nullable=True)

    registered_to = relationship("Associate")

    def __repr__(self):
        return f"<Vehicle {self.make} {self.model} [{self.chassis_number}] {self.current_step}>"
