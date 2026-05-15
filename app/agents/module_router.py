"""GFI Platform - ModuleRouterAgent.

Post-commit agent that routes processed documents to the appropriate
domain module (ADV, Comptabilité, HR) and auto-creates records.

Runs as the final node in the document_to_ledger pipeline after commit.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
import structlog
from app.schemas.artifacts import WorkflowState, NodeResult
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)

# Map document types to target modules
DOC_TYPE_MODULE_MAP = {
    # ADV module
    "ADV_CONTRACT": "adv",
    "ADV_PAYMENT": "adv",
    "DEVIS": "adv",
    "BON_COMMANDE": "adv",
    "BON_LIVRAISON": "adv",
    # Comptabilité module
    "INVOICE": "comptabilite",
    "RECEIPT": "comptabilite",
    "BANK_STATEMENT": "comptabilite",
    "CHEQUE": "comptabilite",
    "AVOIR": "comptabilite",
    "QUITTANCE": "comptabilite",
    # HR module
    "PAYROLL": "hr",
    "BULLETIN_PAIE": "hr",
    "ATTESTATION": "hr",
    # General
    "CONTRACT": "adv",
    "OTHER": "documents",
}

# Doc types that should ALSO create ADV receivables (dual-routed)
ADV_RECEIVABLE_TYPES = {
    "INVOICE", "AVOIR", "QUITTANCE",
    "ADV_CONTRACT", "DEVIS", "BON_COMMANDE", "CONTRACT",
}


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Route committed documents to the appropriate domain module and create records."""
    from sqlalchemy import select
    from app.models.core import (
        Artifact, ArtifactType, Document, AuditLog,
    )

    artifacts_created = []
    warnings = []
    errors = []

    # Get the extraction artifacts to read extracted fields
    extraction_ids = state.artifacts.get("extraction", [])
    if not extraction_ids:
        # Nothing to route — the document stays in documents module
        return NodeResult(status="OK", artifacts_created=[], warnings=["No extraction data to route"], errors=[])

    for ext_id in extraction_ids:
        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == ext_id)
        )
        ext_artifact = result.scalar_one_or_none()
        if not ext_artifact:
            continue

        data = ext_artifact.data
        doc_id = data.get("doc_id", "")
        doc_type = data.get("doc_type", "OTHER")
        fields = data.get("fields", [])

        # Determine target module
        target_module = DOC_TYPE_MODULE_MAP.get(doc_type, "documents")

        # Build field lookup dict
        field_map = {}
        for f in fields:
            fname = f.get("field_name") or f.get("name")
            fval = f.get("normalized_value") or f.get("value")
            if fname and fval:
                field_map[fname] = fval

        # Update the Document record with routing info
        doc_result = await ctx.db_session.execute(
            select(Document).where(Document.id == doc_id)
        )
        doc = doc_result.scalar_one_or_none()
        if doc:
            doc.module_routed_to = target_module

        # Auto-create domain records based on module
        try:
            if target_module == "adv":
                record_id = await _create_adv_record(ctx, state, doc_type, doc_id, field_map)
                if record_id:
                    artifacts_created.append(record_id)

            elif target_module == "hr":
                record_id = await _create_hr_record(ctx, state, doc_type, doc_id, field_map)
                if record_id:
                    artifacts_created.append(record_id)

            elif target_module == "comptabilite":
                # Journal entries already created by commit node — just tag
                logger.info("module_routed", doc_id=doc_id, module="comptabilite",
                            doc_type=doc_type, note="journal_entries_already_committed")

            # Dual-route: also create ADV receivable for invoices/avoirs
            # even when primary route is comptabilite
            if doc_type in ADV_RECEIVABLE_TYPES and target_module != "adv":
                record_id = await _create_adv_record(ctx, state, doc_type, doc_id, field_map)
                if record_id:
                    artifacts_created.append(record_id)
                    logger.info("adv_dual_routed", doc_id=doc_id, doc_type=doc_type,
                                adv_record_id=record_id)

        except Exception as e:
            warnings.append(
                f"Failed to create {target_module} record for doc {doc_id}: {str(e)}"
            )
            logger.warning("module_router_create_failed",
                           doc_id=doc_id, module=target_module, error=str(e))

        # Audit log for routing
        audit = AuditLog(
            id=str(uuid.uuid4()),
            tenant_id=state.tenant_id,
            user_id=state.actor_user_id,
            action="MODULE_ROUTED",
            entity_type="document",
            entity_id=doc_id,
            new_value={
                "doc_type": doc_type,
                "target_module": target_module,
                "fields_count": len(field_map),
            },
        )
        ctx.db_session.add(audit)

        logger.info("module_routed", doc_id=doc_id, doc_type=doc_type,
                     target_module=target_module)

    await ctx.db_session.flush()

    return NodeResult(
        status="OK",
        artifacts_created=artifacts_created,
        warnings=warnings,
        errors=errors,
    )


