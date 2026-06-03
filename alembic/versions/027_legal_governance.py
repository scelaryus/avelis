"""Legal + governance: contracts, share transfers, capital calls.

Tables:
- contract_lifecycle: all contract types with expiration alerts
- share_transfer: with preemption rights (R-017)
- preemption_right: per-associate response tracking
- capital_call: with CCA freeze on non-payment (R-016)

Revision ID: 027
Revises: 026
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
    # 1. contract_lifecycle
    op.create_table(
        "contract_lifecycle",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("contract_type", sa.String(30), nullable=False),
        sa.Column("contract_ref", sa.String(50), nullable=True, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("counterparty_name", sa.String(255), nullable=False),
        sa.Column("counterparty_id", UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("signature_date", sa.Date, nullable=True),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("expiration_date", sa.Date, nullable=True, index=True),
        sa.Column("termination_date", sa.Date, nullable=True),
        sa.Column("montant", sa.Numeric(15, 2), nullable=True),
        sa.Column("periodicite_paiement", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'BROUILLON'")),
        sa.Column("auto_renewal", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("renewal_notice_days", sa.Integer, nullable=True),
        sa.Column("renewed_contract_id", UUID(as_uuid=True), nullable=True),
        sa.Column("alert_30d_sent", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("alert_15d_sent", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("alert_7d_sent", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("document_url", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_system_columns(),
    )

    # 2. share_transfer
    op.create_table(
        "share_transfer",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("seller_associate_id", UUID(as_uuid=True),
                  sa.ForeignKey("associate.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("buyer_name", sa.String(255), nullable=False),
        sa.Column("buyer_associate_id", UUID(as_uuid=True),
                  sa.ForeignKey("associate.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_internal_transfer", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("ownership_type", sa.String(20), nullable=False),
        sa.Column("target_entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("percentage_transferred", sa.Numeric(7, 4), nullable=False),
        sa.Column("transfer_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("request_date", sa.Date, nullable=False),
        sa.Column("preemption_deadline", sa.Date, nullable=False),
        sa.Column("preemption_period_days", sa.Integer, nullable=False,
                  server_default=sa.text("30")),
        sa.Column("completion_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(30), nullable=False,
                  server_default=sa.text("'DEMANDE'")),
        sa.Column("blocking_reason", sa.Text, nullable=True),
        sa.Column("sum_verified_100pct", sa.Boolean, nullable=True),
        *_system_columns(),
    )

    # 3. preemption_right
    op.create_table(
        "preemption_right",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("share_transfer_id", UUID(as_uuid=True),
                  sa.ForeignKey("share_transfer.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("associate_id", UUID(as_uuid=True),
                  sa.ForeignKey("associate.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline", sa.Date, nullable=False),
        sa.Column("response", sa.String(20), nullable=False,
                  server_default=sa.text("'NOTIFIE'")),
        sa.Column("response_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_system_columns(),
    )

    # 4. capital_call
    op.create_table(
        "capital_call",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("associate_id", UUID(as_uuid=True),
                  sa.ForeignKey("associate.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("call_date", sa.Date, nullable=False),
        sa.Column("call_ref", sa.String(50), nullable=True),
        sa.Column("montant", sa.Numeric(15, 2), nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("montant_paye", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("montant_restant", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'EMIS'")),
        sa.Column("cca_freeze_id", UUID(as_uuid=True),
                  sa.ForeignKey("cca_freeze.id", ondelete="SET NULL"),
                  nullable=True),
        *_system_columns(),
    )

    # Triggers
    for table in ("contract_lifecycle", "share_transfer",
                   "preemption_right", "capital_call"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")


def downgrade() -> None:
    for table in ("capital_call", "preemption_right",
                   "share_transfer", "contract_lifecycle"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")
    op.drop_table("capital_call")
    op.drop_table("preemption_right")
    op.drop_table("share_transfer")
    op.drop_table("contract_lifecycle")
