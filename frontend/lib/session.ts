/**
 * Session token management with heartbeat.
 *
 * - Token is stored in localStorage so it persists across page navigations.
 * - A heartbeat is sent every 30 seconds to keep the Redis TTL alive.
 * - When the user closes the tab, heartbeats stop and the session
 *   expires after 1 hour of inactivity.
 */

import { createSession, sendHeartbeat } from "./api";

const TOKEN_KEY = "reviewpulse_session_token";
const HEARTBEAT_INTERVAL = 30_000; // 30 seconds

/**
 * Get the current session token from localStorage, or create a new one.
 */
export async function getOrCreateToken(): Promise<string> {
  if (typeof window === "undefined") return "";

  const existing = localStorage.getItem(TOKEN_KEY);
  if (existing) return existing;

  const token = await createSession();
  localStorage.setItem(TOKEN_KEY, token);
  return token;
}

/**
 * Start a heartbeat interval that refreshes the session TTL.
 * Returns a cleanup function to stop the heartbeat.
 */
export function startHeartbeat(token: string): () => void {
  // Send an immediate heartbeat
  sendHeartbeat(token);

  const interval = setInterval(() => {
    sendHeartbeat(token);
  }, HEARTBEAT_INTERVAL);

  // Also refresh on visibility change (user returns to tab)
  const onVisibilityChange = () => {
    if (document.visibilityState === "visible") {
      sendHeartbeat(token);
    }
  };
  document.addEventListener("visibilitychange", onVisibilityChange);

  return () => {
    clearInterval(interval);
    document.removeEventListener("visibilitychange", onVisibilityChange);
  };
}

/**
 * Clear the stored session token (e.g., when starting a fresh analysis).
 */
export function clearToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
}
