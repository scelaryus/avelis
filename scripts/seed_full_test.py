"""Seed comprehensive test data for ALL workflows."""
import psycopg2, uuid, hashlib
from datetime import datetime, timezone
from decimal import Decimal

conn = psycopg2.connect("postgresql://gfi_user:gfi_password@localhost:5432/gfi_v7")
cur = conn.cursor()
now = datetime.now(timezone.utc)

cur.execute("SELECT id FROM company WHERE code = 'SARL-DP'")
company_id = str(cur.fetchone()[0])
cur.execute("SELECT id FROM project WHERE code = 'EDEN'")
project_id = str(cur.fetchone()[0])

# ═══ JOURNALS ═══
for code, label in [("HA","Achats"),("VT","Ventes"),("BQ","Banque"),("OD","Operations Diverses")]:
    cur.execute("INSERT INTO journal (id,company_id,code,label,journal_type,created_at,is_deleted) VALUES (%s,%s,%s,%s,%s,%s,false) ON CONFLICT ON CONSTRAINT uq_journal_company_code DO NOTHING",
        (str(uuid.uuid4()), company_id, code, f"Journal {label}", code, now))
conn.commit()

journals = {}
cur.execute("SELECT id,code FROM journal WHERE company_id = %s AND is_deleted=false", (company_id,))
for r in cur.fetchall(): journals[r[1]] = str(r[0])

# ═══ 10 JOURNAL ENTRIES ═══
entries_data = [
    ("HA", "2026-03-05", "Achat ciment — BATIMETAL", [("601",850000,0,"Achat ciment 500 sacs","BATIMETAL"),("401",0,850000,"Fournisseur BATIMETAL","BATIMETAL")]),
    ("HA", "2026-03-08", "Achat fer — SIDER ANNABA", [("601",1200000,0,"Fer a beton T12","SIDER ANNABA"),("401",0,1200000,"Fournisseur SIDER","SIDER ANNABA")]),
    ("HA", "2026-03-12", "Etude sols — GEO EXPERT", [("604",350000,0,"Etude geotechnique EDEN","GEO EXPERT"),("401",0,350000,"Fournisseur GEO EXPERT","GEO EXPERT")]),
    ("VT", "2026-03-10", "Vente F3 — Amrani Rachid", [("411",9300000,0,"Client Amrani apport","Amrani Rachid"),("706",0,9300000,"Vente F3 EDEN","Amrani Rachid")]),
    ("VT", "2026-03-15", "Vente F4 — Benali Karim", [("411",12200000,0,"Client Benali credit","Benali Karim"),("706",0,12200000,"Vente F4 EDEN","Benali Karim")]),
    ("VT", "2026-03-20", "Vente parking — Cherifi", [("411",1500000,0,"Client Cherifi parking","Cherifi Nadia"),("706",0,1500000,"Vente parking","Cherifi Nadia")]),
    ("BQ", "2026-03-11", "Cheque Amrani BNA", [("512",500000,0,"CHQ-44821 BNA","Amrani Rachid"),("411",0,500000,"Reglement Amrani","Amrani Rachid")]),
    ("BQ", "2026-03-18", "Virement BATIMETAL", [("401",850000,0,"Paiement BATIMETAL","BATIMETAL"),("512",0,850000,"Virement sortant","BATIMETAL")]),
    ("OD", "2026-03-25", "CNAS mars 2026", [("635",180000,0,"CNAS patronale mars","CNAS"),("512",0,180000,"Virement CNAS","CNAS")]),
    ("OD", "2026-03-28", "Salaires mars 2026", [("631",450000,0,"Salaires nets mars","Personnel"),("512",0,450000,"Virement salaires","Personnel")]),
]
seq = 100
for jcode, date, label, lines in entries_data:
    seq += 1
    eid = str(uuid.uuid4())
    td = sum(l[1] for l in lines)
    tc = sum(l[2] for l in lines)
    cur.execute("INSERT INTO journal_entry (id,company_id,journal_id,entry_number,entry_date,label,rf_type,total_debit,total_credit,status,source_document_type,period,created_by,created_at,is_deleted) VALUES (%s,%s,%s,%s,%s,%s,'RF1',%s,%s,'POSTED','SEED',%s,'Admin',%s,false)",
        (eid, company_id, journals[jcode], f"{jcode}-2026-{seq:04d}", date, label, td, tc, date[:7], now))
    for acc, d, c, lbl, tiers in lines:
        cur.execute("INSERT INTO journal_entry_line (id,company_id,entry_id,account_code,label,debit,credit,tiers_name,created_at,is_deleted) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,false)",
            (str(uuid.uuid4()), company_id, eid, acc, lbl, d, c, tiers, now))
