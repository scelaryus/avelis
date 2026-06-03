"""Full legal module: litigation, compliance, 6 AI agents.

Tables (8 new):
- legal_case, legal_contract, legal_compliance_rule, legal_compliance_alert,
  legal_contract_clause, legal_contract_template, legal_case_cost_line, legal_ai_task

Seeds: 8 Algerian compliance rules + 6 contract templates + 5 juridique roles

Revision ID: 039
Revises: 038
Create Date: 2026-03-19
"""
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_counter = 0
def _uuid():
    global _counter; _counter += 1
    return f"f7000000-0000-0000-0000-{_counter:012x}"

def _sys():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("auth_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
    ]

COMPLIANCE_RULES = [
    ("ALG-CDD-24M", "CONTRACTUELLE", "Loi 90-11 Art.14", "CDD cumul > 24 mois", "CRITIQUE", "BLOCAGE", "employee_contract", "BATCH_DAILY"),
    ("ALG-PAY-90J", "PAIEMENT", "Code commerce Art.468", "Delai paiement fournisseur > 90j", "MAJEUR", "BLOCAGE", "purchase_order", "REALTIME"),
    ("ALG-CTR-REV", "CONTRACTUELLE", "Code civil Art.561", "Contrat service > 12 mois sans clause revision", "MAJEUR", "ALERTE", "legal_contract", "BATCH_WEEKLY"),
    ("ALG-NC-2ANS", "CONTRACTUELLE", "Loi 90-11 Art.8", "Clause non-concurrence > 2 ans", "MAJEUR", "ALERTE", "legal_contract", "BATCH_WEEKLY"),
    ("ALG-RC-FRNR", "REGLEMENTAIRE", "Code commerce Art.22", "Fournisseur sans registre de commerce", "CRITIQUE", "BLOCAGE", "supplier", "REALTIME"),
    ("ALG-LIC-EXP", "REGLEMENTAIRE", "", "Licence exploitation expiree", "CRITIQUE", "ALERTE", "legal_contract", "BATCH_DAILY"),
    ("ALG-INT-TAUX", "CONTRACTUELLE", "Code civil Art.453", "Taux interet penalite excessif", "MAJEUR", "ALERTE", "legal_contract", "BATCH_WEEKLY"),
    ("ALG-DEP-1M", "PAIEMENT", "Reglement interne", "Depense > 1M DA sans visa juridique", "MAJEUR", "BLOCAGE", "purchase_order", "REALTIME"),
]

TEMPLATES = [
    ("Contrat Fournisseur", "FOURNISSEUR"),
    ("Contrat Client", "CLIENT"),
    ("Contrat de Travail", "TRAVAIL"),
    ("Accord de Confidentialite", "CONFIDENTIALITE"),
    ("Contrat de Prestation", "PRESTATION"),
    ("Contrat de Partenariat", "PARTENARIAT"),
]

ROLES = [
    ("JURISTE", "Juriste", "Read/write assigned contracts and dossiers"),
    ("RESP_JURIDIQUE", "Responsable Juridique", "Validation + all non-confidential dossiers"),
    ("DIR_JURIDIQUE", "Directeur Juridique", "Full access including confidential"),
    ("LECTEUR_JURIDIQUE", "Lecteur Juridique", "Read-only configurable scope"),
    ("UTIL_PORTAIL", "Utilisateur Portail (Externe)", "External: shared dossiers only"),
]


