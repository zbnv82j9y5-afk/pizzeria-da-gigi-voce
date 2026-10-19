"""
PIZZERIA DA GIGI — ordini seguibili dal cliente e comuni di consegna.

- GET /api/consegna/comuni   elenco dei paesi serviti con il costo di consegna
                             (tabella Supabase "comuni_consegna", si modifica
                             senza toccare il codice).
- GET /api/ordini/traccia    stato degli ordini del cliente ("Il mio ordine"):
                             ?ids=<codice>,<codice>  (massimo 10).

La "scheda d'ordine" e' la riga di checkout_pendenti: la usano tutti e tre i
modi di pagare (carta, Satispay, contanti). Il codice dell'ordine e' il suo
id (uuid), impossibile da indovinare: chi non lo conosce non vede nulla.

Stesso principio del resto del sito: se il database non risponde, o non e'
ancora stato aggiornato con database/ordini_tracking.sql, queste funzioni
ripiegano su un comportamento sicuro (costo consegna fisso, nessun elenco)
invece di bloccare l'ordine del cliente.
"""
from __future__ import annotations

import re
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()

# Costo usato solo se la tabella dei comuni non e' disponibile.
COSTO_CONSEGNA_RIPIEGO_CENTESIMI = 250

STATI_CHIUSI = {"consegnato", "annullato"}
_UUID = re.compile(r"^[0-9a-fA-F-]{36}$")


def headers_supabase(cfg: dict) -> dict:
    return {
        "apikey": cfg["key"],
        "Authorization": f"Bearer {cfg['key']}",
        "Content-Type": "application/json",
    }


def _cfg() -> Optional[dict]:
    # Import qui dentro per evitare import circolari con pizzeria_ordini.
    from pizzeria_ordini import _load_supabase_config
    return _load_supabase_config()


async def leggi_comuni(client: httpx.AsyncClient, headers: dict, base_url: str) -> Optional[list[dict]]:
    """Comuni attivi in ordine di elenco. None = tabella non disponibile."""
    try:
        resp = await client.get(
            f"{base_url}/rest/v1/comuni_consegna", headers=headers,
            params={"attivo": "eq.true", "select": "nome,costo_centesimi", "order": "ordine.asc,nome.asc"},
        )
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    return resp.json()


async def costo_consegna(client: httpx.AsyncClient, headers: dict, base_url: str,
                         comune: str) -> tuple[bool, int, str, str]:
    """(valido, costo_centesimi, comune_normalizzato, messaggio_errore).

    Se la tabella dei comuni non c'e' ancora: costo fisso e comune accettato
    cosi' com'e' (deve solo non essere vuoto)."""
    comune = (comune or "").strip()
    comuni = await leggi_comuni(client, headers, base_url)
    if not comuni:
        if not comune:
            return False, 0, "", "Indica il paese o la citta' per la consegna."
        return True, COSTO_CONSEGNA_RIPIEGO_CENTESIMI, comune, ""
    for c in comuni:
        if c["nome"].strip().lower() == comune.lower():
            return True, int(c["costo_centesimi"]), c["nome"], ""
    if not comune:
        return False, 0, "", "Scegli il paese o la citta' di consegna."
    return False, 0, "", f"Purtroppo non consegniamo a {comune}. Scegli il ritiro in negozio."


def indirizzo_completo(indirizzo: str, comune: str) -> str:
    """'Via Roma 1' + 'Sorso' -> 'Via Roma 1, Sorso' (per staff e fattorino)."""
    indirizzo = (indirizzo or "").strip()
    comune = (comune or "").strip()
    if not comune:
        return indirizzo
    if comune.lower() in indirizzo.lower():
        return indirizzo
    return f"{indirizzo}, {comune}" if indirizzo else comune


async def prezzi_pizze(client: httpx.AsyncClient, headers: dict, base_url: str,
                       numeri_menu: list[int]) -> dict:
    lista = ",".join(str(int(n)) for n in numeri_menu) or "0"
    resp = await client.get(
        f"{base_url}/rest/v1/pizze", headers=headers,
        params={"numero_menu": f"in.({lista})",
                "select": "id,numero_menu,nome,prezzo_grande,prezzo_piccola,disponibile"},
    )
    resp.raise_for_status()
    return {r["numero_menu"]: r for r in resp.json()}


