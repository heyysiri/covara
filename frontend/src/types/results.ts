// Mirrors backend/app/schemas/results.py (shared contract). Keep in sync.
import type { DocumentCategory } from "./claim";

export type DocType = DocumentCategory;
export type Severity = "low" | "medium" | "high";
export type RunStatus = "idle" | "processing" | "awaiting_review" | "complete" | "failed";
export type ReadinessStatus = "ready" | "needs_attention" | "incomplete";
export type ClauseType = "coverage" | "exclusion" | "sublimit" | "waiting_period" | "condition" | "definition";
export type Owner = "user" | "hospital" | "doctor" | "insurer";
export type ActionGroup = "upload" | "verify_or_correct" | "policy_review" | "consistent" | "ask_insurer";

/** A page of an uploaded document, or a value from the claim form (source = "claim_form"). */
export interface EvidenceRef {
  source: "document" | "claim_form" | "checklist";
  document_id: string | null;
  filename: string | null;
  page_number: number | null;
  bbox: [number, number, number, number] | null;
  quote: string | null;
  field?: string | null; // claim_form / checklist only, e.g. "claimed_amount"
  value?: string | number | null; // claim_form / checklist only
}

export interface ExtractedField {
  id: string;
  key: string;
  value: string | number | null;
  raw_text: string | null;
  confidence: number;
  evidence: EvidenceRef;
  user_confirmed: boolean;
  method: "gemini" | "groq" | "sarvam" | "rules" | "user";
}

export interface PolicyClause {
  id: string;
  clause_ref: string;
  type: ClauseType;
  title: string;
  text: string;
  document_id: string;
  filename: string;
  page_number: number;
}

export interface SummaryValue {
  value: number | string | null;
  text: string;
  evidence: EvidenceRef;
}

export interface WaitingPeriod {
  name: string;
  days: number;
  evidence: EvidenceRef;
}

export interface PolicySummary {
  sum_insured: SummaryValue | null;
  room_rent_cap: SummaryValue | null;
  room_rent_cap_percent: number | null;
  copay: SummaryValue | null;
  pre_hosp_days: SummaryValue | null;
  post_hosp_days: SummaryValue | null;
  waiting_periods: WaitingPeriod[];
  exclusions: SummaryValue[];
}

export interface ClauseLink {
  clause_id: string;
  verdict: "applies" | "may_apply" | "does_not_apply";
  quote: string;
}

export interface Finding {
  id: string;
  rule_id: string;
  issue_type: string;
  severity: Severity;
  kind: "confirmed" | "possible";
  title: string;
  description: string;
  evidence: EvidenceRef[];
  extracted_value: string | null;
  comparison_value: string | null;
  clause_links: ClauseLink[];
  exposure_amount: number | null;
  blocking: boolean;
  explanation: { rule: string; inputs: Record<string, unknown>; why_it_matters: string };
  requires_human_review: boolean;
  status: "open" | "acknowledged" | "resolved";
}

export interface Action {
  id: string;
  title: string;
  why: string;
  how: string[];
  owner: Owner;
  blocking: boolean;
  group: ActionGroup;
  finding_ids: string[];
  clause_ids: string[];
  checklist_category: string | null;
  draft_message: string | null;
  done: boolean;
}

export interface ChecklistItem {
  category: DocType;
  label: string;
  required: boolean;
  received: boolean;
  document_ids: string[];
  reason: string;
  evidence: EvidenceRef | null;
}

export interface ChecklistSummary {
  required_present: string[];
  required_missing: string[];
  referenced_but_missing: string[];
}

export interface DocumentResult {
  id: string;
  filename: string;
  category: DocType;
  doc_type: DocType;
  detected_type: DocType | null;
  status: "pending" | "processed" | "failed";
  pages: number;
  has_text_layer: boolean;
  extraction_method: string | null;
  error: string | null;
}

export interface LlmCall {
  provider: string;
  model: string;
  task: string;
  cached: boolean;
  latency_ms: number;
  ok: boolean;
  error: string | null;
}

export interface AnalysisResults {
  claim_id: string;
  status: RunStatus;
  stage: string;
  progress: number;
  stages: string[];
  readiness_status: ReadinessStatus | null;
  readiness_explanation: string;
  documents: DocumentResult[];
  fields: ExtractedField[];
  findings: Finding[];
  clauses: PolicyClause[];
  policy_summary: PolicySummary | null;
  action_plan: Action[];
  checklist: ChecklistItem[];
  checklist_summary: ChecklistSummary;
  checks_passed: string[];
  documents_failed: string[];
  providers_used: string[];
  llm_calls: LlmCall[];
  warnings: string[];
  packet_status: string | null;
  error: string | null;
  disclaimer: string;
}

export const CRITICAL_KEYS = new Set([
  "patient_name", "policyholder_name", "policy_number", "member_id", "admission_date",
  "discharge_date", "bill_total", "bill_number", "policy_start", "policy_end", "receipt_amount",
]);
export const REVIEW_THRESHOLD = 0.75;

export const FIELD_LABELS: Record<string, string> = {
  patient_name: "Patient name",
  age: "Age",
  policyholder_name: "Policyholder",
  member_id: "Member ID",
  insurer: "Insurer",
  policy_number: "Policy number",
  policy_start: "Policy start",
  policy_end: "Policy end",
  sum_insured: "Sum insured",
  room_rent_cap: "Room-rent limit",
  room_rent_charged_per_day: "Room rent charged / day",
  waiting_period: "Waiting period",
  hospital_name: "Hospital",
  admission_date: "Admission date",
  discharge_date: "Discharge date",
  diagnosis: "Diagnosis",
  diagnosis_date: "Diagnosis date",
  treatment: "Treatment",
  bill_number: "Bill number",
  bill_date: "Bill date",
  bill_total: "Bill total",
  line_item: "Line item",
  billed_item: "Billed item",
  prescribed_item: "Prescribed item",
  receipt_amount: "Amount received",
  receipt_date: "Receipt date",
  referenced_document: "Refers to",
};
