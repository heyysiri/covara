import { FileText } from "lucide-react";

import { documentFileUrl } from "@/lib/api";
import type { EvidenceRef } from "@/types/results";

/** Opens the original document at the cited page (browser PDF viewer supports #page=N). */
export function EvidenceLink({ claimId, evidence }: { claimId: string; evidence: EvidenceRef }) {
  return (
    <a
      href={`${documentFileUrl(claimId, evidence.document_id)}#page=${evidence.page_number}`}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
      title={evidence.quote ?? undefined}
    >
      <FileText className="size-3" aria-hidden />
      {evidence.filename} · p.{evidence.page_number}
    </a>
  );
}
