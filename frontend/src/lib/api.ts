import type {
  Action,
  AnalysisResults,
  ChecklistItem,
} from "@/types/results";
import type {
  ClaimCreate,
  ClaimOut,
  DocumentCategory,
  HealthResponse,
  UploadResponse,
} from "@/types/claim";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: unknown,
  ) {
    super(message);
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  } catch {
    throw new ApiError(`Cannot reach the Covara backend at ${API_URL}`, 0);
  }
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      /* non-JSON error body */
    }
    const message = typeof detail === "string" ? detail : `Request failed (${res.status})`;
    throw new ApiError(message, res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const getHealth = () => request<HealthResponse>("/health");

export const createClaim = (payload: ClaimCreate) =>
  request<ClaimOut>("/claims", json("POST", { domain: "health", ...payload }));

export const updateClaim = (claimId: string, payload: { claimed_amount?: number | null; patient_name?: string | null }) =>
  request<ClaimOut>(`/claims/${claimId}`, json("PATCH", payload));

export const deleteClaim = (claimId: string) =>
  request<void>(`/claims/${claimId}`, { method: "DELETE" });

export const getChecklist = (claimId: string) => request<ChecklistItem[]>(`/claims/${claimId}/checklist`);

export const documentFileUrl = (claimId: string, documentId: string) =>
  `${API_URL}/claims/${claimId}/documents/${documentId}/file`;

export const startAnalysis = (claimId: string) =>
  request<AnalysisResults>(`/claims/${claimId}/analyze`, { method: "POST" });

export const getResults = (claimId: string) => request<AnalysisResults>(`/claims/${claimId}/results`);

export interface FieldEdit {
  field_id: string;
  value?: string | number | null;
  confirm?: boolean;
}

export const submitReview = (claimId: string, edits: FieldEdit[], rerun = true) =>
  request<AnalysisResults>(`/claims/${claimId}/review`, json("POST", { edits, rerun }));

export const setActionDone = (claimId: string, actionId: string, done: boolean) =>
  request<Action>(`/claims/${claimId}/actions/${actionId}`, json("PATCH", { done }));

export function uploadDocuments(claimId: string, category: DocumentCategory, files: File[]) {
  const form = new FormData();
  form.append("category", category);
  files.forEach((f) => form.append("files", f));
  return request<UploadResponse>(`/claims/${claimId}/documents`, { method: "POST", body: form });
}
