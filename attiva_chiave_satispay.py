"""
Script da lanciare UNA SOLA VOLTA (a mano, dal Terminale: `python3
attiva_chiave_satispay.py`), quando arriva l'email con l'activation code
della Sandbox Satispay. Registra la chiave pubblica già generata in
satispay_keys/ e ottiene il key_id da salvare come variabile d'ambiente.

Prima di lanciarlo, incolla l'activation code ricevuto via email al posto
di "INCOLLA_QUI_ACTIVATION_CODE" qui sotto.
"""
import requests

ACTIVATION_CODE = "INCOLLA_QUI_ACTIVATION_CODE"

with open("satispay_keys/satispay_public_sandbox.pem") as f:
    public_key_pem = f.read()

risposta = requests.post(
    "https://staging.authservices.satispay.com/g_business/v1/authentication_keys",
    json={"public_key": public_key_pem, "token": ACTIVATION_CODE},
)
risposta.raise_for_status()
dati = risposta.json()
print("\nAttivazione riuscita! Il tuo key_id è:\n")
print("  ", dati["key_id"])
print("\nSalvalo come variabile d'ambiente SATISPAY_KEY_ID su Render (e anche")
print("in un file .env locale se vuoi testare da qui). Vedi anche il contenuto")
print("di satispay_keys/satispay_private_sandbox.pem: quello va salvato come")
print("variabile d'ambiente SATISPAY_PRIVATE_KEY (mai committato su Git).")
