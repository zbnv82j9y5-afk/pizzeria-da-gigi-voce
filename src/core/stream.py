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
    """Credenziali TURN gratuite per il server-ponte.

    Preferiamo le chiavi dirette di Cloudflare (CLOUDFLARE_TURN_KEY_ID /
    CLOUDFLARE_TURN_KEY_API_TOKEN) quando ci sono: il metodo via HF_TOKEN
    passa da un dominio (turn.fastrtc.org) che si e' rivelato irraggiungibile
    dalla rete di Render. Se le chiavi Cloudflare non ci sono, proviamo comunque
    con HF_TOKEN come ripiego.

    Servono sia al lato client (browser) sia al lato server (aiortc): senza
    configurarle anche qui, il server non prova mai il collegamento tramite
    il server-ponte. Il ttl e' lungo (24 ore) perche' viene richiesto una
    sola volta all'avvio del server, non ad ogni chiamata."""
    turn_key_id = os.environ.get("CLOUDFLARE_TURN_KEY_ID")
    turn_key_api_token = os.environ.get("CLOUDFLARE_TURN_KEY_API_TOKEN")
    hf_token = os.environ.get("HF_TOKEN")

    if not turn_key_id and not turn_key_api_token and not hf_token:
        return None

    try:
        if turn_key_id and turn_key_api_token:
            return get_cloudflare_turn_credentials(
                turn_key_id=turn_key_id,
                turn_key_api_token=turn_key_api_token,
                hf_token="",
                ttl=86400,
            )
        return get_cloudflare_turn_credentials(hf_token=hf_token, ttl=86400)
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
        # chiude in modo pulito — con 5 e 90s evitiamo che un singolo test
        # fallito blocchi tutti i tentativi successivi.
        concurrency_limit=5,
        time_limit=90,
    )

    logger.info("FastRTC stream created")
    return stream
