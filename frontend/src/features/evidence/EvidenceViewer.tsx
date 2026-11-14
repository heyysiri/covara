"use client";

import { useState } from "react";
import { ArrowLeft, Check, Copy, FileText, Scale } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useI18n, useLocalized } from "@/i18n";
import type { Action, AnalysisResults, ClauseLink, EvidenceRef, Finding, PolicyClause } from "@/types/results";

import { EvidencePage } from "./EvidencePage";


/** Wrap the verified quote inside the clause text so the user sees exactly which words matched. */
function Marked({ text, quote }: { text: string; quote: string }) {
  const i = quote ? text.indexOf(quote) : -1;
  if (i === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, i)}
      <mark className="rounded bg-yellow-300/70 px-0.5 text-foreground dark:bg-yellow-500/40">{quote}</mark>
      {text.slice(i + quote.length)}
    </>
  );
}

function formatInput(v: unknown): string {
  if (typeof v === "number") return v.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  if (Array.isArray(v)) return v.map(formatInput).join(", ");
  if (v && typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function CopyMessage({ text }: { text: string }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  return (
    <Button
      size="xs"
      variant="outline"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          /* clipboard blocked */
        }
      }}
    >
      {copied ? <Check /> : <Copy />} {copied ? t("Copied") : t("Copy message")}
    </Button>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="min-w-0 space-y-3 rounded-lg border p-3">
      <h3 className="flex items-center gap-2 text-sm font-semibold">
        <span className="flex size-5 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground">{n}</span>
        {title}
      </h3>
      {children}
    </section>
  );
}

function DocumentEvidence({ claimId, evidence }: { claimId: string; evidence: EvidenceRef[] }) {
  const { t } = useI18n();
  const docs = evidence.filter((e) => e.source === "document" && e.document_id);
  const others = evidence.filter((e) => e.source !== "document" || !e.document_id);
  const [i, setI] = useState(0);
  const current = docs[Math.min(i, docs.length - 1)];
  return (
    <div className="space-y-3">
      {others.map((e, k) => (
        <div key={k} className="rounded-md border bg-muted/40 p-2 text-sm">
          <p className="text-xs text-muted-foreground">{e.source === "claim_form" ? t("From your claim form") : t("From the document checklist")}</p>
          <p className="font-medium">
            {(e.field ?? "").replace(/_/g, " ")}
            {e.value != null && (
              <>: {typeof e.value === "number" ? e.value.toLocaleString("en-IN") : Array.isArray(e.value) ? (e.value as string[]).join(", ") : String(e.value)}</>
            )}
          </p>
        </div>
      ))}
      {docs.length > 1 && (
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="Evidence documents">
          {docs.map((e, k) => (
            <button
              key={k}
              role="tab"
              aria-selected={k === i}
              onClick={() => setI(k)}
              className={`rounded-full border px-2.5 py-0.5 text-xs ${k === i ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted"}`}
            >
              {e.filename} · p.{e.page_number}
            </button>
          ))}
        </div>
      )}
      {current ? (
        <>
          <EvidencePage key={`${current.document_id}-${current.page_number}-${current.quote}`} claimId={claimId} evidence={current} />
        </>
      ) : (
        others.length === 0 && <p className="text-sm text-muted-foreground">{t("No document page is attached to this finding.")}</p>
      )}
    </div>
  );
}

function PolicyEvidence({ claimId, links, clauses }: { claimId: string; links: ClauseLink[]; clauses: Map<string, PolicyClause> }) {
  const { t } = useI18n();
  const VERDICT: Record<ClauseLink["verdict"], string> = { applies: t("Applies"), may_apply: t("May apply"), does_not_apply: t("Does not apply") };
  const [openPage, setOpenPage] = useState<string | null>(null);
  const shown = links.map((l) => ({ l, c: clauses.get(l.clause_id) })).filter((x): x is { l: ClauseLink; c: PolicyClause } => !!x.c);
  if (shown.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        {t("No matching clause was found in the uploaded policy for this finding, so none is shown. Covara never invents a clause.")}
      </p>
    );
  return (
    <div className="space-y-3">
      {shown.map(({ l, c }) => (
        <div key={c.id} className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">
              {t("Clause {ref}", { ref: c.clause_ref })}
            </span>
            <Badge variant={l.verdict === "applies" ? "default" : "secondary"}>{VERDICT[l.verdict]}</Badge>
            <span className="text-xs text-muted-foreground">
              {c.filename} · p.{c.page_number}
            </span>
          </div>
          <p className="whitespace-pre-line rounded-md border bg-muted/30 p-2 text-xs leading-relaxed">
            <Marked text={c.text} quote={l.quote} />
          </p>
          <Button size="xs" variant="outline" onClick={() => setOpenPage(openPage === c.id ? null : c.id)}>
            <FileText /> {openPage === c.id ? t("Hide policy page") : t("Show policy page")}
          </Button>
          {openPage === c.id && (
            <EvidencePage
              claimId={claimId}
              quote={l.quote}
              caption={`${c.filename} · page ${c.page_number}`}
              evidence={{ document_id: c.document_id, filename: c.filename, page_number: c.page_number, bbox: null, quote: l.quote }}
            />
          )}
        </div>
      ))}
    </div>
  );
}

