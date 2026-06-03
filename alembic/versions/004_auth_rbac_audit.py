"""Authentication, authorization (RBAC), immutable audit trail, Separation of Duties.

Tables created:
- role (18 roles: 15 core + 3 HR sub-roles)
- permission (49 granular permissions)
- role_permission (access matrix junction)
- user_role (per-company role assignment, uses GFIBase)
- audit_trail (immutable append-only log)
- sod_rule (5 Separation of Duties rules)

Expands auth_user with authentication fields.

Database enforcement:
- audit_trail: trigger blocks ALL UPDATE and DELETE — even for admins.
- user_role: soft-delete + no-physical-delete triggers (KT-10).
- SoD rules seeded for application-level enforcement.

Revision ID: 004
Revises: 003
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"

# ─── Deterministic UUID counters ─────────────────────────────────────────────
_rp_counter = 0


def _rp_uuid():
    """Generate deterministic UUIDs for role_permission rows."""
    global _rp_counter
    _rp_counter += 1
    return f"80000000-0000-0000-0000-{_rp_counter:012x}"


# ─── Standard system columns for GFIBase tables ─────────────────────────────
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


# ═════════════════════════════════════════════════════════════════════════════
# SEED DATA DEFINITIONS
# ═════════════════════════════════════════════════════════════════════════════

# ── 18 Roles ─────────────────────────────────────────────────────────────────
# (code, name, description, module_scope, escalation_level)
ROLES = [
    ("ADMIN_SYS", "Administrateur Système",
     "Technical configuration only, no business validation.",
     None, None),
    ("DAF", "DAF (Directeur Administratif et Financier)",
     "ALL final validations. Only role with CC write access.",
     None, 4),
    ("MANAGER_FINANCE", "Manager Finance",
     "Accounting closings, G50 generation, journal validation.",
     "COMPTABILITE", None),
    ("COMPTABLE", "Comptable",
     "Entry recording (auto-generated only), ledger consultation.",
     "COMPTABILITE", None),
    ("MANAGER_TRESORERIE", "Manager Trésorerie",
     "Treasury closings, CCA management.",
     "TRESORERIE", None),
    ("TRESORIER", "Trésorier",
     "Bank reconciliation, movement recording.",
     "TRESORERIE", None),
    ("MANAGER_ADV", "Manager ADV (Responsable ADV)",
     "Engagement approvals, discount validation, full dossier control.",
     "ADV", None),
    ("GESTIONNAIRE_ADV", "Gestionnaire ADV",
     "Client file management, document follow-up.",
     "ADV", None),
    ("AGENT_COMMERCIAL", "Agent Commercial",
     "Quote creation only. ZERO RF2 visibility — columns stripped entirely.",
     "ADV", None),
    ("MANAGER_RH", "Manager RH (DRH)",
     "Payroll approval, SPI, contracts, discipline.",
     "HR", 3),
    ("MANAGER_PROJETS", "Manager Projets",
     "Work situation validation, advancement tracking.",
     "PROJET", None),
    ("CHEF_CHANTIER", "Chef de Chantier",
     "Site reception, quality verification.",
     "CHANTIER", None),
    ("MANAGER_ACHATS", "Manager Achats",
     "Purchase order validation, supplier management.",
     "ACHATS", None),
    ("MAGASINIER", "Magasinier",
     "Stock entry/exit, QR scanning.",
     "STOCK", None),
    ("MANAGER_JURIDIQUE", "Manager Juridique",
     "Contract lifecycle, share transfers, preemption rights.",
     "JURIDIQUE", None),
    # ── HR sub-roles ─────────────────────────────────────────────────────
    ("CHARGE_PAIE", "Chargé Paie & Social",
     "Payslips, salary rules, contributions, declarations. "
     "CANNOT access recruitment, training, appraisals, discipline (except reading PVs).",
     "HR_PAIE", 2),
    ("CHARGE_RECRUTEMENT", "Chargé Recrutement & Formation",
     "Job positions, applicants, tests, training, skills. "
     "CANNOT access payslips, salary rules, bank accounts. "
     "Can read employee files WITHOUT salary data.",
     "HR_RECRUTEMENT", 2),
    ("ASSISTANTE_RH", "Assistante RH",
     "Employee files (create/read/update, no salary info), documents, "
     "leave requests, equipment. CANNOT delete anything, "
     "cannot access payslips, salary rules, discipline (except reading PVs).",
     "HR", 1),
]

ROLE_IDS = {}
for i, (code, *_) in enumerate(ROLES, start=1):
    ROLE_IDS[code] = f"60000000-0000-0000-0000-{i:012x}"


# ── 49 Permissions ───────────────────────────────────────────────────────────
# (code, module, action, description)
PERMISSIONS = [
    # RF1
    ("rf1.read", "RF1", "READ", "Consulter les transactions RF1"),
    ("rf1.write", "RF1", "WRITE", "Créer/modifier les transactions RF1"),
    ("rf1.validate", "RF1", "VALIDATE", "Valider les transactions RF1"),
    # RF2
    ("rf2.read", "RF2", "READ", "Consulter les données RF2 (accès audité)"),
    ("rf2.write", "RF2", "WRITE", "Créer/modifier les transactions RF2"),
    ("rf2.validate", "RF2", "VALIDATE", "Valider les transactions RF2"),
    # CFF
    ("cff.read", "CFF", "READ", "Consulter les calculs CFF"),
    ("cff.write", "CFF", "WRITE", "Créer/modifier les entrées CFF"),
    ("cff.validate", "CFF", "VALIDATE", "Valider les calculs CFF"),
    # Centre de Coût
    ("cc.read", "CENTRE_COUT", "READ", "Consulter les centres de coût"),
    ("cc.write", "CENTRE_COUT", "WRITE", "Écriture centres de coût (DAF exclusif)"),
    # ADV Notaire
    ("adv_notaire.read", "ADV_NOTAIRE", "READ", "Consulter dossiers notaire"),
    ("adv_notaire.write", "ADV_NOTAIRE", "WRITE", "Gérer dossiers notaire"),
    ("adv_notaire.validate", "ADV_NOTAIRE", "VALIDATE", "Valider pipeline notaire"),
    # ADV EDD
    ("adv_edd.read", "ADV_EDD", "READ", "Consulter EDD"),
    ("adv_edd.write", "ADV_EDD", "WRITE", "Gérer EDD"),
    ("adv_edd.validate", "ADV_EDD", "VALIDATE", "Valider pipeline EDD"),
    # Comptabilité
    ("compta.read", "COMPTABILITE", "READ", "Consulter écritures comptables"),
    ("compta.write", "COMPTABILITE", "WRITE", "Saisir écritures comptables"),
    ("compta.validate", "COMPTABILITE", "VALIDATE", "Valider journaux"),
    ("compta.close", "COMPTABILITE", "CLOSE", "Clôtures comptables"),
    ("compta.g50", "COMPTABILITE", "G50", "Génération G50"),
    # Trésorerie
    ("tresorerie.read", "TRESORERIE", "READ", "Consulter trésorerie"),
    ("tresorerie.write", "TRESORERIE", "WRITE", "Enregistrer mouvements"),
    ("tresorerie.validate", "TRESORERIE", "VALIDATE", "Rapprochement bancaire"),
    ("tresorerie.close", "TRESORERIE", "CLOSE", "Clôtures trésorerie"),
    ("tresorerie.cca", "TRESORERIE", "CCA_MANAGE", "Gestion CCA"),
    # HR
    ("hr.read", "HR", "READ", "Consulter données RH"),
    ("hr.write", "HR", "WRITE", "Gérer données RH"),
    ("hr.validate", "HR", "VALIDATE", "Approuver actions RH"),
    # HR Paie
    ("hr_paie.read", "HR_PAIE", "READ", "Consulter bulletins et règles salariales"),
    ("hr_paie.write", "HR_PAIE", "WRITE", "Saisir/modifier bulletins de paie"),
    ("hr_paie.approve", "HR_PAIE", "APPROVE", "Approuver bulletins de paie"),
    # HR Recrutement
    ("hr_recrutement.read", "HR_RECRUTEMENT", "READ", "Consulter recrutement"),
    ("hr_recrutement.write", "HR_RECRUTEMENT", "WRITE", "Gérer recrutement"),
    # HR Formation
    ("hr_formation.read", "HR_FORMATION", "READ", "Consulter plans de formation"),
    ("hr_formation.write", "HR_FORMATION", "WRITE", "Gérer formations"),
    # HR Discipline
    ("hr_discipline.read", "HR_DISCIPLINE", "READ", "Consulter PV disciplinaires"),
    ("hr_discipline.write", "HR_DISCIPLINE", "WRITE", "Gérer procédures disciplinaires"),
    # HR Employee
    ("hr_employee.read", "HR_EMPLOYEE", "READ",
     "Consulter dossiers employés (hors salaire)"),
    ("hr_employee.write", "HR_EMPLOYEE", "WRITE",
     "Créer/modifier dossiers employés"),
    ("hr_employee.salary", "HR_EMPLOYEE", "SALARY_READ",
     "Consulter données salariales dans dossiers"),
    # Projet
    ("projet.read", "PROJET", "READ", "Consulter projets"),
    ("projet.write", "PROJET", "WRITE", "Modifier projets"),
    ("projet.validate", "PROJET", "VALIDATE", "Valider situations de travaux"),
    # Chantier
    ("chantier.read", "CHANTIER", "READ", "Consulter chantier"),
    ("chantier.write", "CHANTIER", "WRITE", "Saisir réceptions/vérifications"),
    # Achats
    ("achats.read", "ACHATS", "READ", "Consulter achats"),
    ("achats.write", "ACHATS", "WRITE", "Créer bons de commande"),
    ("achats.validate", "ACHATS", "VALIDATE", "Valider bons de commande"),
    # Stock
    ("stock.read", "STOCK", "READ", "Consulter stock"),
    ("stock.write", "STOCK", "WRITE", "Mouvements stock, scanning QR"),
    # Juridique
    ("juridique.read", "JURIDIQUE", "READ", "Consulter données juridiques"),
    ("juridique.write", "JURIDIQUE", "WRITE", "Gérer contrats et actes"),
    # System
    ("system.config", "SYSTEM", "CONFIG", "Configuration technique système"),
]

PERM_IDS = {}
for i, (code, *_) in enumerate(PERMISSIONS, start=1):
    PERM_IDS[code] = f"70000000-0000-0000-0000-{i:012x}"

ALL_PERM_CODES = [p[0] for p in PERMISSIONS]


# ── Role → Permission mapping ────────────────────────────────────────────────
# "*" means ALL permissions.
# Reconciled from both the main 15-role matrix AND the ADV-specific RBAC table.
ROLE_PERMS = {
    "ADMIN_SYS": ["*"],
    "DAF": ["*"],
    "MANAGER_FINANCE": [
        "rf1.read", "rf1.write", "rf1.validate",
        "cff.read", "cc.read",
        "compta.read", "compta.write", "compta.validate", "compta.close",
        "compta.g50",
    ],
    "COMPTABLE": [
        # Main matrix: RF1 R/W. ADV table: RF1 Full → use Full.
        "rf1.read", "rf1.write", "rf1.validate",
        "compta.read", "compta.write",
        # ADV table: EDD Read, Notaire Read.
        "adv_edd.read", "adv_notaire.read",
    ],
    "MANAGER_TRESORERIE": [
        "rf1.read", "rf1.write", "rf1.validate",
        "rf2.read", "rf2.write", "rf2.validate",
        "cc.read",
        "adv_notaire.read", "adv_notaire.write", "adv_notaire.validate",
        "tresorerie.read", "tresorerie.write", "tresorerie.validate",
        "tresorerie.close", "tresorerie.cca",
    ],
    "TRESORIER": [
        # Main matrix: RF1 R/W, RF2 Read, Notaire Read.
        # ADV table: RF1 Full, RF2 Full, Notaire Full → use Full.
        "rf1.read", "rf1.write", "rf1.validate",
        "rf2.read", "rf2.write", "rf2.validate",
        "adv_notaire.read", "adv_notaire.write", "adv_notaire.validate",
        "adv_edd.read",
        "tresorerie.read", "tresorerie.write",
    ],
    "MANAGER_ADV": [
        "rf1.read", "rf1.write", "rf1.validate",
        "rf2.read", "rf2.write", "rf2.validate",
        "cc.read",
        "adv_notaire.read", "adv_notaire.write", "adv_notaire.validate",
        "adv_edd.read", "adv_edd.write", "adv_edd.validate",
    ],
    "GESTIONNAIRE_ADV": [
        "rf1.read", "rf1.write",
        "rf2.read",
        "adv_notaire.read",
        "adv_edd.read", "adv_edd.write",
    ],
    "AGENT_COMMERCIAL": [
        # ZERO RF2 visibility — not even rf2.read.
        "rf1.read",
        "adv_edd.read",
    ],
    "MANAGER_RH": [
        # Full HR scope
        "rf1.read", "rf1.write", "rf1.validate",
        "hr.read", "hr.write", "hr.validate",
        "hr_paie.read", "hr_paie.write", "hr_paie.approve",
        "hr_recrutement.read", "hr_recrutement.write",
        "hr_formation.read", "hr_formation.write",
        "hr_discipline.read", "hr_discipline.write",
        "hr_employee.read", "hr_employee.write", "hr_employee.salary",
    ],
    "MANAGER_PROJETS": [
        "rf1.read", "cc.read",
        "projet.read", "projet.write", "projet.validate",
    ],
    "CHEF_CHANTIER": [
        "rf1.read",
        "chantier.read", "chantier.write",
    ],
    "MANAGER_ACHATS": [
        "rf1.read", "rf1.write",
        "achats.read", "achats.write", "achats.validate",
    ],
    "MAGASINIER": [
        "rf1.read",
        "stock.read", "stock.write",
    ],
    "MANAGER_JURIDIQUE": [
        "rf1.read",
        "juridique.read", "juridique.write",
    ],
    # ── HR sub-roles ─────────────────────────────────────────────────────
    "CHARGE_PAIE": [
        "hr_paie.read", "hr_paie.write",
        "hr_employee.read", "hr_employee.salary",
        "hr_discipline.read",  # PV reading only
    ],
    "CHARGE_RECRUTEMENT": [
        "hr_recrutement.read", "hr_recrutement.write",
        "hr_formation.read", "hr_formation.write",
        "hr_employee.read",  # no salary
    ],
    "ASSISTANTE_RH": [
        "hr_employee.read", "hr_employee.write",  # no salary, no delete
        "hr_discipline.read",  # PV reading only
    ],
}


# ── 5 SoD rules ─────────────────────────────────────────────────────────────
SOD_RULES = [
    ("SOD-001", "Purchase order creator cannot validate it",
     "achats.write", "achats.validate", "SAME_RECORD", "MANAGER_ACHATS"),
    ("SOD-002", "Payment recorder cannot reconcile it",
     "tresorerie.write", "tresorerie.validate", "SAME_RECORD",
     "MANAGER_TRESORERIE"),
    ("SOD-003", "Agent cannot validate own discount > 5%",
     "adv_edd.write", "adv_edd.validate", "SAME_RECORD", "MANAGER_ADV"),
    ("SOD-004", "Payslip calculator cannot approve it",
     "hr_paie.write", "hr_paie.approve", "SAME_RECORD", "MANAGER_RH"),
    ("SOD-005", "Discipline initiator cannot be sole decision-maker",
     "hr_discipline.write", "hr_discipline.write", "SAME_RECORD",
     "MANAGER_RH"),
]

SOD_IDS = {}
for i, (code, *_) in enumerate(SOD_RULES, start=1):
    SOD_IDS[code] = f"90000000-0000-0000-0000-{i:012x}"


def upgrade() -> None:
    # ═════════════════════════════════════════════════════════════════════
    # 1. EXPAND auth_user
    # ═════════════════════════════════════════════════════════════════════
    op.add_column("auth_user", sa.Column(
        "email", sa.String(255), unique=True, nullable=True))
    op.add_column("auth_user", sa.Column(
        "full_name", sa.String(255), nullable=True))
    op.add_column("auth_user", sa.Column(
        "password_hash", sa.Text, nullable=True))
    op.add_column("auth_user", sa.Column(
        "last_login", sa.DateTime(timezone=True), nullable=True))
    op.add_column("auth_user", sa.Column(
        "failed_login_attempts", sa.Integer, nullable=False,
        server_default=sa.text("0")))
    op.add_column("auth_user", sa.Column(
        "locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("auth_user", sa.Column(
        "must_change_password", sa.Boolean, nullable=False,
        server_default=sa.text("false")))
    op.add_column("auth_user", sa.Column(
        "updated_at", sa.DateTime(timezone=True), nullable=False,
        server_default=sa.text("now()")))

    # Add updated_at trigger to auth_user
    op.execute("""
        CREATE TRIGGER trg_auth_user_updated_at
        BEFORE UPDATE ON auth_user
        FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 2. CREATE TABLES
    # ═════════════════════════════════════════════════════════════════════

    # ── 2a. role ─────────────────────────────────────────────────────────
    op.create_table(
        "role",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(40), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("module_scope", sa.String(40), nullable=True),
        sa.Column("is_system", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
        sa.Column("escalation_level", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("is_deleted", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
    )

    # ── 2b. permission ───────────────────────────────────────────────────
    op.create_table(
        "permission",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(60), unique=True, nullable=False),
        sa.Column("module", sa.String(40), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("is_deleted", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
    )

    # ── 2c. role_permission ──────────────────────────────────────────────
    op.create_table(
        "role_permission",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("role_id", UUID(as_uuid=True),
                  sa.ForeignKey("role.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("permission_id", UUID(as_uuid=True),
                  sa.ForeignKey("permission.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("role_id", "permission_id",
                            name="uq_role_permission_role_perm"),
    )

    # ── 2d. user_role (GFIBase — has company_id) ─────────────────────────
    op.create_table(
        "user_role",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("role_id", UUID(as_uuid=True),
                  sa.ForeignKey("role.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        *_system_columns(),
        sa.UniqueConstraint("user_id", "role_id", "company_id",
                            name="uq_user_role_user_role_company"),
    )

    # ── 2e. audit_trail (immutable — custom column set) ──────────────────
    op.create_table(
        "audit_trail",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        # Multi-tenant
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        # WHO
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("role_code", sa.String(40), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        # WHAT
        sa.Column("action", sa.String(20), nullable=False, index=True),
        sa.Column("resource_type", sa.String(100), nullable=False, index=True),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=True),
        sa.Column("data_before", JSONB, nullable=True),
        sa.Column("data_after", JSONB, nullable=True),
        # WHEN
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()"), index=True),
        # CONTEXT
        sa.Column("module", sa.String(40), nullable=True),
        sa.Column("workflow_step", sa.String(60), nullable=True),
        sa.Column("verification_level", sa.Integer, nullable=True),
        sa.Column("event_id", UUID(as_uuid=True), nullable=True),
        # RF2 flag
        sa.Column("rf2_access", sa.Boolean, nullable=False,
                  server_default=sa.text("false"), index=True),
    )

    # ── 2f. sod_rule ────────────────────────────────────────────────────
    op.create_table(
        "sod_rule",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(20), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("action_a", sa.String(60), nullable=False),
        sa.Column("action_b", sa.String(60), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False,
                  server_default=sa.text("'SAME_RECORD'")),
        sa.Column("escalate_to_role", sa.String(40), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. TRIGGERS
    # ═════════════════════════════════════════════════════════════════════

    # ── 3a. audit_trail: IMMUTABLE — block ALL UPDATE and DELETE ─────────
    op.execute("""
        CREATE OR REPLACE FUNCTION gfi_audit_immutable()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'Audit trail is immutable. UPDATE and DELETE are forbidden.'
            USING ERRCODE = 'P0001';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_trail_immutable
        BEFORE UPDATE OR DELETE ON audit_trail
        FOR EACH ROW EXECUTE FUNCTION gfi_audit_immutable();
    """)

    # ── 3b. user_role: updated_at + soft-delete (KT-10) ─────────────────
    op.execute("""
        CREATE TRIGGER trg_user_role_updated_at
        BEFORE UPDATE ON user_role
        FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
    """)
    op.execute("SELECT gfi_apply_no_delete_trigger('user_role');")

    # ═════════════════════════════════════════════════════════════════════
    # 4. SEED — 18 roles
    # ═════════════════════════════════════════════════════════════════════
    for code, name, desc, module_scope, esc_level in ROLES:
        rid = ROLE_IDS[code]
        desc_escaped = desc.replace("'", "''")
        mod = f"'{module_scope}'" if module_scope else "NULL"
        esc = str(esc_level) if esc_level is not None else "NULL"
        op.execute(f"""
            INSERT INTO role (id, code, name, description, module_scope,
                              escalation_level)
            VALUES ('{rid}', '{code}', '{name}', '{desc_escaped}', {mod}, {esc});
        """)

    # ═════════════════════════════════════════════════════════════════════
    # 5. SEED — 55 permissions
    # ═════════════════════════════════════════════════════════════════════
    for code, module, action, desc in PERMISSIONS:
        pid = PERM_IDS[code]
        desc_escaped = desc.replace("'", "''")
        op.execute(f"""
            INSERT INTO permission (id, code, module, action, description)
            VALUES ('{pid}', '{code}', '{module}', '{action}',
                    '{desc_escaped}');
        """)

    # ═════════════════════════════════════════════════════════════════════
    # 6. SEED — role_permission matrix
    # ═════════════════════════════════════════════════════════════════════
    for role_code, perm_list in ROLE_PERMS.items():
        rid = ROLE_IDS[role_code]
        # Expand "*" to all permissions
        codes = ALL_PERM_CODES if perm_list == ["*"] else perm_list
        for perm_code in codes:
            pid = PERM_IDS[perm_code]
            rpid = _rp_uuid()
            op.execute(f"""
                INSERT INTO role_permission (id, role_id, permission_id)
                VALUES ('{rpid}', '{rid}', '{pid}');
            """)

    # ═════════════════════════════════════════════════════════════════════
    # 7. SEED — 5 SoD rules
    # ═════════════════════════════════════════════════════════════════════
    for code, desc, action_a, action_b, scope, escalate_to in SOD_RULES:
        sid = SOD_IDS[code]
        desc_escaped = desc.replace("'", "''")
        esc_sql = f"'{escalate_to}'" if escalate_to else "NULL"
        op.execute(f"""
            INSERT INTO sod_rule (id, code, description, action_a, action_b,
                                  scope, escalate_to_role)
            VALUES ('{sid}', '{code}', '{desc_escaped}',
                    '{action_a}', '{action_b}', '{scope}', {esc_sql});
        """)


def downgrade() -> None:
    # Drop triggers
    op.execute(
        "DROP TRIGGER IF EXISTS trg_audit_trail_immutable ON audit_trail;"
    )
    op.execute("DROP FUNCTION IF EXISTS gfi_audit_immutable();")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_user_role_updated_at ON user_role;"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_user_role_no_delete ON user_role;"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_auth_user_updated_at ON auth_user;"
    )

    # Drop tables
    op.drop_table("sod_rule")
    op.drop_table("audit_trail")
    op.drop_table("user_role")
    op.drop_table("role_permission")
    op.drop_table("permission")
    op.drop_table("role")

    # Remove added auth_user columns
    for col in ("updated_at", "must_change_password", "locked_until",
                "failed_login_attempts", "last_login", "password_hash",
                "full_name", "email"):
        op.drop_column("auth_user", col)
