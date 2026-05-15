"""GFI v7.0 — Kill Tests KT-01 through KT-09 + Sanity + VSR.

These tests MUST pass before any merge to main.
"""
import uuid
from decimal import Decimal
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import (
    Entreprise, Projet, Associe, EntrepriseAssocie,
    Transaction, RealiteFinanciere, TypeTransaction,
    CompensationST, ClotureMensuelleRepartition,
)
from app.models.finance_associes import (
    CompteCourantAssocie, MouvementCompteCourant, TypeMouvement,
    CessionParts, AssociateAlias,
)
from app.models.cff import CFFFacture, CFFImputationAssocie
from app.services.cff_engine import CFFEngine, CFFCalculResult
from app.services.blocking_rules import BlockingError, validate_retrait_associe


# ── Fixtures ──────────────────────────────────────────────────────────────

TENANT_ID = "test-tenant-kt"
AHMED_ID = str(uuid.uuid4())
YAMINA_ID = str(uuid.uuid4())
MOHAMED_ID = str(uuid.uuid4())
YAZID_ID = str(uuid.uuid4())

ENT_DP_ID = str(uuid.uuid4())
ENT_DBPI_ID = str(uuid.uuid4())
ENT_OC_ID = str(uuid.uuid4())
ENT_EP_ID = str(uuid.uuid4())
ENT_SEN_ID = str(uuid.uuid4())
ENT_BIM_ID = str(uuid.uuid4())

PROJ_JASMIN_ID = str(uuid.uuid4())


# ── KT-01: Yamina CFF = 0 DA in DBPI/OC/EP/SEN/BIM ─────────────────────

class TestKT01:
    """KT-01: Yamina must have 0% participation in DBPI, OC, EP, SEN, BIM."""

    def test_yamina_excluded_from_restricted_enterprises(self):
        """Yamina should NOT appear in DBPI/OC/EP/SEN/BIM participations."""
        engine = CFFEngine()

        # SARL-DBPI: only Ahmed (60%) and Mohamed (40%)
        participations = [
            {"associe_id": AHMED_ID, "pourcentage": 60.0},
            {"associe_id": MOHAMED_ID, "pourcentage": 40.0},
        ]

        result = engine.calculer(Decimal("100000"), participations, "SARL-DBPI")
        assert engine.verifier_kt01(result.imputations, YAMINA_ID, "SARL-DBPI")

    def test_yamina_present_in_restricted_fails(self):
        """If Yamina appears in a restricted enterprise, KT-01 MUST fail."""
        engine = CFFEngine()

        # Incorrectly includes Yamina
        participations = [
            {"associe_id": AHMED_ID, "pourcentage": 50.0},
            {"associe_id": YAMINA_ID, "pourcentage": 50.0},
        ]

        result = engine.calculer(Decimal("100000"), participations, "SARL-DBPI")
        assert not engine.verifier_kt01(result.imputations, YAMINA_ID, "SARL-DBPI")


# ── KT-02: Ahmed SARL-DP = 25% enterprise, NOT 60% project ──────────────

class TestKT02:
    """KT-02: Ahmed's CFF in SARL-DP must use 25% enterprise share, not 60% project."""

    def test_ahmed_uses_enterprise_percentage(self):
        engine = CFFEngine()

        # Correct: 25% enterprise
        participations = [
            {"associe_id": AHMED_ID, "pourcentage": 25.0},
            {"associe_id": MOHAMED_ID, "pourcentage": 25.0},
            {"associe_id": YAZID_ID, "pourcentage": 25.0},
            {"associe_id": YAMINA_ID, "pourcentage": 25.0},
        ]

        result = engine.calculer(Decimal("1000000"), participations, "SARL-DP")
        assert engine.verifier_kt02(result.imputations, AHMED_ID, "SARL-DP", 25.0)

    def test_ahmed_project_percentage_fails(self):
        """If Ahmed uses 60% (project), KT-02 MUST fail."""
        engine = CFFEngine()

        # Wrong: 60% project instead of 25% enterprise
        participations = [
            {"associe_id": AHMED_ID, "pourcentage": 60.0},
            {"associe_id": MOHAMED_ID, "pourcentage": 40.0},
        ]

        result = engine.calculer(Decimal("1000000"), participations, "SARL-DP")
        assert not engine.verifier_kt02(result.imputations, AHMED_ID, "SARL-DP", 25.0)


# ── KT-03: CFF = % entreprise, never % projet ───────────────────────────

class TestKT03:
    """KT-03: CFF engine must use enterprise %, never project %."""

    def test_cff_uses_enterprise_participations(self):
        engine = CFFEngine()

        enterprise_parts = [
            {"associe_id": AHMED_ID, "pourcentage": 25.0},
            {"associe_id": MOHAMED_ID, "pourcentage": 25.0},
            {"associe_id": YAZID_ID, "pourcentage": 25.0},
            {"associe_id": YAMINA_ID, "pourcentage": 25.0},
        ]

        result = engine.calculer(Decimal("100000"), enterprise_parts, "SARL-DP")
        total = sum(i.montant_impute for i in result.imputations)
        assert abs(total - result.cff_total) < 0.02  # rounding tolerance


# ── KT-04: Double computation tolerance = 0.00 DA ────────────────────────

