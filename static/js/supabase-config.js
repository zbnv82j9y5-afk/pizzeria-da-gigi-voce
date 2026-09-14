// ============================================================================
// CONFIGURAZIONE SUPABASE — condivisa da web app clienti E dashboard staff
// ============================================================================
// Incolla qui l'URL del progetto e la "anon public key" che trovi in
// Supabase: apri il tuo progetto -> Project Settings -> API.
//
// Finché SUPABASE_URL resta "INSERISCI_URL_PROGETTO", sia il menu clienti
// sia la dashboard restano nel loro comportamento attuale (il menu mostra
// tutte le pizze come sempre; la dashboard mostra un avviso invece del
// login) — nessun rischio di rompere quello che già funziona.
//
// Un solo file da modificare per collegare TUTTO il sistema: questo stesso
// config.js è incluso sia da menu.html/index_pizzeria.html sia dalla
// dashboard-staff.
// ============================================================================
window.PIZZERIA_CONFIG = {
  SUPABASE_URL: "https://pidkptzjcicspxtaubgh.supabase.co",
  SUPABASE_ANON_KEY: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBpZGtwdHpqY2ljc3B4dGF1YmdoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg0MjU3NTAsImV4cCI6MjEwNDAwMTc1MH0.T9d7Dn_xnU4Wfnf-eCtgVLTafw2tqGcDb7XVnDQTxyE",

  // PIN di accesso staff (dashboard) — CAMBIALI prima di usare la dashboard
  // con dati reali. Nota: è un controllo semplice fatto nel browser, non un
  // vero login: chi vede il codice della pagina può risalire al PIN. Va
  // benissimo per iniziare e per i test; prima di usarla con clienti veri,
  // vale la pena sostituirlo con un vero login Supabase (vedi il commento
  // nel file database/schema.sql sulle policy di sicurezza).
  PIN_PIZZAIOLO: "1234",
  PIN_ADMIN: "0000",
};
