#!/bin/bash
# Script to update Gemini API key in .env file

echo "======================================================"
echo "🔑 GEMINI API KEY UPDATE SCRIPT"
echo "======================================================"
echo ""
echo "Opening Google AI Studio in browser..."
echo ""

# Open browser
firefox --new-tab "https://aistudio.google.com/app/apikey" 2>/dev/null &

echo "📝 INSTRUCTIONS:"
echo "1. Login with your Google account"
echo "2. Click 'Create API Key' button"
echo "3. Select or create a Google Cloud project"
echo "4. Copy the generated API key (starts with 'AIza...')"
echo ""
echo "======================================================"
echo ""

read -p "Enter your NEW Gemini API key: " NEW_KEY

if [ -z "$NEW_KEY" ]; then
    echo "❌ No key provided. Exiting."
    exit 1
fi

# Validate format (basic check)
if [[ ! $NEW_KEY =~ ^AIza ]]; then
    echo "⚠️  Warning: API key doesn't start with 'AIza'. Are you sure this is correct?"
    read -p "Continue anyway? (y/n): " CONFIRM
    if [ "$CONFIRM" != "y" ]; then
        echo "Cancelled."
        exit 1
    fi
fi

# Update .env file
ENV_FILE="/home/ai/omi-gemini-integration/.env"

echo ""
echo "Updating $ENV_FILE..."

# Create backup
cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"

# Update key
sed -i "s/^GEMINI_API_KEY=.*/GEMINI_API_KEY=$NEW_KEY/" "$ENV_FILE"

echo "✅ API key updated successfully!"
echo ""
echo "======================================================"
echo "🧪 TESTING NEW KEY..."
echo "======================================================"
echo ""

# Test the new key
cd /home/ai/omi-gemini-integration
source venv/bin/activate
python scripts/check_api_keys.py

exit $?
