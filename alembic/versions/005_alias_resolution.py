"""Alias resolution engine: entity_alias table + pg_trgm + seed registry.

Enables resolving 20+ years of variant names to canonical entities.
Pipeline: exact match -> fuzzy (pg_trgm >= 0.6) -> BLOCK + formulaire.

Database features:
- pg_trgm extension for trigram similarity search
- GIN index on alias_normalized for fast fuzzy lookups
- unaccent extension for accent-insensitive normalization
- Soft-delete + no-physical-delete triggers (KT-10)

Seed data: ~80 aliases across projects, associates, and companies.

Kill Test KT-05: "LIAZID" -> blocked, proposes "Lyazid"
Test TD-09: "LES LYS" and "02 HECTARE" -> both resolve to LYS

Revision ID: 005
Revises: 004
Create Date: 2026-03-18
"""
from typing import Sequence, Union
import unicodedata

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"

# Use ETS-DK as the company_id for alias seed records (first entity).
# Aliases are system-wide but GFIBase requires a company_id.
DEFAULT_COMPANY_ID = "10000000-0000-0000-0000-000000000001"

# ─── Deterministic UUID counter ──────────────────────────────────────────────
_alias_counter = 0


def _alias_uuid():
    global _alias_counter
    _alias_counter += 1
    return f"a1000000-0000-0000-0000-{_alias_counter:012x}"


