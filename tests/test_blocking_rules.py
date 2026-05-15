"""GAP 3 — Integration tests for blocking validation rules."""
import uuid
from decimal import Decimal

import pytest

from app.models.core import Tenant
from app.models.financial import Entreprise, Associe, Projet, StatutProjet
from app.models.registry import PartProjet
from app.models.finance_associes import (
    CompteCourantAssocie,
    AssociateAlias,
)


# ── Helpers ────────────────────────────────────────────────────────────────

async def _setup_tenant_and_company(db, tenant_id):
    """Seed a minimal tenant + entreprise + associe."""
    tenant = Tenant(
        id=tenant_id,
        name="TEST",
        code="TST",
        description="Test tenant",
        settings={},
    )
    db.add(tenant)
    await db.flush()

    ent = Entreprise(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        raison_sociale="TEST CORP",
        devise="DZD",
    )
    db.add(ent)
    await db.flush()
    return ent


async def _create_associe(db, tenant_id, ent_id, nom, part_pct=50):
    assoc = Associe(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        entreprise_id=ent_id,
        nom=nom,
        part_pct=part_pct,
    )
    db.add(assoc)
    await db.flush()
    return assoc


async def _create_project(db, tenant_id, ent_id, nom="PROJ1"):
    proj = Projet(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        entreprise_id=ent_id,
        code=nom,
        nom=nom,
        statut=StatutProjet.ACTIF,
    )
    db.add(proj)
    await db.flush()
    return proj


# ── Blocking: Retrait Associé ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrait_no_account(db, tenant_id):
    """Retrait on an associé with no CompteCourantAssocie → BlockingError."""
    from app.services.blocking_rules import validate_retrait_associe, BlockingError

    ent = await _setup_tenant_and_company(db, tenant_id)
    assoc = await _create_associe(db, tenant_id, ent.id, "JOHN DOE")
    # No CCA created

    with pytest.raises(BlockingError, match="introuvable"):
        await validate_retrait_associe(assoc.id, Decimal("1000"), db)


@pytest.mark.asyncio
async def test_retrait_frozen_account(db, tenant_id):
    """Retrait on a frozen account → BlockingError."""
    from app.services.blocking_rules import validate_retrait_associe, BlockingError

    ent = await _setup_tenant_and_company(db, tenant_id)
    assoc = await _create_associe(db, tenant_id, ent.id, "JOHN DOE")

    cca = CompteCourantAssocie(
        id=str(uuid.uuid4()),
        associe_id=assoc.id,
        solde_global=Decimal("50000"),
        solde_disponible_retrait=Decimal("25000"),
        est_gele=True,
    )
    db.add(cca)
    await db.flush()

    with pytest.raises(BlockingError, match="gelé"):
        await validate_retrait_associe(assoc.id, Decimal("1000"), db)


@pytest.mark.asyncio
async def test_retrait_insufficient_balance(db, tenant_id):
    """Retrait exceeding available balance → BlockingError."""
    from app.services.blocking_rules import validate_retrait_associe, BlockingError

    ent = await _setup_tenant_and_company(db, tenant_id)
    assoc = await _create_associe(db, tenant_id, ent.id, "JOHN DOE")

    cca = CompteCourantAssocie(
        id=str(uuid.uuid4()),
        associe_id=assoc.id,
        solde_global=Decimal("50000"),
        solde_disponible_retrait=Decimal("5000"),
        est_gele=False,
    )
    db.add(cca)
    await db.flush()

    with pytest.raises(BlockingError, match="solde disponible"):
        await validate_retrait_associe(assoc.id, Decimal("10000"), db)


