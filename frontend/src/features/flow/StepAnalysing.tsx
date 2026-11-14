"use client";

import { Check, Loader2, Lock } from "lucide-react";

import { useI18n, useLocalized } from "@/i18n";
import type { AnalysisResults } from "@/types/results";

/** Step 3: a calm waiting screen that shows what is happening, since a check takes about a minute. */
export function StepAnalysing({ results }: { results: AnalysisResults | null }) {
  const { t } = useI18n();
  const stages = results?.stages ?? [];
  const labels = useLocalized(stages);
  const progress = results?.progress ?? 0;
  const active = Math.min(stages.length - 1, Math.floor(progress * stages.length));
  return (
    <div className="flex flex-col items-center pt-6 text-center">
      <span className="relative flex size-28 items-center justify-center">
        <span className="absolute inset-0 animate-ping rounded-full bg-brand/25" />
        <span className="relative flex size-24 items-center justify-center rounded-full bg-gradient-to-br from-brand to-[#0a6fc4] text-white shadow-lg">
          <Loader2 className="size-10 animate-spin" aria-hidden />
        </span>
      </span>
      <h2 className="mt-6 text-xl font-semibold text-navy">{t("Checking your claim")}</h2>
      <p className="mt-1 max-w-xs text-sm text-muted-foreground">{t("This usually takes about a minute. You can keep this screen open.")}</p>

      <div className="mt-6 h-2 w-full max-w-xs overflow-hidden rounded-full bg-navy/10" role="progressbar" aria-valuenow={Math.round(progress * 100)} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-full rounded-full bg-brand transition-all duration-700" style={{ width: `${Math.max(6, progress * 100)}%` }} />
      </div>

      <ol className="mt-6 w-full max-w-xs space-y-3 text-left">
        {stages.map((s, i) => {
          const label = labels[i] ?? s;
          const done = progress >= 1 || i < active;
          return (
            <li key={s} className={`flex items-center gap-3 text-sm ${done ? "text-navy" : i === active ? "font-semibold text-navy" : "text-muted-foreground"}`}>
              <span className={`flex size-6 shrink-0 items-center justify-center rounded-full ${done ? "bg-emerald-500 text-white" : i === active ? "bg-brand text-navy" : "bg-navy/10"}`}>
                {done ? <Check className="size-3.5" aria-hidden /> : i === active ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : null}
              </span>
              {label}
            </li>
          );
        })}
      </ol>

      <p className="mt-8 flex items-center gap-1.5 text-xs text-muted-foreground">
        <Lock className="size-3.5" aria-hidden /> {t("Your documents stay private and can be deleted any time.")}
      </p>
    </div>
  );
}
