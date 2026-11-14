import type { Metadata } from "next";
import Link from "next/link";
import { ShieldCheck } from "lucide-react";

import { BackendStatus } from "@/components/BackendStatus";
import { DocumentUpload } from "@/components/DocumentUpload";

export const metadata: Metadata = { title: "New claim · Covara" };

export default function ClaimPage() {
  return (
    <div className="mx-auto flex min-h-screen w-full max-w-3xl flex-col px-6">
      <header className="flex items-center justify-between py-5">
        <Link href="/" className="flex items-center gap-2 text-lg font-semibold tracking-tight">
          <ShieldCheck className="size-5" aria-hidden /> Covara
        </Link>
        <BackendStatus />
      </header>
      <main className="flex-1 pb-16">
        <h1 className="mb-1 text-2xl font-semibold tracking-tight">Prepare a claim</h1>
        <p className="mb-6 text-sm text-muted-foreground">
          Upload your documents to start a claim-preparation session.
        </p>
        <DocumentUpload />
      </main>
      <footer className="py-6 text-xs text-muted-foreground">
        AI-assisted preparation tool, not an insurer decision.
      </footer>
    </div>
  );
}
