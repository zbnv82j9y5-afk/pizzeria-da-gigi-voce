"""
PIZZERIA DA GIGI — pagamento online con carta di credito/debito (Stripe),
alternativa a Satispay per chi non ha l'app o preferisce pagare con carta.
Stessa architettura di satispay_routes.py (Opzione B: il magazzino si scala
SOLO a pagamento confermato, mai prima) e stessa tabella "checkout_pendenti"
(colonna "provider" per distinguere le due strade) — cosi' la logica di
calcolo prezzi/fedelta/creazione ordini/rimborso parziale non va duplicata.
Vedi STRIPE-INTEGRAZIONE.md per il piano completo.

Finche' STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET non sono impostate come
variabili d'ambiente, /api/checkout/stripe/avvia risponde con un errore
chiaro (503) invece di rompersi — il resto del sito (menu, Satispay,
pagamento alla consegna) continua a funzionare esattamente come prima.
"""
import httpx
from fastapi import APIRouter, HTTPException, Request

import stripe_client
from pizzeria_ordini import _load_supabase_config
from satispay_routes import (
    AvviaCheckoutBody,
    DELIVERY_FEE_CENTESIMI,
    _headers,
    _prezzi_pizze,
    _aggiorna_fedelta,
)

import os

router = APIRouter()


@router.post("/api/checkout/stripe/avvia")
async def avvia_checkout_stripe(body: AvviaCheckoutBody, request: Request):
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
                "provider": "stripe",
            },
        )
        crea_resp.raise_for_status()
        checkout = crea_resp.json()[0]

        base = str(request.base_url).rstrip("/")
        success_url = f"{base}/riepilogo.html?checkout_id={checkout['id']}&pagamento=stripe_ok"
        cancel_url = f"{base}/riepilogo.html?checkout_id={checkout['id']}&pagamento=stripe_annullato"

        try:
            sessione = await stripe_client.crea_sessione_checkout(
                importo_centesimi=totale_centesimi,
                checkout_id=checkout["id"],
                success_url=success_url,
                cancel_url=cancel_url,
            )
        except stripe_client.StripeNonConfigurato as e:
            raise HTTPException(503, str(e))
        except Exception as e:
            raise HTTPException(502, f"Stripe ha rifiutato la richiesta di pagamento: {e}")

        await client.patch(
            f"{cfg['url']}/rest/v1/checkout_pendenti", headers=headers,
            params={"id": f"eq.{checkout['id']}"},
            json={"stripe_session_id": sessione["id"]},
        )

    return {"checkout_id": checkout["id"], "url": sessione["url"]}


@router.post("/api/stripe/webhook")
async def webhook_stripe(request: Request):
    """Chiamata dal SERVER di Stripe (mai dal browser del cliente): niente
    cookie di accesso, per questo /api/stripe/webhook e' nella lista dei
    percorsi liberi in serve.py. A differenza del callback Satispay, qui
    l'evento arriva gia' completo — ma va SEMPRE verificata la firma prima
    di fidarsi del contenuto (leggi_evento_webhook solleva un errore se la
    firma non torna)."""
    cfg = _load_supabase_config()
    if cfg is None:
        return {"ok": True}

    payload = await request.body()
    firma_header = request.headers.get("stripe-signature", "")
    try:
        evento = stripe_client.leggi_evento_webhook(payload, firma_header)
    except Exception:
        raise HTTPException(400, "Firma webhook non valida")

    if evento["type"] != "checkout.session.completed":
        return {"ok": True}  # ignoriamo gli altri eventi (non ci servono)

    sessione = evento["data"]["object"]
    if getattr(sessione, "payment_status", None) != "paid":
        return {"ok": True}  # sessione completata ma non ancora pagata (raro): aspettiamo l'evento giusto

    checkout_id = getattr(sessione, "client_reference_id", None)
    if not checkout_id:
        return {"ok": True}

    headers = _headers(cfg)
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{cfg['url']}/rest/v1/checkout_pendenti", headers=headers,
            params={"id": f"eq.{checkout_id}", "select": "*"},
        )
        resp.raise_for_status()
        righe = resp.json()
        if not righe or righe[0]["stato"] != "in_attesa":
            return {"ok": True}  # gia' gestito prima (Stripe puo' ripetere il webhook), o non e' un nostro checkout

        checkout = righe[0]
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
            # Stesso edge case gestito per Satispay: il cliente ha gia'
            # pagato ma una pizza e' finita nel frattempo — le righe riuscite
            # restano valide, per quella fallita si rimborsa automaticamente.
            importo_da_rimborsare = sum(r["prezzo_unitario_centesimi"] * r["quantita"] for r in righe_fallite)
            descrizione = ", ".join(f"pizza #{r['numero_menu']} {r['formato']}" for r in righe_fallite)
            payment_intent_id = getattr(sessione, "payment_intent", None)
            try:
                if not payment_intent_id:
                    raise RuntimeError("payment_intent assente nella sessione Stripe")
                await stripe_client.rimborsa_pagamento(payment_intent_id, importo_da_rimborsare)
                note = f"Rimborso parziale eseguito ({importo_da_rimborsare/100:.2f} EUR) per: {descrizione}"
            except Exception as e:
                note = f"ATTENZIONE: rimborso parziale FALLITO per {descrizione} — verificare a mano. Errore: {e}"

        await client.patch(
            f"{cfg['url']}/rest/v1/checkout_pendenti", headers=headers,
            params={"id": f"eq.{checkout['id']}"},
            json={"stato": "pagato", "ordini_creati": risultati, "note": note},
        )
        await _aggiorna_fedelta(client, headers, cfg["url"], checkout["telefono_cliente"])

    return {"ok": True}


@router.get("/api/stripe/diagnostica")
async def diagnostica_stripe():
    return {
        "STRIPE_SECRET_KEY_impostata": bool(os.environ.get("STRIPE_SECRET_KEY")),
        "STRIPE_WEBHOOK_SECRET_impostata": bool(os.environ.get("STRIPE_WEBHOOK_SECRET")),
    }
