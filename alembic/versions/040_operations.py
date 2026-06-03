"""Operations management: 11-source budget aggregation, Gantt planning, S-curve.

Tables (6 new):
- operation: engagement with state machine + 25 RM rules
- operation_budget_agrege: per-source budget breakdown (11 sources)
- operation_planning_task: WBS tasks with critical path
- operation_dependency: task dependencies (FD/DD/FF/DF)
- operation_snapshot: baselines and periodic snapshots
- wbs_template: pre-configured WBS templates per category (5 seeded)

Materialized view: budget_complet_operation (refreshed hourly)

Revision ID: 040
Revises: 039
Create Date: 2026-03-19
"""
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_c = 0
def _uuid():
    global _c; _c += 1
    return f"f8000000-0000-0000-0000-{_c:012x}"

def _sys():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("auth_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
    ]

WBS_TEMPLATES = [
    ("GROS_OEUVRE", "Gros Oeuvre Standard", [
        {"code_wbs": "1", "intitule": "Installation chantier", "type_tache": "TACHE"},
        {"code_wbs": "2", "intitule": "Terrassement", "type_tache": "TACHE"},
        {"code_wbs": "3", "intitule": "Fondations", "type_tache": "TACHE"},
        {"code_wbs": "4", "intitule": "Infrastructure", "type_tache": "TACHE"},
        {"code_wbs": "5", "intitule": "Superstructure", "type_tache": "SUMMARY"},
        {"code_wbs": "6", "intitule": "Etancheite", "type_tache": "TACHE"},
        {"code_wbs": "7", "intitule": "Reception", "type_tache": "JALON_PLANNING"},
    ]),
    ("BET_ARCHITECTURE", "BET Architecture", [
        {"code_wbs": "1", "intitule": "Releve", "type_tache": "TACHE"},
        {"code_wbs": "2", "intitule": "APS", "type_tache": "LIVRABLE"},
        {"code_wbs": "3", "intitule": "APD", "type_tache": "LIVRABLE"},
        {"code_wbs": "4", "intitule": "Permis construire", "type_tache": "JALON_PLANNING"},
        {"code_wbs": "5", "intitule": "EXE", "type_tache": "LIVRABLE"},
        {"code_wbs": "6", "intitule": "Suivi chantier", "type_tache": "TACHE"},
    ]),
    ("MACHINE_OEM", "Machine OEM", [
        {"code_wbs": "1", "intitule": "Commande", "type_tache": "JALON_PLANNING"},
        {"code_wbs": "2", "intitule": "Fabrication FAT", "type_tache": "TACHE"},
        {"code_wbs": "3", "intitule": "Expedition + Dedouanement", "type_tache": "TACHE"},
        {"code_wbs": "4", "intitule": "Installation + SAT", "type_tache": "TACHE"},
        {"code_wbs": "5", "intitule": "Formation", "type_tache": "TACHE"},
        {"code_wbs": "6", "intitule": "Reception definitive", "type_tache": "JALON_PLANNING"},
    ]),
    ("SECOND_OEUVRE", "Second Oeuvre", [
        {"code_wbs": "1", "intitule": "Preparation", "type_tache": "TACHE"},
        {"code_wbs": "2", "intitule": "Approvisionnement", "type_tache": "TACHE"},
        {"code_wbs": "3", "intitule": "Execution", "type_tache": "SUMMARY"},
        {"code_wbs": "4", "intitule": "Finitions", "type_tache": "TACHE"},
        {"code_wbs": "5", "intitule": "Reception", "type_tache": "JALON_PLANNING"},
    ]),
    ("RH_CDI", "Recrutement CDI", [
        {"code_wbs": "1", "intitule": "Publication offre", "type_tache": "TACHE"},
        {"code_wbs": "2", "intitule": "Candidatures", "type_tache": "TACHE"},
        {"code_wbs": "3", "intitule": "Entretiens", "type_tache": "TACHE"},
        {"code_wbs": "4", "intitule": "Selection + Contrat", "type_tache": "TACHE"},
        {"code_wbs": "5", "intitule": "Integration", "type_tache": "TACHE"},
    ]),
]


