"""GFI Platform – Seed Import Service.

Parses the authoritative Markdown documents and populates the database
with extracted data:

  1. docs/Employé (hr.employee).md          → employees table
  2. docs/Organigrammes AVELIS 2025.md       → departments table
  3. docs/NOMENCLATURE DES ENTREPRISE ET ACTIONNAIRE.md → entreprises, associes,
                                                           ownership_relations, projets
  4. docs/SYSTÈME DE RÉMUNÉRATION AUTOMATISÉ SPI 360°.md → spi_rules,
                                                             spi_bonus_malus_rules
  5. docs/Structure du système de rémunération.md → remuneration_baremes, spi_kpis

All seed operations are idempotent — they skip records that already exist.
"""
from __future__ import annotations

import uuid
import structlog
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hr import Employee, EmploymentStatus
from app.models.financial import Entreprise, Projet, Associe, StatutProjet
from app.models.spi import (
    Department, SPIRule, SPIKpi, SPIScore, SPIBonusMalusRule,
    OwnershipRelation, RemunerationBareme,
    BonusMalusType, FunctionCategory, SPICategory,
)
from app.models.finance_associes import AssociateAlias, CompteCourantAssocie
from app.models.bim_edd import REPricingRule, PricingRuleType
from app.services.employee_import import split_employee_name

logger = structlog.get_logger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# Master seed function
# ────────────────────────────────────────────────────────────────────────────

async def run_full_seed(db: AsyncSession, tenant_id: str) -> dict:
    """Execute all seed imports in order. Returns summary."""
    summary = {}
    summary["departments"] = await seed_departments(db, tenant_id)
    summary["employees"] = await seed_employees(db, tenant_id)
    summary["companies"] = await seed_companies_and_shareholders(db, tenant_id)
    summary["spi_rules"] = await seed_spi_rules(db, tenant_id)
    summary["bonus_malus"] = await seed_bonus_malus_rules(db, tenant_id)
    summary["baremes"] = await seed_remuneration_baremes(db, tenant_id)
    summary["kpis"] = await seed_kpis(db, tenant_id)
    summary["aliases"] = await seed_associate_aliases(db, tenant_id)
    summary["comptes_courants"] = await seed_comptes_courants(db, tenant_id)
    summary["pricing_rules"] = await seed_pricing_rules(db, tenant_id)
    await db.commit()
    logger.info("seed_complete", summary=summary)
    return summary


# ────────────────────────────────────────────────────────────────────────────
# 1. Departments (from docs/Organigrammes AVELIS 2025.md)
# ────────────────────────────────────────────────────────────────────────────

DEPARTMENTS_DATA = [
    {"code": "DG", "name": "Direction Générale", "parent_code": None, "sort": 0},
    {"code": "DAF", "name": "Département Administratif et Financier", "parent_code": "DG", "sort": 1},
    {"code": "DMV", "name": "Département Commercial et Marketing", "parent_code": "DG", "sort": 2},
    {"code": "DO", "name": "Département Opérationnel", "parent_code": "DG", "sort": 3},
    {"code": "DRH", "name": "Département Ressources Humaines (RH)", "parent_code": "DG", "sort": 4},
    {"code": "SAV", "name": "Service Après-Vente (SAV) / Relation Client", "parent_code": "DG", "sort": 5},
]


async def seed_departments(db: AsyncSession, tenant_id: str) -> dict:
    """Seed departments from org chart."""
    created = 0
    dept_map = {}

    for d in DEPARTMENTS_DATA:
        existing = await db.execute(
            select(Department).where(Department.tenant_id == tenant_id, Department.code == d["code"])
        )
        if existing.scalar_one_or_none():
            # Re-query to get the ID for parent mapping
            r = await db.execute(
                select(Department).where(Department.tenant_id == tenant_id, Department.code == d["code"])
            )
            dept_map[d["code"]] = r.scalar_one().id
            continue

        parent_id = dept_map.get(d["parent_code"]) if d["parent_code"] else None
        dept = Department(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            code=d["code"],
            name=d["name"],
            parent_id=parent_id,
            sort_order=d["sort"],
        )
        db.add(dept)
        await db.flush()
        dept_map[d["code"]] = dept.id
        created += 1

    return {"created": created, "total": len(DEPARTMENTS_DATA)}


# ────────────────────────────────────────────────────────────────────────────
# 2. Employees (from docs/Employé (hr.employee).md)
# ────────────────────────────────────────────────────────────────────────────

