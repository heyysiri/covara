"use client";

import { useRef, useState } from "react";
import { Camera, CheckCircle2, Circle, FileArchive, FileText, FolderOpen, Images, Loader2, Trash2, UploadCloud, XCircle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { BottomBar, PrimaryButton } from "@/features/flow/AppShell";
import type { Item } from "@/features/flow/types";
import { useI18n } from "@/i18n";
import { ALLOWED_EXTENSIONS } from "@/lib/ingest";
import { DOCUMENT_CATEGORIES, type DocumentCategory, type DocumentOut } from "@/types/claim";
import type { ChecklistItem } from "@/types/results";

/** Step 2: add papers by camera, files or a zip; see at a glance what is still missing. */
export function StepDocuments({
  items,
  docs,
  checklist,
  notice,
  error,
  busy,
  running,
  onFiles,
  onDropData,
  onCategory,
  onRemoveItem,
  onRemoveDoc,
  onCheck,
}: {
  items: Item[];
  docs: DocumentOut[];
  checklist: ChecklistItem[];
  notice: string[];
  error: string | null;
  busy: boolean;
  running: boolean;
  onFiles: (list: FileList | null) => void;
  onDropData: (dt: DataTransfer) => void;
  onCategory: (key: string, c: DocumentCategory) => void;
  onRemoveItem: (key: string) => void;
  onRemoveDoc: (id: string) => void;
  onCheck: () => void;
}) {
  const { t } = useI18n();
  const cameraRef = useRef<HTMLInputElement>(null);
  const filesRef = useRef<HTMLInputElement>(null);
  const zipRef = useRef<HTMLInputElement>(null);
  const folderRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const staged = items.filter((i) => i.status === "staged");
  const label = (c: string) => {
    const l = DOCUMENT_CATEGORIES.find((x) => x.value === c)?.label;
    return l ? t(l) : c;
  };
  const stagedCats = new Set(staged.map((i) => i.category as string));
  const required = checklist.filter((c) => c.required);
  const reset = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFiles(e.target.files);
    e.target.value = "";
  };
  const tile = "flex flex-col items-center justify-center gap-1.5 rounded-2xl border bg-card p-3 text-center text-sm font-medium text-navy shadow-sm transition-colors active:bg-secondary hover:bg-secondary/60";

  return (
    <>
      <h2 className="text-xl font-semibold text-navy">{t("Add your documents")}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{t("Photos of paper bills work. Add as many as you have; you can add more later.")}</p>

      {required.length > 0 && (
        <div className="mt-4 rounded-2xl border bg-card p-3.5">
          <p className="mb-2 text-sm font-medium text-navy">{t("Insurers usually need")}</p>
          <ul className="flex flex-wrap gap-2">
            {required.map((c) => {
              const state = c.received ? "received" : stagedCats.has(c.category) ? "ready" : "missing";
              return (
                <li
                  key={c.category}
                  className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
                    state === "received" ? "border-emerald-500/40 bg-emerald-50 text-emerald-800" : state === "ready" ? "border-brand/50 bg-[#e6f8ff] text-navy" : "border-border bg-background text-muted-foreground"
                  }`}
                >
                  {state === "missing" ? <Circle className="size-3.5" aria-hidden /> : <CheckCircle2 className="size-3.5" aria-hidden />}
                  {t(c.label)}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          onDropData(e.dataTransfer);
        }}
        className={`mt-4 rounded-2xl border-2 border-dashed p-3 transition-colors ${dragging ? "border-brand bg-[#e6f8ff]" : "border-border"}`}
      >
        <div className="grid grid-cols-3 gap-2.5">
          <button type="button" className={tile} onClick={() => cameraRef.current?.click()}>
            <Camera className="size-6 text-brand" aria-hidden /> {t("Take photo")}
          </button>
          <button type="button" className={tile} onClick={() => filesRef.current?.click()}>
            <Images className="size-6 text-brand" aria-hidden /> {t("Files & photos")}
          </button>
          <button type="button" className={tile} onClick={() => zipRef.current?.click()}>
            <FileArchive className="size-6 text-brand" aria-hidden /> {t("ZIP")}
          </button>
        </div>
        <p className="mt-2.5 hidden items-center justify-center gap-2 text-xs text-muted-foreground md:flex">
          <UploadCloud className="size-4" aria-hidden /> {t("Or drop files or a folder here")}
          <button type="button" onClick={() => folderRef.current?.click()} className="inline-flex items-center gap-1 font-medium text-navy underline-offset-2 hover:underline">
            <FolderOpen className="size-3.5" aria-hidden /> {t("Choose folder")}
          </button>
        </p>
        <input ref={cameraRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={reset} />
        <input ref={filesRef} type="file" multiple accept={[...ALLOWED_EXTENSIONS, ".zip"].join(",")} className="hidden" onChange={reset} />
        <input ref={zipRef} type="file" accept=".zip,application/zip" className="hidden" onChange={reset} />
        {/* webkitdirectory lets desktop browsers pick a whole folder */}
        <input ref={folderRef} type="file" className="hidden" onChange={reset} {...({ webkitdirectory: "", directory: "" } as Record<string, string>)} />
      </div>

      {notice.length > 0 && (
        <Alert className="mt-3">
          <AlertTitle>{t("Heads up")}</AlertTitle>
          <AlertDescription>
            {notice.map((line) => (
              <p key={line}>{line}</p>
            ))}
          </AlertDescription>
        </Alert>
      )}

      {items.length > 0 && (
        <ul className="mt-4 space-y-2.5">
          {items.map((item) => (
            <li key={item.key} className="rounded-2xl border bg-card p-3">
              <div className="flex items-start gap-3">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-secondary text-navy">
                  <FileText className="size-5" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{item.file.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {(item.file.size / 1024).toFixed(0)} KB
                    {item.error && <span className="ml-2 text-destructive">{item.error}</span>}
                    {item.duplicate && <span className="ml-2 text-amber-600">{t("Same file already uploaded (possible duplicate)")}</span>}
                  </p>
                </div>
                <StatusIcon status={item.status} />
                {(item.status === "staged" || item.status === "rejected") && (
                  <Button variant="ghost" size="icon-sm" aria-label={t("Remove {name}", { name: item.file.name })} onClick={() => onRemoveItem(item.key)}>
                    <Trash2 />
                  </Button>
                )}
              </div>
              <select
                aria-label={t("Category for {name}", { name: item.file.name })}
                value={item.category}
                disabled={item.status !== "staged"}
                onChange={(e) => onCategory(item.key, e.target.value as DocumentCategory)}
                className="mt-2.5 h-10 w-full rounded-lg border bg-background px-3 text-sm disabled:opacity-60"
              >
                {DOCUMENT_CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {t(c.label)}
                  </option>
                ))}
              </select>
            </li>
          ))}
        </ul>
      )}

      {docs.length > 0 && (
        <div className="mt-4 rounded-2xl border bg-card">
          <p className="border-b px-3.5 py-2.5 text-sm font-medium text-navy">{t("Already added ({n})", { n: docs.length })}</p>
          <ul className="divide-y">
            {docs.map((d) => (
              <li key={d.id} className="flex items-center gap-3 px-3.5 py-2.5 text-sm">
                <CheckCircle2 className="size-4 shrink-0 text-emerald-600" aria-hidden />
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{d.original_filename}</span>
                  <span className="block text-xs text-muted-foreground">
                    {label(d.category)}
                    {d.duplicate_of && <span className="ml-2 text-amber-600">{t("Same file as an earlier upload")}</span>}
                  </span>
                </span>
                <Button variant="ghost" size="icon-sm" aria-label={t("Remove {name}", { name: d.original_filename })} disabled={running} onClick={() => onRemoveDoc(d.id)}>
                  <Trash2 />
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && (
        <Alert variant="destructive" className="mt-3">
          <AlertTitle>{t("Could not upload")}</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <BottomBar>
        <PrimaryButton onClick={onCheck} disabled={busy || running || (staged.length === 0 && docs.length === 0)}>
          {busy && <Loader2 className="animate-spin" />}
          {t("Check my claim")}
          {staged.length > 0 && ` (${staged.length})`}
        </PrimaryButton>
      </BottomBar>
    </>
  );
}

function StatusIcon({ status }: { status: Item["status"] }) {
  const { t } = useI18n();
  if (status === "uploading") return <Loader2 className="mt-1 size-4 animate-spin" aria-label={t("Uploading")} />;
  if (status === "uploaded") return <CheckCircle2 className="mt-1 size-4 text-emerald-600" aria-label={t("Uploaded")} />;
  if (status === "rejected") return <XCircle className="mt-1 size-4 text-destructive" aria-label={t("Rejected")} />;
  return null;
}
