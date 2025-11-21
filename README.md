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
7. **Modality Processors** - Sistema estensibile per elaborazione multimodale (testo, audio, immagini)
8. **Language Support** - Rilevamento lingua e traduzione automatica

### Nuove Funzionalità Multimodali e Multilingue

Il sistema è stato esteso per supportare elaborazione multimodale e multilingue:

#### Modalità Supportate
- **Testo**: Elaborazione trascritti conversazionali (esistente)
- **Audio**: Trascrizione e analisi audio streams da dispositivi OMI
- **Immagini**: Analisi contenuti visivi e OCR intelligente

#### Caratteristiche Multilingue
- **Rilevamento Automatico**: Identificazione lingua del contenuto
- **Traduzione**: Supporto per 12+ lingue (EN, ES, FR, DE, IT, PT, ZH, JA, KO, RU, AR, HI)
- **Fallback**: Gestione elegante contenuti multilingue

#### Architettura Estensibile
- **Processor Registry**: Sistema plugin-based per aggiungere nuove modalità
- **Abstract Base Classes**: Interfacce standard per implementazioni custom
- **Factory Pattern**: Creazione dinamica processors basata su configurazione
- **Plugin System**: Directory `modules/plugins/` per estensioni custom

#### Configurazione Multimodale

```bash
# Audio Processing
ENABLE_AUDIO_PROCESSING=true
AUDIO_SAMPLE_RATE=16000
MAX_AUDIO_DURATION_SECONDS=300

# Image Analysis
ENABLE_IMAGE_ANALYSIS=true
MAX_IMAGE_SIZE_MB=10
SUPPORTED_IMAGE_FORMATS=jpg,jpeg,png,webp,bmp

# Multilingual Support
ENABLE_LANGUAGE_DETECTION=true
ENABLE_TRANSLATION=true
DEFAULT_LANGUAGE=en
SUPPORTED_LANGUAGES=en,es,fr,de,it,pt,zh,ja,ko,ru,ar,hi
```

#### Esempi Utilizzo

**Elaborazione Audio:**
```python
from modules.orchestrator import OMIGeminiOrchestrator
from modules.modality_processor import ModalityType

orchestrator = OMIGeminiOrchestrator()
result = orchestrator.process_multimodal_input(
    audio_bytes, ModalityType.AUDIO, user_id
)
```

**Plugin Custom:**
```python
# modules/plugins/custom_processor.py
from modules.modality_processor import TextProcessor

class CustomTextProcessor(TextProcessor):
    def process(self, input_data: str, **kwargs):
        # Implementazione custom
        return ProcessingResult(...)
```

**Documentazione Plugin**: Vedi `modules/plugins/example_custom_processor.py`

## Setup

### Prerequisites

- **Python 3.9+** - Required for FastAPI and async operations
- **Git** - For cloning the repository
- **Virtual Environment** - Recommended for dependency isolation

### 1. Clone Repository

```bash
git clone <repository-url>
cd omi-gemini-integration
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Upgrade pip first
pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt

# Verify installation
python -c "import fastapi, google.generativeai, requests; print('All dependencies installed successfully')"
```

### 4. Environment Configuration

#### Copy Environment Template

```bash
cp .env.template .env
```

#### Required Environment Variables

Edit `.env` with your credentials:

```bash
# OMI Integration (Required)
OMI_APP_ID=your_omi_app_id_here
OMI_APP_SECRET=your_omi_app_secret_here
OMI_USER_UID=your_omi_user_uid_here

# Gemini AI (Required)
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Google Workspace Integration
GOOGLE_CLIENT_SECRET_PATH=config/client_secret.json

# Optional: Security Settings
WEBHOOK_SECRET=your_webhook_secret_here
ENFORCE_HTTPS=false
ENABLE_RATE_LIMITING=true
RATE_LIMIT_PER_MINUTE=60

# Optional: Server Configuration
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8000
DEBUG=true
LOG_LEVEL=INFO
```

#### Obtaining API Keys

