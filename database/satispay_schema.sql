-- ============================================================================
-- SATISPAY — tabelle di supporto (Opzione B: si scala il magazzino SOLO a
-- pagamento confermato). Non tocca nessuna tabella esistente: "ordini",
-- "ricette", "ingredienti", "panetti", "pizze" restano come sono, e
-- crea_ordine() continua a funzionare esattamente come oggi.
--
-- GIA' APPLICATO su Supabase (progetto "Pizzeria da Gigi") — questo file
-- resta solo come documentazione dello schema effettivo. Se in futuro serve
-- ricrearlo (es. altro progetto Supabase), rilancialo pure: usa "if not
-- exists" ovunque possibile.
-- ============================================================================

create table if not exists checkout_pendenti (
  id                          uuid primary key default gen_random_uuid(),
  carrello                    jsonb not null,       -- [{numero_menu, formato, quantita, prezzo_unitario_centesimi}, ...]
  nome_cliente                text,
  telefono_cliente            text not null,
  indirizzo_cliente           text,
  importo_centesimi           int not null,         -- totale VERO (calcolato server-side dai prezzi reali)
  sconto_applicato_centesimi  int not null default 0,
  omaggio_bibita              boolean not null default false,  -- true se e' il primo ordine via app di questo cliente
  satispay_payment_id         text unique,
  stato                       text not null default 'in_attesa'
                                check (stato in ('in_attesa','pagato','fallito','scaduto')),
  ordini_creati               jsonb,                -- riempito a pagamento confermato: risultato di crea_ordine per riga
  note                        text,                 -- es. avviso di rimborso parziale (pizza esaurita nel frattempo)
  creato_il                   timestamptz not null default now(),
  aggiornato_il               timestamptz not null default now()
);

create index if not exists idx_checkout_satispay_payment_id
  on checkout_pendenti (satispay_payment_id);

-- Fedeltà clienti, identificati per numero di telefono (già raccolto ad
-- ogni ordine): niente login/account da gestire.
create table if not exists clienti_fedelta (
  telefono                      text primary key,
  primo_ordine_fatto            boolean not null default false,
  punti                         int not null default 0,        -- Opzione A (attiva): bibita gratis ogni 3 punti
  sconto_disponibile_centesimi  int not null default 0,        -- Opzione B (non attiva per ora)
  ordini_totali                 int not null default 0,
  aggiornato_il                  timestamptz not null default now()
);

alter table checkout_pendenti enable row level security;
alter table clienti_fedelta enable row level security;

-- Stesso schema di sicurezza gia' in uso per le altre tabelle del sito
-- (accesso tramite anon key, come pizze/ordini/panetti): l'app e' pubblica
-- e non ha login clienti, quindi le policy restano aperte qui come lo sono
-- altrove nello stesso database.
drop policy if exists "checkout_pendenti_accesso_pubblico" on checkout_pendenti;
create policy "checkout_pendenti_accesso_pubblico" on checkout_pendenti
  for all using (true) with check (true);

drop policy if exists "clienti_fedelta_accesso_pubblico" on clienti_fedelta;
create policy "clienti_fedelta_accesso_pubblico" on clienti_fedelta
  for all using (true) with check (true);