async def _create_adv_record(
    ctx: RunContext,
    state: WorkflowState,
    doc_type: str,
    doc_id: str,
    field_map: dict,
) -> str | None:
    """Auto-create ADV domain records (Contract, Payment, Receivable)."""
    from app.models.adv import Contract, Payment, Receivable, Client
    from app.models.adv import ContractStatus, PaymentStatus
    from sqlalchemy import select, func

    tenant_id = state.tenant_id

    # Try to find or create client
    client_name = (
        field_map.get("client_name")
        or field_map.get("supplier_name")
        or field_map.get("vendor_name")
        or field_map.get("emetteur")
        or "Client Inconnu"
    )

    result = await ctx.db_session.execute(
        select(Client).where(
            Client.tenant_id == tenant_id,
            func.upper(Client.name) == client_name.upper(),
        )
    )
    client = result.scalar_one_or_none()

    if not client:
        # Auto-create client
        client = Client(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            code=f"CLI-{str(uuid.uuid4())[:8].upper()}",
            name=client_name,
            is_active=True,
        )
        ctx.db_session.add(client)
        await ctx.db_session.flush()
        logger.info("auto_created_client", client_id=client.id, name=client_name)

    amount = _safe_decimal(
        field_map.get("total_ttc")
        or field_map.get("total_amount")
        or field_map.get("amount")
        or field_map.get("montant_ttc")
    )

    if doc_type in ("ADV_CONTRACT", "CONTRACT", "DEVIS", "BON_COMMANDE"):
        contract_id = str(uuid.uuid4())
        contract = Contract(
            id=contract_id,
            tenant_id=tenant_id,
            client_id=client.id,
            contract_number=field_map.get("contract_number") or field_map.get("reference") or f"CTR-{contract_id[:8].upper()}",
            title=field_map.get("description") or field_map.get("object") or f"Contrat {doc_type}",
            status=ContractStatus.ACTIVE if doc_type != "DEVIS" else ContractStatus.DRAFT,
            total_amount=amount,
            currency=field_map.get("currency") or "DZD",
            doc_ids=[doc_id],
            created_by=state.actor_user_id,
        )

        # Set dates
        start_date = _parse_date(field_map.get("date") or field_map.get("contract_date"))
        if start_date:
            contract.start_date = start_date
        end_date = _parse_date(field_map.get("end_date"))
        if end_date:
            contract.end_date = end_date

        ctx.db_session.add(contract)
        logger.info("auto_created_contract", contract_id=contract_id, doc_type=doc_type)

        # Also create a receivable for the contract amount (except DEVIS)
        if amount and doc_type != "DEVIS":
            receivable_id = await _create_receivable(
                ctx, tenant_id, client.id, contract_id, doc_id, field_map, amount,
            )
            if receivable_id:
                logger.info("auto_created_receivable_from_contract",
                            receivable_id=receivable_id, contract_id=contract_id)

        return contract_id

    elif doc_type in ("INVOICE", "AVOIR", "QUITTANCE"):
        # Invoices create a receivable (creance) in ADV
        receivable_id = await _create_receivable(
            ctx, tenant_id, client.id, None, doc_id, field_map, amount,
        )
        if receivable_id:
            logger.info("auto_created_receivable_from_invoice",
                        receivable_id=receivable_id, doc_type=doc_type)
            return receivable_id
        return None

    elif doc_type in ("ADV_PAYMENT", "BON_LIVRAISON"):
        payment_id = str(uuid.uuid4())
        payment_date = _parse_date(field_map.get("payment_date") or field_map.get("date"))
        payment = Payment(
            id=payment_id,
            tenant_id=tenant_id,
            client_id=client.id,
            payment_ref=field_map.get("payment_ref") or field_map.get("reference") or f"PAY-{payment_id[:8].upper()}",
            amount=amount,
            currency=field_map.get("currency") or "DZD",
            payment_date=payment_date or date.today(),
            payment_method=field_map.get("payment_method") or "virement",
            doc_ids=[doc_id],
        )
        ctx.db_session.add(payment)
        logger.info("auto_created_payment", payment_id=payment_id, doc_type=doc_type)
        return payment_id

    return None


