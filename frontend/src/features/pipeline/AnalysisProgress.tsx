import { CheckCircle2, Circle, Loader2 } from "lucide-react";

import type { AnalysisResults } from "@/types/results";

export function AnalysisProgress({ results }: { results: AnalysisResults }) {
  const total = results.stages.length || 1;
  const doneCount = Math.round(results.progress * total);
  return (
    <div className="space-y-3" aria-live="polite">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-500"
          style={{ width: `${Math.max(4, results.progress * 100)}%` }}
        />
      </div>
      <ol className="grid gap-1.5 text-sm sm:grid-cols-3">
        {results.stages.map((label, i) => {
          const state = i < doneCount ? "done" : i === doneCount ? "active" : "todo";
          return (
            <li key={label} className="flex items-center gap-2">
              {state === "done" ? (
                <CheckCircle2 className="size-4 text-emerald-600" aria-hidden />
              ) : state === "active" ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Circle className="size-4 text-muted-foreground/50" aria-hidden />
              )}
              <span className={state === "todo" ? "text-muted-foreground" : ""}>{label}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
