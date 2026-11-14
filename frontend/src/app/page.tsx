import Link from "next/link";
import { ArrowRight, FileSearch, Link2, ListChecks, ShieldCheck } from "lucide-react";

import { BackendStatus } from "@/components/BackendStatus";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const FEATURES = [
  {
    icon: FileSearch,
    title: "Cross-check your documents",
    text: "Compare names, dates and amounts across your policy, bills and discharge summary.",
  },
  {
    icon: Link2,
    title: "Evidence-linked findings",
    text: "Every finding points to the document page and the relevant policy clause.",
  },
  {
    icon: ListChecks,
    title: "A clear action plan",
    text: "Know what to upload, verify or clarify before you submit your claim.",
  },
];

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-5">
        <span className="flex items-center gap-2 text-lg font-semibold tracking-tight">
          <ShieldCheck className="size-5" aria-hidden /> Covara
        </span>
        <BackendStatus />
      </header>

      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-6">
        <section className="py-16 sm:py-24">
          <p className="mb-3 text-sm font-medium text-muted-foreground">
            AI-powered insurance claim readiness and intelligence
          </p>
          <h1 className="max-w-2xl text-4xl font-semibold tracking-tight sm:text-5xl">
            Know your coverage. Prepare with confidence.
          </h1>
          <p className="mt-5 max-w-xl text-lg text-muted-foreground">
            Upload your health-insurance policy and hospital documents. Covara checks them against
            each other, surfaces gaps and inconsistencies, and gives you a claim-preparation report.
          </p>
          <div className="mt-8">
            <Link href="/claim" className={buttonVariants({ size: "lg" })}>
              Start a claim <ArrowRight />
            </Link>
          </div>
        </section>

        <section className="grid gap-4 pb-16 sm:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <Card key={title}>
              <CardHeader>
                <Icon className="mb-2 size-5 text-muted-foreground" aria-hidden />
                <CardTitle>{title}</CardTitle>
                <CardDescription>{text}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </section>
      </main>

      <footer className="mx-auto w-full max-w-5xl px-6 py-6 text-xs text-muted-foreground">
        Covara is an AI-assisted preparation tool. It does not decide whether an insurer will
        approve a claim and does not replace an insurer, doctor, broker or licensed adviser. Use
        synthetic documents for demos.
      </footer>
    </div>
  );
}
