"use client";

import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { ChevronLeft, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { LanguageSelect, useI18n } from "@/i18n";

/**
 * The app frame every screen lives in. Mobile first: full-bleed on a phone; on a laptop it is a centred phone-width
 * column, so the demo reads as "a step inside a mobile app". Header, content, and a fixed bottom bar for the main action.
 */
export function AppShell({
  title,
  subtitle,
  onBack,
  backHref,
  step,
  bottom,
  padBottom,
  children,
  tall = false,
}: {
  title: string;
  subtitle?: string;
  onBack?: () => void;
  backHref?: string;
  step?: { index: number; total: number };
  bottom?: ReactNode;
  /** Reserve room for a fixed bar that the page renders itself (defaults to true when `bottom` is given). */
  padBottom?: boolean;
  children: ReactNode;
  /** Taller header with room for a hero (used by the home screen). */
  tall?: boolean;
}) {
  const { t } = useI18n();
  const back = (
    <span className="flex size-9 items-center justify-center rounded-full bg-white/10 transition-colors hover:bg-white/20">
      <ChevronLeft className="size-5" aria-hidden />
    </span>
  );
  return (
    <div className="min-h-dvh bg-[#e4eef9] md:py-6">
      <div className="relative mx-auto flex min-h-dvh w-full max-w-[480px] flex-col overflow-x-clip bg-background md:min-h-[calc(100dvh-3rem)] md:overflow-hidden md:rounded-[2rem] md:border md:shadow-2xl">
        <header className={`bg-gradient-to-br from-[#002e6e] via-[#04479a] to-[#0a6fc4] px-4 text-white ${tall ? "pb-14 pt-4" : "pb-5 pt-4"}`}>
          <div className="flex items-center gap-2">
            {onBack ? (
              <button type="button" onClick={onBack} aria-label={t("Back")} className="-ml-1">
                {back}
              </button>
            ) : backHref ? (
              <Link href={backHref} aria-label={t("Back")} className="-ml-1">
                {back}
              </Link>
            ) : (
              <ShieldCheck className="size-6 text-brand" aria-hidden />
            )}
            <h1 className="min-w-0 flex-1 truncate text-lg font-semibold tracking-tight">{title}</h1>
            <LanguageSelect className="h-8 w-[5.5rem] border-white/30 bg-white/10 text-white [&>option]:text-black" />
          </div>
          {subtitle && <p className="mt-2 text-sm text-white/80">{subtitle}</p>}
          {step && (
            <div className="mt-4" role="progressbar" aria-valuemin={1} aria-valuemax={step.total} aria-valuenow={step.index}>
              <div className="flex gap-1.5">
                {Array.from({ length: step.total }, (_, i) => (
                  <span key={i} className={`h-1.5 flex-1 rounded-full transition-colors ${i < step.index ? "bg-brand" : "bg-white/25"}`} />
                ))}
              </div>
              <p className="mt-1.5 text-xs text-white/70">{t("Step {n} of {m}", { n: step.index, m: step.total })}</p>
            </div>
          )}
        </header>
        <main className={`flex-1 px-4 ${tall ? "-mt-8" : "pt-4"} ${bottom || padBottom ? "pb-32" : "pb-10"}`}>{children}</main>
        {bottom}
      </div>
    </div>
  );
}

/** Fixed action bar at the bottom of the screen, aligned with the app column. */
export function BottomBar({ children }: { children: ReactNode }) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-40 mx-auto w-full max-w-[480px] border-t bg-card/95 px-4 pt-3 shadow-[0_-4px_16px_rgba(0,46,110,0.08)] backdrop-blur pb-[max(0.75rem,env(safe-area-inset-bottom))]">
      {children}
    </div>
  );
}

/** Paytm-style primary action: cyan pill, navy text, thumb-sized. */
export function PrimaryButton({ className = "", ...props }: ComponentProps<typeof Button>) {
  return (
    <Button
      {...props}
      className={`h-12 w-full rounded-full bg-brand! text-base font-semibold text-navy! hover:bg-[#33c9f5]! disabled:opacity-45 ${className}`}
    />
  );
}

export function SecondaryButton({ className = "", ...props }: ComponentProps<typeof Button>) {
  return <Button variant="outline" {...props} className={`h-12 w-full rounded-full border-navy/25 text-base font-semibold text-navy ${className}`} />;
}
