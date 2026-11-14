"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchSpeech } from "@/lib/api";

/** Plays spoken text (Sarvam text-to-speech, via the backend). One clip at a time. */
export function useSpeaker() {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [speaking, setSpeaking] = useState(false);

  const halt = useCallback(() => {
    audio.current?.pause();
    audio.current = null;
    setSpeaking(false);
  }, []);

  const speak = useCallback(
    async (text: string, lang: string) => {
      halt();
      const url = URL.createObjectURL(await fetchSpeech(text, lang));
      const el = new Audio(url);
      audio.current = el;
      el.onended = () => {
        URL.revokeObjectURL(url);
        setSpeaking(false);
      };
      setSpeaking(true);
      await el.play();
    },
    [halt],
  );

  useEffect(() => halt, [halt]);
  return { speaking, speak, halt };
}
