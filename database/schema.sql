-- ============================================================================
-- PIZZERIA DA GIGI — SCHEMA DATABASE (Postgres / Supabase)
-- ============================================================================
-- Incolla questo file per intero nell'editor SQL di Supabase (Project ->
-- SQL Editor -> New query) ed esegui con "Run". Crea le 5 tabelle descritte
-- nel documento di architettura: ingredienti, panetti, pizze, ricette, ordini.
--
-- Le colonne "stato" e "quantita_rimanenti" si calcolano DA SOLE (generated
-- always as ...) — non le aggiorna mai nessuno a mano, quindi non possono mai
-- andare fuori sincrono con la quantità reale.
--
-- "quantita_iniziale" su ingredienti è la scorta piena di inizio giornata:
-- serve solo al pulsante "Ripristina tutto" della dashboard, per riportare le
-- quantità al valore standard senza doverle reinserire a mano ogni mattina.
--
-- Le pizze hanno DUE prezzi (grande/piccola), come nel menu reale — la
-- ricetta (tabella ricette) resta UNICA per pizza, indipendente dal formato:
-- è la stessa semplificazione del documento di architettura ("ogni pizza
-- consuma esattamente 1 panetto qualunque sia la ricetta"), qui estesa a
-- "la stessa ricetta serve sia per la grande sia per la piccola". È
-- volutamente approssimato — una piccola userà in realtà un po' meno
-- impasto e condimento — ma è un ottimo punto di partenza: se in futuro
-- servirà più precisione, la tabella ricette può diventare
-- (pizza_id, formato, ingrediente_id, quantita).
-- ============================================================================

create table if not exists ingredienti (
  id                   bigint generated always as identity primary key,
  nome                 text not null unique,
  quantita_disponibile numeric not null default 0,
  quantita_iniziale    numeric not null default 0,
  unita_misura         text not null default 'kg',
  soglia_allarme       numeric not null default 1,
  stato                text generated always as (
    case
      when quantita_disponibile <= 0 then 'esaurito'
      when quantita_disponibile <= soglia_allarme then 'scorte_basse'
      else 'disponibile'
    end
  ) stored,
  data_aggiornamento   timestamptz not null default now()
);

create table if not exists panetti (
  id                  bigint generated always as identity primary key,
  data                date not null default current_date unique,
  quantita_preparati  int not null default 0,
  quantita_utilizzati int not null default 0,
  quantita_rimanenti  int generated always as
    (quantita_preparati - quantita_utilizzati) stored
);

create table if not exists pizze (
  id             bigint generated always as identity primary key,
  numero_menu    int,
  nome           text not null unique,
  descrizione    text,
  prezzo_grande  numeric not null,
  prezzo_piccola numeric not null,
  immagine_url   text,
  disponibile    boolean not null default true,
  categoria      text default 'classica'
);

create table if not exists ricette (
  id                  bigint generated always as identity primary key,
  pizza_id            bigint not null references pizze(id) on delete cascade,
  ingrediente_id      bigint not null references ingredienti(id) on delete cascade,
  quantita_necessaria numeric not null,
  unique (pizza_id, ingrediente_id)
);

create table if not exists ordini (
  id                bigint generated always as identity primary key,
  pizza_id          bigint references pizze(id),
  data_ora          timestamptz not null default now(),
  stato             text not null default 'ricevuto',
  formato           text not null default 'grande',
  quantita          int not null default 1,
  nome_cliente      text,
  telefono_cliente  text,
  indirizzo_cliente text,
  totale            numeric
);

-- ----------------------------------------------------------------------------
-- Sicurezza (RLS) — versione semplice per iniziare.
-- ----------------------------------------------------------------------------
-- Il menu (pizze) e lo stato del magazzino (ingredienti/panetti) devono poter
-- essere LETTI da chiunque visiti il sito o l'assistente AI, senza login.
-- Le SCRITTURE (dashboard staff, backend ordini) per ora restano permesse con
-- la sola "anon key" per semplicità, dato che l'accesso staff è protetto da
-- un PIN gestito nell'app, non da un vero login Supabase.
--
-- ATTENZIONE (nota per lo sviluppatore): questo va bene per iniziare e per
-- testare, ma NON è una vera protezione lato server — chiunque conosca la
-- anon key potrebbe scrivere nel database. Prima di andare online con clienti
-- reali, vale la pena sostituire il PIN con un vero login Supabase (Auth) e
-- restringere le policy di scrittura a utenti autenticati con ruolo staff.

alter table ingredienti enable row level security;
alter table panetti     enable row level security;
alter table pizze       enable row level security;
alter table ricette     enable row level security;
alter table ordini      enable row level security;

create policy "lettura pubblica" on ingredienti for select using (true);
create policy "lettura pubblica" on panetti     for select using (true);
create policy "lettura pubblica" on pizze       for select using (true);
create policy "lettura pubblica" on ricette     for select using (true);

create policy "scrittura semplice" on ingredienti for all using (true) with check (true);
create policy "scrittura semplice" on panetti     for all using (true) with check (true);
create policy "scrittura semplice" on pizze       for all using (true) with check (true);
create policy "scrittura semplice" on ricette     for all using (true) with check (true);
create policy "scrittura semplice" on ordini      for all using (true) with check (true);
