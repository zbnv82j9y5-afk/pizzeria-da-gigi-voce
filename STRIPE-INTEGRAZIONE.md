# Integrazione Stripe (pagamento con carta) — Pizzeria da Gigi

Aggiunge il pagamento con carta di credito/debito come alternativa a
Satispay: stesso identico impianto (vedi SATISPAY-INTEGRAZIONE.md se
presente), stessa tabella "checkout_pendenti" (colonna `provider` per
distinguere le due strade), stessa Opzione B (il magazzino si scala SOLO a
pagamento confermato).

## Cosa cambia per il cliente

Nella schermata di riepilogo ordine ci sono ora TRE modi di completare
l'ordine, tutti alternativi tra loro:

1. **✅ Conferma — pago alla consegna** (contanti/POS al fattorino o in
   negozio — per la consegna a domicilio, solo se il cliente è nell'elenco
   clienti di fiducia)
2. **📲 Paga subito con Satispay** (serve l'app Satispay e il numero di
   telefono)
3. **💳 Paga con carta** (Stripe — pagina sicura ospitata da Stripe, il
   cliente inserisce i dati della carta lì, mai sul nostro sito)

## Come funziona (lato tecnico)

1. Il cliente clicca "Paga con carta" → il browser chiama
   `POST /api/checkout/stripe/avvia` con carrello + dati cliente.
2. Il server ricalcola il totale dai prezzi VERI del database (mai fidandosi
   del browser — stessa logica di Satispay), salva una riga in
   `checkout_pendenti` con `provider = 'stripe'`, e chiede a Stripe di
   creare una "Checkout Session".
3. Il browser viene mandato (redirect) sulla pagina di pagamento ospitata
   da Stripe stesso (dominio `checkout.stripe.com`).
4. Il cliente paga con la carta. Stripe fa due cose in parallelo:
   - richiama in automatico il nostro sito su `success_url` (il cliente
     torna su `riepilogo.html`);
   - manda un webhook al nostro server (`POST /api/stripe/webhook`) — è
     QUESTO che fa davvero fede, non il ritorno del browser (che il
     cliente potrebbe in teoria manipolare o non arrivare mai a
     completare, es. chiude la scheda subito dopo aver pagato).
5. Il webhook verifica la firma (garantisce che la richiesta arrivi
   davvero da Stripe), poi crea l'ordine vero (stessa funzione SQL
   `crea_ordine` usata da Satispay e dal pagamento alla consegna).
6. La pagina `riepilogo.html`, tornata dal redirect, controlla lo stato del
   checkout (stesso endpoint `GET /api/checkout/stato/{id}` già usato per
   Satispay) finché non risulta "pagato", poi mostra la conferma.

Se una pizza risultasse esaurita proprio nei secondi tra pagamento e
creazione ordine (caso raro, stessa gestione di Satispay): l'ordine per le
altre pizze va comunque a buon fine, e la differenza per la pizza mancante
viene rimborsata automaticamente sulla carta del cliente.

## Come attivarlo (passo per passo)

### 1. Crea un account Stripe

A differenza di Satispay, **non serve un codice di attivazione**: basta
registrarsi su https://dashboard.stripe.com/register con un'email. Appena
creato l'account si è già in **modalità test** (nessun soldo vero si
muove, si può iniziare a provare subito, senza verifiche del business).

### 2. Recupera le chiavi di test

Nel pannello Stripe (in alto a destra: assicurati di essere in modalità
"Test", non "Live"), vai su **Sviluppatori → Chiavi API**
(https://dashboard.stripe.com/test/apikeys). Ci sono due chiavi:

- **Publishable key** (inizia con `pk_test_...`) — non ci serve per questa
  integrazione (usiamo Stripe Checkout, non serve incollarla da nessuna
  parte sul sito).
- **Secret key** (inizia con `sk_test_...`) — questa sì, va salvata come
  variabile d'ambiente `STRIPE_SECRET_KEY` su Render. È sensibile quanto la
  chiave privata di Satispay: **mai condividerla, mai metterla su Git**.

### 3. Crea il webhook

Sempre nel pannello Stripe, in modalità test, vai su
**Sviluppatori → Webhook → Aggiungi endpoint**
(https://dashboard.stripe.com/test/webhooks):

- URL endpoint: `https://pizzeria-da-gigi-sito.onrender.com/api/stripe/webhook`
- Eventi da ascoltare: seleziona solo `checkout.session.completed`

Dopo averlo creato, Stripe mostra una **Signing secret** (inizia con
`whsec_...`): va salvata come variabile d'ambiente `STRIPE_WEBHOOK_SECRET`
su Render — stessa sensibilità della secret key.

### 4. Imposta le variabili d'ambiente su Render

Come già fatto per Satispay: Render → il servizio → Environment →
aggiungi `STRIPE_SECRET_KEY` e `STRIPE_WEBHOOK_SECRET` con i valori del
passo 2 e 3, poi "Save, rebuild, and deploy".

### 5. Collauda con una carta di test

In modalità test, Stripe accetta solo carte "finte" apposite, es.:

- Numero: `4242 4242 4242 4242`
- Scadenza: una data futura qualsiasi (es. `12/34`)
- CVC: 3 cifre qualsiasi (es. `123`)
- Nome/CAP: qualsiasi valore

Con questa carta il pagamento va sempre a buon fine. Per provare un
pagamento rifiutato, Stripe ha altre carte di test dedicate (elenco
completo: https://docs.stripe.com/testing).

### 6. Verifica veloce senza fare un ordine vero

Come per Satispay, c'è un endpoint diagnostico:
`https://pizzeria-da-gigi-sito.onrender.com/api/stripe/diagnostica` — deve
rispondere con entrambe le variabili a `true`.

## Passaggio a pagamenti veri (più avanti, quando sarete pronti)

Nel pannello Stripe si passa dalla modalità "Test" a "Live" (in alto a
destra) — Stripe potrebbe chiedere qualche dato in più sull'attività
(partita IVA, IBAN per gli incassi). Le chiavi live iniziano con
`sk_live_...`/`whsec_...` (diverse da quelle di test): si creano un nuovo
webhook e si sostituiscono semplicemente le due variabili d'ambiente su
Render — nessuna modifica al codice.

## Fonti

- https://docs.stripe.com/api/checkout/sessions/create
- https://docs.stripe.com/webhooks
- https://docs.stripe.com/testing
