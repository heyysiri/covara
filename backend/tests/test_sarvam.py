"""Sarvam helpers (OCR parsing, protected translation), Hindi normalisation, summary, speech and translate endpoints.

Everything runs offline: the Sarvam client is replaced by fakes.
"""

import io
import json
import types
import zipfile

import pytest

from app.core import sarvam
from app.modules.extraction import normalize as nz
from app.modules.extraction.ingest import IngestedDoc, apply_ocr, find_bbox
from tests.test_pipeline import _analyze, _claim_with_docs, client, docs  # noqa: F401  (fixtures)


# ---------------------------------------------------------------- normalisation


def test_devanagari_digits_and_hindi_months():
    assert nz.ascii_digits("१५-०८-२०२६") == "15-08-2026"
    assert nz.parse_date("१५-०८-२०२६") == "2026-08-15"
    assert nz.parse_date("15 अगस्त 2026") == "2026-08-15"
    assert nz.parse_amount("₹ ८५,०००.००") == 85000
    assert nz.normalize_value("bill_total", "८५,०००") == 85000
    assert nz.normalize_value("patient_name", "श्री रवि कुमार शर्मा") == "श्री रवि कुमार शर्मा".title()


# ---------------------------------------------------------------- OCR parsing


def _ocr_zip() -> bytes:
    page = {"page_num": 1, "blocks": [
        {"reading_order": 2, "bbox_norm": [0.1, 0.4, 0.9, 0.6], "text":
         "<table><tr><td>बिल संख्या:</td><td>INV-2026-08-10457</td></tr><tr><td>कुल देय राशि</td><td>₹ 85,000.00</td></tr></table>"},
        {"reading_order": 1, "bbox_norm": [0.1, 0.1, 0.9, 0.2], "text": "डेमो सिटी केयर हॉस्पिटल"},
    ]}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("bill.jpg/metadata/page_001.json", json.dumps(page))
        z.writestr("manifest.json", "{}")
    return buf.getvalue()


def test_ocr_zip_parsing_and_bbox_lookup(tmp_path):
    pages = sarvam._parse_zip(_ocr_zip(), 0)
    assert len(pages) == 1
    assert pages[0].text.splitlines() == ["डेमो सिटी केयर हॉस्पिटल", "बिल संख्या: | INV-2026-08-10457", "कुल देय राशि | ₹ 85,000.00"]
    row = pages[0].blocks[2]  # second table row: lower half of the table block
    assert row.bbox[1] == pytest.approx(0.5) and row.bbox[3] == pytest.approx(0.6)
    doc = IngestedDoc("d", "bill.jpg", tmp_path / "bill.jpg", "image/jpeg", "sha")
    apply_ocr(doc, pages)
    assert doc.has_text_layer and doc.ocr_source == "sarvam"
    assert find_bbox(doc, 1, "कुल देय राशि | ₹ 85,000.00") == row.bbox
    assert find_bbox(doc, 1, "text that is not there") is None


# ---------------------------------------------------------------- translation


class _FakeTranslator:
    """Pretends to translate: upper-cases words but keeps [[n]] placeholders (or drops them on demand)."""

    def __init__(self, drop_placeholders=False):
        self.drop, self.calls = drop_placeholders, 0
        self.text = types.SimpleNamespace(translate=self._translate)

    def _translate(self, input, **kw):
        self.calls += 1
        import re
        out = "HI " + (re.sub(r"\[\[\d+\]\]", "", input) if self.drop else input)
        return types.SimpleNamespace(translated_text=out)


def test_translation_protects_numbers_dates_ids_and_files(monkeypatch):
    sarvam._tr_cache.clear()
    fake = _FakeTranslator()
    monkeypatch.setattr(sarvam, "_client", lambda: fake)
    src = "Bill total on final_bill.pdf is ₹85,000 but you claim ₹95,000 (INV-2026-08-10457, 15-Aug-2026, rule V4)."
    out, ok = sarvam.translate(src, "hi-IN")
    assert ok and out.startswith("HI ")
    for token in ("final_bill.pdf", "₹85,000", "₹95,000", "INV-2026-08-10457", "15-Aug-2026", "V4"):
        assert token in out


def test_translation_falls_back_to_english_when_a_protected_value_is_lost(monkeypatch):
    sarvam._tr_cache.clear()
    monkeypatch.setattr(sarvam, "_client", lambda: _FakeTranslator(drop_placeholders=True))
    src = "The total is ₹85,000 on page 1."
    out, ok = sarvam.translate(src, "hi-IN")
    assert out == src and ok is False  # never show a translation that may have changed an amount


