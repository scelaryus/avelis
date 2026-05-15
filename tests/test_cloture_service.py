"""GAP 5 — Integration tests for clôture mensuelle service."""
import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.core import Tenant
from app.models.financial import (
    Entreprise,
    Associe,
    Projet,
    Exercice,
    CentreCoutMensuel,
    StatutProjet,
)
from app.models.registry import PartProjet
from app.models.finance_associes import CompteCourantAssocie


async def _setup_cloture_data(db, tenant_id):
    """Create tenant + company + 2 associés + project + parts + CCA + exercice + CCM."""
    tenant = Tenant(
        id=tenant_id, name="TEST", code="TST", description="Test", settings={}
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

    assoc1 = Associe(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        entreprise_id=ent.id,
        nom="ASSOC A",
        part_pct=60,
    )
    assoc2 = Associe(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        entreprise_id=ent.id,
        nom="ASSOC B",
        part_pct=40,
    )
    db.add_all([assoc1, assoc2])
    await db.flush()

    proj = Projet(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        entreprise_id=ent.id,
        code="PROJ1",
        nom="Project 1",
        statut=StatutProjet.ACTIF,
    )
    db.add(proj)
    await db.flush()

    # Parts projets: 60/40
    pp1 = PartProjet(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        projet_id=proj.id,
        associe_id=assoc1.id,
        pourcentage=Decimal("60"),
    )
    pp2 = PartProjet(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        projet_id=proj.id,
        associe_id=assoc2.id,
        pourcentage=Decimal("40"),
    )
    db.add_all([pp1, pp2])
    await db.flush()

    # Comptes courants (no tenant_id on this model)
    cca1 = CompteCourantAssocie(
        id=str(uuid.uuid4()),
        associe_id=assoc1.id,
        solde_global=Decimal("0"),
        solde_disponible_retrait=Decimal("0"),
    )
    cca2 = CompteCourantAssocie(
        id=str(uuid.uuid4()),
        associe_id=assoc2.id,
        solde_global=Decimal("0"),
        solde_disponible_retrait=Decimal("0"),
    )
    db.add_all([cca1, cca2])
    await db.flush()

    # Exercice
    exercice = Exercice(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        entreprise_id=ent.id,
        annee=2025,
        date_debut=date(2025, 1, 1),
        date_fin=date(2025, 12, 31),
    )
    db.add(exercice)
    await db.flush()

    # CentreCoutMensuel for January 2025
    # resultat_ultra_reel = TNM = total_recettes - total_depenses = 180k - 80k = 100k
    # Also need all the sub-fields for double-computation to pass
    ccm = CentreCoutMensuel(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        projet_id=proj.id,
        entreprise_id=ent.id,
        exercice_id=exercice.id,
        mois=1,
        annee=2025,
        # Recettes
        encaissements_rd=Decimal("100000"),
        encaissements_rnd=Decimal("0"),
        gains_contentieux=Decimal("0"),
        liberations_transit=Decimal("0"),
        total_recettes=Decimal("100000"),
        # Dépenses directes
        decaissements_rd=Decimal("0"),
        decaissements_rnd=Decimal("0"),
        cout_fictif_fd=Decimal("0"),
        pertes_contentieux=Decimal("0"),
        stock_consomme_cump=Decimal("0"),
        masse_salariale_directe=Decimal("0"),
        total_depenses_directes=Decimal("0"),
        # Charges communes
        charges_communes_montant=Decimal("0"),
        # Totaux
        total_depenses=Decimal("0"),
        resultat_ultra_reel=Decimal("100000"),  # TNM = 100k
    )
    db.add(ccm)
    await db.flush()

    return {
        "ent": ent,
        "assoc1": assoc1,
        "assoc2": assoc2,
        "proj": proj,
        "cca1": cca1,
        "cca2": cca2,
        "exercice": exercice,
        "ccm": ccm,
    }


@pytest.mark.asyncio
async def test_cloture_basic(db, tenant_id):
    """Clôture for a project with 2 associés at 60/40 and TNM = 100k."""
    from app.services.cloture_service import executer_cloture_mensuelle

    data = await _setup_cloture_data(db, tenant_id)

    cloture = await executer_cloture_mensuelle(
        projet_id=data["proj"].id,
        mois=1,
        annee=2025,
        created_by="test_user",
        db=db,
        est_test_fictif=False,
    )

    assert cloture is not None
    assert cloture.statut.value == "SUCCES"
    assert cloture.tresorerie_nette_mois == Decimal("100000")
    # montant_a_liberer = TNM * 50% = 50,000
    assert cloture.montant_a_liberer == Decimal("50000")
    assert cloture.hash_verification is not None
    assert len(cloture.hash_verification) == 64


@pytest.mark.asyncio
async def test_cloture_updates_cca_balances(db, tenant_id):
    """After clôture, CCA balances should be updated with pro-rata amounts."""
    from app.services.cloture_service import executer_cloture_mensuelle
    from sqlalchemy import select

    data = await _setup_cloture_data(db, tenant_id)

    await executer_cloture_mensuelle(
        projet_id=data["proj"].id,
        mois=1,
        annee=2025,
        created_by="test_user",
        db=db,
    )

    # Refresh CCAs
    result1 = await db.execute(
        select(CompteCourantAssocie).where(
            CompteCourantAssocie.id == data["cca1"].id
        )
    )
    cca1 = result1.scalar_one()

    result2 = await db.execute(
        select(CompteCourantAssocie).where(
            CompteCourantAssocie.id == data["cca2"].id
        )
    )
    cca2 = result2.scalar_one()

    # Pro-rata: 50k × 60% = 30k for assoc1, 50k × 40% = 20k for assoc2
    assert cca1.solde_global == Decimal("30000")
    assert cca2.solde_global == Decimal("20000")


@pytest.mark.asyncio
async def test_cloture_duplicate_blocked(db, tenant_id):
    """Running clôture twice for same month → should raise (unique constraint)."""
    from app.services.cloture_service import executer_cloture_mensuelle

    data = await _setup_cloture_data(db, tenant_id)

    await executer_cloture_mensuelle(
        projet_id=data["proj"].id,
        mois=1,
        annee=2025,
        created_by="test_user",
        db=db,
    )

    with pytest.raises(Exception):
        await executer_cloture_mensuelle(
            projet_id=data["proj"].id,
            mois=1,
            annee=2025,
            created_by="test_user",
            db=db,
        )
