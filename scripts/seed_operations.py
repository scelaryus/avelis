"""Seed operations: WBS templates, 3 sample operations with budget sources and planning tasks."""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import text
from app.db import SessionLocal

db = SessionLocal()

def uid():
    return str(uuid.uuid4())

# Get company and project IDs
co_id = str(db.execute(text("SELECT id FROM company LIMIT 1")).scalar())
proj_aurea = db.execute(text("SELECT id FROM project WHERE code='AUREA'")).scalar()
proj_eden = db.execute(text("SELECT id FROM project WHERE code='EDEN'")).scalar()
proj_irene = db.execute(text("SELECT id FROM project WHERE code='IRENE'")).scalar()

# ═══ SEED WBS TEMPLATES ═══
db.execute(text("DELETE FROM wbs_template"))

templates = [
    ("GROS_OEUVRE", "Gros oeuvre standard", [
        {"code": "1", "title": "Installation chantier", "type": "TACHE", "duration": 15},
        {"code": "1.1", "title": "Terrassement", "type": "TACHE", "duration": 20},
        {"code": "2", "title": "Fondations", "type": "TACHE", "duration": 30},
        {"code": "3", "title": "Infrastructure (sous-sol)", "type": "TACHE", "duration": 45},
        {"code": "4", "title": "Superstructure (par niveau)", "type": "SUMMARY", "duration": 60},
        {"code": "4.1", "title": "RDC", "type": "TACHE", "duration": 15},
        {"code": "4.2", "title": "Etages courants", "type": "TACHE", "duration": 40},
        {"code": "5", "title": "Etancheite", "type": "TACHE", "duration": 15},
        {"code": "6", "title": "Reception provisoire", "type": "JALON_PLANNING", "duration": 1},
    ]),
    ("BET_ARCHITECTURE", "Bureau etudes architecture", [
        {"code": "1", "title": "Releve existant", "type": "TACHE", "duration": 10},
        {"code": "2", "title": "APS (Avant-Projet Sommaire)", "type": "TACHE", "duration": 20},
        {"code": "3", "title": "APD (Avant-Projet Detaille)", "type": "TACHE", "duration": 30},
        {"code": "4", "title": "Permis de construire", "type": "JALON_PLANNING", "duration": 60},
        {"code": "5", "title": "EXE (Execution)", "type": "TACHE", "duration": 45},
        {"code": "6", "title": "Suivi chantier", "type": "TACHE", "duration": 180},
        {"code": "7", "title": "Reception", "type": "JALON_PLANNING", "duration": 1},
    ]),
    ("SECOND_OEUVRE", "Second oeuvre standard", [
        {"code": "1", "title": "Preparation et approvisionnement", "type": "TACHE", "duration": 15},
        {"code": "2", "title": "Cloisons et faux plafonds", "type": "TACHE", "duration": 30},
        {"code": "3", "title": "Electricite et plomberie", "type": "TACHE", "duration": 40},
        {"code": "4", "title": "Revetements sols et murs", "type": "TACHE", "duration": 25},
        {"code": "5", "title": "Menuiserie et serrurerie", "type": "TACHE", "duration": 20},
        {"code": "6", "title": "Peinture et finitions", "type": "TACHE", "duration": 15},
        {"code": "7", "title": "Nettoyage", "type": "TACHE", "duration": 5},
        {"code": "8", "title": "Reception", "type": "JALON_PLANNING", "duration": 1},
    ]),
    ("MACHINE_OEM", "Achat machine OEM (industriel)", [
        {"code": "1", "title": "Commande et confirmation", "type": "TACHE", "duration": 5},
        {"code": "2", "title": "Fabrication usine", "type": "TACHE", "duration": 90},
        {"code": "3", "title": "Tests usine (FAT)", "type": "TACHE", "duration": 5},
        {"code": "4", "title": "Expedition FOB", "type": "TACHE", "duration": 7},
        {"code": "5", "title": "Transit maritime", "type": "TACHE", "duration": 45},
        {"code": "6", "title": "Dedouanement Algerie", "type": "TACHE", "duration": 30},
        {"code": "7", "title": "Livraison sur site", "type": "TACHE", "duration": 3},
        {"code": "8", "title": "Installation", "type": "TACHE", "duration": 15},
        {"code": "9", "title": "Tests site (SAT)", "type": "TACHE", "duration": 5},
        {"code": "10", "title": "Formation operateurs", "type": "TACHE", "duration": 10},
        {"code": "11", "title": "Reception definitive", "type": "JALON_PLANNING", "duration": 1},
    ]),
    ("RH_CDI", "Recrutement CDI", [
        {"code": "1", "title": "Publication offre", "type": "TACHE", "duration": 3},
        {"code": "2", "title": "Reception candidatures", "type": "TACHE", "duration": 15},
        {"code": "3", "title": "Tri et entretiens", "type": "TACHE", "duration": 10},
        {"code": "4", "title": "Selection finale", "type": "TACHE", "duration": 3},
        {"code": "5", "title": "Contrat et signature", "type": "TACHE", "duration": 5},
        {"code": "6", "title": "Integration (30 jours)", "type": "TACHE", "duration": 30},
        {"code": "7", "title": "Fin periode essai", "type": "JALON_PLANNING", "duration": 1},
    ]),
]