conn.commit()
print(f"Journal: {len(entries_data)} ecritures (HA/VT/BQ/OD)")

# ═══ BANK STATEMENT ═══
stmt_id = str(uuid.uuid4())
cur.execute("INSERT INTO bank_statement (id,company_id,bank_name,period,total_debit,total_credit,movements_count,matched_count,status,uploaded_by,created_at,is_deleted) VALUES (%s,%s,'BNA','2026-03',1830000,850000,6,0,'IMPORTED','Admin',%s,false)", (stmt_id, company_id, now))
mvts = [
    ("2026-03-11","CHQ-44821","Remise cheque Amrani R.",0,500000),
    ("2026-03-14","VIR-118","Virement recu Benali K.",0,350000),
    ("2026-03-18","VIR-S042","Paiement BATIMETAL ciment",850000,0),
    ("2026-03-22","VIR-S043","Reglement GEO EXPERT",350000,0),
    ("2026-03-25","VIR-CNAS","CNAS cotisations mars",180000,0),
    ("2026-03-28","VIR-SAL","Salaires mars personnel",450000,0),
]
bal = 5000000
for date, ref, label, d, c in mvts:
    bal = bal - d + c
    cur.execute("INSERT INTO bank_movement (id,company_id,statement_id,movement_date,label,reference,debit,credit,balance_after,reconciled,created_at,is_deleted) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,false,%s,false)",
        (str(uuid.uuid4()), company_id, stmt_id, date, label, ref, d, c, bal, now))
conn.commit()
print(f"Banque: 1 releve BNA, {len(mvts)} mouvements")

# ═══ GED DOCUMENTS ═══
docs = [
    ("FACTURE_FOURNISSEUR","FAC-BATIMETAL-042.pdf","BATIMETAL SARL",850000,"Facture ciment 500 sacs"),
    ("FACTURE_FOURNISSEUR","FAC-SIDER-118.pdf","SIDER ANNABA",1200000,"Facture fer a beton T12"),
    ("FACTURE_FOURNISSEUR","FAC-GEO-007.pdf","GEO EXPERT",350000,"Facture etude geotechnique"),
    ("FACTURE_CLIENT","FAC-AMRANI-001.pdf","Amrani Rachid",9300000,"Vente F3-A-002"),
    ("FACTURE_CLIENT","FAC-BENALI-001.pdf","Benali Karim",12200000,"Vente F4-B-001"),
    ("CONTRAT","CTR-BATIMETAL.pdf","BATIMETAL SARL",5000000,"Contrat fourniture EDEN"),
    ("ACTE_NOTARIE","ACTE-AMRANI.pdf","Amrani Rachid",9300000,"Acte vente F3"),
    ("FICHE_PAIE","PAIE-HAMDI-03.pdf","Karim Hamdi",41937,"Bulletin paie mars"),
    ("PV_CHANTIER","PV-EDEN-12.pdf",None,0,"PV chantier avancement 35%"),
    ("RELEVE_BANCAIRE","RELEVE-BNA-03.pdf","BNA",0,"Releve BNA mars"),
]
for dtype, fname, tiers, montant, resume in docs:
    sha = hashlib.sha256(f"{fname}-{uuid.uuid4()}".encode()).hexdigest()
    cur.execute("INSERT INTO document_registry (id,company_id,file_name_original,sha256_hash,size_bytes,mime_type,doc_type,entite,projet,annee,tiers,montant_da,resume,status,ingested_at,archived_at,ingested_by,storage_url,confidence_scores) VALUES (%s,%s,%s,%s,50000,'application/pdf',%s,'SARL-DP','EDEN',2026,%s,%s,%s,'ARCHIVED',%s,%s,'admin@gfi.dz','/uploads/seed','{}')",
        (str(uuid.uuid4()), company_id, fname, sha, dtype, tiers, montant if montant > 0 else None, resume, now, now))
conn.commit()
print(f"GED: {len(docs)} documents archives")

# ═══ ADV DOSSIERS ═══
for t in ["echeance_c","echeancier_c","credit_tier_c","expert_report_c","wire_transfer_order_c","escrow_movement_c","dossier_document","dossier_transition_log"]:
    try:
        if t == "echeance_c":
            cur.execute("DELETE FROM echeance_c WHERE echeancier_id IN (SELECT id FROM echeancier_c)")
        else:
            cur.execute(f"DELETE FROM {t}")
    except: conn.rollback()
cur.execute("DELETE FROM payment")
cur.execute("DELETE FROM hr_commission")
cur.execute("DELETE FROM notary_escrow_c")
cur.execute("DELETE FROM dossier_adv")
cur.execute("UPDATE lot SET status='DISPONIBLE', locked_by=NULL, locked_until=NULL")
conn.commit()

