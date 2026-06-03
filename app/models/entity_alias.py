"""
GFI v7.0 — EntityAlias: canonical alias resolution table.

Over 20+ years, projects/people/companies appear under dozens of names.
This table maps EVERY known alias to its canonical entity, enabling:
  1. Exact match (case-insensitive, accent-insensitive)
  2. Fuzzy match via pg_trgm (threshold >= 0.6)
  3. BLOCK + formulaire if confidence < 50% (zero-hallucination rule)

entity_type: PROJECT, ASSOCIATE, COMPANY
target_id:   UUID of the canonical project/associate/company record
alias:       the variant name (stored lowercase, accent-stripped for matching)
alias_raw:   the original alias as provided (preserves accents/case)

New aliases can be added at runtime via API without restart.
"""

from sqlalchemy import Column, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, GFIBase


class EntityAlias(GFIBase, Base):
    __tablename__ = "entity_alias"
    __table_args__ = (
        UniqueConstraint(
            "entity_type", "alias_normalized",
            name="uq_entity_alias_type_normalized",
        ),
    )

    # ── What type of entity this alias resolves to ───────────────────────
    # PROJECT, ASSOCIATE, COMPANY
    entity_type = Column(String(20), nullable=False, index=True)

    # ── Target: which canonical record this alias points to ──────────────
    # Polymorphic FK — points to project.id, associate.id, or company.id
    # depending on entity_type. No DB-level FK (polymorphic).
    target_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # ── The alias text ───────────────────────────────────────────────────
    alias_raw = Column(Text, nullable=False)
    # Normalized form: lowercase, accent-stripped, trimmed.
    # Used for exact matching and trigram indexing.
    alias_normalized = Column(Text, nullable=False, index=True)

    # ── Canonical name (denormalized for fast display) ───────────────────
    canonical_name = Column(String(255), nullable=False)

    def __repr__(self):
        return (
            f"<EntityAlias '{self.alias_raw}' -> "
            f"{self.entity_type}:{self.canonical_name}>"
        )
