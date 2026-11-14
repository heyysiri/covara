"use client";

import { useState } from "react";
import { Banknote, Check, ChevronDown, Hospital, Info, Loader2, Lock } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { BottomBar, PrimaryButton } from "@/features/flow/AppShell";
import { useI18n } from "@/i18n";
import type { ClaimType } from "@/types/claim";

const field = "h-12 w-full rounded-xl border bg-card px-4 text-base outline-none transition-shadow placeholder:text-muted-foreground/70 focus:border-brand focus:ring-4 focus:ring-brand/20";

export interface DetailsState {
  claimType: ClaimType;
  amount: string;
  name: string;
  consent: boolean;
}

/** Step 1: three questions, one screen. */
export function StepDetails({
  value,
  onChange,
  locked,
  fromPayment,
  busy,
  error,
  onContinue,
}: {
  value: DetailsState;
  onChange: (v: DetailsState) => void;
  /** The claim already exists (consent recorded), so the claim type and consent can no longer change. */
  locked: boolean;
  fromPayment: boolean;
  busy: boolean;
  error: string | null;
  onContinue: () => void;
}) {
  const { t } = useI18n();
  const [more, setMore] = useState(false);
  const set = (p: Partial<DetailsState>) => onChange({ ...value, ...p });
  const types: { id: ClaimType; icon: typeof Banknote; title: string; text: string }[] = [
    { id: "reimbursement", icon: Banknote, title: t("Reimbursement"), text: t("You paid the hospital and want the money back") },
    { id: "cashless", icon: Hospital, title: t("Cashless"), text: t("The hospital bills your insurer directly") },
  ];
  return (
    <>
      <h2 className="text-xl font-semibold text-navy">{t("Tell us about your claim")}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{t("Three quick questions. You can change the amount later.")}</p>

      <fieldset className="mt-5" disabled={locked}>
        <legend className="mb-2 text-sm font-medium">{t("What kind of claim is it?")}</legend>
        <div className="grid gap-2.5">
          {types.map(({ id, icon: Icon, title, text }) => {
            const on = value.claimType === id;
            return (
              <label key={id} className={`flex cursor-pointer items-center gap-3 rounded-2xl border-2 bg-card p-3.5 transition-colors ${on ? "border-brand bg-[#f1fbff]" : "border-border"} ${locked ? "opacity-70" : ""}`}>
                <input type="radio" name="claim-type" value={id} checked={on} onChange={() => set({ claimType: id })} className="sr-only" />
                <span className={`flex size-11 shrink-0 items-center justify-center rounded-full ${on ? "bg-brand text-navy" : "bg-secondary text-navy"}`}>
                  <Icon className="size-5" aria-hidden />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold text-navy">{title}</span>
                  <span className="block text-sm text-muted-foreground">{text}</span>
                </span>
                {on && <Check className="size-5 text-brand" aria-hidden />}
              </label>
            );
          })}
        </div>
      </fieldset>

      <label className="mt-5 block text-sm font-medium" htmlFor="amount">
        {t("How much are you claiming?")}
      </label>
      <div className="relative mt-2">
        <span className="pointer-events-none absolute inset-y-0 left-4 flex items-center text-lg font-semibold text-navy">₹</span>
        <input
          id="amount"
          inputMode="decimal"
          autoComplete="off"
          placeholder={t("e.g. 95000")}
          value={value.amount}
          onChange={(e) => set({ amount: e.target.value })}
          className={`${field} pl-9 text-lg font-semibold`}
        />
      </div>
      {fromPayment && (
        <p className="mt-1.5 flex items-center gap-1.5 text-xs text-navy/70">
          <Info className="size-3.5" aria-hidden /> {t("Filled in from your hospital payment. Change it if you are claiming a different amount.")}
        </p>
      )}

      <label className="mt-5 block text-sm font-medium" htmlFor="patient">
        {t("Patient name")} <span className="font-normal text-muted-foreground">({t("optional")})</span>
      </label>
      <input id="patient" autoComplete="name" placeholder={t("As written on the policy")} value={value.name} onChange={(e) => set({ name: e.target.value })} className={`${field} mt-2`} />

      <div className="mt-6 rounded-2xl border bg-card p-4">
        <label className={`flex items-start gap-3 ${locked ? "opacity-70" : "cursor-pointer"}`}>
          <input type="checkbox" checked={value.consent} disabled={locked} onChange={(e) => set({ consent: e.target.checked })} className="mt-0.5 size-5 shrink-0 accent-[#002e6e]" />
          <span className="text-sm">
            <span className="flex items-center gap-1.5 font-medium text-navy">
              <Lock className="size-3.5" aria-hidden /> {t("I agree to Covara checking my documents")}
            </span>
            <span className="mt-0.5 block text-muted-foreground">{t("Only to prepare this claim. You can delete everything at any time.")}</span>
          </span>
        </label>
        <button type="button" onClick={() => setMore(!more)} aria-expanded={more} className="mt-2 flex items-center gap-1 text-sm font-medium text-navy">
          {t("How is my data used?")} <ChevronDown className={`size-4 transition-transform ${more ? "rotate-180" : ""}`} aria-hidden />
        </button>
        {more && (
          <p className="mt-2 text-sm text-muted-foreground">
            {t('Documents are read by AI services (Claude and Sarvam) only to extract claim details, are not used for any other purpose, and can be deleted at any time with "Delete my data". Claims are removed automatically after a few days.')}
          </p>
        )}
      </div>

      {error && (
        <Alert variant="destructive" className="mt-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <BottomBar>
        <PrimaryButton onClick={onContinue} disabled={busy || !value.consent}>
          {busy && <Loader2 className="animate-spin" />} {t("Continue")}
        </PrimaryButton>
        {!value.consent && <p className="mt-1.5 text-center text-xs text-muted-foreground">{t("Tick the box above to continue.")}</p>}
      </BottomBar>
    </>
  );
}
