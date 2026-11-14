"use client";

import { FileText } from "lucide-react";

import { useI18n } from "@/i18n";
import { documentFileUrl } from "@/lib/api";
import type { EvidenceRef } from "@/types/results";

/** Opens the original document at the cited page (browser PDF viewer supports #page=N). */
export function EvidenceLink({ claimId, evidence }: { claimId: string; evidence: EvidenceRef }) {
  const { t } = useI18n();
  if (evidence.source === "claim_form" || !evidence.document_id) {
    const claimFormFields: Record<string, string> = {
      claimed_amount: t("claimed amount"),
      patient_name: t("patient name"),
    };
    const fieldLabel = evidence.field ? (claimFormFields[evidence.field] ?? evidence.field.replace(/_/g, " ")) : "";
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <FileText className="size-3" aria-hidden />
        {t("Claim form")}
        {fieldLabel ? ` · ${fieldLabel}` : ""}
        {evidence.value != null ? `: ${evidence.value}` : ""}
      </span>
    );
  }
  return (
    <a
      href={`${documentFileUrl(claimId, evidence.document_id)}#page=${evidence.page_number}`}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
      title={evidence.quote ?? undefined}
    >
      <FileText className="size-3" aria-hidden />
      {evidence.filename} · {t("p.{n}", { n: evidence.page_number ?? "" })}
    </a>
  );
}
