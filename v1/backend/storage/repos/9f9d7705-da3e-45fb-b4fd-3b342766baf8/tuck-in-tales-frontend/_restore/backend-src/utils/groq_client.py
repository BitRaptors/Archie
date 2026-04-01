import os
import logging
from groq import Groq, GroqError
from dotenv import load_dotenv
from typing import Optional

# Load environment variables from .env file
load_dotenv()

# Get API key from environment
groq_api_key = os.getenv("GROQ_API_KEY")

# Initialize Groq client globally or via a function
# Global instance:
async_groq_client: Optional[Groq] = None

if groq_api_key:
    try:
        async_groq_client = Groq(api_key=groq_api_key)
        logging.info("Groq client initialized successfully.")
    except GroqError as e:
        logging.error(f"Failed to initialize Groq client: {e}")
        async_groq_client = None
    except Exception as e:
        logging.error(f"An unexpected error occurred initializing Groq client: {e}")
        async_groq_client = None
else:
    logging.warning("GROQ_API_KEY environment variable not found. Groq client not initialized.")
    async_groq_client = None # Ensure it's None if key is missing

# Optional: Function to get the client instance (useful if initialization is deferred)
def get_groq_client() -> Optional[Groq]:
    """Returns the initialized Groq client instance, if available."""
    if not async_groq_client:
        # Maybe try to re-initialize here if appropriate, or just warn
        logging.warning("Attempted to get Groq client, but it was not initialized.")
    return async_groq_client

# Example of how to potentially handle async initialization if needed later
# async def initialize_groq_client():
#     global async_groq_client
#     api_key = os.getenv("GROQ_API_KEY")
#     if api_key and not async_groq_client:
#         try:
#             async_groq_client = Groq(api_key=api_key) # Assuming Groq client is async compatible
#             logging.info("Async Groq client initialized.")
#         except Exception as e:
#             logging.error(f"Failed to initialize async Groq client: {e}")
#     elif not api_key:
#          logging.warning("GROQ_API_KEY missing for async init.")

# Note: Ensure environment variables are loaded before this module is imported elsewhere.
# Placing load_dotenv() at the top helps achieve this. 