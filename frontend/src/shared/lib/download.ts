import { useSessionStore } from "../../auth/session.store";

/**
 * Downloads a file from an authenticated or pre-signed URL.
 * Injects the Bearer Authorization header if an access token is present,
 * receives the blob, and triggers a browser file download.
 */
export async function downloadFromUrl(url: string, filename: string): Promise<void> {
  const token = useSessionStore.getState().accessToken;
  const headers: HeadersInit = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    method: "GET",
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`Failed to download file: ${response.status} ${response.statusText}`);
  }

  const blob = await response.blob();
  const blobUrl = window.URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = filename;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();

  // Cleanup after trigger
  setTimeout(() => {
    document.body.removeChild(link);
    window.URL.revokeObjectURL(blobUrl);
  }, 100);
}
