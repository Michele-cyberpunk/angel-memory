# Deployment Guide - OMI-Gemini Integration

## Status Implementazione

### ✅ Fase Alpha - COMPLETATA

**Componenti Implementati:**
- ✅ Struttura progetto completa
- ✅ Configurazione centralizzata (`config/settings.py`)
- ✅ OMI Client (Import API + Notifications)
- ✅ Transcript Processor con fallback chain Gemini
- ✅ Psychological Analyzer (ADHD + Anxiety detection)
- ✅ Workspace Automation (Gmail, Calendar, Slides)
- ✅ Orchestrator principale
- ✅ FastAPI Webhook Server
- ✅ Test suite completa
- ✅ Documentazione README

**Credenziali Configurate:**
- ✅ OMI_APP_ID, OMI_APP_SECRET, OMI_USER_UID
- ⚠️ GEMINI_API_KEY (richiede verifica/aggiornamento)
- ⏳ Google Workspace OAuth2 (opzionale, da configurare)

---

## Problema Rilevato: Gemini API Key

### Diagnosi

Durante il testing, la chiave API `GOOGLE_API_KEY=AIzaSyA2CjRD9pGVGV4Ihjsx0mB7XiVt2crtx2Q` presente nell'environment non è valida per Gemini API.

**Errore:**
```
400 API key not valid. Please pass a valid API key. [reason: "API_KEY_INVALID"]
```

### Soluzione

#### Opzione 1: Verifica Chiave Esistente

