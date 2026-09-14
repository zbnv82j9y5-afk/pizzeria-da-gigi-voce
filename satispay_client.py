"""
Client minimale per le API Satispay (Online/G-Business), basato sulla
documentazione ufficiale: https://developers.satispay.com/reference/introduction

NON ANCORA COLLEGATO al resto del sito (nessun altro file lo importa): è
pronto per quando arriveranno le credenziali sandbox. Finché le variabili
d'ambiente SATISPAY_KEY_ID / SATISPAY_PRIVATE_KEY non sono impostate, le
funzioni qui sotto sollevano un errore chiaro se richiamate — ma il resto
del sito continua a funzionare normalmente, dato che questo file non viene
importato da nessuna parte per ora.

Usa httpx (asincrono), come il resto del backend (vedi pizzeria_ordini.py),
invece di aggiungere una libreria nuova solo per questo. L'unica dipendenza
davvero nuova è "cryptography", necessaria per firmare le richieste con la
chiave privata RSA (aggiunta a requirements.txt).
"""
import os
import base64
import hashlib
import json
from datetime import datetime, timezone
from email.utils import format_datetime

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# In sandbox: "staging.authservices.satispay.com". In produzione (più avanti,
# quando si passa live): "authservices.satispay.com" — si cambia solo questa
# variabile d'ambiente su Render, nessuna modifica al codice.
SATISPAY_BASE_URL = os.environ.get("SATISPAY_BASE_URL", "staging.authservices.satispay.com")
SATISPAY_KEY_ID = os.environ.get("SATISPAY_KEY_ID")  # None finché non fatta l'attivazione (vedi attiva_chiave_satispay.py)
SATISPAY_PRIVATE_KEY_PEM = os.environ.get("SATISPAY_PRIVATE_KEY")


class SatispayNonConfigurato(RuntimeError):
    """Sollevato se si prova a usare questo modulo prima di aver impostato
    SATISPAY_KEY_ID e SATISPAY_PRIVATE_KEY come variabili d'ambiente."""
    pass


def _verifica_configurato():
    if not SATISPAY_KEY_ID or not SATISPAY_PRIVATE_KEY_PEM:
        raise SatispayNonConfigurato(
            "Satispay non è ancora configurato: mancano SATISPAY_KEY_ID e/o "
            "SATISPAY_PRIVATE_KEY tra le variabili d'ambiente. Vedi "
            "SATISPAY-INTEGRAZIONE.md, sezione 5.1.1, per come ottenerle."
        )


def _load_private_key():
    return serialization.load_pem_private_key(
        SATISPAY_PRIVATE_KEY_PEM.encode(), password=None
    )


def _firma_richiesta(method: str, path: str, body_bytes: bytes) -> dict:
    """Costruisce gli header firmati richiesti da ogni chiamata autenticata.
    Segue esattamente lo schema documentato da Satispay: (request-target) +
    host + date + digest, firmati con RSA-SHA256 e codificati in Base64."""
    host = SATISPAY_BASE_URL
    date = format_datetime(datetime.now(timezone.utc), usegmt=True)
    digest = "SHA-256=" + base64.b64encode(hashlib.sha256(body_bytes).digest()).decode()

    stringa_da_firmare = (
        f"(request-target): {method.lower()} {path}\n"
        f"host: {host}\n"
        f"date: {date}\n"
        f"digest: {digest}"
    )

    firma = _load_private_key().sign(
        stringa_da_firmare.encode(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    firma_b64 = base64.b64encode(firma).decode()

    authorization = (
        f'Signature keyId="{SATISPAY_KEY_ID}", algorithm="rsa-sha256", '
        f'headers="(request-target) host date digest", signature="{firma_b64}"'
    )

    return {
        "Host": host,
        "Date": date,
        "Digest": digest,
        "Authorization": authorization,
        "Content-Type": "application/json",
    }


async def _post(path: str, payload: dict) -> dict:
    _verifica_configurato()
    body = json.dumps(payload).encode()
    headers = _firma_richiesta("post", path, body)
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(f"https://{SATISPAY_BASE_URL}{path}", content=body, headers=headers)
    r.raise_for_status()
    return r.json()


async def _get(path: str) -> dict:
    _verifica_configurato()
    headers = _firma_richiesta("get", path, b"")
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"https://{SATISPAY_BASE_URL}{path}", headers=headers)
    r.raise_for_status()
    return r.json()


async def crea_pagamento(importo_centesimi: int, checkout_id: str, callback_base_url: str) -> dict:
    """flow=MATCH_CODE è quello usato per il flusso e-commerce "One-off -
    Web-redirect / Web-button" (non è solo per i pagamenti in negozio,
    nonostante il nome)."""
    payload = {
        "flow": "MATCH_CODE",
        "amount_unit": importo_centesimi,
        "currency": "EUR",
        "external_code": checkout_id,  # per ritrovare il nostro checkout dai log Satispay
        "callback_url": f"{callback_base_url}?payment_id={{uuid}}",
        "redirect_url": f"{callback_base_url.rsplit('/api', 1)[0]}/riepilogo.html?checkout_id={checkout_id}",
    }
    return await _post("/g_business/v1/payments", payload)


async def stato_pagamento(payment_id: str) -> dict:
    return await _get(f"/g_business/v1/payments/{payment_id}")


async def rimborsa_pagamento(payment_id_originale: str, importo_centesimi: int) -> dict:
    payload = {
        "flow": "REFUND",
        "parent_payment_uid": payment_id_originale,
        "amount_unit": importo_centesimi,
        "currency": "EUR",
    }
    return await _post("/g_business/v1/payments", payload)