function ActionBlock({ a, owner }: { a: Action; owner: string }) {
  const { t } = useI18n();
  const [title, , draft, ...how] = useLocalized([a.title, a.why, a.draft_message ?? "", ...a.how]);
  return (
    <div className="space-y-1.5 rounded-md border p-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-sm font-medium">{title}</span>
        <Badge variant="outline">{owner}</Badge>
        {a.blocking && <Badge variant="destructive">{t("Blocking")}</Badge>}
        {a.done && <Badge variant="secondary">{t("Done")}</Badge>}
      </div>
      {how.length > 0 && (
        <ol className="list-decimal space-y-0.5 pl-5 text-xs">
          {how.map((h, i) => (
            <li key={i}>{h}</li>
          ))}
        </ol>
      )}
      {a.draft_message && (
        <div className="space-y-1">
          <p className="whitespace-pre-line rounded bg-muted/50 p-2 text-xs">{draft}</p>
          <CopyMessage text={draft} />
        </div>
      )}
    </div>
  );
}

function IssueAndAction({ finding, actions }: { finding: Finding; actions: Action[] }) {
  const { t } = useI18n();
  const OWNER = { user: t("You"), hospital: t("Hospital"), doctor: t("Doctor"), insurer: t("Insurer") } as const;
  const SEVERITY = { high: t("High severity"), medium: t("Medium severity"), low: t("Low severity") } as const;
  const [title, description, rule, assumptionL] = useLocalized([
    finding.title, finding.description, finding.explanation.rule,
    String((finding.explanation.inputs as Record<string, unknown>).assumption ?? ""),
  ]);
  const { assumption, ...inputs } = finding.explanation.inputs as Record<string, unknown>;
  const rows = Object.entries(inputs).filter(([, v]) => v !== null && v !== undefined && v !== "");
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant={finding.severity === "high" ? "destructive" : "secondary"}>{SEVERITY[finding.severity]}</Badge>
          {finding.blocking && <Badge variant="destructive">{t("Blocks the packet")}</Badge>}
        </div>
        <p className="text-sm font-medium">{title}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
        {finding.exposure_amount != null && (
          <p className="rounded-md border border-amber-500/40 bg-amber-500/5 p-2 text-xs">
            {t("Estimated amount to review: ₹{amount}. This is an estimate to review, not a coverage decision.", { amount: finding.exposure_amount.toLocaleString("en-IN") })}
          </p>
        )}
      </div>

      <details className="rounded-md border p-2 text-xs">
        <summary className="flex cursor-pointer items-center gap-1.5 font-medium text-muted-foreground">
          <Scale className="size-3.5" aria-hidden /> {t("How Covara checked it")}
        </summary>
        <p className="mt-2 text-sm">{rule}</p>
        {rows.length > 0 && (
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
            {rows.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted-foreground">{k.replace(/_/g, " ")}</dt>
                <dd className="break-words">{formatInput(v)}</dd>
              </div>
            ))}
          </dl>
        )}
        {typeof assumption === "string" && <p className="mt-2 text-muted-foreground">{assumptionL}</p>}
      </details>

      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("What to do next")}</p>
        {actions.length === 0 && <p className="text-sm text-muted-foreground">{t("No action is linked to this finding.")}</p>}
        {actions.map((a) => (
          <ActionBlock key={a.id} a={a} owner={OWNER[a.owner]} />
        ))}
      </div>
    </div>
  );
}

/** "Why was this flagged?": document evidence -> policy condition -> issue and next step, side by side. */
export function EvidenceViewer({
  claimId,
  finding,
  results,
  onBack,
}: {
  claimId: string;
  finding: Finding;
  results: AnalysisResults;
  onBack: () => void;
}) {
  const { t } = useI18n();
  const clauses = new Map(results.clauses.map((c) => [c.id, c]));
  const actions = results.action_plan.filter((a) => a.finding_ids.includes(finding.id));
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="ghost" onClick={onBack}>
          <ArrowLeft /> {t("All findings")}
        </Button>
        <h2 className="text-base font-semibold">{t("Why was this flagged?")}</h2>
      </div>
      <div className="grid gap-3 lg:grid-cols-[1.3fr_1fr_1fr]">
        <Step n={1} title={t("What the documents say")}>
          <DocumentEvidence claimId={claimId} evidence={finding.evidence} />
        </Step>
        <Step n={2} title={t("Policy condition")}>
          <PolicyEvidence claimId={claimId} links={finding.clause_links} clauses={clauses} />
        </Step>
        <Step n={3} title={t("The issue and your next step")}>
          <IssueAndAction finding={finding} actions={actions} />
        </Step>
      </div>
    </div>
  );
}
