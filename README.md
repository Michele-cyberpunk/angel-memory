# OMI-Gemini Integration System

Sistema di integrazione tra OMI (Open Memory Interface), Gemini AI e Google Workspace per rielaborazione intelligente di trascritti conversazionali e automazione.

## Architettura

```
OMI App → Webhook → Gemini AI (cleaning + analysis) → OMI Memories + Google Workspace
```

### Componenti

1. **OMI Client** - Comunicazione con OMI Import API
2. **Transcript Processor** - Pulizia trascritti con Gemini (fallback chain: Flash → Pro → Lite)
3. **Psychological Analyzer** - Analisi pattern ADHD, ansia, tono emotivo
4. **Workspace Automation** - Integrazione Gmail, Calendar, Slides
5. **Orchestrator** - Coordinamento pipeline completa
6. **Webhook Server** - FastAPI server per ricevere webhook da OMI

## Setup

### 1. Installazione Dipendenze

```bash
cd /home/ai/omi-gemini-integration
pip install -r requirements.txt
```

### 2. Configurazione Credenziali

Copia `.env.template` in `.env` e completa:

```bash
cp .env.template .env
nano .env
```

Credenziali necessarie:
- ✅ OMI_APP_ID, OMI_APP_SECRET, OMI_USER_UID (già configurate)
- ✅ GEMINI_API_KEY (già configurato)
- ⚠️ Google Workspace OAuth2 (da configurare usare il file presente)

### 3. Setup Google Workspace (Opzionale)

Per automazione Gmail/Calendar/Slides:

