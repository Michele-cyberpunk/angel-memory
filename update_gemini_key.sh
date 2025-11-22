#!/bin/bash
# Script per aggiornare la Gemini API key compromessa

echo "🔐 Aggiornamento Gemini API Key"
echo "================================"
echo ""
echo "IMPORTANTE: Prima di continuare, genera una nuova API key da:"
echo "https://aistudio.google.com/app/apikey"
echo ""
read -p "Hai già generato la nuova API key? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Genera prima la nuova API key, poi ritorna qui."
    exit 1
fi

echo ""
read -p "Inserisci la NUOVA Gemini API key: " NEW_API_KEY

if [ -z "$NEW_API_KEY" ]; then
    echo "❌ API key non può essere vuota!"
    exit 1
fi

if [ ${#NEW_API_KEY} -lt 30 ]; then
    echo "❌ API key troppo corta, verifica di aver copiato tutto!"
    exit 1
fi

echo ""
echo "📡 Aggiornamento Railway..."
cd "/home/ai/Scaricati/Angel Memory"

railway variables --set "GEMINI_API_KEY=$NEW_API_KEY"

if [ $? -eq 0 ]; then
    echo "✅ API key aggiornata su Railway!"
    echo ""
    echo "📝 Aggiorno anche .env locale..."

    # Backup .env
    cp .env .env.backup

    # Update .env
    sed -i "s/^GEMINI_API_KEY=.*/GEMINI_API_KEY=$NEW_API_KEY/" .env

    echo "✅ .env aggiornato (backup salvato in .env.backup)"
    echo ""
    echo "⏳ Railway sta facendo il redeploy (circa 30-60 secondi)..."
    echo ""
    echo "🧪 Tra 60 secondi puoi testare con:"
    echo "   curl https://angel-memory-production.up.railway.app/health"
    echo ""
    echo "✅ COMPLETATO! Il sistema sarà operativo tra 1 minuto."
else
    echo "❌ Errore durante l'aggiornamento. Verifica:"
    echo "   1. Sei connesso a Railway (railway login)"
    echo "   2. Sei nella directory corretta"
    echo "   3. Il progetto è linkato (railway link)"
fi
