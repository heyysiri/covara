import { PacketPanel } from "@/features/packet/PacketPanel";
import { FindingsPanel } from "@/features/verification/FindingsPanel";
import type { ExtraTab } from "@/features/pipeline/AnalysisView";

/** Tabs owned by Person 2, plugged into the shared AnalysisView (Findings with its evidence viewer, then Packet). */
export function buildExtraTabs(claimId: string): ExtraTab[] {
  return [
    {
      id: "findings",
      first: true,
      label: (r) => `Findings${r.findings.length ? ` (${r.findings.length})` : ""}`,
      render: (r) => <FindingsPanel claimId={claimId} results={r} />,
    },
    { id: "packet", label: "Claim packet", render: (r) => <PacketPanel claimId={claimId} results={r} /> },
  ];
}
