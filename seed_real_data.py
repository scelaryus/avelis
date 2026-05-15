"""Seed the 9 real entités juridiques, 9 associés, 16 projets, and participation matrix.

Source of truth: SPECIFICATION_GFI7_V3.1_CORRIGEE.md — Sections 1.1, 1.2, 1.3, 1.4

Run: python seed_real_data.py
"""
import asyncio
import uuid
import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))


def uid():
    return str(uuid.uuid4())


# ── Fixed UUIDs for stable references ──
TENANT_ID = "00000000-0000-0000-0000-000000000001"
ADMIN_ID = "00000000-0000-0000-0000-000000000099"

# Entreprise IDs
ENT_IDS = {
    "ETS-DK":   "ent-0001-0000-0000-000000000001",
    "SARL-DP":  "ent-0002-0000-0000-000000000002",
    "SARL-DBPI":"ent-0003-0000-0000-000000000003",
    "SARL-OC":  "ent-0004-0000-0000-000000000004",
    "SARL-SEN": "ent-0005-0000-0000-000000000005",
    "SARL-EP":  "ent-0006-0000-0000-000000000006",
    "EURL-BIM": "ent-0007-0000-0000-000000000007",
    "SARL-AMF": "ent-0008-0000-0000-000000000008",
    "EURL-BAY": "ent-0009-0000-0000-000000000009",
}

# Associé IDs
ASS_IDS = {
    "Ahmed":      "ass-0001-0000-0000-000000000001",
    "Mohamed":    "ass-0002-0000-0000-000000000002",
    "Yazid":      "ass-0003-0000-0000-000000000003",
    "Yamina":     "ass-0004-0000-0000-000000000004",
    "Boumerdassi":"ass-0005-0000-0000-000000000005",
    "Amirat":     "ass-0006-0000-0000-000000000006",
    "Laid":       "ass-0007-0000-0000-000000000007",
    "Moukhtari_T":"ass-0008-0000-0000-000000000008",
    "Moukhtari_A":"ass-0009-0000-0000-000000000009",
}

# ── Data from spec Section 1.1 ──
ENTREPRISES = [
    {"code": "ETS-DK",   "raison_sociale": "ETS Dendani Khadidja",     "forme_juridique": "ETS",  "statut": "ACTIF — À FERMER", "role_principal": "Entité historique"},
    {"code": "SARL-DP",  "raison_sociale": "SARL Dendani Promotion",   "forme_juridique": "SARL", "statut": "ACTIF",            "role_principal": "Promotion immobilière"},
    {"code": "SARL-DBPI","raison_sociale": "SARL DBPI Immobilier",     "forme_juridique": "SARL", "statut": "ACTIF — À FERMER", "role_principal": "Promotion immobilière"},
    {"code": "SARL-OC",  "raison_sociale": "SARL Omega Construction",  "forme_juridique": "SARL", "statut": "À FERMER",         "role_principal": "Construction"},
    {"code": "SARL-SEN", "raison_sociale": "SARL Senimar",             "forme_juridique": "SARL", "statut": "À DÉVELOPPER",     "role_principal": "Promotion immobilière"},
    {"code": "SARL-EP",  "raison_sociale": "SARL Avelis Promotion",     "forme_juridique": "SARL", "statut": "À DÉVELOPPER",     "role_principal": "Portefeuille Avelis"},
    {"code": "EURL-BIM", "raison_sociale": "EURL Bimha Construction",  "forme_juridique": "EURL", "statut": "À DÉVELOPPER",     "role_principal": "Construction et réalisation"},
    {"code": "SARL-AMF", "raison_sociale": "SARL AMENFORT Béton",      "forme_juridique": "SARL", "statut": "DISSOUTE",         "role_principal": "Origine du capital"},
    {"code": "EURL-BAY", "raison_sociale": "EURL BAYTI / ALLO MAISON", "forme_juridique": "EURL", "statut": "SATELLITE",        "role_principal": "Satellite (factures RF3)"},
]

# ── Data from spec Section 1.2 ──
ASSOCIES = [
    {"key": "Ahmed",      "nom": "DENDANI",      "prenom": "Ahmed",    "est_fondateur": True,  "ordre_priorite": "A", "role": "DAF / Gérant"},
    {"key": "Mohamed",    "nom": "DENDANI",      "prenom": "Mohamed",  "est_fondateur": True,  "ordre_priorite": "B", "role": "Associé"},
    {"key": "Yazid",      "nom": "DENDANI",      "prenom": "Yazid (Lyazid)", "est_fondateur": True, "ordre_priorite": "C", "role": "Associé"},
    {"key": "Yamina",     "nom": "DENDANI",      "prenom": "Yamina (Ait Benamara)", "est_fondateur": True, "ordre_priorite": "D", "role": "Associée"},
    {"key": "Boumerdassi","nom": "BOUMERDASSI",  "prenom": "Mustapha", "est_fondateur": False, "ordre_priorite": "E", "role": "Associé projet"},
    {"key": "Amirat",     "nom": "AMIRAT",       "prenom": "Brahim",   "est_fondateur": False, "ordre_priorite": "F", "role": "Associé projet"},
    {"key": "Laid",       "nom": "DENDANI",      "prenom": "Laid",     "est_fondateur": False, "ordre_priorite": "G", "role": "Associé projet"},
    {"key": "Moukhtari_T","nom": "MOUKHTARI",    "prenom": "Tarek",    "est_fondateur": False, "ordre_priorite": "H", "role": "Associé projet"},
    {"key": "Moukhtari_A","nom": "MOUKHTARI",    "prenom": "Amine",    "est_fondateur": False, "ordre_priorite": "I", "role": "Associé projet"},
]

