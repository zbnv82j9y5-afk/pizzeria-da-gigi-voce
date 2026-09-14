-- ============================================================================
-- PIZZERIA DA GIGI — FUNZIONI E TRIGGER AUTOMATICI
-- ============================================================================
-- Esegui DOPO schema.sql. Queste funzioni vivono dentro il database, non nel
-- codice del backend: così qualunque scrittura (dashboard, backend ordini,
-- persino una modifica manuale nell'editor Supabase) ricalcola da sola quali
-- pizze restano ordinabili — è la regola d'oro dell'architettura: "nessuna
-- parte del sistema decide da sola, tutti chiedono al database".
-- ============================================================================

-- Scala un ingrediente di una certa quantità (mai sotto zero).
create or replace function scala_ingrediente(id_ingrediente bigint, quantita numeric)
returns void as $$
begin
  update ingredienti
  set quantita_disponibile = greatest(quantita_disponibile - quantita, 0),
      data_aggiornamento = now()
  where id = id_ingrediente;
end;
$$ language plpgsql;

-- Scala 1 panetto dal contatore di oggi (crea la riga del giorno se manca).
create or replace function scala_panetto()
returns void as $$
begin
  insert into panetti (data, quantita_preparati, quantita_utilizzati)
  values (current_date, 0, 0)
  on conflict (data) do nothing;

  update panetti
  set quantita_utilizzati = quantita_utilizzati + 1
  where data = current_date;
end;
$$ language plpgsql;

-- Riporta OGNI ingrediente alla sua scorta piena di inizio giornata
-- (pulsante "Ripristina tutto" della dashboard — sezione 2.2 del documento).
create or replace function ripristina_ingredienti()
returns void as $$
begin
  update ingredienti
  set quantita_disponibile = quantita_iniziale,
      data_aggiornamento = now();
end;
$$ language plpgsql;

-- Ricalcola pizze.disponibile per TUTTE le pizze, in base a:
--  1) i panetti rimasti oggi (se sono 0, tutte le pizze si spengono)
--  2) se la ricetta della pizza usa un ingrediente con stato 'esaurito'
create or replace function recalcola_disponibilita_pizze()
returns void as $$
declare
  panetti_oggi int;
begin
  select quantita_rimanenti into panetti_oggi
  from panetti where data = current_date;

  if panetti_oggi is null or panetti_oggi <= 0 then
    update pizze set disponibile = false where disponibile is distinct from false;
    return;
  end if;

  update pizze p
  set disponibile = not exists (
    select 1
    from ricette r
    join ingredienti i on i.id = r.ingrediente_id
    where r.pizza_id = p.id
      and i.stato = 'esaurito'
  )
  where p.disponibile is distinct from not exists (
    select 1
    from ricette r
    join ingredienti i on i.id = r.ingrediente_id
    where r.pizza_id = p.id
      and i.stato = 'esaurito'
  );
end;
$$ language plpgsql;

-- Wrapper per i trigger (i trigger devono chiamare una funzione che ritorna
-- "trigger", non "void").
create or replace function trg_recalcola_pizze()
returns trigger as $$
begin
  perform recalcola_disponibilita_pizze();
  return null;
end;
$$ language plpgsql;

-- Si attiva ogni volta che cambia la quantità di un ingrediente (quindi anche
-- quando scala_ingrediente() lo fa scendere a 0, o quando Gigi tocca
-- "Esaurito"/"Ripristina" nella dashboard).
drop trigger if exists trg_ingredienti_recalcola on ingredienti;
create trigger trg_ingredienti_recalcola
after update of quantita_disponibile on ingredienti
for each statement
execute function trg_recalcola_pizze();

-- Si attiva quando cambiano i panetti di oggi (inserimento della mattina,
-- oppure ogni volta che un ordine ne consuma uno).
drop trigger if exists trg_panetti_recalcola on panetti;
create trigger trg_panetti_recalcola
after insert or update of quantita_preparati, quantita_utilizzati on panetti
for each statement
execute function trg_recalcola_pizze();

-- Si attiva se l'admin aggiunge/modifica/rimuove una ricetta (es. una pizza
-- nuova, o cambia gli ingredienti di una pizza esistente).
drop trigger if exists trg_ricette_recalcola on ricette;
create trigger trg_ricette_recalcola
after insert or update or delete on ricette
for each statement
execute function trg_recalcola_pizze();

