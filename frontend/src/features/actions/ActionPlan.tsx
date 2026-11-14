"use client";

import { useState } from "react";
import { Building2, Check, Copy, Search, Shield, Stethoscope, User } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useI18n, useLocalized } from "@/i18n";
import { setActionDone } from "@/lib/api";
import type { Action, AnalysisResults, Owner } from "@/types/results";

function CopyButton({ text }: { text: string }) {
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

export function ActionPlan({
  claimId,
  results,
  onChange,
  onViewEvidence,
}: {
  claimId: string;
  results: AnalysisResults;
  onChange: (actions: Action[]) => void;
  /** Jump to the "Why was this flagged?" view of a finding (document, field, clause, reason). */
  onViewEvidence?: (findingId: string) => void;
}) {
  const { t } = useI18n();
  const OWNER: Record<Owner, { label: string; icon: typeof User }> = {
    user: { label: t("You"), icon: User },
    hospital: { label: t("Hospital"), icon: Building2 },
    doctor: { label: t("Doctor"), icon: Stethoscope },
    insurer: { label: t("Insurer"), icon: Shield },
  };
  const actions = results.action_plan;
  const open = actions.filter((a) => !a.done).length;

  // Backend text arrives in English: translate it for display (amounts, dates and IDs stay unchanged).
  const loc = useLocalized([
    ...actions.flatMap((a) => [a.title, a.why, a.draft_message ?? "", ...a.how]),
    ...results.checks_passed,
  ]);
  const starts = actions.reduce<number[]>((acc, a, i) => {
    acc.push(i === 0 ? 0 : acc[i - 1] + 3 + actions[i - 1].how.length);
    return acc;
  }, []);
  const actionsEnd = actions.reduce((n, a) => n + 3 + a.how.length, 0);
  const L = actions.map((a, i) => {
    const seg = loc.slice(starts[i], starts[i] + 3 + a.how.length);
    return { title: seg[0], why: seg[1], draft: a.draft_message ? seg[2] : null, how: seg.slice(3) };
  });
  const checksL = loc.slice(actionsEnd, actionsEnd + results.checks_passed.length);

  async function toggle(a: Action) {
    const updated = await setActionDone(claimId, a.id, !a.done);
    onChange(actions.map((x) => (x.id === a.id ? updated : x)));
  }

  const consistent = results.checks_passed.length > 0 && (
    <div className="rounded-lg border p-3">
      <p className="mb-1 flex items-center gap-1.5 text-sm font-medium">
        <Check className="size-4 text-emerald-600" aria-hidden /> {t("Appears consistent")}
      </p>
      <ul className="list-disc space-y-0.5 pl-5 text-sm text-muted-foreground">
        {results.checks_passed.map((c, i) => (
          <li key={c}>{checksL[i]}</li>
        ))}
      </ul>
    </div>
  );

  if (actions.length === 0)
    return (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">{t("No actions needed. Your documents look complete and consistent.")}</p>
        {consistent}
      </div>
    );

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        {t("{open} of {total} actions open. Blocking items are listed first.", { open, total: actions.length })}
      </p>
      <p className="rounded-xl bg-secondary/60 p-3 text-xs text-navy">
        {t("Ticking a box only tracks your own progress. To clear an item, actually fix it (change the amount, remove the duplicate, add the missing document), then press Re-check: Covara re-reads your documents.")}
      </p>
      <ul className="space-y-2">
        {actions.map((a, ai) => {
          const O = OWNER[a.owner];
          const al = L[ai];
          return (
            <li key={a.id} className={`rounded-lg border p-3 ${a.done ? "opacity-60" : ""}`}>
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={a.done}
                  onChange={() => toggle(a)}
                  className="mt-1 size-4 accent-primary"
                  aria-label={t('Mark "{title}" as done', { title: al.title })}
                />
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className={`text-sm font-medium ${a.done ? "line-through" : ""}`}>{al.title}</p>
                    {a.blocking && <Badge variant="destructive">{t("Blocking")}</Badge>}
                    <Badge variant="outline">
                      <O.icon className="mr-1 size-3" aria-hidden /> {O.label}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{al.why}</p>
                  {a.how.length > 0 && (
                    <ol className="list-decimal space-y-0.5 pl-5 text-sm">
                      {al.how.map((h, i) => (
                        <li key={i}>{h}</li>
                      ))}
                    </ol>
                  )}
                  <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    {a.checklist_category && <span>{t("From the document checklist")}</span>}
                  </div>
                  {onViewEvidence && a.finding_ids.length > 0 && (
                    <button
                      type="button"
                      onClick={() => onViewEvidence(a.finding_ids[0])}
                      className="inline-flex h-9 items-center gap-1.5 rounded-full border border-navy/25 bg-card px-3.5 text-sm font-medium text-navy hover:bg-secondary"
                    >
                      <Search className="size-4" aria-hidden /> {t("See the evidence")}
                    </button>
                  )}
                  {a.draft_message && (
                    <details className="rounded-md bg-muted/50 p-2 text-sm">
                      <summary className="cursor-pointer text-xs font-medium">
                        {t("Ready-to-send message to {who}", { who: O.label.toLowerCase() })}
                      </summary>
                      <pre className="mt-2 whitespace-pre-wrap font-sans text-sm">{al.draft ?? a.draft_message}</pre>
                      <div className="mt-2">
                        <CopyButton text={al.draft ?? a.draft_message} />
                      </div>
                    </details>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
      {consistent}
    </div>
  );
}
