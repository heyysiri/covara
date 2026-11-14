"""Sarvam AI helpers: document OCR (Sarvam Vision), translation, speech to text, text to speech.

All functions raise SarvamError (never leak provider exceptions or keys). Everything here is optional:
`available()` is False without SARVAM_API_KEY and the pipeline falls back to Claude / English.

- OCR: scanned or image-only documents are read by Sarvam Vision; results (page text + block bounding
  boxes) are cached on disk by file hash (so "Delete my data" purges them with the model cache).
- Translate: amounts, dates, IDs, file names and rule ids are swapped for [[n]] placeholders before
  translation and restored after; if any placeholder is lost the line is returned in English instead.
- Speech: browser recordings (webm/ogg/mp4/wav) go to Saaras; replies are voiced with Bulbul.
"""

from __future__ import annotations

import base64
import html
import io
import json
import logging
import re
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx
import pymupdf

from app.config import get_settings
from app.schemas.results import LlmCall
from app.services import providers

log = logging.getLogger("covara.sarvam")

# Languages offered in the UI. Sarvam supports more; add a code here and run scripts/gen_i18n.py to extend.
LANGUAGES: dict[str, str] = {
    "en-IN": "English", "hi-IN": "हिन्दी",
}
TTS_SPEAKER = "ritu"
OCR_PAGES_PER_JOB = 10
OCR_MAX_PAGES = 40
TERMINAL = {"completed", "partially_completed", "failed", "rejected"}


class SarvamError(RuntimeError):
    pass


def available() -> bool:
    return bool(get_settings().sarvam_api_key)


def _client():
    try:
        return providers.get_sarvam_client()
    except Exception as e:  # missing key / SDK problem
        raise SarvamError("sarvam_unavailable") from e


# ------------------------------------------------------------------ OCR (Sarvam Vision)


@dataclass
class OcrBlock:
    text: str
    bbox: list[float]  # normalised [x0, y0, x1, y1]


@dataclass
class OcrPage:
    number: int  # 1-based, across the whole document
    text: str
    blocks: list[OcrBlock] = field(default_factory=list)


def _cache_file(sha256: str) -> Path:
    from app.core import llm  # local import: llm imports providers, not this module

    return llm._cache_dir() / f"{sha256}_sarvamocr.json"


def _flatten_html(markup: str) -> list[str]:
    """Sarvam returns tables as HTML. Turn each row into 'cell | cell' and drop other tags."""
    markup = re.sub(r"</t[dh]>\s*<t[dh][^>]*>", " | ", markup)
    markup = re.sub(r"</tr>|</p>|<br\s*/?>|</li>|</h\d>", "\n", markup)
    text = html.unescape(re.sub(r"<[^>]+>", "", markup))
    return [re.sub(r"\s+", " ", ln).strip(" |") for ln in text.splitlines() if ln.strip(" |")]


def _page_from_json(data: dict, offset: int) -> OcrPage:
    blocks: list[OcrBlock] = []
    lines: list[str] = []
    for b in sorted(data.get("blocks", []), key=lambda b: b.get("reading_order", 0)):
        rows = _flatten_html(b.get("text") or "")
        box = b.get("bbox_norm") or [0, 0, 1, 1]
        x0, y0, x1, y1 = (min(max(float(v), 0.0), 1.0) for v in box)
        n = max(len(rows), 1)
        for i, row in enumerate(rows):  # spread a multi-row block's box over its rows
            h = (y1 - y0) / n
            blocks.append(OcrBlock(row, [round(x0, 4), round(y0 + i * h, 4), round(x1, 4), round(y0 + (i + 1) * h, 4)]))
            lines.append(row)
    return OcrPage(number=int(data.get("page_num", 1)) + offset, text="\n".join(lines), blocks=blocks)


def _parse_zip(content: bytes, offset: int) -> list[OcrPage]:
    pages: list[OcrPage] = []
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        for name in sorted(z.namelist()):
            if re.search(r"metadata/page_\d+\.json$", name):
                pages.append(_page_from_json(json.loads(z.read(name).decode("utf-8")), offset))
    return sorted(pages, key=lambda p: p.number)


def _chunks(path: Path, content_type: str, filename: str) -> list[tuple[str, bytes, str, int]]:
    if content_type != "application/pdf":
        return [(filename, path.read_bytes(), content_type, 0)]
    with pymupdf.open(path) as pdf:
        n = min(len(pdf), OCR_MAX_PAGES)
        if n <= OCR_PAGES_PER_JOB:
            return [(filename, path.read_bytes(), content_type, 0)]
        out = []
        for start in range(0, n, OCR_PAGES_PER_JOB):
            part = pymupdf.open()
            part.insert_pdf(pdf, from_page=start, to_page=min(start + OCR_PAGES_PER_JOB, n) - 1)
            out.append((f"part{start // OCR_PAGES_PER_JOB + 1}_{filename}", part.tobytes(), content_type, start))
        return out