def upgrade() -> None:
    # 1. wbs_template (before operation for template deployment)
    op.create_table("wbs_template",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("categorie", sa.String(30), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("tasks", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 2. operation
    op.create_table("operation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("code_operation", sa.String(30), unique=True, nullable=False, index=True),
        sa.Column("intitule", sa.String(300), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("project.id", ondelete="RESTRICT"), nullable=True, index=True),
        sa.Column("categorie", sa.String(30), nullable=False),
        sa.Column("tiers_id", UUID(as_uuid=True), nullable=True),
        sa.Column("contrat_legal_id", UUID(as_uuid=True), sa.ForeignKey("legal_contract.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("montant_engage_ht", sa.Numeric(15, 2), nullable=True),
        sa.Column("montant_engage_ttc", sa.Numeric(15, 2), nullable=True),
        sa.Column("montant_rf2", sa.Numeric(15, 2), nullable=True),
        sa.Column("devise", sa.String(3), nullable=False, server_default=sa.text("'DZD'")),
        sa.Column("statut", sa.String(20), nullable=False, server_default=sa.text("'BROUILLON'")),
        sa.Column("date_debut", sa.Date, nullable=True),
        sa.Column("date_fin_prevue", sa.Date, nullable=True),
        sa.Column("date_fin_reelle", sa.Date, nullable=True),
        sa.Column("responsable_id", UUID(as_uuid=True), sa.ForeignKey("auth_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("visa_tresorier", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("visa_tresorier_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_sys(),
    )

    # 3. operation_budget_agrege
    op.create_table("operation_budget_agrege",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("operation_id", UUID(as_uuid=True), sa.ForeignKey("operation.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("source_code", sa.String(20), nullable=False, index=True),
        sa.Column("source_label", sa.String(100), nullable=False),
        sa.Column("montant_prevu", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("montant_reel", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("methode_calcul", sa.String(20), nullable=False),
        sa.Column("cle_repartition", JSONB, nullable=True),
        sa.Column("derniere_maj", sa.DateTime(timezone=True), nullable=True),
        sa.Column("detail_lignes", JSONB, nullable=True),
        *_sys(),
    )

    # 4. operation_planning_task
    op.create_table("operation_planning_task",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("operation_id", UUID(as_uuid=True), sa.ForeignKey("operation.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("parent_task_id", UUID(as_uuid=True), sa.ForeignKey("operation_planning_task.id", ondelete="SET NULL"), nullable=True),
        sa.Column("jalon_id", UUID(as_uuid=True), nullable=True),
        sa.Column("code_wbs", sa.String(20), nullable=False),
        sa.Column("intitule", sa.String(300), nullable=False),
        sa.Column("type_tache", sa.String(20), nullable=False),
        sa.Column("date_debut_prevue", sa.Date, nullable=True),
        sa.Column("date_fin_prevue", sa.Date, nullable=True),
        sa.Column("date_debut_reelle", sa.Date, nullable=True),
        sa.Column("date_fin_reelle", sa.Date, nullable=True),
        sa.Column("avancement_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("avancement_methode", sa.String(20), nullable=True),
        sa.Column("budget_tache", sa.Numeric(15, 2), nullable=True),
        sa.Column("cout_reel_tache", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("est_critique", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("responsable_id", UUID(as_uuid=True), nullable=True),
        sa.Column("statut_tache", sa.String(20), nullable=False, server_default=sa.text("'A_FAIRE'")),
        sa.Column("notes", sa.Text, nullable=True),
        *_sys(),
    )

    # 5. operation_dependency
    op.create_table("operation_dependency",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("predecesseur_id", UUID(as_uuid=True), sa.ForeignKey("operation_planning_task.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("successeur_id", UUID(as_uuid=True), sa.ForeignKey("operation_planning_task.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("type_dependance", sa.String(2), nullable=False, server_default=sa.text("'FD'")),
        sa.Column("decalage_jours", sa.Integer, nullable=False, server_default=sa.text("0")),
        *_sys(),
    )

    # 6. operation_snapshot
    op.create_table("operation_snapshot",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("company.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("operation_id", UUID(as_uuid=True), sa.ForeignKey("operation.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("type_snapshot", sa.String(20), nullable=False),
        sa.Column("date_snapshot", sa.Date, nullable=False),
        sa.Column("donnees_taches", JSONB, nullable=False),
        sa.Column("commentaire", sa.Text, nullable=True),
        *_sys(),
    )

    # Materialized view
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS budget_complet_operation AS
        SELECT
            o.id AS operation_id,
            o.code_operation,
            o.intitule,
            o.montant_engage_ttc AS budget_contrat,
            COALESCE(SUM(b.montant_prevu), 0) AS budget_total_prevu,
            COALESCE(SUM(b.montant_reel), 0) AS budget_total_reel,
            COALESCE(SUM(b.montant_reel), 0) - COALESCE(SUM(b.montant_prevu), 0) AS ecart_absolu
        FROM operation o
        LEFT JOIN operation_budget_agrege b ON b.operation_id = o.id AND b.is_deleted = false
        WHERE o.is_deleted = false
        GROUP BY o.id, o.code_operation, o.intitule, o.montant_engage_ttc;
    """)

    # Triggers
    for t in ("operation", "operation_budget_agrege", "operation_planning_task",
              "operation_dependency", "operation_snapshot"):
        op.execute(f"""CREATE TRIGGER trg_{t}_updated_at BEFORE UPDATE ON {t}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();""")
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{t}');")

    # Seed WBS templates
    for cat, name, tasks in WBS_TEMPLATES:
        uid = _uuid()
        tasks_json = json.dumps(tasks).replace("'", "''")
        op.execute(f"""INSERT INTO wbs_template (id, categorie, name, tasks)
            VALUES ('{uid}', '{cat}', '{name}', '{tasks_json}'::jsonb);""")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS budget_complet_operation;")
    for t in ("operation_snapshot", "operation_dependency", "operation_planning_task",
              "operation_budget_agrege", "operation"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_updated_at ON {t};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_no_delete ON {t};")
    op.drop_table("operation_snapshot")
    op.drop_table("operation_dependency")
    op.drop_table("operation_planning_task")
    op.drop_table("operation_budget_agrege")
    op.drop_table("operation")
    op.drop_table("wbs_template")
