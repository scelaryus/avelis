"""Document Intelligence System — AI Classification Agent.
Full CDC prompt from CDC-GFI-GED-001 §5.1.
Classifies documents using Claude API via OpenRouter."""
import json
import hashlib
from openai import OpenAI

OPENROUTER_KEY = "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"
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY)

# Full system prompt from CDC §5.1
SYSTEM_PROMPT = """Tu es un agent de classification documentaire pour Groupe GFI, societe algerienne de promotion immobiliere et de fabrication industrielle basee a Bab Ezzouar, Alger, Algerie.

Contexte du groupe:
Le groupe comprend 7 entites legales:
- ETS-DK (ETS GFI Fondation): entite historique
- SARL-DP (SARL GFI Promotions): promotion immobiliere
- SARL-DBPI: developpement et promotion
- SARL-OC: operationnel chantiers
- SARL-EP: exploitation et promotion
- SARL-SEN: services
- EURL-BIM: BIM et ingenierie

Projets actifs: AUREA (198 logements, Cheraga), IRENE (50000m2, Tidjelabine), JASMIN (alias Sahel), EDEN (alias FOES), OPERA (alias Ouled Fayet), BAYTI (alias NOVUS), ALLO_MAISON (industriel).

Alias de projets: FOES=EDEN, Sahel=JASMIN, Ouled Fayet=OPERA, Ami Djamel=IRENE, NOVUS=BAYTI, 02H=LYS, Cheraga=AUREA.

Ta mission: classifier le document et retourner UNIQUEMENT un JSON valide.

Champs a retourner (tous obligatoires, null si impossible):

doc_type: FACTURE_FOURNISSEUR, FACTURE_CLIENT, BON_COMMANDE, DEVIS, CONTRAT, AVENANT_CONTRAT, SITUATION_TRAVAUX, PV_RECEPTION, PV_CHANTIER, PLAN_TECHNIQUE, PHOTO_CHANTIER, FICHE_PAIE, RAPPORT_INTERNE, COURRIER, PERMIS_AUTORISATION, ACTE_NOTARIE, RELEVE_BANCAIRE, ACCORD_PRET, AUTRE

entite: ETS-DK, SARL-DP, SARL-DBPI, SARL-OC, SARL-EP, SARL-SEN, EURL-BIM, GROUPE, null

projet: AUREA, IRENE, JASMIN, EDEN, OPERA, BAYTI, ALLO_MAISON, LYS, MAGNOLIA, GROUPE, null

annee: entier 4 chiffres ou null
mois: 1-12 ou null
reference_doc: reference interne exacte ou null
tiers: nom complet de la contrepartie ou null
montant_da: float ou null
montant_devise: float ou null
devise: code ISO 3 lettres ou null
tags: max 5 mots-cles en minuscules avec underscores
resume: 1-2 phrases factuelles et precises
confidence: objet avec scores 0.0-1.0 pour doc_type, entite, projet, annee, reference_doc, tiers, montant_da

Regles:
1. null honnete > valeur fausse confiante
2. Scores de confiance = certitude reelle
3. Mapper les alias vers le nom canonique
4. Resume informatif (pas "ce document est une facture" mais "facture de beton pour AUREA, 4.8M DA")
5. Documents GACEB lies a l'avance 120M AMENFORT: tagger gaceb_avance_amenfort
"""


def classify_document(text: str, metadata: dict = None) -> dict:
    """Classify a document using Claude AI. Returns full classification with confidence scores."""
    if not metadata:
        metadata = {}

    user_msg = f"""Metadonnees du fichier:
Nom: {metadata.get('filename', 'inconnu')}
Extension: {metadata.get('extension', '')}
Type MIME: {metadata.get('mime_type', '')}
Taille: {metadata.get('size_bytes', 0)} octets
Dossier parent: {metadata.get('parent_folder', '')}
Date EXIF: {metadata.get('exif_date', '')}
Proprietes Office: {json.dumps(metadata.get('office_props', {}), ensure_ascii=False)}

Texte extrait ({len(text)} caracteres):
{text[:4000]}
{"... [texte tronque]" if len(text) > 4000 else ""}
"""

    try:
        resp = client.chat.completions.create(
            model="anthropic/claude-sonnet-4",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=1500,
            temperature=0.2,
        )
        content = resp.choices[0].message.content.strip()
        # Parse JSON
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content.strip())
        # Ensure confidence object exists
        result.setdefault("confidence", {})
        for field in ["doc_type", "entite", "projet", "annee", "reference_doc", "tiers", "montant_da"]:
            result["confidence"].setdefault(field, 0.5)
        return result
    except Exception as e:
        return {
            "doc_type": None, "entite": None, "projet": None, "annee": None,
            "mois": None, "reference_doc": None, "tiers": None,
            "montant_da": None, "montant_devise": None, "devise": None,
            "tags": [], "resume": f"Erreur de classification: {str(e)}",
            "confidence": {f: 0.0 for f in ["doc_type", "entite", "projet", "annee", "reference_doc", "tiers", "montant_da"]},
        }


def compute_archival_decision(confidence: dict, threshold: float = 0.85, daf_threshold: float = 0.65) -> dict:
    """Determine archival decision based on confidence scores. CDC §6."""
    critical_fields = ["doc_type", "entite", "projet", "annee"]
    secondary_fields = ["reference_doc", "tiers", "montant_da"]

    critical_scores = {f: confidence.get(f, 0) for f in critical_fields}
    secondary_scores = {f: confidence.get(f, 0) for f in secondary_fields}

    all_critical_above = all(s >= threshold for s in critical_scores.values())
    any_critical_below_daf = any(s < daf_threshold for f, s in critical_scores.items() if f in ("doc_type", "entite"))
    low_critical = {f: s for f, s in critical_scores.items() if s < threshold}
    low_secondary = {f: s for f, s in secondary_scores.items() if s < threshold}

    if all_critical_above:
        return {
            "decision": "AUTO_ARCHIVE",
            "message": "Tous les champs critiques au-dessus du seuil. Archivage automatique.",
            "low_fields": low_secondary,
        }
    elif any_critical_below_daf:
        return {
            "decision": "DAF_REVIEW",
            "message": "Champs critiques tres incertains. Revision DAF requise.",
            "low_fields": {**low_critical, **low_secondary},
        }
    else:
        return {
            "decision": "CONFIRM_FORM",
            "message": "Certains champs necessitent confirmation.",
            "low_fields": {**low_critical, **low_secondary},
        }


def generate_canonical_path(doc: dict) -> str:
    """Generate canonical path per CDC §8.1."""
    entite = doc.get("entite") or "GROUPE"
    doc_type = doc.get("doc_type") or "AUTRE"
    projet = doc.get("projet") or "GROUPE"
    annee = str(doc.get("annee") or "0000")
    mois = f"{doc.get('mois') or 0:02d}"
    ref = doc.get("reference_doc") or doc.get("id", "unknown")[:8]
    ext = doc.get("extension") or "pdf"
    # Sanitize ref for path
    ref = ref.replace("/", "_").replace("\\", "_").replace(" ", "_")
    return f"/GD/{entite}/{doc_type}/{projet}/{annee}/{mois}/{ref}.{ext}"
