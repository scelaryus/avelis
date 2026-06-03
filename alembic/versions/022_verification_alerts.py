"""Verification system, alerts, scheduled reports, DAF dashboard.

Tables:
- alert: 5-level alert system (INFO to BLOQUANT)
- verification_run: execution log for V1-V10
- scheduled_report: 7 automated report configs (seeded)
- daf_dashboard_snapshot: periodic dashboard data

Revision ID: 022
Revises: 021
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_rpt_counter = 0


def _rpt_uuid():
    global _rpt_counter
    _rpt_counter += 1
    return f"f3000000-0000-0000-0000-{_rpt_counter:012x}"


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


REPORTS = [
    ("RPT_CC_GROUP", "Monthly CC Group Report", "MONTHLY",
     "0 8 1 * *", '["DAF"]', False,
     "Full RF1+RF2+RF3 consolidation, all entities, all projects."),
    ("RPT_PROJECT", "Monthly Project Report", "MONTHLY",
     "0 8 1 * *", '["DAF", "MANAGER_PROJETS"]', False,
     "Marge brute/nette, budget consumption, GACEB balance."),
    ("RPT_ASSOCIATE", "Monthly Associate Report", "MONTHLY",
     "0 8 1 * *", '["DAF"]', True,
     "CONFIDENTIEL. Per associate: QP per project, CFF, withdrawals."),
    ("RPT_BUDGET_OVERRUN", "Budget Overrun Alert", "IMMEDIATE",
     None, '["DAF", "MANAGER_PROJETS"]', False,
     "Triggered when cost > 80% of budget on any CC node."),
    ("RPT_CC_TREASURY", "CC-Treasury Reconciliation", "DAILY",
     "0 4 * * *", '["TRESORIER", "DAF"]', False,
     "Discrepancies between CC and treasury."),
    ("RPT_ALIASES", "Unresolved Aliases Report", "WEEKLY",
     "0 9 * * 1", '["DAF"]', False,
     "Aliases pending human validation."),
    ("RPT_FORMULAIRES", "Pending Formulaires Report", "DAILY",
     "0 8 * * *", '["DAF"]', False,
     "Unanswered formulaires with age, priority, blocking impact."),
]


def upgrade() -> None:
    # ═════════════════════════════════════════════════════════════════════
    # 1. alert
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "alert",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("level", sa.String(10), nullable=False, index=True),
        sa.Column("code", sa.String(30), nullable=True, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("verification_code", sa.String(10), nullable=True),
        sa.Column("resource_type", sa.String(60), nullable=True),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'ACTIVE'")),
        sa.Column("is_blocking", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("acknowledged_by", UUID(as_uuid=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("detail_json", JSONB, nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. verification_run
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "verification_run",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("verification_code", sa.String(10), nullable=False, index=True),
        sa.Column("verification_name", sa.String(100), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.String(10), nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("items_checked", sa.Integer, nullable=True),
        sa.Column("items_failed", sa.Integer, nullable=True),
        sa.Column("detail_json", JSONB, nullable=True),
        sa.Column("alert_id", UUID(as_uuid=True),
                  sa.ForeignKey("alert.id", ondelete="SET NULL"),
                  nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. scheduled_report (system reference)
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "scheduled_report",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(30), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("schedule_cron", sa.String(50), nullable=True),
        sa.Column("recipient_roles", JSONB, nullable=False),
        sa.Column("confidential", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 4. daf_dashboard_snapshot
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "daf_dashboard_snapshot",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("snapshot_date", sa.Date, nullable=False, index=True),
        sa.Column("total_encaissements_officiel", sa.Numeric(15, 2), nullable=True),
        sa.Column("total_encaissements_interne", sa.Numeric(15, 2), nullable=True),
        sa.Column("total_decaissements_officiel", sa.Numeric(15, 2), nullable=True),
        sa.Column("total_decaissements_interne", sa.Numeric(15, 2), nullable=True),
        sa.Column("total_cff", sa.Numeric(15, 2), nullable=True),
        sa.Column("solde_net_officiel", sa.Numeric(15, 2), nullable=True),
        sa.Column("solde_net_interne", sa.Numeric(15, 2), nullable=True),
        sa.Column("ecart", sa.Numeric(15, 2), nullable=True),
        sa.Column("associate_data", JSONB, nullable=True),
        sa.Column("top_projects", JSONB, nullable=True),
        sa.Column("active_alerts_count", sa.Integer, nullable=True),
        sa.Column("active_alerts_summary", JSONB, nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 5. CHECK CONSTRAINTS
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        ALTER TABLE alert
        ADD CONSTRAINT chk_alert_level
        CHECK (level IN ('INFO', 'ATTENTION', 'ALERTE', 'CRITIQUE', 'BLOQUANT'));
    """)

    op.execute("""
        ALTER TABLE verification_run
        ADD CONSTRAINT chk_vr_result
        CHECK (result IN ('PASS', 'FAIL'));
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 6. TRIGGERS
    # ═════════════════════════════════════════════════════════════════════
    for table in ("alert", "verification_run", "daf_dashboard_snapshot"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)
    op.execute("SELECT gfi_apply_no_delete_trigger('alert');")
    op.execute("SELECT gfi_apply_no_delete_trigger('verification_run');")
    op.execute("SELECT gfi_apply_no_delete_trigger('daf_dashboard_snapshot');")

    # ═════════════════════════════════════════════════════════════════════
    # 7. SEED — 7 scheduled reports
    # ═════════════════════════════════════════════════════════════════════
    for code, name, freq, cron, roles, conf, desc in REPORTS:
        uid = _rpt_uuid()
        name_esc = name.replace("'", "''")
        desc_esc = desc.replace("'", "''")
        cron_sql = f"'{cron}'" if cron else "NULL"
        conf_sql = "true" if conf else "false"
        op.execute(f"""
            INSERT INTO scheduled_report (
                id, code, name, frequency, schedule_cron,
                recipient_roles, confidential, description
            ) VALUES (
                '{uid}', '{code}', '{name_esc}', '{freq}', {cron_sql},
                '{roles}'::jsonb, {conf_sql}, '{desc_esc}'
            );
        """)


def downgrade() -> None:
    for table in ("daf_dashboard_snapshot", "verification_run", "alert"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")
    op.drop_table("daf_dashboard_snapshot")
    op.drop_table("verification_run")
    op.drop_table("scheduled_report")
    op.drop_table("alert")
