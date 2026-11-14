// Turn whatever the user drops or picks (files, a folder, a .zip) into a flat list of documents.
// Pure browser/File logic: no project-alias imports, so it can be tested outside Next.js.

import { unzipSync } from "fflate";

export const ALLOWED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg"];
export const MAX_FILE_MB = 20;
export const MAX_ARCHIVE_ENTRIES = 200;
export const MAX_ARCHIVE_TOTAL_MB = 200;

const MB = 1024 * 1024;
const MIME: Record<string, string> = {
  ".pdf": "application/pdf",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
};

export interface IncomingFile {
  file: File;
  /** Where it came from, e.g. "medical/final_bill.pdf" (folder or zip) or just the file name. */
  path: string;
}

export interface Collected {
  files: IncomingFile[];
  /** Hidden, system or unsupported files found inside folders/zips and ignored. */
  skipped: number;
  /** Human-readable problems (bad zip, too many entries, oversized entry...). */
  problems: string[];
}

interface Raw {
  file: File;
  path: string;
  /** true = the user picked this file itself (show a rejection if unsupported);
   *  false = found inside a folder or zip (silently skip unsupported/hidden). */
  direct: boolean;
}

export const extOf = (name: string): string => {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot).toLowerCase();
};

export const baseName = (path: string): string => path.slice(path.lastIndexOf("/") + 1);

/** .DS_Store, __MACOSX/, Thumbs.db, ._file, anything under a dot-folder. */
export const isHidden = (path: string): boolean =>
  path
    .split("/")
    .filter(Boolean)
    .some((seg) => seg.startsWith(".") || seg === "__MACOSX" || seg.toLowerCase() === "thumbs.db");

const isZip = (name: string) => extOf(name) === ".zip";

function empty(): Collected {
  return { files: [], skipped: 0, problems: [] };
}

/** Unzip in memory. Entries are filtered BEFORE decompression by the sizes in the zip header. */
export async function expandZip(zip: File): Promise<Collected> {
  const out = empty();
  let count = 0;
  let total = 0;
  try {
    const data = new Uint8Array(await zip.arrayBuffer());
    const entries = unzipSync(data, {
      filter: (f) => {
        if (f.name.endsWith("/")) return false; // folder entry, nothing to extract
        if (isHidden(f.name) || isZip(f.name) || !ALLOWED_EXTENSIONS.includes(extOf(f.name))) {
          out.skipped++;
          return false;
        }
        if (f.originalSize > MAX_FILE_MB * MB) {
          out.problems.push(`${baseName(f.name)} in ${zip.name} is larger than ${MAX_FILE_MB} MB and was skipped.`);
          return false;
        }
        if (count + 1 > MAX_ARCHIVE_ENTRIES || total + f.originalSize > MAX_ARCHIVE_TOTAL_MB * MB) {
          out.skipped++;
          return false;
        }
        count++;
        total += f.originalSize;
        return true;
      },
    });
    if (out.skipped > 0 && count >= MAX_ARCHIVE_ENTRIES) {
      out.problems.push(`${zip.name} has more than ${MAX_ARCHIVE_ENTRIES} documents; the rest were skipped.`);
    }
    for (const [path, bytes] of Object.entries(entries)) {
      const name = baseName(path);
      out.files.push({
        path: `${zip.name.replace(/\.zip$/i, "")}/${path}`,
        file: new File([bytes as unknown as BlobPart], name, { type: MIME[extOf(name)] }),
      });
    }
  } catch {
    out.problems.push(`${zip.name} is not a valid zip file.`);
  }
  return out;
}

async function expandAll(raw: Raw[]): Promise<Collected> {
  const out = empty();
  for (const r of raw) {
    if (isZip(r.file.name)) {
      const z = await expandZip(r.file);
      out.files.push(...z.files);
      out.skipped += z.skipped;
      out.problems.push(...z.problems);
    } else if (r.direct) {
      out.files.push({ file: r.file, path: r.path });
    } else if (isHidden(r.path) || !ALLOWED_EXTENSIONS.includes(extOf(r.file.name))) {
      out.skipped++;
    } else {
      out.files.push({ file: r.file, path: r.path });
    }
  }
  return out;
}

/** From <input type="file"> (including webkitdirectory, which sets webkitRelativePath). */
export function collectFromInput(list: FileList | File[]): Promise<Collected> {
  const raw: Raw[] = Array.from(list).map((file) => {
    const rel = (file as File & { webkitRelativePath?: string }).webkitRelativePath;
    return rel ? { file, path: rel, direct: false } : { file, path: file.name, direct: true };
  });
  return expandAll(raw);
}

function readEntries(reader: FileSystemDirectoryReader): Promise<FileSystemEntry[]> {
  // readEntries returns results in batches; keep calling until it returns an empty batch.
  return new Promise((resolve, reject) => {
    const all: FileSystemEntry[] = [];
    const next = () =>
      reader.readEntries((batch) => {
        if (batch.length === 0) resolve(all);
        else {
          all.push(...batch);
          next();
        }
      }, reject);
    next();
  });
}

async function walk(entry: FileSystemEntry, direct: boolean, out: Raw[]): Promise<void> {
  if (entry.isFile) {
    const file = await new Promise<File>((res, rej) => (entry as FileSystemFileEntry).file(res, rej));
    out.push({ file, path: entry.fullPath.replace(/^\//, ""), direct });
  } else if (entry.isDirectory) {
    const children = await readEntries((entry as FileSystemDirectoryEntry).createReader());
    for (const child of children) await walk(child, false, out);
  }
}

/** From a drag-and-drop, including dropped folders. */
export async function collectFromDrop(dt: DataTransfer): Promise<Collected> {
  // Entries must be grabbed synchronously: the DataTransfer is emptied after the first await.
  const entries = Array.from(dt.items ?? [])
    .map((item) => (item.kind === "file" ? item.webkitGetAsEntry?.() ?? null : null))
    .filter((e): e is FileSystemEntry => e !== null);
  const fallback = Array.from(dt.files ?? []);
  const raw: Raw[] = [];
  if (entries.length > 0) {
    for (const entry of entries) await walk(entry, entry.isFile, raw);
  } else {
    fallback.forEach((file) => raw.push({ file, path: file.name, direct: true }));
  }
  return expandAll(raw);
}
