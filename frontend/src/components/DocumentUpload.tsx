"use client";

import { useRef, useState } from "react";
import {
  CheckCircle2,
  FileArchive,
  FileText,
  FolderOpen,
  Loader2,
  Trash2,
  UploadCloud,
  XCircle,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, createClaim, uploadDocuments } from "@/lib/api";
import {
  ALLOWED_EXTENSIONS,
  MAX_FILE_MB,
  collectFromDrop,
  collectFromInput,
  type Collected,
} from "@/lib/ingest";
import {
  DOCUMENT_CATEGORIES,
  type ClaimType,
  type DocumentCategory,
} from "@/types/claim";

const MAX_MB = MAX_FILE_MB;
const ALLOWED = ALLOWED_EXTENSIONS;

type ItemStatus = "staged" | "uploading" | "uploaded" | "rejected";

interface Item {
  key: string;
  file: File;
  /** Folder/zip path for display, e.g. "claim_b/medical/final_bill.pdf". */
  path: string;
  category: DocumentCategory;
  status: ItemStatus;
  error?: string;
}

function validate(file: File): string | null {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ALLOWED.includes(ext)) return "Unsupported type. Use PDF, PNG or JPG.";
  if (file.size > MAX_MB * 1024 * 1024) return `Larger than ${MAX_MB} MB.`;
  if (file.size === 0) return "File is empty.";
  return null;
}

function guessFrom(text: string): DocumentCategory {
  const n = text.toLowerCase();
  if (n.includes("policy")) return "policy";
  if (n.includes("discharge")) return "discharge_summary";
  if (n.includes("itemi")) return "itemised_bill";
  if (n.includes("bill")) return "final_bill";
  if (n.includes("prescription") || n.includes("rx")) return "prescription";
  if (n.includes("report") || n.includes("lab")) return "diagnostic_report";
  if (n.includes("receipt")) return "payment_receipt";
  return "other";
}

// File name first; fall back to the folder path (e.g. a "policy/" folder) when the name says nothing.
function guessCategory(name: string, path: string): DocumentCategory {
  const byName = guessFrom(name);
  return byName !== "other" ? byName : guessFrom(path);
}

