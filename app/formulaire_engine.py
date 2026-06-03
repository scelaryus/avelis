"""
GFI v7.0 — Formulaire Engine: the zero-hallucination enforcement layer.

Absolute rule: the system NEVER guesses. When information is missing,
it generates a targeted formulaire, assigns it to the DAF (or appropriate
role), and BLOCKS the dependent operation until answered.

Core API:
  generate_formulaire(code, context, ...) → Formulaire
  answer_formulaire(formulaire_id, response_data, ...) → Formulaire
  is_blocked(code, context_key) → bool
  require_not_blocked(code, context_key) → raises if blocked
  escalate_overdue() → list of escalated formulaire IDs
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import and_, func

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class OperationBlocked(Exception):
    """Raised when a financial operation is blocked by a pending formulaire."""

    def __init__(self, message: str, formulaire_id: UUID, code: str):
        super().__init__(message)
        self.formulaire_id = formulaire_id
        self.code = code


# ── Escalation levels ────────────────────────────────────────────────────────
ESCALATION_REMINDER = 1   # J+3: email reminder
ESCALATION_ALERT = 2      # J+7: notification + dashboard
ESCALATION_CRITIQUE = 3   # J+14: DAF alert
ESCALATION_BLOCKING = 4   # J+30: all dependent operations frozen


def generate_formulaire(
    session: Session,
    *,
    code: str,
    company_id: UUID,
    context: dict,
    blocked_resource_type: str | None = None,
    blocked_resource_id: UUID | None = None,
    assigned_to: UUID | None = None,
    created_by: UUID | None = None,
) -> object:
    """
    Generate a formulaire instance from a catalogue template.

    This is the ONLY correct response to missing data.
    The system NEVER invents values — it creates a formulaire instead.

    Args:
        code: Catalogue code (e.g., "FC-001", "F-REC-001")
        company_id: Which entity this formulaire belongs to
        context: Dict with template variables to render the question
        blocked_resource_type: Table name of the blocked resource
        blocked_resource_id: UUID of the blocked resource
        assigned_to: Specific user to assign (default: role-based)
        created_by: Who triggered the formulaire

    Returns:
        The created Formulaire instance.

    Raises:
        ValueError: If the catalogue code is unknown.
    """
    from app.models.formulaire_catalogue import FormulaireCatalogue
    from app.models.formulaire import Formulaire

    catalogue = (
        session.query(FormulaireCatalogue)
        .filter(
            FormulaireCatalogue.code == code,
            FormulaireCatalogue.is_deleted.is_(False),
        )
        .first()
    )
    if not catalogue:
        raise ValueError(f"Unknown formulaire code: '{code}'")

    # Render the question template with context values
    question_text = catalogue.question_template
    for key, value in context.items():
        question_text = question_text.replace(f"[{key}]", str(value))

    # Calculate first escalation date
    now = datetime.now(timezone.utc)
    next_esc = now + timedelta(days=catalogue.escalation_reminder_days)

    formulaire = Formulaire(
        company_id=company_id,
        catalogue_id=catalogue.id,
        code=code,
        priority=catalogue.priority,
        status="EN_ATTENTE",
        question_text=question_text,
        trigger_context=context,
        blocked_resource_type=blocked_resource_type,
        blocked_resource_id=blocked_resource_id,
        assigned_to=assigned_to,
        assigned_role=catalogue.default_assignee_role,
        escalation_level=0,
        next_escalation_at=next_esc,
        created_by=created_by,
    )
    session.add(formulaire)
    session.flush()

    return formulaire


def answer_formulaire(
    session: Session,
    *,
    formulaire_id: UUID,
    response_data: dict,
    responded_by: UUID,
) -> object:
    """
    Record the DAF's (or assignee's) answer to a formulaire.

    Sets status to REMPLI and unblocks the dependent operation.
    Logs the response in the audit trail.
    """
    from app.models.formulaire import Formulaire

    formulaire = session.get(Formulaire, formulaire_id)
    if formulaire is None:
        raise ValueError(f"Formulaire {formulaire_id} not found.")

    if formulaire.status != "EN_ATTENTE":
        raise ValueError(
            f"Formulaire {formulaire.code} is not EN_ATTENTE "
            f"(current: {formulaire.status})."
        )

    now = datetime.now(timezone.utc)
    formulaire.response_data = response_data
    formulaire.responded_by = responded_by
    formulaire.responded_at = now
    formulaire.status = "REMPLI"

    session.flush()
    return formulaire


def is_blocked(
    session: Session,
    code: str,
    company_id: UUID,
    *,
    blocked_resource_type: str | None = None,
    blocked_resource_id: UUID | None = None,
) -> bool:
    """
    Check if a pending formulaire blocks the given operation/resource.

    Returns True if at least one EN_ATTENTE formulaire exists matching
    the code and optional resource filter.
    """
    from app.models.formulaire import Formulaire

    q = session.query(Formulaire.id).filter(
        Formulaire.code == code,
        Formulaire.company_id == company_id,
        Formulaire.status == "EN_ATTENTE",
        Formulaire.is_deleted.is_(False),
    )
    if blocked_resource_type:
        q = q.filter(
            Formulaire.blocked_resource_type == blocked_resource_type
        )
    if blocked_resource_id:
        q = q.filter(
            Formulaire.blocked_resource_id == blocked_resource_id
        )
    return q.first() is not None


def get_blocking_formulaire(
    session: Session,
    code: str,
    company_id: UUID,
    *,
    blocked_resource_type: str | None = None,
    blocked_resource_id: UUID | None = None,
) -> object | None:
    """Return the blocking formulaire if one exists, else None."""
    from app.models.formulaire import Formulaire

    q = session.query(Formulaire).filter(
        Formulaire.code == code,
        Formulaire.company_id == company_id,
        Formulaire.status == "EN_ATTENTE",
        Formulaire.is_deleted.is_(False),
    )
    if blocked_resource_type:
        q = q.filter(
            Formulaire.blocked_resource_type == blocked_resource_type
        )
    if blocked_resource_id:
        q = q.filter(
            Formulaire.blocked_resource_id == blocked_resource_id
        )
    return q.first()


def require_not_blocked(
    session: Session,
    code: str,
    company_id: UUID,
    *,
    blocked_resource_type: str | None = None,
    blocked_resource_id: UUID | None = None,
) -> None:
    """
    Raise OperationBlocked if a pending formulaire exists for this code/resource.

    Call this BEFORE any financial operation that depends on data
    that might be missing.
    """
    from app.models.formulaire import Formulaire

    f = get_blocking_formulaire(
        session, code, company_id,
        blocked_resource_type=blocked_resource_type,
        blocked_resource_id=blocked_resource_id,
    )
    if f:
        raise OperationBlocked(
            f"Operation blocked by formulaire {f.code} (ID: {f.id}). "
            f"Status: {f.status}. Question: {f.question_text}",
            formulaire_id=f.id,
            code=f.code,
        )


def generate_if_not_exists(
    session: Session,
    *,
    code: str,
    company_id: UUID,
    context: dict,
    blocked_resource_type: str | None = None,
    blocked_resource_id: UUID | None = None,
    created_by: UUID | None = None,
) -> object:
    """
    Generate a formulaire ONLY if one doesn't already exist for this
    code + resource combination. Idempotent — safe to call multiple times.

    Returns the existing or newly created formulaire.
    """
    existing = get_blocking_formulaire(
        session, code, company_id,
        blocked_resource_type=blocked_resource_type,
        blocked_resource_id=blocked_resource_id,
    )
    if existing:
        return existing

    return generate_formulaire(
        session,
        code=code,
        company_id=company_id,
        context=context,
        blocked_resource_type=blocked_resource_type,
        blocked_resource_id=blocked_resource_id,
        created_by=created_by,
    )


def escalate_overdue(session: Session) -> list[UUID]:
    """
    Process all overdue formulaires and advance their escalation level.

    Escalation schedule:
      Level 0 → 1 at J+3:  email reminder
      Level 1 → 2 at J+7:  notification + dashboard alert
      Level 2 → 3 at J+14: DAF alert (CRITIQUE level)
      Level 3 → 4 at J+30: BLOQUANT — all dependent operations frozen

    Returns list of formulaire IDs that were escalated.
    """
    from app.models.formulaire import Formulaire
    from app.models.formulaire_catalogue import FormulaireCatalogue

    now = datetime.now(timezone.utc)

    overdue = (
        session.query(Formulaire)
        .filter(
            Formulaire.status == "EN_ATTENTE",
            Formulaire.is_deleted.is_(False),
            Formulaire.next_escalation_at <= now,
        )
        .all()
    )

    escalated_ids = []

    for f in overdue:
        cat = session.get(FormulaireCatalogue, f.catalogue_id)
        if not cat:
            continue

        f.escalation_level += 1
        f.last_relance_at = now

        # Calculate next escalation date based on new level
        if f.escalation_level == ESCALATION_REMINDER:
            days = cat.escalation_alert_days - cat.escalation_reminder_days
        elif f.escalation_level == ESCALATION_ALERT:
            days = cat.escalation_critique_days - cat.escalation_alert_days
        elif f.escalation_level == ESCALATION_CRITIQUE:
            days = cat.escalation_blocking_days - cat.escalation_critique_days
        else:
            # Level 4+: no more escalation, stays BLOQUANT
            f.next_escalation_at = None
            days = None

        if days is not None:
            f.next_escalation_at = now + timedelta(days=days)

        escalated_ids.append(f.id)

    if escalated_ids:
        session.flush()

    return escalated_ids


def expire_formulaire(
    session: Session,
    formulaire_id: UUID,
) -> None:
    """Mark a formulaire as EXPIRE (superseded or no longer relevant)."""
    from app.models.formulaire import Formulaire

    f = session.get(Formulaire, formulaire_id)
    if f and f.status == "EN_ATTENTE":
        f.status = "EXPIRE"
        session.flush()


def get_pending_for_user(
    session: Session,
    user_id: UUID,
    company_id: UUID | None = None,
) -> list:
    """Return all pending formulaires assigned to a specific user."""
    from app.models.formulaire import Formulaire

    q = session.query(Formulaire).filter(
        Formulaire.assigned_to == user_id,
        Formulaire.status == "EN_ATTENTE",
        Formulaire.is_deleted.is_(False),
    )
    if company_id:
        q = q.filter(Formulaire.company_id == company_id)
    return q.order_by(
        Formulaire.priority.desc(),
        Formulaire.created_at.asc(),
    ).all()


def get_pending_for_role(
    session: Session,
    role_code: str,
    company_id: UUID | None = None,
) -> list:
    """Return all pending formulaires assigned to a role (unassigned to specific user)."""
    from app.models.formulaire import Formulaire

    q = session.query(Formulaire).filter(
        Formulaire.assigned_role == role_code,
        Formulaire.status == "EN_ATTENTE",
        Formulaire.is_deleted.is_(False),
    )
    if company_id:
        q = q.filter(Formulaire.company_id == company_id)
    return q.order_by(
        Formulaire.priority.desc(),
        Formulaire.created_at.asc(),
    ).all()
