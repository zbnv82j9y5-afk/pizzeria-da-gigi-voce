-- ============================================================================
-- ORDINI SEGUIBILI — "Il mio ordine" per il cliente, schermata "Ordini" per lo
-- staff, comune di consegna.
--
-- La tabella checkout_pendenti diventa la SCHEDA D'ORDINE unica per tutti i
-- metodi di pagamento (carta, Satispay e ora anche contanti): contiene gia'
-- cliente, carrello, importo e stato del pagamento. Qui si aggiungono:
--   - modalita / comune          -> ritiro o consegna, e in quale comune
--   - stato_ordine               -> a che punto e' la preparazione
--   - consegna_entro             -> orario promesso dal pizzaiolo
--   - accettato_il / chiuso_il   -> per i tempi
-- La tabella "ordini" (una riga per pizza, usata da magazzino e conti) non
-- cambia.
--
-- Solo aggiunte: nessuna colonna o riga esistente viene cancellata. Si puo'
-- rilanciare piu' volte senza danni.
-- GIA' APPLICATO su Supabase via MCP: questo file resta come documentazione.
-- ============================================================================

alter table checkout_pendenti add column if not exists modalita       text not null default 'ritiro';
alter table checkout_pendenti add column if not exists comune         text;
alter table checkout_pendenti add column if not exists stato_ordine   text not null default 'nuovo';
alter table checkout_pendenti add column if not exists consegna_entro timestamptz;
alter table checkout_pendenti add column if not exists accettato_il   timestamptz;
alter table checkout_pendenti add column if not exists chiuso_il      timestamptz;

alter table checkout_pendenti drop constraint if exists checkout_pendenti_modalita_check;
alter table checkout_pendenti add constraint checkout_pendenti_modalita_check
  check (modalita in ('ritiro', 'consegna'));

alter table checkout_pendenti drop constraint if exists checkout_pendenti_stato_ordine_check;
alter table checkout_pendenti add constraint checkout_pendenti_stato_ordine_check
  check (stato_ordine in ('nuovo', 'accettato', 'in_forno', 'in_consegna', 'pronto', 'consegnato', 'annullato'));

-- Nuovo metodo "contanti" (pagamento alla consegna / in negozio)...
alter table checkout_pendenti drop constraint if exists checkout_pendenti_provider_check;
alter table checkout_pendenti add constraint checkout_pendenti_provider_check
  check (provider in ('satispay', 'stripe', 'contanti'));

-- ...e il relativo stato di pagamento "da_pagare" (si paga a mano).
alter table checkout_pendenti drop constraint if exists checkout_pendenti_stato_check;
alter table checkout_pendenti add constraint checkout_pendenti_stato_check
  check (stato in ('in_attesa', 'pagato', 'fallito', 'scaduto', 'da_pagare'));

create index if not exists idx_checkout_ordini_aperti
  on checkout_pendenti (stato_ordine, creato_il);

-- Le schede gia' esistenti prima di questa modifica erano prove: le
-- consideriamo chiuse, cosi' non compaiono come "nuove" allo staff.
update checkout_pendenti
   set stato_ordine = 'consegnato', chiuso_il = coalesce(chiuso_il, now())
 where stato_ordine = 'nuovo' and accettato_il is null and creato_il < now() - interval '1 minute';

-- ----------------------------------------------------------------------------
-- Comuni serviti e costo della consegna. Si modificano da Supabase
-- (Table Editor -> comuni_consegna) senza toccare il codice:
--   attivo = false  -> il comune sparisce dall'elenco del cliente
--   ordine          -> posizione nell'elenco
-- ----------------------------------------------------------------------------
create table if not exists comuni_consegna (
  id               bigint generated always as identity primary key,
  nome             text not null unique,
  costo_centesimi  int  not null default 250 check (costo_centesimi >= 0),
  attivo           boolean not null default true,
  ordine           int  not null default 0
);

alter table comuni_consegna enable row level security;
drop policy if exists "comuni_consegna_accesso_pubblico" on comuni_consegna;
create policy "comuni_consegna_accesso_pubblico" on comuni_consegna
  for all using (true) with check (true);

-- Elenco di esempio (la pizzeria lo personalizzera' piu' avanti; in futuro
-- si potra' passare a tariffe per distanza dalla pizzeria).
insert into comuni_consegna (nome, costo_centesimi, ordine)
select v.nome, v.costo, v.ordine
from (values ('Sassari', 250, 1), ('Sorso', 350, 2), ('Sennori', 350, 3)) as v(nome, costo, ordine)
where not exists (select 1 from comuni_consegna);

-- ----------------------------------------------------------------------------
-- Tempo reale: la dashboard staff vede subito i nuovi ordini.
-- ----------------------------------------------------------------------------
do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime')
     and not exists (select 1 from pg_publication_tables
                     where pubname = 'supabase_realtime' and schemaname = 'public'
                       and tablename = 'checkout_pendenti') then
    execute 'alter publication supabase_realtime add table public.checkout_pendenti';
  end if;
end $$;
