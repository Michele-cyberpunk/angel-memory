#!/usr/bin/env python3
"""
Generate client_secret.json and token.json from environment variables
Run this on Railway startup to configure OAuth
"""
import os
import json
import base64
from pathlib import Path

def setup_oauth_credentials():
    """Generate client_secret.json from environment variables"""

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

    if not all([client_id, client_secret, redirect_uri]):
        print("⚠️  Missing OAuth environment variables")
        return False

    # Determine project ID from client ID (it's in the prefix)
    # Format: PROJECT_NUMBER-HASH.apps.googleusercontent.com
    project_id = "gen-lang-client-0003881093"  # Default from client_secret

    client_secret_data = {
        "web": {
            "client_id": client_id,
            "project_id": project_id,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret,
            "redirect_uris": [redirect_uri, "http://localhost:8080/"]
        }
    }

    # Ensure config directory exists
    config_dir = Path(__file__).parent.parent / "config"
    config_dir.mkdir(exist_ok=True)

    # Write client_secret.json
    client_secret_file = config_dir / "client_secret.json"
    with open(client_secret_file, 'w') as f:
        json.dump(client_secret_data, f, indent=2)

    print(f"✅ Generated {client_secret_file}")
    return True

def setup_oauth_token():
    """Decode and write token.json from base64 environment variable"""

    token_b64 = os.getenv("GOOGLE_TOKEN_B64")

    if not token_b64:
        print("⚠️  GOOGLE_TOKEN_B64 not set, skipping token setup")
        return False

    try:
        # Decode base64 token
        token_data = base64.b64decode(token_b64)

        # Ensure config directory exists
        config_dir = Path(__file__).parent.parent / "config"
        config_dir.mkdir(exist_ok=True)

        # Write token.json (binary pickle file)
        token_file = config_dir / "token.json"
        with open(token_file, 'wb') as f:
            f.write(token_data)

        print(f"✅ Generated {token_file}")
        return True

    except Exception as e:
        print(f"❌ Failed to decode token: {e}")
        return False

if __name__ == "__main__":
    creds_success = setup_oauth_credentials()
    token_success = setup_oauth_token()

    # Exit 0 if at least client_secret was created
    exit(0 if creds_success else 1)
