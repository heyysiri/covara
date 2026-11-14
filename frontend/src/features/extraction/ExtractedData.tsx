"use client";

import { useState } from "react";
import { Check, Pencil, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useI18n, useLocalized, type TFn } from "@/i18n";
import type { FieldEdit } from "@/lib/api";
import { DOCUMENT_CATEGORIES } from "@/types/claim";
import {
  CRITICAL_KEYS,
  FIELD_LABELS,
  REVIEW_THRESHOLD,
  type AnalysisResults,
  type ExtractedField,
} from "@/types/results";

import { EvidenceLink } from "./EvidenceLink";

function fmt(f: ExtractedField, t: TFn): string {
  if (f.value === null || f.value === "") return t("Unknown");
  if (f.key === "line_item") return `${f.raw_text ?? ""} · ₹${Number(f.value).toLocaleString("en-IN")}`;
  if (f.key === "waiting_period") return t("{text} · {n} days", { text: f.raw_text ?? "", n: f.value ?? "" });
  if (typeof f.value === "number" && /amount|total|sum_insured|room_rent/.test(f.key))
    return `₹${f.value.toLocaleString("en-IN")}`;
  return String(f.value);
}

export const needsReview = (f: ExtractedField) =>
  CRITICAL_KEYS.has(f.key) && f.confidence < REVIEW_THRESHOLD && !f.user_confirmed;

function Confidence({ f }: { f: ExtractedField }) {
  const { t } = useI18n();
  if (f.user_confirmed) return <Badge variant="secondary">{t("Confirmed")}</Badge>;
  const pct = Math.round(f.confidence * 100);
  if (f.confidence < REVIEW_THRESHOLD)
    return <Badge variant="destructive">{t("Low confidence {pct}%", { pct })}</Badge>;
  return <Badge variant="outline">{pct}%</Badge>;
}

export function ExtractedData({
  claimId,
  results,
  onReview,
  busy,
}: {
  claimId: string;
  results: AnalysisResults;
  onReview: (edits: FieldEdit[]) => void;
  busy: boolean;
}) {
  const { t } = useI18n();
  const typeLabel = (v: string) => {
    const label = DOCUMENT_CATEGORIES.find((c) => c.value === v)?.label;
    return label ? t(label) : v;
  };
  const fieldLabel = (key: string) => (FIELD_LABELS[key] ? t(FIELD_LABELS[key]) : key);
  const docErrorsL = useLocalized(results.documents.map((d) => d.error ?? ""));
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const toReview = results.fields.filter(needsReview);

  return (
    <div className="space-y-5">
      {toReview.length > 0 && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
          <p className="font-medium">
            {toReview.length === 1 ? t("Please confirm 1 value") : t("Please confirm {n} values", { n: toReview.length })}
          </p>
          <p className="text-xs text-muted-foreground">
            {t("Covara was not sure about these important values. Check them against the document and confirm or correct them. Unknown values are never guessed.")}
          </p>
        </div>
      )}
      {results.documents.map((doc, di) => {
        const fields = results.fields.filter((f) => f.evidence.document_id === doc.id);
        return (
          <section key={doc.id} className="rounded-lg border">
            <header className="flex flex-wrap items-center gap-2 border-b px-3 py-2">
              <p className="text-sm font-medium">{doc.filename}</p>
              <Badge variant="secondary">{typeLabel(doc.doc_type)}</Badge>
              {doc.detected_type && doc.detected_type !== doc.doc_type && (
                <span className="text-xs text-muted-foreground">
                  {t("(looks like: {type})", { type: typeLabel(doc.detected_type) })}
                </span>
              )}
              <span className="ml-auto text-xs text-muted-foreground">
                {doc.status === "failed"
                  ? docErrorsL[di]
                  : doc.pages === 1
                    ? t("1 page")
                    : t("{n} pages", { n: doc.pages })}
              </span>
            </header>
            {fields.length === 0 ? (
              <p className="px-3 py-3 text-sm text-muted-foreground">{t("No details extracted.")}</p>
            ) : (
              <ul className="divide-y">
                {fields.map((f) => (
                  <li
                    key={f.id}
                    className={`grid gap-1 px-3 py-2 sm:grid-cols-[11rem_1fr_auto] sm:items-center ${
                      needsReview(f) ? "bg-amber-500/5" : ""
                    }`}
                  >
                    <span className="text-xs font-medium text-muted-foreground">
                      {fieldLabel(f.key)}
                    </span>
                    <div className="min-w-0">
                      {editing === f.id ? (
                        <form
                          className="flex gap-1"
                          onSubmit={(e) => {
                            e.preventDefault();
                            onReview([{ field_id: f.id, value: draft, confirm: true }]);
                            setEditing(null);
                          }}
                        >
                          <input
                            autoFocus
                            value={draft}
                            onChange={(e) => setDraft(e.target.value)}
                            className="h-7 w-full rounded-md border bg-background px-2 text-sm"
                            aria-label={t("Correct {field}", { field: fieldLabel(f.key) })}
                          />
                          <Button size="icon-sm" type="submit" aria-label={t("Save")}>
                            <Check />
                          </Button>
                          <Button size="icon-sm" variant="ghost" type="button" onClick={() => setEditing(null)} aria-label={t("Cancel")}>
                            <X />
                          </Button>
                        </form>
                      ) : (
                        <p className={`truncate text-sm ${f.value === null ? "italic text-muted-foreground" : ""}`}>
                          {fmt(f, t)}
                        </p>
                      )}
                      <div className="flex flex-wrap items-center gap-x-2">
                        <EvidenceLink claimId={claimId} evidence={f.evidence} />
                        {f.evidence.quote && (
                          <span className="truncate text-xs text-muted-foreground/80">“{f.evidence.quote}”</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Confidence f={f} />
                      {needsReview(f) && (
                        <Button
                          size="xs"
                          variant="outline"
                          disabled={busy}
                          onClick={() => onReview([{ field_id: f.id, confirm: true }])}
                        >
                          {t("Confirm")}
                        </Button>
                      )}
                      <Button
                        size="icon-xs"
                        variant="ghost"
                        disabled={busy}
                        aria-label={t("Correct value")}
                        onClick={() => {
                          setEditing(f.id);
                          setDraft(String(f.key === "line_item" ? f.value ?? "" : f.raw_text ?? f.value ?? ""));
                        }}
                      >
                        <Pencil />
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}
