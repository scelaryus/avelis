"""Seed fresh test data for all ADV tabs: echeancier, deblocages, notaire, documents, historique."""
import psycopg2
import uuid
from datetime import datetime, timezone

conn = psycopg2.connect("postgresql://gfi_user:gfi_password@localhost:5432/gfi_v7")
cur = conn.cursor()
now = datetime.now(timezone.utc)


# ── Clean up ─────────────────────────────────────────────────────────────
cur.execute("SELECT id FROM dossier_adv")
dossier_ids = [r[0] for r in cur.fetchall()]
for did in dossier_ids:
    did_s = str(did)
    cur.execute("DELETE FROM echeance_c WHERE echeancier_id IN (SELECT id FROM echeancier_c WHERE dossier_id = %s)", (did_s,))
    cur.execute("DELETE FROM echeancier_c WHERE dossier_id = %s", (did_s,))
    cur.execute("DELETE FROM credit_tier_c WHERE dossier_id = %s", (did_s,))
    cur.execute("DELETE FROM expert_report_c WHERE dossier_id = %s", (did_s,))
    cur.execute("DELETE FROM wire_transfer_order_c WHERE dossier_id = %s", (did_s,))
    cur.execute("DELETE FROM escrow_movement_c WHERE dossier_id = %s", (did_s,))
    cur.execute("DELETE FROM dossier_document WHERE dossier_id = %s", (did_s,))
    cur.execute("DELETE FROM dossier_transition_log WHERE dossier_id = %s", (did_s,))
    cur.execute("DELETE FROM payment WHERE dossier_id = %s", (did_s,))
cur.execute("DELETE FROM notary_escrow_c")
cur.execute("DELETE FROM hr_commission WHERE dossier_adv_id IN (SELECT id FROM dossier_adv)")
cur.execute("DELETE FROM dossier_adv")
cur.execute("UPDATE lot SET status = 'DISPONIBLE', locked_by = NULL, locked_until = NULL WHERE status != 'DISPONIBLE'")
conn.commit()
print("Cleaned old data")


# ── References ───────────────────────────────────────────────────────────
cur.execute("SELECT id FROM company WHERE code = 'SARL-DP'")
company_id = str(cur.fetchone()[0])
cur.execute("SELECT id FROM project WHERE code = 'EDEN'")
project_id = str(cur.fetchone()[0])


# ═════════════════════════════════════════════════════════════════════════
# DOSSIER 1: FONDS_PROPRES — ENGAGE
# Test: Echeancier generation, installment payment, penalties
# ═════════════════════════════════════════════════════════════════════════
d1_id = str(uuid.uuid4())
cur.execute("SELECT id FROM lot WHERE ref = 'A-F3-A-002'")
lot1 = str(cur.fetchone()[0])
cur.execute("""
    INSERT INTO dossier_adv (id, company_id, numero, client_name, lot_id, project_id,
        type_paiement, prix_rf1, prix_rf2, status, rf2_status, montant_rf2_securise,
        tier_engagement_pct, tier_discount_pct, prix_base_rf1, prix_base_rf2, prix_base_reel,
        created_at, updated_at, is_deleted)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,false)
""", (d1_id, company_id, 'ADV-2026-EDEN-0101', 'Amrani Rachid', lot1, project_id,
      'FONDS_PROPRES', 9300000, 3000000, 'ENGAGE', 'SECURISE', 3000000,
      30, 0, 9300000, 3000000, 12300000, now, now))
cur.execute("UPDATE lot SET status = 'RESERVE' WHERE id = %s", (lot1,))

# 1.5M RF1 already paid (leaves 7.8M for echeancier)
for amt in [500000, 500000, 500000]:
    cur.execute("""
        INSERT INTO payment (id, company_id, dossier_id, type_rf, mode_reglement, montant, status, created_at, is_deleted)
        VALUES (%s,%s,%s,'RF1','CHEQUE',%s,'ENCAISSE',%s,false)
    """, (str(uuid.uuid4()), company_id, d1_id, amt, now))

print("Created: ADV-2026-EDEN-0101 | FONDS_PROPRES | ENGAGE | 1.5M paid, ready for echeancier")


# ═════════════════════════════════════════════════════════════════════════
# DOSSIER 2: CREDIT_BANCAIRE — EN_COURS_CREDIT
# Test: Credit tiers, expert reports, wire orders, documents, escrow
# ═════════════════════════════════════════════════════════════════════════
d2_id = str(uuid.uuid4())
cur.execute("SELECT id FROM lot WHERE ref = 'A-F4-B-001'")
lot2 = str(cur.fetchone()[0])
cur.execute("""
    INSERT INTO dossier_adv (id, company_id, numero, client_name, lot_id, project_id,
        type_paiement, prix_rf1, prix_rf2, status, rf2_status, montant_rf2_securise,
        tier_engagement_pct, tier_discount_pct, prix_base_rf1, prix_base_rf2, prix_base_reel,
        created_at, updated_at, is_deleted)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,false)
""", (d2_id, company_id, 'ADV-2026-EDEN-0102', 'Benali Karim', lot2, project_id,
      'CREDIT_BANCAIRE', 12200000, 4500000, 'EN_COURS_CREDIT', 'SECURISE', 4500000,
      30, 0, 12200000, 4500000, 16700000, now, now))
