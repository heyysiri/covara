"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { EvidenceLink } from "@/features/extraction/EvidenceLink";
import type { AnalysisResults, ClauseType, SummaryValue } from "@/types/results";

const TYPE_LABEL: Record<ClauseType, string> = {
  coverage: "Coverage",
  exclusion: "Exclusion",
  sublimit: "Limit",
  waiting_period: "Waiting period",
  condition: "Condition",
  definition: "Definition",
};

function Stat({ label, v, claimId }: { label: string; v: SummaryValue | null; claimId: string }) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-sm font-medium">{v ? v.text : "Not found in policy"}</p>
      {v && <EvidenceLink claimId={claimId} evidence={v.evidence} />}
    </div>
  );
}

export function PolicyPanel({ claimId, results }: { claimId: string; results: AnalysisResults }) {
  const s = results.policy_summary;
  const [filter, setFilter] = useState<ClauseType | "all" | "linked">("all");
  const linked = new Set(results.findings.flatMap((f) => f.clause_links.map((l) => l.clause_id)));
  const clauses = results.clauses.filter((c) =>
    filter === "all" ? true : filter === "linked" ? linked.has(c.id) : c.type === filter,
  );

  if (!s && results.clauses.length === 0)
    return <p className="text-sm text-muted-foreground">No policy document was analysed. Upload your policy and re-check.</p>;

  return (
    <div className="space-y-5">
      {s && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat claimId={claimId} label="Sum insured" v={s.sum_insured} />
            <Stat claimId={claimId} label="Room-rent limit" v={s.room_rent_cap} />
            <Stat claimId={claimId} label="Co-payment" v={s.copay} />
            <Stat claimId={claimId} label="Pre-hospitalisation" v={s.pre_hosp_days} />
            <Stat claimId={claimId} label="Post-hospitalisation" v={s.post_hosp_days} />
            <div className="rounded-lg border p-3">
              <p className="text-xs text-muted-foreground">Waiting periods</p>
              {s.waiting_periods.length === 0 ? (
                <p className="mt-0.5 text-sm font-medium">Not found in policy</p>
              ) : (
                <ul className="mt-0.5 space-y-0.5">
                  {s.waiting_periods.map((w) => (
                    <li key={w.name} className="text-sm">
                      <span className="font-medium">{w.name}</span>: {w.days} days{" "}
                      <EvidenceLink claimId={claimId} evidence={w.evidence} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
          {s.exclusions.length > 0 && (
            <div className="rounded-lg border p-3">
              <p className="mb-1 text-xs text-muted-foreground">Exclusions listed in the policy</p>
              <ul className="list-disc space-y-0.5 pl-5 text-sm">
                {s.exclusions.map((e, i) => (
                  <li key={i}>{e.text}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      <div>
        <div className="mb-2 flex flex-wrap gap-1">
          {(["all", ...(linked.size ? ["linked"] : []), ...Object.keys(TYPE_LABEL)] as const).map((t) => (
            <button
              key={t}
              onClick={() => setFilter(t as typeof filter)}
              className={`rounded-full border px-2.5 py-0.5 text-xs ${
                filter === t ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted"
              }`}
            >
              {t === "all" ? "All clauses" : t === "linked" ? "Linked to findings" : TYPE_LABEL[t as ClauseType]}
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
                {linked.has(c.id) && <Badge variant="secondary">Linked to a finding</Badge>}
                <span className="ml-auto">
                  <EvidenceLink
                    claimId={claimId}
                    evidence={{ document_id: c.document_id, filename: c.filename, page_number: c.page_number, bbox: null, quote: null }}
                  />
                </span>
              </div>
              <p className="line-clamp-4 whitespace-pre-line text-xs text-muted-foreground">{c.text}</p>
            </li>
          ))}
          {clauses.length === 0 && <li className="text-sm text-muted-foreground">No clauses of this type.</li>}
        </ul>
      </div>
    </div>
  );
}
