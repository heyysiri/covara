"use client";

import { useRef, useState } from "react";
import { ClipboardCheck, FolderOpen, ScanSearch } from "lucide-react";

import { BottomBar, PrimaryButton } from "@/features/flow/AppShell";
import { useI18n } from "@/i18n";

/** Three swipeable cards that explain the flow before asking for anything. */
export function Onboarding({ onStart }: { onStart: () => void }) {
  const { t } = useI18n();
  const scroller = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);
  const slides = [
    { icon: FolderOpen, title: t("Add your papers"), text: t("Policy, hospital bills, discharge summary, prescriptions. Photos, PDFs or a whole folder all work.") },
    { icon: ScanSearch, title: t("We check them like an insurer would"), text: t("Names, dates, amounts and policy conditions are compared across every document. Every flag shows exactly where it came from.") },
    { icon: ClipboardCheck, title: t("Fix it before you submit"), text: t("Get a simple to-do list, ready-to-send messages for the hospital, and a claim packet. Available in English and Hindi.") },
  ];
  const last = index === slides.length - 1;

  function next() {
    if (last) return onStart();
    const el = scroller.current;
    el?.scrollTo({ left: (index + 1) * el.clientWidth, behavior: "smooth" });
  }

  return (
    <>
      <div
        ref={scroller}
        onScroll={(e) => setIndex(Math.round(e.currentTarget.scrollLeft / e.currentTarget.clientWidth))}
        className="-mx-4 flex snap-x snap-mandatory overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {slides.map(({ icon: Icon, title, text }) => (
          <section key={title} className="flex w-full shrink-0 snap-center flex-col items-center px-8 pb-6 pt-8 text-center">
            <span className="flex size-40 items-center justify-center rounded-full bg-gradient-to-br from-[#d9f1fc] to-white shadow-inner">
              <span className="flex size-24 items-center justify-center rounded-full bg-brand text-navy shadow-lg">
                <Icon className="size-12" aria-hidden />
              </span>
            </span>
            <h2 className="mt-8 text-2xl font-semibold tracking-tight text-navy">{title}</h2>
            <p className="mt-3 max-w-xs text-base text-muted-foreground">{text}</p>
          </section>
        ))}
      </div>
      <div className="flex justify-center gap-2" aria-hidden>
        {slides.map((s, i) => (
          <span key={s.title} className={`h-2 rounded-full transition-all ${i === index ? "w-6 bg-navy" : "w-2 bg-navy/25"}`} />
        ))}
      </div>
      <p className="mt-8 text-center text-xs text-muted-foreground">
        {t("Covara is an AI-assisted preparation tool. It does not decide whether an insurer will approve a claim.")}
      </p>
      <BottomBar>
        <PrimaryButton onClick={next}>{last ? t("Get started") : t("Next")}</PrimaryButton>
        {!last && (
          <button type="button" onClick={onStart} className="mt-2 w-full py-1 text-sm font-medium text-navy/70">
            {t("Skip")}
          </button>
        )}
      </BottomBar>
    </>
  );
}