def _normalize(text: str) -> str:
    """Normalize: lowercase, strip accents, collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


# ─── Standard system columns ────────────────────────────────────────────────
def _system_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_by", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("version", sa.Integer, nullable=False,
                  server_default=sa.text("1")),
    ]


# ─── Reuse entity UUIDs from prior migrations ───────────────────────────────
COMPANY_IDS = {
    "ETS-DK":   "10000000-0000-0000-0000-000000000001",
    "SARL-DP":  "10000000-0000-0000-0000-000000000002",
    "SARL-DBPI":"10000000-0000-0000-0000-000000000003",
    "SARL-OC":  "10000000-0000-0000-0000-000000000004",
    "SARL-SEN": "10000000-0000-0000-0000-000000000005",
    "SARL-EP":  "10000000-0000-0000-0000-000000000006",
    "EURL-BIM": "10000000-0000-0000-0000-000000000007",
    "SARL-AMF": "10000000-0000-0000-0000-000000000008",
    "EURL-BAY": "10000000-0000-0000-0000-000000000009",
    "SARL-M60": "10000000-0000-0000-0000-00000000000a",
    "SARL-ARC": "10000000-0000-0000-0000-00000000000b",
    "SCI-DEN":  "10000000-0000-0000-0000-00000000000c",
}

ASSOCIATE_IDS = {
    "ADMIN Ahmed":                  "20000000-0000-0000-0000-000000000001",
    "ASSOC Mohamed":                "20000000-0000-0000-0000-000000000002",
    "ASSOC Yazid (Lyazid)":         "20000000-0000-0000-0000-000000000003",
    "ASSOC Yamina (Ait Benamara)":  "20000000-0000-0000-0000-000000000004",
    "BOUMERDASSI Mustapha":           "20000000-0000-0000-0000-000000000005",
    "AMIRAT Brahim":                  "20000000-0000-0000-0000-000000000006",
    "ASSOC Laid":                   "20000000-0000-0000-0000-000000000007",
    "MOUKHTARI Tarek":                "20000000-0000-0000-0000-000000000008",
    "MOUKHTARI Amine":                "20000000-0000-0000-0000-000000000009",
}

PROJECT_IDS = {
    "EDEN":         "30000000-0000-0000-0000-000000000001",
    "JASMIN":       "30000000-0000-0000-0000-000000000002",
    "OPERA":        "30000000-0000-0000-0000-000000000003",
    "LYS":          "30000000-0000-0000-0000-000000000004",
    "IRENE":        "30000000-0000-0000-0000-000000000005",
    "MAGNOLIA":     "30000000-0000-0000-0000-000000000006",
    "AUREA":        "30000000-0000-0000-0000-000000000007",
    "ASTERIA":      "30000000-0000-0000-0000-000000000008",
    "MOSQUEE":      "30000000-0000-0000-0000-000000000009",
    "T21000":       "30000000-0000-0000-0000-00000000000a",
    "T5000":        "30000000-0000-0000-0000-00000000000b",
    "T2400":        "30000000-0000-0000-0000-00000000000c",
    "ELITE-DRIVE":  "30000000-0000-0000-0000-00000000000d",
    "ALLO-MAISON":  "30000000-0000-0000-0000-00000000000e",
    "PFSB":         "30000000-0000-0000-0000-00000000000f",
    "DG":           "30000000-0000-0000-0000-000000000010",
}

# ═════════════════════════════════════════════════════════════════════════════
# ALIAS SEED DATA
# ═════════════════════════════════════════════════════════════════════════════
# Each entry: (entity_type, target_key, canonical_name, [list of raw aliases])
# The canonical name itself is ALSO registered as an alias for exact-match.

PROJECT_ALIASES = [
    ("LYS", "Les Lys", [
        "LYS", "Les Lys", "02H", "02 Hectare", "Bentala", "Draria",
        "02Hectare", "LES LYS", "Dhous 2 hectare",
    ]),
    ("IRENE", "Irène / 05 Hectare", [
        "IRENE", "Irène", "05 Hectare", "5H", "Ami Djamel", "05H",
        "05HECTARE", "Boumerdes",
    ]),
    ("JASMIN", "Les Jasmins", [
        "JASMIN", "Sahel", "Les Jasmins",
    ]),
    ("EDEN", "Eden", [
        "EDEN", "FOES",
    ]),
    ("OPERA", "Jardin de l'Opéra", [
        "OPERA", "Ouled Fayet", "Les Jardins de l'Opera",
        "Jardin de l'Opéra",
    ]),
    ("MAGNOLIA", "Magnolia", [
        "MAGNOLIA", "Les Magnolia",
    ]),
    ("AUREA", "Auréa", [
        "AUREA", "Cheraga", "Chéraga", "Auréa",
    ]),
    ("ASTERIA", "Asteria", [
        "ASTERIA", "El Achour",
    ]),
    ("MOSQUEE", "Mosquée Taoura", [
        "MOSQUEE", "Mosquée Taoura", "Taoura", "Taourga",
    ]),
    ("T21000", "Terrain 21 000 m²", [
        "T21000", "Terrain 21000",
    ]),
    ("T5000", "Terrain 5 000 m²", [
        "T5000", "Terrain 5000",
    ]),
    ("T2400", "Terrain 2 400 m²", [
        "T2400", "Terrain 2400",
    ]),
    ("ELITE-DRIVE", "Elite Drive", [
        "ELITE-DRIVE", "ELITE DRIVE", "Elite Drive",
    ]),
    ("ALLO-MAISON", "Allo Maison", [
        "ALLO-MAISON", "ALLO MAISON", "Allo Maison",
    ]),
    ("PFSB", "PFSB", [
        "PFSB",
    ]),
    ("DG", "DG", [
        "DG",
    ]),
]

ASSOCIATE_ALIASES = [
    ("ADMIN Ahmed", "ADMIN Ahmed", [
        "ADMIN Ahmed", "Ahmed", "Hmed", "A.GFI",
        "AHMED ADMIN", "A.D.",
    ]),
    ("ASSOC Mohamed", "ASSOC Mohamed", [
        "ASSOC Mohamed", "Mohamed", "Moh", "Mohammed",
        "M.GFI", "Mouh",
    ]),
    ("ASSOC Yazid (Lyazid)", "ASSOC Yazid (Lyazid)", [
        "ASSOC Yazid (Lyazid)", "Yazid", "Lyazid", "Bouabdellah",
        "Lyazid Bouabdellah", "Y.Bouabdellah",
    ]),
    ("ASSOC Yamina (Ait Benamara)", "ASSOC Yamina (Ait Benamara)", [
        "ASSOC Yamina (Ait Benamara)", "Yamina", "Y.Ait Benamara",
        "Yamina AIT", "Ait Benamara", "ASSOC Yamina",
    ]),
    ("BOUMERDASSI Mustapha", "BOUMERDASSI Mustapha", [
        "BOUMERDASSI Mustapha", "Boumerdassi",
    ]),
    ("AMIRAT Brahim", "AMIRAT Brahim", [
        "AMIRAT Brahim", "Amirat",
    ]),
    ("ASSOC Laid", "ASSOC Laid", [
        "ASSOC Laid", "Laid",
    ]),
    ("MOUKHTARI Tarek", "MOUKHTARI Tarek", [
        "MOUKHTARI Tarek", "Moukhtari",
    ]),
    ("MOUKHTARI Amine", "MOUKHTARI Amine", [
        "MOUKHTARI Amine", "Moukhtari Amine",
    ]),
]

COMPANY_ALIASES = [
    ("SARL-AMF", "SARL AMENFORT Béton", [
        "SARL AMENFORT Béton", "AMENFORT", "SARL AMENFORT",
        "Amenfort Beton", "Amenfort Béton",
    ]),
    ("EURL-BAY", "EURL BAYTI / ALLO MAISON", [
        "EURL BAYTI / ALLO MAISON", "BAYTI", "Bayti", "EURL BAYTI",
        "Allo Maison", "BAYTI ALLO MAISON",
        "Novus Allo Maison", "SARL Novus Allo Maison",
    ]),
    ("SARL-DP", "SARL GFI Promotion", [
        "SARL GFI Promotion", "GFI Promo",
        "GFI Promotion",
    ]),
    ("SARL-DBPI", "SARL DBPI Immobilier", [
        "SARL DBPI Immobilier", "DBPI", "SARL DBPI", "DBPI Immobilier",
    ]),
    ("SARL-OC", "SARL Omega Construction", [
        "SARL Omega Construction", "Omega", "SARL Omega",
        "Omega Construction",
    ]),
    ("EURL-BIM", "EURL Bimha Construction", [
        "EURL Bimha Construction", "Bimha", "EURL Bimha",
        "Bimha Construction",
    ]),
    ("SARL-SEN", "SARL Senimar", [
        "SARL Senimar", "Senimar",
    ]),
    ("SARL-EP", "SARL Elite Promotion", [
        "SARL Elite Promotion", "Elite", "SARL Elite", "Elite Promotion",
    ]),
    ("SARL-M60", "SARL Maison en 60 Jours", [
        "SARL Maison en 60 Jours", "Maison 60 Jours", "M60J",
    ]),
    ("SARL-ARC", "SARL ARCEN", [
        "SARL ARCEN", "ARCEN", "Arcen",
    ]),
    ("SCI-DEN", "SCI GFI", [
        "SCI GFI", "SCI", "SCI DEN",
    ]),
    ("ETS-DK", "ETS GFI Fondation", [
        "ETS GFI Fondation", "ETS-DK", "ETS DK",
        "GFI Fondation",
    ]),
]


def upgrade() -> None:
    # ═════════════════════════════════════════════════════════════════════
    # 1. ENABLE pg_trgm AND unaccent EXTENSIONS
    # ═════════════════════════════════════════════════════════════════════
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")

    # ═════════════════════════════════════════════════════════════════════
    # 2. CREATE entity_alias TABLE
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "entity_alias",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        # Entity classification
        sa.Column("entity_type", sa.String(20), nullable=False, index=True),
        # Polymorphic target
        sa.Column("target_id", UUID(as_uuid=True), nullable=False, index=True),
        # Alias text
        sa.Column("alias_raw", sa.Text, nullable=False),
        sa.Column("alias_normalized", sa.Text, nullable=False),
        # Canonical name (denormalized)
        sa.Column("canonical_name", sa.String(255), nullable=False),
        # System columns
        *_system_columns(),
        # Unique: one normalized alias per entity type
        sa.UniqueConstraint("entity_type", "alias_normalized",
                            name="uq_entity_alias_type_normalized"),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. GIN INDEX for trigram fuzzy search
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE INDEX ix_entity_alias_trgm
        ON entity_alias
        USING GIN (alias_normalized gin_trgm_ops);
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 4. TRIGGERS
    # ═════════════════════════════════════════════════════════════════════
    op.execute("""
        CREATE TRIGGER trg_entity_alias_updated_at
        BEFORE UPDATE ON entity_alias
        FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
    """)
    op.execute("SELECT gfi_apply_no_delete_trigger('entity_alias');")

    # ═════════════════════════════════════════════════════════════════════
    # 5. SEED — Project aliases
    # ═════════════════════════════════════════════════════════════════════
    seen_normalized = set()  # guard against accidental duplicates

    for proj_code, canonical, aliases in PROJECT_ALIASES:
        target_id = PROJECT_IDS[proj_code]
        for alias_raw in aliases:
            norm = _normalize(alias_raw)
            key = ("PROJECT", norm)
            if key in seen_normalized:
                continue
            seen_normalized.add(key)
            uid = _alias_uuid()
            raw_escaped = alias_raw.replace("'", "''")
            canon_escaped = canonical.replace("'", "''")
            op.execute(f"""
                INSERT INTO entity_alias (
                    id, company_id, entity_type, target_id,
                    alias_raw, alias_normalized, canonical_name,
                    created_by
                ) VALUES (
                    '{uid}', '{DEFAULT_COMPANY_ID}', 'PROJECT',
                    '{target_id}', '{raw_escaped}', '{norm}',
                    '{canon_escaped}', '{SYSTEM_USER_ID}'
                );
            """)

    # ═════════════════════════════════════════════════════════════════════
    # 6. SEED — Associate aliases
    # ═════════════════════════════════════════════════════════════════════
    for assoc_key, canonical, aliases in ASSOCIATE_ALIASES:
        target_id = ASSOCIATE_IDS[assoc_key]
        for alias_raw in aliases:
            norm = _normalize(alias_raw)
            key = ("ASSOCIATE", norm)
            if key in seen_normalized:
                continue
            seen_normalized.add(key)
            uid = _alias_uuid()
            raw_escaped = alias_raw.replace("'", "''")
            canon_escaped = canonical.replace("'", "''")
            op.execute(f"""
                INSERT INTO entity_alias (
                    id, company_id, entity_type, target_id,
                    alias_raw, alias_normalized, canonical_name,
                    created_by
                ) VALUES (
                    '{uid}', '{DEFAULT_COMPANY_ID}', 'ASSOCIATE',
                    '{target_id}', '{raw_escaped}', '{norm}',
                    '{canon_escaped}', '{SYSTEM_USER_ID}'
                );
            """)

    # ═════════════════════════════════════════════════════════════════════
    # 7. SEED — Company aliases
    # ═════════════════════════════════════════════════════════════════════
    for company_code, canonical, aliases in COMPANY_ALIASES:
        target_id = COMPANY_IDS[company_code]
        for alias_raw in aliases:
            norm = _normalize(alias_raw)
            key = ("COMPANY", norm)
            if key in seen_normalized:
                continue
            seen_normalized.add(key)
            uid = _alias_uuid()
            raw_escaped = alias_raw.replace("'", "''")
            canon_escaped = canonical.replace("'", "''")
            op.execute(f"""
                INSERT INTO entity_alias (
                    id, company_id, entity_type, target_id,
                    alias_raw, alias_normalized, canonical_name,
                    created_by
                ) VALUES (
                    '{uid}', '{DEFAULT_COMPANY_ID}', 'COMPANY',
                    '{target_id}', '{raw_escaped}', '{norm}',
                    '{canon_escaped}', '{SYSTEM_USER_ID}'
                );
            """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_entity_alias_updated_at ON entity_alias;"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_entity_alias_no_delete ON entity_alias;"
    )
    op.execute("DROP INDEX IF EXISTS ix_entity_alias_trgm;")
    op.drop_table("entity_alias")
    op.execute("DROP EXTENSION IF EXISTS unaccent;")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
