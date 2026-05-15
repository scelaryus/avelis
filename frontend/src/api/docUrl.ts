/**
 * Build a document download/preview URL with JWT token as query param.
 * This is needed because <img src> and <iframe src> cannot send Authorization headers.
 */
export function docDownloadUrl(docId: string): string {
  const token = localStorage.getItem("access_token") || "";
  return `/api/v1/documents/${docId}/download?token=${encodeURIComponent(token)}`;
}
