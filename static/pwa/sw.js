/*
 * Service worker MINIMO per la Pizzeria Da Gigi.
 *
 * Serve solo a rendere l'app "installabile" (alias sulla Home).
 * NON mette in cache menu, prezzi, ordini o dati Supabase: tutto passa
 * sempre dalla rete, quindi il comportamento del sito resta identico.
 *
 * L'unica cosa che fa in più: se il telefono è senza connessione e si apre
 * l'app dall'icona, mostra una pagina "Sei offline" invece della schermata
 * di errore del browser.
 *
 * Viene servito su /sw.js (dalla radice del sito) da pizzeria_pwa.py,
 * così il suo raggio d'azione copre tutte le pagine.
 */
const VERSION = 'dagigi-sw-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

const OFFLINE_HTML = `<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#c0392b">
<title>Da Gigi – offline</title>
<style>
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
       background:#faf6f0;color:#333;font-family:-apple-system,system-ui,sans-serif;text-align:center;padding:24px}
  h1{color:#c0392b;font-size:30px;margin:0 0 8px}
  p{color:#6b6459;margin:0 0 22px;line-height:1.45}
  button{background:#1e8449;color:#fff;border:0;border-radius:12px;padding:14px 26px;font-size:16px;font-weight:700}
</style></head>
<body><div>
  <div style="font-size:54px">🍕</div>
  <h1>Sei offline</h1>
  <p>Non riusciamo a raggiungere la Pizzeria Da Gigi.<br>Controlla la connessione e riprova.</p>
  <button onclick="location.reload()">Riprova</button>
</div></body></html>`;

self.addEventListener('fetch', (event) => {
  const req = event.request;
  // Interveniamo SOLO sull'apertura delle pagine; API, Supabase, immagini,
  // script ecc. vanno dritti in rete senza passare da qui.
  if (req.mode !== 'navigate') return;
  event.respondWith(
    fetch(req).catch(() =>
      new Response(OFFLINE_HTML, {
        status: 503,
        headers: { 'Content-Type': 'text/html; charset=utf-8' },
      })
    )
  );
});
