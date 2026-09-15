import asyncio
import json
import logging
import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, StreamingResponse
from fastrtc import Stream, get_cloudflare_turn_credentials_async

from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Stream instance will be set by the app factory
_stream: Stream | None = None


def set_stream(stream: Stream) -> None:
    """Set the stream instance for routes."""
    global _stream
    _stream = stream


async def _get_turn_credentials_con_retry(tentativi: int = 3):
    """Chiede le credenziali TURN gratuite (Cloudflare via HF_TOKEN).

    A volte il primo tentativo fallisce per un problema di rete/DNS
    momentaneo del container appena riavviato: riproviamo un paio di
    volte con una breve pausa prima di arrenderci."""
    ultimo_errore = None
    for tentativo in range(1, tentativi + 1):
        try:
            return await get_cloudflare_turn_credentials_async(ttl=600)
        except Exception as e:
            ultimo_errore = e
            logger.warning(
                f"Tentativo {tentativo}/{tentativi} di ottenere le credenziali TURN fallito: {e}"
            )
            if tentativo < tentativi:
                await asyncio.sleep(1.5 * tentativo)
    logger.warning(f"Credenziali TURN non ottenute dopo {tentativi} tentativi, si prosegue senza: {ultimo_errore}")
    return None


@router.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Serve the main HTML page.

    Su una rete "normale" (casa/telefono) la connessione WebRTC spesso
    riesce anche senza server TURN, ma su reti piu' restrittive (aziendali,
    alcune reti mobili) puo' fallire senza. Se e' impostata la variabile
    d'ambiente HF_TOKEN (gratuita, vedi GIGIAI-DEPLOY.md), chiediamo le
    credenziali TURN gratuite di Cloudflare tramite FastRTC — senza,
    l'app funziona comunque ma potrebbe non collegarsi da certe reti."""
    rtc_config = None
    if os.environ.get("HF_TOKEN"):
        rtc_config = await _get_turn_credentials_con_retry()
    html_path = settings.static_dir / "index.html"
    html_content = html_path.read_text()
    html_content = html_content.replace("__RTC_CONFIGURATION__", json.dumps(rtc_config))
    return HTMLResponse(content=html_content)


@router.get("/outputs")
async def outputs(webrtc_id: str) -> StreamingResponse:
    """Stream outputs for a WebRTC connection."""

    async def output_stream():
        if _stream is None:
            return
        async for output in _stream.output_stream(webrtc_id):
            data = json.dumps(output.args[0])
            yield f"event: output\ndata: {data}\n\n"

    return StreamingResponse(output_stream(), media_type="text/event-stream")


@router.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}