La chiave potrebbe essere per un servizio Google diverso (Maps, YouTube, ecc.). Verifica su [Google Cloud Console](https://console.cloud.google.com/apis/credentials) se hai una chiave abilitata per **Generative Language API**.

#### Opzione 2: Genera Nuova Chiave Gemini

1. Vai su [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click "Create API Key"
3. Seleziona o crea progetto Google Cloud
4. Copia la chiave generata (formato: `AIza...`)

5. Aggiorna `.env`:
```bash
cd /home/ai/omi-gemini-integration
nano .env

# Sostituisci la riga GEMINI_API_KEY con la nuova chiave:
GEMINI_API_KEY=AIza_YOUR_NEW_KEY_HERE
```

6. Riavvia i test:
```bash
source venv/bin/activate
python test_example.py
```

---

## Quick Start (Dopo Fix API Key)

### 1. Verifica Configurazione

```bash
cd /home/ai/omi-gemini-integration
cat .env
```

Assicurati che tutte le credenziali siano presenti:
```bash
OMI_APP_ID=01K76TYMGYY3EHAPDVKJ91VN9A
OMI_APP_SECRET=sk_9c9bc22d4d61a870d5188c84ac7e6640
OMI_USER_UID=TcKWu3rCazPZc4GgmZY9jNcx7wH3
GEMINI_API_KEY=<YOUR_VALID_KEY>
```

### 2. Avvia Server Webhook

```bash
cd /home/ai/omi-gemini-integration
source venv/bin/activate
python webhook_server.py
```

Il server sarà disponibile su: `http://localhost:8000`

### 3. Esposizione Pubblica con ngrok

In un terminale separato:

```bash
# Installa ngrok se necessario
# curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
# echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
# sudo apt update && sudo apt install ngrok

# Avvia tunnel
ngrok http 8000
```

Output esempio:
```
Forwarding  https://abc123.ngrok.io -> http://localhost:8000
```

### 4. Configurazione App OMI

1. Apri OMI app sul tuo dispositivo
2. Vai a **Settings → Developer Mode**
3. Abilita Developer Mode
4. Configura webhook:
   - **Memory Creation Webhook URL**: `https://abc123.ngrok.io/webhook/memory`
   - **Real-Time Transcript URL** (opzionale): `https://abc123.ngrok.io/webhook/realtime`

5. Salva configurazione

### 5. Test Webhook

#### Test Manuale con curl:

```bash
curl -X POST "http://localhost:8000/webhook/memory?uid=TcKWu3rCazPZc4GgmZY9jNcx7wH3" \
  -H "Content-Type: application/json" \
  -d '{
    "id": 999,
    "created_at": "2025-11-18T22:00:00Z",
    "transcript_segments": [
      {
        "text": "This is a test transcript with some umm filler words",
        "speaker": "SPEAKER_00",
        "start": 0.0,
        "end": 3.0
      }
    ],
    "structured": {
      "title": "Test Memory",
      "overview": "Test conversation"
    }
  }'
```

#### Test con OMI App:

1. Crea una nuova memoria nell'app OMI
2. Verifica nei logs del server:
   ```bash
   tail -f logs/webhook_server.log
   ```
3. Dovresti vedere:
   - Ricezione webhook
   - Pulizia trascritto con Gemini
   - Analisi psicologica
   - Creazione nuova memoria
   - Invio notifica all'app

---

## Monitoring e Debug

### Logs Server

```bash
# Logs in tempo reale
tail -f logs/webhook_server.log

# Solo errori
grep ERROR logs/webhook_server.log

# Ultimi 50 log
tail -50 logs/webhook_server.log
```

### Health Check

```bash
# Verifica server attivo
curl http://localhost:8000/health

# Test endpoint root
curl http://localhost:8000/
```

### Test Manuale Pipeline

```bash
cd /home/ai/omi-gemini-integration
source venv/bin/activate

# Analizza ultime 5 conversazioni reali da OMI
curl -X POST "http://localhost:8000/api/analyze?limit=5"
```

---

## Google Workspace Integration (Opzionale)

### Setup OAuth2

Per abilitare automazione Gmail/Calendar/Slides:

1. **Google Cloud Console** → [Credentials](https://console.cloud.google.com/apis/credentials)
2. Click **"+ CREATE CREDENTIALS" → OAuth 2.0 Client ID**
3. Application type: **Desktop app**
4. Nome: "OMI-Gemini Integration"
5. Download JSON → Salva come `config/client_secret.json`

6. Abilita API:
   - [Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com)
   - [Google Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com)
   - [Google Slides API](https://console.cloud.google.com/apis/library/slides.googleapis.com)

### Prima Autenticazione

```bash
cd /home/ai/omi-gemini-integration
source venv/bin/activate
python -c "from modules.workspace_automation import WorkspaceAutomation; wa = WorkspaceAutomation(); wa.authenticate()"
```

Si aprirà un browser per il login Google. Autorizza l'app.

Le credenziali verranno salvate automaticamente in `config/token.json`.

---

## Architettura Sistema

```
┌─────────────┐
│   OMI App   │
└──────┬──────┘
       │ Webhook POST
       ▼
┌─────────────────────────────┐
│  FastAPI Webhook Server     │
│  (webhook_server.py)        │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│    Orchestrator             │
│  (orchestrator.py)          │
└──────┬──────────────────────┘
       │
       ├─────────────────────────────┐
       │                             │
       ▼                             ▼
┌──────────────┐          ┌──────────────────┐
│ Transcript   │          │ Psychological    │
│ Processor    │          │ Analyzer         │
│ (Gemini AI)  │          │ (Gemini AI)      │
└──────┬───────┘          └────────┬─────────┘
       │                           │
       │                           │
       ▼                           ▼
┌─────────────────────────────────────────┐
│         OMI Import API                  │
│   (Memories + Notifications)            │
└─────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│   Google Workspace APIs (Opzionale)     │
│   Gmail | Calendar | Slides             │
└─────────────────────────────────────────┘
```

---

## Flusso Operativo Dettagliato

### 1. Webhook Memory Creation

```
OMI App crea memoria
  ↓
POST /webhook/memory?uid={user_id}
  ↓
Orchestrator.process_memory_webhook()
  ↓
├─ Estrae trascritto da memoria
├─ TranscriptProcessor.process_transcript()
│  └─ Gemini cleaning (Flash → Pro → Lite fallback)
├─ PsychologicalAnalyzer.analyze()
│  └─ Gemini analysis (ADHD, Anxiety, Emotion)
├─ OMIClient.create_memories()
│  └─ Salva analisi come nuova memoria
├─ WorkspaceAutomation.should_create_email()
│  └─ (Se necessario) crea bozza email Gmail
└─ OMIClient.send_notification()
   └─ Notifica push all'app OMI
```

### 2. Real-Time Transcript Processing

```
OMI App durante conversazione
  ↓
POST /webhook/realtime?session_id={id}&uid={user_id}
  ↓
Orchestrator.process_realtime_transcript()
  ↓
Accumula segmenti per sessione
  ↓
(Analisi completa alla creazione memoria)
```

---

## Sicurezza e Best Practices

### Credenziali

- ✅ `.env` file NON committato (gitignore)
- ✅ OAuth2 tokens in `config/token.json` (gitignore)
- ⚠️ In produzione, usa secret manager (AWS Secrets, Google Secret Manager)

### Rate Limiting

Gemini API limits (tier gratuito):
- Flash: 15 req/min, 1M tokens/day
- Pro: 2 req/min, 50K tokens/day

OMI Import API:
- Implementa retry con exponential backoff
- Monitora 429 errors

### HTTPS

- ❌ ngrok è OK per dev/testing
- ✅ In produzione, usa server con certificato SSL valido
- ✅ Valida webhook signatures (se disponibili)

---

## Troubleshooting

### Server non si avvia

```bash
# Verifica porta 8000 libera
lsof -i :8000

# Cambia porta se necessario
export WEBHOOK_PORT=8080
python webhook_server.py
```

### Gemini API Errors

**400 API_KEY_INVALID**
→ Genera nuova chiave su [Google AI Studio](https://aistudio.google.com/app/apikey)

**429 Too Many Requests**
→ Attendi 1 minuto (rate limit)
→ Implementa caching trascritti già processati

**500 Internal Error**
→ Verifica modelli disponibili:
```python
import google.generativeai as genai
genai.configure(api_key="YOUR_KEY")
for m in genai.list_models():
    print(m.name)
```

### OMI API Errors

**403 Forbidden**
→ Verifica user abbia abilitato app in OMI
→ Controlla capabilities app in OMI Developer Settings

**401 Unauthorized**
→ Verifica `OMI_APP_SECRET` corretto

### Webhook non riceve chiamate

1. Verifica ngrok attivo: `curl https://your-ngrok-url.ngrok.io/health`
2. Controlla URL configurato in OMI app
3. Verifica Developer Mode abilitato
4. Test manuale con curl

---

## Next Steps (Fase Beta)

### To-Do

1. ⏳ **Fix Gemini API Key** → Genera nuova chiave valida
2. ⏳ **Test End-to-End** → Webhook reale da OMI app
3. ⏳ **Google Workspace OAuth** → Setup client_secret.json
4. ⏳ **Email Automation** → Test generazione bozze
5. ⏳ **Calendar Integration** → Estrazione eventi da trascritti
6. ⏳ **Slides Generation** → Template presentazioni

### Fase Gamma (Futura)

7. ⏳ Deploy produzione (Docker + HTTPS)
8. ⏳ Database per caching analisi
9. ⏳ Dashboard monitoring
10. ⏳ Multi-user support

---

## Supporto

**Documentazione:**
- OMI: https://docs.omi.me/
- Gemini: https://ai.google.dev/gemini-api/docs
- FastAPI: https://fastapi.tiangolo.com/

**Community:**
- OMI Discord: http://discord.omi.me
- GitHub Issues: https://github.com/BasedHardware/omi/issues

---

**Ultima aggiornamento**: 2025-11-18
**Versione Sistema**: 1.0.0 (Fase Alpha completa)
