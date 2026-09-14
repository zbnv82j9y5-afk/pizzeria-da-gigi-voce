from fastrtc import Stream, ReplyOnPause
import numpy as np
import os

def process_audio(audio: tuple[int, np.ndarray]):
    """Riceve l'audio e restituisce un messaggio di test"""
    try:
        sample_rate, audio_data = audio
        print(f"Audio ricevuto: {len(audio_data)} campioni a {sample_rate} Hz")
        
        # Crea un tono semplice come risposta (beep)
        duration = 0.5  # secondi
        t = np.linspace(0, duration, int(sample_rate * duration))
        beep = np.sin(2 * np.pi * 440 * t) * 0.5  # 440 Hz a volume medio
        
        yield (sample_rate, beep.astype(np.float32))
        
    except Exception as e:
        print(f"Errore: {e}")
        # Silenzio in caso di errore
        yield audio

stream = Stream(
    ReplyOnPause(process_audio),
    modality="audio",
    mode="send-receive"
)

stream.ui.launch()
