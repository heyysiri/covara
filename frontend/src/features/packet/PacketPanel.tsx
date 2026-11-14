"use client";

import { CheckCircle2, FileJson, FileText, Package, XCircle } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useI18n, useLocalized } from "@/i18n";
import { API_URL } from "@/lib/api";
import { DOCUMENT_CATEGORIES } from "@/types/claim";
import type { AnalysisResults } from "@/types/results";

// Order and names come from the shared document categories, not a second list.
const ORDER = DOCUMENT_CATEGORIES.map((c) => c.value as string);
const LABEL = Object.fromEntries(DOCUMENT_CATEGORIES.map((c) => [c.value, c.label]));

function Download({ href, icon: Icon, title, text, disabled }: { href: string; icon: typeof FileText; title: string; text: string; disabled: boolean }) {
  const cls = cn(
    buttonVariants({ variant: "outline" }),
    "h-auto w-full flex-col items-start gap-1 whitespace-normal rounded-2xl bg-card p-4 text-left",
    disabled && "pointer-events-none opacity-50",
  );
  return (
    <a href={disabled ? undefined : href} download className={cls} aria-disabled={disabled}>
      <span className="flex items-center gap-2 font-medium">
        <Icon aria-hidden /> {title}
      </span>
      <span className="text-xs font-normal text-muted-foreground">{text}</span>
    </a>
  );
}

/** The claim packet: status, what is blocking it, what it contains, and the downloads. */
export function PacketPanel({ claimId, results }: { claimId: string; results: AnalysisResults }) {
  const { t } = useI18n();
  const ready = results.status === "complete";
  const incomplete = (results.packet_status ?? "").toUpperCase().startsWith("INCOMPLETE");
  const blocking = results.findings.filter((f) => f.blocking && f.status === "open");
  // A document another file refers to already has its own finding; only list plain missing documents here.
  const missing = results.checklist.filter((c) => c.required && !c.received && !c.evidence);
  const docs = [...results.documents].sort((a, b) => ORDER.indexOf(a.doc_type) - ORDER.indexOf(b.doc_type));
  const base = `${API_URL}/claims/${claimId}`;
  const [statusL, disclaimerL, ...blockingL] = useLocalized([results.packet_status ?? "", results.disclaimer, ...blocking.map((f) => f.title)]);

  return (
    <div className="space-y-5">
      <div
        className={`flex items-start gap-3 rounded-lg border p-4 ${
          incomplete ? "border-destructive/40 bg-destructive/5" : "border-emerald-600/40 bg-emerald-600/5"
        }`}
      >
        {incomplete ? <XCircle className="mt-0.5 size-5 shrink-0 text-destructive" aria-hidden /> : <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-600" aria-hidden />}
        <div className="space-y-1">
          <p className="font-semibold">{results.packet_status ? statusL : t("Run the analysis to prepare the packet")}</p>
          <p className="text-sm text-muted-foreground">
            {incomplete
              ? t("You can download a draft now. While blocking items are open, every page is stamped INCOMPLETE so it is not mistaken for a finished packet.")
              : t("No blocking items are open. Items marked 'to review' are worth a look, and the insurer makes the final decision.")}
          </p>
        </div>
      </div>

      {(blocking.length > 0 || missing.length > 0) && (
        <div className="rounded-lg border p-3">
          <p className="mb-1.5 text-sm font-medium">{t("What is blocking the packet")}</p>
          <ul className="list-disc space-y-0.5 pl-5 text-sm">
            {blocking.map((f, i) => (
              <li key={f.id}>{blockingL[i]}</li>
            ))}
            {missing.map((c) => (
              <li key={c.category}>{t("Missing document: {name}", { name: LABEL[c.category] ? t(LABEL[c.category]) : c.label })}</li>
            ))}
          </ul>
          <p className="mt-1.5 text-xs text-muted-foreground">{t("Fix these, then press Re-check. The status updates and the stamp is removed.")}</p>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-3">
        <Download href={`${base}/packet`} icon={Package} title={t("Claim packet (PDF)")} disabled={!ready}
          text={t("One file: cover and summary, document index, evidence references, then your original documents with bookmarks.")} />
        <Download href={`${base}/report`} icon={FileText} title={t("Readiness report (PDF)")} disabled={!ready}
          text={t("What was checked, what was found, the policy clauses involved and your next steps. For you, not the insurer.")} />
        <Download href={`${base}/packet.json`} icon={FileJson} title="claim.json" disabled={!ready}
          text={t("The same facts as structured data, laid out so they can later map to a standard health-claims exchange.")} />
      </div>

      <div className="rounded-lg border p-3">
        <p className="mb-1.5 text-sm font-medium">{t("The packet contains, in this order")}</p>
        <ol className="list-decimal space-y-0.5 pl-5 text-sm">
          <li>{t("Cover page, claim summary and document index")}</li>
          <li>{t("Evidence references: where each flagged point sits in your documents")}</li>
          {docs.map((d) => (
            <li key={d.id}>
              {LABEL[d.doc_type] ? t(LABEL[d.doc_type]) : d.doc_type} <span className="text-muted-foreground">· {d.filename}</span>
            </li>
          ))}
        </ol>
      </div>

      <p className="text-xs text-muted-foreground">{disclaimerL}</p>
    </div>
  );
}
