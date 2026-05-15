"""GFI Platform - Google Drive Integration Service.

Provides per-user OAuth2 authentication and file browsing/download
for mass import from Google Drive folders.
"""
import structlog
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Google OAuth2 endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"
GOOGLE_DRIVE_API = "https://www.googleapis.com/drive/v3"

# Scopes needed for Google Drive read access
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]


class GoogleDriveService:
    """Handles Google Drive OAuth2 and file operations."""

    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI

    @property
    def is_configured(self) -> bool:
        """Check if Google Drive integration is configured."""
        return bool(self.client_id and self.client_secret)

    def get_auth_url(self, state: str = "") -> str:
        """Generate Google OAuth2 authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for tokens."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                },
            )
            response.raise_for_status()
            data = response.json()

            # Get user info
            userinfo = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {data['access_token']}"},
            )
            userinfo_data = userinfo.json() if userinfo.status_code == 200 else {}

            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token"),
                "expires_in": data.get("expires_in", 3600),
                "token_expiry": datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600)),
                "email": userinfo_data.get("email"),
            }

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            data = response.json()

            return {
                "access_token": data["access_token"],
                "expires_in": data.get("expires_in", 3600),
                "token_expiry": datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600)),
            }

    async def list_folder(
        self,
        access_token: str,
        folder_id: str = "root",
        page_token: Optional[str] = None,
    ) -> dict:
        """List files/folders in a Google Drive folder."""
        import httpx

        query = f"'{folder_id}' in parents and trashed = false"
        params = {
            "q": query,
            "fields": "nextPageToken, files(id, name, mimeType, size, modifiedTime)",
            "pageSize": 100,
            "orderBy": "name",
        }
        if page_token:
            params["pageToken"] = page_token

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GOOGLE_DRIVE_API}/files",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()

            files = []
            folders = []
            for item in data.get("files", []):
                entry = {
                    "id": item["id"],
                    "name": item["name"],
                    "mimeType": item["mimeType"],
                    "size": int(item.get("size", 0)),
                    "modifiedTime": item.get("modifiedTime"),
                }
                if item["mimeType"] == "application/vnd.google-apps.folder":
                    folders.append(entry)
                else:
                    files.append(entry)

            return {
                "folder_id": folder_id,
                "folders": folders,
                "files": files,
                "nextPageToken": data.get("nextPageToken"),
            }

    async def list_folder_recursive(
        self,
        access_token: str,
        folder_id: str = "root",
        allowed_mimes: set[str] | None = None,
    ) -> list[dict]:
        """Recursively list all files in a folder and subfolders."""
        if allowed_mimes is None:
            allowed_mimes = {
                "application/pdf",
                "image/png",
                "image/jpeg",
                "image/tiff",
            }

        all_files = []
        result = await self.list_folder(access_token, folder_id)

        # Add files matching allowed MIME types
        for f in result["files"]:
            if f["mimeType"] in allowed_mimes:
                all_files.append(f)

        # Recurse into subfolders
        for subfolder in result["folders"]:
            sub_files = await self.list_folder_recursive(
                access_token, subfolder["id"], allowed_mimes
            )
            all_files.extend(sub_files)

        return all_files

    async def download_file(self, access_token: str, file_id: str) -> tuple[bytes, str]:
        """Download a file from Google Drive. Returns (content, mime_type)."""
        import httpx

        async with httpx.AsyncClient() as client:
            # Get file metadata first
            meta_response = await client.get(
                f"{GOOGLE_DRIVE_API}/files/{file_id}",
                params={"fields": "name, mimeType, size"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            meta_response.raise_for_status()
            meta = meta_response.json()

            # Download content
            response = await client.get(
                f"{GOOGLE_DRIVE_API}/files/{file_id}",
                params={"alt": "media"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()

            return response.content, meta.get("mimeType", "application/octet-stream")

    async def download_folder_files(
        self,
        access_token: str,
        folder_id: str,
    ) -> list[tuple[str, bytes, str]]:
        """Download all importable files from a Google Drive folder.
        Returns list of (filename, content, mime_type) tuples.
        """
        files = await self.list_folder_recursive(access_token, folder_id)
        downloaded = []

        for file_info in files:
            try:
                content, mime_type = await self.download_file(
                    access_token, file_info["id"]
                )
                # Enforce size limit
                max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
                if len(content) > max_size:
                    logger.warning("gdrive_file_too_large",
                                   name=file_info["name"],
                                   size=len(content))
                    continue

                downloaded.append((file_info["name"], content, mime_type))
                logger.info("gdrive_file_downloaded",
                            name=file_info["name"],
                            size=len(content))

            except Exception as e:
                logger.warning("gdrive_download_failed",
                               file_id=file_info["id"],
                               name=file_info["name"],
                               error=str(e))

        return downloaded


def get_google_drive_service() -> GoogleDriveService:
    """Factory for GoogleDriveService."""
    return GoogleDriveService()
