"""
pizzeria_pwa.py — rende la Pizzeria Da Gigi "installabile" (icone sulla Home).

DUE app distinte, ognuna con la sua icona sul telefono:

  Clienti     /                      (sito pubblico: home, menu, riepilogo)
  Staff       /staff/accesso/        -> dashboard staff, pulsantiera del PIN
                                        (Pizzaiolo o Admin si sceglie li')

Indirizzi aggiunti a serve.py:
  /manifest.webmanifest              manifest app Clienti
  /sw.js                             service worker unico (radice del sito)
  /favicon.ico                       icona 32px
  /staff/                            porta direttamente a /staff/accesso/
  /staff/<ruolo>/                    la dashboard (dashboard-staff/index.html)
                                     con in più i tag dell'app di quel ruolo
  /staff/<ruolo>/manifest.webmanifest

La dashboard originale NON viene modificata: i tag PWA vengono aggiunti al
volo solo quando la si apre da /staff/<ruolo>/. All'indirizzo di sempre,
/dashboard-staff/, resta identica a prima. Il PIN resta sempre obbligatorio.

Collegamento in serve.py (lo fa da solo applica_pwa.py):
    from pizzeria_pwa import router as pwa_router
    app.include_router(pwa_router)
da mettere SUBITO DOPO la riga `app = FastAPI(...)`, prima delle altre rotte.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

BASE_DIR = Path(__file__).resolve().parent
PWA_DIR = BASE_DIR / "static" / "pwa"
DASHBOARD_FILE = BASE_DIR / "dashboard-staff" / "index.html"
DASHBOARD_URL = "/dashboard-staff/"
ICONS = "/static/pwa/icons"

router = APIRouter()

# Il browser deve sempre ricontrollare manifest, service worker e pagine staff,
# altrimenti una modifica futura resterebbe "incastrata" sui telefoni.
NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}

# ---------------------------------------------------------------- app Clienti

def _file(name: str, media_type: str, extra_headers: dict | None = None) -> Response:
    path = PWA_DIR / name
    if not path.is_file():
        return Response(f"{name} non trovato in static/pwa/", status_code=404)
    headers = dict(NO_CACHE)
    if extra_headers:
        headers.update(extra_headers)
    return FileResponse(path, media_type=media_type, headers=headers)


@router.get("/manifest.webmanifest", include_in_schema=False)
async def pwa_manifest():
    return _file("manifest.webmanifest", "application/manifest+json")


@router.get("/sw.js", include_in_schema=False)
async def pwa_service_worker():
    return _file("sw.js", "application/javascript", {"Service-Worker-Allowed": "/"})


@router.get("/favicon.ico", include_in_schema=False)
async def pwa_favicon():
    path = PWA_DIR / "icons" / "favicon-32.png"
    if not path.is_file():
        return Response(status_code=404)
    return FileResponse(path, media_type="image/png")

# ------------------------------------------------------- app staff (2 ruoli)
# Per cambiare il nome che compare sotto l'icona, modifica "short_name"
# (Android) e "titolo_ios" (iPhone): massimo ~12 caratteri.
RUOLI = {
    # App unica da mettere sulla Home: apre la pulsantiera del PIN e il ruolo
    # (Pizzaiolo o Admin) si sceglie li', come dal browser.
    "accesso": {
        "name": "Da Gigi · Staff",
        "short_name": "Staff Gigi",
        "titolo_ios": "Staff Gigi",
        "theme": "#333333",
        "descr": "Pizzaiolo o Admin: scegli il ruolo all'accesso",
        "emoji": "👨‍🍳🔑",
        "preseleziona": False,
    },
}


def _manifest_staff(ruolo: str) -> dict:
    r = RUOLI[ruolo]
    base = f"/staff/{ruolo}/"
    ic = f"{ICONS}/staff-{ruolo}"
    return {
        "id": base,
        "name": r["name"],
        "short_name": r["short_name"],
        "description": f"Area riservata Pizzeria Da Gigi — {r['descr']}",
        "lang": "it",
        "start_url": base + "?source=homescreen",
        "scope": base,
        "display": "standalone",
        "orientation": "any",          # va bene anche su tablet in orizzontale
        "background_color": "#faf6f0",
        "theme_color": r["theme"],
        "icons": [
            {"src": f"{ic}-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": f"{ic}-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": f"{ic}-maskable-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": f"{ic}-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }


def _head_staff(ruolo: str) -> str:
    r = RUOLI[ruolo]
    ic = f"{ICONS}/staff-{ruolo}"
    nome = r["titolo_ios"]
    return (
        "<!-- PWA Da Gigi staff: inizio -->\n"
        f'<link rel="manifest" href="/staff/{ruolo}/manifest.webmanifest">\n'
        f'<meta name="theme-color" content="{r["theme"]}">\n'
        '<meta name="mobile-web-app-capable" content="yes">\n'
        '<meta name="apple-mobile-web-app-capable" content="yes">\n'
        '<meta name="apple-mobile-web-app-status-bar-style" content="default">\n'
        f'<meta name="apple-mobile-web-app-title" content="{nome}">\n'
        f'<meta name="application-name" content="{nome}">\n'
        '<meta name="robots" content="noindex,nofollow">\n'
        f'<link rel="apple-touch-icon" sizes="180x180" href="{ic}-apple-touch-icon.png">\n'
        f'<link rel="icon" type="image/png" sizes="192x192" href="{ic}-192.png">\n'
        f'<script src="/static/pwa/pwa-install.js" defer data-chiave="{ruolo}" '
        f'data-nome="{nome}" data-icona="{ic}-192.png" '
        f'data-titolo="Aggiungi l\'app {nome} alla Home" '
        'data-sottotitolo="Apri la tua area riservata con un tocco." '
        'data-sottotitolo-guida="Un\'icona per entrare subito nella tua area."></script>\n'
        + (f'<script src="/static/pwa/pwa-staff.js" defer data-ruolo="{ruolo}"></script>\n'
           if r.get("preseleziona") else "")
        + "<!-- PWA Da Gigi staff: fine -->\n"
    )


# Tag che, se un giorno finissero dentro la dashboard, farebbero confusione
# con quelli dell'app di ruolo: li togliamo solo dalla copia servita qui.
_RIMUOVI = re.compile(
    r'<link[^>]+rel=["\'](?:manifest|apple-touch-icon)["\'][^>]*>\s*'
    r'|<meta[^>]+name=["\'](?:theme-color|apple-mobile-web-app-title|application-name)["\'][^>]*>\s*',
    re.IGNORECASE,
)
# Risorse con indirizzo relativo (es. src="app.js") vanno ancora cercate in
# /dashboard-staff/, visto che la pagina ora è servita da /staff/<ruolo>/.
_RELATIVI = re.compile(
    r'(<(?:script|img|link|source|audio|video)\b[^>]*?\b(?:src|href)=["\'])'
    r'(?![a-zA-Z][a-zA-Z0-9+.-]*:|/|#)([^"\']+)',
    re.IGNORECASE,
)


@router.get("/staff", include_in_schema=False)
async def staff_redirect():
    return RedirectResponse("/staff/", status_code=307)


@router.get("/staff/", include_in_schema=False)
async def staff_index():
    # Un'unica app staff: si va dritti alla pulsantiera del PIN, dove si
    # sceglie Pizzaiolo o Admin. Da li' compare anche "Aggiungi alla Home".
    return RedirectResponse("/staff/accesso/", status_code=307)


@router.get("/staff/{ruolo}", include_in_schema=False)
async def staff_ruolo_redirect(ruolo: str):
    if ruolo not in RUOLI:
        return Response(status_code=404)
    return RedirectResponse(f"/staff/{ruolo}/", status_code=307)


@router.get("/staff/{ruolo}/manifest.webmanifest", include_in_schema=False)
async def staff_manifest(ruolo: str):
    if ruolo not in RUOLI:
        return Response(status_code=404)
    return Response(
        json.dumps(_manifest_staff(ruolo), ensure_ascii=False, indent=2),
        media_type="application/manifest+json",
        headers=NO_CACHE,
    )


@router.get("/staff/{ruolo}/", include_in_schema=False)
async def staff_dashboard(ruolo: str):
    if ruolo not in RUOLI:
        return Response(status_code=404)
    if not DASHBOARD_FILE.is_file():
        # Nessuna dashboard trovata: meglio portare dove si trova di solito.
        return RedirectResponse(DASHBOARD_URL, status_code=307)
    html = DASHBOARD_FILE.read_text(encoding="utf-8")
    html = _RIMUOVI.sub("", html)
    html = _RELATIVI.sub(lambda m: m.group(1) + DASHBOARD_URL + m.group(2), html)
    blocco = _head_staff(ruolo)
    m = re.search(r"</head\s*>", html, re.IGNORECASE)
    html = html[: m.start()] + blocco + html[m.start():] if m else blocco + html
    return HTMLResponse(html, headers=NO_CACHE)
