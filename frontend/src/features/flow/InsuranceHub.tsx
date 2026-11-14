"use client";

import Link from "next/link";
import {
  ArrowRight,
  Banknote,
  Bell,
  ClipboardCheck,
  FileText,
  HeartPulse,
  Home,
  Hospital,
  RefreshCw,
  Search,
  ShieldCheck,
  User,
  Wallet,
} from "lucide-react";

import { AppShell } from "@/features/flow/AppShell";
import { useI18n } from "@/i18n";

/**
 * "Where Covara fits": a mock of the Insurance section of a payments super-app. The Claim readiness tile is the new step.
 * Everything here is a demo screen with synthetic data, not an integration.
 */
export function InsuranceHub() {
  const { t } = useI18n();
  const tiles = [
    { icon: HeartPulse, label: t("Buy health plan") },
    { icon: FileText, label: t("My policies") },
    { icon: RefreshCw, label: t("Renew") },
    { icon: Banknote, label: t("Track claim") },
  ];
  return (
    <AppShell title={t("Insurance")} tall bottom={<HubNav />}>
      <div className="mb-5 flex items-center gap-2 rounded-2xl border bg-card px-4 py-3 text-sm text-muted-foreground shadow-sm">
        <Search className="size-4" aria-hidden /> {t("Search insurance, claims, policies")}
      </div>

      <Link
        href="/claim?amount=85000&source=payment"
        className="group block rounded-2xl border border-brand/40 bg-gradient-to-br from-[#e6f8ff] to-white p-4 shadow-sm transition-shadow hover:shadow-md"
      >
        <div className="flex items-start gap-3">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-navy text-white">
            <Hospital className="size-5" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <p className="flex items-center gap-1.5 text-xs font-medium text-navy/70">
              <Bell className="size-3.5" aria-hidden /> {t("You paid a hospital")}
            </p>
            <p className="mt-0.5 font-semibold text-navy">{t("₹85,000 to Demo City Care Hospital")}</p>
            <p className="mt-0.5 text-sm text-muted-foreground">{t("Planning to claim this from your insurer? Check your papers first.")}</p>
          </div>
        </div>
        <span className="mt-3 flex h-11 items-center justify-center gap-2 rounded-full bg-brand text-sm font-semibold text-navy transition-colors group-hover:bg-[#33c9f5]">
          {t("Prepare my claim")} <ArrowRight className="size-4" aria-hidden />
        </span>
      </Link>

      <h2 className="mb-3 mt-7 text-base font-semibold text-navy">{t("Health insurance")}</h2>
      <div className="grid grid-cols-4 gap-2 text-center">
        {tiles.map(({ icon: Icon, label }) => (
          <div key={label} className="space-y-1.5" aria-hidden>
            <span className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-secondary text-navy">
              <Icon className="size-6" />
            </span>
            <p className="text-[11px] leading-tight text-foreground/80">{label}</p>
          </div>
        ))}
      </div>

      <Link
        href="/claim"
        className="mt-5 flex items-center gap-3 rounded-2xl border-2 border-brand bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
      >
        <span className="relative flex size-14 shrink-0 items-center justify-center rounded-2xl bg-brand text-navy">
          <ClipboardCheck className="size-7" aria-hidden />
          <span className="absolute -right-2 -top-2 rounded-full bg-[#ff4f6d] px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">{t("New")}</span>
        </span>
        <span className="min-w-0 flex-1">
          <span className="block font-semibold text-navy">{t("Claim readiness")}</span>
          <span className="block text-sm text-muted-foreground">{t("Check your hospital papers before you submit your claim")}</span>
        </span>
        <ArrowRight className="size-5 shrink-0 text-navy" aria-hidden />
      </Link>

      <h2 className="mb-3 mt-7 text-base font-semibold text-navy">{t("Why check before you claim?")}</h2>
      <ul className="space-y-2.5">
        {[
          t("Catch mismatched names, dates and amounts before the insurer does"),
          t("See which policy condition applies, with the exact wording"),
          t("Get a simple to-do list and a ready claim packet"),
        ].map((text) => (
          <li key={text} className="flex items-start gap-3 rounded-xl bg-card p-3 text-sm shadow-sm">
            <ShieldCheck className="mt-0.5 size-5 shrink-0 text-brand" aria-hidden /> {text}
          </li>
        ))}
      </ul>

      <p className="mt-7 rounded-xl bg-muted/60 p-3 text-xs text-muted-foreground">
        {t("Demo screen: this shows where Covara could appear inside a payments app. Other tiles are placeholders. Covara is an AI-assisted preparation tool and does not decide whether an insurer will approve a claim.")}
      </p>
    </AppShell>
  );
}

function HubNav() {
  const { t } = useI18n();
  const items = [
    { icon: Home, label: t("Home"), active: false },
    { icon: ShieldCheck, label: t("Insurance"), active: true },
    { icon: Wallet, label: t("Payments"), active: false },
    { icon: User, label: t("Profile"), active: false },
  ];
  return (
    <nav aria-label={t("Main")} className="fixed inset-x-0 bottom-0 z-40 mx-auto grid w-full max-w-[480px] grid-cols-4 md:hidden border-t bg-card/95 pt-2 shadow-[0_-4px_16px_rgba(0,46,110,0.08)] backdrop-blur pb-[max(0.5rem,env(safe-area-inset-bottom))]">
      {items.map(({ icon: Icon, label, active }) => (
        <span key={label} aria-current={active ? "page" : undefined} className={`flex flex-col items-center gap-0.5 py-1 text-[11px] ${active ? "font-semibold text-navy" : "text-muted-foreground"}`}>
          <Icon className={`size-5 ${active ? "text-brand" : ""}`} aria-hidden /> {label}
        </span>
      ))}
    </nav>
  );
}
