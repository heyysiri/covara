"""Readiness: nothing sensitive in logs, and broken input never takes the pipeline down."""

import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.safe_log import safe_trace
from app.main import app
from app.modules.pipeline import runner
from app.services import claim_store

SAMPLES = Path(__file__).resolve().parents[2] / "sample_documents"


def test_safe_trace_has_the_location_but_never_the_message():
    try:
        raise ValueError("patient Anita Verma, bill 32300")
    except ValueError as e:
        text = safe_trace(e)
    assert "ValueError" in text and "test_hardening.py" in text
    assert "Anita" not in text and "32300" not in text


@pytest.fixture
def offline(tmp_path, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(s, "cache_dir", tmp_path / "cache")
    for key in ("anthropic_api_key", "gemini_api_key", "groq_api_key"):
        monkeypatch.setattr(s, key, "")
    monkeypatch.setattr(s, "claude_use_cli", False)
    claim_store.reset()
    runner.reset()
    return TestClient(app)


def upload(client, cid, name, data, category):
    r = client.post(f"/claims/{cid}/documents", data={"category": category}, files=[("files", (name, data, "application/pdf"))])
    assert r.status_code == 201, r.text


@pytest.mark.skipif(not (SAMPLES / "expected_results" / "claim_a.json").exists(), reason="sample documents missing")
def test_a_corrupt_document_fails_alone_and_the_rest_are_still_analysed(offline):
    truth = json.loads((SAMPLES / "expected_results" / "claim_a.json").read_text())
    cid = offline.post("/claims", json={**truth["claim_input"], "consent_given": True}).json()["id"]
    for item in truth["upload_set"]:
        p = SAMPLES / item["file"]
        upload(offline, cid, p.name, p.read_bytes(), item["doc_type"])
    upload(offline, cid, "broken_report.pdf", b"%PDF-1.4\nthis is not a real pdf body", "diagnostic_report")
    offline.post(f"/claims/{cid}/analyze")
    res = offline.get(f"/claims/{cid}/results").json()
    assert res["status"] == "complete"  # the run did not fail
    by_name = {d["filename"]: d for d in res["documents"]}
    assert by_name["broken_report.pdf"]["status"] == "failed" and by_name["claim_a_final_bill.pdf"]["status"] == "processed"
    assert res["fields"], "the good documents were still read"


def test_a_failure_inside_the_pipeline_is_logged_without_content(offline, caplog, monkeypatch):
    secret = "Anita Verma 32300"

    def boom(*a, **k):
        raise ValueError(f"bad value {secret}")

    monkeypatch.setattr("app.modules.pipeline.verify_adapter.run_engine", boom)
    cid = offline.post("/claims", json={"consent_given": True}).json()["id"]
    p = SAMPLES / "policy" / "claim_a_policy.pdf"
    if not p.exists():
        pytest.skip("sample documents missing")
    upload(offline, cid, p.name, p.read_bytes(), "policy")
    with caplog.at_level(logging.DEBUG):
        offline.post(f"/claims/{cid}/analyze")
    assert offline.get(f"/claims/{cid}/results").json()["status"] == "complete"  # verification failing does not fail the run
    assert "ValueError" in caplog.text and secret not in caplog.text and "Anita" not in caplog.text
