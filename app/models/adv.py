"""GFI Platform - ADV (Administration des Ventes) domain models."""
import uuid
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime, ForeignKey,
    Enum as SAEnum, Numeric, Date, JSON, func
)
from app.database import Base
import enum


class ContractStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    SUSPENDED = "SUSPENDED"


# ── Section 8: Lot lifecycle statuses ──────────────────────────────────────

class StatutLotADV(str, enum.Enum):
    DISPONIBLE = "DISPONIBLE"
    VERROUILLE = "VERROUILLE"      # 15-min commercial lock
    RESERVE = "RESERVE"             # SPOT payment received
    ENGAGE = "ENGAGE"               # Contract signed, RF2 secured
    VENDU = "VENDU"                 # 100% paid, keys delivered
    INDISPONIBLE = "INDISPONIBLE"   # Technical/legal hold
    DEFAUT_PAIEMENT = "DEFAUT_PAIEMENT"


class ModePaiement(str, enum.Enum):
    SPOT = "SPOT"
    CREDIT_BANCAIRE = "CREDIT_BANCAIRE"
    FONDS_PROPRES = "FONDS_PROPRES"


class StatutRF2(str, enum.Enum):
    NON_APPLICABLE = "NON_APPLICABLE"
    EN_ATTENTE = "EN_ATTENTE"
    SECURISE = "SECURISE"


# ── DossierVente — the complete sale lifecycle wrapper ─────────────────────

class DossierVente(Base):
    """Wraps the full sale lifecycle per lot — from reservation to delivery.

    Implements Section 8 of SPECIFICATION_GFI7_V3.1:
    - EX-ADV-001: DISPONIBLE → RÉSERVÉ → ENGAGÉ → VENDU
    - EX-ADV-002 (KT-07): RF2 blocking before engagement
    - EX-ADV-004: 30-day default payment detection
    """
    __tablename__ = "dossiers_vente"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=False)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=False)
    client_id = Column(String(36), ForeignKey("clients.id"))
    contract_id = Column(String(36), ForeignKey("contracts.id"))

    # Lot reference (links to EDD unit)
    lot_code = Column(String(100), nullable=False)
    unit_id = Column(String(36))  # FK to re_units if EDD is active

    # Lifecycle
    statut_lot = Column(SAEnum(StatutLotADV), default=StatutLotADV.DISPONIBLE, nullable=False)
    mode_paiement = Column(SAEnum(ModePaiement))

    # Pricing
    prix_vente_rf1 = Column(Numeric(18, 2), default=0)  # Official declared price
    prix_vente_rf2 = Column(Numeric(18, 2), default=0)  # Undeclared cash complement
    prix_total = Column(Numeric(18, 2), default=0)       # RF1 + RF2

    # RF2 tracking (R-004 / KT-07)
    statut_rf2 = Column(SAEnum(StatutRF2), default=StatutRF2.NON_APPLICABLE)
    montant_rf2_recu = Column(Numeric(18, 2), default=0)

    # Payment tracking
    montant_total_paye = Column(Numeric(18, 2), default=0)
    montant_restant = Column(Numeric(18, 2), default=0)

    # Commercial lock
    verrouille_par = Column(String(36), ForeignKey("users.id"))
    verrouille_at = Column(DateTime)

    # Dates
    date_reservation = Column(Date)
    date_engagement = Column(Date)
    date_livraison = Column(Date)

    # Dunning
    jours_retard_max = Column(Integer, default=0)
    derniere_relance = Column(Date)
    niveau_relance = Column(Integer, default=0)  # 0=none, 1=J+1, 2=J+7, 3=J+14, 4=J+30

    # Metadata
    notes = Column(Text)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"


class Client(Base):
    __tablename__ = "clients"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=True)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=True)
    code = Column(String(50), nullable=False)
    name = Column(String(500), nullable=False)
    legal_name = Column(String(500))
    tax_id = Column(String(50))
    ice = Column(String(50))  # Business tax ID
    address = Column(Text)
    city = Column(String(100))
    country = Column(String(100), default="Algeria")
    phone = Column(String(50))
    email = Column(String(255))
    payment_terms_days = Column(Integer, default=30)
    credit_limit = Column(Numeric(18, 2))
    account_code = Column(String(20))  # linked COA account
    metadata_ = Column("metadata", JSON, default={})
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Contract(Base):
    __tablename__ = "contracts"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=False)
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=True)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=True)
    contract_number = Column(String(100), nullable=False)
    title = Column(String(500))
    status = Column(SAEnum(ContractStatus), default=ContractStatus.DRAFT)
    start_date = Column(Date)
    end_date = Column(Date)
    total_amount = Column(Numeric(18, 2))
    currency = Column(String(3), default="DZD")
    terms = Column(JSON, default={})
    doc_ids = Column(JSON, default=[])
    notes = Column(Text)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Receivable(Base):
    __tablename__ = "receivables"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=False)
    contract_id = Column(String(36), ForeignKey("contracts.id"))
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=True)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=True)
    invoice_ref = Column(String(100))
    amount = Column(Numeric(18, 2), nullable=False)
    amount_paid = Column(Numeric(18, 2), default=0)
    currency = Column(String(3), default="DZD")
    due_date = Column(Date)
    status = Column(SAEnum(PaymentStatus), default=PaymentStatus.PENDING)
    realite_financiere = Column(String(3), default="RF1")  # RF1=Réel Déclaré, RF2=Réel Non Déclaré, RF3=Fictif
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id"))
    doc_ids = Column(JSON, default=[])
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Payment(Base):
    __tablename__ = "payments"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=False)
    receivable_id = Column(String(36), ForeignKey("receivables.id"))
    entreprise_id = Column(String(36), ForeignKey("entreprises.id"), nullable=True)
    projet_id = Column(String(36), ForeignKey("projets.id"), nullable=True)
    payment_ref = Column(String(100))
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), default="DZD")
    payment_date = Column(Date, nullable=False)
    payment_method = Column(String(50))
    bank_ref = Column(String(100))
    realite_financiere = Column(String(3), default="RF1")  # RF1=Réel Déclaré, RF2=Réel Non Déclaré, RF3=Fictif
    journal_entry_id = Column(String(36), ForeignKey("journal_entries.id"))
    doc_ids = Column(JSON, default=[])
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
