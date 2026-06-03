from app.models.base import Base, GFIBase
from app.models.auth_user import AuthUser
from app.models.company import Company
from app.models.associate import Associate
from app.models.project import Project
from app.models.entreprise_associe import EntrepriseAssocie
from app.models.part_projet import PartProjet
from app.models.role import Role
from app.models.permission import Permission
from app.models.role_permission import RolePermission
from app.models.user_role import UserRole
from app.models.audit_trail import AuditTrail
from app.models.sod_rule import SodRule
from app.models.entity_alias import EntityAlias
from app.models.formulaire_catalogue import FormulaireCatalogue
from app.models.formulaire import Formulaire
from app.models.formulaire_attachment import FormulaireAttachment
from app.models.financial_transaction import FinancialTransaction
from app.models.bareme_timbre import BaremeTimbre
from app.models.cff_calculation import CffCalculation
from app.models.cff_imputation import CffImputation
from app.models.account import Account
from app.models.journal import Journal
from app.models.journal_sequence import JournalSequence
from app.models.journal_entry import JournalEntry
from app.models.journal_entry_line import JournalEntryLine
from app.models.bank_reconciliation import BankStatement, BankMovement
from app.models.fiscal_declaration import FiscalDeclaration
from app.models.cca_account import CcaAccount
from app.models.cca_movement import CcaMovement
from app.models.cca_freeze import CcaFreeze
from app.models.treasury_closing import TreasuryClosing
from app.models.closed_period import ClosedPeriod
from app.models.lot import Lot
from app.models.lot_lock import LotLock
from app.models.client import Client
from app.models.dossier_adv import DossierAdv
from app.models.dossier_payment import DossierPayment
from app.models.dossier_document import DossierDocument
from app.models.dossier_transition import DossierTransition
from app.models.payment import Payment
from app.models.notary_escrow import (
    NotaryEscrow, EscrowMovement, EtatDetaille, EtatDetailleLine,
)
from app.models.credit_workflow import (
    CreditTier, ExpertReport, WireTransferOrder, GuaranteeFund,
)
from app.models.echeancier import Echeancier, Echeance
from app.models.document_generation import (
    DocumentTemplate, GeneratedDocument, RelanceTracker,
)
from app.models.cost_center import CostCenterNode, CostCenterEntry
from app.models.cc_category import (
    CcCategoryConfig, PayrollImputation, AllocationKey, BbzCharge,
)
from app.models.margin import MarginCalculation, QuotePartResult
from app.models.verification import (
    Alert, VerificationRun, ScheduledReport, DafDashboardSnapshot,
)
from app.models.gaceb import GacebAdvance, WorkSituation, Vehicle
from app.models.associate_operations import (
    AssociateWithdrawal, InterProjectFlow, FoundingCapital,
)
from app.models.procurement import (
    Supplier, PurchaseRequest, PurchaseOrder,
    GoodsReceipt, Warehouse, StockItem, StockMovement,
)
from app.models.project_management import (
    ProjectTask, TaskAdvancement, SubcontractorContract,
)
from app.models.legal import (
    ContractLifecycle, ShareTransfer, PreemptionRight, CapitalCall,
)
from app.models.hr import (
    Department, JobPosition, SalaryStructure,
    Employee, EmployeeContract,
)
from app.models.payroll import Payslip
from app.models.payslip_verification import PayslipVerification
from app.models.onboarding import (
    RecruitmentRequest, Candidate, OnboardingChecklist, EquipmentAssignment,
)
from app.models.access_control import (
    SiteMiddleware, AccessController, AccessZone,
    BadgeRecord, BadgeEvent, MiddlewareCommand,
)
from app.models.leave import LeaveBalance, LeaveRequest, LeaveVerification
from app.models.offboarding import (
    DisciplinaryCase, OffboardingProcess, StcCalculation,
)
from app.models.compliance import (
    DataProcessingRegistry, ConsentRecord, DataAccessRequest,
    DataPurgeLog, Visitor, HrDocumentTemplate,
)
from app.models.ged import Document, DocumentVersion, DocumentProcessingRun
from app.models.detection import DetectionPattern, DetectionFinding
from app.models.meta_ia import MetaIaProposal, MetaIaSandbox
from app.models.legal_module import (
    LegalCase, LegalContract, LegalComplianceRule, LegalComplianceAlert,
    LegalContractClause, LegalContractTemplate, LegalCaseCostLine, LegalAiTask,
)
from app.models.operations import (
    Operation, OperationBudgetAgrege, OperationPlanningTask,
    OperationDependency, OperationSnapshot, WbsTemplate,
)

