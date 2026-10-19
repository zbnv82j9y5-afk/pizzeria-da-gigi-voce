"""
Menu della Pizzeria Da Gigi per l'assistente vocale.

Il menu (con prezzi e disponibilita') viene letto dal database Supabase,
tabella "pizze": la colonna "disponibile" e' aggiornata in automatico dai
trigger del magazzino (vedi database/funzioni.sql), quindi se un ingrediente
finisce la pizza risulta non disponibile anche per GigiAI.

URL e chiave si prendono dalle variabili d'ambiente SUPABASE_URL /
SUPABASE_ANON_KEY oppure, se mancano, dallo stesso file usato dal sito
(static/js/supabase-config.js). Se il database non risponde si usa il menu
di riserva qui sotto, cosi' l'assistente funziona comunque.
"""

import logging
import os
import re
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_JS_PATH = BASE_DIR / "static" / "js" / "supabase-config.js"

MENU_RISERVA = [
    {"numero_menu": 1, "nome": 'Marinara', "descrizione": 'pomodoro, aglio, origano', "prezzo_grande": 3.5, "prezzo_piccola": 2.5, "disponibile": True},
    {"numero_menu": 2, "nome": 'Margherita', "descrizione": 'pomodoro, mozzarella', "prezzo_grande": 4.5, "prezzo_piccola": 3.0, "disponibile": True},
    {"numero_menu": 3, "nome": 'Romana', "descrizione": 'pomodoro, mozzarella, acciughe, capperi', "prezzo_grande": 5.0, "prezzo_piccola": 3.5, "disponibile": True},
    {"numero_menu": 4, "nome": 'Toscana', "descrizione": 'pomodoro, mozzarella, salsiccia, cipolla', "prezzo_grande": 5.0, "prezzo_piccola": 3.5, "disponibile": True},
    {"numero_menu": 5, "nome": 'Completa', "descrizione": 'pomodoro, mozzarella, funghi, carciofi, prosciutto, uovo', "prezzo_grande": 5.0, "prezzo_piccola": 3.5, "disponibile": True},
    {"numero_menu": 6, "nome": 'Imperiale', "descrizione": 'pomodoro, mozzarella, prosciutto, funghi, carciofi, olive', "prezzo_grande": 6.0, "prezzo_piccola": 4.0, "disponibile": True},
    {"numero_menu": 7, "nome": 'Cardinale', "descrizione": 'pomodoro, mozzarella, acciughe, capperi, olive', "prezzo_grande": 6.0, "prezzo_piccola": 4.0, "disponibile": True},
    {"numero_menu": 8, "nome": 'Veneziana', "descrizione": 'pomodoro, mozzarella, cipolla, acciughe', "prezzo_grande": 6.5, "prezzo_piccola": 4.5, "disponibile": True},
    {"numero_menu": 9, "nome": 'Wurstel', "descrizione": 'pomodoro, mozzarella, wurstel', "prezzo_grande": 5.0, "prezzo_piccola": 4.0, "disponibile": True},
    {"numero_menu": 10, "nome": 'Canadese', "descrizione": 'pomodoro, mozzarella, bacon, cipolla', "prezzo_grande": 6.0, "prezzo_piccola": 4.0, "disponibile": True},
    {"numero_menu": 11, "nome": 'Diavola', "descrizione": 'pomodoro, mozzarella, salame piccante', "prezzo_grande": 6.0, "prezzo_piccola": 4.0, "disponibile": True},
    {"numero_menu": 12, "nome": 'Salsiccia', "descrizione": 'pomodoro, mozzarella, salsiccia', "prezzo_grande": 6.5, "prezzo_piccola": 4.5, "disponibile": True},
    {"numero_menu": 13, "nome": 'Sarda', "descrizione": 'pomodoro, mozzarella, pancetta, cipolla, pecorino', "prezzo_grande": 7.0, "prezzo_piccola": 4.5, "disponibile": True},
    {"numero_menu": 14, "nome": 'Boscanola', "descrizione": 'pomodoro, mozzarella, funghi, salsiccia', "prezzo_grande": 7.0, "prezzo_piccola": 5.0, "disponibile": True},
    {"numero_menu": 15, "nome": 'Arrabbiata', "descrizione": 'pomodoro, mozzarella, salame piccante, peperoncino', "prezzo_grande": 7.0, "prezzo_piccola": 5.0, "disponibile": True},
    {"numero_menu": 16, "nome": 'Quattro Stagioni', "descrizione": 'pomodoro, mozzarella, prosciutto, funghi, carciofi, olive', "prezzo_grande": 6.5, "prezzo_piccola": 5.0, "disponibile": True},
    {"numero_menu": 17, "nome": 'Capricciosa', "descrizione": 'pomodoro, mozzarella, prosciutto, funghi, carciofi, olive, uovo', "prezzo_grande": 7.0, "prezzo_piccola": 5.0, "disponibile": True},
    {"numero_menu": 18, "nome": 'Tucano', "descrizione": 'pomodoro, mozzarella, prosciutto cotto, funghi', "prezzo_grande": 6.0, "prezzo_piccola": 4.0, "disponibile": True},
    {"numero_menu": 19, "nome": 'Calzone (chiusa)', "descrizione": 'pomodoro, mozzarella, prosciutto, ricotta', "prezzo_grande": 6.5, "prezzo_piccola": 4.5, "disponibile": True},
    {"numero_menu": 20, "nome": 'Calzone Farcito (chiusa)', "descrizione": 'pomodoro, mozzarella, prosciutto, ricotta, funghi', "prezzo_grande": 7.0, "prezzo_piccola": 5.0, "disponibile": True},
    {"numero_menu": 21, "nome": 'Gorgonzola', "descrizione": 'pomodoro, mozzarella, gorgonzola', "prezzo_grande": 6.5, "prezzo_piccola": 4.5, "disponibile": True},
    {"numero_menu": 22, "nome": 'Quattro Formaggi', "descrizione": 'pomodoro, mozzarella, gorgonzola, parmigiano, provola', "prezzo_grande": 7.0, "prezzo_piccola": 5.0, "disponibile": True},
    {"numero_menu": 23, "nome": 'Pesto', "descrizione": 'pomodoro, mozzarella, pesto', "prezzo_grande": 8.5, "prezzo_piccola": 4.5, "disponibile": True},
    {"numero_menu": 24, "nome": 'Sassarese', "descrizione": 'pomodoro, mozzarella, salsiccia, cipolla, pancetta', "prezzo_grande": 6.0, "prezzo_piccola": 4.0, "disponibile": True},
    {"numero_menu": 25, "nome": 'Greca', "descrizione": 'pomodoro, mozzarella, olive, cipolla, origano', "prezzo_grande": 6.0, "prezzo_piccola": 4.0, "disponibile": True},
    {"numero_menu": 26, "nome": 'Ortolana', "descrizione": 'pomodoro, mozzarella, verdure grigliate', "prezzo_grande": 7.0, "prezzo_piccola": 5.0, "disponibile": True},
    {"numero_menu": 27, "nome": 'Antunna', "descrizione": 'pomodoro, mozzarella, tonno, cipolla', "prezzo_grande": 6.5, "prezzo_piccola": 4.5, "disponibile": True},
    {"numero_menu": 28, "nome": 'Porcini', "descrizione": 'pomodoro, mozzarella, funghi porcini', "prezzo_grande": 7.5, "prezzo_piccola": 5.5, "disponibile": True},
    {"numero_menu": 29, "nome": 'Tirolese', "descrizione": 'pomodoro, mozzarella, speck, cipolla', "prezzo_grande": 8.0, "prezzo_piccola": 6.0, "disponibile": True},
    {"numero_menu": 30, "nome": 'Patatosa', "descrizione": 'pomodoro, mozzarella, patate, rosmarino', "prezzo_grande": 6.0, "prezzo_piccola": 4.0, "disponibile": True},
    {"numero_menu": 31, "nome": 'Furia', "descrizione": 'pomodoro, mozzarella, salame piccante, olive, peperoncino', "prezzo_grande": 7.0, "prezzo_piccola": 5.0, "disponibile": True},
    {"numero_menu": 32, "nome": 'Bresaola', "descrizione": 'pomodoro, mozzarella, bresaola, rucola, scaglie di grana', "prezzo_grande": 7.0, "prezzo_piccola": 5.0, "disponibile": True},
    {"numero_menu": 33, "nome": 'San Daniele', "descrizione": 'pomodoro, mozzarella, prosciutto crudo San Daniele, rucola', "prezzo_grande": 7.0, "prezzo_piccola": 5.0, "disponibile": True},
    {"numero_menu": 34, "nome": 'Primavera', "descrizione": 'pomodoro, mozzarella, verdure di stagione', "prezzo_grande": 8.0, "prezzo_piccola": 3.5, "disponibile": True},
    {"numero_menu": 35, "nome": 'Logudoresse', "descrizione": 'pomodoro, mozzarella, salsiccia, funghi, carciofi', "prezzo_grande": 7.5, "prezzo_piccola": 5.5, "disponibile": True},
    {"numero_menu": 36, "nome": 'Salmone', "descrizione": 'pomodoro, mozzarella, salmone affumicato', "prezzo_grande": 7.5, "prezzo_piccola": 5.5, "disponibile": True},
    {"numero_menu": 37, "nome": 'Catalana', "descrizione": 'pomodoro, mozzarella, acciughe, capperi, olive, origano', "prezzo_grande": 7.0, "prezzo_piccola": 5.5, "disponibile": True},
    {"numero_menu": 38, "nome": 'Carbonara', "descrizione": 'pomodoro, mozzarella, uovo, pancetta, pecorino', "prezzo_grande": 7.5, "prezzo_piccola": 5.5, "disponibile": True},
    {"numero_menu": 39, "nome": 'Mare e Monti', "descrizione": 'pomodoro, mozzarella, frutti di mare, funghi', "prezzo_grande": 8.0, "prezzo_piccola": 5.0, "disponibile": True},
    {"numero_menu": 40, "nome": 'Campagnola', "descrizione": 'pomodoro, mozzarella, cavallo, patate al forno', "prezzo_grande": 7.5, "prezzo_piccola": 6.5, "disponibile": True}
]


