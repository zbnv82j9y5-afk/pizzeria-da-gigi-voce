import asyncio
import base64
import json
import logging
import time

import numpy as np
import openai
from fastrtc import AdditionalOutputs, AsyncStreamHandler, wait_for_item

from ..config import settings, get_session_config
from .menu_db import carica_menu, euro, menu_come_testo
from .saluto_audio import TESTO_SALUTO, audio_saluto_pcm

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
        # Saluto iniziale: parte quando il browser conferma che l'audio e'
        # attivo (POST /saluto), altrimenti su iPhone andrebbe perso.
        self._evento_saluto = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._gia_risposto = False
        # Audio del cliente arrivato prima che OpenAI fosse collegato
        # (es. parla subito dopo il saluto registrato): lo teniamo da parte.
        self._audio_in_attesa: list[str] = []
        # Ricollegamento dopo una caduta di linea: ordine da ripristinare.
        self._ripristino: list[dict] | None = None
        self._in_sospeso: list = []  # azioni chieste prima che start_up partisse

    def copy(self) -> "OpenAIRealtimeHandler":
        """Create a copy of this handler for new connections."""
        return OpenAIRealtimeHandler()

    async def start_up(self) -> None:
        """Connect to OpenAI Realtime API and handle events."""
        try:
            self._loop = asyncio.get_running_loop()
            t0 = time.monotonic()
            asyncio.create_task(self._gestisci_saluto())
            for azione in self._in_sospeso:
                asyncio.ensure_future(azione())
            self._in_sospeso.clear()
            # Menu e collegamento a OpenAI in parallelo: si parte prima.
            menu_task = asyncio.create_task(carica_menu())
            client = openai.AsyncOpenAI()
            async with client.realtime.connect(model=settings.openai_realtime_model) as conn:
                logger.info(f"Connected to OpenAI Realtime API in {time.monotonic() - t0:.1f}s")
                self.menu, da_db = await menu_task
                logger.info(f"Menu caricato ({len(self.menu)} pizze, da database: {da_db}) a {time.monotonic() - t0:.1f}s")
                await conn.session.update(
                    session=get_session_config(
                        menu_testo=menu_come_testo(self.menu),
                        transcription_model=settings.openai_transcription_model,
                        sample_rate=settings.sample_rate,
                    )
                )
                # Il saluto fa gia' parte della conversazione: Gavina sa di
                # essersi presentata e non lo ripete.
                if self._ripristino is None:
                    await conn.conversation.item.create(item={
                        "type": "message", "role": "assistant",
                        "content": [{"type": "output_text", "text": TESTO_SALUTO}],
                    })
                for pezzo in self._audio_in_attesa:
                    await conn.input_audio_buffer.append(audio=pezzo)
                self._audio_in_attesa.clear()
                self.connection = conn
                logger.info(f"Sessione pronta a {time.monotonic() - t0:.1f}s")
                await self._handle_events()
        except Exception as e:
            logger.error(f"OpenAI Realtime error: {e}")
            raise

    def _programma(self, azione) -> None:
        """Esegue la coroutine azione() nel loop della conversazione."""
        if self._loop is not None:
            self._loop.call_soon_threadsafe(lambda: asyncio.ensure_future(azione()))
        else:
            self._in_sospeso.append(azione)

    def richiedi_saluto(self) -> None:
        """Chiamato dalla route /saluto quando l'audio del cliente e' attivo."""
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._evento_saluto.set)
        else:
            self._evento_saluto.set()

    def richiedi_ripristino(self, righe: list[dict]) -> None:
        """Chiamato dalla route /ripristina dopo una caduta di linea."""
        self._ripristino = list(righe or [])
        self._gia_risposto = True  # niente saluto: si riprende il discorso
        self.richiedi_saluto()
        self._programma(self._esegui_ripristino)

    async def _attendi_connessione(self, secondi: float = 20) -> bool:
        fine = time.monotonic() + secondi
        while self.connection is None and time.monotonic() < fine:
            await asyncio.sleep(0.1)
        return self.connection is not None

    async def _gestisci_saluto(self) -> None:
        try:
            await asyncio.wait_for(self._evento_saluto.wait(), timeout=60)
        except asyncio.TimeoutError:
            return  # audio mai attivato: il saluto andrebbe perso
        if self._gia_risposto or self._ripristino is not None:
            return
        self._gia_risposto = True
        pcm = audio_saluto_pcm()
        if pcm:
            # Saluto registrato inviato subito nella linea, senza aspettare
            # che OpenAI sia collegato. Pezzi da 100 ms.
            passo = 4800
            for i in range(0, len(pcm), passo):
                await self.output_queue.put(
                    (self.output_sample_rate, np.frombuffer(pcm[i:i + passo], dtype=np.int16).reshape(1, -1))
                )
            logger.info("Saluto registrato inviato")
            return
        # Riserva: saluto dal vivo appena OpenAI e' collegato.
        if await self._attendi_connessione():
            await self.connection.response.create(response={
                "instructions": f"Saluta ora il cliente dicendo: \"{TESTO_SALUTO}\" Poi aspetta che parli."
            })

    async def _esegui_ripristino(self) -> None:
        if not await self._attendi_connessione():
            return
        righe = self._ripristino or []
        articoli = [
            {"numero_menu": r.get("numero_menu"), "formato": r.get("formato"), "quantita": r.get("quantita")}
            for r in righe
        ]
        if articoli:
            riepilogo = await self.aggiorna_ordine(articoli)
            nota = (
                "La linea con il cliente e' caduta ed e' stata appena ripristinata. "
                f"Ordine gia' registrato: {', '.join(riepilogo['ordine'])}. Totale {riepilogo['totale']}."
            )
            istruzioni = ("Di' in una frase breve che la linea era caduta e che hai ancora il suo ordine, "
                          "riepilogalo in poche parole e chiedi se vuole aggiungere altro o confermare.")
        else:
            nota = "La linea con il cliente e' caduta ed e' stata appena ripristinata. Nessuna pizza era ancora registrata."
            istruzioni = "Di' in una frase breve che la linea era caduta e chiedi gentilmente cosa desidera ordinare."
        logger.info(f"Ripristino dopo caduta di linea: {len(articoli)} righe")
        await self.connection.conversation.item.create(item={
            "type": "message", "role": "system",
            "content": [{"type": "input_text", "text": nota}],
        })
        await self.connection.response.create(response={"instructions": istruzioni})

    async def _handle_events(self) -> None:
        """Process events from OpenAI Realtime API."""
        async for event in self.connection:
            if event.type == "input_audio_buffer.speech_started":
                self._gia_risposto = True  # il cliente ha parlato per primo
                self.clear_queue()

            elif event.type == "response.created":
                self._gia_risposto = True

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
        _, array = frame
        array = array.squeeze()
        audio_message = base64.b64encode(array.tobytes()).decode("utf-8")
        if not self.connection:
            # Tiene al massimo gli ultimi ~3 secondi in attesa del collegamento.
            self._audio_in_attesa.append(audio_message)
            if len(self._audio_in_attesa) > 150:
                del self._audio_in_attesa[:-150]
            return
        await self.connection.input_audio_buffer.append(audio=audio_message)

    async def emit(self) -> tuple[int, np.ndarray] | AdditionalOutputs | None:
        """Emit audio or transcription to the client."""
        return await wait_for_item(self.output_queue)

    async def shutdown(self) -> None:
        """Clean up resources."""
        if self.connection:
            await self.connection.close()
            self.connection = None
