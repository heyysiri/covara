"""The highlighted page image behind 'Why was this flagged?' (M5)."""

from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services import claim_store

SAMPLES = Path(__file__).resolve().parents[2] / "sample_documents"
POLICY = SAMPLES / "policy" / "claim_b_policy.pdf"
BILL = SAMPLES / "medical" / "claim_b_final_bill.pdf"
CLAUSE_41 = "Room rent is payable up to 1% of the Sum Insured per day"
WRAPPED = "the excess room rent is not payable and all Associated Medical Expenses (see clause 1.4) will be reduced"

pytestmark = pytest.mark.skipif(not POLICY.exists(), reason="sample documents not generated")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "upload_dir", tmp_path)
    claim_store.reset()
    return TestClient(app)


def upload(client, path: Path, category: str = "policy", content_type: str = "application/pdf"):
    cid = client.post("/claims", json={"consent_given": True}).json()["id"]
    r = client.post(f"/claims/{cid}/documents", data={"category": category},
                    files=[("files", (path.name, path.read_bytes(), content_type))])
    assert r.status_code == 201, r.text
    return cid, r.json()["uploaded"][0]["id"]


def png_size(data: bytes) -> tuple[int, int]:
    pix = pymupdf.Pixmap(data)
    return pix.width, pix.height


def url(cid, did, page):
    return f"/claims/{cid}/documents/{did}/pages/{page}/image"


def test_quote_is_located_and_highlighted(client):
    cid, did = upload(client, POLICY)
    plain = client.get(url(cid, did, 4))
    r = client.get(url(cid, did, 4), params={"highlight": CLAUSE_41})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.headers["x-highlights-found"] == "1" and r.headers["x-highlights-requested"] == "1"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n" and png_size(r.content) == png_size(plain.content)
    assert r.content != plain.content  # something was actually drawn


def test_wrapped_quote_across_lines_is_found(client):
    cid, did = upload(client, POLICY)
    r = client.get(url(cid, did, 4), params={"highlight": WRAPPED})
    assert r.headers["x-highlights-found"] == "1"


def test_several_quotes_on_one_page(client):
    cid, did = upload(client, POLICY)
    r = client.get(url(cid, did, 4), params=[("highlight", CLAUSE_41), ("highlight", "ICU charges are payable up to 2%")])
    assert r.headers["x-highlights-found"] == "2"


def test_quote_that_is_not_on_the_page_is_reported_honestly(client):
    """The UI uses this to say 'could not locate the quote' instead of pretending."""
    cid, did = upload(client, POLICY)
    r = client.get(url(cid, did, 4), params={"highlight": "this sentence is nowhere in the policy"})
    assert r.status_code == 200 and r.headers["x-highlights-found"] == "0"
    assert client.get(url(cid, did, 4)).content == r.content  # nothing drawn


def test_quote_on_the_wrong_page_is_not_found(client):
    cid, did = upload(client, POLICY)
    assert client.get(url(cid, did, 1), params={"highlight": CLAUSE_41}).headers["x-highlights-found"] == "0"


def test_bbox_is_the_fallback_when_the_quote_is_missing(client):
    cid, did = upload(client, BILL, "final_bill")
    plain = client.get(url(cid, did, 1))
    r = client.get(url(cid, did, 1), params={"highlight": "not on the page", "bbox": "0.1,0.4,0.9,0.5"})
    assert r.headers["x-highlights-found"] == "0" and r.headers["x-bbox-highlights"] == "1"
    assert r.content != plain.content
    # when the quote IS found the box is not drawn on top of it
    ok = client.get(url(cid, did, 1), params={"highlight": "TOTAL PAYABLE: Rs. 85,000.00", "bbox": "0.1,0.4,0.9,0.5"})
    assert ok.headers["x-highlights-found"] == "1" and ok.headers["x-bbox-highlights"] == "0"


def test_the_stored_original_is_never_modified(client):
    cid, did = upload(client, POLICY)
    stored = next(get_settings().upload_dir.rglob("*.pdf"))
    before = stored.read_bytes()
    client.get(url(cid, did, 4), params={"highlight": CLAUSE_41})
    assert stored.read_bytes() == before == POLICY.read_bytes()


def test_images_can_be_rendered_too(client, tmp_path):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 30), False)
    pix.set_rect(pix.irect, (200, 200, 200))
    img = tmp_path / "scan.png"
    img.write_bytes(pix.tobytes("png"))
    cid, did = upload(client, img, "other", "image/png")
    r = client.get(url(cid, did, 1), params={"bbox": "0.1,0.1,0.5,0.5"})
    assert r.status_code == 200 and r.headers["x-bbox-highlights"] == "1"


def test_errors(client):
    cid, did = upload(client, POLICY)
    assert client.get(url(cid, did, 99)).status_code == 404  # page out of range
    assert client.get(url(cid, did, 0)).status_code == 422  # pages start at 1
    assert client.get(url(cid, "nope", 1)).status_code == 404
    assert client.get(url("nope", did, 1)).status_code == 404
    assert client.get(url(cid, did, 1), params={"bbox": "0.9,0.9,0.1,0.1"}).status_code == 422
    assert client.get(url(cid, did, 1), params={"bbox": "a,b,c,d"}).status_code == 422
    assert client.get(url(cid, did, 1), params={"dpi": 5000}).status_code == 422


def test_cors_exposes_the_highlight_headers(client):
    cid, did = upload(client, POLICY)
    r = client.get(url(cid, did, 4), params={"highlight": CLAUSE_41}, headers={"Origin": "http://localhost:3000"})
    assert "x-highlights-found" in r.headers["access-control-expose-headers"].lower()


def test_no_highlight_on_unrelated_common_words(client):
    """Regression: a long quote that is not on the page must not highlight a stray word such as 'policy'."""
    cid, did = upload(client, POLICY)
    quote = "the claimant shall provide notarised proof of income within fourteen days under this policy"
    assert client.get(url(cid, did, 4), params={"highlight": quote}).headers["x-highlights-found"] == "0"


def test_slightly_reworded_quote_still_highlights_when_most_of_it_matches(client):
    cid, did = upload(client, POLICY)
    reworded = ("Room rent is payable up to 1% of the Sum Insured per day (Rs. 5,000 per day for a Sum Insured of "
                "Rs. 5,00,000). If the Insured opts for a room with a daily rent higher than this cap, the excess "
                "room rent is not payable")
    assert client.get(url(cid, did, 4), params={"highlight": reworded}).headers["x-highlights-found"] == "1"


def test_focus_returns_a_readable_close_up_around_the_highlight(client):
    cid, did = upload(client, POLICY)
    whole = client.get(url(cid, did, 4), params={"highlight": CLAUSE_41})
    close = client.get(url(cid, did, 4), params={"highlight": CLAUSE_41, "focus": "true"})
    assert close.status_code == 200 and close.headers["x-focused"] == "1" and close.headers["x-highlights-found"] == "1"
    (ww, wh), (cw, ch) = png_size(whole.content), png_size(close.content)
    assert ch < wh / 2  # a band, not the whole page
    # no highlight to centre on -> the whole page, not an arbitrary crop
    none = client.get(url(cid, did, 4), params={"highlight": "not on this page at all", "focus": "true"})
    assert none.headers["x-focused"] == "0" and png_size(none.content) == (ww, wh)
