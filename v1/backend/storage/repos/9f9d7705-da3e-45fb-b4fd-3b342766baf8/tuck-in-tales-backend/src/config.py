import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import Optional

# Load environment variables from .env file
# Make sure this runs before importing Settings elsewhere if using .env
load_dotenv()

class Settings(BaseSettings):
    # Supabase credentials
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    SUPABASE_BUCKET_PHOTOS: str = "photos" # Default value if not set in env
    SUPABASE_BUCKET_AVATARS: str = "avatars" # Default value if not set in env
    AVATARS_BUCKET: str = "avatars" # ADDED: Public bucket for generated avatars

    # OpenAI API Key
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Embedding model
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    # Edit model
    OPENAI_EDIT_MODEL: str = os.getenv("OPENAI_EDIT_MODEL", "gpt-image-1")
    OPENAI_IMAGE_MODEL: str = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    # Chat model
    OPENAI_CHAT_MODEL: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini") # Defaulting to gpt-4o-mini

    # Firebase Admin SDK Credentials
    FIREBASE_SERVICE_ACCOUNT_KEY_PATH: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_PATH", "firebase-service-account.json")

    # Groq
    GROQ_API_KEY: Optional[str] = None # Optional Groq key
    GROQ_VISION_MODEL: str = "llava-v1.5-7b-4096-preview" # Default vision model
    # Example of another model: "meta-llama/llama-4-scout-17b-16e-instruct" (Check Groq docs for vision support)

    # Gemini
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", "")
    GEMINI_IMAGE_MODEL: str = os.getenv("GEMINI_IMAGE_MODEL", "gemini-1.5-flash")

    # Image Generation Provider Selection
    IMAGE_GENERATION_PROVIDER: str = os.getenv("IMAGE_GENERATION_PROVIDER", "OPENAI").upper()
    
    # Add other settings as needed (e.g., FIREBASE_CONFIG)

    class Config:
        # If using a .env file:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore" # Ignore extra fields from env file if any

# Create a single settings instance to be used throughout the app
settings = Settings() 