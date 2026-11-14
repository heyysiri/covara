"use client";

import { useState } from "react";
import { CheckCircle2, Download as Download_, FileText, Loader2, Package, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import { useI18n, useLocalized } from "@/i18n";
import { API_URL } from "@/lib/api";
import { DOCUMENT_CATEGORIES } from "@/types/claim";
import type { AnalysisResults } from "@/types/results";

// Order and names come from the shared document categories, not a second list.
const ORDER = DOCUMENT_CATEGORIES.map((c) => c.value as string);
const LABEL = Object.fromEntries(DOCUMENT_CATEGORIES.map((c) => [c.value, c.label]));

function Download({ href, icon: Icon, title, text, disabled }: { href: string; icon: typeof FileText; title: string; text: string; disabled: boolean }) {
  return (
    <a
      href={disabled ? undefined : href}
      download
      aria-disabled={disabled}
      className={cn("flex items-center gap-3 rounded-2xl border bg-card p-4 transition-colors hover:bg-secondary/60", disabled && "pointer-events-none opacity-50")}
    >
      <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-secondary text-navy">
        <Icon className="size-5" aria-hidden />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-semibold text-navy">{title}</span>
        <span className="block text-sm text-muted-foreground">{text}</span>
      </span>
      <Download_ className="size-5 shrink-0 text-navy" aria-hidden />
    </a>
  );
}

/** The claim packet: one status card, two downloads, and a collapsed list of what is inside. */
export function PacketPanel({ claimId, results }: { claimId: string; results: AnalysisResults }) {
  const { t, lang } = useI18n();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const ready = results.status === "complete";
  const incomplete = (results.packet_status ?? "").toUpperCase().startsWith("INCOMPLETE");
  const blocking = results.findings.filter((f) => f.blocking && f.status === "open");
  // A document another file refers to already has its own finding; only list plain missing documents here.
  const missing = results.checklist.filter((c) => c.required && !c.received && !c.evidence);
  const docs = [...results.documents].sort((a, b) => ORDER.indexOf(a.doc_type) - ORDER.indexOf(b.doc_type));
  const base = `${API_URL}/claims/${claimId}`;
  const [statusL, ...blockingL] = useLocalized([results.packet_status ?? "", ...blocking.map((f) => f.title)]);

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <section className={`rounded-2xl border p-4 ${incomplete ? "border-destructive/30 bg-red-50" : "border-emerald-500/40 bg-emerald-50"}`}>
        <div className="flex items-center gap-2.5">
          {incomplete ? <XCircle className="size-6 shrink-0 text-destructive" aria-hidden /> : <CheckCircle2 className="size-6 shrink-0 text-emerald-600" aria-hidden />}
          <h2 className="text-lg font-semibold text-navy">{results.packet_status ? statusL : t("Run the analysis to prepare the packet")}</h2>
        </div>
        {(blocking.length > 0 || missing.length > 0) && (
          <ul className="mt-3 space-y-1.5 text-sm">
            {blocking.map((f, i) => (
              <li key={f.id} className="flex gap-2">
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-destructive" /> {blockingL[i]}
              </li>
            ))}
            {missing.map((c) => (
              <li key={c.category} className="flex gap-2">
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-destructive" />
                {t("Missing document: {name}", { name: LABEL[c.category] ? t(LABEL[c.category]) : c.label })}
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-xs text-muted-foreground">
          {incomplete ? t("Fix these, then press Re-check. A draft is stamped INCOMPLETE until then.") : t("No blocking items are open. The insurer makes the final decision.")}
        </p>
      </section>

      <div className="grid gap-3">
        <Download href={`${base}/packet`} icon={Package} title={t("Claim packet")} disabled={!ready} text={t("Summary, evidence and your documents in one PDF")} />
        <button
          type="button"
          disabled={!ready || busy}
          onClick={async () => {
            setBusy(true);
            setErr(null);
            try {
              const res = await fetch(`${base}/report?lang=${lang}`);
              if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? "failed");
              const url = URL.createObjectURL(await res.blob());
              const a = document.createElement("a");
              a.href = url;
              a.download = `covara-report-${claimId.slice(0, 8)}.pdf`;
              a.click();
              URL.revokeObjectURL(url);
            } catch (e) {
              setErr(e instanceof Error && e.message !== "failed" ? e.message : t("The report could not be created. Please try again."));
            } finally {
              setBusy(false);
            }
          }}
          className="flex items-center gap-3 rounded-2xl border bg-card p-4 text-left transition-colors hover:bg-secondary/60 disabled:opacity-50"
        >
          <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-secondary text-navy">
            <FileText className="size-5" aria-hidden />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block font-semibold text-navy">{t("Readiness report")}</span>
            <span className="block text-sm text-muted-foreground">
              {busy ? t("Preparing your report. This can take a minute in Hindi.") : t("What we checked and what to do next")}
            </span>
          </span>
          {busy ? <Loader2 className="size-5 shrink-0 animate-spin text-navy" aria-hidden /> : <Download_ className="size-5 shrink-0 text-navy" aria-hidden />}
        </button>
        {err && <p className="text-sm text-destructive">{err}</p>}
      </div>

      <details className="rounded-2xl border bg-card p-4">
        <summary className="cursor-pointer text-sm font-medium text-navy">{t("What is inside the packet")}</summary>
        <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm">
          <li>{t("Cover page, claim summary and document index")}</li>
          <li>{t("Evidence references: where each flagged point sits in your documents")}</li>
          {docs.map((d) => (
            <li key={d.id}>
              {LABEL[d.doc_type] ? t(LABEL[d.doc_type]) : d.doc_type} <span className="text-muted-foreground">· {d.filename}</span>
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}
