"""Generate comprehensive dummy data for all GFI v7 modules.

Run: python seed_dummy_data.py

Covers:
  - Entreprises + Projets + Associés
  - Employees with SPI fields (various roles/departments)
  - TacheSPI tasks (various statuses, scores, deadlines)
  - OffrePerformance (bonus/malus offers)
  - SPIMensuel (monthly SPI scores with C1-C4)
  - AlerteRH (HR alerts)
  - PlanStrategique (strategic plans)
  - ADV: Clients, Contracts, Receivables, Payments
  - CC: CCNode hierarchy, CCDistribution, CCImputation
"""

import asyncio
import uuid
import json
from datetime import date, datetime, timedelta
from decimal import Decimal

# ── Bootstrap ──
import sys, os
sys.path.insert(0, os.path.dirname(__file__))


def uid():
    return str(uuid.uuid4())


async def main():
    from app.database import AsyncSessionLocal, async_engine, Base
    from sqlalchemy import select, text

    # Import ALL models so Base.metadata knows about them
    import app.models.core          # noqa
    import app.models.hr            # noqa
    import app.models.adv           # noqa
    import app.models.financial     # noqa
    import app.models.legal         # noqa
    import app.models.spi           # noqa
    import app.models.treasury      # noqa
    import app.models.registry      # noqa
    import app.models.integrations  # noqa
    import app.models.finance_associes  # noqa
    import app.models.bim_edd       # noqa
    import app.models.cff           # noqa
    import app.models.rbac_gfi      # noqa
    import app.models.juridique     # noqa
    import app.models.meta_ia       # noqa
    import app.models.cc_hierarchique  # noqa
    import app.models.planification    # noqa

    # Create all tables
    from app.database import sync_engine
    Base.metadata.create_all(sync_engine)

    async with AsyncSessionLocal() as db:
        # ── Get or create tenant ──
        from app.models.core import Tenant, User
        result = await db.execute(select(Tenant).limit(1))
        tenant = result.scalar_one_or_none()
        if not tenant:
            tenant = Tenant(id=uid(), name="AVELIS PROMOTION", code="AVELIS",
                            description="Société de promotion immobilière", settings={})
            db.add(tenant)
            await db.flush()

        T = tenant.id

        # ── Get admin user ──
        result = await db.execute(select(User).where(User.tenant_id == T).limit(1))
        admin = result.scalar_one_or_none()
        if not admin:
            from passlib.context import CryptContext
            pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
            admin = User(id=uid(), tenant_id=T, email="admin@gfi.ma",
                         hashed_password=pwd.hash("admin123"),
                         full_name="Admin", role="SUPER_ADMIN", is_active=True)
            db.add(admin)
            await db.flush()

        print(f"Tenant: {T}")
        print(f"Admin: {admin.email}")

        # ════════════════════════════════════════════════════════════════
        # 1. ENTREPRISES & PROJETS
        # ════════════════════════════════════════════════════════════════
        from app.models.financial import Entreprise, Projet, StatutProjet, Associe

        # Check if already seeded
        existing = await db.execute(select(Entreprise).where(Entreprise.tenant_id == T).limit(1))
        if existing.scalar_one_or_none():
            print("Entreprises already exist, skipping...")
            ent_result = await db.execute(select(Entreprise).where(Entreprise.tenant_id == T))
            entreprises = ent_result.scalars().all()
            proj_result = await db.execute(select(Projet).where(Projet.tenant_id == T))
            projets = proj_result.scalars().all()
        else:
            entreprises_data = [
                {"raison_sociale": "AVELIS PROMOTION SARL", "nif": "001234567890", "rc": "16/00-1234567B89",
                 "forme_juridique": "SARL", "capital_social": 10_000_000, "adresse": "Cité 800 logements, Bt A1, Bordj El Kiffan, Alger",
                 "telephone": "+213 21 55 66 77", "email": "contact@avelispromo.dz"},
                {"raison_sociale": "AVELIS CONSTRUCTION SPA", "nif": "002345678901", "rc": "16/00-2345678C90",
                 "forme_juridique": "SPA", "capital_social": 50_000_000, "adresse": "Zone industrielle, Rouiba, Alger",
                 "telephone": "+213 21 44 55 66", "email": "contact@avelisconstruction.dz"},
                {"raison_sociale": "IMMO INVEST EURL", "nif": "003456789012", "rc": "16/00-3456789D01",
                 "forme_juridique": "EURL", "capital_social": 5_000_000, "adresse": "Boulevard Mohamed V, Alger Centre",
                 "telephone": "+213 21 33 44 55", "email": "contact@immoinvest.dz"},
            ]
            entreprises = []
            for ed in entreprises_data:
                e = Entreprise(id=uid(), tenant_id=T, **ed)
                db.add(e)
                entreprises.append(e)
            await db.flush()

            projets_data = [
                {"entreprise": entreprises[0], "code": "RES-BEK-01", "nom": "Résidence El Firdaous — Bordj El Kiffan",
                 "type_projet": "IMMOBILIER", "wilaya": "Alger", "commune": "Bordj El Kiffan",
                 "nombre_lots": 120, "budget_previsionnel": 850_000_000, "taux_avancement": 65},
                {"entreprise": entreprises[0], "code": "RES-DRG-02", "nom": "Résidence Les Jardins — Dergana",
                 "type_projet": "IMMOBILIER", "wilaya": "Alger", "commune": "Dergana",
                 "nombre_lots": 80, "budget_previsionnel": 520_000_000, "taux_avancement": 30},
                {"entreprise": entreprises[1], "code": "INF-ROU-01", "nom": "Programme 500 Logements — Rouiba",
                 "type_projet": "INFRASTRUCTURE", "wilaya": "Alger", "commune": "Rouiba",
                 "nombre_lots": 500, "budget_previsionnel": 2_500_000_000, "taux_avancement": 10},
                {"entreprise": entreprises[2], "code": "COM-ALG-01", "nom": "Centre Commercial — Alger Centre",
                 "type_projet": "COMMERCIAL", "wilaya": "Alger", "commune": "Alger Centre",
                 "nombre_lots": 45, "budget_previsionnel": 350_000_000, "taux_avancement": 85},
            ]
            projets = []
            for pd in projets_data:
                ent = pd.pop("entreprise")
                p = Projet(id=uid(), tenant_id=T, entreprise_id=ent.id, statut=StatutProjet.ACTIF,
                           date_debut=date(2024, 3, 1), date_fin_prevue=date(2027, 6, 30), **pd)
                db.add(p)
                projets.append(p)
            await db.flush()

            # Associés
            associes_data = [
                {"nom": "BENALI Ahmed", "part_pct": 60},
                {"nom": "KHEDIM Youcef", "part_pct": 25},
                {"nom": "MANSOURI Karim", "part_pct": 15},
            ]
            for ad in associes_data:
                a = Associe(id=uid(), tenant_id=T, entreprise_id=entreprises[0].id,
                            nom=ad["nom"], prenom="", part_pct=ad["part_pct"])
                db.add(a)
            await db.flush()
            print(f"Created {len(entreprises)} entreprises, {len(projets)} projets, {len(associes_data)} associés")

        # ════════════════════════════════════════════════════════════════
        # 2. EMPLOYEES
        # ════════════════════════════════════════════════════════════════
        from app.models.hr import Employee, EmploymentStatus

        existing_emp = await db.execute(select(Employee).where(Employee.tenant_id == T).limit(1))
        if existing_emp.scalar_one_or_none():
            print("Employees already exist, checking SPI fields...")
            emp_result = await db.execute(select(Employee).where(Employee.tenant_id == T))
            employees = emp_result.scalars().all()
            # Update SPI fields if needed
            for emp in employees:
                if not emp.prime_spi_plafond or float(emp.prime_spi_plafond or 0) == 0:
                    emp.prime_spi_plafond = 15000
                    emp.avenant_spi_signe = True
            await db.flush()
        else:
            employees_data = [
                {"first_name": "Ahmed", "last_name": "DENDANI", "employee_number": "EMP-001",
                 "department": "Direction Générale", "position": "Directeur Général",
                 "base_salary": 250000, "prime_spi_plafond": 50000, "email": "ahmed.dendani@promo-avelis.com",
                 "manager_name": "Ahmed Dendani", "mentor_name": "Ahmed Dendani"},
                {"first_name": "Djamel", "last_name": "ADJAOUD", "employee_number": "EMP-002",
                 "department": "Direction Générale / Département Ressources Humaines (RH)", "position": "Office Manager / RH",
                 "base_salary": 180000, "prime_spi_plafond": 35000, "email": "djamel.adjaoud@promo-avelis.com",
                 "manager_name": "Ahmed Dendani", "mentor_name": "Ahmed Dendani"},
                {"first_name": "Lyazid", "last_name": "BOUABDELLAH", "employee_number": "EMP-003",
                 "department": "Direction Générale / Département Administratif et Financier", "position": "Manager Finance",
                 "base_salary": 160000, "prime_spi_plafond": 30000, "email": "lyazid.bouabdellah@promo-avelis.com",
                 "manager_name": "Ahmed Dendani", "mentor_name": "Ahmed Dendani"},
                {"first_name": "Rachid", "last_name": "LAMRANI", "employee_number": "EMP-004",
                 "department": "Direction Générale / Département Commercial et Marketing", "position": "Marketing & Sales Performance Manager",
                 "base_salary": 150000, "prime_spi_plafond": 30000, "est_commercial": True,
                 "objectif_ventes_mensuel": 50000000, "email": "rachid.lamrani@promo-avelis.com",
                 "manager_name": "Ahmed Dendani", "mentor_name": "Ahmed Dendani"},
                {"first_name": "Yasmina", "last_name": "BARACHE", "employee_number": "EMP-005",
                 "department": "Direction Générale / Service Après-Vente (SAV) / Relation Client", "position": "Manager Supply Chain Générale",
                 "base_salary": 120000, "prime_spi_plafond": 25000, "email": "yasmine.barache@promo-avelis.com",
                 "manager_name": "Ahmed Dendani", "mentor_name": "Ahmed Dendani"},
                {"first_name": "Brahim", "last_name": "SEDDIKI", "employee_number": "EMP-006",
                 "department": "Direction Générale / Département Ressources Humaines (RH)", "position": "Gestionnaire GDS MGX et Acheteur De Service",
                 "base_salary": 80000, "prime_spi_plafond": 15000, "email": "brahim.seddiki@promo.avelis.com",
                 "manager_name": "Adjaoud Djamel", "mentor_name": "Adjaoud Djamel"},
                {"first_name": "Zahia", "last_name": "BENALLAL", "employee_number": "EMP-007",
                 "department": "Direction Générale / Département Ressources Humaines (RH)", "position": "RH",
                 "base_salary": 70000, "prime_spi_plafond": 15000, "email": "zahia.benallal@promo-avelis.com",
                 "manager_name": "Adjaoud Djamel", "mentor_name": "Adjaoud Djamel"},
                {"first_name": "Hichem", "last_name": "MOUHOUB", "employee_number": "EMP-008",
                 "department": "Direction Générale / Département Administratif et Financier", "position": "Manager Finance",
                 "base_salary": 120000, "prime_spi_plafond": 25000, "email": "hichem.mouhoub@promo-avelis.com",
                 "manager_name": "Lyazid Bouabdellah", "mentor_name": "Lyazid Bouabdellah"},
                {"first_name": "Mourad", "last_name": "MEZIANI", "employee_number": "EMP-009",
                 "department": "Direction Générale / Département Commercial et Marketing", "position": "Commercial",
                 "base_salary": 80000, "prime_spi_plafond": 20000, "est_commercial": True,
                 "objectif_ventes_mensuel": 30000000, "email": "mourad.meziani@promo-avelis.com",
                 "manager_name": "Lyazid Bouabdellah", "mentor_name": "Lyazid Bouabdellah"},
                {"first_name": "Oussama", "last_name": "BOUNOUA", "employee_number": "EMP-010",
                 "department": "Direction Générale / Département Commercial et Marketing", "position": "Sales Admin & Tender Officer",
                 "base_salary": 75000, "prime_spi_plafond": 15000, "est_commercial": True,
                 "objectif_ventes_mensuel": 25000000, "email": "oussama.bounoua@promo-avelis.com",
                 "manager_name": "Lamrani Rachid", "mentor_name": "Lamrani Rachid"},
                {"first_name": "Rafik", "last_name": "BETIT", "employee_number": "EMP-011",
                 "department": "Direction Générale / Département Ressources Humaines (RH)", "position": "Agent de Sécurité",
                 "base_salary": 45000, "prime_spi_plafond": 10000, "email": None,
                 "manager_name": "Seddiki Brahim", "mentor_name": "Seddiki Brahim"},
                {"first_name": "Djazia", "last_name": "MANSOURI", "employee_number": "EMP-012",
                 "department": "Direction Générale", "position": None,
                 "base_salary": 60000, "prime_spi_plafond": 12000, "email": "djazia.mansouri@promo-avelis.com",
                 "manager_name": "Ahmed Dendani", "mentor_name": "Ahmed Dendani"},
                {"first_name": "Ahmed", "last_name": "ABBAS", "employee_number": "EMP-013",
                 "department": None, "position": None,
                 "base_salary": 50000, "prime_spi_plafond": 10000, "email": None, "phone": "0549007000"},
                {"first_name": "Saadi", "last_name": "AMMOUR", "employee_number": "EMP-014",
                 "department": None, "position": None,
                 "base_salary": 50000, "prime_spi_plafond": 10000, "email": None, "phone": "0549007000"},
                {"first_name": "Farah", "last_name": "ATTAR", "employee_number": "EMP-015",
                 "department": None, "position": None,
                 "base_salary": 55000, "prime_spi_plafond": 12000, "email": "farah.attar@promo-avelis.com"},
                {"first_name": "Abir", "last_name": "ABDALLAH", "employee_number": "EMP-016",
                 "department": None, "position": None,
                 "base_salary": 55000, "prime_spi_plafond": 12000, "email": "abdallah.abir@promo-avelis.com"},
                {"first_name": "Samira", "last_name": "AMROUCHE", "employee_number": "EMP-017",
                 "department": None, "position": None,
                 "base_salary": 50000, "prime_spi_plafond": 10000, "email": None, "phone": "0549007000"},
                {"first_name": "Sabrina", "last_name": "BEN SEKKA", "employee_number": "EMP-018",
                 "department": None, "position": None,
                 "base_salary": 50000, "prime_spi_plafond": 10000, "email": "sabrina.bensekka@promo-avelis.com"},
                {"first_name": "Mohamed", "last_name": "BABOU", "employee_number": "EMP-019",
                 "department": None, "position": None,
                 "base_salary": 55000, "prime_spi_plafond": 12000, "email": "mohamed.babou@promo-avelis.com"},
                {"first_name": "Hanane", "last_name": "BOUTOBZA", "employee_number": "EMP-020",
                 "department": None, "position": None,
                 "base_salary": 55000, "prime_spi_plafond": 12000, "email": "hanane.boutobza@promo-avelis.com"},
                {"first_name": "Wafa", "last_name": "FERGUOUS", "employee_number": "EMP-021",
                 "department": None, "position": None,
                 "base_salary": 55000, "prime_spi_plafond": 12000, "email": "wafa.ferguous@promo-avelis.com"},
                {"first_name": "Safa", "last_name": "FOUDIA", "employee_number": "EMP-022",
                 "department": None, "position": None,
                 "base_salary": 55000, "prime_spi_plafond": 12000, "email": "safa.foudia@promo-avelis.com"},
                {"first_name": "Leila", "last_name": "HAMI", "employee_number": "EMP-023",
                 "department": None, "position": None,
                 "base_salary": 55000, "prime_spi_plafond": 12000, "email": "laila.hami@promo-avelis.com"},
                {"first_name": "Omar", "last_name": "REZIKI", "employee_number": "EMP-024",
                 "department": None, "position": None,
                 "base_salary": 50000, "prime_spi_plafond": 10000, "email": "omar.reziki@promo-avelis.com"},
                {"first_name": "Amira", "last_name": "LAICHE", "employee_number": "EMP-025",
                 "department": None, "position": None,
                 "base_salary": 55000, "prime_spi_plafond": 12000, "email": "amira.laiche@promo-avelis.com"},
                {"first_name": "Nesrine", "last_name": "DJETTOU", "employee_number": "EMP-026",
                 "department": None, "position": None,
                 "base_salary": 55000, "prime_spi_plafond": 12000, "email": "nessrine.djettou@promo-avelis.com"},
                {"first_name": "Meroua", "last_name": "DJEBARNI", "employee_number": "EMP-027",
                 "department": None, "position": None,
                 "base_salary": 55000, "prime_spi_plafond": 12000, "email": "meroua.djebarni@promo-avelis.com"},
                {"first_name": "Yasmine", "last_name": "ZAAF", "employee_number": "EMP-028",
                 "department": None, "position": None,
                 "base_salary": 55000, "prime_spi_plafond": 12000, "email": "yasmine.zaaf@promo-avelis.com"},
                {"first_name": "Imene", "last_name": "SEMAOUNE", "employee_number": "EMP-029",
                 "department": None, "position": None,
                 "base_salary": 55000, "prime_spi_plafond": 12000, "email": "imene.semaoune@promo.avelis.com"},
                {"first_name": "Hacene", "last_name": "OULD SAID", "employee_number": "EMP-030",
                 "department": None, "position": None,
                 "base_salary": 50000, "prime_spi_plafond": 10000, "email": "hacene.ouldsaid@promo-avelis.mom"},
            ]

            employees = []
            for i, ed in enumerate(employees_data):
                spi_fields = {
                    "prime_spi_plafond": ed.pop("prime_spi_plafond", 15000),
                    "avenant_spi_signe": True,
                    "solde_bonus_malus": 0,
                    "spi_courant": 0,
                    "mois_consecutifs_sous_50": 0,
                    "mois_consecutifs_sous_70": 0,
                    "statut_rh": "ACTIF",
                    "est_commercial": ed.pop("est_commercial", False),
                    "objectif_ventes_mensuel": ed.pop("objectif_ventes_mensuel", None),
                }
                # Link first employee to admin user
                user_id = admin.id if i == 0 else None
                emp = Employee(
                    id=uid(), tenant_id=T, status=EmploymentStatus.ACTIVE,
                    hire_date=date(2023, 1, 15) + timedelta(days=i * 30),
                    user_id=user_id,
                    entite_juridique_id=entreprises[0].id,
                    projets_affectes=json.dumps({projets[0].id: 60, projets[1].id: 40}),
                    **ed, **spi_fields,
                )
                # Set manager
                if i > 0:
                    emp.manager_id = employees[0].id  # Everyone reports to DG
                db.add(emp)
                employees.append(emp)
            await db.flush()

            # Link admin user to first employee
            admin.employee_id = employees[0].id
            await db.flush()
            print(f"Created {len(employees)} employees")

        # ════════════════════════════════════════════════════════════════
        # 3. TACHES SPI + OFFRES PERFORMANCE
        # ════════════════════════════════════════════════════════════════
        from app.models.planification import (
            TacheSPI, StatutTache, PrioriteTache, SourceTache,
            OffrePerformance, StatutOffre, ResultatOffre,
            SPIMensuel, AlerteRH, TypeAlerte, PlanStrategique, StatutPlan, HorizonPlan,
        )

        existing_tache = await db.execute(select(TacheSPI).where(TacheSPI.tenant_id == T).limit(1))
        if existing_tache.scalar_one_or_none():
            print("TacheSPI already exist, skipping tasks/SPI...")
        else:
            today = date.today()
            mois_courant = today.strftime("%Y-%m")
            mois_precedent = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

            # ── Tasks for each employee ──
            task_templates = [
                # Employee 0 (DG) — strategic tasks
                {"titre": "Valider le budget prévisionnel Q2 2026", "priorite": PrioriteTache.CRITIQUE,
                 "source": SourceTache.OBJECTIF_CEO, "statut": StatutTache.VALIDEE,
                 "score_execution": 95, "score_qualite": 90, "score_global_tache": 92.5,
                 "valide_par_systeme": True, "valide_par_manager": True, "delta_days": -5},
                # Employee 1 (DAF) — finance tasks
                {"titre": "Préparer les états financiers mensuels", "priorite": PrioriteTache.ELEVEE,
                 "source": SourceTache.OBJECTIF_MANAGER, "statut": StatutTache.VALIDEE,
                 "score_execution": 100, "score_qualite": 85, "score_global_tache": 92.5,
                 "valide_par_systeme": True, "valide_par_manager": True, "delta_days": -3},
                {"titre": "Réconciliation bancaire comptes courants", "priorite": PrioriteTache.NORMALE,
                 "source": SourceTache.OBJECTIF_MANAGER, "statut": StatutTache.EN_COURS,
                 "delta_days": 5},
                # Employee 2 (Dir Commercial) — sales tasks
                {"titre": "Objectif ventes mensuel 50M DA — Résidence El Firdaous", "priorite": PrioriteTache.CRITIQUE,
                 "source": SourceTache.CRM, "statut": StatutTache.VALIDEE,
                 "score_execution": 100, "score_qualite": 95, "score_global_tache": 97.5,
                 "valide_par_systeme": True, "valide_par_manager": True, "delta_days": -2},
                {"titre": "Relance clients en retard de paiement", "priorite": PrioriteTache.ELEVEE,
                 "source": SourceTache.CRM, "statut": StatutTache.EN_REVUE,
                 "score_execution": 75, "delta_days": 1},
                # Employee 3 (RH) — HR tasks
                {"titre": "Traitement paie mensuelle Mars 2026", "priorite": PrioriteTache.CRITIQUE,
                 "source": SourceTache.OBJECTIF_MANAGER, "statut": StatutTache.VALIDEE,
                 "score_execution": 100, "score_qualite": 90, "score_global_tache": 95,
                 "valide_par_systeme": True, "valide_par_manager": True, "delta_days": -1},
                {"titre": "Planification formation sécurité chantier", "priorite": PrioriteTache.NORMALE,
                 "source": SourceTache.OBJECTIF_MANAGER, "statut": StatutTache.VALIDEE,
                 "score_execution": 80, "score_qualite": 75, "score_global_tache": 77.5,
                 "valide_par_systeme": True, "valide_par_manager": True, "delta_days": -7},
                # Employee 4 (Conseiller Commercial)
                {"titre": "Prospection nouveaux clients — Zone Dergana", "priorite": PrioriteTache.ELEVEE,
                 "source": SourceTache.CRM, "statut": StatutTache.VALIDEE,
                 "score_execution": 85, "score_qualite": 80, "score_global_tache": 82.5,
                 "valide_par_systeme": True, "valide_par_manager": True, "delta_days": -4},
                {"titre": "Suivi contrat client BERRAHMA — lot F3", "priorite": PrioriteTache.NORMALE,
                 "source": SourceTache.CRM, "statut": StatutTache.EN_COURS,
                 "delta_days": 3},
                # Employee 5 (Téléconseillère)
                {"titre": "Appels sortants leads site web — 50 appels/jour", "priorite": PrioriteTache.NORMALE,
                 "source": SourceTache.CRM, "statut": StatutTache.VALIDEE,
                 "score_execution": 70, "score_qualite": 65, "score_global_tache": 67.5,
                 "valide_par_systeme": True, "valide_par_manager": True, "delta_days": -6},
                # Employee 6 (Chef de chantier)
                {"titre": "Supervision coulage dalle — Bâtiment C", "priorite": PrioriteTache.CRITIQUE,
                 "source": SourceTache.OBJECTIF_MANAGER, "statut": StatutTache.VALIDEE,
                 "score_execution": 100, "score_qualite": 95, "score_global_tache": 97.5,
                 "valide_par_systeme": True, "valide_par_manager": True, "delta_days": 0},
                {"titre": "Contrôle qualité ferraillage étage 3", "priorite": PrioriteTache.ELEVEE,
                 "source": SourceTache.OBJECTIF_MANAGER, "statut": StatutTache.EN_COURS,
                 "delta_days": 2},
                # Employee 7 (Chargée Finance)
                {"titre": "Saisie factures fournisseurs Février", "priorite": PrioriteTache.NORMALE,
                 "source": SourceTache.OBJECTIF_MANAGER, "statut": StatutTache.VALIDEE,
                 "score_execution": 90, "score_qualite": 85, "score_global_tache": 87.5,
                 "valide_par_systeme": True, "valide_par_manager": True, "delta_days": -2},
                # Employee 8 (Magasinier)
                {"titre": "Inventaire stock ciment et acier", "priorite": PrioriteTache.NORMALE,
                 "source": SourceTache.MAINTENANCE, "statut": StatutTache.VALIDEE,
                 "score_execution": 75, "score_qualite": 70, "score_global_tache": 72.5,
                 "valide_par_systeme": True, "valide_par_manager": True, "delta_days": -3},
                {"titre": "Réception livraison briques — 20 palettes", "priorite": PrioriteTache.ELEVEE,
                 "source": SourceTache.MAINTENANCE, "statut": StatutTache.REJETEE,
                 "score_execution": 25, "score_qualite": 0, "score_global_tache": 0,
                 "valide_par_systeme": False, "valide_par_manager": False, "delta_days": -10},
                # Employee 9 (Marketing)
                {"titre": "Campagne réseaux sociaux — Résidence Les Jardins", "priorite": PrioriteTache.ELEVEE,
                 "source": SourceTache.OBJECTIF_MANAGER, "statut": StatutTache.VALIDEE,
                 "score_execution": 90, "score_qualite": 88, "score_global_tache": 89,
                 "valide_par_systeme": True, "valide_par_manager": True, "delta_days": -1},
                # Employee 10 (Architecte)
                {"titre": "Plans exécution Bâtiment D — Résidence El Firdaous", "priorite": PrioriteTache.CRITIQUE,
                 "source": SourceTache.OBJECTIF_MANAGER, "statut": StatutTache.VALIDEE,
                 "score_execution": 95, "score_qualite": 92, "score_global_tache": 93.5,
                 "valide_par_systeme": True, "valide_par_manager": True, "delta_days": -2},
                # Employee 11 (Archiviste)
                {"titre": "Classement dossiers contrats clients Q1", "priorite": PrioriteTache.BASSE,
                 "source": SourceTache.MAINTENANCE, "statut": StatutTache.VALIDEE,
                 "score_execution": 100, "score_qualite": 80, "score_global_tache": 90,
                 "valide_par_systeme": True, "valide_par_manager": True, "delta_days": -4},
            ]

            # Assign tasks to employees round-robin style
            emp_idx = 0
            seq = 1
            all_taches = []
            for tt in task_templates:
                emp = employees[min(emp_idx, len(employees) - 1)]
                delta = tt.pop("delta_days", 0)
                deadline = today + timedelta(days=delta)
                tache = TacheSPI(
                    id=uid(), tenant_id=T,
                    reference=f"TACHE-2026-{seq:04d}",
                    titre=tt["titre"],
                    description=f"Tâche assignée: {tt['titre']}",
                    assignee_id=emp.id,
                    assigneur_id=employees[0].id,
                    source_type=tt["source"],
                    priorite=tt["priorite"],
                    statut=tt["statut"],
                    date_debut_prevue=deadline - timedelta(days=7),
                    date_fin_prevue=deadline,
                    date_debut_reelle=deadline - timedelta(days=6) if tt["statut"] != StatutTache.ASSIGNEE else None,
                    date_fin_reelle=deadline - timedelta(days=abs(delta)) if tt["statut"] == StatutTache.VALIDEE else None,
                    score_execution=tt.get("score_execution"),
                    score_qualite=tt.get("score_qualite"),
                    score_global_tache=tt.get("score_global_tache"),
                    valide_par_systeme=tt.get("valide_par_systeme"),
                    valide_par_manager=tt.get("valide_par_manager"),
                    date_validation=datetime.utcnow() if tt.get("valide_par_manager") else None,
                    projet_id=projets[0].id,
                    entite_juridique_id=entreprises[0].id,
                    kpis=[{"indicateur": "Taux completion", "cible": 100, "unite": "%", "valeur_reelle": tt.get("score_execution", 0)}],
                    task_type="daily_plan",
                    required_role={"CRM": "sales", "MAINTENANCE": "operations"}.get(tt["source"].value, "operations"),
                    source_text=f"Manager instruction: {tt['titre']}",
                )
                db.add(tache)
                all_taches.append(tache)
                seq += 1
                emp_idx += 1

            await db.flush()
            print(f"Created {len(all_taches)} TacheSPI records")

            # ── OffrePerformance for some validated tasks ──
            offres_created = 0
            for tache in all_taches:
                if tache.statut == StatutTache.VALIDEE and float(tache.score_global_tache or 0) > 0:
                    bonus_pct = 5.0 if float(tache.score_global_tache) >= 90 else 3.0
                    emp = next(e for e in employees if e.id == tache.assignee_id)
                    plafond = float(emp.prime_spi_plafond or 15000)
                    bonus_da = round(plafond * bonus_pct / 100, 2)
                    resultat = ResultatOffre.BONUS_VERSE if float(tache.score_global_tache) >= 75 else ResultatOffre.MALUS_APPLIQUE
                    montant = bonus_da if resultat == ResultatOffre.BONUS_VERSE else -bonus_da

                    offre = OffrePerformance(
                        id=uid(), tenant_id=T,
                        tache_id=tache.id, employe_id=tache.assignee_id,
                        bonus_propose_pct=bonus_pct, bonus_propose_da=bonus_da,
                        bonus_final_pct=bonus_pct, bonus_final_da=bonus_da, malus_final_da=bonus_da,
                        statut=StatutOffre.EXECUTEE, resultat=resultat,
                        montant_applique=montant,
                        signature_employe=True, signature_manager=True,
                        date_verrouillage=datetime.utcnow(),
                    )
                    db.add(offre)
                    offres_created += 1
            await db.flush()
            print(f"Created {offres_created} OffrePerformance records")

            # ── SPIMensuel for current + previous month ──
            spi_scores = {
                0: {"c1": 92, "c2": 88, "c3": 95, "c4": 85},   # DG
                1: {"c1": 88, "c2": 90, "c3": 92, "c4": 82},   # DAF
                2: {"c1": 85, "c2": 90, "c3": 88, "c4": 95},   # Dir Commercial
                3: {"c1": 90, "c2": 85, "c3": 95, "c4": 78},   # RH
                4: {"c1": 78, "c2": 75, "c3": 80, "c4": 82},   # Conseiller Commercial
                5: {"c1": 65, "c2": 60, "c3": 70, "c4": 55},   # Téléconseillère (low)
                6: {"c1": 95, "c2": 92, "c3": 88, "c4": 85},   # Chef de chantier
                7: {"c1": 82, "c2": 85, "c3": 90, "c4": 78},   # Chargée Finance
                8: {"c1": 60, "c2": 55, "c3": 75, "c4": 50},   # Magasinier (low)
                9: {"c1": 85, "c2": 88, "c3": 85, "c4": 80},   # Marketing
                10: {"c1": 90, "c2": 95, "c3": 85, "c4": 88},  # Architecte
                11: {"c1": 88, "c2": 80, "c3": 90, "c4": 72},  # Archiviste
            }

            from app.services.spi_engine import compute_prime_spi, ROLE_WEIGHTS, DEFAULT_WEIGHTS

            for mois in [mois_precedent, mois_courant]:
                for i, emp in enumerate(employees):
                    scores = spi_scores.get(i, {"c1": 70, "c2": 70, "c3": 70, "c4": 70})
                    # Slight variation for previous month
                    if mois == mois_precedent:
                        scores = {k: max(0, min(100, v - 5 + (i % 7))) for k, v in scores.items()}

                    # Get role weights
                    pos = (emp.position or "").upper()
                    weights = DEFAULT_WEIGHTS.copy()
                    for role_key, role_weights in ROLE_WEIGHTS.items():
                        if role_key in pos:
                            weights = role_weights
                            break

                    score_spi = round((scores["c1"] * weights["c1"] + scores["c2"] * weights["c2"] +
                                       scores["c3"] * weights["c3"] + scores["c4"] * weights["c4"]) / 100.0, 2)
                    score_spi = min(max(score_spi, 0), 100)

                    prime = compute_prime_spi(score_spi, float(emp.prime_spi_plafond or 15000))

                    spi_m = SPIMensuel(
                        id=uid(), tenant_id=T,
                        employe_id=emp.id, mois=mois,
                        c1_execution=scores["c1"], c2_qualite=scores["c2"],
                        c3_comportement=scores["c3"], c4_metier=scores["c4"],
                        w1=weights["c1"], w2=weights["c2"], w3=weights["c3"], w4=weights["c4"],
                        score_spi=score_spi, fiabilite_score=85 + (i % 15),
                        prime_calculee=prime, malus_calcule=0,
                        solde_bm_mois=0, commission_mois=0, prime_plan=0,
                        taches_total=2, taches_validees=1 + (1 if score_spi > 75 else 0),
                        taches_rejetees=1 if score_spi < 60 else 0,
                        taches_en_retard=1 if score_spi < 70 else 0,
                        est_confirme=mois == mois_precedent,
                        valide_par_manager=mois == mois_precedent,
                    )
                    db.add(spi_m)

                    # Update employee current SPI
                    if mois == mois_courant:
                        emp.spi_courant = score_spi

            await db.flush()
            print(f"Created {len(employees) * 2} SPIMensuel records (2 months)")

            # ── AlerteRH for low performers ──
            for i, emp in enumerate(employees):
                spi = float(emp.spi_courant or 0)
                if spi < 70 and spi > 0:
                    alert_type = TypeAlerte.AVERTISSEMENT if spi < 50 else TypeAlerte.SURVEILLANCE
                    severity = "CRITICAL" if spi < 50 else "WARNING"
                    alerte = AlerteRH(
                        id=uid(), tenant_id=T, employe_id=emp.id,
                        type_alerte=alert_type,
                        message=f"SPI {spi}% — {'Avertissement formel' if spi < 50 else 'Sous surveillance'}",
                        severite=severity, mois_reference=mois_courant, score_spi=spi,
                    )
                    db.add(alerte)
            await db.flush()

            # ── Plan Stratégique ──
            plan = PlanStrategique(
                id=uid(), tenant_id=T,
                reference="PLAN-2026-0001",
                proposeur_id=employees[2].id,  # Dir Commercial proposes
                titre="Expansion commerciale Zone Est Alger — Q2 2026",
                description="Ouvrir 3 nouveaux points de vente dans les communes de Bab Ezzouar, Dar El Beida et Rouiba pour capter la demande croissante en logement.",
                objectif_mesurable="Augmenter le volume de ventes de 30% sur Q2 vs Q1",
                horizon=HorizonPlan.MOIS_3,
                statut=StatutPlan.VALIDE,
                valideur_id=employees[0].id,
                date_validation=datetime.utcnow(),
                montant_prime=float(employees[2].base_salary or 160000) * 0.05,
                prime_versee=True,
                avancement_pct=25,
                score_pertinence_ia=82,
                faisabilite_score=78,
                projet_id=projets[0].id,
                entite_juridique_id=entreprises[0].id,
            )
            db.add(plan)

            plan2 = PlanStrategique(
                id=uid(), tenant_id=T,
                reference="PLAN-2026-0002",
                proposeur_id=employees[9].id,  # Marketing proposes
                titre="Stratégie digitale — Refonte site web + SEO",
                description="Refondre le site web, optimiser le SEO, et lancer des campagnes Google Ads pour générer 200+ leads/mois.",
                objectif_mesurable="200 leads qualifiés par mois d'ici Juin 2026",
                horizon=HorizonPlan.MOIS_6,
                statut=StatutPlan.SOUMIS,
                score_pertinence_ia=75,
                faisabilite_score=85,
            )
            db.add(plan2)
            await db.flush()
            print("Created 2 PlanStrategique records")

        # ════════════════════════════════════════════════════════════════
        # 4. ADV: Clients, Contracts, Payments
        # ════════════════════════════════════════════════════════════════
        from app.models.adv import Client, Contract, ContractStatus, Payment, Receivable, PaymentStatus
        from app.models.financial import Encaissement, Decaissement, StatutFiscal

        existing_client = await db.execute(select(Client).where(Client.tenant_id == T).limit(1))
        if existing_client.scalar_one_or_none():
            print("ADV data already exists, skipping...")
        else:
            clients_data = [
                {"code": "CLI-001", "name": "BERRAHMA Mourad", "phone": "+213 555 12 34 56",
                 "email": "berrahma@gmail.com", "city": "Alger", "address": "Cité Bab Ezzouar Bt 12"},
                {"code": "CLI-002", "name": "HAMIDOUCHE Nadia", "phone": "+213 555 23 45 67",
                 "email": "hamidouche.n@gmail.com", "city": "Blida", "address": "Rue du 1er Novembre"},
                {"code": "CLI-003", "name": "SAIDI Mohamed", "phone": "+213 555 34 56 78",
                 "email": "saidi.med@gmail.com", "city": "Boumerdes"},
                {"code": "CLI-004", "name": "BENMOUSSA Khadija", "phone": "+213 555 45 67 89",
                 "email": "benmoussa.k@outlook.com", "city": "Alger", "address": "Hydra, Lot 15"},
                {"code": "CLI-005", "name": "OUARAB Sofiane", "phone": "+213 555 56 78 90",
                 "email": "ouarab.s@gmail.com", "city": "Tizi Ouzou"},
                {"code": "CLI-006", "name": "ZIANE Farida", "phone": "+213 555 67 89 01",
                 "email": "ziane.f@yahoo.com", "city": "Alger", "address": "Kouba, Résidence El Amir"},
                {"code": "CLI-007", "name": "SCI BATIMMO", "legal_name": "SCI BATIMMO SARL",
                 "phone": "+213 21 88 99 00", "email": "contact@batimmo.dz", "city": "Alger",
                 "tax_id": "NIF-004567890123"},
                {"code": "CLI-008", "name": "MEBARKI Abdelhak", "phone": "+213 555 78 90 12",
                 "email": "mebarki.a@gmail.com", "city": "Oran"},
            ]
            clients = []
            for cd in clients_data:
                c = Client(id=uid(), tenant_id=T, entreprise_id=entreprises[0].id,
                           projet_id=projets[0].id, country="Algérie", **cd)
                db.add(c)
                clients.append(c)
            await db.flush()

            # Contracts
            lot_types = ["F3", "F4", "F3", "F5", "F3", "F4", "DUPLEX", "F3"]
            lot_prices = [8_500_000, 12_000_000, 8_800_000, 15_500_000, 9_200_000, 11_500_000, 22_000_000, 8_700_000]

            contracts = []
            for i, client in enumerate(clients):
                lot_num = f"L{(i+1):03d}"
                contract = Contract(
                    id=uid(), tenant_id=T, client_id=client.id,
                    entreprise_id=entreprises[0].id, projet_id=projets[0].id,
                    contract_number=f"CTR-2026-{(i+1):04d}",
                    title=f"Vente Lot {lot_num} — {lot_types[i]} — Résidence El Firdaous",
                    status=ContractStatus.ACTIVE if i < 6 else ContractStatus.DRAFT,
                    start_date=date(2025, 6, 1) + timedelta(days=i * 30),
                    total_amount=lot_prices[i],
                    currency="DZD",
                    terms={"lot_number": lot_num, "type": lot_types[i], "etage": (i % 5) + 1,
                           "superficie": 85 + (i * 10), "mode_paiement": "APPORT_50" if i < 4 else "CREDIT"},
                    created_by=admin.id,
                )
                db.add(contract)
                contracts.append(contract)

            await db.flush()

            # Receivables & Payments
            for i, contract in enumerate(contracts):
                total = float(contract.total_amount)
                # Each contract has 3-4 payment tranches
                tranches = [
                    {"pct": 0.30, "label": "Apport initial", "status": PaymentStatus.PAID, "paid": True},
                    {"pct": 0.25, "label": "2ème tranche", "status": PaymentStatus.PAID if i < 4 else PaymentStatus.PENDING, "paid": i < 4},
                    {"pct": 0.25, "label": "3ème tranche", "status": PaymentStatus.PENDING, "paid": False},
                    {"pct": 0.20, "label": "Remise des clés", "status": PaymentStatus.PENDING, "paid": False},
                ]
                for j, tr in enumerate(tranches):
                    amount = round(total * tr["pct"], 2)
                    due = date(2025, 6, 1) + timedelta(days=i * 30 + j * 90)
                    recv = Receivable(
                        id=uid(), tenant_id=T, client_id=clients[i].id, contract_id=contract.id,
                        entreprise_id=entreprises[0].id, projet_id=projets[0].id,
                        invoice_ref=f"FAC-{contract.contract_number}-T{j+1}",
                        amount=amount, amount_paid=amount if tr["paid"] else 0,
                        due_date=due, status=tr["status"], currency="DZD",
                    )
                    db.add(recv)
                    await db.flush()

                    if tr["paid"]:
                        pay_date = due + timedelta(days=2)
                        payment = Payment(
                            id=uid(), tenant_id=T, client_id=clients[i].id,
                            receivable_id=recv.id,
                            entreprise_id=entreprises[0].id, projet_id=projets[0].id,
                            payment_ref=f"PAY-{contract.contract_number}-T{j+1}",
                            amount=amount, currency="DZD",
                            payment_date=pay_date,
                            payment_method="CHEQUE" if j == 0 else "VIREMENT",
                        )
                        db.add(payment)

                        # Bridge: also create Encaissement for CC visibility
                        enc = Encaissement(
                            id=uid(), tenant_id=T,
                            entreprise_id=entreprises[0].id,
                            projet_id=projets[0].id,
                            date_encaissement=pay_date,
                            montant=amount,
                            statut_fiscal=StatutFiscal.REEL_DECLARE,
                            moyen_paiement="CHEQUE" if j == 0 else "VIREMENT",
                            reference=f"ADV-{contract.contract_number}-T{j+1}",
                            description=f"Paiement client {clients[i].name}",
                        )
                        db.add(enc)

            await db.flush()
            print(f"Created {len(clients)} clients, {len(contracts)} contracts, receivables & payments")

        # ════════════════════════════════════════════════════════════════
        # 5. CC HIERARCHIQUE (Centre de Coût)
        # ════════════════════════════════════════════════════════════════
        from app.models.cc_hierarchique import CCNode, CategorieCC, CCImputation, TypeImputation, SensImputation

        existing_cc = await db.execute(select(CCNode).where(CCNode.tenant_id == T).limit(1))
        if existing_cc.scalar_one_or_none():
            print("CC nodes already exist, skipping...")
        else:
            # Build a 3-level CC hierarchy: Groupe → Entreprise → Projet
            groupe_node = CCNode(
                id=uid(), tenant_id=T,
                code="GRP-AVELIS", libelle="Groupe AVELIS PROMOTION",
                categorie=CategorieCC.ADMIN, niveau=0,
                chemin_complet="GRP-AVELIS",
                entreprise_id=None, projet_id=None,
            )
            db.add(groupe_node)
            await db.flush()

            for ent in entreprises:
                ent_code = f"ENT-{ent.raison_sociale[:10].upper().replace(' ', '')}"
                ent_node = CCNode(
                    id=uid(), tenant_id=T,
                    code=ent_code, libelle=ent.raison_sociale,
                    categorie=CategorieCC.ADMIN, niveau=1,
                    chemin_complet=f"GRP-AVELIS/{ent_code}",
                    parent_id=groupe_node.id,
                    entreprise_id=ent.id,
                )
                db.add(ent_node)
                await db.flush()

                # Project nodes under this enterprise
                for proj in projets:
                    if proj.entreprise_id == ent.id:
                        proj_node = CCNode(
                            id=uid(), tenant_id=T,
                            code=proj.code, libelle=proj.nom,
                            categorie=CategorieCC.CONSTR, niveau=2,
                            chemin_complet=f"GRP-AVELIS/{ent_code}/{proj.code}",
                            parent_id=ent_node.id,
                            entreprise_id=ent.id, projet_id=proj.id,
                            budget_annuel_prevu=float(proj.budget_previsionnel or 0),
                        )
                        db.add(proj_node)
                        await db.flush()

                        # Sub-categories under each project
                        sub_categories = [
                            (CategorieCC.TERRAIN, "Terrain", 3),
                            (CategorieCC.CONSTR, "Construction", 3),
                            (CategorieCC.COMMERCIAL, "Commercial", 3),
                            (CategorieCC.MASSE_SAL, "Masse Salariale", 3),
                        ]
                        for cat, label, niv in sub_categories:
                            sub_code = f"{proj.code}/{cat.value}"
                            sub_node = CCNode(
                                id=uid(), tenant_id=T,
                                code=sub_code, libelle=f"{label} — {proj.nom[:30]}",
                                categorie=cat, niveau=niv,
                                chemin_complet=f"GRP-AVELIS/{ent_code}/{proj.code}/{cat.value}",
                                parent_id=proj_node.id,
                                entreprise_id=ent.id, projet_id=proj.id,
                            )
                            db.add(sub_node)
                            await db.flush()

                        # Add some imputations on the project node
                        imputations_data = [
                            {"type_imputation": TypeImputation.ENCAISSEMENT, "sens": SensImputation.CREDIT,
                             "montant": 25_000_000, "libelle": "Apports clients Février", "realite_financiere": "RF1"},
                            {"type_imputation": TypeImputation.ENCAISSEMENT, "sens": SensImputation.CREDIT,
                             "montant": 18_000_000, "libelle": "Paiements clients Mars", "realite_financiere": "RF1"},
                            {"type_imputation": TypeImputation.DECAISSEMENT_DIRECT, "sens": SensImputation.DEBIT,
                             "montant": 8_500_000, "libelle": "Travaux béton Bat C", "realite_financiere": "RF1"},
                            {"type_imputation": TypeImputation.DECAISSEMENT_DIRECT, "sens": SensImputation.DEBIT,
                             "montant": 3_200_000, "libelle": "Matériaux construction", "realite_financiere": "RF1"},
                            {"type_imputation": TypeImputation.CFF, "sens": SensImputation.DEBIT,
                             "montant": 1_800_000, "libelle": "Honoraires architecte", "realite_financiere": "RF2"},
                        ]
                        for imp_data in imputations_data:
                            imp = CCImputation(
                                id=uid(), tenant_id=T,
                                cc_node_id=proj_node.id,
                                date_imputation=date(2026, 2, 15),
                                periode="2026-02",
                                quote_parts=[],
                                **imp_data,
                            )
                            db.add(imp)

            await db.flush()
            print("Created CC hierarchy (Groupe -> Entreprise -> Projet) with imputations")

        # ════════════════════════════════════════════════════════════════
        # COMMIT ALL
        # ════════════════════════════════════════════════════════════════
        await db.commit()
        print("\n=== ALL DUMMY DATA SEEDED SUCCESSFULLY ===")
        print(f"Login: admin@gfi.ma / admin123")
        print(f"Frontend: http://localhost:3003")
        print(f"Backend API: http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(main())