@pytest.mark.asyncio
async def test_retrait_valid(db, tenant_id):
    """Retrait within balance → should not raise."""
    from app.services.blocking_rules import validate_retrait_associe

    ent = await _setup_tenant_and_company(db, tenant_id)
    assoc = await _create_associe(db, tenant_id, ent.id, "JOHN DOE")

    cca = CompteCourantAssocie(
        id=str(uuid.uuid4()),
        associe_id=assoc.id,
        solde_global=Decimal("50000"),
        solde_disponible_retrait=Decimal("25000"),
        est_gele=False,
    )
    db.add(cca)
    await db.flush()

    # Should not raise
    await validate_retrait_associe(assoc.id, Decimal("20000"), db)


# ── Blocking: Project Shares Sum ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_shares_sum_exceeds_100(db, tenant_id):
    """Adding shares that would exceed 100% → BlockingError."""
    from app.services.blocking_rules import validate_project_shares_sum, BlockingError

    ent = await _setup_tenant_and_company(db, tenant_id)
    assoc1 = await _create_associe(db, tenant_id, ent.id, "JOHN DOE", 60)
    assoc2 = await _create_associe(db, tenant_id, ent.id, "JANE DOE", 40)
    proj = await _create_project(db, tenant_id, ent.id)

    # Add 60% for assoc1
    pp1 = PartProjet(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        projet_id=proj.id,
        associe_id=assoc1.id,
        pourcentage=Decimal("60"),
    )
    db.add(pp1)
    await db.flush()

    # Try adding 50% for assoc2 → total 110 → should block
    with pytest.raises(BlockingError, match="100%"):
        await validate_project_shares_sum(proj.id, db, new_pourcentage=Decimal("50"))


@pytest.mark.asyncio
async def test_shares_sum_valid(db, tenant_id):
    """Adding shares within 100% → should not raise."""
    from app.services.blocking_rules import validate_project_shares_sum

    ent = await _setup_tenant_and_company(db, tenant_id)
    assoc1 = await _create_associe(db, tenant_id, ent.id, "JOHN DOE", 60)
    proj = await _create_project(db, tenant_id, ent.id)

    pp1 = PartProjet(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        projet_id=proj.id,
        associe_id=assoc1.id,
        pourcentage=Decimal("60"),
    )
    db.add(pp1)
    await db.flush()

    # Adding 40% → total 100 → ok
    await validate_project_shares_sum(proj.id, db, new_pourcentage=Decimal("40"))


# ── Blocking: Associate Exact Match ──────────────────────────────────────

@pytest.mark.asyncio
async def test_associate_exact_match_found(db, tenant_id):
    """Exact match on associe name → returns associe."""
    from app.services.blocking_rules import validate_associate_exact_match

    ent = await _setup_tenant_and_company(db, tenant_id)
    assoc = await _create_associe(db, tenant_id, ent.id, "AHMED DENDANI")

    result = await validate_associate_exact_match("AHMED DENDANI", db)
    assert result is not None
    assert result.id == assoc.id


@pytest.mark.asyncio
async def test_associate_exact_match_via_alias(db, tenant_id):
    """Exact match on alias → returns associe."""
    from app.services.blocking_rules import validate_associate_exact_match

    ent = await _setup_tenant_and_company(db, tenant_id)
    assoc = await _create_associe(db, tenant_id, ent.id, "AHMED DENDANI")

    alias = AssociateAlias(
        id=str(uuid.uuid4()),
        associe_id=assoc.id,
        alias="A. DENDANI",
    )
    db.add(alias)
    await db.flush()

    result = await validate_associate_exact_match("A. DENDANI", db)
    assert result is not None
    assert result.id == assoc.id


@pytest.mark.asyncio
async def test_associate_no_match_raises_blocking(db, tenant_id):
    """No exact match → raises BlockingError (never auto-validate)."""
    from app.services.blocking_rules import validate_associate_exact_match, BlockingError

    ent = await _setup_tenant_and_company(db, tenant_id)
    await _create_associe(db, tenant_id, ent.id, "AHMED DENDANI")

    with pytest.raises(BlockingError, match="Aucun associé"):
        await validate_associate_exact_match("ZZZZZ UNKNOWN", db)
