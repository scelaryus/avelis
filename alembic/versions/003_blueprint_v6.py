"""Blueprint v6.0 — 27 new tables (treasury, registry, workflow, IA)

Revision ID: 003_blueprint_v6
Revises: 002_company_workflow
Create Date: 2026-03-09

New tables added:
  Treasury:  journaux, comptes_bancaires, bulletins_paie, declarations_fiscales,
             echeancier_clients, capital_associes, retraits_associes,
             consolidation_associes, consolidation_entreprises
  Registry:  notaires, banques_partenaires, projet_notaires, projet_banques,
             parts_projets, mutations_foncieres, lots_immobiliers,
             projet_entreprise_historique, dossiers_fictifs_reference
  Core:      import_sessions, versions_documents, archivage_physique,
             document_segments, ia_extraction_log, verifications_hash,
             workflow_dossiers, workflow_phases_log, demandes_completion
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003_blueprint_v6"
down_revision: Union[str, None] = "002_company_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ═══════════════════════════════════════════════════════════════════════
    # TREASURY TABLES
    # ═══════════════════════════════════════════════════════════════════════

    # ── journaux ──
    op.create_table(
        "journaux",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("entreprise_id", sa.String(36), sa.ForeignKey("entreprises.id"), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("libelle", sa.String(200), nullable=False),
        sa.Column("type_journal", sa.String(20), default="OD"),
        sa.Column("actif", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("entreprise_id", "code", name="uq_journal_ent_code"),
    )

    # ── comptes_bancaires ──
    op.create_table(
        "comptes_bancaires",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("entreprise_id", sa.String(36), sa.ForeignKey("entreprises.id"), nullable=False),
        sa.Column("banque", sa.String(100), nullable=False),
        sa.Column("agence", sa.String(200)),
        sa.Column("numero_compte", sa.String(50)),
        sa.Column("iban", sa.String(50)),
        sa.Column("rib", sa.String(30)),
        sa.Column("devise", sa.String(3), server_default="DZD"),
        sa.Column("solde_actuel", sa.Numeric(18, 2), server_default="0"),
        sa.Column("actif", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── bulletins_paie ──
    op.create_table(
        "bulletins_paie",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("employe_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("entreprise_id", sa.String(36), sa.ForeignKey("entreprises.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=True),
        sa.Column("mois", sa.Integer, nullable=False),
        sa.Column("annee", sa.Integer, nullable=False),
        sa.Column("salaire_base", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("heures_sup", sa.Numeric(18, 2), server_default="0"),
        sa.Column("prime_rendement", sa.Numeric(18, 2), server_default="0"),
        sa.Column("indemnites", sa.Numeric(18, 2), server_default="0"),
        sa.Column("salaire_brut", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("cnas_salarie", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("irg", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("autres_retenues", sa.Numeric(18, 2), server_default="0"),
        sa.Column("total_retenues", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("salaire_net", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("cnas_patronal", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("cacobatph", sa.Numeric(18, 2), server_default="0"),
        sa.Column("cout_employeur_rd", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("complement_nd", sa.Numeric(18, 2), server_default="0"),
        sa.Column("salaire_reel_total", sa.Numeric(18, 2), server_default="0"),
        sa.Column("reference_fiche_caisse", sa.String(100)),
        sa.Column("statut", sa.String(20), server_default="BROUILLON"),
        sa.Column("est_test_fictif", sa.Boolean, server_default="false"),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("employe_id", "annee", "mois", name="uq_bulletin_emp_mois"),
        sa.CheckConstraint("mois >= 1 AND mois <= 12", name="ck_bulletin_mois"),
    )

    # ── declarations_fiscales ──
    op.create_table(
        "declarations_fiscales",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("entreprise_id", sa.String(36), sa.ForeignKey("entreprises.id"), nullable=False),
        sa.Column("exercice_id", sa.String(36), sa.ForeignKey("exercices.id"), nullable=False),
        sa.Column("type_declaration", sa.String(20), nullable=False),
        sa.Column("mois", sa.Integer, nullable=True),
        sa.Column("annee", sa.Integer, nullable=False),
        sa.Column("montant_tva_collectee", sa.Numeric(18, 2), server_default="0"),
        sa.Column("montant_tva_deductible", sa.Numeric(18, 2), server_default="0"),
        sa.Column("montant_tva_a_payer", sa.Numeric(18, 2), server_default="0"),
        sa.Column("montant_tap", sa.Numeric(18, 2), server_default="0"),
        sa.Column("montant_irg_salaires", sa.Numeric(18, 2), server_default="0"),
        sa.Column("montant_total", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("date_depot", sa.Date),
        sa.Column("reference", sa.String(100)),
        sa.Column("statut", sa.String(20), server_default="BROUILLON"),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── echeancier_clients ──
    op.create_table(
        "echeancier_clients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("client_id", sa.String(36), sa.ForeignKey("clients_cc.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False),
        sa.Column("lot_id", sa.String(36), sa.ForeignKey("lots.id"), nullable=True),
        sa.Column("numero_echeance", sa.Integer, nullable=False),
        sa.Column("montant", sa.Numeric(18, 2), nullable=False),
        sa.Column("date_prevue", sa.Date, nullable=False),
        sa.Column("date_paiement", sa.Date),
        sa.Column("statut", sa.String(20), server_default="EN_ATTENTE"),
        sa.Column("jours_retard", sa.Integer, server_default="0"),
        sa.Column("alerte_envoyee", sa.Boolean, server_default="false"),
        sa.Column("encaissement_id", sa.String(36), sa.ForeignKey("encaissements.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── capital_associes ──
    op.create_table(
        "capital_associes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("associe_id", sa.String(36), sa.ForeignKey("associes.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False),
        sa.Column("montant", sa.Numeric(18, 2), nullable=False),
        sa.Column("date_apport", sa.Date, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("reference", sa.String(100)),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint("montant > 0", name="ck_capital_montant_positif"),
    )
    op.create_index("ix_capital_associe", "capital_associes", ["associe_id", "projet_id"])

    # ── retraits_associes ──
    op.create_table(
        "retraits_associes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("associe_id", sa.String(36), sa.ForeignKey("associes.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False),
        sa.Column("montant", sa.Numeric(18, 2), nullable=False),
        sa.Column("date_retrait", sa.Date, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("reference", sa.String(100)),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint("montant > 0", name="ck_retrait_montant_positif"),
    )
    op.create_index("ix_retrait_associe", "retraits_associes", ["associe_id", "projet_id"])

    # ── consolidation_associes ──
    op.create_table(
        "consolidation_associes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("associe_id", sa.String(36), sa.ForeignKey("associes.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False),
        sa.Column("exercice_id", sa.String(36), sa.ForeignKey("exercices.id"), nullable=True),
        sa.Column("mois", sa.Integer, nullable=False),
        sa.Column("annee", sa.Integer, nullable=False),
        sa.Column("pourcentage", sa.Numeric(8, 2), server_default="0"),
        sa.Column("capital_verse", sa.Numeric(18, 2), server_default="0"),
        sa.Column("retraits", sa.Numeric(18, 2), server_default="0"),
        sa.Column("quote_part_recettes", sa.Numeric(18, 2), server_default="0"),
        sa.Column("quote_part_depenses", sa.Numeric(18, 2), server_default="0"),
        sa.Column("quote_part_resultat", sa.Numeric(18, 2), server_default="0"),
        sa.Column("position_nette", sa.Numeric(18, 2), server_default="0"),
        sa.Column("alerte_negative", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("associe_id", "projet_id", "annee", "mois", name="uq_consol_associe_mois"),
    )

    # ── consolidation_entreprises ──
    op.create_table(
        "consolidation_entreprises",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("entreprise_id", sa.String(36), sa.ForeignKey("entreprises.id"), nullable=False),
        sa.Column("exercice_id", sa.String(36), sa.ForeignKey("exercices.id"), nullable=True),
        sa.Column("mois", sa.Integer, nullable=False),
        sa.Column("annee", sa.Integer, nullable=False),
        sa.Column("total_recettes", sa.Numeric(18, 2), server_default="0"),
        sa.Column("total_depenses", sa.Numeric(18, 2), server_default="0"),
        sa.Column("total_resultat", sa.Numeric(18, 2), server_default="0"),
        sa.Column("nombre_projets_actifs", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("entreprise_id", "annee", "mois", name="uq_consol_ent_mois"),
    )

    # ═══════════════════════════════════════════════════════════════════════
    # REGISTRY TABLES
    # ═══════════════════════════════════════════════════════════════════════

    # ── notaires ──
    op.create_table(
        "notaires",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("nom", sa.String(200), nullable=False),
        sa.Column("prenom", sa.String(200)),
        sa.Column("titre", sa.String(50), server_default="Maître"),
        sa.Column("adresse", sa.Text),
        sa.Column("telephone", sa.String(50)),
        sa.Column("email", sa.String(200)),
        sa.Column("actif", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── banques_partenaires ──
    op.create_table(
        "banques_partenaires",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("nom_banque", sa.String(200), nullable=False),
        sa.Column("agence", sa.String(200)),
        sa.Column("adresse", sa.Text),
        sa.Column("telephone", sa.String(50)),
        sa.Column("actif", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "code", name="uq_banque_code"),
    )

    # ── projet_notaires ──
    op.create_table(
        "projet_notaires",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False),
        sa.Column("notaire_id", sa.String(36), sa.ForeignKey("notaires.id"), nullable=False),
        sa.Column("date_debut", sa.Date),
        sa.Column("date_fin", sa.Date),
        sa.Column("actif", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("projet_id", "notaire_id", name="uq_projet_notaire"),
    )

    # ── projet_banques ──
    op.create_table(
        "projet_banques",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False),
        sa.Column("banque_id", sa.String(36), sa.ForeignKey("banques_partenaires.id"), nullable=False),
        sa.Column("date_debut", sa.Date),
        sa.Column("date_fin", sa.Date),
        sa.Column("actif", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("projet_id", "banque_id", name="uq_projet_banque"),
    )

    # ── parts_projets ──
    op.create_table(
        "parts_projets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False),
        sa.Column("associe_id", sa.String(36), sa.ForeignKey("associes.id"), nullable=False),
        sa.Column("pourcentage", sa.Numeric(8, 2), nullable=False),
        sa.Column("montant_apport", sa.Numeric(18, 2), server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("projet_id", "associe_id", name="uq_part_projet_associe"),
        sa.CheckConstraint("pourcentage > 0 AND pourcentage <= 100", name="ck_part_pct_range"),
    )

    # ── mutations_foncieres ──
    op.create_table(
        "mutations_foncieres",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False),
        sa.Column("type_mutation", sa.String(30), nullable=False),
        sa.Column("cedant_id", sa.String(36)),
        sa.Column("cedant_type", sa.String(20)),
        sa.Column("cessionnaire_id", sa.String(36)),
        sa.Column("cessionnaire_type", sa.String(20)),
        sa.Column("date_mutation", sa.Date),
        sa.Column("montant", sa.Numeric(18, 2)),
        sa.Column("reference_acte", sa.String(100)),
        sa.Column("description", sa.Text),
        sa.Column("ordre", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_mutation_projet", "mutations_foncieres", ["projet_id", "ordre"])

    # ── lots_immobiliers ──
    op.create_table(
        "lots_immobiliers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False),
        sa.Column("bloc", sa.String(10), nullable=False),
        sa.Column("etage", sa.String(10), nullable=False),
        sa.Column("numero_lot", sa.String(20), nullable=False),
        sa.Column("type_bien", sa.String(30), nullable=False),
        sa.Column("surface", sa.Numeric(10, 2), nullable=False),
        sa.Column("prix", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("statut", sa.String(20), server_default="DISPONIBLE"),
        sa.Column("client_id", sa.String(36), sa.ForeignKey("clients_cc.id"), nullable=True),
        sa.Column("date_reservation", sa.Date),
        sa.Column("date_vente", sa.Date),
        sa.Column("date_livraison", sa.Date),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("projet_id", "bloc", "etage", "numero_lot", name="uq_lot_immo"),
        sa.CheckConstraint("surface > 0", name="ck_lot_surface_pos"),
        sa.CheckConstraint("prix >= 0", name="ck_lot_prix_pos"),
    )
    op.create_index("ix_lot_statut", "lots_immobiliers", ["projet_id", "statut"])

    # ── projet_entreprise_historique ──
    op.create_table(
        "projet_entreprise_historique",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False),
        sa.Column("entreprise_id", sa.String(36), sa.ForeignKey("entreprises.id"), nullable=False),
        sa.Column("date_debut", sa.Date, nullable=False),
        sa.Column("date_fin", sa.Date, nullable=True),
        sa.Column("type_transition", sa.String(50)),
        sa.Column("reference_acte", sa.String(100)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("projet_id", "entreprise_id", "date_debut", name="uq_proj_ent_hist"),
    )

    # ── dossiers_fictifs_reference ──
    op.create_table(
        "dossiers_fictifs_reference",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("donnees_entree", sa.JSON, nullable=False),
        sa.Column("resultats_attendus", sa.JSON, nullable=False),
        sa.Column("derniere_execution", sa.DateTime, nullable=True),
        sa.Column("dernier_resultat", sa.JSON, nullable=True),
        sa.Column("dernier_statut", sa.String(10)),
        sa.Column("ecart_detecte", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CORE / DOCUMENT / WORKFLOW TABLES
    # ═══════════════════════════════════════════════════════════════════════

    # ── import_sessions ──
    op.create_table(
        "import_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("nombre_fichiers", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fichiers_traites", sa.Integer, server_default="0"),
        sa.Column("fichiers_erreur", sa.Integer, server_default="0"),
        sa.Column("statut", sa.String(20), server_default="EN_COURS"),
        sa.Column("erreurs", sa.JSON),
        sa.Column("date_import", sa.DateTime, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── versions_documents ──
    op.create_table(
        "versions_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("numero_version", sa.Integer, nullable=False),
        sa.Column("hash_sha256", sa.String(64), nullable=False),
        sa.Column("chemin_fichier", sa.String(500)),
        sa.Column("taille_octets", sa.Integer),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "numero_version", name="uq_doc_version"),
    )

    # ── archivage_physique ──
    op.create_table(
        "archivage_physique",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("emplacement", sa.String(200)),
        sa.Column("armoire", sa.String(50)),
        sa.Column("etagere", sa.String(50)),
        sa.Column("boite", sa.String(50)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # ── document_segments ──
    op.create_table(
        "document_segments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("numero_segment", sa.Integer, nullable=False),
        sa.Column("nombre_total_segments", sa.Integer, nullable=False),
        sa.Column("page_debut", sa.Integer),
        sa.Column("page_fin", sa.Integer),
        sa.Column("onglet_excel", sa.String(100)),
        sa.Column("ligne_debut", sa.Integer),
        sa.Column("ligne_fin", sa.Integer),
        sa.Column("modele_ia_utilise", sa.String(50), nullable=False),
        sa.Column("texte_extrait", sa.Text),
        sa.Column("donnees_extraites", sa.JSON),
        sa.Column("certitude_globale", sa.Numeric(5, 2)),
        sa.Column("temps_traitement_ms", sa.Integer),
        sa.Column("tokens_utilises", sa.Integer),
        sa.Column("est_consolide", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "numero_segment", name="uq_doc_segment"),
    )
    op.create_index("ix_segment_document", "document_segments", ["document_id"])

    # ── ia_extraction_log ──
    op.create_table(
        "ia_extraction_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("segment_id", sa.String(36), sa.ForeignKey("document_segments.id"), nullable=True),
        sa.Column("modele", sa.String(50), nullable=False),
        sa.Column("type_requete", sa.String(50), nullable=False),
        sa.Column("prompt_resume", sa.Text),
        sa.Column("reponse_json", sa.JSON),
        sa.Column("tokens_input", sa.Integer),
        sa.Column("tokens_output", sa.Integer),
        sa.Column("cout_estime", sa.Numeric(8, 4)),
        sa.Column("temps_ms", sa.Integer),
        sa.Column("succes", sa.Boolean, server_default="true"),
        sa.Column("erreur", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_ia_log_document", "ia_extraction_log", ["document_id"])
    op.create_index("ix_ia_log_date", "ia_extraction_log", ["created_at"])

    # ── verifications_hash ──
    op.create_table(
        "verifications_hash",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("table_cible", sa.String(100), nullable=False),
        sa.Column("enregistrement_id", sa.String(36), nullable=False),
        sa.Column("hash_sha256", sa.String(64), nullable=False),
        sa.Column("donnees_hashees", sa.JSON),
        sa.Column("est_cloture", sa.Boolean, server_default="false"),
        sa.Column("date_cloture", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_verif_hash_table", "verifications_hash", ["table_cible", "enregistrement_id"])

    # ── workflow_dossiers ──
    op.create_table(
        "workflow_dossiers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("entreprise_id", sa.String(36), sa.ForeignKey("entreprises.id"), nullable=True),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=True),
        sa.Column("phase_actuelle", sa.Integer, nullable=False, server_default="0"),
        sa.Column("score_actuel", sa.Integer, server_default="0"),
        sa.Column("statut", sa.String(20), server_default="EN_COURS"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint("phase_actuelle >= 0 AND phase_actuelle <= 6", name="ck_wd_phase_range"),
    )

    # ── workflow_phases_log ──
    op.create_table(
        "workflow_phases_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("dossier_id", sa.String(36), sa.ForeignKey("workflow_dossiers.id"), nullable=False),
        sa.Column("phase", sa.Integer, nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("score", sa.Integer),
        sa.Column("resultat", sa.JSON),
        sa.Column("erreurs", sa.Text),
        sa.Column("duree_ms", sa.Integer),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_wf_phase_log_dossier", "workflow_phases_log", ["dossier_id", "phase"])

    # ── demandes_completion ──
    op.create_table(
        "demandes_completion",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("dossier_id", sa.String(36), sa.ForeignKey("workflow_dossiers.id"), nullable=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("type_demande", sa.String(50), nullable=False),
        sa.Column("champ_manquant", sa.String(100)),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("format_attendu", sa.String(200)),
        sa.Column("priorite", sa.String(20), server_default="NORMALE"),
        sa.Column("statut", sa.String(20), server_default="DETECTE"),
        sa.Column("reponse", sa.Text),
        sa.Column("demandeur_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("repondeur_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("fichier_joint_id", sa.String(36), sa.ForeignKey("documents.id")),
        sa.Column("date_detection", sa.DateTime),
        sa.Column("date_resolution", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_demande_statut", "demandes_completion", ["statut"])
    op.create_index("ix_demande_dossier", "demandes_completion", ["dossier_id"])


def downgrade() -> None:
    # Drop in reverse order
    op.drop_table("demandes_completion")
    op.drop_table("workflow_phases_log")
    op.drop_table("workflow_dossiers")
    op.drop_table("verifications_hash")
    op.drop_table("ia_extraction_log")
    op.drop_table("document_segments")
    op.drop_table("archivage_physique")
    op.drop_table("versions_documents")
    op.drop_table("import_sessions")
    op.drop_table("dossiers_fictifs_reference")
    op.drop_table("projet_entreprise_historique")
    op.drop_table("lots_immobiliers")
    op.drop_table("mutations_foncieres")
    op.drop_table("parts_projets")
    op.drop_table("projet_banques")
    op.drop_table("projet_notaires")
    op.drop_table("banques_partenaires")
    op.drop_table("notaires")
    op.drop_table("consolidation_entreprises")
    op.drop_table("consolidation_associes")
    op.drop_table("retraits_associes")
    op.drop_table("capital_associes")
    op.drop_table("echeancier_clients")
    op.drop_table("declarations_fiscales")
    op.drop_table("bulletins_paie")
    op.drop_table("comptes_bancaires")
    op.drop_table("journaux")
