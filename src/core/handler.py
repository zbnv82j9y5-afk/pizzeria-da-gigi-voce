import asyncio
import base64
import logging

import numpy as np
import openai
from fastrtc import AdditionalOutputs, AsyncStreamHandler, wait_for_item

from ..config import settings, get_session_config

logger = logging.getLogger(__name__)


class OpenAIRealtimeHandler(AsyncStreamHandler):
    """Handler for OpenAI Realtime API with WebRTC audio streaming."""

    def __init__(self) -> None:
        super().__init__(
            expected_layout="mono",
            output_sample_rate=settings.sample_rate,
            input_sample_rate=settings.sample_rate,
        )
        self.connection = None
        self.output_queue: asyncio.Queue = asyncio.Queue()

    def copy(self) -> "OpenAIRealtimeHandler":
        """Create a copy of this handler for new connections."""
        return OpenAIRealtimeHandler()

    async def start_up(self) -> None:
        """Connect to OpenAI Realtime API and handle events."""
        try:
            client = openai.AsyncOpenAI()
            async with client.realtime.connect(
                model=settings.openai_realtime_model
            ) as conn:
                logger.info("Connected to OpenAI Realtime API")
                # Build session config with system instructions
                session_config = get_session_config()
                # Add transcription model
                session_config["input_audio_transcription"] = {
                    "model": settings.openai_transcription_model
                }
                await conn.session.update(session=session_config)
                self.connection = conn
                # Fa parlare GigiAI per prima: genera subito un saluto di
                # benvenuto, senza aspettare che il cliente parli per primo.
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
                logger.info(f"User: {event.transcript}")
                await self.output_queue.put(
                    AdditionalOutputs({"role": "user", "content": event.transcript})
                )

            elif event.type == "response.output_audio_transcript.done":
                logger.info(f"Assistant: {event.transcript}")
                await self.output_queue.put(
                    AdditionalOutputs({"role": "assistant", "content": event.transcript})
                )

            elif event.type == "response.output_audio.delta":
                await self.output_queue.put(
                    (
                        self.output_sample_rate,
                        np.frombuffer(
                            base64.b64decode(event.delta), dtype=np.int16
                        ).reshape(1, -1),
                    )
                )

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
