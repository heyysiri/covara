"""The synthetic-claim generator is data-driven: guard that it reproduces the committed files and its own ground truth."""

import hashlib
import sys
import tempfile
from pathlib import Path

import pytest

SAMPLES = Path(__file__).resolve().parents[2] / "sample_documents"
sys.path.insert(0, str(SAMPLES / "tools"))

pytestmark = pytest.mark.skipif(not (SAMPLES / "tools" / "claimgen").exists(), reason="claimgen not present")


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def built():
    from claimgen.__main__ import build

    out = {}
    for key in "abc":
        root = Path(tempfile.mkdtemp(prefix=f"claimgen-{key}-"))
        out[key] = (root, *build(key, root))
    return out


@pytest.mark.parametrize("key", list("abc"))
def test_every_quote_in_the_ground_truth_is_on_its_page(built, key):
    _, exp, errors = built[key]
    assert errors == [] and exp["expected_fields"]


@pytest.mark.parametrize("key", list("abc"))
def test_regenerating_reproduces_the_committed_files_byte_for_byte(built, key):
    """If someone edits a scenario or a builder, the committed PDFs and ground truth must be regenerated with it."""
    root, exp, _ = built[key]
    committed = [p for p in (SAMPLES / "policy").glob(f"claim_{key}_*.pdf")] + [p for p in (SAMPLES / "medical").rglob(f"claim_{key}_*.pdf")]
    assert committed, f"no committed files for claim {key}"
    for p in committed:
        regenerated = root / p.relative_to(SAMPLES)
        assert regenerated.exists() and digest(regenerated) == digest(p), p.name
    committed_json = SAMPLES / "expected_results" / f"claim_{key}.json"
    if key == "a" or key == "c":  # written by this generator: exact text
        assert committed_json.read_text() == (root / "expected_results" / f"claim_{key}.json").read_text()
    else:  # claim B's JSON predates the generator (key order and a note differ): the content must still be identical
        import json

        old = json.loads(committed_json.read_text())
        f = lambda x: (x["key"], json.dumps(x["value"], sort_keys=True), x["file"], x["page"], x["quote"])  # noqa: E731
        g = lambda x: (x["rule_id"], x["issue_type"], x["kind"], x["severity"], x["blocking"], x.get("exposure_amount"))  # noqa: E731
        assert sorted(map(f, old["expected_fields"])) == sorted(map(f, exp["expected_fields"]))
        assert sorted(map(g, old["expected_findings"])) == sorted(map(g, exp["expected_findings"]))
        assert old["upload_set"] == exp["upload_set"] and old["expected_packet_status"] == exp["expected_packet_status"]


def test_the_clean_claim_plants_nothing_and_claim_c_plants_only_the_waiting_period(built):
    assert built["a"][1]["expected_findings"] == [] and built["a"][1]["expected_packet_status"] == "Prepared for submission"
    (f,) = built["c"][1]["expected_findings"]
    assert f["rule_id"] == "V11" and not f["blocking"] and f["waiting"]["elapsed_days"] == 18 and f["waiting"]["days"] == 730


def test_claim_b_ground_truth_still_lists_its_five_planted_defects(built):
    rules = sorted((f["rule_id"], f["blocking"]) for f in built["b"][1]["expected_findings"])
    assert rules == [("V1", True), ("V10", False), ("V2", False), ("V4", True), ("V7", True)]