def ocr_document(path: Path, content_type: str, filename: str, sha256: str, calls: list[LlmCall],
                 content_kind: str = "mixed") -> list[OcrPage]:
    """Read a scanned/image document with Sarvam Vision. Cached by file hash."""
    cache = _cache_file(sha256)
    t0 = time.monotonic()
    if cache.exists():
        try:
            pages = [OcrPage(p["number"], p["text"], [OcrBlock(**b) for b in p["blocks"]])
                     for p in json.loads(cache.read_text())]
            calls.append(LlmCall(provider="sarvam", model="sarvam-vision", task="ocr", cached=True,
                                 latency_ms=0, ok=True))
            return pages
        except (OSError, ValueError, TypeError, KeyError):
            cache.unlink(missing_ok=True)
    if get_settings().demo_mode:
        raise SarvamError("demo_mode_no_cache")
    try:
        client = _client()
        pages: list[OcrPage] = []
        for name, data, mime, offset in _chunks(path, content_type, filename):
            job = client.doc_ai.parse(file=[(name, data, mime)], content_type=content_kind)
            deadline = time.monotonic() + get_settings().llm_timeout_s
            while True:
                st = client.doc_ai.get_status(job.job_id)
                if st.status in TERMINAL:
                    break
                if time.monotonic() > deadline:
                    raise SarvamError("ocr_timeout")
                time.sleep(1.2)
            if st.status not in ("completed", "partially_completed"):
                raise SarvamError(f"ocr_{st.status}")
            dl = client.doc_ai.get_download_url(job.job_id)
            resp = httpx.request(dl.method or "GET", dl.url, headers=dl.headers or None, follow_redirects=True,
                                 timeout=60)
            resp.raise_for_status()
            pages.extend(_parse_zip(resp.content, offset))
        if not pages or not any(p.text.strip() for p in pages):
            raise SarvamError("ocr_empty")
    except SarvamError:
        calls.append(LlmCall(provider="sarvam", model="sarvam-vision", task="ocr", cached=False,
                             latency_ms=int((time.monotonic() - t0) * 1000), ok=False, error="ocr_failed"))
        raise
    except Exception as e:
        calls.append(LlmCall(provider="sarvam", model="sarvam-vision", task="ocr", cached=False,
                             latency_ms=int((time.monotonic() - t0) * 1000), ok=False, error=type(e).__name__))
        log.warning("sarvam ocr failed: %s", type(e).__name__)
        raise SarvamError("ocr_failed") from e
    cache.write_text(json.dumps([asdict(p) for p in pages], ensure_ascii=False))
    calls.append(LlmCall(provider="sarvam", model="sarvam-vision", task="ocr", cached=False,
                         latency_ms=int((time.monotonic() - t0) * 1000), ok=True))
    return pages


# ------------------------------------------------------------------ translation

_PROTECT = re.compile(
    r"""(
        [\w.\-]+\.(?:pdf|png|jpe?g)                      # file names
      | (?:₹|Rs\.?)\s?\d[\d,]*(?:\.\d+)?                 # amounts with a currency mark
      | \b\d{4}-\d{2}-\d{2}\b                            # 2026-08-15
      | \b\d{1,2}[-/ ](?:[A-Za-z]{3,9}|\d{1,2})[-/ ]\d{2,4}\b   # 15-Aug-2026, 15/08/2026
      | \b[A-Z]{1,6}(?:[-/][A-Za-z0-9]+)+\b              # INV-2026-08-10457, SSH-2026-004567, RX-7781
      | \{\w+\}                                          # UI template variables like {count}
      | \bV\d{1,2}\b                                     # rule ids
      | \d[\d,]*(?:\.\d+)?%?                             # numbers, percentages
    )""",
    re.X,
)
_tr_cache: dict[tuple[str, str], tuple[str, bool]] = {}

# Sarvam rate-limits translation. Calls are spaced by MIN_INTERVAL (raise it for bulk jobs) and a "too many
# requests" answer is retried with a growing pause.
MIN_INTERVAL = 0.0
_gate = threading.Lock()
_next_slot = 0.0


def _call_translate(client, **kw):
    global _next_slot
    for attempt in range(5):
        with _gate:
            now = time.monotonic()
            wait = max(0.0, _next_slot - now)
            _next_slot = max(now, _next_slot) + MIN_INTERVAL
        if wait:
            time.sleep(wait)
        try:
            return client.text.translate(**kw)
        except Exception as e:
            if type(e).__name__ != "TooManyRequestsError" or attempt == 4:
                raise
            time.sleep(2.0 * (attempt + 1))


