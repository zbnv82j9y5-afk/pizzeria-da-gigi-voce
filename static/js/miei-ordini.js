/*
 * miei-ordini.js — "Il mio ordine" per il cliente.
 *
 * Il telefono ricorda i codici degli ultimi ordini (localStorage
 * "mieiOrdini"); lo stato vero lo chiede sempre al server
 * (/api/ordini/traccia), che lo legge dalla scheda d'ordine aggiornata dallo
 * staff nella schermata "Ordini" della dashboard.
 *
 * Usato da:
 *   - riepilogo.html  -> MieiOrdini.salva(codice) quando l'ordine parte
 *   - index_pizzeria.html -> riquadro in alto (#mioOrdineBanner)
 *   - ordine.html     -> pagina completa con l'avanzamento
 *
 * Se qualcosa non funziona (rete assente, database non aggiornato...) non
 * mostra nulla: il resto del sito resta identico.
 */
(function () {
  'use strict';
  var CHIAVE = 'mieiOrdini';
  var MAX = 8;
  var GIORNI = 3;

  function leggi() {
    try {
      var l = JSON.parse(localStorage.getItem(CHIAVE)) || [];
      var limite = Date.now() - GIORNI * 864e5;
      return l.filter(function (o) { return o && o.id && (o.t || 0) > limite; });
    } catch (e) { return []; }
  }
  function scrivi(l) { try { localStorage.setItem(CHIAVE, JSON.stringify(l.slice(0, MAX))); } catch (e) {} }

  function salva(id) {
    if (!id) return;
    var l = leggi().filter(function (o) { return o.id !== id; });
    l.unshift({ id: id, t: Date.now() });
    scrivi(l);
  }

  function ora(iso) {
    if (!iso) return '';
    try { return new Date(iso).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' }); }
    catch (e) { return ''; }
  }
  function euro(c) { return '€ ' + ((c || 0) / 100).toFixed(2).replace('.', ','); }

  // Ordine "reale" da mostrare: pagato, oppure da pagare in contanti, oppure
  // un pagamento online ancora in verifica da pochi minuti.
  function daMostrare(o) {
    if (o.pagamento === 'fallito' || o.pagamento === 'scaduto') return false;
    if (o.pagamento === 'in_attesa') {
      var eta = Date.now() - new Date(o.creato_il).getTime();
      return eta < 30 * 60 * 1000;
    }
    return true;
  }

  var PASSI_CONSEGNA = ['nuovo', 'accettato', 'in_forno', 'in_consegna', 'consegnato'];
  var PASSI_RITIRO = ['nuovo', 'accettato', 'in_forno', 'pronto', 'consegnato'];

  function descrivi(o) {
    var consegna = o.modalita === 'consegna';
    var entro = ora(o.consegna_entro);
    var tempo = entro ? (consegna ? 'Consegna entro le ' + entro : 'Pronta entro le ' + entro) : '';
    if (o.pagamento === 'in_attesa') {
      return { icona: '⏳', titolo: 'Pagamento in verifica', testo: 'Appena il pagamento è confermato l\'ordine arriva in pizzeria.', classe: 'attesa' };
    }
    switch (o.stato_ordine) {
      case 'nuovo': return { icona: '📨', titolo: 'Ordine ricevuto', testo: 'La pizzeria lo sta guardando: tra poco ti conferma l\'orario.', classe: 'attesa' };
      case 'accettato': return { icona: '👍', titolo: 'Ordine confermato', testo: tempo, classe: 'ok' };
      case 'in_forno': return { icona: '🔥', titolo: 'Le tue pizze sono in forno', testo: tempo, classe: 'ok' };
      case 'in_consegna': return { icona: '🛵', titolo: 'In consegna', testo: entro ? 'Arriva entro le ' + entro : 'Il fattorino sta arrivando', classe: 'ok' };
      case 'pronto': return { icona: '✅', titolo: 'Pronto da ritirare', testo: 'Ti aspettiamo in pizzeria!', classe: 'ok' };
      case 'consegnato': return { icona: '✔️', titolo: consegna ? 'Consegnato' : 'Ritirato', testo: 'Buon appetito!', classe: 'fine' };
      case 'annullato': return { icona: '❌', titolo: 'Ordine annullato', testo: 'Per informazioni chiama la pizzeria.', classe: 'annullato' };
    }
    return { icona: '📦', titolo: 'Ordine', testo: '', classe: 'attesa' };
  }

  function passi(o) {
    var lista = o.modalita === 'consegna' ? PASSI_CONSEGNA : PASSI_RITIRO;
    var nomi = {
      nuovo: 'Ricevuto', accettato: 'Confermato', in_forno: 'In forno',
      in_consegna: 'In consegna', pronto: 'Pronto', consegnato: o.modalita === 'consegna' ? 'Consegnato' : 'Ritirato'
    };
    var attuale = lista.indexOf(o.stato_ordine);
    return lista.map(function (s, i) { return { nome: nomi[s], fatto: i <= attuale, attuale: i === attuale }; });
  }

  function aggiorna() {
    var codici = leggi().map(function (o) { return o.id; });
    if (!codici.length) return Promise.resolve([]);
    return fetch('/api/ordini/traccia?ids=' + encodeURIComponent(codici.join(',')), { cache: 'no-store' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (d) { return (d.ordini || []).filter(daMostrare); });
  }

  // ---------- riquadro sulla home ----------
  var CSS = '' +
    '.mo-banner{display:flex;align-items:center;gap:12px;margin:12px auto 4px;max-width:520px;' +
    'background:#fff;border:2px solid #1e8449;border-radius:16px;padding:12px 14px;text-decoration:none;color:#333;' +
    'box-shadow:0 4px 14px rgba(0,0,0,.06);font-family:Mulish,-apple-system,system-ui,sans-serif;}' +
    '.mo-banner.attesa{border-color:#a97a12;} .mo-banner.annullato{border-color:#c0392b;}' +
    '.mo-banner .mo-ico{font-size:28px;line-height:1;}' +
    '.mo-banner .mo-txt{flex:1;min-width:0;}' +
    '.mo-banner b{display:block;font-size:15px;} .mo-banner span{display:block;font-size:13px;color:#6b6459;}' +
    '.mo-banner .mo-go{font-weight:800;color:#1e8449;font-size:13px;white-space:nowrap;}';

  function iniettaCss() {
    if (document.getElementById('mo-css')) return;
    var s = document.createElement('style'); s.id = 'mo-css'; s.textContent = CSS;
    document.head.appendChild(s);
  }

  function mostraBanner(el) {
    if (!el || !leggi().length) return;
    iniettaCss();
    function giro() {
      aggiorna().then(function (ordini) {
        var attivi = ordini.filter(function (o) { return !o.chiuso; });
        if (!attivi.length) { el.innerHTML = ''; return; }
        var o = attivi[0], d = descrivi(o);
        var altri = attivi.length > 1 ? ' (+' + (attivi.length - 1) + ')' : '';
        el.innerHTML = '<a class="mo-banner ' + d.classe + '" href="ordine.html">' +
          '<span class="mo-ico">' + d.icona + '</span>' +
          '<span class="mo-txt"><b>Il tuo ordine' + altri + ': ' + d.titolo + '</b><span>' + (d.testo || 'Tocca per i dettagli') + '</span></span>' +
          '<span class="mo-go">Vedi ›</span></a>';
      }).catch(function () { /* nessun riquadro */ });
    }
    giro();
    setInterval(function () { if (!document.hidden) giro(); }, 30000);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) giro(); });
  }

  window.MieiOrdini = {
    salva: salva, elenco: leggi, aggiorna: aggiorna, descrivi: descrivi, passi: passi,
    ora: ora, euro: euro, mostraBanner: mostraBanner
  };

  document.addEventListener('DOMContentLoaded', function () {
    var el = document.getElementById('mioOrdineBanner');
    if (el) mostraBanner(el);
  });
})();
