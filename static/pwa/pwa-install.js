/*
 * pwa-install.js — "Aggiungi Da Gigi alla Home"
 *
 * Cosa fa, da solo, appena incluso in una pagina:
 *  1. registra il service worker minimo (/sw.js) quando il browser lo permette;
 *  2. Android/Chrome/Edge/Samsung: intercetta `beforeinstallprompt`, lo tiene
 *     da parte e mostra il banner "Crea alias"; al tocco apre il vero prompt
 *     di installazione del sistema e gestisce la risposta;
 *  3. iPhone/iPad (dove quell'evento non esiste): mostra un banner con la
 *     guida passo-passo "Condividi > Aggiungi alla schermata Home";
 *  4. Android senza prompt automatico (es. sito ancora su http in Wi-Fi):
 *     mostra la guida manuale "⋮ > Aggiungi a schermata Home";
 *  5. non mostra NIENTE se l'app è già aperta dall'icona (modalità standalone),
 *     se è già stata installata, o se il cliente ha chiuso il banner di recente.
 *
 * Nessun alert()/confirm()/prompt() nativo: tutta l'interfaccia è nella pagina.
 * Se qualcosa va storto (browser vecchio, localStorage bloccato…) il sito
 * continua a funzionare esattamente come prima: il banner semplicemente non c'è.
 *
 * Opzioni (attributi sul tag <script>):
 *   data-delay="2500"   ms di attesa prima di mostrare il banner (default 2500)
 *   data-banner="off"   non mostrare il banner automatico (resta usabile
 *                       un pulsante tuo con l'attributo data-pwa-install)
 *   data-chiave, data-titolo, data-sottotitolo, data-sottotitolo-guida,
 *   data-nome, data-icona   testi/icona del banner e memoria separata
 *                       (usati dalle app staff Pizzaiolo e Admin)
 *
 * Pulsante personalizzato: qualunque elemento con `data-pwa-install` diventa
 * visibile solo quando l'alias si può creare e, al tocco, avvia la procedura.
 * Da codice: window.DaGigiPWA.install()
 */
