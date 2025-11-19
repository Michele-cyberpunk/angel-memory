# OMI-Gemini Integration - Webhook Info

## Deployment Info (Railway)

**Production URL:** `https://omi-gemini-integration-production.up.railway.app`

**Project ID:** `eef20211-dc0e-417a-8ad9-dcb9b86702f7`
**Service ID:** `1a101a72-2767-4609-b3d0-653fa953bd98`

**Latest Commit:** `506292b` - Fix OMI API 422 error: add required 'text' field and correct text_source

**Deployed:** 2025-11-19
**Status:** Active and tested

---

## Webhook Endpoints

### 1. Health Check
```
GET https://omi-gemini-integration-production.up.railway.app/health
```

Response:
```json
{
    "status": "healthy",
    "orchestrator_initialized": true,
    "timestamp": "2025-11-19T20:26:54Z"
}
```

### 2. Memory Creation Webhook (OMI Integration)
```
POST https://omi-gemini-integration-production.up.railway.app/webhook/memory?uid={USER_UID}
```

**Your UID:** `TcKWu3rCazPZc4GgmZY9jNcx7wH3`

**Full endpoint for OMI app:**
```
https://omi-gemini-integration-production.up.railway.app/webhook/memory?uid=TcKWu3rCazPZc4GgmZY9jNcx7wH3
```

**Expected payload:** OMI memory object with transcript_segments

**Test result (2025-11-19 20:23):**
```json
{
    "status": "success",
    "message": "Processed 5 steps",
    "details": {
        "steps_completed": [
            "transcript_extracted",
            "transcript_cleaned",
            "psychological_analysis",
            "memory_saved",
            "notification_sent"
        ],
        "errors": []
    }
}
```

### 3. Real-time Transcript Webhook
```
POST https://omi-gemini-integration-production.up.railway.app/webhook/transcript?uid={USER_UID}
```

### 4. Audio Stream Webhook
```
POST https://omi-gemini-integration-production.up.railway.app/webhook/audio?uid={USER_UID}
```

---

## What This Webhook Does

1. Receives conversation transcript from OMI app
2. Cleans transcript using Gemini AI (2.5-pro/flash/flash-lite)
3. Performs psychological analysis (ADHD/anxiety patterns)
4. Saves analysis back to OMI as new memory
5. Sends push notification to OMI app

---

## Integration with OMI App

Configure in OMI app settings:
- **Webhook URL:** `https://omi-gemini-integration-production.up.railway.app/webhook/memory?uid=TcKWu3rCazPZc4GgmZY9jNcx7wH3`
- **Event:** Memory Created
- **Method:** POST
- **Content-Type:** application/json

---

## Fixed Issues

**422 Error (Fixed 2025-11-19):**
- Added required 'text' field to OMI API memory creation
- Changed text_source from "integration" to "other" (valid value)
- Files modified: `modules/orchestrator.py`, `modules/omi_client.py`

---

## Data Storage

**All data is stored on OMI Cloud (persistent)**
- Cleaned transcripts: saved as OMI memories
- Analysis results: saved as OMI memories with tags
- No local storage on Railway (ephemeral filesystem)

---

## Environment Variables (Configured on Railway)

- `OMI_APP_ID`: 01K76TYMGYY3EHAPDVKJ91VN9A
- `OMI_USER_UID`: TcKWu3rCazPZc4GgmZY9jNcx7wH3
- `GEMINI_API_KEY`: (configured)
- `OMI_APP_SECRET`: (configured)
- `OMI_BASE_URL`: https://api.omi.me

---

**Last Updated:** 2025-11-19 20:27 UTC
**Status:** Production ready, fully tested
