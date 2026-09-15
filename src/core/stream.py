import logging
import os

import gradio as gr
from fastrtc import Stream, get_cloudflare_turn_credentials

from .handler import OpenAIRealtimeHandler

logger = logging.getLogger(__name__)


def update_chatbot(chatbot: list[dict], response: dict) -> list[dict]:
    """Update chatbot with new message."""
    chatbot.append(response)
    return chatbot


def _turn_config() -> dict | None:
    """Credenziali TURN gratuite (Cloudflare via HF_TOKEN), se disponibili.

    Servono sia al lato client (browser) sia al lato server (aiortc): senza
    configurarle anche qui, il server non prova mai il collegamento tramite
    il server-ponte, e la chiamata audio non riesce quasi mai a stabilirsi
    quando client e server sono su reti diverse (il nostro caso: Render +
    rete di casa/telefono). Il ttl e' lungo (24 ore) perche' viene richiesto
    una sola volta all'avvio del server, non ad ogni chiamata."""
    if not os.environ.get("HF_TOKEN"):
        return None
    try:
        return get_cloudflare_turn_credentials(ttl=86400)
    except Exception as e:
        logger.warning(f"Impossibile ottenere le credenziali TURN per il server: {e}")
        return None


def create_stream() -> Stream:
    """Create and configure the FastRTC stream."""
    chatbot = gr.Chatbot(type="messages")
    turn_config = _turn_config()

    stream = Stream(
        OpenAIRealtimeHandler(),
        mode="send-receive",
        modality="audio",
        additional_inputs=[chatbot],
        additional_outputs=[chatbot],
        additional_outputs_handler=update_chatbot,
        rtc_configuration=turn_config,
        server_rtc_configuration=turn_config,
        # Senza questi due, FastRTC/Gradio permette una sola connessione alla
        # volta e non libera mai lo "slot" di una connessione che non si
        # chiude in modo pulito (esattamente quello che ci e' successo con
        # gli errori di rete precedenti) — con 5 e 90s evitiamo che un
        # singolo test fallito blocchi tutti i tentativi successivi.
        concurrency_limit=5,
        time_limit=90,
    )

    logger.info("FastRTC stream created")
    return stream
