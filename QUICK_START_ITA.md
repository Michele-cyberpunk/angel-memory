# Angel Memory - Quick Start Italiano

## 🚨 ATTENZIONE - AZIONE IMMEDIATA RICHIESTA

La tua Gemini API key è stata **compromessa** e disabilitata da Google.

### Cosa fare SUBITO:

#### 1. Genera nuova API key (2 minuti)
1. Vai su: https://aistudio.google.com/app/apikey
2. Clicca su "Create API key"
3. Copia la nuova key generata
4. ELIMINA la vecchia key compromessa dalla lista

#### 2. Aggiorna Railway (1 minuto)
```bash
cd "/home/ai/Scaricati/Angel Memory"
railway variables --set "GEMINI_API_KEY=LA_TUA_NUOVA_API_KEY_QUI"
```

#### 3. Aggiorna .env locale (opzionale)
```bash
nano .env
# Cambia la riga GEMINI_API_KEY con la nuova key
```

#### 4. Testa che funzioni
```bash
# Attendi 30 secondi per il redeploy automatico, poi:
curl -X POST "https://angel-memory-production.up.railway.app/webhook/memory?uid=TcKWu3rCazPZc4GgmZY9jNcx7wH3" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test_001",
    "transcript_segments": [
      {"text": "Test funzionamento", "start": 0.0, "end": 2.0}
    ]
  }'
```

Se vedi `"status": "success"` senza warning → TUTTO OK! ✅

---

## 📍 Il Tuo Deployment

**URL Server:** https://angel-memory-production.up.railway.app/
**GitHub:** https://github.com/Michele-cyberpunk/angel-memory
**Status:** 🟢 ONLINE (ma API key da aggiornare)

---

## 🔗 Webhook URLs per OMI

Configura questi URL nell'app OMI (Developer Settings):

**Memory Creation:**
```
https://angel-memory-production.up.railway.app/webhook/memory?uid=TcKWu3rCazPZc4GgmZY9jNcx7wH3
```

**Realtime Processing:**
```
https://angel-memory-production.up.railway.app/webhook/realtime?uid=TcKWu3rCazPZc4GgmZY9jNcx7wH3
```

**Audio Processing:**
```
https://angel-memory-production.up.railway.app/webhook/audio?uid=TcKWu3rCazPZc4GgmZY9jNcx7wH3
```

---

## ✅ Cosa è già pronto

- ✅ Server deployato e funzionante su Railway
- ✅ Repository GitHub pubblicato e sincronizzato
- ✅ Tutte le variabili d'ambiente configurate
- ✅ Webhook endpoints attivi e testati
- ✅ Health checks e monitoring operativi
- ✅ Rate limiting e security attivi
- ⚠️ Solo API key Gemini da aggiornare

---

## 🧪 Test Rapidi

### Health Check
```bash
curl https://angel-memory-production.up.railway.app/health | jq
```

Deve rispondere `"overall_status": "healthy"`

### Test Webhook
```bash
curl -X POST "https://angel-memory-production.up.railway.app/webhook" \
  -H "Content-Type: application/json" \
  -d '{"test": "hello"}'
```

Deve rispondere `{"status": "received", ...}`

---

## 📊 Comandi Utili

### Vedere logs in tempo reale
```bash
cd "/home/ai/Scaricati/Angel Memory"
railway logs
```

### Aggiornare una variabile
```bash
railway variables --set "NOME_VARIABILE=valore"
```

### Vedere tutte le variabili
```bash
railway variables --kv
```

### Forzare un redeploy
```bash
railway up
```

---

## 🆘 Troubleshooting

### Il webhook non risponde
1. Controlla health: `curl https://angel-memory-production.up.railway.app/health`
2. Vedi logs: `railway logs`
3. Verifica variabili: `railway variables --kv`

### Errori Gemini API
→ Assicurati di aver aggiornato GEMINI_API_KEY con key valida

### 403 Forbidden
→ Controlla che OMI_APP_SECRET e OMI_DEV_KEY siano corretti

---

## 📖 Documentazione Completa

Vedi `DEPLOYMENT_STATUS.md` per dettagli completi su:
- Architettura del sistema
- Formato payload webhooks
- Metriche e monitoring
- Cronologia deployment
- Troubleshooting avanzato

---

**Tempo stimato per fix API key:** 3 minuti totali
**Dopo il fix:** Sistema completamente operativo e pronto per OMI! 🚀
