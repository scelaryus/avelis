"""Core SQLAlchemy models — the tables that ALL other modules depend on."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    Column, String, Boolean, Integer, Numeric, DateTime, Date, ForeignKey,
    Text, CheckConstraint, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)

def new_uuid():
    return uuid.uuid4()


# ── Company (12 legal entities) ──────────────────────────────────────────────

class Company(Base):
    __tablename__ = "company"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    code = Column(String(20), unique=True, nullable=False, index=True)
    legal_name = Column(String(200), nullable=False)
    legal_form = Column(String(10), nullable=False)  # ETS, SARL, EURL, SCI
    nif = Column(String(30), nullable=True)
    rc = Column(String(30), nullable=True)
    status = Column(String(30), nullable=False, default="ACTIF")
    fiscal_regime = Column(String(20), default="REEL")
    ibs_rate = Column(Numeric(5, 2), nullable=True)
    tap_rate = Column(Numeric(5, 2), nullable=True)
    cnas_regime = Column(String(10), nullable=True)  # GENERAL or BTPH
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    is_deleted = Column(Boolean, default=False)
    version = Column(Integer, default=1)

    projects = relationship("Project", back_populates="company")
    ownership_rows = relationship("EntrepriseAssocie", back_populates="company")


# ── Associate (9 people) ────────────────────────────────────────────────────

class Associate(Base):
    __tablename__ = "associate"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    canonical_name = Column(String(100), nullable=False, unique=True)
    is_founder = Column(Boolean, default=False)
    role = Column(String(50), nullable=True)
    associate_type = Column(String(20), default="INTERNAL")  # INTERNAL, EXTERNAL
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


# ── EntrepriseAssocie (company ownership %) ──────────────────────────────────

class EntrepriseAssocie(Base):
    __tablename__ = "entreprise_associe"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    associate_id = Column(UUID(as_uuid=True), ForeignKey("associate.id"), nullable=False)
    percentage = Column(Numeric(7, 4), nullable=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    company = relationship("Company", back_populates="ownership_rows")
    associate = relationship("Associate")

    __table_args__ = (
        UniqueConstraint("company_id", "associate_id", name="uq_company_associate"),
    )


# ── Project (16 projects) ───────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "project"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    code = Column(String(30), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    status = Column(String(30), nullable=False, default="ACTIF")
    client_count = Column(Integer, nullable=True)
    terrain_cost_estimate = Column(Numeric(15, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    is_deleted = Column(Boolean, default=False)

    company = relationship("Company", back_populates="projects")
    ownership_rows = relationship("PartProjet", back_populates="project")


# ── PartProjet (project ownership %) ────────────────────────────────────────

class PartProjet(Base):
    __tablename__ = "part_projet"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    associate_id = Column(UUID(as_uuid=True), ForeignKey("associate.id"), nullable=False)
    percentage = Column(Numeric(7, 4), nullable=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    project = relationship("Project", back_populates="ownership_rows")
    associate = relationship("Associate")

    __table_args__ = (
        UniqueConstraint("project_id", "associate_id", name="uq_project_associate"),
    )


# ── Alias ───────────────────────────────────────────────────────────────────

class Alias(Base):
    __tablename__ = "alias"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    alias_text = Column(String(200), nullable=False, index=True)
    canonical_type = Column(String(20), nullable=False)  # PROJECT, ASSOCIATE, COMPANY
    canonical_code = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("alias_text", "canonical_type", name="uq_alias_type"),
    )


# ── Lot (EDD inventory) ────────────────────────────────────────────────────

class Lot(Base):
    __tablename__ = "lot"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False)
    ref = Column(String(30), unique=True, nullable=False, index=True)
    typology = Column(String(20), nullable=False)  # F2, F3, F4, F5, Duplex, etc.
    surface = Column(Numeric(8, 2), nullable=False)
    floor = Column(Integer, default=0)
    block = Column(String(5))
    orientation = Column(String(10))
    status = Column(String(20), nullable=False, default="DISPONIBLE")
    rf1_price = Column(Numeric(15, 2), nullable=False)
    rf2_price = Column(Numeric(15, 2), default=0)
    locked_by = Column(String(100), nullable=True)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    is_deleted = Column(Boolean, default=False)


# ── Pricing Tier ────────────────────────────────────────────────────────────

class PricingTier(Base):
    __tablename__ = "pricing_tier"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False)
    typology = Column(String(20), nullable=False)
    palier_label = Column(String(10), nullable=False, default="30%")
    palier_min = Column(Integer, nullable=False)
    palier_max = Column(Integer, nullable=False)
    discount_pct = Column(Numeric(5, 2), nullable=False, default=0)
    is_active = Column(Boolean, default=True)
    created_by = Column(String(100))
    updated_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("project_id", "typology", "palier_label", name="uq_pricing_tier_label"),
    )


# ── AuthUser ────────────────────────────────────────────────────────────────

class AuthUser(Base):
    __tablename__ = "auth_user"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    email = Column(String(200), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    full_name = Column(String(200), nullable=False)
    role = Column(String(50), nullable=False)
    has_rf2_access = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


# ── Employee ────────────────────────────────────────────────────────────────

class Employee(Base):
    __tablename__ = "employee"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    matricule = Column(String(30), unique=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    department = Column(String(100))
    position = Column(String(100))
    status = Column(String(20), default="ACTIVE")
    hire_date = Column(DateTime(timezone=True))
    salary_base = Column(Numeric(12, 2))
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


# ── Payslip ─────────────────────────────────────────────────────────────────

class Payslip(Base):
    __tablename__ = "payslip"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False)
    period = Column(String(7), nullable=False)  # YYYY-MM
    # Gross components
    salary_base = Column(Numeric(12, 2), nullable=False)
    prime_rendement = Column(Numeric(12, 2), default=0)
    prime_nuisance = Column(Numeric(12, 2), default=0)
    indemnite_transport = Column(Numeric(12, 2), default=0)
    heures_sup_amount = Column(Numeric(12, 2), default=0)
    gross = Column(Numeric(12, 2), nullable=False)
    # Deductions
    cnas_employee = Column(Numeric(12, 2), nullable=False)
    cnas_rate = Column(Numeric(6, 4), nullable=False)  # 9 or 9.375
    taxable = Column(Numeric(12, 2), nullable=False)
    irg_brut = Column(Numeric(12, 2), default=0)
    irg_abatement = Column(Numeric(12, 2), default=0)
    irg_final = Column(Numeric(12, 2), default=0)
    other_deductions = Column(Numeric(12, 2), default=0)
    net = Column(Numeric(12, 2), nullable=False)
    # Employer
    cnas_employer = Column(Numeric(12, 2), nullable=False)
    cnas_employer_rate = Column(Numeric(6, 4), nullable=False)
    formation = Column(Numeric(12, 2), default=0)
    apprentissage = Column(Numeric(12, 2), default=0)
    employer_total = Column(Numeric(12, 2), nullable=False)
    # Status
    status = Column(String(20), default="CALCULATED")
    verified_l1 = Column(String(10), default="PENDING")
    verified_l2 = Column(String(10), default="PENDING")
    verified_l3 = Column(String(10), default="PENDING")
    verified_l4 = Column(String(10), default="PENDING")
    verified_l5 = Column(String(10), default="PENDING")
    verified_l6 = Column(String(10), default="PENDING")
    approved_by = Column(String(100))
    rejected_reason = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)

    employee = relationship("Employee")


# ── Leave Request ───────────────────────────────────────────────────────────

class LeaveRequest(Base):
    __tablename__ = "leave_request"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False)
    leave_type = Column(String(20), nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    days = Column(Integer, nullable=False)
    justification = Column(Text)
    certificate_doc_id = Column(String(100))
    status = Column(String(20), default="EN_ATTENTE")
    approved_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)

    employee = relationship("Employee")


# ── DossierADV ──────────────────────────────────────────────────────────────

class DossierADV(Base):
    __tablename__ = "dossier_adv"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    numero = Column(String(30), unique=True, nullable=False)
    client_name = Column(String(200), nullable=False)
    lot_id = Column(UUID(as_uuid=True), ForeignKey("lot.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False)
    type_paiement = Column(String(30), nullable=False)
    prix_rf1 = Column(Numeric(15, 2), nullable=False)
    prix_rf2 = Column(Numeric(15, 2), default=0)
    status = Column(String(30), default="PRE_RESERVE")
    rf2_status = Column(String(30), default="NON_SECURISE")
    montant_rf2_securise = Column(Numeric(15, 2), default=0)
    agent_commercial_id = Column(UUID(as_uuid=True), ForeignKey("employee.id"), nullable=True)
    created_by_user = Column(String(200))
    # Tier pricing
    tier_engagement_pct = Column(Integer)  # 30, 50, 70, or 100
    tier_discount_pct = Column(Numeric(5, 2), default=0)
    prix_base_rf1 = Column(Numeric(15, 2))  # original RF1 before discount
    prix_base_rf2 = Column(Numeric(15, 2))  # original RF2 before discount
    prix_base_reel = Column(Numeric(15, 2))  # original total before discount
    tier_locked = Column(Boolean, default=False)
    tier_locked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    is_deleted = Column(Boolean, default=False)

    lot = relationship("Lot")
    project = relationship("Project")
    payments = relationship("Payment", back_populates="dossier")


# ── Payment ─────────────────────────────────────────────────────────────────

class Payment(Base):
    __tablename__ = "payment"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    dossier_id = Column(UUID(as_uuid=True), ForeignKey("dossier_adv.id"), nullable=False)
    type_rf = Column(String(5), nullable=False)  # RF1, RF2
    mode_reglement = Column(String(20), nullable=False)
    montant = Column(Numeric(15, 2), nullable=False)
    reference = Column(String(100))
    status = Column(String(20), default="EN_ATTENTE")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)

    dossier = relationship("DossierADV", back_populates="payments")

    __table_args__ = (
        CheckConstraint(
            "(type_rf = 'RF1' AND mode_reglement IN ('CHEQUE','VIREMENT','CHEQUE_NOTAIRE')) OR "
            "(type_rf = 'RF2' AND mode_reglement = 'ESPECES')",
            name="ck_payment_rf_mode"
        ),
    )


# ── CCA ─────────────────────────────────────────────────────────────────────

class CcaAccount(Base):
    __tablename__ = "cca_account"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    associate_id = Column(UUID(as_uuid=True), ForeignKey("associate.id"), nullable=False)
    balance = Column(Numeric(15, 2), default=0)
    is_deleted = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("company_id", "associate_id", name="uq_cca_company_associate"),
    )


# ── CCA Movement ────────────────────────────────────────────────────────────

class CcaMovement(Base):
    __tablename__ = "cca_movement"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    associate_id = Column(UUID(as_uuid=True), ForeignKey("associate.id"), nullable=False)
    cca_account_id = Column(UUID(as_uuid=True), ForeignKey("cca_account.id"), nullable=False)
    type = Column(String(20), nullable=False)  # DEPOT, RETRAIT, CFF, DISTRIBUTION, PRELEV
    montant = Column(Numeric(15, 2), nullable=False)  # positive=credit, negative=debit
    label = Column(String(300))
    project_code = Column(String(30), nullable=True)
    justificative_doc_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    created_by = Column(String(100))
    is_deleted = Column(Boolean, default=False)


# ── CFF Record ──────────────────────────────────────────────────────────────

class CffRecord(Base):
    __tablename__ = "cff_record"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    emitter_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    receiver_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=True)
    montant_ht = Column(Numeric(15, 2), nullable=False)
    tva = Column(Numeric(15, 2), nullable=False)
    tap = Column(Numeric(15, 2), nullable=False)
    ibs_base = Column(Numeric(15, 2), nullable=False)
    ibs = Column(Numeric(15, 2), nullable=False)
    stamp_duty = Column(Numeric(15, 2), nullable=False)
    cff_total = Column(Numeric(15, 2), nullable=False)
    invoice_date = Column(DateTime(timezone=True))
    status = Column(String(20), default="CALCULE")  # CALCULE, IMPUTE, BLOQUE
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


class CffImputation(Base):
    __tablename__ = "cff_imputation"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    cff_record_id = Column(UUID(as_uuid=True), ForeignKey("cff_record.id"), nullable=False)
    associate_id = Column(UUID(as_uuid=True), ForeignKey("associate.id"), nullable=False)
    percentage = Column(Numeric(7, 4), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


# ── Closed Period ───────────────────────────────────────────────────────────

class ClosedPeriod(Base):
    __tablename__ = "closed_period"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    period = Column(String(7), nullable=False)  # YYYY-MM
    status = Column(String(20), default="OUVERTE")  # OUVERTE, EN_COURS, CLOTUREE
    step_completed = Column(Integer, default=0)
    sha256_hash = Column(String(64), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    closed_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("company_id", "period", name="uq_closed_period"),
    )


# ── GACEB Advance ───────────────────────────────────────────────────────────

class GacebAdvance(Base):
    __tablename__ = "gaceb_advance"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False)
    initial_amount = Column(Numeric(15, 2), nullable=False)
    deducted_amount = Column(Numeric(15, 2), default=0)
    residual = Column(Numeric(15, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


# ── Cost Center Node ─────────────────────────────────────────────────────────

# ── HrCommission (already referenced by adv.py) ─────────────────────────────
# Defined further down if not already present


# ── Credit Tier (5 disbursement tiers per credit dossier) ─────────────────────

class CreditTierC(Base):
    __tablename__ = "credit_tier_c"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    dossier_id = Column(UUID(as_uuid=True), ForeignKey("dossier_adv.id"), nullable=False)
    tier_number = Column(Integer, nullable=False)  # 0,1,2,3,4
    tier_label = Column(String(30), nullable=False)
    percentage = Column(Numeric(5, 2), nullable=False)
    montant = Column(Numeric(15, 2), nullable=False)
    routing = Column(String(20), nullable=False)  # VIA_NOTAIRE or DIRECT
    status = Column(String(20), default="EN_ATTENTE")
    expert_report_id = Column(UUID(as_uuid=True), nullable=True)
    wire_order_id = Column(UUID(as_uuid=True), nullable=True)
    request_submitted_at = Column(DateTime(timezone=True), nullable=True)
    wire_received_at = Column(DateTime(timezone=True), nullable=True)
    debloque_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


# ── Expert Report ─────────────────────────────────────────────────────────────

class ExpertReportC(Base):
    __tablename__ = "expert_report_c"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    dossier_id = Column(UUID(as_uuid=True), ForeignKey("dossier_adv.id"), nullable=False)
    tier_percentage = Column(Numeric(5, 2), nullable=False)  # 15, 35, 25
    expert_name = Column(String(255), nullable=False)
    report_date = Column(Date, nullable=False)
    completion_pct = Column(Numeric(5, 2), nullable=True)
    conformity = Column(Boolean, nullable=True)
    observations = Column(Text, nullable=True)
    document_url = Column(Text, nullable=True)
    status = Column(String(20), default="RECU")  # RECU, VALIDE, REJETE
    validated_by = Column(String(100), nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


# ── Wire Transfer Order ───────────────────────────────────────────────────────

class WireTransferOrderC(Base):
    __tablename__ = "wire_transfer_order_c"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    dossier_id = Column(UUID(as_uuid=True), ForeignKey("dossier_adv.id"), nullable=False)
    tier_percentage = Column(Numeric(5, 2), nullable=False)  # 15, 35, 25
    montant = Column(Numeric(15, 2), nullable=False)
    status = Column(String(20), default="EN_ATTENTE")  # EN_ATTENTE, SIGNE, EXECUTE
    signature_date = Column(Date, nullable=True)
    scan_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


# ── Echeancier (installment schedule) ─────────────────────────────────────────

class EcheancierC(Base):
    __tablename__ = "echeancier_c"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    dossier_id = Column(UUID(as_uuid=True), ForeignKey("dossier_adv.id"), nullable=False)
    solde_rf1 = Column(Numeric(15, 2), nullable=False)
    date_engagement = Column(Date, nullable=False)
    date_livraison_prevue = Column(Date, nullable=False)
    duree_mois = Column(Integer, nullable=False)
    frequence = Column(String(20), default="MENSUEL")
    nb_echeances = Column(Integer, nullable=False)
    montant_echeance = Column(Numeric(15, 2), nullable=False)
    montant_derniere = Column(Numeric(15, 2), nullable=False)
    taux_penalite_annuel = Column(Numeric(5, 2), default=Decimal("5.00"))
    status = Column(String(20), default="ACTIF")  # ACTIF, TERMINE, DEFAUT
    total_paye = Column(Numeric(15, 2), default=0)
    total_penalites = Column(Numeric(15, 2), default=0)
    nb_retards = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


class EcheanceC(Base):
    __tablename__ = "echeance_c"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    echeancier_id = Column(UUID(as_uuid=True), ForeignKey("echeancier_c.id"), nullable=False)
    numero = Column(Integer, nullable=False)
    date_echeance = Column(Date, nullable=False)
    montant = Column(Numeric(15, 2), nullable=False)
    status = Column(String(20), default="A_VENIR")  # A_VENIR, DUE, PAYEE, EN_RETARD, DEFAUT
    date_paiement = Column(Date, nullable=True)
    montant_paye = Column(Numeric(15, 2), nullable=True)
    payment_id = Column(UUID(as_uuid=True), nullable=True)
    jours_retard = Column(Integer, default=0)
    penalite_montant = Column(Numeric(15, 2), default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


# ── Notary Escrow ─────────────────────────────────────────────────────────────

class NotaryEscrowC(Base):
    __tablename__ = "notary_escrow_c"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=False)
    notaire_name = Column(String(255), nullable=True)
    solde_transitoire = Column(Numeric(15, 2), default=0)
    expected_5pct_reserve = Column(Numeric(15, 2), default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


class EscrowMovementC(Base):
    __tablename__ = "escrow_movement_c"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    escrow_id = Column(UUID(as_uuid=True), ForeignKey("notary_escrow_c.id"), nullable=False)
    dossier_id = Column(UUID(as_uuid=True), ForeignKey("dossier_adv.id"), nullable=True)
    movement_date = Column(DateTime(timezone=True), nullable=False)
    movement_type = Column(String(10), nullable=False)  # CREDIT or DEBIT
    montant = Column(Numeric(15, 2), nullable=False)
    balance_after = Column(Numeric(15, 2), nullable=False)
    source = Column(String(255), nullable=True)
    destination = Column(String(255), nullable=True)
    motif = Column(String(30), nullable=False)
    reference_cheque = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


# ── Dossier Transition Log (audit trail) ──────────────────────────────────────

class DossierTransitionLog(Base):
    __tablename__ = "dossier_transition_log"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    dossier_id = Column(UUID(as_uuid=True), ForeignKey("dossier_adv.id"), nullable=False)
    from_status = Column(String(30), nullable=False)
    to_status = Column(String(30), nullable=False)
    triggered_by = Column(String(200), nullable=True)
    blockers_overridden = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


# ── Document Checklist Item ───────────────────────────────────────────────────

class DossierDocument(Base):
    __tablename__ = "dossier_document"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    dossier_id = Column(UUID(as_uuid=True), ForeignKey("dossier_adv.id"), nullable=False)
    document_type = Column(String(50), nullable=False)
    label = Column(String(200), nullable=False)
    source = Column(String(20), nullable=False)  # CLIENT, BANQUE, ENTREPRISE, NOTAIRE, EXPERT
    required = Column(Boolean, default=True)
    received = Column(Boolean, default=False)
    received_at = Column(DateTime(timezone=True), nullable=True)
    document_url = Column(Text, nullable=True)
    relance_count = Column(Integer, default=0)
    last_relance_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


# ── Storage Zone ──────────────────────────────────────────────────────────────

class StorageZone(Base):
    __tablename__ = "storage_zone"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    code = Column(String(30), nullable=False)
    label = Column(String(200), nullable=False)
    location = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_storage_zone_code"),
    )


# ── Stock Item ────────────────────────────────────────────────────────────────

class StockItem(Base):
    __tablename__ = "stock_item"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=True)
    zone_id = Column(UUID(as_uuid=True), ForeignKey("storage_zone.id"), nullable=True)
    # Identity
    code = Column(String(40), unique=True, nullable=False, index=True)
    barcode = Column(String(60), unique=True, nullable=False, index=True)
    name = Column(String(300), nullable=False)
    category = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    # AI-detected fields
    ai_detected_name = Column(String(300), nullable=True)
    ai_confidence = Column(Numeric(5, 2), nullable=True)
    image_url = Column(Text, nullable=True)
    # Quantities
    quantity = Column(Numeric(12, 2), nullable=False, default=0)
    unit = Column(String(20), nullable=False, default="UNITE")
    unit_price = Column(Numeric(15, 2), nullable=False, default=0)
    total_value = Column(Numeric(15, 2), nullable=False, default=0)
    # Status
    status = Column(String(20), default="ACTIF")
    min_stock_alert = Column(Numeric(12, 2), nullable=True)
    created_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    is_deleted = Column(Boolean, default=False)


# ── Stock Movement (in/out tracking) ──────────────────────────────────────────

class StockMovement(Base):
    __tablename__ = "stock_movement"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    item_id = Column(UUID(as_uuid=True), ForeignKey("stock_item.id"), nullable=False)
    movement_type = Column(String(10), nullable=False)  # ENTREE, SORTIE, AJUSTEMENT
    quantity = Column(Numeric(12, 2), nullable=False)
    unit_price = Column(Numeric(15, 2), nullable=True)
    total_value = Column(Numeric(15, 2), nullable=True)
    reason = Column(String(200), nullable=True)
    created_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


# ── Supplier (Fournisseur) ────────────────────────────────────────────────────

class Supplier(Base):
    __tablename__ = "supplier"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    code = Column(String(30), unique=True, nullable=False)
    name = Column(String(300), nullable=False)
    contact_name = Column(String(200), nullable=True)
    phone = Column(String(30), nullable=True)
    email = Column(String(200), nullable=True)
    address = Column(Text, nullable=True)
    nif = Column(String(30), nullable=True)
    rc = Column(String(30), nullable=True)
    rib = Column(String(30), nullable=True)
    bank_name = Column(String(100), nullable=True)
    category = Column(String(50), nullable=True)  # MATERIAUX, SERVICES, EQUIPEMENT, etc.
    status = Column(String(20), default="ACTIF")
    total_contracts = Column(Numeric(15, 2), default=0)
    total_paid = Column(Numeric(15, 2), default=0)
    total_remaining = Column(Numeric(15, 2), default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    is_deleted = Column(Boolean, default=False)


class SupplierContract(Base):
    __tablename__ = "supplier_contract"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("supplier.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=True)
    contract_number = Column(String(50), unique=True, nullable=False)
    label = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    montant_ht = Column(Numeric(15, 2), nullable=False)
    tva_rate = Column(Numeric(5, 2), default=Decimal("19.00"))
    montant_tva = Column(Numeric(15, 2), nullable=False)
    montant_ttc = Column(Numeric(15, 2), nullable=False)
    date_signature = Column(Date, nullable=True)
    date_debut = Column(Date, nullable=True)
    date_fin = Column(Date, nullable=True)
    status = Column(String(20), default="ACTIF")  # BROUILLON, ACTIF, TERMINE, RESILIE
    total_paid = Column(Numeric(15, 2), default=0)
    remaining = Column(Numeric(15, 2), nullable=True)
    # Stock items delivered under this contract
    stock_items_received = Column(Integer, default=0)
    stock_value_received = Column(Numeric(15, 2), default=0)
    created_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    is_deleted = Column(Boolean, default=False)


class SupplierPayment(Base):
    __tablename__ = "supplier_payment"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("supplier.id"), nullable=False)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("supplier_contract.id"), nullable=True)
    montant = Column(Numeric(15, 2), nullable=False)
    mode_reglement = Column(String(20), nullable=False)  # CHEQUE, VIREMENT, ESPECES
    reference = Column(String(100), nullable=True)
    date_paiement = Column(Date, nullable=False)
    status = Column(String(20), default="ENCAISSE")  # EN_ATTENTE, ENCAISSE, REJETE
    observations = Column(Text, nullable=True)
    proof_url = Column(Text, nullable=True)
    created_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


class CostCenterNode(Base):
    __tablename__ = "cost_center_node"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("cost_center_node.id"), nullable=True)
    code = Column(String(80), unique=True, nullable=False, index=True)
    label = Column(String(200), nullable=False)
    level = Column(Integer, nullable=False, default=0)  # 0=groupe, 1=entity, 2=project, 3=category
    categorie = Column(String(30), nullable=True)  # CC1-CC16
    montant_rf1 = Column(Numeric(15, 2), default=0)
    montant_rf2 = Column(Numeric(15, 2), default=0)
    montant_rf3 = Column(Numeric(15, 2), default=0)
    montant_rf4 = Column(Numeric(15, 2), default=0)
    montant_total = Column(Numeric(15, 2), default=0)
    impact_tresorerie = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


class CostCenterEntry(Base):
    __tablename__ = "cost_center_entry"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    node_id = Column(UUID(as_uuid=True), ForeignKey("cost_center_node.id"), nullable=False)
    rf_type = Column(String(5), nullable=False)  # RF1, RF2, RF3, RF4
    montant = Column(Numeric(15, 2), nullable=False)
    label = Column(String(300))
    source_type = Column(String(30))  # FACTURE, SITUATION, PAIE, CFF, CCA
    source_doc_id = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


# ── Accounting (Journal, Entries, Bank) ────────────────────────────────────────

class AccountSCF(Base):
    __tablename__ = "account"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    code = Column(String(10), unique=True, nullable=False)
    label = Column(String(200), nullable=False)
    account_class = Column(Integer, nullable=False)
    detail = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class JournalC(Base):
    __tablename__ = "journal"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    code = Column(String(10), nullable=False)
    label = Column(String(100), nullable=False)
    journal_type = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


class JournalEntryC(Base):
    __tablename__ = "journal_entry"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    journal_id = Column(UUID(as_uuid=True), ForeignKey("journal.id"), nullable=False)
    entry_number = Column(String(30), nullable=False)
    entry_date = Column(Date, nullable=False)
    label = Column(String(300), nullable=False)
    rf_type = Column(String(5), default="RF1")
    total_debit = Column(Numeric(15, 2), default=0)
    total_credit = Column(Numeric(15, 2), default=0)
    status = Column(String(20), default="DRAFT")
    source_document_type = Column(String(50), nullable=True)
    source_document_id = Column(String(100), nullable=True)
    period = Column(String(7), nullable=True)
    created_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


class JournalEntryLineC(Base):
    __tablename__ = "journal_entry_line"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    entry_id = Column(UUID(as_uuid=True), ForeignKey("journal_entry.id"), nullable=False)
    account_code = Column(String(10), nullable=False)
    label = Column(String(300), nullable=True)
    debit = Column(Numeric(15, 2), default=0)
    credit = Column(Numeric(15, 2), default=0)
    tiers_name = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


class BankStatementC(Base):
    __tablename__ = "bank_statement"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    bank_name = Column(String(100), nullable=False)
    account_number = Column(String(30), nullable=True)
    period = Column(String(7), nullable=False)
    opening_balance = Column(Numeric(15, 2), default=0)
    closing_balance = Column(Numeric(15, 2), default=0)
    total_debit = Column(Numeric(15, 2), default=0)
    total_credit = Column(Numeric(15, 2), default=0)
    movements_count = Column(Integer, default=0)
    matched_count = Column(Integer, default=0)
    status = Column(String(20), default="IMPORTED")
    uploaded_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


class BankMovementC(Base):
    __tablename__ = "bank_movement"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    statement_id = Column(UUID(as_uuid=True), ForeignKey("bank_statement.id"), nullable=False)
    movement_date = Column(Date, nullable=False)
    label = Column(String(300), nullable=False)
    reference = Column(String(100), nullable=True)
    debit = Column(Numeric(15, 2), default=0)
    credit = Column(Numeric(15, 2), default=0)
    balance_after = Column(Numeric(15, 2), nullable=True)
    reconciled = Column(Boolean, default=False)
    matched_payment_id = Column(String(100), nullable=True)
    matched_entry_id = Column(String(100), nullable=True)
    match_confidence = Column(Numeric(5, 2), nullable=True)
    match_method = Column(String(20), nullable=True)
    reconciled_by = Column(String(200), nullable=True)
    reconciled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


class GacebSituation(Base):
    __tablename__ = "gaceb_situation"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    advance_id = Column(UUID(as_uuid=True), ForeignKey("gaceb_advance.id"), nullable=False)
    num = Column(Integer, nullable=False)
    brut = Column(Numeric(15, 2), nullable=False)
    deduction = Column(Numeric(15, 2), default=0)
    net = Column(Numeric(15, 2), nullable=False)
    solde_after = Column(Numeric(15, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)


# ── Audit Trail (APPEND-ONLY) ───────────────────────────────────────────────

class AuditTrail(Base):
    __tablename__ = "audit_trail"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=True)
    user_id = Column(String(100), nullable=False)
    user_role = Column(String(50))
    action = Column(String(30), nullable=False)  # CREATE, UPDATE, DELETE, APPROVE, REJECT, LOGIN
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100))
    module = Column(String(30))
    data_before = Column(JSONB, nullable=True)
    data_after = Column(JSONB, nullable=True)
    ip_address = Column(String(45))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    # NO updated_at, NO is_deleted — this table is IMMUTABLE


# ── Document (GED) ──────────────────────────────────────────────────────────

class Document(Base):
    __tablename__ = "document"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=True)
    filename = Column(String(300), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)
    file_hash = Column(String(64), nullable=True)  # SHA-256 for dedup
    doc_type = Column(String(50), nullable=True)  # facture, contrat, pv, situation, etc.
    entity_code = Column(String(20))
    project_code = Column(String(30))
    extracted_text = Column(Text, nullable=True)
    extracted_metadata = Column(JSONB, nullable=True)
    pipeline_status = Column(String(20), default="UPLOADED")  # UPLOADED, OCR, CLASSIFIED, INDEXED
    pipeline_layer = Column(Integer, default=1)
    uploaded_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=utcnow)
    is_deleted = Column(Boolean, default=False)

    __table_args__ = (
        Index("ix_document_hash", "file_hash"),
        Index("ix_document_type", "doc_type"),
    )


# ── Document Registry (DIS — Document Intelligence System) ─────────────────

class DocumentRegistry(Base):
    """Full document registry per CDC-GFI-GED-001. One row per archived document."""
    __tablename__ = "document_registry"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=True)
    # Canonical path: /GD/{entite}/{doc_type}/{projet}/{annee}/{mois}/{ref}.{ext}
    canonical_path = Column(String(500), unique=True, nullable=True)
    storage_url = Column(String(500))
    file_name_original = Column(String(300), nullable=False)
    sha256_hash = Column(String(64), unique=True, nullable=True)
    size_bytes = Column(Integer, default=0)
    mime_type = Column(String(100))
    # Classification fields
    doc_type = Column(String(30))  # FACTURE_FOURNISSEUR, CONTRAT, PLAN_TECHNIQUE, etc.
    entite = Column(String(20))  # ETS-DK, SARL-DP, GROUPE, etc.
    projet = Column(String(30))  # AUREA, IRENE, EDEN, GROUPE, etc.
    annee = Column(Integer)
    mois = Column(Integer)
    reference_doc = Column(String(120))
    tiers = Column(String(200))
    montant_da = Column(Numeric(15, 2))
    montant_devise = Column(Numeric(15, 2))
    devise = Column(String(3))  # EUR, USD, CNY
    tags = Column(JSONB, default=[])
    resume = Column(Text)
    confidence_scores = Column(JSONB)  # {"doc_type": 0.97, "entite": 0.91, ...}
    # Pipeline status
    status = Column(String(20), default="PENDING")  # PENDING, EXTRACTING, CLASSIFYING, AWAITING_REVIEW, ARCHIVED, QUARANTINE, DRAFT
    ingested_at = Column(DateTime(timezone=True), default=utcnow)
    archived_at = Column(DateTime(timezone=True))
    ingested_by = Column(String(100))
    validated_by = Column(String(100))
    # Content
    raw_text_excerpt = Column(Text)  # first 2000 chars for full-text search
    extracted_text_full = Column(Text)  # full extracted text
    metadata_raw = Column(JSONB)  # EXIF, Office props, IFC header, etc.
    parent_folder_hint = Column(String(300))
    ocr_quality_flag = Column(Boolean, default=False)
    ocr_confidence = Column(Numeric(5, 2))
    # Versioning
    version_of = Column(UUID(as_uuid=True), ForeignKey("document_registry.id"), nullable=True)
    is_latest = Column(Boolean, default=True)
    # Context
    entite_secondaire = Column(String(20))  # for inter-entity documents
    context_hint = Column(Text)  # extra context from uploader or email subject
    priority = Column(String(10), default="NORMAL")  # URGENT, NORMAL, BULK
    # Job tracking
    job_id = Column(String(100))
    processing_time_ms = Column(Integer)
    retry_count = Column(Integer, default=0)
    error_log = Column(Text)

    __table_args__ = (
        Index("ix_docr_hash", "sha256_hash"),
        Index("ix_docr_entite", "entite"),
        Index("ix_docr_projet", "projet"),
        Index("ix_docr_doctype", "doc_type"),
        Index("ix_docr_annee", "annee"),
        Index("ix_docr_status", "status"),
        Index("ix_docr_tiers", "tiers"),
    )


# ── Notification ────────────────────────────────────────────────────────────

class Notification(Base):
    __tablename__ = "notification"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id = Column(String(100), nullable=False)
    title = Column(String(300), nullable=False)
    message = Column(Text)
    module = Column(String(30))
    link = Column(String(300))
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)


# ── SPI (Score de Performance Integre) ─────────────────────────────────────

class SpiProfile(Base):
    __tablename__ = "hr_spi_profile"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee.id"), unique=True, nullable=False)
    taux_prime = Column(Numeric(5, 2), default=20)  # 15-30% of salary_base
    role_type = Column(String(20), nullable=False, default="SUPPORT")  # COMMERCIAL, OPERATIONNEL, TECHNIQUE, MANAGEMENT, SUPPORT
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    employee = relationship("Employee")


class SpiObjective(Base):
    __tablename__ = "hr_spi_objective"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    spi_profile_id = Column(UUID(as_uuid=True), ForeignKey("hr_spi_profile.id"), nullable=False)
    period = Column(String(7), nullable=False)  # YYYY-MM
    type = Column(String(15), nullable=False)  # QUANTITATIF, QUALITATIF
    title = Column(String(200), nullable=False)
    description = Column(Text)
    target_value = Column(Numeric(15, 2), nullable=False)
    unit = Column(String(20), default="score")
    weight = Column(Numeric(5, 2), nullable=False)  # weights per type must sum to 100
    source_module = Column(String(20))  # ADV, CC, STOCK, DRH, null=manual
    assigned_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=utcnow)


class SpiEvaluation(Base):
    __tablename__ = "hr_spi_evaluation"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    spi_profile_id = Column(UUID(as_uuid=True), ForeignKey("hr_spi_profile.id"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False)
    period = Column(String(7), nullable=False)
    quantitative_score = Column(Numeric(5, 2), default=0)
    qualitative_score = Column(Numeric(5, 2), default=0)
    spi_total = Column(Numeric(5, 2), default=0)  # 0.60 * quant + 0.40 * qual
    prime_rendement_calculated = Column(Numeric(15, 2), default=0)
    status = Column(String(20), default="BROUILLON")  # BROUILLON, EVALUE, VALIDE, CONTESTE
    evaluated_by = Column(String(100))
    evaluated_at = Column(DateTime(timezone=True))
    validated_by = Column(String(100))
    validated_at = Column(DateTime(timezone=True))
    employee_comment = Column(Text)
    manager_comment = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    employee = relationship("Employee")
    objective_results = relationship("SpiObjectiveResult", back_populates="evaluation")

    __table_args__ = (
        UniqueConstraint("employee_id", "period", name="uq_spi_eval_employee_period"),
    )


class SpiObjectiveResult(Base):
    __tablename__ = "hr_spi_objective_result"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    objective_id = Column(UUID(as_uuid=True), ForeignKey("hr_spi_objective.id"), nullable=False)
    evaluation_id = Column(UUID(as_uuid=True), ForeignKey("hr_spi_evaluation.id"), nullable=False)
    actual_value = Column(Numeric(15, 2), default=0)
    achievement_pct = Column(Numeric(6, 2), default=0)  # capped at 150
    weighted_score = Column(Numeric(6, 2), default=0)
    data_source = Column(String(15), default="MANUEL")  # AUTOMATIQUE, MANUEL
    proof_document_id = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=utcnow)

    evaluation = relationship("SpiEvaluation", back_populates="objective_results")
    objective = relationship("SpiObjective")


class HrCommission(Base):
    __tablename__ = "hr_commission"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee.id"), nullable=True)  # NULL until commercial claims it
    dossier_adv_id = Column(UUID(as_uuid=True), ForeignKey("dossier_adv.id"))
    period = Column(String(7), nullable=False)
    payment_mode = Column(String(20))
    chiffre_encaisse = Column(Numeric(15, 2), default=0)
    taux_commission = Column(Numeric(5, 2), default=0)
    commission_brute = Column(Numeric(15, 2), default=0)
    role_in_sale = Column(String(20))  # COMMERCIAL, MANAGER, EQUIPE
    distribution_pct = Column(Numeric(5, 2), default=0)
    commission_nette = Column(Numeric(15, 2), default=0)
    status = Column(String(15), default="EN_ATTENTE")  # EN_ATTENTE, SOUMIS, VALIDE, REFUSE, PAYE
    payslip_id = Column(UUID(as_uuid=True), ForeignKey("payslip.id"))
    proof_document_id = Column(String(200))  # proof of client acquisition
    claim_note = Column(Text)  # commercial's explanation
    created_at = Column(DateTime(timezone=True), default=utcnow)


# ── SPI 360 — Daily/Monthly/Config/Task/Deliverable ───────────────────────

class SpiConfig(Base):
    """Per-position SPI weight configuration. Custom weights override default 30/25/25/20."""
    __tablename__ = "hr_spi_config"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    job_position = Column(String(100), unique=True, nullable=False)
    pillar_weights = Column(JSONB, default={"planification": 30, "qualite": 25, "comportement": 25, "performance": 20})
    criteria = Column(JSONB)  # detailed criteria per pillar
    bonus_tiers = Column(JSONB)  # custom bonus tiers if different from global
    malus_tiers = Column(JSONB)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SpiDaily(Base):
    """One row per employee per day — the living SPI counter."""
    __tablename__ = "hr_spi_daily"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False)
    date = Column(Date, nullable=False)
    pillar_planification = Column(Numeric(6, 2), default=0)
    pillar_qualite = Column(Numeric(6, 2), default=0)
    pillar_comportement = Column(Numeric(6, 2), default=100)  # starts at 100, only deductions
    pillar_performance = Column(Numeric(6, 2), default=0)
    counter_bonus = Column(Integer, default=0)
    counter_malus = Column(Integer, default=0)
    spi_raw = Column(Numeric(6, 2), default=0)  # weighted sum of 4 pillars
    spi_adjusted = Column(Numeric(6, 2), default=0)  # spi_raw + counter
    spi_final = Column(Numeric(6, 2), default=0)
    tasks_completed = Column(Integer, default=0)
    deliverables_validated = Column(Integer, default=0)
    is_inactive_day = Column(Boolean, default=False)
    consecutive_inactive_days = Column(Integer, default=0)
    calculated_at = Column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("employee_id", "date", name="uq_spi_daily"),)


class SpiMonthly(Base):
    """Aggregated monthly SPI for payroll integration."""
    __tablename__ = "hr_spi_monthly"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False)
    period = Column(String(7), nullable=False)
    avg_spi = Column(Numeric(6, 2), default=0)
    min_spi = Column(Numeric(6, 2), default=0)
    max_spi = Column(Numeric(6, 2), default=0)
    days_counted = Column(Integer, default=0)
    days_inactive = Column(Integer, default=0)
    bonus_tier = Column(String(20))
    bonus_percentage = Column(Numeric(5, 2), default=0)
    bonus_amount = Column(Numeric(15, 2), default=0)
    malus_tier = Column(String(20))
    malus_percentage = Column(Numeric(5, 2), default=0)
    malus_amount = Column(Numeric(15, 2), default=0)
    salary_freeze_active = Column(Boolean, default=False)
    is_termination_candidate = Column(Boolean, default=False)
    validated_by = Column(String(100))
    status = Column(String(15), default="CALCULE")  # CALCULE, VALIDE, CONTESTE, PAYE
    created_at = Column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("employee_id", "period", name="uq_spi_monthly"),)


class SpiTask(Base):
    """Tasks tracked for SPI contribution. Requires dual validation."""
    __tablename__ = "hr_spi_task"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    date_assigned = Column(Date, nullable=False)
    date_due = Column(Date, nullable=False)
    date_completed = Column(Date)
    status = Column(String(20), default="ASSIGNEE")  # ASSIGNEE, EN_COURS, COMPLETEE, EN_RETARD, NON_REALISEE
    validation_algo = Column(String(10), default="PENDING")  # PENDING, PASS, FLAG, FAIL
    validation_algo_details = Column(JSONB)
    validation_manager = Column(String(10), default="PENDING")  # PENDING, VALIDE, REFUSE
    validation_manager_by = Column(String(100))
    validation_manager_at = Column(DateTime(timezone=True))
    counts_toward_spi = Column(Boolean, default=False)
    spi_points = Column(Numeric(6, 2), default=0)
    proof_document_id = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=utcnow)


class SpiDeliverable(Base):
    """Deliverables quality tracking for SPI Pillar 2."""
    __tablename__ = "hr_spi_deliverable"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False)
    title = Column(String(300), nullable=False)
    date_submitted = Column(Date, nullable=False)
    quality_status = Column(String(30), default="PENDING")  # VALIDE_SANS_RETOUR, VALIDE_AVEC_RETOUR, REFUSE_PUIS_CORRIGE, REFUSE_DEFINITIF
    quality_score = Column(Numeric(5, 2), default=0)  # 100, 70, 50, 0
    reviewer_id = Column(String(100))
    review_comment = Column(Text)
    proof_document_id = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=utcnow)


class MissionBonus(Base):
    """Mission mobility bonus — 2,000 DA/day if personal vehicle."""
    __tablename__ = "hr_mission_bonus"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False)
    date = Column(Date, nullable=False)
    uses_personal_vehicle = Column(Boolean, default=False)
    daily_bonus = Column(Numeric(10, 2), default=2000)
    validated_by = Column(String(100))
    status = Column(String(15), default="DECLARE")  # DECLARE, VALIDE, PAYE
    created_at = Column(DateTime(timezone=True), default=utcnow)


# ── Task Assignment Workflow ───────────────────────────────────────────────

class TaskNeed(Base):
    """DAF's daily description of what needs to be done."""
    __tablename__ = "task_need"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    submitted_by = Column(String(100), nullable=False)
    need_text = Column(Text, nullable=False)
    submitted_at = Column(DateTime(timezone=True), default=utcnow)
    decomposition_status = Column(String(15), default="SOUMIS")  # SOUMIS, DECOMPOSE, APPROUVE, REJETE
    decomposition_result = Column(JSONB)
    approved_by = Column(String(100))
    approved_at = Column(DateTime(timezone=True))


