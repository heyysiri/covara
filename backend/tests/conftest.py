import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def _no_disk_persistence(monkeypatch):
    """Tests never write claim snapshots into the real backend/.data. test_persistence turns it on with a temp dir."""
    monkeypatch.setattr(get_settings(), "persist_claims", False)
