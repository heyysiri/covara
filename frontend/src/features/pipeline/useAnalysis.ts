"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, getResults, startAnalysis, submitReview, type FieldEdit } from "@/lib/api";
import type { AnalysisResults } from "@/types/results";

const POLL_MS = 1500;

/** Start / re-check an analysis and poll GET /results while it is processing. */
export function useAnalysis(claimId: string | null) {
  const [results, setResults] = useState<AnalysisResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const processing = results?.status === "processing";

  // Poll while the run is processing; each new results object schedules the next poll.
  useEffect(() => {
    if (!claimId || !processing) return;
    let cancelled = false;
    const t = setTimeout(async () => {
      try {
        const r = await getResults(claimId);
        if (!cancelled) setResults(r);
      } catch (e) {
        if (!cancelled) setError(e instanceof ApiError ? e.message : "Could not load results.");
      }
    }, POLL_MS);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [claimId, processing, results]);

  const kick = useCallback(
    async (fn: () => Promise<AnalysisResults>) => {
      setError(null);
      try {
        setResults(await fn());
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Could not start the analysis.");
      }
    },
    [],
  );

  const start = useCallback(() => {
    if (claimId) kick(() => startAnalysis(claimId));
  }, [claimId, kick]);

  const review = useCallback(
    (edits: FieldEdit[]) => {
      if (claimId) kick(() => submitReview(claimId, edits, true));
    },
    [claimId, kick],
  );

  return { results, setResults, error, start, review, running: processing };
}
