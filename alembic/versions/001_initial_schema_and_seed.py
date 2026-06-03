"""Initial schema: auth_user, company, associate + seed 12 entities and 9 associates.

Revision ID: 001
Revises: None
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ─── Fixed UUIDs for seed data (deterministic, reproducible) ─────────────────

# System user for seeded records
SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"

# Company UUIDs (keyed by code)
COMPANY_IDS = {
    "ETS-DK":   "10000000-0000-0000-0000-000000000001",
    "SARL-DP":  "10000000-0000-0000-0000-000000000002",
    "SARL-DBPI":"10000000-0000-0000-0000-000000000003",
    "SARL-OC":  "10000000-0000-0000-0000-000000000004",
    "SARL-SEN": "10000000-0000-0000-0000-000000000005",
    "SARL-EP":  "10000000-0000-0000-0000-000000000006",
    "EURL-BIM": "10000000-0000-0000-0000-000000000007",
    "SARL-AMF": "10000000-0000-0000-0000-000000000008",
    "EURL-BAY": "10000000-0000-0000-0000-000000000009",
    "SARL-M60": "10000000-0000-0000-0000-00000000000a",
    "SARL-ARC": "10000000-0000-0000-0000-00000000000b",
    "SCI-DEN":  "10000000-0000-0000-0000-00000000000c",
}

# Associate UUIDs
ASSOCIATE_IDS = {
    "ADMIN Ahmed":                    "20000000-0000-0000-0000-000000000001",
    "ASSOC Mohamed":                  "20000000-0000-0000-0000-000000000002",
    "ASSOC Yazid (Lyazid)":           "20000000-0000-0000-0000-000000000003",
    "ASSOC Yamina (Ait Benamara)":    "20000000-0000-0000-0000-000000000004",
    "BOUMERDASSI Mustapha":             "20000000-0000-0000-0000-000000000005",
    "AMIRAT Brahim":                    "20000000-0000-0000-0000-000000000006",
    "ASSOC Laid":                     "20000000-0000-0000-0000-000000000007",
    "MOUKHTARI Tarek":                  "20000000-0000-0000-0000-000000000008",
    "MOUKHTARI Amine":                  "20000000-0000-0000-0000-000000000009",
}


def upgrade() -> None:
    # ── 1. auth_user (FK target for created_by) ──────────────────────────
    op.create_table(
        "auth_user",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(150), unique=True, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    # ── 2. company ───────────────────────────────────────────────────────
    op.create_table(
        "company",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        # Identity
        sa.Column("code", sa.String(20), unique=True, nullable=False),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("legal_form", sa.String(10), nullable=False),
        # Tax / registry
        sa.Column("nif", sa.String(30), nullable=True),
        sa.Column("rc", sa.String(50), nullable=True),
        # Status
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("activity", sa.String(255), nullable=True),
        # Fiscal
        sa.Column("fiscal_regime", sa.String(20), nullable=True),
        sa.Column("ibs_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("tap_rate", sa.Numeric(5, 2), nullable=True),
        # CNAS
        sa.Column("cnas_regime", sa.String(10), nullable=True),
        sa.Column("cnas_employee_rate", sa.Numeric(6, 3), nullable=True),
        sa.Column("cnas_employer_rate", sa.Numeric(6, 3), nullable=True),
        # System columns
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
    )

    # ── 3. associate ─────────────────────────────────────────────────────
    op.create_table(
        "associate",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("canonical_name", sa.String(255), nullable=False),
        sa.Column("is_founder", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("role", sa.String(100), nullable=True),
        sa.Column("has_cca", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        # System columns
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
    )

    # ── 4. updated_at auto-update trigger function ───────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    for table in ("company", "associate"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)

    # ── 5. Seed system user ──────────────────────────────────────────────
    op.execute(f"""
        INSERT INTO auth_user (id, username)
        VALUES ('{SYSTEM_USER_ID}', 'system');
    """)

    # ── 6. Seed 12 companies ─────────────────────────────────────────────
    companies = [
        # (code, legal_name, legal_form, status, activity, cnas_regime, employee_rate, employer_rate)
        ("ETS-DK",   "ETS GFI Fondation",       "ETS",  "ACTIF — À FERMER",  "Commerce matériaux",              "GENERAL", "9.000",  "25.000"),
        ("SARL-DP",  "SARL GFI Promotion",      "SARL", "ACTIF",             "Promotion immobilière",           "BTPH",    "9.375",  "25.375"),
        ("SARL-DBPI","SARL DBPI Immobilier",         "SARL", "ACTIF — À FERMER",  "Promotion immobilière",           "BTPH",    "9.375",  "25.375"),
        ("SARL-OC",  "SARL Omega Construction",      "SARL", "À FERMER",          "Construction",                    "BTPH",    "9.375",  "25.375"),
        ("SARL-SEN", "SARL Senimar",                 "SARL", "À DÉVELOPPER",      "Promotion immobilière",           "BTPH",    "9.375",  "25.375"),
        ("SARL-EP",  "SARL Elite Promotion",         "SARL", "À DÉVELOPPER",      "Promotion immobilière",           "BTPH",    "9.375",  "25.375"),
        ("EURL-BIM", "EURL Bimha Construction",      "EURL", "À DÉVELOPPER",      "Construction et réalisation",     "BTPH",    "9.375",  "25.375"),
        ("SARL-AMF", "SARL AMENFORT Béton",          "SARL", "DISSOUTE",          "Origine du capital (historique)",  None,      None,     None),
        ("EURL-BAY", "EURL BAYTI / ALLO MAISON",    "EURL", "SATELLITE",         "Factures RF3 uniquement",         "GENERAL", "9.000",  "25.000"),
        ("SARL-M60", "SARL Maison en 60 Jours",     "SARL", "ACTIF",             "Construction industrialisée",     "BTPH",    "9.375",  "25.375"),
        ("SARL-ARC", "SARL ARCEN",                   "SARL", "ACTIF",             "Centrales à béton",               "BTPH",    "9.375",  "25.375"),
        ("SCI-DEN",  "SCI GFI",                  "SCI",  "ACTIF",             "Gestion patrimoine",              "GENERAL", "9.000",  "25.000"),
    ]

    for code, name, form, status, activity, cnas, emp_rate, pat_rate in companies:
        cid = COMPANY_IDS[code]
        cnas_val = f"'{cnas}'" if cnas else "NULL"
        emp_val = emp_rate if emp_rate else "NULL"
        pat_val = pat_rate if pat_rate else "NULL"
        op.execute(f"""
            INSERT INTO company (
                id, code, legal_name, legal_form, status, activity,
                cnas_regime, cnas_employee_rate, cnas_employer_rate,
                created_by
            ) VALUES (
                '{cid}', '{code}', '{name}', '{form}', '{status}', '{activity}',
                {cnas_val}, {emp_val}, {pat_val},
                '{SYSTEM_USER_ID}'
            );
        """)

    # ── 7. Seed 9 associates (one row per associate, linked to first relevant company) ──
    # These are "person" records. Full company-associate mapping will be in a junction table later.
    # For now, founders link to ETS-DK (the original entity); project associates to their primary company.
    associates = [
        # (name, is_founder, role, has_cca, company_code)
        ("ADMIN Ahmed",                 True,  "DAF / Gérant",             True,  "ETS-DK"),
        ("ASSOC Mohamed",               True,  "Associé",                  True,  "ETS-DK"),
        ("ASSOC Yazid (Lyazid)",        True,  "Associé",                  True,  "ETS-DK"),
        ("ASSOC Yamina (Ait Benamara)", True,  "Associée",                 True,  "ETS-DK"),
        ("BOUMERDASSI Mustapha",          False, "Associé projet",           False, "SARL-DP"),
        ("AMIRAT Brahim",                 False, "Associé projet",           False, "SARL-DP"),
        ("ASSOC Laid",                  False, "Associé projet (T5000 50%)", False, "SARL-DBPI"),
        ("MOUKHTARI Tarek",               False, "Associé projet",           False, "SARL-DP"),
        ("MOUKHTARI Amine",               False, "Associé projet",           False, "SARL-DP"),
    ]

    for name, founder, role, cca, company_code in associates:
        aid = ASSOCIATE_IDS[name]
        cid = COMPANY_IDS[company_code]
        op.execute(f"""
            INSERT INTO associate (
                id, company_id, canonical_name, is_founder, role, has_cca,
                created_by
            ) VALUES (
                '{aid}', '{cid}', '{name}', {str(founder).lower()}, '{role}', {str(cca).lower()},
                '{SYSTEM_USER_ID}'
            );
        """)


def downgrade() -> None:
    # Drop triggers first
    for table in ("associate", "company"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
    op.execute("DROP FUNCTION IF EXISTS gfi_set_updated_at();")

    op.drop_table("associate")
    op.drop_table("company")
    op.drop_table("auth_user")
