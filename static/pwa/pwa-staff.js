/*
 * pwa-staff.js — usato solo dalle app staff (/staff/pizzaiolo/ e /staff/admin/).
 *
 * Aperta l'icona "Pizzaiolo" o "Admin", la dashboard mostra la sua normale
 * schermata col PIN. Questo script prova SOLO a semplificare quel passo:
 *   - se trova un pulsante / scheda / scelta col nome del ruolo, lo seleziona;
 *   - mette il cursore nel campo del PIN.
 * Non inserisce mai il PIN e non accede da solo: la password resta obbligatoria.
 * Se non trova nulla di riconoscibile, non fa niente (la dashboard funziona
 * esattamente come all'indirizzo /dashboard-staff/).
 */
(function () {
  'use strict';
  var s = document.currentScript;
  var ruolo = (s && s.getAttribute('data-ruolo')) || '';
  if (!ruolo) return;
  var parole = ruolo === 'admin' ? ['admin', 'amministratore', 'titolare']
                                  : ['pizzaiolo', 'cucina', 'forno'];

  function visibile(el) {
    if (!el || !el.getClientRects().length) return false;
    var st = window.getComputedStyle(el);
    return st.visibility !== 'hidden' && st.display !== 'none';
  }
  function testo(el) { return (el.textContent || el.value || '').toLowerCase().replace(/\s+/g, ' ').trim(); }
  function campoPin() {
    var c = document.querySelectorAll('input[type=password], input[inputmode=numeric], input[type=tel], input[type=number]');
    for (var i = 0; i < c.length; i++) if (visibile(c[i])) return c[i];
    return null;
  }

  var cliccato = false;
  function preseleziona() {
    try {
      var pin = campoPin();
      // 1) un <select> con l'opzione del ruolo
      var sel = document.querySelectorAll('select');
      for (var i = 0; i < sel.length; i++) {
        if (!visibile(sel[i])) continue;
        for (var j = 0; j < sel[i].options.length; j++) {
          var o = sel[i].options[j];
          if (parole.some(function (p) { return testo(o).indexOf(p) !== -1 || (o.value || '').toLowerCase() === p; })) {
            if (sel[i].value !== o.value) {
              sel[i].value = o.value;
              sel[i].dispatchEvent(new Event('change', { bubbles: true }));
            }
            if (pin) { pin.focus(); return true; }
            return false;
          }
        }
      }
      // 2) un radio con etichetta del ruolo
      var radios = document.querySelectorAll('input[type=radio]');
      for (i = 0; i < radios.length; i++) {
        var lab = radios[i].closest('label') || (radios[i].id && document.querySelector('label[for="' + radios[i].id + '"]'));
        var t = (lab ? testo(lab) : '') + ' ' + (radios[i].value || '').toLowerCase();
        if (parole.some(function (p) { return t.indexOf(p) !== -1; })) {
          if (!radios[i].checked) radios[i].click();
          if (pin) { pin.focus(); return true; }
          return false;
        }
      }
      // 3) UN SOLO pulsante/scheda visibile col nome del ruolo (se sono di piu', non indoviniamo).
      //    Va bene sia "scegli il ruolo, poi compare il PIN" sia "ruolo e PIN insieme".
      if (!cliccato) {
        var cand = [];
        var els = document.querySelectorAll('button, [role=tab], [role=button], .tab, .role, .ruolo');
        for (i = 0; i < els.length; i++) {
          var el = els[i];
          if (!visibile(el)) continue;
          var tx = testo(el);
          if (tx.length > 40) continue;
          if (/accedi|entra|login|conferma|esci|logout/.test(tx)) continue;
          if (parole.some(function (p) { return tx.indexOf(p) !== -1; })) cand.push(el);
        }
        if (cand.length === 1) { cand[0].click(); cliccato = true; return false; }
      }
      if (pin) { pin.focus(); return true; }
      return false;
    } catch (e) {
      return true; // in caso di imprevisti non insistiamo
    }
  }

  function avvia() {
    var tentativi = 0;
    var t = setInterval(function () {
      tentativi++;
      if (preseleziona() || tentativi > 60) clearInterval(t);  // fino a ~15 s: la dashboard aspetta Supabase
    }, 250);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', avvia);
  else avvia();
})();
