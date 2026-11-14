// Mirrors backend/app/schemas/claim.py and results.py. Keep in sync.

export type ClaimType = "reimbursement" | "cashless";

export type DocumentCategory =
  | "policy"
  | "final_bill"
  | "itemised_bill"
  | "discharge_summary"
  | "prescription"
  | "diagnostic_report"
  | "payment_receipt"
  | "other";

export const DOCUMENT_CATEGORIES: { value: DocumentCategory; label: string }[] = [
  { value: "policy", label: "Insurance policy / schedule" },
  { value: "final_bill", label: "Hospital final bill" },
  { value: "itemised_bill", label: "Itemised bill" },
  { value: "discharge_summary", label: "Discharge summary" },
  { value: "prescription", label: "Prescription" },
  { value: "diagnostic_report", label: "Diagnostic report" },
  { value: "payment_receipt", label: "Payment receipt" },
  { value: "other", label: "Other supporting document" },
];

export interface DocumentOut {
  id: string;
  claim_id: string;
  original_filename: string;
  category: DocumentCategory;
  content_type: string;
  size_bytes: number;
  sha256: string;
  status: "uploaded" | "processing" | "processed" | "failed";
  uploaded_at: string;
  duplicate_of: string | null;
}

export interface ClaimOut {
  id: string;
  domain: "health";
  claim_type: ClaimType;
  status: "created" | "documents_uploaded" | "analyzing" | "analyzed" | "failed";
  created_at: string;
  claimed_amount: number | null;
  patient_name: string | null;
  consent_at: string | null;
  documents: DocumentOut[];
}

export interface RejectedFile {
  filename: string;
  reason: string;
}

export interface UploadResponse {
  uploaded: DocumentOut[];
  rejected: RejectedFile[];
  duplicates: DocumentOut[];
}

export interface ClaimCreate {
  claim_type: ClaimType;
  claimed_amount?: number | null;
  patient_name?: string | null;
  consent_given: boolean;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  providers_configured: { gemini: boolean; groq: boolean; sarvam: boolean };
}
