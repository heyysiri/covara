"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { EvidenceLink } from "@/features/extraction/EvidenceLink";
import { useI18n, useLocalized } from "@/i18n";
import type { AnalysisResults, ClauseType, SummaryValue } from "@/types/results";

function Stat({ label, v, claimId }: { label: string; v: SummaryValue | null; claimId: string }) {
  const { t } = useI18n();
  const [text] = useLocalized([v?.text ?? ""]);
  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-sm font-medium">{v ? text : t("Not found in policy")}</p>
      {v && <EvidenceLink claimId={claimId} evidence={v.evidence} />}
    </div>
  );
}

export function PolicyPanel({ claimId, results }: { claimId: string; results: AnalysisResults }) {
  const { t } = useI18n();
  const TYPE_LABEL: Record<ClauseType, string> = {
    coverage: t("Coverage"),
    exclusion: t("Exclusion"),
    sublimit: t("Limit"),
    waiting_period: t("Waiting period"),
    condition: t("Condition"),
    definition: t("Definition"),
  };
  const s = results.policy_summary;
  const summaryTexts = useLocalized([
    ...(s?.waiting_periods.map((w) => w.name) ?? []),
    ...(s?.exclusions.map((e) => e.text) ?? []),
  ]);
  const waitingL = summaryTexts.slice(0, s?.waiting_periods.length ?? 0);
  const exclusionsL = summaryTexts.slice(s?.waiting_periods.length ?? 0);
  const [filter, setFilter] = useState<ClauseType | "all" | "linked">("all");
  const linked = new Set(results.findings.flatMap((f) => f.clause_links.map((l) => l.clause_id)));
  const clauses = results.clauses.filter((c) =>
    filter === "all" ? true : filter === "linked" ? linked.has(c.id) : c.type === filter,
  );

  if (!s && results.clauses.length === 0)
    return <p className="text-sm text-muted-foreground">{t("No policy document was analysed. Upload your policy and re-check.")}</p>;

  return (
    <div className="space-y-5">
      {s && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat claimId={claimId} label={t("Sum insured")} v={s.sum_insured} />
            <Stat claimId={claimId} label={t("Room-rent limit")} v={s.room_rent_cap} />
            <Stat claimId={claimId} label={t("Co-payment")} v={s.copay} />
            <Stat claimId={claimId} label={t("Pre-hospitalisation")} v={s.pre_hosp_days} />
            <Stat claimId={claimId} label={t("Post-hospitalisation")} v={s.post_hosp_days} />
            <div className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">{t("Waiting periods")}</p>
              {s.waiting_periods.length === 0 ? (
                <p className="mt-0.5 text-sm font-medium">{t("Not found in policy")}</p>
              ) : (
                <ul className="mt-0.5 space-y-0.5">
                  {s.waiting_periods.map((w, i) => (
                    <li key={w.name} className="text-sm">
                      <span className="font-medium">{waitingL[i]}</span>: {t("{n} days", { n: w.days })}{" "}
                      <EvidenceLink claimId={claimId} evidence={w.evidence} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
          {s.exclusions.length > 0 && (
            <div className="rounded-lg border p-3">
              <p className="mb-1 text-xs text-muted-foreground">{t("Exclusions listed in the policy")}</p>
              <ul className="list-disc space-y-0.5 pl-5 text-sm">
                {s.exclusions.map((e, i) => (
                  <li key={i}>{exclusionsL[i]}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      <div>
        <div className="mb-2 flex flex-wrap gap-1">
          {(["all", ...(linked.size ? ["linked"] : []), ...Object.keys(TYPE_LABEL)] as const).map((k) => (
            <button
              key={k}
              onClick={() => setFilter(k as typeof filter)}
              className={`rounded-full border px-2.5 py-0.5 text-xs ${
                filter === k ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted"
              }`}
            >
              {k === "all" ? t("All clauses") : k === "linked" ? t("Linked to findings") : TYPE_LABEL[k as ClauseType]}
            </button>
          ))}
        </div>
        <ul className="space-y-2">
          {clauses.map((c) => (
            <li key={c.id} className={`rounded-lg border p-3 ${linked.has(c.id) ? "border-amber-500/60" : ""}`}>
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">
                  {c.clause_ref}. {c.title}
                </span>
                <Badge variant="outline">{TYPE_LABEL[c.type]}</Badge>
                {linked.has(c.id) && <Badge variant="secondary">{t("Linked to a finding")}</Badge>}
                <span className="ml-auto">
                  <EvidenceLink
                    claimId={claimId}
                    evidence={{ source: "document", document_id: c.document_id, filename: c.filename, page_number: c.page_number, bbox: null, quote: null }}
                  />
                </span>
              </div>
              <p className="line-clamp-4 whitespace-pre-line text-xs text-muted-foreground">{c.text}</p>
            </li>
          ))}
          {clauses.length === 0 && <li className="text-sm text-muted-foreground">{t("No clauses of this type.")}</li>}
        </ul>
      </div>
    </div>
  );
}
