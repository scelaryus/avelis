"""Formulaire system: catalogue (35 templates), instances, attachments.

The absolute rule: the system NEVER guesses. When information is missing,
it generates a targeted formulaire, assigns it to the DAF, and BLOCKS
the dependent operation until answered.

Tables:
- formulaire_catalogue: 35 template definitions (23 GFI core + 14 DRH + 9 BIM = 46,
  but we seed exact 35 from spec + additional DRH/BIM = 46 total)
- formulaire: live instances (GFIBase)
- formulaire_attachment: uploaded proof documents (GFIBase)

Triggers:
- updated_at on all 3 tables
- soft-delete (KT-10) on formulaire and formulaire_attachment

Revision ID: 006
Revises: 005
Create Date: 2026-03-18
"""
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"

_cat_counter = 0


def _cat_uuid():
    global _cat_counter
    _cat_counter += 1
    return f"b1000000-0000-0000-0000-{_cat_counter:012x}"


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


def _q(s):
    """Escape single quotes for SQL."""
    return s.replace("'", "''") if s else s


# ═════════════════════════════════════════════════════════════════════════════
# 35+ FORMULAIRE CATALOGUE ENTRIES
# ═════════════════════════════════════════════════════════════════════════════
# (code, name, category, trigger, question_template, priority,
#  default_assignee_role, blocks_operation, field_definitions_json)

