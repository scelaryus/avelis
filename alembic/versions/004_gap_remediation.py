"""GAP remediation — finance_associes, bim_edd, MFA columns

Revision ID: 004_gap_remediation
Revises: 003_blueprint_v6
Create Date: 2025-06-01

New tables:
  Finance:  comptes_courants_associes, mouvements_comptes_courants,
            clotures_mensuelles, appels_de_fonds, cessions_parts,
            associate_aliases
  BIM/EDD:  re_projects, re_blocks, re_levels, re_units, re_unit_annexes,
            re_pricing_rules, re_validations, re_edd_documents

Modified tables:
  users:    +mfa_secret, +mfa_enabled
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004_gap_remediation"
down_revision: Union[str, None] = "003_blueprint_v6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ═══════════════════════════════════════════════════════════════════════
    # MFA columns on users
    # ═══════════════════════════════════════════════════════════════════════
    op.add_column("users", sa.Column("mfa_secret", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), server_default="0", nullable=True))

    # ═══════════════════════════════════════════════════════════════════════
    # FINANCE ASSOCIÉS TABLES
    # ═══════════════════════════════════════════════════════════════════════

    op.create_table(
        "comptes_courants_associes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("associe_id", sa.String(36), sa.ForeignKey("associes.id"), nullable=False),
        sa.Column("solde_global", sa.Numeric(18, 2), server_default="0"),
        sa.Column("solde_disponible_retrait", sa.Numeric(18, 2), server_default="0"),
        sa.Column("est_gele", sa.Boolean(), server_default="0"),
        sa.Column("date_gel", sa.DateTime(), nullable=True),
        sa.Column("motif_gel", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "associe_id", name="uq_cca_tenant_associe"),
    )

    op.create_table(
        "mouvements_comptes_courants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("compte_id", sa.String(36), sa.ForeignKey("comptes_courants_associes.id"), nullable=False),
        sa.Column("type_mouvement", sa.String(50), nullable=False),
        sa.Column("sens", sa.String(10), nullable=False),
        sa.Column("montant", sa.Numeric(18, 2), nullable=False),
        sa.Column("date_mouvement", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("reference", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cloture_id", sa.String(36), nullable=True),
        sa.Column("appel_fonds_id", sa.String(36), nullable=True),
        sa.Column("cession_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_mvt_compte", "mouvements_comptes_courants", ["compte_id", "date_mouvement"])

    op.create_table(
        "clotures_mensuelles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False),
        sa.Column("mois", sa.Integer(), nullable=False),
        sa.Column("annee", sa.Integer(), nullable=False),
        sa.Column("tnm_extracted", sa.Numeric(18, 2)),
        sa.Column("tnm_verification", sa.Numeric(18, 2)),
        sa.Column("double_computation_ok", sa.Boolean(), server_default="0"),
        sa.Column("montant_a_liberer", sa.Numeric(18, 2)),
        sa.Column("detail_distribution", sa.JSON(), nullable=True),
        sa.Column("hash_sha256", sa.String(64)),
        sa.Column("statut", sa.String(30), server_default="EN_ATTENTE"),
        sa.Column("erreur", sa.Text(), nullable=True),
        sa.Column("est_test_fictif", sa.Boolean(), server_default="0"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("projet_id", "mois", "annee", name="uq_cloture_projet_mois"),
    )

    op.create_table(
        "appels_de_fonds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False),
        sa.Column("associe_id", sa.String(36), sa.ForeignKey("associes.id"), nullable=False),
        sa.Column("montant_appel", sa.Numeric(18, 2), nullable=False),
        sa.Column("montant_verse", sa.Numeric(18, 2), server_default="0"),
        sa.Column("date_appel", sa.Date(), nullable=False),
        sa.Column("date_echeance", sa.Date(), nullable=True),
        sa.Column("statut", sa.String(30), server_default="EMIS"),
        sa.Column("reference", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "cessions_parts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False),
        sa.Column("vendeur_id", sa.String(36), sa.ForeignKey("associes.id"), nullable=False),
        sa.Column("acheteur_id", sa.String(36), sa.ForeignKey("associes.id"), nullable=False),
        sa.Column("pourcentage_cede", sa.Numeric(8, 2), nullable=False),
        sa.Column("prix_cession", sa.Numeric(18, 2)),
        sa.Column("date_cession", sa.Date(), nullable=False),
        sa.Column("statut", sa.String(30), server_default="BROUILLON"),
        sa.Column("reference_acte", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "associate_aliases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("associe_id", sa.String(36), sa.ForeignKey("associes.id"), nullable=False),
        sa.Column("alias", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "alias", name="uq_alias_unique"),
    )
    op.create_index("ix_alias_lookup", "associate_aliases", ["alias"])

    # ═══════════════════════════════════════════════════════════════════════
    # BIM / EDD TABLES
    # ═══════════════════════════════════════════════════════════════════════

    op.create_table(
        "re_projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False, unique=True),
        sa.Column("nom_programme", sa.String(200), nullable=False),
        sa.Column("adresse", sa.Text(), nullable=True),
        sa.Column("ville", sa.String(100), nullable=True),
        sa.Column("wilaya", sa.String(100), nullable=True),
        sa.Column("nombre_blocs", sa.Integer(), server_default="0"),
        sa.Column("nombre_unites_total", sa.Integer(), server_default="0"),
        sa.Column("surface_terrain", sa.Numeric(12, 2), nullable=True),
        sa.Column("surface_plancher", sa.Numeric(12, 2), nullable=True),
        sa.Column("permis_construire", sa.String(100), nullable=True),
        sa.Column("date_permis", sa.Date(), nullable=True),
        sa.Column("edd_statut", sa.String(20), server_default="DRAFT"),
        sa.Column("edd_frozen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "re_blocks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("re_project_id", sa.String(36), sa.ForeignKey("re_projects.id"), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("nom", sa.String(100), nullable=True),
        sa.Column("nombre_niveaux", sa.Integer(), server_default="0"),
        sa.Column("nombre_unites", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("re_project_id", "code", name="uq_re_block_code"),
    )

    op.create_table(
        "re_levels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("block_id", sa.String(36), sa.ForeignKey("re_blocks.id"), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("label", sa.String(50), nullable=True),
        sa.Column("ordre", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("block_id", "code", name="uq_re_level_code"),
    )

    op.create_table(
        "re_units",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("level_id", sa.String(36), sa.ForeignKey("re_levels.id"), nullable=False),
        sa.Column("re_project_id", sa.String(36), sa.ForeignKey("re_projects.id"), nullable=False),
        sa.Column("numero", sa.String(20), nullable=False),
        sa.Column("type_bien", sa.String(30), nullable=False),
        sa.Column("surface_habitable", sa.Numeric(10, 2), nullable=False),
        sa.Column("surface_utile", sa.Numeric(10, 2), nullable=True),
        sa.Column("surface_terrasse", sa.Numeric(10, 2), server_default="0"),
        sa.Column("surface_balcon", sa.Numeric(10, 2), server_default="0"),
        sa.Column("surface_cave", sa.Numeric(10, 2), server_default="0"),
        sa.Column("prix_total", sa.Numeric(18, 2), nullable=True),
        sa.Column("prix_m2", sa.Numeric(12, 2), nullable=True),
        sa.Column("statut", sa.String(20), server_default="DISPONIBLE"),
        sa.Column("client_id", sa.String(36), nullable=True),
        sa.Column("orientation", sa.String(20), nullable=True),
        sa.Column("vue", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("re_project_id", "numero", name="uq_re_unit_numero"),
        sa.CheckConstraint("surface_habitable > 0", name="ck_unit_surface_pos"),
    )
    op.create_index("ix_re_unit_statut", "re_units", ["re_project_id", "statut"])

    op.create_table(
        "re_unit_annexes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("unit_id", sa.String(36), sa.ForeignKey("re_units.id"), nullable=False),
        sa.Column("type_annexe", sa.String(20), nullable=False),
        sa.Column("surface", sa.Numeric(10, 2), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "re_pricing_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("re_project_id", sa.String(36), sa.ForeignKey("re_projects.id"), nullable=False),
        sa.Column("type_bien", sa.String(30), nullable=False),
        sa.Column("pricing_mode", sa.String(20), server_default="AU_M2"),
        sa.Column("prix_m2", sa.Numeric(12, 2), nullable=True),
        sa.Column("prix_forfaitaire", sa.Numeric(18, 2), nullable=True),
        sa.Column("etage_min", sa.Integer(), server_default="0"),
        sa.Column("etage_max", sa.Integer(), server_default="99"),
        sa.Column("majoration_etage_pct", sa.Numeric(5, 2), server_default="0"),
        sa.Column("majoration_vue_pct", sa.Numeric(5, 2), server_default="0"),
        sa.Column("actif", sa.Boolean(), server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_pricing_project_type", "re_pricing_rules", ["re_project_id", "type_bien"])

    op.create_table(
        "re_validations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("re_project_id", sa.String(36), sa.ForeignKey("re_projects.id"), nullable=False),
        sa.Column("statut", sa.String(20), nullable=False),
        sa.Column("rapport", sa.JSON(), nullable=False),
        sa.Column("nb_errors", sa.Integer(), server_default="0"),
        sa.Column("nb_warnings", sa.Integer(), server_default="0"),
        sa.Column("nb_ok", sa.Integer(), server_default="0"),
        sa.Column("validated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "re_edd_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("re_project_id", sa.String(36), sa.ForeignKey("re_projects.id"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("statut", sa.String(20), server_default="DRAFT"),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("document_url", sa.String(500), nullable=True),
        sa.Column("generated_by", sa.String(36), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("frozen_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("re_project_id", "version", name="uq_edd_doc_version"),
    )


def downgrade() -> None:
    # BIM/EDD
    op.drop_table("re_edd_documents")
    op.drop_table("re_validations")
    op.drop_index("ix_pricing_project_type", table_name="re_pricing_rules")
    op.drop_table("re_pricing_rules")
    op.drop_table("re_unit_annexes")
    op.drop_index("ix_re_unit_statut", table_name="re_units")
    op.drop_table("re_units")
    op.drop_table("re_levels")
    op.drop_table("re_blocks")
    op.drop_table("re_projects")

    # Finance Associés
    op.drop_index("ix_alias_lookup", table_name="associate_aliases")
    op.drop_table("associate_aliases")
    op.drop_table("cessions_parts")
    op.drop_table("appels_de_fonds")
    op.drop_table("clotures_mensuelles")
    op.drop_index("ix_mvt_compte", table_name="mouvements_comptes_courants")
    op.drop_table("mouvements_comptes_courants")
    op.drop_table("comptes_courants_associes")

    # MFA columns
    op.drop_column("users", "mfa_enabled")
    op.drop_column("users", "mfa_secret")