async def _create_receivable(
    ctx: RunContext,
    tenant_id: str,
    client_id: str,
    contract_id: str | None,
    doc_id: str,
    field_map: dict,
    amount: Decimal | None,
) -> str | None:
    """Create a Receivable record from extracted document fields."""
    from app.models.adv import Receivable, PaymentStatus

    if not amount or amount <= 0:
        return None

    receivable_id = str(uuid.uuid4())
    due_date = _parse_date(
        field_map.get("due_date")
        or field_map.get("echeance")
        or field_map.get("date_echeance")
    )

    # Default due date: 30 days from invoice date
    if not due_date:
        invoice_date = _parse_date(field_map.get("date") or field_map.get("invoice_date"))
        if invoice_date:
            from datetime import timedelta
            due_date = invoice_date + timedelta(days=30)
        else:
            due_date = date.today()

    invoice_ref = (
        field_map.get("invoice_ref")
        or field_map.get("invoice_number")
        or field_map.get("numero_facture")
        or field_map.get("reference")
        or f"FAC-{receivable_id[:8].upper()}"
    )

    receivable = Receivable(
        id=receivable_id,
        tenant_id=tenant_id,
        client_id=client_id,
        contract_id=contract_id,
        invoice_ref=invoice_ref,
        amount=amount,
        amount_paid=Decimal("0"),
        currency=field_map.get("currency") or "DZD",
        due_date=due_date,
        status=PaymentStatus.PENDING,
        doc_ids=[doc_id],
    )
    ctx.db_session.add(receivable)
    return receivable_id


async def _create_hr_record(
    ctx: RunContext,
    state: WorkflowState,
    doc_type: str,
    doc_id: str,
    field_map: dict,
) -> str | None:
    """Auto-create HR domain records (e.g. payroll entries)."""
    from app.models.hr import Employee
    from app.models.treasury import BulletinPaie
    from sqlalchemy import select, func

    tenant_id = state.tenant_id

    if doc_type in ("PAYROLL", "BULLETIN_PAIE"):
        # Try to match employee
        employee_name = field_map.get("employee_name") or field_map.get("destinataire")
        employee = None

        if employee_name:
            # Search by concatenated first+last name
            result = await ctx.db_session.execute(
                select(Employee).where(
                    Employee.tenant_id == tenant_id,
                    func.upper(Employee.last_name + ' ' + Employee.first_name) == employee_name.upper(),
                )
            )
            employee = result.scalar_one_or_none()

        if not employee and employee_name:
            # Try partial match on last_name
            result = await ctx.db_session.execute(
                select(Employee).where(
                    Employee.tenant_id == tenant_id,
                    func.upper(Employee.last_name).contains(
                        employee_name.upper().split()[0] if employee_name.split() else employee_name.upper()
                    ),
                ).limit(1)
            )
            employee = result.scalar_one_or_none()

        if employee:
            bulletin_id = str(uuid.uuid4())
            now = datetime.utcnow()
            salaire_base = _safe_decimal(field_map.get("salaire_base") or field_map.get("base_salary")) or Decimal("0")
            salaire_net = _safe_decimal(field_map.get("salaire_net") or field_map.get("net_salary") or field_map.get("net_payable")) or Decimal("0")
            bulletin = BulletinPaie(
                id=bulletin_id,
                tenant_id=tenant_id,
                employe_id=employee.id,
                entreprise_id=employee.tenant_id,  # fallback
                mois=int(field_map.get("mois") or now.month),
                annee=int(field_map.get("annee") or now.year),
                salaire_base=salaire_base,
                salaire_brut=_safe_decimal(field_map.get("salaire_brut")) or salaire_base,
                cnas_salarie=Decimal("0"),
                irg=Decimal("0"),
                total_retenues=Decimal("0"),
                salaire_net=salaire_net,
                cnas_patronal=Decimal("0"),
                cout_employeur_rd=Decimal("0"),
            )
            ctx.db_session.add(bulletin)
            logger.info("auto_created_bulletin", bulletin_id=bulletin_id,
                         employee=f"{employee.last_name} {employee.first_name}")
            return bulletin_id
        else:
            logger.warning("hr_employee_not_found", employee_name=employee_name,
                           doc_id=doc_id)

    return None


def _safe_decimal(value) -> Decimal | None:
    """Safely convert to Decimal."""
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(",", ".").replace(" ", ""))
    except Exception:
        return None


def _parse_date(value) -> date | None:
    """Try parsing a date string."""
    if value is None:
        return None
    if isinstance(value, date):
        return value

    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None