class TaskAssignment(Base):
    """Individual subtask from decomposition — the full negotiation + execution lifecycle."""
    __tablename__ = "task_assignment"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    need_id = Column(UUID(as_uuid=True), ForeignKey("task_need.id"), nullable=False)
    task_title = Column(String(300), nullable=False)
    task_description = Column(Text)
    expected_deliverable = Column(Text)
    complexity = Column(String(10), default="MOYEN")  # SIMPLE, MOYEN, COMPLEXE
    department = Column(String(50))
    required_skills = Column(JSONB)
    assigned_employee_id = Column(UUID(as_uuid=True), ForeignKey("employee.id"))
    assignment_reason = Column(Text)
    estimated_duration_hours = Column(Numeric(6, 2))
    estimated_bonus_da = Column(Numeric(10, 2))
    # Employee proposition
    employee_proposed_duration = Column(Numeric(6, 2))
    employee_proposed_bonus = Column(Numeric(10, 2))
    employee_proposed_at = Column(DateTime(timezone=True))
    employee_comment = Column(Text)
    # DAF response
    daf_response = Column(String(20))  # PENDING, ACCEPTED_EMPLOYEE, COUNTER, REJECTED
    daf_counter_bonus = Column(Numeric(10, 2))
    daf_responded_at = Column(DateTime(timezone=True))
    # Agreed terms
    agreed_bonus = Column(Numeric(10, 2))
    agreed_duration_hours = Column(Numeric(6, 2))
    deadline = Column(DateTime(timezone=True))
    accepted_at = Column(DateTime(timezone=True))
    # Status
    status = Column(String(25), default="PROPOSE")
    # Proof + AI validation
    proof_document_ids = Column(JSONB)
    completion_note = Column(Text)
    ai_match_score = Column(Numeric(5, 2))
    ai_explanation = Column(Text)
    ai_proposed_score = Column(Numeric(5, 2))
    ai_red_flags = Column(JSONB)
    ai_validated_at = Column(DateTime(timezone=True))
    # Finalization
    final_score = Column(Numeric(5, 2))
    final_score_justification = Column(Text)
    actual_payment = Column(Numeric(10, 2))
    finalized_by = Column(String(100))
    finalized_at = Column(DateTime(timezone=True))
    payslip_id = Column(UUID(as_uuid=True), ForeignKey("payslip.id"))
    spi_task_id = Column(UUID(as_uuid=True), ForeignKey("hr_spi_task.id"))
    created_at = Column(DateTime(timezone=True), default=utcnow)

    employee = relationship("Employee")
    need = relationship("TaskNeed")


