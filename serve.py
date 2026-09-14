import hashlib
import hmac
import html as html_lib
import os
import socket

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from pizzeria_ordini import router as ordini_router
from satispay_routes import router as satispay_router
from stripe_routes import router as stripe_router

app = FastAPI()

# Sistema ordini: verifica davvero la disponibilita' e scala il magazzino su
# Supabase quando un cliente conferma l'ordine (se il database e' collegato
# — vedi static/js/supabase-config.js). Se non e' ancora collegato, o non
# risponde, l'ordine passa comunque: nessun rischio per i clienti durante
# la configurazione.
app.include_router(ordini_router)
app.include_router(satispay_router)
app.include_router(stripe_router)

# Percorsi delle cartelle
BASE_DIR = os.path.dirname(__file__)
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# ============================================================================
# PASSWORD DI CANTIERE — il sito è ancora in costruzione/valutazione, non
# ancora pronto per i clienti veri. La prima schermata (home) resta sempre
# visibile a chiunque (è la "vetrina" da far vedere), ma per andare oltre
# (menu, ordine, dashboard staff, ecc.) serve una password condivisa.
#
# NON è una vera autenticazione per-utente (niente account, niente PIN
# personali) — serve solo a tenere fuori i curiosi mentre il sito è in
# lavorazione. Cambia la password quando vuoi impostando la variabile
# d'ambiente DEMO_PASSWORD su Render (Settings → Environment) — senza
# quella variabile viene usata la password di default qui sotto.
# ============================================================================
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "DaGigi2026!")
COOKIE_ACCESSO = "accesso_cantiere"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 giorni: una volta inserita, non la richiede più per un mese

# Pagine raggiungibili SENZA password: solo quelle del gate stesso (altrimenti
# nessuno riuscirebbe mai ad autenticarsi). Tutto il resto — home compresa,
# menu, riepilogo/ordine, assistente, dashboard staff — richiede la password.
PERCORSI_LIBERI = {"/password", "/entra-password", "/api/satispay/callback", "/api/stripe/webhook"}


def _token_atteso() -> str:
    return hashlib.sha256(DEMO_PASSWORD.encode()).hexdigest()


def _accesso_valido(request: Request) -> bool:
    cookie = request.cookies.get(COOKIE_ACCESSO, "")
    return hmac.compare_digest(cookie, _token_atteso())


PAGINA_PASSWORD_TEMPLATE = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Accesso — Pizzeria da Gigi</title>
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
    <h1>🍕 Da Gigi</h1>
    <p>Il sito è ancora in fase di realizzazione.<br>Inserisci la password per continuare.</p>
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


@app.middleware("http")
async def richiedi_password_cantiere(request: Request, call_next):
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
    if hmac.compare_digest(password, DEMO_PASSWORD):
        risposta = RedirectResponse(url=next or "/", status_code=303)
        risposta.set_cookie(
            COOKIE_ACCESSO, _token_atteso(),
            max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax",
        )
        return risposta
    return HTMLResponse(_pagina_password(next, errore=True), status_code=401)


# Monta le cartelle statiche
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/templates", StaticFiles(directory=TEMPLATES_DIR), name="templates")

# Dashboard staff (magazzino/stato del giorno) — pagina separata, collegata
# direttamente a Supabase dal browser (vedi dashboard-staff/config.js).
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard-staff")
if os.path.isdir(DASHBOARD_DIR):
    app.mount("/dashboard-staff", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard-staff")

# Lista dei file HTML disponibili
HTML_FILES = [
    "index.html",
    "index_pizzeria.html",
    "menu.html",
    "assistente.html",
    "riepilogo.html"
]

def serve_html(filename: str):
    """Cerca il file in templates/ e static/"""
    for directory in [TEMPLATES_DIR, STATIC_DIR]:
        file_path = os.path.join(directory, filename)
        if os.path.exists(file_path):
            return FileResponse(file_path)
    return {"error": f"File {filename} non trovato"}

# Route per la home
@app.get("/")
async def serve_root():
    # La home a schermo singolo (2 bottoni: Ordina a Voce / Menu Pizze)
    return serve_html("index_pizzeria.html")

@app.get("/index.html")
async def serve_index():
    return serve_html("index.html")

@app.get("/index_pizzeria.html")
async def serve_index_pizzeria():
    return serve_html("index_pizzeria.html")

@app.get("/menu.html")
async def serve_menu():
    return serve_html("menu.html")

@app.get("/assistente.html")
async def serve_assistente():
    return serve_html("assistente.html")

@app.get("/riepilogo.html")
async def serve_riepilogo():
    return serve_html("riepilogo.html")

# Fallback: se l'URL non corrisponde, prova a servire come file HTML
@app.get("/{filename}")
async def serve_any(filename: str):
    if filename.endswith(".html"):
        return serve_html(filename)
    return {"error": f"File {filename} non trovato"}

def get_local_ip():
    """Indirizzo di questo computer sulla rete Wi-Fi/LAN locale, per aprire
    il sito da telefono o tablet mentre sono collegati alla STESSA rete."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    import uvicorn
    local_ip = get_local_ip()
    print("🍕 Pizzeria da Gigi - Server")
    print("📁 Cerca file in:")
    print(f"   - {TEMPLATES_DIR}")
    print(f"   - {STATIC_DIR}")
    print("\n🌐 Da QUESTO computer:")
    print("   http://127.0.0.1:8000/")
    print("   http://127.0.0.1:8000/index.html")
    print("   http://127.0.0.1:8000/index_pizzeria.html")
    print("   http://127.0.0.1:8000/menu.html")
    print("   http://127.0.0.1:8000/assistente.html")
    print("   http://127.0.0.1:8000/riepilogo.html")
    print("   http://127.0.0.1:8000/dashboard-staff/  (dashboard staff)")
    print("\n📱 Da TELEFONO o TABLET, sulla STESSA rete Wi-Fi di questo computer:")
    print(f"   http://{local_ip}:8000/dashboard-staff/")
    print(f"   http://{local_ip}:8000/menu.html")
    print("   (se il Mac chiede il permesso di accettare connessioni in arrivo, scegli \"Consenti\")")
    print("\n🚀 Avvio server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
