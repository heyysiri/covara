"use client";

import { useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, Loader2, RefreshCw, XCircle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ActionPlan } from "@/features/actions/ActionPlan";
import { ExtractedData, needsReview } from "@/features/extraction/ExtractedData";
import { Checklist } from "@/features/intake/Checklist";
import { PolicyPanel } from "@/features/policy/PolicyPanel";
import { ListenButton } from "@/features/voice/ListenButton";
import { useI18n, useLocalized } from "@/i18n";
import type { FieldEdit } from "@/lib/api";
import type { AnalysisResults } from "@/types/results";

import { AnalysisProgress } from "./AnalysisProgress";

export interface ExtraTab {
  id: string;
  label: string | ((results: AnalysisResults) => string);
  render: (results: AnalysisResults) => ReactNode;
  /** List this tab before the built-in ones and open it by default (e.g. Findings). */
  first?: boolean;
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
  const { t } = useI18n();
  const READINESS = {
    ready: { label: t("Ready to submit"), icon: CheckCircle2, cls: "border-emerald-600/40 bg-emerald-600/5 text-emerald-700 dark:text-emerald-400" },
    needs_attention: { label: t("Needs attention"), icon: AlertTriangle, cls: "border-amber-500/50 bg-amber-500/5 text-amber-700 dark:text-amber-400" },
    incomplete: { label: t("Incomplete"), icon: XCircle, cls: "border-destructive/40 bg-destructive/5 text-destructive" },
  } as const;
  const loc = useLocalized([
    results.readiness_explanation,
    results.error ?? "",
    results.packet_status ?? "",
    results.disclaimer,
    ...results.warnings,
  ]);
  const [explanationL, errorL, packetL, disclaimerL, ...warningsL] = loc;
  const running = results.status === "processing";
  const hasData = results.documents.length > 0;
  const reviewCount = results.fields.filter(needsReview).length;
  const openActions = results.action_plan.filter((a) => !a.done).length;
  const extra = (x: ExtraTab) => ({ id: x.id, label: typeof x.label === "function" ? x.label(results) : x.label });
  const tabs = [
    ...extraTabs.filter((x) => x.first).map(extra),
    { id: "actions", label: `${t("Action plan")}${openActions ? ` (${openActions})` : ""}` },
    { id: "extracted", label: `${t("Extracted data")}${reviewCount ? ` · ${t("{n} to confirm", { n: reviewCount })}` : ""}` },
    { id: "policy", label: t("Policy") },
    { id: "checklist", label: t("Checklist") },
    ...extraTabs.filter((x) => !x.first).map(extra),
  ];
  const [tab, setTab] = useState(extraTabs.find((x) => x.first)?.id ?? "actions");
  const r = results.readiness_status ? READINESS[results.readiness_status] : null;
  const aiCalls = results.llm_calls.filter((c) => c.ok);

  return (
    <div className="space-y-4">
      {running && <AnalysisProgress results={results} />}

      {results.status === "failed" && (
        <Alert variant="destructive">
          <AlertTitle>{t("Analysis failed")}</AlertTitle>
          <AlertDescription>{errorL}</AlertDescription>
        </Alert>
      )}

      {hasData && r && (
        <div className={`flex flex-wrap items-start gap-3 rounded-lg border p-4 ${r.cls}`}>
          <r.icon className="mt-0.5 size-5 shrink-0" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="font-semibold">{r.label}</p>
            <p className="text-sm text-foreground/80">{explanationL}</p>
            {results.packet_status && (
              <p className="mt-1 text-xs font-medium text-foreground/70">{t("Claim packet: {status}", { status: packetL })}</p>
            )}
          </div>
          <ListenButton claimId={claimId} disabled={running} />
          <Button variant="outline" size="sm" onClick={onRecheck} disabled={running}>
            {running ? <Loader2 className="animate-spin" /> : <RefreshCw />} {t("Re-check")}
          </Button>
        </div>
      )}

      {results.warnings.length > 0 && (
        <ul className="space-y-1">
          {results.warnings.map((w, i) => (
            <li key={w} className="flex items-start gap-2 text-xs text-muted-foreground">
              <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden /> {warningsL[i]}
            </li>
          ))}
        </ul>
      )}

      {hasData && (
        <>
          <div role="tablist" className="flex flex-wrap gap-1 border-b">
            {tabs.map((x) => (
              <button
                key={x.id}
                role="tab"
                aria-selected={tab === x.id}
                onClick={() => setTab(x.id)}
                className={`-mb-px border-b-2 px-3 py-2 text-sm ${
                  tab === x.id ? "border-primary font-medium" : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                {x.label}
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
            {extraTabs.find((x) => x.id === tab)?.render(results)}
          </div>
          <p className="text-xs text-muted-foreground">
            {aiCalls.length > 0
              ? aiCalls.length === 1
                ? t("Read with {providers} (1 model call, {cached} from cache).", { providers: results.providers_used.join(", "), cached: aiCalls.filter((c) => c.cached).length })
                : t("Read with {providers} ({n} model calls, {cached} from cache).", { providers: results.providers_used.join(", "), n: aiCalls.length, cached: aiCalls.filter((c) => c.cached).length })
              : t("Read with Covara's rule-based extractor (no AI provider configured).")}{" "}
            {t("Every value links to its source page.")} {disclaimerL}
          </p>
        </>
      )}
    </div>
  );
}
