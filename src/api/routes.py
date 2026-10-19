import json
import logging

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastrtc import Stream

from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Stream instance will be set by the app factory
_stream: Stream | None = None


def set_stream(stream: Stream) -> None:
    """Set the stream instance for routes."""
    global _stream
    _stream = stream


@router.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Serve the main HTML page.

    Le credenziali del server-ponte (TURN) vengono richieste una sola volta
    all'avvio del server (vedi src/core/stream.py) e riutilizzate qui per il
    client — cosi' il browser e il server usano esattamente la stessa
    configurazione, ed evitiamo di richiederle di nuovo (e rischiare un
    errore di rete) ad ogni apertura della pagina."""
    rtc_config = _stream.rtc_configuration if _stream is not None else None
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


@router.get("/saluto.mp3")
async def saluto_mp3() -> Response:
    from ..core.saluto_audio import audio_saluto
    audio = audio_saluto()
    if not audio:
        return Response(status_code=404)
    return Response(content=audio, media_type="audio/mpeg",
                    headers={"Cache-Control": "public, max-age=3600"})


@router.post("/saluto")
async def saluto(dati: dict) -> dict:
    """Il browser avvisa che l'audio e' attivo: Gavina puo' salutare."""
    webrtc_id = str(dati.get("webrtc_id", ""))
    handler = _stream.handlers.get(webrtc_id) if _stream is not None else None
    if handler is None or not hasattr(handler, "richiedi_saluto"):
        return {"ok": False}
    handler.richiedi_saluto()
    return {"ok": True}


@router.post("/ripristina")
async def ripristina(dati: dict) -> dict:
    """Dopo una caduta di linea la pagina si ricollega e manda l'ordine gia' fatto."""
    webrtc_id = str(dati.get("webrtc_id", ""))
    handler = _stream.handlers.get(webrtc_id) if _stream is not None else None
    if handler is None or not hasattr(handler, "richiedi_ripristino"):
        return {"ok": False}
    righe = dati.get("righe") if isinstance(dati.get("righe"), list) else []
    handler.richiedi_ripristino(righe[:30])
    return {"ok": True}


@router.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}
