"use client";

import { CheckCircle2, CircleDashed, XCircle } from "lucide-react";

import { useI18n, useLocalized } from "@/i18n";
import type { ChecklistItem } from "@/types/results";

export function Checklist({ items }: { items: ChecklistItem[] }) {
  const { t } = useI18n();
  const loc = useLocalized(items.flatMap((i) => [i.label, i.reason]));
  if (items.length === 0) return null;
  const required = items.filter((i) => i.required);
  const have = required.filter((i) => i.received).length;
  return (
    <div className="rounded-lg border">
      <div className="flex items-center justify-between border-b px-3 py-2">
        <p className="text-sm font-medium">{t("Document checklist")}</p>
        <p className="text-xs text-muted-foreground">
          {t("{have} of {total} required received", { have, total: required.length })}
        </p>
      </div>
      <ul className="divide-y">
        {items.map((item, idx) => {
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
                  {loc[idx * 2]}
                  {!item.required && !item.received && (
                    <span className="ml-1 text-xs text-muted-foreground">{t("(if referenced)")}</span>
                  )}
                  {item.required && !item.received && (
                    <span className="ml-2 text-xs font-medium text-destructive">{t("Missing")}</span>
                  )}
                </p>
                <p className="text-xs text-muted-foreground">{loc[idx * 2 + 1]}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
