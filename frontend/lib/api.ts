// Talks to the backend. Each exported function is one API endpoint.
import type { Category, ReviewGroup, Row, Session, Summary, UserRule } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// The backend sends every error as { error: { code, message, details } }.
// We turn that into an ApiError so the page can show error.message to the user.
export class ApiError extends Error {
  code: string;
  status: number;

  constructor(code: string, message: string, status = 0) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

// Reads the error out of a failed response.
export async function toApiError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    if (body.error) {
      return new ApiError(body.error.code, body.error.message, res.status);
    }
  } catch {
    // The body was not JSON. Fall through to a generic message.
  }
  return new ApiError("http_error", `Request failed (HTTP ${res.status})`, res.status);
}

// Sends one request. Returns the JSON body, or throws an ApiError.
async function callApi(path: string, options: RequestInit = {}) {
  let res: Response;
  try {
    res = await fetch(API_URL + path, options);
  } catch {
    throw new ApiError("network_error", `Cannot reach the API at ${API_URL}. Is the backend running?`);
  }
  if (!res.ok) {
    throw await toApiError(res);
  }
  return res.json();
}

// Options for a request that sends a JSON body.
function withJsonBody(method: string, body: object): RequestInit {
  return {
    method: method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function getCategories(): Promise<Category[]> {
  return callApi("/api/categories");
}

export function uploadStatement(file: File, taxYear?: number): Promise<Session> {
  const form = new FormData();
  form.append("files", file);
  if (taxYear) {
    form.append("tax_year", String(taxYear));
  }
  return callApi("/api/sessions", { method: "POST", body: form });
}

export function getTransactions(sessionId: string): Promise<Row[]> {
  return callApi(`/api/sessions/${sessionId}/transactions`);
}

export function getReviewGroups(sessionId: string): Promise<ReviewGroup[]> {
  return callApi(`/api/sessions/${sessionId}/review`);
}

export function getSummary(sessionId: string): Promise<Summary> {
  return callApi(`/api/sessions/${sessionId}/summary`);
}

// Changes one row's category and/or business-use %. The backend marks it as decided by the user.
export function updateTransaction(
  sessionId: string,
  transactionId: string,
  changes: { category?: string; business_pct?: number },
): Promise<Row> {
  return callApi(`/api/sessions/${sessionId}/transactions/${transactionId}`, withJsonBody("PATCH", changes));
}

// Changes several rows at once (e.g. a whole Needs Review group). The backend applies all of them or none,
// so a failure never leaves a group half-fixed.
export function updateTransactions(
  sessionId: string,
  transactionIds: string[],
  changes: { category?: string; business_pct?: number },
): Promise<Row[]> {
  const body = { transaction_ids: transactionIds, ...changes };
  return callApi(`/api/sessions/${sessionId}/transactions`, withJsonBody("PATCH", body));
}

// "Always categorize MERCHANT as CATEGORY". The backend also updates the rows already uploaded.
export function saveAlwaysRule(sessionId: string, merchantKey: string, category: string): Promise<UserRule> {
  const body = { merchant_key: merchantKey, category: category, apply_to_existing: true };
  return callApi(`/api/sessions/${sessionId}/rules`, withJsonBody("POST", body));
}

export function exportUrl(sessionId: string): string {
  return `${API_URL}/api/sessions/${sessionId}/export.csv`;
}
