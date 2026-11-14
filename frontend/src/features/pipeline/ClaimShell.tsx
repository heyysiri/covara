"use client";

import Link from "next/link";
import { ShieldCheck } from "lucide-react";

import { BackendStatus } from "@/components/BackendStatus";
import { DocumentUpload } from "@/components/DocumentUpload";
import { LanguageSelect, useI18n } from "@/i18n";

/** Translatable page chrome for /claim (the page itself stays a server component for its metadata). */
export function ClaimShell() {
  const { t } = useI18n();
  return (
    <div className="flex min-h-screen flex-col">
      <header className="bg-gradient-to-br from-[#002e6e] to-[#04479a] pb-16 pt-4 text-white">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2 text-lg font-semibold tracking-tight">
            <ShieldCheck className="size-6 text-brand" aria-hidden /> Covara
          </Link>
          <div className="flex items-center gap-2">
            <LanguageSelect className="border-white/30 bg-white/10 text-white [&>option]:text-black" />
            <BackendStatus />
          </div>
        </div>
        <div className="mx-auto mt-5 w-full max-w-3xl px-4 sm:px-6">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("Prepare a claim")}</h1>
          <p className="mt-1 text-sm text-white/80">{t("Upload your documents to start a claim-preparation session.")}</p>
        </div>
      </header>
      <main className="mx-auto -mt-10 w-full max-w-3xl flex-1 px-4 pb-16 sm:px-6">
        <DocumentUpload />
      </main>
      <footer className="mx-auto w-full max-w-3xl px-4 py-6 text-xs text-muted-foreground sm:px-6">
        {t("AI-assisted preparation tool, not an insurer decision.")}
      </footer>
    </div>
  );
}
