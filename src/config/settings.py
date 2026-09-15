import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_realtime_model: str = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1-mini")
    openai_transcription_model: str = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")

    # Audio
    sample_rate: int = 24000

    # Server
    host: str = os.getenv("HOST", "localhost")
    port: int = int(os.getenv("PORT", "7860"))

    # Paths
    base_dir: Path = Path(__file__).parent.parent.parent
    static_dir: Path = base_dir / "static"

    # Lambda API (for future integration)
    lambda_api_url: str = os.getenv("LAMBDA_API_URL", "")
    lambda_api_key: str = os.getenv("LAMBDA_API_KEY", "")

    def __post_init__(self):
        if not self.openai_api_key:
            self.openai_api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not self.openai_api_key:
                raise ValueError("DEEPSEEK_API_KEY environment variable is required")
            self.base_url = "https://api.deepseek.com"
settings = Settings()