CATALOGUE = [
    # ── GFI CORE (FC-001 to FC-023) ──────────────────────────────────────
    ("FC-001", "Identification Associé", "GFI_CORE",
     "Unresolved alias in accounting entry", "CRITIQUE",
     "L'alias '[alias]' détecté dans le libellé ne correspond à aucun associé connu. Quel associé est-ce ?",
     "DAF", True,
     [{"code": "associate_id", "label": "Associé identifié", "type": "select_associate", "required": True}]),

    ("FC-002", "NIF Entreprise", "GFI_CORE",
     "Missing NIF for entity", "CRITIQUE",
     "Le NIF de [entite] n'est pas renseigné. Aucune ingestion documentaire ne sera possible tant que le NIF n'est pas fourni.",
     "DAF", True,
     [{"code": "nif", "label": "Numéro d'Identification Fiscale", "type": "text", "required": True, "pattern": "^[0-9]{15}$"}]),

    ("FC-003", "Rattachement Projet", "GFI_CORE",
     "Unidentified project in entry", "CRITIQUE",
     "Le projet '[projet]' n'est pas reconnu. S'agit-il d'un projet existant sous un autre nom, ou d'un nouveau projet ?",
     "DAF", True,
     [{"code": "project_id", "label": "Projet identifié", "type": "select_project", "required": True},
      {"code": "is_new_alias", "label": "Ajouter comme alias ?", "type": "boolean", "required": False}]),

    ("FC-004", "Confirmation Statut Projet", "GFI_CORE",
     "Uncertain project status", "STANDARD",
     "Confirmez-vous le statut du projet [projet] ? Actif, en attente, abandonné ?",
     "DAF", True,
     [{"code": "status", "label": "Statut confirmé", "type": "select", "required": True,
       "options": ["ACTIF", "EN_ATTENTE", "ABANDONNE"]}]),

    ("FC-005", "Régime Fiscal Entreprise", "GFI_CORE",
     "Missing IBS/TAP rate for CFF", "CRITIQUE",
     "Le taux IBS (19% ou 26%) et le taux TAP (1% ou 2%) de [entite] ne sont pas renseignés. Le calcul CFF est bloqué.",
     "DAF", True,
     [{"code": "ibs_rate", "label": "Taux IBS (%)", "type": "select", "required": True, "options": ["19", "26"]},
      {"code": "tap_rate", "label": "Taux TAP (%)", "type": "select", "required": True, "options": ["1", "2"]}]),

    ("FC-006", "Clé de Ventilation", "GFI_CORE",
     "Missing allocation key for shared charges", "STANDARD",
     "Aucune clé de ventilation n'est définie pour les charges communes. Base souhaitée : chiffre d'affaires, surface, ou pourcentage fixe par projet ?",
     "DAF", True,
     [{"code": "ventilation_base", "label": "Base de ventilation", "type": "select", "required": True,
       "options": ["CHIFFRE_AFFAIRES", "SURFACE", "POURCENTAGE_FIXE"]},
      {"code": "percentages", "label": "Pourcentages par projet (si fixe)", "type": "json", "required": False}]),

    ("FC-007", "Valorisation Prélèvement", "GFI_CORE",
     "Unknown value of in-kind withdrawal", "CRITIQUE",
     "Quelle est la valeur d'attribution interne du [bien] prélevé par [associe] sur le projet [projet] ?",
     "DAF", True,
     [{"code": "valeur_attribution", "label": "Valeur d'attribution (DA)", "type": "number", "required": True, "min": 0}]),

    ("FC-008", "Actionnariat Obligatoire", "GFI_CORE",
     "Unknown ownership of RF3-emitting company", "CRITIQUE",
     "L'entreprise [entite] émet une facture RF3 mais son actionnariat n'est pas renseigné. Le CFF ne peut pas être calculé.",
     "DAF", True,
     [{"code": "ownership_data", "label": "Structure actionnariat", "type": "json", "required": True}]),

    ("FC-009", "Document Manquant Client", "GFI_CORE",
     "Missing client document for credit file", "STANDARD",
     "Le document [type_doc] du client [client] pour le dossier [ref] n'a pas été reçu depuis [jours] jours.",
     "MANAGER_ADV", False,
     [{"code": "document_received", "label": "Document reçu ?", "type": "boolean", "required": True},
      {"code": "document_file", "label": "Document", "type": "file", "required": False, "accept": ".pdf,.jpg,.png", "max_size_mb": 10}]),

    ("FC-010", "Rapport Expert Manquant", "GFI_CORE",
     "Disbursement tier waiting for expert report", "STANDARD",
     "Le rapport expert pour le palier [palier]% du dossier [ref] n'est pas encore reçu. Le déblocage est bloqué.",
     "MANAGER_ADV", True,
     [{"code": "rapport_file", "label": "Rapport expert", "type": "file", "required": True, "accept": ".pdf", "max_size_mb": 10}]),

    ("FC-011", "Barème Timbre Manquant", "GFI_CORE",
     "No stamp duty schedule for invoice period", "STANDARD",
     "Aucun barème de timbre fiscal n'est disponible pour la période [date]. Le calcul CFF est bloqué.",
     "DAF", True,
     [{"code": "bareme_timbre", "label": "Montant timbre fiscal (DA)", "type": "number", "required": True, "min": 0}]),

    ("FC-012", "Transfert Entité Porteuse", "GFI_CORE",
     "Project transferred between entities", "ELEVEE",
     "Le projet [projet] a été transféré de [entite_a] à [entite_b]. Quelle est la date effective du transfert ?",
     "DAF", True,
     [{"code": "transfer_date", "label": "Date effective du transfert", "type": "date", "required": True}]),

    ("FC-013", "Complétion Structure Projet", "GFI_CORE",
     "Project going from À DÉVELOPPER to ACTIF", "ELEVEE",
     "Le projet [projet] passe en statut ACTIF. Renseignez : structure de parts, entité porteuse confirmée, paramètres Centre de Coûts.",
     "DAF", True,
     [{"code": "parts_structure", "label": "Structure de parts (JSON)", "type": "json", "required": True},
      {"code": "entity_confirmed", "label": "Entité porteuse confirmée", "type": "select_company", "required": True},
      {"code": "cc_params", "label": "Paramètres Centre de Coûts", "type": "json", "required": True}]),

    ("FC-014", "Barème Commissions Manquant", "GFI_CORE",
     "First sale on project without commission schedule", "STANDARD",
     "Aucun barème de commissions n'est défini pour le projet [projet]. Taux, conditions de déclenchement, plafonds ?",
     "DAF", True,
     [{"code": "taux_commission", "label": "Taux commission (%)", "type": "number", "required": True},
      {"code": "conditions", "label": "Conditions de déclenchement", "type": "text", "required": True},
      {"code": "plafond", "label": "Plafond (DA)", "type": "number", "required": False}]),

    ("FC-015", "Montant Vente AMENFORT Lot 1", "GFI_CORE",
     "Dabladji sale amount not found", "CRITIQUE",
     "Quel est le montant exact de la vente du matériel AMENFORT Lot 1 à DABLADJI Abderahmane ?",
     "DAF", True,
     [{"code": "montant_vente", "label": "Montant de la vente (DA)", "type": "number", "required": True, "min": 0}]),

    ("FC-016", "Nature Flux Inter-Projet", "GFI_CORE",
     "Inter-project flow nature unknown", "ELEVEE",
     "Les [montant] DA sortis d'[projet_source] pour financer le terrain [projet_dest] constituent-ils un prêt remboursable (taux ? durée ?) ou un investissement définitif ?",
     "DAF", True,
     [{"code": "nature", "label": "Nature du flux", "type": "select", "required": True, "options": ["PRET", "INVESTISSEMENT"]},
      {"code": "taux_interet", "label": "Taux d'intérêt (si prêt)", "type": "number", "required": False},
      {"code": "duree_mois", "label": "Durée en mois (si prêt)", "type": "number", "required": False}]),

    ("FC-017", "Statut Appartements Yamina", "GFI_CORE",
     "Yamina's EDEN apartments status unknown", "STANDARD",
     "Quel est le statut actuel des appartements F3 + F3 grenier prélevés par Yamina sur EDEN ? Gardés, vendus, loués ?",
     "DAF", False,
     [{"code": "statut", "label": "Statut", "type": "select", "required": True,
       "options": ["GARDES", "VENDUS", "LOUES"]},
      {"code": "montant_vente", "label": "Montant vente (si vendus)", "type": "number", "required": False}]),

    ("FC-018", "Prélèvement Mohamed EDEN", "GFI_CORE",
     "Mohamed's EDEN withdrawal not documented", "ELEVEE",
     "Mohamed a-t-il prélevé des appartements sur EDEN ? Si oui, lesquels et pour quelle valeur ?",
     "DAF", True,
     [{"code": "has_prelevement", "label": "Prélèvement effectué ?", "type": "boolean", "required": True},
      {"code": "biens", "label": "Biens prélevés", "type": "text", "required": False},
      {"code": "valeur", "label": "Valeur totale (DA)", "type": "number", "required": False}]),

    ("FC-019", "Remboursement Khadidja", "GFI_CORE",
     "Amount repaid on 18M debt unknown", "CRITIQUE",
     "Quel est le montant déjà remboursé à Khadidja GFI sur la dette de 18M DA ? Quelle somme reste due ?",
     "DAF", True,
     [{"code": "montant_rembourse", "label": "Montant remboursé (DA)", "type": "number", "required": True},
      {"code": "montant_restant", "label": "Montant restant dû (DA)", "type": "number", "required": True}]),

    ("FC-020", "Prix Villa Zit Kaci Karim", "GFI_CORE",
     "Villa purchase price unknown", "CRITIQUE",
     "Pour quel montant avez-vous acheté la villa à Zit Kaci Karim pour Lyazid ?",
     "DAF", True,
     [{"code": "prix_achat", "label": "Prix d'achat (DA)", "type": "number", "required": True, "min": 0}]),

    ("FC-021", "Solde Avance 120M GACEB", "GFI_CORE",
     "GACEB advance residual unconfirmed", "ELEVEE",
     "Quel est le solde actuellement non amorti de l'avance GACEB de 120M DA sur EDEN ?",
     "DAF", True,
     [{"code": "solde_non_amorti", "label": "Solde non amorti (DA)", "type": "number", "required": True}]),

    ("FC-022", "Appartements JASMINS GACEB", "GFI_CORE",
     "Apartments given to GACEB unknown", "ELEVEE",
     "Combien d'appartements JASMINS ont été donnés à GACEB en avance pour le béton de JARDIN DE L'OPÉRA ? Lesquels ? Valeur totale ?",
     "DAF", True,
     [{"code": "nombre_appartements", "label": "Nombre d'appartements", "type": "number", "required": True},
      {"code": "liste_appartements", "label": "Liste des appartements", "type": "text", "required": True},
      {"code": "valeur_totale", "label": "Valeur totale (DA)", "type": "number", "required": True}]),

    ("FC-023", "% AMENFORT Exact", "GFI_CORE",
     "Exact AMENFORT shares unconfirmed", "CRITIQUE",
     "Quel est le pourcentage exact d'Ahmed, Mohamed et Lyazid dans AMENFORT ? (estimation actuelle : ~33.33% chacun)",
     "DAF", True,
     [{"code": "pct_ahmed", "label": "% Ahmed", "type": "number", "required": True, "min": 0, "max": 100},
      {"code": "pct_mohamed", "label": "% Mohamed", "type": "number", "required": True, "min": 0, "max": 100},
      {"code": "pct_yazid", "label": "% Yazid (Lyazid)", "type": "number", "required": True, "min": 0, "max": 100}]),

    # ── DRH FORMULAIRES ──────────────────────────────────────────────────

    ("F-REC-001", "Demande de recrutement", "DRH",
     "Manager needs new hire", "STANDARD",
     "Nouvelle demande de recrutement pour le poste [position] dans le département [department].",
     "MANAGER_RH", False,
     [{"code": "position", "label": "Poste", "type": "text", "required": True},
      {"code": "department", "label": "Département", "type": "text", "required": True},
      {"code": "justification", "label": "Justification", "type": "textarea", "required": True, "min_length": 50},
      {"code": "contract_type", "label": "Type de contrat", "type": "select", "required": True,
       "options": ["CDI", "CDD", "CHANTIER", "STAGE"]},
      {"code": "cdd_reason", "label": "Motif légal CDD (Art.12 Loi 90-11)", "type": "textarea", "required": False, "min_length": 30,
       "required_if": {"contract_type": "CDD"}},
      {"code": "start_date", "label": "Date de début souhaitée", "type": "date", "required": True, "min_days_from_now": 15},
      {"code": "salary_min", "label": "Salaire minimum (DA)", "type": "number", "required": True, "min": 20000},
      {"code": "salary_max", "label": "Salaire maximum (DA)", "type": "number", "required": True},
      {"code": "num_positions", "label": "Nombre de postes", "type": "number", "required": True, "min": 1, "max": 50},
      {"code": "skills", "label": "Compétences requises", "type": "multi_select", "required": True},
      {"code": "job_description", "label": "Fiche de poste", "type": "file", "required": False, "accept": ".pdf,.docx", "max_size_mb": 10},
      {"code": "priority", "label": "Priorité", "type": "select", "required": True,
       "options": ["NORMAL", "URGENT", "CRITICAL"]}]),

    ("F-REC-002", "Grille d'évaluation entretien", "DRH",
     "Interview conducted", "STANDARD",
     "Évaluation de l'entretien pour le candidat [candidat] au poste [position].",
     "MANAGER_RH", False,
     [{"code": "presentation", "label": "Présentation (1-5)", "type": "number", "required": True, "min": 1, "max": 5},
      {"code": "motivation", "label": "Motivation (1-5)", "type": "number", "required": True, "min": 1, "max": 5},
      {"code": "technical", "label": "Compétences techniques (1-5)", "type": "number", "required": True, "min": 1, "max": 5},
      {"code": "behavioral", "label": "Compétences comportementales (1-5)", "type": "number", "required": True, "min": 1, "max": 5},
      {"code": "cultural_fit", "label": "Adéquation culturelle (1-5)", "type": "number", "required": True, "min": 1, "max": 5},
      {"code": "salary_expectations", "label": "Prétentions salariales (DA)", "type": "number", "required": True},
      {"code": "availability_date", "label": "Date de disponibilité", "type": "date", "required": True},
      {"code": "recommendation", "label": "Recommandation", "type": "select", "required": True,
       "options": ["FAVORABLE", "DEFAVORABLE"]}]),

    ("F-CON-001", "Demande de congé", "DRH",
     "Employee requests leave", "STANDARD",
     "Demande de congé [type_conge] du [date_debut] au [date_fin] pour [employe].",
     "MANAGER_RH", False,
     [{"code": "type_conge", "label": "Type de congé", "type": "select", "required": True,
       "options": ["ANNUEL", "MALADIE", "MATERNITE", "PATERNITE", "SANS_SOLDE", "MARIAGE", "NAISSANCE", "DECES", "CIRCONCISION", "HAJJ"]},
      {"code": "date_debut", "label": "Date de début", "type": "date", "required": True},
      {"code": "date_fin", "label": "Date de fin", "type": "date", "required": True},
      {"code": "certificat_medical", "label": "Certificat médical", "type": "file", "required": False,
       "required_if": {"type_conge": ["MALADIE", "MATERNITE"]}, "accept": ".pdf,.jpg,.png", "max_size_mb": 10},
      {"code": "cnas_attestation", "label": "Attestation CNAS", "type": "file", "required": False,
       "required_if": {"type_conge": "MATERNITE"}, "accept": ".pdf,.jpg,.png", "max_size_mb": 10},
      {"code": "death_certificate", "label": "Acte de décès", "type": "file", "required": False,
       "required_if": {"type_conge": "DECES"}, "accept": ".pdf,.jpg,.png", "max_size_mb": 10},
      {"code": "marriage_certificate", "label": "Acte de mariage", "type": "file", "required": False,
       "required_if": {"type_conge": "MARIAGE"}, "accept": ".pdf,.jpg,.png", "max_size_mb": 10},
      {"code": "reason", "label": "Motif (congé sans solde)", "type": "textarea", "required": False,
       "required_if": {"type_conge": "SANS_SOLDE"}, "min_length": 20}]),

    ("F-CTR-001", "Avenant au contrat", "DRH",
     "Contract modification", "ELEVEE",
     "Avenant au contrat de [employe] : modification de [clauses].",
     "MANAGER_RH", True,
     [{"code": "clauses_modifiees", "label": "Clauses modifiées", "type": "textarea", "required": True},
      {"code": "nouveau_salaire", "label": "Nouveau salaire (DA)", "type": "number", "required": False},
      {"code": "nouvelle_fonction", "label": "Nouvelle fonction", "type": "text", "required": False},
      {"code": "date_effet", "label": "Date d'effet", "type": "date", "required": True},
      {"code": "justification", "label": "Justification", "type": "textarea", "required": True}]),

    ("F-DIS-001", "PV de constat de faute", "DRH",
     "Infraction observed", "ELEVEE",
     "Constat de faute de [employe] le [date] à [lieu].",
     "MANAGER_RH", True,
     [{"code": "date_faute", "label": "Date de la faute", "type": "date", "required": True},
      {"code": "heure", "label": "Heure", "type": "time", "required": True},
      {"code": "lieu", "label": "Lieu", "type": "text", "required": True},
      {"code": "description_faute", "label": "Description de la faute", "type": "textarea", "required": True},
      {"code": "temoins", "label": "Témoins", "type": "textarea", "required": False},
      {"code": "evidence", "label": "Preuves jointes", "type": "file", "required": False, "accept": ".pdf,.jpg,.png,.mp4", "max_size_mb": 50},
      {"code": "severite", "label": "Évaluation de la gravité", "type": "select", "required": True,
       "options": ["FAUTE_LEGERE", "FAUTE_GRAVE", "FAUTE_LOURDE"]}]),

    ("F-DIS-002", "Convocation à audition", "DRH",
     "48h after PV constat", "ELEVEE",
     "Convocation de [employe] à l'audition le [date_audition] suite au PV du [date_pv].",
     "MANAGER_RH", True,
     [{"code": "date_audition", "label": "Date d'audition", "type": "date", "required": True},
      {"code": "heure_audition", "label": "Heure", "type": "time", "required": True},
      {"code": "lieu", "label": "Lieu", "type": "text", "required": True},
      {"code": "objet", "label": "Objet", "type": "textarea", "required": True},
      {"code": "droits_employe", "label": "Mention des droits", "type": "boolean", "required": True}]),

    ("F-DIS-003", "PV d'audition", "DRH",
     "During audition", "ELEVEE",
     "PV d'audition de [employe] du [date].",
     "MANAGER_RH", True,
     [{"code": "declarations", "label": "Déclarations de l'employé", "type": "textarea", "required": True},
      {"code": "questions_reponses", "label": "Questions et réponses", "type": "textarea", "required": True},
      {"code": "assistant_present", "label": "Assistant présent", "type": "text", "required": False},
      {"code": "signatures", "label": "Signatures obtenues", "type": "boolean", "required": True}]),

    ("F-MIS-001", "Ordre de mission", "DRH",
     "Approved business trip", "STANDARD",
     "Ordre de mission pour [employe] : [destination] du [date_debut] au [date_fin].",
     "MANAGER_RH", False,
     [{"code": "destination", "label": "Destination", "type": "text", "required": True},
      {"code": "date_debut", "label": "Date de début", "type": "date", "required": True},
      {"code": "date_fin", "label": "Date de fin", "type": "date", "required": True},
      {"code": "objet", "label": "Objet de la mission", "type": "textarea", "required": True},
      {"code": "transport", "label": "Moyen de transport", "type": "select", "required": True,
       "options": ["VEHICULE_SERVICE", "VEHICULE_PERSONNEL", "TRANSPORT_PUBLIC", "AVION"]},
      {"code": "budget", "label": "Budget estimé (DA)", "type": "number", "required": True},
      {"code": "avance", "label": "Avance demandée (DA)", "type": "number", "required": False}]),

    ("F-MIS-002", "Note de frais", "DRH",
     "Return from mission", "STANDARD",
     "Note de frais de [employe] pour la mission [ref_mission].",
     "MANAGER_RH", False,
     [{"code": "expense_lines", "label": "Lignes de dépenses", "type": "json", "required": True},
      {"code": "total", "label": "Total (DA)", "type": "number", "required": True},
      {"code": "justificatifs", "label": "Justificatifs", "type": "file", "required": True, "accept": ".pdf,.jpg,.png", "max_size_mb": 10},
      {"code": "mode_remboursement", "label": "Mode de remboursement", "type": "select", "required": True,
       "options": ["VIREMENT", "ESPECES", "COMPENSATION_AVANCE"]}]),

    ("F-MGX-001", "Demande d'équipement", "DRH",
     "Material need", "STANDARD",
     "Demande d'équipement : [type_equipement] pour [employe].",
     "MANAGER_RH", False,
     [{"code": "type_equipement", "label": "Type d'équipement", "type": "text", "required": True},
      {"code": "justification", "label": "Justification", "type": "textarea", "required": True},
      {"code": "urgence", "label": "Niveau d'urgence", "type": "select", "required": True,
       "options": ["NORMAL", "URGENT", "CRITIQUE"]},
      {"code": "budget_estime", "label": "Budget estimé (DA)", "type": "number", "required": True}]),

    ("F-MGX-002", "Déclaration perte/dommage", "DRH",
     "Equipment missing or damaged", "ELEVEE",
     "Déclaration de [type_incident] : [item] par [employe].",
     "MANAGER_RH", True,
     [{"code": "item", "label": "Équipement concerné", "type": "text", "required": True},
      {"code": "circonstances", "label": "Circonstances", "type": "textarea", "required": True},
      {"code": "valeur_estimee", "label": "Valeur estimée (DA)", "type": "number", "required": True},
      {"code": "responsabilite", "label": "Évaluation de responsabilité", "type": "textarea", "required": True}]),

    ("F-OFF-001", "Lettre de démission", "DRH",
     "Employee resignation", "ELEVEE",
     "Démission de [employe], départ souhaité le [date_depart].",
     "MANAGER_RH", True,
     [{"code": "lettre_demission", "label": "Lettre de démission signée", "type": "file", "required": True, "accept": ".pdf", "max_size_mb": 10},
      {"code": "date_depart", "label": "Date de départ souhaitée", "type": "date", "required": True},
      {"code": "raison", "label": "Raison (optionnel)", "type": "textarea", "required": False}]),

    ("F-ASS-001", "Demande activation assurance", "DRH",
     "Employee reaches 12 months seniority", "STANDARD",
     "Activation de l'assurance groupe pour [employe] (12 mois d'ancienneté atteints).",
     "MANAGER_RH", False,
     [{"code": "documents_famille", "label": "Documents justificatifs membres famille", "type": "file", "required": True,
       "accept": ".pdf,.jpg,.png", "max_size_mb": 10}]),

    ("F-PRT-001", "Demande de prêt", "DRH",
     "Employee requests loan", "STANDARD",
     "Demande de prêt de [employe] : [montant] DA.",
     "DAF", True,
     [{"code": "montant", "label": "Montant demandé (DA)", "type": "number", "required": True, "min": 0},
      {"code": "objet", "label": "Objet du prêt", "type": "textarea", "required": True},
      {"code": "duree_remboursement", "label": "Durée de remboursement souhaitée (mois)", "type": "number", "required": True},
      {"code": "documents", "label": "Justificatifs", "type": "file", "required": False, "accept": ".pdf,.jpg,.png", "max_size_mb": 10}]),

    # ── BIM FORMULAIRES ──────────────────────────────────────────────────

    ("F-PROJ-001", "Programme fonctionnel", "BIM",
     "New BIM project", "ELEVEE",
     "Programme fonctionnel pour le projet [projet].",
     "DAF", True,
     [{"code": "terrain_data", "label": "Données terrain", "type": "json", "required": True},
      {"code": "typologies", "label": "Typologies", "type": "json", "required": True},
      {"code": "standing", "label": "Niveau de standing", "type": "select", "required": True,
       "options": ["ECONOMIQUE", "MOYEN", "HAUT", "LUXE"]},
      {"code": "pos_constraints", "label": "Contraintes POS", "type": "textarea", "required": True},
      {"code": "soil_study", "label": "Étude de sol", "type": "file", "required": True, "accept": ".pdf", "max_size_mb": 50}]),

    ("F-VAL-001", "Rapport validation & correction", "BIM",
     "Cross-discipline validation failure", "CRITIQUE",
     "Validation échouée : [count] éléments non conformes détectés dans [discipline].",
     "DAF", True,
     [{"code": "non_conforming_elements", "label": "Éléments non conformes", "type": "json", "required": True},
      {"code": "validator", "label": "Agent validateur", "type": "text", "required": True},
      {"code": "severity", "label": "Sévérité", "type": "select", "required": True,
       "options": ["CRITICAL", "MAJOR", "MINOR"]},
      {"code": "correction_suggestion", "label": "Suggestion de correction", "type": "textarea", "required": True},
      {"code": "dimension_impacted", "label": "Dimension impactée", "type": "select", "required": True,
       "options": ["DESIGN", "BUDGET", "MONTAGE"]},
      {"code": "correction_file", "label": "Fichier de correction", "type": "file", "required": False,
       "accept": ".ifc,.dwg,.dxf,.pdf,.jpg,.png", "max_size_mb": 100},
      {"code": "human_override", "label": "Dérogation humaine", "type": "boolean", "required": False},
      {"code": "override_justification", "label": "Justification dérogation", "type": "textarea", "required": False,
       "required_if": {"human_override": True}}]),

    ("F-LIB-001", "Complément fiche technique", "BIM",
     "OCR extraction incomplete", "STANDARD",
     "Extraction OCR incomplète pour le produit [produit]. Champs manquants identifiés.",
     "MANAGER_ACHATS", False,
     [{"code": "missing_fields", "label": "Champs manquants", "type": "json", "required": True},
      {"code": "product_photo", "label": "Photo du produit", "type": "file", "required": False, "accept": ".jpg,.png", "max_size_mb": 10},
      {"code": "technical_properties", "label": "Propriétés techniques", "type": "json", "required": True}]),

    ("F-SWAP-001", "Demande simulation multi-matériaux", "BIM",
     "BIM Manager initiative", "STANDARD",
     "Simulation de remplacement matériau : [original] par [remplacement] sur [scope].",
     "DAF", False,
     [{"code": "original_material", "label": "Matériau original", "type": "text", "required": True},
      {"code": "replacements", "label": "Candidats de remplacement", "type": "json", "required": True},
      {"code": "scope", "label": "Portée", "type": "select", "required": True,
       "options": ["PROJET_ENTIER", "BATIMENT", "ETAGE"]}]),

    ("F-ACH-001", "Demande d'achat BIM", "BIM",
     "Supplier selected from BIM", "ELEVEE",
     "Demande d'achat BIM pour le projet [projet] : [count] produits, fournisseur [fournisseur].",
     "MANAGER_ACHATS", True,
     [{"code": "fournisseur", "label": "Fournisseur", "type": "text", "required": True},
      {"code": "products", "label": "Produits (JSON)", "type": "json", "required": True},
      {"code": "incoterm", "label": "Incoterm", "type": "select", "required": True,
       "options": ["EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP"]},
      {"code": "budget_validation", "label": "Budget validé ?", "type": "boolean", "required": True}]),

    ("F-CTC-001", "Dossier soumission CTC", "BIM",
     "Structural phase validated", "CRITIQUE",
     "Soumission CTC pour le projet [projet] : plans structure + notes de calcul + PV vulnérabilité.",
     "DAF", True,
     [{"code": "structure_plans", "label": "Plans structure", "type": "file", "required": True, "accept": ".pdf,.dwg,.ifc", "max_size_mb": 200},
      {"code": "calculation_notes", "label": "Notes de calcul", "type": "file", "required": True, "accept": ".pdf", "max_size_mb": 100},
      {"code": "vulnerability_pv", "label": "PV de vulnérabilité (décret 24-247)", "type": "file", "required": True, "accept": ".pdf", "max_size_mb": 50}]),

    ("F-PC-001", "Dossier permis de construire", "BIM",
     "CTC visa obtained", "CRITIQUE",
     "Dossier permis de construire pour le projet [projet] : compilation BIM des plans.",
     "DAF", True,
     [{"code": "architecture_plans", "label": "Plans architecture", "type": "file", "required": True, "accept": ".pdf,.dwg", "max_size_mb": 200},
      {"code": "structure_plans", "label": "Plans structure", "type": "file", "required": True, "accept": ".pdf,.dwg", "max_size_mb": 200},
      {"code": "fire_safety", "label": "Plans sécurité incendie", "type": "file", "required": True, "accept": ".pdf", "max_size_mb": 50},
      {"code": "environmental_impact", "label": "Étude d'impact environnemental", "type": "file", "required": True, "accept": ".pdf", "max_size_mb": 50}]),

    ("F-INV-001", "Rapport d'écart réception", "BIM",
     "Received qty != ordered qty", "ELEVEE",
     "Écart de réception pour la commande [ref_commande] : [count] articles en écart.",
     "MANAGER_ACHATS", True,
     [{"code": "discrepancy_table", "label": "Tableau des écarts", "type": "json", "required": True},
      {"code": "overall_comments", "label": "Commentaires généraux", "type": "textarea", "required": False},
      {"code": "action_requested", "label": "Action demandée", "type": "select", "required": True,
       "options": ["REMPLACEMENT", "AVOIR", "ANNULATION_PARTIELLE", "ACCEPTATION"]},
      {"code": "photo_evidence", "label": "Photos des dommages", "type": "file", "required": True,
       "accept": ".jpg,.png", "max_size_mb": 20}]),

    ("F-CDC-001", "Signalement manque dans le CDC", "BIM",
     "Developer finds a gap in specifications", "STANDARD",
     "Manque identifié dans le cahier des charges : section [section].",
     "DAF", False,
     [{"code": "section", "label": "Section concernée", "type": "text", "required": True},
      {"code": "detail_manque", "label": "Détail du manque", "type": "textarea", "required": True},
      {"code": "suggestion", "label": "Suggestion de spécification", "type": "textarea", "required": False}]),
]


