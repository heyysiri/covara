"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, FileText, Loader2, Sparkles, Trash2, UploadCloud, XCircle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DeleteClaimButton } from "@/features/intake/DeleteClaimButton";
import { Checklist } from "@/features/intake/Checklist";
import { AnalysisView } from "@/features/pipeline/AnalysisView";
import { useAnalysis } from "@/features/pipeline/useAnalysis";
import { ApiError, createClaim, getChecklist, updateClaim, uploadDocuments } from "@/lib/api";
import type { ChecklistItem } from "@/types/results";
import {
  DOCUMENT_CATEGORIES,
  type ClaimType,
  type DocumentCategory,
} from "@/types/claim";

const MAX_MB = 20;
const ALLOWED = [".pdf", ".png", ".jpg", ".jpeg"];

type ItemStatus = "staged" | "uploading" | "uploaded" | "rejected";

interface Item {
  key: string;
  file: File;
  category: DocumentCategory;
  status: ItemStatus;
  error?: string;
  duplicate?: boolean;
}

function validate(file: File): string | null {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ALLOWED.includes(ext)) return "Unsupported type. Use PDF, PNG or JPG.";
  if (file.size > MAX_MB * 1024 * 1024) return `Larger than ${MAX_MB} MB.`;
  if (file.size === 0) return "File is empty.";
  return null;
}

function guessCategory(name: string): DocumentCategory {
  const n = name.toLowerCase();
  if (n.includes("policy")) return "policy";
  if (n.includes("discharge")) return "discharge_summary";
  if (n.includes("itemi")) return "itemised_bill";
  if (n.includes("bill")) return "final_bill";
  if (n.includes("prescription") || n.includes("rx")) return "prescription";
  if (n.includes("report") || n.includes("lab")) return "diagnostic_report";
  if (n.includes("receipt")) return "payment_receipt";
  return "other";
}

