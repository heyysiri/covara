"use client";

import Link from "next/link";
import { ArrowRight, FileSearch, Link2, ListChecks, ShieldCheck } from "lucide-react";

import { BackendStatus } from "@/components/BackendStatus";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { LanguageSelect, useI18n } from "@/i18n";

export default function Home() {
  const { t } = useI18n();
  const features = [
    {
      icon: FileSearch,
      title: t("Cross-check your documents"),
      text: t("Compare names, dates and amounts across your policy, bills and discharge summary."),
    },
    {
      icon: Link2,
      title: t("Evidence-linked findings"),
      text: t("Every finding points to the document page and the relevant policy clause."),
    },
    {
      icon: ListChecks,
      title: t("A clear action plan"),
      text: t("Know what to upload, verify or clarify before you submit your claim."),
    },
  ];

  return (
    <div className="flex min-h-screen flex-col">
      <header className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-5">
        <span className="flex items-center gap-2 text-lg font-semibold tracking-tight">
          <ShieldCheck className="size-6 text-brand" aria-hidden /> <span className="text-navy dark:text-foreground">Covara</span>
        </span>
        <div className="flex items-center gap-2">
          <LanguageSelect />
          <BackendStatus />
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-6">
        <section className="my-6 rounded-3xl bg-gradient-to-br from-[#002e6e] via-[#04479a] to-[#0a8fd6] px-6 py-14 text-white shadow-lg sm:my-10 sm:px-12 sm:py-20">
          <p className="mb-3 text-sm font-medium text-[#8fdcfa]">
            {t("AI-powered insurance claim readiness and intelligence")}
          </p>
          <h1 className="max-w-2xl text-4xl font-semibold tracking-tight sm:text-5xl">
            {t("Know your coverage. Prepare with confidence.")}
          </h1>
          <p className="mt-5 max-w-xl text-lg text-white/85">
            {t("Upload your health-insurance policy and hospital documents. Covara checks them against each other, surfaces gaps and inconsistencies, and gives you a claim-preparation report.")}
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/claim" className={buttonVariants({ size: "lg", className: "bg-brand! text-navy! hover:bg-[#33c9f5]!" })}>
              {t("Start a claim")} <ArrowRight />
            </Link>
          </div>
        </section>

        <section className="grid gap-4 pb-16 sm:grid-cols-3">
          {features.map(({ icon: Icon, title, text }) => (
            <Card key={title}>
              <CardHeader>
                <span className="mb-3 flex size-10 items-center justify-center rounded-full bg-secondary"><Icon className="size-5 text-navy" aria-hidden /></span>
                <CardTitle>{title}</CardTitle>
                <CardDescription>{text}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </section>
      </main>

      <footer className="mx-auto w-full max-w-5xl px-6 py-6 text-xs text-muted-foreground">
        {t("Covara is an AI-assisted preparation tool. It does not decide whether an insurer will approve a claim and does not replace an insurer, doctor, broker or licensed adviser. Use synthetic documents for demos.")}
      </footer>
    </div>
  );
}