cur.execute("UPDATE lot SET status = 'RESERVE' WHERE id = %s", (lot2,))

# 5 credit tiers
tiers_def = [
    (0, 'VSP 20%', 20, 'VIA_NOTAIRE'),
    (1, 'Palier 15%', 15, 'DIRECT'),
    (2, 'Palier 35%', 35, 'DIRECT'),
    (3, 'Palier 25%', 25, 'DIRECT'),
    (4, 'Remise cles 5%', 5, 'VIA_NOTAIRE'),
]
for num, label, pct, routing in tiers_def:
    montant = round(12200000 * pct / 100, 2)
    cur.execute("""
        INSERT INTO credit_tier_c (id, company_id, dossier_id, tier_number, tier_label, percentage, montant, routing, status, created_at, is_deleted)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'EN_ATTENTE',%s,false)
    """, (str(uuid.uuid4()), company_id, d2_id, num, label, pct, montant, routing, now))

# 9 documents (3 received, 6 pending)
docs = [
    ('CIN', 'CIN client', 'CLIENT', True),
    ('FICHE_FAMILIALE', 'Fiche familiale', 'CLIENT', True),
    ('ATTESTATION_TRAVAIL', 'Attestation de travail', 'CLIENT', False),
    ('FICHES_PAIE', '3 fiches de paie', 'CLIENT', False),
    ('RELEVES_BANCAIRES', 'Releves bancaires 6 mois', 'CLIENT', False),
    ('CONTRAT_CREDIT', 'Contrat credit signe', 'BANQUE', False),
    ('CONTRAT_ENREGISTRE_IMPOTS', 'Contrat enregistre aux impots', 'CLIENT', False),
    ('ACTE_PROPRIETE', 'Acte propriete terrain', 'ENTREPRISE', True),
    ('ORDRES_VIREMENT', '3 ordres de virement signes', 'CLIENT', False),
]
for dtype, label, source, received in docs:
    cur.execute("""
        INSERT INTO dossier_document (id, company_id, dossier_id, document_type, label, source, required, received, received_at, relance_count, created_at, is_deleted)
        VALUES (%s,%s,%s,%s,%s,%s,true,%s,%s,%s,%s,false)
    """, (str(uuid.uuid4()), company_id, d2_id, dtype, label, source,
          received, now if received else None, 2 if not received else 0, now))

# Wire transfer orders: 15% signed, 35% signed, 25% not yet
for pct in [15, 35, 25]:
    montant = round(12200000 * pct / 100, 2)
    status = 'SIGNE' if pct in (15, 35) else 'EN_ATTENTE'
    sig_date = '2026-03-10' if status == 'SIGNE' else None
    cur.execute("""
        INSERT INTO wire_transfer_order_c (id, company_id, dossier_id, tier_percentage, montant, status, signature_date, created_at, is_deleted)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,false)
    """, (str(uuid.uuid4()), company_id, d2_id, pct, montant, status, sig_date, now))

# Expert reports: 15% validated, 35% received but not yet validated
r15_id = str(uuid.uuid4())
cur.execute("""
    INSERT INTO expert_report_c (id, company_id, dossier_id, tier_percentage, expert_name, report_date, completion_pct, conformity, status, validated_by, validated_at, created_at, is_deleted)
    VALUES (%s,%s,%s,15,'Expert Bouzid','2026-03-15',100,true,'VALIDE','Resp. Technique',%s,%s,false)
""", (r15_id, company_id, d2_id, now, now))
r35_id = str(uuid.uuid4())
cur.execute("""
    INSERT INTO expert_report_c (id, company_id, dossier_id, tier_percentage, expert_name, report_date, completion_pct, conformity, status, created_at, is_deleted)
    VALUES (%s,%s,%s,35,'Expert Bouzid','2026-03-20',85,true,'RECU',%s,false)
""", (r35_id, company_id, d2_id, now))

# Link reports to tiers
cur.execute("""UPDATE credit_tier_c SET status = 'EXPERT_VALIDE', expert_report_id = %s
    WHERE dossier_id = %s AND percentage = 15""", (r15_id, d2_id))
cur.execute("""UPDATE credit_tier_c SET status = 'EXPERT_RECU', expert_report_id = %s
    WHERE dossier_id = %s AND percentage = 35""", (r35_id, d2_id))

