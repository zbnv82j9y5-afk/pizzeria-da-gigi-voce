import json
import logging

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, StreamingResponse
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


@router.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}
