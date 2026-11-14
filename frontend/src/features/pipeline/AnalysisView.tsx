"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, Info, ListChecks, Loader2, MoreHorizontal, Package, RefreshCw, Search, XCircle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ActionPlan } from "@/features/actions/ActionPlan";
import { ExtractedData, needsReview } from "@/features/extraction/ExtractedData";
import { SecondaryButton } from "@/features/flow/AppShell";
import { Checklist } from "@/features/intake/Checklist";
import { DeleteClaimButton } from "@/features/intake/DeleteClaimButton";
import { PacketPanel } from "@/features/packet/PacketPanel";
import { PolicyPanel } from "@/features/policy/PolicyPanel";
import { FindingsPanel } from "@/features/verification/FindingsPanel";
import { ListenButton } from "@/features/voice/ListenButton";
import { useI18n, useLocalized } from "@/i18n";
import type { FieldEdit } from "@/lib/api";
import type { AnalysisResults } from "@/types/results";

import { AnalysisProgress } from "./AnalysisProgress";

type Tab = "todo" | "findings" | "packet" | "more";
type More = "extracted" | "policy" | "checklist";

/**
 * The results screen of the claim flow. Mobile first: a status card, then one section at a time, switched from a bottom
 * tab bar (To do / Findings / Packet / More). "To do" comes first because the point is what the policyholder does next.
 */