export function DocumentUpload() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [claimType, setClaimType] = useState<ClaimType>("reimbursement");
  const [claimId, setClaimId] = useState<string | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [claimedAmount, setClaimedAmount] = useState("");
  const [patientName, setPatientName] = useState("");
  const [consent, setConsent] = useState(false);
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const analysis = useAnalysis(claimId);

  const amountValue = claimedAmount.trim() ? Number(claimedAmount.replace(/[,₹\s]/g, "")) : null;

  useEffect(() => {
    if (!claimId) return;
    getChecklist(claimId).then(setChecklist).catch(() => {});
  }, [claimId, items, analysis.results?.status]);

  function resetAll() {
    setClaimId(null);
    setItems([]);
    setChecklist([]);
    analysis.setResults(null);
  }

  function addFiles(list: FileList | null) {
    if (!list) return;
    const added: Item[] = Array.from(list).map((file) => {
      const problem = validate(file);
      return {
        key: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2)}`,
        file,
        category: guessCategory(file.name),
        status: problem ? "rejected" : "staged",
        error: problem ?? undefined,
      };
    });
    setItems((prev) => [...prev, ...added]);
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
        id = (
          await createClaim({
            claim_type: claimType,
            claimed_amount: amountValue,
            patient_name: patientName.trim() || null,
            consent_given: consent,
          })
        ).id;
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
          const dupNames = new Set(res.duplicates.map((d) => d.original_filename));
          group.forEach((g) => {
            const reason = [...rejected.entries()].find(([name]) => g.file.name.includes(name))?.[1];
            const duplicate = [...dupNames].some((n) => g.file.name.includes(n.replace(/_/g, " ")) || n === g.file.name);
            patch(g.key, reason ? { status: "rejected", error: reason } : { status: "uploaded", duplicate });
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
          <CardTitle>1. Claim details</CardTitle>
          <CardDescription>Health insurance claims are supported in this MVP.</CardDescription>
        </CardHeader>
        <CardContent>
          <label className="sr-only" htmlFor="claim-type">
            Claim type
          </label>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="space-y-1 text-xs font-medium">
              Claim type
              <select
                id="claim-type"
                value={claimType}
                disabled={claimId !== null}
                onChange={(e) => setClaimType(e.target.value as ClaimType)}
                className="h-9 w-full rounded-md border bg-background px-3 text-sm font-normal disabled:opacity-60"
              >
                <option value="reimbursement">Reimbursement</option>
                <option value="cashless">Cashless</option>
              </select>
            </label>
            <label className="space-y-1 text-xs font-medium">
              Amount you are claiming (₹)
              <input
                inputMode="decimal"
                placeholder="e.g. 95000"
                value={claimedAmount}
                onChange={(e) => setClaimedAmount(e.target.value)}
                onBlur={() => {
                  if (claimId && (amountValue === null || !Number.isNaN(amountValue)))
                    updateClaim(claimId, { claimed_amount: amountValue }).catch(() => {});
                }}
                className="h-9 w-full rounded-md border bg-background px-3 text-sm font-normal"
              />
            </label>
            <label className="space-y-1 text-xs font-medium">
              Patient name
              <input
                placeholder="As on the policy"
                value={patientName}
                onChange={(e) => setPatientName(e.target.value)}
                onBlur={() => claimId && updateClaim(claimId, { patient_name: patientName.trim() || null }).catch(() => {})}
                className="h-9 w-full rounded-md border bg-background px-3 text-sm font-normal"
              />
            </label>
          </div>
          <label className="mt-4 flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={consent}
              disabled={claimId !== null}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-0.5 size-4 accent-primary"
            />
            <span>
              I consent to Covara processing these documents to prepare my claim. Documents are read by
              AI providers (Google Gemini, Groq) only to extract claim details, are not used for any
              other purpose, and can be deleted at any time with &quot;Delete my data&quot;.
            </span>
          </label>
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
              addFiles(e.dataTransfer.files);
            }}
            className={`flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
              dragging ? "border-primary bg-muted" : "border-border hover:bg-muted/50"
            }`}
          >
            <UploadCloud className="size-8 text-muted-foreground" aria-hidden />
            <p className="text-sm font-medium">Drag and drop files here, or click to browse</p>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept={ALLOWED.join(",")}
              className="hidden"
              onChange={(e) => {
                addFiles(e.target.files);
                e.target.value = "";
              }}
            />
          </div>

          {items.length > 0 && (
            <ul className="divide-y rounded-lg border">
              {items.map((item) => (
                <li key={item.key} className="flex flex-wrap items-center gap-3 p-3">
                  <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{item.file.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {(item.file.size / 1024).toFixed(0)} KB
                      {item.error && <span className="ml-2 text-destructive">{item.error}</span>}
                      {item.duplicate && (
                        <span className="ml-2 text-amber-600">Same file already uploaded (possible duplicate)</span>
                      )}
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
            <Button onClick={submit} disabled={busy || stagedCount === 0 || !consent}>
              {busy && <Loader2 className="animate-spin" />}
              {claimId ? "Upload more documents" : "Create claim & upload"}
              {stagedCount > 0 && ` (${stagedCount})`}
            </Button>
            {!consent && stagedCount > 0 && (
              <span className="text-xs text-muted-foreground">Tick the consent box above to upload.</span>
            )}
            {claimId && (
              <span className="text-xs text-muted-foreground">
                Claim session <code className="font-mono">{claimId.slice(0, 8)}</code> ·{" "}
                {uploadedCount} uploaded
              </span>
            )}
            {claimId && (
              <span className="ml-auto">
                <DeleteClaimButton claimId={claimId} onDeleted={resetAll} />
              </span>
            )}
          </div>
          {claimId && !analysis.results?.documents.length && <Checklist items={checklist} />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>3. Analyse</CardTitle>
          <CardDescription>
            Covara reads every document, checks it against your policy and builds an action plan.
            Each value links back to the page it came from.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!analysis.results?.documents.length && (
            <Button
              onClick={analysis.start}
              disabled={!claimId || uploadedCount === 0 || analysis.running || busy}
            >
              {analysis.running ? <Loader2 className="animate-spin" /> : <Sparkles />}
              {analysis.running ? "Analysing…" : "Analyse claim"}
            </Button>
          )}
          {analysis.error && (
            <Alert variant="destructive">
              <AlertTitle>Could not analyse</AlertTitle>
              <AlertDescription>{analysis.error}</AlertDescription>
            </Alert>
          )}
          {claimId && analysis.results && (
            <AnalysisView
              claimId={claimId}
              results={analysis.results}
              onRecheck={analysis.start}
              onReview={analysis.review}
              onResults={analysis.setResults}
            />
          )}
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
