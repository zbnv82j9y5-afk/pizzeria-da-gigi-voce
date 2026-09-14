-- ============================================================================
-- STRIPE — pagamento con carta di credito/debito, alternativo a Satispay.
-- Riusa la tabella checkout_pendenti gia' creata per Satispay (vedi
-- satispay_schema.sql): aggiunge solo le colonne che servono a distinguere
-- ed eseguire il pagamento con Stripe, senza duplicare la tabella.
--
-- GIA' APPLICATO su Supabase (progetto "Pizzeria da Gigi") tramite MCP —
-- questo file resta come documentazione dello schema effettivo.
-- ============================================================================

alter table checkout_pendenti
  add column if not exists provider text not null default 'satispay'
    check (provider in ('satispay', 'stripe'));

alter table checkout_pendenti
  add column if not exists stripe_session_id text unique;

create index if not exists idx_checkout_stripe_session_id
  on checkout_pendenti (stripe_session_id);
