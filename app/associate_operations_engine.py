"""
GFI v7.0 — Associate Operations Engine.

Manages apartment withdrawals (CC9), inter-project flows (CC7),
and founding capital ODs.

Withdrawals are 100% to the specific associate — NOT distributed.
Inter-project flows generate mirror entries: debit source / credit dest.
Founding capital creates the first CCA credits.

Core API:
  record_withdrawal(...)       -> CC9 + CCA + generates formulaire if missing data
  record_inter_project_flow(...)  -> CC7 mirror + FC-016
  record_founding_capital(...)    -> OD + CCA credit
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def record_withdrawal(
    session: Session,
    *,
    company_id: UUID,
    project_id: UUID,
    associate_id: UUID,
    description: str,
    valeur_attribution: Decimal,
    lot_references: list[str] | None = None,
    withdrawal_date: date | None = None,
    disposition: str | None = None,
    ceded_to: str | None = None,
    sale_price: Decimal | None = None,
    buyer_name: str | None = None,
    created_by: UUID | None = None,
) -> object:
    """
    Record an associate apartment withdrawal from a project.
    CC9: 100% to the specific associate, NOT distributed.
    Creates CCA debit + CC entry.
    """
    from app.models.associate_operations import AssociateWithdrawal
    from app.cc_category_engine import impute_to_category

    valeur = Decimal(str(valeur_attribution))

    withdrawal = AssociateWithdrawal(
        company_id=company_id,
        project_id=project_id,
        associate_id=associate_id,
        description=description,
        lot_references=lot_references,
        valeur_attribution=valeur,
        withdrawal_date=withdrawal_date or date.today(),
        disposition=disposition,
        ceded_to=ceded_to,
        sale_price=Decimal(str(sale_price)) if sale_price else None,
        buyer_name=buyer_name,
        created_by=created_by,
    )

    if sale_price:
        sp = Decimal(str(sale_price))
        withdrawal.net_benefit = _r2(sp - valeur)

    session.add(withdrawal)
    session.flush()

    # CC9 imputation: 100% to the specific associate
    cc_entry = impute_to_category(
        session,
        category="ASSOC",
        company_id=company_id,
        project_id=project_id,
        rf_type="RF1",
        montant=valeur,
        entry_date=withdrawal_date or date.today(),
        libelle=f"Prelevement {description}",
        associate_id=associate_id,
        source_type="associate_withdrawal",
        source_id=withdrawal.id,
        created_by=created_by,
    )

    # CCA debit
    from app.cca_engine import record_personal_debt
    from app.models.cca_account import CcaAccount

    cca = (
        session.query(CcaAccount)
        .filter(
            CcaAccount.company_id == company_id,
            CcaAccount.associate_id == associate_id,
            CcaAccount.is_deleted.is_(False),
        )
        .first()
    )

    if cca:
        record_personal_debt(
            session,
            cca_account_id=cca.id,
            company_id=company_id,
            movement_date=withdrawal_date or date.today(),
            amount=valeur,
            label=f"Prelevement: {description}",
            justification_type="PRELEVEMENT_BIEN",
            project_id=project_id,
            created_by=created_by,
        )

    return withdrawal


def record_inter_project_flow(
    session: Session,
    *,
    company_id: UUID,
    source_project_id: UUID,
    dest_project_id: UUID,
    montant: Decimal,
    description: str,
    flow_date: date | None = None,
    created_by: UUID | None = None,
) -> object:
    """
    Record an inter-project flow. Creates mirror CC7 entries.
    Generates FC-016 to determine nature (loan vs investment).

    Debit distributed at SOURCE project %, credit at DEST project %.
    """
    from app.models.associate_operations import InterProjectFlow
    from app.cc_category_engine import impute_to_category
    from app.formulaire_engine import generate_if_not_exists
    from app.models.project import Project

    montant = Decimal(str(montant))
    fdate = flow_date or date.today()

    source = session.get(Project, source_project_id)
    dest = session.get(Project, dest_project_id)

    flow = InterProjectFlow(
        company_id=company_id,
        source_project_id=source_project_id,
        dest_project_id=dest_project_id,
        montant=montant,
        flow_date=fdate,
        description=description,
        nature="INDETERMINE",
        created_by=created_by,
    )
    session.add(flow)
    session.flush()

    # CC7 debit on source (distributed at source project %)
    impute_to_category(
        session,
        category="INTER_PROJ",
        company_id=company_id,
        project_id=source_project_id,
        rf_type="RF1",
        montant=montant,
        entry_date=fdate,
        libelle=f"Sortie vers {dest.code if dest else 'projet'}: {description}",
        source_type="inter_project_flow",
        source_id=flow.id,
        created_by=created_by,
    )

    # CC credit on dest (under TERRAIN or target category)
    dest_code = dest.code if dest else "UNK"
    impute_to_category(
        session,
        category="TERRAIN",
        company_id=company_id,
        project_id=dest_project_id,
        rf_type="RF1",
        montant=montant,
        entry_date=fdate,
        libelle=f"Financement depuis {source.code if source else 'projet'}: {description}",
        source_type="inter_project_flow",
        source_id=flow.id,
        created_by=created_by,
    )

    # Generate FC-016 to determine nature
    source_name = source.code if source else str(source_project_id)
    dest_name = dest.code if dest else str(dest_project_id)
    fc = generate_if_not_exists(
        session,
        code="FC-016",
        company_id=company_id,
        context={
            "montant": str(montant),
            "projet_source": source_name,
            "projet_dest": dest_name,
        },
        blocked_resource_type="inter_project_flow",
        blocked_resource_id=flow.id,
        created_by=created_by,
    )
    flow.formulaire_ref = "FC-016"

    session.flush()
    return flow


def record_founding_capital(
    session: Session,
    *,
    company_id: UUID,
    project_id: UUID,
    associate_id: UUID,
    od_reference: str,
    source_entity: str,
    source_description: str,
    montant: Decimal | None = None,
    capital_date: date | None = None,
    is_amenfort_linked: bool = False,
    created_by: UUID | None = None,
) -> object:
    """
    Record a founding capital OD.
    Creates the first CCA credit for the associate.
    If amount unknown (AMENFORT sale) -> generates FC-015.
    """
    from app.models.associate_operations import FoundingCapital
    from app.formulaire_engine import generate_if_not_exists

    fc = FoundingCapital(
        company_id=company_id,
        project_id=project_id,
        associate_id=associate_id,
        od_reference=od_reference,
        montant=Decimal(str(montant)) if montant else None,
        source_description=source_description,
        source_entity=source_entity,
        capital_date=capital_date,
        is_amenfort_linked=is_amenfort_linked,
        created_by=created_by,
    )

    if montant is None and is_amenfort_linked:
        fc.formulaire_ref = "FC-015"
        generate_if_not_exists(
            session,
            code="FC-015",
            company_id=company_id,
            context={"source": "AMENFORT Lot 1 sale to Dabladji"},
            created_by=created_by,
        )

    session.add(fc)
    session.flush()

    # If amount is known, create CCA credit
    if montant:
        from app.cca_engine import deposit
        from app.models.cca_account import CcaAccount

        cca = (
            session.query(CcaAccount)
            .filter(
                CcaAccount.company_id == company_id,
                CcaAccount.associate_id == associate_id,
                CcaAccount.is_deleted.is_(False),
            )
            .first()
        )
        if cca:
            deposit(
                session,
                cca_account_id=cca.id,
                company_id=company_id,
                movement_date=capital_date or date.today(),
                amount=Decimal(str(montant)),
                label=f"Apport fondateur {od_reference}: {source_description}",
                justification_type="OD_FONDATEUR",
                justification_ref=od_reference,
                created_by=created_by,
            )

    return fc