def test_translate_is_a_noop_for_english_and_numbers_only(monkeypatch):
    fake = _FakeTranslator()
    monkeypatch.setattr(sarvam, "_client", lambda: fake)
    assert sarvam.translate("hello", "en-IN") == ("hello", True)
    assert sarvam.translate("85,000", "hi-IN") == ("85,000", True)
    assert fake.calls == 0


# ---------------------------------------------------------------- summary


def test_summary_endpoint_needs_a_finished_analysis_then_describes_it(client, docs):  # noqa: F811
    cid = _claim_with_docs(client, docs)
    assert client.get(f"/claims/{cid}/summary").status_code == 409
    _analyze(client, cid)
    s = client.get(f"/claims/{cid}/summary").json()
    assert s["readiness"] == "needs_attention" and s["lang"] == "en-IN"
    titles = " ".join(i["title"] for i in s["issues"])
    assert "claim" in titles.lower() and any(i["blocking"] for i in s["issues"])
    assert s["steps"] and s["speech"].startswith(s["headline"])


# ---------------------------------------------------------------- speech + batch translate


def test_speech_endpoints_need_a_key_then_work_with_a_provider(client, monkeypatch):  # noqa: F811
    assert client.post("/speech/tts", json={"text": "hello"}).status_code == 503
    assert client.post("/speech/stt", files={"audio": ("a.webm", b"x", "audio/webm")}).status_code == 503
    monkeypatch.setattr(sarvam, "available", lambda: True)
    monkeypatch.setattr(sarvam, "synthesize", lambda text, lang="en-IN", pace=1.0: b"ID3mp3bytes")
    monkeypatch.setattr(sarvam, "transcribe", lambda audio, mime, language="unknown": ("आपका दावा", "hi-IN"))
    tts = client.post("/speech/tts", json={"text": "hello", "lang": "hi-IN"})
    assert tts.status_code == 200 and tts.headers["content-type"] == "audio/mpeg" and tts.content == b"ID3mp3bytes"
    stt = client.post("/speech/stt", data={"lang": "unknown"}, files={"audio": ("a.webm", b"x" * 100, "audio/webm")})
    assert stt.json() == {"transcript": "आपका दावा", "language": "hi-IN"}
    assert client.post("/speech/stt", files={"audio": ("a.webm", b"", "audio/webm")}).status_code == 422
    assert client.post("/speech/tts", json={"text": ""}).status_code == 422


def test_batch_translate_endpoint(client, monkeypatch):  # noqa: F811
    r = client.post("/translate", json={"texts": ["hello"], "lang": "en-IN"}).json()
    assert r == {"texts": ["hello"], "ok": [True]}
    r = client.post("/translate", json={"texts": ["hello"], "lang": "hi-IN"}).json()  # no key: English, flagged not ok
    assert r == {"texts": ["hello"], "ok": [False]}
    monkeypatch.setattr(sarvam, "available", lambda: True)
    monkeypatch.setattr(sarvam, "translate", lambda text, lang, source="en-IN": (f"<{text}>", True))
    r = client.post("/translate", json={"texts": ["a", "b"], "lang": "hi-IN"}).json()
    assert r == {"texts": ["<a>", "<b>"], "ok": [True, True]}
    assert client.get("/speech/languages").json()["languages"]["hi-IN"] == "हिन्दी"



def test_quote_matching_ignores_punctuation_and_accepts_the_value_when_the_label_differs(tmp_path):
    import hashlib
    import pymupdf
    from app.modules.extraction.ingest import ingest, locate_quote

    pdf = tmp_path / "r.pdf"
    d = pymupdf.open()
    d.new_page().insert_text((50, 60), "Received from\nRavi K Sharma\nTowards Invoice\nINV-2026-08-10457\n", fontsize=10)
    d.save(pdf)
    doc = ingest("d", "r.pdf", pdf, "application/pdf", hashlib.sha256(pdf.read_bytes()).hexdigest())
    assert locate_quote(doc, "Received from: Ravi K Sharma", 1) == 1  # colon vs line break
    assert locate_quote(doc, "Patient Name: Ravi K Sharma", 1) is None  # a label that is not on the page
    assert locate_quote(doc, "Ravi K Sharma", 1) == 1  # ...but the value itself is