-- ----------------------------------------------------------------------------
-- Funzione "porta d'ingresso" per un nuovo ordine: verifica e scala tutto in
-- UNA sola operazione indivisibile (fondamentale se due clienti ordinano nello
-- stesso secondo: senza questo, due letture "quasi contemporanee" della stessa
-- riga potrebbero permettere di vendere una pizza che in realtà non c'è più).
-- Ritorna una riga con esito ('ok' oppure il motivo del rifiuto).
-- ----------------------------------------------------------------------------
create or replace function crea_ordine(
  p_pizza_id bigint,
  p_formato text default 'grande',
  p_quantita int default 1,
  p_nome text default null,
  p_telefono text default null,
  p_indirizzo text default null
)
returns table (ok boolean, motivo text, ordine_id bigint) as $$
declare
  panetti_oggi int;
  riga record;
  v_prezzo numeric;
  v_ordine_id bigint;
begin
  if p_formato not in ('grande', 'piccola') then
    return query select false, 'Formato non valido (usa grande o piccola)', null::bigint;
    return;
  end if;

  -- Blocca la riga dei panetti di oggi per evitare due ordini in corsa fra loro.
  insert into panetti (data) values (current_date) on conflict (data) do nothing;
  select quantita_rimanenti into panetti_oggi
  from panetti where data = current_date for update;

  if panetti_oggi is null or panetti_oggi < p_quantita then
    return query select false, 'Panetti terminati per oggi', null::bigint;
    return;
  end if;

  -- Verifica ogni ingrediente della ricetta (con lock, stesso motivo di sopra).
  for riga in
    select i.id, i.nome, i.quantita_disponibile, r.quantita_necessaria
    from ricette r
    join ingredienti i on i.id = r.ingrediente_id
    where r.pizza_id = p_pizza_id
    for update of i
  loop
    if riga.quantita_disponibile < riga.quantita_necessaria * p_quantita then
      return query select false, (riga.nome || ' non è sufficiente'), null::bigint;
      return;
    end if;
  end loop;

  -- Tutto ok: scala ingredienti, scala panetti, registra l'ordine.
  for riga in
    select ingrediente_id, quantita_necessaria
    from ricette where pizza_id = p_pizza_id
  loop
    perform scala_ingrediente(riga.ingrediente_id, riga.quantita_necessaria * p_quantita);
  end loop;

  for i in 1..p_quantita loop
    perform scala_panetto();
  end loop;

  select (case when p_formato = 'grande' then prezzo_grande else prezzo_piccola end)
    into v_prezzo from pizze where id = p_pizza_id;

  insert into ordini (pizza_id, formato, quantita, stato, nome_cliente, telefono_cliente, indirizzo_cliente, totale)
  values (p_pizza_id, p_formato, p_quantita, 'ricevuto', p_nome, p_telefono, p_indirizzo, v_prezzo * p_quantita)
  returning id into v_ordine_id;

  perform recalcola_disponibilita_pizze();

  return query select true, 'ok', v_ordine_id;
end;
$$ language plpgsql;

-- ----------------------------------------------------------------------------
-- Corregge una discordanza che si vede a inizio giornata: se nessuno ha
-- ancora toccato i panetti di OGGI (nessun salvataggio dalla dashboard,
-- nessun ordine), la riga di "panetti" per oggi non esiste ancora — e senza
-- quella riga il trigger che spegne le pizze non e' mai scattato, quindi
-- "pizze.disponibile" resta ancora quello di ieri (es. "40 ordinabili")
-- anche se i panetti di oggi sono davvero 0.
--
-- Questa funzione crea la riga di oggi se manca (a 0/0, come sempre) e
-- ricalcola SUBITO la disponibilita' delle pizze di conseguenza. Va chiamata
-- ad ogni apertura della dashboard staff e del menu clienti, cosi' il numero
-- "pizze ordinabili" e' sempre coerente con i panetti davvero preparati,
-- fin dal primo secondo della giornata.
-- ----------------------------------------------------------------------------
create or replace function sincronizza_stato_giornaliero()
returns void as $$
begin
  insert into panetti (data) values (current_date) on conflict (data) do nothing;
  perform recalcola_disponibilita_pizze();
end;
$$ language plpgsql;

-- ----------------------------------------------------------------------------
-- Suggerimento di riordino automatico — sezione "🛒 Riordino" della dashboard.
--
-- Idea: invece di un valore fisso di "scorta ottimale" da cambiare a mano
-- quando cambia la stagione, calcoliamo quanto si sta DAVVERO consumando
-- ogni ingrediente guardando gli ultimi "p_giorni_finestra" giorni di ordini
-- veri (tabella ordini + ricette, gia' esistenti — nessun dato nuovo da
-- tracciare). Da quel consumo medio giornaliero ricaviamo quanto tenerne in
-- magazzino per coprire "p_giorni_copertura" giorni, e quindi quanto
-- comprare per arrivarci. Cosi', se siamo in piena stagione (tanti ordini)
-- il consiglio sale da solo; a fine stagione (pochi ordini) scende da solo
-- — senza che nessuno debba ricordarsi di cambiare un'impostazione.
--
-- Se un ingrediente non ha ancora ordini registrati nel periodo, il consumo
-- medio risulta 0 e quindi non viene suggerito nessun acquisto (scelta
-- prudente: niente dati veri, nessun consiglio inventato).
-- ----------------------------------------------------------------------------
create or replace function report_riordino(
  p_giorni_finestra int default 7,
  p_giorni_copertura int default 7
)
returns table (
  ingrediente_id             bigint,
  nome                       text,
  unita_misura               text,
  quantita_disponibile       numeric,
  consumo_medio_giornaliero  numeric,
  scorta_obiettivo           numeric,
  quantita_da_comprare       numeric
) as $$
begin
  return query
  select
    i.id,
    i.nome,
    i.unita_misura,
    i.quantita_disponibile,
    round(coalesce(c.consumo_totale, 0) / p_giorni_finestra, 3) as consumo_medio_giornaliero,
    round((coalesce(c.consumo_totale, 0) / p_giorni_finestra) * p_giorni_copertura, 3) as scorta_obiettivo,
    round(greatest(
      ((coalesce(c.consumo_totale, 0) / p_giorni_finestra) * p_giorni_copertura) - i.quantita_disponibile,
      0
    ), 3) as quantita_da_comprare
  from ingredienti i
  left join (
    select r.ingrediente_id, sum(o.quantita * r.quantita_necessaria) as consumo_totale
    from ordini o
    join ricette r on r.pizza_id = o.pizza_id
    where o.data_ora >= now() - (p_giorni_finestra || ' days')::interval
    group by r.ingrediente_id
  ) c on c.ingrediente_id = i.id
  order by quantita_da_comprare desc, i.nome;
end;
$$ language plpgsql stable;
