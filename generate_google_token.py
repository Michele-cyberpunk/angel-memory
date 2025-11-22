#!/usr/bin/env python3
"""
Script per generare token.json di autenticazione Google OAuth2
Esegui questo script UNA VOLTA per autorizzare l'accesso a Gmail/Calendar
"""
import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Se modifichi questi scopes, elimina token.json e rigenera
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/presentations'
]

def main():
    creds = None
    token_file = 'config/token.json'
    client_secret_file = 'config/client_secret.json'

    # Controlla se esiste già un token
    if os.path.exists(token_file):
        print(f"Token già esistente: {token_file}")
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)

    # Se non ci sono credenziali valide, fai login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Token scaduto, refresh in corso...")
            creds.refresh(Request())
        else:
            if not os.path.exists(client_secret_file):
                print(f"❌ File {client_secret_file} non trovato!")
                print("Assicurati che il file esista.")
                return

            print("📝 Avvio flusso OAuth2...")
            print("Si aprirà una finestra del browser per il login Google")
            print("Accedi con: michele.biology@gmail.com")
            print()

            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_file, SCOPES)
            creds = flow.run_local_server(port=8080)

        # Salva il token per la prossima volta
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)

        print(f"✅ Token salvato in {token_file}")
        print("✅ Autenticazione completata!")
        print()
        print("Ora puoi usare Gmail/Calendar automation.")
    else:
        print("✅ Token valido già presente")
        print(f"Email: {creds._id_token.get('email') if hasattr(creds, '_id_token') else 'N/A'}")

if __name__ == '__main__':
    main()