(function () {
  'use strict';
  if (window.__daGigiPWA) return;
  window.__daGigiPWA = true;

  var script = document.currentScript;
  var DELAY = parseInt((script && script.getAttribute('data-delay')) || '2500', 10);
  var AUTO_BANNER = !script || script.getAttribute('data-banner') !== 'off';
  function attr(name, def) { var v = script && script.getAttribute(name); return v ? v : def; }
  // Personalizzazione per le app staff (Pizzaiolo / Admin):
  var APP_KEY = attr('data-chiave', 'clienti');
  var TITLE = attr('data-titolo', 'Aggiungi Da Gigi alla Home');
  var SUB_PROMPT = attr('data-sottotitolo', 'Apri menu e ordini con un tocco, come un’app.');
  var SUB_GUIDE = attr('data-sottotitolo-guida', 'Un’icona sul telefono per ordinare al volo.');
  var APP_NAME = attr('data-nome', 'Da Gigi');
  var SNOOZE_KEY = 'dagigi_pwa_snooze_until' + (APP_KEY === 'clienti' ? '' : '_' + APP_KEY);
  var INSTALLED_KEY = 'dagigi_pwa_installed' + (APP_KEY === 'clienti' ? '' : '_' + APP_KEY);
  var SNOOZE_DAYS_CLOSE = 7;    // "×" sul banner
  var SNOOZE_DAYS_DECLINE = 3;  // "Annulla" nel prompt di sistema

  // ---------- utilità sicure ----------
  function lsGet(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { window.localStorage.setItem(k, v); } catch (e) {} }

  var ua = navigator.userAgent || '';
  var isIOS = /iPad|iPhone|iPod/.test(ua) ||
              (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  var isAndroid = /Android/i.test(ua);
  var isInAppBrowser = /FBAN|FBAV|Instagram|Line\/|MicroMessenger|TikTok|Snapchat/i.test(ua);
  var iosBrowser = /CriOS/.test(ua) ? 'chrome' : /FxiOS/.test(ua) ? 'firefox' :
                   /EdgiOS/.test(ua) ? 'edge' : 'safari';

  function isStandalone() {
    return (window.matchMedia && (
              window.matchMedia('(display-mode: standalone)').matches ||
              window.matchMedia('(display-mode: minimal-ui)').matches ||
              window.matchMedia('(display-mode: fullscreen)').matches)) ||
           window.navigator.standalone === true;
  }
  function isSnoozed() {
    var until = parseInt(lsGet(SNOOZE_KEY) || '0', 10);
    return until && Date.now() < until;
  }
  function snooze(days) { lsSet(SNOOZE_KEY, String(Date.now() + days * 864e5)); }

  // ---------- 1. service worker ----------
  // Funziona solo in "contesto sicuro" (https:// oppure localhost).
  // Su http://192.168.x.x il browser lo rifiuta: lì si usa la guida manuale.
  if ('serviceWorker' in navigator && window.isSecureContext) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function (err) {
        if (window.console) console.warn('[Da Gigi] service worker non registrato:', err);
      });
    });
  }

  // ---------- app aperta dall'icona: spazio per orologio/notch ----------
  // Su iPhone, nell'app installata la pagina arriva fino al bordo superiore e
  // il contenuto scorre sotto l'orologio. Qui (SOLO in modalità app) si
  // aggiunge una fascia color crema alta quanto la barra di stato, si sposta
  // giù il contenuto della stessa misura e si abbassano le intestazioni
  // "sticky". Nel browser normale non cambia nulla.
  function spazioBarraDiStato() {
    try {
      var vp = document.querySelector('meta[name="viewport"]');
      if (vp && !/viewport-fit/.test(vp.content)) vp.content += ', viewport-fit=cover';
      var top = 'env(safe-area-inset-top, 0px)';
      var st = document.createElement('style');
      st.id = 'dg-pwa-safe';
      st.textContent =
        '#dg-safe-spacer{height:' + top + ';flex:0 0 auto;}' +
        '#dg-safe-cover{position:fixed;top:0;left:0;right:0;height:' + top + ';' +
        'background:var(--cream,#faf6f0);z-index:2147482999;pointer-events:none;}';
      (document.head || document.documentElement).appendChild(st);
      var applica = function () {
        if (!document.body || document.getElementById('dg-safe-cover')) return;
        var cover = document.createElement('div'); cover.id = 'dg-safe-cover';
        var sp = document.createElement('div'); sp.id = 'dg-safe-spacer';
        sp.setAttribute('aria-hidden', 'true'); cover.setAttribute('aria-hidden', 'true');
        document.body.insertBefore(sp, document.body.firstChild);
        document.body.appendChild(cover);
        // Intestazioni che restano attaccate in alto: le mettiamo sotto la fascia.
        var all = document.body.querySelectorAll('*');
        for (var i = 0; i < all.length; i++) {
          var cs = window.getComputedStyle(all[i]);
          if ((cs.position === 'sticky' || cs.position === 'fixed') && cs.top === '0px' &&
              all[i].id !== 'dg-safe-cover') {
            all[i].style.top = top;
          }
        }
      };
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', applica);
      else applica();
    } catch (e) { /* in caso di problemi resta tutto com'era */ }
  }

  // Già aperta dall'icona: segniamolo e non mostriamo mai il banner.
  if (isStandalone()) {
    lsSet(INSTALLED_KEY, '1');
    document.documentElement.classList.add('app-standalone');
    spazioBarraDiStato();
    exposeApi(null);
    return;
  }

  // ---------- stile (iniettato, palette trattoria del sito) ----------
  var css = '' +
    '.dg-pwa-banner{position:fixed;left:12px;right:12px;bottom:calc(12px + env(safe-area-inset-bottom,0px));' +
    'z-index:2147483000;max-width:480px;margin:0 auto;background:#fff;color:#333;border-radius:16px;' +
    'box-shadow:0 10px 30px rgba(0,0,0,.18),0 0 0 1px rgba(0,0,0,.04);padding:14px 44px 14px 14px;' +
    'display:flex;align-items:center;gap:12px;font-family:Mulish,-apple-system,system-ui,sans-serif;' +
    'transform:translateY(140%);transition:transform .35s cubic-bezier(.2,.8,.2,1);}' +
    '.dg-pwa-banner.dg-show{transform:translateY(0);}' +
    '.dg-pwa-banner img{width:48px;height:48px;border-radius:12px;flex:0 0 48px;}' +
    '.dg-pwa-txt{flex:1;min-width:0;line-height:1.3;}' +
    '.dg-pwa-txt strong{display:block;font-size:15px;color:#333;}' +
    '.dg-pwa-txt span{display:block;font-size:13px;color:#6b6459;}' +
    '.dg-pwa-cta{flex:0 0 auto;background:#c0392b;color:#fff;border:0;border-radius:12px;' +
    'min-height:44px;padding:0 16px;font:700 14px Mulish,-apple-system,system-ui,sans-serif;cursor:pointer;}' +
    '.dg-pwa-cta:active{background:#a93226;}' +
    '.dg-pwa-x{position:absolute;top:6px;right:6px;width:34px;height:34px;border:0;border-radius:50%;' +
    'background:transparent;color:#6b6459;font-size:22px;line-height:34px;cursor:pointer;}' +
    '.dg-pwa-x:active{background:#f1ece4;}' +
    '.dg-pwa-overlay{position:fixed;inset:0;z-index:2147483001;background:rgba(0,0,0,.45);' +
    'display:flex;align-items:flex-end;justify-content:center;opacity:0;transition:opacity .25s;}' +
    '.dg-pwa-overlay.dg-show{opacity:1;}' +
    '.dg-pwa-sheet{position:relative;width:100%;max-width:480px;background:#faf6f0;color:#333;' +
    'border-radius:20px 20px 0 0;padding:26px 20px calc(22px + env(safe-area-inset-bottom,0px));' +
    'font-family:Mulish,-apple-system,system-ui,sans-serif;transform:translateY(100%);transition:transform .3s;}' +
    '.dg-pwa-overlay.dg-show .dg-pwa-sheet{transform:translateY(0);}' +
    '.dg-pwa-sheet h3{margin:0 0 4px;font-size:20px;color:#c0392b;}' +
    '.dg-pwa-sheet p.dg-sub{margin:0 0 16px;color:#6b6459;font-size:14px;}' +
    '.dg-pwa-steps{list-style:none;margin:0;padding:0;}' +
    '.dg-pwa-steps li{display:flex;align-items:center;gap:12px;background:#fff;border-radius:12px;' +
    'padding:12px;margin-bottom:8px;font-size:15px;line-height:1.35;}' +
    '.dg-pwa-n{flex:0 0 28px;height:28px;border-radius:50%;background:#c0392b;color:#fff;' +
    'font-weight:800;display:flex;align-items:center;justify-content:center;font-size:14px;}' +
    '.dg-pwa-ico{display:inline-flex;vertical-align:middle;width:22px;height:22px;color:#007aff;}' +
    '.dg-pwa-arrow{position:fixed;z-index:2147483002;font-size:34px;color:#fff;' +
    'text-shadow:0 2px 8px rgba(0,0,0,.4);animation:dgBounce 1s infinite;pointer-events:none;}' +
    '@keyframes dgBounce{0%,100%{transform:translateY(0)}50%{transform:translateY(8px)}}' +
    '.dg-pwa-ok{display:block;width:100%;margin-top:8px;min-height:48px;border:0;border-radius:12px;' +
    'background:#1e8449;color:#fff;font:700 16px Mulish,-apple-system,system-ui,sans-serif;cursor:pointer;}' +
    '.dg-pwa-toast{position:fixed;left:50%;bottom:calc(24px + env(safe-area-inset-bottom,0px));' +
    'transform:translateX(-50%);z-index:2147483003;background:#333;color:#fff;padding:12px 18px;' +
    'border-radius:12px;font:600 14px Mulish,-apple-system,system-ui,sans-serif;' +
    'box-shadow:0 6px 20px rgba(0,0,0,.25);}' +
    '[data-pwa-install]{display:none;}' +
    '[data-pwa-install].dg-pwa-available{display:revert;}';
  function injectCss() {
    if (document.getElementById('dg-pwa-css')) return;
    var s = document.createElement('style');
    s.id = 'dg-pwa-css';
    s.textContent = css;
    (document.head || document.documentElement).appendChild(s);
  }

  var ICON = attr('data-icona', '/static/pwa/icons/icon-192.png');
  var SHARE_SVG = '<svg class="dg-pwa-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M12 3v12"/><path d="M8 7l4-4 4 4"/><path d="M5 11v9h14v-9"/></svg>';
  var PLUS_SVG = '<svg class="dg-pwa-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="4"/>' +
    '<path d="M12 8v8M8 12h8"/></svg>';

  // ---------- stato ----------
  var deferredPrompt = null;   // l'evento beforeinstallprompt messo da parte
  var mode = null;             // 'prompt' | 'ios' | 'android-manual'
  var banner = null;

  function setMode(m) {
    mode = m;
    var btns = document.querySelectorAll('[data-pwa-install]');
    for (var i = 0; i < btns.length; i++) {
      btns[i].classList.toggle('dg-pwa-available', !!m);
    }
  }

  // ---------- banner ----------
  function bottomOffset() {
    // Non coprire le barre fisse già presenti (es. #stickyBar del menu).
    var max = 0;
    var ids = ['stickyBar', 'cartQuickLink'];
    for (var i = 0; i < ids.length; i++) {
      var el = document.getElementById(ids[i]);
      if (!el) continue;
      var st = window.getComputedStyle(el);
      if (st.position !== 'fixed' || st.display === 'none' || st.visibility === 'hidden') continue;
      var r = el.getBoundingClientRect();
      if (r.height && r.bottom >= window.innerHeight - 2) max = Math.max(max, window.innerHeight - r.top);
    }
    return max;
  }

  function showBanner() {
    if (!AUTO_BANNER || !mode || banner || isSnoozed()) return;
    injectCss();
    var title = TITLE;
    var sub, cta;
    if (mode === 'prompt') { sub = SUB_PROMPT; cta = 'Crea alias'; }
    else { sub = SUB_GUIDE; cta = 'Come fare'; }

    banner = document.createElement('div');
    banner.className = 'dg-pwa-banner';
    banner.setAttribute('role', 'dialog');
    banner.setAttribute('aria-label', title);
    banner.innerHTML =
      '<img src="' + ICON + '" alt="">' +
      '<div class="dg-pwa-txt"><strong>' + title + '</strong><span>' + sub + '</span></div>' +
      '<button type="button" class="dg-pwa-cta">' + cta + '</button>' +
      '<button type="button" class="dg-pwa-x" aria-label="Chiudi">&times;</button>';
    var off = bottomOffset();
    if (off) banner.style.bottom = 'calc(' + (off + 10) + 'px + env(safe-area-inset-bottom,0px))';
    document.body.appendChild(banner);
    banner.querySelector('.dg-pwa-cta').addEventListener('click', install);
    banner.querySelector('.dg-pwa-x').addEventListener('click', function () {
      snooze(SNOOZE_DAYS_CLOSE);
      hideBanner();
    });
    requestAnimationFrame(function () { requestAnimationFrame(function () {
      if (banner) banner.classList.add('dg-show');
    }); });
  }

  function hideBanner() {
    if (!banner) return;
    var b = banner; banner = null;
    b.classList.remove('dg-show');
    setTimeout(function () { if (b.parentNode) b.parentNode.removeChild(b); }, 400);
  }

  function toast(msg) {
    injectCss();
    var t = document.createElement('div');
    t.className = 'dg-pwa-toast';
    t.setAttribute('role', 'status');
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 3200);
  }

  // ---------- guida passo-passo (iOS e Android manuale) ----------
  function guideSteps() {
    if (mode === 'ios') {
      if (isInAppBrowser) {
        return {
          sub: 'Questo browser interno non permette di creare l’icona.',
          steps: [
            'Tocca <b>⋯</b> o <b>' + SHARE_SVG + '</b> in alto/in basso',
            'Scegli <b>Apri in Safari</b>',
            'In Safari tocca ' + SHARE_SVG + ' <b>Condividi</b> › ' + PLUS_SVG + ' <b>Aggiungi alla schermata Home</b>'
          ],
          arrow: null
        };
      }
      var where = iosBrowser === 'safari' ? 'nella barra in basso' :
                  iosBrowser === 'chrome' ? 'nella barra dell’indirizzo, in alto a destra' :
                  'nel menu del browser';
      return {
        sub: 'Due tocchi e “' + APP_NAME + '” è sulla tua Home.',
        steps: [
          'Tocca ' + SHARE_SVG + ' <b>Condividi</b> ' + where,
          'Scorri e scegli ' + PLUS_SVG + ' <b>Aggiungi alla schermata Home</b>',
          'Tocca <b>Aggiungi</b> in alto a destra'
        ],
        arrow: null  // su iPhone la barra di Safari è sotto il foglio: la freccia non si vedrebbe
      };
    }
    // Android senza prompt automatico
    return {
      sub: 'Il tuo browser non ha mostrato il pulsante automatico: si fa in due tocchi.',
      steps: [
        'Tocca <b>⋮</b> (tre puntini) in alto a destra',
        'Scegli <b>Aggiungi a schermata Home</b> oppure <b>Installa app</b>',
        'Conferma con <b>Aggiungi</b>'
      ],
      arrow: 'top-right'
    };
  }

  function openGuide() {
    injectCss();
    var g = guideSteps();
    var ov = document.createElement('div');
    ov.className = 'dg-pwa-overlay';
    var lis = '';
    for (var i = 0; i < g.steps.length; i++) {
      lis += '<li><span class="dg-pwa-n">' + (i + 1) + '</span><span>' + g.steps[i] + '</span></li>';
    }
    ov.innerHTML =
      '<div class="dg-pwa-sheet" role="dialog" aria-modal="true" aria-label="Aggiungi alla schermata Home">' +
      '<button type="button" class="dg-pwa-x" aria-label="Chiudi">&times;</button>' +
      '<h3>Aggiungi alla Home</h3><p class="dg-sub">' + g.sub + '</p>' +
      '<ol class="dg-pwa-steps">' + lis + '</ol>' +
      '<button type="button" class="dg-pwa-ok">Ho capito</button></div>';
    var arrow = null;
    if (g.arrow) {
      arrow = document.createElement('div');
      arrow.className = 'dg-pwa-arrow';
      arrow.setAttribute('aria-hidden', 'true');
      if (g.arrow === 'bottom') {
        arrow.textContent = '↓';
        arrow.style.left = '50%'; arrow.style.marginLeft = '-10px';
        arrow.style.bottom = 'calc(4px + env(safe-area-inset-bottom,0px))';
      } else {
        arrow.textContent = '↑';
        arrow.style.right = '14px'; arrow.style.top = '4px';
      }
    }
    function close() {
      ov.classList.remove('dg-show');
      if (arrow && arrow.parentNode) arrow.parentNode.removeChild(arrow);
      setTimeout(function () { if (ov.parentNode) ov.parentNode.removeChild(ov); }, 300);
    }
    ov.addEventListener('click', function (e) { if (e.target === ov) close(); });
    ov.querySelector('.dg-pwa-x').addEventListener('click', close);
    ov.querySelector('.dg-pwa-ok').addEventListener('click', function () {
      // Ha visto la guida: non riproporre il banner per qualche giorno.
      snooze(SNOOZE_DAYS_DECLINE);
      hideBanner();
      close();
    });
    document.body.appendChild(ov);
    if (arrow) document.body.appendChild(arrow);
    requestAnimationFrame(function () { requestAnimationFrame(function () { ov.classList.add('dg-show'); }); });
  }

  // ---------- azione principale ----------
  function install() {
    if (mode === 'prompt' && deferredPrompt) {
      var ev = deferredPrompt;
      deferredPrompt = null; // un evento si può usare una volta sola
      hideBanner();
      try {
        ev.prompt();
        ev.userChoice.then(function (choice) {
          if (choice && choice.outcome === 'accepted') {
            lsSet(INSTALLED_KEY, '1');
            setMode(null);
            toast('Fatto! Trovi “' + APP_NAME + '” sulla schermata Home');
          } else {
            snooze(SNOOZE_DAYS_DECLINE);
            // Chrome potrà rilanciare beforeinstallprompt più avanti.
            setMode(null);
          }
        }).catch(function () { setMode(null); });
      } catch (e) {
        // Prompt non disponibile: ripiega sulla guida manuale.
        mode = isIOS ? 'ios' : 'android-manual';
        openGuide();
      }
      return;
    }
    if (mode === 'ios' || mode === 'android-manual') openGuide();
  }

  // ---------- eventi del browser ----------
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();          // blocca la mini-barra automatica di Chrome
    deferredPrompt = e;          // la usiamo noi al tocco su "Crea alias"
    hideBanner();                // se c'era già la guida manuale, la sostituiamo
    setMode('prompt');
    scheduleBanner(400);
  });

  window.addEventListener('appinstalled', function () {
    lsSet(INSTALLED_KEY, '1');
    deferredPrompt = null;
    hideBanner();
    setMode(null);
  });

  var bannerTimer = null;
  function scheduleBanner(ms) {
    clearTimeout(bannerTimer);
    bannerTimer = setTimeout(function () {
      if (document.body) showBanner();
      else document.addEventListener('DOMContentLoaded', showBanner);
    }, ms);
  }

  function bindCustomButtons() {
    var btns = document.querySelectorAll('[data-pwa-install]');
    for (var i = 0; i < btns.length; i++) {
      if (btns[i].__dgBound) continue;
      btns[i].__dgBound = true;
      btns[i].addEventListener('click', function (e) { e.preventDefault(); install(); });
    }
    setMode(mode);
  }

  function exposeApi() {
    window.DaGigiPWA = {
      install: function () { install(); },
      isStandalone: isStandalone,
      canInstall: function () { return !!mode; },
      mode: function () { return mode; }
    };
  }
  exposeApi();

  function init() {
    injectCss();
    bindCustomButtons();
    if (isIOS) {
      setMode('ios');
      scheduleBanner(DELAY);
    } else if (isAndroid) {
      // Diamo tempo a Chrome di lanciare beforeinstallprompt; se non arriva
      // (es. sito su http in Wi-Fi, Firefox, browser vecchi) mostriamo la guida.
      setTimeout(function () {
        if (!mode) { setMode('android-manual'); scheduleBanner(0); }
      }, Math.max(DELAY, 3500));
    }
    // Computer: solo se il browser lancia beforeinstallprompt (Chrome/Edge).
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
