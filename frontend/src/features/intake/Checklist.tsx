import { CheckCircle2, CircleDashed, XCircle } from "lucide-react";

import type { ChecklistItem } from "@/types/results";

export function Checklist({ items }: { items: ChecklistItem[] }) {
  if (items.length === 0) return null;
  const required = items.filter((i) => i.required);
  const have = required.filter((i) => i.received).length;
  return (
    <div className="rounded-lg border">
      <div className="flex items-center justify-between border-b px-3 py-2">
        <p className="text-sm font-medium">Document checklist</p>
        <p className="text-xs text-muted-foreground">
          {have} of {required.length} required received
        </p>
      </div>
      <ul className="divide-y">
        {items.map((item) => {
          const Icon = item.received ? CheckCircle2 : item.required ? XCircle : CircleDashed;
          const color = item.received
            ? "text-emerald-600"
            : item.required
              ? "text-destructive"
              : "text-muted-foreground";
          return (
            <li key={item.category} className="flex items-start gap-3 px-3 py-2">
              <Icon className={`mt-0.5 size-4 shrink-0 ${color}`} aria-hidden />
              <div className="min-w-0">
                <p className="text-sm">
                  {item.label}
                  {!item.required && !item.received && (
                    <span className="ml-1 text-xs text-muted-foreground">(if referenced)</span>
                  )}
                  {item.required && !item.received && (
                    <span className="ml-2 text-xs font-medium text-destructive">Missing</span>
                  )}
                </p>
                <p className="text-xs text-muted-foreground">{item.reason}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
