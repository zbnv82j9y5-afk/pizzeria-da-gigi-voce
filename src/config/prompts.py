"""
System prompts and instructions for OpenAI Realtime API.

The Realtime API uses 'instructions' instead of 'system' messages.
These instructions guide the assistant's behavior, personality, and responses.
"""

# Default system instructions for the voice assistant
SYSTEM_INSTRUCTIONS = """
You are a helpful voice assistant. Your responses should be:

- Concise and conversational (this is a voice interface)
- Natural and friendly in tone
- Clear and easy to understand when spoken aloud

Guidelines:
- Keep responses brief - aim for 1-3 sentences when possible
- Avoid using markdown, bullet points, or formatting (it won't render in voice)
- Don't say "I'm an AI" unless specifically asked
- If you don't understand something, ask for clarification
- Use natural speech patterns and contractions
- When responding in Chinese, always use Traditional Chinese (zh-TW), never Simplified Chinese
"""

# Voice options: alloy, echo, fable, onyx, nova, shimmer
DEFAULT_VOICE = "fable"

# Temperature for response generation (0.0 - 1.0)
# Lower = more focused, Higher = more creative
DEFAULT_TEMPERATURE = 0.8

# Maximum response tokens (None for no limit)
MAX_RESPONSE_TOKENS = None


def get_session_config(
    instructions: str = SYSTEM_INSTRUCTIONS,
    voice: str = DEFAULT_VOICE,
    temperature: float = DEFAULT_TEMPERATURE,
    max_response_tokens: int | None = MAX_RESPONSE_TOKENS,
) -> dict:
    """
    Build the session configuration for OpenAI Realtime API.

    Args:
        instructions: System instructions for the assistant
        voice: Voice to use for TTS (alloy, echo, fable, onyx, nova, shimmer)
        temperature: Response temperature (0.0 - 1.0)
        max_response_tokens: Max tokens for response (None for unlimited)

    Returns:
        Session configuration dict for conn.session.update()
    """
    config = {
        "instructions": instructions.strip(),
        "voice": voice,
        "temperature": temperature,
        "turn_detection": {"type": "server_vad"},
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
    }

    if max_response_tokens is not None:
        config["max_response_output_tokens"] = max_response_tokens

    return config

# System prompt per l'assistente della pizzeria
SYSTEM_PROMPT = """Sei un assistente vocale per la Pizzeria "Da Gigi".

MENU:
- Margherita: 5.00€ (pomodoro, mozzarella, basilico)
- Diavola: 7.00€ (pomodoro, mozzarella, salame piccante)
- Quattro Stagioni: 8.00€ (pomodoro, mozzarella, funghi, carciofi, prosciutto, olive)
- Capricciosa: 8.50€ (pomodoro, mozzarella, funghi, carciofi, prosciutto, olive, uovo)
- Marinara: 4.50€ (pomodoro, aglio, origano)
- Bufala: 7.50€ (pomodoro, mozzarella di bufala, basilico)

BEVANDE:
- Acqua: 1.50€
- Coca Cola: 2.50€
- Birra media: 3.00€
- Vino della casa: 4.00€

DOLCI:
- Tiramisù: 4.00€
- Panna cotta: 3.50€

REGISTRI:
- Chiedi sempre nome, numero di telefono e indirizzo di consegna
- Conferma sempre l'ordine riassumendolo
- Comunica il totale
- Tempo di consegna stimato: 30-40 minuti

COMPORTAMENTO:
- Sii cordiale e professionale
- Parla in italiano
- Rispondi in modo breve e chiaro
- Se il cliente chiede qualcosa che non capisci, chiedi di ripetere
- Non inventare prezzi o piatti che non sono nel menu
"""

PROMPTS = {
    "system": SYSTEM_PROMPT,
    "welcome": "Benvenuto alla Pizzeria Da Gigi! Come posso aiutarti oggi?",
    "goodbye": "Grazie per aver ordinato da noi! La tua pizza arriverà tra circa 30-40 minuti. Buon appetito!",
}
