"use client";

import { useEffect, useState } from "react";
import { Loader2, Volume2, VolumeX } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n";
import { getSummary, getVoiceInfo } from "@/lib/api";

import { useSpeaker } from "./useSpeaker";

let voiceInfo: Promise<boolean> | null = null;
const voiceAvailable = () => (voiceInfo ??= getVoiceInfo().then((v) => v.sarvam).catch(() => false));

/** Reads the claim summary aloud in the selected language (hidden when voice is not configured). */
export function ListenButton({ claimId, disabled }: { claimId: string; disabled?: boolean }) {
  const { t, lang } = useI18n();
  const { speaking, speak, halt } = useSpeaker();
  const [available, setAvailable] = useState(false);
  const [loading, setLoading] = useState(false);
  const [transcript, setTranscript] = useState<string | null>(null); // what is being read, so listeners can follow along

  useEffect(() => {
    let cancelled = false;
    void voiceAvailable().then((ok) => !cancelled && setAvailable(ok));
    return () => {
      cancelled = true;
    };
  }, []);

  if (!available) return null;

  async function toggle() {
    if (speaking) return halt();
    setLoading(true);
    try {
      const summary = await getSummary(claimId, lang);
      setTranscript(summary.speech);
      await speak(summary.speech, lang);
    } catch {
      halt();
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Button variant="outline" size="sm" onClick={toggle} disabled={disabled || loading}>
        {loading ? <Loader2 className="animate-spin" /> : speaking ? <VolumeX /> : <Volume2 />}
        {speaking ? t("Stop") : t("Listen")}
      </Button>
      {transcript && (
        <div className="order-last basis-full rounded-xl bg-white/70 p-3 text-sm">
          <div className="mb-1 flex items-center justify-between text-xs font-medium opacity-70">
            {t("Reading aloud")}
            <button type="button" onClick={() => setTranscript(null)} className="underline underline-offset-2">
              {t("Hide")}
            </button>
          </div>
          <p>{transcript}</p>
        </div>
      )}
    </>
  );
}