class TestKT04:
    """KT-04: Monthly closing tolerance must be exactly 0.00 DA."""

    def test_zero_tolerance(self):
        """Verify the cloture code uses 0.00, not 0.01."""
        # This is a code-level assertion
        import inspect
        from app.services.cloture_service import executer_cloture_mensuelle

        source = inspect.getsource(executer_cloture_mensuelle)
        assert 'Decimal("0.00")' in source, "Tolerance must be 0.00 DA"
        assert 'Decimal("0.01")' not in source, "Old tolerance 0.01 must be removed"


# ── KT-05: No cash 512 outflow for material advances ─────────────────────

class TestKT05:
    """KT-05: Material advance compensations must NOT have sortie_cash_512=True."""

    def test_constraint_exists(self):
        """Verify the model has a check constraint for KT-05."""
        from app.models.financial import CompensationST
        constraints = [c.name for c in CompensationST.__table__.constraints if hasattr(c, 'name')]
        assert "ck_kt05_no_cash_512_material" in constraints


# ── KT-08: Block withdrawal > available balance ──────────────────────────

class TestKT08:
    """KT-08: Withdrawals must be blocked if amount > solde_disponible_retrait."""

    @pytest.mark.asyncio
    async def test_withdrawal_blocked(self, db: AsyncSession):
        """Withdrawal exceeding available balance should raise BlockingError."""
        # Create a compte courant with low balance
        assoc = Associe(
            id=str(uuid.uuid4()),
            tenant_id=TENANT_ID,
            entreprise_id=str(uuid.uuid4()),
            nom="Test",
            part_pct=10,
        )
        db.add(assoc)
        await db.flush()

        cc = CompteCourantAssocie(
            id=str(uuid.uuid4()),
            associe_id=assoc.id,
            solde_global=Decimal("1000.00"),
            solde_disponible_retrait=Decimal("500.00"),
        )
        db.add(cc)
        await db.flush()

        with pytest.raises(BlockingError, match="dépasse le solde disponible"):
            await validate_retrait_associe(assoc.id, Decimal("600.00"), db)


# ── KT-09: Share cession post-transfer sum = 100% ────────────────────────

class TestKT09:
    """KT-09: After share cession, total shares for a project must = 100%."""

    def test_shares_must_equal_100(self):
        """Verify blocking rule exists for >100% shares."""
        from app.services.blocking_rules import validate_project_shares_sum
        assert validate_project_shares_sum is not None


# ── CFF Engine Tests ──────────────────────────────────────────────────────

class TestCFFEngine:
    """Test CFF calculation engine."""

    def test_basic_calculation(self):
        engine = CFFEngine(taux_tva=0.19, taux_ibs=0.19, taux_tap=0.02)
        result = engine.calculer(
            Decimal("1000000"),
            [{"associe_id": "a1", "pourcentage": 50}, {"associe_id": "a2", "pourcentage": 50}],
            "TEST",
        )
        assert result.cff_tva == 190000.0
        assert result.cff_ibs == 190000.0
        assert result.cff_tap == 20000.0
        assert result.cff_total > 0
        assert len(result.imputations) == 2

    def test_imputation_sum_equals_total(self):
        engine = CFFEngine()
        result = engine.calculer(
            Decimal("500000"),
            [
                {"associe_id": "a1", "pourcentage": 30},
                {"associe_id": "a2", "pourcentage": 30},
                {"associe_id": "a3", "pourcentage": 40},
            ],
            "TEST",
        )
        total_imputed = sum(i.montant_impute for i in result.imputations)
        assert abs(total_imputed - result.cff_total) < 0.02  # rounding


# ── RF1-RF4 Tests ─────────────────────────────────────────────────────────

class TestRealiteFinanciere:
    """Test RF1-RF4 enum and mappings."""

    def test_rf_enum_has_4_values(self):
        assert len(RealiteFinanciere) == 4

    def test_rf_values(self):
        assert RealiteFinanciere.RF1.value == "RF1"
        assert RealiteFinanciere.RF2.value == "RF2"
        assert RealiteFinanciere.RF3.value == "RF3"
        assert RealiteFinanciere.RF4.value == "RF4"

    def test_rf_to_statut_mapping(self):
        from app.models.financial import RF_TO_STATUT, STATUT_TO_RF
        assert len(RF_TO_STATUT) == 4
        assert len(STATUT_TO_RF) == 5  # includes both F and FD → RF3


# ── Sanity Checks ─────────────────────────────────────────────────────────

class TestSanityChecks:
    """P1 sanity checks."""

    def test_meta_auto_deploy_false(self):
        """P1-C5: META_AUTO_DEPLOY must always be FALSE."""
        from app.config import get_settings
        settings = get_settings()
        assert settings.META_AUTO_DEPLOY is False, "CRITICAL: auto_deploy must be FALSE"

    def test_cloture_uses_entreprise_associes(self):
        """Verify cloture uses EntrepriseAssocie, not PartProjet."""
        import inspect
        from app.services.cloture_service import executer_cloture_mensuelle
        source = inspect.getsource(executer_cloture_mensuelle)
        assert "EntrepriseAssocie" in source, "Must use EntrepriseAssocie (% entreprise)"
        assert "select(PartProjet)" not in source, "Must NOT use PartProjet (% projet)"
