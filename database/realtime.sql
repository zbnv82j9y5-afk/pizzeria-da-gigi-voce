-- ============================================================================
-- PIZZERIA DA GIGI — attiva il tempo reale (Realtime) sulle tabelle che
-- devono aggiornarsi da sole: quando un ordine scala ingredienti/panetti, o
-- una pizza si esaurisce, la dashboard staff e il menu clienti lo vedono
-- SUBITO, senza bisogno di ricaricare la pagina o cambiare schermata.
--
-- Esegui questo file UNA VOLTA nell'editor SQL di Supabase (Project -> SQL
-- Editor -> New query -> Run). Puoi eseguirlo anche piu' volte per sbaglio:
-- salta da solo le tabelle gia' attive, senza dare errore.
--
-- Perche' serve: creare le tabelle (schema.sql) NON basta per farle
-- funzionare in tempo reale — Supabase trasmette solo le modifiche delle
-- tabelle esplicitamente aggiunte alla pubblicazione "supabase_realtime".
-- Questo passaggio mancava e per questo la dashboard restava ferma finche'
-- non si cambiava schermata o si ricaricava la pagina a mano.
--
-- Aggiornato per includere anche "ordini" e "spese": servono alla nuova
-- sezione Conti (solo Admin), cosi' incassi/uscite/report pizze si
-- aggiornano da soli quando arriva un nuovo ordine o una nuova spesa,
-- esattamente come gia' succede per magazzino e panetti.
-- ============================================================================

do $$
declare
  tabella text;
begin
  foreach tabella in array array['ingredienti', 'panetti', 'pizze', 'ordini', 'spese'] loop
    if not exists (
      select 1 from pg_publication_tables
      where pubname = 'supabase_realtime'
        and schemaname = 'public'
        and tablename = tabella
    ) then
      execute format('alter publication supabase_realtime add table public.%I', tabella);
    end if;
  end loop;
end $$;
