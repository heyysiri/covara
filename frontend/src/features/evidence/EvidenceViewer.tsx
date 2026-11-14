"use client";

import { useState } from "react";
import { ArrowLeft, Check, Copy, FileText, Scale } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Action, AnalysisResults, ClauseLink, EvidenceRef, Finding, PolicyClause } from "@/types/results";

import { EvidencePage } from "./EvidencePage";

const VERDICT: Record<ClauseLink["verdict"], string> = {
  applies: "Applies",
  may_apply: "May apply",
  does_not_apply: "Does not apply",
};

const OWNER = { user: "You", hospital: "Hospital", doctor: "Doctor", insurer: "Insurer" } as const;

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
      {copied ? <Check /> : <Copy />} {copied ? "Copied" : "Copy message"}
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
  const docs = evidence.filter((e) => e.source === "document" && e.document_id);
  const others = evidence.filter((e) => e.source !== "document" || !e.document_id);
  const [i, setI] = useState(0);
  const current = docs[Math.min(i, docs.length - 1)];
  return (
    <div className="space-y-3">
      {others.map((e, k) => (
        <div key={k} className="rounded-md border bg-muted/40 p-2 text-sm">
          <p className="text-xs text-muted-foreground">{e.source === "claim_form" ? "From your claim form" : "From the document checklist"}</p>
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
          {current.quote && (
            <p className="space-y-0.5 rounded-md bg-muted/50 p-2 text-xs">
              {current.field && (
                <span className="block">
                  <span className="text-muted-foreground">Extracted field: </span>
                  <strong>{current.field.replace(/_/g, " ")}</strong>
                </span>
              )}
              <span className="block">
                <span className="text-muted-foreground">Text cited: </span>
                {current.quote}
              </span>
            </p>
          )}
        </>
      ) : (
        others.length === 0 && <p className="text-sm text-muted-foreground">No document page is attached to this finding.</p>
      )}
    </div>
  );
}

function PolicyEvidence({ claimId, links, clauses }: { claimId: string; links: ClauseLink[]; clauses: Map<string, PolicyClause> }) {
  const [openPage, setOpenPage] = useState<string | null>(null);
  const shown = links.map((l) => ({ l, c: clauses.get(l.clause_id) })).filter((x): x is { l: ClauseLink; c: PolicyClause } => !!x.c);
  if (shown.length === 0)
    return (
      <p className="text-sm text-muted-foreground">
        No matching clause was found in the uploaded policy for this finding, so none is shown. Covara never invents a clause.
      </p>
    );
  return (
    <div className="space-y-3">
      {shown.map(({ l, c }) => (
        <div key={c.id} className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">
              Clause {c.clause_ref} · {c.title}
            </span>
            <Badge variant={l.verdict === "applies" ? "default" : "secondary"}>{VERDICT[l.verdict]}</Badge>
            <span className="text-xs text-muted-foreground">
              {c.filename} · p.{c.page_number}
            </span>
          </div>
          <p className="whitespace-pre-line rounded-md border bg-muted/30 p-2 text-xs leading-relaxed">
            <Marked text={c.text} quote={l.quote} />
          </p>
          <p className="text-xs text-muted-foreground">Highlighted words are quoted verbatim from the policy.</p>
          <Button size="xs" variant="outline" onClick={() => setOpenPage(openPage === c.id ? null : c.id)}>
            <FileText /> {openPage === c.id ? "Hide policy page" : "Show policy page"}
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

function IssueAndAction({ finding, actions }: { finding: Finding; actions: Action[] }) {
  const { assumption, ...inputs } = finding.explanation.inputs as Record<string, unknown>;
  const rows = Object.entries(inputs).filter(([, v]) => v !== null && v !== undefined && v !== "");
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant={finding.severity === "high" ? "destructive" : "secondary"}>{finding.severity} severity</Badge>
          <Badge variant="outline">{finding.kind === "confirmed" ? "Confirmed mismatch" : "Possible, please review"}</Badge>
          {finding.blocking && <Badge variant="destructive">Blocks the packet</Badge>}
        </div>
        <p className="text-sm font-medium">{finding.title}</p>
        <p className="text-sm text-muted-foreground">{finding.description}</p>
        {finding.exposure_amount != null && (
          <p className="rounded-md border border-amber-500/40 bg-amber-500/5 p-2 text-xs">
            Estimated amount to review: <strong>₹{finding.exposure_amount.toLocaleString("en-IN")}</strong>. This is an estimate to review, not a
            coverage decision.
          </p>
        )}
      </div>

      <div className="space-y-1.5">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <Scale className="size-3.5" aria-hidden /> How Covara checked it
        </p>
        <p className="text-sm">{finding.explanation.rule}</p>
        {rows.length > 0 && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 rounded-md bg-muted/40 p-2 text-xs">
            {rows.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted-foreground">{k.replace(/_/g, " ")}</dt>
                <dd className="break-words">{formatInput(v)}</dd>
              </div>
            ))}
          </dl>
        )}
        {typeof assumption === "string" && <p className="text-xs text-muted-foreground">{assumption}</p>}
        {finding.explanation.why_it_matters && <p className="text-xs">{finding.explanation.why_it_matters}</p>}
      </div>

      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">What to do next</p>
        {actions.length === 0 && <p className="text-sm text-muted-foreground">No action is linked to this finding.</p>}
        {actions.map((a) => (
          <div key={a.id} className="space-y-1.5 rounded-md border p-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-sm font-medium">{a.title}</span>
              <Badge variant="outline">{OWNER[a.owner]}</Badge>
              {a.blocking && <Badge variant="destructive">Blocking</Badge>}
              {a.done && <Badge variant="secondary">Done</Badge>}
            </div>
            <p className="text-xs text-muted-foreground">{a.why}</p>
            {a.how.length > 0 && (
              <ol className="list-decimal space-y-0.5 pl-5 text-xs">
                {a.how.map((h, i) => (
                  <li key={i}>{h}</li>
                ))}
              </ol>
            )}
            {a.draft_message && (
              <div className="space-y-1">
                <p className="whitespace-pre-line rounded bg-muted/50 p-2 text-xs">{a.draft_message}</p>
                <CopyMessage text={a.draft_message} />
              </div>
            )}
          </div>
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
  const clauses = new Map(results.clauses.map((c) => [c.id, c]));
  const actions = results.action_plan.filter((a) => a.finding_ids.includes(finding.id));
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="ghost" onClick={onBack}>
          <ArrowLeft /> All findings
        </Button>
        <h2 className="text-base font-semibold">Why was this flagged?</h2>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        <Step n={1} title="What the documents say">
          <DocumentEvidence claimId={claimId} evidence={finding.evidence} />
        </Step>
        <Step n={2} title="Policy condition">
          <PolicyEvidence claimId={claimId} links={finding.clause_links} clauses={clauses} />
        </Step>
        <Step n={3} title="The issue and your next step">
          <IssueAndAction finding={finding} actions={actions} />
        </Step>
      </div>
    </div>
  );
}
