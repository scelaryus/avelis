"""GFI Platform - NormalizationAgent (deterministic).

Normalizes extracted entities: formatting, currencies, dates.
No hallucination — deterministic transforms only.
"""
import re
import uuid
import structlog
from datetime import datetime
from decimal import Decimal, InvalidOperation
from app.schemas.artifacts import (
    WorkflowState, NodeResult, NormalizedEntitySet, NormalizedField,
)
from app.orchestrator.engine import RunContext

logger = structlog.get_logger(__name__)


async def run(state: WorkflowState, ctx: RunContext) -> NodeResult:
    """Normalize extracted entities."""
    from sqlalchemy import select
    from app.models.core import Artifact, ArtifactType

    artifacts_created = []

    # Get extraction artifacts
    extraction_ids = state.artifacts.get("extraction", [])

    for ext_id in extraction_ids:
        result = await ctx.db_session.execute(
            select(Artifact).where(Artifact.id == ext_id)
        )
        artifact = result.scalar_one_or_none()
        if not artifact:
            continue

        data = artifact.data
        # Skip doc_type_classification artifacts
        if "doc_type_classification" in data:
            continue

        doc_id = data.get("doc_id", "")
        doc_type = data.get("doc_type", "OTHER")
        fields = data.get("fields", [])
        line_items = data.get("line_items")

        normalized_fields = []
        derived_checks = []

        for field_data in fields:
            field_name = field_data.get("field_name", "")
            original_value = field_data.get("value")
            transforms = []

            normalized_value = original_value

            # Amount normalization
            if _is_amount_field(field_name):
                normalized_value, t = _normalize_amount(original_value)
                transforms.extend(t)

            # Date normalization
            elif _is_date_field(field_name):
                normalized_value, t = _normalize_date(original_value)
                transforms.extend(t)

            # Currency normalization
            elif field_name == "currency":
                normalized_value, t = _normalize_currency(original_value)
                transforms.extend(t)

            # Name normalization (suppliers, clients)
            elif _is_name_field(field_name):
                normalized_value, t = _normalize_name(original_value)
                transforms.extend(t)

            normalized_fields.append(NormalizedField(
                field_name=field_name,
                original_value=str(original_value) if original_value is not None else None,
                normalized_value=normalized_value,
                normalization_applied=transforms,
            ))

        # Derived checks (e.g., HT + TVA = TTC)
        if doc_type == "INVOICE":
            checks = _compute_derived_checks(normalized_fields)
            derived_checks.extend(checks)

        # Normalize line items
        norm_line_items = None
        if line_items:
            norm_line_items = _normalize_line_items(line_items)

        normalized = NormalizedEntitySet(
            doc_id=doc_id,
            doc_type=doc_type,
            fields=normalized_fields,
            derived_checks=derived_checks,
            line_items=norm_line_items,
        )

        norm_artifact = Artifact(
            id=uuid.uuid4(),
            tenant_id=state.tenant_id,
            workflow_id=state.workflow_id,
            doc_id=doc_id,
            artifact_type=ArtifactType.NORMALIZED_ENTITY_SET,
            data=normalized.model_dump(),
            algo_version="v3.0-normalize",
        )
        ctx.db_session.add(norm_artifact)
        artifacts_created.append(str(norm_artifact.id))

    await ctx.db_session.flush()
    logger.info("normalization_complete", count=len(artifacts_created))

    return NodeResult(status="OK", artifacts_created=artifacts_created, warnings=[], errors=[])


def _is_amount_field(name: str) -> bool:
    return any(k in name.lower() for k in ["total", "amount", "salary", "ht", "ttc", "tva", "price", "balance"])


def _is_date_field(name: str) -> bool:
    return "date" in name.lower()


def _is_name_field(name: str) -> bool:
    return any(k in name.lower() for k in ["name", "supplier", "vendor", "client", "employee", "party"])