import json
for cat, name, tasks in templates:
    tid = uid()
    db.execute(text("INSERT INTO wbs_template (id, categorie, name, tasks) VALUES (:id, :cat, :name, :tasks)"),
               {"id": tid, "cat": cat, "name": name, "tasks": json.dumps(tasks)})
print(f"Seeded {len(templates)} WBS templates")

# ═══ SEED 3 OPERATIONS ═══
db.execute(text("DELETE FROM operation_dependency"))
db.execute(text("DELETE FROM operation_planning_task"))
db.execute(text("DELETE FROM operation_budget_agrege"))
db.execute(text("DELETE FROM operation_snapshot"))
db.execute(text("DELETE FROM operation"))

ops = [
    {
        "id": uid(), "code": "OP-SARLDP-2026-0001", "title": "Gros-oeuvre AUREA",
        "project_id": str(proj_aurea) if proj_aurea else None, "categorie": "GROS_OEUVRE",
        "montant_ht": 85000000, "montant_ttc": 101150000, "statut": "EN_COURS",
        "date_debut": "2025-06-01", "date_fin": "2027-06-30",
        "budget_sources": [
            ("S1_CONTRAT", "Contrat", 85000000, 85000000),
            ("S2_RH_PAIE", "Masse salariale", 4200000, 3800000),
            ("S4_TRESORERIE", "Flux tresorerie", 85000000, 72000000),
            ("S7_STOCK", "Stock materiaux", 6500000, 5200000),
            ("S8_FLOTTE", "Vehicules", 3200000, 2800000),
            ("S9_IT", "IT/Licences", 180000, 150000),
            ("S10_ASSURANCE", "Assurances", 1700000, 1700000),
            ("S11_OVERHEAD", "Overhead", 2400000, 2100000),
        ],
        "tasks": [
            ("1", "Installation chantier", "2025-06-01", "2025-06-15", 100, "TACHE", True, 2000000),
            ("2", "Terrassement", "2025-06-16", "2025-07-15", 100, "TACHE", True, 5000000),
            ("3", "Fondations", "2025-07-16", "2025-09-15", 85, "TACHE", True, 15000000),
            ("4", "Infrastructure", "2025-09-16", "2025-12-31", 60, "TACHE", True, 20000000),
            ("5", "Superstructure RDC", "2026-01-01", "2026-03-15", 30, "TACHE", True, 12000000),
            ("6", "Superstructure etages", "2026-03-16", "2026-12-31", 0, "TACHE", False, 25000000),
            ("7", "Etancheite", "2027-01-01", "2027-03-31", 0, "TACHE", False, 4000000),
            ("8", "Reception provisoire", "2027-06-30", "2027-06-30", 0, "JALON_PLANNING", False, 0),
        ],
    },
    {
        "id": uid(), "code": "OP-ETSDK-2026-0002", "title": "BET Architecture EDEN Phase 2",
        "project_id": str(proj_eden) if proj_eden else None, "categorie": "BET_ARCHITECTURE",
        "montant_ht": 12000000, "montant_ttc": 14280000, "statut": "VALIDE",
        "date_debut": "2026-04-01", "date_fin": "2027-03-31",
        "budget_sources": [
            ("S1_CONTRAT", "Contrat", 12000000, 0),
            ("S2_RH_PAIE", "Suivi interne", 800000, 0),
        ],
        "tasks": [
            ("1", "APS", "2026-04-01", "2026-05-15", 0, "TACHE", True, 3000000),
            ("2", "APD", "2026-05-16", "2026-07-31", 0, "TACHE", True, 4000000),
            ("3", "EXE", "2026-08-01", "2026-11-30", 0, "TACHE", False, 5000000),
        ],
    },
    {
        "id": uid(), "code": "OP-SARLDP-2026-0003", "title": "Second oeuvre IRENE Batiment A",
        "project_id": str(proj_irene) if proj_irene else None, "categorie": "SECOND_OEUVRE",
        "montant_ht": 35000000, "montant_ttc": 41650000, "statut": "EN_COURS",
        "date_debut": "2026-01-15", "date_fin": "2026-09-30",
        "budget_sources": [
            ("S1_CONTRAT", "Contrat", 35000000, 35000000),
            ("S2_RH_PAIE", "Masse salariale", 2100000, 1800000),
            ("S7_STOCK", "Materiaux", 3500000, 2800000),
            ("S11_OVERHEAD", "Overhead", 800000, 600000),
        ],
        "tasks": [
            ("1", "Cloisons", "2026-01-15", "2026-03-15", 100, "TACHE", True, 8000000),
            ("2", "Electricite/Plomberie", "2026-02-01", "2026-05-15", 70, "TACHE", True, 12000000),
            ("3", "Revetements", "2026-04-01", "2026-07-15", 20, "TACHE", False, 8000000),
            ("4", "Peinture", "2026-06-01", "2026-08-31", 0, "TACHE", False, 5000000),
            ("5", "Reception", "2026-09-30", "2026-09-30", 0, "JALON_PLANNING", False, 0),
        ],
    },
]

