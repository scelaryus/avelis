"""Projects table, entreprise_associe, part_projet + ownership seed data.

This migration creates the three most critical financial tables in the system:
1. project — the 16 real-estate projects
2. entreprise_associe — company-level ownership % (for CFF, company charges)
3. part_projet — project-level ownership % (for profit distribution)

% in the COMPANY != % in the PROJECT.  Confusing them causes grave errors.

Database-level enforcement:
- KT-09: After any INSERT/UPDATE on entreprise_associe or part_projet,
  a trigger verifies sum(percentage) = 100.0000% for the affected group.
  If not -> ROLLBACK.
- Soft-delete triggers (KT-10) applied to all three new tables.
- updated_at auto-update triggers applied to all three new tables.

Revision ID: 003
Revises: 002
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ─── Reuse UUIDs from migration 001 ─────────────────────────────────────────
SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"

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

ASSOCIATE_IDS = {
    "Ahmed":  "20000000-0000-0000-0000-000000000001",
    "Mohamed":"20000000-0000-0000-0000-000000000002",
    "Yazid":  "20000000-0000-0000-0000-000000000003",
    "Yamina": "20000000-0000-0000-0000-000000000004",
    "Laid":   "20000000-0000-0000-0000-000000000007",
}

# ─── Project UUIDs ───────────────────────────────────────────────────────────
PROJECT_IDS = {
    "EDEN":         "30000000-0000-0000-0000-000000000001",
    "JASMIN":       "30000000-0000-0000-0000-000000000002",
    "OPERA":        "30000000-0000-0000-0000-000000000003",
    "LYS":          "30000000-0000-0000-0000-000000000004",
    "IRENE":        "30000000-0000-0000-0000-000000000005",
    "MAGNOLIA":     "30000000-0000-0000-0000-000000000006",
    "AUREA":        "30000000-0000-0000-0000-000000000007",
    "ASTERIA":      "30000000-0000-0000-0000-000000000008",
    "MOSQUEE":      "30000000-0000-0000-0000-000000000009",
    "T21000":       "30000000-0000-0000-0000-00000000000a",
    "T5000":        "30000000-0000-0000-0000-00000000000b",
    "T2400":        "30000000-0000-0000-0000-00000000000c",
    "ELITE-DRIVE":  "30000000-0000-0000-0000-00000000000d",
    "ALLO-MAISON":  "30000000-0000-0000-0000-00000000000e",
    "PFSB":         "30000000-0000-0000-0000-00000000000f",
    "DG":           "30000000-0000-0000-0000-000000000010",
}

# Counters for deterministic UUID generation in ownership rows.
_ea_counter = 0
_pp_counter = 0


def _ea_uuid():
    global _ea_counter
    _ea_counter += 1
    return f"40000000-0000-0000-0000-{_ea_counter:012x}"


def _pp_uuid():
    global _pp_counter
    _pp_counter += 1
    return f"50000000-0000-0000-0000-{_pp_counter:012x}"


# ─── Standard system columns snippet (for create_table) ─────────────────────
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


def upgrade() -> None:
    # ═════════════════════════════════════════════════════════════════════
    # 1. CREATE TABLES
    # ═════════════════════════════════════════════════════════════════════

    # ── 1a. project ──────────────────────────────────────────────────────
    op.create_table(
        "project",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        # Identity
        sa.Column("code", sa.String(30), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("aliases", ARRAY(sa.Text), nullable=True),
        # Status
        sa.Column("status", sa.String(40), nullable=False),
        # Client tracking
        sa.Column("client_count", sa.Integer, nullable=True),
        # Financial
        sa.Column("terrain_cost_estimate", sa.Numeric(15, 2), nullable=True),
        # Land ownership (distinct from project parts)
        sa.Column("proprietaire_foncier", sa.Text, nullable=True),
        # Non-commercial flag
        sa.Column("is_non_commercial", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        # Transfer tracking (FC-012)
        sa.Column("transferred_from_company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=True),
        sa.Column("transfer_date", sa.Date, nullable=True),
        sa.Column("transfer_formulaire_ref", sa.String(20), nullable=True),
        # System columns
        *_system_columns(),
    )

    # ── 1b. entreprise_associe ───────────────────────────────────────────
    op.create_table(
        "entreprise_associe",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("associate_id", UUID(as_uuid=True),
                  sa.ForeignKey("associate.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("percentage", sa.Numeric(7, 4), nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        # System columns
        *_system_columns(),
        # Unique constraint: one percentage per associate per company
        sa.UniqueConstraint("company_id", "associate_id",
                            name="uq_entreprise_associe_company_associate"),
    )

    # ── 1c. part_projet ──────────────────────────────────────────────────
    op.create_table(
        "part_projet",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("associate_id", UUID(as_uuid=True),
                  sa.ForeignKey("associate.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("percentage", sa.Numeric(7, 4), nullable=False),
        # System columns
        *_system_columns(),
        # Unique constraint: one percentage per associate per project
        sa.UniqueConstraint("project_id", "associate_id",
                            name="uq_part_projet_project_associate"),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. TRIGGERS — updated_at, soft-delete, 100% sum (KT-09)
    # ═════════════════════════════════════════════════════════════════════

    # ── 2a. updated_at triggers ──────────────────────────────────────────
    for table in ("project", "entreprise_associe", "part_projet"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)

    # ── 2b. Soft-delete triggers (KT-10) ────────────────────────────────
    for table in ("project", "entreprise_associe", "part_projet"):
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")

    # ── 2c. KT-09: 100% sum constraint on entreprise_associe ────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_check_ea_sum()
        RETURNS TRIGGER AS $$
        DECLARE
            total NUMERIC(10, 4);
        BEGIN
            SELECT COALESCE(SUM(percentage), 0) INTO total
            FROM entreprise_associe
            WHERE company_id = NEW.company_id
              AND is_deleted = false;

            IF total != 100.0000 THEN
                RAISE EXCEPTION
                    'KT-09: entreprise_associe sum for company_id=% is %.4s%%, expected 100.0000%%',
                    NEW.company_id, total
                USING ERRCODE = 'check_violation';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Use CONSTRAINT trigger with DEFERRABLE so we can insert multiple rows
    # in one transaction and only check the sum at COMMIT.
    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_entreprise_associe_sum_check
        AFTER INSERT OR UPDATE ON entreprise_associe
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION gfi_check_ea_sum();
    """)

    # ── 2d. KT-09: 100% sum constraint on part_projet ───────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_check_pp_sum()
        RETURNS TRIGGER AS $$
        DECLARE
            total NUMERIC(10, 4);
        BEGIN
            SELECT COALESCE(SUM(percentage), 0) INTO total
            FROM part_projet
            WHERE project_id = NEW.project_id
              AND is_deleted = false;

            IF total != 100.0000 THEN
                RAISE EXCEPTION
                    'KT-09: part_projet sum for project_id=% is %.4s%%, expected 100.0000%%',
                    NEW.project_id, total
                USING ERRCODE = 'check_violation';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE CONSTRAINT TRIGGER trg_part_projet_sum_check
        AFTER INSERT OR UPDATE ON part_projet
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION gfi_check_pp_sum();
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 3. SEED DATA — 16 projects
    # ═════════════════════════════════════════════════════════════════════

    # Helper to escape single quotes in SQL strings
    def q(s):
        return s.replace("'", "''") if s else s

    # (code, name, aliases, company_code, status, client_count,
    #  terrain_cost_estimate, proprietaire_foncier, is_non_commercial,
    #  transferred_from_code, transfer_date)
    projects = [
        ("EDEN", "Eden",
         ["FOES"],
         "ETS-DK", "ACTIF", 154,
         250000000, None, False, None, None),

        ("JASMIN", "Les Jasmins",
         ["Sahel", "Les Jasmins"],
         "ETS-DK", "ACTIF", 100,
         50000000, None, False, None, None),

        ("OPERA", "Jardin de l''Opéra",
         ["Ouled Fayet", "Les Jardins de l''Opera"],
         "SARL-DP", "ACTIF", None,
         340000000, None, False, "ETS-DK", None),

        ("LYS", "Les Lys",
         ["02H", "02 Hectare", "Bentala", "Draria", "Dhous 2 hectare"],
         "SARL-DBPI", "ACTIF", None,
         200000000, None, False, None, None),

        ("IRENE", "Irène / 05 Hectare",
         ["5H", "Ami Djamel", "05H", "Boumerdes"],
         "SARL-DP", "ACTIF", None,
         500000000, None, False, None, None),

        ("MAGNOLIA", "Magnolia",
         ["Les Magnolia"],
         "SARL-OC", "ACTIF", 18,
         32000000, None, False, None, None),

        ("AUREA", "Auréa",
         ["Cheraga", "Chéraga"],
         "SARL-DP", "ACTIF", 199,
         340000000, None, False, None, None),

        ("ASTERIA", "Asteria",
         ["El Achour"],
         "SARL-SEN", "ACTIF", 52,
         230000000, None, False, None, None),

        ("MOSQUEE", "Mosquée Taoura",
         ["Taoura", "Taourga"],
         "ETS-DK", "DONATION", None,
         None, None, True, None, None),

        ("T21000", "Terrain 21 000 m²",
         None,
         "ETS-DK", "TERRAIN", None,
         None, "ADMIN Ahmed (100% propriétaire foncier)", False, None, None),

        ("T5000", "Terrain 5 000 m²",
         None,
         "SARL-DBPI", "EN_ATTENTE_CONFIRMATION", None,
         None, None, False, None, None),

        ("T2400", "Terrain 2 400 m²",
         None,
         "SARL-DBPI", "TERRAIN", None,
         None, None, False, None, None),

        ("ELITE-DRIVE", "Elite Drive",
         None,
         "EURL-BIM", "A_DEVELOPPER", None,
         None, None, False, None, None),

        ("ALLO-MAISON", "Allo Maison",
         None,
         "SARL-DP", "A_DEVELOPPER", None,
         None, None, False, None, None),

        ("PFSB", "PFSB",
         None,
         "EURL-BIM", "A_DEVELOPPER", None,
         None, None, False, None, None),

        ("DG", "DG",
         None,
         "SARL-DBPI", "A_DEVELOPPER", None,
         None, None, False, None, None),
    ]

    for (code, name, aliases, company_code, status, clients,
         terrain_cost, prop_foncier, non_commercial,
         transferred_from, transfer_date) in projects:

        pid = PROJECT_IDS[code]
        cid = COMPANY_IDS[company_code]

        # Build aliases array literal
        if aliases:
            arr_items = ", ".join(f"'{q(a)}'" for a in aliases)
            aliases_sql = f"ARRAY[{arr_items}]::TEXT[]"
        else:
            aliases_sql = "NULL"

        clients_sql = str(clients) if clients is not None else "NULL"
        terrain_sql = str(terrain_cost) if terrain_cost is not None else "NULL"
        prop_sql = f"'{q(prop_foncier)}'" if prop_foncier else "NULL"
        non_comm = "true" if non_commercial else "false"

        if transferred_from:
            tfrom_sql = f"'{COMPANY_IDS[transferred_from]}'"
        else:
            tfrom_sql = "NULL"

        tdate_sql = f"'{transfer_date}'" if transfer_date else "NULL"

        op.execute(f"""
            INSERT INTO project (
                id, company_id, code, name, aliases, status,
                client_count, terrain_cost_estimate, proprietaire_foncier,
                is_non_commercial, transferred_from_company_id,
                transfer_date, created_by
            ) VALUES (
                '{pid}', '{cid}', '{q(code)}', '{q(name)}', {aliases_sql}, '{status}',
                {clients_sql}, {terrain_sql}, {prop_sql},
                {non_comm}, {tfrom_sql},
                {tdate_sql}, '{SYSTEM_USER_ID}'
            );
        """)

    # ═════════════════════════════════════════════════════════════════════
    # 4. SEED — entreprise_associe (company-level ownership)
    # ═════════════════════════════════════════════════════════════════════
    #
    # Each tuple: (company_code, [(associate_key, percentage, note), ...])
    # Yamina is explicitly ABSENT from companies where she has 0%.
    # EURL-BAY is SKIPPED entirely (TBD — blocked by FC-008).

    ea_data = [
        ("ETS-DK", [
            ("Ahmed", "25.0000", None), ("Mohamed", "25.0000", None),
            ("Yazid", "25.0000", None), ("Yamina", "25.0000", None),
        ]),
        ("SARL-DP", [
            ("Ahmed", "25.0000", None), ("Mohamed", "25.0000", None),
            ("Yazid", "25.0000", None), ("Yamina", "25.0000", None),
        ]),
        ("SARL-DBPI", [
            ("Ahmed", "60.0000", None), ("Mohamed", "20.0000", None),
            ("Yazid", "20.0000", None),
        ]),
        ("SARL-OC", [
            ("Ahmed", "60.0000", None), ("Mohamed", "20.0000", None),
            ("Yazid", "20.0000", None),
        ]),
        ("SARL-SEN", [
            ("Ahmed", "60.0000", None), ("Mohamed", "20.0000", None),
            ("Yazid", "20.0000", None),
        ]),
        ("SARL-EP", [
            ("Ahmed", "60.0000", None), ("Mohamed", "20.0000", None),
            ("Yazid", "20.0000", None),
        ]),
        ("EURL-BIM", [
            ("Ahmed", "60.0000", None), ("Mohamed", "20.0000", None),
            ("Yazid", "20.0000", None),
        ]),
        ("SARL-AMF", [
            ("Ahmed",  "33.3334", "Approximate — confirm via FC-023"),
            ("Mohamed","33.3333", "Approximate — confirm via FC-023"),
            ("Yazid",  "33.3333", "Approximate — confirm via FC-023"),
        ]),
        # EURL-BAY: SKIPPED — ownership TBD, blocked by FC-008
        ("SARL-M60", [
            ("Ahmed", "60.0000", None), ("Mohamed", "20.0000", None),
            ("Yazid", "20.0000", None),
        ]),
        ("SARL-ARC", [
            ("Ahmed", "60.0000", None), ("Mohamed", "20.0000", None),
            ("Yazid", "20.0000", None),
        ]),
        ("SCI-DEN", [
            ("Ahmed", "60.0000", None), ("Mohamed", "20.0000", None),
            ("Yazid", "20.0000", None),
        ]),
    ]

    for company_code, associates in ea_data:
        cid = COMPANY_IDS[company_code]
        for assoc_key, pct, note in associates:
            uid = _ea_uuid()
            aid = ASSOCIATE_IDS[assoc_key]
            note_sql = f"'{note}'" if note else "NULL"
            op.execute(f"""
                INSERT INTO entreprise_associe (
                    id, company_id, associate_id, percentage, note, created_by
                ) VALUES (
                    '{uid}', '{cid}', '{aid}', {pct}, {note_sql}, '{SYSTEM_USER_ID}'
                );
            """)

    # ═════════════════════════════════════════════════════════════════════
    # 5. SEED — part_projet (project-level ownership)
    # ═════════════════════════════════════════════════════════════════════
    #
    # ONLY projects with status ACTIF, TERRAIN, or DONATION get rows.
    # Projects with A_DEVELOPPER or EN_ATTENTE_CONFIRMATION: NO ROWS.
    #
    # Each tuple: (project_code, [(associate_key, percentage), ...])

    pp_data = [
        # EDEN (ETS-DK): 25/25/25/25
        ("EDEN", [
            ("Ahmed", "25.0000"), ("Mohamed", "25.0000"),
            ("Yazid", "25.0000"), ("Yamina", "25.0000"),
        ]),
        # JASMIN (ETS-DK): 34/33/33/0 — Yamina absent
        ("JASMIN", [
            ("Ahmed", "34.0000"), ("Mohamed", "33.0000"),
            ("Yazid", "33.0000"),
        ]),
        # OPERA (now SARL-DP): 25/25/25/25 as per project table
        ("OPERA", [
            ("Ahmed", "25.0000"), ("Mohamed", "25.0000"),
            ("Yazid", "25.0000"), ("Yamina", "25.0000"),
        ]),
        # LYS (SARL-DBPI): 60/20/20/0 — Yamina absent
        ("LYS", [
            ("Ahmed", "60.0000"), ("Mohamed", "20.0000"),
            ("Yazid", "20.0000"),
        ]),
        # IRENE (SARL-DP): 60/20/20/0 — CRITICAL: differs from SARL-DP's 25/25/25/25
        ("IRENE", [
            ("Ahmed", "60.0000"), ("Mohamed", "20.0000"),
            ("Yazid", "20.0000"),
        ]),
        # MAGNOLIA (SARL-OC): 60/20/20/0
        ("MAGNOLIA", [
            ("Ahmed", "60.0000"), ("Mohamed", "20.0000"),
            ("Yazid", "20.0000"),
        ]),
        # AUREA (SARL-DP): 60/20/20/0 — CRITICAL: differs from SARL-DP's 25/25/25/25
        ("AUREA", [
            ("Ahmed", "60.0000"), ("Mohamed", "20.0000"),
            ("Yazid", "20.0000"),
        ]),
        # ASTERIA (SARL-SEN): 60/20/20/0
        ("ASTERIA", [
            ("Ahmed", "60.0000"), ("Mohamed", "20.0000"),
            ("Yazid", "20.0000"),
        ]),
        # MOSQUEE (ETS-DK): 34/33/33/0 — non-commercial, fund tracking only
        ("MOSQUEE", [
            ("Ahmed", "34.0000"), ("Mohamed", "33.0000"),
            ("Yazid", "33.0000"),
        ]),
        # T21000 (ETS-DK): 25/25/25/25 — GFI split, NOT propriétaire foncier
        ("T21000", [
            ("Ahmed", "25.0000"), ("Mohamed", "25.0000"),
            ("Yazid", "25.0000"), ("Yamina", "25.0000"),
        ]),
        # T2400 (SARL-DBPI): 50/50/0/0
        ("T2400", [
            ("Ahmed", "50.0000"), ("Mohamed", "50.0000"),
        ]),
        # T5000: EN_ATTENTE_CONFIRMATION → NO ROWS (FC-004 required)
        # ELITE-DRIVE: A_DEVELOPPER → NO ROWS (FC-013 required)
        # ALLO-MAISON: A_DEVELOPPER → NO ROWS (FC-013 required)
        # PFSB: A_DEVELOPPER → NO ROWS (FC-013 required)
        # DG: A_DEVELOPPER → NO ROWS (FC-013 required)
    ]

    for project_code, associates in pp_data:
        pid = PROJECT_IDS[project_code]
        # part_projet.company_id = the project's carrying entity
        # Look up which company carries this project
        proj_company = None
        for (code, name, aliases, company_code, status, clients,
             terrain_cost, prop_foncier, non_commercial,
             transferred_from, transfer_date) in projects:
            if code == project_code:
                proj_company = company_code
                break
        cid = COMPANY_IDS[proj_company]

        for assoc_key, pct in associates:
            uid = _pp_uuid()
            aid = ASSOCIATE_IDS[assoc_key]
            op.execute(f"""
                INSERT INTO part_projet (
                    id, company_id, project_id, associate_id, percentage,
                    created_by
                ) VALUES (
                    '{uid}', '{cid}', '{pid}', '{aid}', {pct},
                    '{SYSTEM_USER_ID}'
                );
            """)


def downgrade() -> None:
    # Drop triggers
    for table in ("part_projet", "entreprise_associe", "project"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")

    op.execute("DROP TRIGGER IF EXISTS trg_part_projet_sum_check ON part_projet;")
    op.execute("DROP TRIGGER IF EXISTS trg_entreprise_associe_sum_check ON entreprise_associe;")
    op.execute("DROP FUNCTION IF EXISTS gfi_check_pp_sum();")
    op.execute("DROP FUNCTION IF EXISTS gfi_check_ea_sum();")

    op.drop_table("part_projet")
    op.drop_table("entreprise_associe")
    op.drop_table("project")