1. Vai a [Google Cloud Console](https://console.cloud.google.com)
2. Crea nuovo progetto "OMI-Gemini-Integration"
3. Abilita API:
   - Gmail API
   - Google Calendar API
   - Google Slides API
4. Crea credenziali OAuth 2.0 (Desktop app, ma in questo caso non va bene dato che sarà tutto lato railwey o firebase o cloud run a discrezione del LLm che sta programmando e sta analizzando questo scritto)
5. Scarica `client_secret.json` in `config/`

### 4. Avvio Server

```bash
python webhook_server.py
```

Il server parte su `http://localhost:8000`

### 5. Esposizione Webhook (ngrok)

Per testare con OMI app reale:

```bash
# Installa ngrok se necessario
# Avvia tunnel
ngrok http 8000

# Copia URL pubblico (es. https://abc123.ngrok.io)
# Configura in OMI app: Settings → Developer → Webhook URL
```

## Utilizzo

### Webhook Endpoints

#### 1. Memory Creation Webhook
```
POST /webhook/memory?uid={user_id}
```
Triggered automaticamente quando OMI app crea una memoria.

**Payload**: Oggetto memoria completo da OMI

**Processo**:
1. Estrae trascritto dalla memoria
2. Pulisce il testo ricevuto con Gemini (fallback chain)
3. Analisi psicologica (ADHD, ansia, tono emotivo, identificazione di bias e rionoscimento realistico della situazione (da implementare))
4. Salva analisi come nuova memoria in OMI
5. (Opzionale) Crea bozza email se necessario
6. Invia notifica all'app OMI

#### 2. Real-Time Transcript Webhook
```
POST /webhook/realtime?session_id={id}&uid={user_id}
```
Riceve segmenti di trascritto in tempo reale durante conversazioni.

#### 3. Audio Streaming Webhook
```
POST /webhook/audio?sample_rate={rate}&uid={user_id}
```
Riceve audio bytes raw (PCM) dal dispositivo OMI.

### API Endpoints

#### Manual Analysis
```bash
curl -X POST "http://localhost:8000/api/analyze?limit=5"
```
Analizza manualmente le ultime N conversazioni da OMI.

#### Health Check
```bash
curl http://localhost:8000/health
```

## Flusso Operativo Completo

### Fase Alpha (MVP) - ✅ IMPLEMENTATA

1. Setup credenziali OMI + Gemini
2. Integrazione base OMI Import API
3. Pulizia trascritti con Gemini Flash
4. Test webhook memory creation

### Fase Beta - DA IMPLEMENTARE

5. Fallback chain completo (Flash → Pro → Flash-Lite)
6. Analisi psicologica (ADHD + ansia)
7. Generazione automatica email drafts
8. Lettura email via Gmail API

### Fase Gamma - DA IMPLEMENTARE

9. Generazione presentazioni Slides
10. Integrazione completa Calendar
11. Sistema notifiche app OMI
12. Ottimizzazioni performance

## Testing Locale

### Test Webhook Memory Creation

```bash
curl -X POST "http://localhost:8000/webhook/memory?uid=test_user_123" \
  -H "Content-Type: application/json" \
  -d '{
    "id": 999,
    "created_at": "2025-11-18T10:00:00Z",
    "transcript_segments": [
      {
        "text": "This is a test transcript with some errors and umm filler words that need cleaning",
        "speaker": "SPEAKER_00",
        "start": 0.0,
        "end": 5.0
      }
    ],
    "structured": {
      "title": "Test Memory",
      "overview": "Test conversation"
    }
  }'
```

### Test Manual Analysis

```bash
# Analizza ultime 3 conversazioni reali da OMI
curl -X POST "http://localhost:8000/api/analyze?limit=3"
```

## Struttura File

```
omi-gemini-integration/
├── config/
│   ├── __init__.py
│   ├── settings.py           # Configurazione centralizzata
│   ├── client_secret.json    # OAuth2 Google (da creare)
│   └── token.json           # Token OAuth salvato automaticamente
├── modules/
│   ├── __init__.py
│   ├── omi_client.py         # Client OMI Import API
│   ├── transcript_processor.py  # Gemini cleaning con fallback
│   ├── psychological_analyzer.py # Analisi psicologica
│   ├── workspace_automation.py  # Gmail, Calendar, Slides
│   └── orchestrator.py       # Coordinatore principale
├── tests/
│   └── (test files)
├── logs/
│   └── webhook_server.log
├── .env                      # Credenziali (NON committare!)
├── .env.template             # Template credenziali
├── requirements.txt
├── webhook_server.py         # FastAPI server
└── README.md

```

## Configurazione App OMI

1. Apri OMI app → Settings → Developer Mode
2. Abilita Developer Mode
3. Configura capabilities:
   - ✅ Memory Creation Trigger
   - ✅ Real-Time Transcript Processor (opzionale)
   - ✅ Create/Read Memories (Import API)
4. Imposta webhook URL: `https://your-ngrok-url.ngrok.io/webhook/memory`

## Logs e Debug

```bash
# Visualizza logs in tempo reale
tail -f logs/webhook_server.log

# Filtra solo errori
grep ERROR logs/webhook_server.log
```

## Troubleshooting

### "Missing GEMINI_API_KEY"
- Verifica `.env` contenga `GEMINI_API_KEY=...`
- Riavvia server dopo modifica `.env`

### "Missing OMI credentials"
- Controlla `OMI_APP_ID`, `OMI_APP_SECRET`, `OMI_USER_UID` in `.env`

### "Gmail API not initialized"
- Setup Google Workspace OAuth2 (vedi sezione Setup)
- Esegui authenticazione: il server aprirà browser per login Google

### Webhook non riceve chiamate
- Verifica ngrok sia attivo: `ngrok http 8000`
- Controlla URL configurato in OMI app corrisponda a ngrok URL
- Verifica OMI app sia in Developer Mode

## Sicurezza

- ❌ NON committare `.env` con credenziali reali
- ❌ NON esporre webhook server senza HTTPS in produzione
- ✅ Usa ngrok o servizio simile per testing
- ✅ Implementa validazione webhook signatures in produzione
- ✅ Rate limiting per API calls

## Prossimi Passi

1. ✅ Fase Alpha completata (MVP funzionante)
2. ⏳ Testare con conversazioni reali da OMI
3. ⏳ Implementare Fase Beta (automazione Gmail completa)
4. ⏳ Implementare Fase Gamma (Calendar + Slides)
5. ⏳ Deploy produzione con HTTPS

## Supporto

- **Documentazione OMI**: https://docs.omi.me/
- **GitHub OMI**: https://github.com/BasedHardware/omi
- **Discord OMI**: http://discord.omi.me
- **Gemini API Docs**: https://ai.google.dev/gemini-api/docs

---

**Versione**: 1.0.0 (Fase Alpha)
**Data**: 2025-11-18
**Autore**: OMI-Gemini Integration Team
