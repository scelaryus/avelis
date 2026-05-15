"""GFI Platform - Import Sessions API router.

Handles mass file import from PC folders and Google Drive.
Endpoints:
  POST   /import-sessions/upload         — Upload multiple files from PC
  POST   /import-sessions/google-drive   — Import from Google Drive folder
  GET    /import-sessions                — List import sessions
  GET    /import-sessions/{id}           — Get session details + results
  POST   /import-sessions/{id}/process   — Trigger AI processing for a session
  GET    /google-drive/auth-url          — Get Google OAuth2 URL
  POST   /google-drive/callback          — Handle OAuth2 callback
  GET    /google-drive/status            — Check Google Drive connection
  GET    /google-drive/browse            — Browse Google Drive folders
"""
import uuid
from datetime import datetime
from typing import Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks, status
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.core import (
    User, ImportSession, ImportSessionStatus, ImportSourceType, AuditLog,
)
from app.models.integrations import UserIntegration, IntegrationProvider
from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.services.import_orchestrator import ingest_files_to_session, run_import_session
from app.services.google_drive import get_google_drive_service

router = APIRouter(tags=["Import"])
logger = structlog.get_logger(__name__)
settings = get_settings()

ALLOWED_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/tiff"}


# ── Schemas ───────────────────────────────────────────────────────

class ImportSessionResponse(BaseModel):
    id: str
    source_type: str
    source_path: Optional[str] = None
    processing_mode: str = "FULL_AUTO"
    nombre_fichiers: int
    fichiers_traites: int
    fichiers_erreur: int
    fichiers_dupliques: int = 0
    statut: str
    resultats: Optional[list] = None
    erreurs: Optional[list] = None
    date_import: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class GoogleDriveImportRequest(BaseModel):
    folder_id: str
    folder_name: Optional[str] = None


class GoogleDriveCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None


class GoogleDriveStatusResponse(BaseModel):
    connected: bool
    email: Optional[str] = None
    provider: str = "GOOGLE_DRIVE"


# ── PC Folder Upload ────────────────────────────────────────────

