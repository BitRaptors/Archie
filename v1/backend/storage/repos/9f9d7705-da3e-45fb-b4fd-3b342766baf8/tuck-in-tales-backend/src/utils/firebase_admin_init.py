import firebase_admin
from firebase_admin import credentials
from src.config import settings
import os

def initialize_firebase_admin():
    """Initializes the Firebase Admin SDK using service account credentials."""
    cred_path = settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH
    if not os.path.exists(cred_path):
        print(f"WARNING: Firebase service account key not found at {cred_path}. Firebase Admin SDK not initialized.")
        # Potentially raise an error if Firebase Auth is strictly required
        # raise FileNotFoundError(f"Firebase service account key not found at {cred_path}")
        return

    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialized successfully.")
    except Exception as e:
        print(f"Error initializing Firebase Admin SDK: {e}")
        # Handle initialization error appropriately
        raise

# Initialize on import (or call this explicitly from main.py startup event)
# Initializing here ensures it runs once when the module is first imported.
initialize_firebase_admin() 