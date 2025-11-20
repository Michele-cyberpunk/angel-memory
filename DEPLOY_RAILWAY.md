# Deploy su Railway - OMI-Gemini Integration (CLOUD ONLY)

**⚠️ NESSUN COMPONENTE LOCALE RICHIESTO. TUTTO GIRA SU RAILWAY.**

## Architettura Cloud (100% Online)

Per far funzionare tutto senza il tuo PC, creeremo **due servizi** all'interno del tuo progetto Railway. Le due "scatole" si parleranno tra loro direttamente nel cloud.

1.  **Servizio A (Cervello OMI)**: Esegue il server ufficiale OMI.
2.  **Servizio B (La Tua App)**: Esegue questo codice Python (Webhook, Gemini, Email).

---

## Step 1: Crea il Servizio A (OMI MCP) su Railway

1.  Nella dashboard del tuo progetto Railway, clicca **+ New** -> **Docker Image**.
2.  Incolla l'immagine: `omiai/mcp-server:latest` e premi Invio.
3.  Clicca sul nuovo servizio creato -> **Variables** -> **New Variable**.
    *   `OMI_API_KEY`: Incolla il tuo OMI App Secret.
4.  Vai su **Settings** -> **Networking** -> **Public Networking** -> **Generate Domain**.
    *   Copia questo dominio (es. `mcp-production.up.railway.app`).

---

## Step 2: Crea il Servizio B (Python App) su Railway

1.  Clicca **+ New** -> **GitHub Repo** -> Seleziona questa repo `omi-gemini-integration`.
2.  Clicca sul servizio -> **Variables**.
3.  Aggiungi le variabili (copiale dal tuo `.env` o vedi sotto), PIÙ questa fondamentale:
    *   `MCP_SERVER_URL`: `https://IL-TUO-DOMINIO-MCP.up.railway.app/sse`
    *   *(Nota: aggiungi /sse alla fine del dominio copiato nello Step 1)*

---

## Step 3: Configura l'App su OMI (Developer Portal)

1.  Vai su [OMI Developer Portal](https://omi.me/developer).
2.  Clicca **Create App** -> **Memory Creation Trigger**.
3.  Compila i dettagli:
    *   **Name**: Gemini Analyzer
    *   **Description**: Analisi psicologica automatica.
4.  **Endpoint URL**: Incolla il dominio della tua App Python su Railway (Servizio B) seguito da `/webhook/memory`.
    *   Esempio: `https://python-app-production.up.railway.app/webhook/memory`
5.  Assicurati che il parametro `uid` sia incluso (OMI lo aggiunge spesso automaticamente o devi specificarlo nella config).

---

## Configurazione Variabili Completa

```
OMI_APP_ID=...
OMI_APP_SECRET=...
OMI_USER_UID=...
GEMINI_API_KEY=...
MCP_SERVER_URL=https://your-mcp-server.up.railway.app/sse
```

## Verifica

Controlla i log del Webhook Server. Dovresti vedere:
`MCP Integration initialized (Mode: SSE)`
`Connecting to MCP via SSE: ...`
