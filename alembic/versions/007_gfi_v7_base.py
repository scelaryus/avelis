"""GFI v7.0 — Base migration: new tables + column extensions.

Revision ID: 007
Revises: 006
Create Date: 2026-03-13

New tables:
  - entreprise_associes, origine_capital_detail
  - transactions, flux_inter_projets, compensations_st
  - clotures_mensuelles_repartitions, vehicules_groupe
  - cff_factures, cff_imputation_associes
  - roles, utilisateurs, utilisateur_roles, audit_log_gfi
  - dossiers_juridiques, permis_autorisations, commandes_achats, stock_materiel
  - contrats_travail, fiches_paie
  - meta_objets_metier_detectes, meta_rapports_lacunes, meta_specifications_generees
  - meta_code_genere, meta_resultats_tests, meta_feedback_apprentissage

Extended tables:
  - entreprises: +taux_ibs, +taux_tap, +taux_tva, +capital_social, +forme_juridique, +date_creation
  - projets: +nb_clients_total, +est_abandonne, +passif_residuel, +superficie_terrain, etc.
  - associes: +nin, +est_fondateur, +ordre_priorite, +date_naissance, +lieu_naissance, etc.
  - clotures_mensuelles: +tnm_calcul_1, +tnm_calcul_2, +ecart_computation, +etape_courante
  - mouvements_comptes_courants: +realite_financiere
  - employees: +realite_financiere, +nin, +est_declare_cnas
"""

