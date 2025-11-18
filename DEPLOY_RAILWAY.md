# Deploy su Railway - OMI-Gemini Integration

## Perché Railway

✅ HTTPS automatico con certificato SSL
✅ Deploy diretto da GitHub
✅ Environment variables integrate
✅ Logs in tempo reale
✅ 500 ore/mese gratuite ($5 credit)
✅ **NO processi locali** - tutto in cloud

---

## Step 1: Preparazione Repository Git

```bash
cd /home/ai/omi-gemini-integration

# Inizializza git se non già fatto
git init

# Add all files
git add .
git commit -m "Initial commit - OMI-Gemini webhook server"

# Create GitHub repository (se non esiste)
gh repo create omi-gemini-integration --private --source=. --remote=origin --push
```

## Step 2: Deploy su Railway

### Opzione A: Deploy con Railway CLI (Raccomandato)

```bash
# Installa Railway CLI
npm install -g @railway/cli

# Login
railway login

# Create new project
railway init

# Add environment variables
railway variables set OMI_APP_ID=01K76TYMGYY3EHAPDVKJ91VN9A
railway variables set OMI_APP_SECRET=sk_9c9bc22d4d61a870d5188c84ac7e6640
railway variables set OMI_USER_UID=TcKWu3rCazPZc4GgmZY9jNcx7wH3
railway variables set GEMINI_API_KEY=AIzaSyAnmX8MIzQhGgIYGaYQTB54QRZyfb5i0ec
railway variables set OMI_BASE_URL=https://api.omi.me
railway variables set GEMINI_PRIMARY_MODEL=gemini-2.0-flash-exp
railway variables set GEMINI_FALLBACK_MODEL=gemini-2.5-flash
railway variables set GEMINI_LITE_MODEL=gemini-2.5-flash-lite
railway variables set LOG_LEVEL=INFO
railway variables set DEBUG=false

# Deploy
railway up

# Get public URL
railway domain
```

### Opzione B: Deploy via Web Dashboard

1. Vai su [railway.app](https://railway.app)
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Autorizza Railway su GitHub
4. Seleziona repository `omi-gemini-integration`
5. Railway rileva automaticamente Python e FastAPI
6. Vai a **Settings → Variables**
7. Copia TUTTE le variabili da `.railway-env`:
   ```
   OMI_APP_ID=01K76TYMGYY3EHAPDVKJ91VN9A
   OMI_APP_SECRET=sk_9c9bc22d4d61a870d5188c84ac7e6640
   OMI_USER_UID=TcKWu3rCazPZc4GgmZY9jNcx7wH3
   GEMINI_API_KEY=AIzaSyAnmX8MIzQhGgIYGaYQTB54QRZyfb5i0ec
   ...
   ```
8. Click **"Deploy"**
9. Vai a **Settings → Networking → Generate Domain**
10. Copia URL pubblico (es. `https://omi-gemini-production.up.railway.app`)

---

## Step 3: Verifica Deployment

```bash
# Test health endpoint
curl https://YOUR-RAILWAY-URL.railway.app/health

# Expected output:
# {"status":"healthy","orchestrator_initialized":true,"timestamp":"..."}
```

---

## Step 4: Configurazione OMI App

1. Apri OMI app → Settings → Developer Mode
2. Abilita Developer Mode
3. Imposta webhook URL:
   ```
   https://YOUR-RAILWAY-URL.railway.app/webhook/memory
   ```
4. Salva configurazione

---

## Step 5: Test End-to-End

### Test Manuale con curl

```bash
curl -X POST "https://YOUR-RAILWAY-URL.railway.app/webhook/memory?uid=TcKWu3rCazPZc4GgmZY9jNcx7wH3" \
  -H "Content-Type: application/json" \
  -d '{
    "id": 999,
    "created_at": "2025-11-18T23:00:00Z",
    "transcript_segments": [
      {
        "text": "Test transcript with some umm filler words",
        "speaker": "SPEAKER_00",
        "start": 0.0,
        "end": 3.0
      }
    ],
    "structured": {
      "title": "Test Memory",
      "overview": "Test"
    }
  }'
```

### Test Reale con OMI App

1. Crea una nuova memoria nell'app OMI
2. Verifica nei Railway logs:
   - Dashboard → **Deployments** → Click deployment → **View Logs**
3. Dovresti vedere:
   - Webhook ricevuto
   - Trascritto pulito da Gemini
   - Analisi psicologica completata
   - Nuova memoria creata
   - Notifica inviata

---

## Monitoring

### Railway Dashboard

- **Logs**: Real-time application logs
- **Metrics**: CPU, Memory, Network usage
- **Deployments**: Deployment history

### Comandi CLI

```bash
# View logs
railway logs

# Check status
railway status

# Redeploy
railway up --detach
```

---

## Troubleshooting

### Build failed

```bash
# Check build logs in Railway dashboard
# Verify requirements.txt is up to date
# Ensure Python 3.12 is specified in runtime.txt
```

### Environment variables not loaded

```bash
# Verify all vars are set in Railway dashboard
railway variables

# Reload deployment
railway up --detach
```

### Webhook not receiving calls

1. Verify Railway URL is accessible: `curl https://YOUR-URL/health`
2. Check OMI app webhook configuration matches Railway URL
3. Verify Developer Mode is enabled in OMI app

---

## Costi

**Railway Free Tier:**
- $5 credit/mese
- 500 ore di esecuzione
- 1 GB RAM
- Shared CPU

**Stima utilizzo OMI-Gemini:**
- ~100 ore/mese (sempre attivo)
- ~200 MB RAM
- **Costo: $0-2/mese**

---

## Files Importanti per Deploy

- ✅ `railway.json` - Configurazione Railway
- ✅ `Procfile` - Start command
- ✅ `runtime.txt` - Versione Python
- ✅ `nixpacks.toml` - Build configuration
- ✅ `requirements.txt` - Dipendenze Python
- ✅ `.railway-env` - Template environment variables
- ✅ `.gitignore` - Files da NON committare

---

**Ready for deployment!**

Tutto è configurato per deploy immediato su Railway con HTTPS automatico e zero configurazione locale.