# ── Data from spec Section 1.4 — Matrice de participation par entité (% entreprise) ──
# Only the 7 active/operational entities (AMENFORT and BAYTI have no active participation)
PARTICIPATION_MATRIX = {
    # entité_code: {associé_key: pourcentage}
    "ETS-DK":    {"Ahmed": 25.0, "Mohamed": 25.0, "Yazid": 25.0, "Yamina": 25.0},
    "SARL-DP":   {"Ahmed": 25.0, "Mohamed": 25.0, "Yazid": 25.0, "Yamina": 25.0},
    "SARL-DBPI": {"Ahmed": 60.0, "Mohamed": 20.0, "Yazid": 20.0, "Yamina": 0.0},
    "SARL-OC":   {"Ahmed": 60.0, "Mohamed": 20.0, "Yazid": 20.0, "Yamina": 0.0},
    "SARL-SEN":  {"Ahmed": 60.0, "Mohamed": 20.0, "Yazid": 20.0, "Yamina": 0.0},
    "SARL-EP":   {"Ahmed": 60.0, "Mohamed": 20.0, "Yazid": 20.0, "Yamina": 0.0},
    "EURL-BIM":  {"Ahmed": 60.0, "Mohamed": 20.0, "Yazid": 20.0, "Yamina": 0.0},
}

# ── Data from spec Section 1.3 — Projects ──
PROJETS = [
    {"code": "JASMIN",      "nom": "Les Jasmins / Sahel",          "entite": "ETS-DK",   "statut": "ACTIF",        "parts": {"Ahmed": 34, "Mohamed": 33, "Yazid": 33, "Yamina": 0}},
    {"code": "EDEN",        "nom": "Eden / Foes",                  "entite": "ETS-DK",   "statut": "ACTIF",        "parts": {"Ahmed": 25, "Mohamed": 25, "Yazid": 25, "Yamina": 25}},
    {"code": "OPERA",       "nom": "Jardin de l'Opéra / Ouled Fayet","entite": "SARL-DP","statut": "ACTIF",        "parts": {"Ahmed": 25, "Mohamed": 25, "Yazid": 25, "Yamina": 25}},
    {"code": "LYS",         "nom": "Les Lys / 02 Hectare / Draria","entite": "SARL-DBPI","statut": "ACTIF",        "parts": {"Ahmed": 60, "Mohamed": 20, "Yazid": 20, "Yamina": 0}},
    {"code": "T21000",      "nom": "Terrain 21 000 m²",            "entite": "ETS-DK",   "statut": "TERRAIN",      "parts": {"Ahmed": 25, "Mohamed": 25, "Yazid": 25, "Yamina": 25}},
    {"code": "T5000",       "nom": "Terrain 5 000 m²",             "entite": "SARL-DBPI","statut": "EN ATTENTE",   "parts": {"Ahmed": 50, "Laid": 50}},
    {"code": "T2400",       "nom": "Terrain 2 400 m²",             "entite": "SARL-DBPI","statut": "TERRAIN",      "parts": {"Ahmed": 50, "Mohamed": 50}},
    {"code": "IRENE",       "nom": "Irène / 05 ha / Ami Djamel",   "entite": "SARL-DP",  "statut": "ACTIF",        "parts": {"Ahmed": 60, "Mohamed": 20, "Yazid": 20, "Yamina": 0}},
    {"code": "MAGNOLIA",    "nom": "Magnolia",                     "entite": "SARL-OC",  "statut": "ACTIF",        "parts": {"Ahmed": 60, "Mohamed": 20, "Yazid": 20, "Yamina": 0}},
    {"code": "AUREA",       "nom": "Auréa / Chéraga",              "entite": "SARL-DP",  "statut": "ACTIF",        "parts": {"Ahmed": 60, "Mohamed": 20, "Yazid": 20, "Yamina": 0}},
    {"code": "ASTERIA",     "nom": "Asteria / El Achour",          "entite": "SARL-SEN", "statut": "ACTIF",        "parts": {"Ahmed": 60, "Mohamed": 20, "Yazid": 20, "Yamina": 0}},
    {"code": "MOSQUEE",     "nom": "Mosquée Taoura",               "entite": "ETS-DK",   "statut": "DONATION",     "parts": {"Ahmed": 34, "Mohamed": 33, "Yazid": 33, "Yamina": 0}},
    {"code": "AVELIS-DRIVE", "nom": "Avelis Drive",                  "entite": "EURL-BIM", "statut": "À DÉVELOPPER", "parts": {}},
    {"code": "ALLO-MAISON", "nom": "Allo Maison",                  "entite": "SARL-DP",  "statut": "À DÉVELOPPER", "parts": {}},
    {"code": "PFSB",        "nom": "PFSB",                         "entite": "EURL-BIM", "statut": "À DÉVELOPPER", "parts": {}},
    {"code": "DG",          "nom": "DG",                           "entite": "SARL-DBPI","statut": "À DÉVELOPPER", "parts": {}},
]


