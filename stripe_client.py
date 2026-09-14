"""
Client minimale per le API Stripe (Checkout Sessions), basato sulla
documentazione ufficiale: https://docs.stripe.com/api/checkout/sessions e
https://docs.stripe.com/webhooks

A differenza di satispay_client.py, qui si usa la libreria ufficiale
"stripe" (aggiunta a requirements.txt) invece di richieste HTTP scritte a
mano: per Satispay serve una firma RSA personalizzata (nessuna libreria la
fa per noi), mentre per Stripe la libreria ufficiale gestisce sia le
chiamate sia — soprattutto — la verifica della firma dei webhook, che a
mano sarebbe facile sbagliare (e sbagliarla vorrebbe dire fidarsi di
richieste che potrebbero non venire davvero da Stripe).

Finche' STRIPE_SECRET_KEY (e, per i webhook, STRIPE_WEBHOOK_SECRET) non sono
impostate come variabili d'ambiente, le funzioni qui sotto sollevano un
errore chiaro se richiamate — il resto del sito continua a funzionare
normalmente, dato che questo file non viene importato da nessuna parte
tranne stripe_routes.py.
"""
import os

import stripe

# In test mode le chiavi iniziano con "sk_test_"/"whsec_..."; quando si passa
# a pagamenti veri, sul dashboard Stripe si passa alla modalita' "live" e si
# sostituiscono qui le stesse due variabili d'ambiente — nessuna modifica al
# codice.
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")


class StripeNonConfigurato(RuntimeError):
    """Sollevato se si prova a usare questo modulo prima di aver impostato
    STRIPE_SECRET_KEY tra le variabili d'ambiente. Vedi STRIPE-INTEGRAZIONE.md
    per come ottenerla."""
    pass


def _verifica_configurato():
    if not STRIPE_SECRET_KEY:
        raise StripeNonConfigurato(
            "Il pagamento con carta non e' ancora configurato: manca "
            "STRIPE_SECRET_KEY tra le variabili d'ambiente. Vedi "
            "STRIPE-INTEGRAZIONE.md per come ottenerla."
        )


async def crea_sessione_checkout(importo_centesimi: int, checkout_id: str, success_url: str, cancel_url: str) -> dict:
    """Crea una Stripe Checkout Session in modalita' 'payment' (pagamento
    singolo, non abbonamento). Una sola riga con il totale gia' calcolato
    server-side (stessa logica di satispay_client.crea_pagamento, mai dal
    browser): il cliente vede una pagina ospitata da Stripe dove inserisce i
    dati della carta — Pizzeria Da Gigi non vede né salva mai il numero di
    carta, e non deve occuparsene per la sicurezza (PCI compliance)."""
    _verifica_configurato()
    return await stripe.checkout.Session.create_async(
        api_key=STRIPE_SECRET_KEY,
        mode="payment",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {"name": "Ordine Pizzeria Da Gigi"},
                "unit_amount": importo_centesimi,
            },
            "quantity": 1,
        }],
        client_reference_id=checkout_id,
        metadata={"checkout_id": checkout_id},
        success_url=success_url,
        cancel_url=cancel_url,
    )


async def rimborsa_pagamento(payment_intent_id: str, importo_centesimi: int) -> dict:
    """Usato solo nel caso raro in cui il cliente ha gia' pagato ma una
    pizza del carrello e' risultata esaurita nel frattempo (stessa logica di
    satispay_client.rimborsa_pagamento)."""
    _verifica_configurato()
    return await stripe.Refund.create_async(
        api_key=STRIPE_SECRET_KEY,
        payment_intent=payment_intent_id,
        amount=importo_centesimi,
    )


def leggi_evento_webhook(payload: bytes, firma_header: str) -> stripe.Event:
    """Verifica che la richiesta arrivi davvero da Stripe (firma HMAC del
    corpo della richiesta) e restituisce l'evento decodificato. Solleva
    stripe.SignatureVerificationError se la firma non torna — in quel caso
    il chiamante (stripe_routes.py) deve rispondere 400 e NON fidarsi per
    nessun motivo del contenuto della richiesta."""
    if not STRIPE_WEBHOOK_SECRET:
        raise StripeNonConfigurato(
            "Webhook Stripe non configurato: manca STRIPE_WEBHOOK_SECRET tra "
            "le variabili d'ambiente."
        )
    return stripe.Webhook.construct_event(payload, firma_header, STRIPE_WEBHOOK_SECRET)