**OMI Credentials:**
1. Go to [OMI Developer Portal](https://omi.me/developer)
2. Create a new app with "Memory Creation Trigger" capability
3. Copy App ID, App Secret, and your User UID

**Gemini API Key:**
1. Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create a new API key
3. Copy the key to `GEMINI_API_KEY`

### 5. Google Workspace Setup (Optional)

For Gmail/Calendar/Slides automation:

1. **Google Cloud Console**: Go to [console.cloud.google.com](https://console.cloud.google.com)
2. **Create Project**: "OMI-Gemini-Integration"
3. **Enable APIs**:
   - Gmail API
   - Google Calendar API
   - Google Slides API
4. **Create OAuth 2.0 Credentials**:
   - Application type: **Web application** (for production)
   - Authorized redirect URIs: Add your production domain
5. **Download Credentials**: Save as `config/client_secret.json`

### 6. Verify Configuration

```bash
# Test configuration loading
python -c "from config.settings import AppSettings; print('Configuration loaded successfully')"

# Test API key validation
python scripts/check_api_keys.py
```

### 7. Start Development Server

```bash
# Activate virtual environment (if not already)
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Start the server
python webhook_server.py
```

The server will start on `http://localhost:8000`

### 8. Test Local Setup

#### Health Check
```bash
curl http://localhost:8000/health
```

#### Manual API Test
```bash
curl -X POST "http://localhost:8000/api/analyze?limit=1"
```

### 9. Production Deployment Setup

For production deployment, see the [Deployment Guides](#deployment) section below.

## Deployment

### Available Deployment Guides

| Platform | Guide | Setup Time | Best For |
|----------|-------|------------|----------|
| **Railway** | [DEPLOY_RAILWAY.md](DEPLOY_RAILWAY.md) | 5-10 min | Quick cloud deployment |
| **General** | [DEPLOYMENT.md](DEPLOYMENT.md) | 15-30 min | Complete deployment guide |

### Railway Deployment (Recommended)

Railway provides the easiest path to production:

1. **Connect Repository**: Link your GitHub repo to Railway
2. **Auto-Deploy**: Railway detects Python and deploys automatically
3. **Environment Variables**: Copy from your `.env` file
4. **Production URL**: Get HTTPS domain for OMI webhooks

See [DEPLOY_RAILWAY.md](DEPLOY_RAILWAY.md) for step-by-step instructions.

### Other Platforms

For deployment to Heroku, AWS, Docker, or other platforms, see the comprehensive guide in [DEPLOYMENT.md](DEPLOYMENT.md) which includes:

- Detailed setup procedures
- Environment configuration
- Production security considerations
- Monitoring and troubleshooting
- Cost optimization tips

### Production Checklist

- [ ] HTTPS enabled (`ENFORCE_HTTPS=true`)
- [ ] Environment variables set securely
- [ ] Webhook signature validation enabled
- [ ] Rate limiting configured
- [ ] Monitoring/logging set up
- [ ] Backup strategy for data
- [ ] Domain configured and SSL certificate valid

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

## API Documentation

The OMI-Gemini Integration provides both webhook endpoints (called by OMI) and manual API endpoints for testing and administration.

### Base URL
```
https://your-domain.com  # Production
http://localhost:8000    # Development
```

### Authentication
- Webhook endpoints use optional signature validation
- Manual endpoints are unprotected (use firewall/load balancer for security)
- Set `WEBHOOK_SECRET` environment variable for signature validation

### Endpoints

#### 1. Health Check
**GET** `/`

Basic health check endpoint.

**Response:**
```json
{
  "status": "online",
  "service": "OMI-Gemini Integration",
  "timestamp": "2025-11-21T15:22:14.754Z"
}
```

#### 2. Detailed Health Check
**GET** `/health`

Comprehensive health check with component status.

**Response:**
```json
{
  "status": "healthy",
  "orchestrator_initialized": true,
  "timestamp": "2025-11-21T15:22:14.754Z"
}
```

#### 3. Performance Statistics
**GET** `/performance`

Returns performance metrics and system stats.

**Response:**
```json
{
  "performance_stats": {
    "total_requests": 150,
    "average_response_time": 2.3,
    "error_rate": 0.02,
    "memory_usage_mb": 85.6
  },
  "timestamp": "2025-11-21T15:22:14.754Z"
}
```

#### 4. Memory Creation Webhook
**POST** `/webhook/memory`

Called automatically by OMI when a new memory is created.

**Query Parameters:**
- `uid` (string, required): User identifier

**Headers:**
- `Content-Type`: `application/json`
- `X-OMI-Signature` (optional): Webhook signature for validation
- `X-OMI-Timestamp` (optional): Request timestamp

**Request Body:**
```json
{
  "id": 12345,
  "created_at": "2025-11-21T15:22:14Z",
  "transcript_segments": [
    {
      "text": "Hello, how are you today?",
      "speaker": "SPEAKER_00",
      "start": 0.0,
      "end": 3.5
    }
  ],
  "structured": {
    "title": "Daily Conversation",
    "overview": "Casual greeting and check-in"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Processed 4 steps, 0 errors",
  "details": {
    "success": true,
    "steps_completed": ["transcript_cleaning", "psychological_analysis", "memory_creation", "notification_sent"],
    "errors": [],
    "processing_time_seconds": 2.1
  }
}
```

**Error Response:**
```json
{
  "detail": "Missing or invalid 'uid' query parameter"
}
```

#### 5. Real-Time Transcript Webhook
**POST** `/webhook/realtime`

Receives real-time transcript segments during active conversations.

**Query Parameters:**
- `session_id` (string, required): Unique session identifier
- `uid` (string, required): User identifier

**Request Body:**
```json
[
  {
    "text": "I'm doing well, thank you for asking.",
    "speaker": "SPEAKER_01",
    "start": 3.5,
    "end": 6.2
  }
]
```

**Response:**
```json
{
  "status": "success",
  "result": {
    "segments_processed": 1,
    "session_id": "session_123",
    "accumulated_segments": 5
  }
}
```

#### 6. Audio Streaming Webhook
**POST** `/webhook/audio`

Receives raw audio bytes from OMI device.

**Query Parameters:**
- `sample_rate` (integer, required): Audio sample rate (8000-48000)
- `uid` (string, required): User identifier

**Headers:**
- `Content-Type`: `application/octet-stream`

**Request Body:** Raw PCM16 audio bytes

**Response:**
```json
{
  "status": "success",
  "bytes_received": 16000,
  "sample_rate": 16000,
  "buffered": true,
  "buffer_size": 32000
}
```

#### 7. Manual Analysis
**POST** `/api/analyze`

Manually trigger analysis of recent conversations.

**Query Parameters:**
- `limit` (integer, optional): Number of conversations to analyze (1-50, default: 5)

**Response:**
```json
{
  "status": "success",
  "conversations_analyzed": 3,
  "results": [
    {
      "memory_id": 12345,
      "transcript_cleaned": "Cleaned transcript text...",
      "psychological_analysis": {
        "adhd_indicators": 0.2,
        "anxiety_level": 0.1,
        "emotional_tone": "neutral"
      },
      "processing_time": 1.8
    }
  ]
}
```

### Rate Limiting

- Default: 60 requests per minute per client
- Configurable via `RATE_LIMIT_PER_MINUTE` environment variable
- Applies to all webhook endpoints
- Client identified by `uid` parameter or IP address

### Error Codes

| Status Code | Meaning |
|-------------|---------|
| 200 | Success |
| 207 | Partial Success (some steps failed) |
| 400 | Bad Request (invalid parameters) |
| 401 | Unauthorized (invalid signature) |
| 403 | Forbidden (insufficient permissions) |
| 413 | Request Too Large |
| 429 | Rate Limit Exceeded |
| 500 | Internal Server Error |

### Testing API Endpoints

#### Test Memory Webhook
```bash
curl -X POST "http://localhost:8000/webhook/memory?uid=test_user" \
  -H "Content-Type: application/json" \
  -d '{
    "id": 999,
    "created_at": "2025-11-21T15:22:14Z",
    "transcript_segments": [
      {"text": "This is a test transcript", "speaker": "SPEAKER_00", "start": 0, "end": 5}
    ],
    "structured": {"title": "Test", "overview": "Test conversation"}
  }'
```

#### Test Health Check
```bash
curl http://localhost:8000/health
```

#### Test Manual Analysis
```bash
curl -X POST "http://localhost:8000/api/analyze?limit=2"
```

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

### Configuration Issues

#### "Missing GEMINI_API_KEY"
- **Symptom**: `400 API key not valid` error
- **Solution**:
  - Verify `.env` contains `GEMINI_API_KEY=your_key_here`
  - Generate new key at [Google AI Studio](https://aistudio.google.com/app/apikey)
  - Restart server after changing `.env`
  - Check key format (should start with `AIza...`)

#### "Missing OMI credentials"
- **Symptom**: `401 Unauthorized` or connection failures
- **Solution**:
  - Check `OMI_APP_ID`, `OMI_APP_SECRET`, `OMI_USER_UID` in `.env`
  - Verify credentials in [OMI Developer Portal](https://omi.me/developer)
  - Ensure app has "Memory Creation Trigger" capability enabled

#### "Configuration loading failed"
- **Symptom**: Server fails to start with config errors
- **Solution**:
  - Run `python -c "from config.settings import AppSettings; print('OK')"`
  - Check for syntax errors in `.env` file
  - Ensure all required environment variables are set
  - Verify file permissions on `.env`

### API and Service Issues

#### Gemini API Errors

**429 Too Many Requests**
- **Cause**: Rate limit exceeded (15 req/min for Flash, 2 req/min for Pro)
- **Solution**:
  - Wait 1 minute before retrying
  - Implement exponential backoff in your code
  - Consider upgrading to paid tier for higher limits

**500 Internal Server Error**
- **Cause**: Gemini service temporarily unavailable
- **Solution**:
  - Check [Google Cloud Status](https://status.cloud.google.com/)
  - Try fallback model (Flash → Pro → Lite)
  - Implement retry logic with backoff

**400 Bad Request**
- **Cause**: Invalid request format or unsupported model
- **Solution**:
  - Verify model name (`gemini-pro`, `gemini-flash`, etc.)
  - Check request payload structure
  - Update to latest API version

#### OMI API Errors

**403 Forbidden**
- **Cause**: Insufficient permissions or invalid app configuration
- **Solution**:
  - Verify user has enabled your app in OMI settings
  - Check app capabilities in OMI Developer Portal
  - Ensure webhook URL is correctly configured

**401 Unauthorized**
- **Cause**: Invalid or expired credentials
- **Solution**:
  - Regenerate app secret in OMI Developer Portal
  - Update credentials in `.env`
  - Check for special characters in credentials

### Webhook Issues

#### "Webhook not receiving calls"
- **Symptom**: No webhook events from OMI app
- **Solutions**:
  - **Development**: Verify ngrok is running (`ngrok http 8000`)
  - **Production**: Check Railway/Heroku domain is accessible
  - Verify webhook URL in OMI app matches exactly
  - Ensure OMI app is in Developer Mode
  - Check server logs for incoming requests
  - Test endpoint manually: `curl https://your-domain.com/health`

#### "Invalid webhook signature"
- **Symptom**: `401 Invalid signature` in logs
- **Solution**:
  - Set `WEBHOOK_SECRET` in environment variables
  - Ensure same secret is configured in OMI Developer Portal
  - Check timestamp validation (requests older than 5 minutes are rejected)

#### "Rate limit exceeded"
- **Symptom**: `429 Too Many Requests`
- **Solution**:
  - Increase `RATE_LIMIT_PER_MINUTE` in settings
  - Implement queuing for high-volume scenarios
  - Check for webhook loops or misconfigurations

### Google Workspace Integration

#### "Gmail API not initialized"
- **Symptom**: Workspace automation features not working
- **Solution**:
  - Complete OAuth2 setup (see Setup section)
  - Run authentication flow: server will open browser for login
  - Verify `config/client_secret.json` exists and is valid
  - Check Google Cloud Console for enabled APIs

#### "OAuth2 token expired"
- **Symptom**: Authentication errors after some time
- **Solution**:
  - Delete `config/token.json` to force re-authentication
  - Re-run the authentication flow
  - Check token refresh logic in code

### Server and Performance Issues

#### "Server won't start"
- **Symptom**: Port binding errors or immediate crashes
- **Solutions**:
  - Check if port 8000 is available: `lsof -i :8000`
  - Change port: `export WEBHOOK_PORT=8080`
  - Verify Python dependencies: `pip check`
  - Check system resources (memory, disk space)

#### "High memory usage"
- **Symptom**: Server consuming excessive RAM
- **Solution**:
  - Monitor with `/performance` endpoint
  - Implement memory limits in Docker/container config
  - Check for memory leaks in long-running processes
  - Consider horizontal scaling

#### "Slow response times"
- **Symptom**: Webhook processing takes too long
- **Solution**:
  - Check Gemini API response times
  - Monitor with `/performance` endpoint
  - Optimize database queries if applicable
  - Consider async processing for heavy operations

### Deployment Issues

#### Railway/Heroku Deployment Fails
- **Symptom**: Build fails in cloud platform
- **Solutions**:
  - Check build logs for specific errors
  - Ensure `requirements.txt` includes all dependencies
  - Verify environment variables are set correctly
  - Check Python version compatibility

#### Docker Container Issues
- **Symptom**: Container won't start or crashes
- **Solutions**:
  - Check Docker logs: `docker logs <container_id>`
  - Verify environment file mounting
  - Check port mapping and networking
  - Ensure proper file permissions

### Logging and Debugging

#### Enable Debug Logging
```bash
# Set in .env or environment
LOG_LEVEL=DEBUG
DEBUG=true
```

#### Monitor Logs
```bash
# Development
tail -f logs/webhook_server.log

# Production (Railway/Heroku)
# Check platform-specific log commands
```

#### Performance Monitoring
```bash
# Check server health
curl https://your-domain.com/health

# Get performance stats
curl https://your-domain.com/performance
```

### Common Development Issues

#### "Module not found" errors
- **Solution**: Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

#### "Permission denied" on files
- **Solution**: Check file permissions in project directory
- Ensure write access to `logs/` and `config/` directories

#### Git/Repository Issues
- **Solution**: Check `.gitignore` includes sensitive files
- Never commit `.env` or `config/token.json`

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