@router.post("/import-sessions/upload", response_model=ImportSessionResponse)
async def upload_folder_files(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    processing_mode: str = Query("FULL_AUTO", enum=["FULL_AUTO", "CLASSIFY_ONLY"]),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload multiple files from PC for mass import and AI processing."""
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")

    if len(files) > 500:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 500 files per import session")

    # Create import session
    session_id = str(uuid.uuid4())
    session = ImportSession(
        id=session_id,
        tenant_id=user.tenant_id,
        user_id=str(user.id),
        source_type=ImportSourceType.PC_FOLDER,
        source_path="PC Upload",
        processing_mode=processing_mode,
        nombre_fichiers=len(files),
        statut=ImportSessionStatus.EN_COURS,
    )
    db.add(session)
    await db.flush()

    # Read and validate files
    files_data = []
    skipped = 0
    for f in files:
        if f.content_type not in ALLOWED_TYPES:
            skipped += 1
            logger.warning("import_file_skipped_type", filename=f.filename, type=f.content_type)
            continue

        content = await f.read()
        max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_size:
            skipped += 1
            logger.warning("import_file_skipped_size", filename=f.filename, size=len(content))
            continue

        files_data.append((f.filename, content, f.content_type))

    if not files_data:
        session.statut = ImportSessionStatus.ERREUR
        session.erreurs = [{"code": "NO_VALID_FILES", "message": "No valid files to import"}]
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid files to import (check file types and sizes)",
        )

    # Update actual file count
    session.nombre_fichiers = len(files_data)

    # Ingest files (classify + store + create Document records)
    ingest_results = await ingest_files_to_session(
        files_data=files_data,
        tenant_id=user.tenant_id,
        user_id=str(user.id),
        session_id=session_id,
        db=db,
    )

    # Audit log
    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=str(user.id),
        action="IMPORT_SESSION_CREATED",
        entity_type="import_session",
        entity_id=session_id,
        new_value={
            "source": "PC_FOLDER",
            "files_count": len(files_data),
            "skipped": skipped,
        },
    ))
    await db.commit()

    # Start background AI processing if FULL_AUTO
    if processing_mode == "FULL_AUTO":
        background_tasks.add_task(run_import_session, session_id)

    await db.refresh(session)
    return _session_to_response(session)


# ── Google Drive Import ──────────────────────────────────────────

@router.post("/import-sessions/google-drive", response_model=ImportSessionResponse)
async def import_from_google_drive(
    body: GoogleDriveImportRequest,
    background_tasks: BackgroundTasks,
    processing_mode: str = Query("FULL_AUTO", enum=["FULL_AUTO", "CLASSIFY_ONLY"]),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Import files from a Google Drive folder. Requires prior Google OAuth2 authentication."""
    gdrive = get_google_drive_service()
    if not gdrive.is_configured:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google Drive not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )

    # Get user's Google Drive token
    result = await db.execute(
        select(UserIntegration).where(
            UserIntegration.user_id == str(user.id),
            UserIntegration.provider == IntegrationProvider.GOOGLE_DRIVE,
            UserIntegration.is_active == True,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration or not integration.access_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google Drive not connected. Please authenticate first via /google-drive/auth-url",
        )

    # Refresh token if expired
    access_token = integration.access_token
    if integration.token_expiry and integration.token_expiry < datetime.utcnow():
        if integration.refresh_token:
            try:
                refreshed = await gdrive.refresh_access_token(integration.refresh_token)
                access_token = refreshed["access_token"]
                integration.access_token = access_token
                integration.token_expiry = refreshed["token_expiry"]
                await db.flush()
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Failed to refresh Google token: {str(e)}. Please re-authenticate.",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google token expired and no refresh token. Please re-authenticate.",
            )

    # Create import session
    session_id = str(uuid.uuid4())
    session = ImportSession(
        id=session_id,
        tenant_id=user.tenant_id,
        user_id=str(user.id),
        source_type=ImportSourceType.GOOGLE_DRIVE,
        source_path=f"gdrive://{body.folder_id}" + (f" ({body.folder_name})" if body.folder_name else ""),
        processing_mode=processing_mode,
        nombre_fichiers=0,  # will be updated after download
        statut=ImportSessionStatus.EN_COURS,
    )
    db.add(session)
    await db.flush()

    # Download files from Google Drive
    try:
        downloaded_files = await gdrive.download_folder_files(access_token, body.folder_id)
    except Exception as e:
        session.statut = ImportSessionStatus.ERREUR
        session.erreurs = [{"code": "GDRIVE_ERROR", "message": str(e)}]
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to download from Google Drive: {str(e)}",
        )

    if not downloaded_files:
        session.statut = ImportSessionStatus.ERREUR
        session.erreurs = [{"code": "NO_FILES", "message": "No importable files found in the folder"}]
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No importable files (PDF, PNG, JPG, TIFF) found in the selected Google Drive folder",
        )

    session.nombre_fichiers = len(downloaded_files)

    # Ingest files
    ingest_results = await ingest_files_to_session(
        files_data=downloaded_files,
        tenant_id=user.tenant_id,
        user_id=str(user.id),
        session_id=session_id,
        db=db,
    )

    # Audit
    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=str(user.id),
        action="IMPORT_SESSION_CREATED",
        entity_type="import_session",
        entity_id=session_id,
        new_value={
            "source": "GOOGLE_DRIVE",
            "folder_id": body.folder_id,
            "files_count": len(downloaded_files),
        },
    ))
    await db.commit()

    # Start background AI processing
    if processing_mode == "FULL_AUTO":
        background_tasks.add_task(run_import_session, session_id)

    await db.refresh(session)
    return _session_to_response(session)


# ── Session listing & details ─────────────────────────────────────

