"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/features/flow/AppShell";
import { Onboarding } from "@/features/flow/Onboarding";
import { StepAnalysing } from "@/features/flow/StepAnalysing";
import { StepDetails, type DetailsState } from "@/features/flow/StepDetails";
import { StepDocuments } from "@/features/flow/StepDocuments";
import type { Item } from "@/features/flow/types";
import { AnalysisView } from "@/features/pipeline/AnalysisView";
import { useAnalysis } from "@/features/pipeline/useAnalysis";
import { useI18n, type TFn } from "@/i18n";
import { ApiError, createClaim, deleteDocument, getChecklist, listDocuments, updateClaim, uploadDocuments } from "@/lib/api";
import { ALLOWED_EXTENSIONS, MAX_FILE_MB, collectFromDrop, collectFromInput, type Collected } from "@/lib/ingest";
import { type DocumentCategory, type DocumentOut } from "@/types/claim";
import type { ChecklistItem } from "@/types/results";

type Step = "intro" | "details" | "documents" | "analysing" | "results";
const STEPS: Step[] = ["details", "documents", "analysing", "results"];

function validate(file: File, t: TFn): string | null {
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(ext)) return t("Unsupported type. Use PDF, PNG or JPG.");
  if (file.size > MAX_FILE_MB * 1024 * 1024) return t("Larger than {mb} MB.", { mb: MAX_FILE_MB });
  if (file.size === 0) return t("File is empty.");
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

/** The claim journey as a short sequence of mobile screens: intro, details, documents, checking, results. */
export function ClaimFlow({ initialAmount, source }: { initialAmount?: string; source?: string }) {
  const { t } = useI18n();
  const [step, setStep] = useState<Step>("intro");
  const [details, setDetails] = useState<DetailsState>({ claimType: "reimbursement", amount: initialAmount ?? "", name: "", consent: false });
  const [claimId, setClaimId] = useState<string | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [docs, setDocs] = useState<DocumentOut[]>([]);
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [notice, setNotice] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const analysis = useAnalysis(claimId);

  const amount = details.amount.trim() ? Number(details.amount.replace(/[,₹\s]/g, "")) : null;
  const status = analysis.results?.status;

  // Keep the checklist and document list fresh while a claim exists.
  useEffect(() => {
    if (!claimId) return;
    getChecklist(claimId).then(setChecklist).catch(() => {});
    listDocuments(claimId).then(setDocs).catch(() => {});
  }, [claimId, items, status]);

  // The waiting screen turns into the results as soon as the analysis finishes (or fails): derived, not stored.
  const shown: Step = step === "analysing" && (status === "complete" || status === "failed") ? "results" : step;

  function addCollected(c: Collected) {
    const added: Item[] = c.files.map(({ file, path }) => {
      const problem = validate(file, t);
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
        c.skipped === 1
          ? t("Ignored 1 hidden, system or unsupported file found in the folder or zip.")
          : t("Ignored {n} hidden, system or unsupported files found in the folder or zip.", { n: c.skipped }),
      );
    }
    if (added.length === 0 && lines.length === 0) lines.push(t("No documents found."));
    setNotice(lines);
  }

  const patch = (key: string, p: Partial<Item>) => setItems((prev) => prev.map((i) => (i.key === key ? { ...i, ...p } : i)));

  /** "Continue" on the details screen: create the claim (this records consent) or update its amount and name. */
  async function saveDetails() {
    setError(null);
    setBusy(true);
    try {
      if (!claimId) {
        const created = await createClaim({
          claim_type: details.claimType,
          claimed_amount: amount !== null && !Number.isNaN(amount) ? amount : null,
          patient_name: details.name.trim() || null,
          consent_given: details.consent,
        });
        setClaimId(created.id);
      } else {
        await updateClaim(claimId, { claimed_amount: amount !== null && !Number.isNaN(amount) ? amount : null, patient_name: details.name.trim() || null });
      }
      setStep("documents");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("Something went wrong."));
    } finally {
      setBusy(false);
    }
  }

  /** Upload everything staged, one request per category. Returns true if nothing is left staged. */
  async function uploadStaged(id: string): Promise<boolean> {
    const pending = items.filter((i) => i.status === "staged");
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
        const msg = e instanceof ApiError ? e.message : t("Upload failed.");
        group.forEach((g) => patch(g.key, { status: "rejected", error: msg }));
        return false;
      }
    }
    return true;
  }

  async function checkClaim() {
    if (!claimId) return;
    setError(null);
    setBusy(true);
    try {
      if (!(await uploadStaged(claimId))) {
        setError(t("Some files could not be uploaded. Remove them or try again."));
        return;
      }
      const have = await listDocuments(claimId);
      if (have.length === 0) {
        setError(t("Add at least one document first."));
        return;
      }
      setStep("analysing");
      analysis.start();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("Something went wrong."));
    } finally {
      setBusy(false);
    }
  }

  async function removeDoc(id: string) {
    if (!claimId) return;
    try {
      await deleteDocument(claimId, id);
      setDocs((d) => d.filter((x) => x.id !== id));
      getChecklist(claimId).then(setChecklist).catch(() => {});
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("Could not remove the document."));
    }
  }

  function startOver() {
    setClaimId(null);
    setItems([]);
    setDocs([]);
    setChecklist([]);
    setNotice([]);
    setDetails({ claimType: "reimbursement", amount: "", name: "", consent: false });
    analysis.setResults(null);
    setStep("intro");
  }

  const index = STEPS.indexOf(shown) + 1;
  const stepInfo = index > 0 ? { index: Math.min(index, 3), total: 3 } : undefined;

  if (shown === "intro")
    return (
      <AppShell title={t("Claim readiness")} backHref="/">
        <Onboarding onStart={() => setStep("details")} />
      </AppShell>
    );

  if (shown === "details")
    return (
      <AppShell title={t("Claim details")} onBack={() => setStep("intro")} step={stepInfo}>
        <StepDetails value={details} onChange={setDetails} locked={claimId !== null} fromPayment={source === "payment" && details.amount === initialAmount} busy={busy} error={error} onContinue={saveDetails} />
      </AppShell>
    );

  if (shown === "documents")
    return (
      <AppShell title={t("Your documents")} onBack={() => setStep("details")} step={stepInfo}>
        <StepDocuments
          items={items}
          docs={docs}
          checklist={checklist}
          notice={notice}
          error={error}
          busy={busy}
          running={analysis.running}
          onFiles={(list) => list && list.length > 0 && void collectFromInput(list).then(addCollected)}
          onDropData={(dt) => void collectFromDrop(dt).then(addCollected)}
          onCategory={(key, category) => patch(key, { category })}
          onRemoveItem={(key) => setItems((prev) => prev.filter((i) => i.key !== key))}
          onRemoveDoc={removeDoc}
          onCheck={checkClaim}
        />
      </AppShell>
    );

  if (shown === "analysing")
    return (
      <AppShell title={t("Checking your claim")} step={stepInfo}>
        <StepAnalysing results={analysis.results} />
      </AppShell>
    );

  return (
    <AppShell title={t("Your claim check")} onBack={() => setStep("documents")} step={stepInfo} padBottom wide>
      {analysis.error && <p className="mb-3 rounded-xl border border-destructive/40 bg-red-50 p-3 text-sm text-destructive">{analysis.error}</p>}
      {claimId && analysis.results && (
        <AnalysisView
          claimId={claimId}
          results={analysis.results}
          onRecheck={analysis.start}
          onReview={analysis.review}
          onResults={analysis.setResults}
          onAddDocuments={() => setStep("documents")}
          onDeleted={startOver}
        />
      )}
    </AppShell>
  );
}
