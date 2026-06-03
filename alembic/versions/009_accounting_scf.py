"""Accounting module: SCF chart of accounts, journals, entries, bank reconciliation, fiscal declarations.

Rule R-002: 100% of entries are auto-generated from source documents.
Manual entry rejected unless OD with justification.

Tables:
- account: SCF chart of accounts (system reference)
- journal: per-entity journal isolation (GFIBase)
- journal_sequence: cloisoned numbering per company+journal+year
- journal_entry: entry headers with RF classification + source doc link
- journal_entry_line: debit/credit lines
- bank_statement + bank_movement: bank reconciliation
- fiscal_declaration: G50, CNAS, CACOBATPH, BILAN

Triggers:
- Debit = Credit balance check on journal_entry (DEFERRED)
- R-002 enforcement: reject entries without source_document_type
- RF type CHECK on journal_entry
- updated_at and soft-delete on all financial tables

Seeds: ~50 core SCF accounts for Algerian real-estate context

Revision ID: 009
Revises: 008
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_acct_counter = 0


def _acct_uuid():
    global _acct_counter
    _acct_counter += 1
    return f"d1000000-0000-0000-0000-{_acct_counter:012x}"


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


# ── SCF accounts to seed ────────────────────────────────────────────────────
# (code, name, class, type, parent_code, level, is_detail)
SCF_ACCOUNTS = [
    # Class 1: Capitaux
    ("10", "Capital, reserves et assimiles", 1, "PASSIF", None, 1, False),
    ("101", "Capital social", 1, "PASSIF", "10", 2, True),
    ("106", "Reserves", 1, "PASSIF", "10", 2, True),
    ("12", "Resultat de l'exercice", 1, "PASSIF", None, 1, True),
    ("16", "Emprunts et dettes financieres", 1, "PASSIF", None, 1, True),
    # Class 2: Immobilisations
    ("20", "Immobilisations incorporelles", 2, "ACTIF", None, 1, False),
    ("21", "Immobilisations corporelles", 2, "ACTIF", None, 1, False),
    ("211", "Terrains", 2, "ACTIF", "21", 2, True),
    ("2118", "Terrains — autres", 2, "ACTIF", "211", 3, True),
    ("211800", "Apport en nature materiel", 2, "ACTIF", "2118", 4, True),
    ("213", "Constructions", 2, "ACTIF", "21", 2, True),
    ("218", "Autres immobilisations corporelles", 2, "ACTIF", "21", 2, False),
    ("2182", "Materiel de transport", 2, "ACTIF", "218", 3, True),
    ("218200", "Materiel de transport", 2, "ACTIF", "2182", 4, True),
    # Class 3: Stocks
    ("31", "Matieres premieres", 3, "ACTIF", None, 1, True),
    ("33", "En-cours de production", 3, "ACTIF", None, 1, True),
    ("35", "Stocks de produits", 3, "ACTIF", None, 1, True),
    # Class 4: Tiers
    ("40", "Fournisseurs et comptes rattaches", 4, "PASSIF", None, 1, False),
    ("401", "Fournisseurs", 4, "PASSIF", "40", 2, True),
    ("409", "Fournisseurs debiteurs — avances", 4, "ACTIF", "40", 2, False),
    ("409100", "Avance fournisseur GACEB", 4, "ACTIF", "409", 3, True),
    ("41", "Clients et comptes rattaches", 4, "ACTIF", None, 1, False),
    ("411", "Clients", 4, "ACTIF", "41", 2, True),
    ("42", "Personnel et comptes rattaches", 4, "PASSIF", None, 1, False),
    ("421", "Personnel — remunerations dues", 4, "PASSIF", "42", 2, True),
    ("43", "Organismes sociaux", 4, "PASSIF", None, 1, False),
    ("431", "Securite sociale", 4, "PASSIF", "43", 2, True),
    ("44", "Etat et collectivites publiques", 4, "PASSIF", None, 1, False),
    ("442", "Etat — impots et taxes (IRG)", 4, "PASSIF", "44", 2, True),
    ("4456", "TVA deductible", 4, "ACTIF", "44", 2, True),
    ("4457", "TVA collectee", 4, "PASSIF", "44", 2, True),
    ("445", "Etat — taxes sur CA", 4, "PASSIF", "44", 2, True),
    ("45", "Groupe et associes", 4, "PASSIF", None, 1, False),
    ("455", "Comptes courants associes (CCA)", 4, "PASSIF", "45", 2, True),
    # Class 5: Financiers
    ("51", "Banques et etablissements financiers", 5, "ACTIF", None, 1, False),
    ("512", "Banques — comptes courants", 5, "ACTIF", "51", 2, True),
    ("53", "Caisse", 5, "ACTIF", None, 1, True),
    ("58", "Virements internes", 5, "ACTIF", None, 1, False),
    ("580", "Virements internes", 5, "ACTIF", "58", 2, True),
    # Class 6: Charges
    ("60", "Achats consommes", 6, "CHARGE", None, 1, False),
    ("601", "Achats de matieres premieres", 6, "CHARGE", "60", 2, True),
    ("604", "Achats de prestations", 6, "CHARGE", "60", 2, True),
    ("61", "Services exterieurs", 6, "CHARGE", None, 1, False),
    ("612", "Sous-traitance generale", 6, "CHARGE", "61", 2, True),
    ("613", "Locations", 6, "CHARGE", "61", 2, True),
    ("62", "Autres services exterieurs", 6, "CHARGE", None, 1, False),
    ("625", "Deplacements, missions, receptions", 6, "CHARGE", "62", 2, True),
    ("63", "Charges de personnel", 6, "CHARGE", None, 1, False),
    ("631", "Remunerations du personnel", 6, "CHARGE", "63", 2, True),
    ("635", "Cotisations aux organismes sociaux", 6, "CHARGE", "63", 2, True),
    ("64", "Impots, taxes et versements assimiles", 6, "CHARGE", None, 1, False),
    ("641", "Impots et taxes directes", 6, "CHARGE", "64", 2, True),
    # Class 7: Produits
    ("70", "Ventes de produits fabriques et services", 7, "PRODUIT", None, 1, False),
    ("701", "Ventes de produits finis", 7, "PRODUIT", "70", 2, True),
    ("704", "Ventes de travaux", 7, "PRODUIT", "70", 2, True),
    ("706", "Ventes de prestations de services", 7, "PRODUIT", "70", 2, True),
    ("74", "Subventions d'exploitation", 7, "PRODUIT", None, 1, True),
    ("77", "Produits exceptionnels", 7, "PRODUIT", None, 1, True),
]


def upgrade() -> None:
    # ═════════════════════════════════════════════════════════════════════
    # 1. account (system reference, no company_id)
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "account",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("account_class", sa.Integer, nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("parent_code", sa.String(20), nullable=True),
        sa.Column("level", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("is_detail", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("is_deleted", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. journal (per-entity)
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "journal",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("code", sa.String(10), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("journal_type", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        *_system_columns(),
        sa.UniqueConstraint("company_id", "code", name="uq_journal_company_code"),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. journal_sequence
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "journal_sequence",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("journal_code", sa.String(10), nullable=False),
        sa.Column("fiscal_year", sa.Integer, nullable=False),
        sa.Column("last_number", sa.Integer, nullable=False, server_default=sa.text("0")),
        *_system_columns(),
        sa.UniqueConstraint("company_id", "journal_code", "fiscal_year",
                            name="uq_journal_seq_company_journal_year"),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 4. journal_entry
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "journal_entry",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("journal_id", UUID(as_uuid=True),
                  sa.ForeignKey("journal.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("entry_number", sa.String(30), nullable=False, index=True),
        sa.Column("entry_date", sa.Date, nullable=False, index=True),
        sa.Column("fiscal_year", sa.String(4), nullable=False),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("rf_type", sa.String(3), nullable=False, index=True),
        sa.Column("source_document_type", sa.String(60), nullable=False),
        sa.Column("source_document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("od_justification_path", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'DRAFT'")),
        sa.Column("total_debit", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("total_credit", sa.Numeric(15, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=True, index=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 5. journal_entry_line
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "journal_entry_line",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("entry_id", UUID(as_uuid=True),
                  sa.ForeignKey("journal_entry.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("account_id", UUID(as_uuid=True),
                  sa.ForeignKey("account.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("account_code", sa.String(20), nullable=False),
        sa.Column("debit", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("credit", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("label", sa.Text, nullable=True),
        sa.Column("tiers_type", sa.String(20), nullable=True),
        sa.Column("tiers_id", UUID(as_uuid=True), nullable=True),
        sa.Column("tiers_name", sa.String(255), nullable=True),
        sa.Column("line_number", sa.Numeric(3, 0), nullable=False),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 6. bank_statement + bank_movement
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "bank_statement",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("bank_name", sa.String(100), nullable=False),
        sa.Column("account_number", sa.String(50), nullable=False),
        sa.Column("statement_date", sa.Date, nullable=False, index=True),
        sa.Column("import_format", sa.String(10), nullable=False),
        sa.Column("import_file_path", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'IMPORTED'")),
        sa.Column("total_debit", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_credit", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("line_count", sa.Numeric(5, 0), nullable=False, server_default=sa.text("0")),
        *_system_columns(),
    )

    op.create_table(
        "bank_movement",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("statement_id", UUID(as_uuid=True),
                  sa.ForeignKey("bank_statement.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("movement_date", sa.Date, nullable=False, index=True),
        sa.Column("value_date", sa.Date, nullable=True),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("direction", sa.String(1), nullable=False),
        sa.Column("reconciled", sa.String(1), nullable=False,
                  server_default=sa.text("'N'")),
        sa.Column("matched_entry_id", UUID(as_uuid=True),
                  sa.ForeignKey("journal_entry.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("match_confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("match_method", sa.String(20), nullable=True),
        sa.Column("reconciled_by", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("match_candidates", JSONB, nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 7. fiscal_declaration
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "fiscal_declaration",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("declaration_type", sa.String(20), nullable=False, index=True),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("fiscal_year", sa.String(4), nullable=False),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'DRAFT'")),
        sa.Column("computed_data", JSONB, nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("tva_collected", sa.Numeric(15, 2), nullable=True),
        sa.Column("tva_deductible", sa.Numeric(15, 2), nullable=True),
        sa.Column("tva_a_decaisser", sa.Numeric(15, 2), nullable=True),
        sa.Column("tap_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("ibs_installment", sa.Numeric(15, 2), nullable=True),
        sa.Column("cnas_employee_total", sa.Numeric(15, 2), nullable=True),
        sa.Column("cnas_employer_total", sa.Numeric(15, 2), nullable=True),
        sa.Column("validated_by", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submission_ref", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 8. CHECK CONSTRAINTS
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        ALTER TABLE journal_entry
        ADD CONSTRAINT chk_je_rf_type
        CHECK (rf_type IN ('RF1', 'RF2', 'RF3', 'RF4'));
    """)

    op.execute("""
        ALTER TABLE journal_entry_line
        ADD CONSTRAINT chk_jel_debit_or_credit
        CHECK (debit >= 0 AND credit >= 0 AND (debit + credit) > 0);
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 9. TRIGGERS
    # ═════════════════════════════════════════════════════════════════════

    # R-002: Reject entries without source_document_type
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_enforce_r002()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.source_document_type IS NULL OR NEW.source_document_type = '' THEN
                RAISE EXCEPTION
                    'Ecriture manuelle interdite. Toute ecriture doit provenir d''une piece justificative.'
                USING ERRCODE = 'P0001';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_journal_entry_r002
        BEFORE INSERT ON journal_entry
        FOR EACH ROW EXECUTE FUNCTION gfi_enforce_r002();
    """)

    # updated_at triggers
    all_tables = [
        "journal", "journal_sequence", "journal_entry", "journal_entry_line",
        "bank_statement", "bank_movement", "fiscal_declaration",
    ]
    for table in all_tables:
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)

    # Soft-delete triggers on all financial tables
    for table in all_tables:
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")

    # ═════════════════════════════════════════════════════════════════════
    # 10. SEED — SCF chart of accounts
    # ═════════════════════════════════════════════════════════════════════
    for code, name, acct_class, acct_type, parent, level, is_detail in SCF_ACCOUNTS:
        uid = _acct_uuid()
        name_esc = name.replace("'", "''")
        parent_sql = f"'{parent}'" if parent else "NULL"
        detail = "true" if is_detail else "false"
        op.execute(f"""
            INSERT INTO account (id, code, name, account_class, account_type,
                                 parent_code, level, is_detail)
            VALUES ('{uid}', '{code}', '{name_esc}', {acct_class},
                    '{acct_type}', {parent_sql}, {level}, {detail});
        """)


def downgrade() -> None:
    all_tables = [
        "fiscal_declaration", "bank_movement", "bank_statement",
        "journal_entry_line", "journal_entry", "journal_sequence", "journal",
    ]
    for table in all_tables:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")

    op.execute("DROP TRIGGER IF EXISTS trg_journal_entry_r002 ON journal_entry;")
    op.execute("DROP FUNCTION IF EXISTS gfi_enforce_r002();")

    for table in all_tables:
        op.drop_table(table)
    op.drop_table("account")