def upgrade() -> None:
    # 1. legal_contract_template (before legal_contract for FK)
    op.create_table("legal_contract_template",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("contract_type", sa.String(30), nullable=False),
        sa.Column("template_body", sa.Text, nullable=True),
        sa.Column("default_clauses", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 2. legal_case
    op.create_table("legal_case",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("name", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("case_type", sa.String(30), nullable=False, index=True),
        sa.Column("stage", sa.String(40), nullable=False, server_default=sa.text("'OUVERT'")),
        sa.Column("priority", sa.String(20), nullable=False, server_default=sa.text("'NORMAL'")),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("date_open", sa.Date, nullable=False),
        sa.Column("date_close", sa.Date, nullable=True),
        sa.Column("date_deadline", sa.Date, nullable=True, index=True),
        sa.Column("partner_name", sa.String(255), nullable=True),
        sa.Column("partner_lawyer", sa.String(255), nullable=True),
        sa.Column("company_lawyer", sa.String(255), nullable=True),
        sa.Column("assigned_juriste_id", UUID(as_uuid=True), sa.ForeignKey("auth_user.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("manager_id", UUID(as_uuid=True), nullable=True),
        sa.Column("employee_id", UUID(as_uuid=True), sa.ForeignKey("employee.id", ondelete="SET NULL"), nullable=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("project.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("amount_claimed", sa.Numeric(15, 2), nullable=True),
        sa.Column("amount_recovered", sa.Numeric(15, 2), nullable=True),
        sa.Column("cost_total", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("result", sa.String(20), nullable=False, server_default=sa.text("'EN_COURS'")),
        sa.Column("is_confidential", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("ai_risk_score", sa.Float, nullable=True),
        sa.Column("ai_summary", sa.Text, nullable=True),
        sa.Column("ai_suggested_actions", JSONB, nullable=True),
        *_sys(),
    )

    # 3. legal_contract
    op.create_table("legal_contract",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("name", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("contract_type", sa.String(30), nullable=False, index=True),
        sa.Column("state", sa.String(20), nullable=False, server_default=sa.text("'BROUILLON'")),
        sa.Column("partner_name", sa.String(255), nullable=True),
        sa.Column("employee_id", UUID(as_uuid=True), sa.ForeignKey("employee.id", ondelete="SET NULL"), nullable=True),
        sa.Column("date_start", sa.Date, nullable=True),
        sa.Column("date_end", sa.Date, nullable=True, index=True),
        sa.Column("renewal_type", sa.String(20), nullable=True),
        sa.Column("renewal_notice_days", sa.Integer, nullable=True, server_default=sa.text("60")),
        sa.Column("amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("legal_contract_template.id", ondelete="SET NULL"), nullable=True),
        sa.Column("compliance_status", sa.String(20), nullable=False, server_default=sa.text("'NON_EVALUE'")),
        sa.Column("ai_extracted_clauses", JSONB, nullable=True),
        sa.Column("ai_risk_assessment", sa.Text, nullable=True),
        sa.Column("document_url", sa.Text, nullable=True),
        *_sys(),
    )

    # 4. legal_compliance_rule (system reference)
    op.create_table("legal_compliance_rule",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(20), unique=True, nullable=False),
        sa.Column("rule_type", sa.String(20), nullable=False),
        sa.Column("legal_reference", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("condition_domain", JSONB, nullable=True),
        sa.Column("condition_python", sa.Text, nullable=True),
        sa.Column("ai_prompt", sa.Text, nullable=True),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("action_type", sa.String(20), nullable=False),
        sa.Column("target_model", sa.String(50), nullable=True),
        sa.Column("evaluation_mode", sa.String(20), nullable=False, server_default=sa.text("'BATCH_DAILY'")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 5. legal_compliance_alert
    op.create_table("legal_compliance_alert",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("rule_id", UUID(as_uuid=True), sa.ForeignKey("legal_compliance_rule.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("rule_code", sa.String(20), nullable=False),
        sa.Column("target_table", sa.String(50), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default=sa.text("'OUVERTE'")),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("recommended_action", sa.Text, nullable=True),
        sa.Column("justification_doc_url", sa.Text, nullable=True),
        sa.Column("assigned_to", UUID(as_uuid=True), nullable=True),
        sa.Column("date_detected", sa.DateTime(timezone=True), nullable=False),
        sa.Column("date_resolved", sa.DateTime(timezone=True), nullable=True),
        *_sys(),
    )

    # 6. legal_contract_clause
    op.create_table("legal_contract_clause",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("legal_contract.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("clause_type", sa.String(30), nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("is_ai_extracted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("risk_level", sa.String(10), nullable=True),
        sa.Column("position_in_doc", sa.Integer, nullable=True),
        *_sys(),
    )

    # 7. legal_case_cost_line
    op.create_table("legal_case_cost_line",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("legal_case.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("cost_date", sa.Date, nullable=False),
        sa.Column("cost_type", sa.String(20), nullable=False),
        *_sys(),
    )

    # 8. legal_ai_task
    op.create_table("legal_ai_task",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("agent_type", sa.String(30), nullable=False, index=True),
        sa.Column("input_data", JSONB, nullable=False),
        sa.Column("output_data", JSONB, nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column("priority", sa.Integer, nullable=False, server_default=sa.text("5")),
        sa.Column("error_log", sa.Text, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("case_id", UUID(as_uuid=True), nullable=True),
        sa.Column("contract_id", UUID(as_uuid=True), nullable=True),
        *_sys(),
    )

    # Triggers
    for t in ("legal_case", "legal_contract", "legal_compliance_alert",
              "legal_contract_clause", "legal_case_cost_line", "legal_ai_task"):
        op.execute(f"""CREATE TRIGGER trg_{t}_updated_at BEFORE UPDATE ON {t}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();""")
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{t}');")

    # Seed compliance rules
    for code, rtype, ref, desc, sev, action, target, mode in COMPLIANCE_RULES:
        uid = _uuid()
        desc_esc = desc.replace("'", "''")
        ref_esc = ref.replace("'", "''") if ref else ""
        op.execute(f"""INSERT INTO legal_compliance_rule
            (id, code, rule_type, legal_reference, description, severity, action_type, target_model, evaluation_mode)
            VALUES ('{uid}', '{code}', '{rtype}', '{ref_esc}', '{desc_esc}', '{sev}', '{action}', '{target}', '{mode}');""")

    # Seed templates
    for name, ctype in TEMPLATES:
        uid = _uuid()
        op.execute(f"""INSERT INTO legal_contract_template (id, name, contract_type)
            VALUES ('{uid}', '{name}', '{ctype}');""")

    # Seed 5 new juridique roles
    for code, name, desc in ROLES:
        uid = _uuid()
        desc_esc = desc.replace("'", "''")
        op.execute(f"""INSERT INTO role (id, code, name, description, module_scope)
            VALUES ('{uid}', '{code}', '{name}', '{desc_esc}', 'JURIDIQUE');""")


def downgrade() -> None:
    for t in ("legal_ai_task", "legal_case_cost_line", "legal_contract_clause",
              "legal_compliance_alert", "legal_contract", "legal_case"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_updated_at ON {t};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_no_delete ON {t};")
    op.drop_table("legal_ai_task")
    op.drop_table("legal_case_cost_line")
    op.drop_table("legal_contract_clause")
    op.drop_table("legal_compliance_alert")
    op.drop_table("legal_contract")
    op.drop_table("legal_case")
    op.drop_table("legal_compliance_rule")
    op.drop_table("legal_contract_template")
    for code, _, _ in ROLES:
        op.execute(f"DELETE FROM role WHERE code = '{code}';")