async def main():
    from app.database import AsyncSessionLocal, async_engine, Base
    from sqlalchemy import text

    # Import all models
    import app.models.core
    import app.models.hr
    import app.models.adv
    import app.models.financial
    import app.models.legal
    import app.models.spi
    import app.models.treasury
    import app.models.registry
    import app.models.integrations
    import app.models.finance_associes
    import app.models.bim_edd
    import app.models.cff
    import app.models.rbac_gfi
    import app.models.juridique

    async with AsyncSessionLocal() as session:
        # ── 1. Create tenant ──
        await session.execute(text("""
            INSERT OR REPLACE INTO tenants (id, name, code, description)
            VALUES (:id, :name, :code, :desc)
        """), {"id": TENANT_ID, "name": "Groupe Dendani", "code": "GD", "desc": "Groupe Dendani — Bab Ezzouar, Alger"})

        # ── 2. Create admin user ──
        from app.auth.security import get_password_hash
        pwd_hash = get_password_hash("admin123")
        await session.execute(text("""
            INSERT OR REPLACE INTO users (id, tenant_id, email, hashed_password, full_name, role, is_active)
            VALUES (:id, :tid, :email, :pwd, :name, :role, 1)
        """), {"id": ADMIN_ID, "tid": TENANT_ID, "email": "admin@gfi.dz", "pwd": pwd_hash, "name": "Ahmed Dendani (Admin)", "role": "admin"})

        # ── 3. Create 9 entreprises ──
        for ent in ENTREPRISES:
            ent_id = ENT_IDS[ent["code"]]
            await session.execute(text("""
                INSERT OR REPLACE INTO entreprises (id, tenant_id, code, raison_sociale, forme_juridique, statut, role_principal, devise, is_active)
                VALUES (:id, :tid, :code, :rs, :fj, :st, :rp, 'DZD', :active)
            """), {
                "id": ent_id, "tid": TENANT_ID,
                "code": ent["code"], "rs": ent["raison_sociale"],
                "fj": ent["forme_juridique"], "st": ent["statut"],
                "rp": ent["role_principal"],
                "active": 0 if ent["statut"] == "DISSOUTE" else 1,
            })
        print(f"Created {len(ENTREPRISES)} entreprises")

        # ── 4. Create 9 associés ──
        # Associates are linked to a "primary" enterprise (first founder enterprise)
        # but the real participation is in entreprise_associes
        first_ent_id = ENT_IDS["ETS-DK"]
        for ass in ASSOCIES:
            ass_id = ASS_IDS[ass["key"]]
            await session.execute(text("""
                INSERT OR REPLACE INTO associes (id, tenant_id, entreprise_id, nom, prenom, part_pct, est_fondateur, ordre_priorite, is_active)
                VALUES (:id, :tid, :eid, :nom, :prenom, :pct, :fond, :ordre, 1)
            """), {
                "id": ass_id, "tid": TENANT_ID, "eid": first_ent_id,
                "nom": ass["nom"], "prenom": ass["prenom"],
                "pct": 25.0 if ass["est_fondateur"] else 0.0,
                "fond": 1 if ass["est_fondateur"] else 0,
                "ordre": ass["ordre_priorite"],
            })
        print(f"Created {len(ASSOCIES)} associés")

        # ── 5. Create entreprise_associes (participation matrix) ──
        ea_count = 0
        for ent_code, parts in PARTICIPATION_MATRIX.items():
            ent_id = ENT_IDS[ent_code]
            for ass_key, pct in parts.items():
                ass_id = ASS_IDS[ass_key]
                ea_id = uid()
                await session.execute(text("""
                    INSERT OR REPLACE INTO entreprise_associes (id, entreprise_id, associe_id, pourcentage, est_actif)
                    VALUES (:id, :eid, :aid, :pct, 1)
                """), {"id": ea_id, "eid": ent_id, "aid": ass_id, "pct": pct / 100.0})
                ea_count += 1
        print(f"Created {ea_count} entreprise-associé links")

        # ── 6. Create 16 projets ──
        for proj in PROJETS:
            ent_id = ENT_IDS[proj["entite"]]
            proj_id = uid()
            await session.execute(text("""
                INSERT INTO projets (id, tenant_id, entreprise_id, code, nom, statut, is_active)
                VALUES (:id, :tid, :eid, :code, :nom, :statut, 1)
            """), {
                "id": proj_id, "tid": TENANT_ID, "eid": ent_id,
                "code": proj["code"], "nom": proj["nom"], "statut": proj["statut"],
            })
        print(f"Created {len(PROJETS)} projets")

        await session.commit()

        # ── 7. Seed SCF plan comptable & default journals ──
        from app.services.scf_plan_comptable import seed_scf_plan_comptable, ensure_default_journals
        accounts = await seed_scf_plan_comptable(session, TENANT_ID)
        journals = await ensure_default_journals(session, TENANT_ID)
        print(f"Created {accounts} SCF accounts, {journals} default journals")

        # ── 7b. Create CCAs for 4 founders (EX-CCA-001) ──
        cca_count = 0
        for ass in ASSOCIES:
            if ass["est_fondateur"]:
                ass_id = ASS_IDS[ass["key"]]
                await session.execute(text("""
                    INSERT OR IGNORE INTO comptes_courants_associes
                    (id, associe_id, solde_global, solde_disponible_retrait, solde_avances_non_remboursees, est_gele)
                    VALUES (:id, :aid, 5000000, 2500000, 0, 0)
                """), {"id": uid(), "aid": ass_id})
                cca_count += 1
        print(f"Created {cca_count} CCA accounts for founders (EX-CCA-001)")
        await session.commit()

        # ── 7c. Seed grille salariale (EX-RH-001) ──
        GRILLE = [
            ("DIRECTION", 1, "Directeur Général", 450000, 30000, 5000, 0, 0),
            ("DIRECTION", 2, "Directeur de département", 220000, 20000, 5000, 0, 0),
            ("CADRE", 1, "Cadre supérieur", 180000, 15000, 5000, 0, 0),
            ("CADRE", 2, "Cadre confirmé", 150000, 12000, 5000, 0, 0),
            ("CADRE", 3, "Cadre junior", 120000, 10000, 5000, 0, 0),
            ("MAITRISE", 1, "Chef d'équipe", 110000, 8000, 5000, 3000, 0),
            ("MAITRISE", 2, "Technicien supérieur", 95000, 6000, 5000, 3000, 0),
            ("MAITRISE", 3, "Technicien", 80000, 5000, 5000, 3000, 0),
            ("EXECUTION", 1, "Agent qualifié", 65000, 4000, 5000, 3000, 2000),
            ("EXECUTION", 2, "Agent", 55000, 3000, 5000, 3000, 2000),
            ("COMMERCIAL", 1, "Responsable commercial", 150000, 10000, 5000, 0, 0),
            ("COMMERCIAL", 2, "Commercial confirmé", 100000, 8000, 5000, 0, 0),
            ("COMMERCIAL", 3, "Commercial junior", 80000, 5000, 5000, 0, 0),
        ]
        for cat, ech, intitule, base, exp, transport, panier, nuisance in GRILLE:
            await session.execute(text("""
                INSERT INTO grille_salariale (id, tenant_id, categorie, echelon, intitule, salaire_base,
                    indemnite_experience, indemnite_transport, indemnite_panier, prime_nuisance, is_active)
                VALUES (:id, :tid, :cat, :ech, :int, :base, :exp, :tr, :pan, :nui, 1)
            """), {
                "id": uid(), "tid": TENANT_ID, "cat": cat, "ech": ech, "int": intitule,
                "base": base, "exp": exp, "tr": transport, "pan": panier, "nui": nuisance,
            })
        print(f"Created {len(GRILLE)} salary grid entries (EX-RH-001)")
        await session.commit()

        # ── 8. Seed departments ──
        DEPARTMENTS = [
            ("DG", "Direction Générale", None, 0),
            ("DAF", "Direction Administrative et Financière", "DG", 1),
            ("DMV", "Direction Marketing et Ventes", "DG", 2),
            ("DO", "Direction des Opérations", "DG", 3),
            ("DRH", "Direction des Ressources Humaines", "DG", 4),
            ("DJ", "Direction Juridique", "DG", 5),
            ("COMPTA", "Service Comptabilité", "DAF", 10),
            ("TRESOR", "Service Trésorerie", "DAF", 11),
            ("ADV", "Service ADV", "DMV", 20),
            ("MKTG", "Service Marketing", "DMV", 21),
            ("CHANTIER", "Service Chantiers", "DO", 30),
            ("ACHATS", "Service Achats & Logistique", "DO", 31),
            ("QUALITE", "Service Qualité", "DO", 32),
        ]
        dept_ids = {}
        for code, name, parent_code, sort in DEPARTMENTS:
            did = uid()
            dept_ids[code] = did
            parent = dept_ids.get(parent_code)
            await session.execute(text("""
                INSERT INTO departments (id, tenant_id, code, name, parent_id, sort_order, is_active)
                VALUES (:id, :tid, :code, :name, :pid, :sort, 1)
            """), {"id": did, "tid": TENANT_ID, "code": code, "name": name, "pid": parent, "sort": sort})
        print(f"Created {len(DEPARTMENTS)} departments")

        # ── 9. Seed employees ──
        from datetime import timedelta
        import random
        random.seed(42)

        EMPLOYEES = [
            # (num, first, last, dept, position, entity, salary, is_commercial, est_declare)
            ("EMP001", "Ahmed", "DENDANI", "DG", "Directeur Général / DAF", "ETS-DK", 450000, False, True),
            ("EMP002", "Karim", "BENSAID", "DAF", "Responsable Comptabilité", "SARL-DP", 180000, False, True),
            ("EMP003", "Nassima", "HAMIDI", "COMPTA", "Comptable", "SARL-DP", 120000, False, True),
            ("EMP004", "Sofiane", "MEDJDOUB", "DMV", "Directeur Commercial", "SARL-DP", 200000, True, True),
            ("EMP005", "Amina", "KHELIFI", "ADV", "Responsable ADV", "SARL-DP", 150000, True, True),
            ("EMP006", "Yacine", "BOUDIAF", "ADV", "Commercial", "SARL-DP", 100000, True, True),
            ("EMP007", "Fatima", "ZERROUKI", "ADV", "Téléconseillère", "SARL-DP", 80000, True, True),
            ("EMP008", "Rachid", "HAMADACHE", "DO", "Directeur Opérations", "SARL-OC", 220000, False, True),
            ("EMP009", "Mourad", "AITOUCHE", "CHANTIER", "Chef de chantier JASMIN", "ETS-DK", 130000, False, True),
            ("EMP010", "Slimane", "BENALI", "CHANTIER", "Chef de chantier LYS", "SARL-DBPI", 130000, False, True),
            ("EMP011", "Omar", "FERHAT", "CHANTIER", "Conducteur travaux", "SARL-OC", 110000, False, True),
            ("EMP012", "Nadia", "BERKANI", "DRH", "Responsable RH", "SARL-DP", 160000, False, True),
            ("EMP013", "Djamel", "TOUATI", "ACHATS", "Responsable Achats", "SARL-DP", 140000, False, True),
            ("EMP014", "Samira", "HADDAD", "MKTG", "Chargée Marketing", "SARL-DP", 110000, True, True),
            ("EMP015", "Lyes", "MESSAOUD", "QUALITE", "Ingénieur Qualité", "SARL-OC", 135000, False, True),
            ("EMP016", "Hakim", "SAIDI", "DJ", "Juriste", "SARL-DP", 150000, False, True),
            ("EMP017", "Meriem", "BOUZIDI", "TRESOR", "Trésorière", "SARL-DP", 125000, False, True),
            ("EMP018", "Kamel", "RAHMANI", "ADV", "Commercial terrain", "SARL-SEN", 95000, True, False),
            ("EMP019", "Farid", "MOHAMMEDI", "CHANTIER", "Chef de chantier IRENE", "SARL-DP", 130000, False, True),
            ("EMP020", "Rania", "ABDELLI", "ADV", "Assistante ADV", "EURL-BIM", 85000, True, True),
        ]
        emp_ids = {}
        for num, first, last, dept, position, ent_code, salary, is_comm, est_decl in EMPLOYEES:
            eid = uid()
            emp_ids[num] = eid
            hire = date(2020, 1, 1) + timedelta(days=random.randint(0, 1500))
            spi = round(random.uniform(40, 95), 2)
            await session.execute(text("""
                INSERT INTO employees (
                    id, tenant_id, employee_number, first_name, last_name,
                    email, department, position, department_id,
                    entite_juridique_id, base_salary, currency,
                    hire_date, is_active, status, est_declare_cnas,
                    est_commercial, spi_courant, realite_financiere,
                    statut_rh
                ) VALUES (
                    :id, :tid, :num, :first, :last,
                    :email, :dept, :pos, :did,
                    :eid, :sal, 'DZD',
                    :hire, 1, 'ACTIVE', :decl,
                    :comm, :spi, :rf,
                    'ACTIF'
                )
            """), {
                "id": eid, "tid": TENANT_ID, "num": num,
                "first": first, "last": last,
                "email": f"{first.lower()}.{last.lower()}@gfi.dz",
                "dept": dept, "pos": position, "did": dept_ids.get(dept),
                "eid": ENT_IDS.get(ent_code), "sal": salary,
                "hire": hire.isoformat(), "decl": 1 if est_decl else 0,
                "comm": 1 if is_comm else 0, "spi": spi,
                "rf": "RF1" if est_decl else "RF2",
            })
        print(f"Created {len(EMPLOYEES)} employees")
        await session.commit()

        # ── 10. Seed transactions (across entities/projects) ──
        # Fetch real project IDs
        proj_rows = await session.execute(text(
            "SELECT id, code, entreprise_id FROM projets WHERE tenant_id = :tid"
        ), {"tid": TENANT_ID})
        proj_map = {r[1]: (r[0], r[2]) for r in proj_rows.fetchall()}

        txn_count = 0
        base_date = date(2025, 7, 1)
        TXN_DATA = [
            # (ent_code, proj_code, rf, type, montant, desc, compte_d, compte_c)
            ("ETS-DK", "JASMIN", "RF1", "ENCAISSEMENT", 3500000, "Vente appart F3 Bloc A", "512", "701"),
            ("ETS-DK", "JASMIN", "RF2", "ENCAISSEMENT", 1200000, "Complément espèces client", "531", "701"),
            ("ETS-DK", "EDEN", "RF1", "ENCAISSEMENT", 4800000, "Vente appart F4 Bloc B", "512", "701"),
            ("SARL-DP", "OPERA", "RF1", "ENCAISSEMENT", 5200000, "Vente appart F3", "512", "701"),
            ("SARL-DP", "IRENE", "RF1", "ENCAISSEMENT", 2900000, "Vente terrain lot 12", "512", "701"),
            ("SARL-DP", "AUREA", "RF1", "ENCAISSEMENT", 6100000, "Vente F4 duplex", "512", "701"),
            ("SARL-DP", "AUREA", "RF2", "ENCAISSEMENT", 2000000, "Complément espèces", "531", "701"),
            ("SARL-DBPI", "LYS", "RF1", "ENCAISSEMENT", 3800000, "Vente F3 niveau 2", "512", "701"),
            ("SARL-OC", "MAGNOLIA", "RF1", "ENCAISSEMENT", 2200000, "Vente studio", "512", "701"),
            ("SARL-SEN", "ASTERIA", "RF1", "ENCAISSEMENT", 4500000, "Vente F3 bloc C", "512", "701"),
            # Décaissements
            ("ETS-DK", "JASMIN", "RF1", "DECAISSEMENT", 1800000, "Travaux gros oeuvre ST", "605", "401"),
            ("ETS-DK", "JASMIN", "RF1", "DECAISSEMENT", 450000, "Matériaux ciment/fer", "601", "401"),
            ("SARL-DP", "IRENE", "RF1", "DECAISSEMENT", 2200000, "Travaux fondations", "605", "401"),
            ("SARL-DP", "AUREA", "RF1", "DECAISSEMENT", 3100000, "Travaux structure", "605", "401"),
            ("SARL-DBPI", "LYS", "RF1", "DECAISSEMENT", 1500000, "Travaux VRD", "605", "401"),
            ("SARL-OC", "MAGNOLIA", "RF1", "DECAISSEMENT", 950000, "Matériaux second oeuvre", "602", "401"),
            # Salaires
            ("SARL-DP", None, "RF1", "DECAISSEMENT", 1850000, "Salaires mensuels Mars", "631", "421"),
            ("ETS-DK", None, "RF1", "DECAISSEMENT", 580000, "Salaires mensuels Mars", "631", "421"),
            ("SARL-OC", None, "RF1", "DECAISSEMENT", 475000, "Salaires mensuels Mars", "631", "421"),
            # CNAS
            ("SARL-DP", None, "RF1", "DECAISSEMENT", 480000, "Cotisations CNAS T1", "635", "431"),
            ("ETS-DK", None, "RF1", "DECAISSEMENT", 150000, "Cotisations CNAS T1", "635", "431"),
            # Factures RF3 inter-groupe
            ("SARL-DP", "OPERA", "RF3", "ENCAISSEMENT", 1500000, "Facture RF3 SARL-DP → ETS-DK", "411", "701"),
            ("SARL-OC", "MAGNOLIA", "RF3", "ENCAISSEMENT", 800000, "Facture RF3 SARL-OC → SARL-DP", "411", "701"),
            # TVA
            ("SARL-DP", None, "RF1", "DECAISSEMENT", 988000, "TVA collectée Mars", "4457", "512"),
            ("SARL-DP", None, "RF1", "ENCAISSEMENT", 418000, "TVA déductible Mars", "4456", "512"),
            # TAP
            ("SARL-DP", None, "RF1", "DECAISSEMENT", 104000, "TAP Mars", "4471", "512"),
        ]
        import hashlib
        for i, (ent_code, proj_code, rf, typ, montant, desc, cd, cc) in enumerate(TXN_DATA):
            ent_id = ENT_IDS[ent_code]
            proj_id = proj_map[proj_code][0] if proj_code and proj_code in proj_map else None
            txn_date = base_date + timedelta(days=i * 3)
            h = hashlib.sha256(f"{ent_id}{txn_date}{montant}{i}".encode()).hexdigest()
            await session.execute(text("""
                INSERT INTO transactions (
                    id, tenant_id, entreprise_id, projet_id, realite_financiere,
                    type_transaction, montant, date_transaction, description,
                    reference, compte_debit, compte_credit, hash_sha256, created_by
                ) VALUES (
                    :id, :tid, :eid, :pid, :rf,
                    :typ, :montant, :dt, :desc,
                    :ref, :cd, :cc, :hash, :uid
                )
            """), {
                "id": uid(), "tid": TENANT_ID, "eid": ent_id, "pid": proj_id,
                "rf": rf, "typ": typ, "montant": montant, "dt": txn_date.isoformat(),
                "desc": desc, "ref": f"TXN-{2025}-{i+1:04d}", "cd": cd, "cc": cc,
                "hash": h, "uid": ADMIN_ID,
            })
            txn_count += 1
        print(f"Created {txn_count} transactions")
        await session.commit()

        # ── 11. Seed cost center hierarchy ──
        # Level 0: Groupe → Level 1: Entité → Level 2: Projet
        cc_count = 0
        root_id = uid()
        await session.execute(text("""
            INSERT INTO cc_nodes (id, tenant_id, code, libelle, niveau, parent_id, chemin_complet, est_actif, accepte_imputation)
            VALUES (:id, :tid, 'GD', 'Groupe Dendani', 0, NULL, '/GD', 1, 0)
        """), {"id": root_id, "tid": TENANT_ID})
        cc_count += 1

        for ent in ENTREPRISES:
            ent_node_id = uid()
            ent_code = ent["code"]
            await session.execute(text("""
                INSERT INTO cc_nodes (id, tenant_id, code, libelle, niveau, parent_id, chemin_complet, entreprise_id, est_actif, accepte_imputation)
                VALUES (:id, :tid, :code, :lib, 1, :pid, :path, :eid, 1, 0)
            """), {
                "id": ent_node_id, "tid": TENANT_ID, "code": ent_code,
                "lib": ent["raison_sociale"], "pid": root_id,
                "path": f"/GD/{ent_code}", "eid": ENT_IDS[ent_code],
            })
            cc_count += 1

            # Add project nodes under entity
            for proj in PROJETS:
                if proj["entite"] == ent_code:
                    proj_node_id = uid()
                    proj_id = proj_map.get(proj["code"], (None, None))[0]
                    await session.execute(text("""
                        INSERT INTO cc_nodes (id, tenant_id, code, libelle, niveau, parent_id, chemin_complet, entreprise_id, projet_id, est_actif, accepte_imputation)
                        VALUES (:id, :tid, :code, :lib, 2, :pid, :path, :eid, :projid, 1, 1)
                    """), {
                        "id": proj_node_id, "tid": TENANT_ID,
                        "code": f"{ent_code}/{proj['code']}",
                        "lib": proj["nom"], "pid": ent_node_id,
                        "path": f"/GD/{ent_code}/{proj['code']}",
                        "eid": ENT_IDS[ent_code], "projid": proj_id,
                    })
                    cc_count += 1
        print(f"Created {cc_count} cost center nodes")
        await session.commit()

        # ── 12. Seed SPI monthly scores ──
        spi_count = 0
        for m in [1, 2, 3]:
            mois_str = f"2025-{m:02d}"
            for num, first, last, dept, *_ in EMPLOYEES:
                eid = emp_ids[num]
                c1 = round(random.uniform(30, 100), 2)
                c2 = round(random.uniform(30, 100), 2)
                c3 = round(random.uniform(30, 100), 2)
                c4 = round(random.uniform(30, 100), 2)
                score = round(c1 * 0.30 + c2 * 0.25 + c3 * 0.25 + c4 * 0.20, 2)
                await session.execute(text("""
                    INSERT INTO spi_mensuels (
                        id, tenant_id, employe_id, mois,
                        c1_execution, c2_qualite, c3_comportement, c4_metier,
                        w1, w2, w3, w4, score_spi, est_confirme
                    ) VALUES (
                        :id, :tid, :eid, :mois,
                        :c1, :c2, :c3, :c4,
                        30, 25, 25, 20, :score, 1
                    )
                """), {
                    "id": uid(), "tid": TENANT_ID, "eid": eid,
                    "mois": mois_str,
                    "c1": c1, "c2": c2, "c3": c3, "c4": c4, "score": score,
                })
                spi_count += 1
        print(f"Created {spi_count} SPI monthly scores")

        # ── 13. Seed journal entries (from transactions) ──
        je_count = 0
        for i, (ent_code, proj_code, rf, typ, montant, desc, cd, cc) in enumerate(TXN_DATA[:10]):
            ent_id = ENT_IDS[ent_code]
            txn_date = base_date + timedelta(days=i * 3)
            je_id = uid()
            await session.execute(text("""
                INSERT INTO journal_entries (
                    id, tenant_id, entreprise_id, entry_date, reference,
                    description, status, realite_financiere, auto_generated
                ) VALUES (
                    :id, :tid, :eid, :dt, :ref,
                    :desc, 'COMMITTED', :rf, 1
                )
            """), {
                "id": je_id, "tid": TENANT_ID, "eid": ent_id,
                "dt": txn_date.isoformat(), "ref": f"JE-{2025}-{i+1:04d}",
                "desc": desc, "rf": rf,
            })
            # Debit line
            await session.execute(text("""
                INSERT INTO journal_lines (id, entry_id, line_no, account_code, label, debit, credit)
                VALUES (:id, :jid, 1, :ac, :label, :montant, 0)
            """), {"id": uid(), "jid": je_id, "ac": cd, "label": desc, "montant": montant})
            # Credit line
            await session.execute(text("""
                INSERT INTO journal_lines (id, entry_id, line_no, account_code, label, debit, credit)
                VALUES (:id, :jid, 2, :ac, :label, 0, :montant)
            """), {"id": uid(), "jid": je_id, "ac": cc, "label": desc, "montant": montant})
            je_count += 1
        print(f"Created {je_count} journal entries with {je_count * 2} lines")

        await session.commit()

        # ── 14. Seed chantier data (Section 10) ──
        # Sous-traitants
        ST_DATA = [
            ("ST BATIMEX", "GROS_OEUVRE", 85, 78, 90),
            ("ST ELECPRO", "ELECTRICITE", 72, 65, 88),
            ("ST HYDRA PLOMB", "PLOMBERIE", 80, 82, 75),
            ("ST PEINTURE PLUS", "PEINTURE", 90, 88, 85),
            ("ST VRD CONSTRUCT", "VRD", 68, 60, 70),
        ]
        st_ids = {}
        for nom, spec, sq, sd, ss in ST_DATA:
            sid = uid()
            st_ids[nom] = sid
            sg = round(sq * 0.4 + sd * 0.35 + ss * 0.25, 2)
            await session.execute(text("""
                INSERT INTO sous_traitants (id, tenant_id, raison_sociale, specialite,
                    score_qualite, score_delais, score_securite, score_global, nb_evaluations, est_agree, is_active)
                VALUES (:id, :tid, :nom, :spec, :sq, :sd, :ss, :sg, 3, 1, 1)
            """), {"id": sid, "tid": TENANT_ID, "nom": nom, "spec": spec, "sq": sq, "sd": sd, "ss": ss, "sg": sg})
        print(f"Created {len(ST_DATA)} sous-traitants")

        # Taches chantier for JASMIN project
        jasmin_id = proj_map.get("JASMIN", (None, None))[0]
        if jasmin_id:
            TACHES = [
                ("T001", "Terrassement et fondations", "GROS_OEUVRE", 100, "TERMINE", 8000000, 7800000),
                ("T002", "Structure béton RDC-R+4", "GROS_OEUVRE", 85, "EN_COURS", 25000000, 22000000),
                ("T003", "Maçonnerie et cloisons", "GROS_OEUVRE", 60, "EN_COURS", 12000000, 7500000),
                ("T004", "Plomberie et sanitaires", "PLOMBERIE", 30, "EN_COURS", 6000000, 2000000),
                ("T005", "Électricité courant fort/faible", "ELECTRICITE", 20, "EN_COURS", 8000000, 1800000),
                ("T006", "Enduit et peinture", "PEINTURE", 0, "A_FAIRE", 5000000, 0),
                ("T007", "VRD et espaces verts", "VRD", 10, "EN_COURS", 4000000, 500000),
                ("T008", "Menuiserie aluminium", "SECOND_OEUVRE", 0, "A_FAIRE", 7000000, 0),
            ]
            for code, lib, cat, avance, statut, budget, cout in TACHES:
                st_key = {"GROS_OEUVRE": "ST BATIMEX", "ELECTRICITE": "ST ELECPRO", "PLOMBERIE": "ST HYDRA PLOMB",
                           "PEINTURE": "ST PEINTURE PLUS", "VRD": "ST VRD CONSTRUCT"}.get(cat)
                await session.execute(text("""
                    INSERT INTO taches_chantier (id, tenant_id, projet_id, entreprise_id, code, libelle, categorie,
                        avancement_pct, statut, budget_prevu, cout_reel, sous_traitant_id, created_by)
                    VALUES (:id, :tid, :pid, :eid, :code, :lib, :cat, :av, :st, :bud, :cout, :stid, :uid)
                """), {
                    "id": uid(), "tid": TENANT_ID, "pid": jasmin_id, "eid": ENT_IDS["ETS-DK"],
                    "code": code, "lib": lib, "cat": cat, "av": avance, "st": statut,
                    "bud": budget, "cout": cout, "stid": st_ids.get(st_key), "uid": ADMIN_ID,
                })
            print(f"Created {len(TACHES)} taches chantier for JASMIN")

            # Situations de travaux
            for i, (st_nom, montant) in enumerate([
                ("ST BATIMEX", 7800000), ("ST HYDRA PLOMB", 2000000), ("ST ELECPRO", 1800000),
            ]):
                await session.execute(text("""
                    INSERT INTO situations_travaux (id, tenant_id, projet_id, entreprise_id, sous_traitant_id,
                        numero, periode, montant_ht, montant_tva, montant_ttc, retenue_garantie, montant_net,
                        avancement_cumule_pct, avancement_periode_pct, statut, realite_financiere, created_by)
                    VALUES (:id, :tid, :pid, :eid, :stid,
                        :num, :per, :ht, :tva, :ttc, :ret, :net,
                        :avc, :avp, 'VALIDEE', 'RF1', :uid)
                """), {
                    "id": uid(), "tid": TENANT_ID, "pid": jasmin_id, "eid": ENT_IDS["ETS-DK"],
                    "stid": st_ids[st_nom],
                    "num": f"SIT-2025-{i+1:03d}", "per": "2025-03",
                    "ht": montant, "tva": round(montant * 0.19), "ttc": round(montant * 1.19),
                    "ret": round(montant * 1.19 * 0.05), "net": round(montant * 1.19 * 0.95),
                    "avc": [85, 30, 20][i], "avp": [15, 10, 10][i], "uid": ADMIN_ID,
                })
            print(f"Created 3 situations de travaux")
        await session.commit()

        # ── 15. Seed ADV clients, contracts, EDD units, dossiers de vente ──
        # Clients
        ADV_CLIENTS = [
            ("CLT001", "BENHAMIDA Sofiane", "Alger", "SARL-DP", "AUREA"),
            ("CLT002", "MEBARKI Amina", "Blida", "SARL-DP", "AUREA"),
            ("CLT003", "TOUATI Rachid", "Boumerdes", "SARL-DP", "IRENE"),
            ("CLT004", "HADJ ARAB Yasmina", "Alger", "ETS-DK", "JASMIN"),
            ("CLT005", "BOUDIAF Karim", "Tipaza", "ETS-DK", "JASMIN"),
            ("CLT006", "FERHAT Nadia", "Alger", "ETS-DK", "EDEN"),
            ("CLT007", "SAHRAOUI Mohamed", "Alger", "SARL-DBPI", "LYS"),
            ("CLT008", "KHELIFI Djamel", "Alger", "SARL-OC", "MAGNOLIA"),
            ("CLT009", "BELKACEM Fatima", "Alger", "SARL-SEN", "ASTERIA"),
            ("CLT010", "RAHMANI Yacine", "Alger", "SARL-DP", "OPERA"),
        ]
        client_ids = {}
        for code, name, city, ent_code, proj_code in ADV_CLIENTS:
            cid = uid()
            client_ids[code] = cid
            ent_id = ENT_IDS.get(ent_code)
            pid = proj_map.get(proj_code, (None, None))[0]
            await session.execute(text("""
                INSERT INTO clients (id, tenant_id, entreprise_id, projet_id, code, name, city, is_active)
                VALUES (:id, :tid, :eid, :pid, :code, :name, :city, 1)
            """), {"id": cid, "tid": TENANT_ID, "eid": ent_id, "pid": pid,
                   "code": code, "name": name, "city": city})
        print(f"Created {len(ADV_CLIENTS)} ADV clients")

        # EDD projects + units (for AUREA as example)
        aurea_proj_id = uid()
        await session.execute(text("""
            INSERT INTO re_projects (id, tenant_id, code, name, status)
            VALUES (:id, :tid, 'AUREA', 'Résidence Auréa — Chéraga', 'ACTIVE')
        """), {"id": aurea_proj_id, "tid": TENANT_ID})

        aurea_blk_id = uid()
        await session.execute(text("""
            INSERT INTO re_blocks (id, project_id, code, name)
            VALUES (:id, :pid, 'BLKA', 'Bloc A')
        """), {"id": aurea_blk_id, "pid": aurea_proj_id})

        edd_unit_ids = []
        for floor in range(5):
            lvl_id = uid()
            lvl_code = f"L{floor:02d}" if floor > 0 else "RDC"
            await session.execute(text("""
                INSERT INTO re_levels (id, block_id, code)
                VALUES (:id, :bid, :code)
            """), {"id": lvl_id, "bid": aurea_blk_id, "code": lvl_code})

            for apt in range(1, 4):
                uid_val = uid()
                edd_unit_ids.append(uid_val)
                typo = ["F2", "F3", "F4"][apt - 1]
                sh = [55, 78, 105][apt - 1]
                price = sh * 120000
                await session.execute(text("""
                    INSERT INTO re_units (id, level_id, code, typology, area_sh, area_su, price_total, edd_state, usage_type)
                    VALUES (:id, :lid, :code, :typo, :sh, :su, :price, 'DRAFT', 'HABITATION')
                """), {
                    "id": uid_val, "lid": lvl_id,
                    "code": f"AUREA-BLKA-{lvl_code}-{apt:03d}",
                    "typo": typo, "sh": sh, "su": sh * 0.85, "price": price,
                })
        print(f"Created EDD: 1 project, 1 block, 5 levels, {len(edd_unit_ids)} units")

        # Dossiers de vente (some in various statuses)
        aurea_ent_id = ENT_IDS["SARL-DP"]
        aurea_projet_db_id = proj_map.get("AUREA", (None, None))[0]

        DOSSIERS = [
            ("AUREA-BLKA-RDC-001", "CLT001", "VENDU", "SPOT", 6600000, 2000000, 8600000, 8600000),
            ("AUREA-BLKA-RDC-002", "CLT002", "ENGAGE", "CREDIT_BANCAIRE", 9360000, 3000000, 5000000, 3000000),
            ("AUREA-BLKA-L01-001", "CLT003", "RESERVE", "SPOT", 6600000, 1500000, 1500000, 0),
            ("AUREA-BLKA-L01-002", None, "DISPONIBLE", None, 9360000, 0, 0, 0),
            ("AUREA-BLKA-L02-001", None, "DISPONIBLE", None, 12600000, 0, 0, 0),
            ("AUREA-BLKA-L02-002", "CLT010", "ENGAGE", "FONDS_PROPRES", 9360000, 2000000, 4500000, 2000000),
        ]
        for lot, clt_code, statut, mode, rf1, rf2, paye, rf2_recu in DOSSIERS:
            cid = client_ids.get(clt_code) if clt_code else None
            total = rf1 + rf2
            rf2_statut = "SECURISE" if rf2_recu >= rf2 and rf2 > 0 else ("EN_ATTENTE" if rf2 > 0 else "NON_APPLICABLE")
            await session.execute(text("""
                INSERT INTO dossiers_vente (
                    id, tenant_id, entreprise_id, projet_id, client_id, lot_code,
                    statut_lot, mode_paiement, prix_vente_rf1, prix_vente_rf2, prix_total,
                    statut_rf2, montant_rf2_recu, montant_total_paye, montant_restant,
                    created_by
                ) VALUES (
                    :id, :tid, :eid, :pid, :cid, :lot,
                    :statut, :mode, :rf1, :rf2, :total,
                    :rf2s, :rf2r, :paye, :restant,
                    :uid
                )
            """), {
                "id": uid(), "tid": TENANT_ID, "eid": aurea_ent_id,
                "pid": aurea_projet_db_id, "cid": cid, "lot": lot,
                "statut": statut, "mode": mode, "rf1": rf1, "rf2": rf2, "total": total,
                "rf2s": rf2_statut, "rf2r": rf2_recu, "paye": paye,
                "restant": total - paye, "uid": ADMIN_ID,
            })
        print(f"Created {len(DOSSIERS)} dossiers de vente")
        await session.commit()

        print("\n=== REAL DATA SEEDED SUCCESSFULLY ===")
        print("Login: admin@gfi.dz / admin123")


if __name__ == "__main__":
    asyncio.run(main())
