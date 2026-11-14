"""Keep claims across restarts, on local disk, and delete them after a retention period.

No database: each claim is one JSON file under `data_dir` (backend/.data, git-ignored) holding the claim, its analysis
results and the user's edits. Uploaded files already live on disk under `upload_dir`. Everything here is for local use
and the demo; production would swap this module for a real store without touching the rest.

Privacy: claims older than `retention_hours` are removed with their files and cached model output, and deleting a claim
removes its snapshot too.
"""

from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import get_settings
from app.core import llm
from app.modules.pipeline import runner
from app.schemas.claim import ClaimOut, ClaimStatus
from app.schemas.results import AnalysisResults, RunStatus
from app.services import claim_store

_lock = threading.Lock()


def _dir() -> Path:
    return get_settings().data_dir / "claims"


def _enabled() -> bool:
    return get_settings().persist_claims


def snapshot(claim_id: str) -> None:
    """Write the claim's current state (or remove its snapshot if the claim no longer exists)."""
    if not _enabled():
        return
    claim = claim_store.get_claim(claim_id)
    target = _dir() / f"{claim_id}.json"
    with _lock:
        if claim is None:
            target.unlink(missing_ok=True)
            return
        res = runner._results.get(claim_id)
        payload = {
            "claim": json.loads(claim.model_dump_json()),
            "results": json.loads(res.model_dump_json()) if res else None,
            "overrides": runner._overrides.get(claim_id, {}),
            "done_actions": sorted(runner._done_actions.get(claim_id, set())),
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(target)  # atomic: a crash never leaves a half-written file


def snapshot_all() -> None:
    for c in claim_store.all_claims():
        snapshot(c.id)


def load_all() -> int:
    """Restore claims saved by a previous run. An analysis that was running when the process stopped is marked failed."""
    if not _enabled() or not _dir().is_dir():
        return 0
    n = 0
    for f in sorted(_dir().glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            claim = ClaimOut.model_validate(data["claim"])
            claim_store._claims[claim.id] = claim
            if data.get("results"):
                res = AnalysisResults.model_validate(data["results"])
                if res.status == RunStatus.PROCESSING:
                    res.status, res.error = RunStatus.FAILED, "The analysis was interrupted by a restart. Press Re-check."
                    claim.status = ClaimStatus.FAILED
                runner._results[claim.id] = res
            runner._overrides[claim.id] = data.get("overrides", {})
            runner._done_actions[claim.id] = set(data.get("done_actions", []))
            n += 1
        except Exception:  # a damaged snapshot must never stop the app from starting
            continue
    return n


def delete_everywhere(claim_id: str) -> bool:
    """Delete my data: files, extracted fields, results, snapshot and cached model outputs for these files."""
    claim = claim_store.get_claim(claim_id)
    if claim is None:
        return False
    used_elsewhere = {d.sha256 for c in claim_store.all_claims() if c.id != claim_id for d in c.documents}
    llm.purge_cache_for([d.sha256 for d in claim.documents if d.sha256 not in used_elsewhere])
    runner.forget(claim_id)
    claim_store.delete_claim(claim_id)
    snapshot(claim_id)  # claim is gone, so this removes the snapshot
    return True


def expire_old(now: datetime | None = None) -> int:
    """Delete claims older than the retention period. Returns how many were removed."""
    hours = get_settings().retention_hours
    if hours <= 0:
        return 0
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(hours=hours)
    old = [c.id for c in claim_store.all_claims() if c.created_at < cutoff]
    for cid in old:
        delete_everywhere(cid)
    return len(old)
