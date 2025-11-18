#!/usr/bin/env python3
"""
Script to verify all API keys are configured correctly
"""
import sys
import os

# Add project to path
sys.path.insert(0, '/home/ai/omi-gemini-integration')

from config.settings import OMIConfig, GeminiConfig, GoogleWorkspaceConfig
import requests
import google.generativeai as genai

def check_omi_credentials():
    """Verify OMI credentials"""
    print("\n" + "="*60)
    print("🔍 CHECKING OMI CREDENTIALS")
    print("="*60)

    try:
        print(f"OMI_APP_ID: {OMIConfig.APP_ID[:20]}... ({'✅ SET' if OMIConfig.APP_ID else '❌ MISSING'})")
        print(f"OMI_APP_SECRET: {OMIConfig.APP_SECRET[:10]}... ({'✅ SET' if OMIConfig.APP_SECRET else '❌ MISSING'})")
        print(f"OMI_USER_UID: {OMIConfig.USER_UID[:20]}... ({'✅ SET' if OMIConfig.USER_UID else '❌ MISSING'})")
        print(f"OMI_BASE_URL: {OMIConfig.BASE_URL}")

        # Test API connectivity
        url = f"{OMIConfig.BASE_URL}/v2/integrations/{OMIConfig.APP_ID}/memories"
        headers = {"Authorization": f"Bearer {OMIConfig.APP_SECRET}"}
        params = {"uid": OMIConfig.USER_UID, "limit": 1}

        print("\n📡 Testing OMI API connectivity...")
        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            print("✅ OMI API: CONNECTED")
            data = response.json()
            print(f"   Retrieved {len(data)} memories")
            return True
        elif response.status_code == 401:
            print("❌ OMI API: UNAUTHORIZED (invalid credentials)")
            return False
        elif response.status_code == 403:
            print("⚠️  OMI API: FORBIDDEN (check app permissions)")
            return False
        else:
            print(f"⚠️  OMI API: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ OMI API Error: {str(e)}")
        return False

def check_gemini_credentials():
    """Verify Gemini API key"""
    print("\n" + "="*60)
    print("🔍 CHECKING GEMINI CREDENTIALS")
    print("="*60)

    api_key = GeminiConfig.API_KEY

    if not api_key:
        print("❌ GEMINI_API_KEY: NOT SET")
        print("\n📝 To get a Gemini API key:")
        print("1. Go to: https://aistudio.google.com/app/apikey")
        print("2. Click 'Create API Key'")
        print("3. Copy the key (starts with 'AIza...')")
        print("4. Update .env file: GEMINI_API_KEY=<your_key>")
        return False

    print(f"GEMINI_API_KEY: {api_key[:15]}... ✅ SET")

    # Test API
    try:
        print("\n📡 Testing Gemini API connectivity...")
        genai.configure(api_key=api_key)

        # Try to list models
        models = list(genai.list_models())

        if models:
            print(f"✅ GEMINI API: CONNECTED")
            print(f"   Available models: {len(models)}")

            # Check specific models we need
            model_names = [m.name for m in models]
            print("\n   Checking required models:")

            primary = GeminiConfig.PRIMARY_MODEL
            if any(primary in m for m in model_names):
                print(f"   ✅ {primary}")
            else:
                print(f"   ⚠️  {primary} (not found, will use fallback)")

            fallback = GeminiConfig.FALLBACK_MODEL
            if any(fallback in m for m in model_names):
                print(f"   ✅ {fallback}")
            else:
                print(f"   ❌ {fallback} (not available)")

            lite = GeminiConfig.LITE_MODEL
            if any(lite in m for m in model_names):
                print(f"   ✅ {lite}")
            else:
                print(f"   ❌ {lite} (not available)")

            return True
        else:
            print("⚠️  GEMINI API: Connected but no models available")
            return False

    except Exception as e:
        error_msg = str(e)

        if "API_KEY_INVALID" in error_msg or "API key not valid" in error_msg:
            print("❌ GEMINI API: INVALID KEY")
            print("\n📝 Your API key is invalid. Please:")
            print("1. Go to: https://aistudio.google.com/app/apikey")
            print("2. Generate a NEW API key")
            print("3. Update .env: GEMINI_API_KEY=<new_key>")
        elif "quota" in error_msg.lower():
            print("⚠️  GEMINI API: QUOTA EXCEEDED")
        else:
            print(f"❌ GEMINI API Error: {error_msg}")

        return False

def check_google_workspace():
    """Check Google Workspace OAuth setup"""
    print("\n" + "="*60)
    print("🔍 CHECKING GOOGLE WORKSPACE (OPTIONAL)")
    print("="*60)

    client_secret = GoogleWorkspaceConfig.CLIENT_SECRET_FILE
    token_file = GoogleWorkspaceConfig.TOKEN_FILE

    if os.path.exists(client_secret):
        print(f"✅ client_secret.json: FOUND")
    else:
        print(f"⏳ client_secret.json: NOT FOUND (optional)")
        print("   For Gmail/Calendar/Slides automation, create OAuth credentials:")
        print("   https://console.cloud.google.com/apis/credentials")

    if os.path.exists(token_file):
        print(f"✅ token.json: FOUND (authenticated)")
        return True
    else:
        print(f"⏳ token.json: NOT FOUND (not authenticated yet)")
        return False

def main():
    """Run all checks"""
    print("\n" + "="*60)
    print("🔑 API KEY VERIFICATION TOOL")
    print("="*60)

    results = {
        "omi": False,
        "gemini": False,
        "workspace": False
    }

    # Check all credentials
    results["omi"] = check_omi_credentials()
    results["gemini"] = check_gemini_credentials()
    results["workspace"] = check_google_workspace()

    # Summary
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)

    print(f"\nOMI Integration API: {'✅ READY' if results['omi'] else '❌ FAILED'}")
    print(f"Gemini AI API: {'✅ READY' if results['gemini'] else '❌ FAILED'}")
    print(f"Google Workspace: {'✅ READY' if results['workspace'] else '⏳ OPTIONAL'}")

    # Overall status
    print("\n" + "-"*60)

    if results["omi"] and results["gemini"]:
        print("✅ SYSTEM READY - Core functionality available")
        print("\nYou can now:")
        print("1. Start webhook server: python webhook_server.py")
        print("2. Expose with ngrok: ngrok http 8000")
        print("3. Configure OMI app with webhook URL")
        return 0
    else:
        print("⚠️  CONFIGURATION INCOMPLETE")
        print("\nRequired fixes:")

        if not results["omi"]:
            print("❌ OMI credentials need verification")
        if not results["gemini"]:
            print("❌ Gemini API key needs to be updated")

        print("\nSee instructions above for each failed check.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