def upgrade() -> None:
    # ═════════════════════════════════════════════════════════════════════
    # 1. CREATE TABLES
    # ═════════════════════════════════════════════════════════════════════

    # ── 1a. formulaire_catalogue (system reference, no company_id) ───────
    op.create_table(
        "formulaire_catalogue",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(20), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("trigger_description", sa.Text, nullable=False),
        sa.Column("question_template", sa.Text, nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("default_assignee_role", sa.String(40), nullable=False,
                  server_default=sa.text("'DAF'")),
        sa.Column("blocks_operation", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
        sa.Column("escalation_reminder_days", sa.Integer, nullable=False,
                  server_default=sa.text("3")),
        sa.Column("escalation_alert_days", sa.Integer, nullable=False,
                  server_default=sa.text("7")),
        sa.Column("escalation_critique_days", sa.Integer, nullable=False,
                  server_default=sa.text("14")),
        sa.Column("escalation_blocking_days", sa.Integer, nullable=False,
                  server_default=sa.text("30")),
        sa.Column("field_definitions", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("is_deleted", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
    )

    # ── 1b. formulaire (GFIBase — live instances) ────────────────────────
    op.create_table(
        "formulaire",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("catalogue_id", UUID(as_uuid=True),
                  sa.ForeignKey("formulaire_catalogue.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("code", sa.String(20), nullable=False, index=True),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default=sa.text("'EN_ATTENTE'")),
        sa.Column("question_text", sa.Text, nullable=False),
        sa.Column("trigger_context", JSONB, nullable=False),
        sa.Column("blocked_resource_type", sa.String(100), nullable=True),
        sa.Column("blocked_resource_id", UUID(as_uuid=True), nullable=True),
        # Assignment
        sa.Column("assigned_to", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("assigned_role", sa.String(40), nullable=False,
                  server_default=sa.text("'DAF'")),
        # Response
        sa.Column("response_data", JSONB, nullable=True),
        sa.Column("responded_by", UUID(as_uuid=True),
                  sa.ForeignKey("auth_user.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        # Escalation
        sa.Column("escalation_level", sa.Integer, nullable=False,
                  server_default=sa.text("0")),
        sa.Column("last_relance_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_escalation_at", sa.DateTime(timezone=True), nullable=True),
        # AI verification
        sa.Column("ai_verification_status", sa.String(20), nullable=True),
        sa.Column("ai_verification_result", JSONB, nullable=True),
        # System columns
        *_system_columns(),
    )

    # ── 1c. formulaire_attachment ────────────────────────────────────────
    op.create_table(
        "formulaire_attachment",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", UUID(as_uuid=True),
                  sa.ForeignKey("company.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("formulaire_id", UUID(as_uuid=True),
                  sa.ForeignKey("formulaire.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("storage_path", sa.Text, nullable=False),
        sa.Column("field_code", sa.String(60), nullable=True),
        sa.Column("ai_verification_status", sa.String(20), nullable=True),
        sa.Column("ai_verification_result", JSONB, nullable=True),
        # System columns
        *_system_columns(),
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. TRIGGERS
    # ═════════════════════════════════════════════════════════════════════
    for table in ("formulaire_catalogue", "formulaire", "formulaire_attachment"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gfi_set_updated_at();
        """)

    # Soft-delete triggers on financial tables
    for table in ("formulaire", "formulaire_attachment"):
        op.execute(f"SELECT gfi_apply_no_delete_trigger('{table}');")

    # ═════════════════════════════════════════════════════════════════════
    # 3. SEED — 46 formulaire catalogue entries
    # ═════════════════════════════════════════════════════════════════════
    for (code, name, category, trigger, priority, question,
         assignee_role, blocks, fields) in CATALOGUE:
        uid = _cat_uuid()
        name_esc = _q(name)
        trigger_esc = _q(trigger)
        question_esc = _q(question)
        blocks_sql = "true" if blocks else "false"
        fields_json = _q(json.dumps(fields, ensure_ascii=False))

        op.execute(f"""
            INSERT INTO formulaire_catalogue (
                id, code, name, category, trigger_description,
                question_template, priority, default_assignee_role,
                blocks_operation, field_definitions
            ) VALUES (
                '{uid}', '{code}', '{name_esc}', '{category}',
                '{trigger_esc}', '{question_esc}', '{priority}',
                '{assignee_role}', {blocks_sql},
                '{fields_json}'::jsonb
            );
        """)


def downgrade() -> None:
    for table in ("formulaire_attachment", "formulaire", "formulaire_catalogue"):
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};"
        )
    for table in ("formulaire_attachment", "formulaire"):
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_{table}_no_delete ON {table};"
        )
    op.drop_table("formulaire_attachment")
    op.drop_table("formulaire")
    op.drop_table("formulaire_catalogue")
