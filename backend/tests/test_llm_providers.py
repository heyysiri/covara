"""LLM_PROVIDERS restricts which model providers exist, so a production deployment can run on Gemini alone."""

from pydantic import BaseModel

from app.config import get_settings
from app.core import llm


class Out(BaseModel):
    answer: str


def run(monkeypatch, tmp_path, providers, keys):
    s = get_settings()
    monkeypatch.setattr(s, "cache_dir", tmp_path)
    monkeypatch.setattr(s, "llm_providers", providers)
    monkeypatch.setattr(s, "demo_mode", False)
    for k in ("anthropic_api_key", "gemini_api_key", "groq_api_key"):
        monkeypatch.setattr(s, k, "key" if k.split("_")[0] in keys else "")
    monkeypatch.setattr(s, "claude_use_cli", "claude" in keys)
    monkeypatch.setattr(llm, "claude_backend", lambda: "api" if "claude" in keys else None)
    used = []
    monkeypatch.setattr(llm, "_call_claude", lambda *a, **k: used.append("claude") or '{"answer": "c"}')
    monkeypatch.setattr(llm, "_call_gemini", lambda *a, **k: used.append("gemini") or '{"answer": "g"}')
    monkeypatch.setattr(llm, "_call_groq", lambda *a, **k: used.append("groq") or '{"answer": "q"}')
    calls = []
    obj, provider = llm.generate_json(task="t", prompt="p", schema=Out, input_hash="h" + providers + "".join(keys),
                                      prompt_version="v", calls=calls, prefer=("groq", "claude", "gemini"))
    return obj, provider, used


def test_gemini_only_never_touches_the_other_providers_even_if_they_are_configured(monkeypatch, tmp_path):
    obj, provider, used = run(monkeypatch, tmp_path, "gemini", {"claude", "gemini", "groq"})
    assert provider == "gemini" and obj.answer == "g" and used == ["gemini"]


def test_gemini_only_with_no_key_returns_nothing_instead_of_falling_back(monkeypatch, tmp_path):
    obj, provider, used = run(monkeypatch, tmp_path, "gemini", {"claude"})
    assert obj is None and provider is None and used == []


def test_default_keeps_the_callers_own_order(monkeypatch, tmp_path):
    _, provider, used = run(monkeypatch, tmp_path, "claude,gemini,groq", {"claude", "gemini", "groq"})
    assert provider == "groq" and used == ["groq"]


def test_configured_order_overrides_the_callers(monkeypatch, tmp_path):
    _, provider, _ = run(monkeypatch, tmp_path, "gemini,claude", {"claude", "gemini"})
    assert provider == "gemini"


def test_gemini_client_uses_the_api_version_that_supports_json_mode(monkeypatch):
    from app.services import providers

    monkeypatch.setattr(get_settings(), "gemini_api_key", "dummy")
    assert providers.get_gemini_client()._api_client._http_options.api_version == "v1beta"
