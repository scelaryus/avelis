"""Seed legal cases with realistic Groupe GFI litigation data."""
from datetime import date, datetime, timezone
from decimal import Decimal
from app.db import engine, SessionLocal
from app.models.core import Base, LegalCase, LegalCaseEvent, Company

Base.metadata.create_all(engine)
db = SessionLocal()
co = db.query(Company).first()

db.query(LegalCaseEvent).delete()
db.query(LegalCase).delete()
db.commit()

def add_case(data, events):
    case = LegalCase(company_id=co.id, **data)
    db.add(case)
    db.flush()
    for ev in events:
        kwargs = {"case_id": case.id, "event_type": ev[0], "title": ev[1], "created_by": "system"}
        if len(ev) > 2: kwargs["description"] = ev[2]
        if len(ev) > 3: kwargs["old_stage"] = ev[3]
        if len(ev) > 4: kwargs["new_stage"] = ev[4]
        if len(ev) > 5 and ev[5] is not None: kwargs["amount"] = ev[5]
        db.add(LegalCaseEvent(**kwargs))

add_case(
    {"name": "LGL/2024/00001", "case_type": "contentieux_commercial", "title": "Impaye fournisseur BETICA - etude de sol AUREA",
     "description": "BETICA SARL a realise une etude geotechnique pour AUREA. Facture de 15M DA impayee depuis 6 mois. Mise en demeure recue.",
     "stage": "mise_en_demeure", "priority": "important", "partner_name": "BETICA SARL",
     "partner_lawyer": "Me Khelifi", "company_lawyer": "Me Boudjema", "assigned_juriste": "Juriste interne",
     "project_code": "AUREA", "amount_claimed": Decimal("15000000"), "ai_risk_score": Decimal("65"),
     "ai_summary": "Risque moyen. Facture justifiee par contrat signe. Accord amiable possible.",
     "date_open": date(2024, 9, 15), "date_deadline": date(2026, 4, 15)},
    [("CREATION", "Ouverture du dossier", "Reception mise en demeure BETICA"),
     ("DOCUMENT", "Contrat original joint", "CTR-2024-BETICA-001"),
     ("STAGE_CHANGE", "Mise en demeure envoyee", "Lettre recommandee AR envoyee", "ouvert", "mise_en_demeure"),
     ("NOTE", "Appel BETICA", "BETICA accepte de negocier un echeancier")]
)

add_case(
    {"name": "LGL/2025/00002", "case_type": "contentieux_rh", "title": "Contestation licenciement - Boumediene Kamel",
     "description": "Ex-chef de chantier licencie pour abandon de poste conteste devant le tribunal du travail de Bir Mourad Rais.",
     "stage": "audience_programmee", "priority": "critique", "partner_name": "Boumediene Kamel",
     "partner_lawyer": "Me Taleb", "company_lawyer": "Me Boudjema", "assigned_juriste": "Juriste interne",
     "employee_name": "Boumediene Kamel", "amount_claimed": Decimal("2400000"), "ai_risk_score": Decimal("40"),
     "ai_summary": "Risque modere. Dossier disciplinaire bien documente. Procedure conforme Loi 90-11.",
     "date_open": date(2025, 3, 1), "date_deadline": date(2026, 5, 10)},
    [("CREATION", "Reception assignation", "Tribunal du travail BMR ref TT-2025-00412"),
     ("DOCUMENT", "Dossier defense constitue", "PV constat + PV audition + decision + temoins"),
     ("NOTE", "Analyse juridique", "Procedure conforme art. 73 Loi 90-11. Delegue syndical present a l audition."),
     ("STAGE_CHANGE", "Audience programmee", "Audience 10/05/2026 tribunal BMR", "ouvert", "audience_programmee")]
)

