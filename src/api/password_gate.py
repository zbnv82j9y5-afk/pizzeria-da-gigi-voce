"""
Password di cantiere per GigiAI (assistente vocale) — stessa logica gia'
usata per il sito ordini (vedi sito-online/serve.py). Serve a evitare che
chiunque trovi il link possa avviare conversazioni: ogni conversazione
consuma credito VERO sull'API Realtime di OpenAI (a pagamento), quindi un
accesso pubblico senza controllo sarebbe un rischio economico concreto.

NON e' un vero login per-utente (nessun account, nessun PIN personale):
e' una password condivisa, pensata solo per tenere fuori i curiosi mentre
il progetto e' in prova. Cambiala impostando la variabile d'ambiente
GIGIAI_PASSWORD su Render — senza quella variabile viene usata la password
di default qui sotto.
"""
import hashlib
import hmac
import html as html_lib
import os

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

GIGIAI_PASSWORD = os.environ.get("GIGIAI_PASSWORD", "DaGigi2026!")
COOKIE_ACCESSO = "accesso_gigiai"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 giorni

# Percorsi raggiungibili SENZA password: quelli del gate stesso, piu'
# /health (usato solo per i controlli automatici del server di hosting,
# non fa parlare l'assistente quindi non consuma credito OpenAI).
PERCORSI_LIBERI = {"/password", "/entra-password", "/health"}


def _token_atteso() -> str:
    return hashlib.sha256(GIGIAI_PASSWORD.encode()).hexdigest()


def _accesso_valido(request: Request) -> bool:
    cookie = request.cookies.get(COOKIE_ACCESSO, "")
    return hmac.compare_digest(cookie, _token_atteso())


PAGINA_PASSWORD_TEMPLATE = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Accesso — GigiAI</title>
<style>
  body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background:#faf6f0;
          display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; padding:16px; }}
  .box {{ background:#fff; border-radius:18px; padding:30px 26px; max-width:340px; width:100%;
          box-shadow:0 10px 30px rgba(51,34,20,0.12); text-align:center; box-sizing:border-box; }}
  h1 {{ font-size:1.4em; color:#c0392b; margin:0 0 8px; }}
  p {{ color:#6b6459; font-size:.88em; margin:0 0 18px; line-height:1.4; }}
  input[type=password] {{ width:100%; padding:13px 14px; border:1.5px solid rgba(51,51,51,0.16); border-radius:12px;
                           font-size:1em; box-sizing:border-box; margin-bottom:14px; }}
  button {{ width:100%; padding:14px; border:none; border-radius:12px; background:#c0392b; color:#fff;
            font-weight:800; font-size:1em; cursor:pointer; }}
  button:active {{ opacity:.85; }}
  .errore {{ color:#c0392b; font-size:.84em; margin:-8px 0 14px; font-weight:700; }}
</style>
</head>
<body>
  <div class="box">
    <h1>🎙️ GigiAI</h1>
    <p>L'assistente vocale e' ancora in fase di prova.<br>Inserisci la password per continuare.</p>
    {errore_html}
    <form method="POST" action="/entra-password">
      <input type="hidden" name="next" value="{next_path}">
      <input type="password" name="password" placeholder="Password" autofocus required>
      <button type="submit">Continua</button>
    </form>
  </div>
</body>
</html>"""


def _pagina_password(next_path: str, errore: bool = False) -> str:
    next_sicuro = html_lib.escape(next_path or "/", quote=True)
    errore_html = '<p class="errore">Password errata, riprova.</p>' if errore else ""
    return PAGINA_PASSWORD_TEMPLATE.format(errore_html=errore_html, next_path=next_sicuro)


def aggiungi_password_gate(app: FastAPI) -> None:
    """Applica il controllo password a tutte le rotte dell'app, tranne
    quelle elencate in PERCORSI_LIBERI. Va chiamata PRIMA di stream.mount()
    e app.include_router(), cosi' il middleware si applica anche alle
    rotte WebRTC (altrimenti chiunque potrebbe avviare una conversazione
    aggirando la pagina di accesso)."""

    @app.middleware("http")
    async def richiedi_password_gigiai(request: Request, call_next):
        path = request.url.path
        if path in PERCORSI_LIBERI or _accesso_valido(request):
            return await call_next(request)
        prossimo = path + (("?" + request.url.query) if request.url.query else "")
        return RedirectResponse(url=f"/password?next={prossimo}", status_code=303)

    @app.get("/password", response_class=HTMLResponse)
    async def pagina_password(next: str = "/"):
        return _pagina_password(next)

    @app.post("/entra-password")
    async def verifica_password(password: str = Form(...), next: str = Form("/")):
        if hmac.compare_digest(password, GIGIAI_PASSWORD):
            risposta = RedirectResponse(url=next or "/", status_code=303)
            risposta.set_cookie(
                COOKIE_ACCESSO, _token_atteso(),
                max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax",
            )
            return risposta
        return HTMLResponse(_pagina_password(next, errore=True), status_code=401)
