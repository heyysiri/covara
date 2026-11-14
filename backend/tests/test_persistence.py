"""Claims survive a restart, expire after the retention period, and deleting a claim leaves nothing on disk."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core import persistence
from app.main import app
from app.modules.pipeline import runner
from app.schemas.results import RunStatus
from app.services import claim_store

SAMPLES = Path(__file__).resolve().parents[2] / "sample_documents"
pytestmark = pytest.mark.skipif(not (SAMPLES / "expected_results" / "claim_a.json").exists(), reason="sample documents missing")


@pytest.fixture
def disk(tmp_path, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "persist_claims", True)
    monkeypatch.setattr(s, "data_dir", tmp_path / "data")
    monkeypatch.setattr(s, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(s, "cache_dir", tmp_path / "cache")
    monkeypatch.setattr(s, "retention_hours", 72)
    for key in ("anthropic_api_key", "gemini_api_key", "groq_api_key"):
        monkeypatch.setattr(s, key, "")
    monkeypatch.setattr(s, "claude_use_cli", False)  # offline rules path
    claim_store.reset()
    runner.reset()
    return TestClient(app), tmp_path


def make_claim(client, upload=True):
    truth = json.loads((SAMPLES / "expected_results" / "claim_a.json").read_text())
    cid = client.post("/claims", json={**truth["claim_input"], "consent_given": True}).json()["id"]
    if upload:
        for item in truth["upload_set"]:
            p = SAMPLES / item["file"]
            assert client.post(f"/claims/{cid}/documents", data={"category": item["doc_type"]},
                               files=[("files", (p.name, p.read_bytes(), "application/pdf"))]).status_code == 201
    return cid


def restart() -> int:
    """What a process restart does to memory, then what startup does."""
    claim_store.reset()
    runner.reset()
    return persistence.load_all()


def test_a_claim_with_its_documents_and_edits_survives_a_restart(disk):
    client, _ = disk
    cid = make_claim(client)
    client.patch(f"/claims/{cid}", json={"claimed_amount": 12345})
    assert restart() == 1
    r = client.get(f"/claims/{cid}")
    assert r.status_code == 200 and r.json()["claimed_amount"] == 12345 and len(r.json()["documents"]) == 6
    doc = r.json()["documents"][0]
    assert client.get(f"/claims/{cid}/documents/{doc['id']}/file").status_code == 200  # the file is still served
    assert r.json()["consent_at"] is not None


def test_results_and_the_users_ticked_actions_survive_a_restart(disk):
    client, _ = disk
    cid = make_claim(client)
    client.post(f"/claims/{cid}/analyze")
    before = client.get(f"/claims/{cid}/results").json()
    assert before["status"] == "complete" and before["fields"]
    action = before["action_plan"][0] if before["action_plan"] else None
    if action:
        client.patch(f"/claims/{cid}/actions/{action['id']}", json={"done": True})
    restart()
    after = client.get(f"/claims/{cid}/results").json()
    assert after["status"] == "complete" and len(after["fields"]) == len(before["fields"])
    assert after["packet_status"] == before["packet_status"]
    if action:
        assert next(a for a in after["action_plan"] if a["id"] == action["id"])["done"] is True
    assert client.get(f"/claims/{cid}/report").status_code == 200  # the PDF can be rebuilt from the restored results


def test_an_analysis_interrupted_by_a_restart_is_reported_not_left_spinning(disk):
    client, _ = disk
    cid = make_claim(client)
    client.post(f"/claims/{cid}/analyze")
    res = runner._results[cid]
    res.status = RunStatus.PROCESSING  # pretend the process died mid-run
    persistence.snapshot(cid)
    restart()
    out = client.get(f"/claims/{cid}/results").json()
    assert out["status"] == "failed" and "restart" in out["error"].lower()


def test_expired_claims_are_removed_with_their_files_and_fresh_ones_are_kept(disk):
    client, tmp = disk
    old, fresh = make_claim(client), make_claim(client)
    claim_store.get_claim(old).created_at = datetime.now(timezone.utc) - timedelta(hours=100)
    persistence.snapshot_all()
    assert persistence.expire_old() == 1
    assert client.get(f"/claims/{old}").status_code == 404 and client.get(f"/claims/{fresh}").status_code == 200
    assert not (tmp / "uploads" / old).exists() and (tmp / "uploads" / fresh).exists()
    assert not (tmp / "data" / "claims" / f"{old}.json").exists() and (tmp / "data" / "claims" / f"{fresh}.json").exists()
    restart()
    assert client.get(f"/claims/{old}").status_code == 404  # and it stays gone after a restart


def test_retention_zero_keeps_everything(disk, monkeypatch):
    client, _ = disk
    monkeypatch.setattr(get_settings(), "retention_hours", 0)
    cid = make_claim(client, upload=False)
    claim_store.get_claim(cid).created_at = datetime.now(timezone.utc) - timedelta(days=400)
    assert persistence.expire_old() == 0 and client.get(f"/claims/{cid}").status_code == 200


def test_delete_my_data_removes_the_snapshot_files_and_results(disk):
    client, tmp = disk
    cid = make_claim(client)
    client.post(f"/claims/{cid}/analyze")
    assert (tmp / "data" / "claims" / f"{cid}.json").exists()
    assert client.delete(f"/claims/{cid}").status_code == 204
    assert not (tmp / "data" / "claims" / f"{cid}.json").exists() and not (tmp / "uploads" / cid).exists()
    restart()
    assert client.get(f"/claims/{cid}").status_code == 404


def test_a_damaged_snapshot_does_not_stop_startup(disk):
    client, tmp = disk
    cid = make_claim(client)
    (tmp / "data" / "claims" / "broken.json").write_text("{not json")
    assert restart() == 1 and client.get(f"/claims/{cid}").status_code == 200


def test_persistence_can_be_switched_off_and_the_folder_is_git_ignored(disk, monkeypatch):
    client, tmp = disk
    monkeypatch.setattr(get_settings(), "persist_claims", False)
    make_claim(client, upload=False)
    assert not (tmp / "data").exists()
    assert "backend/.data/" in (Path(__file__).resolve().parents[2] / ".gitignore").read_text()
