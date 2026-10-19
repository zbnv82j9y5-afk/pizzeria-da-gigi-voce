"""
Saluto registrato di Gavina.

Il collegamento alla Realtime API di OpenAI richiede alcuni secondi. Per non
lasciare il cliente nel silenzio, all'avvio del server generiamo UNA volta il
saluto con la stessa voce (OpenAI text-to-speech, voce "marin") e lo teniamo
in memoria: la pagina lo riproduce appena il microfono e' attivo, mentre la
conversazione vera si collega in sottofondo.
Se la generazione fallisce, si torna al saluto "dal vivo" (route /saluto).
"""

import logging

import openai

from ..config.prompts import DEFAULT_VOICE

logger = logging.getLogger(__name__)

TESTO_SALUTO = (
    "Ciao! Sono Gavina, l'assistente vocale di Gigi. Lui è al forno, "
    "quindi oggi gli ordini li prendo io. Cosa ti preparo?"
)

_audio_mp3: bytes | None = None
_audio_pcm: bytes | None = None  # PCM 16 bit, 24 kHz, mono (come la Realtime API)


def genera_saluto() -> None:
    """Genera il saluto in PCM (inviato dentro la telefonata WebRTC: il
    telefono non lo blocca) e in mp3 (per eventuali usi nella pagina)."""
    global _audio_mp3, _audio_pcm
    client = openai.OpenAI(timeout=20)
    parametri = dict(
        model="gpt-4o-mini-tts",
        voice=DEFAULT_VOICE,
        input=TESTO_SALUTO,
        instructions="Voce femminile italiana, allegra, cordiale e naturale, ritmo vivace.",
    )
    try:
        pcm = client.audio.speech.create(response_format="pcm", **parametri).content
        _audio_pcm = pcm[: len(pcm) - (len(pcm) % 2)]
        logger.info(f"Saluto registrato pronto ({len(_audio_pcm) / 48000:.1f} s)")
    except Exception as e:  # noqa: BLE001 - qualunque errore: si usa il saluto dal vivo
        _audio_pcm = None
        logger.warning(f"Saluto registrato non disponibile, uso quello dal vivo: {e}")
    try:
        _audio_mp3 = client.audio.speech.create(response_format="mp3", **parametri).content
    except Exception:  # noqa: BLE001
        _audio_mp3 = None


def audio_saluto() -> bytes | None:
    return _audio_mp3


def audio_saluto_pcm() -> bytes | None:
    return _audio_pcm