lots = {}
for ref in ['A-F3-A-002','A-F4-B-001','A-F3-A-003']:
    cur.execute("SELECT id FROM lot WHERE ref = %s", (ref,))
    lots[ref] = str(cur.fetchone()[0])

dossiers = [
    (lots['A-F3-A-002'],"ADV-2026-EDEN-0201","Amrani Rachid","FONDS_PROPRES",9300000,3000000,"ENGAGE","SECURISE",3000000),
    (lots['A-F4-B-001'],"ADV-2026-EDEN-0202","Benali Karim","CREDIT_BANCAIRE",12200000,4500000,"EN_COURS_CREDIT","SECURISE",4500000),
    (lots['A-F3-A-003'],"ADV-2026-EDEN-0203","Cherifi Nadia","FONDS_PROPRES",9450000,3000000,"PRE_RESERVE","PARTIELLEMENT_SECURISE",1800000),
]
for lot_id, numero, client, tp, rf1, rf2, status, rf2s, rf2sec in dossiers:
    d_id = str(uuid.uuid4())
    cur.execute("INSERT INTO dossier_adv (id,company_id,numero,client_name,lot_id,project_id,type_paiement,prix_rf1,prix_rf2,status,rf2_status,montant_rf2_securise,created_at,updated_at,is_deleted) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,false)",
        (d_id, company_id, numero, client, lot_id, project_id, tp, rf1, rf2, status, rf2s, rf2sec, now, now))
    cur.execute("UPDATE lot SET status=%s WHERE id=%s", ("RESERVE" if status != "PRE_RESERVE" else "DISPONIBLE", lot_id))
    if numero.endswith("0201"):
        for amt in [500000,500000,500000]:
            cur.execute("INSERT INTO payment (id,company_id,dossier_id,type_rf,mode_reglement,montant,status,created_at,is_deleted) VALUES (%s,%s,%s,'RF1','CHEQUE',%s,'ENCAISSE',%s,false)", (str(uuid.uuid4()),company_id,d_id,amt,now))
    if numero.endswith("0203"):
        cur.execute("INSERT INTO payment (id,company_id,dossier_id,type_rf,mode_reglement,montant,status,created_at,is_deleted) VALUES (%s,%s,%s,'RF1','CHEQUE',500000,'EN_ATTENTE',%s,false)", (str(uuid.uuid4()),company_id,d_id,now))
    if numero.endswith("0202"):
        for num,lbl,pct,rt in [(0,"VSP 20%",20,"VIA_NOTAIRE"),(1,"Palier 15%",15,"DIRECT"),(2,"Palier 35%",35,"DIRECT"),(3,"Palier 25%",25,"DIRECT"),(4,"Remise cles 5%",5,"VIA_NOTAIRE")]:
            st = "EXPERT_VALIDE" if pct==15 else ("EXPERT_RECU" if pct==35 else "EN_ATTENTE")
            cur.execute("INSERT INTO credit_tier_c (id,company_id,dossier_id,tier_number,tier_label,percentage,montant,routing,status,created_at,is_deleted) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,false)",
                (str(uuid.uuid4()),company_id,d_id,num,lbl,pct,round(12200000*pct/100,2),rt,st,now))
        for dtype,label,source in [("CIN","CIN client","CLIENT"),("CONTRAT_CREDIT","Contrat credit","BANQUE"),("ORDRES_VIREMENT","Ordres virement","CLIENT")]:
            cur.execute("INSERT INTO dossier_document (id,company_id,dossier_id,document_type,label,source,required,received,relance_count,created_at,is_deleted) VALUES (%s,%s,%s,%s,%s,%s,true,false,0,%s,false)",
                (str(uuid.uuid4()),company_id,d_id,dtype,label,source,now))
    for fr,to in [("DISPONIBLE","PRE_RESERVE"),("PRE_RESERVE","RESERVE")]+([("RESERVE","ENGAGE")] if status in ("ENGAGE","EN_COURS_CREDIT") else [])+([("ENGAGE","EN_COURS_CREDIT")] if status=="EN_COURS_CREDIT" else []):
        cur.execute("INSERT INTO dossier_transition_log (id,company_id,dossier_id,from_status,to_status,triggered_by,created_at) VALUES (%s,%s,%s,%s,%s,'Admin',%s)", (str(uuid.uuid4()),company_id,d_id,fr,to,now))
conn.commit()
print(f"ADV: 3 dossiers (0201 FP/ENGAGE, 0202 CREDIT, 0203 FP/PRE_RESERVE)")

