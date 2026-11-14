import { API_URL } from "@/lib/api";
import type { EvidenceRef } from "@/types/results";

/** URL of the page image with the cited text highlighted (backend renders it with PyMuPDF). */
export function evidenceImageUrl(
  claimId: string,
  e: Pick<EvidenceRef, "document_id" | "page_number" | "bbox" | "quote">,
  opts: { quote?: string | null; dpi?: number; focus?: boolean } = {},
): string {
  const q = new URLSearchParams();
  const quote = opts.quote === undefined ? e.quote : opts.quote;
  if (quote) q.append("highlight", quote);
  if (e.bbox) q.append("bbox", e.bbox.join(","));
  q.set("dpi", String(opts.dpi ?? 110));
  if (opts.focus) q.set("focus", "true");
  return `${API_URL}/claims/${claimId}/documents/${e.document_id}/pages/${e.page_number}/image?${q}`;
}