def _normalize_amount(value) -> tuple:
    """Normalize amount to decimal string."""
    if value is None:
        return None, []

    transforms = []
    s = str(value).strip()

    # Remove currency symbols and spaces
    s = re.sub(r'[€$£¥]', '', s)
    s = s.replace('\u00a0', '').replace(' ', '')
    transforms.append("removed_currency_symbols")

    # Handle French format (1.234,56 → 1234.56)
    if re.match(r'^\d{1,3}(\.\d{3})*(,\d{1,2})?$', s):
        s = s.replace('.', '').replace(',', '.')
        transforms.append("french_to_standard_decimal")
    # Handle comma as decimal separator (1234,56 → 1234.56)
    elif ',' in s and '.' not in s:
        s = s.replace(',', '.')
        transforms.append("comma_to_dot_decimal")

    try:
        d = Decimal(s)
        # Round to 2 decimal places
        d = d.quantize(Decimal('0.01'))
        return str(d), transforms
    except (InvalidOperation, ValueError):
        return str(value), ["normalization_failed"]


def _normalize_date(value) -> tuple:
    """Normalize date to ISO format."""
    if value is None:
        return None, []

    s = str(value).strip()
    transforms = []

    # Try various date formats
    date_formats = [
        ("%d/%m/%Y", "dd/mm/yyyy"),
        ("%d-%m-%Y", "dd-mm-yyyy"),
        ("%d.%m.%Y", "dd.mm.yyyy"),
        ("%d/%m/%y", "dd/mm/yy"),
        ("%Y-%m-%d", "yyyy-mm-dd"),
        ("%m/%d/%Y", "mm/dd/yyyy"),
    ]

    for fmt, label in date_formats:
        try:
            dt = datetime.strptime(s, fmt)
            transforms.append(f"parsed_{label}_to_iso")
            return dt.strftime("%Y-%m-%d"), transforms
        except ValueError:
            continue

    return s, ["date_parse_failed"]


def _normalize_currency(value) -> tuple:
    """Normalize currency code."""
    if value is None:
        return "DZD", ["defaulted_to_DZD"]

    mapping = {
        "€": "EUR", "eur": "EUR", "euro": "EUR", "euros": "EUR",
        "$": "USD", "usd": "USD",
        "da": "DZD", "dzd": "DZD", "dinar": "DZD", "dinars": "DZD",
        "dh": "MAD", "mad": "MAD", "dirham": "MAD", "dirhams": "MAD",
        "£": "GBP", "gbp": "GBP",
    }

    s = str(value).strip().lower()
    if s in mapping:
        return mapping[s], [f"mapped_{s}_to_{mapping[s]}"]

    return str(value).upper()[:3], []


def _normalize_name(value) -> tuple:
    """Normalize business/person names."""
    if value is None:
        return None, []

    s = str(value).strip()
    transforms = []

    # Remove extra whitespace
    s = re.sub(r'\s+', ' ', s)
    transforms.append("collapsed_whitespace")

    # Title case
    s = s.upper()
    transforms.append("uppercased")

    return s, transforms


def _compute_derived_checks(fields: list[NormalizedField]) -> list[dict]:
    """Check HT + TVA ≈ TTC for invoices."""
    checks = []
    field_map = {f.field_name: f.normalized_value for f in fields}

    total_ht = field_map.get("total_ht")
    total_tva = field_map.get("total_tva")
    total_ttc = field_map.get("total_ttc")

    if total_ht and total_tva and total_ttc:
        try:
            ht = Decimal(str(total_ht))
            tva = Decimal(str(total_tva))
            ttc = Decimal(str(total_ttc))
            expected = ht + tva
            diff = abs(expected - ttc)

            checks.append({
                "check": "HT+TVA=TTC",
                "expected": str(expected),
                "actual": str(ttc),
                "difference": str(diff),
                "result": "OK" if diff <= Decimal("0.02") else "MISMATCH",
            })
        except (InvalidOperation, ValueError):
            checks.append({
                "check": "HT+TVA=TTC",
                "result": "CANNOT_COMPUTE",
                "reason": "Non-numeric values",
            })

    return checks


def _normalize_line_items(items: list[dict]) -> list[dict]:
    """Normalize line item amounts."""
    normalized = []
    for item in items:
        norm_item = dict(item)
        for key in ["amount", "unit_price", "quantity"]:
            if key in norm_item and norm_item[key] is not None:
                val, _ = _normalize_amount(norm_item[key])
                norm_item[key] = val
        normalized.append(norm_item)
    return normalized
