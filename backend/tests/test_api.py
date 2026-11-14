import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services import claim_store

PDF = b"%PDF-1.4\n%fake pdf for tests\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "upload_dir", tmp_path)
    claim_store.reset()
    return TestClient(app)


def _claim(client) -> str:
    r = client.post("/claims", json={})
    assert r.status_code == 201
    return r.json()["id"]


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert set(body["providers_configured"]) == {"gemini", "groq", "sarvam"}


def test_cors_preflight_allows_frontend(client):
    r = client.options(
        "/claims",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_blocks_unknown_origin(client):
    r = client.options(
        "/claims",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in r.headers


def test_create_and_get_claim(client):
    cid = _claim(client)
    r = client.get(f"/claims/{cid}")
    assert r.status_code == 200
    assert r.json()["status"] == "created"
    assert client.get("/claims/nope").status_code == 404


def test_upload_pdf_and_list(client):
    cid = _claim(client)
    r = client.post(
        f"/claims/{cid}/documents",
        data={"category": "policy"},
        files=[("files", ("../../etc/My Policy.pdf", PDF, "application/pdf"))],
    )
    assert r.status_code == 201
    doc = r.json()["uploaded"][0]
    assert doc["category"] == "policy"
    assert "/" not in doc["original_filename"]
    assert doc["size_bytes"] == len(PDF)
    listed = client.get(f"/claims/{cid}/documents").json()
    assert [d["id"] for d in listed] == [doc["id"]]


def test_rejects_bad_type_and_spoofed_content(client):
    cid = _claim(client)
    r = client.post(
        f"/claims/{cid}/documents",
        data={"category": "other"},
        files=[
            ("files", ("a.exe", b"MZ", "application/octet-stream")),
            ("files", ("b.pdf", b"not really a pdf", "application/pdf")),
        ],
    )
    assert r.status_code == 422


def test_partial_success(client):
    cid = _claim(client)
    r = client.post(
        f"/claims/{cid}/documents",
        data={"category": "final_bill"},
        files=[
            ("files", ("bill.png", PNG, "image/png")),
            ("files", ("notes.txt", b"hello", "text/plain")),
        ],
    )
    assert r.status_code == 201
    body = r.json()
    assert len(body["uploaded"]) == 1 and len(body["rejected"]) == 1


def test_size_limit(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    cid = _claim(client)
    r = client.post(
        f"/claims/{cid}/documents",
        data={"category": "policy"},
        files=[("files", ("big.pdf", PDF, "application/pdf"))],
    )
    assert r.status_code == 422


def test_invalid_category(client):
    cid = _claim(client)
    r = client.post(
        f"/claims/{cid}/documents",
        data={"category": "bogus"},
        files=[("files", ("a.pdf", PDF, "application/pdf"))],
    )
    assert r.status_code == 422


def test_pipeline_endpoints_are_501(client):
    cid = _claim(client)
    assert client.post(f"/claims/{cid}/analyze").status_code == 501
    assert client.get(f"/claims/{cid}/results").status_code == 501
    assert client.get(f"/claims/{cid}/report").status_code == 501
