"""GAP 8 BIM/EDD schema rewrite — v2 pipeline

Revision ID: 005_bim_edd_v2
Revises: 004_gap_remediation
Create Date: 2025-06-15

Drop old BIM/EDD tables and recreate with v2 schema:
  - re_projects      (simplified: code/name/lat/lon/north_angle)
  - re_blocks        (project_id FK, max 8-char code)
  - re_levels        (block_id FK, code Lxx, elevation)
  - re_units         (10 area fields, exposure, pricing, edd_state)
  - re_unit_annexes  (B/T/J/P/C enum type)
  - re_pricing_rules (coefficient-based, code unique)
  - re_validations   (multi-stage: object_type+object_id)
  - re_docs          (replaces re_edd_documents, FK to documents)
  - bim_import_jobs  (IFC/RVT import tracking)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "005_bim_edd_v2"
down_revision: Union[str, None] = "004_gap_remediation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ═══════════════════════════════════════════════════════════════════════
    # Drop old BIM/EDD tables (order: children first)
    # ═══════════════════════════════════════════════════════════════════════
    op.drop_table("re_edd_documents")
    op.drop_table("re_validations")
    try:
        op.drop_index("ix_pricing_project_type", table_name="re_pricing_rules")
    except Exception:
        pass
    op.drop_table("re_pricing_rules")
    op.drop_table("re_unit_annexes")
    try:
        op.drop_index("ix_re_unit_statut", table_name="re_units")
    except Exception:
        pass
    op.drop_table("re_units")
    op.drop_table("re_levels")
    op.drop_table("re_blocks")
    op.drop_table("re_projects")

    # ═══════════════════════════════════════════════════════════════════════
    # Create v2 BIM/EDD tables
    # ═══════════════════════════════════════════════════════════════════════

    op.create_table(
        "re_projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("lat", sa.Numeric(10, 7), nullable=True),
        sa.Column("lon", sa.Numeric(10, 7), nullable=True),
        sa.Column("north_angle", sa.Numeric(8, 4), nullable=True),
        sa.Column("status", sa.String(20), server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "re_blocks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("re_projects.id"), nullable=False),
        sa.Column("code", sa.String(8), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "code", name="uq_re_block_project_code"),
    )

    op.create_table(
        "re_levels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("block_id", sa.String(36), sa.ForeignKey("re_blocks.id"), nullable=False),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("elevation", sa.Numeric(8, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("block_id", "code", name="uq_re_level_block_code"),
    )

    op.create_table(
        "re_units",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("level_id", sa.String(36), sa.ForeignKey("re_levels.id"), nullable=False),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("typology", sa.String(50), nullable=True),
        sa.Column("bedrooms", sa.Integer(), nullable=True),
        sa.Column("bathrooms", sa.Integer(), nullable=True),
        sa.Column("height_clear", sa.Numeric(5, 2), nullable=True),
        sa.Column("area_sh", sa.Numeric(10, 2), nullable=True),
        sa.Column("area_su", sa.Numeric(10, 2), nullable=True),
        sa.Column("area_sb", sa.Numeric(10, 2), nullable=True),
        sa.Column("area_st", sa.Numeric(10, 2), nullable=True),
        sa.Column("area_sj", sa.Numeric(10, 2), nullable=True),
        sa.Column("area_sp", sa.Numeric(10, 2), nullable=True),
        sa.Column("area_sc", sa.Numeric(10, 2), nullable=True),
        sa.Column("area_scom", sa.Numeric(10, 2), nullable=True),
        sa.Column("area_net_bim", sa.Numeric(10, 2), nullable=True),
        sa.Column("area_gross_bim", sa.Numeric(10, 2), nullable=True),
        sa.Column("exposure", sa.String(5), nullable=True),
        sa.Column("view_class", sa.String(20), nullable=True),
        sa.Column("price_base", sa.Numeric(15, 2), nullable=True),
        sa.Column("price_total", sa.Numeric(15, 2), nullable=True),
        sa.Column("edd_state", sa.String(20), server_default="DRAFT"),
        sa.Column("is_annex", sa.Boolean(), server_default="0"),
        sa.Column("annex_type", sa.String(5), nullable=True),
        sa.Column("usage_type", sa.String(50), nullable=True),
        sa.Column("ifc_space_id", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.CheckConstraint("bedrooms IS NULL OR bedrooms >= 0", name="ck_bedrooms_pos"),
        sa.CheckConstraint("bathrooms IS NULL OR bathrooms >= 0", name="ck_bathrooms_pos"),
    )
    op.create_index("idx_re_unit_code", "re_units", ["code"])
    op.create_index("idx_re_unit_level", "re_units", ["level_id"])
    op.create_index("idx_re_unit_edd_state", "re_units", ["edd_state"])

    op.create_table(
        "re_unit_annexes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("unit_id", sa.String(36), sa.ForeignKey("re_units.id"), nullable=False),
        sa.Column("type", sa.String(5), nullable=False),
        sa.Column("area", sa.Numeric(10, 2), nullable=False),
        sa.Column("ifc_space_id", sa.String(200), nullable=True),
        sa.Column("code_suffix", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "re_pricing_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("rule_type", sa.String(20), nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("value", sa.Numeric(8, 4), nullable=False),
        sa.Column("scope", sa.String(50), nullable=True),
        sa.Column("condition_field", sa.String(100), nullable=True),
        sa.Column("condition_value", sa.String(100), nullable=True),
        sa.Column("is_per_level", sa.Boolean(), server_default="0"),
        sa.Column("cap_value", sa.Numeric(8, 4), nullable=True),
        sa.Column("active_from", sa.Date(), nullable=True),
        sa.Column("active_to", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "re_validations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("object_type", sa.String(50), nullable=False),
        sa.Column("object_id", sa.String(36), nullable=False),
        sa.Column("stage", sa.String(30), nullable=False),
        sa.Column("validator_role", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("ts", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_re_validation_object", "re_validations", ["object_type", "object_id"])

    op.create_table(
        "re_docs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("unit_id", sa.String(36), sa.ForeignKey("re_units.id"), nullable=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("re_projects.id"), nullable=True),
        sa.Column("doc_type", sa.String(40), nullable=False),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column("is_obsolete", sa.Boolean(), server_default="0"),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "bim_import_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("re_projects.id"), nullable=True),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_format", sa.String(10), nullable=False),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("status", sa.String(20), server_default="PENDING"),
        sa.Column("ids_report", sa.JSON(), nullable=True),
        sa.Column("bcf_report", sa.JSON(), nullable=True),
        sa.Column("units_found", sa.Integer(), server_default="0"),
        sa.Column("units_valid", sa.Integer(), server_default="0"),
        sa.Column("units_rejected", sa.Integer(), server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_bim_import_project", "bim_import_jobs", ["project_id", "status"])


def downgrade() -> None:
    op.drop_index("idx_bim_import_project", table_name="bim_import_jobs")
    op.drop_table("bim_import_jobs")
    op.drop_table("re_docs")
    op.drop_index("idx_re_validation_object", table_name="re_validations")
    op.drop_table("re_validations")
    op.drop_table("re_pricing_rules")
    op.drop_table("re_unit_annexes")
    op.drop_index("idx_re_unit_edd_state", table_name="re_units")
    op.drop_index("idx_re_unit_level", table_name="re_units")
    op.drop_index("idx_re_unit_code", table_name="re_units")
    op.drop_table("re_units")
    op.drop_table("re_levels")
    op.drop_table("re_blocks")
    op.drop_table("re_projects")

    # Recreate old tables (v1 schema from 004)
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
