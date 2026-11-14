"use client";

import { useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, Loader2, RefreshCw, XCircle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ActionPlan } from "@/features/actions/ActionPlan";
import { ExtractedData, needsReview } from "@/features/extraction/ExtractedData";
import { Checklist } from "@/features/intake/Checklist";
import { PolicyPanel } from "@/features/policy/PolicyPanel";
import type { FieldEdit } from "@/lib/api";
import type { AnalysisResults } from "@/types/results";

import { AnalysisProgress } from "./AnalysisProgress";

const READINESS = {
  ready: { label: "Ready to submit", icon: CheckCircle2, cls: "border-emerald-600/40 bg-emerald-600/5 text-emerald-700 dark:text-emerald-400" },
  needs_attention: { label: "Needs attention", icon: AlertTriangle, cls: "border-amber-500/50 bg-amber-500/5 text-amber-700 dark:text-amber-400" },
  incomplete: { label: "Incomplete", icon: XCircle, cls: "border-destructive/40 bg-destructive/5 text-destructive" },
} as const;

export interface ExtraTab {
  id: string;
  label: string;
  render: (results: AnalysisResults) => ReactNode;
}

/**
 * Person 1 workspace panels: readiness, checklist, extracted data, policy, action plan.
 * Person 2 can pass extra tabs (Findings / Evidence / Packet) via `extraTabs`.
 */
export function AnalysisView({
  claimId,
  results,
  onRecheck,
  onReview,
  onResults,
  extraTabs = [],
}: {
  claimId: string;
  results: AnalysisResults;
  onRecheck: () => void;
  onReview: (edits: FieldEdit[]) => void;
  onResults: (r: AnalysisResults) => void;
  extraTabs?: ExtraTab[];
}) {
  const running = results.status === "processing";
  const hasData = results.documents.length > 0;
  const reviewCount = results.fields.filter(needsReview).length;
  const openActions = results.action_plan.filter((a) => !a.done).length;
  const tabs = [
    { id: "actions", label: `Action plan${openActions ? ` (${openActions})` : ""}` },
    { id: "extracted", label: `Extracted data${reviewCount ? ` · ${reviewCount} to confirm` : ""}` },
    { id: "policy", label: "Policy" },
    { id: "checklist", label: "Checklist" },
    ...extraTabs.map((t) => ({ id: t.id, label: t.label })),
  ];
  const [tab, setTab] = useState("actions");
  const r = results.readiness_status ? READINESS[results.readiness_status] : null;
  const aiCalls = results.llm_calls.filter((c) => c.ok);

  return (
    <div className="space-y-4">
      {running && <AnalysisProgress results={results} />}

      {results.status === "failed" && (
        <Alert variant="destructive">
          <AlertTitle>Analysis failed</AlertTitle>
          <AlertDescription>{results.error}</AlertDescription>
        </Alert>
      )}

      {hasData && r && (
        <div className={`flex flex-wrap items-start gap-3 rounded-lg border p-4 ${r.cls}`}>
          <r.icon className="mt-0.5 size-5 shrink-0" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="font-semibold">{r.label}</p>
            <p className="text-sm text-foreground/80">{results.readiness_explanation}</p>
            {results.packet_status && (
              <p className="mt-1 text-xs font-medium text-foreground/70">Claim packet: {results.packet_status}</p>
            )}
          </div>
          <Button variant="outline" size="sm" onClick={onRecheck} disabled={running}>
            {running ? <Loader2 className="animate-spin" /> : <RefreshCw />} Re-check
          </Button>
        </div>
      )}

      {results.warnings.length > 0 && (
        <ul className="space-y-1">
          {results.warnings.map((w) => (
            <li key={w} className="flex items-start gap-2 text-xs text-muted-foreground">
              <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden /> {w}
            </li>
          ))}
        </ul>
      )}

      {hasData && (
        <>
          <div role="tablist" className="flex flex-wrap gap-1 border-b">
            {tabs.map((t) => (
              <button
                key={t.id}
                role="tab"
                aria-selected={tab === t.id}
                onClick={() => setTab(t.id)}
                className={`-mb-px border-b-2 px-3 py-2 text-sm ${
                  tab === t.id ? "border-primary font-medium" : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div role="tabpanel">
            {tab === "actions" && (
              <ActionPlan claimId={claimId} results={results} onChange={(action_plan) => onResults({ ...results, action_plan })} />
            )}
            {tab === "extracted" && <ExtractedData claimId={claimId} results={results} onReview={onReview} busy={running} />}
            {tab === "policy" && <PolicyPanel claimId={claimId} results={results} />}
            {tab === "checklist" && <Checklist items={results.checklist} />}
            {extraTabs.find((t) => t.id === tab)?.render(results)}
          </div>
          <p className="text-xs text-muted-foreground">
            {aiCalls.length > 0
              ? `Read with ${results.providers_used.join(", ")} (${aiCalls.length} model call${aiCalls.length > 1 ? "s" : ""}, ${aiCalls.filter((c) => c.cached).length} from cache). `
              : "Read with Covara's rule-based extractor (no AI provider configured). "}
            Every value links to its source page. {results.disclaimer}
          </p>
        </>
      )}
    </div>
  );
}
