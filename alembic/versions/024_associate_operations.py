"""Associate operations: withdrawals, inter-project flows, founding capital.

Tables:
- associate_withdrawal: CC9 apartment withdrawals (100% to specific associate)
- inter_project_flow: CC7 mirror entries + FC-016 for nature
- founding_capital: 4 ODs that started EDEN

Seeds:
- Ahmed F3+F2 (25M), Lyazid F3+F4 (25M), Yamina F3+F3g (25M) from EDEN
- Khadidja F4 (18M) → Ahmed personal debt
- EDEN→JASMINS 35M inter-project flow
- 4 founding capital ODs (Ahmed/Mohamed/Lyazid from AMENFORT, Yamina from EURL ABC)

Revision ID: 024
Revises: 023
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"
ETS_DK_ID = "10000000-0000-0000-0000-000000000001"
EDEN_ID = "30000000-0000-0000-0000-000000000001"
JASMIN_ID = "30000000-0000-0000-0000-000000000002"
AHMED_ID = "20000000-0000-0000-0000-000000000001"
MOHAMED_ID = "20000000-0000-0000-0000-000000000002"
YAZID_ID = "20000000-0000-0000-0000-000000000003"
YAMINA_ID = "20000000-0000-0000-0000-000000000004"

_wd_counter = 0


def _wd_uuid():
    global _wd_counter
    _wd_counter += 1
    return f"f5000000-0000-0000-0000-{_wd_counter:012x}"


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


def upgrade() -> None:
    # ═════════════════════════════════════════════════════════════════════
    # 1. associate_withdrawal
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "associate_withdrawal",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("associate_id", UUID(as_uuid=True),
                  sa.ForeignKey("associate.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("lot_references", JSONB, nullable=True),
        sa.Column("valeur_attribution", sa.Numeric(15, 2), nullable=False),
        sa.Column("withdrawal_date", sa.Date, nullable=True),
        sa.Column("disposition", sa.String(20), nullable=True),
        sa.Column("ceded_to", sa.String(255), nullable=True),
        sa.Column("sale_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("buyer_name", sa.String(255), nullable=True),
        sa.Column("net_benefit", sa.Numeric(15, 2), nullable=True),
        sa.Column("cc_entry_id", UUID(as_uuid=True), nullable=True),
        sa.Column("cca_movement_id", UUID(as_uuid=True), nullable=True),
        sa.Column("formulaire_ref", sa.String(20), nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. inter_project_flow
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "inter_project_flow",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("source_project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("dest_project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("montant", sa.Numeric(15, 2), nullable=False),
        sa.Column("flow_date", sa.Date, nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("nature", sa.String(20), nullable=False,
                  server_default=sa.text("'INDETERMINE'")),
        sa.Column("taux_interet", sa.Numeric(5, 2), nullable=True),
        sa.Column("duree_mois", sa.Integer, nullable=True),
        sa.Column("formulaire_ref", sa.String(20), nullable=True),
        sa.Column("cc_debit_entry_id", UUID(as_uuid=True), nullable=True),
        sa.Column("cc_credit_entry_id", UUID(as_uuid=True), nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 3. founding_capital
    # ═════════════════════════════════════════════════════════════════════
    op.create_table(
        "founding_capital",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("project.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("associate_id", UUID(as_uuid=True),
                  sa.ForeignKey("associate.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("od_reference", sa.String(20), nullable=False),
        sa.Column("montant", sa.Numeric(15, 2), nullable=True),
        sa.Column("source_description", sa.Text, nullable=False),
        sa.Column("capital_date", sa.Date, nullable=True),
        sa.Column("source_entity", sa.String(100), nullable=False),
        sa.Column("is_amenfort_linked", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("cc_entry_id", UUID(as_uuid=True), nullable=True),
        sa.Column("cca_movement_id", UUID(as_uuid=True), nullable=True),
        sa.Column("formulaire_ref", sa.String(20), nullable=True),
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 4. TRIGGERS
    # ═════════════════════════════════════════════════════════════════════
    for table in ("associate_withdrawal", "inter_project_flow", "founding_capital"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")

    # ═════════════════════════════════════════════════════════════════════
    # 5. SEED — Known withdrawals from EDEN
    # ═════════════════════════════════════════════════════════════════════
    def _q(s):
        return s.replace("'", "''")

    withdrawals = [
        (AHMED_ID, "F3 (15M) + F2 (10M) preleves sur EDEN",
         '["F3-EDEN", "F2-EDEN"]', 25000000, "VENDU",
         "Bouadjina", 33000000, "Bouadjina", 6000000, None),
        (YAZID_ID, "F3 + F4 preleves sur EDEN, cedes a Ahmed",
         '["F3-EDEN", "F4-EDEN"]', 25000000, "CEDE",
         "Ahmed Admin", None, None, None, None),
        (YAMINA_ID, "F3 + F3 grenier preleves sur EDEN — statut inconnu",
         '["F3-EDEN", "F3G-EDEN"]', 25000000, "INCONNU",
         None, None, None, None, "FC-017"),
    ]

    for (assoc_id, desc, lots, valeur, disp,
         ceded_to, sale_price, buyer, net_ben, fc_ref) in withdrawals:
        uid = _wd_uuid()
        desc_esc = _q(desc)
        ceded_sql = f"'{_q(ceded_to)}'" if ceded_to else "NULL"
        sp_sql = str(sale_price) if sale_price else "NULL"
        buyer_sql = f"'{_q(buyer)}'" if buyer else "NULL"
        nb_sql = str(net_ben) if net_ben else "NULL"
        fc_sql = f"'{fc_ref}'" if fc_ref else "NULL"
        disp_sql = f"'{disp}'" if disp else "NULL"

        op.execute(f"""
            INSERT INTO associate_withdrawal (
                id, company_id, project_id, associate_id,
                description, lot_references, valeur_attribution,
                disposition, ceded_to, sale_price, buyer_name,
                net_benefit, formulaire_ref, created_by
            ) VALUES (
                '{uid}', '{ETS_DK_ID}', '{EDEN_ID}', '{assoc_id}',
                '{desc_esc}', '{lots}'::jsonb, {valeur},
                {disp_sql}, {ceded_sql}, {sp_sql}, {buyer_sql},
                {nb_sql}, {fc_sql}, '{SYSTEM_USER_ID}'
            );
        """)

    # Khadidja F4 (Ahmed's personal debt)
    uid = _wd_uuid()
    op.execute(f"""
        INSERT INTO associate_withdrawal (
            id, company_id, project_id, associate_id,
            description, lot_references, valeur_attribution,
            disposition, buyer_name, sale_price, created_by
        ) VALUES (
            '{uid}', '{ETS_DK_ID}', '{EDEN_ID}', '{AHMED_ID}',
            'F4 attribue a Khadidja GFI — vendu a Benmoussa — dette personnelle Ahmed 18M',
            '["F4-EDEN-KHADIDJA"]'::jsonb, 18000000,
            'VENDU', 'Benmoussa', 18000000, '{SYSTEM_USER_ID}'
        );
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 6. SEED — EDEN→JASMINS 35M inter-project flow
    # ═════════════════════════════════════════════════════════════════════
    uid = _wd_uuid()
    op.execute(f"""
        INSERT INTO inter_project_flow (
            id, company_id, source_project_id, dest_project_id,
            montant, description, nature, formulaire_ref, created_by
        ) VALUES (
            '{uid}', '{ETS_DK_ID}', '{EDEN_ID}', '{JASMIN_ID}',
            35000000,
            '35M de la tresorerie EDEN pour financer terrain JASMINS (~50M total, 15M depuis AMENFORT)',
            'INDETERMINE', 'FC-016', '{SYSTEM_USER_ID}'
        );
    """)

    # ═════════════════════════════════════════════════════════════════════
    # 7. SEED — 4 founding capital ODs
    # ═════════════════════════════════════════════════════════════════════
    founders = [
        ("OD-001", AHMED_ID, "AMENFORT", True,
         "Part Ahmed de la vente AMENFORT Lot 1 a Dabladji — montant exact via FC-015",
         "FC-015"),
        ("OD-002", MOHAMED_ID, "AMENFORT", True,
         "Part Mohamed de la vente AMENFORT Lot 1 a Dabladji", "FC-015"),
        ("OD-003", YAZID_ID, "AMENFORT", True,
         "Part Lyazid de la vente AMENFORT Lot 1 a Dabladji", "FC-015"),
        ("OD-004", YAMINA_ID, "EURL ABC S.I.", False,
         "Apport personnel Yamina depuis EURL ABC S.I. — independant AMENFORT. Cause racine des regles Y1-Y5.",
         None),
    ]

    for od_ref, assoc_id, source, is_amf, desc, fc_ref in founders:
        uid = _wd_uuid()
        desc_esc = desc.replace("'", "''")
        is_amf_sql = "true" if is_amf else "false"
        fc_sql = f"'{fc_ref}'" if fc_ref else "NULL"
        op.execute(f"""
            INSERT INTO founding_capital (
                id, company_id, project_id, associate_id,
                od_reference, source_entity, source_description,
                is_amenfort_linked, formulaire_ref, created_by
            ) VALUES (
                '{uid}', '{ETS_DK_ID}', '{EDEN_ID}', '{assoc_id}',
                '{od_ref}', '{source}', '{desc_esc}',
                {is_amf_sql}, {fc_sql}, '{SYSTEM_USER_ID}'
            );
        """)


def downgrade() -> None:
    for table in ("founding_capital", "inter_project_flow", "associate_withdrawal"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};")
    op.drop_table("founding_capital")
    op.drop_table("inter_project_flow")
    op.drop_table("associate_withdrawal")