def _config_supabase() -> dict | None:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    if not (url and key):
        try:
            testo = CONFIG_JS_PATH.read_text(encoding="utf-8")
        except OSError:
            return None
        u = re.search(r'SUPABASE_URL\s*:\s*"([^"]*)"', testo)
        k = re.search(r'SUPABASE_ANON_KEY\s*:\s*"([^"]*)"', testo)
        url = u.group(1).strip() if u else ""
        key = k.group(1).strip() if k else ""
    if not url or not key or "INSERISCI" in url or "INSERISCI" in key:
        return None
    return {"url": url.rstrip("/"), "key": key}


async def carica_menu() -> tuple[list[dict], bool]:
    """Ritorna (menu, da_database). Non solleva mai eccezioni."""
    cfg = _config_supabase()
    if cfg is None:
        return [dict(p) for p in MENU_RISERVA], False
    headers = {"apikey": cfg["key"], "Authorization": f"Bearer {cfg['key']}"}
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(
                f"{cfg['url']}/rest/v1/pizze",
                headers=headers,
                params={
                    "select": "numero_menu,nome,descrizione,prezzo_grande,prezzo_piccola,disponibile",
                    "order": "numero_menu.asc",
                },
            )
            resp.raise_for_status()
            righe = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning(f"Menu da Supabase non disponibile, uso il menu di riserva: {e}")
        return [dict(p) for p in MENU_RISERVA], False

    menu = []
    for r in righe:
        if r.get("numero_menu") is None:
            continue
        menu.append({
            "numero_menu": int(r["numero_menu"]),
            "nome": r.get("nome") or "",
            "descrizione": r.get("descrizione") or "",
            "prezzo_grande": float(r.get("prezzo_grande") or 0),
            "prezzo_piccola": float(r.get("prezzo_piccola") or 0),
            "disponibile": r.get("disponibile") is not False,
        })
    if not menu:
        return [dict(p) for p in MENU_RISERVA], False
    return menu, True


def euro(valore: float) -> str:
    """5.5 -> '5,50 euro' (formato leggibile ad alta voce)."""
    return f"{valore:.2f}".replace(".", ",") + " euro"


def menu_come_testo(menu: list[dict]) -> str:
    righe = []
    for p in menu:
        stato = "" if p["disponibile"] else "  [ESAURITA OGGI: non ordinabile]"
        righe.append(
            f"{p['numero_menu']}. {p['nome']} - {p['descrizione']} - "
            f"grande {euro(p['prezzo_grande'])} / piccola {euro(p['prezzo_piccola'])}{stato}"
        )
    return "\n".join(righe)