export function AnalysisView({
  claimId,
  results,
  onRecheck,
  onReview,
  onResults,
  onAddDocuments,
  onDeleted,
  claimedAmount,
  onSaveAmount,
}: {
  claimId: string;
  results: AnalysisResults;
  onRecheck: () => void;
  onReview: (edits: FieldEdit[]) => void;
  onResults: (r: AnalysisResults) => void;
  onAddDocuments: () => void;
  onDeleted: () => void;
  claimedAmount: number | null;
  /** Save the claimed amount on the claim. */
  onSaveAmount: (amount: number | null) => Promise<void>;
}) {
  const { t } = useI18n();
  const READINESS = {
    ready: { label: t("Ready to submit"), icon: CheckCircle2, cls: "border-emerald-500/40 bg-emerald-50 text-emerald-900", icon_cls: "text-emerald-600" },
    needs_attention: { label: t("Needs attention"), icon: AlertTriangle, cls: "border-amber-500/50 bg-amber-50 text-amber-950", icon_cls: "text-amber-600" },
    incomplete: { label: t("Incomplete"), icon: XCircle, cls: "border-destructive/40 bg-red-50 text-red-950", icon_cls: "text-destructive" },
  } as const;
  const [explanationL, errorL, disclaimerL, ...warningsL] = useLocalized([
    results.readiness_explanation,
    results.error ?? "",
    results.disclaimer,
    ...results.warnings,
  ]);
  const [tab, setTab] = useState<Tab>("todo");
  const [amountText, setAmountText] = useState(claimedAmount == null ? "" : String(claimedAmount));
  const [saving, setSaving] = useState(false);
  const [focus, setFocus] = useState<string | null>(null); // a finding to open straight away on the Findings tab
  const [more, setMore] = useState<More>("extracted");
  const running = results.status === "processing";
  const open = results.findings.filter((f) => f.status === "open");
  const blocking = open.filter((f) => f.blocking).length;
  const openActions = results.action_plan.filter((a) => !a.done).length;
  const reviewCount = results.fields.filter(needsReview).length;
  const r = results.readiness_status ? READINESS[results.readiness_status] : null;

  const nav: { id: Tab; label: string; icon: typeof ListChecks; badge?: number }[] = [
    { id: "todo", label: t("To do"), icon: ListChecks, badge: openActions },
    { id: "findings", label: t("Findings"), icon: Search, badge: open.length },
    { id: "packet", label: t("Packet"), icon: Package },
    { id: "more", label: t("More"), icon: MoreHorizontal, badge: reviewCount },
  ];

  function viewEvidence(findingId: string) {
    setFocus(findingId);
    setTab("findings");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="flex flex-col gap-4">
      {results.status === "failed" && (
        <Alert variant="destructive">
          <AlertTitle>{t("Analysis failed")}</AlertTitle>
          <AlertDescription>{errorL}</AlertDescription>
        </Alert>
      )}

      {running && (
        <div className="rounded-2xl border bg-card p-4">
          <AnalysisProgress results={results} />
        </div>
      )}

      {r && tab !== "todo" && tab !== "packet" && (
        <section className={`md:order-1 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-2xl border px-4 py-3 ${r.cls}`} aria-live="polite">
          <r.icon className={`size-5 shrink-0 ${r.icon_cls}`} aria-hidden />
          <span className="font-semibold">{r.label}</span>
          {open.length > 0 && (
            <span className="ml-auto text-xs font-medium opacity-80">
              {[blocking > 0 && t("{n} to fix before submitting", { n: blocking }), open.length - blocking > 0 && t("{n} to review", { n: open.length - blocking })]
                .filter(Boolean)
                .join(" · ")}
            </span>
          )}
        </section>
      )}

      {r && tab === "todo" && (
        <section className={`md:order-1 rounded-2xl border p-4 ${r.cls}`} aria-live="polite">
          <div className="flex items-start gap-3">
            <r.icon className={`mt-0.5 size-7 shrink-0 ${r.icon_cls}`} aria-hidden />
            <div className="min-w-0 flex-1">
              <h2 className="text-lg font-semibold">{r.label}</h2>
              <p className="mt-0.5 text-sm opacity-90">{explanationL}</p>
            </div>
          </div>
          {open.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium">
              {blocking > 0 && <span className="rounded-full bg-white/70 px-2.5 py-1">{t("{n} to fix before submitting", { n: blocking })}</span>}
              {open.length - blocking > 0 && <span className="rounded-full bg-white/70 px-2.5 py-1">{t("{n} to review", { n: open.length - blocking })}</span>}
            </div>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <ListenButton claimId={claimId} disabled={running} />
            <button
              type="button"
              onClick={onRecheck}
              disabled={running}
              className="ml-auto flex h-10 items-center gap-1.5 rounded-full border border-current/25 bg-white/70 px-4 text-sm font-semibold disabled:opacity-50"
            >
              {running ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />} {t("Re-check")}
            </button>
          </div>
        </section>
      )}

      {results.warnings.length > 0 && (
        <ul className="space-y-1 md:order-2">
          {results.warnings.map((w, i) => (
            <li key={w} className="flex items-start gap-2 text-xs text-muted-foreground">
              <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden /> {warningsL[i]}
            </li>
          ))}
        </ul>
      )}

      <div role="tabpanel" aria-label={nav.find((n) => n.id === tab)?.label} className="md:order-4">
        {tab === "todo" && (
          <section className="mb-4 rounded-2xl border bg-card p-4">
            <h3 className="text-sm font-semibold text-navy">{t("Fixed something? Update your claim")}</h3>
            <label htmlFor="fix-amount" className="mt-3 block text-xs font-medium">
              {t("Amount you are claiming (₹)")}
            </label>
            <div className="mt-1 flex gap-2">
              <input
                id="fix-amount"
                inputMode="decimal"
                value={amountText}
                onChange={(e) => setAmountText(e.target.value)}
                className="h-11 min-w-0 flex-1 rounded-xl border bg-background px-3 text-base outline-none focus:border-brand focus:ring-4 focus:ring-brand/20"
              />
              <button
                type="button"
                disabled={running || saving}
                onClick={async () => {
                  const n = amountText.trim() ? Number(amountText.replace(/[,₹\s]/g, "")) : null;
                  if (n !== null && Number.isNaN(n)) return;
                  setSaving(true);
                  try {
                    await onSaveAmount(n);
                    onRecheck();
                  } finally {
                    setSaving(false);
                  }
                }}
                className="h-11 shrink-0 rounded-full bg-brand px-4 text-sm font-semibold text-navy disabled:opacity-50"
              >
                {saving ? <Loader2 className="size-4 animate-spin" /> : t("Save & re-check")}
              </button>
            </div>
            <button type="button" onClick={onAddDocuments} className="mt-3 text-sm font-medium text-navy underline underline-offset-2">
              {t("Add or remove documents")}
            </button>
          </section>
        )}
        {tab === "todo" && <ActionPlan claimId={claimId} results={results} onChange={(action_plan) => onResults({ ...results, action_plan })} onViewEvidence={viewEvidence} />}
        {tab === "findings" && <FindingsPanel key={focus ?? "list"} claimId={claimId} results={results} initialOpenId={focus} />}
        {tab === "packet" && <PacketPanel claimId={claimId} results={results} />}
        {tab === "more" && (
          <div className="space-y-4">
            <div className="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden" role="tablist">
              {([["extracted", t("Extracted data")], ["policy", t("Policy")], ["checklist", t("Checklist")]] as [More, string][]).map(([id, label]) => (
                <button
                  key={id}
                  role="tab"
                  aria-selected={more === id}
                  onClick={() => setMore(id)}
                  className={`shrink-0 rounded-full border px-4 py-2 text-sm font-medium ${more === id ? "border-navy bg-navy text-white" : "bg-card text-navy"}`}
                >
                  {label}
                  {id === "extracted" && reviewCount > 0 && ` · ${t("{n} to confirm", { n: reviewCount })}`}
                </button>
              ))}
            </div>
            {more === "extracted" && <ExtractedData claimId={claimId} results={results} onReview={onReview} busy={running} />}
            {more === "policy" && <PolicyPanel claimId={claimId} results={results} />}
            {more === "checklist" && <Checklist items={results.checklist} />}
            <SecondaryButton onClick={onAddDocuments}>{t("Add or change documents")}</SecondaryButton>
            <div className="flex justify-center">
              <DeleteClaimButton claimId={claimId} onDeleted={onDeleted} />
            </div>
          </div>
        )}
      </div>

      <p className="pt-2 text-xs text-muted-foreground md:order-5">
        {t("Every value links to its source page.")} {disclaimerL}
      </p>

      <nav
        aria-label={t("Results")}
        className="fixed inset-x-0 bottom-0 z-40 mx-auto grid w-full max-w-[480px] grid-cols-4 border-t bg-card/95 pt-1.5 shadow-[0_-4px_16px_rgba(0,46,110,0.08)] backdrop-blur pb-[max(0.5rem,env(safe-area-inset-bottom))] md:static md:order-3 md:max-w-none md:rounded-2xl md:border md:bg-card md:p-1 md:shadow-none"
      >
        {nav.map(({ id, label, icon: Icon, badge }) => {
          const on = tab === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => {
                setFocus(null);
                setTab(id);
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
              aria-current={on ? "page" : undefined}
              className={`relative flex flex-col items-center gap-0.5 py-1.5 text-[11px] md:flex-row md:justify-center md:gap-2 md:rounded-xl md:py-3 md:text-sm ${on ? "font-semibold text-navy md:bg-secondary" : "text-muted-foreground md:hover:bg-muted"}`}
            >
              <span className="relative">
                <Icon className={`size-6 ${on ? "text-brand" : ""}`} aria-hidden />
                {!!badge && (
                  <span className="absolute -right-2.5 -top-1.5 min-w-4 rounded-full bg-[#ff4f6d] px-1 text-center text-[10px] font-bold leading-4 text-white">{badge}</span>
                )}
              </span>
              {label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
