"""044 — Accounting journal, entries, bank reconciliation tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None


def upgrade():
    # ── Account (SCF chart of accounts) ───────────────────────────────
    op.create_table(
        "account",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(10), unique=True, nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("account_class", sa.Integer, nullable=False),
        sa.Column("detail", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Journal ───────────────────────────────────────────────────────
    op.create_table(
        "journal",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("journal_type", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
        sa.UniqueConstraint("company_id", "code", name="uq_journal_company_code"),
    )

    # ── Journal Entry ─────────────────────────────────────────────────
    op.create_table(
        "journal_entry",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("journal_id", UUID(as_uuid=True), sa.ForeignKey("journal.id"), nullable=False),
        sa.Column("entry_number", sa.String(30), nullable=False),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("rf_type", sa.String(5), nullable=False, server_default="RF1"),
        sa.Column("total_debit", sa.Numeric(15, 2), server_default="0"),
        sa.Column("total_credit", sa.Numeric(15, 2), server_default="0"),
        sa.Column("status", sa.String(20), server_default="DRAFT"),
        sa.Column("source_document_type", sa.String(50), nullable=True),
        sa.Column("source_document_id", sa.String(100), nullable=True),
        sa.Column("period", sa.String(7), nullable=True),
        sa.Column("created_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )
    op.create_index("ix_journal_entry_date", "journal_entry", ["entry_date"])
    op.create_index("ix_journal_entry_period", "journal_entry", ["period"])

    # ── Journal Entry Line ────────────────────────────────────────────
    op.create_table(
        "journal_entry_line",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("entry_id", UUID(as_uuid=True), sa.ForeignKey("journal_entry.id"), nullable=False),
        sa.Column("account_code", sa.String(10), nullable=False),
        sa.Column("label", sa.String(300), nullable=True),
        sa.Column("debit", sa.Numeric(15, 2), server_default="0"),
        sa.Column("credit", sa.Numeric(15, 2), server_default="0"),
        sa.Column("tiers_name", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )
    op.create_index("ix_jel_entry", "journal_entry_line", ["entry_id"])

    # ── Bank Statement ────────────────────────────────────────────────
    op.create_table(
        "bank_statement",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("bank_name", sa.String(100), nullable=False),
        sa.Column("account_number", sa.String(30), nullable=True),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("opening_balance", sa.Numeric(15, 2), server_default="0"),
        sa.Column("closing_balance", sa.Numeric(15, 2), server_default="0"),
        sa.Column("total_debit", sa.Numeric(15, 2), server_default="0"),
        sa.Column("total_credit", sa.Numeric(15, 2), server_default="0"),
        sa.Column("movements_count", sa.Integer, server_default="0"),
        sa.Column("matched_count", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(20), server_default="IMPORTED"),
        sa.Column("uploaded_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )

    # ── Bank Movement ─────────────────────────────────────────────────
    op.create_table(
        "bank_movement",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("statement_id", UUID(as_uuid=True), sa.ForeignKey("bank_statement.id"), nullable=False),
        sa.Column("movement_date", sa.Date, nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("debit", sa.Numeric(15, 2), server_default="0"),
        sa.Column("credit", sa.Numeric(15, 2), server_default="0"),
        sa.Column("balance_after", sa.Numeric(15, 2), nullable=True),
        sa.Column("reconciled", sa.Boolean, server_default="false"),
        sa.Column("matched_payment_id", sa.String(100), nullable=True),
        sa.Column("matched_entry_id", sa.String(100), nullable=True),
        sa.Column("match_confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("match_method", sa.String(20), nullable=True),
        sa.Column("reconciled_by", sa.String(200), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, server_default="false"),
    )
    op.create_index("ix_bank_movement_statement", "bank_movement", ["statement_id"])
    op.create_index("ix_bank_movement_date", "bank_movement", ["movement_date"])

    # Seed basic SCF accounts
    import uuid
    from sqlalchemy import text
    accounts = [
        ("401", "Fournisseurs", 4), ("411", "Clients", 4),
        ("512", "Banque", 5), ("530", "Caisse", 5),
        ("601", "Achats matieres premieres", 6), ("602", "Achats consommables", 6),
        ("604", "Achats etudes et prestations", 6), ("613", "Loyers", 6),
        ("631", "Charges de personnel", 6), ("635", "Charges sociales", 6),
        ("661", "Charges financieres", 6), ("681", "Dotations amortissements", 6),
        ("701", "Ventes marchandises", 7), ("704", "Ventes prestations", 7),
        ("706", "Ventes immobilieres", 7), ("761", "Produits financiers", 7),
    ]
    for code, label, cls in accounts:
        uid = str(uuid.uuid4())
        op.execute(text(
            f"INSERT INTO account (id, code, label, account_class, detail) "
            f"VALUES ('{uid}', '{code}', '{label}', {cls}, true) "
            f"ON CONFLICT (code) DO NOTHING"
        ))


def downgrade():
    op.drop_table("bank_movement")
    op.drop_table("bank_statement")
    op.drop_table("journal_entry_line")
    op.drop_table("journal_entry")
    op.drop_table("journal")
    op.drop_table("account")
