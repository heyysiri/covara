"use client";

import { useState } from "react";
import { Building2, Check, Copy, Shield, Stethoscope, User } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { setActionDone } from "@/lib/api";
import type { Action, AnalysisResults, Owner } from "@/types/results";

const OWNER: Record<Owner, { label: string; icon: typeof User }> = {
  user: { label: "You", icon: User },
  hospital: { label: "Hospital", icon: Building2 },
  doctor: { label: "Doctor", icon: Stethoscope },
  insurer: { label: "Insurer", icon: Shield },
};

function CopyButton({ text }: { text: string }) {
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

export function ActionPlan({
  claimId,
  results,
  onChange,
}: {
  claimId: string;
  results: AnalysisResults;
  onChange: (actions: Action[]) => void;
}) {
  const actions = results.action_plan;
  const clauses = new Map(results.clauses.map((c) => [c.id, c]));
  const findings = new Map(results.findings.map((f) => [f.id, f]));
  const open = actions.filter((a) => !a.done).length;

  async function toggle(a: Action) {
    const updated = await setActionDone(claimId, a.id, !a.done);
    onChange(actions.map((x) => (x.id === a.id ? updated : x)));
  }

  if (actions.length === 0)
    return <p className="text-sm text-muted-foreground">No actions needed. Your documents look complete and consistent.</p>;

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        {open} of {actions.length} actions open. Blocking items are listed first.
      </p>
      <ul className="space-y-2">
        {actions.map((a) => {
          const O = OWNER[a.owner];
          return (
            <li key={a.id} className={`rounded-lg border p-3 ${a.done ? "opacity-60" : ""}`}>
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={a.done}
                  onChange={() => toggle(a)}
                  className="mt-1 size-4 accent-primary"
                  aria-label={`Mark "${a.title}" as done`}
                />
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className={`text-sm font-medium ${a.done ? "line-through" : ""}`}>{a.title}</p>
                    {a.blocking && <Badge variant="destructive">Blocking</Badge>}
                    <Badge variant="outline">
                      <O.icon className="mr-1 size-3" aria-hidden /> {O.label}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{a.why}</p>
                  {a.how.length > 0 && (
                    <ol className="list-decimal space-y-0.5 pl-5 text-sm">
                      {a.how.map((h, i) => (
                        <li key={i}>{h}</li>
                      ))}
                    </ol>
                  )}
                  <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    {a.finding_ids.map((id) => findings.get(id)).filter(Boolean).map((f) => (
                      <span key={f!.id}>
                        Finding: {f!.title} ({f!.rule_id})
                      </span>
                    ))}
                    {a.clause_ids.map((id) => clauses.get(id)).filter(Boolean).map((c) => (
                      <span key={c!.id}>
                        Policy clause {c!.clause_ref} · {c!.filename} p.{c!.page_number}
                      </span>
                    ))}
                    {a.checklist_category && <span>From the document checklist</span>}
                  </div>
                  {a.draft_message && (
                    <details className="rounded-md bg-muted/50 p-2 text-sm">
                      <summary className="cursor-pointer text-xs font-medium">
                        Ready-to-send message to {O.label.toLowerCase()}
                      </summary>
                      <pre className="mt-2 whitespace-pre-wrap font-sans text-sm">{a.draft_message}</pre>
                      <div className="mt-2">
                        <CopyButton text={a.draft_message} />
                      </div>
                    </details>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
