"""
GFI v7.0 — Seed the database with REAL Groupe GFI data.
Run: python scripts/seed_data.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from hashlib import sha256
from app.db import SessionLocal, engine, Base
from app.models.core import (
    Company, Associate, EntrepriseAssocie, Project, PartProjet,
    Alias, Lot, AuthUser, Employee, DossierADV, Payment,
    CcaAccount, GacebAdvance, GacebSituation,
)

def seed():
    db = SessionLocal()
    try:
        # ── CLEAR EXISTING DATA ────────────────────────────────────────
        for tbl in reversed(Base.metadata.sorted_tables):
            db.execute(tbl.delete())
        db.commit()
        print("Cleared existing data.")

        # ── 1. COMPANIES (12 entities) ─────────────────────────────────
        companies_data = [
            ("ETS-DK",    "ETS GFI Fondation",           "ETS",  "ACTIF",           "GENERAL", 19, 2),
            ("SARL-DP",   "SARL GFI Promotion",         "SARL", "ACTIF",           "BTPH",    19, 2),
            ("SARL-DBPI", "SARL DBPI Immobilier",           "SARL", "ACTIF",           "BTPH",    19, 2),
            ("SARL-OC",   "SARL Oméga Construction",        "SARL", "ACTIF",           "BTPH",    None, None),
            ("SARL-M60",  "SARL Maison en 60 Jours",        "SARL", "À DÉVELOPPER",    "BTPH",    None, None),
            ("SARL-EP",   "SARL Elite Promotion",           "SARL", "À DÉVELOPPER",    "BTPH",    None, None),
            ("SARL-SEN",  "SARL Senimar",                   "SARL", "À DÉVELOPPER",    "BTPH",    None, None),
            ("EURL-BIM",  "EURL Bimha Construction",        "EURL", "À DÉVELOPPER",    "BTPH",    None, None),
            ("SARL-ARC",  "SARL ARCEN",                     "SARL", "À DÉVELOPPER",    "BTPH",    None, None),
            ("SCI-DEN",   "SCI GFI",                    "SCI",  "À DÉVELOPPER",    "GENERAL", None, None),
            ("SARL-AMF",  "SARL AMENFORT Béton",            "SARL", "DISSOUTE",        "BTPH",    19, 2),
            ("EURL-BAY",  "EURL BAYTI / ALLO MAISON",      "EURL", "SATELLITE",       "GENERAL", 19, 1),
        ]
        companies = {}
        for code, name, form, status, cnas, ibs, tap in companies_data:
            c = Company(code=code, legal_name=name, legal_form=form, status=status,
                        cnas_regime=cnas,
                        ibs_rate=Decimal(str(ibs)) if ibs else None,
                        tap_rate=Decimal(str(tap)) if tap else None)
            db.add(c)
            db.flush()
            companies[code] = c
        print(f"Seeded {len(companies)} companies.")

        # ── 2. ASSOCIATES (9 people) ──────────────────────────────────
        associates_data = [
            ("ADMIN Ahmed",            True,  "DAF / Gérant",          "INTERNAL"),
            ("ASSOC Mohamed",          True,  "Associé",               "INTERNAL"),
            ("ASSOC Yazid (Lyazid)",   True,  "Associé",               "INTERNAL"),
            ("ASSOC Yamina",           True,  "Associée",              "INTERNAL"),
            ("ASSOC Laid",             False, "Associé projet (T5000)","INTERNAL"),
            ("DABLADJI Abderahmane",     False, "Acheteur Lot 1",       "EXTERNAL"),
            ("BOUMERDASSI Mustapha",     False, "Associé projet",       "EXTERNAL"),
            ("GACEB Abderazak",          False, "Sous-traitant",        "EXTERNAL"),
            ("AMIRAT Brahim",            False, "Associé projet",       "EXTERNAL"),
        ]
        associates = {}
        for name, founder, role, atype in associates_data:
            a = Associate(canonical_name=name, is_founder=founder, role=role, associate_type=atype)
            db.add(a)
            db.flush()
            associates[name] = a
        print(f"Seeded {len(associates)} associates.")

        # ── 3. ENTREPRISE_ASSOCIE (company ownership %) ───────────────
        ahmed = associates["ADMIN Ahmed"]
        mohamed = associates["ASSOC Mohamed"]
        yazid = associates["ASSOC Yazid (Lyazid)"]
        yamina = associates["ASSOC Yamina"]

        ownership_data = [
            # (company_code, associate, percentage)
            ("ETS-DK",    ahmed,   25), ("ETS-DK",    mohamed, 25), ("ETS-DK",    yazid,   25), ("ETS-DK",    yamina,  25),
            ("SARL-DP",   ahmed,   25), ("SARL-DP",   mohamed, 25), ("SARL-DP",   yazid,   25), ("SARL-DP",   yamina,  25),
            ("SARL-DBPI", ahmed,   60), ("SARL-DBPI", mohamed, 20), ("SARL-DBPI", yazid,   20),
            ("SARL-OC",   ahmed,   60), ("SARL-OC",   mohamed, 20), ("SARL-OC",   yazid,   20),
            ("SARL-EP",   ahmed,   60), ("SARL-EP",   mohamed, 20), ("SARL-EP",   yazid,   20),
            ("SARL-SEN",  ahmed,   60), ("SARL-SEN",  mohamed, 20), ("SARL-SEN",  yazid,   20),
            ("EURL-BIM",  ahmed,   60), ("EURL-BIM",  mohamed, 20), ("EURL-BIM",  yazid,   20),
            ("SARL-AMF",  ahmed, 33.3334), ("SARL-AMF",  mohamed, 33.3333), ("SARL-AMF",  yazid, 33.3333),
        ]
        for code, assoc, pct in ownership_data:
            db.add(EntrepriseAssocie(
                company_id=companies[code].id, associate_id=assoc.id,
                percentage=Decimal(str(pct))))
        db.flush()
        print(f"Seeded {len(ownership_data)} entreprise_associe rows.")

        # ── 4. PROJECTS (16 projects) ─────────────────────────────────
        projects_data = [
            ("EDEN",        "Résidence Eden",               "ETS-DK",    "ACTIF",      154, 250000000),
            ("JASMIN",      "Les Jasmins",                  "ETS-DK",    "ACTIF",      100, 50000000),
            ("OPERA",       "Jardin de l'Opéra",            "SARL-DP",   "ACTIF",      None, 340000000),
            ("LYS",         "Les Lys",                      "SARL-DBPI", "ACTIF",      None, 200000000),
            ("IRENE",       "Irène / 05 Hectare",           "SARL-DP",   "ACTIF",      None, 500000000),
            ("MAGNOLIA",    "Magnolia",                     "SARL-OC",   "ACTIF",      18, 32000000),
            ("AUREA",       "Auréa",                        "SARL-DP",   "ACTIF",      199, 340000000),
            ("ASTERIA",     "Asteria",                      "SARL-SEN",  "À DÉVELOPPER", 52, 230000000),
            ("MOSQUEE",     "Mosquée Taoura",               "ETS-DK",    "DONATION",   None, None),
            ("T21000",      "Terrain 21 000 m²",            "ETS-DK",    "TERRAIN",    None, None),
            ("T5000",       "Terrain 5 000 m²",             "SARL-DBPI", "EN_ATTENTE", None, None),
            ("T2400",       "Terrain 2 400 m²",             "SARL-DBPI", "TERRAIN",    None, None),
            ("ALLO-MAISON", "Allo Maison",                  "SARL-DP",   "À DÉVELOPPER", None, None),
            ("ELITE-DRIVE", "Elite Drive",                  "EURL-BIM",  "À DÉVELOPPER", None, None),
            ("PFSB",        "PFSB",                         "EURL-BIM",  "À DÉVELOPPER", None, None),
            ("DG",          "DG",                           "SARL-DBPI", "À DÉVELOPPER", None, None),
        ]
        projects = {}
        for code, name, comp_code, status, clients, terrain in projects_data:
            p = Project(code=code, name=name, company_id=companies[comp_code].id,
                        status=status, client_count=clients,
                        terrain_cost_estimate=Decimal(str(terrain)) if terrain else None)
            db.add(p)
            db.flush()
            projects[code] = p
        print(f"Seeded {len(projects)} projects.")

        # ── 5. PART_PROJET (project ownership %) ─────────────────────
        # Only for projects NOT in À DÉVELOPPER status
        laid = associates["ASSOC Laid"]
        parts_data = [
            ("EDEN",   [(ahmed,25),(mohamed,25),(yazid,25),(yamina,25)]),
            ("JASMIN", [(ahmed,34),(mohamed,33),(yazid,33)]),
            ("OPERA",  [(ahmed,25),(mohamed,25),(yazid,25),(yamina,25)]),
            ("LYS",    [(ahmed,60),(mohamed,20),(yazid,20)]),
            ("IRENE",  [(ahmed,60),(mohamed,20),(yazid,20)]),
            ("MAGNOLIA",[(ahmed,60),(mohamed,20),(yazid,20)]),
            ("AUREA",  [(ahmed,60),(mohamed,20),(yazid,20)]),
            ("MOSQUEE",[(ahmed,34),(mohamed,33),(yazid,33)]),
            ("T21000", [(ahmed,25),(mohamed,25),(yazid,25),(yamina,25)]),
            ("T5000",  [(ahmed,50),(laid,50)]),
            ("T2400",  [(ahmed,50),(mohamed,50)]),
        ]
        part_count = 0
        for proj_code, assocs in parts_data:
            p = projects[proj_code]
            for assoc, pct in assocs:
                db.add(PartProjet(
                    project_id=p.id, company_id=p.company_id,
                    associate_id=assoc.id, percentage=Decimal(str(pct))))
                part_count += 1
        db.flush()
        print(f"Seeded {part_count} part_projet rows.")

        # ── 6. ALIASES ────────────────────────────────────────────────
        alias_data = [
            ("FOES", "PROJECT", "EDEN"), ("Sahel", "PROJECT", "JASMIN"),
            ("Les Jasmins", "PROJECT", "JASMIN"), ("Ouled Fayet", "PROJECT", "OPERA"),
            ("Les Jardins de l'Opera", "PROJECT", "OPERA"),
            ("Ami Djamel", "PROJECT", "IRENE"), ("5H", "PROJECT", "IRENE"),
            ("05H", "PROJECT", "IRENE"), ("05 Hectare", "PROJECT", "IRENE"),
            ("Boumerdes", "PROJECT", "IRENE"),
            ("02H", "PROJECT", "LYS"), ("02 Hectare", "PROJECT", "LYS"),
            ("Bentala", "PROJECT", "LYS"), ("Draria", "PROJECT", "LYS"),
            ("Les Lys", "PROJECT", "LYS"), ("Dhous 2 hectare", "PROJECT", "LYS"),
            ("Cheraga", "PROJECT", "AUREA"), ("Chéraga", "PROJECT", "AUREA"),
            ("El Achour", "PROJECT", "ASTERIA"),
            ("Taoura", "PROJECT", "MOSQUEE"), ("Taourga", "PROJECT", "MOSQUEE"),
            ("BAYTI", "COMPANY", "EURL-BAY"), ("Novus", "COMPANY", "EURL-BAY"),
            ("AMENFORT", "COMPANY", "SARL-AMF"),
            ("Ahmed", "ASSOCIATE", "ADMIN Ahmed"), ("Hmed", "ASSOCIATE", "ADMIN Ahmed"),
            ("Mohamed", "ASSOCIATE", "ASSOC Mohamed"), ("Moh", "ASSOCIATE", "ASSOC Mohamed"),
            ("Mouh", "ASSOCIATE", "ASSOC Mohamed"),
            ("Yazid", "ASSOCIATE", "ASSOC Yazid (Lyazid)"), ("Lyazid", "ASSOCIATE", "ASSOC Yazid (Lyazid)"),
            ("Bouabdellah", "ASSOCIATE", "ASSOC Yazid (Lyazid)"),
            ("Yamina", "ASSOCIATE", "ASSOC Yamina"),
        ]
        for text, ctype, code in alias_data:
            db.add(Alias(alias_text=text, canonical_type=ctype, canonical_code=code))
        db.flush()
        print(f"Seeded {len(alias_data)} aliases.")

        # ── 7. LOTS (10 EDEN + 10 AUREA) ─────────────────────────────
        eden_co = companies["ETS-DK"]
        aurea_co = companies["SARL-DP"]
        eden_proj = projects["EDEN"]
        aurea_proj = projects["AUREA"]

        lot_data = []
        for i in range(1, 6):
            lot_data.append((eden_co.id, eden_proj.id, f"E-F3-A-{i:03d}", "F3", 85+i, i, "A", "Sud",
                             8000000 + i*200000, 2500000, "DISPONIBLE" if i <= 3 else ("RÉSERVÉ" if i == 4 else "ENGAGÉ")))
        for i in range(1, 6):
            lot_data.append((eden_co.id, eden_proj.id, f"E-F4-B-{i:03d}", "F4", 115+i*2, i, "B", "Nord",
                             11000000 + i*300000, 4000000, "DISPONIBLE" if i <= 2 else "RÉSERVÉ"))
        for i in range(1, 6):
            lot_data.append((aurea_co.id, aurea_proj.id, f"A-F3-A-{i:03d}", "F3", 82+i*2, i, "A", "Est",
                             9000000 + i*150000, 3000000, "DISPONIBLE"))
        for i in range(1, 6):
            lot_data.append((aurea_co.id, aurea_proj.id, f"A-F4-B-{i:03d}", "F4", 120+i*3, i, "B", "Ouest",
                             12000000 + i*200000, 4500000, "DISPONIBLE"))

        lots = {}
        for co_id, proj_id, ref, typ, surf, flr, blk, orient, rf1, rf2, status in lot_data:
            l = Lot(company_id=co_id, project_id=proj_id, ref=ref, typology=typ,
                    surface=Decimal(str(surf)), floor=flr, block=blk, orientation=orient,
                    rf1_price=Decimal(str(rf1)), rf2_price=Decimal(str(rf2)), status=status)
            db.add(l)
            db.flush()
            lots[ref] = l
        print(f"Seeded {len(lots)} lots.")

        # ── 8. AUTH USERS ─────────────────────────────────────────────
        def hash_pw(pw):
            return sha256(pw.encode()).hexdigest()

        users_data = [
            ("ahmed.gfi@groupe-gfi.dz", "test123", "Ahmed Admin", "DAF", True),
            ("agent.commercial.1@groupe-gfi.dz", "test123", "Karim Hamdi", "AGENT_COMMERCIAL", False),
            ("gestionnaire.adv.1@groupe-gfi.dz", "test123", "Nadia Ait Kaci", "GESTIONNAIRE_ADV", True),
            ("tresorier.1@groupe-gfi.dz", "test123", "Ali Bouali", "TRESORIER", True),
            ("comptable.1@groupe-gfi.dz", "test123", "Fatima Meziane", "COMPTABLE", False),
            ("drh.1@groupe-gfi.dz", "test123", "Samira Benali", "DRH", False),
        ]
        for email, pw, name, role, rf2 in users_data:
            db.add(AuthUser(email=email, password_hash=hash_pw(pw), full_name=name, role=role, has_rf2_access=rf2))
        db.flush()
        print(f"Seeded {len(users_data)} users.")

        # ── 9. EMPLOYEES ──────────────────────────────────────────────
        emp_data = [
            (companies["SARL-DP"].id, "SARLDP-2024-0001", "Karim", "Hamdi", "Commercial", "Agent commercial", 45000),
            (companies["SARL-DP"].id, "SARLDP-2024-0003", "Nadia", "Ait Kaci", "Finance", "Comptable", 55000),
            (companies["ETS-DK"].id, "ETSDK-2024-0001", "Ahmed", "Bouali", "Technique", "Chef de chantier", 65000),
            (companies["ETS-DK"].id, "ETSDK-2023-0015", "Youcef", "Meziane", "Technique", "Conducteur travaux", 80000),
            (companies["SARL-DP"].id, "SARLDP-2025-0012", "Fatima", "Benali", "Administration", "Assistante RH", 35000),
        ]
        for co_id, mat, fn, ln, dept, pos, sal in emp_data:
            db.add(Employee(company_id=co_id, matricule=mat, first_name=fn, last_name=ln,
                            department=dept, position=pos, salary_base=Decimal(str(sal))))
        db.flush()
        print(f"Seeded {len(emp_data)} employees.")

        # ── 10. DOSSIERS ADV (3 at different stages) ──────────────────
        lot_reserved = lots["E-F4-B-003"]
        lot_engaged = lots["E-F3-A-005"]
        lot_fp = lots["E-F4-B-004"]

        d1 = DossierADV(company_id=eden_co.id, numero="ADV-2026-EDEN-0001",
                         client_name="Benmoussa Ali", lot_id=lot_reserved.id, project_id=eden_proj.id,
                         type_paiement="CREDIT_BANCAIRE", prix_rf1=lot_reserved.rf1_price,
                         prix_rf2=lot_reserved.rf2_price, status="RÉSERVÉ",
                         rf2_status="SECURISE", montant_rf2_securise=lot_reserved.rf2_price)
        d2 = DossierADV(company_id=eden_co.id, numero="ADV-2026-EDEN-0002",
                         client_name="Kaci Noureddine", lot_id=lot_engaged.id, project_id=eden_proj.id,
                         type_paiement="CREDIT_BANCAIRE", prix_rf1=lot_engaged.rf1_price,
                         prix_rf2=lot_engaged.rf2_price, status="ENGAGÉ",
                         rf2_status="SECURISE", montant_rf2_securise=lot_engaged.rf2_price)
        d3 = DossierADV(company_id=eden_co.id, numero="ADV-2026-EDEN-0003",
                         client_name="Amrani Said", lot_id=lot_fp.id, project_id=eden_proj.id,
                         type_paiement="FONDS_PROPRES", prix_rf1=lot_fp.rf1_price,
                         prix_rf2=lot_fp.rf2_price, status="EN_COURS_FONDS_PROPRES",
                         rf2_status="SECURISE", montant_rf2_securise=lot_fp.rf2_price)
        db.add_all([d1, d2, d3])
        db.flush()

        # Add payments
        db.add(Payment(company_id=eden_co.id, dossier_id=d1.id, type_rf="RF1",
                        mode_reglement="CHEQUE", montant=Decimal("2000000"), reference="CHQ-001", status="ENCAISSÉ"))
        db.add(Payment(company_id=eden_co.id, dossier_id=d1.id, type_rf="RF2",
                        mode_reglement="ESPECES", montant=lot_reserved.rf2_price, status="ENCAISSÉ"))
        db.add(Payment(company_id=eden_co.id, dossier_id=d3.id, type_rf="RF1",
                        mode_reglement="CHEQUE", montant=Decimal("3500000"), reference="CHQ-045", status="ENCAISSÉ"))
        db.add(Payment(company_id=eden_co.id, dossier_id=d3.id, type_rf="RF2",
                        mode_reglement="ESPECES", montant=lot_fp.rf2_price, status="ENCAISSÉ"))
        db.flush()
        print("Seeded 3 dossiers ADV with payments.")

        # ── 11. CCA BALANCES ──────────────────────────────────────────
        cca_data = [
            (ahmed, "ETS-DK", -27507000), (ahmed, "SARL-DP", 5000000),
            (mohamed, "ETS-DK", 4453000), (mohamed, "SARL-DP", 2000000),
            (yazid, "ETS-DK", 4453000), (yazid, "SARL-DP", 1500000),
            (yamina, "ETS-DK", -5000000), (yamina, "SARL-DP", 3000000),
        ]
        for assoc, comp_code, bal in cca_data:
            db.add(CcaAccount(company_id=companies[comp_code].id,
                              associate_id=assoc.id, balance=Decimal(str(bal))))
        db.flush()
        print(f"Seeded {len(cca_data)} CCA accounts.")

        # ── 12. GACEB ADVANCE ─────────────────────────────────────────
        adv_gaceb = GacebAdvance(
            company_id=eden_co.id, project_id=eden_proj.id,
            initial_amount=Decimal("120000000"), deducted_amount=Decimal("45000000"),
            residual=Decimal("75000000"))
        db.add(adv_gaceb)
        db.flush()

        sits = [
            (1, 35000000, 20000000, 15000000, 100000000),
            (2, 40000000, 15000000, 25000000, 85000000),
            (3, 30000000, 10000000, 20000000, 75000000),
        ]
        for num, brut, ded, net, solde in sits:
            db.add(GacebSituation(
                company_id=eden_co.id, advance_id=adv_gaceb.id, num=num,
                brut=Decimal(str(brut)), deduction=Decimal(str(ded)),
                net=Decimal(str(net)), solde_after=Decimal(str(solde))))
        db.flush()
        print("Seeded GACEB advance + 3 situations.")

        # ── COMMIT ────────────────────────────────────────────────────
        db.commit()
        print("\n✅ ALL SEED DATA COMMITTED SUCCESSFULLY.")
        print(f"   Companies: {len(companies_data)}")
        print(f"   Associates: {len(associates_data)}")
        print(f"   Projects: {len(projects_data)}")
        print(f"   Lots: {len(lot_data)}")
        print(f"   Users: {len(users_data)}")

    except Exception as e:
        db.rollback()
        print(f"❌ SEED FAILED: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()