@router.get("/api/consegna/comuni")
async def elenco_comuni():
    cfg = _cfg()
    if cfg is None:
        return {"comuni": [], "costo_fisso_centesimi": COSTO_CONSEGNA_RIPIEGO_CENTESIMI}
    async with httpx.AsyncClient(timeout=6.0) as client:
        comuni = await leggi_comuni(client, headers_supabase(cfg), cfg["url"])
    return {"comuni": comuni or [], "costo_fisso_centesimi": COSTO_CONSEGNA_RIPIEGO_CENTESIMI}


@router.get("/api/ordini/traccia")
async def traccia_ordini(ids: str = ""):
    codici = [c.strip() for c in ids.split(",") if c.strip()][:10]
    codici = [c for c in codici if _UUID.match(c)]
    if not codici:
        return {"ordini": []}
    cfg = _cfg()
    if cfg is None:
        raise HTTPException(503, "Database non collegato")

    headers = headers_supabase(cfg)
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(
            f"{cfg['url']}/rest/v1/checkout_pendenti", headers=headers,
            params={"id": f"in.({','.join(codici)})", "select": "*"},
        )
        if resp.status_code != 200:
            raise HTTPException(502, "Database non raggiungibile")
        schede = resp.json()

        numeri = set()
        for s in schede:
            for r in (s.get("ordini_creati") or s.get("carrello") or []):
                if r.get("numero_menu") is not None:
                    numeri.add(int(r["numero_menu"]))
        nomi = {}
        if numeri:
            try:
                nomi = {n: p["nome"] for n, p in (await prezzi_pizze(client, headers, cfg["url"], sorted(numeri))).items()}
            except httpx.HTTPError:
                nomi = {}

    risultato = []
    for s in schede:
        righe_sorgente = s.get("ordini_creati") or s.get("carrello") or []
        righe = []
        for r in righe_sorgente:
            n = r.get("numero_menu")
            righe.append({
                "numero_menu": n,
                "nome": nomi.get(n, f"Pizza n. {n}"),
                "formato": r.get("formato"),
                "quantita": r.get("quantita", 1),
                "prezzo_unitario_centesimi": r.get("prezzo_unitario_centesimi"),
                "ok": r.get("ok", True),
            })
        stato_ordine = s.get("stato_ordine") or "nuovo"
        risultato.append({
            "id": s["id"],
            "codice": s["id"][:6].upper(),
            "creato_il": s.get("creato_il"),
            "pagamento": s.get("stato"),           # pagato | da_pagare | in_attesa | fallito | scaduto
            "metodo": s.get("provider"),            # stripe | satispay | contanti
            "stato_ordine": stato_ordine,
            "consegna_entro": s.get("consegna_entro"),
            "modalita": s.get("modalita") or ("consegna" if s.get("indirizzo_cliente") else "ritiro"),
            "comune": s.get("comune"),
            "indirizzo": s.get("indirizzo_cliente"),
            "nome": s.get("nome_cliente"),
            "importo_centesimi": s.get("importo_centesimi"),
            "omaggio_bibita": s.get("omaggio_bibita"),
            "note": s.get("note"),
            "righe": righe,
            "chiuso": stato_ordine in STATI_CHIUSI or s.get("stato") in ("fallito", "scaduto"),
        })
    risultato.sort(key=lambda o: o.get("creato_il") or "", reverse=True)
    return {"ordini": risultato}


_COLONNE_NUOVE = ("modalita", "comune", "stato_ordine")


async def inserisci_scheda(client: httpx.AsyncClient, headers: dict, base_url: str, dati: dict) -> httpx.Response:
    """Crea la scheda d'ordine in checkout_pendenti. Se il database non ha
    ancora le colonne nuove (ordini_tracking.sql non applicato) riprova senza,
    cosi' i pagamenti continuano a funzionare come prima."""
    h = {**headers, "Prefer": "return=representation"}
    resp = await client.post(f"{base_url}/rest/v1/checkout_pendenti", headers=h, json=dati)
    if resp.status_code == 400 and any(k in dati for k in _COLONNE_NUOVE):
        ridotti = {k: v for k, v in dati.items() if k not in _COLONNE_NUOVE}
        resp = await client.post(f"{base_url}/rest/v1/checkout_pendenti", headers=h, json=ridotti)
    return resp