for op in ops:
    db.execute(text("""
    INSERT INTO operation (id, company_id, code_operation, intitule, project_id, categorie,
        montant_engage_ht, montant_engage_ttc, statut, date_debut, date_fin_prevue)
    VALUES (:id, :co, :code, :title, :proj, :cat, :ht, :ttc, :statut, :debut, :fin)
    """), {
        "id": op["id"], "co": co_id, "code": op["code"], "title": op["title"],
        "proj": op["project_id"], "cat": op["categorie"],
        "ht": op["montant_ht"], "ttc": op["montant_ttc"], "statut": op["statut"],
        "debut": op["date_debut"], "fin": op["date_fin"],
    })

    # Budget sources
    for src_code, src_label, prevu, reel in op.get("budget_sources", []):
        db.execute(text("""
        INSERT INTO operation_budget_agrege (id, company_id, operation_id, source_code, source_label,
            montant_prevu, montant_reel, methode_calcul)
        VALUES (:id, :co, :op_id, :src, :label, :prevu, :reel, :method)
        """), {
            "id": uid(), "co": co_id, "op_id": op["id"], "src": src_code,
            "label": src_label, "prevu": prevu, "reel": reel,
            "method": "DIRECT" if src_code == "S1_CONTRAT" else "CRON_MENSUEL",
        })

    # Planning tasks
    for code_wbs, title, debut, fin, avancement, type_t, critique, budget in op.get("tasks", []):
        db.execute(text("""
        INSERT INTO operation_planning_task (id, company_id, operation_id, code_wbs, intitule,
            date_debut_prevue, date_fin_prevue, avancement_pct, type_tache, est_critique, budget_tache,
            statut_tache, avancement_methode)
        VALUES (:id, :co, :op_id, :wbs, :title, :debut, :fin, :avancement, :type, :critique, :budget,
            :statut, 'MANUEL')
        """), {
            "id": uid(), "co": co_id, "op_id": op["id"], "wbs": code_wbs, "title": title,
            "debut": debut, "fin": fin, "avancement": avancement, "type": type_t,
            "critique": critique, "budget": budget,
            "statut": "TERMINEE" if avancement >= 100 else "EN_COURS" if avancement > 0 else "A_FAIRE",
        })

db.commit()

# Verify
op_count = db.execute(text("SELECT count(*) FROM operation")).scalar()
budget_count = db.execute(text("SELECT count(*) FROM operation_budget_agrege")).scalar()
task_count = db.execute(text("SELECT count(*) FROM operation_planning_task")).scalar()
template_count = db.execute(text("SELECT count(*) FROM wbs_template")).scalar()
print(f"Seeded: {op_count} operations, {budget_count} budget sources, {task_count} planning tasks, {template_count} templates")
db.close()
