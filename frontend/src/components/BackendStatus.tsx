"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { getHealth } from "@/lib/api";

type State = "checking" | "online" | "offline";

export function BackendStatus() {
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

  const label = { checking: "Checking API…", online: "API online", offline: "API offline" }[state];
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
