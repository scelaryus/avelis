"""Plan Comptable SCF Algérien — seed data and auto-journal creation.

Implements:
  - EX-SCF-001: Built-in SCF chart of accounts
  - EX-SCF-002: Auto-create default journals per entity
"""
import uuid
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# ── SCF Plan Comptable Algérien (classes 1-7) ──────────────────────────────
# Only the main accounts used in real-estate / construction.
# Sub-accounts can be added per entity via the API.

SCF_ACCOUNTS = [
    # Classe 1 — Capitaux propres
    ("10", "Capital, réserves et assimilés", "equity"),
    ("101", "Capital social", "equity"),
    ("106", "Réserves", "equity"),
    ("108", "Compte de l'exploitant", "equity"),
    ("12", "Résultat de l'exercice", "equity"),
    ("120", "Résultat de l'exercice (bénéfice)", "equity"),
    ("129", "Résultat de l'exercice (perte)", "equity"),
    ("13", "Produits et charges différés", "equity"),
    ("16", "Emprunts et dettes assimilées", "liability"),
    ("164", "Emprunts auprès des établissements de crédit", "liability"),
    ("165", "Dépôts et cautionnements reçus", "liability"),
    ("168", "Autres emprunts et dettes assimilées", "liability"),
    ("17", "Dettes rattachées à des participations", "liability"),
    ("171", "Dettes rattachées à des participations (groupe)", "liability"),
    ("173", "Comptes courants d'associés", "liability"),

    # Classe 2 — Immobilisations
    ("20", "Immobilisations incorporelles", "asset"),
    ("21", "Immobilisations corporelles", "asset"),
    ("211", "Terrains", "asset"),
    ("213", "Constructions", "asset"),
    ("215", "Installations techniques, matériel et outillage", "asset"),
    ("218", "Autres immobilisations corporelles", "asset"),
    ("23", "Immobilisations en cours", "asset"),
    ("26", "Participations et créances rattachées", "asset"),
    ("27", "Autres immobilisations financières", "asset"),
    ("28", "Amortissements des immobilisations", "asset"),

    # Classe 3 — Stocks et en-cours
    ("31", "Matières premières et fournitures", "asset"),
    ("33", "En-cours de production de biens", "asset"),
    ("35", "Stocks de produits", "asset"),
    ("37", "Stocks à l'extérieur", "asset"),
    ("38", "Achats stockés", "asset"),
    ("39", "Pertes de valeur sur stocks", "asset"),

    # Classe 4 — Tiers
    ("40", "Fournisseurs et comptes rattachés", "liability"),
    ("401", "Fournisseurs", "liability"),
    ("404", "Fournisseurs d'immobilisations", "liability"),
    ("408", "Fournisseurs — factures non parvenues", "liability"),
    ("409", "Fournisseurs débiteurs — avances et acomptes", "asset"),
    ("41", "Clients et comptes rattachés", "asset"),
    ("411", "Clients", "asset"),
    ("413", "Clients — effets à recevoir", "asset"),
    ("416", "Clients douteux", "asset"),
    ("418", "Clients — produits non encore facturés", "asset"),
    ("419", "Clients créditeurs — avances reçues", "liability"),
    ("42", "Personnel et comptes rattachés", "liability"),
    ("421", "Personnel — rémunérations dues", "liability"),
    ("425", "Personnel — avances et acomptes", "asset"),
    ("43", "Organismes sociaux et comptes rattachés", "liability"),
    ("431", "CNAS", "liability"),
    ("432", "Autres organismes sociaux", "liability"),
    ("44", "État et collectivités publiques", "liability"),
    ("441", "État — impôts sur les bénéfices (IBS)", "liability"),
    ("4452", "État — TVA due intracommunautaire", "liability"),
    ("4456", "TVA déductible", "asset"),
    ("4457", "TVA collectée", "liability"),
    ("4458", "TVA à régulariser", "liability"),
    ("447", "Autres impôts, taxes et versements assimilés", "liability"),
    ("4471", "TAP — Taxe sur l'Activité Professionnelle", "liability"),
    ("4472", "IRG — Impôt sur le Revenu Global", "liability"),
    ("4473", "Timbre fiscal", "liability"),
    ("45", "Groupe et associés", "liability"),
    ("451", "Opérations groupe", "liability"),
    ("455", "Associés — comptes courants", "liability"),
    ("456", "Associés — opérations sur le capital", "liability"),
    ("46", "Débiteurs divers et créditeurs divers", "liability"),
    ("47", "Comptes transitoires ou d'attente", "liability"),
    ("48", "Charges ou produits constatés d'avance", "liability"),
    ("49", "Pertes de valeur sur comptes de tiers", "asset"),

    # Classe 5 — Financier
    ("51", "Banques, établissements financiers et assimilés", "asset"),
    ("512", "Banques — comptes courants", "asset"),
    ("514", "Chèques à encaisser", "asset"),
    ("515", "Trésor public et établissements publics", "asset"),
    ("517", "Autres organismes financiers", "asset"),
    ("52", "Instruments financiers dérivés", "asset"),
    ("53", "Caisse", "asset"),
    ("531", "Caisse siège", "asset"),
    ("532", "Caisse chantier", "asset"),
    ("54", "Régies d'avances et accréditifs", "asset"),
    ("58", "Virements internes", "asset"),
    ("59", "Pertes de valeur sur actifs financiers", "asset"),

    # Classe 6 — Charges
    ("60", "Achats consommés", "expense"),
    ("601", "Matières premières", "expense"),
    ("602", "Autres approvisionnements", "expense"),
    ("604", "Achats d'études et de prestations de services", "expense"),
    ("605", "Achats de matériel, équipements et travaux", "expense"),
    ("607", "Achats de marchandises", "expense"),
    ("61", "Services extérieurs", "expense"),
    ("613", "Locations", "expense"),
    ("614", "Charges locatives et de copropriété", "expense"),
    ("615", "Entretien et réparations", "expense"),
    ("616", "Primes d'assurance", "expense"),
    ("617", "Études et recherches", "expense"),
    ("618", "Documentation et divers", "expense"),
    ("62", "Autres services extérieurs", "expense"),
    ("621", "Personnel extérieur à l'entreprise", "expense"),
    ("622", "Rémunérations d'intermédiaires et honoraires", "expense"),
    ("623", "Publicité, publications, relations publiques", "expense"),
    ("624", "Transports de biens et transport collectif du personnel", "expense"),
    ("625", "Déplacements, missions et réceptions", "expense"),
    ("626", "Frais postaux et de télécommunications", "expense"),
    ("627", "Services bancaires et assimilés", "expense"),
    ("63", "Charges de personnel", "expense"),
    ("631", "Rémunérations du personnel", "expense"),
    ("634", "Rémunérations de l'exploitant", "expense"),
    ("635", "Cotisations aux organismes sociaux (CNAS)", "expense"),
    ("636", "Charges sociales de l'exploitant", "expense"),
    ("637", "Autres charges sociales", "expense"),
    ("64", "Impôts, taxes et versements assimilés", "expense"),
    ("641", "Impôts et taxes directes", "expense"),
    ("642", "Impôts et taxes indirectes", "expense"),
    ("645", "Autres impôts et taxes (TAP, CACOBATPH)", "expense"),
    ("65", "Autres charges opérationnelles", "expense"),
    ("66", "Charges financières", "expense"),
    ("661", "Charges d'intérêts", "expense"),
    ("665", "Écarts de change (pertes)", "expense"),
    ("67", "Éléments extraordinaires — charges", "expense"),
    ("68", "Dotations aux amortissements, provisions et pertes de valeur", "expense"),
    ("69", "Impôts sur les bénéfices (IBS)", "expense"),
    ("695", "IBS — Impôt sur les bénéfices des sociétés", "expense"),

    # Classe 7 — Produits
    ("70", "Ventes de marchandises et produits fabriqués, ventes de prestations", "revenue"),
    ("701", "Ventes de produits finis (immobilier)", "revenue"),
    ("704", "Ventes de travaux", "revenue"),
    ("705", "Ventes d'études", "revenue"),
    ("706", "Prestations de services", "revenue"),
    ("707", "Ventes de marchandises", "revenue"),
    ("708", "Produits des activités annexes", "revenue"),
    ("71", "Production stockée ou déstockée", "revenue"),
    ("72", "Production immobilisée", "revenue"),
    ("74", "Subventions d'exploitation", "revenue"),
    ("75", "Autres produits opérationnels", "revenue"),
    ("76", "Produits financiers", "revenue"),
    ("761", "Produits des participations", "revenue"),
    ("762", "Revenus des actifs financiers", "revenue"),
    ("765", "Écarts de change (gains)", "revenue"),
    ("77", "Éléments extraordinaires — produits", "revenue"),
    ("78", "Reprises sur pertes de valeur et provisions", "revenue"),
]

