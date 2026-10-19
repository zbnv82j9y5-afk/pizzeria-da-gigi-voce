import asyncio
import base64
import json
import logging

import numpy as np
import openai
from fastrtc import AdditionalOutputs, AsyncStreamHandler, wait_for_item

from ..config import settings, get_session_config
from .menu_db import carica_menu, euro, menu_come_testo

logger = logging.getLogger(__name__)


class OpenAIRealtimeHandler(AsyncStreamHandler):
    """GigiAI: OpenAI Realtime API + WebRTC, con presa d'ordine tramite strumenti."""

    def __init__(self) -> None:
        super().__init__(
            expected_layout="mono",
            output_sample_rate=settings.sample_rate,
            input_sample_rate=settings.sample_rate,
        )
        self.connection = None
        self.output_queue: asyncio.Queue = asyncio.Queue()
        self.menu: list[dict] = []
        self.ordine: list[dict] = []  # righe valide dell'ordine corrente

    def copy(self) -> "OpenAIRealtimeHandler":
        """Create a copy of this handler for new connections."""
        return OpenAIRealtimeHandler()

    async def start_up(self) -> None:
        """Connect to OpenAI Realtime API and handle events."""
        try:
            self.menu, da_db = await carica_menu()
            logger.info(f"Menu caricato ({len(self.menu)} pizze, da database: {da_db})")

            client = openai.AsyncOpenAI()
            async with client.realtime.connect(model=settings.openai_realtime_model) as conn:
                logger.info("Connected to OpenAI Realtime API")
                await conn.session.update(
                    session=get_session_config(
                        menu_testo=menu_come_testo(self.menu),
                        transcription_model=settings.openai_transcription_model,
                        sample_rate=settings.sample_rate,
                    )
                )
                self.connection = conn
                # GigiAI saluta per prima e poi aspetta il cliente.
                await conn.response.create()
                await self._handle_events()
        except Exception as e:
            logger.error(f"OpenAI Realtime error: {e}")
            raise

    async def _handle_events(self) -> None:
        """Process events from OpenAI Realtime API."""
        async for event in self.connection:
            if event.type == "input_audio_buffer.speech_started":
                self.clear_queue()

            elif event.type == "conversation.item.input_audio_transcription.completed":
                logger.info(f"Cliente: {event.transcript}")
                await self.output_queue.put(
                    AdditionalOutputs({"role": "user", "content": event.transcript})
                )

            elif event.type == "response.output_audio_transcript.done":
                logger.info(f"GigiAI: {event.transcript}")
                await self.output_queue.put(
                    AdditionalOutputs({"role": "assistant", "content": event.transcript})
                )

            elif event.type == "response.output_audio.delta":
                await self.output_queue.put(
                    (
                        self.output_sample_rate,
                        np.frombuffer(base64.b64decode(event.delta), dtype=np.int16).reshape(1, -1),
                    )
                )

            elif event.type == "response.done":
                await self._esegui_strumenti(event.response)

            elif event.type == "error":
                # Prima questi errori venivano ignorati in silenzio (es. una
                # configurazione di sessione rifiutata): ora finiscono nei log.
                logger.error(f"Errore dalla Realtime API: {getattr(event, 'error', event)}")

    # ------------------------------------------------------------------
    # Strumenti (function calling)
    # ------------------------------------------------------------------
    async def _esegui_strumenti(self, response) -> None:
        chiamate = [
            item for item in (getattr(response, "output", None) or [])
            if getattr(item, "type", None) == "function_call"
        ]
        if not chiamate:
            return
        for chiamata in chiamate:
            try:
                argomenti = json.loads(chiamata.arguments or "{}")
            except json.JSONDecodeError:
                argomenti = {}
            logger.info(f"Strumento {chiamata.name}: {argomenti}")
            if chiamata.name == "aggiorna_ordine":
                risultato = await self.aggiorna_ordine(argomenti.get("articoli") or [])
            elif chiamata.name == "conferma_ordine":
                risultato = await self.conferma_ordine()
            else:
                risultato = {"ok": False, "errore": f"Strumento sconosciuto: {chiamata.name}"}
            await self.connection.conversation.item.create(
                item={
                    "type": "function_call_output",
                    "call_id": chiamata.call_id,
                    "output": json.dumps(risultato, ensure_ascii=False),
                }
            )
        # Fa rispondere GigiAI a voce usando il risultato degli strumenti.
        await self.connection.response.create()

    async def aggiorna_ordine(self, articoli: list[dict]) -> dict:
        # Rilegge la disponibilita' dal database: il magazzino puo' essere
        # cambiato da quando e' iniziata la telefonata.
        menu_fresco, da_db = await carica_menu()
        if da_db:
            self.menu = menu_fresco
        per_numero = {p["numero_menu"]: p for p in self.menu}

        righe, non_disponibili, non_trovate = [], [], []
        for a in articoli:
            try:
                numero = int(a.get("numero_menu"))
                quantita = max(1, int(a.get("quantita") or 1))
            except (TypeError, ValueError):
                continue
            formato = "piccola" if str(a.get("formato", "")).lower().startswith("picc") else "grande"
            pizza = per_numero.get(numero)
            if pizza is None:
                non_trovate.append(numero)
                continue
            if not pizza["disponibile"]:
                non_disponibili.append(pizza["nome"])
                continue
            prezzo = pizza["prezzo_grande"] if formato == "grande" else pizza["prezzo_piccola"]
            # Unisce eventuali righe doppie (stessa pizza e stesso formato).
            esistente = next((r for r in righe if r["numero_menu"] == numero and r["formato"] == formato), None)
            if esistente:
                esistente["quantita"] += quantita
                esistente["subtotale"] = round(esistente["prezzo_unitario"] * esistente["quantita"], 2)
            else:
                righe.append({
                    "numero_menu": numero,
                    "nome": pizza["nome"],
                    "formato": formato,
                    "quantita": quantita,
                    "prezzo_unitario": prezzo,
                    "subtotale": round(prezzo * quantita, 2),
                })

        self.ordine = righe
        totale = round(sum(r["subtotale"] for r in righe), 2)
        await self.output_queue.put(AdditionalOutputs({
            "type": "ordine",
            "righe": righe,
            "totale": totale,
        }))
        return {
            "ok": True,
            "ordine": [
                f"{r['quantita']} {r['nome']} {r['formato']} ({euro(r['subtotale'])})" for r in righe
            ],
            "totale": euro(totale),
            "pizze_esaurite_non_aggiunte": non_disponibili,
            "numeri_non_trovati": non_trovate,
        }

    async def conferma_ordine(self) -> dict:
        if not self.ordine:
            return {"ok": False, "errore": "L'ordine e' vuoto: prima registra le pizze con aggiorna_ordine."}
        carrello: dict[str, dict] = {}
        for r in self.ordine:
            voce = carrello.setdefault(str(r["numero_menu"]), {"grande": 0, "piccola": 0})
            voce[r["formato"]] += r["quantita"]
        codice = base64.urlsafe_b64encode(
            json.dumps(carrello, separators=(",", ":")).encode()
        ).decode().rstrip("=")
        url = f"{settings.sito_url.rstrip('/')}/riepilogo.html?ordine_vocale={codice}"
        await self.output_queue.put(AdditionalOutputs({"type": "pagamento", "url": url}))
        return {
            "ok": True,
            "messaggio": "Sullo schermo e' comparso il pulsante 'Procedi al pagamento'.",
        }

    async def receive(self, frame: tuple[int, np.ndarray]) -> None:
        """Receive audio from user and send to OpenAI."""
        if not self.connection:
            return
        _, array = frame
        array = array.squeeze()
        audio_message = base64.b64encode(array.tobytes()).decode("utf-8")
        await self.connection.input_audio_buffer.append(audio=audio_message)

    async def emit(self) -> tuple[int, np.ndarray] | AdditionalOutputs | None:
        """Emit audio or transcription to the client."""
        return await wait_for_item(self.output_queue)

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self.connection:
            await self.connection.close()
            self.connection = None
