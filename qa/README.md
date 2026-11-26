# Test automatici — Beach Torneo V11.1

Questa cartella raccoglie i test browser **Playwright** della versione V11.1.

## Esecuzione locale

```bash
python -m pip install -r qa/requisiti.txt
python -m playwright install chromium
python qa/esegui_test.py index.html
```

La suite principale verifica 25 scenari di generazione, interfaccia, autorizzazioni **simulate**, gestione dei tornei, sincronizzazione e conflitti. I test aggiuntivi verificano 15 scenari relativi a beach, padel, classifiche, backup, stampa e mobile.

## GitHub Actions

Il workflow `.github/workflows/collaudo.yml` viene eseguito automaticamente per le pull request e per i push che modificano `index.html`, `qa/` o il workflow stesso. Si puo avviare anche manualmente dalla scheda **Actions**.

Il runner utilizza una **copia temporanea di `index.html`** con la configurazione Supabase disattivata. Le API vengono simulate nel browser: la suite non usa credenziali reali e **non modifica tornei o database Supabase**.

### Limiti

Questi test **non sostituiscono** i test end-to-end con una vera istanza Supabase: RLS, RPC SQL, sincronizzazione reale tra dispositivi e sicurezza delle sessioni richiedono un collaudo separato.

**Nota sulla pubblicazione:** se GitHub Pages pubblica direttamente il branch `main`, questo workflow non blocca automaticamente il deploy in caso di test falliti. E consigliabile approvare e unire le pull request solo dopo il completamento positivo dei test.