EMPLOYEES_DATA = [
    {"name": "ABBAS AHMED", "email": None, "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "ADJAOUD DJAMEL", "email": "djamel.adjaoud@promo-avelis.com", "dept": "Direction Générale / Département Ressources Humaines (RH)", "manager": "Ahmed Dendani", "mentor": "Ahmed Dendani", "position": "Office Manager / RH", "phone": "0560582000", "status": "draft"},
    {"name": "AMMOUR SAADI", "email": None, "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "AMROUCHE SAMIRA", "email": None, "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "ATTAR FARAH", "email": "farah.attar@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "Abdallah Abir", "email": "abdallah.abir@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0560584000", "status": None},
    {"name": "Administrator", "email": "Aghilas@tab-cs.tech", "dept": "Direction Générale", "manager": "Ahmed Dendani", "mentor": "Ahmed Dendani", "position": None, "phone": "0549007000", "status": None},
    {"name": "Ahmed Dendani", "email": "ahmed.dendani@promo-avelis.com", "dept": "Direction Générale", "manager": "Ahmed Dendani", "position": None, "phone": None, "status": None},
    {"name": "Akila Aiouaz", "email": "akila.aiouaz@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0560584000", "status": None},
    {"name": "Ali Tabti", "email": "ali.tabti@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0560584000", "status": None},
    {"name": "BABOU MOHAMED", "email": "mohamed.babou@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0560584000", "status": None},
    {"name": "BARACHE YASMINA", "email": "yasmine.barache@promo-avelis.com", "dept": "Direction Générale / Service Après-Vente (SAV) / Relation Client", "manager": "Ahmed Dendani", "mentor": "Ahmed Dendani", "position": "Manager Supply Chain Générale", "phone": None, "status": "cancel"},
    {"name": "BEN SEKKA SABRINA", "email": "sabrina.bensekka@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "BENALLAL ZAHIA", "email": "zahia.benallal@promo-avelis.com", "dept": "Direction Générale / Département Ressources Humaines (RH)", "manager": "ADJAOUD DJAMEL", "mentor": "ADJAOUD DJAMEL", "position": None, "phone": None, "status": None},
    {"name": "BENBIDA ABDELKADER", "email": None, "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "BENDAOUD MOUSSA", "email": None, "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "BENSAIFIA MOHAMED", "email": None, "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "BETIT RAFIK", "email": None, "dept": "Direction Générale / Département Ressources Humaines (RH)", "manager": "SEDDIKI BRAHIM", "mentor": "SEDDIKI BRAHIM", "position": "Agent de Séccurité", "phone": "0549007000", "status": None},
    {"name": "BOUNOUA OUSSAMA", "email": "oussama.bounoua@promo-avelis.com", "dept": "Direction Générale / Département Commercial et Marketing", "manager": "LAMRANI RACHID", "mentor": "LAMRANI RACHID", "position": "Sales Admin & Tender Officer", "phone": "0549007000", "status": None},
    {"name": "BOUTOBZA HANANE", "email": "hanane.boutobza@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "Boukerkour imene", "email": "boukerkour.imene@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0560584000", "status": None},
    {"name": "DIAF MOHAMED", "email": None, "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "DJADI MADJID", "email": None, "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "DJADI NABIL", "email": None, "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "DJEBARNI MEROUA", "email": "meroua.djebarni@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "DJEMA YOUNES-AMINE", "email": "amine.djema@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "DJETTOU NESRINE", "email": "nessrine.djettou@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "FALI RACHID", "email": None, "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "FERGUOUS WAFA", "email": "wafa.ferguous@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "FOUDIA SAFA", "email": "safa.foudia@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": None, "status": None},
    {"name": "HAMI LEILA", "email": "laila.hami@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "Hadji Amel", "email": "Hadji.Amel@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0560584000", "status": None},
    {"name": "Hakim mahfoud", "email": "Hakim.mahfoud@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0560584000", "status": None},
    {"name": "Imene Kandi", "email": "Imene.kandi@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0560584000", "status": None},
    {"name": "LAICHE AMIRA", "email": "amira.laiche@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "LAMRANI RACHID", "email": "rachid.lamrani@promo-avelis.com", "dept": "Direction Générale / Département Commercial et Marketing", "manager": "Ahmed Dendani", "mentor": "Ahmed Dendani", "position": "Marketing & Sales Performance Manager", "phone": "0549007000", "status": None},
    {"name": "LYAZID BOUABDELLAH", "email": "lyazid.bouabdellah@promo-avelis.com", "dept": "Direction Générale / Département Administratif et Financier", "manager": "Ahmed Dendani", "mentor": "Ahmed Dendani", "position": "Manager Finance", "phone": "0549007000", "status": None},
    {"name": "MANSOURI DJAZIA", "email": "djazia.mansouri@promo-avelis.com", "dept": None, "manager": "Ahmed Dendani", "mentor": "Ahmed Dendani", "position": None, "phone": None, "status": None},
    {"name": "MENSOURI CAMILIA", "email": "camelia.mensouri@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "MEZIANI MOURAD", "email": "mourad.meziani@promo-avelis.com", "dept": "Direction Générale / Département Commercial et Marketing", "manager": "LYAZID BOUABDELLAH", "mentor": "LYAZID BOUABDELLAH", "position": None, "phone": "0549007000", "status": None},
    {"name": "MOUHOUB HICHEM", "email": "hichem.mouhoub@promo-avelis.com", "dept": "Direction Générale / Département Administratif et Financier", "manager": "LYAZID BOUABDELLAH", "mentor": "LYAZID BOUABDELLAH", "position": "Manager Finance", "phone": "0549007000", "status": None},
    {"name": "OULD SAID HACENE", "email": "hacene.ouldsaid@promo-avelis.mom", "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "REZIKI OMAR", "email": "omar.reziki@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "SADLI HAKIM", "email": None, "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "SAIDANI MOHAMED HICHEM", "email": None, "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "SEDDIKI BRAHIM", "email": "brahim.seddiki@promo.avelis.com", "dept": "Direction Générale / Département Ressources Humaines (RH)", "manager": "ADJAOUD DJAMEL", "mentor": "ADJAOUD DJAMEL", "position": "Gestionnaire GDS MGX et Acheteur De Service", "phone": "0549007000", "status": None},
    {"name": "SEMAOUNE IMENE", "email": "imene.semaoune@promo.avelis.com", "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "Sara Argoub", "email": "sara.argoub@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0560584000", "status": None},
    {"name": "Souilah dalia", "email": "Souilah.dalia@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0560584000", "status": None},
    {"name": "TEBICH OUSSAMA SEDDIK", "email": "oussama.tebich@promo-elouedite.com", "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "Wanis Hadj Mohammed", "email": "Wanis.HadjMohammed@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0560584000", "status": None},
    {"name": "ZAAF YASMINE", "email": "yasmine.zaaf@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0549007000", "status": None},
    {"name": "fedoul meriem", "email": "fedoul.meriem@promo-avelis.com", "dept": None, "manager": None, "position": None, "phone": "0560584000", "status": None},
]


def _map_department_code(dept_str: Optional[str]) -> Optional[str]:
    """Map department string from MD to department code."""
    if not dept_str:
        return None
    dept_lower = dept_str.lower()
    if "ressources humaines" in dept_lower or "rh" in dept_lower:
        return "DRH"
    if "administratif et financier" in dept_lower or "financier" in dept_lower:
        return "DAF"
    if "commercial" in dept_lower or "marketing" in dept_lower:
        return "DMV"
    if "après-vente" in dept_lower or "sav" in dept_lower:
        return "SAV"
    if "opérationnel" in dept_lower:
        return "DO"
    if "direction générale" in dept_lower:
        return "DG"
    return None


def _infer_function_category(position: Optional[str], dept: Optional[str]) -> Optional[str]:
    """Infer FunctionCategory from employee position title and department.

    Priority: position keywords first, then department-based fallback.
    Returns a FunctionCategory enum value string or None.
    """
    pos_lower = (position or "").lower()
    dept_lower = (dept or "").lower()

    # ── Position-based (highest priority) ──────────────────────────────
    # Marketing takes precedence when both "marketing" and "sales" appear
    # (e.g. "Marketing & Sales Performance Manager" → MARKETING)
    if any(k in pos_lower for k in ("marketing", "brand", "communication", "publicité")):
        return "MARKETING"
    if any(k in pos_lower for k in ("sales", "commercial", "tender", "vente")):
        return "COMMERCIAL"
    if any(k in pos_lower for k in ("finance", "comptab", "trésor")):
        return "MANAGEMENT"
    if any(k in pos_lower for k in ("rh", "office manager")):
        return "SUPPORT"
    if any(k in pos_lower for k in ("sécurité", "securité", "security", "séccurité")):
        return "SUPPORT"
    if any(k in pos_lower for k in ("supply chain", "acheteur", "gestionnaire", "logistique")):
        return "OPERATIONS"
    if any(k in pos_lower for k in ("sav", "relation client")):
        return "SAV"
    if "manager" in pos_lower or "directeur" in pos_lower:
        return "MANAGEMENT"

    # ── Department-based fallback ──────────────────────────────────────
    if "commercial" in dept_lower and "marketing" not in dept_lower:
        return "COMMERCIAL"
    if "marketing" in dept_lower and "commercial" in dept_lower:
        # DMV employees without a specific position default to COMMERCIAL
        return "COMMERCIAL"
    if "marketing" in dept_lower:
        return "MARKETING"
    if "financier" in dept_lower or "administratif" in dept_lower:
        return "MANAGEMENT"
    if "ressources humaines" in dept_lower or "rh" in dept_lower:
        return "SUPPORT"
    if "après-vente" in dept_lower or "sav" in dept_lower:
        return "SAV"
    if "opérationnel" in dept_lower:
        return "OPERATIONS"
    if "direction générale" == dept_lower.strip():
        return "MANAGEMENT"

    return None


async def seed_employees(db: AsyncSession, tenant_id: str) -> dict:
    """Seed employees from Markdown dataset."""
    created = 0
    updated = 0
    skipped = 0

    # Build department lookup
    dept_result = await db.execute(
        select(Department).where(Department.tenant_id == tenant_id)
    )
    dept_map = {d.code: d.id for d in dept_result.scalars().all()}

    for emp_data in EMPLOYEES_DATA:
        name = emp_data["name"]
        # Skip system/admin accounts
        if name.lower() in ("administrator",):
            skipped += 1
            continue

        first_name, last_name = split_employee_name(name, emp_data.get("email"))

        # Map department
        dept_code = _map_department_code(emp_data.get("dept"))
        department_id = dept_map.get(dept_code) if dept_code else None

        # Map status
        status_map = {
            "draft": EmploymentStatus.ACTIVE,
            "cancel": EmploymentStatus.TERMINATED,
            None: EmploymentStatus.ACTIVE,
        }
        emp_status = status_map.get(emp_data.get("status"), EmploymentStatus.ACTIVE)

        existing = None
        if emp_data.get("email"):
            existing = (await db.execute(
                select(Employee).where(
                    Employee.tenant_id == tenant_id,
                    Employee.email == emp_data.get("email"),
                )
            )).scalar_one_or_none()
        if existing is None:
            existing = (await db.execute(
                select(Employee).where(
                    Employee.tenant_id == tenant_id,
                    Employee.first_name == first_name,
                    Employee.last_name == last_name,
                )
            )).scalar_one_or_none()

        if existing is not None:
            existing.first_name = first_name
            existing.last_name = last_name
            existing.email = emp_data.get("email")
            existing.phone = emp_data.get("phone")
            existing.professional_address = emp_data.get("professional_address") or "Avelis Promotion immobilière"
            existing.activities = emp_data.get("activities")
            existing.status = emp_status
            existing.is_active = emp_data.get("active", True)
            existing.department = emp_data.get("dept")
            existing.department_id = department_id
            existing.position = emp_data.get("position")
            existing.upcoming_activity_due_date = emp_data.get("upcoming_activity_due_date")
            existing.function_category = _infer_function_category(
                emp_data.get("position"), emp_data.get("dept")
            )
            existing.company = emp_data.get("company") or "Avelis Promotion immobilière"
            existing.currency = existing.currency or "DZD"
            updated += 1
            continue

        emp = Employee(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            employee_number=f"EMP-{created + 1:04d}",
            first_name=first_name,
            last_name=last_name,
            email=emp_data.get("email"),
            phone=emp_data.get("phone"),
            professional_address=emp_data.get("professional_address") or "Avelis Promotion immobilière",
            activities=emp_data.get("activities"),
            status=emp_status,
            is_active=emp_data.get("active", True),
            department=emp_data.get("dept"),
            department_id=department_id,
            position=emp_data.get("position"),
            upcoming_activity_due_date=emp_data.get("upcoming_activity_due_date"),
            function_category=_infer_function_category(
                emp_data.get("position"), emp_data.get("dept")
            ),
            company=emp_data.get("company") or "Avelis Promotion immobilière",
            currency="DZD",
        )
        db.add(emp)
        created += 1

    await db.flush()

    # Second pass: resolve manager references
    all_emps_result = await db.execute(
        select(Employee).where(Employee.tenant_id == tenant_id)
    )
    all_emps = all_emps_result.scalars().all()
    emp_by_name = {}
    for e in all_emps:
        full = f"{e.first_name} {e.last_name}".strip()
        emp_by_name[full.upper()] = e.id
        emp_by_name[f"{e.last_name} {e.first_name}".strip().upper()] = e.id

    for emp_data in EMPLOYEES_DATA:
        mgr_name = emp_data.get("manager")
        if not mgr_name:
            continue
        mgr_id = emp_by_name.get(mgr_name.upper())
        if not mgr_id:
            continue

        first_name, last_name = split_employee_name(emp_data["name"], emp_data.get("email"))

        emp_result = await db.execute(
            select(Employee).where(
                Employee.tenant_id == tenant_id,
                Employee.first_name == first_name,
                Employee.last_name == last_name,
            )
        )
        emp = emp_result.scalar_one_or_none()
        if emp and mgr_id != emp.id:
            emp.manager_id = mgr_id

    for emp_data in EMPLOYEES_DATA:
        mentor_name = emp_data.get("mentor")
        if not mentor_name:
            continue
        mentor_id = emp_by_name.get(mentor_name.upper())
        if not mentor_id:
            continue

        first_name, last_name = split_employee_name(emp_data["name"], emp_data.get("email"))

        emp_result = await db.execute(
            select(Employee).where(
                Employee.tenant_id == tenant_id,
                Employee.first_name == first_name,
                Employee.last_name == last_name,
            )
        )
        emp = emp_result.scalar_one_or_none()
        if emp and mentor_id != emp.id:
            emp.mentor_id = mentor_id

    await db.flush()
    return {"created": created, "updated": updated, "skipped": skipped}


# ────────────────────────────────────────────────────────────────────────────
# 3. Companies & Shareholders (from docs/NOMENCLATURE DES ENTREPRISE ET ACTIONNAIRE.md)
# ────────────────────────────────────────────────────────────────────────────

COMPANIES_DATA = [
    {
        "name": "ETS DENDANI KHADIDJA",
        "status": "A FERMER",
        "shareholders": [
            {"name": "AHMED DENDANI KHADIDJA", "pct": 25},
            {"name": "MOHAMED DENDANI", "pct": 25},
            {"name": "LYAZID BOUABDELLAH", "pct": 25},
            {"name": "YAMINA AIT BENAMARA", "pct": 25},
        ],
        "projects": [
            {"name": "EDEN", "shareholders": {"AHMED DENDANI KHADIDJA": 34, "MOHAMED DENDANI": 33, "LYAZID BOUABDELLAH": 33}},
            {"name": "LES JASMINS", "shareholders": {"AHMED DENDANI KHADIDJA": 34, "MOHAMED DENDANI": 33, "LYAZID BOUABDELLAH": 33}},
        ],
    },
    {
        "name": "SARL DENDANI PROMOTION",
        "status": "A DEVLOPER",
        "shareholders": [
            {"name": "AHMED DENDANI", "pct": 25},
            {"name": "MOHAMED DENDANI", "pct": 25},
            {"name": "LYAZID BOUABDELLAH", "pct": 25},
            {"name": "YAMINA AIT BENAMARA", "pct": 25},
        ],
        "projects": [
            {"name": "LES JARDIN DE LOPERA", "shareholders": {"AHMED DENDANI": 60, "MOHAMED DENDANI": 20, "LYAZID BOUABDELLAH": 20}},
            {"name": "05 HECTARE BOUMERDES", "shareholders": {"AHMED DENDANI": 60, "MOHAMED DENDANI": 20, "LYAZID BOUABDELLAH": 20}},
            {"name": "AVELIS DRIVE", "shareholders": {"AHMED DENDANI": 60, "MOHAMED DENDANI": 20, "LYAZID BOUABDELLAH": 20}},
            {"name": "ALLO MAISON", "shareholders": {"AHMED DENDANI": 60, "MOHAMED DENDANI": 20, "LYAZID BOUABDELLAH": 20}},
        ],
    },
    {
        "name": "SARL DBPI IMMOBILIER",
        "status": "A FERMER APRES TRANSFERT",
        "shareholders": [
            {"name": "AHMED DENDANI", "pct": 60},
            {"name": "MOHAMED DENDANI", "pct": 20},
            {"name": "BOUABDELLAH LYAZID", "pct": 20},
        ],
        "projects": [
            {"name": "LES LYS", "shareholders": {"AHMED DENDANI": 60, "MOHAMED DENDANI": 20, "BOUABDELLAH LYAZID": 20}},
        ],
    },
    {
        "name": "SARL OMEGA CONSTRUCTION",
        "status": "A FERMER",
        "shareholders": [
            {"name": "AHMED DENDANI", "pct": 60},
            {"name": "MOHAMED DENDANI", "pct": 20},
            {"name": "BOUABDELLAH LYAZID", "pct": 20},
        ],
        "projects": [
            {"name": "LES MAGNOLIA", "shareholders": {"AHMED DENDANI": 60, "MOHAMED DENDANI": 20, "BOUABDELLAH LYAZID": 20}},
        ],
    },
    {
        "name": "SARL AVELIS PROMOTION",
        "status": "A DEVLOPER",
        "shareholders": [
            {"name": "AHMED DENDANI", "pct": 60},
            {"name": "MOHAMED DENDANI", "pct": 20},
            {"name": "LYAZID BOUABDELLAH", "pct": 20},
        ],
        "projects": [
            {"name": "CHERAGA", "shareholders": {"AHMED DENDANI": 60, "MOHAMED DENDANI": 20, "LYAZID BOUABDELLAH": 20}},
        ],
    },
    {
        "name": "SARL SENIMAR",
        "status": "A DEVLOPER",
        "shareholders": [
            {"name": "AHMED DENDANI", "pct": 60},
            {"name": "MOHAMED DENDANI", "pct": 20},
            {"name": "LYAZID BOUABDELLAH", "pct": 20},
        ],
        "projects": [
            {"name": "EL ACHOUR", "shareholders": {"AHMED DENDANI": 60, "MOHAMED DENDANI": 20, "LYAZID BOUABDELLAH": 20}},
        ],
    },
    {
        "name": "EURL BIMHA CONSTRUCTION",
        "status": "A DEVLOPER",
        "shareholders": [
            {"name": "AHMED DENDANI", "pct": 60},
            {"name": "MOHAMED DENDANI", "pct": 20},
            {"name": "LYAZID BOUABDELLAH", "pct": 20},
        ],
        "projects": [
            {"name": "AVELIS DRIVE", "shareholders": {"AHMED DENDANI": 60, "MOHAMED DENDANI": 20, "LYAZID BOUABDELLAH": 20}},
            {"name": "PFSB", "shareholders": {"AHMED DENDANI": 60, "MOHAMED DENDANI": 20, "LYAZID BOUABDELLAH": 20}},
        ],
    },
    # COR-009: AMENFORT — 8th enterprise, dissolved, 3 associates (no Yamina)
    {
        "name": "SARL AMENFORT BÉTON",
        "status": "DISSOUTE",
        "shareholders": [
            {"name": "AHMED DENDANI", "pct": 33.33},
            {"name": "MOHAMED DENDANI", "pct": 33.33},
            {"name": "LYAZID BOUABDELLAH", "pct": 33.34},
        ],
        "projects": [
            {"name": "EDEN ST", "shareholders": {"AHMED DENDANI": 33.33, "MOHAMED DENDANI": 33.33, "LYAZID BOUABDELLAH": 33.34}},
        ],
    },
]


async def seed_companies_and_shareholders(db: AsyncSession, tenant_id: str) -> dict:
    """Seed companies, shareholders, projects, and ownership relations."""
    companies_created = 0
    shareholders_created = 0
    projects_created = 0
    ownership_created = 0

    for comp_data in COMPANIES_DATA:
        comp_name = comp_data["name"]

        # Check/create Entreprise
        existing_ent = await db.execute(
            select(Entreprise).where(
                Entreprise.tenant_id == tenant_id,
                Entreprise.raison_sociale == comp_name,
            )
        )
        ent = existing_ent.scalar_one_or_none()
        if not ent:
            is_active = comp_data.get("status", "") != "DISSOUTE"
            ent = Entreprise(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                raison_sociale=comp_name,
                devise="DZD",
                is_active=is_active,
            )
            db.add(ent)
            await db.flush()
            companies_created += 1

        # Shareholders (Associe)
        for sh in comp_data.get("shareholders", []):
            existing_assoc = await db.execute(
                select(Associe).where(
                    Associe.tenant_id == tenant_id,
                    Associe.entreprise_id == ent.id,
                    Associe.nom == sh["name"],
                )
            )
            if not existing_assoc.scalar_one_or_none():
                assoc = Associe(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    entreprise_id=ent.id,
                    nom=sh["name"],
                    part_pct=sh["pct"],
                )
                db.add(assoc)
                shareholders_created += 1

            # Company-level ownership relation
            existing_own = await db.execute(
                select(OwnershipRelation).where(
                    OwnershipRelation.tenant_id == tenant_id,
                    OwnershipRelation.entreprise_id == ent.id,
                    OwnershipRelation.shareholder_name == sh["name"],
                    OwnershipRelation.projet_id == None,
                )
            )
            if not existing_own.scalar_one_or_none():
                db.add(OwnershipRelation(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    entreprise_id=ent.id,
                    shareholder_name=sh["name"],
                    ownership_pct=sh["pct"],
                    status=comp_data.get("status"),
                ))
                ownership_created += 1

        # Projects
        for proj_data in comp_data.get("projects", []):
            proj_name = proj_data["name"]
            existing_proj = await db.execute(
                select(Projet).where(
                    Projet.tenant_id == tenant_id,
                    Projet.entreprise_id == ent.id,
                    Projet.nom == proj_name,
                )
            )
            proj = existing_proj.scalar_one_or_none()
            if not proj:
                proj = Projet(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    entreprise_id=ent.id,
                    code=proj_name.replace(" ", "_").upper()[:50],
                    nom=proj_name,
                    statut=StatutProjet.ACTIF if "DEVLOPER" in (comp_data.get("status") or "") else StatutProjet.TERMINE,
                )
                db.add(proj)
                await db.flush()
                projects_created += 1

            # Project-level ownership
            for sh_name, sh_pct in proj_data.get("shareholders", {}).items():
                if sh_pct <= 0:
                    continue
                existing_own = await db.execute(
                    select(OwnershipRelation).where(
                        OwnershipRelation.tenant_id == tenant_id,
                        OwnershipRelation.entreprise_id == ent.id,
                        OwnershipRelation.projet_id == proj.id,
                        OwnershipRelation.shareholder_name == sh_name,
                    )
                )
                if not existing_own.scalar_one_or_none():
                    db.add(OwnershipRelation(
                        id=str(uuid.uuid4()),
                        tenant_id=tenant_id,
                        entreprise_id=ent.id,
                        projet_id=proj.id,
                        shareholder_name=sh_name,
                        ownership_pct=sh_pct,
                        status=comp_data.get("status"),
                    ))
                    ownership_created += 1

    await db.flush()
    return {
        "companies_created": companies_created,
        "shareholders_created": shareholders_created,
        "projects_created": projects_created,
        "ownership_relations_created": ownership_created,
    }


# ────────────────────────────────────────────────────────────────────────────
# 4. SPI Rules (from docs/SYSTÈME DE RÉMUNÉRATION AUTOMATISÉ SPI 360°.md)
# ────────────────────────────────────────────────────────────────────────────

SPI_RULES_DATA = [
    {
        "role_code": "Project Planning Manager",
        "role_label": "Project Planning Manager",
        "category": "MANAGEMENT",
        "weights": (40, 30, 20, 10),
        "criteria": [
            {"category": "planification", "items": [
                {"label": "Tâches planifiées / tâches réalisées", "weight_pct": 40},
            ]},
            {"category": "qualite", "items": [
                {"label": "Respect des jalons / précision du planning", "weight_pct": 30},
            ]},
            {"category": "comportement", "items": [
                {"label": "Collaboration avec BI / structure documentaire", "weight_pct": 20},
            ]},
            {"category": "performance", "items": [
                {"label": "Propositions de prévention ou correction", "weight_pct": 10},
            ]},
        ],
    },
    {
        "role_code": "BI & Performance Data Analyst",
        "role_label": "BI & Performance Data Analyst",
        "category": "SUPPORT",
        "weights": (35, 30, 20, 15),
        "criteria": [
            {"category": "planification", "items": [
                {"label": "Tableaux de bord créés / mis à jour (temps réel)", "weight_pct": 35},
            ]},
            {"category": "qualite", "items": [
                {"label": "Fiabilité et cohérence des données analysées", "weight_pct": 30},
            ]},
            {"category": "comportement", "items": [
                {"label": "Réactivité aux demandes de la direction", "weight_pct": 20},
            ]},
            {"category": "performance", "items": [
                {"label": "Propositions d'amélioration automatique ou d'alertes", "weight_pct": 15},
            ]},
        ],
    },
    {
        "role_code": "Sales Admin & Tender Officer",
        "role_label": "Sales Admin & Tender Officer",
        "category": "COMMERCIAL",
        "weights": (40, 30, 20, 10),
        "criteria": [
            {"category": "planification", "items": [
                {"label": "Dossiers transmis conformes avec TCO", "weight_pct": 40},
            ]},
            {"category": "qualite", "items": [
                {"label": "Respect des délais d'appels d'offres / contrats", "weight_pct": 30},
            ]},
            {"category": "comportement", "items": [
                {"label": "Zéro erreur / zéro relance direction", "weight_pct": 20},
            ]},
            {"category": "performance", "items": [
                {"label": "Suivi documentaire archivé", "weight_pct": 10},
            ]},
        ],
    },
    {
        "role_code": "Marketing & Brand Manager",
        "role_label": "Marketing & Brand Manager",
        "category": "MARKETING",
        "weights": (35, 30, 20, 15),
        "criteria": [
            {"category": "planification", "items": [
                {"label": "Leads qualifiés mensuels générés", "weight_pct": 35},
            ]},
            {"category": "qualite", "items": [
                {"label": "Cohérence de l'image visuelle / ligne de marque", "weight_pct": 30},
            ]},
            {"category": "comportement", "items": [
                {"label": "Projets de contenu / campagnes livrés", "weight_pct": 20},
            ]},
            {"category": "performance", "items": [
                {"label": "Initiatives stratégiques marketing", "weight_pct": 15},
            ]},
        ],
    },
    {
        "role_code": "Technical Sales Executive",
        "role_label": "Technical Sales Executive",
        "category": "COMMERCIAL",
        "weights": (50, 25, 15, 10),
        "commission_cash": 1.0,
        "commission_credit": 0.5,
        "criteria": [
            {"category": "planification", "items": [
                {"label": "Ventes réalisées (directes ou par conversion)", "weight_pct": 50},
            ]},
            {"category": "qualite", "items": [
                {"label": "Nombre de leads traités et relancés dans les délais", "weight_pct": 25},
            ]},
            {"category": "comportement", "items": [
                {"label": "Tenue de compte et service post-prospection", "weight_pct": 15},
            ]},
            {"category": "performance", "items": [
                {"label": "Participation aux vidéos, publications, contenus auto-produits", "weight_pct": 10},
            ]},
        ],
    },
    {
        "role_code": "Manager Finance",
        "role_label": "Manager Finance",
        "category": "MANAGEMENT",
        "weights": (35, 30, 20, 15),
        "criteria": [
            {"category": "planification", "items": [
                {"label": "Exactitude des bilans, rapprochements, journaux", "weight_pct": 35},
            ]},
            {"category": "qualite", "items": [
                {"label": "Suivi des déclarations (G50, CNAS, CASNOS)", "weight_pct": 30},
            ]},
            {"category": "comportement", "items": [
                {"label": "Suivi budgétaire et analyse des écarts", "weight_pct": 20},
            ]},
            {"category": "performance", "items": [
                {"label": "Encadrement RH + tableaux de pilotage", "weight_pct": 15},
            ]},
        ],
    },
    {
        "role_code": "Operations Support Officer",
        "role_label": "Operations Support Officer (LAD / ERP)",
        "category": "OPERATIONS",
        "weights": (40, 30, 20, 10),
        "criteria": [
            {"category": "planification", "items": [
                {"label": "Taux de matériels / moyens tracés dans l'ERP", "weight_pct": 40},
            ]},
            {"category": "qualite", "items": [
                {"label": "Absence d'erreur / mouvement non justifié", "weight_pct": 30},
            ]},
            {"category": "comportement", "items": [
                {"label": "Rapidité de traitement", "weight_pct": 20},
            ]},
            {"category": "performance", "items": [
                {"label": "Suggestions d'amélioration de traçabilité", "weight_pct": 10},
            ]},
        ],
    },
    {
        "role_code": "General Recovery Officer",
        "role_label": "General Recovery Officer",
        "category": "SAV",
        "weights": (40, 25, 20, 15),
        "criteria": [
            {"category": "planification", "items": [
                {"label": "Montants récupérés / échéanciers respectés", "weight_pct": 40},
            ]},
            {"category": "qualite", "items": [
                {"label": "Taux de dossiers bloqués résolus", "weight_pct": 25},
            ]},
            {"category": "comportement", "items": [
                {"label": "Coordination avec banque / notaire / juriste", "weight_pct": 20},
            ]},
            {"category": "performance", "items": [
                {"label": "Absence d'erreur ou de fausse relance", "weight_pct": 15},
            ]},
        ],
    },
    {
        "role_code": "Welcome Desk Assistant",
        "role_label": "Welcome Desk Assistant",
        "category": "SUPPORT",
        "weights": (40, 30, 20, 10),
        "criteria": [
            {"category": "planification", "items": [
                {"label": "Accueil noté élégamment par la direction", "weight_pct": 40},
            ]},
            {"category": "qualite", "items": [
                {"label": "Disponibilité, présentation, maîtrise du poste", "weight_pct": 30},
            ]},
            {"category": "comportement", "items": [
                {"label": "Rapidité du service boissons / réactivité", "weight_pct": 20},
            ]},
            {"category": "performance", "items": [
                {"label": "Tenue du poste et propreté", "weight_pct": 10},
            ]},
        ],
    },
    {
        "role_code": "Kitchen Assistant & Waitress",
        "role_label": "Kitchen Assistant & Waitress",
        "category": "SUPPORT",
        "weights": (40, 30, 20, 10),
        "criteria": [
            {"category": "planification", "items": [
                {"label": "Qualité du service (chariot, catégorie, respect circuit)", "weight_pct": 40},
            ]},
            {"category": "qualite", "items": [
                {"label": "Implication dans les événements internes", "weight_pct": 30},
            ]},
            {"category": "comportement", "items": [
                {"label": "Soutien à la cuisine et à l'entretien", "weight_pct": 20},
            ]},
            {"category": "performance", "items": [
                {"label": "Ponctualité / tenue", "weight_pct": 10},
            ]},
        ],
    },
    {
        "role_code": "Housekeeper",
        "role_label": "Housekeeper",
        "category": "SUPPORT",
        "weights": (40, 30, 20, 10),
        "criteria": [
            {"category": "planification", "items": [
                {"label": "Contrôle hebdomadaire de propreté validé sans relance", "weight_pct": 40},
            ]},
            {"category": "qualite", "items": [
                {"label": "Zéro tâche répétée ou réclamée deux fois", "weight_pct": 30},
            ]},
            {"category": "comportement", "items": [
                {"label": "Proactivité sur les zones à nettoyer sans demande", "weight_pct": 20},
            ]},
            {"category": "performance", "items": [
                {"label": "Respect des horaires et du matériel", "weight_pct": 10},
            ]},
        ],
    },
    {
        "role_code": "Driver",
        "role_label": "Driver",
        "category": "SUPPORT",
        "weights": (40, 30, 20, 10),
        "criteria": [
            {"category": "planification", "items": [
                {"label": "Ponctualité trajets / 0 erreur de destination", "weight_pct": 40},
            ]},
            {"category": "qualite", "items": [
                {"label": "Véhicule propre quotidiennement + contrôles effectués", "weight_pct": 30},
            ]},
            {"category": "comportement", "items": [
                {"label": "Présence et disponibilité H24 validée par le supérieur", "weight_pct": 20},
            ]},
            {"category": "performance", "items": [
                {"label": "Tenue et conduite professionnelle", "weight_pct": 10},
            ]},
        ],
    },
    {
        "role_code": "Marketing & Sales Performance Manager",
        "role_label": "Marketing & Sales Performance Manager",
        "category": "MANAGEMENT",
        "weights": (35, 25, 25, 15),
        "criteria": [
            {"category": "planification", "items": [
                {"label": "Stratégie marketing et ventes exécutée", "weight_pct": 35},
            ]},
            {"category": "qualite", "items": [
                {"label": "Performance de l'équipe commerciale", "weight_pct": 25},
            ]},
            {"category": "comportement", "items": [
                {"label": "Leadership et encadrement", "weight_pct": 25},
            ]},
            {"category": "performance", "items": [
                {"label": "CA généré et marge", "weight_pct": 15},
            ]},
        ],
    },
    {
        "role_code": "Office Manager / RH",
        "role_label": "Office Manager / RH",
        "category": "MANAGEMENT",
        "weights": (30, 25, 30, 15),
        "criteria": [
            {"category": "planification", "items": [
                {"label": "Gestion administrative et organisationnelle", "weight_pct": 30},
            ]},
            {"category": "qualite", "items": [
                {"label": "Qualité du suivi RH et conformité", "weight_pct": 25},
            ]},
            {"category": "comportement", "items": [
                {"label": "Gestion des conflits et discipline", "weight_pct": 30},
            ]},
            {"category": "performance", "items": [
                {"label": "Indicateurs RH et tableaux de bord", "weight_pct": 15},
            ]},
        ],
    },
]


async def seed_spi_rules(db: AsyncSession, tenant_id: str) -> dict:
    """Seed SPI rules from specifications."""
    created = 0

    for rule_data in SPI_RULES_DATA:
        existing = await db.execute(
            select(SPIRule).where(
                SPIRule.tenant_id == tenant_id,
                SPIRule.role_code == rule_data["role_code"],
                SPIRule.is_active == True,
            )
        )
        if existing.scalar_one_or_none():
            continue

        w = rule_data["weights"]
        criteria_map = {}
        for c in rule_data.get("criteria", []):
            criteria_map[c["category"]] = c["items"]

        rule = SPIRule(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            role_code=rule_data["role_code"],
            role_label=rule_data["role_label"],
            function_category=FunctionCategory(rule_data.get("category", "SUPPORT")),
            weight_planification=w[0],
            weight_qualite=w[1],
            weight_comportement=w[2],
            weight_performance=w[3],
            criteria_planification=criteria_map.get("planification", []),
            criteria_qualite=criteria_map.get("qualite", []),
            criteria_comportement=criteria_map.get("comportement", []),
            criteria_performance=criteria_map.get("performance", []),
            commission_cash_pct=rule_data.get("commission_cash", 0),
            commission_credit_pct=rule_data.get("commission_credit", 0),
        )
        db.add(rule)
        created += 1

    await db.flush()
    return {"created": created, "total": len(SPI_RULES_DATA)}


# ────────────────────────────────────────────────────────────────────────────
# 5. Bonus/Malus Rules
# ────────────────────────────────────────────────────────────────────────────

BONUS_MALUS_SEED = [
    {"type": "BONUS", "label": "SPI ≥ 90 → +20% salaire", "spi_min": 90, "spi_max": 130, "pct": 20, "hr": False, "term": False, "freeze": False, "sort": 1},
    {"type": "BONUS", "label": "SPI ≥ 130 (2 mois) → +50% + prime exceptionnelle", "spi_min": 130, "spi_max": 200, "pct": 50, "hr": False, "term": False, "freeze": False, "sort": 2, "months": 2},
    {"type": "MALUS", "label": "SPI < 70 → -15% salaire", "spi_min": 50, "spi_max": 70, "pct": -15, "hr": False, "term": False, "freeze": False, "sort": 3},
    {"type": "MALUS", "label": "SPI < 50 → -30% + alerte RH", "spi_min": 30, "spi_max": 50, "pct": -30, "hr": True, "term": False, "freeze": False, "sort": 4},
    {"type": "MALUS", "label": "SPI < 50 (2 mois) → rupture automatique", "spi_min": 0, "spi_max": 50, "pct": -30, "hr": True, "term": True, "freeze": True, "sort": 5, "months": 2},
    {"type": "MALUS", "label": "Inactivité 5 jours → gel salaire + alerte RH", "spi_min": 0, "spi_max": 100, "pct": 0, "hr": True, "term": False, "freeze": True, "sort": 6},
]


async def seed_bonus_malus_rules(db: AsyncSession, tenant_id: str) -> dict:
    """Seed bonus/malus rules."""
    created = 0
    for bm in BONUS_MALUS_SEED:
        existing = await db.execute(
            select(SPIBonusMalusRule).where(
                SPIBonusMalusRule.tenant_id == tenant_id,
                SPIBonusMalusRule.label == bm["label"],
            )
        )
        if existing.scalar_one_or_none():
            continue

        rule = SPIBonusMalusRule(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            rule_type=BonusMalusType(bm["type"]),
            label=bm["label"],
            spi_min=bm["spi_min"],
            spi_max=bm["spi_max"],
            consecutive_months=bm.get("months", 1),
            salary_adjustment_pct=bm["pct"],
            triggers_hr_alert=bm["hr"],
            triggers_termination=bm["term"],
            triggers_salary_freeze=bm["freeze"],
            sort_order=bm["sort"],
        )
        db.add(rule)
        created += 1

    await db.flush()
    return {"created": created, "total": len(BONUS_MALUS_SEED)}


# ────────────────────────────────────────────────────────────────────────────
# 6. Remuneration Barèmes (from docs/Structure du système de rémunération.md)
# ────────────────────────────────────────────────────────────────────────────

BAREME_SEED = [
    {"cat": "SUPPORT", "label": "0-29% : Salaire de base uniquement", "min": 0, "max": 29, "adj": 0, "sort": 1},
    {"cat": "SUPPORT", "label": "30-50% : Négociation, -20% salaire", "min": 30, "max": 50, "adj": -20, "sort": 2},
    {"cat": "SUPPORT", "label": "51-75% : Salaire normal", "min": 51, "max": 75, "adj": 0, "sort": 3},
    {"cat": "SUPPORT", "label": "76-92% : Bonus +10% sur salaire négocié", "min": 76, "max": 92, "adj": 10, "sort": 4},
    {"cat": "SUPPORT", "label": "93-100% : Bonus +20% sur salaire négocié", "min": 93, "max": 100, "adj": 20, "sort": 5},
    {"cat": "COMMERCIAL", "label": "Commission cash 1%", "min": 0, "max": 100, "adj": 0, "sort": 1},
    {"cat": "COMMERCIAL", "label": "Commission crédit 0.5%", "min": 0, "max": 100, "adj": 0, "sort": 2},
    {"cat": "SAV", "label": "Bonus recouvrement élevé", "min": 80, "max": 100, "adj": 15, "sort": 1},
    {"cat": "SAV", "label": "Malus recouvrement faible", "min": 0, "max": 50, "adj": -10, "sort": 2},
]


async def seed_remuneration_baremes(db: AsyncSession, tenant_id: str) -> dict:
    """Seed remuneration barèmes."""
    created = 0
    for b in BAREME_SEED:
        existing = await db.execute(
            select(RemunerationBareme).where(
                RemunerationBareme.tenant_id == tenant_id,
                RemunerationBareme.label == b["label"],
            )
        )
        if existing.scalar_one_or_none():
            continue

        db.add(RemunerationBareme(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            function_category=FunctionCategory(b["cat"]),
            label=b["label"],
            performance_min_pct=b["min"],
            performance_max_pct=b["max"],
            salary_adjustment_pct=b["adj"],
            sort_order=b["sort"],
        ))
        created += 1

    await db.flush()
    return {"created": created, "total": len(BAREME_SEED)}


# ────────────────────────────────────────────────────────────────────────────
# 7. KPIs (from docs/Structure du système de rémunération.md)
# ────────────────────────────────────────────────────────────────────────────

KPI_SEED = [
    {"code": "TASK_COMPLETION_RATE", "name": "Taux de complétion des tâches", "cat": "PLANIFICATION", "target": 100, "unit": "%"},
    {"code": "ON_TIME_DELIVERY", "name": "Livraison dans les délais", "cat": "PLANIFICATION", "target": 95, "unit": "%"},
    {"code": "QUALITY_SCORE", "name": "Score qualité (validation sans retour)", "cat": "QUALITE_EXECUTION", "target": 90, "unit": "%"},
    {"code": "ZERO_ERROR_RATE", "name": "Taux zéro erreur", "cat": "QUALITE_EXECUTION", "target": 100, "unit": "%"},
    {"code": "ATTENDANCE_RATE", "name": "Taux de présence", "cat": "COMPORTEMENT", "target": 98, "unit": "%"},
    {"code": "DISCIPLINE_SCORE", "name": "Score discipline (0 sanctions)", "cat": "COMPORTEMENT", "target": 100, "unit": "points"},
    {"code": "SALES_TARGET", "name": "Objectif ventes atteint", "cat": "PERFORMANCE_METIER", "target": 100, "unit": "%"},
    {"code": "LEAD_CONVERSION", "name": "Taux de conversion leads", "cat": "PERFORMANCE_METIER", "target": 30, "unit": "%"},
    {"code": "RECOVERY_RATE", "name": "Taux de recouvrement", "cat": "PERFORMANCE_METIER", "target": 85, "unit": "%"},
    {"code": "DASHBOARD_UPDATES", "name": "Tableaux de bord mis à jour", "cat": "PLANIFICATION", "target": 100, "unit": "%"},
    {"code": "PROACTIVITY_INDEX", "name": "Indice de proactivité", "cat": "COMPORTEMENT", "target": 80, "unit": "points"},
]


async def seed_kpis(db: AsyncSession, tenant_id: str) -> dict:
    """Seed KPI definitions."""
    created = 0
    for k in KPI_SEED:
        existing = await db.execute(
            select(SPIKpi).where(SPIKpi.tenant_id == tenant_id, SPIKpi.code == k["code"])
        )
        if existing.scalar_one_or_none():
            continue

        db.add(SPIKpi(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            code=k["code"],
            name=k["name"],
            category=SPICategory(k["cat"]),
            target_value=k.get("target"),
            unit=k.get("unit", "points"),
        ))
        created += 1

    await db.flush()
    return {"created": created, "total": len(KPI_SEED)}


# ────────────────────────────────────────────────────────────────────────────
# 8. Associate Aliases (GAP 4 / GAP 9)
# ────────────────────────────────────────────────────────────────────────────

ASSOCIATE_ALIASES_DATA = {
    # canonical_name → [alias1, alias2, ...]
    "AHMED DENDANI": [
        "AHMED DENDANI KHADIDJA",
        "A. DENDANI",
        "DENDANI AHMED",
    ],
    "MOHAMED DENDANI": [
        "M. DENDANI",
        "DENDANI MOHAMED",
    ],
    "LYAZID BOUABDELLAH": [
        "BOUABDELLAH LYAZID",
        "L. BOUABDELLAH",
        "BOUABDELLAH",
    ],
    "YAMINA AIT BENAMARA": [
        "AIT BENAMARA YAMINA",
        "Y. AIT BENAMARA",
    ],
}


async def seed_associate_aliases(db: AsyncSession, tenant_id: str) -> dict:
    """Seed associate aliases for exact-match + fuzzy lookup."""
    created = 0

    # Get all associes for this tenant
    result = await db.execute(
        select(Associe).where(Associe.tenant_id == tenant_id)
    )
    associes = result.scalars().all()

    # Build name → associe map
    assoc_map: dict[str, Associe] = {}
    for a in associes:
        assoc_map[a.nom.upper().strip()] = a

    for canonical, aliases in ASSOCIATE_ALIASES_DATA.items():
        assoc = assoc_map.get(canonical.upper().strip())
        if not assoc:
            continue

        for alias_text in aliases:
            existing = await db.execute(
                select(AssociateAlias).where(
                    AssociateAlias.alias == alias_text,
                )
            )
            if existing.scalar_one_or_none():
                continue

            db.add(AssociateAlias(
                id=str(uuid.uuid4()),
                associe_id=assoc.id,
                alias=alias_text,
            ))
            created += 1

    await db.flush()
    return {"created": created}


# ────────────────────────────────────────────────────────────────────────────
# 9. Comptes Courants Associés (GAP 2 / GAP 9)
# ────────────────────────────────────────────────────────────────────────────

async def seed_comptes_courants(db: AsyncSession, tenant_id: str) -> dict:
    """Create a CompteCourantAssocie for every Associe that doesn't have one."""
    result = await db.execute(
        select(Associe).where(Associe.tenant_id == tenant_id)
    )
    associes = result.scalars().all()

    created = 0
    for a in associes:
        existing = await db.execute(
            select(CompteCourantAssocie).where(
                CompteCourantAssocie.associe_id == a.id,
            )
        )
        if existing.scalar_one_or_none():
            continue

        db.add(CompteCourantAssocie(
            id=str(uuid.uuid4()),
            associe_id=a.id,
            solde_global=0,
            solde_disponible_retrait=0,
        ))
        created += 1

    await db.flush()
    return {"created": created}


# ────────────────────────────────────────────────────────────────────────────
# 10. Default Pricing Rules (GAP 8 — coefficient-based)
# ────────────────────────────────────────────────────────────────────────────

DEFAULT_PRICING_RULES = [
    # FACADE
    {"code": "facade_principale", "rule_type": "FACADE", "label": "Façade principale (+10%)", "value": 0.10, "scope": "ALL", "condition_field": "exposure", "condition_value": "S"},
    {"code": "facade_secondaire", "rule_type": "FACADE", "label": "Façade secondaire (-5%)", "value": -0.05, "scope": "ALL", "condition_field": "exposure", "condition_value": "N"},
    {"code": "vue_mer_directe", "rule_type": "FACADE", "label": "Vue mer directe (+50%)", "value": 0.50, "scope": "ALL", "condition_field": "view_class", "condition_value": "mer"},
    {"code": "facade_sans_vue_mer", "rule_type": "FACADE", "label": "Façade sans vue mer (-10%)", "value": -0.10, "scope": "ALL", "condition_field": "view_class", "condition_value": "none"},
    # VERTICAL
    {"code": "bonus_etage_vue_mer", "rule_type": "VERTICAL", "label": "Bonus étage vue mer (+5%/niv)", "value": 0.05, "scope": "ALL", "condition_field": "view_class", "condition_value": "mer", "is_per_level": True, "cap_value": 0.25},
    {"code": "villa_dernier_etage", "rule_type": "VERTICAL", "label": "Villa dernier étage (+15%)", "value": 0.15, "scope": "VILLA"},
    # COMMERCIAL
    {"code": "client_direct", "rule_type": "COMMERCIAL", "label": "Client direct (-2%)", "value": -0.02, "scope": "ALL"},
    {"code": "commission_progressive", "rule_type": "COMMERCIAL", "label": "Commission progressive base 0.5%", "value": 0.005, "scope": "ALL"},
    {"code": "second_appartement", "rule_type": "COMMERCIAL", "label": "2ème appartement (-3%)", "value": -0.03, "scope": "UNIT"},
    # FINANCIAL
    {"code": "prix_lancement", "rule_type": "FINANCIAL", "label": "Prix lancement (-5%)", "value": -0.05, "scope": "ALL"},
    {"code": "gestion_tresorerie_cash", "rule_type": "FINANCIAL", "label": "Trésorerie cash (-1.5%)", "value": -0.015, "scope": "ALL"},
    # PARTNERSHIP
    {"code": "client_agence", "rule_type": "PARTNERSHIP", "label": "Client agence (+3% commission)", "value": 0.03, "scope": "ALL"},
    {"code": "bonus_performance", "rule_type": "PARTNERSHIP", "label": "Bonus performance (cap 3%)", "value": 0.02, "scope": "ALL", "cap_value": 0.03},
]


async def seed_pricing_rules(db: AsyncSession, tenant_id: str) -> dict:
    """Seed global coefficient pricing rules (not per-project)."""
    created = 0
    for rule_data in DEFAULT_PRICING_RULES:
        existing = await db.execute(
            select(REPricingRule).where(
                REPricingRule.code == rule_data["code"],
            )
        )
        if existing.scalar_one_or_none():
            continue

        db.add(REPricingRule(
            id=str(uuid.uuid4()),
            code=rule_data["code"],
            rule_type=PricingRuleType(rule_data["rule_type"]),
            label=rule_data.get("label"),
            value=rule_data["value"],
            scope=rule_data.get("scope", "ALL"),
            condition_field=rule_data.get("condition_field"),
            condition_value=rule_data.get("condition_value"),
            is_per_level=rule_data.get("is_per_level", False),
            cap_value=rule_data.get("cap_value"),
        ))
        created += 1

    await db.flush()
    return {"created": created}