class TaskNegotiationLog(Base):
    """Full negotiation history per task."""
    __tablename__ = "task_negotiation_log"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("task_assignment.id"), nullable=False)
    action = Column(String(40), nullable=False)
    actor_id = Column(String(100), nullable=False)
    details = Column(JSONB)
    timestamp = Column(DateTime(timezone=True), default=utcnow)


# ── Discipline ─────────────────────────────────────────────────────────────

class DisciplineCase(Base):
    """Tracks every infraction and sanction per employee. Full audit history."""
    __tablename__ = "discipline_case"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee.id"), nullable=False)
    # Infraction details (F-DIS-001)
    infraction_date = Column(Date, nullable=False)
    infraction_time = Column(String(10))
    infraction_location = Column(String(200))
    description = Column(Text, nullable=False)
    witnesses = Column(JSONB, default=[])  # list of witness names
    severity_declared = Column(String(15), nullable=False)  # MINEURE, MOYENNE, GRAVE
    evidence_document_ids = Column(JSONB, default=[])  # proof uploads
    # AI evaluation
    ai_severity = Column(String(15))  # AI-confirmed severity
    ai_sanction_suggested = Column(String(30))  # AVERTISSEMENT, BLAME, MISE_A_PIED, LICENCIEMENT
    ai_justification = Column(Text)
    ai_evaluated_at = Column(DateTime(timezone=True))
    # Convocation (F-DIS-002) — must be >= 48h after PV
    convocation_date = Column(DateTime(timezone=True))
    convocation_sent = Column(Boolean, default=False)
    # Audition (F-DIS-003)
    audition_date = Column(DateTime(timezone=True))
    audition_pv = Column(Text)
    audition_assistant_name = Column(String(200))
    audition_assistant_role = Column(String(100))
    # Decision
    sanction_applied = Column(String(30))  # final decision: AVERTISSEMENT, BLAME, MISE_A_PIED, LICENCIEMENT, CLASSEE_SANS_SUITE
    sanction_duration_days = Column(Integer)  # for MISE_A_PIED
    sanction_decided_by = Column(String(100))
    sanction_decided_at = Column(DateTime(timezone=True))
    sanction_comment = Column(Text)
    # Status
    status = Column(String(20), default="PV_CONSTAT")  # PV_CONSTAT, CONVOQUE, AUDITIONNE, DECIDE, CLOTURE
    # Workflow
    reported_by = Column(String(100), nullable=False)
    validated_by_drh = Column(String(100))
    validated_by_dg = Column(String(100))
    validated_by_pdg = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    employee = relationship("Employee")


