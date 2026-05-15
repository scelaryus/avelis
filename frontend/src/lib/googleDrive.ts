/**
 * Google Drive Picker — select files from Drive then download as blobs.
 *
 * Requires two env vars (set in .env):
 *   VITE_GOOGLE_CLIENT_ID  — OAuth 2.0 Client ID (Web application)
 *   VITE_GOOGLE_API_KEY     — API key with Drive API enabled
 *
 * The Google API + GSI scripts must be loaded in index.html.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */
declare global {
  interface Window {
    gapi: any;
    google: any;
  }
}

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;
const API_KEY = import.meta.env.VITE_GOOGLE_API_KEY as string | undefined;
const SCOPES = "https://www.googleapis.com/auth/drive.readonly";

/** True when both env vars are configured */
export function isGoogleDriveEnabled(): boolean {
  return !!(CLIENT_ID && API_KEY);
}

// ── Internal helpers ──────────────────────────────────────────────────

let gapiLoaded = false;
let pickerLoaded = false;

function loadGapi(): Promise<void> {
  if (gapiLoaded) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const check = () => {
      if (!window.gapi) return reject(new Error("gapi not loaded — check index.html"));
      window.gapi.load("client:picker", {
        callback: () => {
          gapiLoaded = true;
          pickerLoaded = true;
          resolve();
        },
        onerror: reject,
      });
    };
    // gapi script may still be loading
    if (window.gapi) check();
    else setTimeout(check, 500);
  });
}

function getOAuthToken(): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!window.google?.accounts?.oauth2) {
      return reject(new Error("Google Identity Services not loaded"));
    }
    const client = window.google.accounts.oauth2.initTokenClient({
      client_id: CLIENT_ID!,
      scope: SCOPES,
      callback: (response: any) => {
        if (response.error) return reject(new Error(response.error));
        resolve(response.access_token);
      },
    });
    client.requestAccessToken();
  });
}

export interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  size?: number;
}

/**
 * Opens the Google Drive Picker and returns selected files metadata.
 * Handles OAuth automatically.
 */
export async function openDrivePicker(): Promise<{ files: DriveFile[]; accessToken: string }> {
  await loadGapi();
  const accessToken = await getOAuthToken();

  return new Promise((resolve) => {
    const view = new window.google.picker.DocsView(window.google.picker.ViewId.DOCS)
      .setMimeTypes("application/pdf,image/png,image/jpeg,image/tiff")
      .setMode(window.google.picker.DocsViewMode.LIST);

    const picker = new window.google.picker.PickerBuilder()
      .addView(view)
      .setOAuthToken(accessToken)
      .setDeveloperKey(API_KEY!)
      .setTitle("Sélectionner des documents depuis Google Drive")
      .enableFeature(window.google.picker.Feature.MULTISELECT_ENABLED)
      .setCallback((data: any) => {
        if (data.action === window.google.picker.Action.PICKED) {
          const files: DriveFile[] = data.docs.map((doc: any) => ({
            id: doc.id,
            name: doc.name,
            mimeType: doc.mimeType,
            size: doc.sizeBytes,
          }));
          resolve({ files, accessToken });
        } else if (data.action === window.google.picker.Action.CANCEL) {
          resolve({ files: [], accessToken });
        }
      })
      .build();

    picker.setVisible(true);
  });
}

/**
 * Download a single file from Google Drive as a Blob using the user's token.
 */
export async function downloadDriveFile(
  fileId: string,
  accessToken: string,
): Promise<Blob> {
  const response = await fetch(
    `https://www.googleapis.com/drive/v3/files/${fileId}?alt=media`,
    { headers: { Authorization: `Bearer ${accessToken}` } },
  );
  if (!response.ok) {
    throw new Error(`Failed to download Drive file ${fileId}: ${response.status}`);
  }
  return response.blob();
}

/**
 * Full flow: open picker → download selected files → return as File objects
 * ready for FormData upload to our backend.
 */
export async function pickAndDownloadDriveFiles(): Promise<File[]> {
  const { files, accessToken } = await openDrivePicker();
  if (!files.length) return [];

  const downloaded: File[] = [];
  for (const driveFile of files) {
    const blob = await downloadDriveFile(driveFile.id, accessToken);
    const file = new File([blob], driveFile.name, { type: driveFile.mimeType });
    downloaded.push(file);
  }
  return downloaded;
}
