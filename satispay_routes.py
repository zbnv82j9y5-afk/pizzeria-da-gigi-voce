"""
PIZZERIA DA GIGI — pagamento online con Satispay (Opzione B: il magazzino si
scala SOLO a pagamento confermato, mai prima). Vedi SATISPAY-INTEGRAZIONE.md
per il piano completo.

Finche' SATISPAY_KEY_ID / SATISPAY_PRIVATE_KEY non sono impostate come
variabili d'ambiente, /api/checkout/avvia risponde con un errore chiaro
(503) invece di rompersi — il resto del sito (menu, ordine con pagamento
alla consegna) continua a funzionare esattamente come prima.
"""
import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import os

import satispay_client
from pizzeria_ordini import _load_supabase_config

router = APIRouter()

# Tenere allineato con DELIVERY_FEE in templates/riepilogo.html (e
# static/riepilogo.html) — non c'e' un'unica fonte di verita' per questo
# valore, esattamente come per i prezzi delle pizze (vedi sotto).
DELIVERY_FEE_CENTESIMI = 250


class RigaCarrelloCheckout(BaseModel):
    numero_menu: int
    formato: str  # "grande" oppure "piccola"
    quantita: int = 1


class DatiClienteCheckout(BaseModel):
    nome: str
    telefono: str
    indirizzo: str = ""


class AvviaCheckoutBody(BaseModel):
    carrello: list[RigaCarrelloCheckout]
    modalita: str = "ritiro"
    cliente: DatiClienteCheckout


def _headers(cfg: dict) -> dict:
    return {
        "apikey": cfg["key"],
        "Authorization": f"Bearer {cfg['key']}",
        "Content-Type": "application/json",
    }


async def _prezzi_pizze(client: httpx.AsyncClient, headers: dict, base_url: str, numeri_menu: list[int]) -> dict:
    """Legge id/prezzo_grande/prezzo_piccola/disponibile per i numeri_menu
    richiesti IN UNA SOLA query, cosi' il totale che paga davvero il cliente
    e' sempre calcolato dai prezzi VERI del database — mai da quelli
    (duplicati, solo per la grafica) mostrati nel browser, che un cliente in
    teoria potrebbe manomettere."""
    lista = ",".join(str(n) for n in numeri_menu)
    resp = await client.get(
        f"{base_url}/rest/v1/pizze", headers=headers,
        params={"numero_menu": f"in.({lista})", "select": "id,numero_menu,prezzo_grande,prezzo_piccola,disponibile"},
    )
    resp.raise_for_status()
    return {r["numero_menu"]: r for r in resp.json()}


