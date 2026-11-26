# V11.2 — protezione login e test PostgreSQL

Questo intervento aggiunge un limite **aggregato per torneo** ai tentativi di accesso del mini-organizzatore. Nella V11.1 il blocco dipendeva solo da `p_client_id`, un identificativo gestito dal browser e modificabile dal chiamante.

## Come funziona

- Si conserva la RPC `public.v111_login(integer,text,text)`: **nessuna modifica richiesta all'`index.html`**.
- Resta il blocco V11.1 dopo 5 password sbagliate dallo stesso identificativo browser.
- Inoltre il server blocca **per 60 secondi il login di un torneo dopo 20 password errate in una finestra di 60 secondi**, anche se vengono usati 20 identificativi browser diversi.
- Per conteggi consistenti fra chiamate parallele, l'RPC blocca la riga del torneo con `SELECT … FOR UPDATE`.
- I contatori sono nella nuova tabella `public.v112_login_limits`, con RLS attiva e **senza permessi di lettura/scrittura diretta** per `anon` e `authenticated`.
- Le sessioni, i PIN, i dati dei tornei e le credenziali esistenti non vengono cancellati.

**Limite importante:** chi attacca può provocare il breve blocco del login legittimo di quel torneo; è un compromesso per contenere la forza bruta con una RPC pubblica. Il limite è condiviso per torneo, **non è un rate limiter IP affidabile** e non sostituisce WAF/Edge Function con CAPTCHA server-side per applicazioni esposte a grande traffico. L'Architetto accede separatamente tramite Supabase Auth.

## Test automatici

Il workflow [Database login integration tests](../.github/workflows/db-integration.yml) avvia un **PostgreSQL 17 temporaneo** su GitHub Actions, applica lo script due volte (controllando l'idempotenza), e verifica tramite SQL:

- rotazione di 20 `client_id` e blocco aggregato;
- impossibilità di leggere la tabella dei contatori come ruolo `anon`;
- isolamento di due tornei;
- rilascio del blocco dopo la scadenza;
- permanenza del blocco per singolo browser;
- login valido, creazione di sessioni e rifiuto dei tornei archiviati.

I test verificano la logica della RPC su un PostgreSQL effimero con uno **schema minimo di compatibilità**: non sono un collaudo completo del gateway Supabase Auth/PostgREST e non utilizzano il database di produzione. Non richiedono password Supabase nei GitHub Secrets.

## Rilascio

**Unire la Pull Request non applica lo script SQL a Supabase.** È una separazione intenzionale, per evitare aggiornamenti invisibili del backend.

1. Assicurarsi che GitHub Actions sia verde e fare un backup dei tornei importanti.
2. Revisionare `db/patches/v112_login_guard.sql`; poi eseguirlo in Supabase SQL Editor sul progetto **Torneo** (in un'unica query da `BEGIN;` a `COMMIT;`), oppure autorizzare esplicitamente l'applicazione tramite l'integrazione Supabase.
3. Controllare che la tabella `v112_login_limits` abbia RLS attiva, `anon` non possa leggerla e che un login legittimo funzioni.
4. Nessuna sostituzione di `index.html` è necessaria; il nome della RPC rimane lo stesso.

**Per tornare alla V11.1:** ripristinare la definizione precedente di `v111_login` dal file `Aggiornamento_Supabase_V11_1.sql`; poi, se desiderato, eliminare la tabella `v112_login_limits`. Non eliminare la tabella prima di ripristinare la funzione.

## Da migliorare in seguito

- Un ambiente Supabase dedicato alla staging e test HTTP con `anon`, `authenticated` e sessioni reali.
- Limitazione degli accessi al gateway (IP/reputazione/CAPTCHA) che non dipenda dal browser.
- Abilitare in Supabase Auth il controllo delle password compromesse, se disponibile per il piano del progetto.
