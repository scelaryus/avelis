"""16 CC cost categories: configuration, payroll imputation, allocation keys, BBZ.

Tables:
- cc_category_config: 16 category definitions with distribution rules (seeded)
- payroll_imputation: employee time allocation across projects (CC4)
- allocation_key: configurable ventilation keys (CC5 BBZ, shared charges)
- bbz_charge: BBZ charge components (fit-out, rent advance, monthly rent)

Revision ID: 020
Revises: 019
Create Date: 2026-03-18
"""
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_cfg_counter = 0


def _cfg_uuid():
    global _cfg_counter
    _cfg_counter += 1
    return f"f2000000-0000-0000-0000-{_cfg_counter:012x}"


def _system_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_by", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("version", sa.Integer, nullable=False,
                  server_default=sa.text("1")),
    ]


CATEGORIES = [
    (1, "TERRAIN", "Cout du terrain", "PCT_PROJET",
     ["211", "622"], True, None,
     "Terrains + frais notaire. Cross-check avec actes."),
    (2, "CONSTR", "Construction (situations de travaux)", "PCT_PROJET",
     ["612"], True, None,
     "Brut/Deductions/Net. GACEB: gross amount here, deductions in CC8."),
    (3, "VRD", "Materiaux (achats directs)", "PCT_PROJET",
     ["601", "604"], True, None,
     "Direct material purchases, not subcontractor situations."),
    (4, "CHARGES_GEN", "Masse salariale imputee", "PCT_PROJET",
     ["631", "635"], True, None,
     "Split per payroll_imputation table. ventilated per employee time."),
    (5, "BBZ", "Bureau Bab Ezzouar", "CUSTOM",
     ["613"], True, None,
     "3 components: fit-out 60M + advance 10M + rent 24M = 94M. Ventilated."),
    (6, "CFF", "Dossier fiscal fictif", "PCT_ENTREPRISE",
     [], True, None,
     "CRITICAL: % ENTREPRISE EMETTRICE. NEVER % projet."),
    (7, "INTER_PROJ", "Flux inter-projets", "PCT_PROJET",
     ["580"], True, None,
     "Mirror entries: debit source / credit dest. FC-016 for nature."),
    (8, "COMPENSATION", "Compensations en nature", "PCT_PROJET",
     [], False, None,
     "No cash movement. impact_tresorerie=false. GACEB 120M, vehicles, apts."),
    (9, "ASSOC", "Prelevements associes", "ASSOCIATE_100PCT",
     ["455"], True, None,
     "100% to specific associate. NOT distributed among all."),
    (10, "COMMISSION", "Commissions et dettes personnelles", "ASSOCIATE_100PCT",
     ["455"], True, None,
     "Villa Yazid, Khadidja 18M. 100% to specific associate."),
    (11, "IMPOTS", "Fiscal (impots reels)", "MIXED",
     ["64"], True, None,
     "G50, TVA, TAP, IBS on real business. NOT CC6 (fictitious taxes)."),
    (12, "VENTES_RF1", "Ventes declarees (RF1)", "PCT_PROJET",
     ["701", "704"], True, None,
     "Revenue from RF1 payments. Official accounting."),
    (13, "VENTES_RF2", "Ventes non declarees (RF2)", "PCT_PROJET",
     [], True, None,
     "Revenue from RF2 cash payments. Internal tracking only."),
    (14, "FRAIS_ADM", "Frais administratifs", "MIXED",
     ["621", "625", "65"], True, None,
     "Honoraria, insurance, legal. Project or company level."),
    (15, "FRAIS_FIN", "Frais financiers", "MIXED",
     ["66"], True, None,
     "Bank charges, loan interest."),
    (16, "DIVERS", "Divers (a reclassifier)", "PCT_PROJET",
     [], True, 30,
     "Unclassified. DAF must reclassify within 30 days -> alert."),
]


def upgrade() -> None:
    # ═════════════════════════════════════════════════════════════════════
    # 1. cc_category_config (system reference)
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "cc_category_config",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(20), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("cc_number", sa.Integer, nullable=False),
        sa.Column("distribution_rule", sa.String(30), nullable=False),
        sa.Column("source_accounts", JSONB, nullable=True),
        sa.Column("source_modules", JSONB, nullable=True),
        sa.Column("impact_tresorerie", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
        sa.Column("requires_allocation_key", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("auto_reclassify_days", sa.Integer, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("is_deleted", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. payroll_imputation
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "payroll_imputation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("employee_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("employee_name", sa.String(255), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("pourcentage_temps", sa.Numeric(5, 2), nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date, nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. allocation_key
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "allocation_key",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("key_name", sa.String(100), nullable=False),
        sa.Column("cc_category", sa.String(20), nullable=False, index=True),
        sa.Column("basis", sa.String(30), nullable=False),
        sa.Column("allocations", JSONB, nullable=True),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 4. bbz_charge
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "bbz_charge",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("charge_type", sa.String(30), nullable=False),
        sa.Column("montant_total", sa.Numeric(15, 2), nullable=False),
        sa.Column("amortization_method", sa.String(20), nullable=True),
        sa.Column("amortization_months", sa.Integer, nullable=True),
        sa.Column("monthly_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 5. CHECK CONSTRAINTS
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        ALTER TABLE allocation_key
        ADD CONSTRAINT chk_ak_basis
        CHECK (basis IN ('CHIFFRE_AFFAIRES', 'SURFACE', 'POURCENTAGE_FIXE'));
    """)

    op.execute("""
        ALTER TABLE bbz_charge
        ADD CONSTRAINT chk_bbz_type
        CHECK (charge_type IN ('FIT_OUT', 'RENT_ADVANCE', 'MONTHLY_RENT'));
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 6. TRIGGERS
    # ═════════════════════════════════════════════════════════════════════
    for table in ("payroll_imputation", "allocation_key", "bbz_charge"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")

    # ═════════════════════════════════════════════════════════════════════
    # 7. SEED — 16 CC category configs
    # ═════════════════════════════════════════════════════════════════════
    for (cc_num, code, name, dist_rule, accounts,
         impact, reclass_days, desc) in CATEGORIES:
        uid = _cfg_uuid()
        desc_esc = desc.replace("'", "''")
        name_esc = name.replace("'", "''")
        accounts_json = json.dumps(accounts)
        impact_sql = "true" if impact else "false"
        reclass = str(reclass_days) if reclass_days else "NULL"
        req_alloc = "true" if code == "BBZ" else "false"

        op.execute(f"""
            INSERT INTO cc_category_config (
                id, code, name, cc_number, distribution_rule,
                source_accounts, impact_tresorerie,
                requires_allocation_key, auto_reclassify_days,
                description
            ) VALUES (
                '{uid}', '{code}', '{name_esc}', {cc_num}, '{dist_rule}',
                '{accounts_json}'::jsonb, {impact_sql},
                {req_alloc}, {reclass},
                '{desc_esc}'
            );
        """)


def downgrade() -> None:
    for table in ("bbz_charge", "allocation_key", "payroll_imputation"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")
    op.drop_table("bbz_charge")
    op.drop_table("allocation_key")
    op.drop_table("payroll_imputation")
    op.drop_table("cc_category_config")
