"""Build the UI dictionary: every English UI sentence -> Indian languages, translated with Sarvam.

    cd backend && .venv/bin/python -m scripts.gen_i18n              # all languages, only missing entries
    cd backend && .venv/bin/python -m scripts.gen_i18n hi-IN te-IN  # selected languages

English sentences are discovered in frontend/src: t("...") / t('...') calls, the display maps in
types/results.ts (FIELD_LABELS) and types/claim.ts (DOCUMENT_CATEGORIES), and an optional i18n/extra.ts.
Output: frontend/src/i18n/translations.json  { "hi-IN": { "English sentence": "translation" } }.
Placeholders like {n} and numbers are protected by app.core.sarvam.translate; an entry that cannot be translated
safely is left out (the UI then shows the English sentence). These are machine translations: have a native speaker
review them before real use.
"""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.core import sarvam

SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"
OUT = SRC / "i18n" / "translations.json"
T_DOUBLE = re.compile(r'\bt\(\s*"((?:[^"\\]|\\.)*)"')
T_SINGLE = re.compile(r"\bt\(\s*'((?:[^'\\]|\\.)*)'")
STR = re.compile(r'"((?:[^"\\]|\\.)*)"')


def unescape(s: str) -> str:
    return json.loads('"' + s.replace('\\"', '"').replace('"', '\\"') + '"') if "\\" in s else s


def collect() -> list[str]:
    keys: dict[str, None] = {}
    for path in SRC.rglob("*.ts*"):
        if path.name == "translations.json":
            continue
        text = path.read_text()
        for rx in (T_DOUBLE, T_SINGLE):
            for m in rx.finditer(text):
                keys[unescape(m.group(1).replace("\\'", "'"))] = None
    results = (SRC / "types" / "results.ts").read_text()
    block = results[results.index("FIELD_LABELS"):]
    for m in re.finditer(r'^\s+\w+:\s*"([^"]+)",', block[: block.index("};")], re.M):
        keys[m.group(1)] = None
    for m in re.finditer(r'label:\s*"([^"]+)"', (SRC / "types" / "claim.ts").read_text()):
        keys[m.group(1)] = None
    extra = SRC / "i18n" / "extra.ts"  # optional: sentences translated through a variable
    if extra.exists():
        for m in STR.finditer(extra.read_text()):
            keys[unescape(m.group(1))] = None
    return [k for k in keys if re.search(r"[A-Za-z]{2,}", k)]


def translate_one(key: str, lang: str) -> tuple[str, str | None]:
    for attempt in range(4):
        try:
            text, ok = sarvam.translate(key, lang)
            return key, text if ok else None
        except sarvam.SarvamError:
            time.sleep(1.5 * (attempt + 1))
    return key, None


def main(langs: list[str]) -> int:
    if not sarvam.available():
        print("SARVAM_API_KEY is not set in backend/.env")
        return 1
    sarvam.MIN_INTERVAL = 0.7  # stay under Sarvam's translation rate limit
    keys = collect()
    print(f"{len(keys)} English UI sentences found; ~{len(keys) * len(langs) * 0.7 / 60:.0f} min at the safe pace", flush=True)
    data: dict[str, dict[str, str]] = json.loads(OUT.read_text()) if OUT.exists() else {}
    failed = 0
    for lang in langs:
        done = data.setdefault(lang, {})
        todo = [k for k in keys if k not in done]
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=3) as pool:
            for key, text in pool.map(lambda k: translate_one(k, lang), todo):
                if text is None:
                    failed += 1
                else:
                    done[key] = text
        data[lang] = {k: done[k] for k in keys if k in done}  # drop entries for sentences that no longer exist
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True))
        print(f"{lang}: {len(data[lang])}/{len(keys)} translated ({len(todo)} new, {time.time() - t0:.0f}s)", flush=True)
    print(f"done; {failed} sentences could not be translated safely and stay English")
    return 0


if __name__ == "__main__":
    wanted = sys.argv[1:] or [c for c in sarvam.LANGUAGES if c != "en-IN"]
    sys.exit(main(wanted))
