"use client";

import { useState } from "react";
import { Check, Pencil, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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

const typeLabel = (t: string) => DOCUMENT_CATEGORIES.find((c) => c.value === t)?.label ?? t;

function fmt(f: ExtractedField): string {
  if (f.value === null || f.value === "") return "Unknown";
  if (f.key === "line_item") return `${f.raw_text ?? ""} · ₹${Number(f.value).toLocaleString("en-IN")}`;
  if (f.key === "waiting_period") return `${f.raw_text ?? ""} · ${f.value} days`;
  if (typeof f.value === "number" && /amount|total|sum_insured|room_rent/.test(f.key))
    return `₹${f.value.toLocaleString("en-IN")}`;
  return String(f.value);
}

export const needsReview = (f: ExtractedField) =>
  CRITICAL_KEYS.has(f.key) && f.confidence < REVIEW_THRESHOLD && !f.user_confirmed;

function Confidence({ f }: { f: ExtractedField }) {
  if (f.user_confirmed) return <Badge variant="secondary">Confirmed</Badge>;
  const pct = Math.round(f.confidence * 100);
  if (f.confidence < REVIEW_THRESHOLD)
    return <Badge variant="destructive">Low confidence {pct}%</Badge>;
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
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const toReview = results.fields.filter(needsReview);

  return (
    <div className="space-y-5">
      {toReview.length > 0 && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
          <p className="font-medium">Please confirm {toReview.length} value{toReview.length > 1 ? "s" : ""}</p>
          <p className="text-xs text-muted-foreground">
            Covara was not sure about these important values. Check them against the document and
            confirm or correct them. Unknown values are never guessed.
          </p>
        </div>
      )}
      {results.documents.map((doc) => {
        const fields = results.fields.filter((f) => f.evidence.document_id === doc.id);
        return (
          <section key={doc.id} className="rounded-lg border">
            <header className="flex flex-wrap items-center gap-2 border-b px-3 py-2">
              <p className="text-sm font-medium">{doc.filename}</p>
              <Badge variant="secondary">{typeLabel(doc.doc_type)}</Badge>
              {doc.detected_type && doc.detected_type !== doc.doc_type && (
                <span className="text-xs text-muted-foreground">
                  (looks like: {typeLabel(doc.detected_type)})
                </span>
              )}
              <span className="ml-auto text-xs text-muted-foreground">
                {doc.status === "failed"
                  ? doc.error
                  : `${doc.pages} page${doc.pages === 1 ? "" : "s"} · read by ${doc.extraction_method ?? "—"}`}
              </span>
            </header>
            {fields.length === 0 ? (
              <p className="px-3 py-3 text-sm text-muted-foreground">No details extracted.</p>
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
                      {FIELD_LABELS[f.key] ?? f.key}
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
                            aria-label={`Correct ${FIELD_LABELS[f.key] ?? f.key}`}
                          />
                          <Button size="icon-sm" type="submit" aria-label="Save">
                            <Check />
                          </Button>
                          <Button size="icon-sm" variant="ghost" type="button" onClick={() => setEditing(null)} aria-label="Cancel">
                            <X />
                          </Button>
                        </form>
                      ) : (
                        <p className={`truncate text-sm ${f.value === null ? "italic text-muted-foreground" : ""}`}>
                          {fmt(f)}
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
                          Confirm
                        </Button>
                      )}
                      <Button
                        size="icon-xs"
                        variant="ghost"
                        disabled={busy}
                        aria-label="Correct value"
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
