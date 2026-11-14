"use client";

import { useState } from "react";
import { Loader2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { deleteClaim } from "@/lib/api";

/** "Delete my data": removes files, extracted data, results and cached model outputs. */
export function DeleteClaimButton({ claimId, onDeleted }: { claimId: string; onDeleted: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  if (!confirming)
    return (
      <Button variant="ghost" size="sm" onClick={() => setConfirming(true)}>
        <Trash2 /> Delete my data
      </Button>
    );
  return (
    <span className="flex items-center gap-2 text-xs">
      Delete all files and results for this claim?
      <Button
        variant="destructive"
        size="sm"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await deleteClaim(claimId);
            onDeleted();
          } finally {
            setBusy(false);
            setConfirming(false);
          }
        }}
      >
        {busy && <Loader2 className="animate-spin" />} Delete
      </Button>
      <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>
        Cancel
      </Button>
    </span>
  );
}