# ── Legal Contract (tous contrats sauf employes — geres par RH) ────────────

class LegalContract(Base):
    __tablename__ = "legal_contract"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    name = Column(String(30), unique=True, nullable=False)  # CTR/YYYY/NNNNN
    contract_type = Column(String(20), nullable=False)  # fournisseur, client, partenariat, prestation, cadre, confidentialite
    title = Column(String(300), nullable=False)
    partner_name = Column(String(200))
    partner_nif = Column(String(20))
    partner_rc = Column(String(20))
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=True)
    # Dates
    date_start = Column(Date)
    date_end = Column(Date)
    renewal_type = Column(String(20), default="manuelle")  # automatique, manuelle, non_renouvelable
    renewal_notice_days = Column(Integer, default=60)
    # Financial
    amount_ht = Column(Numeric(15, 2), default=0)
    amount_ttc = Column(Numeric(15, 2), default=0)
    # Status
    status = Column(String(20), default="brouillon")  # brouillon, en_revue, valide, signe, actif, expire, resilie, archive
    # Compliance
    compliance_status = Column(String(20), default="non_evalue")  # conforme, non_conforme, en_cours_audit, non_evalue
    ai_risk_assessment = Column(Text)
    ai_extracted_clauses = Column(JSONB)
    # Clauses
    clauses = Column(JSONB, default=[])  # [{name, text, risk_level}]
    # Documents
    signed_document_id = Column(String(100))
    # Metadata
    created_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project = relationship("Project")