@router.get("/import-sessions", response_model=list[ImportSessionResponse])
async def list_import_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all import sessions for the current tenant."""
    result = await db.execute(
        select(ImportSession)
        .where(ImportSession.tenant_id == user.tenant_id)
        .order_by(desc(ImportSession.created_at))
        .limit(limit)
        .offset(offset)
    )
    sessions = result.scalars().all()
    return [_session_to_response(s) for s in sessions]


@router.get("/import-sessions/{session_id}", response_model=ImportSessionResponse)
async def get_import_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific import session."""
    result = await db.execute(
        select(ImportSession).where(
            ImportSession.id == session_id,
            ImportSession.tenant_id == user.tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import session not found")
    return _session_to_response(session)


@router.post("/import-sessions/{session_id}/process")
async def trigger_processing(
    session_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger AI processing for a CLASSIFY_ONLY session."""
    result = await db.execute(
        select(ImportSession).where(
            ImportSession.id == session_id,
            ImportSession.tenant_id == user.tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import session not found")

    if session.statut == ImportSessionStatus.EN_COURS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is already being processed",
        )

    # Reset for reprocessing
    session.statut = ImportSessionStatus.EN_COURS
    session.fichiers_traites = 0
    session.fichiers_erreur = 0
    session.resultats = []
    session.completed_at = None
    await db.commit()

    background_tasks.add_task(run_import_session, session_id)

    return {"message": "Processing started", "session_id": session_id}


# ── Google Drive OAuth2 ──────────────────────────────────────────

@router.get("/google-drive/auth-url")
async def get_google_auth_url(
    user: User = Depends(get_current_user),
):
    """Get Google OAuth2 authorization URL for Drive access."""
    gdrive = get_google_drive_service()
    if not gdrive.is_configured:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google Drive integration not configured",
        )

    auth_url = gdrive.get_auth_url(state=str(user.id))
    return {"auth_url": auth_url}


@router.post("/google-drive/callback", response_model=GoogleDriveStatusResponse)
async def google_drive_callback(
    body: GoogleDriveCallbackRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth2 callback and store tokens."""
    gdrive = get_google_drive_service()

    try:
        tokens = await gdrive.exchange_code(body.code)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange Google authorization code: {str(e)}",
        )

    # Upsert UserIntegration
    result = await db.execute(
        select(UserIntegration).where(
            UserIntegration.user_id == str(user.id),
            UserIntegration.provider == IntegrationProvider.GOOGLE_DRIVE,
        )
    )
    integration = result.scalar_one_or_none()

    if integration:
        integration.access_token = tokens["access_token"]
        integration.refresh_token = tokens.get("refresh_token") or integration.refresh_token
        integration.token_expiry = tokens["token_expiry"]
        integration.provider_email = tokens.get("email")
        integration.is_active = True
        integration.updated_at = datetime.utcnow()
    else:
        integration = UserIntegration(
            id=str(uuid.uuid4()),
            tenant_id=user.tenant_id,
            user_id=str(user.id),
            provider=IntegrationProvider.GOOGLE_DRIVE,
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            token_expiry=tokens["token_expiry"],
            provider_email=tokens.get("email"),
            scopes="drive.readonly userinfo.email",
            is_active=True,
        )
        db.add(integration)

    # Audit
    db.add(AuditLog(
        tenant_id=user.tenant_id,
        user_id=str(user.id),
        action="GOOGLE_DRIVE_CONNECTED",
        entity_type="user_integration",
        entity_id=str(integration.id),
    ))
    await db.commit()

    return GoogleDriveStatusResponse(
        connected=True,
        email=tokens.get("email"),
    )


@router.get("/google-drive/status", response_model=GoogleDriveStatusResponse)
async def google_drive_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if the current user has Google Drive connected."""
    result = await db.execute(
        select(UserIntegration).where(
            UserIntegration.user_id == str(user.id),
            UserIntegration.provider == IntegrationProvider.GOOGLE_DRIVE,
            UserIntegration.is_active == True,
        )
    )
    integration = result.scalar_one_or_none()

    if integration and integration.access_token:
        return GoogleDriveStatusResponse(
            connected=True,
            email=integration.provider_email,
        )
    return GoogleDriveStatusResponse(connected=False)


@router.get("/google-drive/browse")
async def browse_google_drive(
    folder_id: str = Query("root"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Browse Google Drive folders and files."""
    gdrive = get_google_drive_service()
    if not gdrive.is_configured:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google Drive not configured",
        )

    # Get token
    result = await db.execute(
        select(UserIntegration).where(
            UserIntegration.user_id == str(user.id),
            UserIntegration.provider == IntegrationProvider.GOOGLE_DRIVE,
            UserIntegration.is_active == True,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Google Drive not connected")

    # Refresh if needed
    access_token = integration.access_token
    if integration.token_expiry and integration.token_expiry < datetime.utcnow():
        if integration.refresh_token:
            refreshed = await gdrive.refresh_access_token(integration.refresh_token)
            access_token = refreshed["access_token"]
            integration.access_token = access_token
            integration.token_expiry = refreshed["token_expiry"]
            await db.commit()

    try:
        listing = await gdrive.list_folder(access_token, folder_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to browse Google Drive: {str(e)}",
        )

    return listing


@router.delete("/google-drive/disconnect")
async def disconnect_google_drive(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect Google Drive integration."""
    result = await db.execute(
        select(UserIntegration).where(
            UserIntegration.user_id == str(user.id),
            UserIntegration.provider == IntegrationProvider.GOOGLE_DRIVE,
        )
    )
    integration = result.scalar_one_or_none()
    if integration:
        integration.is_active = False
        integration.access_token = None
        db.add(AuditLog(
            tenant_id=user.tenant_id,
            user_id=str(user.id),
            action="GOOGLE_DRIVE_DISCONNECTED",
            entity_type="user_integration",
            entity_id=str(integration.id),
        ))
        await db.commit()

    return {"message": "Google Drive disconnected"}


# ── Helpers ───────────────────────────────────────────────────────

def _session_to_response(s: ImportSession) -> ImportSessionResponse:
    return ImportSessionResponse(
        id=str(s.id),
        source_type=s.source_type.value if s.source_type else "PC_FOLDER",
        source_path=s.source_path,
        processing_mode=s.processing_mode or "FULL_AUTO",
        nombre_fichiers=s.nombre_fichiers or 0,
        fichiers_traites=s.fichiers_traites or 0,
        fichiers_erreur=s.fichiers_erreur or 0,
        fichiers_dupliques=s.fichiers_dupliques or 0,
        statut=s.statut.value if s.statut else "EN_COURS",
        resultats=s.resultats,
        erreurs=s.erreurs,
        date_import=s.date_import,
        completed_at=s.completed_at,
    )
