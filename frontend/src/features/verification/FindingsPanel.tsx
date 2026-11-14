"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EvidenceViewer } from "@/features/evidence/EvidenceViewer";
import { EvidenceLink } from "@/features/extraction/EvidenceLink";
import { useI18n, useLocalized } from "@/i18n";
import type { AnalysisResults, Finding } from "@/types/results";

type Filter = "all" | "blocking" | "review";

function FindingCard({ claimId, finding, results, onOpen }: { claimId: string; finding: Finding; results: AnalysisResults; onOpen: () => void }) {
  const { t } = useI18n();
  const [title, description] = useLocalized([finding.title, finding.description]);
  const clauses = new Map(results.clauses.map((c) => [c.id, c]));
  const linked = finding.clause_links.map((l) => clauses.get(l.clause_id)).filter((c) => !!c);
  return (
    <li className={`space-y-2 rounded-lg border p-3 ${finding.blocking ? "border-destructive/40" : ""}`}>
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge variant={finding.severity === "high" ? "destructive" : "secondary"}>{{ high: t("High"), medium: t("Medium"), low: t("Low") }[finding.severity]}</Badge>
        <Badge variant="outline">{finding.kind === "confirmed" ? t("Confirmed") : t("To review")}</Badge>
        {finding.blocking && <Badge variant="destructive">{t("Blocks the packet")}</Badge>}
        <span className="ml-auto text-xs text-muted-foreground">{finding.rule_id}</span>
      </div>
      <p className="text-sm font-medium">{title}</p>
      <p className="text-sm text-muted-foreground">{description}</p>
      {finding.extracted_value != null && finding.comparison_value != null && (
        <p className="text-xs">
          <span className="rounded bg-muted px-1.5 py-0.5">{finding.extracted_value}</span>
          <span className="mx-1.5 text-muted-foreground">vs</span>
          <span className="rounded bg-muted px-1.5 py-0.5">{finding.comparison_value}</span>
        </p>
      )}
      {finding.exposure_amount != null && (
        <p className="text-xs font-medium text-amber-700 dark:text-amber-400">
          {t("Estimated amount to review: ₹{amount} (an estimate, not a decision)", { amount: finding.exposure_amount.toLocaleString("en-IN") })}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        {finding.evidence.map((e, i) => (
          <EvidenceLink key={i} claimId={claimId} evidence={e} />
        ))}
        {linked.map((c) => (
          <span key={c!.id} className="text-xs text-muted-foreground">
            {t("Policy clause {ref} · p.{page}", { ref: c!.clause_ref, page: c!.page_number })}
          </span>
        ))}
      </div>
      <Button size="sm" variant="outline" onClick={onOpen}>
        <Search /> {t("Why was this flagged?")}
      </Button>
    </li>
  );
}

/** Findings from the verification engine, each one opening its evidence trail. */
export function FindingsPanel({ claimId, results, initialOpenId = null }: { claimId: string; results: AnalysisResults; initialOpenId?: string | null }) {
  const { t } = useI18n();
  const passedL = useLocalized(results.checks_passed);
  const [filter, setFilter] = useState<Filter>("all");
  const [openId, setOpenId] = useState<string | null>(initialOpenId);
  const [showPassed, setShowPassed] = useState(false);
  const findings = results.findings;
  const blocking = findings.filter((f) => f.blocking).length;
  const selected = findings.find((f) => f.id === openId);

  if (selected) return <EvidenceViewer claimId={claimId} finding={selected} results={results} onBack={() => setOpenId(null)} />;

  const shown = findings.filter((f) => (filter === "blocking" ? f.blocking : filter === "review" ? !f.blocking : true));
  const chip = (id: Filter, label: string) => (
    <button
      key={id}
      onClick={() => setFilter(id)}
      className={`rounded-full border px-2.5 py-0.5 text-xs ${filter === id ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted"}`}
    >
      {label}
    </button>
  );

  return (
    <div className="space-y-4">
      {findings.length === 0 ? (
        <div className="flex items-start gap-2 rounded-lg border border-emerald-600/40 bg-emerald-600/5 p-3 text-sm">
          <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />
          <p>
            {t("No issues were found by the checks Covara ran. This is a preparation check, not an insurer decision; the insurer may still ask for more.")}
          </p>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <AlertTriangle className="size-4 text-amber-600" aria-hidden />
            <p className="text-sm">
              {t("{b} to fix · {r} to review", { b: blocking, r: findings.length - blocking })}
            </p>
            <div className="ml-auto flex gap-1">
              {chip("all", t("All"))}
              {chip("blocking", t("To fix"))}
              {chip("review", t("To review"))}
            </div>
          </div>
          <ul className="space-y-2">
            {shown.map((f) => (
              <FindingCard key={f.id} claimId={claimId} finding={f} results={results} onOpen={() => setOpenId(f.id)} />
            ))}
            {shown.length === 0 && <li className="text-sm text-muted-foreground">{t("Nothing in this filter.")}</li>}
          </ul>
        </>
      )}

      {results.checks_passed.length > 0 && (
        <div className="rounded-lg border p-3">
          <button className="flex w-full items-center gap-1.5 text-left text-sm font-medium" onClick={() => setShowPassed(!showPassed)}>
            {showPassed ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
            <CheckCircle2 className="size-4 text-emerald-600" aria-hidden />
            {t("{n} checks passed", { n: results.checks_passed.length })}
          </button>
          {showPassed && (
            <ul className="mt-2 list-disc space-y-0.5 pl-9 text-xs text-muted-foreground">
              {results.checks_passed.map((c, i) => (
                <li key={c}>{passedL[i]}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