print("Created: ADV-2026-EDEN-0102 | CREDIT_BANCAIRE | EN_COURS_CREDIT | 5 tiers, 9 docs, 2 reports, 2/3 orders")


# ═════════════════════════════════════════════════════════════════════════
# DOSSIER 3: FONDS_PROPRES — PRE_RESERVE (fresh, RF2 partial)
# Test: RF2 securization, transition blocking, payment recording
# ═════════════════════════════════════════════════════════════════════════
d3_id = str(uuid.uuid4())
cur.execute("SELECT id FROM lot WHERE ref = 'A-F3-A-003'")
lot3 = str(cur.fetchone()[0])
cur.execute("""
    INSERT INTO dossier_adv (id, company_id, numero, client_name, lot_id, project_id,
        type_paiement, prix_rf1, prix_rf2, status, rf2_status, montant_rf2_securise,
        created_at, updated_at, is_deleted)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,false)
""", (d3_id, company_id, 'ADV-2026-EDEN-0103', 'Cherifi Nadia', lot3, project_id,
      'FONDS_PROPRES', 9450000, 3000000, 'PRE_RESERVE', 'PARTIELLEMENT_SECURISE', 1800000,
      now, now))

# One EN_ATTENTE payment (not yet validated)
cur.execute("""
    INSERT INTO payment (id, company_id, dossier_id, type_rf, mode_reglement, montant, status, created_at, is_deleted)
    VALUES (%s,%s,%s,'RF1','CHEQUE',500000,'EN_ATTENTE',%s,false)
""", (str(uuid.uuid4()), company_id, d3_id, now))

print("Created: ADV-2026-EDEN-0103 | FONDS_PROPRES | PRE_RESERVE | RF2 60% (1.8M/3M), 1 payment pending")


# ═════════════════════════════════════════════════════════════════════════
# TRANSITION HISTORY for all dossiers
# ═════════════════════════════════════════════════════════════════════════
transitions = [
    (d1_id, 'DISPONIBLE', 'PRE_RESERVE', 'Agent Mourad'),
    (d1_id, 'PRE_RESERVE', 'RESERVE', 'Agent Mourad'),
    (d1_id, 'RESERVE', 'ENGAGE', 'Responsable ADV'),
    (d2_id, 'DISPONIBLE', 'PRE_RESERVE', 'Agent Kamel'),
    (d2_id, 'PRE_RESERVE', 'RESERVE', 'Agent Kamel'),
    (d2_id, 'RESERVE', 'ENGAGE', 'Responsable ADV'),
    (d2_id, 'ENGAGE', 'EN_COURS_CREDIT', 'Responsable ADV'),
    (d3_id, 'DISPONIBLE', 'PRE_RESERVE', 'Agent Samia'),
]
for did, fr, to, by in transitions:
    cur.execute("""
        INSERT INTO dossier_transition_log (id, company_id, dossier_id, from_status, to_status, triggered_by, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (str(uuid.uuid4()), company_id, did, fr, to, by, now))

conn.commit()
conn.close()

print()
print("=" * 70)
print("TEST PLAN")
print("=" * 70)
print()
print("DOSSIER 0101 (Fonds Propres, ENGAGE):")
print("  Tab Echeancier  -> Generate echeancier (7.8M over 24 months)")
print("                  -> Pay installment #1 (cheque only)")
print("  Tab Documents   -> Empty (engage without auto-init, trigger transition)")
print("  Tab Paiements   -> 3 payments ENCAISSE (500K each)")
print("  Tab Historique   -> 3 transitions logged")
print()
print("DOSSIER 0102 (Credit Bancaire, EN_COURS_CREDIT):")
print("  Tab Deblocages  -> 5 tiers: tier 0 EN_ATTENTE, tier 1 EXPERT_VALIDE,")
print("                     tier 2 EXPERT_RECU, tiers 3-4 EN_ATTENTE")
print("                  -> Click 'Enregistrer deblocage' on tier 1 (15%)")
print("                  -> Click 'VSP 20%' on tier 0 to test escrow transit")
print("  Tab Documents   -> 9 docs: 3 received, 6 pending with alert levels")
print("                  -> Click 'Marquer recu' on pending docs")
print("  Tab Notaire     -> Empty until you trigger VSP 20% from Deblocages")
print("                  -> After VSP: 2 movements (CREDIT + DEBIT)")
print("  Tab Historique   -> 4 transitions logged")
print()
print("DOSSIER 0103 (Fonds Propres, PRE_RESERVE):")
print("  Tab Paiements   -> 1 payment EN_ATTENTE -> click 'Valider'")
print("  Tab Resume      -> RF2 60% progress bar")
print("  Transitions     -> Try RESERVE (blocked: RF2 not secured)")
print("                  -> Record RF2 payments to reach 100%")
