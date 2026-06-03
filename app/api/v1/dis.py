"""Router — Document Intelligence System (DIS).
6-step pipeline: ingest, extract, classify, score, confirm, archive.
CDC-GFI-GED-001 compliant.
AI vision extraction for images/scans. Google Drive link fetch."""
import base64
import hashlib
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.api.v1.deps import get_current_user, CurrentUser, get_db
from app.api.v1.schemas import ApiResponse, Meta
from app.models.core import DocumentRegistry, Company, Project
from app.agents.document_classifier import classify_document, compute_archival_decision, generate_canonical_path

router = APIRouter(prefix="/dis", tags=["Document Intelligence"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

IMAGE_EXTS = {"jpg", "jpeg", "png", "tiff", "webp", "bmp"}
MIME_MAP = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "tiff": "image/tiff", "webp": "image/webp", "bmp": "image/bmp"}


def _extract_with_vision(content: bytes, ext: str, filename: str) -> str:
    """Use Claude vision to OCR/extract all text from an image or scanned document."""
    try:
        from app.agents.llm import get_llm
        llm = get_llm(temperature=0.0, max_tokens=4000)

        mime = MIME_MAP.get(ext, "image/jpeg")
        b64 = base64.b64encode(content).decode("utf-8")

        response = llm.invoke([{
            "role": "user",
            "content": [
                {"type": "text", "text": (
                    "Extrais TOUT le texte visible dans cette image de document. "
                    "C'est un document professionnel (facture, contrat, PV, courrier, plan, etc.) "
                    "d'une entreprise immobiliere algerienne. "
                    "Retourne le texte brut tel qu'il apparait, en preservant la structure "
                    "(en-tetes, montants, dates, noms, references, numeros). "
                    "Si c'est un tableau, reproduis les colonnes. "
                    "Ne resume PAS — extrais TOUT le texte mot pour mot. "
                    "Si l'image est floue ou illisible, extrais ce que tu peux et indique [illisible] pour les parties manquantes."
                )},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }])
        return response.content.strip()
    except Exception as e:
        return f"[Vision extraction error: {str(e)[:200]}]"


def _extract_pdf_with_vision(file_path: str) -> str:
    """For scanned PDFs: convert first pages to images, then use vision."""
    try:
        # Try pdf2image if available
        try:
            from pdf2image import convert_from_path
            images = convert_from_path(file_path, first_page=1, last_page=3, dpi=200)
        except ImportError:
            # Fallback: use Pillow to read if it's a single-page image-PDF
            # This won't work for most PDFs, so we try PyMuPDF
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(file_path)
                texts = []
                for page_num in range(min(3, len(doc))):
                    page = doc[page_num]
                    pix = page.get_pixmap(dpi=200)
                    img_bytes = pix.tobytes("jpeg")
                    text = _extract_with_vision(img_bytes, "jpeg", f"page_{page_num+1}")
                    texts.append(f"--- Page {page_num+1} ---\n{text}")
                doc.close()
                return "\n\n".join(texts)
            except ImportError:
                # Last resort: send the raw PDF bytes to vision (Claude can handle PDFs)
                with open(file_path, "rb") as f:
                    pdf_bytes = f.read()
                return _extract_with_vision(pdf_bytes, "pdf", file_path)

        # pdf2image worked — process each page
        import io
        texts = []
        for i, img in enumerate(images):
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            text = _extract_with_vision(buf.getvalue(), "jpeg", f"page_{i+1}")
            texts.append(f"--- Page {i+1} ---\n{text}")
        return "\n\n".join(texts)
    except Exception as e:
        return f"[PDF vision extraction error: {str(e)[:200]}]"

CONFIDENCE_THRESHOLD = 0.85
DAF_THRESHOLD = 0.65


# ═══ STEP 1: INGEST ═══

@router.post("/ingest")
async def ingest_document(
    file: UploadFile = File(...),
    context_hint: str = Form(default=""),
    priority: str = Form(default="NORMAL"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Ingest a single file into the DIS pipeline. CDC §3."""
    content = await file.read()
    size = len(content)

    # DIS_006: max 100MB
    if size > 100 * 1024 * 1024:
        raise HTTPException(400, f"DIS_006: Fichier trop volumineux ({size / 1024 / 1024:.1f} Mo > 100 Mo max)")

    # Compute SHA-256
    sha256 = hashlib.sha256(content).hexdigest()

    # DIS_002: Check duplicate
    existing = db.query(DocumentRegistry).filter(DocumentRegistry.sha256_hash == sha256).first()
    if existing:
        raise HTTPException(409, {
            "code": "DIS_002",
            "message": f"Doublon detecte. Ce fichier est deja archive sous: {existing.canonical_path}",
            "existing_id": str(existing.id),
            "existing_path": existing.canonical_path,
            "archived_at": str(existing.archived_at) if existing.archived_at else None,
        })

    # Save file locally
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "bin"
    file_id = str(uuid.uuid4())
    local_path = os.path.join(UPLOAD_DIR, f"{file_id}.{ext}")
    with open(local_path, "wb") as f:
        f.write(content)

    # Create registry entry
    doc = DocumentRegistry(
        company_id=db.query(Company).first().id,
        file_name_original=file.filename,
        sha256_hash=sha256,
        size_bytes=size,
        mime_type=file.content_type or "application/octet-stream",
        storage_url=local_path,
        status="PENDING",
        ingested_by=user.email,
        priority=priority,
        context_hint=context_hint,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # ═══ STEP 2: EXTRACT TEXT ═══
    doc.status = "EXTRACTING"
    db.commit()

    extracted_text = ""
    try:
        if ext == "pdf":
            # Try text extraction first (fast, works for digital PDFs)
            try:
                import PyPDF2
                with open(local_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception:
                extracted_text = ""
            # If text extraction returned little content, it's likely a scanned PDF → use vision
            if len(extracted_text.strip()) < 50:
                vision_text = _extract_pdf_with_vision(local_path)
                if len(vision_text.strip()) > len(extracted_text.strip()):
                    extracted_text = vision_text
        elif ext in ("txt", "csv"):
            extracted_text = content.decode("utf-8", errors="replace")
        elif ext in ("docx",):
            # Try python-docx if available
            try:
                import docx
                doc_obj = docx.Document(local_path)
                extracted_text = "\n".join(p.text for p in doc_obj.paragraphs if p.text.strip())
            except ImportError:
                extracted_text = f"[Document Word: {file.filename} — installez python-docx pour extraction]"
        elif ext in IMAGE_EXTS:
            # Images: use Claude vision to OCR
            extracted_text = _extract_with_vision(content, ext, file.filename)
        else:
            extracted_text = f"[Fichier {ext}: {file.filename}]"
    except Exception as e:
        extracted_text = f"[Erreur extraction: {str(e)}]"

    # If vision/OCR still returned very little, try vision on any file as last resort
    if len(extracted_text.strip()) < 10 and ext not in ("txt", "csv"):
        # DIS_001: extraction failed
        doc.status = "QUARANTINE"
        doc.error_log = "DIS_001: Extraction echouee - contenu insuffisant"
        db.commit()
        return ApiResponse(data={
            "id": str(doc.id), "status": "QUARANTINE",
            "error": "DIS_001", "message": "Fichier illisible ou contenu insuffisant",
        })

    doc.extracted_text_full = extracted_text
    doc.raw_text_excerpt = extracted_text[:2000]

    # ═══ STEP 3: CLASSIFY WITH AI ═══
    doc.status = "CLASSIFYING"
    db.commit()

    import time
    start = time.time()
    metadata = {
        "filename": file.filename, "extension": ext,
        "mime_type": file.content_type, "size_bytes": size,
        "parent_folder": context_hint,
    }
    classification = classify_document(extracted_text, metadata)
    processing_ms = int((time.time() - start) * 1000)
    doc.processing_time_ms = processing_ms

    # Store classification
    doc.doc_type = classification.get("doc_type")
    doc.entite = classification.get("entite")
    doc.projet = classification.get("projet")
    doc.annee = classification.get("annee")
    doc.mois = classification.get("mois")
    doc.reference_doc = classification.get("reference_doc")
    doc.tiers = classification.get("tiers")
    if classification.get("montant_da") is not None:
        doc.montant_da = Decimal(str(classification["montant_da"]))
    if classification.get("montant_devise") is not None:
        doc.montant_devise = Decimal(str(classification["montant_devise"]))
    doc.devise = classification.get("devise")
    doc.tags = classification.get("tags", [])
    doc.resume = classification.get("resume")
    doc.confidence_scores = classification.get("confidence", {})

    # ═══ STEP 4: SCORE AND DECIDE ═══
    decision = compute_archival_decision(doc.confidence_scores)

    if decision["decision"] == "AUTO_ARCHIVE":
        # ═══ STEP 6: AUTO ARCHIVE ═══
        doc.canonical_path = generate_canonical_path({
            "entite": doc.entite, "doc_type": doc.doc_type, "projet": doc.projet,
            "annee": doc.annee, "mois": doc.mois, "reference_doc": doc.reference_doc,
            "id": str(doc.id), "extension": ext,
        })
        doc.status = "ARCHIVED"
        doc.archived_at = datetime.now(timezone.utc)
        db.commit()
        return ApiResponse(data={
            "id": str(doc.id), "status": "ARCHIVED",
            "decision": "AUTO_ARCHIVE",
            "canonical_path": doc.canonical_path,
            "classification": classification,
            "extracted_text_preview": extracted_text[:500],
            "processing_ms": processing_ms,
        })
    elif decision["decision"] == "DAF_REVIEW":
        doc.status = "AWAITING_REVIEW"
        db.commit()
        return ApiResponse(data={
            "id": str(doc.id), "status": "AWAITING_REVIEW",
            "decision": "DAF_REVIEW",
            "message": decision["message"],
            "classification": classification,
            "extracted_text_preview": extracted_text[:500],
            "low_fields": decision["low_fields"],
            "processing_ms": processing_ms,
        })
    else:
        # CONFIRM_FORM
        doc.status = "AWAITING_REVIEW"
        db.commit()
        return ApiResponse(data={
            "id": str(doc.id), "status": "AWAITING_REVIEW",
            "decision": "CONFIRM_FORM",
            "message": decision["message"],
            "classification": classification,
            "extracted_text_preview": extracted_text[:500],
            "low_fields": decision["low_fields"],
            "processing_ms": processing_ms,
        })


# ═══ BATCH INGEST (multiple files) ═══

@router.post("/ingest-batch")
async def ingest_batch(files: list[UploadFile] = File(...),
                       context_hint: str = Form(default=""),
                       db: Session = Depends(get_db),
                       user: CurrentUser = Depends(get_current_user)):
    """Ingest multiple files. Each processed independently through the pipeline."""
    results = []
    for file in files:
        try:
            content = await file.read()
            sha256 = hashlib.sha256(content).hexdigest()
            existing = db.query(DocumentRegistry).filter(DocumentRegistry.sha256_hash == sha256).first()
            if existing:
                results.append({"filename": file.filename, "status": "DUPLICATE", "existing_path": existing.canonical_path})
                continue

            ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "bin"
            file_id = str(uuid.uuid4())
            local_path = os.path.join(UPLOAD_DIR, f"{file_id}.{ext}")
            with open(local_path, "wb") as f:
                f.write(content)

            doc = DocumentRegistry(
                company_id=db.query(Company).first().id,
                file_name_original=file.filename, sha256_hash=sha256,
                size_bytes=len(content), mime_type=file.content_type,
                storage_url=local_path, status="PENDING",
                ingested_by=user.email, context_hint=context_hint,
            )
            db.add(doc)
            db.commit()
            results.append({"filename": file.filename, "id": str(doc.id), "status": "QUEUED"})
        except Exception as e:
            results.append({"filename": file.filename, "status": "ERROR", "message": str(e)})

    return ApiResponse(data={"queued": len([r for r in results if r["status"] == "QUEUED"]),
                              "duplicates": len([r for r in results if r["status"] == "DUPLICATE"]),
                              "errors": len([r for r in results if r["status"] == "ERROR"]),
                              "results": results})


# ═══ GOOGLE DRIVE INGEST ═══

def _extract_drive_file_id(url_or_id: str) -> str | None:
    """Extract Google Drive file ID from various URL formats or raw ID."""
    url_or_id = url_or_id.strip()
    # Direct file ID (no slashes, typically 33+ chars)
    if re.match(r'^[a-zA-Z0-9_-]{20,}$', url_or_id):
        return url_or_id
    # https://drive.google.com/file/d/FILE_ID/view
    m = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url_or_id)
    if m:
        return m.group(1)
    # https://drive.google.com/open?id=FILE_ID
    m = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url_or_id)
    if m:
        return m.group(1)
    # https://docs.google.com/document/d/FILE_ID/edit
    m = re.search(r'/d/([a-zA-Z0-9_-]+)', url_or_id)
    if m:
        return m.group(1)
    # https://drive.google.com/drive/folders/FOLDER_ID
    m = re.search(r'/folders/([a-zA-Z0-9_-]+)', url_or_id)
    if m:
        return m.group(1)
    return None


def _download_drive_file(file_id: str) -> tuple[bytes, str]:
    """Download a publicly shared Google Drive file. Returns (content, filename)."""
    import urllib.request
    import urllib.error

    # First try the direct download URL
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        req = urllib.request.Request(download_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GFI-DIS/1.0",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            # Try to get filename from Content-Disposition header
            cd = resp.headers.get("Content-Disposition", "")
            filename = "drive_document"
            m = re.search(r'filename="?([^";\n]+)"?', cd)
            if m:
                filename = m.group(1).strip()
            elif not cd:
                # If no content-disposition, might be an HTML confirm page for large files
                if content[:100].lower().startswith(b'<!doctype') or b'<html' in content[:200].lower():
                    # Google shows a virus scan warning page for large files — extract confirm link
                    html = content.decode("utf-8", errors="replace")
                    confirm_match = re.search(r'confirm=([a-zA-Z0-9_-]+)', html)
                    if confirm_match:
                        confirm_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm={confirm_match.group(1)}"
                        req2 = urllib.request.Request(confirm_url, headers={
                            "User-Agent": "Mozilla/5.0 GFI-DIS/1.0",
                        })
                        with urllib.request.urlopen(req2, timeout=30) as resp2:
                            content = resp2.read()
                            cd2 = resp2.headers.get("Content-Disposition", "")
                            m2 = re.search(r'filename="?([^";\n]+)"?', cd2)
                            if m2:
                                filename = m2.group(1).strip()
                    else:
                        raise ValueError("Fichier non accessible — verifiez que le partage est 'Tous ceux qui ont le lien'")
            return content, filename
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"Fichier introuvable (ID: {file_id}). Verifiez le lien.")
        elif e.code == 403:
            raise ValueError("Acces refuse. Le fichier doit etre partage en mode 'Tous ceux qui ont le lien'.")
        raise ValueError(f"Erreur Drive HTTP {e.code}: {str(e)[:100]}")
    except urllib.error.URLError as e:
        raise ValueError(f"Erreur reseau: {str(e)[:100]}")


@router.post("/ingest-drive")
async def ingest_drive(body: dict, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(get_current_user)):
    """Ingest a document from a Google Drive link. Supports file and folder links.
    Files must be shared as 'Anyone with the link'."""
    url_or_id = body.get("folder_id", "") or body.get("url", "") or body.get("link", "")
    if not url_or_id:
        raise HTTPException(400, "Lien Google Drive requis (url, link, ou folder_id)")

    file_id = _extract_drive_file_id(url_or_id)
    if not file_id:
        raise HTTPException(400, f"Impossible d'extraire l'ID du fichier depuis: {url_or_id[:100]}")

    # Download the file
    try:
        content, filename = _download_drive_file(file_id)
    except ValueError as e:
        raise HTTPException(422, str(e))

    if len(content) < 100:
        raise HTTPException(422, "Fichier vide ou trop petit")
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(400, f"DIS_006: Fichier trop volumineux ({len(content) / 1024 / 1024:.1f} Mo)")

    # Compute SHA-256 and check duplicate
    sha256 = hashlib.sha256(content).hexdigest()
    existing = db.query(DocumentRegistry).filter(DocumentRegistry.sha256_hash == sha256).first()
    if existing:
        raise HTTPException(409, {
            "code": "DIS_002",
            "message": f"Doublon. Fichier deja archive: {existing.canonical_path}",
            "existing_id": str(existing.id),
        })

    # Determine extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"

    # Save locally
    local_file_id = str(uuid.uuid4())
    local_path = os.path.join(UPLOAD_DIR, f"{local_file_id}.{ext}")
    with open(local_path, "wb") as f:
        f.write(content)

    # Create registry entry
    doc = DocumentRegistry(
        company_id=db.query(Company).first().id,
        file_name_original=filename,
        sha256_hash=sha256,
        size_bytes=len(content),
        mime_type=f"application/{ext}" if ext not in IMAGE_EXTS else MIME_MAP.get(ext, "application/octet-stream"),
        storage_url=local_path,
        status="EXTRACTING",
        ingested_by=user.email,
        context_hint=f"Google Drive: {url_or_id[:100]}",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Extract text (same logic as file upload)
    extracted_text = ""
    try:
        if ext == "pdf":
            try:
                import PyPDF2
                with open(local_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception:
                extracted_text = ""
            if len(extracted_text.strip()) < 50:
                vision_text = _extract_pdf_with_vision(local_path)
                if len(vision_text.strip()) > len(extracted_text.strip()):
                    extracted_text = vision_text
        elif ext in ("txt", "csv"):
            extracted_text = content.decode("utf-8", errors="replace")
        elif ext in IMAGE_EXTS:
            extracted_text = _extract_with_vision(content, ext, filename)
        else:
            extracted_text = f"[Fichier {ext}: {filename}]"
    except Exception as e:
        extracted_text = f"[Erreur extraction: {str(e)}]"

    if len(extracted_text.strip()) < 10:
        doc.status = "QUARANTINE"
        doc.error_log = "DIS_001: Extraction echouee sur fichier Drive"
        db.commit()
        return ApiResponse(data={
            "id": str(doc.id), "status": "QUARANTINE", "source": "DRIVE",
            "filename": filename, "error": "DIS_001",
        })

    doc.extracted_text_full = extracted_text
    doc.raw_text_excerpt = extracted_text[:2000]

    # Classify with AI
    doc.status = "CLASSIFYING"
    db.commit()
    import time
    start = time.time()
    metadata = {"filename": filename, "extension": ext, "source": "google_drive"}
    classification = classify_document(extracted_text, metadata)
    doc.processing_time_ms = int((time.time() - start) * 1000)

    # Store classification
    for field in ["doc_type", "entite", "projet", "annee", "mois", "reference_doc", "tiers", "devise", "resume"]:
        if classification.get(field) is not None:
            setattr(doc, field, classification[field])
    if classification.get("montant_da") is not None:
        doc.montant_da = Decimal(str(classification["montant_da"]))
    doc.tags = classification.get("tags", [])
    doc.confidence_scores = classification.get("confidence", {})

    # Score and decide
    decision = compute_archival_decision(doc.confidence_scores)

    if decision["decision"] == "AUTO_ARCHIVE":
        doc.canonical_path = generate_canonical_path({
            "entite": doc.entite, "doc_type": doc.doc_type, "projet": doc.projet,
            "annee": doc.annee, "mois": doc.mois, "reference_doc": doc.reference_doc,
            "id": str(doc.id), "extension": ext,
        })
        doc.status = "ARCHIVED"
        doc.archived_at = datetime.now(timezone.utc)
    else:
        doc.status = "AWAITING_REVIEW"
    db.commit()

    return ApiResponse(data={
        "id": str(doc.id), "status": doc.status,
        "source": "DRIVE", "filename": filename,
        "decision": decision["decision"],
        "classification": classification,
        "extracted_text_preview": extracted_text[:500],
        "processing_ms": doc.processing_time_ms,
    })


# ═══ FILE PREVIEW (serve uploaded file for review) ═══

@router.get("/{doc_id}/preview")
async def preview_document(doc_id: str, db: Session = Depends(get_db)):
    """Serve the uploaded file so the frontend can display it inline."""
    from fastapi.responses import FileResponse
    doc = db.query(DocumentRegistry).filter(DocumentRegistry.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document introuvable")
    if not doc.storage_url or not os.path.exists(doc.storage_url):
        raise HTTPException(404, "Fichier physique introuvable")
    return FileResponse(
        doc.storage_url,
        media_type=doc.mime_type or "application/octet-stream",
        filename=doc.file_name_original,
    )


# ═══ STEP 5: CONFIRM + AUTO-ROUTE ═══

# Routing rules: doc_type → where it should go after archival
DOC_ROUTING = {
    # Financial → Cost Center
    "FACTURE_FOURNISSEUR": {"cc": True, "cc_source": "FACTURE", "cc_categorie": "CC2-ACHATS"},
    "FACTURE_CLIENT":      {"cc": True, "cc_source": "FACTURE", "cc_categorie": "CC1-VENTES"},
    "SITUATION_TRAVAUX":   {"cc": True, "cc_source": "SITUATION", "cc_categorie": "CC3-TRAVAUX"},
    "BON_COMMANDE":        {"cc": True, "cc_source": "FACTURE", "cc_categorie": "CC2-ACHATS"},
    "DEVIS":               {"cc": False},
    "RELEVE_BANCAIRE":     {"cc": False},
    "ACCORD_PRET":         {"cc": True, "cc_source": "FACTURE", "cc_categorie": "CC8-FINANCEMENT"},
    # Legal → Juridique module
    "CONTRAT":             {"cc": False, "legal": True},
    "AVENANT_CONTRAT":     {"cc": False, "legal": True},
    "ACTE_NOTARIE":        {"cc": False, "legal": True},
    "PERMIS_AUTORISATION": {"cc": False, "legal": True},
    # HR → Employee record
    "FICHE_PAIE":          {"cc": True, "cc_source": "PAIE", "cc_categorie": "CC4-PERSONNEL", "hr": True},
    # Construction → Operations
    "PV_RECEPTION":        {"cc": False, "operations": True},
    "PV_CHANTIER":         {"cc": False, "operations": True},
    "PLAN_TECHNIQUE":      {"cc": False, "operations": True},
    "PHOTO_CHANTIER":      {"cc": False},
    # General
    "RAPPORT_INTERNE":     {"cc": False},
    "COURRIER":            {"cc": False},
    "AUTRE":               {"cc": False},
}


def _route_to_cost_center(doc, routing, db):
    """Create a CostCenterEntry via shared helper (includes dedup guard)."""
    from app.api.v1.cc_helpers import impute_cc
    if not doc.montant_da or doc.montant_da <= 0:
        return None
    result = impute_cc(
        db,
        entite_code=doc.entite,
        projet_code=doc.projet,
        rf_type="RF1",
        montant=doc.montant_da,
        label=f"{doc.doc_type}: {doc.tiers or doc.file_name_original} — {doc.resume or ''}".strip()[:300],
        source_type=routing.get("cc_source", "FACTURE"),
        source_doc_id=str(doc.id),
    )
    return result


def _route_to_legal(doc, db):
    """Create LegalContract or LegalCase from legal documents."""
    from app.models.core import LegalContract, LegalCase
    from datetime import date

    company = db.query(Company).first()
    if not company:
        return None

    project = None
    if doc.projet:
        project = db.query(Project).filter(Project.code == doc.projet).first()

    try:
        if doc.doc_type == "CONTRAT":
            # Create a LegalContract
            count = db.query(func.count(LegalContract.id)).scalar() or 0
            name = f"CTR/{datetime.now().year}/{count + 1:05d}"
            # Ensure unique
            while db.query(LegalContract).filter(LegalContract.name == name).first():
                count += 1
                name = f"CTR/{datetime.now().year}/{count + 1:05d}"
            contract = LegalContract(
                company_id=company.id,
                name=name,
                contract_type="fournisseur",
                title=f"{doc.tiers or 'Contrat'} — {doc.resume or doc.file_name_original}"[:300],
                partner_name=doc.tiers,
                project_id=project.id if project else None,
                amount_ht=doc.montant_da or 0,
                amount_ttc=doc.montant_da or 0,
                status="en_revue",
                signed_document_id=str(doc.id),
                created_by=doc.validated_by,
            )
            db.add(contract)
            db.flush()
            return {
                "module": "JURIDIQUE", "type": "CONTRACT",
                "contract_id": str(contract.id), "contract_name": name,
                "doc_type": doc.doc_type, "tiers": doc.tiers,
            }
        else:
            # AVENANT_CONTRAT, ACTE_NOTARIE, PERMIS_AUTORISATION → LegalCase
            count = db.query(func.count(LegalCase.id)).scalar() or 0
            name = f"JUR/{datetime.now().year}/{count + 1:05d}"
            while db.query(LegalCase).filter(LegalCase.name == name).first():
                count += 1
                name = f"JUR/{datetime.now().year}/{count + 1:05d}"
            case_types = {
                "AVENANT_CONTRAT": "avenant", "ACTE_NOTARIE": "acte_notarie",
                "PERMIS_AUTORISATION": "autorisation",
            }
            case = LegalCase(
                company_id=company.id,
                name=name,
                case_type=case_types.get(doc.doc_type, "autre"),
                title=f"{doc.tiers or doc.doc_type} — {doc.resume or doc.file_name_original}"[:300],
                description=doc.resume,
                stage="ouvert", priority="normal",
                partner_name=doc.tiers,
                project_id=project.id if project else None,
                project_code=project.code if project else None,
                amount_claimed=doc.montant_da or 0,
                invoice_ids=[str(doc.id)],
                date_open=date.today(),
            )
            db.add(case)
            db.flush()
            return {
                "module": "JURIDIQUE", "type": "CASE",
                "case_id": str(case.id), "case_name": name,
                "doc_type": doc.doc_type, "tiers": doc.tiers,
            }
    except Exception as e:
        return {"module": "JURIDIQUE", "error": str(e)[:100], "doc_type": doc.doc_type}


def _route_to_hr(doc, db):
    """Link payroll documents to employee records."""
    try:
        from app.models.core import Employee
        if doc.tiers:
            # Try to find employee by name
            emp = db.query(Employee).filter(
                Employee.is_deleted == False,
                (Employee.first_name + " " + Employee.last_name).ilike(f"%{doc.tiers}%")
            ).first()
            if emp:
                return {"module": "RH", "employee_id": str(emp.id), "employee_name": f"{emp.first_name} {emp.last_name}"}
        return {"module": "RH", "employee_id": None, "note": "Employe non identifie automatiquement"}
    except Exception:
        return None


@router.patch("/{doc_id}/confirm")
async def confirm_document(doc_id: str, body: dict, db: Session = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    """Confirm/correct classification, archive, and auto-route to relevant modules."""
    doc = db.query(DocumentRegistry).filter(DocumentRegistry.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document introuvable")
    if doc.status not in ("AWAITING_REVIEW", "DRAFT"):
        raise HTTPException(400, f"Document en statut {doc.status} — confirmation impossible")

    # Update fields from body
    for field in ["doc_type", "entite", "projet", "annee", "mois", "reference_doc",
                  "tiers", "montant_da", "montant_devise", "devise", "tags", "resume"]:
        if field in body:
            val = body[field]
            if field == "montant_da" and val is not None:
                val = Decimal(str(val))
            if field == "montant_devise" and val is not None:
                val = Decimal(str(val))
            setattr(doc, field, val)

    # DIS_008: check critical fields
    for critical in ["doc_type", "entite", "projet", "annee"]:
        if not getattr(doc, critical):
            raise HTTPException(422, f"DIS_008: Champ obligatoire manquant: {critical}")

    # DIS_009: check user's doc scope — can they upload this type?
    if user.doc_scope is not None and doc.doc_type not in user.doc_scope:
        raise HTTPException(403,
            f"Vous n'avez pas acces au type '{doc.doc_type}'. "
            f"Types autorises pour votre role ({user.role}): {', '.join(user.doc_scope)}")

    # Generate canonical path and archive
    ext = doc.file_name_original.rsplit(".", 1)[-1].lower() if "." in doc.file_name_original else "bin"
    doc.canonical_path = generate_canonical_path({
        "entite": doc.entite, "doc_type": doc.doc_type, "projet": doc.projet,
        "annee": doc.annee, "mois": doc.mois, "reference_doc": doc.reference_doc,
        "id": str(doc.id), "extension": ext,
    })
    doc.status = "ARCHIVED"
    doc.archived_at = datetime.now(timezone.utc)
    doc.validated_by = user.email

    # ═══ CONTENT-BASED DEDUP WARNING ═══
    content_dedup_warning = None
    if doc.montant_da and doc.montant_da > 0:
        from app.models.core import CostCenterEntry
        from datetime import timedelta
        cc_source = DOC_ROUTING.get(doc.doc_type, {}).get("cc_source", "FACTURE")
        date_low = datetime.now(timezone.utc) - timedelta(days=30)
        date_high = datetime.now(timezone.utc) + timedelta(days=30)
        q = db.query(CostCenterEntry).filter(
            CostCenterEntry.source_type == cc_source,
            CostCenterEntry.montant == doc.montant_da,
            CostCenterEntry.is_deleted == False,
            CostCenterEntry.created_at >= date_low,
            CostCenterEntry.created_at <= date_high,
            CostCenterEntry.source_doc_id != str(doc.id),
        )
        if doc.tiers:
            q = q.filter(CostCenterEntry.label.ilike(f"%{doc.tiers}%"))
        similar = q.first()
        if similar:
            content_dedup_warning = (
                f"ATTENTION doublon potentiel: une ecriture CC similaire existe "
                f"(montant={similar.montant}, source={similar.source_doc_id}, "
                f"date={similar.created_at.date() if similar.created_at else '?'}). "
                f"Verifiez qu'il ne s'agit pas du meme document."
            )

    # ═══ AUTO-ROUTING: send to relevant modules ═══
    routing = DOC_ROUTING.get(doc.doc_type, {"cc": False})
    routed_to = []
    cc_done = False

    # 1. Cost Center imputation — CC-routable types with montant
    if routing.get("cc") and doc.montant_da and doc.montant_da > 0:
        cc_result = _route_to_cost_center(doc, routing, db)
        if cc_result:
            routed_to.append({"target": "CENTRE_DE_COUT", **cc_result})
            cc_done = True

    # 2. ALWAYS add to CC if not already done — every document leaves a trace
    if not cc_done:
        from app.api.v1.cc_helpers import impute_cc
        montant = doc.montant_da if doc.montant_da and doc.montant_da > 0 else Decimal("0")
        source = routing.get("cc_source", "DOCUMENT")
        # For zero-montant: use a small epsilon so impute_cc doesn't skip (it rejects montant==0)
        # Instead, call impute_cc only if montant > 0, otherwise create entry directly
        if montant > 0:
            trace = impute_cc(
                db, entite_code=doc.entite, projet_code=doc.projet,
                rf_type="RF1", montant=montant,
                label=f"{doc.doc_type}: {doc.tiers or doc.file_name_original} — {doc.resume or ''}".strip()[:300],
                source_type=source, source_doc_id=str(doc.id),
            )
            if trace:
                routed_to.append({"target": "CENTRE_DE_COUT", **trace})
        else:
            # Zero-montant trace entry — no financial impact, just document linkage
            from app.models.core import CostCenterEntry as CCE, CostCenterNode as CCN
            # Check dedup
            existing = db.query(CCE).filter(
                CCE.source_doc_id == str(doc.id), CCE.source_type == "DOCUMENT", CCE.is_deleted == False
            ).first()
            if not existing:
                node = db.query(CCN).filter(CCN.is_deleted == False).order_by(CCN.level).first()
                if node:
                    comp = db.query(Company).first()
                    db.add(CCE(
                        company_id=comp.id if comp else node.company_id,
                        node_id=node.id, rf_type="RF1", montant=Decimal("0"),
                        label=f"{doc.doc_type}: {doc.tiers or doc.file_name_original} — {doc.resume or ''}".strip()[:300],
                        source_type="DOCUMENT", source_doc_id=str(doc.id),
                    ))
                    routed_to.append({"target": "CENTRE_DE_COUT", "node_code": node.code, "entry_montant": "0", "trace_only": True})

    # 3. Legal module forwarding
    if routing.get("legal"):
        legal_result = _route_to_legal(doc, db)
        if legal_result:
            routed_to.append({"target": "JURIDIQUE", **legal_result})

    # 4. HR module forwarding
    if routing.get("hr"):
        hr_result = _route_to_hr(doc, db)
        if hr_result:
            routed_to.append({"target": "RH", **hr_result})

    # 5. Operations forwarding
    if routing.get("operations"):
        routed_to.append({"target": "OPERATIONS", "doc_type": doc.doc_type})

    db.commit()

    resp = {
        "id": str(doc.id), "status": "ARCHIVED",
        "canonical_path": doc.canonical_path,
        "routed_to": routed_to,
        "message": f"Document archive et route vers {len(routed_to)} module(s)" if routed_to else "Document archive",
    }
    if content_dedup_warning:
        resp["dedup_warning"] = content_dedup_warning
    return ApiResponse(data=resp)


@router.patch("/{doc_id}/draft")
async def save_draft(doc_id: str, body: dict, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(get_current_user)):
    """Save as draft without archiving."""
    doc = db.query(DocumentRegistry).filter(DocumentRegistry.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document introuvable")
    for field in ["doc_type", "entite", "projet", "annee", "mois", "reference_doc",
                  "tiers", "tags", "resume"]:
        if field in body:
            setattr(doc, field, body[field])
    doc.status = "DRAFT"
    db.commit()
    return ApiResponse(data={"id": str(doc.id), "status": "DRAFT"})


@router.patch("/{doc_id}/quarantine")
async def quarantine_document(doc_id: str, body: dict, db: Session = Depends(get_db),
                               user: CurrentUser = Depends(get_current_user)):
    """Put document in quarantine. Requires reason."""
    doc = db.query(DocumentRegistry).filter(DocumentRegistry.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document introuvable")
    reason = body.get("reason", "")
    if not reason:
        raise HTTPException(400, "Motif de quarantaine obligatoire")
    doc.status = "QUARANTINE"
    doc.error_log = f"Quarantaine manuelle par {user.email}: {reason}"
    db.commit()
    return ApiResponse(data={"id": str(doc.id), "status": "QUARANTINE"})


# ═══ SEARCH & BROWSE ═══

@router.get("/search")
async def search_documents(q: str = "", entite: str = "", projet: str = "", doc_type: str = "",
                           annee_min: int = 0, annee_max: int = 9999, tiers: str = "",
                           status: str = "", page: int = 1, limit: int = 50,
                           db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """Search documents with filters and facets. CDC §10."""
    query = db.query(DocumentRegistry)
    if q:
        query = query.filter(or_(
            DocumentRegistry.raw_text_excerpt.ilike(f"%{q}%"),
            DocumentRegistry.resume.ilike(f"%{q}%"),
            DocumentRegistry.reference_doc.ilike(f"%{q}%"),
            DocumentRegistry.tiers.ilike(f"%{q}%"),
            DocumentRegistry.file_name_original.ilike(f"%{q}%"),
        ))
    if entite:
        query = query.filter(DocumentRegistry.entite == entite)
    if projet:
        query = query.filter(DocumentRegistry.projet == projet)
    if doc_type:
        query = query.filter(DocumentRegistry.doc_type == doc_type)
    if annee_min > 0:
        query = query.filter(DocumentRegistry.annee >= annee_min)
    if annee_max < 9999:
        query = query.filter(DocumentRegistry.annee <= annee_max)
    if tiers:
        query = query.filter(DocumentRegistry.tiers.ilike(f"%{tiers}%"))
    if status:
        query = query.filter(DocumentRegistry.status == status)

    total = query.count()
    offset = (page - 1) * limit
    docs = query.order_by(DocumentRegistry.ingested_at.desc()).offset(offset).limit(limit).all()

    # Facets
    facet_entite = db.query(DocumentRegistry.entite, func.count()).group_by(DocumentRegistry.entite).all()
    facet_projet = db.query(DocumentRegistry.projet, func.count()).group_by(DocumentRegistry.projet).all()
    facet_type = db.query(DocumentRegistry.doc_type, func.count()).group_by(DocumentRegistry.doc_type).all()

    return ApiResponse(data={
        "documents": [{
            "id": str(d.id), "filename": d.file_name_original, "canonical_path": d.canonical_path,
            "doc_type": d.doc_type, "entite": d.entite, "projet": d.projet,
            "annee": d.annee, "mois": d.mois, "reference_doc": d.reference_doc,
            "tiers": d.tiers, "montant_da": str(d.montant_da) if d.montant_da else None,
            "resume": d.resume, "status": d.status, "tags": d.tags or [],
            "confidence": d.confidence_scores,
            "ingested_at": str(d.ingested_at), "archived_at": str(d.archived_at) if d.archived_at else None,
        } for d in docs],
        "facets": {
            "entite": {str(k): v for k, v in facet_entite if k},
            "projet": {str(k): v for k, v in facet_projet if k},
            "doc_type": {str(k): v for k, v in facet_type if k},
        },
    }, meta=Meta(total=total, limit=limit, offset=offset))


@router.get("/review-queue")
async def review_queue(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """Documents awaiting review. CDC §14.4."""
    docs = db.query(DocumentRegistry).filter(
        DocumentRegistry.status.in_(["AWAITING_REVIEW", "DRAFT"])
    ).order_by(DocumentRegistry.ingested_at.asc()).limit(50).all()

    return ApiResponse(data=[{
        "id": str(d.id), "filename": d.file_name_original,
        "doc_type": d.doc_type, "entite": d.entite, "projet": d.projet,
        "annee": d.annee, "status": d.status, "resume": d.resume,
        "confidence": d.confidence_scores,
        "ingested_at": str(d.ingested_at),
        "low_fields": {k: v for k, v in (d.confidence_scores or {}).items() if v < CONFIDENCE_THRESHOLD},
    } for d in docs])


# Stats for dashboard — MUST be before /{doc_id} to avoid route conflict
@router.get("/stats")
async def dis_stats(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    total = db.query(DocumentRegistry).count()
    archived = db.query(DocumentRegistry).filter(DocumentRegistry.status == "ARCHIVED").count()
    review = db.query(DocumentRegistry).filter(DocumentRegistry.status.in_(["AWAITING_REVIEW", "DRAFT"])).count()
    quarantine = db.query(DocumentRegistry).filter(DocumentRegistry.status == "QUARANTINE").count()
    return ApiResponse(data={
        "total": total, "archived": archived,
        "awaiting_review": review, "quarantine": quarantine,
    })


@router.get("/{doc_id}")
async def get_document(doc_id: str, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(get_current_user)):
    """Get full document details. CDC §10."""
    doc = db.query(DocumentRegistry).filter(DocumentRegistry.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document introuvable")

    return ApiResponse(data={
        "id": str(doc.id), "filename": doc.file_name_original,
        "canonical_path": doc.canonical_path, "storage_url": doc.storage_url,
        "sha256": doc.sha256_hash, "size_bytes": doc.size_bytes, "mime_type": doc.mime_type,
        "doc_type": doc.doc_type, "entite": doc.entite, "projet": doc.projet,
        "annee": doc.annee, "mois": doc.mois, "reference_doc": doc.reference_doc,
        "tiers": doc.tiers,
        "montant_da": str(doc.montant_da) if doc.montant_da else None,
        "montant_devise": str(doc.montant_devise) if doc.montant_devise else None,
        "devise": doc.devise, "tags": doc.tags or [], "resume": doc.resume,
        "confidence": doc.confidence_scores, "status": doc.status,
        "raw_text_excerpt": doc.raw_text_excerpt,
        "ingested_at": str(doc.ingested_at), "archived_at": str(doc.archived_at) if doc.archived_at else None,
        "ingested_by": doc.ingested_by, "validated_by": doc.validated_by,
        "ocr_quality_flag": doc.ocr_quality_flag,
        "processing_time_ms": doc.processing_time_ms,
        "version_of": str(doc.version_of) if doc.version_of else None,
        "is_latest": doc.is_latest,
    })