# ── Default journals per entity ────────────────────────────────────────────

DEFAULT_JOURNALS = [
    ("ACH", "Journal des Achats", "ACHAT"),
    ("VTE", "Journal des Ventes", "VENTE"),
    ("BNQ", "Journal de Banque", "BANQUE"),
    ("CAI", "Journal de Caisse", "CAISSE"),
    ("OD", "Journal des Opérations Diverses", "OD"),
]


async def seed_scf_plan_comptable(db: AsyncSession, tenant_id: str) -> int:
    """Seed the SCF plan comptable for a tenant if not already present.

    Returns the number of accounts created.
    """
    # Check if already seeded
    result = await db.execute(
        text("SELECT COUNT(*) FROM chart_of_accounts WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    count = result.scalar()
    if count and count > 20:
        return 0  # Already seeded

    created = 0
    for code, label, account_type in SCF_ACCOUNTS:
        parent = code[:-1] if len(code) > 2 else None
        await db.execute(
            text("""
                INSERT OR IGNORE INTO chart_of_accounts (id, tenant_id, code, label, account_type, parent_code, is_active)
                VALUES (:id, :tid, :code, :label, :atype, :parent, 1)
            """),
            {
                "id": str(uuid.uuid4()),
                "tid": tenant_id,
                "code": code,
                "label": label,
                "atype": account_type,
                "parent": parent,
            },
        )
        created += 1

    await db.commit()
    return created


async def ensure_default_journals(db: AsyncSession, tenant_id: str) -> int:
    """Create default journals for each entity if they don't exist.

    Returns total journals created.
    """
    result = await db.execute(
        text("SELECT id, code FROM entreprises WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    entreprises = result.fetchall()

    created = 0
    for ent_id, ent_code in entreprises:
        for j_code, j_label, j_type in DEFAULT_JOURNALS:
            full_code = f"{ent_code}-{j_code}"
            existing = await db.execute(
                text("SELECT id FROM journaux WHERE entreprise_id = :eid AND code = :code"),
                {"eid": ent_id, "code": full_code},
            )
            if existing.scalar_one_or_none():
                continue
            await db.execute(
                text("""
                    INSERT INTO journaux (id, tenant_id, entreprise_id, code, libelle, type_journal)
                    VALUES (:id, :tid, :eid, :code, :label, :jtype)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "tid": tenant_id,
                    "eid": ent_id,
                    "code": full_code,
                    "label": f"{j_label} — {ent_code}",
                    "jtype": j_type,
                },
            )
            created += 1

    await db.commit()
    return created
