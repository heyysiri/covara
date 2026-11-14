import type {
  ClaimOut,
  ClaimType,
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
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
  return res.json() as Promise<T>;
}

export const getHealth = () => request<HealthResponse>("/health");

export const createClaim = (claimType: ClaimType) =>
  request<ClaimOut>("/claims", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ domain: "health", claim_type: claimType }),
  });

export function uploadDocuments(claimId: string, category: DocumentCategory, files: File[]) {
  const form = new FormData();
  form.append("category", category);
  files.forEach((f) => form.append("files", f));
  return request<UploadResponse>(`/claims/${claimId}/documents`, { method: "POST", body: form });
}
