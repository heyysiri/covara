"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Loader2, Maximize2, X, ZoomIn, ZoomOut } from "lucide-react";

import { useI18n } from "@/i18n";
import { documentFileUrl } from "@/lib/api";
import type { EvidenceRef } from "@/types/results";

import { evidenceImageUrl } from "./evidenceUrl";

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; src: string; located: boolean; requested: boolean };

type Props = {
  claimId: string;
  evidence: Pick<EvidenceRef, "document_id" | "filename" | "page_number" | "bbox" | "quote">;
  /** Override which text to highlight (e.g. a verified clause quote). */
  quote?: string | null;
  caption?: string;
};

/**
 * One cited page of an uploaded document, with the cited text highlighted.
 * Honest about what happened: if the quote could not be found on the page we say so and show the plain page.
 */
export function EvidencePage(props: Props) {
  const { t } = useI18n();
  const { claimId, evidence, quote } = props;
  const url = evidence.document_id && evidence.page_number ? evidenceImageUrl(claimId, evidence, { quote }) : null;
  // Remount when the image changes so loading state resets without setting state inside the effect.
  return url ? <LoadedPage key={url} {...props} url={url} /> : <p className="text-sm text-muted-foreground">{t("No page is attached to this evidence.")}</p>;
}

function LoadedPage({ claimId, evidence, caption, quote, url }: Props & { url: string }) {
  const { t } = useI18n();
  const [full, setFull] = useState(false);
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    fetch(url)
      .then(async (res) => {
        if (!res.ok) throw new Error(res.status === 404 ? t("This page is no longer available.") : t("This page could not be shown."));
        const requested = Number(res.headers.get("x-highlights-requested") ?? 0) > 0;
        const located = Number(res.headers.get("x-highlights-found") ?? 0) > 0 || Number(res.headers.get("x-bbox-highlights") ?? 0) > 0;
        objectUrl = URL.createObjectURL(await res.blob());
        if (!cancelled) setState({ status: "ready", src: objectUrl, located, requested });
      })
      .catch((e: Error) => !cancelled && setState({ status: "error", message: e.message || t("This page could not be shown.") }));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url, t]);

  const open = `${documentFileUrl(claimId, evidence.document_id as string)}#page=${evidence.page_number}`;

  return (
    <figure className="space-y-1.5">
      <figcaption className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">{caption ?? `${evidence.filename} · page ${evidence.page_number}`}</span>
        <button type="button" onClick={() => setFull(true)} className="ml-auto inline-flex items-center gap-1 font-medium text-navy underline-offset-2 hover:underline">
          <Maximize2 className="size-3" aria-hidden /> {t("Full screen")}
        </button>
        <a href={open} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 underline-offset-2 hover:text-foreground hover:underline">
          {t("Original file")} <ExternalLink className="size-3" aria-hidden />
        </a>
      </figcaption>
      <div className="overflow-hidden rounded-lg border bg-muted/30">
        {state.status === "loading" && (
          <div className="flex h-48 items-center justify-center text-muted-foreground">
            <Loader2 className="animate-spin" aria-label="Loading page" />
          </div>
        )}
        {state.status === "error" && <p className="p-4 text-sm text-destructive">{state.message}</p>}
        {state.status === "ready" && (
          // eslint-disable-next-line @next/next/no-img-element -- a generated blob URL, not an optimisable asset
          <img
            src={state.src}
            alt={`${evidence.filename}, page ${evidence.page_number}${state.located ? ", cited text highlighted" : ""}`}
            className="w-full cursor-zoom-in"
            onClick={() => setFull(true)}
          />
        )}
      </div>
      {state.status === "ready" && state.requested && !state.located && (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          {t("Could not locate the exact text on this page, so the page is shown without a highlight.")}
        </p>
      )}
      {state.status === "ready" && <p className="text-xs text-muted-foreground">{t("Tap the page to view it full screen.")}</p>}
      {full && (
        <Lightbox
          title={caption ?? `${evidence.filename} · page ${evidence.page_number}`}
          src={evidenceImageUrl(claimId, evidence, { quote, dpi: 180 })}
          onClose={() => setFull(false)}
        />
      )}
    </figure>
  );
}

/** The same highlighted page, full screen and zoomable. Esc or the close button leaves. */
function Lightbox({ title, src, onClose }: { title: string; src: string; onClose: () => void }) {
  const { t } = useI18n();
  const [zoom, setZoom] = useState(1);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);
  const btn = "flex size-10 items-center justify-center rounded-full bg-white/15 text-white hover:bg-white/25 disabled:opacity-40";
  return (
    <div role="dialog" aria-modal="true" aria-label={title} className="fixed inset-0 z-[100] flex flex-col bg-black/90">
      <div className="flex items-center gap-2 px-3 py-2 text-white">
        <span className="min-w-0 flex-1 truncate text-sm font-medium">{title}</span>
        <button type="button" className={btn} onClick={() => setZoom((z) => Math.max(1, +(z - 0.5).toFixed(1)))} disabled={zoom <= 1} aria-label={t("Zoom out")}>
          <ZoomOut className="size-5" aria-hidden />
        </button>
        <button type="button" className={btn} onClick={() => setZoom((z) => Math.min(4, +(z + 0.5).toFixed(1)))} disabled={zoom >= 4} aria-label={t("Zoom in")}>
          <ZoomIn className="size-5" aria-hidden />
        </button>
        <button type="button" className={btn} onClick={onClose} aria-label={t("Close")}>
          <X className="size-5" aria-hidden />
        </button>
      </div>
      <div className="flex-1 overflow-auto px-2 pb-6" onClick={(e) => e.target === e.currentTarget && onClose()}>
        {/* eslint-disable-next-line @next/next/no-img-element -- the generated highlighted page */}
        <img src={src} alt={title} style={{ width: `${zoom * 100}%`, maxWidth: zoom === 1 ? "min(100%, 900px)" : "none" }} className="mx-auto block rounded bg-white" />
      </div>
    </div>
  );
}
