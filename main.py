#!/usr/bin/env python3
"""
FastRTC OpenAI Realtime Template - Entry Point

Usage:
    uv run python main.py          # FastAPI server (default)
    MODE=UI uv run python main.py  # Gradio UI
"""

import logging
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from src.config import settings
from src.core import create_stream
from src.api import create_app
from src.ui.gradio_app import launch_gradio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Main entry point."""
    mode = os.getenv("MODE", "").upper()

    # Saluto registrato di Gavina (vedi src/core/saluto_audio.py)
    from src.core.saluto_audio import genera_saluto
    genera_saluto()

    # Create the stream (shared across modes)
    stream = create_stream()

    if mode == "UI":
        # Launch Gradio UI
        launch_gradio(stream)

    elif mode == "PHONE":
        # Launch phone mode
        logger.info(f"Starting phone mode on {settings.host}:{settings.port}")
        stream.fastphone(host=settings.host, port=settings.port)

    else:
        # Launch FastAPI server
        import uvicorn

        app = create_app(stream)
        logger.info(f"Starting FastAPI server at http://localhost:{settings.port}")
        uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
