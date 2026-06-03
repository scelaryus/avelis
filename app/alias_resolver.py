"""
GFI v7.0 — Alias Resolution Engine.

Every financial operation MUST resolve names to canonical entities BEFORE
any calculation.  The system NEVER guesses — if confidence is too low,
it BLOCKS and generates a formulaire for DAF review.

Resolution pipeline:
  1. Normalize input (lowercase, strip accents, trim whitespace)
  2. Exact match on alias_normalized
  3. Fuzzy match via pg_trgm similarity (threshold >= 0.6)
  4. If best score < 0.5 → BLOCK + generate FC-001/FC-003

Kill Test KT-05: "LIAZID" → blocked, proposes "Lyazid" correction.
Test TD-09: "LES LYS" and "02 HECTARE" → both resolve to project LYS.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, text

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class EntityType(Enum):
    PROJECT = "PROJECT"
    ASSOCIATE = "ASSOCIATE"
    COMPANY = "COMPANY"


class ResolutionStatus(Enum):
    EXACT = "EXACT"
    FUZZY = "FUZZY"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ResolvedEntity:
    """Result of alias resolution."""

    status: ResolutionStatus
    entity_type: EntityType
    target_id: UUID | None
    canonical_name: str | None
    input_text: str
    normalized_text: str
    confidence: float  # 1.0 for exact, 0.0-1.0 for fuzzy
    # Populated when BLOCKED — nearest candidates for DAF review
    suggestions: list[ResolutionSuggestion]
    # Which formulaire to generate when BLOCKED
    formulaire_code: str | None


@dataclass(frozen=True)
class ResolutionSuggestion:
    """A candidate proposed to the DAF when resolution is blocked."""

    canonical_name: str
    target_id: UUID
    similarity: float
    alias_matched: str


def normalize(text: str) -> str:
    """
    Normalize input for matching: lowercase, strip accents, collapse whitespace.

    Examples:
        "Chéraga"    → "cheraga"
        "05 HECTARE" → "05 hectare"
        "LES  LYS"  → "les lys"
        "Béton"      → "beton"
    """
    # NFD decomposition splits accented chars into base + combining mark
    nfkd = unicodedata.normalize("NFKD", text)
    # Strip combining marks (accents)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Lowercase, collapse whitespace, strip
    return " ".join(stripped.lower().split())


# ── Formulaire codes by entity type ──────────────────────────────────────────
_FORMULAIRE_MAP = {
    EntityType.ASSOCIATE: "FC-001",
    EntityType.PROJECT: "FC-003",
    EntityType.COMPANY: "FC-003",
}

# Thresholds
EXACT_THRESHOLD = 1.0
FUZZY_ACCEPT_THRESHOLD = 0.6  # Accept fuzzy match if similarity >= 0.6
BLOCK_THRESHOLD = 0.5         # Block if best candidate < 0.5
FUZZY_SEARCH_LIMIT = 5        # Max suggestions returned when blocked


def resolve(
    session: Session,
    input_text: str,
    entity_type: EntityType,
) -> ResolvedEntity:
    """
    Resolve an alias to its canonical entity.

    Pipeline:
      1. Exact match (case-insensitive, accent-stripped)
      2. Fuzzy match using pg_trgm similarity()
      3. Block if confidence < threshold

    Returns a ResolvedEntity with status EXACT, FUZZY, or BLOCKED.
    """
    from app.models.entity_alias import EntityAlias

    norm = normalize(input_text)
    if not norm:
        return ResolvedEntity(
            status=ResolutionStatus.BLOCKED,
            entity_type=entity_type,
            target_id=None,
            canonical_name=None,
            input_text=input_text,
            normalized_text=norm,
            confidence=0.0,
            suggestions=[],
            formulaire_code=_FORMULAIRE_MAP[entity_type],
        )

    # ── Step 1: Exact match ──────────────────────────────────────────────
    exact = (
        session.query(EntityAlias)
        .filter(
            EntityAlias.entity_type == entity_type.value,
            EntityAlias.alias_normalized == norm,
            EntityAlias.is_deleted.is_(False),
        )
        .first()
    )
    if exact:
        return ResolvedEntity(
            status=ResolutionStatus.EXACT,
            entity_type=entity_type,
            target_id=exact.target_id,
            canonical_name=exact.canonical_name,
            input_text=input_text,
            normalized_text=norm,
            confidence=EXACT_THRESHOLD,
            suggestions=[],
            formulaire_code=None,
        )

    # ── Step 2: Fuzzy match via pg_trgm ──────────────────────────────────
    # similarity() returns 0.0 to 1.0
    similarity_col = func.similarity(EntityAlias.alias_normalized, norm)

    candidates = (
        session.query(
            EntityAlias.target_id,
            EntityAlias.canonical_name,
            EntityAlias.alias_normalized,
            similarity_col.label("sim"),
        )
        .filter(
            EntityAlias.entity_type == entity_type.value,
            EntityAlias.is_deleted.is_(False),
            similarity_col >= 0.3,  # pre-filter: only consider vaguely close
        )
        .order_by(similarity_col.desc())
        .limit(FUZZY_SEARCH_LIMIT)
        .all()
    )

    if not candidates:
        return ResolvedEntity(
            status=ResolutionStatus.BLOCKED,
            entity_type=entity_type,
            target_id=None,
            canonical_name=None,
            input_text=input_text,
            normalized_text=norm,
            confidence=0.0,
            suggestions=[],
            formulaire_code=_FORMULAIRE_MAP[entity_type],
        )

    best = candidates[0]

    # ── Step 2a: Accept if above fuzzy threshold ─────────────────────────
    if best.sim >= FUZZY_ACCEPT_THRESHOLD:
        return ResolvedEntity(
            status=ResolutionStatus.FUZZY,
            entity_type=entity_type,
            target_id=best.target_id,
            canonical_name=best.canonical_name,
            input_text=input_text,
            normalized_text=norm,
            confidence=float(best.sim),
            suggestions=[],
            formulaire_code=None,
        )

    # ── Step 3: Block — confidence too low ───────────────────────────────
    # Build suggestions for DAF review (deduplicate by target_id)
    seen = set()
    suggestions = []
    for cand in candidates:
        if cand.target_id not in seen:
            seen.add(cand.target_id)
            suggestions.append(
                ResolutionSuggestion(
                    canonical_name=cand.canonical_name,
                    target_id=cand.target_id,
                    similarity=float(cand.sim),
                    alias_matched=cand.alias_normalized,
                )
            )

    return ResolvedEntity(
        status=ResolutionStatus.BLOCKED,
        entity_type=entity_type,
        target_id=None,
        canonical_name=None,
        input_text=input_text,
        normalized_text=norm,
        confidence=float(best.sim),
        suggestions=suggestions,
        formulaire_code=_FORMULAIRE_MAP[entity_type],
    )


def resolve_or_raise(
    session: Session,
    input_text: str,
    entity_type: EntityType,
) -> ResolvedEntity:
    """
    Resolve an alias — raise AliasResolutionBlocked if blocked.

    Use this in financial pipelines where resolution MUST succeed
    before any calculation proceeds.
    """
    result = resolve(session, input_text, entity_type)
    if result.status == ResolutionStatus.BLOCKED:
        suggestion_text = ""
        if result.suggestions:
            top = result.suggestions[0]
            suggestion_text = (
                f" Nearest match: '{top.canonical_name}' "
                f"(similarity: {top.similarity:.0%})"
            )
        raise AliasResolutionBlocked(
            f"Cannot resolve '{input_text}' as {entity_type.value}. "
            f"Confidence too low ({result.confidence:.0%}).{suggestion_text} "
            f"Generate {result.formulaire_code} for DAF review.",
            result=result,
        )
    return result


class AliasResolutionBlocked(Exception):
    """Raised when alias resolution confidence is below threshold."""

    def __init__(self, message: str, result: ResolvedEntity):
        super().__init__(message)
        self.result = result


def add_alias(
    session: Session,
    *,
    entity_type: EntityType,
    target_id: UUID,
    alias_raw: str,
    canonical_name: str,
    company_id: UUID,
    created_by: UUID | None = None,
) -> None:
    """
    Register a new alias at runtime (no restart needed).
    Logged in audit trail via the caller.

    Raises ValueError if the normalized alias already exists for this type.
    """
    from app.models.entity_alias import EntityAlias

    norm = normalize(alias_raw)
    if not norm:
        raise ValueError("Alias cannot be empty after normalization.")

    existing = (
        session.query(EntityAlias.id)
        .filter(
            EntityAlias.entity_type == entity_type.value,
            EntityAlias.alias_normalized == norm,
            EntityAlias.is_deleted.is_(False),
        )
        .first()
    )
    if existing:
        raise ValueError(
            f"Alias '{alias_raw}' (normalized: '{norm}') already exists "
            f"for entity type {entity_type.value}."
        )

    alias = EntityAlias(
        company_id=company_id,
        entity_type=entity_type.value,
        target_id=target_id,
        alias_raw=alias_raw,
        alias_normalized=norm,
        canonical_name=canonical_name,
        created_by=created_by,
    )
    session.add(alias)
    session.flush()


def resolve_project(session: Session, input_text: str) -> ResolvedEntity:
    """Convenience: resolve a project name."""
    return resolve(session, input_text, EntityType.PROJECT)


def resolve_associate(session: Session, input_text: str) -> ResolvedEntity:
    """Convenience: resolve an associate name."""
    return resolve(session, input_text, EntityType.ASSOCIATE)


def resolve_company(session: Session, input_text: str) -> ResolvedEntity:
    """Convenience: resolve a company name."""
    return resolve(session, input_text, EntityType.COMPANY)
