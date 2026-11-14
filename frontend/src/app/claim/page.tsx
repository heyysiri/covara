import type { Metadata } from "next";
import { Suspense } from "react";

import { ClaimFlow } from "@/features/flow/ClaimFlow";

export const metadata: Metadata = { title: "Claim readiness · Covara" };

const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);

// Reading searchParams is request-time data, so it must sit inside a Suspense boundary (Next.js 16).
async function WithParams({ searchParams }: { searchParams: PageProps<"/claim">["searchParams"] }) {
  const sp = await searchParams;
  return <ClaimFlow initialAmount={one(sp.amount)} source={one(sp.source)} />;
}

export default function ClaimPage({ searchParams }: PageProps<"/claim">) {
  return (
    <Suspense fallback={<div className="min-h-dvh bg-[#002e6e]" aria-busy="true" />}>
      <WithParams searchParams={searchParams} />
    </Suspense>
  );
}