__all__ = [
    "Base", "GFIBase", "AuthUser", "Company", "Associate",
    "Project", "EntrepriseAssocie", "PartProjet",
    "Role", "Permission", "RolePermission", "UserRole",
    "AuditTrail", "SodRule", "EntityAlias",
    "FormulaireCatalogue", "Formulaire", "FormulaireAttachment",
    "FinancialTransaction", "BaremeTimbre",
    "CffCalculation", "CffImputation",
    "Account", "Journal", "JournalSequence",
    "JournalEntry", "JournalEntryLine",
    "BankStatement", "BankMovement", "FiscalDeclaration",
    "CcaAccount", "CcaMovement", "CcaFreeze",
    "TreasuryClosing", "ClosedPeriod",
    "Lot", "LotLock",
    "Client", "DossierAdv", "DossierPayment",
    "DossierDocument", "DossierTransition",
    "Payment",
    "NotaryEscrow", "EscrowMovement",
    "EtatDetaille", "EtatDetailleLine",
    "CreditTier", "ExpertReport",
    "WireTransferOrder", "GuaranteeFund",
    "Echeancier", "Echeance",
    "DocumentTemplate", "GeneratedDocument", "RelanceTracker",
    "CostCenterNode", "CostCenterEntry",
    "CcCategoryConfig", "PayrollImputation",
    "AllocationKey", "BbzCharge",
    "MarginCalculation", "QuotePartResult",
    "Alert", "VerificationRun",
    "ScheduledReport", "DafDashboardSnapshot",
    "GacebAdvance", "WorkSituation", "Vehicle",
    "AssociateWithdrawal", "InterProjectFlow", "FoundingCapital",
    "Supplier", "PurchaseRequest", "PurchaseOrder",
    "GoodsReceipt", "Warehouse", "StockItem", "StockMovement",
    "ProjectTask", "TaskAdvancement", "SubcontractorContract",
    "ContractLifecycle", "ShareTransfer", "PreemptionRight", "CapitalCall",
    "Department", "JobPosition", "SalaryStructure",
    "Employee", "EmployeeContract",
    "Payslip", "PayslipVerification",
    "RecruitmentRequest", "Candidate",
    "OnboardingChecklist", "EquipmentAssignment",
    "SiteMiddleware", "AccessController", "AccessZone",
    "BadgeRecord", "BadgeEvent", "MiddlewareCommand",
    "LeaveBalance", "LeaveRequest", "LeaveVerification",
    "DisciplinaryCase", "OffboardingProcess", "StcCalculation",
    "DataProcessingRegistry", "ConsentRecord", "DataAccessRequest",
    "DataPurgeLog", "Visitor", "HrDocumentTemplate",
    "Document", "DocumentVersion", "DocumentProcessingRun",
    "DetectionPattern", "DetectionFinding",
    "MetaIaProposal", "MetaIaSandbox",
    "LegalCase", "LegalContract", "LegalComplianceRule", "LegalComplianceAlert",
    "LegalContractClause", "LegalContractTemplate", "LegalCaseCostLine", "LegalAiTask",
    "Operation", "OperationBudgetAgrege", "OperationPlanningTask",
    "OperationDependency", "OperationSnapshot", "WbsTemplate",
]
