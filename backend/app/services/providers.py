"""AI provider registry: Gemini, Groq and Sarvam.

Provision only - no extraction logic here. Every provider is optional: the app boots
without keys and reports which providers are configured. SDK clients are created lazily
so a missing key or SDK problem never breaks startup.
"""

from app.config import get_settings


def provider_status() -> dict[str, bool]:
    """Which providers have credentials configured. Never exposes the keys themselves."""
    s = get_settings()
    return {
        "gemini": bool(s.gemini_api_key),
        "groq": bool(s.groq_api_key),
        "sarvam": bool(s.sarvam_api_key),
    }


def get_gemini_client():
    from google import genai

    key = get_settings().gemini_api_key
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    return genai.Client(api_key=key)


def get_groq_client():
    from groq import Groq

    key = get_settings().groq_api_key
    if not key:
        raise RuntimeError("GROQ_API_KEY is not configured")
    return Groq(api_key=key)


def get_sarvam_client():
    from sarvamai import SarvamAI

    key = get_settings().sarvam_api_key
    if not key:
        raise RuntimeError("SARVAM_API_KEY is not configured")
    return SarvamAI(api_subscription_key=key)
