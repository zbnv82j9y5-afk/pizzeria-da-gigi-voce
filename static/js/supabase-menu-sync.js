// ============================================================================
// PIZZERIA DA GIGI — sincronizzazione live della disponibilità del menu
// ============================================================================
// Se il database Supabase è configurato (vedi supabase-config.js), tiene
// aggiornata la disponibilità delle pizze leggendo la tabella "pizze" e
// ascoltando i suoi aggiornamenti in tempo reale (Supabase Realtime) — così
// il menu si "spegne" da solo appena lo staff segna un ingrediente esaurito
// dalla dashboard, senza che il cliente debba ricaricare la pagina.
//
// Se NON è configurato (o la libreria supabase-js non si carica, es. niente
// rete), questo file semplicemente non fa nulla: le pagine che lo includono
// restano nel loro comportamento statico di sempre. Nessun rischio di
// rompere una pagina che funziona già.
// ============================================================================
(function () {
  function isConfigured() {
    var cfg = window.PIZZERIA_CONFIG || {};
    return !!cfg.SUPABASE_URL && cfg.SUPABASE_URL.indexOf('INSERISCI') === -1 &&
           !!cfg.SUPABASE_ANON_KEY && cfg.SUPABASE_ANON_KEY.indexOf('INSERISCI') === -1;
  }

  window.PizzeriaLiveMenu = {
    disponibilita: null, // null finché non arriva la prima risposta dal database
    client: null,

    // start(onChange): onChange(mappa) viene richiamata al primo caricamento
    // e ad ogni aggiornamento in tempo reale. mappa è un oggetto
    // { "NOME PIZZA IN MAIUSCOLO": true|false }.
    start: function (onChange) {
      if (!isConfigured() || typeof window.supabase === 'undefined') return;

      try {
        this.client = window.supabase.createClient(
          window.PIZZERIA_CONFIG.SUPABASE_URL,
          window.PIZZERIA_CONFIG.SUPABASE_ANON_KEY
        );
      } catch (e) {
        console.warn('PizzeriaLiveMenu: configurazione Supabase non valida —', e.message);
        return;
      }

      var self = this;
      function refresh() {
        self.client.from('pizze').select('nome, disponibile').then(function (res) {
          if (res.error || !res.data) {
            console.warn('PizzeriaLiveMenu: lettura pizze fallita —', res.error && res.error.message);
            return;
          }
          self._applyRows(res.data, onChange);
        });
      }

      // Corregge subito un'eventuale discordanza tra i panetti di oggi e le
      // pizze segnate come ordinabili (tipico a inizio giornata, prima che lo
      // staff apra la dashboard): senza questo un cliente potrebbe vedere per
      // qualche minuto pizze "disponibili" che in realtà non lo sono ancora.
      // Se questa chiamata fallisce (es. utente ancora anonimo senza questa
      // funzione) il menu funziona comunque come prima, solo un po' più lento
      // ad aggiornarsi.
      this.client.rpc('sincronizza_stato_giornaliero').then(function (res) {
        if (res && res.error) console.warn('PizzeriaLiveMenu: sincronizza_stato_giornaliero —', res.error.message);
        refresh();
      });
      this.client
        .channel('menu-live')
        .on('postgres_changes', { event: '*', schema: 'public', table: 'pizze' }, refresh)
        .subscribe();
    },

    _applyRows: function (rows, onChange) {
      var map = {};
      rows.forEach(function (r) { map[String(r.nome).toUpperCase()] = !!r.disponibile; });
      this.disponibilita = map;
      onChange(map);
    },

    // true/false se la pizza è nel database, sempre true se non ancora
    // caricato o se quel nome non esiste nel database (fallback prudente:
    // non nascondere mai una pizza per un problema di collegamento).
    isDisponibile: function (nomeMaiuscolo) {
      if (!this.disponibilita) return true;
      if (!(nomeMaiuscolo in this.disponibilita)) return true;
      return this.disponibilita[nomeMaiuscolo];
    }
  };
})();
