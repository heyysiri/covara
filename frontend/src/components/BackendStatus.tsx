"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/i18n";
import { getHealth } from "@/lib/api";

type State = "checking" | "online" | "offline";

export function BackendStatus() {
  const { t } = useI18n();
  const [state, setState] = useState<State>("checking");

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then(() => !cancelled && setState("online"))
      .catch(() => !cancelled && setState("offline"));
    return () => {
      cancelled = true;
    };
  }, []);

  const label = {
    checking: t("Checking API…"),
    online: t("API online"),
    offline: t("API offline"),
  }[state];
  return (
    <Badge variant={state === "offline" ? "destructive" : "secondary"} aria-live="polite">
      <span
        className={`mr-1.5 inline-block size-1.5 rounded-full ${
          state === "online" ? "bg-emerald-500" : state === "offline" ? "bg-red-500" : "bg-amber-500"
        }`}
      />
      {label}
    </Badge>
  );
}