# ── Legal Case (Dossier Litige) ────────────────────────────────────────────

class LegalCase(Base):
    __tablename__ = "legal_case"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    company_id = Column(UUID(as_uuid=True), ForeignKey("company.id"), nullable=False)
    name = Column(String(30), unique=True, nullable=False)
    case_type = Column(String(30), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    stage = Column(String(30), default="ouvert")
    priority = Column(String(15), default="normal")
    partner_name = Column(String(200))
    partner_lawyer = Column(String(200))
    company_lawyer = Column(String(200))
    assigned_juriste = Column(String(100))
    assigned_manager = Column(String(100))
    # Proper FKs (audit fix NC-B2)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("legal_contract.id"), nullable=True)
    contract_ref = Column(String(100))  # denormalized for display
    invoice_ids = Column(JSONB, default=[])  # NC-B3: array of payment/invoice UUIDs
    payment_ids = Column(JSONB, default=[])
    invoice_ref = Column(String(100))
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employee.id"), nullable=True)  # for HR litigation
    employee_name = Column(String(200))  # denormalized
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), nullable=True)
    project_code = Column(String(30))  # denormalized
    amount_claimed = Column(Numeric(15, 2), default=0)
    amount_recovered = Column(Numeric(15, 2), default=0)
    cost_honoraires = Column(Numeric(15, 2), default=0)
    cost_frais_justice = Column(Numeric(15, 2), default=0)
    cost_expertise = Column(Numeric(15, 2), default=0)
    cost_total = Column(Numeric(15, 2), default=0)
    ai_risk_score = Column(Numeric(5, 2))
    ai_summary = Column(Text)
    ai_suggested_actions = Column(JSONB)
    result = Column(String(20), default="en_cours")
    result_comment = Column(Text)
    date_open = Column(Date, nullable=False)
    date_deadline = Column(Date)
    date_close = Column(Date)
    is_confidential = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    events = relationship("LegalCaseEvent", back_populates="legal_case", order_by="LegalCaseEvent.event_date.desc()")


class LegalCaseEvent(Base):
    __tablename__ = "legal_case_event"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    case_id = Column(UUID(as_uuid=True), ForeignKey("legal_case.id"), nullable=False)
    event_date = Column(DateTime(timezone=True), default=utcnow)
    event_type = Column(String(30), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    old_stage = Column(String(30))
    new_stage = Column(String(30))
    amount = Column(Numeric(15, 2))
    document_id = Column(String(100))
    created_by = Column(String(100))
    legal_case = relationship("LegalCase", back_populates="events")


# ── Legal AI Feedback (NC-E4) ──────────────────────────────────────────────

class LegalAiFeedback(Base):
    __tablename__ = "legal_ai_feedback"
    id = Column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    case_id = Column(UUID(as_uuid=True), ForeignKey("legal_case.id"), nullable=True)
    prediction_type = Column(String(30), nullable=False)  # risk_score, stage_suggestion, sanction
    predicted_value = Column(String(100))
    actual_value = Column(String(100))
    was_correct = Column(Boolean)
    feedback_by = Column(String(100))
    feedback_date = Column(DateTime(timezone=True), default=utcnow)
    comment = Column(Text)