@router.post("/api/checkout/avvia")
async def avvia_checkout(body: AvviaCheckoutBody, request: Request):
    if not body.carrello:
        raise HTTPException(400, "Carrello vuoto")

    cfg = _load_supabase_config()
    if cfg is None:
        raise HTTPException(503, "Pagamento online non disponibile: database non collegato")

    headers = _headers(cfg)
    async with httpx.AsyncClient(timeout=10.0) as client:
        numeri = [r.numero_menu for r in body.carrello]
        prezzi = await _prezzi_pizze(client, headers, cfg["url"], numeri)

        righe_dettagliate = []
        totale_centesimi = 0
        for riga in body.carrello:
            info = prezzi.get(riga.numero_menu)
            if info is None:
                raise HTTPException(400, f"Pizza numero {riga.numero_menu} non trovata")
            if info.get("disponibile") is False:
                raise HTTPException(409, f"Una pizza del carrello non e' piu' disponibile (numero {riga.numero_menu})")
            prezzo = info["prezzo_grande"] if riga.formato == "grande" else info["prezzo_piccola"]
            prezzo_centesimi = round(float(prezzo) * 100)
            totale_centesimi += prezzo_centesimi * riga.quantita
            righe_dettagliate.append({
                "numero_menu": riga.numero_menu,
                "formato": riga.formato,
                "quantita": riga.quantita,
                "prezzo_unitario_centesimi": prezzo_centesimi,
            })

        if body.modalita == "consegna":
            totale_centesimi += DELIVERY_FEE_CENTESIMI

        # --- fedelta': primo ordine -> omaggio bibita (fisico, non scontato
        # sul pagamento); dal secondo ordine -> punti (vedi _aggiorna_fedelta
        # nel callback, chiamata solo a pagamento confermato) ---
        fed_resp = await client.get(
            f"{cfg['url']}/rest/v1/clienti_fedelta", headers=headers,
            params={"telefono": f"eq.{body.cliente.telefono}", "select": "*"},
        )
        fed_resp.raise_for_status()
        fed_righe = fed_resp.json()
        primo_ordine = not fed_righe or not fed_righe[0].get("primo_ordine_fatto")

        crea_resp = await client.post(
            f"{cfg['url']}/rest/v1/checkout_pendenti",
            headers={**headers, "Prefer": "return=representation"},
            json={
                "carrello": righe_dettagliate,
                "nome_cliente": body.cliente.nome,
                "telefono_cliente": body.cliente.telefono,
                "indirizzo_cliente": body.cliente.indirizzo,
                "importo_centesimi": totale_centesimi,
                "omaggio_bibita": primo_ordine,
            },
        )
        crea_resp.raise_for_status()
        checkout = crea_resp.json()[0]

        callback_url = str(request.base_url).rstrip("/") + "/api/satispay/callback"
        try:
            pagamento = await satispay_client.crea_pagamento(
                importo_centesimi=totale_centesimi,
                checkout_id=checkout["id"],
                callback_base_url=callback_url,
            )
        except satispay_client.SatispayNonConfigurato as e:
            raise HTTPException(503, str(e))
        except httpx.HTTPStatusError as e:
            raise HTTPException(502, f"Satispay ha rifiutato la richiesta di pagamento: {e.response.text}")

        await client.patch(
            f"{cfg['url']}/rest/v1/checkout_pendenti", headers=headers,
            params={"id": f"eq.{checkout['id']}"},
            json={"satispay_payment_id": pagamento["id"]},
        )

    return {"checkout_id": checkout["id"], "satispay_payment_id": pagamento["id"]}


@router.get("/api/checkout/stato/{checkout_id}")
async def stato_checkout(checkout_id: str):
    cfg = _load_supabase_config()
    if cfg is None:
        raise HTTPException(503, "Database non collegato")

    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.get(
            f"{cfg['url']}/rest/v1/checkout_pendenti", headers=_headers(cfg),
            params={"id": f"eq.{checkout_id}", "select": "stato"},
        )
    resp.raise_for_status()
    righe = resp.json()
    if not righe:
        raise HTTPException(404, "Checkout non trovato")
    return {"stato": righe[0]["stato"]}


async def _aggiorna_fedelta(client: httpx.AsyncClient, headers: dict, base_url: str, telefono: str):
    resp = await client.get(
        f"{base_url}/rest/v1/clienti_fedelta", headers=headers,
        params={"telefono": f"eq.{telefono}", "select": "*"},
    )
    resp.raise_for_status()
    righe = resp.json()
    if not righe:
        await client.post(
            f"{base_url}/rest/v1/clienti_fedelta", headers=headers,
            json={"telefono": telefono, "primo_ordine_fatto": True, "ordini_totali": 1, "punti": 0},
        )
        return

    riga = righe[0]
    if not riga.get("primo_ordine_fatto"):
        await client.patch(
            f"{base_url}/rest/v1/clienti_fedelta", headers=headers,
            params={"telefono": f"eq.{telefono}"},
            json={"primo_ordine_fatto": True, "ordini_totali": riga.get("ordini_totali", 0) + 1},
        )
    else:
        await client.patch(
            f"{base_url}/rest/v1/clienti_fedelta", headers=headers,
            params={"telefono": f"eq.{telefono}"},
            json={"punti": riga.get("punti", 0) + 1, "ordini_totali": riga.get("ordini_totali", 0) + 1},
        )


