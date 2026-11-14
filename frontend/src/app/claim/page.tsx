import type { Metadata } from "next";

import { ClaimShell } from "@/features/pipeline/ClaimShell";

export const metadata: Metadata = { title: "New claim · Covara" };

export default function ClaimPage() {
  return <ClaimShell />;
}
