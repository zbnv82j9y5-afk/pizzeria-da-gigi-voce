"""
Istruzioni e configurazione della sessione per GigiAI (OpenAI Realtime API).

ATTENZIONE: la Realtime API "GA" (quella usata dalla libreria openai 2.x)
accetta solo il formato di sessione nuovo: type="realtime", audio.input /
audio.output, voce tra quelle supportate. Se si manda il formato vecchio
(voice="fable", input_audio_format, temperature...) OpenAI rifiuta TUTTA la
configurazione e l'assistente parte "nudo": in inglese, senza menu e senza
istruzioni.
"""

import json

# Il menu viene inserito al posto di {menu} all'avvio di ogni conversazione,
# leggendolo dal database (vedi src/core/menu_db.py).
SYSTEM_INSTRUCTIONS = """
# Ruolo
Ti chiami Gavina e sei l'assistente vocale della Pizzeria Da Gigi: oggi prendi
tu gli ordini al posto di Gigi, il pizzaiolo, che e' impegnato al forno.
Il servizio si chiama "GigiAI", quindi i clienti si aspettano Gigi: con il tuo
saluto rompi il ghiaccio spiegando simpaticamente che lo sostituisci tu.
Parli SEMPRE e SOLO in italiano, anche se il cliente usa parole straniere.
Usa il femminile quando parli di te ("sono pronta", "sono l'addetta").
Tono cordiale, naturale e colloquiale: e' una conversazione a voce.

# Inizio della conversazione
Appena la conversazione inizia, saluta e presentati in modo breve e allegro,
per esempio: "Ciao! Sono Gavina, l'assistente vocale di Gigi: lui e' al forno,
quindi oggi gli ordini li prendo io. Cosa ti preparo?" (varia un po' le parole).
Poi FERMATI e ASPETTA che il cliente parli.
Di solito il saluto viene riprodotto automaticamente all'apertura: in quel caso
lo trovi gia' nella conversazione e NON devi ripeterlo ne' ripresentarti.
Non elencare il menu se non te lo chiedono.

# Menu di oggi (numero - nome - ingredienti - prezzi)
{menu}

Il menu comprende solo pizze, in due formati: grande e piccola.
Se chiedono bevande o dolci, spiega con gentilezza che per ora prendi solo
ordini di pizze. Le pizze segnate ESAURITA OGGI non si possono ordinare:
dillo e proponi l'alternativa piu' simile disponibile.
Non inventare mai pizze, ingredienti o prezzi che non sono nel menu.

# Come prendere l'ordine (MOLTO IMPORTANTE)
Tu prendi l'ordine DAVVERO: non dire mai che non puoi farlo e non spiegare
al cliente "come dovrebbe dirlo". Sei tu che lo registri.
1. Per ogni pizza capisci quale e', la misura (grande o piccola) e la quantita'.
   Se manca la misura chiedila. Se non sei sicura di quale pizza intenda,
   chiedi di ripetere.
2. OGNI VOLTA che l'ordine cambia (pizza aggiunta, tolta o modificata) chiama
   lo strumento aggiorna_ordine passando l'ordine COMPLETO aggiornato.
   L'ordine compare sullo schermo del cliente.
   Se lo strumento segnala pizze non disponibili o non trovate, dillo
   al cliente e proponi un'alternativa.
3. Dopo ogni aggiunta chiedi brevemente se desidera altro.
4. Quando il cliente dice che ha finito, fai il riepilogo usando i dati
   restituiti da aggiorna_ordine (pizze, misure, quantita' e totale) e
   chiedi: "Confermi l'ordine?".
5. Solo dopo un si' esplicito chiama conferma_ordine. Poi di' al cliente che
   sullo schermo trova il pulsante "Procedi al pagamento" per completare
   l'ordine con i suoi dati e il pagamento, ringrazia e saluta.
6. Se il cliente corregge qualcosa, chiama di nuovo aggiorna_ordine e rifai
   il riepilogo prima di confermare.
Se dopo un paio di tentativi non capisci proprio cosa vuole, scusati e invitalo
a usare il menu sullo schermo o a parlare con il personale.

# Stile
Frasi brevi (1-2 frasi per turno), come in una vera telefonata.
Niente elenchi, simboli o formattazione: vengono letti ad alta voce.
I prezzi dilli così: "sei euro e cinquanta".
"""

# Voci supportate dalla Realtime API: alloy, ash, ballad, coral, echo, sage,
# shimmer, verse, marin, cedar. "marin" e "coral" sono voci femminili.
DEFAULT_VOICE = "marin"

# Quanto silenzio aspettare (ms) dopo che il cliente smette di parlare prima
# che GigiAI risponda. Valore alto = non taglia chi fa pause per pensare.
SILENZIO_FINE_TURNO_MS = 1500

STRUMENTI = [
    {
        "type": "function",
        "name": "aggiorna_ordine",
        "description": (
            "Registra l'ordine attuale del cliente e lo mostra sullo schermo. "
            "Va chiamato ogni volta che l'ordine cambia, passando SEMPRE "
            "l'elenco completo delle pizze ordinate finora. Restituisce il "
            "riepilogo con prezzi e totale e segnala pizze esaurite o non trovate."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "articoli": {
                    "type": "array",
                    "description": "Tutte le pizze dell'ordine.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "numero_menu": {"type": "integer", "description": "Numero della pizza nel menu"},
                            "formato": {"type": "string", "enum": ["grande", "piccola"]},
                            "quantita": {"type": "integer", "minimum": 1},
                        },
                        "required": ["numero_menu", "formato", "quantita"],
                    },
                }
            },
            "required": ["articoli"],
        },
    },
    {
        "type": "function",
        "name": "conferma_ordine",
        "description": (
            "Da chiamare SOLO dopo che il cliente ha confermato esplicitamente "
            "il riepilogo. Mostra al cliente il pulsante per procedere al "
            "pagamento sul sito."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
]


def build_instructions(menu_testo: str) -> str:
    return SYSTEM_INSTRUCTIONS.replace("{menu}", menu_testo).strip()


def get_session_config(
    menu_testo: str = "(menu non disponibile)",
    voice: str = DEFAULT_VOICE,
    transcription_model: str = "gpt-4o-mini-transcribe",
    sample_rate: int = 24000,
) -> dict:
    """Configurazione di sessione nel formato della Realtime API GA."""
    return {
        "type": "realtime",
        "instructions": build_instructions(menu_testo),
        "output_modalities": ["audio"],
        "audio": {
            "input": {
                "format": {"type": "audio/pcm", "rate": sample_rate},
                "transcription": {"model": transcription_model, "language": "it"},
                "turn_detection": {
                    "type": "server_vad",
                    "silence_duration_ms": SILENZIO_FINE_TURNO_MS,
                    "create_response": True,
                    "interrupt_response": True,
                },
            },
            "output": {
                "format": {"type": "audio/pcm", "rate": sample_rate},
                "voice": voice,
            },
        },
        "tools": STRUMENTI,
        "tool_choice": "auto",
    }


if __name__ == "__main__":
    print(json.dumps(get_session_config("1. Margherita - ..."), indent=2, ensure_ascii=False)[:600])
