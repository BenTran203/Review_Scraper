/**
 * API client for the ReviewPulse Go gateway.
 *
 * IMPORTANT: The frontend NEVER contacts OpenAI directly.
 * All AI calls are proxied through the Go gateway server-side.
 * No API keys are exposed to the browser.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

// --- Types ---

export interface SessionData {
  token: string;
  url: string;
  platform: string;
  status: string;
  output_language: string;
  error_message?: string;
  created_at: string;
}

export interface AnalysisResult {
  summary: string;
  pros: string[];
  cons: string[];
  sentiment: {
    positive: number;
    neutral: number;
    negative: number;
  };
  keywords: string[];
  language: string;
}

export interface SessionResponse {
  session: SessionData;
  analysis?: AnalysisResult;
}

// --- API Calls ---

export async function analyzeUrl(
  url: string,
  outputLanguage: string,
  sessionToken: string,
): Promise<{ token: string; status: string; platform: string }> {
  const resp = await fetch(`${API_URL}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url,
      output_language: outputLanguage,
      session_token: sessionToken,
    }),
  });

  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.error || `Request failed (${resp.status})`);
  }

  return resp.json();
}

export async function getSession(token: string): Promise<SessionResponse> {
  const resp = await fetch(`${API_URL}/api/session/${token}`);

  if (!resp.ok) {
    throw new Error("Session not found or expired");
  }

  return resp.json();
}

export async function sendHeartbeat(token: string): Promise<void> {
  await fetch(`${API_URL}/api/session/${token}/heartbeat`, {
    method: "POST",
  }).catch(() => {
    // Heartbeat failures are non-critical
  });
}

export async function createSession(): Promise<string> {
  const resp = await fetch(`${API_URL}/api/session`, {
    method: "POST",
  });

  if (!resp.ok) {
    throw new Error("Failed to create session");
  }

  const data = await resp.json();
  return data.token;
}
