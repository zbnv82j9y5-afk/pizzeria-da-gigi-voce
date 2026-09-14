-- ============================================================================
-- PIZZERIA DA GIGI — tabella "spese" (uscite di cassa)
-- ============================================================================
-- Serve alla sezione "Conti" della dashboard, visibile solo all'Admin: ogni
-- volta che arriva una bolletta, una consegna da pagare, ecc., l'Admin la
-- registra qui a mano (non c'e' ancora un collegamento automatico con i costi
-- degli ingredienti — e' un libretto delle uscite semplice, volutamente).
--
-- Esegui questo file UNA VOLTA nell'editor SQL di Supabase (Project -> SQL
-- Editor -> New query -> Run). Puoi eseguirlo anche piu' volte per sbaglio:
-- "if not exists" e i "drop policy if exists" lo rendono sicuro da rilanciare.
-- ============================================================================

create table if not exists spese (
  id          bigint generated always as identity primary key,
  data        date not null default current_date,
  descrizione text not null,
  importo     numeric not null check (importo >= 0),
  creato_il   timestamptz not null default now()
);

alter table spese enable row level security;

drop policy if exists "lettura pubblica" on spese;
create policy "lettura pubblica" on spese for select using (true);

-- Stessa scelta di ordini/ingredienti/panetti: scrittura aperta con la anon
-- key, protetta solo dal PIN della dashboard (vedi nota di sicurezza in
-- schema.sql). Va bene per iniziare; da rivedere prima di scalare.
drop policy if exists "scrittura semplice" on spese;
create policy "scrittura semplice" on spese for all using (true) with check (true);
