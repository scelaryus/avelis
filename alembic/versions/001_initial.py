"""Initial schema - all tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-03-05
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tenants
    op.create_table(
        'tenants',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('settings', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Users
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255)),
        sa.Column('role', sa.String(50), server_default='viewer'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Documents
    op.create_table(
        'documents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('mime_type', sa.String(100)),
        sa.Column('file_size', sa.Integer),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('storage_key', sa.String(500), nullable=False),
        sa.Column('doc_type', sa.String(50), server_default='OTHER'),
        sa.Column('doc_type_confidence', sa.Float, server_default='0'),
        sa.Column('page_count', sa.Integer, server_default='0'),
        sa.Column('has_text_layer', sa.Boolean, server_default='false'),
        sa.Column('text_layer_confidence', sa.Numeric(5, 4), server_default='0'),
        sa.Column('metadata', JSONB, server_default='{}'),
        sa.Column('uploaded_by', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_documents_sha256', 'documents', ['sha256'])
    op.create_index('ix_documents_tenant_sha256', 'documents', ['tenant_id', 'sha256'])

    # Workflows
    op.create_table(
        'workflows',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('actor_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.String(50), server_default='CREATED'),
        sa.Column('graph_type', sa.String(50), server_default='document_to_ledger'),
        sa.Column('doc_ids', JSONB, server_default='[]'),
        sa.Column('artifacts', JSONB, server_default='{}'),
        sa.Column('blocking_reasons', JSONB, server_default='[]'),
        sa.Column('errors', JSONB, server_default='[]'),
        sa.Column('warnings', JSONB, server_default='[]'),
        sa.Column('decisions', JSONB, server_default='[]'),
        sa.Column('current_node', sa.String(100)),
        sa.Column('node_history', JSONB, server_default='[]'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Artifacts
    op.create_table(
        'artifacts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('workflow_id', UUID(as_uuid=True), sa.ForeignKey('workflows.id')),
        sa.Column('doc_id', UUID(as_uuid=True), sa.ForeignKey('documents.id')),
        sa.Column('artifact_type', sa.String(50), nullable=False),
        sa.Column('data', JSONB, nullable=False),
        sa.Column('sha256', sa.String(64)),
        sa.Column('storage_key', sa.String(500)),
        sa.Column('algo_version', sa.String(50)),
        sa.Column('ruleset_version', sa.String(50)),
        sa.Column('model_version', sa.String(50)),
        sa.Column('inputs_hash', sa.String(64)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_artifacts_type_doc', 'artifacts', ['artifact_type', 'doc_id'])
    op.create_index('ix_artifacts_workflow', 'artifacts', ['workflow_id'])
    op.create_index('ix_artifacts_cache', 'artifacts', ['doc_id', 'artifact_type', 'inputs_hash'])

    # Accounting Periods
    op.create_table(
        'accounting_periods',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('start_date', sa.DateTime, nullable=False),
        sa.Column('end_date', sa.DateTime, nullable=False),
        sa.Column('is_closed', sa.Boolean, server_default='false'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Chart of Accounts
    op.create_table(
        'chart_of_accounts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('code', sa.String(20), nullable=False),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('account_type', sa.String(50)),
        sa.Column('parent_code', sa.String(20)),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_coa_tenant_code'),
    )

    # Journal Entries
    op.create_table(
        'journal_entries',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('workflow_id', UUID(as_uuid=True), sa.ForeignKey('workflows.id')),
        sa.Column('entry_date', sa.DateTime, nullable=False),
        sa.Column('reference', sa.String(100)),
        sa.Column('description', sa.Text),
        sa.Column('status', sa.String(50), server_default='PROPOSED'),
        sa.Column('period_id', UUID(as_uuid=True), sa.ForeignKey('accounting_periods.id')),
        sa.Column('source_doc_ids', JSONB, server_default='[]'),
        sa.Column('evidence_anchor_ids', JSONB, server_default='[]'),
        sa.Column('assumptions', JSONB, server_default='[]'),
        sa.Column('committed_by', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('committed_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Journal Lines
    op.create_table(
        'journal_lines',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('entry_id', UUID(as_uuid=True), sa.ForeignKey('journal_entries.id'), nullable=False),
        sa.Column('account_code', sa.String(20), nullable=False),
        sa.Column('label', sa.String(500)),
        sa.Column('debit', sa.Numeric(18, 2), server_default='0'),
        sa.Column('credit', sa.Numeric(18, 2), server_default='0'),
        sa.Column('currency', sa.String(3), server_default='MAD'),
        sa.Column('evidence_anchors', JSONB, server_default='[]'),
        sa.Column('cost_center_code', sa.String(50)),
        sa.Column('project_code', sa.String(50)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Evidence Anchors
    op.create_table(
        'evidence_anchors',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('doc_id', UUID(as_uuid=True), sa.ForeignKey('documents.id'), nullable=False),
        sa.Column('page', sa.Integer, nullable=False),
        sa.Column('bbox', JSONB),
        sa.Column('text_snippet', sa.Text),
        sa.Column('field_name', sa.String(100)),
        sa.Column('confidence', sa.Float),
        sa.Column('ocr_block_index', sa.Integer),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Anomaly Records
    op.create_table(
        'anomaly_records',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('workflow_id', UUID(as_uuid=True), sa.ForeignKey('workflows.id'), nullable=False),
        sa.Column('doc_id', UUID(as_uuid=True), sa.ForeignKey('documents.id')),
        sa.Column('anomaly_code', sa.String(100), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('details', JSONB, server_default='{}'),
        sa.Column('is_resolved', sa.Boolean, server_default='false'),
        sa.Column('resolution', JSONB),
        sa.Column('resolved_by', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('resolved_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Audit Log
    op.create_table(
        'audit_log',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(100)),
        sa.Column('entity_id', sa.String(100)),
        sa.Column('old_value', JSONB),
        sa.Column('new_value', JSONB),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_audit_log_entity', 'audit_log', ['entity_type', 'entity_id'])
    op.create_index('ix_audit_log_tenant_date', 'audit_log', ['tenant_id', 'created_at'])

    # Cost Centers
    op.create_table(
        'cost_centers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('parent_code', sa.String(50)),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_cc_tenant_code'),
    )

    # Cost Center Allocations
    op.create_table(
        'cost_center_allocations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('cost_center_code', sa.String(50), nullable=False),
        sa.Column('period_id', UUID(as_uuid=True), sa.ForeignKey('accounting_periods.id')),
        sa.Column('total_debit', sa.Numeric(18, 2), server_default='0'),
        sa.Column('total_credit', sa.Numeric(18, 2), server_default='0'),
        sa.Column('snapshot_data', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Employees
    op.create_table(
        'employees',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('employee_number', sa.String(50), nullable=False),
        sa.Column('first_name', sa.String(255), nullable=False),
        sa.Column('last_name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255)),
        sa.Column('phone', sa.String(50)),
        sa.Column('hire_date', sa.Date),
        sa.Column('termination_date', sa.Date),
        sa.Column('status', sa.String(20), server_default='ACTIVE'),
        sa.Column('department', sa.String(100)),
        sa.Column('position', sa.String(255)),
        sa.Column('cost_center_code', sa.String(50)),
        sa.Column('base_salary', sa.Numeric(18, 2)),
        sa.Column('currency', sa.String(3), server_default='MAD'),
        sa.Column('bank_account', sa.String(50)),
        sa.Column('tax_id', sa.String(50)),
        sa.Column('social_security_number', sa.String(50)),
        sa.Column('metadata', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Payroll Proposals
    op.create_table(
        'payroll_proposals',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('employee_id', UUID(as_uuid=True), sa.ForeignKey('employees.id'), nullable=False),
        sa.Column('period_id', UUID(as_uuid=True), sa.ForeignKey('accounting_periods.id')),
        sa.Column('period_label', sa.String(50)),
        sa.Column('status', sa.String(20), server_default='DRAFT'),
        sa.Column('gross_salary', sa.Numeric(18, 2)),
        sa.Column('deductions', JSONB, server_default='{}'),
        sa.Column('contributions', JSONB, server_default='{}'),
        sa.Column('net_salary', sa.Numeric(18, 2)),
        sa.Column('journal_entry_id', UUID(as_uuid=True), sa.ForeignKey('journal_entries.id')),
        sa.Column('notes', sa.Text),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('approved_by', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # HR Tasks
    op.create_table(
        'hr_tasks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('employee_id', UUID(as_uuid=True), sa.ForeignKey('employees.id')),
        sa.Column('task_type', sa.String(100), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('status', sa.String(50), server_default='pending'),
        sa.Column('assigned_to', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('due_date', sa.Date),
        sa.Column('completed_at', sa.DateTime),
        sa.Column('metadata', JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Clients (ADV)
    op.create_table(
        'clients',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('legal_name', sa.String(500)),
        sa.Column('tax_id', sa.String(50)),
        sa.Column('ice', sa.String(50)),
        sa.Column('address', sa.Text),
        sa.Column('city', sa.String(100)),
        sa.Column('country', sa.String(100), server_default='Morocco'),
        sa.Column('phone', sa.String(50)),
        sa.Column('email', sa.String(255)),
        sa.Column('payment_terms_days', sa.Integer, server_default='30'),
        sa.Column('credit_limit', sa.Numeric(18, 2)),
        sa.Column('account_code', sa.String(20)),
        sa.Column('metadata', JSONB, server_default='{}'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Contracts (ADV)
    op.create_table(
        'contracts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('client_id', UUID(as_uuid=True), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('contract_number', sa.String(100), nullable=False),
        sa.Column('title', sa.String(500)),
        sa.Column('status', sa.String(20), server_default='DRAFT'),
        sa.Column('start_date', sa.Date),
        sa.Column('end_date', sa.Date),
        sa.Column('total_amount', sa.Numeric(18, 2)),
        sa.Column('currency', sa.String(3), server_default='MAD'),
        sa.Column('terms', JSONB, server_default='{}'),
        sa.Column('doc_ids', JSONB, server_default='[]'),
        sa.Column('notes', sa.Text),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Receivables (ADV)
    op.create_table(
        'receivables',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('client_id', UUID(as_uuid=True), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('contract_id', UUID(as_uuid=True), sa.ForeignKey('contracts.id')),
        sa.Column('invoice_ref', sa.String(100)),
        sa.Column('amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('amount_paid', sa.Numeric(18, 2), server_default='0'),
        sa.Column('currency', sa.String(3), server_default='MAD'),
        sa.Column('due_date', sa.Date),
        sa.Column('status', sa.String(20), server_default='PENDING'),
        sa.Column('journal_entry_id', UUID(as_uuid=True), sa.ForeignKey('journal_entries.id')),
        sa.Column('doc_ids', JSONB, server_default='[]'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Payments (ADV)
    op.create_table(
        'payments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('client_id', UUID(as_uuid=True), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('receivable_id', UUID(as_uuid=True), sa.ForeignKey('receivables.id')),
        sa.Column('payment_ref', sa.String(100)),
        sa.Column('amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('currency', sa.String(3), server_default='MAD'),
        sa.Column('payment_date', sa.Date, nullable=False),
        sa.Column('payment_method', sa.String(50)),
        sa.Column('bank_ref', sa.String(100)),
        sa.Column('journal_entry_id', UUID(as_uuid=True), sa.ForeignKey('journal_entries.id')),
        sa.Column('doc_ids', JSONB, server_default='[]'),
        sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    tables = [
        'payments', 'receivables', 'contracts', 'clients',
        'hr_tasks', 'payroll_proposals', 'employees',
        'cost_center_allocations', 'cost_centers',
        'anomaly_records', 'evidence_anchors',
        'journal_lines', 'journal_entries',
        'chart_of_accounts', 'accounting_periods',
        'artifacts', 'workflows', 'documents',
        'audit_log', 'users', 'tenants',
    ]
    for t in tables:
        op.drop_table(t)