# ═══ STOCK ═══
zone_id = str(uuid.uuid4())
cur.execute("INSERT INTO storage_zone (id,company_id,code,label,location,is_active,created_at,is_deleted) VALUES (%s,%s,'Z-DEPOT','Depot principal','Cheraga',true,%s,false) ON CONFLICT ON CONSTRAINT uq_storage_zone_code DO NOTHING", (zone_id,company_id,now))
cur.execute("SELECT id FROM storage_zone WHERE code='Z-DEPOT'")
zone_id = str(cur.fetchone()[0])
for name,cat,qty,unit,price in [("Ciment CEM II",  "MATERIAU_CONSTRUCTION",200,"SAC",1200),
                                 ("Fer T12","MATERIAU_CONSTRUCTION",500,"KG",180),
                                 ("Peinture blanc","PEINTURE",30,"SEAU",8500),
                                 ("Cable 2.5mm","ELECTRICITE",1000,"M",120),
                                 ("Carrelage 60x60","REVETEMENT",150,"M2",2800)]:
    code = f"STK-{str(uuid.uuid4())[:6].upper()}"
    bc = hashlib.md5(code.encode()).hexdigest()[:13]
    iid = str(uuid.uuid4())
    cur.execute("INSERT INTO stock_item (id,company_id,project_id,zone_id,code,barcode,name,category,quantity,unit,unit_price,total_value,status,min_stock_alert,created_by,created_at,updated_at,is_deleted) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ACTIF',5,'Admin',%s,%s,false)",
        (iid,company_id,project_id,zone_id,code,bc,name,cat,qty,unit,price,qty*price,now,now))
    cur.execute("INSERT INTO stock_movement (id,company_id,item_id,movement_type,quantity,unit_price,total_value,reason,created_by,created_at,is_deleted) VALUES (%s,%s,%s,'ENTREE',%s,%s,%s,'Seed','Admin',%s,false)",
        (str(uuid.uuid4()),company_id,iid,qty,price,qty*price,now))
conn.commit()
print(f"Stock: 5 articles, zone Z-DEPOT")

# ═══ SUPPLIER ═══
sup_id = str(uuid.uuid4())
cur.execute("DELETE FROM supplier_payment")
cur.execute("DELETE FROM supplier_contract")
cur.execute("DELETE FROM supplier")
cur.execute("INSERT INTO supplier (id,company_id,code,name,contact_name,phone,category,total_contracts,total_paid,total_remaining,status,created_at,updated_at,is_deleted) VALUES (%s,%s,'FRN-0001','BATIMETAL SARL','M. Bouzid','0555-123456','MATERIAUX',5950000,850000,5100000,'ACTIF',%s,%s,false)",
    (sup_id,company_id,now,now))
cur.execute("INSERT INTO supplier_contract (id,company_id,supplier_id,project_id,contract_number,label,montant_ht,tva_rate,montant_tva,montant_ttc,status,total_paid,remaining,created_by,created_at,updated_at,is_deleted) VALUES (%s,%s,%s,%s,'CTR-00001','Fourniture materiaux EDEN',5000000,19,950000,5950000,'ACTIF',850000,5100000,'Admin',%s,%s,false)",
    (str(uuid.uuid4()),company_id,sup_id,project_id,now,now))
conn.commit()
print(f"Fournisseur: BATIMETAL + contrat 5.95M TTC")

conn.close()
print()
print("=" * 70)
print("WORKFLOWS A TESTER")
print("=" * 70)
print()
print("1. COMPTABLE (comptable@gfi.dz / gfi2026):")
print("   Journal → 10 ecritures mars 2026 (filtrer par periode)")
print("   Rapprochement Bancaire → releve BNA 6 mvts → 'Rapprocher par AI'")
print("   Rapprochement Ecritures↔Docs → 10 ecritures sans justif → 'Rapprocher par AI'")
print()
print("2. ADV (yazid@gfi.dz ou sara@gfi.dz):")
print("   0201 Amrani  ENGAGE         → Echeancier → generer → payer avec scan")
print("   0202 Benali  EN_COURS_CREDIT→ Deblocages → VSP 20% → paliers → notaire")
print("   0203 Cherifi PRE_RESERVE    → Valider paiement → securiser RF2 → RESERVE")
print()
print("3. STOCK (hayat@gfi.dz):")
print("   Catalogue → 5 articles | Sortie stock → scanner barcode")
print("   Fournisseurs → BATIMETAL → contrat → paiement")
print("   Ajouter element → camera/upload → AI identifie")
print()
print("4. RH (rh@gfi.dz):")
print("   Paie → calculer mars → approuver → verifier CC")
print()
print("5. DAF (ahmed@gfi.dz):")
print("   Dashboard → tout visible | CC → filtrer par annee/entite")
print("   GED → uploader document → AI classifie → confirmer → CC + juridique")
