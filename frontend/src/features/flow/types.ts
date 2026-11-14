import type { DocumentCategory } from "@/types/claim";

export type ItemStatus = "staged" | "uploading" | "uploaded" | "rejected";

/** A file the user picked that is not yet (or has just been) uploaded. */
export interface Item {
  key: string;
  file: File;
  /** Folder/zip path for display, e.g. "claim_b/medical/final_bill.pdf". */
  path: string;
  category: DocumentCategory;
  status: ItemStatus;
  error?: string;
  duplicate?: boolean;
}
