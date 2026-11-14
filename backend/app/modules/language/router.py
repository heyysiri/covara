"""Language and voice endpoints (Sarvam): translate backend text, speech to text, text to speech, spoken summary."""

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from app.core import sarvam
from app.modules.language import service
from app.modules.pipeline import runner
from app.schemas.results import RunStatus
from app.services import claim_store

router = APIRouter(tags=["language"])
MAX_AUDIO_BYTES = 6 * 1024 * 1024


def _claim(claim_id: str):
    claim = claim_store.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.get("/speech/languages")
def languages() -> dict:
    return {"languages": sarvam.LANGUAGES, "sarvam": sarvam.available()}


@router.post("/speech/stt")
async def speech_to_text(audio: UploadFile = File(...), lang: str = Form("unknown")) -> dict:
    """Voice -> text in the spoken language (Sarvam Saaras)."""
    if not sarvam.available():
        raise HTTPException(status_code=503, detail="Voice input needs a Sarvam API key.")
    data = await audio.read()
    if not data or len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=422, detail="Recording is empty or longer than about a minute.")
    try:
        text, detected = sarvam.transcribe(data, audio.content_type or "audio/webm", lang)
    except sarvam.SarvamError:
        raise HTTPException(status_code=502, detail="Could not understand the recording. Please try again.")
    return {"transcript": text, "language": detected}


class TtsIn(BaseModel):
    text: str = Field(min_length=1, max_length=1500)
    lang: str = "en-IN"


@router.post("/speech/tts")
def text_to_speech(payload: TtsIn) -> Response:
    """Text -> spoken audio (Sarvam Bulbul), mp3."""
    if not sarvam.available():
        raise HTTPException(status_code=503, detail="Voice replies need a Sarvam API key.")
    try:
        return Response(content=sarvam.synthesize(payload.text, payload.lang), media_type="audio/mpeg")
    except sarvam.SarvamError:
        raise HTTPException(status_code=502, detail="Could not create the voice reply.")


@router.get("/claims/{claim_id}/summary", response_model=service.Summary)
def summary(claim_id: str, lang: str = "en-IN") -> service.Summary:
    """Plain-language summary of the analysis, in the chosen language (numbers, dates and IDs unchanged)."""
    _claim(claim_id)
    res = runner.get_results(claim_id)
    if res.status != RunStatus.COMPLETE:
        raise HTTPException(status_code=409, detail="The analysis is not finished yet.")
    return service.localize_summary(service.build_summary(res), lang if lang in sarvam.LANGUAGES else "en-IN")


class TranslateIn(BaseModel):
    texts: list[str] = Field(max_length=80)
    lang: str = "hi-IN"


@router.post("/translate")
def translate_batch(payload: TranslateIn) -> dict:
    """Translate backend-generated text for the UI. Amounts, dates, IDs and file names are never altered; a string
    that cannot be translated safely comes back in English (ok=false for that entry)."""
    from concurrent.futures import ThreadPoolExecutor

    lang = payload.lang if payload.lang in sarvam.LANGUAGES else "en-IN"
    texts = [t[:800] for t in payload.texts]
    if lang == "en-IN" or not sarvam.available():
        return {"texts": texts, "ok": [lang == "en-IN"] * len(texts)}

    def one(t: str) -> tuple[str, bool]:
        try:
            return sarvam.translate(t, lang)
        except sarvam.SarvamError:
            return t, False

    with ThreadPoolExecutor(max_workers=4) as pool:
        done = list(pool.map(one, texts))
    return {"texts": [d[0] for d in done], "ok": [d[1] for d in done]}