@router.get("/api/satispay/callback")
async def callback_satispay(payment_id: str):
    """Chiamata dal SERVER di Satispay (mai dal browser del cliente): niente
    cookie di accesso, per questo /api/satispay/callback e' nella lista dei
    percorsi liberi in serve.py. E' solo un "vai a controllare": lo stato
    vero si chiede sempre a Satispay con una GET separata, mai fidandosi del
    solo callback."""
    cfg = _load_supabase_config()
    if cfg is None:
        return {"ok": True}

    try:
        stato_reale = await satispay_client.stato_pagamento(payment_id)
    except Exception:
        # Satispay ripete la chiamata di callback in caso di problemi
        # transitori: meglio non fare nulla ora che rompere qualcosa.
        return {"ok": True}

    headers = _headers(cfg)
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{cfg['url']}/rest/v1/checkout_pendenti", headers=headers,
            params={"satispay_payment_id": f"eq.{payment_id}", "select": "*"},
        )
        resp.raise_for_status()
        righe = resp.json()
        if not righe or righe[0]["stato"] != "in_attesa":
            return {"ok": True}  # gia' gestito prima, o non e' un pagamento nostro: ignora

        checkout = righe[0]
        stato_satispay = stato_reale.get("status")

        if stato_satispay == "ACCEPTED":
            risultati = []
            for riga in checkout["carrello"]:
                pizza_resp = await client.get(
                    f"{cfg['url']}/rest/v1/pizze", headers=headers,
                    params={"numero_menu": f"eq.{riga['numero_menu']}", "select": "id"},
                )
                pizza_resp.raise_for_status()
                pizze_trovate = pizza_resp.json()
                if not pizze_trovate:
                    risultati.append({**riga, "ok": False, "motivo": "Pizza non trovata"})
                    continue

                rpc_resp = await client.post(
                    f"{cfg['url']}/rest/v1/rpc/crea_ordine", headers=headers,
                    json={
                        "p_pizza_id": pizze_trovate[0]["id"],
                        "p_formato": riga["formato"],
                        "p_quantita": riga["quantita"],
                        "p_nome": checkout["nome_cliente"],
                        "p_telefono": checkout["telefono_cliente"],
                        "p_indirizzo": checkout["indirizzo_cliente"],
                    },
                )
                rpc_resp.raise_for_status()
                righe_rpc = rpc_resp.json()
                esito = righe_rpc[0] if righe_rpc else {"ok": False, "motivo": "Nessuna risposta dal database"}
                risultati.append({
                    **riga,
                    "ok": bool(esito.get("ok")),
                    "motivo": esito.get("motivo"),
                    "ordine_id": esito.get("ordine_id"),
                })

            righe_fallite = [r for r in risultati if not r["ok"]]
            note = None
            if righe_fallite:
                # Edge case: il cliente ha pagato ma una pizza e' finita nel
                # frattempo — le righe riuscite restano valide, per quella
                # fallita si rimborsa automaticamente la differenza.
                importo_da_rimborsare = sum(r["prezzo_unitario_centesimi"] * r["quantita"] for r in righe_fallite)
                descrizione = ", ".join(f"pizza #{r['numero_menu']} {r['formato']}" for r in righe_fallite)
                try:
                    await satispay_client.rimborsa_pagamento(payment_id, importo_da_rimborsare)
                    note = f"Rimborso parziale eseguito ({importo_da_rimborsare/100:.2f} EUR) per: {descrizione}"
                except Exception as e:
                    note = f"ATTENZIONE: rimborso parziale FALLITO per {descrizione} — verificare a mano. Errore: {e}"

            await client.patch(
                f"{cfg['url']}/rest/v1/checkout_pendenti", headers=headers,
                params={"id": f"eq.{checkout['id']}"},
                json={"stato": "pagato", "ordini_creati": risultati, "note": note},
            )
            await _aggiorna_fedelta(client, headers, cfg["url"], checkout["telefono_cliente"])
        elif stato_satispay == "CANCELED":
            # Solo CANCELED e' un esito negativo definitivo. Qualunque altro
            # stato (PENDING, AUTHORIZED, ecc.) e' ancora in corso: Satispay
            # richiamera' di nuovo quando cambiera' davvero, quindi non
            # tocchiamo il checkout ora (altrimenti un pagamento poi accettato
            # verrebbe ignorato perche' il checkout non sarebbe piu' "in_attesa").
            await client.patch(
                f"{cfg['url']}/rest/v1/checkout_pendenti", headers=headers,
                params={"id": f"eq.{checkout['id']}"},
                json={"stato": "fallito"},
            )

    return {"ok": True}


@router.get("/api/satispay/diagnostica")
async def diagnostica_satispay():
    return {
        "SATISPAY_KEY_ID_impostata": bool(os.environ.get("SATISPAY_KEY_ID")),
        "SATISPAY_PRIVATE_KEY_impostata": bool(os.environ.get("SATISPAY_PRIVATE_KEY")),
        "SATISPAY_BASE_URL": os.environ.get("SATISPAY_BASE_URL", "(default) staging.authservices.satispay.com"),
    }
