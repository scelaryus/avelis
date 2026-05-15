"""GFI Platform - MatchingAgent.

Matches normalized entities to canonical DB records (suppliers, customers, accounts).
"""
import uuid
import structlog
from app.schemas.artifacts import (
    WorkflowState, NodeResult, MatchingPackage, MatchCandidate,
)
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Match extracted entities to DB records."""
    from sqlalchemy import select
    from app.models.core import Artifact, ArtifactType, ChartOfAccount
    from app.models.adv import Client

    artifacts_created = []

    norm_ids = state.artifacts.get("normalization", [])

    for norm_id in norm_ids:
        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == norm_id)
        )
        artifact = result.scalar_one_or_none()
        if not artifact:
            continue

        data = artifact.data
        doc_id = data.get("doc_id", "")
        doc_type = data.get("doc_type", "OTHER")
        fields = data.get("fields", [])

        matches = []
        unmatched = []

        field_map = {f.get("field_name"): f.get("normalized_value") or f.get("original_value")
                     for f in fields}

        # Match supplier/client name
        for name_field in ["supplier_name", "vendor_name", "client_name"]:
            if name_field in field_map and field_map[name_field]:
                candidate = await _match_entity(
                    ctx, "supplier_or_client", name_field, field_map[name_field]
                )
                if candidate:
                    matches.append(candidate)
                else:
                    unmatched.append({
                        "entity_type": "supplier_or_client",
                        "field_name": name_field,
                        "value": field_map[name_field],
                        "reason": "No match found",
                    })

        # Match account codes based on doc type
        account_mapping = _get_default_accounts(doc_type)
        for role, code in account_mapping.items():
            # Verify account exists
            acc_result = await ctx.db_session.execute(
                select(ChartOfAccount).where(
                    ChartOfAccount.tenant_id == state.tenant_id,
                    ChartOfAccount.code == code,
                    ChartOfAccount.is_active == True,
                )
            )
            acc = acc_result.scalar_one_or_none()
            if acc:
                matches.append(MatchCandidate(
                    entity_type="account",
                    field_name=role,
                    extracted_value=code,
                    matched_id=str(acc.id),
                    matched_label=acc.label,
                    confidence=1.0,
                    method="policy_default",
                ))
            else:
                matches.append(MatchCandidate(
                    entity_type="account",
                    field_name=role,
                    extracted_value=code,
                    matched_id=None,
                    matched_label=None,
                    confidence=0.5,
                    method="policy_default_unverified",
                ))

        matching_pkg = MatchingPackage(
            doc_id=doc_id,
            matches=matches,
            unmatched=unmatched,
        )

        match_artifact = Artifact(
            id=uuid.uuid4(),
            tenant_id=state.tenant_id,
            workflow_id=state.workflow_id,
            doc_id=doc_id,
            artifact_type=ArtifactType.MATCHING_PACKAGE,
            data=matching_pkg.model_dump(),
            algo_version="v3.0-match",
        )
        ctx.db_session.add(match_artifact)
        artifacts_created.append(str(match_artifact.id))

        logger.info("matching_complete", doc_id=doc_id,
                     matched=len(matches), unmatched=len(unmatched))

    await ctx.db_session.flush()

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=[], errors=[])


async def _match_entity(ctx: RunContext, entity_type: str, field_name: str, value: str) -> MatchCandidate | None:
    """Try to match an entity value against DB records."""
    from sqlalchemy import select, func
    from app.models.adv import Client

    if not value:
        return None

    # Exact match first
    result = await ctx.db_session.execute(
        select(Client).where(
            Client.tenant_id == ctx.tenant_id,
            func.upper(Client.name) == value.upper(),
        )
    )
    client = result.scalar_one_or_none()

    if client:
        return MatchCandidate(
            entity_type=entity_type,
            field_name=field_name,
            extracted_value=value,
            matched_id=str(client.id),
            matched_label=client.name,
            confidence=1.0,
            method="exact",
        )

    # Fuzzy match: LIKE
    result = await ctx.db_session.execute(
        select(Client).where(
            Client.tenant_id == ctx.tenant_id,
            func.upper(Client.name).contains(value.upper()[:10]),
        ).limit(3)
    )
    candidates = result.scalars().all()

    if candidates:
        best = candidates[0]
        return MatchCandidate(
            entity_type=entity_type,
            field_name=field_name,
            extracted_value=value,
            matched_id=str(best.id),
            matched_label=best.name,
            confidence=0.6,
            method="fuzzy",
        )

    return None


def _get_default_accounts(doc_type: str) -> dict[str, str]:
    """Get default account codes by document type (Algerian SCF / PCN-based)."""
    defaults = {
        "INVOICE": {
            "expense_account": "612000",    # Achats de matières et fournitures
            "vat_account": "445700",        # TVA sur achats
            "supplier_account": "401000",   # Fournisseurs
        },
        "RECEIPT": {
            "expense_account": "613000",    # Charges diverses
            "cash_account": "512000",       # Banques
        },
        "BANK_STATEMENT": {
            "bank_account": "512000",       # Banques
        },
        "PAYROLL": {
            "salary_account": "631000",     # Rémunérations du personnel
            "social_charges": "635000",     # Charges sociales (CNAS)
            "net_payable": "421000",        # Personnel – rémunérations dues
        },
        "BULLETIN_PAIE": {
            "salary_account": "631000",
            "social_charges": "635000",
            "net_payable": "421000",
        },
        "CHEQUE": {
            "bank_account": "512000",
        },
        "ADV_CONTRACT": {
            "revenue_account": "701000",    # Ventes de marchandises
            "client_account": "411000",     # Clients
        },
        "ADV_PAYMENT": {
            "bank_account": "512000",
            "client_account": "411000",
        },
        "AVOIR": {
            "expense_account": "612000",
            "vat_account": "445700",
            "supplier_account": "401000",
        },
        "QUITTANCE": {
            "expense_account": "613000",
            "cash_account": "512000",
        },
        "DEVIS": {},  # no accounting impact
        "BON_COMMANDE": {},  # no accounting impact
        "BON_LIVRAISON": {},  # no accounting impact
    }
    return defaults.get(doc_type, {})
