"""
PIZZERIA DA GIGI — verifica disponibilita' e scala il magazzino per un ordine.

Chiama direttamente le API REST/RPC di Supabase con httpx (gia' una
dipendenza del progetto), invece di aggiungere la libreria "supabase": legge
URL e chiave dallo stesso file usato dal menu e dalla dashboard,
static/js/supabase-config.js — un'unica fonte di verita' per le credenziali,
niente da configurare due volte.

Se il database non e' ancora collegato (file con i valori segnaposto,
Supabase irraggiungibile, o qualunque errore di rete) l'ordine viene
comunque accettato senza controllo: e' lo stesso comportamento "di ripiego"
gia' usato per il menu e la dashboard, cosi' il checkout non si rompe mai
durante la configurazione iniziale o in caso di problemi di rete.
"""

import re
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent
CONFIG_JS_PATH = BASE_DIR / "static" / "js" / "supabase-config.js"


def _load_supabase_config() -> Optional[dict]:
    """Legge URL e chiave anon da supabase-config.js. None se non configurato."""
    try:
        testo = CONFIG_JS_PATH.read_text(encoding="utf-8")
    except OSError:
        return None

    url_match = re.search(r'SUPABASE_URL\s*:\s*"([^"]*)"', testo)
    key_match = re.search(r'SUPABASE_ANON_KEY\s*:\s*"([^"]*)"', testo)
    if not url_match or not key_match:
        return None

    url = url_match.group(1).strip()
    key = key_match.group(1).strip()
    if not url or not key or "INSERISCI" in url or "INSERISCI" in key:
        return None

    return {"url": url.rstrip("/"), "key": key}


class ArticoloOrdine(BaseModel):
    numero_menu: int
    formato: str  # "grande" oppure "piccola"
    quantita: int = 1


class DatiCliente(BaseModel):
    nome: str = ""
    telefono: str = ""
    indirizzo: str = ""


class NuovoOrdine(BaseModel):
    items: list[ArticoloOrdine]
    modalita: str = "ritiro"
    cliente: DatiCliente = DatiCliente()


async def _elabora_articolo(client: httpx.AsyncClient, headers: dict, base_url: str,
                             cliente: DatiCliente, articolo: ArticoloOrdine) -> dict:
    """Verifica + scala UN articolo del carrello. Ritorna sempre un esito, mai un'eccezione."""
    riga_esito = {"numero_menu": articolo.numero_menu, "formato": articolo.formato}

    resp = await client.get(
        f"{base_url}/rest/v1/pizze",
        headers=headers,
        params={"numero_menu": f"eq.{articolo.numero_menu}", "select": "id"},
    )
    resp.raise_for_status()
    righe = resp.json()
    if not righe:
        riga_esito.update(ok=False, motivo="Pizza non trovata nel database", ordine_id=None)
        return riga_esito
    pizza_id = righe[0]["id"]

    rpc_resp = await client.post(
        f"{base_url}/rest/v1/rpc/crea_ordine",
        headers=headers,
        json={
            "p_pizza_id": pizza_id,
            "p_formato": articolo.formato,
            "p_quantita": articolo.quantita,
            "p_nome": cliente.nome or None,
            "p_telefono": cliente.telefono or None,
            "p_indirizzo": cliente.indirizzo or None,
        },
    )
    rpc_resp.raise_for_status()
    righe_rpc = rpc_resp.json()
    esito = righe_rpc[0] if righe_rpc else {"ok": False, "motivo": "Nessuna risposta dal database"}
    riga_esito.update(
        ok=bool(esito.get("ok")),
        motivo=esito.get("motivo"),
        ordine_id=esito.get("ordine_id"),
    )
    return riga_esito


async def _cliente_e_fidato(client: httpx.AsyncClient, headers: dict, base_url: str, telefono: str) -> bool:
    if not telefono:
        return False
    resp = await client.get(
        f"{base_url}/rest/v1/clienti_fidati_contanti", headers=headers,
        params={"telefono": f"eq.{telefono}", "select": "telefono"},
    )
    resp.raise_for_status()
    return len(resp.json()) > 0


@router.get("/api/clienti/fidato")
async def cliente_fidato(telefono: str):
    cfg = _load_supabase_config()
    if cfg is None or not telefono:
        return {"fidato": False}
    headers = {"apikey": cfg["key"], "Authorization": f"Bearer {cfg['key']}"}
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            fidato = await _cliente_e_fidato(client, headers, cfg["url"], telefono)
    except httpx.HTTPError:
        fidato = False
    return {"fidato": fidato}


@router.post("/api/ordini/crea")
async def crea_ordine_endpoint(ordine: NuovoOrdine):
    cfg = _load_supabase_config()

    if cfg is None:
        # Database non ancora collegato: l'ordine passa comunque (ripiego).
        return {"ok": True, "verificato": False, "risultati": []}

    headers = {
        "apikey": cfg["key"],
        "Authorization": f"Bearer {cfg['key']}",
        "Content-Type": "application/json",
    }

    if ordine.modalita == "consegna":
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                fidato = await _cliente_e_fidato(client, headers, cfg["url"], ordine.cliente.telefono)
        except httpx.HTTPError:
            fidato = False
        if not fidato:
            return {
                "ok": False, "verificato": True, "risultati": [],
                "motivo_generale": (
                    "Il pagamento alla consegna e' riservato ai clienti abituali per gli "
                    "ordini con consegna a domicilio. Scegli il pagamento online, oppure "
                    "il ritiro in negozio per pagare in contanti."
                ),
            }

    risultati = []
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            for articolo in ordine.items:
                riga_esito = await _elabora_articolo(client, headers, cfg["url"], ordine.cliente, articolo)
                risultati.append(riga_esito)
    except httpx.HTTPError:
        # Supabase irraggiungibile ora: stesso ripiego, meglio far passare
        # l'ordine che bloccare il cliente per un problema di rete non suo.
        # Nota: se alcuni articoli erano gia' stati elaborati con successo
        # prima dell'errore, quelli restano comunque registrati nel database.
        return {"ok": True, "verificato": False, "risultati": risultati}

    tutti_ok = all(r["ok"] for r in risultati) if risultati else True
    return {"ok": tutti_ok, "verificato": True, "risultati": risultati}