add_case(
    {"name": "LGL/2025/00003", "case_type": "precontentieux", "title": "Retard livraison ANDA Machine - penalites ALLO MAISON",
     "description": "Fournisseur chinois ANDA Machine: 3 mois de retard. Penalites contractuelles 0.5%/semaine.",
     "stage": "negociation", "priority": "important", "partner_name": "ANDA Machine (Shanghai)",
     "company_lawyer": "Me Boudjema", "assigned_juriste": "Juriste interne",
     "project_code": "ALLO_MAISON", "contract_ref": "CTR-ANDA-2025-001",
     "amount_claimed": Decimal("8750000"), "ai_risk_score": Decimal("30"),
     "ai_summary": "Risque faible. Penalites claires dans le contrat. ANDA a reconnu le retard par email.",
     "date_open": date(2025, 11, 1), "date_deadline": date(2026, 6, 1)},
    [("CREATION", "Constat retard livraison", "Machine non livree a date contractuelle 01/08/2025"),
     ("DOCUMENT", "Email ANDA", "Email 15/09 de Mr Zhang confirmant retard logistique"),
     ("NOTE", "Calcul penalites", "13 sem x 0.5% = 6.5% de 125K EUR = ~8.75M DA"),
     ("STAGE_CHANGE", "Negociation ouverte", "Proposition compensation: pieces + formation", "ouvert", "negociation")]
)

add_case(
    {"name": "LGL/2023/00004", "case_type": "contentieux_commercial", "title": "Malfacons BATIGEST - second oeuvre JASMIN",
     "description": "Sous-traitant BATIGEST: travaux non conformes. Expert judiciaire designe. Rapport favorable au groupe.",
     "stage": "en_delibere", "priority": "normal", "partner_name": "BATIGEST SARL",
     "partner_lawyer": "Me Hamidi", "company_lawyer": "Me Boudjema",
     "project_code": "JASMIN", "amount_claimed": Decimal("6500000"), "ai_risk_score": Decimal("55"),
     "ai_summary": "Rapport expertise favorable. Malfacons confirmees. Prejudice evalue 6.5M DA. En attente jugement.",
     "date_open": date(2023, 6, 15), "date_deadline": date(2026, 7, 1),
     "cost_honoraires": Decimal("800000"), "cost_expertise": Decimal("350000"), "cost_total": Decimal("1150000")},
    [("CREATION", "Constat malfacons", "Rapport photos: infiltrations, fissures, revetements non conformes"),
     ("STAGE_CHANGE", "Assignation tribunal", "Depot tribunal commerce Alger", "ouvert", "audience_programmee"),
     ("COST", "Honoraires avocat", "Provision Me Boudjema", None, None, Decimal("800000")),
     ("COST", "Expertise judiciaire", "Expert Medjdoub", None, None, Decimal("350000")),
     ("DOCUMENT", "Rapport expertise", "Expert confirme malfacons - prejudice 6.5M DA"),
     ("STAGE_CHANGE", "En delibere", "Audience 15/01/2026. Delibere.", "audience_programmee", "en_delibere")]
)

add_case(
    {"name": "LGL/2022/00005", "case_type": "contentieux_judiciaire", "title": "Litige foncier T5000 - revendication heritiers Belkacem",
     "description": "Tiers revendique propriete partielle du terrain T5000. Acte notarie contestataire. Expertise fonciere en cours.",
     "stage": "ouvert", "priority": "critique", "partner_name": "Heritiers Belkacem",
     "partner_lawyer": "Me Zerrouki", "company_lawyer": "Me Boudjema",
     "project_code": "T5000", "amount_claimed": Decimal("45000000"), "ai_risk_score": Decimal("75"),
     "ai_summary": "Risque eleve. Acte notarie adverse semble authentique. Expertise fonciere determinante. Impact majeur sur T5000.",
     "date_open": date(2022, 11, 1), "date_deadline": date(2026, 9, 1), "is_confidential": True},
    [("CREATION", "Reception assignation", "Heritiers revendiquent 2000m2 sur T5000"),
     ("DOCUMENT", "Acte adverse", "Acte notarie 1987 produit par partie adverse"),
     ("DOCUMENT", "Nos titres", "Acte de vente + certificat foncier")]
)

db.commit()
print(f"Seeded {db.query(LegalCase).count()} cases, {db.query(LegalCaseEvent).count()} events")
db.close()