export function DocumentUpload() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [claimType, setClaimType] = useState<ClaimType>("reimbursement");
  const [claimId, setClaimId] = useState<string | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [notice, setNotice] = useState<string[]>([]);
  const folderRef = useRef<HTMLInputElement>(null);
  const zipRef = useRef<HTMLInputElement>(null);

  // Files, folders and .zip archives all end up here as a flat list of documents.
  function addCollected(c: Collected) {
    const added: Item[] = c.files.map(({ file, path }) => {
      const problem = validate(file);
      return {
        key: `${path}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2)}`,
        file,
        path,
        category: guessCategory(file.name, path),
        status: problem ? "rejected" : "staged",
        error: problem ?? undefined,
      };
    });
    setItems((prev) => [...prev, ...added]);
    const lines = [...c.problems];
    if (c.skipped > 0) {
      lines.push(
        `Ignored ${c.skipped} hidden, system or unsupported file${c.skipped === 1 ? "" : "s"} found in the folder or zip.`,
      );
    }
    if (added.length === 0 && lines.length === 0) lines.push("No documents found.");
    setNotice(lines);
  }

  function fromInput(list: FileList | null) {
    if (!list || list.length === 0) return;
    void collectFromInput(list).then(addCollected);
  }

  const patch = (key: string, p: Partial<Item>) =>
    setItems((prev) => prev.map((i) => (i.key === key ? { ...i, ...p } : i)));

  async function submit() {
    setError(null);
    const pending = items.filter((i) => i.status === "staged");
    if (pending.length === 0) return;
    setBusy(true);
    try {
      let id = claimId;
      if (!id) {
        id = (await createClaim(claimType)).id;
        setClaimId(id);
      }
      // One request per category.
      const byCategory = new Map<DocumentCategory, Item[]>();
      pending.forEach((i) => byCategory.set(i.category, [...(byCategory.get(i.category) ?? []), i]));
      for (const [category, group] of byCategory) {
        group.forEach((i) => patch(i.key, { status: "uploading" }));
        try {
          const res = await uploadDocuments(id, category, group.map((g) => g.file));
          const rejected = new Map(res.rejected.map((r) => [r.filename, r.reason]));
          group.forEach((g) => {
            const reason = [...rejected.entries()].find(([name]) => g.file.name.includes(name))?.[1];
            patch(g.key, reason ? { status: "rejected", error: reason } : { status: "uploaded" });
          });
        } catch (e) {
          const msg = e instanceof ApiError ? e.message : "Upload failed.";
          group.forEach((g) => patch(g.key, { status: "rejected", error: msg }));
        }
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong.");
      setItems((prev) => prev.map((i) => (i.status === "uploading" ? { ...i, status: "staged" } : i)));
    } finally {
      setBusy(false);
    }
  }

  const stagedCount = items.filter((i) => i.status === "staged").length;
  const uploadedCount = items.filter((i) => i.status === "uploaded").length;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>1. Claim type</CardTitle>
          <CardDescription>Health insurance claims are supported in this MVP.</CardDescription>
        </CardHeader>
        <CardContent>
          <label className="sr-only" htmlFor="claim-type">
            Claim type
          </label>
          <select
            id="claim-type"
            value={claimType}
            disabled={claimId !== null}
            onChange={(e) => setClaimType(e.target.value as ClaimType)}
            className="h-9 w-full max-w-xs rounded-md border bg-background px-3 text-sm disabled:opacity-60"
          >
            <option value="reimbursement">Reimbursement</option>
            <option value="cashless">Cashless</option>
          </select>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2. Upload documents</CardTitle>
          <CardDescription>
            PDF, PNG or JPG, up to {MAX_MB} MB each. Include your policy, bills, discharge summary,
            prescriptions, reports and receipts. Use synthetic or demo documents only.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div
            role="button"
            tabIndex={0}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              void collectFromDrop(e.dataTransfer).then(addCollected);
            }}
            className={`flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
              dragging ? "border-primary bg-muted" : "border-border hover:bg-muted/50"
            }`}
          >
            <UploadCloud className="size-8 text-muted-foreground" aria-hidden />
            <p className="text-sm font-medium">Drop files, a folder or a .zip here, or click to browse</p>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept={[...ALLOWED, ".zip"].join(",")}
              className="hidden"
              onChange={(e) => {
                fromInput(e.target.files);
                e.target.value = "";
              }}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" size="sm" onClick={() => folderRef.current?.click()}>
              <FolderOpen /> Choose folder
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={() => zipRef.current?.click()}>
              <FileArchive /> Choose .zip
            </Button>
            <span className="text-xs text-muted-foreground">
              Zips and folders are opened in your browser; only the PDF/PNG/JPG documents inside are uploaded.
            </span>
            {/* webkitdirectory lets the user pick a whole folder (supported by all major browsers) */}
            <input
              ref={folderRef}
              type="file"
              className="hidden"
              onChange={(e) => {
                fromInput(e.target.files);
                e.target.value = "";
              }}
              {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
            />
            <input
              ref={zipRef}
              type="file"
              accept=".zip,application/zip"
              className="hidden"
              onChange={(e) => {
                fromInput(e.target.files);
                e.target.value = "";
              }}
            />
          </div>

          {notice.length > 0 && (
            <Alert>
              <AlertTitle>Heads up</AlertTitle>
              <AlertDescription>
                {notice.map((line) => (
                  <p key={line}>{line}</p>
                ))}
              </AlertDescription>
            </Alert>
          )}

          {items.length > 0 && (
            <ul className="divide-y rounded-lg border">
              {items.map((item) => (
                <li key={item.key} className="flex flex-wrap items-center gap-3 p-3">
                  <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{item.file.name}</p>
                    {item.path !== item.file.name && (
                      <p className="truncate text-xs text-muted-foreground">{item.path}</p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      {(item.file.size / 1024).toFixed(0)} KB
                      {item.error && <span className="ml-2 text-destructive">{item.error}</span>}
                    </p>
                  </div>
                  <select
                    aria-label={`Category for ${item.file.name}`}
                    value={item.category}
                    disabled={item.status !== "staged"}
                    onChange={(e) => patch(item.key, { category: e.target.value as DocumentCategory })}
                    className="h-8 rounded-md border bg-background px-2 text-xs disabled:opacity-60"
                  >
                    {DOCUMENT_CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                  <StatusIcon status={item.status} />
                  {(item.status === "staged" || item.status === "rejected") && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`Remove ${item.file.name}`}
                      onClick={() => setItems((prev) => prev.filter((i) => i.key !== item.key))}
                    >
                      <Trash2 />
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}

          {error && (
            <Alert variant="destructive">
              <AlertTitle>Could not upload</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={submit} disabled={busy || stagedCount === 0}>
              {busy && <Loader2 className="animate-spin" />}
              {claimId ? "Upload more documents" : "Create claim & upload"}
              {stagedCount > 0 && ` (${stagedCount})`}
            </Button>
            {claimId && (
              <span className="text-xs text-muted-foreground">
                Claim session <code className="font-mono">{claimId.slice(0, 8)}</code> ·{" "}
                {uploadedCount} uploaded
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>3. Analyse</CardTitle>
          <CardDescription>
            Extraction, cross-document checks and the claim-readiness report arrive in the next
            phases.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button disabled>Analyse claim (coming soon)</Button>
        </CardContent>
      </Card>
    </div>
  );
}

function StatusIcon({ status }: { status: ItemStatus }) {
  if (status === "uploading") return <Loader2 className="size-4 animate-spin" aria-label="Uploading" />;
  if (status === "uploaded")
    return <CheckCircle2 className="size-4 text-emerald-600" aria-label="Uploaded" />;
  if (status === "rejected") return <XCircle className="size-4 text-destructive" aria-label="Rejected" />;
  return <span className="text-xs text-muted-foreground">Ready</span>;
}