def _sentences(line: str, limit: int = 850) -> list[str]:
    if len(line) <= limit:
        return [line]
    parts, cur = [], ""
    for s in re.split(r"(?<=[.!?।])\s+", line):
        if cur and len(cur) + len(s) + 1 > limit:
            parts.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    return parts + ([cur] if cur else [])


def _translate_piece(piece: str, target: str, source: str) -> tuple[str, bool]:
    key = (target + source, piece)
    if key in _tr_cache:
        return _tr_cache[key]
    tokens: list[str] = []

    def hide(m: re.Match) -> str:
        tokens.append(m.group(0))
        return f"[[{len(tokens)}]]"

    masked = _PROTECT.sub(hide, piece)
    if not re.search(r"[A-Za-zऀ-෿]{2,}", re.sub(r"\[\[\d+\]\]", "", masked)):
        return piece, True  # nothing translatable (only numbers/ids)
    client = _client()
    for _ in range(2):
        out = _call_translate(client, input=masked, source_language_code=source, target_language_code=target,
                              mode="formal", numerals_format="international",
                              model="sarvam-translate:v1").translated_text
        if all(out.count(f"[[{i}]]") == 1 for i in range(1, len(tokens) + 1)):
            for i, tok in enumerate(tokens, 1):
                out = out.replace(f"[[{i}]]", tok)
            _tr_cache[key] = (out, True)
            return out, True
    return piece, False  # a protected value went missing: keep the English line rather than risk a wrong number


def translate(text: str, target: str, source: str = "en-IN") -> tuple[str, bool]:
    """Translate text. Returns (text, fully_translated). Never changes numbers, dates, IDs or file names."""
    if not text.strip() or target == source:
        return text, True
    lines = text.split("\n")
    jobs = [(i, p) for i, ln in enumerate(lines) if ln.strip() for p in _sentences(ln)]
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda j: _translate_piece(j[1], target, source), jobs))
    except SarvamError:
        raise
    except Exception as e:
        log.warning("sarvam translate failed: %s", type(e).__name__)
        raise SarvamError("translate_failed") from e
    out: dict[int, list[str]] = {}
    ok = True
    for (i, _), (t, good) in zip(jobs, results):
        out.setdefault(i, []).append(t)
        ok = ok and good
    return "\n".join(" ".join(out.get(i, [""])) if ln.strip() else ln for i, ln in enumerate(lines)), ok


def to_english(text: str) -> str:
    """User text in any Indian language -> English (no-op for text that is already Latin script)."""
    if not re.search(r"[ऀ-෿]", text) or not available():
        return text
    try:
        return _call_translate(_client(), input=text[:900], source_language_code="auto", target_language_code="en-IN",
                               mode="formal", numerals_format="international",
                               model="mayura:v1").translated_text  # mayura accepts source "auto"
    except Exception as e:
        log.warning("sarvam to_english failed: %s", type(e).__name__)
        return text


# ------------------------------------------------------------------ speech

_CODEC = {"webm": "webm", "ogg": "ogg", "mp4": "mp4", "m4a": "mp4", "x-m4a": "mp4", "wav": "wav", "x-wav": "wav",
          "mpeg": "mp3", "mp3": "mp3", "aac": "aac", "flac": "flac", "opus": "opus"}


def transcribe(audio: bytes, mime: str, language: str = "unknown") -> tuple[str, str | None]:
    """Speech -> text in the spoken language. Returns (transcript, detected language code)."""
    kind = (mime or "audio/webm").split(";")[0].split("/")[-1].lower()
    codec = _CODEC.get(kind, "webm")
    try:
        r = _client().speech_to_text.transcribe(
            file=(f"speech.{codec}", audio, f"audio/{kind}"), model="saaras:v3", mode="transcribe",
            language_code=language if language in LANGUAGES or language == "unknown" else "unknown",
            input_audio_codec=codec)
        return (r.transcript or "").strip(), getattr(r, "language_code", None)
    except SarvamError:
        raise
    except Exception as e:
        log.warning("sarvam stt failed: %s", type(e).__name__)
        raise SarvamError("stt_failed") from e


def synthesize(text: str, language: str = "en-IN", pace: float = 1.0) -> bytes:
    """Text -> mp3 bytes (first ~900 characters, split at sentence ends)."""
    language = language if language in LANGUAGES else "en-IN"
    pieces = _sentences(re.sub(r"\s+", " ", text).strip()[:900], 380)
    client = _client()
    audio = b""
    try:
        for piece in pieces:
            r = client.text_to_speech.convert(text=piece, language_code=language, speaker=TTS_SPEAKER,
                                              model="bulbul:v3", output_audio_codec="mp3", pace=pace)
            audio += base64.b64decode(r.audios[0])
    except Exception as e:
        log.warning("sarvam tts failed: %s", type(e).__name__)
        raise SarvamError("tts_failed") from e
    return audio