revision = "007"
down_revision = "006_user_permissions"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # ── New columns on existing tables ──

    # entreprises
    for col, typ in [
        ("taux_ibs", "NUMERIC(5,4) DEFAULT 0.19"),
        ("taux_tap", "NUMERIC(5,4) DEFAULT 0.02"),
        ("taux_tva", "NUMERIC(5,4) DEFAULT 0.19"),
        ("capital_social", "NUMERIC(18,2) DEFAULT 0"),
        ("forme_juridique", "VARCHAR(50)"),
        ("date_creation", "DATE"),
    ]:
        op.execute(f"ALTER TABLE entreprises ADD COLUMN IF NOT EXISTS {col} {typ}")

    # projets
    for col, typ in [
        ("nb_clients_total", "INTEGER DEFAULT 0"),
        ("est_abandonne", "BOOLEAN DEFAULT 0"),
        ("passif_residuel", "NUMERIC(18,2) DEFAULT 0"),
        ("superficie_terrain", "NUMERIC(12,2)"),
        ("commune", "VARCHAR(200)"),
        ("wilaya", "VARCHAR(200)"),
        ("type_projet", "VARCHAR(100)"),
        ("maitre_ouvrage", "VARCHAR(300)"),
        ("numero_permis_construire", "VARCHAR(100)"),
        ("date_permis_construire", "DATE"),
        ("taux_avancement", "NUMERIC(5,2) DEFAULT 0"),
    ]:
        op.execute(f"ALTER TABLE projets ADD COLUMN IF NOT EXISTS {col} {typ}")

    # associes
    for col, typ in [
        ("nin", "VARCHAR(20)"),
        ("est_fondateur", "BOOLEAN DEFAULT 0"),
        ("ordre_priorite", "VARCHAR(10)"),
        ("date_naissance", "DATE"),
        ("lieu_naissance", "VARCHAR(200)"),
        ("adresse", "TEXT"),
        ("telephone", "VARCHAR(50)"),
        ("email", "VARCHAR(255)"),
    ]:
        op.execute(f"ALTER TABLE associes ADD COLUMN IF NOT EXISTS {col} {typ}")

    # clotures_mensuelles
    for col, typ in [
        ("tnm_calcul_1", "NUMERIC(15,2)"),
        ("tnm_calcul_2", "NUMERIC(15,2)"),
        ("ecart_computation", "NUMERIC(15,2)"),
        ("etape_courante", "INTEGER"),
    ]:
        op.execute(f"ALTER TABLE clotures_mensuelles ADD COLUMN IF NOT EXISTS {col} {typ}")

    # mouvements_comptes_courants
    op.execute("ALTER TABLE mouvements_comptes_courants ADD COLUMN IF NOT EXISTS realite_financiere VARCHAR(4)")

    # employees
    for col, typ in [
        ("realite_financiere", "VARCHAR(4) DEFAULT 'RF1'"),
        ("nin", "VARCHAR(20)"),
        ("est_declare_cnas", "BOOLEAN DEFAULT 1"),
    ]:
        op.execute(f"ALTER TABLE employees ADD COLUMN IF NOT EXISTS {col} {typ}")

    # ── New tables ──

    op.create_table(
        "entreprise_associes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entreprise_id", sa.String(36), sa.ForeignKey("entreprises.id"), nullable=False),
        sa.Column("associe_id", sa.String(36), sa.ForeignKey("associes.id"), nullable=False),
        sa.Column("pourcentage", sa.Numeric(6, 4), nullable=False),
        sa.Column("date_entree", sa.Date),
        sa.Column("date_sortie", sa.Date),
        sa.Column("est_actif", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("entreprise_id", "associe_id", name="uq_ent_assoc"),
    )

    op.create_table(
        "origine_capital_detail",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entreprise_id", sa.String(36), sa.ForeignKey("entreprises.id"), nullable=False),
        sa.Column("associe_id", sa.String(36), sa.ForeignKey("associes.id"), nullable=False),
        sa.Column("realite_financiere", sa.String(4)),
        sa.Column("montant", sa.Numeric(18, 2), nullable=False),
        sa.Column("document_reference", sa.String(300)),
        sa.Column("description", sa.Text),
        sa.Column("date_apport", sa.Date),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("entreprise_id", sa.String(36), sa.ForeignKey("entreprises.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id")),
        sa.Column("realite_financiere", sa.String(4), nullable=False),
        sa.Column("type_transaction", sa.String(30), nullable=False),
        sa.Column("montant", sa.Numeric(18, 2), nullable=False),
        sa.Column("date_transaction", sa.Date, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("reference", sa.String(200)),
        sa.Column("compte_debit", sa.String(20)),
        sa.Column("compte_credit", sa.String(20)),
        sa.Column("hash_sha256", sa.String(64)),
        sa.Column("document_id", sa.String(36)),
        sa.Column("created_by", sa.String(36)),
        sa.Column("is_deleted", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "flux_inter_projets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("projet_source_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False),
        sa.Column("projet_destination_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False),
        sa.Column("realite_financiere", sa.String(4), nullable=False),
        sa.Column("nature", sa.String(30), nullable=False),
        sa.Column("montant", sa.Numeric(18, 2), nullable=False),
        sa.Column("solde_restant", sa.Numeric(18, 2), default=0),
        sa.Column("source_externe", sa.Boolean, default=False),
        sa.Column("date_flux", sa.Date, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("document_id", sa.String(36)),
        sa.Column("created_by", sa.String(36)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "compensations_st",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("projet_id", sa.String(36), sa.ForeignKey("projets.id"), nullable=False),
        sa.Column("sous_traitant_id", sa.String(36)),
        sa.Column("realite_financiere", sa.String(4), nullable=False),
        sa.Column("montant", sa.Numeric(18, 2), nullable=False),
        sa.Column("type_ecriture", sa.String(50)),
        sa.Column("compte_debit", sa.String(20)),
        sa.Column("compte_credit", sa.String(20)),
        sa.Column("sortie_cash_512", sa.Boolean, default=False),
        sa.Column("est_avance_materiel", sa.Boolean, default=False),
        sa.Column("description", sa.Text),
        sa.Column("date_compensation", sa.Date, nullable=False),
        sa.Column("created_by", sa.String(36)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "clotures_mensuelles_repartitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cloture_id", sa.String(36), sa.ForeignKey("clotures_mensuelles.id"), nullable=False),
        sa.Column("associe_id", sa.String(36), sa.ForeignKey("associes.id"), nullable=False),
        sa.Column("pourcentage", sa.Numeric(6, 4), nullable=False),
        sa.Column("montant", sa.Numeric(15, 2), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "vehicules_groupe",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("entreprise_id", sa.String(36), sa.ForeignKey("entreprises.id"), nullable=False),
        sa.Column("immatriculation", sa.String(50), nullable=False, unique=True),
        sa.Column("marque", sa.String(100)),
        sa.Column("modele", sa.String(100)),
        sa.Column("date_acquisition", sa.Date, nullable=False),
        sa.Column("prix_acquisition", sa.Numeric(18, 2), nullable=False),
        sa.Column("statut", sa.String(30), default="EN_SERVICE"),
        sa.Column("cede_a_st_id", sa.String(36)),
        sa.Column("date_cession_st", sa.Date),
        sa.Column("montant_cession_st", sa.Numeric(18, 2)),
        sa.Column("situation_deduction_id", sa.String(36)),
        sa.Column("montant_deduit", sa.Numeric(18, 2), default=0),
        sa.Column("date_debut_deduction", sa.Date),
        sa.Column("date_fin_deduction", sa.Date),
        sa.Column("prix_revente", sa.Numeric(18, 2)),
        sa.Column("date_revente", sa.Date),
        sa.Column("acheteur_revente", sa.String(300)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # CFF tables
    op.create_table(
        "cff_factures",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entreprise_id", sa.String(36), sa.ForeignKey("entreprises.id"), nullable=False),
        sa.Column("projet_id", sa.String(36)),
        sa.Column("periode_mois", sa.String(7)),
        sa.Column("montant_ht", sa.Numeric(18, 2), nullable=False),
        sa.Column("cff_tva", sa.Numeric(18, 2), default=0),
        sa.Column("cff_ibs", sa.Numeric(18, 2), default=0),
        sa.Column("cff_tap", sa.Numeric(18, 2), default=0),
        sa.Column("cff_cnas", sa.Numeric(18, 2), default=0),
        sa.Column("cff_timbre", sa.Numeric(18, 2), default=0),
        sa.Column("cff_total", sa.Numeric(18, 2), default=0),
        sa.Column("reference_facture", sa.String(200)),
        sa.Column("description", sa.Text),
        sa.Column("hash_sha256", sa.String(64)),
        sa.Column("created_by", sa.String(36)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "cff_imputation_associes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("facture_id", sa.String(36), sa.ForeignKey("cff_factures.id"), nullable=False),
        sa.Column("associe_id", sa.String(36), sa.ForeignKey("associes.id"), nullable=False),
        sa.Column("pourcentage_entreprise", sa.Numeric(6, 4), nullable=False),
        sa.Column("montant_impute", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # RBAC tables
    op.create_table(
        "roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("libelle", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("permissions", sa.JSON, default={}),
        sa.Column("est_actif", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "utilisateurs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("associe_id", sa.String(36)),
        sa.Column("company_id", sa.String(36)),
        sa.Column("nom_complet", sa.String(300)),
        sa.Column("email", sa.String(255)),
        sa.Column("est_actif", sa.Boolean, default=True),
        sa.Column("derniere_connexion", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "utilisateur_roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("utilisateur_id", sa.String(36), sa.ForeignKey("utilisateurs.id"), nullable=False),
        sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("entreprise_id", sa.String(36)),
        sa.Column("date_attribution", sa.Date),
        sa.Column("est_actif", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "audit_log_gfi",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("utilisateur_id", sa.String(36)),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entite_type", sa.String(100)),
        sa.Column("entite_id", sa.String(36)),
        sa.Column("realite_financiere", sa.String(4)),
        sa.Column("est_sensible", sa.Boolean, default=False),
        sa.Column("ancien_valeur", sa.JSON),
        sa.Column("nouveau_valeur", sa.JSON),
        sa.Column("hash_sha256", sa.String(64)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Juridique tables
    op.create_table(
        "dossiers_juridiques",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("entreprise_id", sa.String(36)),
        sa.Column("projet_id", sa.String(36)),
        sa.Column("reference", sa.String(100)),
        sa.Column("titre", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("type_dossier", sa.String(100)),
        sa.Column("est_succession", sa.Boolean, default=False),
        sa.Column("partie_adverse", sa.String(300)),
        sa.Column("tribunal", sa.String(300)),
        sa.Column("montant_litige", sa.Numeric(18, 2)),
        sa.Column("statut", sa.String(30), default="OUVERT"),
        sa.Column("date_ouverture", sa.Date),
        sa.Column("date_cloture", sa.Date),
        sa.Column("avocat_responsable", sa.String(300)),
        sa.Column("created_by", sa.String(36)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "permis_autorisations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("entreprise_id", sa.String(36)),
        sa.Column("projet_id", sa.String(36)),
        sa.Column("type_permis", sa.String(100), nullable=False),
        sa.Column("numero", sa.String(100)),
        sa.Column("date_delivrance", sa.Date),
        sa.Column("date_expiration", sa.Date),
        sa.Column("autorite_delivrance", sa.String(300)),
        sa.Column("est_valide", sa.Boolean, default=True),
        sa.Column("document_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "commandes_achats",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("entreprise_id", sa.String(36), nullable=False),
        sa.Column("projet_id", sa.String(36)),
        sa.Column("fournisseur_id", sa.String(36)),
        sa.Column("reference", sa.String(100)),
        sa.Column("realite_financiere", sa.String(4)),
        sa.Column("montant_ht", sa.Numeric(18, 2), nullable=False),
        sa.Column("montant_tva", sa.Numeric(18, 2), default=0),
        sa.Column("montant_ttc", sa.Numeric(18, 2)),
        sa.Column("est_avance_materiel", sa.Boolean, default=False),
        sa.Column("statut", sa.String(30), default="BROUILLON"),
        sa.Column("date_commande", sa.Date, nullable=False),
        sa.Column("date_livraison_prevue", sa.Date),
        sa.Column("date_livraison_effective", sa.Date),
        sa.Column("description", sa.Text),
        sa.Column("created_by", sa.String(36)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "stock_materiel",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("entreprise_id", sa.String(36), nullable=False),
        sa.Column("code_article", sa.String(50), nullable=False),
        sa.Column("designation", sa.String(300), nullable=False),
        sa.Column("unite", sa.String(50), default="unité"),
        sa.Column("quantite", sa.Numeric(18, 4), default=0),
        sa.Column("valeur_unitaire", sa.Numeric(18, 4), default=0),
        sa.Column("valeur_totale", sa.Numeric(18, 2), default=0),
        sa.Column("emplacement", sa.String(200)),
        sa.Column("seuil_alerte", sa.Numeric(18, 4), default=0),
        sa.Column("est_actif", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # HR v7 tables
    op.create_table(
        "contrats_travail",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("type_contrat", sa.String(20), nullable=False),
        sa.Column("date_debut", sa.Date, nullable=False),
        sa.Column("date_fin", sa.Date),
        sa.Column("salaire_base", sa.Numeric(18, 2), nullable=False),
        sa.Column("poste", sa.String(255)),
        sa.Column("lieu_travail", sa.String(300)),
        sa.Column("reference", sa.String(100)),
        sa.Column("est_actif", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "fiches_paie",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("contrat_id", sa.String(36)),
        sa.Column("mois", sa.Integer, nullable=False),
        sa.Column("annee", sa.Integer, nullable=False),
        sa.Column("realite_financiere", sa.String(4), default="RF1"),
        sa.Column("salaire_base", sa.Numeric(18, 2), nullable=False),
        sa.Column("heures_supplementaires", sa.Numeric(18, 2), default=0),
        sa.Column("primes", sa.Numeric(18, 2), default=0),
        sa.Column("indemnites", sa.Numeric(18, 2), default=0),
        sa.Column("salaire_brut", sa.Numeric(18, 2), nullable=False),
        sa.Column("cnas_salarial", sa.Numeric(18, 2), default=0),
        sa.Column("cnas_patronal", sa.Numeric(18, 2), default=0),
        sa.Column("irg_retenu", sa.Numeric(18, 2), default=0),
        sa.Column("salaire_net", sa.Numeric(18, 2), nullable=False),
        sa.Column("cout_employeur", sa.Numeric(18, 2), default=0),
        sa.Column("reference_fiche", sa.String(100)),
        sa.Column("statut", sa.String(30), default="BROUILLON"),
        sa.Column("created_by", sa.String(36)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Meta-IA tables
    op.create_table(
        "meta_objets_metier_detectes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36)),
        sa.Column("type_objet", sa.String(100), nullable=False),
        sa.Column("nom_objet", sa.String(300)),
        sa.Column("score_confiance", sa.Float, nullable=False),
        sa.Column("donnees_extraites", sa.JSON),
        sa.Column("source_page", sa.Integer),
        sa.Column("source_bbox", sa.JSON),
        sa.Column("valide_par_humain", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "meta_rapports_lacunes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("module", sa.String(100), nullable=False),
        sa.Column("description_lacune", sa.Text, nullable=False),
        sa.Column("impact", sa.String(50)),
        sa.Column("resolution_proposee", sa.Text),
        sa.Column("est_resolu", sa.Boolean, default=False),
        sa.Column("date_resolution", sa.DateTime),
        sa.Column("resolu_par", sa.String(36)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "meta_specifications_generees",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("module", sa.String(100), nullable=False),
        sa.Column("titre", sa.String(500), nullable=False),
        sa.Column("contenu", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, default=1),
        sa.Column("validation_humaine", sa.Boolean, default=False),
        sa.Column("valide_par", sa.String(36)),
        sa.Column("date_validation", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "meta_code_genere",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("module", sa.String(100), nullable=False),
        sa.Column("fichier_cible", sa.String(500)),
        sa.Column("langage", sa.String(50), default="python"),
        sa.Column("contenu_code", sa.Text, nullable=False),
        sa.Column("auto_deploy", sa.Boolean, default=False, nullable=False),
        sa.Column("revue_par", sa.String(36)),
        sa.Column("date_revue", sa.DateTime),
        sa.Column("est_approuve", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "meta_resultats_tests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("test_name", sa.String(200), nullable=False),
        sa.Column("test_type", sa.String(50)),
        sa.Column("resultat", sa.String(20), nullable=False),
        sa.Column("duree_ms", sa.Integer),
        sa.Column("details", sa.JSON),
        sa.Column("couverture_pct", sa.Float),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "meta_feedback_apprentissage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("objet_id", sa.String(36)),
        sa.Column("type_feedback", sa.String(50)),
        sa.Column("commentaire", sa.Text),
        sa.Column("score_avant", sa.Float),
        sa.Column("score_apres", sa.Float),
        sa.Column("utilisateur_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    # Drop new tables in reverse order
    for table in [
        "meta_feedback_apprentissage", "meta_resultats_tests", "meta_code_genere",
        "meta_specifications_generees", "meta_rapports_lacunes", "meta_objets_metier_detectes",
        "fiches_paie", "contrats_travail",
        "stock_materiel", "commandes_achats", "permis_autorisations", "dossiers_juridiques",
        "audit_log_gfi", "utilisateur_roles", "utilisateurs", "roles",
        "cff_imputation_associes", "cff_factures",
        "vehicules_groupe", "clotures_mensuelles_repartitions",
        "compensations_st", "flux_inter_projets", "transactions",
        "origine_capital_detail", "entreprise_associes",
    ]:
        op.drop_table(table)
